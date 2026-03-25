"""
Paper Trading Intelligence Collector
Accumulates structured observations over time for post-paper-trading analysis.
Writes to bot/data/paper_trading_intel.jsonl (one JSON object per line).

Categories:
  - regime_observation: what regime was detected vs what the market actually did
  - signal_rejection: signals rejected and why, with price snapshots for later validation
  - near_miss: signals that were close to passing (EV > -0.02)
  - momentum_state: overbought/oversold conditions per symbol
  - strategy_agreement: which strategies agree/disagree and on what
  - price_snapshot: periodic price captures for backtesting rejection accuracy
  - trade_taken: any actual trades executed
  - missed_opportunity: price moved favorably after a rejection
"""
import json
import os
import re
import sys
import time
from datetime import datetime
from collections import defaultdict

LOG_FILE = os.environ.get("WAGMI_LOG", os.path.join(os.environ.get("TEMP", "/tmp"), "wagmi_paper.log"))
INTEL_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "paper_trading_intel.jsonl")
SNAPSHOT_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "price_snapshots.jsonl")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def get_current_prices():
    """Fetch current prices for all tracked symbols."""
    try:
        from data.fetcher import DataFetcher
        f = DataFetcher()
        prices = {}
        coins = {"BTC": "bitcoin", "SOL": "solana", "HYPE": "hyperliquid"}
        for sym, cid in coins.items():
            try:
                df = f.fetch_ohlcv(sym, cid, "1h")
                if df is not None and len(df) > 0:
                    last = df.iloc[-1]
                    prices[sym] = {
                        "price": float(last["close"]),
                        "high_1h": float(last["high"]),
                        "low_1h": float(last["low"]),
                        "volume": float(last["volume"]),
                    }
            except Exception:
                pass
        return prices
    except Exception:
        return {}


def get_technicals():
    """Calculate key technicals for each symbol."""
    try:
        from data.fetcher import DataFetcher
        import pandas as pd
        import numpy as np
        f = DataFetcher()
        technicals = {}
        coins = {"BTC": "bitcoin", "SOL": "solana", "HYPE": "hyperliquid"}
        for sym, cid in coins.items():
            try:
                df = f.fetch_ohlcv(sym, cid, "1h")
                if df is None or len(df) < 50:
                    continue
                df = df.tail(100)
                c = df["close"]

                # RSI
                delta = c.diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss
                rsi = (100 - (100 / (1 + rs))).iloc[-1]

                # EMAs
                ema20 = c.ewm(span=20).mean().iloc[-1]
                ema50 = c.ewm(span=50).mean().iloc[-1]

                # Bollinger
                sma20 = c.rolling(20).mean().iloc[-1]
                std20 = c.rolling(20).std().iloc[-1]
                bb_upper = sma20 + 2 * std20
                bb_lower = sma20 - 2 * std20
                bb_pct = (c.iloc[-1] - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) > 0 else 0.5

                # ATR
                tr = pd.concat([df["high"]-df["low"], (df["high"]-c.shift()).abs(), (df["low"]-c.shift()).abs()], axis=1).max(axis=1)
                atr14 = tr.rolling(14).mean().iloc[-1]

                # 24h change
                if len(df) >= 24:
                    chg_24h = (c.iloc[-1] / c.iloc[-24] - 1) * 100
                else:
                    chg_24h = 0

                technicals[sym] = {
                    "price": float(c.iloc[-1]),
                    "rsi": round(float(rsi), 1),
                    "ema20": round(float(ema20), 2),
                    "ema50": round(float(ema50), 2),
                    "ema_cross": "golden" if ema20 > ema50 else "death",
                    "bb_pct": round(float(bb_pct), 2),
                    "atr14": round(float(atr14), 2),
                    "chg_24h": round(float(chg_24h), 1),
                    "trend": "BULLISH" if ema20 > ema50 and c.iloc[-1] > ema20 else
                             "BEARISH" if ema20 < ema50 and c.iloc[-1] < ema20 else "MIXED",
                }
            except Exception:
                pass
        return technicals
    except Exception:
        return {}


