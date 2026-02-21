"""
Generate performance dashboard CSVs from trade and ML data.

Output:
  data/analysis/equity_curve.csv
  data/analysis/symbol_performance.csv
  data/analysis/tp1_to_sl_analysis.csv
  data/analysis/ml_conf_vs_pnl.csv

Usage:
    python -m scripts.generate_dashboards
"""

import csv
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("dashboards")

_ANALYSIS_DIR = os.path.join("data", "analysis")
_TRADES_FILE = os.path.join("data", "trades.csv")
_ML_STATS_FILE = os.path.join("data", "ml", "ml_stats.jsonl")


def _read_trades():
    """Read trades.csv into list of dicts."""
    if not os.path.exists(_TRADES_FILE):
        return []
    with open(_TRADES_FILE) as f:
        return list(csv.DictReader(f))


def equity_curve():
    """Generate data/analysis/equity_curve.csv from trades."""
    trades = _read_trades()
    if not trades:
        logger.info("No trades found, skipping equity_curve")
        return

    equity = 10000.0
    rows = [{"timestamp": "start", "equity": equity, "trade_num": 0}]
    for i, t in enumerate(trades):
        pnl = float(t.get("pnl", 0))
        equity += pnl
        rows.append({
            "timestamp": t.get("timestamp", ""),
            "equity": round(equity, 2),
            "trade_num": i + 1,
        })

    out = os.path.join(_ANALYSIS_DIR, "equity_curve.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    logger.info(f"Wrote {out} ({len(rows)} rows)")


def symbol_performance():
    """Generate data/analysis/symbol_performance.csv."""
    trades = _read_trades()
    if not trades:
        return

    by_sym = {}
    for t in trades:
        sym = t.get("symbol", "?")
        if sym not in by_sym:
            by_sym[sym] = {"symbol": sym, "trades": 0, "wins": 0, "total_pnl": 0.0}
        by_sym[sym]["trades"] += 1
        pnl = float(t.get("pnl", 0))
        by_sym[sym]["total_pnl"] += pnl
        if pnl > 0:
            by_sym[sym]["wins"] += 1

    for s in by_sym.values():
        s["win_rate"] = round(s["wins"] / s["trades"], 3) if s["trades"] else 0
        s["avg_pnl"] = round(s["total_pnl"] / s["trades"], 2) if s["trades"] else 0
        s["total_pnl"] = round(s["total_pnl"], 2)

    rows = sorted(by_sym.values(), key=lambda x: x["total_pnl"], reverse=True)
    out = os.path.join(_ANALYSIS_DIR, "symbol_performance.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    logger.info(f"Wrote {out}")


def tp1_to_sl_analysis():
    """Analyze how often TP1 hits but then SL triggers on remaining."""
    trades = _read_trades()
    if not trades:
        return

    rows = []
    for t in trades:
        tp1_hit = t.get("tp1_hit", "False") == "True"
        sl_hit = t.get("sl_hit", "False") == "True"
        trailing = t.get("trailing_hit", "False") == "True"
        tp2_hit = t.get("tp2_hit", "False") == "True"

        rows.append({
            "symbol": t.get("symbol"),
            "tp1_hit": tp1_hit,
            "final_action": "TP2" if tp2_hit else "TRAILING" if trailing else "SL" if sl_hit else "OTHER",
            "pnl": float(t.get("pnl", 0)),
            "leverage": float(t.get("leverage", 1)),
            "confidence": float(t.get("confidence", 0)),
        })

    out = os.path.join(_ANALYSIS_DIR, "tp1_to_sl_analysis.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)

    # Summary stats
    total = len(rows)
    tp1_hits = sum(1 for r in rows if r["tp1_hit"])
    tp1_then_sl = sum(1 for r in rows if r["tp1_hit"] and r["final_action"] == "SL")
    logger.info(f"TP1->SL analysis: {tp1_hits}/{total} hit TP1, {tp1_then_sl} then hit SL")


def ml_conf_vs_pnl():
    """Correlate ML confidence at entry with trade PnL."""
    trades = _read_trades()
    if not trades:
        return

    rows = []
    for t in trades:
        rows.append({
            "confidence": float(t.get("confidence", 0)),
            "pnl": float(t.get("pnl", 0)),
            "leverage": float(t.get("leverage", 1)),
            "outcome": t.get("outcome", ""),
            "symbol": t.get("symbol", ""),
        })

    out = os.path.join(_ANALYSIS_DIR, "ml_conf_vs_pnl.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    logger.info(f"Wrote {out}")


def main():
    os.makedirs(_ANALYSIS_DIR, exist_ok=True)
    equity_curve()
    symbol_performance()
    tp1_to_sl_analysis()
    ml_conf_vs_pnl()
    logger.info("Dashboard generation complete")


if __name__ == "__main__":
    main()
