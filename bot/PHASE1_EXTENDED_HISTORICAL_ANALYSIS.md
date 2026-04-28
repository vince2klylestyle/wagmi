# PHASE 1 EXTENDED: HISTORICAL GIT & TRADE ANALYSIS

**Date**: 2026-04-28  
**Status**: In-progress analysis  
**Scope**: Complete git history analysis, trade performance patterns, issue identification

---

## TRADE PERFORMANCE EVOLUTION (205 Live Trades)

### Overall Statistics
- **Total trades**: 205
- **Win rate**: 51.7% (106 wins, 99 losses)
- **Total PnL**: -$3,477.12 (LOSING despite >50% WR)
- **Average win**: +$45.68
- **Average loss**: -$84.03
- **Avg loss / Avg win**: 1.84x (unfavorable R:R)

**Key insight**: System has positive win rate but negative expectation due to bad risk/reward.

### Performance by Symbol
| Symbol | Trades | WR | PnL |
|--------|--------|-----|-----|
| BTC | 53 | 66.0% | -$3,484 |
| HYPE | 46 | 30.4% | -$3.76 |
| SOL | 59 | 50.8% | -$3.90 |
| ETH | 47 | 57.4% | +$14.74 |

**Critical issue**: BTC is the profit killer. Despite 66% WR (excellent), losing $3,484 due to unfavorable R:R. This aligns with memory notes about BTC oversizing.

### Performance Degradation Over Time (5 periods, ~41 trades each)

| Period | Dates | Trades | WR | PnL | Status |
|--------|-------|--------|-----|-----|--------|
| 1 | Mar 25-Apr 4 | 41 | 31.7% | +$3,306 | PROFITABLE (good R:R) |
| 2 | Apr 4-9 | 41 | 39% | -$1,133 | Starting to lose |
| 3 | Apr 9-16 | 41 | 34.1% | -$4,426 | Degrading |
| 4 | Apr 16-26 | 41 | 24.4% | -$3,834 | Poor |
| 5 | Apr 26-27 | 41 | 7.3% | -$2,846 | CATASTROPHIC |

**Degradation pattern**: System started profitable but degraded severely by Apr 26 (7.3% WR).

**Note**: Last 50 trades show 86% WR (much better than period 5), suggesting improvement efforts were working. But final period had catastrophic failure.

---

## TIMELINE: OMNISCIENT INTEGRATION & FAILURE

### Phase 1: Initial System (Mar 25 - Apr 14)
- **Status**: Mechanical ensemble (11 strategies)
- **Trades**: ~100
- **WR**: ~40-50%
- **Result**: PROFITABLE (+$3,306 in first period despite low WR)
- **Key**: Good R:R made up for lower win rate

**Why profitable**: Traders were disciplined about risk/reward. Winners larger than losers.

---

### Phase 2: OMNISCIENT INTEGRATION (Apr 15)

**Commit `4c07b21`**: Deploy FULL omniscient integrated brain (365-day backtest, 91.7% WR)

**What happened**:
1. New omniscient_integrated strategy deployed with 91.7% backtest WR
2. Claims of validation and "production-ready" status
3. System weight optimized for omniscient_integrated (given 1.5x weight)

**The problem**: Backtest ≠ live trading. The strategy:
- Was optimized on historical data
- Worked well in trending conditions (91.7% WR in backtest)
- BUT: Had 0% WR in illiquid and ranging regimes

---

### Phase 3: CRITICAL FIXES (Apr 15-25)

Multiple critical bugs discovered and fixed:

| Commit | Issue | Impact |
|--------|-------|--------|
| `21af3a8` | BUY/SELL instead of LONG/SHORT signal format | Signal parsing broken |
| `913c917` | omniscient_integrated hardcoded as production-only | Forced into live trading |
| `dbffb64` | Regime allowlist blocking signals | Regime gating bypassed |
| `0eb8e4d` | Pattern matching only checking LONG, not BOTH | Half of patterns missed |
| `6763da9` | Symbol selection and time-gating issues | Wrong symbols selected |
| `eec955f` | Signal confidence flow and leverage gate bypass | Leverage not gated properly |

**Pattern**: omniscient_integrated had MANY bugs that required intensive fixing.

---

### Phase 4: INTENSIVE RULE GENERATION (Apr 26)

