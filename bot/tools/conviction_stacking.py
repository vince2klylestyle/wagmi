"""Conviction stacking analysis — 2026-04-19.

For each closed trade, evaluates which of the 4 Bonferroni-clearing signals were
TRUE at entry, then buckets by alignment count and computes WR / PF / Wilson CIs.
"""
from __future__ import annotations

import json
import math
from itertools import combinations
from pathlib import Path

import pandas as pd
from scipy import stats

TRADES_CSV = Path(r"C:\Users\vince\WAGMI PROJECT\WAGMI\bot\data\trades.csv")


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def pf(pnls: pd.Series) -> float:
    wins = pnls[pnls > 0].sum()
    losses = -pnls[pnls < 0].sum()
    if losses == 0:
        return float("inf") if wins > 0 else float("nan")
    return float(wins / losses)


def load_trades() -> pd.DataFrame:
    df = pd.read_csv(TRADES_CSV)
    # Parse entry_reasons JSON column
    parsed: list[dict] = []
    for row in df["entry_reasons"].fillna("{}"):
        try:
            parsed.append(json.loads(row))
        except (json.JSONDecodeError, TypeError):
            parsed.append({})
    reasons = pd.json_normalize(parsed)
    out = pd.concat([df.reset_index(drop=True), reasons.reset_index(drop=True)], axis=1)
    # Dedupe columns
    out = out.loc[:, ~out.columns.duplicated()]
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")
    out["hour_utc"] = out["timestamp"].dt.hour
    out["win"] = (out["pnl"] > 0).astype(int)
    # fill num_agree with 1 when missing (sniper_premium rows lack it)
    if "num_agree" not in out.columns:
        out["num_agree"] = 1
    out["num_agree"] = pd.to_numeric(out["num_agree"], errors="coerce").fillna(1).astype(int)
    out["leverage_num"] = pd.to_numeric(out["leverage"], errors="coerce").fillna(0)
    return out


