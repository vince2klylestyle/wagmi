# Phase A.5 Optimization Plan
**Status**: Pending Phase A backtest completion  
**Trigger**: When PHASE_A_AGENT_LEARNING_FRAMEWORK agents extract patterns  
**Goal**: Apply agent-discovered rules to improve config, re-validate with optimized settings  

---

## Discovery-to-Optimization Pipeline

### Step 1: Extract Agent Learning (Post-Backtest)
After 100-day backtest completes, harvest agent outputs:

```bash
# Extract from deep_memory (Learning Agent thesis accuracy)
find bot/data/llm/deep_memory -name "*.json" -type f | xargs grep -l "thesis_accuracy"

# Extract from decisions.jsonl (all 9-agent decisions)
tail -1000 bot/data/decisions.jsonl | jq '.agents | keys[]' | sort | uniq -c

# Extract from backtest logs
grep "Agent.*recommendation\|Agent.*learned\|Agent.*discovered" backtest_phase_a_with_agents.log
```

### Step 2: Categorize Discoveries
Group learnings by type:

**A. Regime-Specific Rules** (Regime Agent + Quant Agent)
```
Example outputs to look for:
- "trending_bear: 100% WR, recommend high confidence (70%+)"
- "ranging: 0% WR, recommend SKIP or MIN_VOTES=3"
- "consolidation: 0% WR, recommend restrict leverage"
```

**B. Setup-Specific Rules** (Learning Agent)
```
Example outputs to look for:
- "trend_follow: 75% WR in backtest, profitable setup type"
- "mean_reversion: 0% WR, disable or gate strictly"
- "standard: 50% WR, mediocre, consider weighting down"
```

**C. Time-of-Day Patterns** (Quant Agent)
```
Example outputs to look for:
- "18:00 UTC: +$475 avg win (+$490, +$475, -$356 bundle)"
- "10:00 UTC: -$435 avg loss (largest loser)"
- "04:00 UTC: +$130 avg win (small but consistent)"
```

**D. Symbol-Specific Edges** (Trade Agent + Learning Agent)
```
Example outputs to look for:
- "BTC: 100% WR in trending, 0% in ranging → gate by regime"
- "SOL: 67% WR overall, solid performer, keep enabled"
- "HYPE: 33% WR, needs caution, recommend reduced leverage"
- "ETH: 0% executed, investigate: why rejected pre-trade?"
```

**E. Confidence Calibration** (Critic Agent + Learning Agent)
```
Example outputs to look for:
- "<60% confidence: 0% WR, raise floor to 70%"
- "60-70% confidence: mixed, consider 75% floor"
- "90-100% confidence: profitable, lower floor here to capture"
```

### Step 3: Design Config Updates

Based on discoveries, design targeted improvements:

#### A. Regime-Specific Gates
**Current**: Single ENSEMBLE_CONFIDENCE_FLOOR=60  
**Proposed**: Per-regime floors

```python
# .env additions
ENSEMBLE_CONFIDENCE_FLOOR_TRENDING=55      # Lower in profitable regime, capture more
ENSEMBLE_CONFIDENCE_FLOOR_RANGING=80       # Higher in dangerous regime, be selective
ENSEMBLE_CONFIDENCE_FLOOR_CONSOLIDATION=80 # Avoid consolidation entirely
MIN_VOTES_REQUIRED_TRENDING=1              # Solo signals OK in trending
MIN_VOTES_REQUIRED_RANGING=3               # Require consensus in ranging
```

#### B. Setup-Specific Leverage
**Current**: Fixed leverage tiers by confidence  
**Proposed**: Per-setup leverage scaling

```python
# trading_config.py additions
SETUP_LEVERAGE_TREND_FOLLOW=12.0      # 75% WR, boost leverage
SETUP_LEVERAGE_MEAN_REVERSION=2.0     # 0% WR, minimal leverage (or disable)
SETUP_LEVERAGE_STANDARD=5.0           # 50% WR, moderate
ENABLE_MEAN_REVERSION_GATE=true       # Gate mean_reversion setup entirely
```

#### C. Symbol-Specific Filters
**Current**: Same risk per symbol  
**Proposed**: Per-symbol enable/risk/max_positions

```python
# .env additions (per CLAUDE.md .overrides pattern)
BTC_ENABLED=true_trending_only        # 100% WR in trending
SOL_ENABLED=true                      # 67% WR, solid
HYPE_ENABLED=true_with_caution        # 33% WR, reduced leverage
ETH_ANALYSIS_NEEDED=true              # 0% executed, investigate rejection path
```

#### D. Time-of-Day Gating
**Current**: No time-of-day filtering  
**Proposed**: Profitable hours boost, losing hours skip

```python
# .env additions
ENABLE_TIME_OF_DAY_FILTER=true
TIME_OF_DAY_PROFITABLE_HOURS=18,04    # 18:00 UTC +$475, 04:00 UTC +$130
TIME_OF_DAY_LOSING_HOURS=10,07        # 10:00 UTC -$435, 07:00 UTC -$448
TIME_OF_DAY_BOOST_CONFIDENCE=0.95     # Lower floor 5% in profitable hours
TIME_OF_DAY_PENALTY_CONFIDENCE=1.10   # Raise floor 10% in losing hours
```

