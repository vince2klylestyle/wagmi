"""
Feature candidate IC sim — temp script for FEATURE_CANDIDATES_2026_04_19.md.

Computes Spearman IC of NEW retroactively-computable features against trade
PnL and Win outcomes from bot/data/trades.csv (n=138).

Inputs (read-only):
- bot/data/trades.csv
- bot/data/cache/{SYMBOL}_{tf}_{Nd}.csv  (open/high/low/close/volume/time)
"""
from __future__ import annotations
import os, sys, json, math
from pathlib import Path
import pandas as pd
import numpy as np
from scipy import stats

ROOT = Path(r"C:\Users\vince\WAGMI PROJECT\WAGMI")
TRADES = ROOT / "bot/data/trades.csv"
CACHE = ROOT / "bot/data/cache"
SYMS = ["BTC", "ETH", "HYPE", "SOL"]

# ---------------- helpers ----------------

def _load_ohlcv(sym: str, tf: str) -> pd.DataFrame:
    """Load longest available cache file for sym/tf, sort by time, dedupe."""
    candidates = sorted(CACHE.glob(f"{sym}_{tf}_*d.csv"))
    frames = []
    for p in candidates:
        try:
            df = pd.read_csv(p)
            frames.append(df)
        except Exception:
            continue
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df["time"] = pd.to_datetime(df["time"], utc=True, format="ISO8601")
    df = df.drop_duplicates(subset=["time"]).sort_values("time").reset_index(drop=True)
    return df

OHLCV: dict[tuple[str, str], pd.DataFrame] = {}
for s in SYMS:
    for tf in ["5m", "1h", "6h", "1d"]:
        df = _load_ohlcv(s, tf)
        if not df.empty:
            OHLCV[(s, tf)] = df

print(f"[load] loaded ohlcv slices: {sorted(OHLCV.keys())}", file=sys.stderr)

# ---------------- trade load ----------------
trades = pd.read_csv(TRADES)
trades["timestamp"] = pd.to_datetime(trades["timestamp"], utc=True)
trades = trades.sort_values("timestamp").reset_index(drop=True)
trades["win"] = (trades["pnl"] > 0).astype(int)
print(f"[load] {len(trades)} trades", file=sys.stderr)

# ---------------- feature constructors ----------------
# Each fn: returns Series aligned to trades.index. NaN allowed; we drop later.

def _bar_at_or_before(df: pd.DataFrame, ts: pd.Timestamp) -> pd.Series | None:
    """Return last OHLCV row whose time <= ts."""
    if df.empty:
        return None
    idx = df["time"].searchsorted(ts, side="right") - 1
    if idx < 0:
        return None
    return df.iloc[idx]

def feat_realized_vol_24h() -> pd.Series:
    """Std of 1h log-returns over trailing 24h."""
    out = []
    for _, r in trades.iterrows():
        df = OHLCV.get((r["symbol"], "1h"))
        if df is None:
            out.append(np.nan); continue
        end = df["time"].searchsorted(r["timestamp"], side="right")
        start = max(0, end - 24)
        sl = df.iloc[start:end]
        if len(sl) < 6:
            out.append(np.nan); continue
        rets = np.log(sl["close"]).diff().dropna()
        out.append(rets.std())
    return pd.Series(out, index=trades.index)

def feat_realized_vol_4h() -> pd.Series:
    """Std of 5m log-returns over trailing 4h."""
    out = []
    for _, r in trades.iterrows():
        df = OHLCV.get((r["symbol"], "5m"))
        if df is None:
            out.append(np.nan); continue
        end = df["time"].searchsorted(r["timestamp"], side="right")
        start = max(0, end - 48)  # 48 5m bars = 4h
        sl = df.iloc[start:end]
        if len(sl) < 12:
            out.append(np.nan); continue
        rets = np.log(sl["close"]).diff().dropna()
        out.append(rets.std())
    return pd.Series(out, index=trades.index)

def feat_vol_of_vol() -> pd.Series:
    """Std of rolling 1h realized vol over trailing 24h."""
    out = []
    for _, r in trades.iterrows():
        df = OHLCV.get((r["symbol"], "1h"))
        if df is None:
            out.append(np.nan); continue
        end = df["time"].searchsorted(r["timestamp"], side="right")
        start = max(0, end - 48)
        sl = df.iloc[start:end].copy()
        if len(sl) < 24:
            out.append(np.nan); continue
        sl["lr"] = np.log(sl["close"]).diff()
        roll = sl["lr"].rolling(6).std().dropna()
        out.append(roll.std())
    return pd.Series(out, index=trades.index)

