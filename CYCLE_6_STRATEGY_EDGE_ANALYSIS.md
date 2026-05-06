# CYCLE 6: Strategy Edge Analysis
**Date**: 2026-05-06  
**Status**: ANALYSIS IN PROGRESS (Cycle 5 paper trading running in parallel)

## Executive Summary

Analyzed current strategy performance data from `ml_data/strategy_weights.json`. Key finding: **sniper_premium is vastly outperforming the ensemble** (67% WR vs 29% WR).

Multiple strategies are disabled/dead (monte_carlo_zones, trend_breakout, confidence_scorer, multi_tier_quality all at 0% trials).

---

## Part 1: Current Strategy Performance (Historical)

### Ranked by Win Rate

| Rank | Strategy | Wins | Trials | WR% | Weight | Status |
|------|----------|------|--------|-----|--------|--------|
| 1️⃣ | sniper_premium | 20.25 | 30.25 | **67%** | 0.66 | ACTIVE ✓ |
| 2️⃣ | regime_trend | 1.34 | 2.27 | **59%** | 0.55 | ACTIVE (small sample) |
| 3️⃣ | ensemble | 359.88 | 1226.29 | 29% | 0.29 | ACTIVE (large sample) |
| 4️⃣ | bollinger_squeeze | 7.99 | 28.23 | 28% | 0.30 | ACTIVE |
| 5️⃣ | omniscient_integrated | 29.99 | 450.00 | 6.7% | 0.07 | ACTIVE (muted) |
| ❌ | monte_carlo_zones | — | 0 | N/A | 0.30 | DISABLED |
| ❌ | trend_breakout | — | 0 | N/A | 0.30 | DISABLED |
| ❌ | confidence_scorer | — | 0 | N/A | 0.30 | DISABLED |
| ❌ | multi_tier_quality | 0 | 0.015 | 0% | 0.30 | DEAD |

---

## Part 2: Key Findings

### Finding 1: Sniper Premium is the Real Edge (CRITICAL)
**Data**:
- 67% WR over 30 trials
- Weight=0.66 (highest allocated)
- Recent outcomes: 20/20 wins (perfect recent streak)

**Interpretation**:
- Sniper strategy is THE profitable path
- Other strategies should be evaluated against sniper's edge
- Ensemble at 29% WR is dragging down sniper at 67%

**Question**: Is sniper_premium overfit? Or is the ensemble missing context that sniper captures?

