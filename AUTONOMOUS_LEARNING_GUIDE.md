# Autonomous Learning Guide
**Created**: 2026-04-28  
**Status**: Cycle 1 Running (365-day backtest)  
**Goal**: Enable agents to discover exact system wiring through empirical discovery

## Quick Start

### Monitor Current Progress
```bash
cd bot && python learning_dashboard.py
```

### Check Cycle 1 Status
```bash
tail -f learning_cycle_1.log
# or
tail -f data/agent_knowledge_base.json
```

### When Cycle 1 Completes
```bash
cd bot && python continuous_learning_orchestrator.py
# Runs 5 continuous cycles (5 × 365 days = 5 years of data)
```

## Architecture Overview

### 4-Module Pipeline

#### Module 1: autonomous_learning_loop.py
**Purpose**: Orchestrate backtests and extract signal data
**Key Methods**:
- `run_backtest()` → Execute year-long backtest
- `extract_signal_data()` → Parse output for all signals/outcomes/regimes/setups
- `agent_analyze_patterns()` → Create agent-readable summaries
- `update_knowledge_base()` → Save to persistent JSON
- `run_learning_cycle()` → One complete cycle (backtest → extract → analyze → save)

**Output**: `data/backtest_results/cycle_N_*.json`, `data/agent_knowledge_base.json`

#### Module 2: agent_learning_harness.py
**Purpose**: Claude agents analyze extracted data
**Key Methods**:
- `prepare_agent_context()` → Build comprehensive context for agents
  - Signal generation stats
  - Regime breakdown (with WR, quality assessment)
  - Setup breakdown (with WR, quality assessment)
  - System architecture explanation
  - Signal quality factors
- `run_agent_learning()` → Invoke Claude CLI with 6-question analysis
- `save_learning_insights()` → Persist agent analysis
- `build_agent_knowledge()` → Consolidate patterns across cycles

**Output**: Agent analysis saved to knowledge base

#### Module 3: continuous_learning_orchestrator.py
**Purpose**: Run multiple cycles in sequence
**Key Methods**:
- `run_continuous_cycles()` → Execute 5+ cycles
- Displays accumulated patterns after each cycle
- Builds compounding knowledge

**Output**: 5-cycle execution with dashboard updates

#### Module 4: learning_dashboard.py
**Purpose**: Real-time monitoring
**Key Methods**:
- `show_status()` → Display file counts, latest runs
- `show_learnings()` → Display discovered patterns
- `show_next_steps()` → Show progress and next actions

## What Agents Learn

### Regime Understanding
**Question**: "Which regimes are truly profitable? Why?"

Agents analyze across all regimes:
- **trending_bull**: How does this perform? Consistent?
- **trending_bear**: Different from bull?
- **ranging**: Profitable at all?
- **consolidation**: When does it work?
- **volatile**: Too risky? Unexploited edge?
- **unknown**: Learning vs gating?

**Output**: `regime_patterns` in knowledge base with avg_wr, consistency, recommendations

### Setup Quality Analysis
**Question**: "Which setups work in which regimes?"

Agents discover:
- **trend_follow**: Works consistently? Which regimes best?
- **mean_reversion**: Truly unprofitable or conditional?
- **standard**: Baseline performance?
- **unknown**: Treat as signal or gate?

**Output**: `setup_patterns` with conditional success rates by regime

### Signal Generation Patterns
**Question**: "When does solo signal outperform consensus?"

Agents map:
- Solo signal performance vs confidence levels
- When does multi-strategy agreement help?
- When does veto prevent wins?
- Confidence calibration per regime/setup

**Output**: `confidence_calibration` curves

### System Wiring Insights
**Question**: "How do regime + setup + strategy interact?"

Agents build causal models:
- "ETH_LONG trending_bull = 75% WR consistently"
- "SOL_SHORT ranging = 15% WR, gate it"
- "Hour 18-22 UTC is -5% across all conditions"
- "After win: re-entry in next 60min fails 70%"

**Output**: `hypothesis_tracker` with validation confidence

### Edge Discovery
**Question**: "What edges exist by symbol/time/regime/setup?"

Agents quantify:
- Symbol-specific edges (BTC vs ETH vs SOL)
- Time-of-day patterns (robust across regimes?)
- Regime-setup combinations (highest WR?)
- Strategy interactions (which pair best?)

**Output**: `symbol_edges`, `temporal_patterns` with evidence counts

### Agent Coaching Opportunities
**Question**: "Where should agents focus effort?"

Agents identify:
- High-uncertainty regions (need more data)
- Easy wins (already validated edges)
- Risk zones (where we lose most)
- Coaching priorities (biggest ROI improvements)

**Output**: Recommendations prioritized by expected impact

## 5-Cycle Roadmap

### Cycle 1: Baseline (365 days)
**Goal**: Validate pipeline, establish baseline understanding
**Expected Results**: 
- 500-1,000 trades captured
- Regime/setup performance mapped
- First agent learnings recorded

### Cycle 2: Regime Understanding (365 days)
**Goal**: Deep regime analysis
**Expected Results**:
- Regime patterns reinforced (consistency check)
- Regime-conditional strategies identified
- Agents can predict regime importance for each setup

