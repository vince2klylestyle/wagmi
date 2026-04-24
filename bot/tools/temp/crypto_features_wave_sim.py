"""
Crypto-features wave IC sim — temp script for CRYPTO_FEATURES_WAVE_2026_04_19.md.

Tests a second wave of candidates beyond the first round
(hour_bucket_4 / btc_4h_return_signed / vote_entropy).

Candidates implemented here (subset — see markdown for why others were skipped):
  - consecutive_same_color_1h    (1h bars)  [computable]
  - consecutive_same_color_5m    (5m bars)  [computable]
  - volume_zscore_24h_1h         (1h vs 24h)[computable — new TF vs round 1]
  - wick_to_body_ratio_1h        (ratio, not wick-fraction)[computable]
  - atr_regime_transition_ratio  (ATR_24h / ATR_30d)[computable]
  - atr_regime_delta_pct         ((ATR_6h - ATR_30d) / ATR_30d)[computable]
  - rsi_divergence_1h_vs_6h      (RSI_14 1h minus RSI_14 6h, sign-aligned)[computable]
  - rsi_1h                       (RSI_14 on 1h, raw)[computable]
  - btc_dominance_proxy_24h      (BTC 24h return minus alt-basket 24h return — "rotation")[computable]
  - cross_exchange_deviation     [UNCOMPUTABLE — only 1 venue cached; skipped]
  - funding_velocity             [UNCOMPUTABLE — history has 12 rows over 3 minutes; skipped]
  - oi_roc                       [UNCOMPUTABLE — same reason; skipped]
  - perp_spot_basis              [UNCOMPUTABLE — no spot cache; skipped]
  - funding_skew_cross_symbol    [UNCOMPUTABLE — same as funding_velocity; skipped]
  - liquidation_clustering       [UNCOMPUTABLE — 4 lines total]

Inputs (read-only):
- bot/data/trades.csv
- bot/data/cache/{SYMBOL}_{tf}_{Nd}.csv
"""
from __future__ import annotations
import sys, json, math
from pathlib import Path
import pandas as pd
import numpy as np
from scipy import stats

ROOT = Path(r"C:\Users\vince\WAGMI PROJECT\WAGMI")
TRADES = ROOT / "bot/data/trades.csv"
CACHE = ROOT / "bot/data/cache"
SYMS = ["BTC", "ETH", "HYPE", "SOL"]


def _load_ohlcv(sym: str, tf: str) -> pd.DataFrame:
    candidates = sorted(CACHE.glob(f"{sym}_{tf}_*d.csv"))
    frames = []
    for p in candidates:
        try:
            frames.append(pd.read_csv(p))
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
    for tf in ["5m", "1h", "6h", "daily"]:
        df = _load_ohlcv(s, tf)
        if not df.empty:
            OHLCV[(s, tf)] = df

print(f"[load] slices: {sorted(OHLCV.keys())}", file=sys.stderr)

# ---------------- trade load ----------------
trades = pd.read_csv(TRADES)
trades["timestamp"] = pd.to_datetime(trades["timestamp"], utc=True)
trades = trades.sort_values("timestamp").reset_index(drop=True)
trades["win"] = (trades["pnl"] > 0).astype(int)
print(f"[load] {len(trades)} trades", file=sys.stderr)


