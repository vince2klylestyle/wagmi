"""
Claude Code Overwatch Analyzer
Parses bot logs and data to produce actionable intelligence.
Run: cd bot && python tools/overwatch_analyzer.py
"""
import re
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta

LOG_FILE = os.environ.get("WAGMI_LOG", os.path.join(os.environ.get("TEMP", "/tmp"), "wagmi_paper.log"))
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def parse_log_lines(max_lines=500):
    """Parse the last N lines of the bot log."""
    if not os.path.exists(LOG_FILE):
        print("ERROR: No log file found at", LOG_FILE)
        return {}

    with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()[-max_lines:]

    # Strip ANSI codes
    ansi_re = re.compile(r'\x1b\[[0-9;]*m')
    lines = [ansi_re.sub('', l).strip() for l in lines]

    results = {
        "heartbeats": [],
        "rejections": [],
        "signals": [],
        "errors": [],
        "solo_signals": [],
        "momentum_exhaustion": [],
        "regime_info": {},
        "weight_demotions": defaultdict(int),
    }

    for line in lines:
        # Heartbeat
        if "[HEARTBEAT]" in line:
            results["heartbeats"].append(line)

        # Ensemble rejections
        m = re.search(r'\[ENSEMBLE\] (\w+) (\w+) rejected: negative EV \(([-\d.]+)\) R:R=([\d.]+) fee_drag=([\d.]+) win_prob=([\d.]+)', line)
        if m:
            results["rejections"].append({
                "symbol": m.group(1), "side": m.group(2),
                "ev": float(m.group(3)), "rr": float(m.group(4)),
                "fee_drag": float(m.group(5)), "win_prob": float(m.group(6)),
            })

        # Solo signals
        m = re.search(r'\[(\w+)\] Symbol\+regime solo: (\w+)/(\w+) conf=(\d+)%', line)
        if m:
            results["solo_signals"].append({
                "symbol": m.group(1) or m.group(2),
                "regime": m.group(3), "conf": int(m.group(4)),
            })

        # Insufficient votes
        m = re.search(r'\[(\w+)\] Only (\d+) (\w+) signal\(s\), need (\d+)\+', line)
        if m:
            results["signals"].append({
                "symbol": m.group(1), "count": int(m.group(2)),
                "side": m.group(3), "needed": int(m.group(4)),
            })

        # Momentum exhaustion
        m = re.search(r'\[(\w+)\] Momentum exhaustion: ADX=(\d+) RSI=(\d+)', line)
        if m:
            results["momentum_exhaustion"].append({
                "symbol": m.group(1), "adx": int(m.group(2)), "rsi": int(m.group(3)),
            })

        # Errors
        if "[E]" in line or "Error" in line:
            results["errors"].append(line)

        # Weight demotions
        m = re.search(r'\[WEIGHTS\] (\w+) DEMOTED: recent_WR=([\d.]+)%', line)
        if m:
            results["weight_demotions"][m.group(1)] += 1

    return results


def analyze_rejections(rejections):
    """Deep analysis of why signals are being rejected."""
    if not rejections:
        print("  No rejections in recent logs")
        return

    # Deduplicate (same signal repeats in logs)
    seen = set()
    unique = []
    for r in rejections:
        key = (r["symbol"], r["side"])
        if key not in seen:
            seen.add(key)
            unique.append(r)

    for r in unique:
        sym, side = r["symbol"], r["side"]
        ev, rr, wp = r["ev"], r["rr"], r["win_prob"]
        fee = r["fee_drag"]

        # What win_prob would make EV = 0?
        # wp * (rr - fee) = (1-wp) * (1+fee)
        # wp * (rr-fee) + wp * (1+fee) = 1+fee
        # wp * (rr-fee+1+fee) = 1+fee
        # wp = (1+fee) / (rr+1)
        breakeven_wp = (1 + fee) / (rr + 1)

        # What confidence would be needed (assuming solo deflation 0.50)?
        needed_conf_solo = breakeven_wp / 0.50 * 100
        # With 2-strat agreement in consolidation (deflation 0.70)?
        needed_conf_2agree = breakeven_wp / 0.70 * 100

        print(f"  {sym} {side}: EV={ev:+.4f}  win_prob={wp:.2f}  R:R={rr:.1f}")
        print(f"    Breakeven win_prob needed: {breakeven_wp:.2f}")
        print(f"    Solo signal: would need {needed_conf_solo:.0f}% confidence (currently too low)")
        print(f"    With 2 strategies agreeing: would need {needed_conf_2agree:.0f}% confidence")

        gap = breakeven_wp - wp
        if gap < 0.05:
            print(f"    ** NEAR MISS: only {gap:.1%} away from positive EV **")
        elif gap < 0.10:
            print(f"    * Close: {gap:.1%} from positive EV")
        else:
            print(f"    Far from positive EV ({gap:.1%} gap)")


