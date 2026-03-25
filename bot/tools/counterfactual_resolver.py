"""
Counterfactual Resolver — Resolve unresolved counterfactual log records against price history.

Reads unresolved records from bot/data/llm/counterfactual_log.jsonl,
checks whether they would have hit TP1/TP2/SL using actual historical price data,
and outputs resolved analysis.

Usage:
    cd bot && python tools/counterfactual_resolver.py
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter

sys.path.insert(0, str(Path(__file__).parent.parent))
logging.basicConfig(level=logging.WARNING)

from data.fetcher import DataFetcher


def load_records(path="data/llm/counterfactual_log.jsonl"):
    """Load counterfactual log records."""
    records = []
    with open(path) as f:
        for line in f:
            try:
                records.append(json.loads(line.strip()))
            except (json.JSONDecodeError, ValueError):
                pass
    return records


def resolve_records(records, price_data, max_bars=48):
    """Resolve records against 1h price data.

    For each record, walk forward from entry time up to max_bars (48h).
    Check if price would hit TP1, TP2, or SL first.

    Args:
        records: List of counterfactual records
        price_data: Dict[symbol -> DataFrame with 'time', 'high', 'low', 'close']
        max_bars: Maximum bars to look ahead

    Returns:
        List of resolved records with outcomes
    """
    resolved = []

    for rec in records:
        symbol = rec.get("symbol", "")
        side = rec.get("side", "")
        entry = rec.get("entry_price", 0)
        sl = rec.get("sl", 0)
        tp1 = rec.get("tp1", 0)
        tp2 = rec.get("tp2", 0)
        created_at = rec.get("created_at", "")

        if not all([symbol, side, entry, sl, tp1]) or symbol not in price_data:
            continue

        df = price_data[symbol]
        if df is None or df.empty:
            continue

        # Find the candle after the record was created
        try:
            rec_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue

        # Find starting index
        mask = df["time"] >= rec_time
        if not mask.any():
            continue
        start_idx = mask.idxmax()

        is_long = side == "BUY"
        hit_tp1 = False
        hit_tp2 = False
        hit_sl = False
        max_favorable = entry
        max_adverse = entry
        bars_to_resolve = 0
        exit_price = entry

        # Walk forward
        for j in range(start_idx, min(start_idx + max_bars, len(df))):
            high = float(df["high"].iloc[j])
            low = float(df["low"].iloc[j])
            close = float(df["close"].iloc[j])
            bars_to_resolve = j - start_idx + 1

            if is_long:
                max_favorable = max(max_favorable, high)
                max_adverse = min(max_adverse, low)
                # Check SL first (worst case)
                if low <= sl:
                    hit_sl = True
                    exit_price = sl
                    break
                if high >= tp1:
                    hit_tp1 = True
                    if tp2 and high >= tp2:
                        hit_tp2 = True
                        exit_price = tp2
                        break
                    # After TP1, check if SL gets hit at breakeven
                    # Continue to see if TP2 reached
            else:  # SELL
                max_favorable = min(max_favorable, low)
                max_adverse = max(max_adverse, high)
                if high >= sl:
                    hit_sl = True
                    exit_price = sl
                    break
                if low <= tp1:
                    hit_tp1 = True
                    if tp2 and low <= tp2:
                        hit_tp2 = True
                        exit_price = tp2
                        break

        # Calculate hypothetical PnL
        if is_long:
            if hit_tp1 and not hit_sl:
                hyp_pnl_pct = (tp1 - entry) / entry * 100
            elif hit_sl:
                hyp_pnl_pct = (sl - entry) / entry * 100
            else:
                # Unreached — use close of last bar
                last_close = float(df["close"].iloc[min(start_idx + max_bars - 1, len(df) - 1)])
                hyp_pnl_pct = (last_close - entry) / entry * 100
        else:
            if hit_tp1 and not hit_sl:
                hyp_pnl_pct = (entry - tp1) / entry * 100
            elif hit_sl:
                hyp_pnl_pct = (entry - sl) / entry * 100
            else:
                last_close = float(df["close"].iloc[min(start_idx + max_bars - 1, len(df) - 1)])
                hyp_pnl_pct = (entry - last_close) / entry * 100

        rec_resolved = {
            **rec,
            "resolved": True,
            "would_hit_tp1": hit_tp1 and not hit_sl,
            "would_hit_tp2": hit_tp2 and not hit_sl,
            "would_hit_sl": hit_sl,
            "max_favorable_price": max_favorable,
            "max_adverse_price": max_adverse,
            "hypothetical_pnl_pct": round(hyp_pnl_pct, 4),
            "bars_to_resolve": bars_to_resolve,
        }
        resolved.append(rec_resolved)

    return resolved


def analyze_resolved(resolved):
    """Analyze resolved counterfactual records."""
    total = len(resolved)
    if total == 0:
        print("No resolved records.")
        return {}

    tp1_wins = [r for r in resolved if r["would_hit_tp1"]]
    sl_losses = [r for r in resolved if r["would_hit_sl"]]
    unresolved = [r for r in resolved if not r["would_hit_tp1"] and not r["would_hit_sl"]]

    print(f"\n{'='*80}")
    print(f"COUNTERFACTUAL ANALYSIS — {total} records resolved")
    print(f"{'='*80}")
    print(f"  Would win (TP1):  {len(tp1_wins):>5d} ({len(tp1_wins)/total*100:.1f}%)")
    print(f"  Would lose (SL):  {len(sl_losses):>5d} ({len(sl_losses)/total*100:.1f}%)")
    print(f"  Unresolved (48h): {len(unresolved):>5d} ({len(unresolved)/total*100:.1f}%)")

    # By skip reason
    print(f"\n--- By Skip Reason ---")
    by_reason = defaultdict(lambda: {"total": 0, "wins": 0, "losses": 0, "pnl_sum": 0})
    for r in resolved:
        reason = r.get("skip_reason", "?")
        by_reason[reason]["total"] += 1
        if r["would_hit_tp1"]:
            by_reason[reason]["wins"] += 1
        if r["would_hit_sl"]:
            by_reason[reason]["losses"] += 1
        by_reason[reason]["pnl_sum"] += r.get("hypothetical_pnl_pct", 0)

    for reason, d in sorted(by_reason.items(), key=lambda x: -x[1]["total"]):
        wr = d["wins"] / d["total"] * 100 if d["total"] else 0
        print(f"  {reason:35s}: {d['total']:>5d} | WR={wr:>5.1f}% | PnL_sum={d['pnl_sum']:>+8.1f}%")

    # By symbol
    print(f"\n--- By Symbol ---")
    by_sym = defaultdict(lambda: {"total": 0, "wins": 0, "pnl_sum": 0})
    for r in resolved:
        sym = r.get("symbol", "?")
        by_sym[sym]["total"] += 1
        if r["would_hit_tp1"]:
            by_sym[sym]["wins"] += 1
        by_sym[sym]["pnl_sum"] += r.get("hypothetical_pnl_pct", 0)

    for sym, d in sorted(by_sym.items(), key=lambda x: -x[1]["total"]):
        wr = d["wins"] / d["total"] * 100 if d["total"] else 0
        print(f"  {sym:10s}: {d['total']:>5d} | WR={wr:>5.1f}% | PnL_sum={d['pnl_sum']:>+8.1f}%")

    # By confidence bucket
    print(f"\n--- By Confidence Bucket ---")
    conf_buckets = defaultdict(lambda: {"total": 0, "wins": 0, "losses": 0, "pnl_sum": 0})
    for r in resolved:
        conf = r.get("confidence", 0)
        if conf < 55:
            bucket = "<55"
        elif conf < 60:
            bucket = "55-60"
        elif conf < 63:
            bucket = "60-63"
        elif conf < 65:
            bucket = "63-65"
        elif conf < 68:
            bucket = "65-68"
        else:
            bucket = "68+"
        conf_buckets[bucket]["total"] += 1
        if r["would_hit_tp1"]:
            conf_buckets[bucket]["wins"] += 1
        if r["would_hit_sl"]:
            conf_buckets[bucket]["losses"] += 1
        conf_buckets[bucket]["pnl_sum"] += r.get("hypothetical_pnl_pct", 0)

    for bucket in ["<55", "55-60", "60-63", "63-65", "65-68", "68+"]:
        d = conf_buckets[bucket]
        if d["total"] > 0:
            wr = d["wins"] / d["total"] * 100
            lr = d["losses"] / d["total"] * 100
            avg_pnl = d["pnl_sum"] / d["total"]
            print(f"  {bucket:10s}: {d['total']:>5d} | WR={wr:>5.1f}% SL={lr:>5.1f}% | avg_PnL={avg_pnl:>+.3f}%")

    # By side
    print(f"\n--- By Side ---")
    by_side = defaultdict(lambda: {"total": 0, "wins": 0, "pnl_sum": 0})
    for r in resolved:
        side = r.get("side", "?")
        by_side[side]["total"] += 1
        if r["would_hit_tp1"]:
            by_side[side]["wins"] += 1
        by_side[side]["pnl_sum"] += r.get("hypothetical_pnl_pct", 0)

    for side, d in sorted(by_side.items()):
        wr = d["wins"] / d["total"] * 100 if d["total"] else 0
        print(f"  {side:10s}: {d['total']:>5d} | WR={wr:>5.1f}% | PnL_sum={d['pnl_sum']:>+8.1f}%")

    # Speed of resolution
    print(f"\n--- Resolution Speed (bars to resolve) ---")
    bars_buckets = defaultdict(lambda: {"total": 0, "wins": 0})
    for r in resolved:
        if not r["would_hit_tp1"] and not r["would_hit_sl"]:
            continue
        bars = r.get("bars_to_resolve", 0)
        if bars <= 3:
            bucket = "1-3h"
        elif bars <= 6:
            bucket = "4-6h"
        elif bars <= 12:
            bucket = "7-12h"
        elif bars <= 24:
            bucket = "13-24h"
        else:
            bucket = "25-48h"
        bars_buckets[bucket]["total"] += 1
        if r["would_hit_tp1"]:
            bars_buckets[bucket]["wins"] += 1

    for bucket in ["1-3h", "4-6h", "7-12h", "13-24h", "25-48h"]:
        d = bars_buckets[bucket]
        if d["total"] > 0:
            wr = d["wins"] / d["total"] * 100
            print(f"  {bucket:10s}: {d['total']:>5d} resolved | WR={wr:>5.1f}%")

    # Top 15 missed opportunities
    print(f"\n--- Top 15 Missed Opportunities ---")
    winners = sorted(resolved, key=lambda x: -(x.get("hypothetical_pnl_pct", 0)))
    for r in winners[:15]:
        pnl = r.get("hypothetical_pnl_pct", 0)
        if pnl <= 0:
            break
        print(f"  {r['symbol']:6s} {r['side']:4s} conf={r.get('confidence',0):5.1f}% "
              f"reason={r.get('skip_reason','?'):25s} "
              f"pnl={pnl:+6.2f}% bars={r.get('bars_to_resolve',0):>3d}")

    # Dollar value estimate (assuming $10k equity, 0.5% risk per trade)
    print(f"\n--- Estimated Dollar Value (if taken at 0.5x size) ---")
    total_hyp_pnl = sum(r.get("hypothetical_pnl_pct", 0) for r in resolved)
    avg_pnl = total_hyp_pnl / len(resolved) if resolved else 0
    # Rough estimate: avg position ~$50 risk, scale by pnl%
    # Better: use actual entry/sl to compute risk per trade
    risk_per_trade = 25  # $50 base * 0.5x = $25 risk at half size
    net_dollar_est = 0
    for r in resolved:
        pnl_pct = r.get("hypothetical_pnl_pct", 0)
        entry = r.get("entry_price", 0)
        sl = r.get("sl", 0)
        if entry and sl:
            stop_width_pct = abs(entry - sl) / entry * 100
            if stop_width_pct > 0:
                # PnL in $ = (pnl_pct / stop_width_pct) * risk_per_trade
                net_dollar_est += (pnl_pct / stop_width_pct) * risk_per_trade

    print(f"  Total hypothetical PnL: {total_hyp_pnl:+.1f}% (avg {avg_pnl:+.3f}% per signal)")
    print(f"  Estimated $ impact (0.5x size): ${net_dollar_est:+,.0f}")
    print(f"  Records: {len(resolved)}")

    return {
        "total": total,
        "wins": len(tp1_wins),
        "losses": len(sl_losses),
        "win_rate": len(tp1_wins) / total if total else 0,
        "total_hyp_pnl_pct": total_hyp_pnl,
        "est_dollar_impact": net_dollar_est,
    }


if __name__ == "__main__":
    print("Loading counterfactual records...")
    records = load_records()
    unresolved = [r for r in records if not r.get("resolved")]
    print(f"Loaded {len(records)} records, {len(unresolved)} unresolved")

    if not unresolved:
        print("All records already resolved!")
        sys.exit(0)

    # Get unique symbols
    symbols = list(set(r.get("symbol", "") for r in unresolved if r.get("symbol")))
    print(f"Symbols: {symbols}")

    # Fetch 1h price data for resolution
    print("Fetching price data...")
    fetcher = DataFetcher(cache_ttl=3600, backtest_mode=True)
    fetcher.backtest_days = 120  # Need enough history
    price_data = {}
    from trading_config import DEFAULT_SYMBOLS
    for sym in symbols:
        sym_cfg = DEFAULT_SYMBOLS.get(sym)
        if sym_cfg:
            data = fetcher.fetch_multi_timeframe(sym, sym_cfg.coingecko_id, ["1h"])
            if "1h" in data and not data["1h"].empty:
                price_data[sym] = data["1h"]
                print(f"  {sym}: {len(data['1h'])} candles")

    # Resolve
    print("Resolving records...")
    resolved = resolve_records(unresolved, price_data, max_bars=48)
    print(f"Resolved {len(resolved)} out of {len(unresolved)}")

    # Analyze
    results = analyze_resolved(resolved)

    # Save resolved records
    out_file = "data/counterfactual_resolved.json"
    with open(out_file, "w") as f:
        json.dump({"summary": results, "records": resolved[:1000]}, f, indent=2, default=str)
    print(f"\nSaved top 1000 resolved records to {out_file}")
