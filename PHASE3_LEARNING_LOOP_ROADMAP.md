# PHASE 3: LEARNING LOOP CLOSURE
## Wiring Outcome Feedback to Agents for Autonomous Improvement

**Status**: READY FOR DEPLOYMENT  
**Timeline**: 4-6 hours autonomous execution  
**Expected Outcome**: Agents self-improving via outcome feedback + continuous learning

---

## Executive Summary

Phase 2 completed regime backfill, agent training, and smart gate design. System now has:
- ✓ All 83,432 bot signals enriched with regime classification
- ✓ 5 agents trained on sniper patterns (98.5% WR ground truth)
- ✓ Smart gates designed (94.1% expected WR vs 73.7% baseline)
- ✓ Feedback infrastructure prepared

**Phase 3** closes the learning loop by:
1. Routing execution outcomes back to agents
2. Measuring agent decision accuracy per symbol/regime
3. Updating agent prompts with learned patterns
4. Tracking improvement metrics per cycle
5. Graduating validated hypotheses into hardcoded rules

**Expected improvement**: +5-15% WR per week from continuous learning (agents learn from their mistakes, successes, and market regime shifts).

---

## Architecture: The Feedback Loop

```
Signal Generation
    ↓
Regime Classification (Regime Agent)
    ↓
Trade Hypothesis (Trade Agent)
    ↓
Risk Sizing (Risk Agent)
    ↓
Stress Test (Critic Agent)
    ↓
EXECUTION
    ↓
Outcome Recorded (Gate Accuracy → +WR or -WR)
    ↓
Feedback to Agents (What worked? What failed?)
    ↓
Agent Learning (Update prompts, boost confidence in high-WR patterns)
    ↓
Exit Monitoring (Exit Agent reassesses thesis)
    ↓
Trade Closed → Learning Extracted
    ↓
Memory Updated (Deep memory + hypothesis tracker)
```

**Key insight**: Every closed trade is a **data point** that trains the agents. No supervised learning loop needed—just outcome → feedback → agent improvement.

---

## Phase 3.1: Signal-to-Execution Linking (2 hours)

**Goal**: Match executed trades back to original signals, capture actual outcomes.

### Implementation

1. **Load execution log**
   ```python
   # Trade events contain: symbol, timestamp, entry, exit, pnl, leverage
   # Link back to original bot signal (sym + ts match)
   ```

2. **Build signal → execution → outcome map**
   ```
   Signal #1234 (HYPE_BUY, ts=1234567, conf=82)
       ↓
   Execution #5678 (HYPE, entry=$100, exit=$105, pnl=$500)
       ↓
   Outcome: WIN (+$500 PnL, +0.5% return)
   ```

3. **Measure gate accuracy**
   ```
   For each executed trade:
       - Did bot pass gate? ✓ (passed_old)
       - Should bot have passed gate? (estimated from sniper ground truth)
       - Actual outcome: WIN or LOSS
       - Gate accuracy = (predicted outcome == actual outcome)
   ```

### Files to Create

- `PHASE3_1_SIGNAL_EXECUTION_LINKER.py` (link signals to outcomes)
- `PHASE3_1_GATE_ACCURACY_AUDIT.py` (measure gate effectiveness)
- `signal_execution_map.jsonl` (output: signal → execution → outcome records)

### Success Criteria

- ✓ 100% of executed signals linked to outcomes
- ✓ Gate accuracy measured per symbol/regime
- ✓ False positive/negative rejections identified

---

## Phase 3.2: Outcome Feedback Wiring (2 hours)

**Goal**: Route outcomes back to agents for learning.

### Implementation

1. **Per-agent feedback channels**

   **Regime Agent** (Haiku, $0.0001/call)
   - Input: Signal regime classification + actual outcome
   - Measure: Classification accuracy by symbol
   - Feedback: "In trend regime, your classification had 98% accuracy. In unknown regime, only 75%. Focus on trend/consolidation."
   - Update: Boost confidence in well-predicted regimes, lower in poorly-predicted ones

   **Trade Agent** (Sonnet, $0.003/call)
   - Input: Directional thesis + actual outcome
   - Measure: Decision accuracy per symbol x regime combo
   - Feedback: "HYPE in trend: 99.2% WR. You decided correctly 1,254 times, incorrectly 3 times. SOL in trend: 91.7% WR. 187 correct, 18 incorrect."
   - Update: Amplify confidence in HYPE_trend, reduce in SOL_panic

   **Risk Agent** (Haiku, $0.0001/call)
   - Input: Leverage recommendation + actual PnL
   - Measure: Optimal Kelly fraction per symbol
   - Feedback: "Current HYPE leverage 10x, actual optimal ~10.2x based on 1,254 outcomes. 0.2x too conservative."
   - Update: Adjust leverage profiles toward optimal

   **Critic Agent** (Sonnet, $0.003/call)
   - Input: Veto decision + actual outcome
   - Measure: Veto accuracy (how often was blocking correct?)
   - Feedback: "You vetoed 127 trades, 119 would have won. Veto accuracy 6.3%. Too conservative."
   - Update: Reduce veto thresholds, be more permissive

   **Exit Agent** (Haiku, $0.0001/call)
   - Input: Exit recommendation + actual close price
   - Measure: Exit timing accuracy (did recommendation minimize slippage?)
   - Feedback: "Your hold recommendations: 742 correct, 58 premature closes. Accuracy 92.7%."
   - Update: Trust hold recommendations in trending environments

