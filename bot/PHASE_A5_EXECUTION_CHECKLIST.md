# Phase A.5 Execution Checklist
**Trigger**: When Phase A backtest completes  
**Expected time**: ~06:00 UTC  
**Duration**: 3-4 hours to complete all steps  
**Output**: Optimized config ready for Phase B  

---

## Step 1: Extract Agent Learning (15 min)

### 1.1 Extract Learning Agent Outputs
```bash
cd bot

# Extract thesis accuracy from deep_memory
find data/llm/deep_memory -name "*.json" | xargs grep -l "thesis_accuracy" | head -10

# Export to analysis file
jq -s 'group_by(.setup_type) | map({
  setup: .[0].setup_type,
  count: length,
  wr: (map(select(.result=="win")) | length) / length,
  avg_pnl: (map(.pnl_usd) | add) / length
})' < data/llm/deep_memory/trades_*.json > /tmp/learning_by_setup.json

# Print summary
echo "=== Learning Agent Extraction ==="
cat /tmp/learning_by_setup.json | jq '.'
```

### 1.2 Extract Quant Agent Analysis
```bash
# All 9-agent decisions from backtest
tail -3600 data/decisions.jsonl | jq 'select(.quant_agent) | {
  symbol,
  regime: .regime,
  setup_type: .setup_type,
  hour: .timestamp | split("T")[1] | split(":")[0],
  confidence: .overall_confidence,
  result: .result
}' > /tmp/quant_analysis.json

# Group by regime
cat /tmp/quant_analysis.json | jq -s 'group_by(.regime) | map({
  regime: .[0].regime,
  count: length,
  wr: (map(select(.result=="win")) | length) / length,
  avg_confidence: (map(.confidence) | add) / length
})'
```

### 1.3 Extract Regime Agent Accuracy
```bash
# Regime classifications vs actual outcomes
tail -3600 data/decisions.jsonl | jq 'select(.regime_agent) | {
  predicted_regime: .regime_agent.regime,
  actual_regime: .regime,
  symbol,
  outcome: .result,
  confidence: .regime_agent.confidence
}' > /tmp/regime_accuracy.json

# Accuracy by predicted regime
cat /tmp/regime_accuracy.json | jq -s 'group_by(.predicted_regime) | map({
  predicted: .[0].predicted_regime,
  accuracy: (map(select(.predicted_regime == .actual_regime)) | length) / length,
  count: length
})'
```

### 1.4 Extract Time-of-Day Performance
```bash
# Group results by UTC hour
tail -3600 data/decisions.jsonl | jq '.timestamp | split("T")[1] | split(":")[0] as $hour | {
  hour: $hour,
  result,
  pnl: .pnl_usd,
  confidence: .overall_confidence
}' | jq -s 'group_by(.hour) | map({
  hour: .[0].hour,
  count: length,
  wr: (map(select(.result=="win")) | length) / length,
  avg_pnl: (map(.pnl_usd) | add) / length,
  avg_confidence: (map(.confidence | select(. != null)) | add) / length
}) | sort_by(.avg_pnl) | reverse'
```

---

## Step 2: Categorize Discoveries (30 min)

### 2.1 Create Summary Document
Create file: `bot/data/PHASE_A_AGENT_DISCOVERIES.md`

```markdown
# Phase A Agent Discoveries

## Regime-Specific Rules
- [trending_bull]: WR=?, avg_confidence=?
- [trending_bear]: WR=?, avg_confidence=?
- [ranging]: WR=?, avg_confidence=?
- [consolidation]: WR=?, avg_confidence=?
- [high_volatility]: WR=?, avg_confidence=?

## Setup-Specific Rules
- [trend_follow]: WR=?, count=?, avg_pnl=?
- [mean_reversion]: WR=?, count=?, avg_pnl=?
- [standard]: WR=?, count=?, avg_pnl=?

## Time-of-Day Patterns
- [Profitable hours]: 18:00 UTC (+$475), 04:00 UTC (+$130)
- [Losing hours]: 10:00 UTC (-$435), 07:00 UTC (-$448)

## Symbol-Specific Edges
- [BTC]: WR=?, best_regime=trending, worst_regime=ranging
- [ETH]: WR=?, analysis=0% executed (investigate rejection path)
- [SOL]: WR=?, best_setup=trend_follow
- [HYPE]: WR=?, caution=high_volatility, reduced_leverage=recommended

## Confidence Calibration
- [<60%]: WR=?, recommendation=raise_floor
- [60-70%]: WR=?, recommendation=?
- [70-80%]: WR=?, recommendation=?
- [80-90%]: WR=?, recommendation=?
- [90-100%]: WR=?, recommendation=?

## Agent Consensus/Disagreement
- [Regime vs Trade agent disagreement rate]: ?%
- [Trade vs Critic agent veto rate]: ?%
- [Regime agreement accuracy]: ?%
```

