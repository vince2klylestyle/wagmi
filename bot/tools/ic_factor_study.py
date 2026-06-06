"""
IC Factor Study — institutional-quant rigor.

Computes Information Coefficient (Spearman rank correlation) of each feature
vs trade outcome (PnL + Win indicator), with t-stats, p-values, Bonferroni
correction, rolling IC decay, pairwise redundancy, and 2-way interactions.

NO code changes to bot. Read-only analysis against bot/data/trades.csv.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats

TRADES_CSV = Path(r"C:\Users\vince\WAGMI PROJECT\WAGMI\bot\data\trades.csv")


# ---------- helpers ----------------------------------------------------------
def spearman_ic(x: pd.Series, y: pd.Series) -> tuple[float, float, float, int]:
    """Return (IC, t-stat, p-value, n) for Spearman rank correlation."""
    df = pd.concat([x, y], axis=1).dropna()
    n = len(df)
    if n < 5:
        return (np.nan, np.nan, np.nan, n)
    a, b = df.iloc[:, 0].to_numpy(), df.iloc[:, 1].to_numpy()
    # Skip if constant
    if np.nanstd(a) == 0 or np.nanstd(b) == 0:
        return (0.0, 0.0, 1.0, n)
    try:
        rho, p = stats.spearmanr(a, b)
    except Exception:
        return (np.nan, np.nan, np.nan, n)
    if np.isnan(rho) or abs(rho) >= 0.999999:
        return (rho, np.nan, np.nan, n)
    denom = 1 - rho * rho
    if denom <= 0:
        return (rho, np.nan, np.nan, n)
    t = rho * math.sqrt(max(n - 2, 1)) / math.sqrt(denom)
    return (float(rho), float(t), float(p), n)


def rolling_ic(x: pd.Series, y: pd.Series, window: int = 30) -> list[float]:
    df = pd.concat([x, y], axis=1).dropna().reset_index(drop=True)
    if len(df) < window + 5:
        return []
    out: list[float] = []
    for i in range(window, len(df) + 1):
        sl = df.iloc[i - window : i]
        if sl.iloc[:, 0].nunique() < 2 or sl.iloc[:, 1].nunique() < 2:
            out.append(np.nan)
            continue
        r, _ = stats.spearmanr(sl.iloc[:, 0], sl.iloc[:, 1])
        out.append(float(r) if not np.isnan(r) else np.nan)
    return out


def ic_half_life(rolling: list[float]) -> Optional[int]:
    """Trades from rolling IC peak until |IC| drops below 50% of peak."""
    vals = [v for v in rolling if not (v is None or (isinstance(v, float) and np.isnan(v)))]
    if not vals:
        return None
    abs_vals = [abs(v) for v in vals]
    peak_idx = int(np.argmax(abs_vals))
    peak = abs_vals[peak_idx]
    if peak == 0:
        return None
    threshold = peak * 0.5
    for j in range(peak_idx + 1, len(abs_vals)):
        if abs_vals[j] < threshold:
            return j - peak_idx
    return None  # never decayed


# ---------- load & flatten ---------------------------------------------------
def load_trades() -> pd.DataFrame:
    df = pd.read_csv(TRADES_CSV)
    # Parse entry_reasons JSON -> columns
    parsed = []
    for r in df["entry_reasons"].fillna("{}"):
        try:
            parsed.append(json.loads(r))
        except Exception:
            parsed.append({})
    er = pd.json_normalize(parsed)
    # Drop any er columns that collide with base df columns (prefer base CSV)
    dup_cols = [c for c in er.columns if c in df.columns]
    er = er.drop(columns=dup_cols)
    df = pd.concat([df.reset_index(drop=True), er.reset_index(drop=True)], axis=1)
    # Ensure no duplicate columns remain
    df = df.loc[:, ~df.columns.duplicated()]

    # Outcome
    df["pnl_num"] = pd.to_numeric(df["pnl"], errors="coerce")
    df["win"] = (df["pnl_num"] > 0).astype(int)

    # Time features
    df["ts"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    df["hour"] = df["ts"].dt.hour
    df["dow"] = df["ts"].dt.dayofweek
    df["hour_bucket"] = (df["hour"] // 4).astype("Int64")  # 0..5

    # Prior-trade derived features
    df = df.sort_values("ts").reset_index(drop=True)
    df["prev_win"] = df["win"].shift(1)
    df["mins_since_prev_close"] = (df["ts"] - df["ts"].shift(1)).dt.total_seconds() / 60.0

    # Numeric extractions (coerce)
    numeric_fields = [
        "confidence", "leverage", "num_agree", "win_prob_deflated", "ev_per_dollar",
        "fee_drag_pct", "rr1", "rr_tp1", "rr_tp2", "trend_adjustment", "regime_score",
        "ml_conf_at_entry", "ml_samples_at_entry", "chop_score", "chop_score_smoothed",
        "atr_pct",
    ]
    for c in numeric_fields:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Top-decile flags
    for c in ("confidence", "ev_per_dollar"):
        if c in df.columns:
            q90 = df[c].quantile(0.90)
            df[f"{c}_top_decile"] = (df[c] >= q90).astype(int)

    return df


# ---------- analysis ---------------------------------------------------------
NUMERIC_FEATURES = [
    "confidence", "leverage", "num_agree", "win_prob_deflated", "ev_per_dollar",
    "fee_drag_pct", "rr1", "rr_tp1", "rr_tp2", "trend_adjustment", "regime_score",
    "ml_conf_at_entry", "ml_samples_at_entry", "chop_score", "chop_score_smoothed",
    "atr_pct", "hour", "dow", "hour_bucket", "mins_since_prev_close", "prev_win",
    "confidence_top_decile", "ev_per_dollar_top_decile",
]

CATEGORICAL_FEATURES = [
    "symbol", "side", "strategy", "primary_driver", "regime", "volatility_band",
    "entry_type",
]


def analyze_numeric(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    rows = []
    for f in features:
        if f not in df.columns:
            continue
        ic_pnl, t_pnl, p_pnl, n_pnl = spearman_ic(df[f], df["pnl_num"])
        ic_win, t_win, p_win, n_win = spearman_ic(df[f], df["win"])
        roll = rolling_ic(df[f], df["pnl_num"], window=30)
        half = ic_half_life(roll)
        sign_flips = 0
        if len(roll) >= 2:
            rs = [r for r in roll if not np.isnan(r)]
            for i in range(1, len(rs)):
                if rs[i - 1] * rs[i] < 0:
                    sign_flips += 1
        rows.append(dict(
            feature=f, n=n_pnl,
            ic_pnl=ic_pnl, t_pnl=t_pnl, p_pnl=p_pnl,
            ic_win=ic_win, t_win=t_win, p_win=p_win,
            roll_n=len(roll), roll_first=(roll[0] if roll else np.nan),
            roll_last=(roll[-1] if roll else np.nan),
            roll_peak=(max(roll, key=abs) if roll else np.nan),
            half_life=half, sign_flips=sign_flips,
        ))
    return pd.DataFrame(rows)


def analyze_categorical(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    rows = []
    for f in features:
        if f not in df.columns:
            continue
        grp = df.groupby(f, dropna=True)["pnl_num"].agg(["count", "mean", "sum"]).reset_index()
        grp = grp.rename(columns={"count": "n", "mean": "mean_pnl", "sum": "total_pnl"})
        # ANOVA-ish: Kruskal–Wallis on pnl across levels
        groups = [g["pnl_num"].dropna().values for _, g in df.groupby(f, dropna=True)]
        groups = [g for g in groups if len(g) >= 3]
        if len(groups) >= 2:
            try:
                h, pval = stats.kruskal(*groups)
            except Exception:
                h, pval = np.nan, np.nan
        else:
            h, pval = np.nan, np.nan
        # Win rate per level
        wr = df.groupby(f)["win"].mean().reset_index().rename(columns={"win": "win_rate"})
        grp = grp.merge(wr, on=f, how="left")
        rows.append(dict(
            feature=f, levels=len(grp), kruskal_H=h, kruskal_p=pval,
            detail=grp.to_dict(orient="records"),
        ))
    return pd.DataFrame(rows)


def pairwise_correlations(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    cols = [c for c in features if c in df.columns]
    sub = df[cols].apply(pd.to_numeric, errors="coerce")
    return sub.corr(method="spearman")


def interaction_ic(df: pd.DataFrame, f1: str, f2: str) -> tuple[float, float, float, int]:
    if f1 not in df.columns or f2 not in df.columns:
        return (np.nan, np.nan, np.nan, 0)
    # rank-product interaction
    a = pd.to_numeric(df[f1], errors="coerce").rank()
    b = pd.to_numeric(df[f2], errors="coerce").rank()
    prod = a * b
    return spearman_ic(prod, df["pnl_num"])


# ---------- main -------------------------------------------------------------
def main() -> int:
    df = load_trades()
    n_total = len(df)

    num = analyze_numeric(df, NUMERIC_FEATURES)
    cat = analyze_categorical(df, CATEGORICAL_FEATURES)

    # Bonferroni correction across all tested features (numeric+categorical)
    n_tests = len(num) + len(cat)
    num["p_pnl_bonf"] = (num["p_pnl"] * n_tests).clip(upper=1.0)
    num["p_win_bonf"] = (num["p_win"] * n_tests).clip(upper=1.0)
    num["survives_bonf_pnl"] = num["p_pnl_bonf"] < 0.05
    num["survives_bonf_win"] = num["p_win_bonf"] < 0.05
    # FDR (Benjamini-Hochberg) on p_pnl
    ps = num["p_pnl"].fillna(1.0).values
    order = np.argsort(ps)
    ranks = np.empty_like(order); ranks[order] = np.arange(1, len(ps) + 1)
    m = len(ps)
    fdr = ps * m / ranks
    num["p_pnl_fdr"] = np.minimum.accumulate(np.sort(fdr)[::-1])[::-1][np.argsort(order)]
    num["survives_fdr_pnl"] = num["p_pnl_fdr"] < 0.10

    # Top 10 by |IC on PnL| that survive Bonferroni (fallback to raw-p if none)
    num_sorted = num.reindex(num["ic_pnl"].abs().sort_values(ascending=False).index)
    survivors_bonf = num_sorted[num_sorted["survives_bonf_pnl"]].head(10)
    survivors_raw  = num_sorted[num_sorted["p_pnl"] < 0.05].head(10)
    top10_bonf = survivors_bonf["feature"].tolist()
    top10_raw  = survivors_raw["feature"].tolist()

    # Pairwise correlations
    top_for_corr = top10_bonf if len(top10_bonf) >= 2 else top10_raw if len(top10_raw) >= 2 else num_sorted.head(10)["feature"].tolist()
    corr_top = pairwise_correlations(df, top_for_corr)

    # Interactions: top 3 features (raw p<0.05) × all others; top 5 by abs IC
    seed_feats = top10_raw[:3] if len(top10_raw) >= 3 else num_sorted.head(3)["feature"].tolist()
    interactions = []
    others = [f for f in NUMERIC_FEATURES if f in df.columns]
    for i, f1 in enumerate(seed_feats):
        for f2 in others:
            if f1 == f2:
                continue
            ic, t, p, n = interaction_ic(df, f1, f2)
            interactions.append(dict(f1=f1, f2=f2, ic=ic, t=t, p=p, n=n))
    inter_df = pd.DataFrame(interactions)
    inter_df["abs_ic"] = inter_df["ic"].abs()
    inter_df = inter_df.sort_values("abs_ic", ascending=False).head(10)

    # Meta-IC: does win_prob_deflated predict outcome as well as best features?
    wp_ic_pnl = num.set_index("feature").loc["win_prob_deflated", "ic_pnl"] if "win_prob_deflated" in num["feature"].values else np.nan
    wp_t_pnl  = num.set_index("feature").loc["win_prob_deflated", "t_pnl"]  if "win_prob_deflated" in num["feature"].values else np.nan
    wp_ic_win = num.set_index("feature").loc["win_prob_deflated", "ic_win"] if "win_prob_deflated" in num["feature"].values else np.nan

    # Write report
    out_path = Path(r"C:\Users\vince\WAGMI PROJECT\WAGMI\bot\data\sessions\IC_FACTOR_STUDY_2026_04_19.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    w = lines.append

    w("# IC Factor Study — 2026-04-19")
    w("")
    w("**Data:** `bot/data/trades.csv` — n = {n} closed trades.  ".format(n=n_total))
    w("**Outcome measures:** PnL (continuous) and Win (binary, pnl>0).  ")
    w("**Method:** Spearman rank correlation (IC) → t-stat = IC·√(n-2)/√(1-IC²) → two-sided p-value.  ")
    w(f"**Multiple-comparison correction:** Bonferroni at n_tests = {n_tests} (numeric + categorical).  ")
    w("**FDR:** Benjamini–Hochberg at q=0.10 also reported for numeric features.  ")
    w("**Rolling IC:** 30-trade window over PnL; half-life = trades from peak until |IC| < 0.5·peak.  ")
    w("")
    w(f"> **Small-sample caveat.** n={n_total} is borderline. A feature needs |IC| ≥ ~0.17 just to clear raw p<0.05 two-sided, and ~0.28 to survive Bonferroni across {n_tests} tests. Treat IC<0.15 as statistically indistinguishable from noise at this sample size. Rolling stability matters as much as point IC.")
    w("")

    # Numeric IC table
    w("## 1. Numeric feature IC table (sorted by |IC_pnl|)")
    w("")
    w("| Feature | n | IC_pnl | t_pnl | p_pnl | p_Bonf | FDR | IC_win | t_win | p_win | Roll peak | Half-life | Sign flips |")
    w("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in num_sorted.iterrows():
        def fmt(x, nd=4):
            try:
                if pd.isna(x): return "—"
                return f"{x:.{nd}f}"
            except Exception:
                return str(x)
        hl = r["half_life"] if r["half_life"] is not None else "—"
        w(f"| {r['feature']} | {int(r['n'])} | {fmt(r['ic_pnl'],3)} | {fmt(r['t_pnl'],2)} | {fmt(r['p_pnl'])} | {fmt(r['p_pnl_bonf'])} | {'Y' if r['survives_fdr_pnl'] else 'n'} | {fmt(r['ic_win'],3)} | {fmt(r['t_win'],2)} | {fmt(r['p_win'])} | {fmt(r['roll_peak'],3)} | {hl} | {int(r['sign_flips'])} |")
    w("")

    # Categorical IC table
    w("## 2. Categorical feature group test (Kruskal–Wallis on PnL)")
    w("")
    w("| Feature | Levels | H | p | Top level (by mean_pnl) | Worst level |")
    w("|---|---:|---:|---:|---|---|")
    for _, r in cat.iterrows():
        detail = pd.DataFrame(r["detail"])
        if detail.empty:
            continue
        d = detail.sort_values("mean_pnl", ascending=False)
        best = d.iloc[0]
        worst = d.iloc[-1]
        def fmt(x, nd=4):
            try:
                if pd.isna(x): return "—"
                return f"{x:.{nd}f}"
            except Exception:
                return str(x)
        best_txt = f"{best[r['feature']]} (n={int(best['n'])}, mean={fmt(best['mean_pnl'],2)}, WR={fmt(best['win_rate'],2)})"
        worst_txt = f"{worst[r['feature']]} (n={int(worst['n'])}, mean={fmt(worst['mean_pnl'],2)}, WR={fmt(worst['win_rate'],2)})"
        w(f"| {r['feature']} | {int(r['levels'])} | {fmt(r['kruskal_H'],2)} | {fmt(r['kruskal_p'])} | {best_txt} | {worst_txt} |")
    w("")
    # Detail blocks for each categorical
    w("### Categorical breakdowns (mean PnL, WR per level)")
    w("")
    for _, r in cat.iterrows():
        detail = pd.DataFrame(r["detail"])
        if detail.empty:
            continue
        w(f"**{r['feature']}** (H={r['kruskal_H']:.2f}, p={r['kruskal_p']:.4f})")
        w("")
        w("| level | n | mean_pnl | total_pnl | win_rate |")
        w("|---|---:|---:|---:|---:|")
        for _, d in detail.sort_values("mean_pnl", ascending=False).iterrows():
            w(f"| {d[r['feature']]} | {int(d['n'])} | {d['mean_pnl']:.3f} | {d['total_pnl']:.2f} | {d['win_rate']:.3f} |")
        w("")

    # Survivors
    w("## 3. Survivors — Bonferroni and FDR")
    w("")
    if len(survivors_bonf):
        w(f"**Bonferroni survivors (p_Bonf < 0.05):** {', '.join(top10_bonf) if top10_bonf else 'none'}")
    else:
        w(f"**Bonferroni survivors:** none. At n={n_total} and {n_tests} tests, Bonferroni is brutal — no feature cleared it.")
    fdr_survivors = num_sorted[num_sorted["survives_fdr_pnl"]]["feature"].tolist()
    w(f"**FDR (BH, q=0.10) survivors:** {', '.join(fdr_survivors) if fdr_survivors else 'none'}")
    raw_survivors = num_sorted[num_sorted['p_pnl'] < 0.05]['feature'].tolist()
    w(f"**Raw p < 0.05 (uncorrected — treat skeptically):** {', '.join(raw_survivors) if raw_survivors else 'none'}")
    w("")

    # Top 10 pairwise correlations
    w("## 4. Redundancy audit — pairwise Spearman among top features")
    w("")
    if corr_top is not None and not corr_top.empty:
        cols = list(corr_top.columns)
        w("| " + " | ".join(["feature"] + cols) + " |")
        w("|" + "|".join(["---"] * (len(cols) + 1)) + "|")
        for idx in cols:
            row_vals = [idx] + [f"{corr_top.loc[idx, c]:.2f}" if not pd.isna(corr_top.loc[idx, c]) else "—" for c in cols]
            w("| " + " | ".join(row_vals) + " |")
        w("")
        # flag |r|>0.8
        flags = []
        for i, c1 in enumerate(cols):
            for c2 in cols[i+1:]:
                v = corr_top.loc[c1, c2]
                if pd.notna(v) and abs(v) > 0.8:
                    flags.append(f"- `{c1}` ↔ `{c2}`: ρ = {v:.2f} — REDUNDANT")
        if flags:
            w("**Redundant pairs (|ρ|>0.8):**")
            for f in flags:
                w(f)
        else:
            w("**No pair with |ρ|>0.8 — features carry mostly independent signal.**")
        w("")
    else:
        w("_Not enough surviving features to compute pairwise correlation matrix._")
        w("")

    # Interactions
    w("## 5. Top 2-way interactions (rank-product IC vs PnL)")
    w("")
    w("Seed features: " + (", ".join(seed_feats) if seed_feats else "none"))
    w("")
    w("| f1 × f2 | IC | t | p | n |")
    w("|---|---:|---:|---:|---:|")
    for _, r in inter_df.head(5).iterrows():
        def fmt(x, nd=4):
            try:
                if pd.isna(x): return "—"
                return f"{x:.{nd}f}"
            except Exception:
                return str(x)
        w(f"| {r['f1']} × {r['f2']} | {fmt(r['ic'],3)} | {fmt(r['t'],2)} | {fmt(r['p'])} | {int(r['n'])} |")
    w("")

    # Meta-IC for win_prob_deflated
    w("## 6. Meta-IC — is `win_prob_deflated` actually calibrated?")
    w("")
    w(f"- IC(win_prob_deflated, PnL) = {wp_ic_pnl:.3f}, t = {wp_t_pnl:.2f}")
    w(f"- IC(win_prob_deflated, Win) = {wp_ic_win:.3f}")
    best_ic = num_sorted.iloc[0]
    w(f"- Best feature IC(·, PnL) = {best_ic['ic_pnl']:.3f} ({best_ic['feature']})")
    if pd.notna(wp_ic_pnl) and pd.notna(best_ic['ic_pnl']) and abs(wp_ic_pnl) < 0.5 * abs(best_ic['ic_pnl']):
        w(f"- **Verdict:** `win_prob_deflated` is under-performing — its IC is less than half the best single feature. The calibration is **not capturing what actually predicts outcome** in this sample.")
    elif pd.notna(wp_ic_pnl) and abs(wp_ic_pnl) < 0.10:
        w("- **Verdict:** `win_prob_deflated` IC ≈ 0 on this sample. It is currently a **noise signal** — either mis-calibrated, or the sample is too small/regime-shifted to score it.")
    else:
        w("- **Verdict:** `win_prob_deflated` carries meaningful rank signal relative to other features.")
    w("")

    # Rolling IC descriptions for top survivors
    w("## 7. Rolling IC decay (30-trade window) — top 5 by |IC_pnl|")
    w("")
    for _, r in num_sorted.head(5).iterrows():
        roll = rolling_ic(df[r["feature"]], df["pnl_num"], window=30)
        if not roll:
            w(f"**{r['feature']}** — insufficient non-null samples for rolling window.")
            w("")
            continue
        peak = max(roll, key=lambda v: abs(v) if not np.isnan(v) else -1)
        first = roll[0]
        last = roll[-1]
        hl = ic_half_life(roll)
        direction = "decaying" if abs(last) < abs(peak) * 0.5 else ("stable" if abs(last) > abs(peak) * 0.8 else "softening")
        # simple ascii sparkline
        spark_chars = "▁▂▃▄▅▆▇█"
        rr = [v for v in roll if not np.isnan(v)]
        if rr:
            lo, hi = min(rr), max(rr)
            rng = hi - lo if hi > lo else 1.0
            spark = "".join(spark_chars[min(7, max(0, int((v - lo) / rng * 7)))] if not np.isnan(v) else " " for v in roll)
        else:
            spark = ""
        w(f"**{r['feature']}** — peak={peak:.3f}, first={first:.3f}, last={last:.3f}, half-life={hl if hl is not None else '∞'}, status={direction}")
        w("")
        w("```")
        w(spark)
        w("```")
        w("")

    # Practitioner summary
    w("## 8. Practitioner summary")
    w("")
    # True alpha = survives Bonferroni OR FDR, with low sign-flips
    alpha_df = num_sorted[(num_sorted["survives_bonf_pnl"]) | (num_sorted["survives_fdr_pnl"])].copy()
    if alpha_df.empty:
        # fallback: largest |IC| with p<0.05 and few sign flips
        alpha_df = num_sorted[(num_sorted["p_pnl"] < 0.05) & (num_sorted["sign_flips"] <= 2)].head(3)
    alpha_df = alpha_df.head(3)

    w("### True alpha (top 3 by rigor)")
    w("")
    if alpha_df.empty:
        w(f"_At n={n_total} no numeric feature survives Bonferroni._ Reporting the 3 features with the largest |IC_pnl| **that also clear raw p<0.05**, understanding these are hypotheses requiring validation on more trades:")
        w("")
        fallback = num_sorted[num_sorted["p_pnl"] < 0.05].head(3)
        for _, r in fallback.iterrows():
            w(f"- **`{r['feature']}`** — IC_pnl={r['ic_pnl']:.3f}, t={r['t_pnl']:.2f}, p={r['p_pnl']:.4f}, p_Bonf={r['p_pnl_bonf']:.3f}, sign_flips={int(r['sign_flips'])}")
    else:
        for _, r in alpha_df.iterrows():
            w(f"- **`{r['feature']}`** — IC_pnl={r['ic_pnl']:.3f}, t={r['t_pnl']:.2f}, p_Bonf={r['p_pnl_bonf']:.3f}, FDR={'pass' if r['survives_fdr_pnl'] else 'fail'}")
    w("")

    # Noise
    noise = num_sorted[(num_sorted["ic_pnl"].abs() < 0.08) & (num_sorted["p_pnl"] > 0.25)].head(8)
    w("### Noise features (IC indistinguishable from 0)")
    w("")
    for _, r in noise.iterrows():
        w(f"- `{r['feature']}` — IC_pnl={r['ic_pnl']:.3f}, p={r['p_pnl']:.3f}")
    w("")

    # Decayed: high peak, low last, large sign flips
    decayed = num_sorted[
        (num_sorted["roll_peak"].abs() > 0.20)
        & (num_sorted["roll_last"].abs() < num_sorted["roll_peak"].abs() * 0.5)
    ].head(5)
    w("### Decayed features (had IC, now fading — watch, don't bet)")
    w("")
    if decayed.empty:
        w("_None detected with current window — possibly because n is barely larger than the window itself._")
    else:
        for _, r in decayed.iterrows():
            w(f"- `{r['feature']}` — peak={r['roll_peak']:.3f}, last={r['roll_last']:.3f}, sign_flips={int(r['sign_flips'])}, half-life={r['half_life'] if r['half_life'] is not None else '∞'}")
    w("")

    # Meta-IC verdict summary
    w("### Is `win_prob_deflated` doing its job?")
    w("")
    w(f"- IC({{win_prob_deflated}}, PnL) = {wp_ic_pnl:.3f} vs best single-feature IC = {best_ic['ic_pnl']:.3f} (`{best_ic['feature']}`).")
    if pd.notna(wp_ic_pnl) and pd.notna(best_ic['ic_pnl']):
        ratio = abs(wp_ic_pnl) / max(abs(best_ic['ic_pnl']), 1e-6)
        w(f"- The bot's composite probability captures {ratio*100:.0f}% of the rank-predictive strength of the single best feature. If ratio < 50%, the calibration is leaking alpha by blending signal with noise.")
    w("")

    # Actionable proposals
    w("## 9. Proposed trading rules (contingent on survival)")
    w("")
    w("> No code changes are made here. These are hypotheses that require either more trades or a walk-forward backtest before wiring in.")
    w("")
    if not alpha_df.empty or (len(raw_survivors) > 0):
        target = alpha_df if not alpha_df.empty else num_sorted[num_sorted['p_pnl'] < 0.05].head(3)
        for _, r in target.iterrows():
            feat = r['feature']
            sign = "positive" if r['ic_pnl'] > 0 else "negative"
            direction = "above" if r['ic_pnl'] > 0 else "below"
            try:
                thr = df[feat].quantile(0.7 if r['ic_pnl'] > 0 else 0.3)
                w(f"- **Gate on `{feat}`** ({sign} IC, {r['ic_pnl']:.3f}): require `{feat}` {direction} {thr:.3f} (70th/30th percentile) before sizing up. Back-test on a rolling 30-trade OOS window before shipping.")
            except Exception:
                pass
    else:
        w("- No feature is reliably differentiated from noise. **Do not add new gates.** Accumulate trades (target n ≥ 250) and re-run IC study. At current n, adding gates has a high false-positive risk that will over-fit the sample.")
    w("")

    # Footer
    w("---")
    w("")
    w(f"_Generated from n={n_total} trades in `bot/data/trades.csv`. Methodology: Spearman IC + t-test + Bonferroni + BH-FDR + 30-trade rolling. Rank-product used for interactions. Kruskal–Wallis used for categorical group tests. At this sample size treat all findings as hypotheses, not laws._")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written: {out_path}")

    # Print quick-read summary to stdout for the caller
    print("\n=== QUICK SUMMARY ===")
    print(f"n = {n_total}, n_tests (Bonferroni) = {n_tests}")
    print("\nTop 5 by |IC_pnl|:")
    print(num_sorted.head(5)[["feature", "n", "ic_pnl", "t_pnl", "p_pnl", "p_pnl_bonf", "survives_bonf_pnl", "survives_fdr_pnl"]].to_string(index=False))
    print("\nBonferroni survivors:", survivors_bonf["feature"].tolist())
    print("FDR survivors:", fdr_survivors)
    print("Raw p<0.05:", raw_survivors)
    print(f"\nwin_prob_deflated IC_pnl = {wp_ic_pnl:.3f}, IC_win = {wp_ic_win:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
