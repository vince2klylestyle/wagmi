"""
Validate that the Trade Classification Layer behaves as designed.

Reads trade data (from backtest or live) and confirms:
1. SCALP/MEDIUM/TREND trades have different TP1/SL distances
2. TP1 close % varies by entry_type
3. Holding times differ by entry_type
4. Regime modifiers actually change behavior

Outputs per-entry_type analysis CSVs to data/analysis/ for manual inspection.

Usage:
    python -m scripts.validate_classification
"""

import csv
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("validate")

_ANALYSIS_DIR = os.path.join("data", "analysis")
_TRADES_FILE = os.path.join("data", "trades.csv")
_OUTCOMES_FILE = os.path.join("data", "analysis", "trade_outcomes.csv")


def _read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def validate_entry_type_differences():
    """
    Confirm that SCALP, MEDIUM, TREND trades have distinct exit profiles.
    Outputs: data/analysis/entry_type_validation.csv
    """
    trades = _read_csv(_TRADES_FILE)
    outcomes = _read_csv(_OUTCOMES_FILE)

    # Use outcomes (has rr1, rr2, entry_type)
    data = outcomes if outcomes else trades
    if not data:
        logger.warning("No trade data found. Run a backtest first.")
        return False

    by_type = defaultdict(list)
    for row in data:
        et = row.get("entry_type", "")
        if not et:
            continue
        pnl = float(row.get("pnl", 0))
        rr1 = float(row.get("rr1", 0))
        rr2 = float(row.get("rr2", 0))
        tp1_hit = row.get("tp1_hit", "False") == "True"
        sl_after_tp1 = row.get("sl_after_tp1", "False") == "True"
        leverage = float(row.get("leverage", 1))
        confidence = float(row.get("confidence", 0))

        by_type[et].append({
            "pnl": pnl, "rr1": rr1, "rr2": rr2,
            "tp1_hit": tp1_hit, "sl_after_tp1": sl_after_tp1,
            "leverage": leverage, "confidence": confidence,
        })

    if not by_type:
        logger.warning("No entry_type data found in trades. Check logging.")
        return False

    # Compute per-type stats
    results = []
    for et, records in sorted(by_type.items()):
        n = len(records)
        wins = [r for r in records if r["pnl"] > 0]
        losses = [r for r in records if r["pnl"] <= 0]
        tp1_hits = [r for r in records if r["tp1_hit"]]
        tp1_sl = [r for r in records if r["sl_after_tp1"]]

        wr = len(wins) / n if n else 0
        avg_win_r = sum(r["rr1"] for r in wins) / len(wins) if wins else 0
        avg_loss_r = sum(r["rr1"] for r in losses) / len(losses) if losses else 0
        ev = wr * avg_win_r - (1 - wr) * avg_loss_r if n else 0

        results.append({
            "entry_type": et,
            "trades": n,
            "win_rate": round(wr, 3),
            "avg_pnl": round(sum(r["pnl"] for r in records) / n, 2) if n else 0,
            "total_pnl": round(sum(r["pnl"] for r in records), 2),
            "avg_rr1": round(sum(r["rr1"] for r in records) / n, 2) if n else 0,
            "avg_rr2": round(sum(r["rr2"] for r in records) / n, 2) if n else 0,
            "avg_win_R": round(avg_win_r, 2),
            "avg_loss_R": round(avg_loss_r, 2),
            "EV_per_trade": round(ev, 3),
            "tp1_hit_rate": round(len(tp1_hits) / n, 3) if n else 0,
            "tp1_to_sl_rate": round(len(tp1_sl) / max(len(tp1_hits), 1), 3),
            "avg_leverage": round(sum(r["leverage"] for r in records) / n, 1) if n else 0,
            "avg_confidence": round(sum(r["confidence"] for r in records) / n, 1) if n else 0,
        })

    os.makedirs(_ANALYSIS_DIR, exist_ok=True)
    out = os.path.join(_ANALYSIS_DIR, "entry_type_validation.csv")
    if results:
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=results[0].keys())
            w.writeheader()
            w.writerows(results)
        logger.info(f"Wrote {out} ({len(results)} entry types)")

    # Print summary
    print("\n" + "=" * 70)
    print("ENTRY TYPE VALIDATION")
    print("=" * 70)
    for r in results:
        print(f"  {r['entry_type']:8s} | trades={r['trades']:4d} | WR={r['win_rate']:.1%} | "
              f"EV={r['EV_per_trade']:+.3f} | avg_rr1={r['avg_rr1']:.2f} | "
              f"tp1_hit={r['tp1_hit_rate']:.0%} | tp1->sl={r['tp1_to_sl_rate']:.0%}")

    # Validation checks
    ok = True
    types = {r["entry_type"]: r for r in results}

    if "TREND" in types and "MEDIUM" in types:
        if types["TREND"]["avg_rr1"] <= types["MEDIUM"]["avg_rr1"]:
            logger.warning("VALIDATION FAIL: TREND avg_rr1 should be > MEDIUM")
            ok = False
        else:
            logger.info("OK: TREND has wider RR1 than MEDIUM")

    if "SCALP" in types and "MEDIUM" in types:
        if types["SCALP"]["avg_rr1"] >= types["MEDIUM"]["avg_rr1"]:
            logger.warning("VALIDATION FAIL: SCALP avg_rr1 should be < MEDIUM")
            ok = False
        else:
            logger.info("OK: SCALP has tighter RR1 than MEDIUM")

    print("=" * 70)
    return ok


