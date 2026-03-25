"""
Unified Overwatch Cycle — Single script that runs the full monitoring pipeline.
Combines intel_collector + overwatch_analyzer + edge_tracker into one efficient pass.
Outputs a concise summary only when something CHANGES. Suppresses repetitive output.

Usage: cd bot && python tools/overwatch_cycle.py
"""
import json
import os
import re
import sys
import time
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

LOG_FILE = os.environ.get("WAGMI_LOG", os.path.join(os.environ.get("TEMP", "/tmp"), "wagmi_paper.log"))
INTEL_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "paper_trading_intel.jsonl")
STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "overwatch_state.json")
CYCLE_LOG = os.path.join(os.path.dirname(__file__), "..", "data", "overwatch_cycles.jsonl")


def load_last_state():
    """Load previous cycle state for change detection."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_state(state):
    """Save current cycle state."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def get_prices():
    """Fetch current prices."""
    try:
        from data.fetcher import DataFetcher
        f = DataFetcher()
        prices = {}
        coins = {"BTC": "bitcoin", "SOL": "solana", "HYPE": "hyperliquid"}
        for sym, cid in coins.items():
            try:
                df = f.fetch_ohlcv(sym, cid, "1h")
                if df is not None and len(df) > 0:
                    prices[sym] = round(float(df.iloc[-1]["close"]), 2)
            except Exception:
                pass
        return prices
    except Exception:
        return {}


def get_technicals(prices_dict):
    """Quick technicals from cached data."""
    try:
        from data.fetcher import DataFetcher
        import pandas as pd
        f = DataFetcher()
        techs = {}
        coins = {"BTC": "bitcoin", "SOL": "solana", "HYPE": "hyperliquid"}
        for sym, cid in coins.items():
            try:
                df = f.fetch_ohlcv(sym, cid, "1h")
                if df is None or len(df) < 20:
                    continue
                c = df["close"].tail(50)
                delta = c.diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rsi = float((100 - 100 / (1 + gain / loss)).iloc[-1])
                techs[sym] = {"rsi": round(rsi, 1), "price": prices_dict.get(sym, 0)}
            except Exception:
                pass
        return techs
    except Exception:
        return {}


def parse_log(max_lines=200):
    """Parse recent bot log for key events."""
    if not os.path.exists(LOG_FILE):
        return {}

    with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()[-max_lines:]

    ansi = re.compile(r'\x1b\[[0-9;]*m')
    lines = [ansi.sub('', l).strip() for l in lines]

    data = {
        "rejections": {},       # {(sym,side): {ev, wp, rr}}
        "strategy_maps": {},    # {sym: {fired, silent, count, total}}
        "signals_taken": [],    # Any actual trades
        "errors": [],
        "heartbeat": None,
    }

    for line in lines:
        if "[HEARTBEAT]" in line:
            data["heartbeat"] = line

        m = re.search(r'\[ENSEMBLE\] (\w+) (\w+) rejected: negative EV \(([-\d.]+)\) R:R=([\d.]+) fee_drag=([\d.]+) win_prob=([\d.]+)', line)
        if m:
            data["rejections"][(m.group(1), m.group(2))] = {
                "ev": float(m.group(3)), "rr": float(m.group(4)),
                "fee_drag": float(m.group(5)), "win_prob": float(m.group(6)),
            }

        m = re.search(r'\[(\w+)\] Strategy map: fired=\[([^\]]*)\] silent=\[([^\]]*)\] \((\d+)/(\d+)\)', line)
        if m:
            data["strategy_maps"][m.group(1)] = {
                "fired": [s.strip().strip("'") for s in m.group(2).split(",") if s.strip()],
                "silent": [s.strip().strip("'") for s in m.group(3).split(",") if s.strip()],
                "count": int(m.group(4)), "total": int(m.group(5)),
            }

        if "PAPER FILL" in line or "ORDER EXECUTED" in line or "Position opened" in line:
            data["signals_taken"].append(line)

        if "[E]" in line and "bot_perception" not in line:
            data["errors"].append(line[:120])

    return data


def check_near_misses(prices):
    """Check all near-misses against current prices."""
    if not os.path.exists(INTEL_FILE):
        return {"total": 0, "missed": 0, "worst_miss": None}

    missed = 0
    total = 0
    worst = None
    worst_mv = 0

    with open(INTEL_FILE) as f:
        for line in f:
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("category") != "near_miss":
                continue
            d = e["data"]
            sym = d["symbol"]
            side = d["side"]
            rp = d.get("price_at_rejection")
            np = prices.get(sym)
            if not rp or not np:
                continue

            mv = ((rp - np) / rp * 100) if side == "SELL" else ((np - rp) / rp * 100)
            total += 1
            if mv > 1.0:
                missed += 1
            if mv > worst_mv:
                worst_mv = mv
                worst = {"sym": sym, "side": side, "rej": rp, "now": np, "mv": mv,
                         "ts": e.get("timestamp", "?")[:16]}

    return {"total": total, "missed": missed, "worst_miss": worst}