def build_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Compute the 4 alignment signals per trade.

    Semantics: a signal is TRUE when it would be FAVORABLE to take the trade
    under the rule — i.e. the rule would green-light it (or at minimum not veto).
    """
    out = df.copy()

    # Signal 1: rsi_div_1h_6h_aligned — not present in CSV.
    # Proxy: multi-timeframe strategy agreement where regime trend matches side.
    #   - regime=trending and side=SHORT  --> treat as aligned bear
    #   - regime=trending and side=LONG   --> aligned bull
    # With only 1 regime flag this is an imperfect proxy. Flag honestly in doc.
    out["S1_rsi_div_aligned"] = (
        (out["regime"].astype(str).str.startswith("trending"))
        & (out["num_agree"] >= 2)
    ).astype(int)

    # Signal 2: HYPE solo LONG veto — TRUE when the trade is NOT a HYPE-solo-LONG
    # (i.e. veto rule green-lights it).
    hype_solo_long = (
        (out["symbol"] == "HYPE")
        & (out["side"].isin(["LONG", "BUY"]))
        & (out["num_agree"] <= 1)
    )
    out["S2_not_hype_solo_long"] = (~hype_solo_long).astype(int)

    # Signal 3: Asia deadzone solo reject — TRUE when NOT (Asia hours AND solo).
    asia_solo = (
        (out["hour_utc"].between(0, 7, inclusive="left"))
        & (out["num_agree"] <= 1)
    )
    out["S3_not_asia_solo"] = (~asia_solo).astype(int)

    # Signal 4: Trending × n_agree>=2 × lev>=4 — TRUE when all three hold.
    out["S4_trending_multi_highlev"] = (
        (out["regime"].astype(str).str.startswith("trending"))
        & (out["num_agree"] >= 2)
        & (out["leverage_num"] >= 4)
    ).astype(int)

    signal_cols = [
        "S1_rsi_div_aligned",
        "S2_not_hype_solo_long",
        "S3_not_asia_solo",
        "S4_trending_multi_highlev",
    ]
    out["align_count"] = out[signal_cols].sum(axis=1)
    return out, signal_cols


def bucket_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for bucket in sorted(df["align_count"].unique()):
        sub = df[df["align_count"] == bucket]
        n = len(sub)
        wins = int(sub["win"].sum())
        wr = wins / n if n else 0.0
        lo, hi = wilson_ci(wins, n)
        mean_pnl = sub["pnl"].mean() if n else float("nan")
        total_pnl = sub["pnl"].sum() if n else 0.0
        pf_val = pf(sub["pnl"])
        rows.append(
            {
                "align_count": int(bucket),
                "n": n,
                "wins": wins,
                "WR": round(wr, 4),
                "WR_CI_lo": round(lo, 4),
                "WR_CI_hi": round(hi, 4),
                "mean_pnl": round(float(mean_pnl), 3) if n else float("nan"),
                "total_pnl": round(float(total_pnl), 2),
                "PF": round(pf_val, 3) if pf_val == pf_val and pf_val != float("inf") else pf_val,
            }
        )
    return pd.DataFrame(rows)


def pair_interactions(df: pd.DataFrame, signal_cols: list[str]) -> pd.DataFrame:
    """For each pair (A,B), compute WR in the 4 cells of (A,B) truth table."""
    rows = []
    base_wr = df["win"].mean()
    for a, b in combinations(signal_cols, 2):
        cell_11 = df[(df[a] == 1) & (df[b] == 1)]
        cell_10 = df[(df[a] == 1) & (df[b] == 0)]
        cell_01 = df[(df[a] == 0) & (df[b] == 1)]
        cell_00 = df[(df[a] == 0) & (df[b] == 0)]

        def cell_stats(c: pd.DataFrame) -> tuple[int, int, float]:
            n = len(c)
            w = int(c["win"].sum())
            return n, w, w / n if n else float("nan")

        n11, w11, wr11 = cell_stats(cell_11)
        n10, w10, wr10 = cell_stats(cell_10)
        n01, w01, wr01 = cell_stats(cell_01)
        n00, w00, wr00 = cell_stats(cell_00)

        # Additive expectation: WR(A=1,B=1) ≈ base + (WR10-base) + (WR01-base)
        if all(not math.isnan(x) for x in (wr10, wr01, wr00)):
            additive_expected = wr00 + (wr10 - wr00) + (wr01 - wr00)
        else:
            additive_expected = float("nan")
        interaction = wr11 - additive_expected if not math.isnan(wr11) else float("nan")

        rows.append(
            {
                "A": a,
                "B": b,
                "n_both": n11,
                "WR_both": round(wr11, 4) if not math.isnan(wr11) else float("nan"),
                "n_A_only": n10,
                "WR_A_only": round(wr10, 4) if not math.isnan(wr10) else float("nan"),
                "n_B_only": n01,
                "WR_B_only": round(wr01, 4) if not math.isnan(wr01) else float("nan"),
                "n_neither": n00,
                "WR_neither": round(wr00, 4) if not math.isnan(wr00) else float("nan"),
                "additive_expected": round(additive_expected, 4)
                if not math.isnan(additive_expected)
                else float("nan"),
                "interaction_effect": round(interaction, 4)
                if not math.isnan(interaction)
                else float("nan"),
            }
        )
    return pd.DataFrame(rows).sort_values(
        "interaction_effect", key=lambda s: s.abs(), ascending=False
    )


def independence_test(df: pd.DataFrame, signal_cols: list[str]) -> dict:
    """If signals were independent given WR, P(all 4 correct) = product of marginal WRs."""
    marginals = {}
    for c in signal_cols:
        sub = df[df[c] == 1]
        marginals[c] = sub["win"].mean() if len(sub) else float("nan")
    prod = 1.0
    for v in marginals.values():
        if math.isnan(v):
            prod = float("nan")
            break
        prod *= v
    # Empirical WR when ALL 4 are true
    full = df[(df[signal_cols] == 1).all(axis=1)]
    empirical = full["win"].mean() if len(full) else float("nan")
    return {
        "marginal_WRs": {k: round(v, 4) for k, v in marginals.items()},
        "product_of_marginals": round(prod, 4) if not math.isnan(prod) else float("nan"),
        "empirical_WR_all4_true": round(empirical, 4) if not math.isnan(empirical) else float("nan"),
        "n_all4_true": int(len(full)),
    }


def regime_decomposition(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for regime in df["regime"].dropna().unique():
        sub = df[df["regime"] == regime]
        for bucket in sorted(sub["align_count"].unique()):
            cell = sub[sub["align_count"] == bucket]
            n = len(cell)
            if n < 3:
                continue
            wins = int(cell["win"].sum())
            wr = wins / n
            lo, hi = wilson_ci(wins, n)
            rows.append(
                {
                    "regime": regime,
                    "align_count": int(bucket),
                    "n": n,
                    "WR": round(wr, 4),
                    "WR_CI": f"[{lo:.2f}, {hi:.2f}]",
                    "PF": round(pf(cell["pnl"]), 3)
                    if pf(cell["pnl"]) not in (float("inf"), float("nan"))
                    else "inf/nan",
                    "mean_pnl": round(float(cell["pnl"].mean()), 3),
                }
            )
    return pd.DataFrame(rows)


def tipping_point(table: pd.DataFrame) -> dict:
    """Find minimum alignment count achieving PF>=2 and WR>0.5."""
    min_pf2 = None
    min_wr50 = None
    for _, r in table.iterrows():
        pf_val = r["PF"]
        try:
            pf_float = float(pf_val)
        except (TypeError, ValueError):
            pf_float = float("nan")
        if min_pf2 is None and pf_float >= 2.0:
            min_pf2 = int(r["align_count"])
        if min_wr50 is None and r["WR"] >= 0.5:
            min_wr50 = int(r["align_count"])
    return {"min_align_for_PF2": min_pf2, "min_align_for_WR50": min_wr50}


def chi_square_trend(df: pd.DataFrame) -> dict:
    """Cochran-Armitage-style: is there a monotone WR trend with align_count?"""
    cont = pd.crosstab(df["align_count"], df["win"])
    if cont.shape[1] < 2:
        return {"chi2": float("nan"), "p": float("nan"), "df": 0}
    chi2, p, dof, _ = stats.chi2_contingency(cont)
    return {"chi2": round(chi2, 3), "p": round(p, 4), "df": int(dof)}


def main() -> None:
    df = load_trades()
    df, signal_cols = build_signals(df)

    print(f"n_trades = {len(df)}")
    print(df[signal_cols + ["align_count", "win", "pnl"]].head())

    bt = bucket_table(df)
    print("\n=== BUCKET TABLE ===")
    print(bt.to_string(index=False))

    pi = pair_interactions(df, signal_cols)
    print("\n=== PAIR INTERACTIONS ===")
    print(pi.to_string(index=False))

    indep = independence_test(df, signal_cols)
    print("\n=== INDEPENDENCE TEST ===")
    print(json.dumps(indep, indent=2))

    rd = regime_decomposition(df)
    print("\n=== REGIME DECOMP ===")
    print(rd.to_string(index=False))

    tp = tipping_point(bt)
    print("\n=== TIPPING POINT ===")
    print(tp)

    cs = chi_square_trend(df)
    print("\n=== CHI-SQUARE TREND ===")
    print(cs)

    # Persist for doc-writing step
    artifacts = {
        "bucket_table": bt.to_dict(orient="records"),
        "pair_interactions": pi.to_dict(orient="records"),
        "independence": indep,
        "regime_decomposition": rd.to_dict(orient="records"),
        "tipping_point": tp,
        "chi_square": cs,
        "n_trades": int(len(df)),
        "overall_WR": round(float(df["win"].mean()), 4),
        "overall_PF": round(pf(df["pnl"]), 3)
        if pf(df["pnl"]) not in (float("inf"), float("nan"))
        else "inf/nan",
    }
    out_path = Path(
        r"C:\Users\vince\WAGMI PROJECT\WAGMI\bot\data\sessions\_conviction_stacking_raw.json"
    )
    out_path.write_text(json.dumps(artifacts, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
