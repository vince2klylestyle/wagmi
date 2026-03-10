"""
Mode Comparison Runner: A/B test LLM autonomy levels on the same data.

Runs the same backtest period at multiple LLM modes and produces a
side-by-side comparison showing exactly where LLM adds or destroys value.

Usage:
    runner = ModeComparisonRunner(symbols=["SOL", "BTC"], days=30)
    report = runner.run()
    print(runner.format_report(report))

CLI:
    python cli.py --mode compare --days 30 --symbols SOL,BTC
"""

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

logger = logging.getLogger("bot.backtest.compare")


@dataclass
class ModeResult:
    """Results from a single mode backtest."""
    mode: int
    mode_name: str
    total_trades: int = 0
    wins: int = 0
    total_pnl: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe: float = 0.0
    profit_factor: float = 0.0
    final_equity: float = 0.0
    starting_equity: float = 10000.0
    by_regime: Dict[str, Dict] = field(default_factory=dict)
    by_symbol: Dict[str, Dict] = field(default_factory=dict)
    llm_cost: float = 0.0
    veto_count: int = 0
    veto_would_have_lost: int = 0
    duration_s: float = 0.0

    @property
    def win_rate(self) -> float:
        return self.wins / self.total_trades if self.total_trades > 0 else 0.0

    @property
    def return_pct(self) -> float:
        return (self.final_equity - self.starting_equity) / self.starting_equity * 100

    @property
    def llm_roi(self) -> float:
        """ROI of LLM spend: (PnL improvement over mode 0) / LLM cost."""
        if self.llm_cost <= 0:
            return 0.0
        return self.total_pnl / self.llm_cost


@dataclass
class ComparisonReport:
    """Full comparison report across modes."""
    symbols: List[str]
    days: int
    modes: List[int]
    results: Dict[int, ModeResult] = field(default_factory=dict)
    baseline_mode: int = 0
    timestamp: float = field(default_factory=time.time)

    def get_delta(self, mode: int, metric: str) -> float:
        """Get delta of a metric vs baseline mode."""
        baseline = self.results.get(self.baseline_mode)
        target = self.results.get(mode)
        if not baseline or not target:
            return 0.0
        b_val = getattr(baseline, metric, 0.0)
        t_val = getattr(target, metric, 0.0)
        return t_val - b_val


MODE_NAMES = {
    0: "OFF (Pure Algo)",
    1: "ADVISORY",
    2: "VETO_ONLY",
    3: "SIZING",
    4: "DIRECTION",
    5: "FULL_AUTO",
}


