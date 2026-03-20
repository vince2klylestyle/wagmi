"""
Single-Signal Trade Audit Module.

Extracts and analyzes single-signal trades (only 1 strategy fires) from the
trade ledger. These represent highest-conviction setups and are the focus of
the agent swarm optimization system.

Single-signal trades are often the highest-edge trades because they represent
one strategy with very strong conviction, rather than a committee consensus.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger("bot.feedback.single_signal_audit")


@dataclass
class SingleSignalTrade:
    """A single-strategy trade extracted from the ledger."""
    trade_id: str
    timestamp: float  # Unix timestamp
    symbol: str
    side: str  # "BUY" or "SELL"

    entry_price: float
    exit_price: float
    sl: float
    tp1: float
    tp2: float

    regime_1h: str
    regime_4h: str
    single_strategy_name: str
    confidence_score: float  # 0-1

    leverage_applied: float
    hold_duration_minutes: float
    exit_type: str  # "TP1", "TP2", "SL", "trailing", "early_exit", "time_stop"

    net_pnl: float  # Dollar profit/loss
    fees_paid: float
    funding_paid: float  # Negative = we pay, positive = we receive

    session_equity_start: float
    session_drawdown_pct: float
    max_adverse_excursion_pct: float  # Against the trade direction
    max_favorable_excursion_pct: float  # For the trade direction

    # Metadata
    entry_adjustment_used: Optional[str] = None  # "market now", "pullback", "reclaim", etc.
    setup_type: Optional[str] = None  # "momentum", "reversal", "breakout", etc.
    contributing_factors: List[str] = field(default_factory=list)  # ["BTC_strong", "high_volume", etc.]


@dataclass
class PerformanceMetrics:
    """Performance stats for a single-signal setup."""
    pattern_name: str  # e.g., "SOL + regime:trend"
    trade_count: int
    win_count: int
    loss_count: int

    win_rate: float  # 0-1
    avg_win_pct: float
    avg_loss_pct: float
    profit_factor: float  # sum(wins) / abs(sum(losses))
    expectancy_pct: float  # Expected return per trade

    sharpe_ratio: float
    sortino_ratio: float
    max_consecutive_wins: int
    max_consecutive_losses: int
    max_drawdown_pct: float

    avg_hold_minutes: float
    avg_entry_mae_pct: float
    avg_exit_mfe_pct: float

    # Breakdown by regime/symbol if applicable
    breakdown: Dict[str, "PerformanceMetrics"] = field(default_factory=dict)


@dataclass
class SniperSetup:
    """A high-edge single-signal setup worth increasing sizing on."""
    pattern_name: str
    symbol: str
    regime: str
    strategy: str

    sample_size: int
    win_rate: float
    profit_factor: float
    sharpe_ratio: float

    recommended_sizing_multiplier: float  # 1.0 = normal, 1.5 = 50% larger position
    confidence: float  # Agent's confidence this setup is real (vs noise)

    recommended_entry_adjustment: Optional[str] = None
    recommended_exit_style: Optional[str] = None

    notes: str = ""


class SingleSignalAudit:
    """Extracts, analyzes, and reports on single-signal trades."""

    def __init__(self, data_dir: str = "bot/data"):
        self.data_dir = Path(data_dir)
        self.trades: List[SingleSignalTrade] = []
        self.audit_state_file = self.data_dir / "feedback" / "single_signal_audit_state.json"
        self.trades_file = self.data_dir / "feedback" / "single_signal_trades.jsonl"
        self.sniper_setups_file = self.data_dir / "feedback" / "sniper_setups.json"

        # Ensure directories exist
        (self.data_dir / "feedback").mkdir(parents=True, exist_ok=True)

    def extract_single_signals(self, lookback_days: int = 30) -> List[SingleSignalTrade]:
        """Extract all single-signal trades from the ledger in the last N days.

        Args:
            lookback_days: How many days back to analyze

        Returns:
            List of SingleSignalTrade objects
        """
        self.trades = []

        # Try to read from trade ledger
        try:
            from execution.trade_logger import TradeLogger
            logger_instance = TradeLogger()

            cutoff_time = datetime.now() - timedelta(days=lookback_days)
            all_trades = logger_instance.read_recent(limit=None)

            for trade in all_trades:
                if trade.get("timestamp", 0) < cutoff_time.timestamp():
                    continue

                # Check if this is a single-signal trade
                num_agree = trade.get("num_strategies_agreeing", 0)
                if num_agree != 1:
                    continue

                # Extract the single strategy that fired
                contributing_strategies = trade.get("contributing_strategies", [])
                if not contributing_strategies:
                    continue

                single_strategy = contributing_strategies[0]

                # Build SingleSignalTrade object
                sig_trade = SingleSignalTrade(
                    trade_id=trade.get("trade_id", ""),
                    timestamp=float(trade.get("timestamp", 0)),
                    symbol=trade.get("symbol", ""),
                    side=trade.get("side", ""),

                    entry_price=float(trade.get("entry_price", 0)),
                    exit_price=float(trade.get("exit_price", 0)),
                    sl=float(trade.get("sl", 0)),
                    tp1=float(trade.get("tp1", 0)),
                    tp2=float(trade.get("tp2", 0)),

                    regime_1h=trade.get("regime_1h", "unknown"),
                    regime_4h=trade.get("regime_4h", "unknown"),
                    single_strategy_name=single_strategy,
                    confidence_score=float(trade.get("confidence", 0.5)),

                    leverage_applied=float(trade.get("leverage", 1.0)),
                    hold_duration_minutes=float(trade.get("hold_duration_minutes", 0)),
                    exit_type=trade.get("exit_type", "unknown"),

                    net_pnl=float(trade.get("pnl", 0)),
                    fees_paid=float(trade.get("fees", 0)),
                    funding_paid=float(trade.get("funding", 0)),

                    session_equity_start=float(trade.get("equity_start", 0)),
                    session_drawdown_pct=float(trade.get("session_dd_pct", 0)),
                    max_adverse_excursion_pct=float(trade.get("mae_pct", 0)),
                    max_favorable_excursion_pct=float(trade.get("mfe_pct", 0)),

                    entry_adjustment_used=trade.get("entry_adjustment"),
                    setup_type=trade.get("setup_type"),
                    contributing_factors=trade.get("contributing_factors", []),
                )

                self.trades.append(sig_trade)

        except Exception as e:
            logger.debug(f"Could not read from trade ledger: {e}")
            # Fallback: try to read from our own ledger file
            self._load_from_file()

        logger.info(f"[AUDIT] Extracted {len(self.trades)} single-signal trades from last {lookback_days} days")
        return self.trades

    def _load_from_file(self):
        """Load single-signal trades from our own jsonl file."""
        if not self.trades_file.exists():
            return

        try:
            with open(self.trades_file, "r") as f:
                for line in f:
                    if not line.strip():
                        continue
                    trade_dict = json.loads(line)
                    trade = SingleSignalTrade(**trade_dict)
                    self.trades.append(trade)
        except Exception as e:
            logger.debug(f"Error loading trades file: {e}")

    def compute_metrics(self) -> Dict[str, PerformanceMetrics]:
        """Compute performance metrics broken down by various groupings.

        Returns:
            Dict with keys like:
            - "overall": metrics for all single-signal trades
            - "by_strategy": {strategy_name: metrics}
            - "by_regime_1h": {regime: metrics}
            - "by_symbol": {symbol: metrics}
            - "by_entry_adjustment": {adjustment: metrics}
        """
        metrics = {}

        # Overall metrics
        metrics["overall"] = self._compute_metrics_for_trades(
            self.trades, "all single-signal trades"
        )

        # By strategy
        by_strategy = {}
        for strategy in set(t.single_strategy_name for t in self.trades):
            trades = [t for t in self.trades if t.single_strategy_name == strategy]
            by_strategy[strategy] = self._compute_metrics_for_trades(trades, strategy)
        metrics["by_strategy"] = by_strategy

        # By regime
        by_regime = {}
        for regime in set(t.regime_1h for t in self.trades):
            trades = [t for t in self.trades if t.regime_1h == regime]
            by_regime[regime] = self._compute_metrics_for_trades(trades, regime)
        metrics["by_regime_1h"] = by_regime

        # By symbol
        by_symbol = {}
        for symbol in set(t.symbol for t in self.trades):
            trades = [t for t in self.trades if t.symbol == symbol]
            by_symbol[symbol] = self._compute_metrics_for_trades(trades, symbol)
        metrics["by_symbol"] = by_symbol

        # By entry adjustment (if available)
        by_entry = {}
        for adj in set(t.entry_adjustment_used for t in self.trades if t.entry_adjustment_used):
            trades = [t for t in self.trades if t.entry_adjustment_used == adj]
            by_entry[adj] = self._compute_metrics_for_trades(trades, f"entry:{adj}")
        metrics["by_entry_adjustment"] = by_entry

        # By exit type
        by_exit = {}
        for exit_type in set(t.exit_type for t in self.trades):
            trades = [t for t in self.trades if t.exit_type == exit_type]
            by_exit[exit_type] = self._compute_metrics_for_trades(trades, f"exit:{exit_type}")
        metrics["by_exit_type"] = by_exit

        logger.info(f"[AUDIT] Computed metrics for {len(metrics)} breakdowns")
        return metrics

    def _compute_metrics_for_trades(self, trades: List[SingleSignalTrade], name: str) -> PerformanceMetrics:
        """Compute metrics for a list of trades."""
        if not trades:
            return PerformanceMetrics(
                pattern_name=name,
                trade_count=0, win_count=0, loss_count=0,
                win_rate=0, avg_win_pct=0, avg_loss_pct=0,
                profit_factor=0, expectancy_pct=0,
                sharpe_ratio=0, sortino_ratio=0,
                max_consecutive_wins=0, max_consecutive_losses=0,
                max_drawdown_pct=0,
                avg_hold_minutes=0, avg_entry_mae_pct=0, avg_exit_mfe_pct=0,
            )

        pnls = [t.net_pnl for t in trades]
        pnl_pcts = [((t.net_pnl - t.fees_paid) / (t.entry_price * abs(t.leverage_applied))) * 100 for t in trades if t.entry_price > 0]

        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        win_count = len(wins)
        loss_count = len(losses)
        total = len(trades)
        win_rate = win_count / total if total > 0 else 0

        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0

        avg_win_pct = sum([p for p in pnl_pcts if p > 0]) / len([p for p in pnl_pcts if p > 0]) if any(p > 0 for p in pnl_pcts) else 0
        avg_loss_pct = sum([p for p in pnl_pcts if p < 0]) / len([p for p in pnl_pcts if p < 0]) if any(p < 0 for p in pnl_pcts) else 0

        profit_factor = sum(wins) / abs(sum(losses)) if sum(losses) != 0 else 0
        expectancy_pct = (win_rate * avg_win_pct) + ((1 - win_rate) * avg_loss_pct) if avg_loss_pct != 0 else 0

        # Sharpe ratio: mean / std of returns
        if pnl_pcts and len(pnl_pcts) > 1:
            mean_ret = sum(pnl_pcts) / len(pnl_pcts)
            variance = sum((p - mean_ret) ** 2 for p in pnl_pcts) / len(pnl_pcts)
            std_ret = variance ** 0.5
            sharpe = (mean_ret / std_ret * (252 ** 0.5)) if std_ret > 0 else 0  # Annualized
        else:
            sharpe = 0

        # Sortino ratio: mean / downside std
        if pnl_pcts and len(pnl_pcts) > 1:
            mean_ret = sum(pnl_pcts) / len(pnl_pcts)
            downside_variance = sum((min(p - mean_ret, 0) ** 2) for p in pnl_pcts) / len(pnl_pcts)
            downside_std = downside_variance ** 0.5
            sortino = (mean_ret / downside_std * (252 ** 0.5)) if downside_std > 0 else 0
        else:
            sortino = 0

        # Max consecutive wins/losses
        max_cons_wins = 0
        max_cons_losses = 0
        current_cons_wins = 0
        current_cons_losses = 0

        for p in pnls:
            if p > 0:
                current_cons_wins += 1
                max_cons_wins = max(max_cons_wins, current_cons_wins)
                current_cons_losses = 0
            else:
                current_cons_losses += 1
                max_cons_losses = max(max_cons_losses, current_cons_losses)
                current_cons_wins = 0

        # Max drawdown
        max_dd = min([t.session_drawdown_pct for t in trades]) if trades else 0

        avg_hold = sum([t.hold_duration_minutes for t in trades]) / len(trades) if trades else 0
        avg_mae = sum([t.max_adverse_excursion_pct for t in trades]) / len(trades) if trades else 0
        avg_mfe = sum([t.max_favorable_excursion_pct for t in trades]) / len(trades) if trades else 0

        return PerformanceMetrics(
            pattern_name=name,
            trade_count=total,
            win_count=win_count,
            loss_count=loss_count,
            win_rate=round(win_rate, 3),
            avg_win_pct=round(avg_win_pct, 2),
            avg_loss_pct=round(avg_loss_pct, 2),
            profit_factor=round(profit_factor, 2),
            expectancy_pct=round(expectancy_pct, 2),
            sharpe_ratio=round(sharpe, 2),
            sortino_ratio=round(sortino, 2),
            max_consecutive_wins=max_cons_wins,
            max_consecutive_losses=max_cons_losses,
            max_drawdown_pct=round(max_dd, 2),
            avg_hold_minutes=round(avg_hold, 1),
            avg_entry_mae_pct=round(avg_mae, 2),
            avg_exit_mfe_pct=round(avg_mfe, 2),
        )

    def find_sniper_setups(self, min_sample_size: int = 5, min_wr: float = 0.55) -> List[SniperSetup]:
        """Identify high-edge single-signal setups worth scaling up.

        Args:
            min_sample_size: Minimum trades to consider (avoid noise)
            min_wr: Minimum win rate threshold for sniper setup

        Returns:
            List of SniperSetup objects ranked by edge
        """
        sniper_setups = []

        # Compute metrics by strategy + regime
        for strategy in set(t.single_strategy_name for t in self.trades):
            for regime in set(t.regime_1h for t in self.trades):
                trades = [
                    t for t in self.trades
                    if t.single_strategy_name == strategy and t.regime_1h == regime
                ]

                if len(trades) < min_sample_size:
                    continue

                metrics = self._compute_metrics_for_trades(trades, f"{strategy}+{regime}")

                if metrics.win_rate >= min_wr:
                    # Find best symbol too
                    for symbol in set(t.symbol for t in trades):
                        sym_trades = [t for t in trades if t.symbol == symbol]
                        if len(sym_trades) < 3:
                            continue

                        sym_metrics = self._compute_metrics_for_trades(sym_trades, f"{symbol}")

                        setup = SniperSetup(
                            pattern_name=f"{strategy}_{regime}_{symbol}",
                            symbol=symbol,
                            regime=regime,
                            strategy=strategy,
                            sample_size=len(sym_trades),
                            win_rate=sym_metrics.win_rate,
                            profit_factor=sym_metrics.profit_factor,
                            sharpe_ratio=sym_metrics.sharpe_ratio,
                            recommended_sizing_multiplier=1.0 + (sym_metrics.win_rate - 0.5),
                            confidence=min(0.95, sym_metrics.win_rate + 0.1),
                            notes=f"PF={sym_metrics.profit_factor:.1f}, Sharpe={sym_metrics.sharpe_ratio:.1f}",
                        )

                        sniper_setups.append(setup)

        # Sort by sharpe ratio (risk-adjusted returns)
        sniper_setups.sort(key=lambda s: s.sharpe_ratio, reverse=True)

        logger.info(f"[AUDIT] Found {len(sniper_setups)} sniper setups with WR >= {min_wr:.0%}")
        return sniper_setups

    def identify_losers(self, max_wr: float = 0.45) -> List[Tuple[str, str, Dict]]:
        """Identify single-signal setups to avoid.

        Returns:
            List of (strategy, regime, metrics) tuples with poor performance
        """
        losers = []

        for strategy in set(t.single_strategy_name for t in self.trades):
            for regime in set(t.regime_1h for t in self.trades):
                trades = [
                    t for t in self.trades
                    if t.single_strategy_name == strategy and t.regime_1h == regime
                ]

                if len(trades) < 3:  # Need at least 3 to judge
                    continue

                metrics = self._compute_metrics_for_trades(trades, f"{strategy}+{regime}")

                if metrics.win_rate <= max_wr:
                    losers.append((strategy, regime, asdict(metrics)))

        logger.info(f"[AUDIT] Found {len(losers)} losing combinations (WR <= {max_wr:.0%})")
        return losers

    def compare_single_vs_ensemble(self) -> Dict[str, Any]:
        """Analyze scenarios where single signal conflicts with ensemble.

        Returns:
            Statistics on outcomes when single signal diverges from consensus
        """
        # This would require ensemble data from the ledger
        # For now, return structure for future extension
        return {
            "scenarios_analyzed": 0,
            "single_signal_accuracy": 0.0,
            "ensemble_accuracy": 0.0,
            "should_trust_single_more": False,
            "notes": "Requires ensemble data from trade ledger",
        }

    def save_audit(self):
        """Save audit state and trades to files."""
        # Save trades as jsonl
        try:
            with open(self.trades_file, "w") as f:
                for trade in self.trades:
                    f.write(json.dumps(asdict(trade)) + "\n")
            logger.info(f"[AUDIT] Saved {len(self.trades)} trades to {self.trades_file}")
        except Exception as e:
            logger.error(f"Error saving trades: {e}")

    def load_previous_audit(self) -> List[SingleSignalTrade]:
        """Load previously saved single-signal trades."""
        self._load_from_file()
        return self.trades

    def get_summary_report(self) -> str:
        """Generate human-readable audit summary."""
        if not self.trades:
            return "No single-signal trades found in audit period."

        metrics = self.compute_metrics()
        overall = metrics.get("overall")

        if not overall:
            return "Could not compute metrics."

        lines = [
            f"{'='*60}",
            f"SINGLE-SIGNAL TRADE AUDIT REPORT",
            f"{'='*60}",
            f"",
            f"Overall Statistics:",
            f"  Total trades: {overall.trade_count}",
            f"  Win rate: {overall.win_rate:.1%}",
            f"  Profit factor: {overall.profit_factor:.2f}",
            f"  Sharpe ratio: {overall.sharpe_ratio:.2f}",
            f"  Expectancy: {overall.expectancy_pct:.2f}% per trade",
            f"  Max consecutive losses: {overall.max_consecutive_losses}",
            f"  Average hold time: {overall.avg_hold_minutes:.0f} minutes",
            f"",
        ]

        # By strategy
        lines.append("Best Performing Strategies:")
        by_strat = sorted(
            metrics.get("by_strategy", {}).items(),
            key=lambda x: x[1].win_rate,
            reverse=True
        )[:3]
        for strat, m in by_strat:
            lines.append(f"  {strat}: {m.win_rate:.0%} WR (n={m.trade_count}, PF={m.profit_factor:.1f})")

        lines.append("")

        # Sniper setups
        snipers = self.find_sniper_setups()
        if snipers:
            lines.append(f"Top Sniper Setups (High Edge):")
            for setup in snipers[:5]:
                lines.append(f"  {setup.pattern_name}: {setup.win_rate:.0%} WR "
                           f"(n={setup.sample_size}, PF={setup.profit_factor:.1f}, "
                           f"size_mult={setup.recommended_sizing_multiplier:.2f})")

        lines.append("")
        lines.append(f"{'='*60}")

        return "\n".join(lines)


__all__ = [
    "SingleSignalTrade",
    "PerformanceMetrics",
    "SniperSetup",
    "SingleSignalAudit",
]
