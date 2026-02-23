"""
EV Dashboard: compute and display EV metrics per entry_type, strategy, regime,
and confidence bucket.

Reads from:
  data/analysis/trade_outcomes.csv
  data/analysis/performance.json

Outputs:
  data/analysis/entry_type_summary.csv
  data/analysis/strategy_summary.csv
  data/analysis/regime_summary.csv
  data/analysis/symbol_summary.csv
  data/analysis/ml_conf_vs_pnl.csv

Usage:
    python -m scripts.ev_dashboard
"""

import csv
import json
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("ev_dashboard")

_ANALYSIS_DIR = os.path.join("data", "analysis")
_OUTCOMES_FILE = os.path.join(_ANALYSIS_DIR, "trade_outcomes.csv")
_PERF_FILE = os.path.join(_ANALYSIS_DIR, "performance.json")
_TRADES_FILE = os.path.join("data", "trades.csv")


def _read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _safe_float(val, default=0.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _ev_stats(records):
    """Compute EV metrics from a list of trade dicts."""
    n = len(records)
    if n == 0:
        return None
    wins = [r for r in records if r["pnl"] > 0]
    losses = [r for r in records if r["pnl"] <= 0]
    wr = len(wins) / n
    avg_win_r = sum(r["rr1"] for r in wins) / len(wins) if wins else 0
    avg_loss_r = sum(abs(r["rr1"]) for r in losses) / len(losses) if losses else 0
    ev = wr * avg_win_r - (1 - wr) * avg_loss_r

    tp1_hits = [r for r in records if r.get("tp1_hit")]
    tp1_then_sl = [r for r in records if r.get("sl_after_tp1")]
    trailing_all = [r for r in records if r.get("trailing")]
    trailing_wins = [r for r in trailing_all if r["pnl"] > 0]
    early_all = [r for r in records if r.get("early_exit")]
    early_saves = [r for r in early_all if r["pnl"] > -0.5]

    return {
        "trades": n,
        "win_rate": round(wr, 3),
        "avg_win_R": round(avg_win_r, 2),
        "avg_loss_R": round(avg_loss_r, 2),
        "EV_per_trade": round(ev, 3),
        "total_pnl": round(sum(r["pnl"] for r in records), 2),
        "tp1_to_sl_rate": round(len(tp1_then_sl) / max(len(tp1_hits), 1), 3),
        "trailing_win_rate": round(len(trailing_wins) / max(len(trailing_all), 1), 3),
        "early_exit_success": round(len(early_saves) / max(len(early_all), 1), 3),
    }


def _parse_trades(source="outcomes"):
    """Parse trade data into normalized dicts."""
    if source == "outcomes":
        raw = _read_csv(_OUTCOMES_FILE)
    else:
        raw = _read_csv(_TRADES_FILE)

    if not raw:
        raw = _read_csv(_TRADES_FILE) if source == "outcomes" else []

    records = []
    for row in raw:
        records.append({
            "symbol": row.get("symbol", ""),
            "side": row.get("side", ""),
            "pnl": _safe_float(row.get("pnl")),
            "rr1": _safe_float(row.get("rr1")),
            "rr2": _safe_float(row.get("rr2")),
            "confidence": _safe_float(row.get("confidence")),
            "leverage": _safe_float(row.get("leverage", 1)),
            "entry_type": row.get("entry_type", ""),
            "primary_driver": row.get("primary_driver", ""),
            "regime": row.get("regime", ""),
            "volatility_band": row.get("volatility_band", ""),
            "tp1_hit": row.get("tp1_hit", "False") == "True",
            "sl_after_tp1": row.get("sl_after_tp1", "False") == "True",
            "trailing": "TRAILING" in row.get("outcome", "") or row.get("trailing_hit", "False") == "True",
            "early_exit": "EARLY_EXIT" in row.get("outcome", "") or row.get("early_exit", "False") == "True",
            "outcome": row.get("outcome", ""),
            "state_path": row.get("state_path", ""),
            "ml_conf_at_entry": _safe_float(row.get("ml_conf_at_entry")),
        })
    return records


def _write_csv(path, rows, fieldnames):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    logger.info(f"Wrote {path} ({len(rows)} rows)")


# ── 1. Entry Type Summary ──────────────────────────────────

def entry_type_summary(records):
    """EV per entry_type -> entry_type_summary.csv"""
    by_type = defaultdict(list)
    for r in records:
        et = r["entry_type"]
        if et:
            by_type[et].append(r)

    rows = []
    for et in ("SCALP", "MEDIUM", "TREND", "REGIME"):
        if et in by_type:
            stats = _ev_stats(by_type[et])
            if stats:
                stats["entry_type"] = et
                rows.append(stats)

    if rows:
        cols = ["entry_type"] + [k for k in rows[0] if k != "entry_type"]
        _write_csv(os.path.join(_ANALYSIS_DIR, "entry_type_summary.csv"), rows, cols)

    print("\n" + "=" * 75)
    print("ENTRY TYPE EV SUMMARY")
    print("=" * 75)
    for r in rows:
        print(f"  {r['entry_type']:8s} | trades={r['trades']:4d} | WR={r['win_rate']:.1%} | "
              f"EV={r['EV_per_trade']:+.3f} | avgW={r['avg_win_R']:.2f}R | "
              f"avgL={r['avg_loss_R']:.2f}R | PnL=${r['total_pnl']:+.0f}")
    return rows


# ── 2. Strategy Summary ────────────────────────────────────

def strategy_summary(records):
    """EV per strategy -> strategy_summary.csv"""
    by_strat = defaultdict(list)
    for r in records:
        drv = r["primary_driver"]
        if drv:
            by_strat[drv].append(r)

    rows = []
    for name, recs in sorted(by_strat.items()):
        stats = _ev_stats(recs)
        if stats:
            # Find best and worst regime for this strategy
            by_reg = defaultdict(list)
            for r in recs:
                if r["regime"]:
                    by_reg[r["regime"]].append(r)
            best_reg = ""
            worst_reg = ""
            best_ev = -999
            worst_ev = 999
            for reg, reg_recs in by_reg.items():
                reg_stats = _ev_stats(reg_recs)
                if reg_stats and reg_stats["trades"] >= 3:
                    if reg_stats["EV_per_trade"] > best_ev:
                        best_ev = reg_stats["EV_per_trade"]
                        best_reg = reg
                    if reg_stats["EV_per_trade"] < worst_ev:
                        worst_ev = reg_stats["EV_per_trade"]
                        worst_reg = reg

            rows.append({
                "primary_driver": name,
                "trades": stats["trades"],
                "win_rate": stats["win_rate"],
                "EV_per_trade": stats["EV_per_trade"],
                "total_pnl": stats["total_pnl"],
                "best_regime": best_reg,
                "worst_regime": worst_reg,
            })

    if rows:
        _write_csv(os.path.join(_ANALYSIS_DIR, "strategy_summary.csv"), rows, rows[0].keys())

    print("\nSTRATEGY EV SUMMARY")
    print("-" * 75)
    for r in rows:
        print(f"  {r['primary_driver']:25s} | trades={r['trades']:4d} | WR={r['win_rate']:.1%} | "
              f"EV={r['EV_per_trade']:+.3f} | best={r['best_regime']} worst={r['worst_regime']}")
    return rows


# ── 3. Regime Summary ──────────────────────────────────────

def regime_summary(records):
    """EV per regime -> regime_summary.csv"""
    by_reg = defaultdict(list)
    for r in records:
        reg = r["regime"]
        if reg:
            by_reg[reg].append(r)

    rows = []
    for reg, recs in sorted(by_reg.items()):
        stats = _ev_stats(recs)
        if stats:
            rows.append({
                "regime": reg,
                "trades": stats["trades"],
                "win_rate": stats["win_rate"],
                "EV_per_trade": stats["EV_per_trade"],
                "total_pnl": stats["total_pnl"],
            })

    if rows:
        _write_csv(os.path.join(_ANALYSIS_DIR, "regime_summary.csv"), rows, rows[0].keys())

    print("\nREGIME EV SUMMARY")
    print("-" * 75)
    for r in rows:
        print(f"  {r['regime']:12s} | trades={r['trades']:4d} | WR={r['win_rate']:.1%} | "
              f"EV={r['EV_per_trade']:+.3f} | PnL=${r['total_pnl']:+.0f}")
    return rows


# ── 4. Symbol Summary ──────────────────────────────────────

def symbol_summary(records):
    """EV per symbol -> symbol_summary.csv"""
    by_sym = defaultdict(list)
    for r in records:
        sym = r["symbol"]
        if sym:
            by_sym[sym].append(r)

    rows = []
    for sym, recs in sorted(by_sym.items()):
        stats = _ev_stats(recs)
        if stats:
            # Best/worst entry_type for this symbol
            by_et = defaultdict(list)
            for r in recs:
                if r["entry_type"]:
                    by_et[r["entry_type"]].append(r)
            best_et = ""
            worst_et = ""
            best_ev = -999
            worst_ev = 999
            for et, et_recs in by_et.items():
                et_stats = _ev_stats(et_recs)
                if et_stats and et_stats["trades"] >= 2:
                    if et_stats["EV_per_trade"] > best_ev:
                        best_ev = et_stats["EV_per_trade"]
                        best_et = et
                    if et_stats["EV_per_trade"] < worst_ev:
                        worst_ev = et_stats["EV_per_trade"]
                        worst_et = et

            rows.append({
                "symbol": sym,
                "trades": stats["trades"],
                "win_rate": stats["win_rate"],
                "EV_per_trade": stats["EV_per_trade"],
                "total_pnl": stats["total_pnl"],
                "best_entry_type": best_et,
                "worst_entry_type": worst_et,
            })

    if rows:
        _write_csv(os.path.join(_ANALYSIS_DIR, "symbol_summary.csv"), rows, rows[0].keys())

    print("\nSYMBOL EV SUMMARY")
    print("-" * 75)
    for r in rows:
        print(f"  {r['symbol']:10s} | trades={r['trades']:4d} | WR={r['win_rate']:.1%} | "
              f"EV={r['EV_per_trade']:+.3f} | best={r['best_entry_type']} worst={r['worst_entry_type']}")
    return rows


# ── 5. ML Confidence vs PnL (bucketed) ─────────────────────

def ml_conf_vs_pnl(records):
    """Confidence buckets vs avg PnL -> ml_conf_vs_pnl.csv"""
    buckets = defaultdict(list)
    for r in records:
        conf = r["confidence"]
        if conf <= 0:
            continue
        # Create buckets: 60-65, 65-70, 70-75, 75-80, 80-85, 85-90, 90+
        if conf < 65:
            b = "60-65"
        elif conf < 70:
            b = "65-70"
        elif conf < 75:
            b = "70-75"
        elif conf < 80:
            b = "75-80"
        elif conf < 85:
            b = "80-85"
        elif conf < 90:
            b = "85-90"
        else:
            b = "90+"
        buckets[b].append(r)

    rows = []
    for bucket in ["60-65", "65-70", "70-75", "75-80", "80-85", "85-90", "90+"]:
        recs = buckets.get(bucket, [])
        if recs:
            n = len(recs)
            wr = sum(1 for r in recs if r["pnl"] > 0) / n
            rows.append({
                "conf_bucket": bucket,
                "trades": n,
                "win_rate": round(wr, 3),
                "avg_pnl": round(sum(r["pnl"] for r in recs) / n, 2),
                "avg_pnl_R": round(sum(r["rr1"] for r in recs) / n, 2),
                "total_pnl": round(sum(r["pnl"] for r in recs), 2),
            })

    if rows:
        _write_csv(os.path.join(_ANALYSIS_DIR, "ml_conf_vs_pnl.csv"), rows, rows[0].keys())

    print("\nCONFIDENCE vs PnL")
    print("-" * 75)
    for r in rows:
        print(f"  {r['conf_bucket']:8s} | trades={r['trades']:4d} | WR={r['win_rate']:.1%} | "
              f"avg_pnl_R={r['avg_pnl_R']:+.2f} | total=${r['total_pnl']:+.0f}")
    return rows


# ── Main ────────────────────────────────────────────────────

def main():
    records = _parse_trades("outcomes")
    if not records:
        print("No trade data found. Run backtests or paper trading first.")
        print(f"Expected: {_OUTCOMES_FILE} or {_TRADES_FILE}")
        return

    print(f"\nEV Dashboard - {len(records)} trades loaded")

    et_rows = entry_type_summary(records)
    strat_rows = strategy_summary(records)
    reg_rows = regime_summary(records)
    sym_rows = symbol_summary(records)
    conf_rows = ml_conf_vs_pnl(records)

    print("\n" + "=" * 75)
    print("CSVs written to data/analysis/:")
    print("  - entry_type_summary.csv")
    print("  - strategy_summary.csv")
    print("  - regime_summary.csv")
    print("  - symbol_summary.csv")
    print("  - ml_conf_vs_pnl.csv")
    print("=" * 75)


if __name__ == "__main__":
    main()
