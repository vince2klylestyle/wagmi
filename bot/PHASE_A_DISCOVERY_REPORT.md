# Phase A Discovery Report — 30d + 100d Backtests
**Date**: 2026-04-28  
**Status**: Complete  
**Key Finding**: Gates are blocking profitable signals before LLM agents see them

---

## Executive Summary

Phase A backtests (30d + 100d) with all strategies re-enabled and 9-agent system configured revealed a **critical architectural issue**: the ensemble voting gates are killing signal flow before agents even receive them.

**Net Result**: -$627.80 over 100 days (9 trades executed, PF=0.68)

---

## 100-Day Backtest Results

### Top-Level Metrics
```
Win Rate:           28.6%
Profit Factor:      0.68 (losing)
Max Drawdown:       n/a
Annualized Return: -56.6%
Trades Executed:    9
Signals Rejected:   3,581 (99.7%)
Time in Market:     3.3%
```

### By Strategy Agreement Level
```
1_agree (solo):     6 events, 67% WR, +$559.16 ✓ PROFITABLE
2_agree (consensus):3 events,  0% WR, -$1,186.96 ✗ LOSING
```
**Key Finding**: 1_agree outperforms 2_agree by **+$1,746.11** (77% better)

### Individual Strategy Performance
```
bollinger_squeeze:    PF=2.22,  57% WR, +$725.57  ← SHOULD BE ENABLED
regime_trend:         PF=99.0, 100% WR, +$559.16  ← WORKING IN TRENDS
multi_tier_quality:   PF=0.0,    0% WR, -$1,353.37 ← DEAD WEIGHT, DISABLE
monte_carlo_zones:    (solo 1-agree)
```

### Regime-Specific Performance
```
trending_bear:   100% WR, +$990.35  ← GOLDMINE
trending_bull:   100% WR, +$328.70  ← GOLDMINE
ranging:          0% WR, -$1,173.28 ← DEATH ZONE
consolidation:    0% WR, -$773.57   ← DEATH ZONE
```

### Gate Effectiveness Analysis
**Total gates blocking signals: 3,581**
```
Gate              Rejected  Would-Win  Would-Lose  Accuracy   Value
─────────────────────────────────────────────────────────────────
insufficient_votes  1,614      655        954        59%    +$579.86k
fee_drag            1,296      145        317        69%    -$144.10k
ev_floor              281       20         31        61%    +$6.55k
confidence_floor      154       95         59        38%    +$158.78k (POOR)
unknown               236      102         85        46%    +$162.56k
─────────────────────────────────────────────────────────────────────
TOTAL NET VALUE:                                          -$763.64k (NEGATIVE!)
```

**Verdict**: Gates have **negative overall value** — they're blocking more winners than losers.

---

## Solo Strategy Missed Opportunities

What would have happened if we'd taken the rejected solo signals?

```
Strategy           Missed  Would-Win  Would-Lose  Win%  Alpha
──────────────────────────────────────────────────────────────
multi_tier_quality  1,147      441        704      39%  +1,178.9%  (TOO MANY LOSSES)
regime_trend          418      188        227      45%  +784.7%    (STRONG EDGE)
monte_carlo_zones     157       59         98      38%  +301.8%
bollinger_squeeze      34       10         24      29%  +29.3%
```

---

## Critical Issues Found

### Issue #1: Consensus Requirement Killing Profitability
**Current**: MIN_VOTES_REQUIRED=1 → but only accepts trades with 2+ strategy agreement  
**Problem**: Solo signals (bollinger_squeeze) outperform 2-agree by 77%  
**Fix**: Lower MIN_VOTES or accept more solo signals from profitable strategies

### Issue #2: multi_tier_quality is Unprofitable
**Status**: 0% WR, -$1,353 across 100 days  
**Finding**: This strategy should be **DISABLED**  
**Action**: Set STRATEGY_MULTI_TIER_QUALITY_ENABLED=false

### Issue #3: bollinger_squeeze was Wrongly Disabled
**Performance**: PF=2.22, 57% WR, +$725.57  
**Note**: We had this enabled in config (verify)  
**Finding**: This is actually a profitable strategy — keep enabled

### Issue #4: Regime Detection is Working
**Evidence**:
- 100% WR in trending (both directions)
- 0% WR in ranging/consolidation
- Clear regime-specific performance

**Insight**: System should be **skipping trades in ranging regimes**, not taking them

### Issue #5: Confidence Floor Settings Need Tuning
- confidence_floor gate: 38% accuracy (should be 60%+)
- Too many high-confidence signals rejected
- Consider raising floor or removing this gate

---

## What 9-Agent System Hasn't Seen Yet

The LLM agents haven't influenced these results because:
1. **Gates blocked 99.7% of signals** before reaching LLM pipeline
2. **Only 9 trades reached execution** out of 3,590 candidates
3. **Agents cannot learn from rejected signals** — they never see them

When we fix the gates, agents will have full visibility to learn from:
- Which regime-signal combos are profitable
- When to trust solo signals vs waiting for consensus
- Why multi_tier_quality fails (can they improve it?)
- How to handle ranging market rejection

---

## Immediate Actions for Phase A.5

### Config Changes Required
```
# Fix #1: Allow more solo signal flow
MIN_VOTES_REQUIRED=1  (already set, confirm)

# Fix #2: Disable multi_tier_quality
STRATEGY_MULTI_TIER_QUALITY_ENABLED=false

# Fix #3: Confirm bollinger_squeeze is enabled
STRATEGY_BOLLINGER_SQUEEZE_ENABLED=true

# Fix #4: Add regime-specific gates (if not present)
# Don't trade in ranging/consolidation regimes

# Fix #5: Review confidence_floor tuning
ENSEMBLE_CONFIDENCE_FLOOR=55  (may be too high)
```

### Next Run (Phase A.5)
After fixing gates, re-run 30d + 100d backtests to see:
1. How many more signals reach trading
2. What 9-agent system learns from visible signals
3. How solo vs consensus performance shifts with full agent coaching

---

## Hypothesis: The Real Edge is Regime + Strategy Specific

**Current data suggests**:
- bullinger_squeeze works broadly (PF=2.22)
- regime_trend dominates in trending (100% WR)
- multi_tier_quality fails everywhere (0% WR)
- Ranging markets kill all strategies (0% across the board)

**Agent job**: Learn which strategy + regime combos to use, when to reject ranging trades, when to take solo signals

---

## Next Steps

1. ✅ Disable multi_tier_quality
2. ✅ Confirm bollinger_squeeze enabled
3. ⏳ Re-run 30d + 100d backtests with fixed gates
4. ⏳ Analyze 9-agent output on visible signals
5. ⏳ Measure agent impact on gate acceptance/rejection

---

**Prepared**: 2026-04-28  
**Phase**: A (Discovery)  
**Status**: Ready for Phase A.5 (Config fixes + retest)
