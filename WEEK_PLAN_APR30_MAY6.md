# Week Plan: April 30 - May 6, 2026
## Full Autonomous Execution with Relentless Self-Improvement

---

## Weekly Goal
**Validate Phase 3.2 system** (75% WR backtest, +$1,177 net 60d) in LIVE trading with autonomous learning loops. Collect 20-50 trades, verify profitability, and identify optimization opportunities.

**Success Criteria:**
- ≥20 trades executed
- Win rate ≥60% (backtest: 75%)
- P&L trending positive
- Zero catastrophic failures
- KB learning closed-loop

---

## Daily Breakdown

### **Day 1: Wed Apr 30 (TODAY)**
**Status: IN PROGRESS**

**Setup (DONE):**
- [x] Crash recovery audit completed
- [x] System health verified (bot running, executor ready)
- [x] Autonomous monitor activated (3-hour check-ins)
- [x] Phase 3.2 system live (aggressive rules, proven edge)

**Tonight (Autonomous):**
- Bot: Generate signals continuously
- Monitor: 3-hour check-ins, report trades/signals
- You: Check in 1-2x if desired, otherwise system runs solo

**Metrics to watch:**
- Signal volume (target: 10-20/day)
- Execution rate (target: 1-3 trades/day)
- Win rate so far (target: 65%+)

**Hands-off:** Yes. System runs autonomously.

---

### **Day 2: Thu May 1**
**Theme: Validation of Core Hypothesis**

**Autonomous Goals:**
- Execute 5-10 trades
- Log all decisions to decisions.jsonl
- Monitor win rate (validate backtest 75% holds)
- Check for regime mismatches

**Check-in Points:**
- Morning (08:00 UTC): Review overnight trades, any errors?
- Evening (20:00 UTC): 24h summary, adjust parameters if WR <50%

**Conditional Actions:**
- If WR >70%: Continue aggressive rules unchanged
- If WR 50-70%: Tighten confidence thresholds (raise mins by 5%)
- If WR <50%: PAUSE aggressive executor, debug mode

**Metrics:** Cumulative WR, P&L, signal distribution

---

### **Day 3: Fri May 2**
**Theme: Strategy Performance Breakdown**

**Autonomous:** Continue trading, collect execution data

**Evening Analysis (you-driven, ~1h):**
1. Run `/signal-check` — which strategies executing most?
2. Analyze: Which symbol/strategy combos are winners?
3. Update: Executor rules if clear pattern emerges
   - If ETH SHORT >80% WR: Lower confidence threshold
   - If SOL BUY <20% WR: Raise threshold or disable temporarily

**Target:** 10-15 total trades, identify winning edge

---

### **Day 4: Sat May 3**
**Theme: Weekend Volatility & Cross-Asset Learning**

**Autonomous:** Continue (lower volatility expected, trades may slow)

**Background:**
- LLM agents learning from 3d worth of closed trades
- Memory systems updating trade DNA
- Counterfactual analysis running (what would have happened?)

**If needed (optional):**
- Review knowledge base for new patterns learned
- Check deep memory for symbol-specific insights

---

### **Day 5: Sun May 4**
**Theme: Week 1 Validation Report**

**You-Driven Deep Analysis (~2h):**

1. **Backtest Validation:**
   ```
   Did Phase 3.2 edge hold in live trading?
   - Backtest: 75% WR, +$1,177 net 60d
   - Live: [actual WR], [actual P&L]
   - Confidence: HIGH if WR >65%, MEDIUM if 55-65%, LOW if <55%
   ```

2. **Symbol Breakdown:**
   ```
   BTC:  [WR]%, [trades], [P&L]
   ETH:  [WR]%, [trades], [P&L]
   SOL:  [WR]%, [trades], [P&L]
   HYPE: [WR]%, [trades], [P&L]
   ```

