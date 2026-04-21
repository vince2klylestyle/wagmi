"""Stop-hunting detector for WAGMI SL-hit trades.

Pulls 5m bars around each SL-hit trade exit (-10m to +60m) from Hyperliquid
via CCXT and determines whether the stop-out was a "hunt" (wick + reversal
through entry within N minutes) or a legitimate follow-through move.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import ccxt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TRADES = ROOT / "data" / "trades.csv"
LEDGER = ROOT / "data" / "trade_ledger.csv"
CACHE = ROOT / "data" / "cache" / "stop_hunt_5m_cache.parquet"
CACHE.parent.mkdir(parents=True, exist_ok=True)

REVERSAL_WINDOWS_MIN = [5, 15, 30, 60]


# ---------- Hyperliquid symbol mapping ----------

def hl_symbol(sym: str) -> str:
    return f"{sym}/USDC:USDC"


# ---------- Data loading ----------

def load_sl_trades() -> pd.DataFrame:
    trades = pd.read_csv(TRADES)
    ledger = pd.read_csv(LEDGER)

    trades["timestamp"] = pd.to_datetime(trades["timestamp"], utc=True)
    ledger["entry_dt"] = pd.to_datetime(ledger["timestamp"], unit="s", utc=True)

    # Align by order; rows are 1:1 between files (same length, same symbol column).
    assert len(trades) == len(ledger), f"{len(trades)} vs {len(ledger)}"
    trades = trades.reset_index(drop=True)
    ledger = ledger.reset_index(drop=True)

    merged = trades.copy()
    merged["hold_hours"] = ledger["hold_hours"]
    merged["exit_type"] = ledger["exit_type"]
    merged["entry_dt"] = merged["timestamp"]
    merged["exit_dt"] = merged["entry_dt"] + pd.to_timedelta(
        merged["hold_hours"], unit="h"
    )

    # SL-hit subset
    sl = merged[merged["sl_hit"] == True].copy()
    # Compute SL price proxy (for SL-hit, exit price is a tight proxy for the SL)
    sl["sl_price"] = sl["exit"]
    sl["entry_price"] = sl["entry"]
    return sl


# ---------- OHLCV fetcher ----------

def fetch_5m_around(
    ex, symbol: str, exit_dt: pd.Timestamp, pre_min: int = 15, post_min: int = 75,
    max_retries: int = 6, base_sleep: float = 2.0,
) -> pd.DataFrame | None:
    """Fetch 5m bars from `exit_dt - pre_min` to `exit_dt + post_min`.

    Retries with exponential backoff on 429s.
    """
    since_ms = int((exit_dt - pd.Timedelta(minutes=pre_min)).timestamp() * 1000)
    limit = (pre_min + post_min) // 5 + 5
    bars = None
    for attempt in range(max_retries):
        try:
            bars = ex.fetch_ohlcv(symbol, "5m", since=since_ms, limit=limit)
            break
        except Exception as e:
            msg = str(e)
            if "429" in msg or "Too Many" in msg:
                wait = base_sleep * (2 ** attempt)
                print(f"   429 backoff {wait:.1f}s ({symbol} attempt {attempt+1})")
                time.sleep(wait)
                continue
            print(f"   fetch fail {symbol} {exit_dt}: {e}")
            return None
    if not bars:
        return None
    df = pd.DataFrame(bars, columns=["ts", "open", "high", "low", "close", "vol"])
    df["dt"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    end = exit_dt + pd.Timedelta(minutes=post_min)
    df = df[(df["dt"] >= exit_dt - pd.Timedelta(minutes=pre_min)) & (df["dt"] <= end)]
    return df.reset_index(drop=True)


# ---------- Hunt detection ----------

@dataclass
class HuntResult:
    idx: int
    symbol: str
    side: str
    entry: float
    sl_price: float
    exit_dt: str
    utc_hour: int
    sl_width_pct: float
    hunt_5m: bool
    hunt_15m: bool
    hunt_30m: bool
    hunt_60m: bool
    would_survive_1_5x: bool  # would trade have stopped if SL were 1.5× wider?
    would_survive_2_0x: bool
    # Reverse check: if NOT a hunt, was this a legitimate continuation?
    continuation_pct_60m: float  # move beyond SL level within 60m (against entry)


def detect_hunt(row: pd.Series, bars: pd.DataFrame) -> HuntResult:
    side = row["side"]
    entry = float(row["entry_price"])
    sl_px = float(row["sl_price"])
    exit_dt = row["exit_dt"]

    # Align to post-exit window
    post = bars[bars["dt"] >= exit_dt].sort_values("dt").reset_index(drop=True)

    # For LONG: hunt = price went below SL then reversed back ABOVE entry
    # For SHORT: hunt = price went above SL then reversed back BELOW entry
    hunts = {}
    for w in REVERSAL_WINDOWS_MIN:
        window = post[post["dt"] <= exit_dt + pd.Timedelta(minutes=w)]
        if len(window) == 0:
            hunts[w] = False
            continue
        if side == "LONG":
            reversed_thru_entry = (window["high"] >= entry).any()
        else:
            reversed_thru_entry = (window["low"] <= entry).any()
        hunts[w] = bool(reversed_thru_entry)

    # Stop width
    sl_width_pct = abs(entry - sl_px) / entry * 100.0

    # Would a 1.5× / 2.0× wider stop have survived?
    # Wider SL levels:
    if side == "LONG":
        sl_1_5 = entry - 1.5 * (entry - sl_px)
        sl_2_0 = entry - 2.0 * (entry - sl_px)
        window60 = post[post["dt"] <= exit_dt + pd.Timedelta(minutes=60)]
        # Would survive if lowest low in post window never touched wider SL
        lo = window60["low"].min() if len(window60) else sl_px
        survive_1_5 = lo > sl_1_5
        survive_2_0 = lo > sl_2_0
    else:
        sl_1_5 = entry + 1.5 * (sl_px - entry)
        sl_2_0 = entry + 2.0 * (sl_px - entry)
        window60 = post[post["dt"] <= exit_dt + pd.Timedelta(minutes=60)]
        hi = window60["high"].max() if len(window60) else sl_px
        survive_1_5 = hi < sl_1_5
        survive_2_0 = hi < sl_2_0

    # Continuation: how far past SL did price go within 60m? (positive = further against us)
    if side == "LONG":
        worst = window60["low"].min() if len(window60) else sl_px
        continuation_pct = (sl_px - worst) / entry * 100.0  # positive = extended below SL
    else:
        worst = window60["high"].max() if len(window60) else sl_px
        continuation_pct = (worst - sl_px) / entry * 100.0

    return HuntResult(
        idx=int(row.name),
        symbol=row["symbol"],
        side=side,
        entry=entry,
        sl_price=sl_px,
        exit_dt=str(exit_dt),
        utc_hour=int(exit_dt.hour),
        sl_width_pct=round(sl_width_pct, 4),
        hunt_5m=hunts[5],
        hunt_15m=hunts[15],
        hunt_30m=hunts[30],
        hunt_60m=hunts[60],
        would_survive_1_5x=bool(survive_1_5),
        would_survive_2_0x=bool(survive_2_0),
        continuation_pct_60m=round(float(continuation_pct), 4),
    )


# ---------- Runner ----------

def run() -> pd.DataFrame:
    sl = load_sl_trades()
    print(f"Loaded {len(sl)} SL-hit trades")

    out_path = ROOT / "data" / "stop_hunt_results.csv"
    # Resume: skip rows already processed (keyed by idx)
    done_idx: set[int] = set()
    if out_path.exists():
        prev = pd.read_csv(out_path)
        done_idx = set(prev["idx"].astype(int).tolist())
        print(f"Resume: {len(done_idx)} trades already done")

    ex = ccxt.hyperliquid({"enableRateLimit": True, "rateLimit": 500})
    # Retry load_markets with backoff too
    for attempt in range(8):
        try:
            ex.load_markets()
            break
        except Exception as e:
            if "429" in str(e) or "Too Many" in str(e):
                wait = 5.0 * (2 ** attempt)
                print(f"load_markets 429, waiting {wait:.1f}s (attempt {attempt+1})")
                time.sleep(wait)
            else:
                raise

    results: list[HuntResult] = []
    sl_reset = sl.reset_index(drop=True)
    for i, row in sl_reset.iterrows():
        # Preserve original trades.csv row index as idx for stable keying
        orig_idx = int(row.name) if hasattr(row, "name") else int(i)
        # We used reset_index(drop=True) so row.name == i. Use position i.
        orig_idx = int(i)
        if orig_idx in done_idx:
            continue
        sym = hl_symbol(row["symbol"])
        if sym not in ex.markets:
            print(f"Skip {sym}: not in markets")
            continue
        # Make row mutable with stable idx
        row = row.copy()
        row.name = orig_idx
        bars = fetch_5m_around(ex, sym, row["exit_dt"])
        if bars is None or len(bars) == 0:
            print(f"Skip {row['symbol']} {row['exit_dt']}: no bars")
            continue
        res = detect_hunt(row, bars)
        results.append(res)
        # Append incrementally so we don't lose progress
        new_row = pd.DataFrame([asdict(res)])
        header = not out_path.exists()
        new_row.to_csv(out_path, mode="a", header=header, index=False)
        if i % 5 == 0:
            print(f"[{i+1}/{len(sl_reset)}] {row['symbol']} {row['side']} hunt30={res.hunt_30m} survive1.5={res.would_survive_1_5x}")
        time.sleep(0.5)  # be polite

    print(f"\nTotal new: {len(results)}  ->  {out_path}")
    return pd.read_csv(out_path)


if __name__ == "__main__":
    run()