### Finding 2: Ensemble is Weak (CRITICAL)
**Data**:
- 29% WR on large sample (1,226 trials)
- Large recent losing streak (15 losses in last 20)
- Weighted 0.29 (second highest, but shouldn't be)

**Interpretation**:
- 29% WR is barely better than random (50% on buy/sell)
- Ensemble voting isn't filtering signals effectively
- Large sample size means this isn't luck (statistically robust)

**Question**: Why is ensemble so weak when Phase 2 baseline had 55% WR?

### Finding 3: Multiple Strategies Are Dead (BLOCKER)
**Data**:
- monte_carlo_zones: 0 trials
- trend_breakout: 0 trials
- confidence_scorer: 0 trials
- multi_tier_quality: 0 outcomes despite setup

**Interpretation**:
- These strategies aren't generating signals
- Possible reasons:
  1. Filters/gates are blocking all signals (regime, confidence, etc.)
  2. Strategies are disabled in code
  3. Market conditions don't support them

**Impact**: Why allocate weight (0.30 default) to disabled strategies?

### Finding 4: Regime Trend Has Potential (GROWTH)
**Data**:
- 59% WR on small sample (2.27 trials)
- Recent: 3 wins in last 5 outcomes
- Weight=0.55 (should be higher if validated)

**Interpretation**:
- Too small sample to trust (2.27 trials is tiny)
- But recent performance is strong (3/5 = 60%)
- Could be real edge if sample size grows

**Question**: Can we increase regime_trend signal flow to build confidence?

---

## Part 3: Per-Symbol Analysis

Data available in `strategy_weights_per_symbol.json`. **Analysis needed**:

- [ ] Which symbols favor sniper_premium?
- [ ] Which symbols favor ensemble?
- [ ] Per-symbol win rates (BTC vs SOL vs ETH vs HYPE)
- [ ] Which symbol/strategy pairs have strongest edges?
- [ ] Which symbol/strategy pairs are breaking (< 30% WR)?

---

## Part 4: Per-Regime Analysis

**Hypothesis**: Strategies have regime-specific edges

**Data needed**:
- How does sniper_premium perform in trending vs ranging?
- Does ensemble improve in choppy markets (where solo filters matter)?
- Does regime_trend only work in trending (obviously)?
- Does bollinger_squeeze only work in ranging?

**Questions to Answer**:
1. trending_bull: Best strategy? (regime_trend? ensemble?)
2. high_volatility: Best strategy? (sniper_premium? bollinger_squeeze?)
3. consolidation: Best strategy? (monte_carlo? multi_tier_quality?)
4. range: Best strategy? (bollinger_squeeze? confidence_scorer?)

---

## Part 5: Root Cause Analysis

### Why is Sniper So Good?

**Possible Reasons**:
1. **Manual signals** - Sniper might be higher quality (human-curated)
2. **Selectivity** - Sniper only trades obvious setups
3. **Sizing** - Sniper might risk less per trade (smaller position scaling)
4. **Context** - Sniper has more information (full market snapshot)
5. **Timing** - Sniper might enter at better prices (less noise)

**Investigation Needed**:
- Compare sniper vs ensemble on identical signals
- Measure slippage, fees, holding times
- Analyze confidence distributions
- Look at entry/exit quality metrics

### Why is Ensemble So Weak?

**Possible Reasons**:
1. **Noise filtering too loose** - confidence_floor=55% is letting in garbage
2. **Voting mechanism flawed** - min_votes=1 allows low-agreement trades
3. **Strategy mix is bad** - Including dead/weak strategies (BB 28% WR)
4. **Per-symbol gates broken** - HYPE strict rules not working
5. **No context** - Ensemble voting ignores regime/volatility/time-of-day

**Investigation Needed**:
- Test ensemble with higher confidence_floor (69%?)
- Test ensemble with min_votes=2 (require agreement)
- Remove dead strategies from ensemble
- Add regime/time-of-day context to voting

### Why Are Some Strategies Dead?

**monte_carlo_zones** (0 trials):
- Possible reason: Monte Carlo signals are filtered out by regime gates
- Test: Is monte_carlo blocked in consolidation/range regimes?
- Fix: Remove regime block if monte_carlo has edge in those regimes

**confidence_scorer** (0 trials):
- Possible reason: Returns confidence assessments, not trade signals
- Test: Is confidence_scorer meant to be voting component, not trade generator?
- Fix: Investigate architecture (might not be a "strategy" in same sense)

---

## Part 6: Recommended Actions

### IMMEDIATE (Before Deployment)

1. **Increase sniper_premium investigation**
   - Task: Analyze 67% WR source (overfit vs real edge)
   - Timeline: 30 minutes
   - Impact: HIGH (understand #1 profitable strategy)

2. **Understand ensemble weakness**
   - Task: Compare ensemble 29% WR to Phase 2 baseline 55% WR
   - Analysis: What changed? Configuration drift?
   - Timeline: 30 minutes
   - Impact: CRITICAL (need to fix #2 strategy)

3. **Revive dead strategies OR remove them**
   - Task: Check if monte_carlo_zones can be unlocked
   - Decision: Activate or remove from weight allocation
   - Timeline: 15 minutes
   - Impact: MEDIUM (clean up unused weight)

4. **Validate regime_trend growth potential**
   - Task: Run targeted backtest with regime_trend
   - Goal: Collect 30+ outcomes to validate 59% WR claim
   - Timeline: 20 minutes
   - Impact: MEDIUM (validate emerging edge)

### AFTER PAPER TRADING COMPLETE

5. **Compare paper trading results to historical**
   - Validate strategy WRs from Cycle 5 paper run
   - Confirm historical weights still accurate
   - Build confidence in deployment decision

6. **Decide strategy portfolio for deployment**
   - Keep sniper_premium (67% WR) at high weight ✓
   - Fix ensemble (currently 29%, should be 55%+)
   - Remove dead strategies or unlock them
   - Enable promising strategies (regime_trend 59%)

---

## Part 7: Decision Matrix

### Go/No-Go Criteria for Each Strategy

| Strategy | Keep If | Remove If | Action |
|----------|---------|-----------|--------|
| sniper_premium | WR ≥ 60% | WR < 40% | ✓ KEEP (67%) |
| ensemble | WR ≥ 50% | WR < 30% | ⚠️ FIX (29%) |
| regime_trend | Sample ≥ 50 + WR ≥ 55% | WR < 40% | 🔍 VALIDATE (59%, n=2.27) |
| bollinger_squeeze | WR ≥ 35% | WR < 25% | ⚠️ MONITOR (28%) |
| monte_carlo_zones | WR ≥ 40% | 0 trials | ❌ UNLOCK OR REMOVE |
| trend_breakout | WR ≥ 40% | 0 trials | ❌ UNLOCK OR REMOVE |
| confidence_scorer | WR ≥ 35% | 0 trials | ❓ CLARIFY ROLE |
| multi_tier_quality | WR ≥ 35% | WR = 0% | ❌ REMOVE |
| omniscient_integrated | WR ≥ 40% | WR < 10% | ❌ MUTE (6.7%) |

---

## Part 8: Next Steps

### Immediate (Next 30 minutes)
1. Analyze sniper_premium edge source
2. Debug ensemble weakness vs Phase 2 baseline
3. Decide monte_carlo fate

### During Paper Trading (Parallel)
4. Run investigation backtests on individual strategies
5. Collect per-symbol breakdown
6. Identify regime-specific edges

### After Paper Trading Complete
7. Compare Cycle 5 paper results to historical
8. Make final deployment decision
9. Prepare strategy portfolio for Cycle 7+

---

## Summary

**Cycle 6 Status**: STARTED

**Key Finding**: Sniper dominates (67% WR) but ensemble underperforms (29% WR). Multiple strategies dead. Significant potential to improve through strategy rebalancing.

**Next**: Complete investigations, finalize strategy portfolio, prepare for deployment.

---

**Report**: 2026-05-06 12:35 UTC  
**Analyst**: Claude Code  
**Confidence**: HIGH (data-driven, clear findings)
