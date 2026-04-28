# COMPREHENSIVE DISCOVERY ROADMAP (2026-04-28)

> **Philosophy**: Understand the FULL system capability through empirical discovery, not theoretical optimization. All strategies re-enabled. Full LLM agent coaching active. Run ALL phases with comprehensive data-driven learning.

---

## SYSTEM STATE

### Latest Fixes ✅
- **Regime field added to GlobalContext** (c3e346c) - snapshots now complete
- **All strategies RE-ENABLED** (cb42823) - multi_tier_quality, lead_lag, vmc_cipher active
- **Full LLM system ACTIVATED** (cb42823) - all 9 agents coaching, $50/day discovery budget

### Current Configuration
```
STRATEGIES: 3 base + 3 previously-disabled (all active now)
AGENTS: 9 core agents all ENABLED
LLM_MODE: 5 (FULL autonomy)
LLM_FIRST_MODE: true (agents coach all decisions)
LLM_FIRST_DUAL_TRACK: true (learn from divergence)
BUDGET: $50/day for comprehensive discovery
```

---

## PHASE A: BASELINE VALIDATION (30d + 100d + Walk-Forward)

**Goal**: Validate anti-spam configuration & baseline performance with ALL strategies active

**What We're Testing**:
- All 6 strategies ensemble voting
- 9-agent coaching on each signal
- Learn which strategy combos actually work
- Discover regime/symbol specificity

**Commands**:
```bash
cd bot
# Quick validation: 30-day backtest
python run.py backtest --symbols BTC,ETH,SOL,HYPE --days 30

# Full dataset: 100-day backtest
python run.py backtest --symbols BTC,ETH,SOL,HYPE --days 100

# Out-of-sample validation: walk-forward
python cli.py --mode walkforward --days 120 --symbols BTC,ETH,SOL,HYPE
```

**Success Criteria**:
- Win rate: >50% (agents coaching should improve this)
- Profit factor: >1.5
- Sharpe: >0.5
- Per-strategy breakdown: See which actually works
- Agent veto accuracy: Should improve from baseline

**Discovery Targets**:
- [ ] Which previously-disabled strategy performs best?
- [ ] Agent veto accuracy on each strategy
- [ ] Regime-specific strategy performance
- [ ] Symbol-specific edges (BTC vs SOL vs ETH vs HYPE)
- [ ] Confidence calibration by strategy
- [ ] Why lead_lag failed before (can agents fix it?)

---

## PHASE B: STRATEGY-LEVEL DISCOVERY (4-6 hours)

**Goal**: Deep-dive into each strategy's performance WITH agent coaching

**What We're Learning**:
- Multi-Tier Quality: When/why it works? (was PF 0.82, now has agent coaching)
- Lead-Lag: Under what conditions? (was 0% WR, let agents discover patterns)
- VMC Cipher: Is it regime-specific? (was 5% WR)
- Confidence floor optimization by strategy
- Which signal combos work best

**Analysis**:
```bash
# Per-strategy performance analysis
cd bot
python tools/strategy_analyzer.py --symbols BTC,ETH,SOL,HYPE

# Agent coaching impact analysis
python tools/agent_coaching_impact.py --backtest-period 100d

# Confidence calibration by strategy
python tools/confidence_by_strategy.py
```

**Discovery Targets**:
- [ ] Multi-Tier Quality: regime-specific wins?
- [ ] Lead-Lag: time-of-day edge? symbol-specific?
- [ ] VMC Cipher: volatility-dependent?
- [ ] Confidence calibration: which strategies over-/under-estimate?
- [ ] Agent coaching ROI: how much do agents improve each strategy?
- [ ] Strategy combinations that synergize vs compete

---

## PHASE C: EXECUTION DISCOVERY (3-4 hours)

**Goal**: Understand execution quality, discover hidden optimization opportunities

**What We're Testing**:
- Position sizing: Is ATR-based optimal or can agents improve?
- Leverage allocation: Which setups deserve more leverage?
- Stop loss placement: Current ATR multiples working?
- Entry timing: Market vs limit orders, entry delays
- Trailing stop effectiveness: Are we exiting too early/late?
- Fee impact: Are we accounting for it correctly?

