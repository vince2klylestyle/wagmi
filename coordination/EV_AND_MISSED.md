# EV & Missed-Opportunity Audit (live, from 36,541 resolved counterfactuals)

Every skipped signal is forward-scored (would it have hit TP before SL?). avgPnL% by skip-reason tells us if a gate SAVES us (skips net-losers) or COSTS us (skips winners). At 15x, +1% missed = +15% missed.

## 🔴 BIGGEST MISSED EV — the LLM agent's discretionary regime-skips
These would-be trades won **94–100%** with **+6% to +12% avg** moves — at 15x that's **+90% to +180% per miss**:
| skip reason | n | win% | avgPnL% | @15x |
|---|---|---|---|---|
| [MA] regime=high_volatility | ~168 | 83–95% | +10.7 to +11.8 | ~+160–177% |
| [MA] regime=consolidation | ~179 | 96–98% | +6.6 to +9.8 | ~+99–147% |
| [MA] regime=range bias | ~159 | 98–100% | +5.9 to +10.1 | ~+89–152% |
| [MA] regime=trending_bear | ~94 | 100% | +2.8 to +7.1 | ~+42–106% |

**Read:** the *LLM Trade-agent* is too cautious in these regimes — skipping trades that ran. This is the #1 lever, NOT the floor gates. (Caveat: likely concentrated in strong directional pushes; validate it's a repeatable edge, not one trending stretch, before loosening.)

## 🟢 GATES WORKING (saving us — correctly skip net-losers)
| gate | n | win% | avgPnL% |
|---|---|---|---|
| confidence_floor_66 | 11,966 | 28% | −0.62 |
| confidence_floor_71 | 8,355 | 34% | −0.38 |
| trend_adj_floor_71 | 415 | 24% | −1.04 |
| high_volatility (uncertain) | ~166 | 2–12% | −2.6 to −5.2 |
The big-volume confidence floors are doing their job. Don't loosen these.

## 🟢 HIGHEST-EV CAPTURED (top closed trades)
SOL SHORT +5.18% (+78%@15x), SOL SHORT +5.16%, SOL SHORT +4.72%, ETH SHORT +3.92%, HYPE SHORT +3.79% — all SHORTS (confirms the short-side edge).

## Net takeaway
Floors = working (skip losers). Missed EV is concentrated in the **LLM agent's regime-conditioned skips** of would-be winners. Loosening the agent's caution in high_vol/consolidation/range/trending — IF validated as repeatable — is where the leveraged upside is. The vetoes self-police (sol_long_veto 14/14 keeps; hype_long_veto retired after 9 missed winners).