3. **Strategy Performance:**
   ```
   vmc_cipher:         [WR]%, [trades], edge valid?
   bollinger_squeeze:  [WR]%, [trades], edge valid?
   monte_carlo_zones:  [WR]%, [trades], edge valid?
   multi_tier_quality: [WR]%, [trades], edge valid?
   ```

4. **Optimization Findings:**
   - Which confidence thresholds worked best?
   - Any regime mismatches (e.g., trending rules in ranging market)?
   - Symbol-specific micro-filters needed?

**Decision Point:**
- **ACCELERATE:** If WR ≥70%, increase leverage or signal volume
- **MAINTAIN:** If WR 60-70%, keep rules unchanged, collect more data
- **PIVOT:** If WR <60%, disable certain strategies, tighten gates

---

### **Day 6: Mon May 5**
**Theme: Feedback Loop Integration & Rule Hardening**

**Autonomous Improvements (based on Sunday findings):**

1. **Rule Updates** (if needed):
   - Adjust confidence thresholds per symbol
   - Enable/disable strategies based on edge validation
   - Update leverage caps if volatility changed

2. **Knowledge Distillation:**
   - Graduated rules from hypotheses → move into trading_config.py
   - Lock in winning patterns (stop testing, start trading)

3. **Agent Learning:**
   - Exit Agent: Trained on closed trades, better exits expected
   - Learning Agent: Updated memory with new patterns
   - Consistency checker: Verify cross-agent coherence

**Target:** Implement top 3 optimizations from Sunday analysis

---

### **Day 7: Tue May 6**
**Theme: Week 2 Planning & Strategy Expansion**

**End-of-Week Review (1-2h):**

1. **Validate 40+ trade sample:**
   - WR trend (improving? stable? degrading?)
   - P&L trajectory (on pace for $500+/week?)
   - Drawdown behavior (largest DD, recovery rate?)

2. **Phase 4 Readiness:**
   - Do we have enough edge validation to expand?
   - Can we safely increase leverage? (25x → 30x?)
   - Add new symbols? (AVAX? ARB? DOGE?)
   - Add new strategies? (Other high-edge ideas?)

3. **Week 2 Plan:**
   - Aggressive optimization: +20% leverage, +2 symbols?
   - Consolidation: Perfect Phase 3.2, lock in edge?
   - Hybrid: Optimize winners, disable losers?

**Hands-off:** Rest of day, system continues autonomously

---

## Autonomous Background Tasks (Running 24/7)

### **Signal Generation**
- Regime Agent: 1h/6h trend classification
- Trade Agent: Entry thesis formation
- Risk Agent: Position sizing
- Critic Agent: Veto validation

**Cadence:** Every 60s on all 4 symbols

### **Learning Loop**
- **Trade Closed** → Learning Agent extracts lessons
- **Pattern Found** → Memory updated, KB evolged
- **Confidence Drift** → Consistency checker flags issues
- **KB Updated** → Executor rules auto-adjust (when enabled)

### **Exit Monitoring**
- Exit Agent: Monitors open positions every 120s
- Reassesses thesis validity
- Recommends exits if conditions change

### **Portfolio Risk**
- Correlation checks between positions
- Liquidation risk monitoring
- Drawdown alerts (if ≥5%)

---

## Check-In Schedule