def parse_recent_log(max_lines=300):
    """Parse recent bot log for signals and rejections."""
    if not os.path.exists(LOG_FILE):
        return {}

    with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()[-max_lines:]

    ansi_re = re.compile(r'\x1b\[[0-9;]*m')
    lines = [ansi_re.sub('', l).strip() for l in lines]

    results = {
        "rejections": [],
        "solo_signals": [],
        "vote_failures": [],
        "momentum_exhaustion": [],
        "strategy_maps": [],
        "squeeze_signals": [],
        "heartbeat": None,
    }

    for line in lines:
        # Heartbeat (take latest)
        if "[HEARTBEAT]" in line:
            results["heartbeat"] = line

        # Rejections
        m = re.search(r'\[ENSEMBLE\] (\w+) (\w+) rejected: negative EV \(([-\d.]+)\) R:R=([\d.]+) fee_drag=([\d.]+) win_prob=([\d.]+)', line)
        if m:
            results["rejections"].append({
                "symbol": m.group(1), "side": m.group(2),
                "ev": float(m.group(3)), "rr": float(m.group(4)),
                "fee_drag": float(m.group(5)), "win_prob": float(m.group(6)),
            })

        # Solo
        m = re.search(r'Symbol\+regime solo: (\w+)/(\w+) conf=(\d+)%', line)
        if m:
            results["solo_signals"].append({
                "symbol": m.group(1), "regime": m.group(2), "conf": int(m.group(3)),
            })

        # Vote failures
        m = re.search(r'\[(\w+)\] Only (\d+) (\w+) signal\(s\), need (\d+)\+', line)
        if m:
            results["vote_failures"].append({
                "symbol": m.group(1), "count": int(m.group(2)), "side": m.group(3),
            })

        # Strategy maps (which strategies fired vs silent)
        m = re.search(r'\[(\w+)\] Strategy map: fired=\[([^\]]*)\] silent=\[([^\]]*)\] \((\d+)/(\d+)\)', line)
        if m:
            results["strategy_maps"].append({
                "symbol": m.group(1),
                "fired": [s.strip().strip("'") for s in m.group(2).split(",") if s.strip()],
                "silent": [s.strip().strip("'") for s in m.group(3).split(",") if s.strip()],
                "count": int(m.group(4)), "total": int(m.group(5)),
            })

        # Squeeze breakout signals
        m = re.search(r'\[(\w+)\] BB Squeeze signal: (\w+) conf=(\d+)% type=(\w+)', line)
        if m:
            results["squeeze_signals"].append({
                "symbol": m.group(1), "side": m.group(2),
                "conf": int(m.group(3)), "type": m.group(4),
            })

        # Momentum
        m = re.search(r'\[(\w+)\] Momentum exhaustion: ADX=(\d+) RSI=(\d+)', line)
        if m:
            results["momentum_exhaustion"].append({
                "symbol": m.group(1), "adx": int(m.group(2)), "rsi": int(m.group(3)),
            })

    return results


def dedupe(items, key_fn):
    """Deduplicate keeping last occurrence."""
    seen = {}
    for item in items:
        seen[key_fn(item)] = item
    return list(seen.values())