### 2.2 Identify Top 3 Optimization Opportunities
```
Opportunity 1: _____ (estimated PnL impact: +$___)
Opportunity 2: _____ (estimated PnL impact: +$___)
Opportunity 3: _____ (estimated PnL impact: +$___)
```

---

## Step 3: Design Config Updates (45 min)

### 3.1 Update .env
Edit `bot/.env` with discoveries:

```bash
# Based on regime-specific WR differences
ENSEMBLE_CONFIDENCE_FLOOR_TRENDING=55      # Lower in profitable regime
ENSEMBLE_CONFIDENCE_FLOOR_RANGING=80       # Higher in dangerous regime
MIN_VOTES_REQUIRED_TRENDING=1              # Solo OK when profitable
MIN_VOTES_REQUIRED_RANGING=3               # Consensus required when risky

# Based on setup-specific performance
ENABLE_MEAN_REVERSION_GATE=true            # Gate 0% WR setup
SETUP_LEVERAGE_TREND_FOLLOW=12.0           # Boost 75% WR setup
SETUP_LEVERAGE_MEAN_REVERSION=2.0          # Minimize losing setup

# Based on time-of-day patterns
ENABLE_TIME_OF_DAY_FILTER=true
TIME_OF_DAY_SKIP_HOURS=10,07               # 10:00 UTC -$435, 07:00 UTC -$448
TIME_OF_DAY_BOOST_HOURS=18,04              # 18:00 UTC +$475, 04:00 UTC +$130

# Based on symbol-specific edges
# (Add per-symbol overrides if applicable)
```

### 3.2 Document Rationale
For each change:
- **Why**: Evidence from agent learning
- **Expected impact**: Estimated PnL improvement
- **Risk**: What could go wrong?

---

## Step 4: Validate Rules Individually (60 min)

### 4.1 Test Regime-Specific Gates
```bash
cd bot
ENSEMBLE_CONFIDENCE_FLOOR_TRENDING=55 \
ENSEMBLE_CONFIDENCE_FLOOR_RANGING=80 \
python run.py backtest --symbols BTC,ETH,SOL,HYPE --days 30 \
  > /tmp/phase_a5_test_regime.log

# Compare to baseline
grep "Net PnL\|Win rate\|Trades executed" /tmp/phase_a5_test_regime.log
```

### 4.2 Test Setup-Specific Leverage
```bash
ENABLE_MEAN_REVERSION_GATE=true \
SETUP_LEVERAGE_TREND_FOLLOW=12.0 \
python run.py backtest --symbols BTC,ETH,SOL,HYPE --days 30 \
  > /tmp/phase_a5_test_setup.log

grep "Net PnL\|Win rate\|Trades executed" /tmp/phase_a5_test_setup.log
```

### 4.3 Test Time-of-Day Filtering
```bash
ENABLE_TIME_OF_DAY_FILTER=true \
TIME_OF_DAY_SKIP_HOURS=10,07 \
python run.py backtest --symbols BTC,ETH,SOL,HYPE --days 30 \
  > /tmp/phase_a5_test_time.log

grep "Net PnL\|Win rate\|Trades executed" /tmp/phase_a5_test_time.log
```

---

## Step 5: Measure Improvement (60 min)

### 5.1 Run Full Phase A.5 Validation (100-day with all optimizations)
```bash
cd bot

# Apply all optimizations together
python run.py backtest --symbols BTC,ETH,SOL,HYPE --days 100 \
  > phase_a5_validation.log

# Extract key metrics
echo "=== Phase A.5 Results ==="
tail -300 phase_a5_validation.log | grep -E "Net PnL|Win rate|Profit factor|Trades executed|Sharpe"
```

### 5.2 Compare to Phase A Baseline
Create comparison file: `bot/data/PHASE_A_VS_A5_COMPARISON.md`

```markdown
| Metric | Phase A | Phase A.5 | Change | Success? |
|--------|---------|-----------|--------|----------|
| Net PnL | -$627.80 | ? | ? | ? |
| Win Rate | 28.6% | ? | ? | ? |
| Profit Factor | 0.66 | ? | ? | ? |
| Trades Executed | 9 | ? | ? | ? |
| Sharpe Ratio | -3.15 | ? | ? | ? |
| Gate Accuracy | 58.9% | ? | ? | ? |

**Success**: Net PnL > 0 AND Win Rate > 50% AND Profit Factor > 1.0
```