class ModeComparisonRunner:
    """Run backtests at multiple LLM modes and compare results."""

    def __init__(
        self,
        symbols: Optional[List[str]] = None,
        days: int = 30,
        modes: Optional[List[int]] = None,
    ):
        self.symbols = symbols or ["SOL", "BTC", "ETH"]
        self.days = days
        self.modes = modes or [0, 2, 3, 5]  # OFF, VETO, SIZING, FULL

    def run(self) -> ComparisonReport:
        """Run backtests at each mode and collect results.

        Mode 0 always runs first (baseline). Data is cached from first run
        so subsequent modes use identical market data.
        """
        report = ComparisonReport(
            symbols=self.symbols,
            days=self.days,
            modes=self.modes,
        )

        # Ensure mode 0 runs first (baseline)
        ordered_modes = sorted(self.modes, key=lambda m: (m != 0, m))

        for mode in ordered_modes:
            logger.info(f"[COMPARE] Running mode {mode} ({MODE_NAMES.get(mode, '?')})")
            start_ts = time.time()

            try:
                result = self._run_single_mode(mode)
                result.duration_s = time.time() - start_ts
                report.results[mode] = result
                logger.info(
                    f"[COMPARE] Mode {mode}: {result.total_trades} trades, "
                    f"WR={result.win_rate:.0%}, PnL=${result.total_pnl:+.0f}, "
                    f"Sharpe={result.sharpe:.2f} ({result.duration_s:.0f}s)"
                )
            except Exception as e:
                logger.error(f"[COMPARE] Mode {mode} failed: {e}")
                report.results[mode] = ModeResult(
                    mode=mode, mode_name=MODE_NAMES.get(mode, f"Mode {mode}")
                )

        # Feed comparison results into pattern cache
        self._ingest_to_pattern_cache(report)

        return report

    def _run_single_mode(self, mode: int) -> ModeResult:
        """Run a single backtest at a specific LLM mode."""
        from trading_config import TradingConfig
        from backtest.engine import BacktestEngine

        # Set LLM mode via environment
        old_mode = os.environ.get("LLM_MODE", "")
        os.environ["LLM_MODE"] = str(mode)

        try:
            config = TradingConfig()
            llm_integration = None

            # For non-zero modes, try to create LLM integration
            if mode > 0:
                try:
                    from backtest.llm_integration import BacktestLLMIntegration
                    llm_integration = BacktestLLMIntegration(config=config)
                except Exception as e:
                    logger.warning(f"[COMPARE] LLM integration unavailable for mode {mode}: {e}")

            engine = BacktestEngine(config=config, llm_integration=llm_integration)
            raw_report = engine.run(symbols=self.symbols, days=self.days)

            results = raw_report.get("results", {})
            risk_metrics = raw_report.get("risk_metrics", {})
            llm_stats = raw_report.get("llm_stats", {})

            return ModeResult(
                mode=mode,
                mode_name=MODE_NAMES.get(mode, f"Mode {mode}"),
                total_trades=results.get("closed_trades", 0),
                wins=results.get("wins", 0),
                total_pnl=results.get("total_pnl", 0.0),
                max_drawdown_pct=raw_report.get("results", {}).get("max_drawdown_pct", 0.0) if "results" in raw_report else 0.0,
                sharpe=risk_metrics.get("sharpe_ratio", 0.0),
                profit_factor=results.get("profit_factor", 0.0),
                final_equity=results.get("final_equity", 10000.0),
                starting_equity=config.starting_equity,
                by_regime=raw_report.get("by_regime", {}),
                by_symbol=raw_report.get("by_symbol", {}),
                llm_cost=llm_stats.get("total_cost", 0.0),
                veto_count=raw_report.get("llm_veto_stats", {}).get("total_vetoes", 0),
                veto_would_have_lost=raw_report.get("llm_veto_stats", {}).get("vetoes_that_would_have_lost", 0),
            )
        finally:
            # Restore original LLM mode
            if old_mode:
                os.environ["LLM_MODE"] = old_mode
            elif "LLM_MODE" in os.environ:
                del os.environ["LLM_MODE"]

    def _ingest_to_pattern_cache(self, report: ComparisonReport):
        """Feed comparison insights into pattern cache."""
        try:
            from llm.pattern_cache import get_pattern_cache
            pc = get_pattern_cache()

            baseline = report.results.get(0)
            if not baseline:
                return

            for mode, result in report.results.items():
                if mode == 0:
                    continue
                pnl_delta = result.total_pnl - baseline.total_pnl
                # Store per-regime mode effectiveness
                for regime, stats in result.by_regime.items():
                    baseline_regime = baseline.by_regime.get(regime, {})
                    regime_delta = stats.get("pnl", 0) - baseline_regime.get("pnl", 0)
                    if abs(regime_delta) > 10:  # Only meaningful deltas
                        key = f"LLM_mode{mode}_{regime}"
                        pc.update_pattern(
                            symbol="ALL",
                            side="BOTH",
                            regime=f"mode{mode}_{regime}",
                            win=regime_delta > 0,
                            pnl=regime_delta,
                            reason=f"Mode {mode} vs Mode 0 in {regime}",
                            source="comparison",
                        )
        except Exception as e:
            logger.debug(f"[COMPARE] Pattern cache ingestion failed: {e}")

    def format_report(self, report: ComparisonReport) -> str:
        """Format comparison report as readable text."""
        lines = []
        lines.append("=" * 70)
        lines.append(f"MODE COMPARISON: {', '.join(report.symbols)} | {report.days} days")
        lines.append("=" * 70)

        # Header
        modes = sorted(report.results.keys())
        header = f"{'Metric':<25}"
        for m in modes:
            header += f" {'Mode ' + str(m):>12}"
        lines.append(header)
        lines.append("-" * 70)

        # Metrics
        metrics = [
            ("Trades", "total_trades", "d"),
            ("Win Rate", "win_rate", ".0%"),
            ("Total PnL", "total_pnl", "+.0f"),
            ("Return %", "return_pct", "+.1f"),
            ("Max Drawdown %", "max_drawdown_pct", ".1f"),
            ("Sharpe Ratio", "sharpe", ".2f"),
            ("Profit Factor", "profit_factor", ".2f"),
            ("LLM Cost", "llm_cost", ".2f"),
            ("LLM ROI", "llm_roi", ".1f"),
            ("Vetoes", "veto_count", "d"),
        ]

        for label, attr, fmt in metrics:
            row = f"{label:<25}"
            for m in modes:
                result = report.results.get(m)
                if result:
                    val = getattr(result, attr, 0)
                    if isinstance(val, float):
                        row += f" {val:>12{fmt}}"
                    else:
                        row += f" {val:>12}"
                else:
                    row += f" {'N/A':>12}"
            lines.append(row)

        # Delta table
        if 0 in report.results and len(report.results) > 1:
            lines.append("")
            lines.append("DELTA vs Mode 0 (Pure Algo):")
            lines.append("-" * 70)
            for m in modes:
                if m == 0:
                    continue
                result = report.results.get(m)
                if not result:
                    continue
                pnl_delta = report.get_delta(m, "total_pnl")
                wr_delta = report.get_delta(m, "win_rate")
                dd_delta = report.get_delta(m, "max_drawdown_pct")
                lines.append(
                    f"  Mode {m} ({result.mode_name}): "
                    f"PnL {pnl_delta:+.0f}, WR {wr_delta:+.1%}, "
                    f"DD {dd_delta:+.1f}%, "
                    f"LLM cost ${result.llm_cost:.2f}"
                )

        lines.append("=" * 70)
        return "\n".join(lines)