def write_intel(entry):
    """Append an intel entry to the JSONL file."""
    entry["timestamp"] = datetime.now().isoformat()
    entry["epoch"] = time.time()
    with open(INTEL_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def collect():
    """Main collection cycle."""
    now = datetime.now().isoformat()
    print(f"[INTEL] Collecting at {now}")

    # 1. Get current market state
    technicals = get_technicals()
    if technicals:
        write_intel({
            "category": "price_snapshot",
            "data": technicals,
        })
        parts = [f"{s}=${d['price']:,.2f}" for s, d in technicals.items()]
        print(f"  Prices: {', '.join(parts)}")

    # 2. Parse bot logs
    log_data = parse_recent_log()

    # 3. Record unique rejections with market context
    rejections = dedupe(log_data["rejections"], lambda r: (r["symbol"], r["side"]))
    for rej in rejections:
        sym = rej["symbol"]
        tech = technicals.get(sym, {})
        write_intel({
            "category": "signal_rejection",
            "data": {**rej, "technicals": tech},
        })

        # Flag near-misses
        if rej["ev"] > -0.02:
            write_intel({
                "category": "near_miss",
                "data": {
                    "symbol": sym, "side": rej["side"],
                    "ev": rej["ev"], "win_prob": rej["win_prob"],
                    "price_at_rejection": tech.get("price"),
                    "rsi_at_rejection": tech.get("rsi"),
                    "note": "Track price movement to see if this would have been profitable",
                },
            })
            print(f"  NEAR MISS: {sym} {rej['side']} EV={rej['ev']:.4f}")

    # 4. Record regime observations (what bot says vs technicals)
    solos = dedupe(log_data["solo_signals"], lambda s: s["symbol"])
    for solo in solos:
        sym = solo["symbol"]
        tech = technicals.get(sym, {})
        bot_regime = solo["regime"]
        actual_trend = tech.get("trend", "unknown")

        # Flag regime mismatch
        mismatch = False
        if bot_regime == "consolidation" and actual_trend == "BULLISH" and tech.get("chg_24h", 0) > 3:
            mismatch = True
        if bot_regime == "consolidation" and actual_trend == "BEARISH" and tech.get("chg_24h", 0) < -3:
            mismatch = True

        write_intel({
            "category": "regime_observation",
            "data": {
                "symbol": sym,
                "bot_regime": bot_regime,
                "actual_trend": actual_trend,
                "rsi": tech.get("rsi"),
                "ema_cross": tech.get("ema_cross"),
                "chg_24h": tech.get("chg_24h"),
                "mismatch": mismatch,
            },
        })
        if mismatch:
            print(f"  REGIME MISMATCH: {sym} bot={bot_regime} but trend={actual_trend} chg={tech.get('chg_24h', 0):+.1f}%")

    # 5. Record momentum state
    mom = dedupe(log_data["momentum_exhaustion"], lambda m: m["symbol"])
    for m in mom:
        tech = technicals.get(m["symbol"], {})
        write_intel({
            "category": "momentum_state",
            "data": {
                "symbol": m["symbol"],
                "adx": m["adx"], "rsi": m["rsi"],
                "price": tech.get("price"),
                "trend": tech.get("trend"),
            },
        })

    # 6. Record vote failures
    votes = dedupe(log_data["vote_failures"], lambda v: (v["symbol"], v["side"]))
    for v in votes:
        write_intel({
            "category": "strategy_agreement",
            "data": {
                "symbol": v["symbol"], "side": v["side"],
                "agreeing": v["count"], "needed": 2,
                "note": "Only 1 strategy agrees, need 2+ for ensemble",
            },
        })

    # 6b. Record strategy maps (which strategies fire where)
    strat_maps = dedupe(log_data.get("strategy_maps", []), lambda s: s["symbol"])
    for sm in strat_maps:
        write_intel({
            "category": "strategy_map",
            "data": sm,
        })
        if sm["count"] >= 2:
            print(f"  MULTI-SIGNAL: {sm['symbol']} {sm['count']}/{sm['total']} strategies fired: {sm['fired']}")

    # 6c. Record squeeze breakouts (high-value signals)
    squeezes = dedupe(log_data.get("squeeze_signals", []), lambda s: s["symbol"])
    for sq in squeezes:
        write_intel({
            "category": "squeeze_breakout",
            "data": sq,
        })
        print(f"  SQUEEZE: {sq['symbol']} {sq['side']} conf={sq['conf']}% type={sq['type']}")

    # 7. Summary
    intel_size = os.path.getsize(INTEL_FILE) if os.path.exists(INTEL_FILE) else 0
    line_count = 0
    if os.path.exists(INTEL_FILE):
        with open(INTEL_FILE) as f:
            line_count = sum(1 for _ in f)

    print(f"  Intel file: {line_count} entries, {intel_size/1024:.1f}KB")
    print(f"  Rejections: {len(rejections)}, Near-misses: {sum(1 for r in rejections if r['ev'] > -0.02)}")
    print(f"  Regime mismatches: {sum(1 for s in solos if technicals.get(s['symbol'], {}).get('trend') == 'BULLISH' and s['regime'] == 'consolidation')}")


if __name__ == "__main__":
    collect()