#### E. Gate Threshold Optimization
**Current**: gates have -763% value (blocking winners)  
**Proposed**: Loosen gates where agents found false positives

```python
# .env adjustments (based on gate analysis from Phase A)
ENSEMBLE_CONFIDENCE_FLOOR=55          # Lower from 60 (insufficient_votes blocking winners)
# But also:
CONFIDENCE_FLOOR_IN_RANGING=80        # Higher in dangerous regime
CONFIDENCE_FLOOR_IN_TRENDING=50       # Lower in profitable regime
```

### Step 4: Validate Individual Rules (Phase A.5 Test)

Before applying all changes, test each rule in isolation:

```bash
# Test 1: Regime-specific gates only
cd bot
ENSEMBLE_CONFIDENCE_FLOOR_TRENDING=55 \
ENSEMBLE_CONFIDENCE_FLOOR_RANGING=80 \
python run.py backtest --symbols BTC,ETH,SOL,HYPE --days 100

# Test 2: Setup-specific leverage only
SETUP_LEVERAGE_TREND_FOLLOW=12.0 \
ENABLE_MEAN_REVERSION_GATE=true \
python run.py backtest --symbols BTC,ETH,SOL,HYPE --days 100

# Test 3: Time-of-day filtering only
ENABLE_TIME_OF_DAY_FILTER=true \
TIME_OF_DAY_PROFITABLE_HOURS=18,04 \
TIME_OF_DAY_LOSING_HOURS=10,07 \
python run.py backtest --symbols BTC,ETH,SOL,HYPE --days 100
```

### Step 5: Measure Improvement

Compare Phase A.5 results vs Phase A baseline:

```
Metrics to track:
- Net PnL: -$627.80 (Phase A) → ? (Phase A.5)
- Win Rate: 28.6% (Phase A) → ? (Phase A.5)
- Profit Factor: 0.66 (Phase A) → ? (Phase A.5)
- Trades Executed: 9 (Phase A) → ? (Phase A.5)
- Signals Reaching Trade: 9 / 3,590 = 0.25% (Phase A) → ? (Phase A.5)
```

**Success Criteria**:
- Net PnL > 0 (positive)
- Win Rate > 50%
- Profit Factor > 1.0
- Trades Executed > 20 (more signal flow)
- Gate accuracy < 0% (gates helping, not hurting)

### Step 6: Iterate

If Phase A.5 improves:
1. Lock in best changes
2. Run Phase A.6 with next set of optimizations
3. Continue until converged (PnL plateaus)

If Phase A.5 regresses:
1. Revert problematic rule
2. Analyze why agent learning failed
3. Refine rule design, try again

---

## Expected Timeline

```
Now (04:00 UTC):           Phase A backtest with agents running
~06:00-06:30 UTC:          Backtest completes
~06:30-07:00 UTC:          Extract agent learning outputs
~07:00-08:00 UTC:          Design config updates (this document's output)
~08:00-08:30 UTC:          Validate rules individually
~08:30-10:30 UTC:          Phase A.5 validation backtests (3 × 100-day runs)
~10:30-11:00 UTC:          Measure improvement
~11:00 UTC+:               Lock in changes, plan Phase B
```

---

## Success Indicators

**Agent learning is working if**:
1. Agents extract regime-specific patterns (trending vs ranging rules)
2. Setup-specific rules emerge (trend_follow vs mean_reversion)
3. Time-of-day patterns identified (profitable/losing hours)
4. Symbol-specific edges discovered (BTC 100%, HYPE 33%)
5. Confidence calibration corrected (high confidence profitable, low unprofitable)

**Phase A.5 is successful if**:
1. Net PnL improves (target: +$100 to +$500)
2. Signal flow increases (target: 15-30 trades executed)
3. Win rate improves (target: >50%)
4. Gates shift from negative to positive value

**If Phase A.5 fails**:
1. Agents didn't learn correctly (check deep_memory/decisions.jsonl)
2. Rules extracted are too aggressive/conservative (tune thresholds)
3. Regime classification unreliable (verify Regime Agent performance)
4. Skip to Phase B with mechanical ensemble, collect more live data

---

## Philosophy

This is not parameter optimization (blind sweeping).  
This is **translation of empirical discovery into executable rules**.

Agents learn what works (regime_trend in trending), agents learn what fails (multi_tier_quality always), agents learn what's conditional (bollinger_squeeze works but multi_tier_quality hurts when paired).

Phase A.5 takes those discoveries and hardcodes them into the config as regime-specific, setup-specific, symbol-specific rules.

Phase B takes the next layer: hypothesis generation, new strategy testing, edge discovery.

---

**Document prepared**: 2026-04-28 04:45 UTC  
**Activation**: When Phase A backtest completes (expected ~06:00 UTC)  
**Next milestone**: Phase A.5 success validation (target ~11:00 UTC)
