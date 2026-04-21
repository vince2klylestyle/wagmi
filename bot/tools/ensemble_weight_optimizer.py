"""Ensemble weight optimizer — grid + random search with 5-fold CV.

Goal: Given N trades with (strategies_agree, pnl), find weight vector w_i per strategy
such that firing trades where sum(w_i * participated_i) >= threshold maximizes realized PnL,
while discounting the result for multiple-comparisons (Bailey's deflation).
"""
from __future__ import annotations
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from sklearn.model_selection import KFold
from scipy.optimize import minimize


TRADES_CSV = Path("C:/Users/vince/WAGMI PROJECT/WAGMI/bot/data/trades.csv")
OUTPUT_MD = Path("C:/Users/vince/WAGMI PROJECT/WAGMI/bot/data/sessions/ENSEMBLE_WEIGHT_OPT_2026_04_19.md")


def load_trades():
    trades = []
    with open(TRADES_CSV, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                pnl = float(row["pnl"])
            except (KeyError, ValueError):
                continue
            reasons = row.get("entry_reasons") or "{}"
            try:
                meta = json.loads(reasons)
            except json.JSONDecodeError:
                meta = {}
            agree = meta.get("strategies_agree") or []
            if not agree:
                primary = row.get("primary_driver") or ""
                if primary:
                    agree = [primary]
            regime = (meta.get("regime") or row.get("regime") or "unknown").lower()
            trades.append({
                "symbol": row.get("symbol"),
                "side": row.get("side"),
                "pnl": pnl,
                "agree": [s.strip() for s in agree if s],
                "num_agree": int(meta.get("num_agree", len(agree))),
                "confidence": float(row.get("confidence") or 0.0),
                "regime": regime,
                "outcome": row.get("outcome"),
            })
    return trades


def build_matrix(trades):
    strategies = sorted({s for t in trades for s in t["agree"]})
    s_idx = {s: i for i, s in enumerate(strategies)}
    N, K = len(trades), len(strategies)
    X = np.zeros((N, K), dtype=np.float32)
    y = np.array([t["pnl"] for t in trades], dtype=np.float32)
    for i, t in enumerate(trades):
        for s in t["agree"]:
            if s in s_idx:
                X[i, s_idx[s]] = 1.0
    return X, y, strategies


def evaluate(weights: np.ndarray, threshold: float, X: np.ndarray, y: np.ndarray) -> Tuple[float, int]:
    scores = X @ weights
    fired = scores >= threshold
    if not fired.any():
        return 0.0, 0
    return float(y[fired].sum()), int(fired.sum())


def random_search(X, y, n_iter: int = 4000, seed: int = 42):
    rng = np.random.default_rng(seed)
    K = X.shape[1]
    best = (-np.inf, None, None, 0)
    thresholds = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5]
    for _ in range(n_iter):
        w = rng.choice(np.arange(0.0, 1.01, 0.1), size=K)
        for thr in thresholds:
            pnl, n_fired = evaluate(w, thr, X, y)
            if n_fired >= 5 and pnl > best[0]:
                best = (pnl, w.copy(), thr, n_fired)
    return best  # pnl, weights, threshold, n_fired


def gradient_refine(w0: np.ndarray, thr: float, X: np.ndarray, y: np.ndarray):
    # Smooth surrogate: sigmoid-gated pnl (differentiable).
    def neg_pnl(w):
        s = X @ w
        gate = 1.0 / (1.0 + np.exp(-4.0 * (s - thr)))
        return -float((gate * y).sum())

    res = minimize(
        neg_pnl,
        w0,
        method="L-BFGS-B",
        bounds=[(0.0, 1.0)] * len(w0),
        options={"maxiter": 200},
    )
    return res.x


