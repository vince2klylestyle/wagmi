"""Validation round: explore the BTC-INVERSE signature + side interactions."""
from __future__ import annotations

import json, math
from pathlib import Path
import numpy as np
import pandas as pd


def wilson_ci(w, n, z=1.96):
    if n == 0: return 0.0, 0.0
    p = w / n
    denom = 1 + z*z/n
    c = (p + z*z/(2*n)) / denom
    m = z * math.sqrt((p*(1-p) + z*z/(4*n))/n) / denom
    return max(0, c-m), min(1, c+m)


def main():
    df = pd.read_csv("C:/Users/vince/WAGMI PROJECT/WAGMI/bot/data/trades_enriched_2026_04_19.csv")
    sol = df[df["symbol"] == "SOL"].copy().reset_index(drop=True)
    reasons = sol["entry_reasons"].apply(lambda x: json.loads(x) if isinstance(x, str) else {})
    sol["n_agree"] = reasons.apply(lambda d: d.get("num_agree", np.nan))
    sol["btc_ret"] = sol["btc_4h_return_signed"]
    sol["btc_aligned"] = np.where(
        sol["side"] == "LONG", sol["btc_ret"] > 0, sol["btc_ret"] < 0
    )
    sol["win"] = sol["pnl"] > 0

    def pf(sub):
        """Profit factor."""
        w = sub[sub["pnl"] > 0]["pnl"].sum()
        l_ = -sub[sub["pnl"] <= 0]["pnl"].sum()
        return w / l_ if l_ > 0 else float("inf")

    def report(name, mask):
        sub = sol[mask]
        n = len(sub)
        if n == 0:
            return dict(name=name, n=0)
        w = (sub["pnl"] > 0).sum()
        wr = w / n
        lo, hi = wilson_ci(w, n)
        return dict(
            name=name, n=n, wins=w, wr=wr, lo=lo, hi=hi,
            pnl=float(sub["pnl"].sum()), pf=pf(sub),
            retained=n/len(sol),
        )

    # MIRROR: make anti-BTC the base hypothesis (since SOL behaves as BTC laggard/mean-revert)
    print(f"Base SOL: n={len(sol)}  WR={sol['win'].mean():.1%}  PnL=${sol['pnl'].sum():.2f}  PF={pf(sol):.2f}")

    print("\n=== ANTI-BTC HYPOTHESIS ===")
    # sol "inverse_aligned" = opposite of btc_aligned => counter-BTC trades
    sol["anti_btc"] = ~sol["btc_aligned"]
    tests = [
        ("anti_btc (counter-BTC)", sol["anti_btc"]),
        ("anti_btc + SHORT",       sol["anti_btc"] & (sol["side"]=="SHORT")),
        ("anti_btc + LONG",        sol["anti_btc"] & (sol["side"]=="LONG")),
        ("anti_btc + adx>=25",     sol["anti_btc"] & (sol["adx_1h_14"]>=25)),
        ("anti_btc + trending_1h", sol["anti_btc"] & sol["regime_1h"].isin(["trend_up","trend_down"])),
        ("anti_btc + volume>=1",   sol["anti_btc"] & (sol["volume_ratio_1h"]>=1)),
        ("anti_btc + chop<2",      sol["anti_btc"] & (sol["chop_score_proxy"]<2)),
        # Strong BTC move magnitude check (is effect sensitive to size?)
        ("anti_btc + |btc_ret|>0.005", sol["anti_btc"] & (sol["btc_ret"].abs()>=0.005)),
        ("anti_btc + |btc_ret|>0.010", sol["anti_btc"] & (sol["btc_ret"].abs()>=0.010)),
    ]
    for name, mask in tests:
        r = report(name, mask)
        print(f"  {name:45s} n={r['n']:3d} WR={r['wr']:.1%} [{r['lo']:.0%},{r['hi']:.0%}] PnL=${r['pnl']:7.2f} PF={r['pf']:.2f} retained={r['retained']:.0%}")

    print("\n=== SECTOR: RANGE vs TREND on 1h ===")
    # Check if BTC-inverse is strongest in ranging regime
    for reg in ["range", "trend_up", "trend_down"]:
        sub = sol[sol["regime_1h"] == reg]
        for aligned in [True, False]:
            s = sub[sub["btc_aligned"] == aligned]
            if len(s) == 0:
                continue
            w = (s["pnl"] > 0).sum()
            lo, hi = wilson_ci(w, len(s))
            tag = "ALIGNED" if aligned else "ANTI"
            print(f"  regime_1h={reg:10s} btc={tag:8s} n={len(s):3d} WR={w/len(s):.1%} [{lo:.0%},{hi:.0%}] PnL=${s['pnl'].sum():7.2f}")

    print("\n=== RECOMMENDED FILTER CANDIDATES ===")
    final = [
        ("ANTI-BTC (raw inverse rule)", sol["anti_btc"]),
        ("ANTI-BTC + SHORT only", sol["anti_btc"] & (sol["side"]=="SHORT")),
        ("ANTI-BTC + adx>=25", sol["anti_btc"] & (sol["adx_1h_14"]>=25)),
        ("ANTI-BTC + trending_1h", sol["anti_btc"] & sol["regime_1h"].isin(["trend_up","trend_down"])),
        # Skip-rules (safer — drop the known-losing cell)
        ("SKIP aligned+SHORT (else take)", ~((sol["btc_aligned"]==True) & (sol["side"]=="SHORT"))),
        ("SKIP aligned+LONG with regime=range",
            ~((sol["btc_aligned"]==True) & (sol["side"]=="LONG") & (sol["regime_1h"]=="range"))),
    ]
    for name, mask in final:
        r = report(name, mask)
        print(f"  {name:45s} n={r['n']:3d} WR={r['wr']:.1%} [{r['lo']:.0%},{r['hi']:.0%}] PnL=${r['pnl']:7.2f} PF={r['pf']:.2f} retained={r['retained']:.0%}")

    # Time-ordering check: is anti-BTC edge spread through time or concentrated?
    print("\n=== TEMPORAL DISTRIBUTION OF ANTI-BTC WINNERS ===")
    sol["ts_dt"] = pd.to_datetime(sol["timestamp"], utc=True)
    sol["week"] = sol["ts_dt"].dt.isocalendar().week
    for w_, grp in sol.groupby("week"):
        anti = grp[grp["anti_btc"]]
        if len(anti) < 2:
            continue
        wins = (anti["pnl"]>0).sum()
        print(f"  week={w_}  anti-BTC n={len(anti):2d} WR={wins/len(anti):.0%} PnL=${anti['pnl'].sum():.2f}")


if __name__ == "__main__":
    main()
