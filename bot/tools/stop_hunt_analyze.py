"""Aggregate stop_hunt_results.csv into report statistics."""
from __future__ import annotations

import pandas as pd
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "data" / "stop_hunt_results.csv"
TRADES = ROOT / "data" / "trades.csv"

MIN_N = 5  # small-n flag


def main() -> dict:
    r = pd.read_csv(RESULTS)
    r["utc_hour"] = r["utc_hour"].astype(int)
    n = len(r)

    # Load trades for PnL context
    trades = pd.read_csv(TRADES)
    sl_trades = trades[trades["sl_hit"] == True].reset_index(drop=True)

    # Overall hunt percentages
    windows = [5, 15, 30, 60]
    overall = {w: round(r[f"hunt_{w}m"].mean() * 100, 1) for w in windows}

    # Per-symbol (hunt_30m)
    per_sym = {}
    for sym, grp in r.groupby("symbol"):
        per_sym[sym] = {
            "n": len(grp),
            "hunt_5m_pct": round(grp["hunt_5m"].mean() * 100, 1),
            "hunt_15m_pct": round(grp["hunt_15m"].mean() * 100, 1),
            "hunt_30m_pct": round(grp["hunt_30m"].mean() * 100, 1),
            "hunt_60m_pct": round(grp["hunt_60m"].mean() * 100, 1),
            "small_n": len(grp) < MIN_N,
        }

    # Per-time-of-day (UTC bucket: asia 0-8, europe 8-16, us 16-24)
    def bucket(h):
        if h < 8:
            return "asia_0-8"
        if h < 16:
            return "europe_8-16"
        return "us_16-24"
    r["tod"] = r["utc_hour"].apply(bucket)
    per_tod = {}
    for tod, grp in r.groupby("tod"):
        per_tod[tod] = {
            "n": len(grp),
            "hunt_30m_pct": round(grp["hunt_30m"].mean() * 100, 1),
            "hunt_60m_pct": round(grp["hunt_60m"].mean() * 100, 1),
            "small_n": len(grp) < MIN_N,
        }

    # Symbol x TOD cross
    cross = {}
    for (sym, tod), grp in r.groupby(["symbol", "tod"]):
        key = f"{sym}__{tod}"
        cross[key] = {
            "n": len(grp),
            "hunt_30m_pct": round(grp["hunt_30m"].mean() * 100, 1),
            "small_n": len(grp) < MIN_N,
        }

    # Wider-stop simulation
    wider = {
        "would_survive_1_5x_pct": round(r["would_survive_1_5x"].mean() * 100, 1),
        "would_survive_2_0x_pct": round(r["would_survive_2_0x"].mean() * 100, 1),
    }
    wider_per_sym = {}
    for sym, grp in r.groupby("symbol"):
        wider_per_sym[sym] = {
            "n": len(grp),
            "survive_1_5x_pct": round(grp["would_survive_1_5x"].mean() * 100, 1),
            "survive_2_0x_pct": round(grp["would_survive_2_0x"].mean() * 100, 1),
        }

    # Continuation analysis (legitimate exits)
    # If hunt_60m == False AND continuation_pct_60m > 0.2% of entry, it's a legit follow-through
    r["legit_exit"] = (~r["hunt_60m"]) & (r["continuation_pct_60m"] > 0.2)
    legit_pct = round(r["legit_exit"].mean() * 100, 1)

    # Biggest hunt contributor cell (symbol x side x tod with highest hunt rate, n>=MIN_N)
    r["cell"] = r["symbol"] + "_" + r["side"] + "_" + r["tod"]
    cell_stats = r.groupby("cell").agg(
        n=("hunt_30m", "size"),
        hunt_30m=("hunt_30m", "mean"),
    ).reset_index()
    cell_stats["hunt_30m_pct"] = (cell_stats["hunt_30m"] * 100).round(1)
    cell_stats = cell_stats[cell_stats["n"] >= MIN_N]
    biggest = cell_stats.sort_values(
        ["hunt_30m_pct", "n"], ascending=[False, False]
    ).head(5).to_dict(orient="records")

    # Distribution of SL width pct
    sl_width = r["sl_width_pct"].describe().to_dict()

    report = {
        "total_sl_trades_analyzed": n,
        "total_sl_trades_in_csv": int(sl_trades.shape[0]),
        "coverage_pct": round(n / sl_trades.shape[0] * 100, 1),
        "overall_hunt_rate_pct": overall,
        "per_symbol_hunt": per_sym,
        "per_time_of_day_hunt": per_tod,
        "symbol_x_tod_cross": cross,
        "wider_stop_survival": wider,
        "wider_stop_per_symbol": wider_per_sym,
        "legit_follow_through_pct_60m": legit_pct,
        "biggest_hunt_cells": biggest,
        "sl_width_pct_stats": {k: round(v, 3) for k, v in sl_width.items()},
    }
    print(json.dumps(report, indent=2, default=str))
    return report


if __name__ == "__main__":
    main()