Commits show "perpetual improvement hourly runs" generating rules:
- `e7d0535`: 3 new rules from live contradiction analysis
- `09cef9b`: 3 new rules, ILLIQUID gate escalated
- `5a9efaf`: 4 new rules, conf calibration freeze
- `bef8f2d`: 2 new rules, 5 critical findings
- `9a41d65`: 5 new rules, critical wiring audit

**Pattern**: System was in "debug mode" generating defensive rules to prevent losses, but the fundamental issue (omniscient_integrated 0% WR in illiquid) was not addressed.

---

### Phase 5: CATASTROPHIC FAILURE (Apr 26-27)

**Trades**: Period 5 (Apr 26-27) shows 7.3% WR (-$2,846)

**What was happening**:
- omniscient_integrated still dominating voting (1.5x weight)
- Market turned illiquid/ranging (perfect storm)
- 0% WR strategy was making most trades
- Defensive rules were not enough
- Bot forced offline after 75 min with no trades (opted to advance to Phase 1)

---

## ROOT CAUSE ANALYSIS

### Why did omniscient_integrated fail?

**Hypothesis**: Strategy was optimized on training data that skewed trending.

Evidence:
- Backtest WR: 91.7% (excellent in trending conditions)
- Live WR in trending: ~50-70% (good)
- Live WR in illiquid: 0% (catastrophic)
- Live WR in ranging: 0% (catastrophic)
- **Illiquid + ranging = 70% of recent signal volume**

**Conclusion**: Strategy was overfit to trending conditions and had no edge in other regimes.

### Why wasn't this caught in backtest?

1. **Backtest data selection**: Likely selected a period with more trending conditions
2. **Regime distribution mismatch**: Live market in late Apr 2026 was illiquid/overbought; backtest data may have been from different market regime
3. **Overfitting to specific market conditions**: Strategy learned patterns specific to training period, not generalizable

### Why did mechanical ensemble (11 strategies) initially work?

- **Diversification**: 11 strategies with different conditions had some balance
- **Good R:R discipline**: Early trades had favorable risk/reward
- **Consensus voting**: min_votes=2 out of 11 meant averaging out bad strategies

When omniscient_integrated (1.5x weight) entered voting:
- It dominated due to high weight
- Consensus broke down
- Bad regime fit was amplified

---

## KEY ARCHITECTURAL ISSUES IDENTIFIED

### 1. **Ensemble Strategy Weighting is Fragile**
Current system:
- 11 strategies with different edge profiles
- omniscient_integrated: 1.5x weight (too high for untested live strategy)
- min_votes=2 out of 11 means 18% agreement threshold (too low for quality gate)
- Veto ratio 1.2 means opposition must be only 1.2x stronger

**Problem**: Single bad strategy with high weight can poison ensemble.

**Solution needed**: 
- Per-symbol strategy weights (e.g., regime_trend weight 0.5x on SOL, 2x on BTC)
- Dynamic weight adjustment based on live performance (Week 4 Swarm Optimizer should handle this)
- Minimum vote count scaled by strategy quality

### 2. **Backtest-Live Gap is HUGE**
Evidence:
- omniscient_integrated: 91.7% backtest WR → 0% live WR in illiquid
- Period 1: +$3,306 profitable
- Period 5: -$2,846 catastrophic

**Root cause**: Backtest conditions ≠ live market conditions

**Solution needed**:
- Live regime detection (Week 1 Regime Agent handles this)
- Regime-conditional backtests (test strategy on each regime separately)
- Cross-validation on out-of-sample periods
- Walk-forward validation (test on future data, not past)

### 3. **LLM Agents Need Live Context**
Phase 1 filtering initiative shows the value:
- Veto omniscient_integrated in illiquid/ranging
- Adjust confidence by regime
- This requires LLM to understand strategy-regime interaction

**Implementation status**:
- ✓ Week 3 deep memory context injection (regime data available)
- ✓ Week 4 Adversary Agent (stress-test thesis with counter-arguments)
- ✓ Week 4 Health Monitor (track agent accuracy)
- ⚠ Phase 1 filtering prepared but not deployed (awaiting API key)

### 4. **Ensemble Voting Assumptions are Wrong**
Current assumption: "More strategies = more robust"

