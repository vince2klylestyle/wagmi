# Counterfactual Summary — 2026-04-29 (§7.1 of OVERNIGHT_BLUEPRINT)

**Source:** `bot/data/counterfactuals/scenarios.json` (352 resolved scenarios)

## Headline

- **Exit timing (134 scenarios):** counterfactual "exit_at_tp1" beats actual 109/134 = **81%** of the time. Aggregate delta: **+$477.22**.
- **Veto override (218 scenarios):** counterfactual "took the veto'd trade" was **0/218 positive**. Aggregate delta: **-$980.47**. The bot's vetoes are correct.

## Exit timing by (symbol, side)

| Pattern | n | Mean Δ | Total Δ | % Positive |
|---|---|---|---|---|
| SOL_short | 30 | +$6.48 | +$194.28 | 67% |
| HYPE_long | 29 | +$4.89 | +$141.85 | 76% |
| SOL_long | 22 | +$2.39 | +$52.57 | 77% |
| HYPE_short | 6 | +$6.08 | +$36.45 | 67% |
| ETH_long | 19 | +$1.07 | +$20.37 | 95% |
| BTC_long | 16 | +$1.16 | +$18.48 | 100% |
| BTC_short | 7 | +$1.30 | +$9.09 | 100% |
| ETH_short | 5 | +$0.83 | +$4.13 | 100% |

## Conclusions

1. **TP1 underweighting is universal.** Every (symbol, side) shows positive aggregate delta. The trailing stop is over-trailing at TP1.
2. **The biggest misses are on the symbol/sides we're losing money on.** SOL_short and HYPE_long are top-2 by delta — i.e., the trades that go against us would have been profitable if we'd locked in TP1.
3. **Action:** Increase TP1 partial-close fraction. Suggested mechanism: scale partial fraction inversely with confidence (lower-confidence signals take more off at TP1; only high-confidence signals trail to TP2).
4. **Vetoes are working.** Don't loosen Critic agent gates without strong cause — the audit shows zero false negatives.