def log_intel(prices, techs, log_data):
    """Append structured intel entry."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "epoch": time.time(),
        "category": "price_snapshot",
        "data": {},
    }
    for sym in prices:
        entry["data"][sym] = {
            "price": prices[sym],
            "rsi": techs.get(sym, {}).get("rsi"),
        }

    with open(INTEL_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

    # Log rejections as near-misses if marginal
    for (sym, side), rej in log_data.get("rejections", {}).items():
        if rej["ev"] >= -0.02:  # Near-miss threshold
            nm_entry = {
                "timestamp": datetime.now().isoformat(),
                "epoch": time.time(),
                "category": "near_miss",
                "data": {
                    "symbol": sym, "side": side,
                    "ev": rej["ev"], "win_prob": rej["win_prob"],
                    "price_at_rejection": prices.get(sym),
                    "rsi_at_rejection": techs.get(sym, {}).get("rsi"),
                },
            }
            with open(INTEL_FILE, "a") as f:
                f.write(json.dumps(nm_entry) + "\n")

    # Log strategy maps
    for sym, smap in log_data.get("strategy_maps", {}).items():
        sm_entry = {
            "timestamp": datetime.now().isoformat(),
            "epoch": time.time(),
            "category": "strategy_map",
            "data": smap | {"symbol": sym},
        }
        with open(INTEL_FILE, "a") as f:
            f.write(json.dumps(sm_entry) + "\n")


def run_cycle():
    """Run one complete overwatch cycle. Only print when something changes."""
    last_state = load_last_state()
    prices = get_prices()
    if not prices:
        print("[OVERWATCH] Failed to fetch prices")
        return

    techs = get_technicals(prices)
    log_data = parse_log()
    near_misses = check_near_misses(prices)

    # Log intel
    log_intel(prices, techs, log_data)

    # Build current state
    current = {
        "prices": prices,
        "missed_count": near_misses["missed"],
        "missed_total": near_misses["total"],
        "rejections": {f"{k[0]}_{k[1]}": v["ev"] for k, v in log_data.get("rejections", {}).items()},
        "strategy_counts": {s: m["count"] for s, m in log_data.get("strategy_maps", {}).items()},
        "trades_taken": len(log_data.get("signals_taken", [])),
        "error_count": len(log_data.get("errors", [])),
    }

    # Detect changes
    changes = []

    # New trade taken
    if current["trades_taken"] > last_state.get("trades_taken", 0):
        changes.append("** NEW TRADE TAKEN **")
        for sig in log_data["signals_taken"]:
            changes.append(f"  {sig}")

    # Missed count changed
    if current["missed_count"] != last_state.get("missed_count", 0):
        changes.append(f"Missed profits: {last_state.get('missed_count', 0)} -> {current['missed_count']}/{current['missed_total']}")

    # New rejection appeared or disappeared
    old_rej = set(last_state.get("rejections", {}).keys())
    new_rej = set(current["rejections"].keys())
    if new_rej - old_rej:
        for r in new_rej - old_rej:
            changes.append(f"New rejection: {r} EV={current['rejections'][r]:.4f}")
    if old_rej - new_rej:
        for r in old_rej - new_rej:
            changes.append(f"Rejection cleared: {r}")

    # Strategy count changed for any symbol
    for sym in current["strategy_counts"]:
        old_ct = last_state.get("strategy_counts", {}).get(sym, 0)
        new_ct = current["strategy_counts"][sym]
        if new_ct != old_ct:
            smap = log_data["strategy_maps"].get(sym, {})
            changes.append(f"{sym} strategies: {old_ct} -> {new_ct} (fired: {smap.get('fired', [])})")

    # Price moved >0.5% since last cycle
    for sym in prices:
        old_p = last_state.get("prices", {}).get(sym, prices[sym])
        pct = abs(prices[sym] - old_p) / old_p * 100 if old_p else 0
        if pct > 0.5:
            changes.append(f"{sym} moved {(prices[sym]-old_p)/old_p*100:+.2f}% (${old_p:,.2f} -> ${prices[sym]:,.2f})")

    # New errors
    if current["error_count"] > last_state.get("error_count", 0):
        changes.append(f"New errors detected: {current['error_count'] - last_state.get('error_count', 0)}")

    # Output
    now = datetime.now().strftime("%H:%M:%S")
    if changes:
        print(f"[{now}] CHANGES DETECTED:")
        for c in changes:
            print(f"  {c}")
        # Always show current state after changes
        print(f"  Prices: BTC=${prices.get('BTC',0):,.0f} SOL=${prices.get('SOL',0):.2f} HYPE=${prices.get('HYPE',0):.2f}")
        print(f"  Misses: {current['missed_count']}/{current['missed_total']} | Trades: {current['trades_taken']}")
        if near_misses["worst_miss"]:
            w = near_misses["worst_miss"]
            print(f"  Worst miss: {w['sym']} {w['side']} +{w['mv']:.2f}% ({w['ts']})")
    else:
        # Quiet cycle — minimal output
        print(f"[{now}] No changes. BTC=${prices.get('BTC',0):,.0f} HYPE=${prices.get('HYPE',0):.2f} Misses={current['missed_count']}/{current['missed_total']}")

    # Log cycle
    cycle_entry = {
        "timestamp": datetime.now().isoformat(),
        "prices": prices,
        "missed": current["missed_count"],
        "total_near_misses": current["missed_total"],
        "changes": len(changes),
        "trades": current["trades_taken"],
    }
    with open(CYCLE_LOG, "a") as f:
        f.write(json.dumps(cycle_entry) + "\n")

    # Save state
    save_state(current)


if __name__ == "__main__":
    run_cycle()
