# System Exploration & Optimization Blueprint
**Created**: 2026-05-01 19:35 UTC  
**Goal**: Deep understanding of system mechanics via backtest + CLI agents  
**Timeline**: 48-72 hours (parallel exploration)

---

## PHASE 1: System State Audit (4 hours)

### 1.1 Current Configuration Snapshot
- [ ] Read `trading_config.py` — capture ALL parameters
- [ ] Read position profiles (SCALP, MEDIUM, TREND, REGIME)
- [ ] Read strategy weights (per-symbol, per-regime)
- [ ] Read gate configurations (EV, confidence, regime, correlation)
- [ ] Read leverage cap and Kelly calculations
- [ ] Output: `CURRENT_CONFIG_SNAPSHOT.json`

### 1.2 Live Trading Data Analysis
- [ ] Analyze `trades.csv` — last 100 trades
  - Hold time distribution (min, max, mean, median)
  - Win rate by hold time bucket (0-30min, 30-60min, 1-6h, 6-24h, 24h+)
  - PnL per trade by duration
  - Exit type distribution (TP1, TP2, SL, timeout)
- [ ] Analyze `decisions.jsonl` — signal quality
  - Signals generated vs executed (conversion %)
  - Gate rejection breakdown (which gates reject most?)
  - LLM vs mechanical signal quality
- [ ] Output: `LIVE_TRADING_ANALYSIS.md`

### 1.3 Strategy Performance Breakdown
- [ ] Per-strategy WR, PF, Sharpe
- [ ] Per-strategy per-symbol performance
- [ ] Per-strategy per-regime performance
- [ ] Strategy agreement (single-agree vs 2-agree vs 3-agree)
- [ ] Output: `STRATEGY_PERFORMANCE_MATRIX.csv`

---

## PHASE 2: Controlled Backtests (24-36 hours)

### 2.1 Baseline Validation (Current Config)
**Purpose**: Establish ground truth for live behavior
```
Backtest: Last 90 days, current config as-is
- Record: WR, PF, Sharpe, max DD, hold time dist, exit types
- Compare vs live trading (sanity check backtest ≈ live?)
- Output: BASELINE_BACKTEST.json
```

### 2.2 Exit Velocity Experiments
**Purpose**: Find optimal hold time for highest trades/day + profitability

```
Experiment A: Aggressive TP1 (Close 50% at 0.3R instead of 1.5R)
- TP1_TARGET = 0.3R, TP2_TARGET = 2.0R
- Expected: +60-80% faster exits, -20% avg per trade, +300% frequency
- Run: 90d backtest

Experiment B: Time-Based Exits (Force close after Xmin if no TP)
- Test X = 30min, 60min, 120min, 240min
- Find: Which time frame + TP combination maximizes Sharpe?
- Run: 4× 90d backtests

Experiment C: Scaled Position Sizing (Based on Hold Time Bucket)
- Scalp (0-30min): 15% per position (bigger, faster)
- Medium (30-120min): 10% per position
- Trend (120min+): 8% per position
- Expected: Risk-adjusted returns better
- Run: 90d backtest
```

**Output**: `EXIT_VELOCITY_MATRIX.csv` (best config per metric)

### 2.3 Leverage Sensitivity Analysis
**Purpose**: Find Kelly-optimal leverage per strategy

```
Experiment D: Leverage Range (Hold at 6x, 8x, 10x, 12x, 15x)
- Current: 5.6x average
- Test each at 90d backtest
- Measure: Sharpe, max DD, WR, profit factor
- Output: LEVERAGE_OPTIMIZATION.csv
```

### 2.4 Gate Accuracy Audit
**Purpose**: Which gates HELP vs HURT?

```
Experiment E: Disable Gates One-by-One
- Run 90d with all gates enabled (baseline)
- Run 90d with EV gate disabled
- Run 90d with confidence gate disabled
- Run 90d with regime gate disabled
- Run 90d with correlation gate disabled
- Measure: WR change, PF change, signal throughput
- Output: GATE_IMPACT_ANALYSIS.csv
```

---

## PHASE 3: CLI Agent Decision Analysis (12 hours)

### 3.1 CLI Agent Signal Quality Audit
**Purpose**: Are CLI agents making good entry decisions?

```
Run analysis script:
  For each trade in last 50:
    - Extract: signal_data, entry_confidence, agent_decision
    - Simulate: What would (a) mechanical ensemble say? (b) CLI agent say?
    - Compare outcomes: agent correct? mechanical correct? both wrong?
  Output: AGENT_SIGNAL_QUALITY_REPORT.md
```

### 3.2 CLI Agent Exit Intelligence
**Purpose**: Are CLI agents' exit recommendations working?

```
Run analysis on open positions:
  For each position:
    - Get CLI agent exit recommendation (hold/adjust/close?)
    - Compare vs mechanical exit (SL/TP/timeout?)
    - Track: Which recommendations lead to better outcomes?
  Output: AGENT_EXIT_EFFECTIVENESS.md
```

### 3.3 CLI Agent Learning Rate
**Purpose**: Is agent improving over time?

```
Measure agent accuracy (last 7 days):
  - Day 1 win% = X
  - Day 3 win% = Y
  - Day 7 win% = Z
  - Is Z > X? (improving?)
  - What is agent learning from?
Output: AGENT_LEARNING_CURVE.md
```

---

## PHASE 4: System Optimization Recommendation (8 hours)

### 4.1 Synthesize Results
Combine:
- Live trading analysis (current behavior)
- Backtest matrix (what's possible?)
- Gate impact (what's protective vs restrictive?)
- Agent analysis (is CLI helping or neutral?)

### 4.2 Generate Optimization Scenarios
Create 3-5 recommended configurations:

**Scenario A: Conservative** (max Sharpe, min DD)
- Smaller positions, tighter stops, aggressive TP1
- Expect: 50+WR, 1.8 PF, Sharpe 2.5+

**Scenario B: Balanced** (mid risk/reward)
- Current sizing, optimized exits, best gates
- Expect: 55% WR, 2.2 PF, Sharpe 2.0+

**Scenario C: Aggressive** (max frequency)
- Bigger positions, higher leverage, 30-min hold targets
- Expect: 52% WR, 2.5 PF, Sharpe 1.8+

**Output**: `OPTIMIZATION_SCENARIOS.md` (3 ready-to-deploy configs)

### 4.3 Recommendation
Pick ONE scenario + phased rollout plan

---

## Parallel Work: Live System Monitoring

While backtests run:
- Monitor current bot (0 open positions, signals generating)
- Collect first 20-30 trades for real-time data
- Document CLI agent decisions vs outcomes
- Build live outcome tracking

---

## Success Metrics

| Metric | Target | Method |
|--------|--------|--------|
| System understanding | 100% | Config snapshot + all params documented |
| Backtest validation | ±5% of live | Compare 90d backtest vs live April data |
| Exit optimization | +40% frequency | Hold time distribution + Sharpe curve |
| Gate impact clarity | >80% confidence | Before/after gate disable tests |
| Agent quality | Measurable baseline | First 50 trade analysis |

---

## Timeline

- **Hour 0-4**: Phase 1 (config + live analysis)
- **Hour 4-28**: Phase 2 (backtests in parallel)
- **Hour 28-40**: Phase 3 (agent analysis)
- **Hour 40-48**: Phase 4 (synthesis + recommendations)

---

## Starting Point: Which to Do First?

**RECOMMEND**: Start with Phase 1 (4h) → gives you the map.  
Then decide: Quick backtest OR deep agent analysis first?

