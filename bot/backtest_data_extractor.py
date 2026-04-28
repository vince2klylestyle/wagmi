"""
Extract full signal data and insights from backtest result JSON files.
Builds comprehensive knowledge base from Cycles 1-5 backtest outputs.
"""

import json
from pathlib import Path
from typing import Dict, List, Any
import re
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class BacktestDataExtractor:
    """Extract detailed signal and performance data from backtest results."""

    def __init__(self, backtest_dir: str = "data/backtest_results"):
        self.backtest_dir = Path(backtest_dir)
        self.results = []

    def extract_all_cycles(self) -> Dict[str, Any]:
        """Extract and consolidate data from all available backtest cycles."""
        cycle_files = sorted(self.backtest_dir.glob("cycle_*.json"))
        logger.info(f"\nFound {len(cycle_files)} backtest result files")

        cycles_data = {}
        for cycle_file in cycle_files:
            cycle_id = cycle_file.stem
            data = self._extract_cycle(cycle_file)
            cycles_data[cycle_id] = data

        return cycles_data

    def _extract_cycle(self, cycle_file: Path) -> Dict[str, Any]:
        """Extract data from a single cycle backtest file."""
        with open(cycle_file) as f:
            raw = json.load(f)

        # Extract from raw_output string
        raw_output = raw.get("raw_output", "")

        cycle_data = {
            "cycle_id": raw.get("run_id"),
            "timestamp": raw.get("timestamp"),
            "metrics": self._parse_summary(raw_output),
            "signal_funnel": self._parse_signal_funnel(raw_output),
            "by_symbol": self._parse_by_symbol(raw_output),
            "by_regime": self._parse_by_regime(raw_output),
            "by_setup": self._parse_by_setup(raw_output),
            "by_hour": self._parse_by_hour(raw_output),
            "strategy_health": self._parse_strategy_health(raw_output),
            "confidence_analysis": self._parse_confidence(raw_output),
            "missed_trades": self._parse_missed_trades(raw_output),
        }

        return cycle_data

    def _parse_summary(self, raw_output: str) -> Dict[str, Any]:
        """Extract summary metrics."""
        metrics = {}

        # Equity change
        equity_match = re.search(r"Equity:\s+\$([\d,]+\.?\d*)\s*->\s*\$([\d,]+\.?\d*)\s*\(([-\d.]+)%\)", raw_output)
        if equity_match:
            metrics["equity_start"] = float(equity_match.group(1).replace(",", ""))
            metrics["equity_end"] = float(equity_match.group(2).replace(",", ""))
            metrics["equity_change_pct"] = float(equity_match.group(3))

        # Win rate
        wr_match = re.search(r"Win Rate:\s+([\d.]+)%", raw_output)
        if wr_match:
            metrics["win_rate"] = float(wr_match.group(1))

        # PnL
        pnl_matches = {
            "gross_pnl": re.search(r"Gross PnL:\s+\$([\d,\-\.]+)", raw_output),
            "fees": re.search(r"Trading fees:\s+\$([\d,\-\.]+)", raw_output),
            "net_pnl": re.search(r"Net PnL:\s+\$([\d,\-\.]+)", raw_output),
        }
        for key, match in pnl_matches.items():
            if match:
                metrics[key] = float(match.group(1).replace(",", ""))

        # Positions
        pos_match = re.search(r"Positions:\s+(\d+)\s+opened", raw_output)
        if pos_match:
            metrics["positions_opened"] = int(pos_match.group(1))

        return metrics

    def _parse_signal_funnel(self, raw_output: str) -> Dict[str, Any]:
        """Extract signal generation and conversion funnel."""
        funnel = {}

        candles_match = re.search(r"Candles processed:\s+(\d+)", raw_output)
        if candles_match:
            funnel["candles_processed"] = int(candles_match.group(1))

        signal_gen_match = re.search(r"Signal gen:\s+(\d+)\s*\(([\d.]+)%\)", raw_output)
        if signal_gen_match:
            funnel["signals_generated"] = int(signal_gen_match.group(1))
            funnel["signal_generation_rate"] = float(signal_gen_match.group(2))

        executed_match = re.search(r"Executed:\s+(\d+)", raw_output)
        if executed_match:
            funnel["trades_executed"] = int(executed_match.group(1))

        conversion_match = re.search(r"Conversion:\s+([\d.]+)%", raw_output)
        if conversion_match:
            funnel["candle_to_trade_conversion"] = float(conversion_match.group(1))

        return funnel

    def _parse_by_symbol(self, raw_output: str) -> Dict[str, Any]:
        """Extract per-symbol performance breakdown."""
        symbols = {}

        # Pattern: BTC: X events, Y% WR, $Z net PnL
        symbol_pattern = r"(BTC|ETH|SOL|HYPE):\s+(\d+)\s+events,\s+([\d.]+)%\s+WR,\s+\$([-\d,\.]+)\s+net PnL"
        for match in re.finditer(symbol_pattern, raw_output):
            symbol = match.group(1)
            symbols[symbol] = {
                "events": int(match.group(2)),
                "win_rate": float(match.group(3)),
                "net_pnl": float(match.group(4).replace(",", "")),
            }

        return symbols

    def _parse_by_regime(self, raw_output: str) -> Dict[str, Any]:
        """Extract per-regime performance breakdown."""
        regimes = {}

        # Pattern: trending_bull: X trades, Y% WR, PnL=$Z
        regime_pattern = r"(trending_bull|trending_bear|ranging|consolidation|high_volatility|low_liquidity).*?(\d+)\s+trades\s+([\d.]+)%\s+WR.*?\$([-\d,\.]+)"
        for match in re.finditer(regime_pattern, raw_output):
            regime = match.group(1)
            regimes[regime] = {
                "trades": int(match.group(2)),
                "win_rate": float(match.group(3)),
                "pnl": float(match.group(4).replace(",", "")),
            }

        return regimes

    def _parse_by_setup(self, raw_output: str) -> Dict[str, Any]:
        """Extract per-setup performance breakdown."""
        setups = {}

        # Pattern: trend_follow: X trades, Y% WR, PnL=$Z
        setup_pattern = r"(trend_follow|mean_reversion|breakout|support_resist).*?(\d+)\s+trades\s+([\d.]+)%\s+WR.*?\$([-\d,\.]+)"
        for match in re.finditer(setup_pattern, raw_output):
            setup = match.group(1)
            setups[setup] = {
                "trades": int(match.group(2)),
                "win_rate": float(match.group(3)),
                "pnl": float(match.group(4).replace(",", "")),
            }

        return setups

    def _parse_by_hour(self, raw_output: str) -> Dict[str, Any]:
        """Extract time-of-day performance breakdown."""
        hours = {}

        # Pattern: HH:00 UTC    X trades  WR=Y%  PnL=$Z
        hour_pattern = r"(\d{2}):00 UTC\s+(\d+)\s+trades\s+([\d.]+)%\s+WR.*?\$([-\d,\.]+)"
        for match in re.finditer(hour_pattern, raw_output):
            hour = match.group(1)
            hours[hour] = {
                "trades": int(match.group(2)),
                "win_rate": float(match.group(3)),
                "pnl": float(match.group(4).replace(",", "")),
            }

        return hours

    def _parse_strategy_health(self, raw_output: str) -> Dict[str, Any]:
        """Extract per-strategy performance."""
        strategies = {}

        # Pattern: strategy_name    PF=X    EV=$Y   net=$Z  WR=W%
        strat_pattern = r"(\w+)\s+PF=([\d.]+)\s+EV=\$([-\d,\.]+)\s+net=\$([-\d,\.]+)\s+WR=([\d.]+)%"
        for match in re.finditer(strat_pattern, raw_output):
            strat = match.group(1)
            strategies[strat] = {
                "profit_factor": float(match.group(2)),
                "expected_value": float(match.group(3).replace(",", "")),
                "net_pnl": float(match.group(4).replace(",", "")),
                "win_rate": float(match.group(5)),
            }

        return strategies

    def _parse_confidence(self, raw_output: str) -> Dict[str, Any]:
        """Extract confidence-based performance buckets."""
        confidence = {}

        # Pattern: NN-NN%: X positions Y% WR $Z
        conf_pattern = r"(\d+-\d+)%:\s+(\d+)\s+positions\s+([\d.]+)%\s+WR\s+\$([-\d,\.]+)"
        for match in re.finditer(conf_pattern, raw_output):
            bucket = match.group(1)
            confidence[bucket] = {
                "positions": int(match.group(2)),
                "win_rate": float(match.group(3)),
                "pnl": float(match.group(4).replace(",", "")),
            }

        return confidence

    def _parse_missed_trades(self, raw_output: str) -> Dict[str, Any]:
        """Extract missed trade feedback (hidden alpha analysis)."""
        missed = {}

        # Pattern: STRATEGY    Missed  Won  Lost   WR%   Alpha%
        missed_pattern = r"(\w+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)%\s+([-\d.]+)%"
        for match in re.finditer(missed_pattern, raw_output):
            strategy = match.group(1)
            missed[strategy] = {
                "missed_signals": int(match.group(2)),
                "would_have_won": int(match.group(3)),
                "would_have_lost": int(match.group(4)),
                "win_rate": float(match.group(5)),
                "alpha_pct": float(match.group(6)),
            }

        return missed

    def consolidate_cycles(self, cycles_data: Dict[str, Any]) -> Dict[str, Any]:
        """Consolidate data across all cycles."""
        logger.info("\n" + "="*70)
        logger.info("CONSOLIDATING BACKTEST DATA ACROSS CYCLES")
        logger.info("="*70)

        consolidated = {
            "total_cycles": len(cycles_data),
            "cycles": cycles_data,
            "aggregate_metrics": self._aggregate_metrics(cycles_data),
            "edge_analysis": self._analyze_edges(cycles_data),
            "consistency_check": self._check_consistency(cycles_data),
        }

        return consolidated

    def _aggregate_metrics(self, cycles_data: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate metrics across cycles."""
        agg = {
            "total_trades": 0,
            "total_wins": 0,
            "total_pnl": 0,
            "total_signals": 0,
            "avg_win_rate": 0,
        }

        for cycle_id, cycle in cycles_data.items():
            metrics = cycle.get("metrics", {})
            funnel = cycle.get("signal_funnel", {})

            agg["total_trades"] += metrics.get("positions_opened", 0)
            agg["total_pnl"] += metrics.get("net_pnl", 0)
            agg["total_signals"] += funnel.get("signals_generated", 0)

        if agg["total_trades"] > 0:
            agg["avg_win_rate"] = (agg["total_wins"] / agg["total_trades"]) * 100 if agg["total_wins"] > 0 else 0

        return agg

    def _analyze_edges(self, cycles_data: Dict[str, Any]) -> Dict[str, Any]:
        """Identify conditional edges from missed trades."""
        edges = {}

        for cycle_id, cycle in cycles_data.items():
            missed = cycle.get("missed_trades", {})
            for strategy, data in missed.items():
                if strategy not in edges:
                    edges[strategy] = []

                edges[strategy].append({
                    "cycle": cycle_id,
                    "missed_signals": data.get("missed_signals", 0),
                    "win_rate": data.get("win_rate", 0),
                    "alpha_pct": data.get("alpha_pct", 0),
                })

        return edges

    def _check_consistency(self, cycles_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check consistency of patterns across cycles."""
        # Will be enhanced as more cycles complete
        return {
            "cycles_available": len(cycles_data),
            "ready_for_validation": len(cycles_data) >= 3,
        }

    def print_summary(self, consolidated: Dict[str, Any]):
        """Print comprehensive analysis summary."""
        logger.info("\n" + "="*70)
        logger.info("AUTONOMOUS LEARNING ANALYSIS SUMMARY")
        logger.info("="*70)

        agg = consolidated.get("aggregate_metrics", {})
        logger.info(f"\nAggregate Performance (Cycles 1-{consolidated['total_cycles']}):")
        logger.info(f"  Total Signals: {agg.get('total_signals', 0)}")
        logger.info(f"  Total Trades: {agg.get('total_trades', 0)}")
        logger.info(f"  Net PnL: ${agg.get('total_pnl', 0):,.2f}")
        logger.info(f"  Avg WR: {agg.get('avg_win_rate', 0):.1f}%")

        edges = consolidated.get("edge_analysis", {})
        logger.info(f"\nHidden Alpha Discovered:")
        for strategy, data in edges.items():
            for entry in data:
                alpha = entry.get("alpha_pct", 0)
                if alpha > 50:  # Show significant alpha
                    logger.info(
                        f"  {strategy}: {entry.get('win_rate', 0):.0f}% WR on "
                        f"{entry.get('missed_signals', 0)} signals (+{alpha:.0f}% alpha)"
                    )

        logger.info(f"\nConsistency Status:")
        consistency = consolidated.get("consistency_check", {})
        logger.info(f"  Cycles Available: {consistency.get('cycles_available', 0)}/5")
        logger.info(f"  Ready for Validation: {'YES' if consistency.get('ready_for_validation') else 'NO'}")


if __name__ == "__main__":
    extractor = BacktestDataExtractor("data/backtest_results")

    # Extract all cycles
    cycles_data = extractor.extract_all_cycles()

    # Consolidate
    consolidated = extractor.consolidate_cycles(cycles_data)

    # Print summary
    extractor.print_summary(consolidated)

    # Save consolidated data
    with open("data/consolidated_cycles_analysis.json", "w") as f:
        json.dump(consolidated, f, indent=2)

    logger.info("\n[SAVED] Consolidated analysis to data/consolidated_cycles_analysis.json")