### Cycle 3: Setup Patterns (365 days)
**Goal**: Discover setup-conditional value
**Expected Results**:
- Which setups work when (detailed matrix)
- Setup-regime interactions quantified
- Conditional filtering rules emerge

### Cycle 4: Cross-Regime Validation (365 days)
**Goal**: Ensure patterns hold across diverse market conditions
**Expected Results**:
- High-consistency patterns validated
- Edge robustness confirmed
- False patterns eliminated

### Cycle 5: Synthesis (365 days)
**Goal**: Full system understanding
**Expected Results**:
- Agent rules book created
- Confidence thresholds per regime/setup
- Symbol-specific coaching profiles
- Ready for live deployment

## Key Metrics Tracked

### Consolidation Across Cycles
```json
{
  "regime_patterns": {
    "trending_bull": {
      "observations": [
        {"cycle": 1, "wr": 65.2, "sample_size": 127},
        {"cycle": 2, "wr": 63.8, "sample_size": 142}
      ],
      "avg_wr": 64.5,
      "consistency": 0.95,
      "num_observations": 2,
      "recommendation": "prioritize"
    }
  }
}
```

### Pattern Validation
- **Consistency**: Std dev of WR across cycles (higher = more robust)
- **Confidence**: Increases with repeated observations
- **Sample Size**: Total trades in pattern (30+ = minimum for significance)

## Running the System

### Simple: Single Cycle
```bash
cd bot
python autonomous_learning_loop.py
# or
python robust_learning_cycle.py
```

### Production: Multi-Cycle
```bash
cd bot
python continuous_learning_orchestrator.py
# Runs 5 cycles, displays progress
# ~5-15 hours total (depending on system resources)
```

### Monitoring
```bash
# Terminal 1: Watch dashboard
watch -n 60 "python learning_dashboard.py"

# Terminal 2: Monitor logs
tail -f learning_cycle_N.log

# Terminal 3: Watch knowledge base grow
watch -n 30 "wc -l data/agent_knowledge_base.json"
```

## Expected Timeline

| Cycle | Duration | Total Time | Key Output |
|-------|----------|-----------|-----------|
| 1 | 1-2 hours | 1-2h | Baseline knowledge |
| 2 | 1-2 hours | 2-4h | Regime understanding |
| 3 | 1-2 hours | 3-6h | Setup patterns |
| 4 | 1-2 hours | 4-8h | Cross-regime validation |
| 5 | 1-2 hours | 5-10h | Full synthesis |

**Total**: 5-10 hours of continuous autonomous learning → agents understand exact system wiring

## Interpreting Results

### High Confidence Finding
```
trending_bull: 65.2% WR (consistency 92%, 4 observations)
→ Agent confidence: HIGH
→ Action: Use in live trading
```

### Low Consistency Pattern
```
ranging: 45% WR (consistency 22%, 5 observations)
→ Agent confidence: LOW
→ Action: Need more data, don't use for decisions
```

### Emergent Edge
```
ETH_LONG + trending_bull + afternoon_session: 78% WR (2 observations)
→ Agent confidence: MEDIUM
→ Action: Watch, validate in next cycle
```

## Troubleshooting

### Cycle Hangs
```bash
# Check if backtest subprocess is still running
ps aux | grep "python run.py"

# If stuck, check last output
tail -100 learning_cycle_N.log

# Can restart with robust_learning_cycle.py (has timeout handling)
```

### No Agent Analysis
- Agents run via Claude CLI (requires `claude` command available)
- Test: `claude --help`
- If missing: install Claude Code CLI

### Knowledge Base Not Updated
- Check file permissions: `ls -la data/agent_knowledge_base.json`
- Check disk space: `df -h`
- Verify JSON syntax: `python -m json.tool data/agent_knowledge_base.json`

## Integration with Live Trading

Once Cycle 5 completes and agents understand system wiring:

1. **Extract Agent Rules** → Convert agent learnings to decision rules
2. **Validate Rules** → Test on holdout data (2026 data not in training)
3. **Deploy Rules** → Update agent prompts with discovered patterns
4. **Monitor Divergence** → Track live vs backtest performance
5. **Iterate** → Run new backtest cycles quarterly as market changes

## Philosophy

**Mechanical Gating (Old Approach)**:
- Delete data agents need → Learning impossible
- Filter 92% of signals → Collapse sample size
- Result: 6 trades/year, no learning

**Agent Learning (New Approach)**:
- Give agents ALL signal context → Learning inevitable
- No mechanical filters (only basic circuit breakers) → Rich data
- Result: 500-2000 trades/year, agents learn patterns

**Key Insight**: Agents learn best when they see diverse data. The more signals they analyze (including failures), the better they understand WHY signals work or don't work. Mechanical gates prevent this learning by hiding data.

---

**Status**: Cycle 1 running. Check `learning_dashboard.py` for progress.  
**Next**: When Cycle 1 completes, run `continuous_learning_orchestrator.py` for full 5-cycle discovery.