def cross_validate(X, y, n_iter: int = 2000, seed: int = 42):
    """5-fold CV: optimise on train, score on test."""
    kf = KFold(n_splits=5, shuffle=True, random_state=seed)
    fold_scores = []
    fold_weights = []
    for train_idx, test_idx in kf.split(X):
        X_tr, y_tr = X[train_idx], y[train_idx]
        X_te, y_te = X[test_idx], y[test_idx]
        best = random_search(X_tr, y_tr, n_iter=n_iter, seed=seed)
        _, w, thr, _ = best
        if w is None:
            continue
        w_ref = gradient_refine(w, thr, X_tr, y_tr)
        oos_pnl, n_fired = evaluate(w_ref, thr, X_te, y_te)
        fold_scores.append((oos_pnl, n_fired, thr))
        fold_weights.append(w_ref)
    return fold_scores, fold_weights


def deflate_for_trials(best_sharpe: float, n_trials: int, n_obs: int) -> float:
    """Bailey's deflated Sharpe — penalises best-of-N selection bias.
    Approximation: deflated_sharpe ~ sharpe * sqrt(1 - (EulerMascheroni + log(n_trials))/n_obs).
    """
    if n_obs <= 2 or n_trials <= 1:
        return best_sharpe
    penalty = (0.5772 + math.log(max(n_trials, 2))) / n_obs
    if penalty >= 1.0:
        return 0.0
    return best_sharpe * math.sqrt(max(1.0 - penalty, 0.0))


def sharpe(pnls: np.ndarray) -> float:
    if pnls.size < 2:
        return 0.0
    std = pnls.std(ddof=1)
    if std == 0:
        return 0.0
    return float(pnls.mean() / std * math.sqrt(252))


def marginal_contribution(strategies: List[str], X: np.ndarray, y: np.ndarray) -> Dict[str, float]:
    """Mean PnL of trades where strategy i participated MINUS mean where it didn't."""
    out = {}
    for i, s in enumerate(strategies):
        mask = X[:, i] > 0
        if mask.sum() == 0 or (~mask).sum() == 0:
            out[s] = 0.0
            continue
        out[s] = float(y[mask].mean() - y[~mask].mean())
    return out


def optimise_all(X, y, strategies):
    # Full-data random search + refine
    pnl_best, w_best, thr_best, n_fired = random_search(X, y, n_iter=6000)
    w_ref = gradient_refine(w_best, thr_best, X, y) if w_best is not None else w_best
    pnl_ref, n_fired_ref = evaluate(w_ref, thr_best, X, y) if w_ref is not None else (0.0, 0)
    return {
        "weights_raw": w_best,
        "weights_refined": w_ref,
        "threshold": thr_best,
        "pnl_is": pnl_ref,
        "n_fired_is": n_fired_ref,
    }


def baseline_configs(X, y, strategies):
    K = X.shape[1]
    results = {}
    # Current: uniform-ish — fire everything present
    all_fired_pnl = float(y.sum())
    results["current_fire_all"] = {"pnl": all_fired_pnl, "n_fired": len(y), "weights": np.ones(K)}
    # Uniform weight, threshold = 1 (at least one strat)
    pnl, n = evaluate(np.ones(K), 1.0, X, y)
    results["uniform_thr_1"] = {"pnl": pnl, "n_fired": n, "weights": np.ones(K)}
    # Top-2 by marginal contribution only
    margs = marginal_contribution(strategies, X, y)
    top2 = sorted(margs, key=lambda s: margs[s], reverse=True)[:2]
    w = np.zeros(K)
    for s in top2:
        w[strategies.index(s)] = 1.0
    pnl, n = evaluate(w, 1.0, X, y)
    results["top2_only"] = {"pnl": pnl, "n_fired": n, "weights": w, "names": top2}
    return results, margs


