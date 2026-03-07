#!/usr/bin/env python3
"""
Deep backtest analysis — cross-dimensional breakdowns.

Usage:
    cd bot
    python deep_analysis.py backtest_20d.csv
    python deep_analysis.py backtest_60d.csv
    python deep_analysis.py backtest_180d.csv
"""

import csv
import sys
from collections import defaultdict


def load(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def pnl(t):
    return float(t.get("pnl", 0) or 0)


def bucket_stats(trades, key_fn):
    b = defaultdict(lambda: {"n": 0, "w": 0, "pnl": 0.0})
    for t in trades:
        k = key_fn(t)
        if k is None:
            continue
        p = pnl(t)
        b[k]["n"] += 1
        b[k]["pnl"] += p
        if p > 0:
            b[k]["w"] += 1
    return b


def print_bucket(buckets, order=None, min_trades=0):
    keys = order if order else sorted(buckets.keys())
    for k in keys:
        if k not in buckets:
            continue
        v = buckets[k]
        if v["n"] < min_trades:
            continue
        wr = v["w"] / v["n"] * 100 if v["n"] else 0
        avg = v["pnl"] / v["n"] if v["n"] else 0
        print(f"  {str(k):<25s} {v['n']:4d} trades  WR={wr:4.0f}%  PnL=${v['pnl']:10.2f}  avg=${avg:8.2f}")


def profit_factor(trades_list):
    gross_w = sum(pnl(t) for t in trades_list if pnl(t) > 0)
    gross_l = abs(sum(pnl(t) for t in trades_list if pnl(t) <= 0))
    return round(gross_w / gross_l, 2) if gross_l > 0 else float("inf")


def main():
    if len(sys.argv) < 2:
        print("Usage: python deep_analysis.py <trades.csv>")
        sys.exit(1)

    path = sys.argv[1]
    trades = load(path)
    total = len(trades)
    winners = [t for t in trades if pnl(t) > 0]
    losers = [t for t in trades if pnl(t) <= 0]
    total_pnl = sum(pnl(t) for t in trades)

    print(f"\n{'=' * 70}")
    print(f"  DEEP ANALYSIS: {path} ({total} close events)")
    print(f"  Net PnL: ${total_pnl:,.2f}  |  WR: {len(winners)/total*100:.1f}%  |  PF: {profit_factor(trades)}")
    print(f"{'=' * 70}")

    # ── SYMBOL x SIDE ──
    print(f"\n{'─' * 70}")
    print("  SYMBOL x SIDE — where do longs/shorts work?")
    print(f"{'─' * 70}")
    b = bucket_stats(trades, lambda t: f"{t['symbol']}_{t.get('side', '?')}")
    print_bucket(b)

    # ── CONFIDENCE BUCKETS ──
    print(f"\n{'─' * 70}")
    print("  CONFIDENCE BUCKETS — is high confidence actually better?")
    print(f"{'─' * 70}")

    def conf_bucket(t):
        try:
            c = float(t.get("confidence", 0) or 0)
        except (ValueError, TypeError):
            return None
        if c < 50: return "<50"
        if c < 60: return "50-59"
        if c < 70: return "60-69"
        if c < 80: return "70-79"
        if c < 90: return "80-89"
        return "90+"

    b = bucket_stats(trades, conf_bucket)
    print_bucket(b, order=["<50", "50-59", "60-69", "70-79", "80-89", "90+"])

    # ── CLOSE REASON ──
    print(f"\n{'─' * 70}")
    print("  CLOSE REASON — how are trades ending?")
    print(f"{'─' * 70}")
    b = bucket_stats(trades, lambda t: t.get("close_reason", "?"))
    print_bucket(b)

    # ── STATE PATH ──
    print(f"\n{'─' * 70}")
    print("  STATE PATH — position lifecycle flows (top 10)")
    print(f"{'─' * 70}")
    b = bucket_stats(trades, lambda t: t.get("state_path", "?"))
    top = sorted(b.items(), key=lambda x: x[1]["n"], reverse=True)[:10]
    print_bucket(dict(top), order=[k for k, _ in top])

    # ── HOLD TIME ──
    print(f"\n{'─' * 70}")
    print("  HOLD TIME — what duration is most profitable?")
    print(f"{'─' * 70}")

    def dur_bucket(t):
        try:
            d = float(t.get("duration_h", 0) or 0)
        except (ValueError, TypeError):
            return None
        if d < 1: return "<1h"
        if d < 2: return "1-2h"
        if d < 4: return "2-4h"
        if d < 8: return "4-8h"
        if d < 16: return "8-16h"
        return "16h+"

    b = bucket_stats(trades, dur_bucket)
    print_bucket(b, order=["<1h", "1-2h", "2-4h", "4-8h", "8-16h", "16h+"])

    # ── LEVERAGE BUCKETS ──
    print(f"\n{'─' * 70}")
    print("  LEVERAGE — does higher leverage help or hurt?")
    print(f"{'─' * 70}")

    def lev_bucket(t):
        try:
            lev = float(t.get("leverage", 0) or 0)
        except (ValueError, TypeError):
            return None
        if lev <= 1: return "1x"
        if lev <= 2: return "1-2x"
        if lev <= 3: return "2-3x"
        if lev <= 4: return "3-4x"
        return "4x+"

    b = bucket_stats(trades, lev_bucket)
    print_bucket(b, order=["1x", "1-2x", "2-3x", "3-4x", "4x+"])

    # ── R:R ACHIEVED ──
    print(f"\n{'─' * 70}")
    print("  R:R ACHIEVED — are winners capturing enough R?")
    print(f"{'─' * 70}")

    def rr_bucket(t):
        try:
            rr = float(t.get("rr_achieved", 0) or 0)
        except (ValueError, TypeError):
            return None
        if rr <= 0: return "<=0R"
        if rr < 1: return "0-1R"
        if rr < 2: return "1-2R"
        if rr < 3: return "2-3R"
        return "3R+"

    b = bucket_stats(trades, rr_bucket)
    print_bucket(b, order=["<=0R", "0-1R", "1-2R", "2-3R", "3R+"])

    # ── STRATEGY AGREEMENT ──
    has_agree = any(t.get("num_agree", "") not in ("", "0") for t in trades)
    if has_agree:
        print(f"\n{'─' * 70}")
        print("  STRATEGY AGREEMENT — do more strategies agreeing = better trades?")
        print(f"{'─' * 70}")

        def agree_bucket(t):
            v = t.get("num_agree", "")
            if v == "":
                return None
            return f"{v}_agree"

        b = bucket_stats(trades, agree_bucket)
        print_bucket(b)

    # ── SYMBOL x CLOSE REASON ──
    print(f"\n{'─' * 70}")
    print("  SYMBOL x CLOSE REASON — where does each coin bleed?")
    print(f"{'─' * 70}")
    b = bucket_stats(trades, lambda t: f"{t['symbol']}_{t.get('close_reason', '?')}")
    print_bucket(b)

    # ── STREAK ANALYSIS ──
    print(f"\n{'─' * 70}")
    print("  STREAK ANALYSIS")
    print(f"{'─' * 70}")
    max_win = max_loss = cur_win = cur_loss = 0
    for t in trades:
        if pnl(t) > 0:
            cur_win += 1; cur_loss = 0
            max_win = max(max_win, cur_win)
        else:
            cur_loss += 1; cur_win = 0
            max_loss = max(max_loss, cur_loss)
    print(f"  Max win streak:  {max_win}")
    print(f"  Max loss streak: {max_loss}")

    # ── FEE IMPACT ──
    print(f"\n{'─' * 70}")
    print("  FEE IMPACT")
    print(f"{'─' * 70}")
    total_fees = sum(float(t.get("fee", 0) or 0) for t in trades)
    gross = total_pnl + total_fees
    print(f"  Gross PnL:      ${gross:10.2f}")
    print(f"  Total fees:     ${total_fees:10.2f}")
    print(f"  Net PnL:        ${total_pnl:10.2f}")
    if gross > 0:
        print(f"  Fee drag:       {total_fees/gross*100:.1f}% of gross")
    print(f"  Avg fee/trade:  ${total_fees/total:.2f}")

    # ── WINNER vs LOSER PROFILE ──
    print(f"\n{'─' * 70}")
    print("  WINNER vs LOSER PROFILE")
    print(f"{'─' * 70}")
    if winners:
        avg_w_dur = sum(float(t.get("duration_h", 0) or 0) for t in winners) / len(winners)
        avg_w_conf = sum(float(t.get("confidence", 0) or 0) for t in winners) / len(winners)
        avg_w_lev = sum(float(t.get("leverage", 0) or 0) for t in winners) / len(winners)
        avg_w_pnl = sum(pnl(t) for t in winners) / len(winners)
        print(f"  Winners ({len(winners):3d}):  avg=${avg_w_pnl:7.2f}  dur={avg_w_dur:.1f}h  conf={avg_w_conf:.0f}  lev={avg_w_lev:.1f}x")
    if losers:
        avg_l_dur = sum(float(t.get("duration_h", 0) or 0) for t in losers) / len(losers)
        avg_l_conf = sum(float(t.get("confidence", 0) or 0) for t in losers) / len(losers)
        avg_l_lev = sum(float(t.get("leverage", 0) or 0) for t in losers) / len(losers)
        avg_l_pnl = sum(pnl(t) for t in losers) / len(losers)
        print(f"  Losers  ({len(losers):3d}):  avg=${avg_l_pnl:7.2f}  dur={avg_l_dur:.1f}h  conf={avg_l_conf:.0f}  lev={avg_l_lev:.1f}x")

    # ── TOP 10 WINNERS ──
    print(f"\n{'─' * 70}")
    print("  TOP 10 WINNERS")
    print(f"{'─' * 70}")
    for t in sorted(trades, key=lambda t: pnl(t), reverse=True)[:10]:
        p = pnl(t)
        print(f"  {t['symbol']:<6s} {t.get('side',''):<5s} conf={t.get('confidence','?'):>3s}  "
              f"lev={t.get('leverage','?'):>4s}  dur={t.get('duration_h','?'):>5s}h  "
              f"{t.get('close_reason','?'):<15s} ${p:+.2f}")

    # ── TOP 10 LOSERS ──
    print(f"\n{'─' * 70}")
    print("  TOP 10 LOSERS")
    print(f"{'─' * 70}")
    for t in sorted(trades, key=lambda t: pnl(t))[:10]:
        p = pnl(t)
        print(f"  {t['symbol']:<6s} {t.get('side',''):<5s} conf={t.get('confidence','?'):>3s}  "
              f"lev={t.get('leverage','?'):>4s}  dur={t.get('duration_h','?'):>5s}h  "
              f"{t.get('close_reason','?'):<15s} ${p:+.2f}")

    print(f"\n{'=' * 70}")
    print("  DONE")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
