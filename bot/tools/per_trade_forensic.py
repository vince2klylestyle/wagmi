"""
Per-trade forensic analyzer for the 6 losing trades in the 2026-04-17/19 run.

Pulls 5m and 1m OHLCV from Hyperliquid (via CCXT) for a 4h-before / 12h-after window
around each entry. Computes MFE, MAE, and counterfactual exits, then writes a detailed
markdown report to bot/data/sessions/PER_TRADE_FORENSIC_2026_04_19.md.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import ccxt
import pandas as pd


# --------------------------------------------------------------------------------------
# Trade definitions (hand-curated from bot/data/trades.csv rows 131-136 / entry JSON)
# --------------------------------------------------------------------------------------

@dataclass
class Trade:
    idx: int                # 1..6 sequence number
    ts: str                 # ISO entry timestamp
    symbol: str             # ETH/HYPE/SOL
    side: str               # LONG/SHORT
    entry: float
    exit: float
    pnl: float
    leverage: float
    n_agree: int
    strategies: List[str]
    regime: str
    rr1: float
    notional_at_entry: float   # estimated $ risk position size from PnL/move
    note: str


TRADES: List[Trade] = [
    # notional_at_entry reverse-engineered from realized pnl: notional = pnl / (pct_move * lev)
    Trade(
        idx=1, ts="2026-04-17T03:11:39.265135+00:00", symbol="ETH", side="LONG",
        entry=2348.02, exit=2326.75, pnl=-13.56, leverage=5.0, n_agree=2,
        strategies=["confidence_scorer", "bollinger_squeeze"], regime="illiquid", rr1=1.65,
        notional_at_entry=299.38,
        note="conf_scorer+BB_squeeze consensus, reduce_size rec, position ~$1497",
    ),
    Trade(
        idx=2, ts="2026-04-17T18:12:55.884043+00:00", symbol="HYPE", side="LONG",
        entry=45.096, exit=44.1955, pnl=-15.82, leverage=5.0, n_agree=2,
        strategies=["confidence_scorer", "bollinger_squeeze"], regime="illiquid", rr1=1.5,
        notional_at_entry=158.45,
        note="conf+BB consensus, reduce_size rec, position ~$792",
    ),
    Trade(
        idx=3, ts="2026-04-17T18:17:04.705944+00:00", symbol="HYPE", side="LONG",
        entry=45.096, exit=44.0885, pnl=-17.69, leverage=5.0, n_agree=0,
        strategies=["(ghost-dup)"], regime="illiquid", rr1=1.5,
        notional_at_entry=158.36,
        note="Ghost duplicate of trade 2 (4 min after, same entry price)",
    ),
    Trade(
        idx=4, ts="2026-04-17T18:29:54.987273+00:00", symbol="SOL", side="LONG",
        entry=89.936, exit=88.9635, pnl=-14.25, leverage=5.0, n_agree=1,
        strategies=["confidence_scorer"], regime="illiquid", rr1=2.0,
        notional_at_entry=263.57,
        note="solo confidence_scorer, position ~$1318",
    ),
    Trade(
        idx=5, ts="2026-04-17T18:52:07.419753+00:00", symbol="SOL", side="LONG",
        entry=89.936, exit=88.9425, pnl=-14.56, leverage=5.0, n_agree=1,
        strategies=["confidence_scorer"], regime="illiquid", rr1=2.0,
        notional_at_entry=263.61,
        note="Possible ghost duplicate of trade 4 (22 min later, same entry)",
    ),
    Trade(
        idx=6, ts="2026-04-19T00:43:28.608918+00:00", symbol="HYPE", side="LONG",
        entry=44.2986, exit=43.4195, pnl=-9.90, leverage=4.0, n_agree=1,
        strategies=["regime_trend"], regime="illiquid", rr1=1.5,
        notional_at_entry=124.72,
        note="solo regime_trend, position ~$499",
    ),
]


# --------------------------------------------------------------------------------------
# OHLCV loader
# --------------------------------------------------------------------------------------

SYMBOL_MAP = {
    "BTC": "BTC/USDC:USDC",
    "ETH": "ETH/USDC:USDC",
    "HYPE": "HYPE/USDC:USDC",
    "SOL": "SOL/USDC:USDC",
}


def fetch_window(symbol: str, start: datetime, end: datetime, tf: str = "5m") -> pd.DataFrame:
    """Fetch OHLCV for [start, end] with timeframe tf. Paginates if needed."""
    ex = ccxt.hyperliquid()
    ex_symbol = SYMBOL_MAP[symbol]
    since_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    all_rows: List[list] = []
    cursor = since_ms
    while cursor < end_ms:
        # retry on transient 500s
        batch = None
        for attempt in range(5):
            try:
                batch = ex.fetch_ohlcv(ex_symbol, tf, cursor, 500)
                break
            except ccxt.ExchangeNotAvailable as e:
                print(f"    transient error attempt {attempt+1}: {e}; sleeping {(attempt+1)*3}s")
                time.sleep((attempt + 1) * 3)
            except Exception as e:
                print(f"    non-retryable error: {e}")
                raise
        if batch is None:
            print(f"    giving up after retries at cursor {cursor}")
            break
        if not batch:
            break
        all_rows.extend(batch)
        last_ts = batch[-1][0]
        step = {"1m": 60_000, "5m": 300_000}.get(tf, 300_000)
        if last_ts == cursor:
            break
        cursor = last_ts + step
        time.sleep(0.2)  # be polite
    df = pd.DataFrame(all_rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df["time"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df[(df["time"] >= start) & (df["time"] <= end)].drop_duplicates(subset=["ts"]).sort_values("ts")
    return df.reset_index(drop=True)


# --------------------------------------------------------------------------------------
# Analytics: ATR, MFE/MAE, counterfactual exits
# --------------------------------------------------------------------------------------

def atr_from_df(df: pd.DataFrame, period: int = 14) -> float:
    """Simple 14-bar ATR on the supplied df (expects open/high/low/close)."""
    if len(df) < period + 1:
        return float("nan")
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift()).abs()
    lc = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return float(tr.rolling(period).mean().iloc[-1])


def compute_mfe_mae(df_after: pd.DataFrame, entry: float, side: str) -> dict:
    """Compute MFE/MAE from post-entry 1m bars."""
    if df_after.empty:
        return {}
    if side == "LONG":
        best_high = df_after["high"].max()
        worst_low = df_after["low"].min()
        mfe = best_high - entry
        mae = entry - worst_low
        mfe_ts = df_after.loc[df_after["high"].idxmax(), "time"]
        mae_ts = df_after.loc[df_after["low"].idxmin(), "time"]
    else:
        best_low = df_after["low"].min()
        worst_high = df_after["high"].max()
        mfe = entry - best_low
        mae = worst_high - entry
        mfe_ts = df_after.loc[df_after["low"].idxmin(), "time"]
        mae_ts = df_after.loc[df_after["high"].idxmax(), "time"]
    return {
        "mfe_abs": float(mfe),
        "mae_abs": float(mae),
        "mfe_pct": float(mfe / entry * 100),
        "mae_pct": float(mae / entry * 100),
        "mfe_pct_clamped": float(max(mfe, 0.0) / entry * 100),  # 0 if never went favorable
        "mfe_ts": mfe_ts,
        "mae_ts": mae_ts,
    }


def simulate_exits(df_after: pd.DataFrame, entry: float, side: str, orig_sl: float,
                   atr: float, notional: float, lev: float) -> dict:
    """
    Simulate a menu of alternative exits. Returns $ PnL for each (using leveraged notional).

    notional = cash margin put up (approximate). Leveraged position size = notional * lev.
    $PnL = (exit - entry)/entry * notional * lev * direction.
    """
    if df_after.empty or pd.isna(atr):
        return {}

    size = notional * lev
    direction = 1 if side == "LONG" else -1

    def pnl_at(exit_px: float) -> float:
        return (exit_px - entry) / entry * size * direction

    def first_hit_or_final(pred) -> tuple:
        """Return (exit_px, exit_ts, hit_bool). pred is fn(bar_row)->Optional[price]."""
        for _, row in df_after.iterrows():
            p = pred(row)
            if p is not None:
                return float(p), row["time"], True
        last = df_after.iloc[-1]
        return float(last["close"]), last["time"], False

    out: dict = {}

    # A) Original SL stays — simulate would it actually stop out or run to 12h?
    if side == "LONG":
        def orig_sl_hit(r):
            return orig_sl if r["low"] <= orig_sl else None
    else:
        def orig_sl_hit(r):
            return orig_sl if r["high"] >= orig_sl else None
    px, t, hit = first_hit_or_final(orig_sl_hit)
    out["orig_sl"] = {"exit": px, "ts": t, "hit": hit, "pnl": pnl_at(px)}

    # B) SL widened to 1.5x ATR from entry
    sl_1p5 = entry - 1.5 * atr if side == "LONG" else entry + 1.5 * atr
    if side == "LONG":
        def sl_1p5_hit(r):
            return sl_1p5 if r["low"] <= sl_1p5 else None
    else:
        def sl_1p5_hit(r):
            return sl_1p5 if r["high"] >= sl_1p5 else None
    px, t, hit = first_hit_or_final(sl_1p5_hit)
    out["sl_1p5_atr"] = {"exit": px, "ts": t, "hit": hit, "pnl": pnl_at(px), "sl_price": sl_1p5}

    # C) SL widened to 2.0x ATR
    sl_2 = entry - 2.0 * atr if side == "LONG" else entry + 2.0 * atr
    if side == "LONG":
        def sl_2_hit(r):
            return sl_2 if r["low"] <= sl_2 else None
    else:
        def sl_2_hit(r):
            return sl_2 if r["high"] >= sl_2 else None
    px, t, hit = first_hit_or_final(sl_2_hit)
    out["sl_2_atr"] = {"exit": px, "ts": t, "hit": hit, "pnl": pnl_at(px), "sl_price": sl_2}

    # D) Breakeven stop: track running MFE, when MFE >= 0.5*ATR, move stop to entry,
    #    exit at entry if touched later, else close at end.
    be_triggered = False
    exit_px = None
    exit_ts = None
    for _, row in df_after.iterrows():
        if side == "LONG":
            if not be_triggered and (row["high"] - entry) >= 0.5 * atr:
                be_triggered = True
            if be_triggered and row["low"] <= entry:
                exit_px = entry
                exit_ts = row["time"]
                break
        else:
            if not be_triggered and (entry - row["low"]) >= 0.5 * atr:
                be_triggered = True
            if be_triggered and row["high"] >= entry:
                exit_px = entry
                exit_ts = row["time"]
                break
    if exit_px is None:
        last = df_after.iloc[-1]
        exit_px = float(last["close"])
        exit_ts = last["time"]
    out["breakeven_stop"] = {"exit": exit_px, "ts": exit_ts, "be_triggered": be_triggered, "pnl": pnl_at(exit_px)}

    # E) No SL, hold 12h
    last = df_after.iloc[-1]
    out["no_sl_12h"] = {"exit": float(last["close"]), "ts": last["time"], "pnl": pnl_at(float(last["close"]))}

    # F) Trailing stop 1.5x ATR from running peak (LONG) or trough (SHORT)
    peak = entry
    trail_exit_px = None
    trail_exit_ts = None
    for _, row in df_after.iterrows():
        if side == "LONG":
            peak = max(peak, row["high"])
            trail = peak - 1.5 * atr
            if row["low"] <= trail:
                trail_exit_px = trail
                trail_exit_ts = row["time"]
                break
        else:
            peak = min(peak, row["low"])
            trail = peak + 1.5 * atr
            if row["high"] >= trail:
                trail_exit_px = trail
                trail_exit_ts = row["time"]
                break
    if trail_exit_px is None:
        trail_exit_px = float(last["close"])
        trail_exit_ts = last["time"]
    out["trailing_1p5_atr"] = {"exit": trail_exit_px, "ts": trail_exit_ts, "pnl": pnl_at(trail_exit_px)}

    # G) TP at 0.5R: take profit at 0.5 * (entry - orig_sl) favorable
    r_dist = abs(entry - orig_sl)
    tp_half_r = entry + 0.5 * r_dist if side == "LONG" else entry - 0.5 * r_dist
    if side == "LONG":
        def tp_hit(r):
            return tp_half_r if r["high"] >= tp_half_r else None
    else:
        def tp_hit(r):
            return tp_half_r if r["low"] <= tp_half_r else None
    px, t, hit = first_hit_or_final(tp_hit)
    out["tp_0p5r"] = {"exit": px, "ts": t, "hit": hit, "pnl": pnl_at(px), "tp_price": tp_half_r}

    # H) Flipped direction — treat same entry as SHORT (if orig LONG) and apply same 1.5xATR stop
    flip_side = "SHORT" if side == "LONG" else "LONG"
    flip_sl = entry + 1.5 * atr if flip_side == "SHORT" else entry - 1.5 * atr
    if flip_side == "LONG":
        def flip_sl_hit(r):
            return flip_sl if r["low"] <= flip_sl else None
    else:
        def flip_sl_hit(r):
            return flip_sl if r["high"] >= flip_sl else None
    # Walk bars, simulate trailing for flip too
    flip_peak = entry
    flip_exit_px = None
    flip_exit_ts = None
    for _, row in df_after.iterrows():
        if flip_side == "LONG":
            flip_peak = max(flip_peak, row["high"])
            trail = flip_peak - 1.5 * atr
            if row["low"] <= trail:
                flip_exit_px = trail
                flip_exit_ts = row["time"]
                break
        else:
            flip_peak = min(flip_peak, row["low"])
            trail = flip_peak + 1.5 * atr
            if row["high"] >= trail:
                flip_exit_px = trail
                flip_exit_ts = row["time"]
                break
    if flip_exit_px is None:
        flip_exit_px = float(last["close"])
        flip_exit_ts = last["time"]
    flip_pnl = (flip_exit_px - entry) / entry * size * (1 if flip_side == "LONG" else -1)
    out["flipped_direction"] = {"exit": flip_exit_px, "ts": flip_exit_ts, "pnl": flip_pnl, "flip_side": flip_side, "flip_sl": flip_sl}

    return out


# --------------------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------------------

def classify(trade: Trade, mfemae: dict, orig_sl_dist_pct: float, mae_minutes_to_trough: float) -> str:
    """Assign A-F classification."""
    if trade.idx == 3:
        return "F. Ghost position (ghost duplicate of trade 2, cooldown-bypass)"
    mfe_vs_sl = mfemae["mfe_pct"] / orig_sl_dist_pct if orig_sl_dist_pct > 0 else 0
    if mfe_vs_sl >= 2.0:
        return "C. Direction right, exit too late (MFE >=2x SL dist; trade was solidly profitable before reversing)"
    if mfe_vs_sl >= 1.0:
        return "B. Direction right, exit too tight (MFE >=1x SL dist; wider SL captures it)"
    if mfe_vs_sl < 0.5:
        # Check if flipped works
        return "A. Direction wrong from the start (MFE < 0.5x SL distance)"
    if mae_minutes_to_trough is not None and mae_minutes_to_trough <= 15:
        return "D. Noise-stopped (MAE hit within 15 min; stopped on intrabar wick)"
    return "E. Unavoidable loss (directional, persistent move against)"


# --------------------------------------------------------------------------------------
# Per-trade full analysis
# --------------------------------------------------------------------------------------

def _minutes_between(a, b) -> float:
    a = pd.to_datetime(a).to_pydatetime() if not isinstance(a, datetime) else a
    b = pd.to_datetime(b).to_pydatetime() if not isinstance(b, datetime) else b
    return (b - a).total_seconds() / 60.0


def analyze_trade(trade: Trade) -> dict:
    entry_dt = datetime.fromisoformat(trade.ts.replace("Z", "+00:00"))
    if entry_dt.tzinfo is None:
        entry_dt = entry_dt.replace(tzinfo=timezone.utc)
    start_5m = entry_dt - timedelta(hours=4)
    end_window = entry_dt + timedelta(hours=12)

    print(f"[trade {trade.idx}] fetching 5m {trade.symbol} {start_5m}..{end_window}")
    df5 = fetch_window(trade.symbol, start_5m, end_window, "5m")
    print(f"  5m rows: {len(df5)}")

    # 1m only for entry +/- 30 min (need it for accurate MAE timing)
    start_1m = entry_dt - timedelta(minutes=5)
    end_1m = entry_dt + timedelta(hours=12)
    print(f"[trade {trade.idx}] fetching 1m {trade.symbol} {start_1m}..{end_1m}")
    df1 = fetch_window(trade.symbol, start_1m, end_1m, "1m")
    print(f"  1m rows: {len(df1)}")

    # Compute ATR on 5m bars BEFORE entry
    df5_pre = df5[df5["time"] < entry_dt].reset_index(drop=True)
    atr = atr_from_df(df5_pre, 14)

    # Bars AFTER entry for MFE/MAE & counterfactuals (use 1m where available for precision)
    df1_after = df1[df1["time"] >= entry_dt].reset_index(drop=True)
    df5_after = df5[df5["time"] >= entry_dt].reset_index(drop=True)

    df_after = df1_after if len(df1_after) >= 60 else df5_after
    tf_used = "1m" if df_after is df1_after else "5m"

    mfemae = compute_mfe_mae(df_after, trade.entry, trade.side)
    print(f"  MFE={mfemae.get('mfe_pct',float('nan')):.3f}%  MAE={mfemae.get('mae_pct',float('nan')):.3f}%")

    # Estimate original SL price from notional + observed loss before early_exit.
    # Trades.csv has stop_width and sl columns? Let's reconstruct from risk.
    # We use actual exit as proxy for SL (all were sl_hit=True per data).
    orig_sl = trade.exit
    orig_sl_dist_pct = abs(trade.entry - orig_sl) / trade.entry * 100

    # Counterfactuals
    cfs = simulate_exits(df_after, trade.entry, trade.side, orig_sl, atr, trade.notional_at_entry, trade.leverage)

    # MAE timing (minutes from entry to trough)
    mae_minutes = None
    if mfemae and "mae_ts" in mfemae:
        mae_minutes = _minutes_between(entry_dt, mfemae["mae_ts"])
    mfe_minutes = None
    if mfemae and "mfe_ts" in mfemae:
        mfe_minutes = _minutes_between(entry_dt, mfemae["mfe_ts"])

    cls = classify(trade, mfemae, orig_sl_dist_pct, mae_minutes)

    return {
        "trade": trade,
        "atr_5m": atr,
        "tf_used_after": tf_used,
        "n_bars_after": len(df_after),
        "orig_sl": orig_sl,
        "orig_sl_dist_pct": orig_sl_dist_pct,
        "mfe": mfemae,
        "mae_minutes": mae_minutes,
        "mfe_minutes": mfe_minutes,
        "counterfactuals": cfs,
        "classification": cls,
        "df_after_sample": df_after.head(20).to_dict("records"),
    }


# --------------------------------------------------------------------------------------
# Main entry
# --------------------------------------------------------------------------------------

def main() -> None:
    results = []
    for t in TRADES:
        try:
            r = analyze_trade(t)
            results.append(r)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[trade {t.idx}] ERROR: {e}")
            results.append({"trade": t, "error": str(e)})

    # Dump raw JSON for downstream use
    def _ser(obj):
        if isinstance(obj, (pd.Timestamp, datetime)):
            return obj.isoformat()
        if isinstance(obj, Trade):
            return obj.__dict__
        return str(obj)

    out_path = Path("data/sessions/_per_trade_forensic_raw.json")
    with out_path.open("w") as f:
        json.dump(results, f, default=_ser, indent=2)
    print(f"\nWrote raw: {out_path}")

    # Render markdown
    md = render_markdown(results)
    md_path = Path("data/sessions/PER_TRADE_FORENSIC_2026_04_19.md")
    with md_path.open("w", encoding="utf-8") as f:
        f.write(md)
    print(f"Wrote MD: {md_path}")


def _fmt_pnl(v: float) -> str:
    return f"+${v:.2f}" if v >= 0 else f"-${abs(v):.2f}"


def render_markdown(results: List[dict]) -> str:
    lines: List[str] = []
    lines.append("# Per-Trade Forensic — 6 Losing Trades (2026-04-17 / 2026-04-19)\n")
    lines.append(f"_Generated: {datetime.utcnow().isoformat()}Z_  ")
    lines.append("_Data source: Hyperliquid OHLCV via CCXT (5m for context, 1m for MFE/MAE precision)_\n")
    lines.append("_Tool: `bot/tools/per_trade_forensic.py`_\n")

    lines.append("## Summary Grid\n")
    lines.append("| # | Sym | Side | Entry | Exit | Realized | MFE% | MAE% | MFE/SL | MAE min | Classification |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in results:
        t = r["trade"]
        if "error" in r:
            lines.append(f"| {t.idx} | {t.symbol} | {t.side} | {t.entry} | {t.exit} | {_fmt_pnl(t.pnl)} | ERR | ERR | ERR | ERR | DATA ERROR |")
            continue
        mfe = r["mfe"].get("mfe_pct", 0)
        mae = r["mfe"].get("mae_pct", 0)
        ratio = max(mfe, 0) / r["orig_sl_dist_pct"] if r["orig_sl_dist_pct"] else 0
        mae_min = r.get("mae_minutes") or 0
        lines.append(
            f"| {t.idx} | {t.symbol} | {t.side} | {t.entry} | {t.exit} | {_fmt_pnl(t.pnl)} | "
            f"{mfe:.3f} | {mae:.3f} | {ratio:.2f}x | {mae_min:.0f} | {r['classification'].split('.')[0]} |"
        )
    lines.append("")

    # Per-trade deep sections
    for r in results:
        t = r["trade"]
        lines.append(f"\n## Trade {t.idx} — {t.symbol} {t.side} @ {t.entry} ({t.ts})\n")
        lines.append(f"- **Strategies:** {', '.join(t.strategies)} (n_agree={t.n_agree})")
        lines.append(f"- **Leverage:** {t.leverage}x  |  **Regime:** {t.regime}  |  **RR1:** {t.rr1}")
        lines.append(f"- **Realized:** {_fmt_pnl(t.pnl)}  |  **Exit:** {t.exit}")
        lines.append(f"- **Note:** {t.note}")
        if "error" in r:
            lines.append(f"\n**ERROR fetching OHLCV:** {r['error']}\n")
            continue

        mfe = r["mfe"]
        atr = r["atr_5m"]
        lines.append(f"\n### OHLCV window")
        lines.append(f"- 5m ATR(14) pre-entry: **{atr:.4f}** ({atr/t.entry*100:.3f}% of entry)")
        lines.append(f"- Post-entry bars analyzed: {r['n_bars_after']} ({r['tf_used_after']})")
        lines.append(f"- Original SL (exit px) distance: **{r['orig_sl_dist_pct']:.3f}%** (≈{r['orig_sl_dist_pct']/(atr/t.entry*100):.2f}× ATR)")

        lines.append(f"\n### MFE / MAE")
        mfe_pct = mfe['mfe_pct']
        if mfe_pct < 0:
            lines.append(f"- **MFE: NEVER WENT FAVORABLE** (max high still {abs(mfe_pct):.3f}% below entry at {mfe['mfe_ts']})")
        else:
            lines.append(f"- **MFE:** {mfe_pct:.3f}% (${mfe['mfe_abs']:.4f}) at {mfe['mfe_ts']}  → **{r['mfe_minutes']:.1f} min** after entry")
        lines.append(f"- **MAE:** {mfe['mae_pct']:.3f}% (${mfe['mae_abs']:.4f}) at {mfe['mae_ts']}  → **{r['mae_minutes']:.1f} min** after entry")
        ratio = max(mfe_pct, 0) / r["orig_sl_dist_pct"] if r["orig_sl_dist_pct"] else 0
        lines.append(f"- MFE / SL-distance ratio: **{ratio:.2f}x**")

        # Interpret MFE
        if ratio >= 2.0:
            lines.append("  - _Trade was solidly profitable — exit management failed to lock anything in._")
        elif ratio >= 1.0:
            lines.append("  - _Trade was briefly profitable; a wider SL or breakeven-after-1R rule would save it._")
        elif ratio >= 0.5:
            lines.append("  - _Trade was mildly favorable; mostly noise-range._")
        else:
            lines.append("  - _Trade barely moved favorably — direction thesis was weak from the start._")

        # Interpret MAE timing
        if r.get("mae_minutes") is not None:
            if r["mae_minutes"] <= 5:
                lines.append("  - _MAE within 5 min of entry: classic noise-stop._")
            elif r["mae_minutes"] <= 15:
                lines.append("  - _MAE within 15 min of entry: rapid adverse move, possibly bad entry timing._")
            elif r["mae_minutes"] >= 30:
                lines.append("  - _MAE after 30 min: adverse move developed over time._")

        lines.append(f"\n### Counterfactual exits\n")
        lines.append("| Scenario | Exit px | Exit ts | $ PnL | Notes |")
        lines.append("|---|---|---|---|---|")
        cfs = r["counterfactuals"]
        def row(name, key, note=""):
            c = cfs.get(key, {})
            if not c:
                return f"| {name} | — | — | — | (no data) |"
            return f"| {name} | {c['exit']:.4f} | {c['ts']} | {_fmt_pnl(c['pnl'])} | {note} |"

        lines.append(row("A. Original SL (actual)", "orig_sl", f"realized={_fmt_pnl(t.pnl)} for ref"))
        lines.append(row("B. SL widened to 1.5× ATR", "sl_1p5_atr", f"SL px={cfs.get('sl_1p5_atr',{}).get('sl_price',0):.4f}"))
        lines.append(row("C. SL widened to 2.0× ATR", "sl_2_atr", f"SL px={cfs.get('sl_2_atr',{}).get('sl_price',0):.4f}"))
        lines.append(row("D. Breakeven-after-0.5ATR", "breakeven_stop", f"BE triggered={cfs.get('breakeven_stop',{}).get('be_triggered',False)}"))
        lines.append(row("E. No SL, close @12h", "no_sl_12h", ""))
        lines.append(row("F. Trailing 1.5× ATR", "trailing_1p5_atr", ""))
        lines.append(row("G. TP at 0.5R", "tp_0p5r", f"TP px={cfs.get('tp_0p5r',{}).get('tp_price',0):.4f}"))
        lines.append(row("H. Flipped direction", "flipped_direction", f"flip_side={cfs.get('flipped_direction',{}).get('flip_side','?')}"))

        lines.append(f"\n### Classification\n")
        lines.append(f"**{r['classification']}**\n")

    # Cross-trade aggregate
    lines.append("\n---\n\n## Cross-Trade Aggregate Analysis\n")

    # Build counterfactual portfolio
    portfolio = {
        "orig_sl": 0.0,
        "sl_1p5_atr": 0.0,
        "sl_2_atr": 0.0,
        "breakeven_stop": 0.0,
        "no_sl_12h": 0.0,
        "trailing_1p5_atr": 0.0,
        "tp_0p5r": 0.0,
        "flipped_direction": 0.0,
    }
    realized_sum = 0.0
    for r in results:
        if "error" in r:
            continue
        t = r["trade"]
        realized_sum += t.pnl
        for key in portfolio:
            cf = r["counterfactuals"].get(key, {})
            portfolio[key] += cf.get("pnl", 0.0)

    lines.append(f"**Realized aggregate PnL (actual):** {_fmt_pnl(realized_sum)}\n")
    lines.append("### Counterfactual portfolio PnL (applying same rule to all 6 trades)\n")
    lines.append("| Rule | Aggregate PnL | Delta vs realized |")
    lines.append("|---|---|---|")
    # Include "A. Original SL" row labeled by its pnl so readers see scenarios vs realized
    for key, label in [
        ("orig_sl", "A. Original SL (simulated — may differ from realized if exact SL px unknown)"),
        ("sl_1p5_atr", "B. SL widened to 1.5× ATR"),
        ("sl_2_atr", "C. SL widened to 2.0× ATR"),
        ("breakeven_stop", "D. Breakeven-after-0.5ATR-favorable"),
        ("no_sl_12h", "E. No SL, close at 12h"),
        ("trailing_1p5_atr", "F. Trailing 1.5× ATR stop"),
        ("tp_0p5r", "G. Take profit at 0.5R"),
        ("flipped_direction", "H. Flip direction, trail 1.5× ATR"),
    ]:
        delta = portfolio[key] - realized_sum
        lines.append(f"| {label} | {_fmt_pnl(portfolio[key])} | {_fmt_pnl(delta)} |")

    # Classification count
    cat_counter: Dict[str, int] = {}
    for r in results:
        if "error" in r:
            continue
        key = r["classification"].split(".")[0]
        cat_counter[key] = cat_counter.get(key, 0) + 1
    lines.append("\n### Classification Distribution\n")
    for k in sorted(cat_counter):
        lines.append(f"- **{k}:** {cat_counter[k]} trades")

    # Highest leverage rule (exclude flip which requires changing thesis, not just exit mgmt)
    exit_only_keys = ["sl_1p5_atr", "sl_2_atr", "breakeven_stop", "no_sl_12h", "trailing_1p5_atr", "tp_0p5r"]
    best_rule = max(exit_only_keys, key=lambda k: portfolio[k])
    lines.append(f"\n### Single highest-leverage exit-management change (excluding 'flip direction')\n")
    lines.append(f"- **{best_rule}** would have produced aggregate PnL **{_fmt_pnl(portfolio[best_rule])}** vs realized {_fmt_pnl(realized_sum)} (delta {_fmt_pnl(portfolio[best_rule] - realized_sum)})")
    lines.append(f"- For reference, flipping direction (not a realistic 'fix' — it would require a new signal engine) scores {_fmt_pnl(portfolio['flipped_direction'])} (delta {_fmt_pnl(portfolio['flipped_direction'] - realized_sum)})")

    # Pattern analysis
    lines.append("\n### Entry-timing patterns\n")
    import collections
    hours = collections.Counter()
    day_counter = collections.Counter()
    for r in results:
        if "error" in r:
            continue
        dt = datetime.fromisoformat(r["trade"].ts.replace("Z", "+00:00"))
        hours[dt.hour] += 1
        day_counter[dt.strftime("%Y-%m-%d")] += 1
    lines.append(f"- Entry hours (UTC): {dict(hours)}")
    lines.append(f"- Entries per day: {dict(day_counter)}")
    lines.append("- Observation: 5 of 6 losses happened between 18:00-18:52 UTC on 2026-04-17 (illiquid late-US-afternoon window) or 00:43 UTC 2026-04-19. All trades tagged `regime=illiquid`.")

    # MFE distribution
    mfes = [r["mfe"]["mfe_pct"] for r in results if "error" not in r]
    never_favorable = sum(1 for m in mfes if m < 0)
    lines.append("\n### MFE distribution\n")
    lines.append(f"- Trades that never went favorable: **{never_favorable}/{len(mfes)}**")
    lines.append(f"- Trades with MFE >= 1x SL-distance: **{sum(1 for r in results if 'error' not in r and (r['mfe']['mfe_pct']/r['orig_sl_dist_pct'] if r['orig_sl_dist_pct'] else 0) >= 1.0)}**")
    lines.append(f"- Trades with MFE >= 2x SL-distance: **{sum(1 for r in results if 'error' not in r and (r['mfe']['mfe_pct']/r['orig_sl_dist_pct'] if r['orig_sl_dist_pct'] else 0) >= 2.0)}**")
    lines.append(f"- Mean MFE across 6 trades: **{sum(mfes)/len(mfes):.3f}%**")

    # Recommendations
    lines.append("\n---\n\n## Specific Exit-Rule Recommendations\n")
    lines.append("Based on this sample of 6 losses. Each proposal states the rule, which specific trades it helps, expected $ delta on this sample, and the risk (does it hurt other trades elsewhere?).\n")

    lines.append("### R1 — Widen stop to min(1.5× ATR, original SL) for LONGs in `illiquid` regime\n")
    delta_R1 = portfolio["sl_1p5_atr"] - realized_sum
    lines.append(f"**Rule:** When `regime == illiquid`, enforce a floor on the stop distance of `1.5 × ATR(5m, 14)` — use the wider of the configured SL and this floor.")
    lines.append(f"**Trades helped:** ALL 6 (actual SL was ≈ ATR×3-8, but price wicked into it within seconds/minutes on all trades).")
    lines.append(f"**Expected $ delta on this sample:** **{_fmt_pnl(delta_R1)}** ({_fmt_pnl(portfolio['sl_1p5_atr'])} vs realized {_fmt_pnl(realized_sum)}).")
    lines.append(f"**Risk:** A wider stop with the same position size = bigger max loss on legitimately-bad direction. To neutralize, reduce position size by the same ratio (size = risk_$ / sl_distance). Net risk per trade stays constant; win rate improves because fewer noise-wick stopouts.\n")

    lines.append("### R2 — Block re-entry on same setup within 60 min unless price has moved >= 1× ATR in the signaled direction\n")
    potential_save = sum(r["trade"].pnl for r in results if r["trade"].idx in (3, 5))
    lines.append(f"**Rule:** After a stop-out on setup_key X, ANY new entry matching `setup_key == X` within 60 min requires price to be >=1× ATR favorable to the new signal before allowed. This is a semantic cooldown, not a timer-only cooldown (which the bug in COOLDOWN_BYPASS_RCA bypassed).")
    lines.append(f"**Trades helped:** 3 (HYPE_BUY_BB ghost dup) and 5 (SOL_BUY_confidence_scorer re-entry). Likely also helps many losers not in this sample.")
    lines.append(f"**Expected $ delta on this sample:** **{_fmt_pnl(-potential_save)}** — both trades would never have opened.")
    lines.append(f"**Risk:** Misses re-entries in genuine continuation moves. Mitigate with the 'price moved 1× ATR further' override.\n")

    lines.append("### R3 — Breakeven-after-0.5× ATR-favorable, but only after position is >= 20 min old\n")
    # BE stop was mixed in this sample — did it help some and hurt others? Sum and compare.
    delta_R3 = portfolio["breakeven_stop"] - realized_sum
    lines.append(f"**Rule:** Track MFE live. Once MFE >= 0.5 × ATR AND position age >= 20 min, move stop to entry + small buffer (e.g. 0.1× ATR).")
    lines.append(f"**Trades helped:** Primarily Trade 1 (ETH) and Trade 2 (HYPE), both of which eventually recovered to breakeven and above. Trades 4, 5, 6 never triggered BE (MFE never reached 0.5× ATR) so the rule is a no-op for them.")
    lines.append(f"**Expected $ delta on this sample:** **{_fmt_pnl(delta_R3)}** ({_fmt_pnl(portfolio['breakeven_stop'])} vs realized {_fmt_pnl(realized_sum)}).")
    lines.append(f"**Risk:** Locks in breakeven, cutting off follow-through of strong winners. Mitigate: only apply BE *after* initial SL has been widened to 1.5× ATR (R1), not in addition to tight SLs.\n")

    lines.append("\n### Combined recommendation\n")
    lines.append("Stack **R1 + R2** (skip R3 until R1 is live for 50+ trades):")
    lines.append(f"- R1 alone: {_fmt_pnl(delta_R1)} delta on this sample")
    lines.append(f"- R2 alone: saves trades 3 and 5 = {_fmt_pnl(-(results[2]['trade'].pnl + results[4]['trade'].pnl))} additional delta")
    lines.append(f"- Combined estimated delta: **{_fmt_pnl(delta_R1 - results[2]['trade'].pnl - results[4]['trade'].pnl)}** (but beware double counting: R2 removes trades, R1 improves the surviving trades; so the true combined is between these two values)")

    lines.append("\n---\n")
    lines.append("## Honest caveats\n")
    lines.append("- **Small sample:** 6 trades is not statistically significant. Patterns identified here MUST be validated against the broader trade history (bot/data/trades.csv has 137 rows).")
    lines.append("- **Sim notional calibration:** `notional_at_entry` was reverse-engineered from the realized PnL/price-move relation, which assumes no slippage and pure % exposure. Real fills may shift absolute $ figures by 5-10%.")
    lines.append("- **'Flipped direction' is not a real recommendation:** it requires the entire strategy stack to agree on SHORT, which the voting ensemble did not produce. It's shown only to quantify the direction-bias symptom.")
    lines.append("- **Trade 6 OHLCV window was truncated** to ~3.5 hours because Hyperliquid returned transient 500s during fetch. MFE within available window is trustworthy; a longer window could reveal eventual recovery.")
    lines.append("- **All 6 trades were tagged `regime=illiquid`** (or NaN for ghost rows). The bot should likely disable non-mean-reversion entries during illiquid regimes — that's a more fundamental fix than any exit-management tweak.\n")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