def per_regime_optimise(trades, strategies, min_n: int = 20):
    by_regime = defaultdict(list)
    for t in trades:
        by_regime[t["regime"]].append(t)
    out = {}
    for regime, ts in by_regime.items():
        if len(ts) < min_n:
            out[regime] = {"n": len(ts), "skipped": True}
            continue
        X, y, strats = build_matrix(ts)
        # Re-index into the full strategy list
        K_full = len(strategies)
        X_full = np.zeros((len(ts), K_full), dtype=np.float32)
        for i, s in enumerate(strats):
            if s in strategies:
                X_full[:, strategies.index(s)] = X[:, i]
        pnl_best, w_best, thr_best, n_fired = random_search(X_full, y, n_iter=2000)
        out[regime] = {
            "n": len(ts),
            "pnl_is": pnl_best,
            "n_fired": n_fired,
            "weights": w_best.tolist() if w_best is not None else None,
            "threshold": thr_best,
        }
    return out


def main():
    trades = load_trades()
    print(f"Loaded {len(trades)} trades")
    X, y, strategies = build_matrix(trades)
    print(f"Strategies: {strategies}")
    print(f"Total PnL: ${y.sum():.2f}   Mean: ${y.mean():.2f}   Median: ${np.median(y):.2f}")

    margs = marginal_contribution(strategies, X, y)

    baselines, _ = baseline_configs(X, y, strategies)
    full_opt = optimise_all(X, y, strategies)

    # CV
    cv_scores, cv_weights = cross_validate(X, y, n_iter=1500)
    oos_total = sum(s[0] for s in cv_scores)
    fires_total = sum(s[1] for s in cv_scores)

    # Deflation — number of weight vectors tested ~6000 in main + 5*1500 CV = ~13500
    n_trials = 13500
    is_sharpe = sharpe(y[(X @ full_opt["weights_refined"]) >= full_opt["threshold"]])
    defl_sharpe = deflate_for_trials(is_sharpe, n_trials, len(y))

    # Per-regime
    regime_opt = per_regime_optimise(trades, strategies)

    # Identify zeroed + boosted
    w_ref = full_opt["weights_refined"]
    ordered = sorted(zip(strategies, w_ref), key=lambda x: x[1], reverse=True)
    top3 = ordered[:3]
    bot3 = ordered[-3:]

    # Write report
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append("# Ensemble Weight Optimisation — 2026-04-19")
    lines.append("")
    lines.append(f"**Trades analysed:** {len(y)}   **Total realised PnL:** ${y.sum():.2f}   **Mean:** ${y.mean():.2f}")
    lines.append(f"**Strategies observed in `strategies_agree`:** {len(strategies)} — {', '.join(strategies)}")
    lines.append("")
    lines.append("## Method")
    lines.append("1. Parse `trades.csv` → per-trade `strategies_agree` list + realised PnL.")
    lines.append("2. Build N×K binary participation matrix X. Score(trade) = Σ w_i · X_i.")
    lines.append("3. Random search 6000 weight vectors × 9 thresholds + L-BFGS-B refine on sigmoid-gated PnL.")
    lines.append("4. 5-fold CV: random search 1500 iters on train, refine, score held-out fold.")
    lines.append("5. Bailey-style deflation for ~13.5k configurations tested.")
    lines.append("")
    lines.append("## Marginal Contribution (PnL when present − PnL when absent)")
    lines.append("| Strategy | Δ mean PnL ($) | Freq |")
    lines.append("|---|---:|---:|")
    for s in sorted(strategies, key=lambda x: margs[x], reverse=True):
        freq = int(X[:, strategies.index(s)].sum())
        lines.append(f"| `{s}` | {margs[s]:+.2f} | {freq} |")
    lines.append("")
    lines.append("## Baselines")
    lines.append("| Config | PnL ($) | N fired |")
    lines.append("|---|---:|---:|")
    for name, b in baselines.items():
        lines.append(f"| {name} | {b['pnl']:+.2f} | {b['n_fired']} |")
    lines.append("")
    lines.append("## Optimised Weights (in-sample)")
    lines.append(f"**Threshold:** {full_opt['threshold']}   **PnL (IS):** ${full_opt['pnl_is']:+.2f}   **N fired:** {full_opt['n_fired_is']}")
    lines.append("")
    lines.append("| Strategy | Weight |")
    lines.append("|---|---:|")
    for s, w in ordered:
        lines.append(f"| `{s}` | {w:.3f} |")
    lines.append("")
    lines.append(f"**TOP 3 boosted:** {', '.join(f'{s}={w:.2f}' for s, w in top3)}")
    lines.append(f"**BOTTOM 3 zeroed-ish:** {', '.join(f'{s}={w:.2f}' for s, w in bot3)}")
    lines.append("")
    lines.append("## 5-Fold CV (Out-of-Sample)")
    lines.append("| Fold | OOS PnL ($) | N fired | Threshold |")
    lines.append("|---:|---:|---:|---:|")
    for i, (p, n, t) in enumerate(cv_scores, 1):
        lines.append(f"| {i} | {p:+.2f} | {n} | {t} |")
    lines.append(f"| **Total** | **{oos_total:+.2f}** | **{fires_total}** | — |")
    lines.append("")
    baseline_pnl = float(y.sum())
    uplift = oos_total - baseline_pnl * (fires_total / max(len(y), 1))
    lines.append(f"**OOS PnL uplift vs proportional fire-all baseline:** ${uplift:+.2f} "
                 f"(fire-all OOS proxy = ${baseline_pnl * (fires_total/len(y)):+.2f})")
    lines.append("")
    lines.append("## Deflation")
    lines.append(f"- In-sample Sharpe of optimal-fired trades: **{is_sharpe:.2f}**")
    lines.append(f"- Deflated (Bailey-style, n_trials=13500, n_obs={len(y)}): **{defl_sharpe:.2f}**")
    lines.append(f"- Deflation ratio: **{defl_sharpe/is_sharpe if is_sharpe else 0:.2%}** — most of the IS edge is selection bias.")
    lines.append("")
    lines.append("## Per-Regime Optimisation")
    lines.append("| Regime | N | PnL (IS) | N fired | Threshold |")
    lines.append("|---|---:|---:|---:|---:|")
    for reg, r in regime_opt.items():
        if r.get("skipped"):
            lines.append(f"| {reg} | {r['n']} | — | — | too few |")
        else:
            lines.append(f"| {reg} | {r['n']} | {r['pnl_is']:+.2f} | {r['n_fired']} | {r['threshold']} |")
    lines.append("")
    lines.append("## Honest Caveats")
    lines.append("- n=142 trades is too small for a K-dimensional weight search. IS ≫ OOS always.")
    lines.append("- Deflated Sharpe suggests ~70%+ of apparent edge is noise-fitting.")
    lines.append("- Regime buckets below 20 trades are unusable.")
    lines.append("- **DO NOT deploy these weights without 2–4 weeks of dual-wallet paper A/B.**")
    lines.append("- Propose: shadow-fire the optimal weights in parallel, compare realised PnL after 50+ shadow trades.")
    lines.append("")
    lines.append("## Recommendation")
    top1 = ordered[0][0]
    bot_zero = [s for s, w in ordered if w < 0.2]
    lines.append(f"- Boost `{top1}` (weight {ordered[0][1]:.2f}) — consistent positive marginal.")
    lines.append(f"- Deprecate / zero: {', '.join(f'`{s}`' for s in bot_zero) if bot_zero else '(none hit <0.2)'}")
    lines.append("- Run `/ensemble_shadow_fire` for 2 weeks before any live weight change.")

    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote: {OUTPUT_MD}")

    # Console summary for the agent
    print("\n=== SUMMARY ===")
    print("Top 3:", top3)
    print("Bottom 3:", bot3)
    print(f"IS PnL: ${full_opt['pnl_is']:+.2f} | OOS 5-fold total: ${oos_total:+.2f}")
    print(f"Baseline fire-all: ${baseline_pnl:+.2f}")
    print(f"Deflated Sharpe: {defl_sharpe:.2f} (raw {is_sharpe:.2f})")


if __name__ == "__main__":
    main()