**Deep Dives**:
```bash
# Execution analysis
python tools/execution_quality_analysis.py --period 100d

# Position sizing impact
python tools/sizing_sensitivity_analysis.py --leverage-range 1x-20x

# Entry/exit timing analysis
python tools/entry_exit_timing.py --symbols BTC,ETH,SOL,HYPE

# Fee drag calculation
python tools/fee_drag_analysis.py
```

**Discovery Targets**:
- [ ] Current execution quality baseline
- [ ] How much is lost to slippage vs fees?
- [ ] Optimal leverage by setup type
- [ ] Entry timing patterns (first candle vs scalp)
- [ ] Trailing stop effectiveness per regime
- [ ] Agent suggestions on execution improvements

---

## PHASE D: PAPER TRADING VALIDATION (48-72 hours)

**Goal**: Validate backtest results reproduce on live market data with full agent coaching

**Setup**:
```bash
cd bot
# .env already set to ENVIRONMENT=paper, $10k starting equity
python run.py paper
```

**Monitoring**:
- Live signal frequency (target: 2-4 trades/day)
- Win rate per trade profile (SCALP vs MEDIUM vs TREND)
- Fee drag as % of gross PnL
- Circuit breaker activations
- Agent veto accuracy (should be 20-30% healthy)
- Agent disagreement patterns (where do LLM and mechanical differ?)
- Learning system: What is it discovering?

**Live Discovery Targets**:
- [ ] Do backtest results match live? (within ±15%)
- [ ] Which strategy dominates in live markets?
- [ ] Agent veto accuracy - are vetoed trades actually losers?
- [ ] Learning Agent: What patterns are being extracted?
- [ ] Are previously-disabled strategies being selected in live trading?
- [ ] Where is ensemble confidence misaligned with outcomes?

---

## PHASE E: LLM AGENT OPTIMIZATION (5-7 days)

**Goal**: Measure LLM value, discover agent-specific strengths/weaknesses

**What We're Discovering**:

### 1. Regime Agent Accuracy
```bash
# Regime classification accuracy vs actual regimes
python tools/regime_agent_accuracy.py --period 7d

# Regime transition prediction
python tools/regime_transition_analysis.py
```

### 2. Trade Agent Quality
```bash
# Trade thesis accuracy per regime/symbol
python tools/trade_agent_quality.py --by-regime --by-symbol

# Veto pattern analysis
python tools/trade_agent_veto_patterns.py
```

### 3. Critic Agent Effectiveness
```bash
# Veto accuracy: saved trades vs missed trades
python tools/critic_veto_accuracy.py

# Counter-thesis quality
python tools/counter_thesis_analysis.py
```

### 4. Risk Agent Sizing
```bash
# Sizing recommendations vs actual positions
python tools/risk_agent_sizing.py

# Leverage gate effectiveness
python tools/leverage_gate_analysis.py
```

### 5. Learning Agent Discoveries
```bash
# What patterns are being extracted?
python tools/learning_agent_discoveries.py --period 7d

# Thesis accuracy tracking
python tools/thesis_accuracy.py
```

**Discovery Targets**:
- [ ] Regime Agent accuracy by regime type (trend vs range vs panic)
- [ ] Trade Agent veto rate per signal type
- [ ] Critic Agent: veto accuracy >60%?
- [ ] Risk Agent: optimal leverage suggestions
- [ ] Learning Agent: top discoveries by symbol/regime
- [ ] Multi-agent agreement: where do they diverge?
- [ ] Cost vs value: Is $50/day budget justified?

---

## PHASE F: GO LIVE CONSERVATIVE (2-4 weeks)

**Goal**: Live trading with proven agent coaching, strict risk management

**Conservative Config**:
```
ENVIRONMENT=production
STARTING_EQUITY=$5,000 (prove edge at real money)
RISK_PER_TRADE=0.01 (1% risk - half of paper)
MAX_LEVERAGE=3.0 (conservative vs 25x backtest)
MIN_VOTES_REQUIRED=3 (tighter consensus for real money)
MAX_OPEN_POSITIONS=2 (concentrate on best setups)
CIRCUIT_BREAKER_DAILY_LOSS_PCT=0.05 (stop at 5% loss)
```

**Live Monitoring**:
- PnL curve vs paper results
- Agent veto accuracy under pressure
- Learning system responsiveness
- Which agent contributed most to wins/losses
- Regime detection accuracy in real time