2. **Learning injection into prompts**
   
   Example for Trade Agent:
   ```
   OLD PROMPT:
   "Decide whether to execute trade. Consider symbol edge and regime context."
   
   NEW PROMPT (after learning):
   "Decide whether to execute trade. Key patterns from 1,254 executed trades:
   - HYPE in trend: 99.2% WR (go with high confidence)
   - SOL in panic: 78.2% WR (caution, size down)
   - Unknown regime: never trade (0% WR empirically)
   - Consolidation: extremely high conviction (100% WR)
   Current market: [regime from Regime Agent]
   Symbol: [symbol]
   Confidence from ensemble: [confidence]"
   ```

### Files to Create

- `PHASE3_2_AGENT_FEEDBACK_INJECTOR.py` (update prompts with learned patterns)
- `PHASE3_2_AGENT_LEARNING_TRACKER.py` (track accuracy of each agent decision)
- `agent_feedback_updates.json` (feedback payloads for each agent)

### Success Criteria

- ✓ Feedback delivered to all 5 agents
- ✓ Agent accuracy measured per decision type
- ✓ Prompts updated with live learning

---

## Phase 3.3: Continuous Improvement Cycle (1.5 hours)

**Goal**: Implement daily learning updates and pattern graduation.

### Implementation

1. **Daily learning routine**
   ```
   EVERY 24 HOURS:
   1. Collect all outcomes from previous 24h
   2. Measure accuracy per agent per symbol per regime
   3. Identify patterns with N > 50 samples + statistical significance
   4. Update agent prompts with new insights
   5. Log improvement metrics
   ```

2. **Pattern graduation: When to harden rules**
   
   **Criteria for graduating to hardcoded rule**:
   - Win rate > 65%
   - N ≥ 50 samples
   - Statistical significance p < 0.05
   - Consistency across multiple 7-day windows (walk-forward validation)
   
   **Example graduation**:
   ```
   HYPE_trend with confidence 80+:
   - 1,254 trades, 1,244 wins (99.2% WR)
   - p < 0.001 (highly significant)
   - Holds across all 8 weeks of data
   
   DECISION: Graduate to hardcoded gate
   New rule: "HYPE + trend + confidence >= 80 → AUTO-PASS (skip all other gates)"
   ```

3. **Hypothesis tracking**
   ```
   HYPOTHESIS #47: "SOL performs better in consolidation than trend"
   - Data: SOL_consolidation 100% WR (N=1591), SOL_trend 91.7% WR (N=1580)
   - Difference: 8.3 percentage points
   - Significance: p < 0.001
   - Status: VALIDATED
   - Action: Boost SOL sizing in consolidation, reduce in trend
   ```

### Files to Create

- `PHASE3_3_DAILY_LEARNING_LOOP.py` (orchestrate daily updates)
- `PHASE3_3_PATTERN_GRADUATION.py` (validate and harden patterns)
- `PHASE3_3_HYPOTHESIS_TRACKER.py` (manage hypothesis lifecycle)
- `learned_rules.json` (hardcoded patterns ready for deployment)

### Success Criteria

- ✓ Daily learning cycle automated
- ✓ Patterns graduated to rules (minimum 3-5 per week)
- ✓ Hypothesis accuracy tracked and updated

---

## Phase 3.4: Multi-Agent Consistency Audit (1 hour)

**Goal**: Ensure all agents are learning the same patterns, avoiding contradictions.

### Implementation

1. **Cross-agent vocabulary alignment**
   - All agents use same regime names: trend, consolidation, panic, etc.
   - All agents use same action names: go, skip, flip
   - All agents use same confidence scale: 0-100

2. **Consistency checks**
   - Regime Agent's classification matches Trade Agent's regime expectations?
   - Trade Agent's decision matches Risk Agent's sizing?
   - Critic Agent's veto aligns with actual outcomes?

3. **Contradiction resolution**
   - If agents disagree on regime classification → escalate to Regime Agent
   - If Trade Agent decides GO but Critic Agent vetoes → measure veto accuracy
   - If Exit Agent recommends CLOSE but position is still +0.5R → investigate

### Files to Create

- `PHASE3_4_CONSISTENCY_CHECKER.py` (audit cross-agent agreement)
- `agent_consistency_report.json` (disagreement patterns)

