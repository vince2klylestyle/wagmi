"""
A/B Backtest Harness — Run experiments with parameter variations.

Programmatic interface for rapid experimentation without modifying production code.
Results saved to bot/data/ab_results/ for analysis.
"""

import sys
import os
import json
import logging
import time
from pathlib import Path
from copy import deepcopy
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
logging.basicConfig(level=logging.WARNING)

from backtest.engine import BacktestEngine
from trading_config import TradingConfig


def run_experiment(name: str, setup_fn=None, days=90, symbols=None):
    """Run a single backtest experiment.

    Args:
        name: Experiment identifier
        setup_fn: Function(engine) that modifies engine settings before run
        days: Backtest period
        symbols: List of symbols (default: BTC, SOL, HYPE)

    Returns:
        Dict with key metrics
    """
    symbols = symbols or ["BTC", "SOL", "HYPE"]

    engine = BacktestEngine()
    if setup_fn:
        setup_fn(engine)

    start = time.time()
    result = engine.run(symbols, days=days)
    elapsed = time.time() - start

    # Extract key metrics
    risk = result.get("risk_metrics", {})
    costs = result.get("costs", {})
    by_agree = result.get("by_agreement", {})
    by_regime = result.get("by_regime", {})
    by_symbol = result.get("symbol_pnl", {})
    positions = result.get("positions", {})
    missed = result.get("missed_trades", {})
    hold_time = result.get("hold_time_analysis", {})

    metrics = {
        "name": name,
        "timestamp": datetime.now().isoformat(),
        "elapsed_s": round(elapsed, 1),
        "days": days,
        "symbols": symbols,
        "net_pnl": costs.get("net_pnl", 0),
        "gross_pnl": costs.get("gross_pnl", 0),
        "fees": costs.get("total_fees", 0),
        "profit_factor": risk.get("profit_factor", 0),
        "annualized_pct": risk.get("annualized_return_pct", 0),
        "sharpe": risk.get("sharpe", 0),
        "sortino": risk.get("sortino", 0),
        "max_dd_pct": result.get("risk_metrics", {}).get("max_dd_pct", 0),
        "total_positions": positions.get("count", 0),
        "win_rate": positions.get("win_rate", 0),
        "avg_winner": positions.get("avg_winner", 0),
        "avg_loser": positions.get("avg_loser", 0),
        "payoff_ratio": positions.get("payoff_ratio", 0),
        "by_agreement": {k: {"trades": v.get("trades", 0), "pnl": round(v.get("pnl", 0), 2), "wr": round(v.get("win_rate", 0) * 100)} for k, v in by_agree.items()},
        "by_regime": {k: {"trades": v.get("trades", 0), "pnl": round(v.get("pnl", 0), 2), "wr": round(v.get("win_rate", 0) * 100)} for k, v in by_regime.items()},
        "by_symbol": {k: round(v, 2) for k, v in by_symbol.items()},
        "hold_time": {k: {"trades": v.get("trades", 0), "pnl": round(v.get("pnl", 0), 2), "wr": round(v.get("win_rate", 0) * 100)} for k, v in hold_time.items()},
        "missed_total": missed.get("total_missed", 0),
        "missed_would_win": missed.get("would_have_won", 0),
    }

    return metrics


def print_comparison(baseline, experiments):
    """Print a comparison table of experiment results."""
    all_runs = [baseline] + experiments

    print("\n" + "=" * 100)
    print("A/B EXPERIMENT RESULTS")
    print("=" * 100)

    # Header
    names = [r["name"][:25] for r in all_runs]
    print(f"{'Metric':<20s}", end="")
    for n in names:
        print(f" {n:>25s}", end="")
    print()
    print("-" * (20 + 26 * len(names)))

    # Key metrics
    rows = [
        ("Net PnL", "net_pnl", "${:.2f}"),
        ("Profit Factor", "profit_factor", "{:.2f}"),
        ("Annualized %", "annualized_pct", "{:.1f}%"),
        ("Sharpe", "sharpe", "{:.2f}"),
        ("Positions", "total_positions", "{:.0f}"),
        ("Win Rate", "win_rate", "{:.1f}%"),
        ("Payoff Ratio", "payoff_ratio", "{:.2f}"),
        ("Avg Winner", "avg_winner", "${:.2f}"),
        ("Avg Loser", "avg_loser", "${:.2f}"),
        ("Missed (would win)", "missed_would_win", "{:.0f}"),
    ]

    for label, key, fmt in rows:
        print(f"{label:<20s}", end="")
        for r in all_runs:
            val = r.get(key, 0)
            try:
                formatted = fmt.format(val)
            except (ValueError, TypeError):
                formatted = str(val)
            # Color coding vs baseline
            print(f" {formatted:>25s}", end="")
        print()

    # Agreement breakdown
    print("\n--- By Agreement ---")
    for agree_key in ["1_agree", "2_agree", "3_agree"]:
        print(f"\n  {agree_key}:")
        for r in all_runs:
            ag = r.get("by_agreement", {}).get(agree_key, {})
            print(f"    {r['name'][:20]:<20s}: trades={ag.get('trades',0):3d} PnL=${ag.get('pnl',0):+8.2f} WR={ag.get('wr',0):.0f}%")

    # Hold time breakdown
    print("\n--- By Hold Time ---")
    for ht_key in ["0-2h", "2-6h", "6-12h", "12-24h"]:
        print(f"\n  {ht_key}:")
        for r in all_runs:
            ht = r.get("hold_time", {}).get(ht_key, {})
            print(f"    {r['name'][:20]:<20s}: trades={ht.get('trades',0):3d} PnL=${ht.get('pnl',0):+8.2f} WR={ht.get('wr',0):.0f}%")

    # Symbol breakdown
    print("\n--- By Symbol ---")
    for r in all_runs:
        syms = r.get("by_symbol", {})
        sym_str = " | ".join(f"{s}: ${v:+.2f}" for s, v in syms.items())
        print(f"  {r['name'][:25]:<25s}: {sym_str}")

    print("\n" + "=" * 100)


def save_results(results, filename="ab_results.json"):
    """Save results to disk."""
    out_dir = Path(__file__).parent.parent / "data" / "ab_results"
    out_dir.mkdir(parents=True, exist_ok=True)

    out_file = out_dir / filename
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {out_file}")


if __name__ == "__main__":
    print("Running A/B experiments...")
    print("This will take several minutes per experiment.\n")

    # ── Experiment 1: Baseline (current settings) ──
    print("[1/5] Running baseline...")
    baseline = run_experiment("BASELINE")

    # ── Experiment 2: No solo trades ──
    def no_solo(engine):
        """Disable all solo trade paths by setting threshold impossibly high."""
        pass  # Will monkey-patch ensemble

    print("[2/5] Running no-solo experiment...")
    # We'll use env vars or direct config overrides
    baseline_no_solo = run_experiment("NO_SOLO")

    print_comparison(baseline, [baseline_no_solo])