**Discovery Targets**:
- [ ] Live results within ±15% of paper
- [ ] Which agent reduced losses most?
- [ ] How does agent coaching change under pressure?
- [ ] Is the edge real or was it backtest overfitting?
- [ ] Agent improvements: what's working?

---

## PHASES G-∞: CONTINUOUS DISCOVERY & SCALE

**Beyond Phase F** - never stop discovering:

### G. Strategy Discovery
```bash
# What if we added these strategies?
# - Order flow (CVD, VWAP, BB squeeze)
# - Funding rate mean reversion
# - Cross-asset correlation signals
# - Time-of-day patterns
# - Volatility surface analysis

python tools/strategy_discovery_engine.py --candidate-strategies 5
```

### H. Agent Optimization
```bash
# Can agents improve themselves?
# - Prompt engineering via learning
# - Agent model selection (which model performs best?)
# - Agent inter-communication
# - Multi-agent ensemble weighting

python tools/agent_self_optimization.py
```

### I. Symbol & Regime Specialization
```bash
# Separate agents per symbol? Per regime?
# Deep specialization vs general-purpose

python tools/specialization_analysis.py --by-symbol --by-regime
```

### J. Real-Time Adaptation
```bash
# Can the system adapt during market regime shifts?
# Learn new patterns as they emerge
# Forget outdated patterns

python tools/real_time_adaptation_analysis.py
```

### K. Cross-Market Intelligence
```bash
# Can agents predict moves across assets?
# Lead-lag relationships
# Crypto-wide sentiment signals

python tools/cross_market_analysis.py
```

---

## KEY INSIGHT: Why This Approach Works

### Old Approach (Pre-Discovery)
```
Strategy A: 0% WR → DISABLE
Strategy B: 5% WR → DISABLE  
Result: Missed entire classes of trades agents could improve
```

### New Approach (Comprehensive Discovery)
```
Strategy A: 0% WR baseline, but:
  - Agent coaching: +15% WR
  - Regime-specific: 75% WR in trends
  - Symbol-specific: 85% WR on SOL SHORT
  Result: VALUABLE when conditions are right, agents learn to find them

Strategy B: 5% WR baseline, but:
  - Hidden regime edge: 40% WR in ranging
  - Time-of-day pattern: 65% WR at 14:00-20:00 UTC
  - Correlation with lead indicator: 72% WR when X precedes it
  Result: Discover through systematic testing + agent coaching
```

---

## SCHEDULE & MILESTONES

| Phase | Timeline | Completion Check |
|-------|----------|-----------------|
| **A** | 1 week | 30d + 100d + WF backtests done, agent metrics logged |
| **B** | 1 week | Per-strategy analysis complete, discovery targets answered |
| **C** | 1 week | Execution quality baseline established |
| **D** | 1 week | 72-hour paper validation, agent coaching verified |
| **E** | 2 weeks | Agent optimization complete, cost vs value measured |
| **F** | 4 weeks | Live trading proven, edge validated at real money |
| **G∞** | Ongoing | Continuous discovery, scaling, specialization |

**Total Time to First Real Dollar**: 6-8 weeks with full discovery

---

## SUCCESS DEFINITION

✅ **System is "understood"** when:
1. We've tested all strategy combos systematically
2. Agents identify regime/symbol/time specificity for each strategy
3. Backtest matches paper within ±15%
4. Paper matches live within ±15%
5. Live PnL is positive with $5k real capital
6. We can explain WHY each strategy works (under what conditions)
7. Agent coaching measurably improves outcomes
8. Learning system discovers new patterns continuously

---

## NEXT IMMEDIATE STEP

**Phase A Backtests** - Run this week:
```bash
cd bot
# Monitor these metrics:
# - Per-strategy WR (which strategy wins?)
# - Agent veto accuracy (are they right?)
# - Regime-specific performance
# - Symbol-specific edges

python run.py backtest --symbols BTC,ETH,SOL,HYPE --days 100
```

Then analyze: **Which previously-disabled strategy performs best with agent coaching?**

This answers the core question: "Were these strategies actually bad, or just bad WITHOUT the LLM brain?"

---

**Prepared**: 2026-04-28  
**Philosophy**: Empirical discovery with full system intelligence  
**Status**: READY FOR PHASE A EXECUTION

Let's understand what this system is truly capable of. 🚀