**Automated (you don't need to do anything):**
- Every 3 hours: Monitor check-in (metrics report)
- Every trade: Decision logged to decisions.jsonl
- Daily: Knowledge base evolution tracked

**Optional (if you want deeper insight):**
- **Morning (08:00 UTC):** Quick status check (2 min)
  - "How many trades last 24h? WR? Any errors?"
- **Evening (20:00 UTC):** Daily review (10 min)
  - "Which strategies executed? Any patterns?"
- **Weekly (Sunday evening):** Deep analysis (2h)
  - Full validation, optimization decisions, Week 2 planning

**Emergency (only if needed):**
- System loses >10% equity: Auto-disable aggressive rules
- Consecutive losses >3: Trigger circuit breaker
- Errors: Logged, auto-reported in check-ins

---

## Files to Monitor

**Metrics:**
- `bot/data/trades.csv` — All executed trades
- `bot/data/llm/decisions.jsonl` — All LLM decisions
- `/tmp/autonomous_monitor_loop.log` — Check-in reports
- `/tmp/autonomous_bot_*.log` — Bot main loop

**Learning:**
- `bot/data/llm/teaching/knowledge_base.json` — Pattern evolution
- `bot/data/llm/deep_memory/` — Learned patterns
- `bot/data/llm/consistency_log.jsonl` — Agent coherence

**Configuration (if optimizing):**
- `.env` — LLM mode, thresholds, leverage
- `bot/trading_config.py` — Strategy rules, gates
- `autonomous_signal_executor.py` — Executor thresholds

---

## Success Metrics (By End of Week)

| Metric | Target | Interpretation |
|---|---|---|
| Total Trades | ≥40 | Enough data to validate edge |
| Win Rate | ≥65% | Backtest edge confirmed (75% target) |
| Net P&L | ≥$200 | Profitability on $400 starting equity |
| Sharpe Ratio | ≥1.5 | Risk-adjusted returns healthy |
| Max Drawdown | ≤10% | Risk management working |
| Avg Trade P&L | ≥$5 | Positive expectancy |

**If achieved:** Ready for Phase 4 (leverage increase, symbol expansion)
**If partial:** Tune parameters, collect more data, next week
**If failed:** Debug strategy, disable losers, restart

---

## Contingency Plans

### Scenario 1: WR <50% (Strategy Not Working Live)
```
Action:
1. PAUSE aggressive executor (stop new trades)
2. Let existing trades close out naturally
3. Debug: Which symbols/strategies failing?
4. Solution: Disable problem strategies, re-tune thresholds
5. Restart with conservative rules (65%+ confidence)
```

### Scenario 2: Consecutive Losses (3+)
```
Action:
1. Circuit breaker triggered automatically
2. System cooldown 2h
3. Review last 3 trades: Why did they lose?
4. If pattern: Disable strategy, tighten gate
5. If anomaly: Resume trading after cooldown
```

### Scenario 3: Unusual Market Conditions
```
Examples: Flash crash, funding change, exchange issue
Action:
1. Monitor detects anomaly (volatility >2 std dev)
2. Auto-scales position sizes down by 50%
3. Continues trading but more cautiously
4. You informed in next check-in
```

### Scenario 4: Bot Crash (Power Loss, etc.)
```
Action:
1. Auto-recovery on restart
2. Reconcile positions with exchange
3. Resume trading from last known state
4. Check-in report shows recovery complete
```

---

## Advanced: Optional Deep Dives (You-Driven)

If you want to go deeper during the week:

1. **Signal Quality Audit:**
   - Which signals had best MFE (maximum favorable excursion)?
   - Could we improve entry timing?

2. **Exit Optimization:**
   - Are TP1/TP2 targets optimal?
   - Should trailing stops activate more often?

3. **Regime Analysis:**
   - Do certain strategies work better in certain regimes?
   - Can we regime-gate the executor rules?

4. **Correlation Learning:**
   - Are BTC/ETH correlated? How does this affect sizing?
   - Can we exploit cross-asset patterns?

5. **Hypothesis Testing:**
   - What micro-filters would improve WR most?
   - Which symbol would add most edge?

---

## Summary

**This Week:** Validate Phase 3.2 edge in live trading, let system run autonomously, make optimization decisions by Sunday.

**Your Role:** Check in every few hours if desired (system doesn't require it), do deep analysis on Days 3, 5, 7.

**System Role:** Generate signals, execute, learn, improve continuously.

**Goal:** Confirm 75% WR backtest edge holds → unlock Phase 4 acceleration.

---

Last updated: 2026-04-30 21:35 UTC
Next plan review: 2026-05-06 20:00 UTC (End of week)