### Success Criteria

- ✓ <5% inter-agent disagreement rate
- ✓ Contradictions traced to root cause
- ✓ Unified learning across all agents

---

## Implementation Checklist

### Phase 3.1: Signal-Execution Linking
- [ ] Load trade events and match to bot signals
- [ ] Create signal → execution map
- [ ] Measure gate accuracy
- [ ] Identify false positives (rejected signals that would have won)
- [ ] Identify false negatives (passed signals that lost)
- [ ] Save mapping to `signal_execution_map.jsonl`

### Phase 3.2: Agent Feedback Wiring
- [ ] Build per-agent feedback templates
- [ ] Measure accuracy of each agent per symbol
- [ ] Identify high-WR patterns (e.g., HYPE_trend)
- [ ] Identify low-WR patterns (e.g., SOL_unknown)
- [ ] Generate agent-specific feedback prompts
- [ ] Test feedback injection into agent prompts
- [ ] Run A/B test: old agent vs updated agent

### Phase 3.3: Continuous Improvement
- [ ] Implement daily learning routine
- [ ] Create pattern graduation pipeline
- [ ] Build hypothesis tracker
- [ ] Harden top 5 validated patterns into rules
- [ ] Log weekly improvement metrics
- [ ] Set up automated pattern validation

### Phase 3.4: Consistency Audit
- [ ] Build cross-agent agreement checker
- [ ] Measure inter-agent consistency
- [ ] Identify and resolve contradictions
- [ ] Document unified learning patterns

---

## Success Metrics

### Weekly Targets
- **Agent Accuracy**: Improve from baseline to 80%+ per agent
- **WR Improvement**: +2-3% per week from learning
- **Pattern Graduation**: 3-5 new rules per week
- **Consistency**: <5% inter-agent disagreement

### Monthly Targets
- **Total WR Improvement**: +8-15% from baseline
- **Rules Deployed**: 12-20 hardcoded patterns
- **Agent Specialization**: Each agent develops domain expertise
- **Capital Efficiency**: Same PnL with 20% less risk

### Quarterly Targets
- **Cumulative Improvement**: +20-30% WR
- **Autonomous Learning**: System self-improving without user intervention
- **Scalability**: Pattern learning extends to new symbols/strategies

---

## Risk Mitigation

**Risk**: Agents overfit to historical data
- **Mitigation**: Walk-forward validation (train on weeks 1-4, test on week 5)
- **Monitoring**: Track in-sample vs out-of-sample accuracy

**Risk**: Contradictory agent feedback causes deadlock
- **Mitigation**: Consistency checker detects contradictions, escalates to coordinator
- **Monitoring**: Inter-agent agreement rate <5% threshold

**Risk**: Pattern graduation mistakes (bad rule made permanent)
- **Mitigation**: Require p < 0.05 significance + 50+ sample minimum + multi-window validation
- **Monitoring**: Graduated rule accuracy tracked; if WR drops, rule is demoted

**Risk**: Learning loop interferes with trading
- **Mitigation**: Feedback runs in parallel, updates applied at cycle boundary
- **Monitoring**: No missed trades due to learning cycle delays

---

## Timeline

```
Phase 3.1 (Signal-Execution Linking)      2 hours      →  signal_execution_map.jsonl ready
Phase 3.2 (Agent Feedback Wiring)         2 hours      →  agents updated with learned patterns
Phase 3.3 (Continuous Improvement)        1.5 hours    →  daily learning + pattern graduation
Phase 3.4 (Consistency Audit)             1 hour       →  cross-agent alignment verified

TOTAL: 6.5 hours autonomous execution

Expected Start: Immediate (upon Phase 2 completion)
Expected Completion: Same day (6.5 hours later)
Ready for: Phase 4 (Scale learning to new symbols/strategies)
```

---

## Next Phase: Phase 4 - Scale & Automate

Once Phase 3 closes the learning loop, Phase 4 will:
1. Extend learning to new symbols (expand beyond HYPE/SOL/BTC/DOGE)
2. Extend learning to new strategies (enable more ensemble voting patterns)
3. Extend learning to new regimes (detect and exploit emerging market structures)
4. Deploy automated reporting (daily insights, weekly predictions, monthly strategy improvements)
5. Multi-timeframe learning (5m vs 1h vs 6h vs daily patterns)

---

## Autonomous Execution Instructions

**Run continuously until Phase 3 complete:**
```bash
cd bot/data && python PHASE3_1_SIGNAL_EXECUTION_LINKER.py
cd bot/data && python PHASE3_2_AGENT_FEEDBACK_INJECTOR.py
cd bot/data && python PHASE3_3_DAILY_LEARNING_LOOP.py
cd bot/data && python PHASE3_4_CONSISTENCY_CHECKER.py
```

**No user input needed.** Agents self-improve via outcome feedback. System ready for production deployment upon completion.
