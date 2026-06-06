"""
Retrospective trade-feature backfill — 2026-04-19.

Enriches every historical trade in `bot/data/trades.csv` with features that
were COMPUTED at signal time but never PERSISTED (per DATA_CAPTURE_AUDIT_2026_04_19.md).

Reconstructs per-trade:
  - atr_1h_14            (14-period ATR on 1h at entry bar)
  - rsi_1h_14, rsi_6h_14 (RSI 14 on 1h and 6h at entry bar)
  - rsi_div_1h_6h_aligned (RSI_1h - RSI_6h, sign-flipped for SHORT — Bonferroni
                          winner from CRYPTO_FEATURES_WAVE, IC=+0.255 vs PnL)
  - adx_1h_14            (14-period Wilder ADX on 1h)
  - chop_score_proxy     (ATR / distance-travelled over last N bars, 1h)
  - stop_width_pct       (from trades.csv entry/sl if present; else NaN)
  - regime_1h, regime_6h (simplified 3-class: trend_up / trend_down / range)
  - mfe_R, mae_R         (max favourable/adverse excursion in R multiples,
                          from entry to exit timestamp or 12h cap)
  - volume_ratio_1h      (current bar volume / 24h rolling mean on 1h)
  - hour_bucket_4        (from timestamp, 0..5)
  - atr_pct              (atr_1h_14 / entry_price)
  - distance_to_1h_high  / distance_to_1h_low  (% from entry)
  - btc_4h_return_signed (BTC 4h log-return, sign-flipped for SHORT on non-BTC
                          symbols to align with "BTC tailwind for trade")

Data source priority:
  1. Stitched disk caches in bot/data/cache/{SYM}_{TF}_*d.csv
  2. CCXT live fetch via bot.data.fetcher.DataFetcher (gap fill)

Outputs:
  - bot/data/trades_enriched_2026_04_19.csv  (original cols + new features)
  - Prints IC table for new features (Spearman vs PnL and Win)
  - Flags Bonferroni-clearing features

Reusable: run any time to refresh the enriched dataset.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import sys
import glob
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats

REPO = Path(r"C:\Users\vince\WAGMI PROJECT\WAGMI")
TRADES_CSV = REPO / "bot" / "data" / "trades.csv"
CACHE_DIR = REPO / "bot" / "data" / "cache"
OUT_CSV = REPO / "bot" / "data" / "trades_enriched_2026_04_19.csv"
BACKUP_DIR = REPO / "bot" / "data" / "backups"

SYMBOLS = ["BTC", "ETH", "HYPE", "SOL"]

# --------------------------------------------------------------------- cache --

def stitch_cache(symbol: str, timeframe: str) -> pd.DataFrame:
    """Merge all disk cache snapshots for a symbol/tf, dedupe, sort."""
    pattern = str(CACHE_DIR / f"{symbol}_{timeframe}_*d.csv")
    files = sorted(glob.glob(pattern))
    if not files:
        return pd.DataFrame()
    dfs = []
    for f in files:
        try:
            d = pd.read_csv(f)
            if "time" in d.columns and len(d) > 0:
                dfs.append(d)
        except Exception:
            continue
    if not dfs:
        return pd.DataFrame()
    out = (
        pd.concat(dfs, ignore_index=True)
        .drop_duplicates(subset=["time"])
        .sort_values("time")
        .reset_index(drop=True)
    )
    out["time"] = pd.to_datetime(out["time"], utc=True, format="ISO8601")
    return out


def live_fetch(symbol: str, timeframe: str) -> pd.DataFrame:
    """Best-effort live CCXT fetch to extend caches past their latest bar."""
    try:
        sys.path.insert(0, str(REPO / "bot"))
        from data.fetcher import DataFetcher  # noqa: E402
    except Exception as e:
        print(f"  [live_fetch] fetcher import failed: {e}")
        return pd.DataFrame()
    coin_id_map = {
        "BTC": "bitcoin", "ETH": "ethereum",
        "SOL": "solana", "HYPE": "hyperliquid",
    }
    coin_id = coin_id_map.get(symbol)
    if not coin_id:
        return pd.DataFrame()
    try:
        fetcher = DataFetcher()
        df = fetcher.fetch_ohlcv(symbol, coin_id, timeframe)
        if df is None or df.empty:
            return pd.DataFrame()
        if "time" not in df.columns:
            return pd.DataFrame()
        df = df.copy()
        df["time"] = pd.to_datetime(df["time"], utc=True, format="ISO8601")
        return df.sort_values("time").reset_index(drop=True)
    except Exception as e:
        print(f"  [live_fetch] {symbol}/{timeframe} failed: {e}")
        return pd.DataFrame()


def build_dataset(symbol: str, timeframe: str) -> pd.DataFrame:
    cached = stitch_cache(symbol, timeframe)
    live = live_fetch(symbol, timeframe)
    if cached.empty and live.empty:
        return pd.DataFrame()
    if cached.empty:
        return live
    if live.empty:
        return cached
    combined = (
        pd.concat([cached, live], ignore_index=True)
        .drop_duplicates(subset=["time"])
        .sort_values("time")
        .reset_index(drop=True)
    )
    return combined


def resample_6h(df_1h: pd.DataFrame) -> pd.DataFrame:
    if df_1h.empty:
        return df_1h
    d = df_1h.copy().set_index("time")
    agg = d.resample("6h").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    }).dropna().reset_index()
    return agg


# -------------------------------------------------------------- indicators --

def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    prev_c = c.shift(1)
    tr = pd.concat(
        [(h - l).abs(), (h - prev_c).abs(), (l - prev_c).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0.0)
    dn = (-d).clip(lower=0.0)
    up_e = up.ewm(alpha=1 / period, adjust=False).mean()
    dn_e = dn.ewm(alpha=1 / period, adjust=False).mean()
    rs = up_e / dn_e.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    up_move = h.diff()
    dn_move = -l.diff()
    plus_dm = np.where((up_move > dn_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((dn_move > up_move) & (dn_move > 0), dn_move, 0.0)
    tr = pd.concat(
        [(h - l).abs(), (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1
    ).max(axis=1)
    atr_ = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / atr_
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / atr_
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False).mean()


def chop_proxy(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """ATR-to-range proxy: high ATR relative to net price travel = chop."""
    atr_ = atr(df, period)
    net_travel = (df["close"] - df["close"].shift(period)).abs()
    return atr_ / net_travel.replace(0, np.nan)


def classify_regime(df: pd.DataFrame, idx: int) -> str:
    """Simplified 3-class regime at bar `idx`: trend_up / trend_down / range.

    Rule: 20-bar EMA slope + ADX filter. Not a verbatim replica of the bot's
    RegimeClassifier (that reads ML/volatility context we don't have offline)
    but captures directional outlook + trend strength.
    """
    if idx < 25 or idx >= len(df):
        return "unknown"
    close = df["close"].iloc[:idx + 1]
    ema20 = close.ewm(span=20, adjust=False).mean()
    slope = (ema20.iloc[-1] - ema20.iloc[-10]) / max(ema20.iloc[-10], 1e-9)
    adx_series = adx(df.iloc[:idx + 1])
    adx_val = adx_series.iloc[-1] if len(adx_series) else 0.0
    if pd.isna(adx_val) or adx_val < 20:
        return "range"
    if slope > 0.005:
        return "trend_up"
    if slope < -0.005:
        return "trend_down"
    return "range"


# ------------------------------------------------------------ per-trade --

def compute_features_for_trade(
    sym: str,
    entry_ts: pd.Timestamp,
    exit_ts: Optional[pd.Timestamp],
    entry_px: float,
    side: str,
    atr_at_entry_hint: Optional[float],
    data_1h: pd.DataFrame,
    data_6h: pd.DataFrame,
    data_5m: pd.DataFrame,
    btc_1h: Optional[pd.DataFrame] = None,
) -> dict:
    out: dict = {}
    side_sign = 1.0 if side == "LONG" else -1.0
    # --- 1h features ---
    if not data_1h.empty:
        idx_1h = data_1h["time"].searchsorted(entry_ts, side="right") - 1
        idx_1h = max(0, min(idx_1h, len(data_1h) - 1))
        out["src_1h_ts"] = data_1h["time"].iloc[idx_1h]
        atr_series = atr(data_1h)
        rsi_series = rsi(data_1h["close"])
        adx_series = adx(data_1h)
        chop_series = chop_proxy(data_1h)
        out["atr_1h_14"] = float(atr_series.iloc[idx_1h]) if idx_1h < len(atr_series) else np.nan
        out["rsi_1h_14"] = float(rsi_series.iloc[idx_1h]) if idx_1h < len(rsi_series) else np.nan
        out["adx_1h_14"] = float(adx_series.iloc[idx_1h]) if idx_1h < len(adx_series) else np.nan
        out["chop_score_proxy"] = float(chop_series.iloc[idx_1h]) if idx_1h < len(chop_series) else np.nan
        out["atr_pct"] = out["atr_1h_14"] / entry_px if entry_px > 0 and not np.isnan(out["atr_1h_14"]) else np.nan
        # Volume ratio: current bar vs trailing 24 bars
        vol = data_1h["volume"]
        vol_mean24 = vol.rolling(24, min_periods=6).mean()
        out["volume_ratio_1h"] = float(vol.iloc[idx_1h] / vol_mean24.iloc[idx_1h]) if idx_1h < len(vol_mean24) and vol_mean24.iloc[idx_1h] > 0 else np.nan
        # Distance to recent high/low (last 24 bars)
        lookback_lo = max(0, idx_1h - 24)
        window = data_1h.iloc[lookback_lo:idx_1h + 1]
        if len(window) > 0 and entry_px > 0:
            out["distance_to_1h_high_pct"] = (window["high"].max() - entry_px) / entry_px * 100
            out["distance_to_1h_low_pct"] = (entry_px - window["low"].min()) / entry_px * 100
        out["regime_1h"] = classify_regime(data_1h, idx_1h)
    else:
        out["regime_1h"] = "unknown"

    # --- 6h features ---
    if not data_6h.empty:
        idx_6h = data_6h["time"].searchsorted(entry_ts, side="right") - 1
        idx_6h = max(0, min(idx_6h, len(data_6h) - 1))
        rsi_6h = rsi(data_6h["close"])
        out["rsi_6h_14"] = float(rsi_6h.iloc[idx_6h]) if idx_6h < len(rsi_6h) else np.nan
        out["regime_6h"] = classify_regime(data_6h, idx_6h)
    else:
        out["regime_6h"] = "unknown"

    # --- rsi_div_1h_6h_aligned: RSI_1h - RSI_6h, sign-flipped by side ---
    r1h = out.get("rsi_1h_14")
    r6h = out.get("rsi_6h_14")
    if r1h is not None and r6h is not None and not (pd.isna(r1h) or pd.isna(r6h)):
        out["rsi_div_1h_6h_aligned"] = float((r1h - r6h) * side_sign)
    else:
        out["rsi_div_1h_6h_aligned"] = np.nan

    # --- btc_4h_return_signed: BTC 4h log-return, sign-flipped by side on alts ---
    if btc_1h is not None and not btc_1h.empty:
        idx_b = btc_1h["time"].searchsorted(entry_ts, side="right") - 1
        idx_b = max(0, min(idx_b, len(btc_1h) - 1))
        idx_b_past = max(0, idx_b - 4)
        c_now = btc_1h["close"].iloc[idx_b]
        c_past = btc_1h["close"].iloc[idx_b_past]
        if c_now > 0 and c_past > 0:
            btc_ret = math.log(float(c_now) / float(c_past))
            # Align: BTC trade gets raw return * side_sign;
            # alt trades: same (tailwind if BTC up and trade long)
            out["btc_4h_return_signed"] = float(btc_ret * side_sign)
        else:
            out["btc_4h_return_signed"] = np.nan
    else:
        out["btc_4h_return_signed"] = np.nan

    # --- MFE/MAE in R multiples on 5m (falls back to 1h if 5m missing) ---
    atr_ref = atr_at_entry_hint or out.get("atr_1h_14") or 0.0
    if atr_ref and atr_ref > 0 and not data_5m.empty:
        cap = (exit_ts or entry_ts) + pd.Timedelta(hours=12)
        end_ts = min(exit_ts, cap) if exit_ts is not None else cap
        mask = (data_5m["time"] >= entry_ts) & (data_5m["time"] <= end_ts)
        window = data_5m.loc[mask]
        if not window.empty:
            if side == "LONG":
                mfe = (window["high"].max() - entry_px) / atr_ref
                mae = (entry_px - window["low"].min()) / atr_ref
            else:  # SHORT
                mfe = (entry_px - window["low"].min()) / atr_ref
                mae = (window["high"].max() - entry_px) / atr_ref
            out["mfe_R"] = float(mfe)
            out["mae_R"] = float(mae)

    # --- hour bucket ---
    out["hour_bucket_4"] = int(entry_ts.hour // 4)
    return out


# ----------------------------------------------------------------- main --

def load_trades() -> pd.DataFrame:
    df = pd.read_csv(TRADES_CSV)
    df["ts"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    # Parse entry_reasons for SL price + atr hint
    sl_list, atr_hint = [], []
    for r in df["entry_reasons"].fillna("{}"):
        try:
            j = json.loads(r)
        except Exception:
            j = {}
        sl_list.append(j.get("per_signal_sl"))
        atr_hint.append(j.get("per_signal_atr"))
    df["sl_parsed"] = sl_list
    df["atr_hint"] = atr_hint
    # stop_width_pct (derivable)
    def sw(row):
        sl = row["sl_parsed"]
        e = row["entry"]
        if sl is None or e is None or pd.isna(e) or e == 0:
            return np.nan
        try:
            return abs(float(sl) - float(e)) / float(e) * 100.0
        except Exception:
            return np.nan
    df["stop_width_pct"] = df.apply(sw, axis=1)
    return df


def backup_trades():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dst = BACKUP_DIR / f"trades_{stamp}.csv"
    shutil.copy2(TRADES_CSV, dst)
    print(f"Backed up trades.csv -> {dst}")


def main() -> int:
    print("=" * 70)
    print("HISTORICAL TRADE FEATURE BACKFILL")
    print("=" * 70)
    backup_trades()

    trades = load_trades()
    n = len(trades)
    print(f"Loaded {n} trades. Symbols: {trades['symbol'].value_counts().to_dict()}")

    # Pre-build per-symbol OHLCV
    print("\nBuilding per-symbol OHLCV from cache + live CCXT gap-fill…")
    data_bank = {}
    for sym in SYMBOLS:
        d1h = build_dataset(sym, "1h")
        d5m = build_dataset(sym, "5m")
        d6h = build_dataset(sym, "6h")
        if d6h.empty and not d1h.empty:
            d6h = resample_6h(d1h)
        data_bank[sym] = {"1h": d1h, "6h": d6h, "5m": d5m}
        cov = lambda d: f"{len(d)} rows, {d['time'].min()} to {d['time'].max()}" if len(d) else "empty"
        print(f"  {sym}: 1h={cov(d1h)} | 6h={cov(d6h)} | 5m={cov(d5m)}")

    print("\nComputing per-trade features…")
    feat_rows = []
    for i, r in trades.iterrows():
        sym = r["symbol"]
        if sym not in data_bank:
            feat_rows.append({})
            continue
        entry_ts = r["ts"]
        # exit_ts not in trades.csv; use timestamp + ~12h cap (outcome already known)
        exit_ts = None
        try:
            entry_px = float(r["entry"])
            exit_px = float(r["exit"])
        except Exception:
            entry_px, exit_px = np.nan, np.nan
        side = str(r["side"]).upper()
        atr_hint = None
        try:
            atr_hint = float(r["atr_hint"]) if r["atr_hint"] is not None and not pd.isna(r["atr_hint"]) else None
        except Exception:
            atr_hint = None
        btc_1h = data_bank.get("BTC", {}).get("1h", pd.DataFrame())
        feats = compute_features_for_trade(
            sym, entry_ts, exit_ts, entry_px, side, atr_hint,
            data_bank[sym]["1h"], data_bank[sym]["6h"], data_bank[sym]["5m"],
            btc_1h=btc_1h,
        )
        feat_rows.append(feats)

    feat_df = pd.DataFrame(feat_rows)
    # assemble enriched CSV (drop helpers)
    enriched = pd.concat(
        [trades.drop(columns=["sl_parsed", "atr_hint"]).reset_index(drop=True),
         feat_df.reset_index(drop=True)],
        axis=1,
    )
    enriched.to_csv(OUT_CSV, index=False)
    print(f"\nEnriched dataset written: {OUT_CSV}")
    print(f"New columns: {[c for c in feat_df.columns]}")
    nonnull = feat_df.notna().sum()
    print("\nNon-null counts per new feature:")
    for c, v in nonnull.items():
        print(f"  {c}: {v}/{n}")

    # ------------------------------------------- IC study on NEW features --
    print("\n" + "=" * 70)
    print("IC STUDY — new features only")
    print("=" * 70)
    enriched["pnl_num"] = pd.to_numeric(enriched["pnl"], errors="coerce")
    enriched["win"] = (enriched["pnl_num"] > 0).astype(int)

    new_numeric = [
        "atr_1h_14", "rsi_1h_14", "rsi_6h_14", "rsi_div_1h_6h_aligned",
        "adx_1h_14", "chop_score_proxy", "stop_width_pct", "atr_pct",
        "volume_ratio_1h", "distance_to_1h_high_pct", "distance_to_1h_low_pct",
        "mfe_R", "mae_R", "hour_bucket_4", "btc_4h_return_signed",
    ]
    present = [c for c in new_numeric if c in enriched.columns]

    def _ic(x, y):
        df = pd.concat([x, y], axis=1).dropna()
        if len(df) < 10 or df.iloc[:, 0].nunique() < 3:
            return (np.nan, np.nan, np.nan, len(df))
        rho, p = stats.spearmanr(df.iloc[:, 0], df.iloc[:, 1])
        if np.isnan(rho) or abs(rho) >= 0.9999:
            return (rho, np.nan, np.nan, len(df))
        t = rho * math.sqrt(max(len(df) - 2, 1)) / math.sqrt(1 - rho * rho)
        return (float(rho), float(t), float(p), len(df))

    rows = []
    for f in present:
        ic_p, t_p, p_p, n_p = _ic(enriched[f], enriched["pnl_num"])
        ic_w, t_w, p_w, n_w = _ic(enriched[f], enriched["win"])
        rows.append(dict(feature=f, n=n_p, ic_pnl=ic_p, t_pnl=t_p, p_pnl=p_p,
                         ic_win=ic_w, t_win=t_w, p_win=p_w))
    ic_df = pd.DataFrame(rows).sort_values("p_pnl")
    n_tests = max(1, len(ic_df))
    ic_df["p_pnl_bonf"] = (ic_df["p_pnl"] * n_tests).clip(upper=1.0)
    ic_df["p_win_bonf"] = (ic_df["p_win"] * n_tests).clip(upper=1.0)
    ic_df["bonf_pnl"] = ic_df["p_pnl_bonf"] < 0.05
    ic_df["bonf_win"] = ic_df["p_win_bonf"] < 0.05

    print("\nIC table (sorted by p_pnl):")
    print(ic_df[["feature", "n", "ic_pnl", "t_pnl", "p_pnl", "p_pnl_bonf",
                 "ic_win", "p_win_bonf"]].to_string(index=False))

    survivors_pnl = ic_df[ic_df["bonf_pnl"]]["feature"].tolist()
    survivors_win = ic_df[ic_df["bonf_win"]]["feature"].tolist()
    print(f"\nBonferroni survivors (PnL): {survivors_pnl or 'none'}")
    print(f"Bonferroni survivors (Win): {survivors_win or 'none'}")

    # Save IC table beside the enriched CSV for downstream use
    ic_out = REPO / "bot" / "data" / "trades_enriched_ic_2026_04_19.csv"
    ic_df.to_csv(ic_out, index=False)
    print(f"IC table written: {ic_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
