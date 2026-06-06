"""Winner Amplification — find sub-conditions that push already-winning cells higher WR."""
import json
import pandas as pd
import numpy as np
from pathlib import Path

CSV = Path("C:/Users/vince/WAGMI PROJECT/WAGMI/bot/data/trades.csv")

def parse_reasons(row):
    try:
        return json.loads(row)
    except Exception:
        return {}

def load():
    df = pd.read_csv(CSV)
    df["reasons"] = df["entry_reasons"].apply(parse_reasons)
    # flatten useful keys
    keys = [
        "num_agree","trend_adjustment","regime_score","mode","rr1","ml_adjusted",
        "entry_type","primary_driver","regime","volatility_band","llm_action",
        "llm_confidence","llm_agreed","signal_flags","flag_max_priority",
        "ev_per_dollar","win_prob_deflated","fee_drag_pct","entry_slippage_pct",
    ]
    for k in keys:
        df[k] = df["reasons"].apply(lambda d: d.get(k))
    df["strategies_agree"] = df["reasons"].apply(lambda d: tuple(sorted(d.get("strategies_agree", []))))
    df["ts"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df["hour_utc"] = df["ts"].dt.hour
    df["dow"] = df["ts"].dt.day_name()
    df["win"] = (df["pnl"] > 0).astype(int)
    df["hour_bucket"] = pd.cut(df["hour_utc"], bins=[-1,3,7,11,15,19,23], labels=["0-3","4-7","8-11","12-15","16-19","20-23"])
    df["conf_bucket"] = pd.cut(df["confidence"], bins=[0,70,80,85,90,100], labels=["<70","70-80","80-85","85-90",">90"])
    df["lev_bucket"] = pd.cut(df["leverage"], bins=[0,2,4,6,10,100], labels=["<=2","2-4","4-6","6-10",">10"])
    df["ev_pct"] = df["ev_per_dollar"].rank(pct=True)
    return df

def wr(sub):
    if len(sub)==0: return float("nan")
    return 100.0 * sub["win"].mean()

def dollar(sub):
    return sub["pnl"].sum()

def summary(tag, sub, baseline=None):
    n = len(sub); w = wr(sub); d = dollar(sub)
    s = f"{tag}: n={n}, WR={w:.1f}%, $={d:.2f}"
    if baseline is not None and len(baseline)>0:
        s += f" (vs baseline WR={wr(baseline):.1f}%, $={dollar(baseline):.2f})"
    return s

def feature_lift(cell, feat, top_n=None):
    """Compute WR by feature value, only show values with n>=2."""
    if feat not in cell.columns: return []
    g = cell.groupby(feat, dropna=False).agg(n=("win","count"), wr=("win","mean"), pnl=("pnl","sum"))
    g["wr"] *= 100
    g = g[g["n"]>=2].sort_values("wr", ascending=False)
    return g

def amplifier_search(cell, candidate_filters, name):
    """Try each candidate filter; return those that raise WR while retaining trades."""
    base_n = len(cell); base_wr = wr(cell); base_d = dollar(cell)
    results = []
    for desc, mask_fn in candidate_filters:
        try:
            mask = mask_fn(cell)
            sub = cell[mask]
            if len(sub)<2: continue
            delta_wr = wr(sub) - base_wr
            retention = len(sub)/base_n
            results.append({
                "filter": desc,
                "kept_n": len(sub),
                "retained_pct": retention*100,
                "kept_wr": wr(sub),
                "delta_wr": delta_wr,
                "kept_pnl": dollar(sub),
                "rejected_n": base_n-len(sub),
                "rejected_wr": wr(cell[~mask]) if (base_n-len(sub))>0 else float("nan"),
                "rejected_pnl": dollar(cell[~mask]),
            })
        except Exception as e:
            continue
    return sorted(results, key=lambda r: (-r["delta_wr"], -r["retained_pct"]))

def run_cell(df, name, mask):
    cell = df[mask].copy()
    print(f"\n=== CELL: {name} ===")
    print(summary("BASELINE", cell))
    if len(cell)<3:
        print("Too few trades, skipping feature audit")
        return cell, []

    # feature lift tables
    for feat in ["hour_bucket","dow","conf_bucket","lev_bucket","primary_driver",
                 "regime","volatility_band","num_agree","side","symbol","entry_type"]:
        g = feature_lift(cell, feat)
        if len(g)>0:
            print(f"\n  [{feat}]")
            print(g.head(8).to_string())
    # ev / win_prob buckets
    if cell["ev_per_dollar"].notna().sum()>=4:
        cell["ev_tier"] = pd.qcut(cell["ev_per_dollar"], q=min(4,cell["ev_per_dollar"].nunique()), duplicates="drop")
        g = feature_lift(cell, "ev_tier")
        if len(g)>0:
            print(f"\n  [ev_per_dollar tiers]")
            print(g.head(8).to_string())

    return cell, []

def try_amplifiers(df, cell_name, cell):
    print(f"\n--- AMPLIFIER CANDIDATES for {cell_name} ---")
    candidates = [
        ("hour_utc>=15", lambda d: d["hour_utc"]>=15),
        ("hour_utc<15", lambda d: d["hour_utc"]<15),
        ("hour_utc in 16-23", lambda d: d["hour_utc"].between(16,23)),
        ("ev_per_dollar>=0.5", lambda d: d["ev_per_dollar"]>=0.5),
        ("ev_per_dollar>=0.7", lambda d: d["ev_per_dollar"]>=0.7),
        ("win_prob_deflated>=0.55", lambda d: d["win_prob_deflated"]>=0.55),
        ("win_prob_deflated>=0.6", lambda d: d["win_prob_deflated"]>=0.6),
        ("num_agree>=2", lambda d: d["num_agree"]>=2),
        ("num_agree>=3", lambda d: d["num_agree"]>=3),
        ("confidence>=80", lambda d: d["confidence"]>=80),
        ("confidence>=85", lambda d: d["confidence"]>=85),
        ("leverage>=6", lambda d: d["leverage"]>=6),
        ("rr1>=1.8", lambda d: d["rr1"]>=1.8),
        ("volatility_band==low", lambda d: d["volatility_band"]=="low"),
        ("volatility_band==normal", lambda d: d["volatility_band"]=="normal"),
        ("trend_adjustment>=5", lambda d: d["trend_adjustment"]>=5),
        ("side==SHORT", lambda d: d["side"]=="SHORT"),
        ("side==LONG", lambda d: d["side"]=="LONG"),
        ("symbol!=HYPE", lambda d: d["symbol"]!="HYPE"),
        ("symbol==BTC", lambda d: d["symbol"]=="BTC"),
        ("primary_driver==regime_trend", lambda d: d["primary_driver"]=="regime_trend"),
        ("primary_driver==multi_tier_quality", lambda d: d["primary_driver"]=="multi_tier_quality"),
        # compound
        ("hour>=15 AND num_agree>=2", lambda d: (d["hour_utc"]>=15)&(d["num_agree"]>=2)),
        ("hour>=15 AND ev>=0.5", lambda d: (d["hour_utc"]>=15)&(d["ev_per_dollar"]>=0.5)),
        ("num_agree>=2 AND ev>=0.5", lambda d: (d["num_agree"]>=2)&(d["ev_per_dollar"]>=0.5)),
        ("hour>=15 AND win_prob>=0.55", lambda d: (d["hour_utc"]>=15)&(d["win_prob_deflated"]>=0.55)),
        ("hour>=15 AND symbol!=HYPE", lambda d: (d["hour_utc"]>=15)&(d["symbol"]!="HYPE")),
        ("side==SHORT AND hour>=15", lambda d: (d["side"]=="SHORT")&(d["hour_utc"]>=15)),
        ("side==SHORT AND num_agree>=2", lambda d: (d["side"]=="SHORT")&(d["num_agree"]>=2)),
    ]
    amps = amplifier_search(cell, candidates, cell_name)
    for r in amps[:12]:
        if r["delta_wr"] > 0 and r["retained_pct"] >= 25:
            print(f"  [+{r['delta_wr']:+.1f}% WR] {r['filter']}: kept {r['kept_n']} ({r['retained_pct']:.0f}%) WR={r['kept_wr']:.1f}% ${r['kept_pnl']:.2f}")
    return amps

def hour_utc_investigation(df):
    print("\n=== HOUR-UTC PATTERN INVESTIGATION ===")
    # Global WR by hour
    g = df.groupby("hour_utc").agg(n=("win","count"), wr=("win","mean"), pnl=("pnl","sum"))
    g["wr"]*=100
    print("\n  Global WR by hour_utc:")
    print(g.to_string())
    # bucketed
    g2 = df.groupby("hour_bucket", observed=True).agg(n=("win","count"), wr=("win","mean"), pnl=("pnl","sum"))
    g2["wr"]*=100
    print("\n  Global WR by hour_bucket (4h):")
    print(g2.to_string())
    # split solo vs consensus
    print("\n  By num_agree category × hour>=15:")
    df["_ge15"] = df["hour_utc"]>=15
    g3 = df.groupby(["num_agree","_ge15"]).agg(n=("win","count"), wr=("win","mean"), pnl=("pnl","sum"))
    g3["wr"]*=100
    print(g3.to_string())
    # by symbol
    print("\n  hour>=15 effect by symbol:")
    for sym in df["symbol"].unique():
        for ge in [True,False]:
            sub = df[(df["symbol"]==sym)&(df["_ge15"]==ge)]
            if len(sub)>=3:
                tag = f">=15UTC" if ge else "<15UTC"
                print(f"    {sym} {tag}: n={len(sub)} WR={wr(sub):.1f}% ${dollar(sub):.2f}")
    # funding hours 0/8/16 UTC
    print("\n  Funding-window hypothesis test (hours 0/8/16 ±1):")
    funding_hrs = {0,1,23,8,9,7,16,17,15}
    sub_fund = df[df["hour_utc"].isin(funding_hrs)]
    sub_nofund = df[~df["hour_utc"].isin(funding_hrs)]
    print(f"    near funding: n={len(sub_fund)} WR={wr(sub_fund):.1f}% ${dollar(sub_fund):.2f}")
    print(f"    away funding: n={len(sub_nofund)} WR={wr(sub_nofund):.1f}% ${dollar(sub_nofund):.2f}")
    # US-open bucket
    print("\n  US-session (13-21 UTC) vs Asia-session (0-8 UTC) vs EU (8-13):")
    df["_sess"] = pd.cut(df["hour_utc"], bins=[-1,8,13,21,23], labels=["asia","eu","us","late"])
    g4 = df.groupby("_sess", observed=True).agg(n=("win","count"), wr=("win","mean"), pnl=("pnl","sum"))
    g4["wr"]*=100
    print(g4.to_string())

def kelly_amplifier(df):
    print("\n=== KELLY SIZING AMPLIFIER ===")
    # Does higher ev_per_dollar predict higher realised pnl/trade in winning cells?
    cell_fp = df[(df["regime"]=="trending")&(df["symbol"]!="HYPE")&(df["num_agree"]>=2)]
    if len(cell_fp)<5:
        print("  Golden cell too small")
    else:
        cell_fp2 = cell_fp.copy()
        cell_fp2["ev_q"] = pd.qcut(cell_fp2["ev_per_dollar"], q=min(3, cell_fp2["ev_per_dollar"].nunique()), duplicates="drop")
        g = cell_fp2.groupby("ev_q", observed=True).agg(n=("win","count"), wr=("win","mean"), avg_pnl=("pnl","mean"), total=("pnl","sum"))
        g["wr"]*=100
        print("  Golden cell: ev_per_dollar tiers -> win rate + avg pnl")
        print(g.to_string())

def regime_transition_amplifier(df):
    print("\n=== REGIME-TRANSITION AMPLIFIER ===")
    df_s = df.sort_values("ts").copy()
    df_s["prev_regime"] = df_s["regime"].shift(1)
    df_s["prev_symbol"] = df_s["symbol"].shift(1)
    df_s["transition"] = (df_s["regime"]!=df_s["prev_regime"])
    g = df_s.groupby("transition").agg(n=("win","count"), wr=("win","mean"), pnl=("pnl","sum"))
    g["wr"]*=100
    print("  Global: trade at regime transition vs mid-regime")
    print(g.to_string())
    # within winning cell
    cell = df_s[(df_s["regime"]=="trending")&(df_s["symbol"]!="HYPE")]
    if len(cell)>=5:
        g2 = cell.groupby("transition").agg(n=("win","count"), wr=("win","mean"), pnl=("pnl","sum"))
        g2["wr"]*=100
        print("\n  Within trending+non-HYPE cell:")
        print(g2.to_string())

def main():
    df = load()
    print(f"Total trades loaded: {len(df)}, baseline WR={wr(df):.1f}%, ${dollar(df):.2f}")

    # Cell 1: Winner-Fingerprint golden cell
    c1 = df[(df["regime"]=="trending") & (df["symbol"]!="HYPE") & (df["num_agree"]>=2)]
    run_cell(df, "C1: Winner-Fingerprint (trending & !HYPE & num_agree>=2)",
             (df["regime"]=="trending") & (df["symbol"]!="HYPE") & (df["num_agree"]>=2))
    try_amplifiers(df, "C1", c1)

    # Cell 2: SHORT-side all symbols
    c2 = df[df["side"]=="SHORT"]
    run_cell(df, "C2: SHORT side all-symbols", df["side"]=="SHORT")
    try_amplifiers(df, "C2", c2)

    # Cell 3: Trending regime any side any symbol
    c3 = df[df["regime"]=="trending"]
    run_cell(df, "C3: Trending regime (any symbol/side)", df["regime"]=="trending")
    try_amplifiers(df, "C3", c3)

    # Cell 4: bollinger_squeeze primary
    c4 = df[df["primary_driver"]=="bollinger_squeeze"]
    run_cell(df, "C4: bollinger_squeeze primary driver", df["primary_driver"]=="bollinger_squeeze")
    try_amplifiers(df, "C4", c4)

    # Cell 5: confidence_scorer 2-agree
    c5 = df[(df["num_agree"]==2) & (df["strategies_agree"].apply(lambda t: "confidence_scorer" in t))]
    run_cell(df, "C5: confidence_scorer in 2-agree", (df["num_agree"]==2) & (df["strategies_agree"].apply(lambda t: "confidence_scorer" in t)))
    try_amplifiers(df, "C5", c5)

    hour_utc_investigation(df)
    kelly_amplifier(df)
    regime_transition_amplifier(df)

if __name__ == "__main__":
    main()