Reality from data:
- Mechanical 11-strategy ensemble with omniscient_integrated: FAILED
- Simple 4-strategy ensemble initially: PROFITABLE
- Adding bad strategy with high weight: DISASTROUS

**Better approach**:
- Quality-weighted voting (better strategies get higher weight)
- Regime-conditional ensemble (different set of strategies for each regime)
- Veto mechanism with high bar (current veto_ratio 1.2 is too lenient)

---

## LESSONS LEARNED

### From Week 1-3 Success
- Mechanical ensemble CAN work if:
  - Risk/reward is good (average win > average loss)
  - Strategies are diversified
  - Weighting is balanced
  - Circuit breakers are in place

### From omniscient_integrated Failure
- Backtest performance does NOT predict live performance
- Strategy optimization is regime-specific
- Market conditions matter more than strategy sophistication
- High weight on untested strategy is dangerous

### From Phase 1 Preparation
- LLM agents add value by:
  - Understanding context (regime, strategy performance)
  - Providing counter-thesis (veto mechanism)
  - Adapting to live market changes
  - Adding regime-awareness to mechanical system

---

## TECHNICAL DEBT & ACTION ITEMS

### CRITICAL (blocks profitability)
1. [ ] **omniscient_integrated regime gating**: Implement Phase 1 filtering or disable strategy
2. [ ] **BTC position sizing**: -$3,484 losses despite 66% WR — reduce position size or disable
3. [ ] **R:R monitoring**: Add early warning if avg loss > 1.5x avg win

### HIGH (improves robustness)
1. [ ] **Per-symbol strategy weights**: regime_trend needs different weight on SOL vs BTC
2. [ ] **Regime-conditional backtests**: Test each strategy on each regime separately
3. [ ] **Walk-forward validation**: Validate on future data (2-week chunks), not past

### MEDIUM (improves efficiency)
1. [ ] **Dynamic strategy weighting**: Use Week 4 Swarm Optimizer to adjust weights per symbol
2. [ ] **Veto threshold tuning**: Current veto_ratio 1.2 may be too lenient
3. [ ] **Min votes by regime**: High volatility may need higher min_votes threshold

### LOW (future-proofing)
1. [ ] **Backtest sensitivity analysis**: Understand which assumptions drive 91.7% WR
2. [ ] **Historical regime analysis**: When does omniscient_integrated work? When does it fail?
3. [ ] **Market regime forecasting**: Can we predict when omniscient_integrated will fail?

---

## NEXT STEPS IN AUDIT

### PHASE 1 Extended (continuing)
- [ ] Analyze Week 2 backend abstraction commits (why was ABC needed?)
- [ ] Understand all 27 critical fix commits
- [ ] Map out which bugs were in code vs. config
- [ ] Identify preventable failures

### PHASE 2 (scheduled)
- [ ] 30-day backtest: Current system vs. omniscient_integrated disabled
- [ ] 90-day backtest: Test Phase 1 filtering effectiveness
- [ ] 1-year backtest: Regime-conditional performance analysis

### PHASE 3 (scheduled)
- [ ] Replay last 60 days through full pipeline
- [ ] Analyze every agent decision (regime → trade → risk → critic → canary)
- [ ] Identify where we skip good trades and take bad ones

### PHASE 4 (scheduled)
- [ ] Stress test: 10x signal volume
- [ ] Failure mode analysis: agent crashes, corrupted data, market halts
- [ ] Recovery testing: restart after failure

---

## CONCLUSION

The WAGMI bot is **architecturally sound** but suffered from:
1. **Untested strategy deployment** (omniscient_integrated without regime validation)
2. **Inadequate weighting management** (1.5x weight on bad-fit strategy)
3. **Backtest-live gap** (91.7% backtest WR vs 0% live WR in illiquid)

**Positive signs**:
- Week 1 initial design was profitable despite low WR
- Week 3-5 infrastructure (deep memory, specialist agents, canary substrate) is solid
- Phase 1 filtering solution is well-designed (just needs deployment)

**Path forward**:
1. Deploy Phase 1 LLM filtering (2 min with API key)
2. Disable or weight-reduce omniscient_integrated until regime-validation complete
3. Implement per-symbol strategy weights
4. Continue audit to find and fix remaining issues