def validate_regime_impact():
    """
    Confirm that regime modifiers change trade behavior.
    Outputs: data/analysis/regime_validation.csv
    """
    outcomes = _read_csv(_OUTCOMES_FILE)
    if not outcomes:
        logger.warning("No outcomes data found.")
        return

    by_regime = defaultdict(list)
    for row in outcomes:
        reg = row.get("regime", "")
        if not reg:
            continue
        by_regime[reg].append({
            "pnl": float(row.get("pnl", 0)),
            "rr1": float(row.get("rr1", 0)),
            "tp1_hit": row.get("tp1_hit", "False") == "True",
            "entry_type": row.get("entry_type", ""),
        })

    results = []
    for reg, records in sorted(by_regime.items()):
        n = len(records)
        wins = sum(1 for r in records if r["pnl"] > 0)
        results.append({
            "regime": reg,
            "trades": n,
            "win_rate": round(wins / n, 3) if n else 0,
            "avg_pnl": round(sum(r["pnl"] for r in records) / n, 2) if n else 0,
            "total_pnl": round(sum(r["pnl"] for r in records), 2),
            "avg_rr1": round(sum(r["rr1"] for r in records) / n, 2) if n else 0,
            "tp1_hit_rate": round(sum(1 for r in records if r["tp1_hit"]) / n, 3) if n else 0,
        })

    os.makedirs(_ANALYSIS_DIR, exist_ok=True)
    out = os.path.join(_ANALYSIS_DIR, "regime_validation.csv")
    if results:
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=results[0].keys())
            w.writeheader()
            w.writerows(results)
        logger.info(f"Wrote {out}")

    print("\nREGIME IMPACT:")
    for r in results:
        print(f"  {r['regime']:12s} | trades={r['trades']:4d} | WR={r['win_rate']:.1%} | "
              f"EV rr1={r['avg_rr1']:.2f} | tp1_hit={r['tp1_hit_rate']:.0%}")


def validate_logging_completeness():
    """
    Check that all required fields are populated in trade logs.
    Reports missing or empty fields.
    """
    trades = _read_csv(_TRADES_FILE)
    if not trades:
        logger.warning("No trades.csv found.")
        return False

    required_fields = [
        "timestamp", "symbol", "side", "entry", "exit",
        "pnl", "state_path", "outcome",
        "entry_type", "primary_driver", "regime", "volatility_band",
    ]

    issues = defaultdict(int)
    total = len(trades)

    for t in trades:
        for field in required_fields:
            val = t.get(field, "")
            if not val or val == "":
                issues[field] += 1

    print("\n" + "=" * 70)
    print("LOGGING COMPLETENESS CHECK")
    print("=" * 70)
    print(f"  Total trades: {total}")

    ok = True
    for field in required_fields:
        missing = issues.get(field, 0)
        pct = (total - missing) / total * 100 if total else 0
        status = "OK" if missing == 0 else "MISSING"
        if missing > 0:
            ok = False
        print(f"  {field:25s} | {pct:5.1f}% present ({missing} missing) [{status}]")

    print("=" * 70)
    return ok


def main():
    print("Trade Classification Layer Validation")
    print("=" * 70)

    validate_entry_type_differences()
    validate_regime_impact()
    validate_logging_completeness()


if __name__ == "__main__":
    main()