def check_missed_trades():
    """Check if missed trade tracker has anything."""
    mt_path = os.path.join(DATA_DIR, "missed_trades.json")
    if os.path.exists(mt_path):
        try:
            with open(mt_path) as f:
                data = json.load(f)
            if data:
                print(f"  Found {len(data)} missed trade records")
                for mt in data[-5:]:  # Last 5
                    print(f"    {mt.get('symbol', '?')} {mt.get('side', '?')} "
                          f"conf={mt.get('confidence', '?')} reason={mt.get('reason', '?')}")
        except Exception:
            pass
    else:
        print("  No missed trade data yet")


def check_trades():
    """Check trade history."""
    csv_path = os.path.join(DATA_DIR, "trades.csv")
    if os.path.exists(csv_path):
        with open(csv_path) as f:
            lines = f.readlines()
        if len(lines) > 1:
            print(f"  {len(lines)-1} trades recorded")
            for line in lines[-5:]:
                print(f"    {line.strip()}")
        else:
            print("  No trades yet (header only)")
    else:
        print("  No trades.csv found — fresh start")


def main():
    print("=" * 70)
    print("  CLAUDE CODE OVERWATCH — Paper Trading Intelligence")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    data = parse_log_lines(500)

    # 1. Latest heartbeat
    print("\n[HEARTBEAT]")
    if data["heartbeats"]:
        hb = data["heartbeats"][-1]
        print(f"  {hb[:200]}")
    else:
        print("  No heartbeat found")

    # 2. Signal rejections
    print("\n[SIGNAL REJECTIONS]")
    analyze_rejections(data["rejections"])

    # 3. Solo signals (only 1 strategy agrees)
    print("\n[SOLO SIGNALS — Need More Agreement]")
    seen_solo = set()
    for s in data["solo_signals"]:
        key = (s["symbol"], s["regime"])
        if key not in seen_solo:
            seen_solo.add(key)
            print(f"  {s['symbol']}: regime={s['regime']} conf={s['conf']}%")

    # 4. Insufficient votes
    print("\n[VOTE FAILURES]")
    seen_votes = set()
    for s in data["signals"]:
        key = (s["symbol"], s["side"])
        if key not in seen_votes:
            seen_votes.add(key)
            print(f"  {s['symbol']}: {s['count']} {s['side']} signal(s), need {s['needed']}+")

    # 5. Momentum exhaustion
    print("\n[MOMENTUM EXHAUSTION]")
    seen_mom = set()
    for m in data["momentum_exhaustion"]:
        if m["symbol"] not in seen_mom:
            seen_mom.add(m["symbol"])
            status = "OVERBOUGHT" if m["rsi"] > 70 else "OVERSOLD" if m["rsi"] < 30 else "normal"
            print(f"  {m['symbol']}: ADX={m['adx']} RSI={m['rsi']} ({status})")

    # 6. Strategy weights
    print("\n[STRATEGY HEALTH]")
    for strat, count in sorted(data["weight_demotions"].items()):
        print(f"  {strat}: demoted {count}x in recent logs")

    # 7. Trade history
    print("\n[TRADE HISTORY]")
    check_trades()

    # 8. Missed trades
    print("\n[MISSED TRADES]")
    check_missed_trades()

    # 9. Errors
    print("\n[ERRORS]")
    unique_errors = set()
    for e in data["errors"]:
        short = e[:120]
        if short not in unique_errors:
            unique_errors.add(short)
            print(f"  {short}")
    if not unique_errors:
        print("  No errors")

    # 10. Recommendations
    print("\n" + "=" * 70)
    print("[RECOMMENDATIONS]")

    if data["rejections"]:
        # Check if HYPE is close to passing
        hype_rej = [r for r in data["rejections"] if r["symbol"] == "HYPE"]
        if hype_rej:
            latest = hype_rej[-1]
            if latest["ev"] > -0.02:
                print("  * HYPE SELL signal is VERY close to positive EV")
                print("    The bot is correctly rejecting but this may flip with a small price move")

        # Check solo signal problem
        solo_count = len(set((s["symbol"],) for s in data["solo_signals"]))
        if solo_count > 0:
            print("  * Multiple symbols generating SOLO signals (1 strategy)")
            print("    The main barrier to trades is lack of multi-strategy agreement")
            print("    This is CORRECT behavior in consolidation — wait for stronger setups")

    seen_mom_rec = set()
    if data["momentum_exhaustion"]:
        for m in data["momentum_exhaustion"]:
            if m["rsi"] > 75 and m["symbol"] not in seen_mom_rec:
                seen_mom_rec.add(m["symbol"])
                print(f"  * {m['symbol']} RSI={m['rsi']} — overbought, short-term pullback likely")
                print(f"    DO NOT chase longs here. Wait for RSI cooldown below 65")

    if not data["rejections"] and not data["solo_signals"]:
        print("  * No signals at all — market may be too quiet or data stale")

    print("=" * 70)


if __name__ == "__main__":
    main()
