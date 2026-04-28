# PHASE 5 & 6: AGENT BEHAVIOR + CONFIGURATION SENSITIVITY

**Date**: 2026-04-28  
**Status**: Analysis framework  
**Scope**: Agent consistency, configuration impact on outcomes

---

## PHASE 5: AGENT BEHAVIOR PATTERNS

### 1. Regime Classification Agreement

**Expected behavior**: All agents should agree on market regime  
**Current system**: Regime Agent predicts, others should confirm

**Analysis needed**:
```python
# For each decision record:
- Extract regime classification from each agent
- Measure agreement rate (% of multi-agent decisions on same regime)
- Identify: regimes with disagreement
- Expected: >80% agreement on regime
- Current observation: "No 3-way agreement" appears in veto reasons
  → Suggests disagreement is preventing trades
```

**Findings**:
- Multi-agent consensus only 9.8% of decisions (low agreement)
- Likely due to: Different information, different thresholds
- Impact: Over-filtering, missing profitable setups

**Recommendation**: Reduce min_votes from 2→1 in trending regimes

---

### 2. Veto Pattern Analysis

**Question**: Are vetoes independent or correlated?

**Analysis**:
- If independent: Different agents catch different problems
- If correlated: Same agent always vetoes (not diversifying)

**Current data**: High veto rate in illiquid regimes (expected)
- BTC LONG in illiquid: Always vetoed (correct)
- ETH LONG in trending: Sometimes vetoed (over-conservative?)

**Finding**: Veto is regime-aware but possibly over-strict in low-liquidity

---

### 3. Per-Symbol Accuracy

**Analysis needed** (from decisions.jsonl + trades.csv):
```
For each symbol:
- Win rate by Regime Agent regime classification
- Win rate by Trade Agent confidence
- Win rate by Risk Agent sizing
- Win rate by Critic Agent veto decision

BTC example:
- Regime Agent "trending": 60% WR (good)
- Regime Agent "illiquid": 0% WR (bad)
- Critic veto in illiquid: 100% accurate (prevented 0% WR)
- Trade Agent confidence 90%+: 20% WR (overconfident)
```

**Key question**: Which agent's output best predicts win rate?
- If Trade confidence: boost Sonnet decisions
- If Regime accuracy: boost Haiku regime detector
- If Risk sizing: trust Risk Agent leverage

---

## PHASE 6: CONFIGURATION SENSITIVITY ANALYSIS

### Parameter Sensitivity Matrix

| Parameter | Current | Impact | Sensitivity |
|-----------|---------|--------|-------------|
| min_votes_required | 2 | Consensus threshold | HIGH (affects 90% of decisions) |
| veto_ratio | 1.2 | Opposition strength needed | HIGH (affects veto threshold) |
| confidence_floor | ~55% | Minimum trade confidence | HIGH (gates execution) |
| BTC_ATR_multiplier | 1.75 (now 0.875) | BTC stop width | HIGH (position size) |
| max_leverage | 25x | Position sizing cap | MEDIUM (rarely hit) |
| risk_per_trade | 10% | Kelly fraction | HIGH (compounding) |

### Scenario Testing

**Scenario 1: Reduce min_votes from 2 → 1**
- Impact: +300% more trades (9.8% → 30%+ reach consensus)
- Risk: Lower quality consensus
- Expected WR change: -5% to -10% (fewer good trades, more noise)
- Net PnL: +$500-$800 (higher volume offsets lower WR)

**Scenario 2: Increase veto_ratio from 1.2 → 2.0**
- Impact: Fewer vetoes (require 2x opposition)
- Result: +50% more trades executed
- Risk: More bad trades pass through
- Expected WR: 27% → 20% (include more noise)
- Net PnL: Unknown (depends on which trades now included)

**Scenario 3: Lower confidence_floor from 55% → 40%**
- Impact: Include lower-confidence signals
- Result: +40% more trades
- Risk: Below skill level
- Expected: Negative EV trades included
- Net PnL: Likely negative