def feat_atr_percentile() -> pd.Series:
    """Percentile rank of current 1h ATR(14) within trailing 30d."""
    out = []
    for _, r in trades.iterrows():
        df = OHLCV.get((r["symbol"], "1h"))
        if df is None:
            out.append(np.nan); continue
        end = df["time"].searchsorted(r["timestamp"], side="right")
        start = max(0, end - 24*30)
        sl = df.iloc[start:end].copy()
        if len(sl) < 30:
            out.append(np.nan); continue
        tr = pd.concat([
            sl["high"] - sl["low"],
            (sl["high"] - sl["close"].shift()).abs(),
            (sl["low"] - sl["close"].shift()).abs(),
        ], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().dropna()
        if atr.empty:
            out.append(np.nan); continue
        cur = atr.iloc[-1]
        pct = (atr <= cur).mean()
        out.append(pct)
    return pd.Series(out, index=trades.index)

def feat_dist_30d_mean_atr() -> pd.Series:
    """(close - mean(close, 30d)) / ATR(14, 1h)."""
    out = []
    for _, r in trades.iterrows():
        df = OHLCV.get((r["symbol"], "1h"))
        if df is None:
            out.append(np.nan); continue
        end = df["time"].searchsorted(r["timestamp"], side="right")
        start = max(0, end - 24*30)
        sl = df.iloc[start:end].copy()
        if len(sl) < 60:
            out.append(np.nan); continue
        mean30 = sl["close"].mean()
        cur = sl["close"].iloc[-1]
        tr = pd.concat([
            sl["high"] - sl["low"],
            (sl["high"] - sl["close"].shift()).abs(),
            (sl["low"] - sl["close"].shift()).abs(),
        ], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().dropna()
        if atr.empty or atr.iloc[-1] == 0:
            out.append(np.nan); continue
        # signed dist; sign-aligned to side
        dist = (cur - mean30) / atr.iloc[-1]
        if r["side"] == "SHORT":
            dist = -dist
        out.append(dist)
    return pd.Series(out, index=trades.index)

def feat_btc_4h_return() -> pd.Series:
    """BTC log-return over trailing 4h, sign-aligned to trade side."""
    btc = OHLCV.get(("BTC", "1h"))
    if btc is None:
        return pd.Series([np.nan]*len(trades), index=trades.index)
    out = []
    for _, r in trades.iterrows():
        end = btc["time"].searchsorted(r["timestamp"], side="right")
        start = max(0, end - 4)
        sl = btc.iloc[start:end]
        if len(sl) < 2:
            out.append(np.nan); continue
        ret = math.log(sl["close"].iloc[-1] / sl["close"].iloc[0])
        if r["side"] == "SHORT":
            ret = -ret
        out.append(ret)
    return pd.Series(out, index=trades.index)

def feat_btc_correlation_4h() -> pd.Series:
    """Spearman correlation of symbol vs BTC 5m closes over trailing 4h."""
    btc = OHLCV.get(("BTC", "5m"))
    if btc is None:
        return pd.Series([np.nan]*len(trades), index=trades.index)
    out = []
    for _, r in trades.iterrows():
        if r["symbol"] == "BTC":
            out.append(1.0); continue
        df = OHLCV.get((r["symbol"], "5m"))
        if df is None:
            out.append(np.nan); continue
        e_b = btc["time"].searchsorted(r["timestamp"], side="right")
        e_s = df["time"].searchsorted(r["timestamp"], side="right")
        b = btc.iloc[max(0, e_b-48):e_b]
        s = df.iloc[max(0, e_s-48):e_s]
        if len(b) < 12 or len(s) < 12:
            out.append(np.nan); continue
        # align on time
        m = pd.merge_asof(b[["time","close"]].rename(columns={"close":"btc"}),
                          s[["time","close"]].rename(columns={"close":"sym"}),
                          on="time", direction="nearest", tolerance=pd.Timedelta("5min"))
        m = m.dropna()
        if len(m) < 12:
            out.append(np.nan); continue
        rho, _ = stats.spearmanr(m["btc"], m["sym"])
        out.append(rho)
    return pd.Series(out, index=trades.index)

def feat_rel_strength_btc_24h() -> pd.Series:
    """sym 24h return minus BTC 24h return, sign-aligned to side."""
    btc = OHLCV.get(("BTC", "1h"))
    if btc is None:
        return pd.Series([np.nan]*len(trades), index=trades.index)
    out = []
    for _, r in trades.iterrows():
        df = OHLCV.get((r["symbol"], "1h"))
        if df is None:
            out.append(np.nan); continue
        e_b = btc["time"].searchsorted(r["timestamp"], side="right")
        e_s = df["time"].searchsorted(r["timestamp"], side="right")
        if e_b < 24 or e_s < 24:
            out.append(np.nan); continue
        b = btc.iloc[e_b-24:e_b]; s = df.iloc[e_s-24:e_s]
        b_ret = math.log(b["close"].iloc[-1] / b["close"].iloc[0])
        s_ret = math.log(s["close"].iloc[-1] / s["close"].iloc[0])
        rs = s_ret - b_ret
        if r["side"] == "SHORT":
            rs = -rs
        out.append(rs)
    return pd.Series(out, index=trades.index)

def feat_hour_of_day() -> pd.Series:
    return trades["timestamp"].dt.hour.astype(float)

def feat_day_of_week() -> pd.Series:
    return trades["timestamp"].dt.dayofweek.astype(float)

def feat_session_us() -> pd.Series:
    """1 if hour in US session 13-21 UTC."""
    h = trades["timestamp"].dt.hour
    return ((h >= 13) & (h <= 21)).astype(float)

def feat_session_asia() -> pd.Series:
    h = trades["timestamp"].dt.hour
    return ((h >= 0) & (h <= 7)).astype(float)

def feat_weekend() -> pd.Series:
    d = trades["timestamp"].dt.dayofweek
    return (d >= 5).astype(float)

def feat_time_since_prior_trade() -> pd.Series:
    """Minutes since the same-symbol prior trade."""
    out = []
    last: dict[str, pd.Timestamp] = {}
    for _, r in trades.iterrows():
        prev = last.get(r["symbol"])
        if prev is None:
            out.append(np.nan)
        else:
            out.append((r["timestamp"] - prev).total_seconds() / 60.0)
        last[r["symbol"]] = r["timestamp"]
    return pd.Series(out, index=trades.index)

def feat_concurrent_signals() -> pd.Series:
    """Trades opened within +/- 30min of this one across all symbols (excl self)."""
    ts = trades["timestamp"].values
    out = []
    for i, t in enumerate(ts):
        delta = (pd.to_datetime(ts) - pd.Timestamp(t)).total_seconds().abs() / 60.0
        cnt = ((delta <= 30) & (np.arange(len(ts)) != i)).sum()
        out.append(int(cnt))
    return pd.Series(out, index=trades.index)

def feat_consecutive_regime_count() -> pd.Series:
    """How many prior consecutive trades had the same regime label."""
    out = []
    streak = 0; prev = None
    for _, r in trades.iterrows():
        if prev is not None and r["regime"] == prev:
            streak += 1
        else:
            streak = 0
        out.append(streak)
        prev = r["regime"]
    return pd.Series(out, index=trades.index)

def feat_strategies_agree_count() -> pd.Series:
    """num_agree from entry_reasons."""
    out = []
    for _, r in trades.iterrows():
        try:
            d = json.loads(r["entry_reasons"]) if isinstance(r["entry_reasons"], str) else {}
            out.append(d.get("num_agree", np.nan))
        except Exception:
            out.append(np.nan)
    return pd.Series(out, index=trades.index)

def feat_vote_entropy() -> pd.Series:
    """Entropy of individual_confidences distribution (composite of votes)."""
    out = []
    for _, r in trades.iterrows():
        try:
            d = json.loads(r["entry_reasons"]) if isinstance(r["entry_reasons"], str) else {}
            ic = d.get("individual_confidences", {})
            vals = np.array(list(ic.values()), dtype=float)
            if vals.size < 2 or vals.sum() == 0:
                out.append(np.nan); continue
            p = vals / vals.sum()
            h = -(p * np.log(p + 1e-12)).sum()
            out.append(h)
        except Exception:
            out.append(np.nan)
    return pd.Series(out, index=trades.index)

def feat_volume_zscore_4h() -> pd.Series:
    """z-score of last 5m volume vs trailing 4h mean."""
    out = []
    for _, r in trades.iterrows():
        df = OHLCV.get((r["symbol"], "5m"))
        if df is None:
            out.append(np.nan); continue
        end = df["time"].searchsorted(r["timestamp"], side="right")
        start = max(0, end - 48)
        sl = df.iloc[start:end]
        if len(sl) < 24:
            out.append(np.nan); continue
        cur = sl["volume"].iloc[-1]
        mu = sl["volume"].mean(); sd = sl["volume"].std()
        out.append((cur - mu) / sd if sd > 0 else np.nan)
    return pd.Series(out, index=trades.index)

def feat_wick_ratio_1h() -> pd.Series:
    """Mean (wick / range) over trailing 6 1h bars — proxy for noise/rejection."""
    out = []
    for _, r in trades.iterrows():
        df = OHLCV.get((r["symbol"], "1h"))
        if df is None:
            out.append(np.nan); continue
        end = df["time"].searchsorted(r["timestamp"], side="right")
        sl = df.iloc[max(0, end-6):end]
        if len(sl) < 3:
            out.append(np.nan); continue
        rng = (sl["high"] - sl["low"]).replace(0, np.nan)
        body = (sl["close"] - sl["open"]).abs()
        wick = (rng - body) / rng
        out.append(wick.mean())
    return pd.Series(out, index=trades.index)

def feat_consecutive_adverse_5m_post() -> pd.Series:
    """POST-ENTRY: count of consecutive 5m bars after entry that moved against position
    until first favorable bar. Cap at 12 (1h)."""
    out = []
    for _, r in trades.iterrows():
        df = OHLCV.get((r["symbol"], "5m"))
        if df is None:
            out.append(np.nan); continue
        end = df["time"].searchsorted(r["timestamp"], side="right")
        sl = df.iloc[end:end+12]
        if len(sl) < 3:
            out.append(np.nan); continue
        adverse = 0
        sign = 1 if r["side"] == "LONG" else -1
        last_close = r["entry"]
        for _, b in sl.iterrows():
            move = (b["close"] - last_close) * sign
            if move > 0:
                break
            adverse += 1
            last_close = b["close"]
        out.append(adverse)
    return pd.Series(out, index=trades.index)

def feat_time_to_first_favorable_5m() -> pd.Series:
    """POST-ENTRY: bars (5m) until close moves favorable vs entry. Cap 24."""
    out = []
    for _, r in trades.iterrows():
        df = OHLCV.get((r["symbol"], "5m"))
        if df is None:
            out.append(np.nan); continue
        end = df["time"].searchsorted(r["timestamp"], side="right")
        sl = df.iloc[end:end+24]
        if len(sl) < 3:
            out.append(np.nan); continue
        sign = 1 if r["side"] == "LONG" else -1
        for k, (_, b) in enumerate(sl.iterrows(), 1):
            if (b["close"] - r["entry"]) * sign > 0:
                out.append(k); break
        else:
            out.append(len(sl) + 1)
    return pd.Series(out, index=trades.index)

# ---------------- run + IC ----------------
FEATURES = {
    # microstructure / temporal / vol / cross-symbol / composite
    "realized_vol_24h_1h": (feat_realized_vol_24h, "moderate", "small", True),
    "realized_vol_4h_5m": (feat_realized_vol_4h, "moderate", "small", True),
    "vol_of_vol_1h": (feat_vol_of_vol, "moderate", "small", True),
    "atr_percentile_30d": (feat_atr_percentile, "moderate", "small", True),
    "dist_30d_mean_atr_signed": (feat_dist_30d_mean_atr, "moderate", "small", True),
    "btc_4h_return_signed": (feat_btc_4h_return, "cheap", "small", True),
    "btc_corr_4h_5m": (feat_btc_correlation_4h, "expensive", "medium", True),
    "rel_strength_vs_btc_24h": (feat_rel_strength_btc_24h, "cheap", "small", True),
    "hour_of_day": (feat_hour_of_day, "cheap", "small", True),
    "day_of_week": (feat_day_of_week, "cheap", "small", True),
    "session_us": (feat_session_us, "cheap", "small", True),
    "session_asia": (feat_session_asia, "cheap", "small", True),
    "weekend": (feat_weekend, "cheap", "small", True),
    "time_since_prior_trade_min": (feat_time_since_prior_trade, "cheap", "small", True),
    "concurrent_signals_30min": (feat_concurrent_signals, "cheap", "small", True),
    "consecutive_regime_count": (feat_consecutive_regime_count, "cheap", "small", True),
    "vote_entropy": (feat_vote_entropy, "cheap", "small", True),
    "volume_zscore_4h": (feat_volume_zscore_4h, "cheap", "small", True),
    "wick_ratio_1h_6bar": (feat_wick_ratio_1h, "cheap", "small", True),
    # post-entry (exit candidates)
    "consec_adverse_5m_post": (feat_consecutive_adverse_5m_post, "cheap", "small", True),
    "time_to_first_favorable_5m": (feat_time_to_first_favorable_5m, "cheap", "small", True),
}

results = []
for name, (fn, cost, effort, computable) in FEATURES.items():
    try:
        s = fn().astype(float)
    except Exception as exc:
        results.append((name, None, None, None, None, None, None, None, cost, effort,
                        computable, f"ERROR:{exc}"))
        continue
    df = pd.DataFrame({"x": s, "pnl": trades["pnl"], "win": trades["win"]}).dropna()
    n = len(df)
    if n < 20 or df["x"].nunique() < 3:
        results.append((name, n, df["x"].nunique(), np.nan, np.nan, np.nan, np.nan, np.nan,
                        cost, effort, computable, "INSUFFICIENT"))
        continue
    rho_pnl, p_pnl = stats.spearmanr(df["x"], df["pnl"])
    rho_win, p_win = stats.spearmanr(df["x"], df["win"])
    # t-stat for IC
    t_pnl = rho_pnl * math.sqrt((n-2) / max(1e-9, 1 - rho_pnl**2))
    t_win = rho_win * math.sqrt((n-2) / max(1e-9, 1 - rho_win**2))
    abs_ic = abs(rho_pnl)
    if abs_ic >= 0.15 and p_pnl < 0.10:
        verdict = "PROMISING"
    elif abs_ic >= 0.10:
        verdict = "MAYBE"
    elif abs_ic < 0.05:
        verdict = "DEAD"
    else:
        verdict = "WEAK"
    results.append((name, n, df["x"].nunique(), rho_pnl, t_pnl, p_pnl, rho_win, p_win,
                    cost, effort, computable, verdict))

# rank by |IC_pnl|
def _key(r):
    v = r[3]
    return -abs(v) if v is not None and not (isinstance(v, float) and math.isnan(v)) else 0
results.sort(key=_key)

print("\n=== IC TABLE ===")
hdr = ("name", "n", "unq", "IC_pnl", "t_pnl", "p_pnl", "IC_win", "p_win",
       "cost", "effort", "comp", "verdict")
print("|".join(hdr))
for r in results:
    name, n, unq, ic, t, p, ic_w, p_w, cost, effort, comp, verdict = r
    fmt = lambda x: f"{x:.3f}" if isinstance(x, float) and not math.isnan(x) else str(x)
    print("|".join([name, str(n), str(unq), fmt(ic), fmt(t), fmt(p),
                    fmt(ic_w), fmt(p_w), cost, effort, str(comp), verdict]))

# write JSON for downstream md
out = []
for r in results:
    name, n, unq, ic, t, p, ic_w, p_w, cost, effort, comp, verdict = r
    out.append({
        "name": name, "n": int(n) if n else 0, "unique": int(unq) if unq else 0,
        "ic_pnl": None if ic is None or (isinstance(ic, float) and math.isnan(ic)) else round(ic, 4),
        "t_pnl": None if t is None or (isinstance(t, float) and math.isnan(t)) else round(t, 3),
        "p_pnl": None if p is None or (isinstance(p, float) and math.isnan(p)) else round(p, 4),
        "ic_win": None if ic_w is None or (isinstance(ic_w, float) and math.isnan(ic_w)) else round(ic_w, 4),
        "p_win": None if p_w is None or (isinstance(p_w, float) and math.isnan(p_w)) else round(p_w, 4),
        "cost": cost, "effort": effort, "computable": comp, "verdict": verdict,
    })

OUT_JSON = ROOT / "bot/tools/temp/feature_ic_results.json"
OUT_JSON.write_text(json.dumps(out, indent=2))
print(f"\n[write] {OUT_JSON}")