---

## Step 6: Iterate or Lock In (30 min)

### If Phase A.5 Succeeds (PnL improved, WR > 50%)
```bash
# Lock in all changes
git add .env trading_config.py
git commit -m "Phase A.5 Success: Applied agent-discovered rules, locked in config"

# Document success
cat > bot/data/PHASE_A5_SUCCESS.md << 'EOF'
# Phase A.5 Success

Optimizations locked in:
- Regime-specific gates
- Setup-specific leverage
- Time-of-day filtering
- (Others as applicable)

Next: Phase B (paper trading validation)
EOF

# Move to Phase B
echo "Ready for Phase B: Paper trading with optimized config"
```

### If Phase A.5 Regresses (PnL worse, WR < 50%)
```bash
# Identify problematic rule
echo "Regression detected. Analyzing..."

# Revert worst-performing rule
git diff HEAD^ # See what changed
git revert HEAD # Undo last commit

# Run again without that rule
SETUP_LEVERAGE_MEAN_REVERSION=5.0  # Revert to default instead of 2.0
python run.py backtest --symbols BTC,ETH,SOL,HYPE --days 30

# Document finding
cat >> bot/data/PHASE_A5_ITERATIONS.md << 'EOF'
## Iteration 2: Reverted mean_reversion_leverage gate
- Result: Still negative
- Analysis: Problem not with setup-specific leverage
- Next: Try regime-specific gates without setup leverage
EOF
```

### If Results Are Mixed
```bash
# Keep winning rules, revert losing ones
# Example: regime-gates helped (+$50), time-gates hurt (-$75)

# Keep: Regime-specific gates
# Revert: Time-of-day filtering

# Test combination
python run.py backtest --symbols BTC,ETH,SOL,HYPE --days 100
```

---

## Phase A.5 Success Criteria

### Minimum Success (proceed to Phase B)
- [ ] Net PnL > 0 (from -$627.80)
- [ ] Win Rate > 50% (from 28.6%)
- [ ] OR Profit Factor > 1.0 (from 0.66)

### Strong Success (high confidence for Phase B)
- [ ] Net PnL > +$200 (35% improvement)
- [ ] Win Rate > 55% (25% improvement)
- [ ] Profit Factor > 1.2 (80% improvement)
- [ ] Trades Executed > 20 (more signal flow)

### Blockbuster Success (ready for Phase C+)
- [ ] Net PnL > +$500 (80% improvement)
- [ ] Win Rate > 60%+
- [ ] Profit Factor > 1.5
- [ ] Trades Executed > 30
- [ ] Gate accuracy > 70%

---

## Timeline

```
06:00 UTC:   Backtest completes, Phase A.5 execution starts
06:15 UTC:   Extract agent learning (this checklist Step 1)
06:45 UTC:   Categorize discoveries (Step 2)
07:30 UTC:   Design config updates (Step 3)
08:30 UTC:   Validate rules individually (Step 4)
09:30 UTC:   Run Phase A.5 full validation (Step 5)
10:30 UTC:   Measure improvement, decide Phase B readiness (Step 6)
11:00 UTC+:  Phase B launch (paper trading) or Phase A.6 (further optimization)
```

---

## Fallback if Things Go Wrong

### Backtest Never Completes
```bash
# Check if it's actually running
ps aux | grep "run.py backtest"

# If hung, kill and restart
pkill -f "run.py backtest"
cd bot && python run.py backtest --symbols BTC,ETH,SOL,HYPE --days 30  # Shorter run
```

### Agent Learning Extraction Fails
```bash
# Check decisions.jsonl exists
ls -lh bot/data/decisions.jsonl

# If empty, agent routing failed
# Check: USE_CLI_LLM=true in .env
# Check: claude --print --output-format json works

# Fallback: Use mechanical ensemble (no agents)
LLM_MODE=0 python run.py backtest --symbols BTC,ETH,SOL,HYPE --days 100
```

### Phase A.5 Results Unclear
```bash
# If metrics are borderline, run 30d + 100d + 30d again
# Variance in small sample might just be luck

python run.py backtest --symbols BTC,ETH,SOL,HYPE --days 30
python run.py backtest --symbols BTC,ETH,SOL,HYPE --days 100
python run.py backtest --symbols BTC,ETH,SOL,HYPE --days 30  # Different time window
```

---

**Checklist prepared**: 2026-04-28  
**Activation**: When Phase A backtest completes  
**Confidence**: High — framework is clear, steps are defined