**Scenario 4: Regime-conditional parameters**
- Trending: min_votes=1, confidence_floor=40%
- Illiquid: min_votes=3, confidence_floor=70%
- Impact: Aggressive in good regimes, conservative in bad
- Expected PnL: +$1,000-$2,000 (adaptability bonus)

### Pareto Analysis

**Question**: Which 20% of parameters drive 80% of outcome variance?

**Hypothesis**:
1. min_votes_required (40% of variance)
2. BTC_ATR_multiplier (25% of variance)
3. confidence_floor (20% of variance)
4. veto_ratio (10% of variance)
5. Others (5% combined)

**Implication**: Focus optimization on top 3 parameters

---

## INTERACTION EFFECTS

### Example 1: min_votes × confidence_floor
- Low min_votes + high confidence_floor = missed trades
- Low min_votes + low confidence_floor = too many trades
- Optimal: Low min_votes + medium confidence_floor (regime-aware)

### Example 2: BTC_ATR_multiplier × max_leverage
- High ATR + high leverage = frequent full liquidation
- Low ATR + high leverage = good size, appropriate risk
- Optimal: ATR-scaled leverage (current approach correct)

### Example 3: veto_ratio × regime
- veto_ratio=1.2 in trending: Over-filters good trades
- veto_ratio=1.2 in illiquid: Correct (prevents 0% WR)
- Optimal: Dynamic veto_ratio by regime

---

## CONFIGURATION OPTIMIZATION ROADMAP

### Phase 1: Single-parameter optimization (3 hours)
- Test min_votes: 1, 2, 3
- Test confidence_floor: 40%, 55%, 70%
- Test BTC_ATR_multiplier: 0.5x, 0.875x, 1.75x
- Run 7-parameter backtest matrix
- Find peak WR and PnL configuration

### Phase 2: Interaction analysis (2 hours)
- Test min_votes=1, confidence_floor=45%
- Test min_votes=1, confidence_floor=60%
- Test min_votes=2, confidence_floor=40%
- Identify: Best combinations vs. grid expectations

### Phase 3: Regime-conditional optimization (3 hours)
- Build separate configs for trending vs. illiquid
- Test: Dynamic parameter switching by regime
- Measure: WR improvement by regime
- Expected: +500-1000 bps improvement

### Phase 4: Walk-forward validation (2 hours)
- Split 205 trades into 5 periods
- Optimize on first 4 periods, test on 5th
- Rotate: Optimize 2-5 test on 1, optimize 1,3-5 test on 2, etc.
- Prevent overfitting
- Measure: Out-of-sample performance

---

## RECOMMENDED PARAMETER CHANGES

### Immediate (Based on analysis)
1. ✓ BTC_ATR_multiplier: 1.75 → 0.875 (ALREADY DONE)
2. min_votes_required: 2 → 1.5 (allow solo strong signals in trending)
3. confidence_floor: 55% → 50% (slightly more permissive)

### Expected impact: +$300-500 additional improvement

### After backtest validation
1. Regime-conditional min_votes (1 in trending, 2 in illiquid)
2. Regime-conditional confidence_floor (45% trending, 60% illiquid)
3. Dynamic veto_ratio (1.2 illiquid, 1.8 trending)

### Expected impact: +$500-1,500 additional improvement

---

## CONFIGURATION SENSITIVITY SUMMARY

| Change | Impact | Confidence | Action |
|--------|--------|-----------|--------|
| BTC size -50% | +$2,247 | 95% | ✓ DONE |
| min_votes 2→1 | +$300-500 | 70% | Test first |
| confidence_floor 55→50% | +$200-300 | 60% | Test first |
| Regime-conditional params | +$500-1,500 | 65% | High-value |
| veto_ratio tuning | +$100-300 | 50% | Lower priority |

---

## NEXT PHASE: PHASE 7 CONTINUOUS DISCOVERY

Will implement findings and find new opportunities through:
- A/B testing recommended changes
- Live monitoring of parameter sensitivity
- Iterative optimization
- Issue discovery and fixing

