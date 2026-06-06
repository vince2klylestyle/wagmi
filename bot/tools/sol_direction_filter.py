"""SOL direction filter research.

Extract SOL trades, compare winners vs losers across features, find best filter.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

DATA = Path("C:/Users/vince/WAGMI PROJECT/WAGMI/bot/data/trades_enriched_2026_04_19.csv")


def wilson_ci(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


def cohen_d(a: pd.Series, b: pd.Series) -> float:
    a = a.dropna().astype(float)
    b = b.dropna().astype(float)
    if len(a) < 2 or len(b) < 2:
        return 0.0
    pooled = math.sqrt(((len(a) - 1) * a.var() + (len(b) - 1) * b.var()) / (len(a) + len(b) - 2))
    if pooled == 0:
        return 0.0
    return (a.mean() - b.mean()) / pooled


def extract_reason_json(row: str) -> dict:
    try:
        return json.loads(row) if isinstance(row, str) else {}
    except Exception:
        return {}


def main() -> None:
    df = pd.read_csv(DATA)
    sol = df[df["symbol"] == "SOL"].copy().reset_index(drop=True)
    print(f"Total SOL trades: {len(sol)}")

    # Parse entry_reasons JSON for n_agree, strategies_agree
    reasons = sol["entry_reasons"].apply(extract_reason_json)
    sol["n_agree"] = reasons.apply(lambda d: d.get("num_agree", np.nan))
    sol["strategies_agree"] = reasons.apply(lambda d: tuple(sorted(d.get("strategies_agree", []))))
    sol["rr1"] = reasons.apply(lambda d: d.get("rr1", np.nan))

    sol["win"] = sol["pnl"] > 0
    sol["ts_dt"] = pd.to_datetime(sol["timestamp"], utc=True, errors="coerce")
    sol["hour"] = sol["ts_dt"].dt.hour

    winners = sol[sol["win"]]
    losers = sol[~sol["win"]]
    n_w, n_l = len(winners), len(losers)
    wr = n_w / len(sol) if len(sol) else 0
    lo, hi = wilson_ci(n_w, len(sol))
    print(f"Baseline WR: {wr:.1%} ({n_w}/{len(sol)})  Wilson95: [{lo:.1%}, {hi:.1%}]")
    print(f"Winners: {n_w}   Losers: {n_l}")
    print(f"Total PnL: ${sol['pnl'].sum():.2f}")
    print(f"Avg win: ${winners['pnl'].mean():.2f}   Avg loss: ${losers['pnl'].mean():.2f}")

    # ======================== FEATURE AUDIT ========================
    num_features = [
        "btc_4h_return_signed", "rsi_1h_14", "rsi_6h_14", "rsi_div_1h_6h_aligned",
        "adx_1h_14", "chop_score_proxy", "atr_pct", "volume_ratio_1h",
        "distance_to_1h_high_pct", "distance_to_1h_low_pct",
        "confidence", "leverage", "n_agree", "rr1",
    ]
    rows = []
    for f in num_features:
        if f not in sol.columns:
            continue
        a = winners[f].dropna().astype(float)
        b = losers[f].dropna().astype(float)
        if len(a) < 3 or len(b) < 3:
            continue
        t, p = stats.ttest_ind(a, b, equal_var=False)
        d = cohen_d(a, b)
        rows.append({
            "feature": f, "mean_win": a.mean(), "mean_loss": b.mean(),
            "n_win": len(a), "n_loss": len(b), "t": t, "p": p, "cohen_d": d,
        })
    feat_df = pd.DataFrame(rows).sort_values("p")
    print("\n=== NUMERIC FEATURE T-TESTS ===")
    print(feat_df.to_string(index=False))

    # Categorical
    print("\n=== CATEGORICAL: side ===")
    for side in sol["side"].dropna().unique():
        sub = sol[sol["side"] == side]
        w = (sub["pnl"] > 0).sum()
        lo_, hi_ = wilson_ci(w, len(sub))
        print(f"  {side:6s}  n={len(sub):3d}  WR={w/len(sub):.1%}  CI=[{lo_:.1%},{hi_:.1%}]  PnL=${sub['pnl'].sum():.2f}")

    print("\n=== CATEGORICAL: regime_1h ===")
    for regime in sol["regime_1h"].dropna().unique():
        sub = sol[sol["regime_1h"] == regime]
        w = (sub["pnl"] > 0).sum()
        lo_, hi_ = wilson_ci(w, len(sub))
        print(f"  {regime:15s}  n={len(sub):3d}  WR={w/len(sub):.1%}  CI=[{lo_:.1%},{hi_:.1%}]  PnL=${sub['pnl'].sum():.2f}")

    print("\n=== CATEGORICAL: regime_6h ===")
    for regime in sol["regime_6h"].dropna().unique():
        sub = sol[sol["regime_6h"] == regime]
        w = (sub["pnl"] > 0).sum()
        lo_, hi_ = wilson_ci(w, len(sub))
        print(f"  {regime:15s}  n={len(sub):3d}  WR={w/len(sub):.1%}  CI=[{lo_:.1%},{hi_:.1%}]  PnL=${sub['pnl'].sum():.2f}")

    print("\n=== CATEGORICAL: n_agree ===")
    for n in sorted(sol["n_agree"].dropna().unique()):
        sub = sol[sol["n_agree"] == n]
        w = (sub["pnl"] > 0).sum()
        lo_, hi_ = wilson_ci(w, len(sub))
        print(f"  n_agree={int(n)}  n={len(sub):3d}  WR={w/len(sub):.1%}  CI=[{lo_:.1%},{hi_:.1%}]  PnL=${sub['pnl'].sum():.2f}")

    print("\n=== CATEGORICAL: strategies_agree ===")
    sa = sol["strategies_agree"].value_counts().head(10)
    for strategies, count in sa.items():
        sub = sol[sol["strategies_agree"] == strategies]
        w = (sub["pnl"] > 0).sum()
        lo_, hi_ = wilson_ci(w, len(sub))
        print(f"  {str(strategies)[:60]:60s}  n={len(sub):3d}  WR={w/len(sub):.1%}  PnL=${sub['pnl'].sum():.2f}")

    # BTC alignment (most important feature per note)
    print("\n=== BTC 4H DIRECTIONAL ALIGNMENT ===")
    # For LONG: aligned means btc_4h_return_signed > 0; For SHORT: < 0
    sol["btc_aligned"] = np.where(
        sol["side"] == "LONG", sol["btc_4h_return_signed"] > 0,
        sol["btc_4h_return_signed"] < 0
    )
    for aligned in [True, False]:
        sub = sol[sol["btc_aligned"] == aligned]
        w = (sub["pnl"] > 0).sum()
        lo_, hi_ = wilson_ci(w, len(sub))
        print(f"  btc_aligned={aligned}  n={len(sub):3d}  WR={w/len(sub):.1%}  CI=[{lo_:.1%},{hi_:.1%}]  PnL=${sub['pnl'].sum():.2f}")

    # Side x btc_aligned
    print("\n=== SIDE x BTC_ALIGNED ===")
    for side in ["LONG", "SHORT"]:
        for aligned in [True, False]:
            sub = sol[(sol["side"] == side) & (sol["btc_aligned"] == aligned)]
            if len(sub) == 0:
                continue
            w = (sub["pnl"] > 0).sum()
            lo_, hi_ = wilson_ci(w, len(sub))
            print(f"  {side} x aligned={aligned}  n={len(sub):3d}  WR={w/len(sub):.1%}  CI=[{lo_:.1%},{hi_:.1%}]  PnL=${sub['pnl'].sum():.2f}")

    # Hour of day
    print("\n=== HOUR OF DAY (4h buckets) ===")
    for b in sorted(sol["hour_bucket_4"].dropna().unique()):
        sub = sol[sol["hour_bucket_4"] == b]
        w = (sub["pnl"] > 0).sum()
        lo_, hi_ = wilson_ci(w, len(sub))
        print(f"  bucket={int(b)}  n={len(sub):3d}  WR={w/len(sub):.1%}  PnL=${sub['pnl'].sum():.2f}")

    # ======================== BEST SINGLE FILTER ========================
    print("\n\n============== BEST SINGLE FILTERS ==============")
    candidates = []

    def test_filter(name: str, mask: pd.Series) -> dict:
        sub = sol[mask]
        n = len(sub)
        if n == 0:
            return {"filter": name, "n": 0, "wr": 0, "lo": 0, "hi": 0, "pnl": 0, "retained_pct": 0}
        w = (sub["pnl"] > 0).sum()
        wr_ = w / n
        lo_, hi_ = wilson_ci(w, n)
        return {
            "filter": name, "n": n, "wins": w, "wr": wr_,
            "lo": lo_, "hi": hi_, "pnl": sub["pnl"].sum(),
            "retained_pct": n / len(sol),
            "avg_win": sub[sub["pnl"] > 0]["pnl"].mean() if w > 0 else 0,
            "avg_loss": sub[sub["pnl"] <= 0]["pnl"].mean() if n - w > 0 else 0,
        }

    filters = [
        ("btc_aligned=True", sol["btc_aligned"] == True),
        ("LONG only", sol["side"] == "LONG"),
        ("SHORT only", sol["side"] == "SHORT"),
        ("regime_1h=trend_up", sol["regime_1h"] == "trend_up"),
        ("regime_1h=trend_down", sol["regime_1h"] == "trend_down"),
        ("regime_1h=trending (both)", sol["regime_1h"].isin(["trend_up", "trend_down"])),
        ("regime_6h=trending", sol["regime_6h"].isin(["trend_up", "trend_down"])),
        ("n_agree >= 2", sol["n_agree"] >= 2),
        ("n_agree >= 3", sol["n_agree"] >= 3),
        ("adx_1h >= 25", sol["adx_1h_14"] >= 25),
        ("adx_1h >= 30", sol["adx_1h_14"] >= 30),
        ("chop_score < 2", sol["chop_score_proxy"] < 2),
        ("chop_score < 1.5", sol["chop_score_proxy"] < 1.5),
        ("rsi_div_aligned (same sign)", np.sign(sol["rsi_1h_14"] - 50) == np.sign(sol["rsi_6h_14"] - 50)),
        ("volume_ratio >= 1", sol["volume_ratio_1h"] >= 1),
        ("volume_ratio >= 1.5", sol["volume_ratio_1h"] >= 1.5),
        ("confidence >= 80", sol["confidence"] >= 80),
        ("confidence >= 85", sol["confidence"] >= 85),
    ]
    for name, mask in filters:
        candidates.append(test_filter(name, mask))
    cand_df = pd.DataFrame(candidates)
    cand_df["edge"] = cand_df["wr"] - wr
    cand_df = cand_df.sort_values(["wr"], ascending=False)
    print(cand_df.to_string(index=False))

    # ======================== BEST COMPOUND FILTERS ========================
    print("\n\n============== COMPOUND FILTERS ==============")
    compounds = [
        ("btc_aligned + n_agree>=2",
         (sol["btc_aligned"] == True) & (sol["n_agree"] >= 2)),
        ("btc_aligned + trending_1h",
         (sol["btc_aligned"] == True) & sol["regime_1h"].isin(["trend_up", "trend_down"])),
        ("btc_aligned + trending_6h",
         (sol["btc_aligned"] == True) & sol["regime_6h"].isin(["trend_up", "trend_down"])),
        ("btc_aligned + side_matches_regime",
         (sol["btc_aligned"] == True) &
         (((sol["side"] == "LONG") & (sol["regime_1h"] == "trend_up")) |
          ((sol["side"] == "SHORT") & (sol["regime_1h"] == "trend_down")))),
        ("trending_1h + n_agree>=2",
         sol["regime_1h"].isin(["trend_up", "trend_down"]) & (sol["n_agree"] >= 2)),
        ("side_matches_regime_1h",
         ((sol["side"] == "LONG") & (sol["regime_1h"] == "trend_up")) |
         ((sol["side"] == "SHORT") & (sol["regime_1h"] == "trend_down"))),
        ("btc_aligned + chop<2",
         (sol["btc_aligned"] == True) & (sol["chop_score_proxy"] < 2)),
        ("btc_aligned + adx>=25",
         (sol["btc_aligned"] == True) & (sol["adx_1h_14"] >= 25)),
        ("WF-SOL (trending_1h + n_agree>=2)",
         sol["regime_1h"].isin(["trend_up", "trend_down"]) & (sol["n_agree"] >= 2)),
        ("WF-SOL + btc_aligned",
         sol["regime_1h"].isin(["trend_up", "trend_down"]) & (sol["n_agree"] >= 2) & (sol["btc_aligned"] == True)),
        ("Triple: trending_1h + trending_6h + btc_aligned",
         sol["regime_1h"].isin(["trend_up", "trend_down"]) &
         sol["regime_6h"].isin(["trend_up", "trend_down"]) &
         (sol["btc_aligned"] == True)),
        ("side_matches_regime_6h",
         ((sol["side"] == "LONG") & (sol["regime_6h"] == "trend_up")) |
         ((sol["side"] == "SHORT") & (sol["regime_6h"] == "trend_down"))),
        ("side_matches_both_regimes",
         (((sol["side"] == "LONG") & (sol["regime_1h"] == "trend_up") & (sol["regime_6h"] == "trend_up")) |
          ((sol["side"] == "SHORT") & (sol["regime_1h"] == "trend_down") & (sol["regime_6h"] == "trend_down")))),
    ]
    comp_rows = []
    for name, mask in compounds:
        comp_rows.append(test_filter(name, mask))
    comp_df = pd.DataFrame(comp_rows).sort_values(["wr"], ascending=False)
    comp_df["edge"] = comp_df["wr"] - wr
    print(comp_df.to_string(index=False))

    # Save
    out_dir = Path("C:/Users/vince/WAGMI PROJECT/WAGMI/bot/data/sessions")
    out_dir.mkdir(exist_ok=True)
    (out_dir / "sol_direction_analysis.json").write_text(json.dumps({
        "baseline_wr": wr, "n_total": len(sol), "n_winners": n_w, "n_losers": n_l,
        "total_pnl": float(sol["pnl"].sum()),
        "numeric_tests": feat_df.to_dict(orient="records"),
        "single_filters": cand_df.to_dict(orient="records"),
        "compound_filters": comp_df.to_dict(orient="records"),
    }, default=str, indent=2))
    print(f"\nSaved JSON to {out_dir/'sol_direction_analysis.json'}")


if __name__ == "__main__":
    main()
