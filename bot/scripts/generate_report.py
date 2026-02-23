"""
Generate a human-readable markdown report from performance data.

Reads:
  data/analysis/performance.json
  data/analysis/entry_type_summary.csv
  data/analysis/strategy_summary.csv
  data/analysis/regime_summary.csv

Writes:
  data/analysis/performance_report.md

Usage:
    python -m scripts.generate_report
"""

import csv
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("report")

_ANALYSIS_DIR = os.path.join("data", "analysis")
_PERF_FILE = os.path.join(_ANALYSIS_DIR, "performance.json")
_REPORT_FILE = os.path.join(_ANALYSIS_DIR, "performance_report.md")


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


def generate_report():
    # Load performance.json
    perf = {}
    if os.path.exists(_PERF_FILE):
        with open(_PERF_FILE, encoding="utf-8") as f:
            perf = json.load(f)

    # Load CSVs (from ev_dashboard)
    et_rows = _read_csv(os.path.join(_ANALYSIS_DIR, "entry_type_summary.csv"))
    strat_rows = _read_csv(os.path.join(_ANALYSIS_DIR, "strategy_summary.csv"))
    reg_rows = _read_csv(os.path.join(_ANALYSIS_DIR, "regime_summary.csv"))
    sym_rows = _read_csv(os.path.join(_ANALYSIS_DIR, "symbol_summary.csv"))

    lines = []
    lines.append("# Performance Report")
    lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("")

    # Overview
    lines.append("## Overview")
    lines.append(f"- Total trades: {perf.get('total_trades', 'N/A')}")
    lines.append(f"- Win rate (last 20): {perf.get('win_rate_20', 0):.1%}")
    lines.append(f"- Win rate (last 50): {perf.get('win_rate_50', 0):.1%}")
    lines.append(f"- Total PnL: ${perf.get('total_pnl', 0):+,.2f}")
    lines.append(f"- Avg PnL per trade: ${perf.get('avg_pnl', 0):+,.2f}")
    lines.append(f"- TP1 success rate: {perf.get('tp1_success_rate', 0):.1%}")
    lines.append(f"- TP1->SL rate: {perf.get('tp1_to_sl_rate', 0):.1%}")
    lines.append("")

    # Entry Type Summary
    if et_rows:
        lines.append("## Entry Type Performance")
        lines.append("")
        lines.append("| Type | Trades | WR | EV/trade | Avg Win R | Avg Loss R | PnL |")
        lines.append("|------|--------|-----|----------|-----------|------------|-----|")
        best_et = None
        best_ev = -999
        worst_et = None
        worst_ev = 999
        for r in et_rows:
            ev = _safe_float(r.get("EV_per_trade"))
            trades = int(_safe_float(r.get("trades")))
            if trades >= 5:
                if ev > best_ev:
                    best_ev = ev
                    best_et = r.get("entry_type")
                if ev < worst_ev:
                    worst_ev = ev
                    worst_et = r.get("entry_type")
            lines.append(
                f"| {r.get('entry_type', '')} | {r.get('trades', '')} | "
                f"{_safe_float(r.get('win_rate')):.1%} | {ev:+.3f} | "
                f"{_safe_float(r.get('avg_win_R')):.2f} | {_safe_float(r.get('avg_loss_R')):.2f} | "
                f"${_safe_float(r.get('total_pnl')):+.0f} |"
            )
        lines.append("")
        if best_et:
            lines.append(f"**Best entry type**: {best_et} (EV={best_ev:+.3f})")
        if worst_et:
            lines.append(f"**Worst entry type**: {worst_et} (EV={worst_ev:+.3f})")
        lines.append("")

    # Strategy Summary
    if strat_rows:
        lines.append("## Strategy Performance")
        lines.append("")
        lines.append("| Strategy | Trades | WR | EV/trade | PnL | Best Regime | Worst Regime |")
        lines.append("|----------|--------|-----|----------|-----|-------------|--------------|")
        worst_strat = None
        worst_strat_ev = 999
        for r in strat_rows:
            ev = _safe_float(r.get("EV_per_trade"))
            trades = int(_safe_float(r.get("trades")))
            if trades >= 5 and ev < worst_strat_ev:
                worst_strat_ev = ev
                worst_strat = r.get("primary_driver")
            lines.append(
                f"| {r.get('primary_driver', '')} | {r.get('trades', '')} | "
                f"{_safe_float(r.get('win_rate')):.1%} | {ev:+.3f} | "
                f"${_safe_float(r.get('total_pnl')):+.0f} | "
                f"{r.get('best_regime', '')} | {r.get('worst_regime', '')} |"
            )
        lines.append("")
        if worst_strat:
            lines.append(f"**Worst strategy**: {worst_strat} (EV={worst_strat_ev:+.3f})")
        lines.append("")

    # Regime Summary
    if reg_rows:
        lines.append("## Regime Performance")
        lines.append("")
        lines.append("| Regime | Trades | WR | EV/trade | PnL |")
        lines.append("|--------|--------|-----|----------|-----|")
        best_reg = None
        best_reg_ev = -999
        for r in reg_rows:
            ev = _safe_float(r.get("EV_per_trade"))
            trades = int(_safe_float(r.get("trades")))
            if trades >= 5 and ev > best_reg_ev:
                best_reg_ev = ev
                best_reg = r.get("regime")
            lines.append(
                f"| {r.get('regime', '')} | {r.get('trades', '')} | "
                f"{_safe_float(r.get('win_rate')):.1%} | {ev:+.3f} | "
                f"${_safe_float(r.get('total_pnl')):+.0f} |"
            )
        lines.append("")
        if best_reg:
            lines.append(f"**Best regime**: {best_reg} (EV={best_reg_ev:+.3f})")
        lines.append("")

    # Recommendations
    lines.append("## Recommendations")
    lines.append("")
    recs = []
    if worst_et and worst_ev < 0:
        recs.append(f"- **{worst_et}** has negative EV ({worst_ev:+.3f}). "
                     "Consider tightening TP1/SL or increasing TP1 close % for this profile.")
    if worst_strat and worst_strat_ev < 0:
        recs.append(f"- **{worst_strat}** has negative EV ({worst_strat_ev:+.3f}). "
                     "Consider reducing its weight in the ensemble.")
    if best_et:
        recs.append(f"- **{best_et}** is the best-performing entry type. "
                     "Consider allowing more capital allocation to this profile.")
    if not recs:
        recs.append("- Not enough data for recommendations. Run more trades or backtests.")
    lines.extend(recs)
    lines.append("")

    # Write report
    os.makedirs(_ANALYSIS_DIR, exist_ok=True)
    report_text = "\n".join(lines)
    with open(_REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report_text)

    print(report_text)
    logger.info(f"Report written to {_REPORT_FILE}")
    return report_text


if __name__ == "__main__":
    generate_report()