# ---------------- helpers ----------------
def _atr(sl: pd.DataFrame, window: int) -> pd.Series:
    tr = pd.concat([
        sl["high"] - sl["low"],
        (sl["high"] - sl["close"].shift()).abs(),
        (sl["low"] - sl["close"].shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window).mean()


def _rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = (-delta.clip(upper=0)).rolling(window).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


# ---------------- features ----------------

def feat_consec_same_color_1h() -> pd.Series:
    """Sign-aligned streak of consecutive same-direction 1h closes ending at entry.
    Positive = streak aligned with trade side; negative = streak against.
    """
    out = []
    for _, r in trades.iterrows():
        df = OHLCV.get((r["symbol"], "1h"))
        if df is None:
            out.append(np.nan); continue
        end = df["time"].searchsorted(r["timestamp"], side="right")
        sl = df.iloc[max(0, end - 12):end]
        if len(sl) < 2:
            out.append(np.nan); continue
        closes = sl["close"].to_numpy()
        opens = sl["open"].to_numpy()
        last_dir = np.sign(closes[-1] - opens[-1])
        if last_dir == 0:
            out.append(0); continue
        streak = 0
        for i in range(len(sl) - 1, -1, -1):
            d = np.sign(closes[i] - opens[i])
            if d == last_dir:
                streak += 1
            else:
                break
        aligned = 1 if r["side"] == "LONG" else -1
        out.append(int(streak * last_dir * aligned))
    return pd.Series(out, index=trades.index)


def feat_consec_same_color_5m() -> pd.Series:
    out = []
    for _, r in trades.iterrows():
        df = OHLCV.get((r["symbol"], "5m"))
        if df is None:
            out.append(np.nan); continue
        end = df["time"].searchsorted(r["timestamp"], side="right")
        sl = df.iloc[max(0, end - 24):end]
        if len(sl) < 3:
            out.append(np.nan); continue
        closes = sl["close"].to_numpy()
        opens = sl["open"].to_numpy()
        last_dir = np.sign(closes[-1] - opens[-1])
        if last_dir == 0:
            out.append(0); continue
        streak = 0
        for i in range(len(sl) - 1, -1, -1):
            d = np.sign(closes[i] - opens[i])
            if d == last_dir:
                streak += 1
            else:
                break
        aligned = 1 if r["side"] == "LONG" else -1
        out.append(int(streak * last_dir * aligned))
    return pd.Series(out, index=trades.index)


def feat_volume_zscore_24h_1h() -> pd.Series:
    """z-score of last 1h volume vs trailing 24h mean (broader window than round-1)."""
    out = []
    for _, r in trades.iterrows():
        df = OHLCV.get((r["symbol"], "1h"))
        if df is None:
            out.append(np.nan); continue
        end = df["time"].searchsorted(r["timestamp"], side="right")
        sl = df.iloc[max(0, end - 24):end]
        if len(sl) < 12:
            out.append(np.nan); continue
        cur = sl["volume"].iloc[-1]
        mu = sl["volume"].mean(); sd = sl["volume"].std()
        out.append((cur - mu) / sd if sd > 0 else np.nan)
    return pd.Series(out, index=trades.index)


def feat_wick_to_body_1h() -> pd.Series:
    """Mean of |upper_wick + lower_wick| / |body| over trailing 6 1h bars.
    Bigger = more rejection noise. Different from round-1 wick_ratio_1h_6bar which
    used wick/range (bounded 0-1). This is unbounded wick/body ratio.
    """
    out = []
    for _, r in trades.iterrows():
        df = OHLCV.get((r["symbol"], "1h"))
        if df is None:
            out.append(np.nan); continue
        end = df["time"].searchsorted(r["timestamp"], side="right")
        sl = df.iloc[max(0, end - 6):end]
        if len(sl) < 3:
            out.append(np.nan); continue
        upper = sl["high"] - sl[["open", "close"]].max(axis=1)
        lower = sl[["open", "close"]].min(axis=1) - sl["low"]
        body = (sl["close"] - sl["open"]).abs().clip(lower=1e-12)
        r_ = (upper + lower) / body
        out.append(r_.mean())
    return pd.Series(out, index=trades.index)


def feat_atr_regime_transition_ratio() -> pd.Series:
    """ATR(14, 1h) over trailing 24h divided by ATR(14, 1h) over trailing 30d.
    > 1 = expanding regime vs baseline. < 1 = contracting.
    """
    out = []
    for _, r in trades.iterrows():
        df = OHLCV.get((r["symbol"], "1h"))
        if df is None:
            out.append(np.nan); continue
        end = df["time"].searchsorted(r["timestamp"], side="right")
        sl30 = df.iloc[max(0, end - 24*30):end]
        sl24 = df.iloc[max(0, end - 24):end]
        if len(sl30) < 60 or len(sl24) < 12:
            out.append(np.nan); continue
        atr30 = _atr(sl30, 14).dropna()
        atr24 = _atr(sl24, 14).dropna()
        if atr30.empty or atr24.empty or atr30.mean() == 0:
            out.append(np.nan); continue
        out.append(atr24.mean() / atr30.mean())
    return pd.Series(out, index=trades.index)


def feat_atr_regime_delta_pct() -> pd.Series:
    """(ATR_6h - ATR_30d) / ATR_30d. Short-lookback vs baseline deviation."""
    out = []
    for _, r in trades.iterrows():
        df = OHLCV.get((r["symbol"], "1h"))
        if df is None:
            out.append(np.nan); continue
        end = df["time"].searchsorted(r["timestamp"], side="right")
        sl30 = df.iloc[max(0, end - 24*30):end]
        sl6 = df.iloc[max(0, end - 6):end]
        if len(sl30) < 60 or len(sl6) < 4:
            out.append(np.nan); continue
        atr30 = _atr(sl30, 14).dropna()
        # naive ATR over last 6 bars
        tr6 = pd.concat([
            sl6["high"] - sl6["low"],
            (sl6["high"] - sl6["close"].shift()).abs(),
            (sl6["low"] - sl6["close"].shift()).abs(),
        ], axis=1).max(axis=1).dropna()
        if atr30.empty or tr6.empty or atr30.mean() == 0:
            out.append(np.nan); continue
        out.append((tr6.mean() - atr30.mean()) / atr30.mean())
    return pd.Series(out, index=trades.index)


def feat_rsi_1h() -> pd.Series:
    out = []
    for _, r in trades.iterrows():
        df = OHLCV.get((r["symbol"], "1h"))
        if df is None:
            out.append(np.nan); continue
        end = df["time"].searchsorted(r["timestamp"], side="right")
        sl = df.iloc[max(0, end - 30):end]
        if len(sl) < 16:
            out.append(np.nan); continue
        rsi = _rsi(sl["close"], 14).dropna()
        if rsi.empty:
            out.append(np.nan); continue
        val = rsi.iloc[-1]
        # sign-align: for LONG lower RSI = more runway; for SHORT higher RSI = more runway
        # express as "overbought-ness in direction of trade" (higher = more likely fade)
        if r["side"] == "LONG":
            out.append(val)  # 50 neutral; 80 overbought (bad for LONG)
        else:
            out.append(100 - val)  # invert so same interpretation
        # so correlation w/ PnL expected negative (OB = worse entry)
    return pd.Series(out, index=trades.index)


def feat_rsi_divergence_1h_vs_6h() -> pd.Series:
    """RSI(14, 1h) - RSI(14, 6h). Sign-aligned to trade side.
    Positive = shorter TF stretched more than longer TF in trade direction."""
    out = []
    for _, r in trades.iterrows():
        d1 = OHLCV.get((r["symbol"], "1h"))
        d6 = OHLCV.get((r["symbol"], "6h"))
        if d1 is None or d6 is None:
            out.append(np.nan); continue
        e1 = d1["time"].searchsorted(r["timestamp"], side="right")
        e6 = d6["time"].searchsorted(r["timestamp"], side="right")
        sl1 = d1.iloc[max(0, e1 - 30):e1]
        sl6 = d6.iloc[max(0, e6 - 30):e6]
        if len(sl1) < 16 or len(sl6) < 16:
            out.append(np.nan); continue
        r1 = _rsi(sl1["close"], 14).dropna()
        r6 = _rsi(sl6["close"], 14).dropna()
        if r1.empty or r6.empty:
            out.append(np.nan); continue
        div = r1.iloc[-1] - r6.iloc[-1]
        # sign-align
        if r["side"] == "SHORT":
            div = -div
        out.append(div)
    return pd.Series(out, index=trades.index)


def feat_btc_dominance_proxy_24h() -> pd.Series:
    """Rotation proxy: BTC 24h return minus equal-weight alt-basket 24h return.
    Positive = BTC-led, alt-weak. Negative = alt-rotation.
    Sign-aligned to trade side * (asset_type).
    For BTC LONG: alignment with +dominance good. For alt LONG: alignment with -dominance (alt rot) good.
    """
    btc = OHLCV.get(("BTC", "1h"))
    if btc is None:
        return pd.Series([np.nan]*len(trades), index=trades.index)
    out = []
    for _, r in trades.iterrows():
        e_b = btc["time"].searchsorted(r["timestamp"], side="right")
        if e_b < 24:
            out.append(np.nan); continue
        b_ret = math.log(btc["close"].iloc[e_b-1] / btc["close"].iloc[e_b-24])
        alt_rets = []
        for alt in ("ETH", "HYPE", "SOL"):
            df = OHLCV.get((alt, "1h"))
            if df is None:
                continue
            e = df["time"].searchsorted(r["timestamp"], side="right")
            if e < 24:
                continue
            alt_rets.append(math.log(df["close"].iloc[e-1] / df["close"].iloc[e-24]))
        if not alt_rets:
            out.append(np.nan); continue
        dom = b_ret - np.mean(alt_rets)
        # sign-align
        is_btc = (r["symbol"] == "BTC")
        side_long = (r["side"] == "LONG")
        # BTC LONG benefits from +dom, BTC SHORT from -dom; alt LONG from -dom, alt SHORT from +dom
        if is_btc and side_long:
            aligned = dom
        elif is_btc and not side_long:
            aligned = -dom
        elif (not is_btc) and side_long:
            aligned = -dom
        else:
            aligned = dom
        out.append(aligned)
    return pd.Series(out, index=trades.index)


# ---------------- run ----------------
FEATURES = {
    "consec_same_color_1h_signed": (feat_consec_same_color_1h, "cheap", "small"),
    "consec_same_color_5m_signed": (feat_consec_same_color_5m, "cheap", "small"),
    "volume_zscore_24h_1h": (feat_volume_zscore_24h_1h, "cheap", "small"),
    "wick_to_body_ratio_1h": (feat_wick_to_body_1h, "cheap", "small"),
    "atr_regime_transition_ratio": (feat_atr_regime_transition_ratio, "moderate", "small"),
    "atr_regime_delta_pct": (feat_atr_regime_delta_pct, "moderate", "small"),
    "rsi_1h_overbought_aligned": (feat_rsi_1h, "cheap", "small"),
    "rsi_divergence_1h_vs_6h_aligned": (feat_rsi_divergence_1h_vs_6h, "cheap", "small"),
    "btc_dominance_proxy_24h_aligned": (feat_btc_dominance_proxy_24h, "cheap", "small"),
}

results = []
for name, (fn, cost, effort) in FEATURES.items():
    try:
        s = fn().astype(float)
    except Exception as exc:
        results.append((name, 0, 0, None, None, None, None, None, cost, effort, f"ERROR:{exc}"))
        continue
    df = pd.DataFrame({"x": s, "pnl": trades["pnl"], "win": trades["win"]}).dropna()
    n = len(df)
    if n < 20 or df["x"].nunique() < 3:
        results.append((name, n, df["x"].nunique() if n else 0,
                        np.nan, np.nan, np.nan, np.nan, np.nan,
                        cost, effort, "INSUFFICIENT"))
        continue
    rho_pnl, p_pnl = stats.spearmanr(df["x"], df["pnl"])
    rho_win, p_win = stats.spearmanr(df["x"], df["win"])
    t_pnl = rho_pnl * math.sqrt((n - 2) / max(1e-9, 1 - rho_pnl ** 2))
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
                    cost, effort, verdict))

