"""Stop-Hunting Detection for WAGMI SL-hit trades.

For each SL-hit trade:
  - Reconstruct SL price as exit price (since sl_hit=True means exit == SL fill).
  - Pull 5m bars from 10m before exit through 60m after.
  - Classify as stop-hunt if price reverses back through ENTRY within N minutes
    (5/15/30/60) after the SL fill bar.
  - Simulate a 1.5x wider stop: would it still have fired?

Output: JSON with aggregate + per-symbol + per-time-of-day breakdowns.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

try:
    import ccxt  # type: ignore
except ImportError:
    ccxt = None  # type: ignore

# ---- Paths ----
ROOT = Path(__file__).resolve().parents[1]
TRADES_CSV = ROOT / "data" / "trades.csv"
CACHE_DIR = ROOT / "data" / "cache"
OUT_JSON = ROOT / "data" / "sessions" / "stop_hunting_analysis.json"

SYMBOLS = ["BTC", "ETH", "SOL", "HYPE"]

# Try several cache horizons so we cover the whole trades range
CACHE_CANDIDATES = ["120d", "90d", "60d", "45d", "30d", "15d", "10d", "7d", "0d"]

# Hyperliquid symbol map
HL_SYMBOL = {"BTC": "BTC/USDC:USDC", "ETH": "ETH/USDC:USDC", "SOL": "SOL/USDC:USDC", "HYPE": "HYPE/USDC:USDC"}


def _fetch_live_bars(sym: str, since_ms: int, until_ms: int) -> Optional[pd.DataFrame]:
    """Fetch 5m OHLCV from Hyperliquid via CCXT, paginated."""
    if ccxt is None:
        return None
    import time as _time
    try:
        ex = ccxt.hyperliquid({"enableRateLimit": True, "timeout": 30000})
        market = HL_SYMBOL.get(sym)
        if not market:
            return None
        all_rows: list[list] = []
        cursor = since_ms
        retries = 0
        while cursor < until_ms:
            try:
                ohlcv = ex.fetch_ohlcv(market, timeframe="5m", since=cursor, limit=1000)
            except Exception as e:
                msg = str(e)
                if "429" in msg or "Too Many" in msg:
                    retries += 1
                    if retries > 5:
                        print(f"  rate-limit giveup {sym}")
                        break
                    wait = 5 * retries
                    print(f"  429 on {sym} — sleeping {wait}s")
                    _time.sleep(wait)
                    continue
                print(f"  fetch error {sym} @ {cursor}: {e}")
                break
            retries = 0
            if not ohlcv:
                # no more data; try skipping ahead
                cursor += 1000 * 5 * 60 * 1000
                continue
            all_rows.extend(ohlcv)
            last_ts = ohlcv[-1][0]
            if last_ts <= cursor:
                cursor = last_ts + 5 * 60 * 1000
                continue
            cursor = last_ts + 5 * 60 * 1000
            _time.sleep(0.3)  # be nice
        if not all_rows:
            return None
        df = pd.DataFrame(all_rows, columns=["ts_ms", "open", "high", "low", "close", "volume"])
        df["time"] = pd.to_datetime(df["ts_ms"], unit="ms", utc=True)
        return df[["open", "high", "low", "close", "volume", "time"]]
    except Exception as e:
        print(f"  ccxt init error: {e}")
        return None


def load_bars_5m(need_until: Optional[pd.Timestamp] = None) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for sym in SYMBOLS:
        frames = []
        for h in CACHE_CANDIDATES:
            f = CACHE_DIR / f"{sym}_5m_{h}.csv"
            if not f.exists():
                continue
            df = pd.read_csv(f)
            df["time"] = pd.to_datetime(df["time"], utc=True)
            frames.append(df)
        if frames:
            all_df = (
                pd.concat(frames, ignore_index=True)
                .drop_duplicates(subset=["time"])
                .sort_values("time")
                .reset_index(drop=True)
            )
        else:
            all_df = pd.DataFrame(columns=["open", "high", "low", "close", "volume", "time"])

        # Gap-fill from CCXT if needed
        if need_until is not None:
            cache_end = all_df["time"].max() if not all_df.empty else pd.Timestamp("2026-03-07", tz="UTC")
            gap_hours = (need_until - cache_end).total_seconds() / 3600 if pd.notna(cache_end) else 1e9
            if gap_hours > 1:
                since_ms = int(cache_end.timestamp() * 1000) if pd.notna(cache_end) else int(pd.Timestamp("2026-03-07", tz="UTC").timestamp() * 1000)
                until_ms = int(need_until.timestamp() * 1000) + 3600 * 1000
                print(f"  Fetching live {sym} from {pd.Timestamp(since_ms, unit='ms', tz='UTC')} to {pd.Timestamp(until_ms, unit='ms', tz='UTC')}...")
                fresh = _fetch_live_bars(sym, since_ms, until_ms)
                if fresh is not None and not fresh.empty:
                    all_df = (
                        pd.concat([all_df, fresh], ignore_index=True)
                        .drop_duplicates(subset=["time"])
                        .sort_values("time")
                        .reset_index(drop=True)
                    )
        out[sym] = all_df
    return out


def classify_trade(
    row: pd.Series,
    bars: pd.DataFrame,
    horizons_min: list[int],
) -> dict:
    """Return dict with per-horizon reversal flags + wider-stop sim."""
    ts = pd.to_datetime(row["timestamp"], utc=True)
    symbol = row["symbol"]
    side = str(row["side"]).upper()
    entry = float(row["entry"])
    sl_price = float(row["exit"])  # reconstructed: SL fill == exit when sl_hit=True

    # SL distance (in price)
    if side == "LONG":
        sl_dist = entry - sl_price
    else:
        sl_dist = sl_price - entry
    sl_dist = abs(sl_dist)

    # Window: 10m before exit through 60m after
    # Trade timestamp is ENTRY; we don't have exit timestamp in CSV.
    # Approximation: use the first bar AFTER entry where wick hits SL as "SL bar",
    # then measure reversals from THAT bar.
    start = ts - timedelta(minutes=10)
    end = ts + timedelta(hours=12)  # generous — SL can fire hours later
    window = bars[(bars["time"] >= start) & (bars["time"] <= end)].reset_index(drop=True)
    if window.empty:
        return {"error": "no_bars", "symbol": symbol}

    # Find the bar where SL fires
    sl_bar_idx: Optional[int] = None
    for i, b in window.iterrows():
        if side == "LONG" and b["low"] <= sl_price:
            sl_bar_idx = i
            break
        if side == "SHORT" and b["high"] >= sl_price:
            sl_bar_idx = i
            break
    if sl_bar_idx is None:
        return {"error": "sl_bar_not_found", "symbol": symbol}

    sl_bar_time = window.loc[sl_bar_idx, "time"]

    # Post-hunt analysis: does price return to ENTRY within N minutes?
    out_flags: dict[str, bool] = {}
    max_reversal_price = None
    for n in horizons_min:
        n_end = sl_bar_time + timedelta(minutes=n)
        post = window[(window["time"] > sl_bar_time) & (window["time"] <= n_end)]
        reverted = False
        if not post.empty:
            if side == "LONG":
                max_reversal_price = float(post["high"].max())
                reverted = max_reversal_price >= entry
            else:
                max_reversal_price = float(post["low"].min())
                reverted = max_reversal_price <= entry
        out_flags[f"hunt_{n}m"] = reverted

    # Wider-stop simulation: SL at 1.5x distance from entry
    if side == "LONG":
        wider_sl = entry - 1.5 * sl_dist
    else:
        wider_sl = entry + 1.5 * sl_dist
    post60 = window[
        (window["time"] > sl_bar_time)
        & (window["time"] <= sl_bar_time + timedelta(hours=4))
    ]
    # Would wider stop STILL have fired (either in the original SL bar or within 4h)?
    wider_fired_in_sl_bar = False
    sl_bar_row = window.loc[sl_bar_idx]
    if side == "LONG":
        wider_fired_in_sl_bar = sl_bar_row["low"] <= wider_sl
    else:
        wider_fired_in_sl_bar = sl_bar_row["high"] >= wider_sl

    wider_fired_post = False
    if not post60.empty:
        if side == "LONG":
            wider_fired_post = (post60["low"] <= wider_sl).any()
        else:
            wider_fired_post = (post60["high"] >= wider_sl).any()
    wider_fired = bool(wider_fired_in_sl_bar or wider_fired_post)

    # Legitimate-loss check: did price keep going against us 60m after SL?
    # LONG legit loss = price stays <= sl_price AND doesn't recover to entry
    legit_loss = not out_flags.get("hunt_60m", False)

    hour_utc = int(sl_bar_time.hour)
    asia_deadzone = 0 <= hour_utc <= 8

    return {
        "symbol": symbol,
        "side": side,
        "entry_ts": ts.isoformat(),
        "sl_bar_time": sl_bar_time.isoformat(),
        "hour_utc": hour_utc,
        "asia_deadzone": asia_deadzone,
        "entry": entry,
        "sl_price": sl_price,
        "sl_dist_pct": sl_dist / entry * 100 if entry else 0,
        "max_reversal_price": max_reversal_price,
        **out_flags,
        "wider_stop_would_fire": wider_fired,
        "legit_loss_60m": legit_loss,
        "pnl": float(row["pnl"]),
    }


def aggregate(results: list[dict], horizons: list[int]) -> dict:
    ok = [r for r in results if "error" not in r]
    total = len(ok)
    out: dict = {"n_sl_hits_analyzed": total, "n_errors": len(results) - total}
    if total == 0:
        return out

    for n in horizons:
        key = f"hunt_{n}m"
        hits = sum(1 for r in ok if r.get(key))
        out[f"pct_hunt_{n}m"] = round(hits / total * 100, 1)
        out[f"count_hunt_{n}m"] = hits

    # Per-symbol breakdown
    by_sym: dict[str, dict] = {}
    for sym in SYMBOLS:
        rows = [r for r in ok if r["symbol"] == sym]
        if not rows:
            continue
        n = len(rows)
        by_sym[sym] = {
            "n": n,
            "pct_hunt_30m": round(sum(1 for r in rows if r.get("hunt_30m")) / n * 100, 1),
            "pct_hunt_60m": round(sum(1 for r in rows if r.get("hunt_60m")) / n * 100, 1),
            "pct_asia": round(sum(1 for r in rows if r.get("asia_deadzone")) / n * 100, 1),
            "small_n": n < 10,
        }
    out["by_symbol"] = by_sym

    # Per time-of-day (8h buckets: asia 0-8, london 8-16, ny 16-24)
    by_tod: dict[str, dict] = {}
    buckets = {"asia_0_8": (0, 8), "london_8_16": (8, 16), "ny_16_24": (16, 24)}
    for name, (lo, hi) in buckets.items():
        rows = [r for r in ok if lo <= r["hour_utc"] < hi]
        if not rows:
            by_tod[name] = {"n": 0}
            continue
        n = len(rows)
        by_tod[name] = {
            "n": n,
            "pct_hunt_30m": round(sum(1 for r in rows if r.get("hunt_30m")) / n * 100, 1),
            "pct_hunt_60m": round(sum(1 for r in rows if r.get("hunt_60m")) / n * 100, 1),
            "small_n": n < 10,
        }
    out["by_time_of_day"] = by_tod

    # Symbol x TOD cross — find biggest contributor
    cross: dict[str, dict] = {}
    for sym in SYMBOLS:
        for name, (lo, hi) in buckets.items():
            rows = [r for r in ok if r["symbol"] == sym and lo <= r["hour_utc"] < hi]
            if not rows:
                continue
            n = len(rows)
            hits = sum(1 for r in rows if r.get("hunt_60m"))
            key = f"{sym}_{name}"
            cross[key] = {
                "n": n,
                "hunts_60m": hits,
                "pct_hunt_60m": round(hits / n * 100, 1),
                "small_n": n < 5,
            }
    out["by_symbol_x_tod"] = cross

    # Top contributor by ABSOLUTE hunt count (not pct — we want mass)
    non_small = {k: v for k, v in cross.items() if not v["small_n"]}
    if non_small:
        top = max(non_small.items(), key=lambda kv: kv[1]["hunts_60m"])
        out["top_contributor"] = {"cell": top[0], **top[1]}
    else:
        # fall back to any cell
        if cross:
            top = max(cross.items(), key=lambda kv: kv[1]["hunts_60m"])
            out["top_contributor"] = {"cell": top[0], **top[1], "warning": "small_n"}

    # Wider-stop sim: what fraction of hunts would a 1.5x stop SAVE?
    hunts_60m = [r for r in ok if r.get("hunt_60m")]
    if hunts_60m:
        saved = sum(1 for r in hunts_60m if not r["wider_stop_would_fire"])
        out["wider_stop_saves_of_hunts_pct"] = round(saved / len(hunts_60m) * 100, 1)
        out["wider_stop_saves_n"] = saved
        out["wider_stop_hunts_total"] = len(hunts_60m)

    # Wider-stop sim: would the wider stop still have fired on legit losses?
    legit = [r for r in ok if r["legit_loss_60m"]]
    if legit:
        still_fired = sum(1 for r in legit if r["wider_stop_would_fire"])
        out["wider_stop_fires_on_legit_pct"] = round(still_fired / len(legit) * 100, 1)
        out["legit_losses_n"] = len(legit)

    # Legit vs hunt split
    out["legit_loss_pct"] = round(sum(1 for r in ok if r["legit_loss_60m"]) / total * 100, 1)

    return out


def main() -> None:
    print("Loading trades...")
    trades = pd.read_csv(TRADES_CSV)
    trades = trades[trades["sl_hit"].astype(str).str.lower() == "true"].reset_index(drop=True)
    print(f"SL-hit trades: {len(trades)}")

    print("Loading 5m bars for all symbols...")
    trades["_ts"] = pd.to_datetime(trades["timestamp"], utc=True)
    need_until = trades["_ts"].max() + timedelta(hours=12)
    bars = load_bars_5m(need_until=need_until)
    for s, df in bars.items():
        print(f"  {s}: {len(df)} bars, range={df['time'].min()} .. {df['time'].max()}")

    horizons = [5, 15, 30, 60]
    results = []
    for _, row in trades.iterrows():
        sym = row["symbol"]
        if sym not in bars:
            results.append({"error": "no_cache", "symbol": sym})
            continue
        try:
            r = classify_trade(row, bars[sym], horizons)
        except Exception as e:
            r = {"error": f"exception: {e}", "symbol": sym}
        results.append(r)

    agg = aggregate(results, horizons)

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUT_JSON.open("w") as f:
        json.dump({"aggregate": agg, "trades": results}, f, indent=2, default=str)

    print("\n=== AGGREGATE ===")
    print(json.dumps(agg, indent=2, default=str))
    print(f"\nWrote {OUT_JSON}")


if __name__ == "__main__":
    main()
