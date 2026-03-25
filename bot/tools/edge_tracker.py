"""
Edge Tracker — Quant-grade signal quality analysis.

Tracks rejected signals and measures what WOULD have happened.
Builds a picture of where our edge exists but isn't being captured.

Reads from paper_trading_intel.jsonl and compares rejection prices
to subsequent price movement to identify:
1. Correctly rejected signals (saved us money)
2. Missed profitable trades (we left money on the table)
3. Strategy-specific edge by regime
4. Optimal confidence thresholds by empirical data
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

INTEL_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "paper_trading_intel.jsonl")
EDGE_REPORT = os.path.join(os.path.dirname(__file__), "..", "data", "edge_analysis.md")


def load_intel():
    """Load all intel entries."""
    entries = []
    if not os.path.exists(INTEL_FILE):
        return entries
    with open(INTEL_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries


def get_current_prices():
    """Get current prices."""
    try:
        from data.fetcher import DataFetcher
        f = DataFetcher()
        prices = {}
        coins = {"BTC": "bitcoin", "SOL": "solana", "HYPE": "hyperliquid"}
        for sym, cid in coins.items():
            try:
                df = f.fetch_ohlcv(sym, cid, "1h")
                if df is not None and len(df) > 0:
                    prices[sym] = float(df.iloc[-1]["close"])
            except Exception:
                pass
        return prices
    except Exception:
        return {}


def analyze_rejections(entries, current_prices):
    """Analyze all rejected signals vs current price."""
    rejections = [e for e in entries if e["category"] == "signal_rejection"]
    near_misses = [e for e in entries if e["category"] == "near_miss"]

    results = {
        "correct_rejections": [],
        "missed_profits": [],
        "inconclusive": [],
    }

    # Deduplicate by (symbol, side, epoch rounded to 5min)
    seen = set()
    unique_rejections = []
    for r in rejections:
        key = (r["data"]["symbol"], r["data"]["side"], int(r["epoch"] // 300))
        if key not in seen:
            seen.add(key)
            unique_rejections.append(r)

    for rej in unique_rejections:
        d = rej["data"]
        sym = d["symbol"]
        side = d["side"]
        tech = d.get("technicals", {})
        rej_price = tech.get("price")
        now_price = current_prices.get(sym)
        if not rej_price or not now_price:
            continue

        # How much did price move in the signal direction?
        if side == "SELL":
            move_pct = (rej_price - now_price) / rej_price * 100
        else:
            move_pct = (now_price - rej_price) / rej_price * 100

        age_min = (time.time() - rej["epoch"]) / 60

        entry = {
            "symbol": sym, "side": side, "ev": d["ev"],
            "win_prob": d["win_prob"], "rr": d["rr"],
            "rej_price": rej_price, "now_price": now_price,
            "move_pct": move_pct, "age_min": age_min,
            "rsi_at_rej": tech.get("rsi"),
            "trend_at_rej": tech.get("trend"),
            "regime": tech.get("ema_cross"),
        }

        if move_pct > 1.0:
            results["missed_profits"].append(entry)
        elif move_pct < -0.5:
            results["correct_rejections"].append(entry)
        else:
            results["inconclusive"].append(entry)

    return results


def analyze_strategy_maps(entries):
    """Analyze which strategies fire where and build a coverage map."""
    maps = [e for e in entries if e["category"] == "strategy_map"]

    # Count how often each strategy fires per symbol
    fire_counts = defaultdict(lambda: defaultdict(int))
    total_scans = defaultdict(int)

    seen = set()
    for m in maps:
        d = m["data"]
        key = (d["symbol"], int(m["epoch"] // 300))
        if key in seen:
            continue
        seen.add(key)

        sym = d["symbol"]
        total_scans[sym] += 1
        for strat in d["fired"]:
            fire_counts[sym][strat] += 1

    return fire_counts, total_scans


def analyze_regime_accuracy(entries, current_prices):
    """Track regime classification accuracy over time."""
    regimes = [e for e in entries if e["category"] == "regime_observation"]

    mismatches = 0
    total = 0
    details = []

    seen = set()
    for r in regimes:
        d = r["data"]
        key = (d["symbol"], int(r["epoch"] // 300))
        if key in seen:
            continue
        seen.add(key)

        total += 1
        if d.get("mismatch"):
            mismatches += 1
            details.append(d)

    return {
        "total": total,
        "mismatches": mismatches,
        "mismatch_rate": mismatches / total if total > 0 else 0,
        "details": details,
    }


def generate_report():
    """Generate comprehensive edge analysis."""
    entries = load_intel()
    if not entries:
        print("No intel data yet.")
        return

    current_prices = get_current_prices()
    rej_analysis = analyze_rejections(entries, current_prices)
    fire_counts, total_scans = analyze_strategy_maps(entries)
    regime_analysis = analyze_regime_accuracy(entries, current_prices)

    # Price snapshots for trend
    snapshots = [e for e in entries if e["category"] == "price_snapshot"]

    lines = []
    lines.append("# Edge Analysis Report")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"Intel entries: {len(entries)}")
    lines.append(f"Price snapshots: {len(snapshots)}")
    lines.append("")

    # 1. Rejection outcomes
    lines.append("## Signal Rejection Outcomes")
    lines.append(f"- Correctly rejected (price moved against signal >0.5%): {len(rej_analysis['correct_rejections'])}")
    lines.append(f"- **MISSED PROFITS (price moved >1% in signal direction)**: {len(rej_analysis['missed_profits'])}")
    lines.append(f"- Inconclusive (price flat): {len(rej_analysis['inconclusive'])}")
    lines.append("")

    if rej_analysis["missed_profits"]:
        lines.append("### Missed Profitable Trades")
        for mp in rej_analysis["missed_profits"]:
            lines.append(f"- **{mp['symbol']} {mp['side']}**: rejected at ${mp['rej_price']:,.2f} "
                        f"(EV={mp['ev']:.4f}), now ${mp['now_price']:,.2f} "
                        f"({mp['move_pct']:+.2f}% in signal direction, {mp['age_min']:.0f}min ago)")
            lines.append(f"  RSI={mp['rsi_at_rej']}, trend={mp['trend_at_rej']}, win_prob={mp['win_prob']:.2f}")
        lines.append("")

    if rej_analysis["correct_rejections"]:
        lines.append("### Correctly Rejected (saved money)")
        for cr in rej_analysis["correct_rejections"]:
            lines.append(f"- {cr['symbol']} {cr['side']}: rejected at ${cr['rej_price']:,.2f}, "
                        f"now ${cr['now_price']:,.2f} ({cr['move_pct']:+.2f}%)")
        lines.append("")

    # 2. Strategy coverage
    lines.append("## Strategy Coverage Map")
    for sym in sorted(total_scans.keys()):
        total = total_scans[sym]
        lines.append(f"\n### {sym} ({total} scans)")
        for strat, count in sorted(fire_counts[sym].items(), key=lambda x: -x[1]):
            pct = count / total * 100 if total > 0 else 0
            lines.append(f"- {strat}: {count}/{total} ({pct:.0f}%)")
        # List silent strategies
        all_strats = set()
        for s in total_scans:
            all_strats.update(fire_counts[s].keys())
        silent = [s for s in ["regime_trend", "confidence_scorer", "multi_tier_quality",
                              "probability_engine", "bollinger_squeeze", "vmc_cipher",
                              "funding_rate", "oi_delta", "lead_lag", "liquidation_cascade"]
                  if s not in fire_counts[sym]]
        if silent:
            lines.append(f"- NEVER FIRED: {', '.join(silent)}")

    # 3. Regime accuracy
    lines.append(f"\n## Regime Classification Accuracy")
    lines.append(f"- Total observations: {regime_analysis['total']}")
    lines.append(f"- Mismatches: {regime_analysis['mismatches']} ({regime_analysis['mismatch_rate']:.0%})")
    if regime_analysis["details"]:
        for d in regime_analysis["details"][:5]:
            lines.append(f"  - {d['symbol']}: bot={d['bot_regime']} actual={d['actual_trend']} "
                        f"RSI={d.get('rsi')} chg_24h={d.get('chg_24h')}%")

    # 4. Price trend over session
    if len(snapshots) >= 2:
        lines.append(f"\n## Price Movement Over Session")
        first = snapshots[0]["data"]
        last = snapshots[-1]["data"]
        for sym in ["BTC", "SOL", "HYPE"]:
            if sym in first and sym in last:
                p0 = first[sym]["price"]
                p1 = last[sym]["price"]
                chg = (p1 - p0) / p0 * 100
                lines.append(f"- {sym}: ${p0:,.2f} -> ${p1:,.2f} ({chg:+.2f}%)")

    # 5. Edge summary
    lines.append(f"\n## Edge Summary")
    total_rej = len(rej_analysis["correct_rejections"]) + len(rej_analysis["missed_profits"]) + len(rej_analysis["inconclusive"])
    if total_rej > 0:
        correct_rate = len(rej_analysis["correct_rejections"]) / total_rej * 100
        miss_rate = len(rej_analysis["missed_profits"]) / total_rej * 100
        lines.append(f"- Rejection accuracy: {correct_rate:.0f}% correct, {miss_rate:.0f}% missed profits")
    lines.append(f"- Strategy coverage: avg {sum(len(v) for v in fire_counts.values()) / max(len(fire_counts), 1):.1f} strategies fire per symbol")

    report = "\n".join(lines)
    print(report)

    # Save report
    with open(EDGE_REPORT, "w") as f:
        f.write(report)
    print(f"\nReport saved to {EDGE_REPORT}")


if __name__ == "__main__":
    generate_report()