# sort by |IC_pnl|
def _key(r):
    v = r[3]
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return 0
    return -abs(v)

results.sort(key=_key)

print("\n=== IC TABLE (wave 2) ===")
hdr = ("name", "n", "unq", "IC_pnl", "t_pnl", "p_pnl", "IC_win", "p_win", "cost", "effort", "verdict")
print("|".join(hdr))
for r in results:
    name, n, unq, ic, t, p, ic_w, p_w, cost, effort, verdict = r
    fmt = lambda x: f"{x:.3f}" if isinstance(x, float) and not math.isnan(x) else str(x)
    print("|".join([name, str(n), str(unq), fmt(ic), fmt(t), fmt(p),
                    fmt(ic_w), fmt(p_w), cost, effort, verdict]))

OUT_JSON = ROOT / "bot/tools/temp/crypto_features_wave_results.json"
out = []
for r in results:
    name, n, unq, ic, t, p, ic_w, p_w, cost, effort, verdict = r
    out.append({
        "name": name, "n": int(n), "unique": int(unq) if unq else 0,
        "ic_pnl": None if ic is None or (isinstance(ic, float) and math.isnan(ic)) else round(ic, 4),
        "t_pnl": None if t is None or (isinstance(t, float) and math.isnan(t)) else round(t, 3),
        "p_pnl": None if p is None or (isinstance(p, float) and math.isnan(p)) else round(p, 4),
        "ic_win": None if ic_w is None or (isinstance(ic_w, float) and math.isnan(ic_w)) else round(ic_w, 4),
        "p_win": None if p_w is None or (isinstance(p_w, float) and math.isnan(p_w)) else round(p_w, 4),
        "cost": cost, "effort": effort, "verdict": verdict,
    })
OUT_JSON.write_text(json.dumps(out, indent=2))
print(f"\n[write] {OUT_JSON}")
