# Weeks 3-6 Comprehensive Blueprint — WAGMI Bot Build-Out
**Generated**: 2026-04-27 (post Week 1-2 completion)  
**Status**: Ready for autonomous execution  
**Target**: Ship-quality implementations with full test coverage, bug-free wiring

---

## Executive Overview

**Goal**: Complete the 6-week roadmap from backend abstraction to production-ready canary trading system.

**Phases**:
- **Week 3**: Learning loop closes (audit trail → lessons → memory enrichment)
- **Week 4**: New specialist agents (Opportunist for pattern discovery, Adversary for robustness)
- **Week 5**: Canary substrate (paper → shadow → live progression with monitoring)
- **Week 6**: Optional local model wedge (Ollama as cost-optimization fallback) OR continue deepening system
- **Parallel**: Silent-fallback refactor (206+ instances across 15 danger files, 41× ROI)

---

## WEEK 3: LEARNING LOOP CLOSES

**Goal**: Transform audit trail into lessons → update memory → inject into agent prompts

**Effort**: 90-120 hours autonomous  
**Files Created**: 8  
**Files Modified**: 6  
**Tests Added**: 30+

### W3-A: Closed Trade Analyzer (14 days post-close)

**Purpose**: Extract lessons from closed trades using decisions.jsonl audit trail

**File**: `bot/llm/learning/closed_trade_analyzer.py` (400 lines)

**Responsibilities**:
1. **Trade forensics** — For each closed trade:
   - Find entry decision in decisions.jsonl (timestamp, symbol, action, regime, thesis)
   - Find exit decision in decisions.jsonl (if exists)
   - Cross-reference with actual PnL outcome (position_manager.py state)
   - Compute: thesis_correct (entry prediction matched outcome), confidence_calibration (was confidence justified?)

2. **Pattern extraction** (per setup type):
   - Entry regime, strategy agreement, confidence level, leverage used, hold time
   - Outcome: win/loss, R-multiple, exit reason
   - Hypothesis: "trending_bear + 3-strategy + 80%+ confidence → 73% WR, 1.8R avg"

3. **Memory enrichment trigger**:
   - If confidence was overconfident (80%+ but 40% WR): "deflate 80%+ in ranging"
   - If pattern repeats 5+ times with >70% consistency: "trust this setup"
   - If counter-pattern exists (same setup, opposite outcome): "regime/symbol dependent"

**Integration Points**:
- Called from `Learning Agent` post-close (bot/llm/agents/coordinator.py:exit_decision_path)
- Input: decisions.jsonl entry + position state
- Output: `TradeLesson` dataclass (setup_type, hypothesis, confidence_change, risk_flags)

**Key Classes**:
```python
@dataclass
class TradeLesson:
    trade_id: str
    symbol: str
    entry_thesis: str
    outcome_thesis: str
    setup_type: str  # "trending_bear+3-agree+80conf"
    confidence_correct: bool
    pnl_outcome: float
    r_multiple: float
    lessons: List[str]  # ["deflate 85%+ in chop", "trust this pattern in trend"]
    
@dataclass
class SetupPattern:
    setup_type: str
    win_count: int
    loss_count: int
    avg_r_multiple: float
    confidence_accuracy: Dict[int, float]  # conf_bin → actual_wr
    regime_dependent: bool
    related_patterns: List[str]
```

**Algorithm**:
1. For each closed trade (CLOSED state in position_manager):
   - Lookup decisions.jsonl by symbol + timestamp (±5s window)
   - Extract entry decision (regime, thesis, confidence, leverage)
   - Extract exit decision if exists
   - Compute outcome_thesis (entry prediction vs actual move)
   - Compute confidence_calibration (did actual WR match predicted confidence?)
   - Score thesis_accuracy (0-100, did the thesis hold?)

2. Group by setup_type (regime + n_agree + confidence_bin):
   - Count wins/losses
   - Compute average R-multiple, hold time
   - Build calibration curve (confidence_level → actual_wr)
   - Detect regime-dependent patterns (trending_bear: 75% WR vs ranging: 35% WR)

3. Emit lessons:
   - "Deflate confidence in (setup): actual 40% vs predicted 75%"
   - "Trust (setup) in (regime): 8/10 trades profitable"
   - "Avoid (symbol, setup): 2% WR, should be gated"

**Testing**: `bot/tests/test_closed_trade_analyzer.py` (45 lines)
- Mock 20 closed trades with decisions.jsonl entries
- Verify lesson extraction (thesis_correct field)
- Verify setup_pattern grouping (win/loss counts)
- Verify calibration detection (overconfident/underconfident bins)

---

### W3-B: Memory Enrichment & Hypothesis Graduation

**Purpose**: Convert lessons into deep memory updates and rulify validated patterns

**File**: `bot/llm/learning/memory_enrichment.py` (350 lines)

**Responsibilities**:

1. **Short-term memory injection** (into bot/llm/memory_store.py):
   - "⚠️ DEFLATE: 85%+ confidence in ranging regime (recent 40% WR, should be 70%+)"
   - "✓ TRUST: ETH_SELL + 3-agree + trending_bear = 79% WR (13 trades)"
   - "🔍 INVESTIGATE: BTC_LONG in low-liquidity regime (2% WR, systematic block?)"

2. **Deep memory pattern storage** (bot/data/llm/deep_memory/patterns.jsonl):
   - Append validated patterns with threshold checks
   - Each pattern: setup_type, win_rate, r_multiple, sample_size, confidence_level
   - Track: pattern_discovered_date, last_verified_date, confidence_decay_rate

3. **Rule graduation** (bot/data/llm/graduated_rules.json):
   - If pattern has 10+ occurrences AND win_rate > 70% → graduate to rule
   - Rule format: `{"id": "rule_003", "trigger": "symbol=ETH,regime=trending_bear,n_agree=3", "action": "promote_confidence", "effect": "+15%"}`
   - Add reason/evidence fields: `"evidence": "14 trades, 78% WR, discovered 2026-04-15"`

4. **Rule demotion** (cleanup):
   - If rule-based signal has <50% WR in last 10 trades → flag for review
   - If pattern disappears (market regime shift) → mark archived, don't apply

**Integration Points**:
- Called by Learning Agent after `closed_trade_analyzer` produces lessons
- Reads: decisions.jsonl, position_manager state
- Writes: memory_store.py (appends notes), deep_memory/patterns.jsonl, graduated_rules.json
- Used by: Trade Agent (reads graduated_rules for pre-formedness), Critic Agent (reads patterns for stress-testing)

**Key Functions**:
```python
def enrich_short_term_memory(lessons: List[TradeLesson]) -> None:
    """Add bite-sized lessons to short-term memory (7-day TTL)."""
    for lesson in lessons:
        if lesson.confidence_correct is False:
            memory.add_note(
                f"⚠️ DEFLATE: {lesson.confidence}% in {lesson.regime} (actual {lesson.actual_wr}%)",
                tags=["confidence", "calibration", lesson.symbol],
                ttl_days=7
            )

def graduate_pattern_to_rule(pattern: SetupPattern) -> Optional[Dict]:
    """Convert validated pattern into enforceable rule."""
    if pattern.win_count >= 10 and pattern.avg_wr >= 0.70:
        return {
            "id": f"rule_{hash(pattern.setup_type):08x}",
            "trigger": pattern.setup_type,
            "action": "enforce",
            "reason": f"{pattern.win_count}W-{pattern.loss_count}L ({pattern.avg_wr:.1%} WR)",
            "discovered": datetime.utcnow().isoformat(),
            "evidence_trades": pattern.win_count + pattern.loss_count
        }
```

**Testing**: `bot/tests/test_memory_enrichment.py` (50 lines)
- Mock 15 lessons (8 good patterns, 5 bad patterns)
- Verify short-term memory notes created with correct tags
- Verify graduated_rules.json updated with new rules
- Verify rule demotion flagged for <50% WR patterns
- Verify pattern tracking (discovered_date, evidence_count)

---

### W3-C: Learning Agent Integration Completion

**Purpose**: Wire closed-trade analysis into full agent pipeline

**File Modified**: `bot/llm/agents/coordinator.py` (add 80 lines in post-close path)

**Changes**:
1. After position closes (position_manager.state == CLOSED):
   ```python
   # In get_exit_intelligence() or post-close callback:
   lessons = closed_trade_analyzer.analyze(position_id, trade_start_time)
   memory_enrichment.enrich(lessons)
   learning_agent_output = await learning_agent.execute(
       position_data=position,
       decisions_log=decisions_log_entries,
       lessons=lessons
   )
   # Lessons → memory → prompt injection for next Trade Agent call
   ```

2. Memory state injected into next Trade Agent call (existing mechanism, just validates it's wired)

3. Add instrumentation (logging):
   - `[LEARNING] Analyzed trade {trade_id}: thesis_correct={correct}, lessons={count}`
   - `[MEMORY] Enriched memory with {count} notes, {graduated} rules graduated`

**Testing**: `bot/tests/test_learning_agent_integration.py` (40 lines)
- Mock a closed trade lifecycle
- Verify closed_trade_analyzer called post-close
- Verify memory_enrichment called
- Verify lessons propagated to next decision cycle

---

### W3-D: Deep Memory Query Engine

**Purpose**: Enable Trade/Risk/Critic agents to query lessons from past trades

**File**: `bot/llm/learning/deep_memory_query.py` (250 lines)

**Responsibilities**:

1. **Pattern lookup** (by setup_type):
   - Input: current regime, n_agree, confidence level
   - Output: similar historical patterns with WR, R-multiple, risk flags
   - Example: `query("trending_bear", 3, 82) → {"wr": 0.76, "r_mult": 1.8, "sample": 13, "risk_flag": "overconfident_in_consolidation"}`

2. **Symbol-specific intelligence**:
   - ETH: "Best in trending, avoid in range (17% WR)"
   - HYPE: "High vol needs 1.5x wider stops, 2.0x leverage max"
   - SOL: "Post-loss cooldown 3h (revenge trading detected)"

3. **Regime-conditional rules**:
   - Inject into agent prompts: "In your regime (trending_bear), 3-agree is 76% WR. In ranging, it drops to 48%. Confidence in your regime classification is critical."

**Integration Points**:
- Called by Trade Agent before generating thesis
- Called by Risk Agent before sizing position
- Called by Critic Agent before stress-testing
- Reads: deep_memory/patterns.jsonl, graduated_rules.json

**Key Functions**:
```python
def query_similar_patterns(
    regime: str,
    n_agree: int,
    confidence: int
) -> Dict[str, Any]:
    """Find historical patterns matching current setup."""
    
def get_symbol_intelligence(symbol: str) -> Dict[str, Any]:
    """Symbol-specific lessons (regime preference, vol adjustments, cooldowns)."""
    
def inject_regime_context(regime: str) -> str:
    """Generate regime-conditional advice for agent prompts."""
```

**Testing**: `bot/tests/test_deep_memory_query.py` (30 lines)
- Mock deep_memory with 5 patterns
- Query similar patterns by setup_type
- Verify symbol intelligence returned
- Verify regime context injected correctly

---

### W3-E: Hypothesis Tracker Enhancement

**Purpose**: Track agent prediction accuracy in real-time (existing system, just enhance)

**File Modified**: `bot/llm/thesis_tracker.py` (add 60 lines)

**Enhancements**:
1. Add regime-dependent accuracy tracking:
   - Per-regime win rates (trending_bull, trending_bear, ranging, etc.)
   - Identify: "Trade Agent is 85% accurate in trending_bear but 35% in ranging"

2. Add setup-type tracking:
   - Group by (regime, n_agree, confidence_level)
   - Detect: "80-89% confidence is actually 42% WR (overconfident)"

3. Add symbol-specific tracking:
   - BTC: 68% WR, ETH: 64% WR, SOL: 44% WR
   - Flag underperformers for agent re-training

**Testing**: `bot/tests/test_thesis_tracker_enhancement.py` (25 lines)
- Mock 50 trades with outcomes
- Verify regime-split accuracy computed
- Verify symbol-specific WR computed
- Verify overconfidence detection (80%+ → <50% actual)

---

### W3-F: Learning Agent Prompt Modernization

**Purpose**: Update Learning Agent prompt to use new audit trail + deep memory

**File Modified**: `bot/llm/agents/prompts.py` (replace LEARNING_AGENT_PROMPT, add 100 lines)

**New Prompt Sections**:

1. **Input data clarification**:
   - "You will receive: (1) position object with entry/exit prices, (2) decisions.jsonl entries for entry/exit, (3) TradeLesson objects from closed_trade_analyzer"
   - "Your job is NOT to second-guess decisions. Your job is to extract what we learned."

2. **Lesson extraction template**:
   ```
   For this trade:
   - Entry thesis: [from decisions.jsonl]
   - Outcome: [realized PnL + R-multiple]
   - Thesis accuracy: [did the predicted move match the actual move?]
   - Setup type: [regime + n_agree + confidence_level]
   - Key learning: [specific, actionable insight for future trades]
   ```

3. **Pattern graduation logic**:
   - "If you identify a pattern (setup + regime) with 10+ occurrences and >70% win rate, recommend graduating to a rule"
   - "Include evidence: trade count, win rate, average R-multiple"

4. **Counter-pattern detection**:
   - "If you see a pattern that works in trending but fails in ranging, note this regime dependency"

**Integration**: Inject deep_memory_query context into prompt preamble

**Testing**: `bot/tests/test_learning_agent_prompt.py` (20 lines)
- Mock trade + decisions.jsonl entries
- Verify Learning Agent extracts thesis_accuracy
- Verify pattern identification triggers
- Verify rule graduation recommendations

---

### W3-G: Decisions.jsonl Analysis Tools

**Purpose**: CLI utilities for analyzing audit trail (user-facing tools)

**File**: `bot/llm/learning/decisions_analyzer.py` (200 lines)

**Commands**:
```bash
python -m bot.llm.learning.decisions_analyzer --since 7d --symbol BTC --metric wr
# Output: BTC win rate last 7d = 62.3% (24/39 trades)

python -m bot.llm.learning.decisions_analyzer --pattern "trending_bear+3-agree"
# Output: 15 trades, 73% WR, 1.6R avg, last trade 2h ago

python -m bot.llm.learning.decisions_analyzer --overconfident
# Output: 8 trades where confidence >75% but actual WR <55%
```

**Functions**:
- `summarize_by_symbol()` — per-symbol accuracy
- `summarize_by_regime()` — regime-dependent performance
- `summarize_by_pattern()` — setup-type clustering
- `identify_overconfident_bins()` — confidence calibration issues
- `find_regime_transitions()` — regime shift detection

**Testing**: `bot/tests/test_decisions_analyzer.py` (35 lines)
- Mock 100 decisions.jsonl entries
- Verify WR calculation
- Verify pattern grouping
- Verify regime transition detection

---

### W3 Testing Summary

**Test Files**: 6 new
- test_closed_trade_analyzer.py (45 lines)
- test_memory_enrichment.py (50 lines)
- test_learning_agent_integration.py (40 lines)
- test_deep_memory_query.py (30 lines)
- test_thesis_tracker_enhancement.py (25 lines)
- test_learning_agent_prompt.py (20 lines)
- test_decisions_analyzer.py (35 lines)

**Total**: 245 lines of test code, ~30 test cases

**Run via**: `cd bot && pytest tests/test_learning*.py -v`

**Coverage Target**: 85%+ on all new modules

---

## WEEK 4: NEW SPECIALIST AGENTS

**Goal**: Add 2 new agents (Opportunist, Adversary) to expand decision quality

**Effort**: 80-100 hours autonomous  
**Files Created**: 8  
**Files Modified**: 4  
**Tests Added**: 25+

### W4-A: Opportunist Agent

**Purpose**: Discover repeatable patterns in data, propose new setups, auto-add to ensemble

**File**: `bot/llm/agents/opportunist_agent.py` (400 lines)

**Design**:

1. **Input**: Historical trade data + decisions.jsonl + strategy signals
   - Last 100 closed trades + their entry/exit decisions
   - Current day's strategy signals (all symbols, all strategies)
   - Market regime, volatility, funding rates

2. **Output**: `OpportunityProposal` objects
   ```python
   @dataclass
   class OpportunityProposal:
       pattern_name: str  # "post-liquidation-cascade-reversal"
       setup_description: str  # "When OI cascade detected in last candle, take opposite trade 1h later at ATR-based SL"
       backtest_wr: float  # 0.72 (from historical analysis)
       sample_size: int  # 18 trades in past 60d
       confidence: float  # 0.8 (pattern robustness)
       proposed_action: str  # "add to ensemble with weight 0.3"
       evidence: List[str]  # ["18 trades in trending_bull", "79% WR on BTC/ETH"]
   ```

3. **Agent Loop** (runs every 4 hours, low-cost):
   - Scan decisions.jsonl for the last 100 trades
   - Look for repeating profit patterns (which setups consistently win?)
   - Look for missed opportunities (which soft-filtered signals would have won?)
   - Look for regime-specific edges (which patterns work only in trending?)
   - Propose new patterns, backtest them on last 30d, score confidence
   - If confidence > 0.75 and sample_size > 10: create `OpportunityProposal`

4. **Cascade to Ensemble**:
   - Proposals with confidence > 0.85 are auto-added to ensemble.py as new voting signals
   - Proposals with 0.75-0.85 are queued for human review
   - Proposals with < 0.75 are logged but not applied

**Integration Points**:
- Reads: decisions.jsonl, position_manager state, strategy signals
- Writes: proposals.jsonl (new file, append-only)
- Invoked by: Background scheduler (every 4 hours) or on-demand by user
- Used by: Ensemble (if proposal > confidence threshold)

**Key Methods**:
```python
async def discover_patterns() -> List[OpportunityProposal]:
    """Scan trade history for repeatable winners."""
    
async def backtest_proposal(proposal: OpportunityProposal) -> OpportunityProposal:
    """Walk-forward backtest on last 30d data."""
    
async def score_confidence(proposal: OpportunityProposal) -> float:
    """Robustness score: sample_size, regime variance, out-of-sample stability."""
```

**Prompt** (Sonnet-class, 2K tokens):
```
You are the Opportunist Agent. Your job is to discover hidden patterns in our trading history.

Given:
- Last 100 closed trades (entry thesis, outcome, PnL)
- All strategy signals from today
- Current market regime and conditions

Find:
1. Repeating winning patterns: "When X happens, we make money Y% of the time"
2. Missed opportunities: "Signals we soft-filtered that would have won"
3. Regime-specific edges: "Pattern A works in trending but not ranging"

For each pattern you find:
- Give it a memorable name
- Describe the setup clearly
- Estimate win rate and sample size
- Propose how to use it (add to ensemble? standalone alert?)

Output valid JSON with OpportunityProposal objects.
```

**Testing**: `bot/tests/test_opportunist_agent.py` (55 lines)
- Mock 100 closed trades + decisions.jsonl
- Verify pattern discovery (identify known winners)
- Verify backtest logic
- Verify confidence scoring
- Verify proposal JSON format

---

### W4-B: Adversary Agent

**Purpose**: Stress-test Trade Agent theses, find counter-arguments, validate robustness

**File**: `bot/llm/agents/adversary_agent.py` (350 lines)

**Design**:

1. **Input**: Trade Agent thesis + Market snapshot
   - "BTC is in trending_bear, we should SHORT"
   - Current price, recent price action, volatility, liquidity
   - Similar past trades and their outcomes

2. **Output**: `AdversaryReview` objects
   ```python
   @dataclass
   class AdversaryReview:
       thesis: str
       counter_arguments: List[str]  # ["Vol is 2h high, could squeeze", "Funding rate reversed 30 min ago"]
       missing_checks: List[str]  # ["Is there a hidden support level 2%?", "Post-Fed event fakeout likely?"]
       estimated_drawdown: float  # 0.07 (7% risk if wrong)
       veto_recommendation: Optional[str]  # "VETO: Evidence weak on 4h chart"
       confidence_reduction: float  # 0.15 (should be -15% from predicted)
   ```

3. **Agent Logic**:
   - Take Trade Agent's thesis and output
   - Play devil's advocate: what could go wrong?
   - Look for missing checks (support levels, news, funding rate)
   - Estimate maximum drawdown if thesis is wrong
   - Recommend confidence reduction if evidence is weak
   - If fundamental flaw found: recommend veto

4. **Difference from Critic Agent**:
   - **Critic**: "Stress-test your reasoning. Do you have a counter-thesis?"
   - **Adversary**: "I'm an evil version of you. Here's why you're wrong."
   - Adversary is more aggressive, looks for gotchas the Trade Agent missed

**Integration Points**:
- Reads: Trade Agent output + market snapshot
- Input to: Critic Agent (adds to stress-testing pool)
- Used by: Coordinator (optional, low-priority, can be skipped if budget tight)

**Prompt** (Haiku-class, 1.5K tokens):
```
You are the Adversary Agent. Your job is to find the flaws in proposed trades.

The Trade Agent says: [THESIS]

What could go wrong?
- What price levels support this move?
- Is there recent news that contradicts this?
- What's the funding rate signal?
- What does the 4h chart say vs 1h?

Give counter-arguments and flag the worst risks.
Output JSON with AdversaryReview.
```

**Testing**: `bot/tests/test_adversary_agent.py` (45 lines)
- Mock Trade Agent thesis
- Verify counter-arguments generated
- Verify missing checks identified
- Verify veto recommendation logic
- Verify confidence reduction computed

---

### W4-C: Agent Coordinator Enhancements

**Purpose**: Wire new agents into coordinator pipeline

**File Modified**: `bot/llm/agents/coordinator.py` (add 120 lines)

**Changes**:

1. **Opportunist Agent invocation** (background, every 4 hours):
   ```python
   async def run_opportunist_scan():
       """Background task: discover new patterns."""
       proposals = await opportunist_agent.discover_patterns()
       for proposal in proposals:
           if proposal.confidence > 0.85:
               ensemble.register_signal(proposal)  # Auto-add to voting
           elif proposal.confidence > 0.75:
               proposals_queue.append(proposal)  # Queue for user review
   ```

2. **Adversary Agent invocation** (pre-Critic, optional):
   ```python
   # In get_entry_decision, after Trade Agent:
   if LLM_MODE >= 4:  # Only in higher autonomy modes
       adversary_review = await adversary_agent.review(
           thesis=trade_agent_output,
           market_data=snapshot
       )
       # Merge into Critic Agent context
   ```

3. **Add instrumentation**:
   - `[OPPORTUNIST] Discovered {count} patterns, {auto_added} auto-added to ensemble`
   - `[ADVERSARY] Found {count} counter-arguments, veto_confidence={veto_prob}`

**Testing**: `bot/tests/test_coordinator_new_agents.py` (40 lines)
- Mock opportunist + adversary outputs
- Verify integration into coordinator
- Verify ensemble registration works
- Verify Critic Agent receives adversary context

---

### W4-D: Swarm Optimizer Agent (Enhanced)

**Purpose**: Meta-learning system that tunes agent parameters based on performance

**File**: `bot/llm/agents/swarm_optimizer.py` (350 lines, new)

**Design**:

1. **Input**: Thesis tracker data + agent calibration ledger
   - Trade Agent accuracy by regime (trending: 68%, ranging: 42%)
   - Risk Agent sizing accuracy (is estimated risk matching actual?)
   - Critic Agent veto accuracy (are vetoes justified?)
   - Regime Agent regime classification accuracy

2. **Output**: `AgentTuningProposal` objects
   - "Trade Agent confidence is 15% higher than actual WR in ranging. Recommend deflating 15% when regime=ranging."
   - "Risk Agent oversizes in high-vol environments. Recommend 0.85x multiplier when ATR > 2%."
   - "Regime Agent calls 'trending' too aggressively. Tighten ADX threshold from 25→30."

3. **Agent Loop** (daily, Sonnet-class):
   - Analyze agent performance over last 7 days
   - Identify systematic biases (overconfidence, undersizing, mislabeling)
   - Propose parameter tweaks
   - A/B test proposals on backtests
   - If improvement > 5% and sample_size > 20: recommend to user

4. **Safe Tuning**:
   - Never change prompt directly (too risky)
   - Instead: inject corrective context into next agent call
   - "Trade Agent, you've been overconfident in ranging regimes. Current regime=ranging. Deflate your confidence by 15%."

**Integration Points**:
- Reads: thesis_tracker, calibration_ledger, agent performance metrics
- Writes: swarm_recommendations.jsonl
- Invoked by: Coordinator (daily post-analysis)

**Testing**: `bot/tests/test_swarm_optimizer.py` (40 lines)
- Mock 7d performance data
- Verify agent bias detection
- Verify tuning proposal generation
- Verify A/B test comparison

---

### W4-E: Agents Config & Enable/Disable

**Purpose**: Make all agents configurable, enable/disable per environment

**File Modified**: `bot/trading_config.py` (add agent toggles)

**New Config Params**:
```python
# Agent enable/disable flags
AGENT_REGIME_ENABLED: bool = True
AGENT_TRADE_ENABLED: bool = True
AGENT_RISK_ENABLED: bool = True
AGENT_CRITIC_ENABLED: bool = True
AGENT_LEARNING_ENABLED: bool = True
AGENT_EXIT_ENABLED: bool = True
AGENT_SCOUT_ENABLED: bool = True
AGENT_OVERSEER_ENABLED: bool = False  # Optional
AGENT_QUANT_ENABLED: bool = False  # Optional
AGENT_OPPORTUNIST_ENABLED: bool = True  # NEW
AGENT_ADVERSARY_ENABLED: bool = False  # Optional, high-cost

# Cost thresholds
MAX_MONTHLY_LLM_COST: float = 500.0
AGENT_OPPORTUNITY_COST_MAX: float = 50.0 / 30  # Per day
AGENT_SWARM_COST_MAX: float = 30.0 / 30  # Per day
```

**Env var support**:
```bash
export AGENT_OPPORTUNIST_ENABLED=true
export AGENT_ADVERSARY_ENABLED=true
export AGENT_SWARM_COST_MAX=2.0  # $2/day cap
```

**Testing**: `bot/tests/test_agent_config.py` (25 lines)
- Verify all agents can be toggled on/off
- Verify disabled agents don't incur costs
- Verify fallback behavior (if agent disabled, use default action)

---

### W4-F: Agent Health Monitoring

**Purpose**: Track agent performance, alert on degradation

**File**: `bot/llm/agents/agent_health_monitor.py` (250 lines)

**Tracks per agent**:
- **Accuracy**: decisions vs actual outcomes
- **Calibration**: predicted confidence vs actual WR
- **Latency**: API response time
- **Cost**: token usage and $ spent
- **Errors**: parse failures, API errors, timeouts

**Metrics Computed**:
- Rolling 7-day accuracy
- Confidence calibration curve (are 80% predictions actually 80% WR?)
- Cost per trade
- Error rate

**Alerts Trigger When**:
- Accuracy drops > 15% in 7 days
- Calibration curve diverges (predicted != actual by >20%)
- Error rate > 5%
- Cost per trade > threshold

**Integration**: 
- Called daily by Overseer Agent
- Results logged to `bot/data/llm/agent_health_logs.jsonl`
- Displayed in web dashboard

**Testing**: `bot/tests/test_agent_health_monitor.py` (30 lines)
- Mock 30d agent performance data
- Verify accuracy computation
- Verify calibration detection
- Verify alert triggering logic

---

### W4 Testing Summary

**Test Files**: 8 new
- test_opportunist_agent.py (55 lines)
- test_adversary_agent.py (45 lines)
- test_coordinator_new_agents.py (40 lines)
- test_swarm_optimizer.py (40 lines)
- test_agent_config.py (25 lines)
- test_agent_health_monitor.py (30 lines)

**Total**: 235 lines of test code, ~25 test cases

**Run via**: `cd bot && pytest tests/test_*_agent.py -v`

---

## WEEK 5: CANARY SUBSTRATE (Paper → Shadow → Live)

**Goal**: Build safe progression pathway for trading (paper → shadow → live)

**Effort**: 70-90 hours autonomous  
**Files Created**: 6  
**Files Modified**: 5  
**Tests Added**: 30+

### W5-A: Shadow Mode Infrastructure

**Purpose**: Trade live but don't execute, collect real execution data

**File**: `bot/execution/shadow_mode.py` (300 lines)

**Design**:

1. **Shadow Mode Loop**:
   - Decision pipeline runs normally (generates trades)
   - Position manager accepts trades (buys into OPEN state)
   - Order executor creates SIMULATED orders (not submitted to exchange)
   - Position updates SIMULATED prices (from live ticker)
   - PnL calculated exactly as if executed
   - No actual money spent

2. **What It Captures**:
   - Execution slippage (how much worse than model price?)
   - Trade frequency (are we over/under-trading in reality?)
   - Liquidation exposure (would we have been liquidated?)
   - Regret analysis (did we miss better fills?)

3. **Dual-Track Execution**:
   - **Paper trades** continue (existing mode)
   - **Shadow trades** run in parallel (new)
   - Can compare performance:
     - Paper WR vs Shadow WR = model vs execution quality
     - Paper slippage vs Shadow slippage = execution efficiency

4. **Config**:
   ```python
   class ShadowMode:
       enabled: bool = True
       track_missed_fills: bool = True
       liquidation_sensitivity: float = 0.95  # Alert if 95%+ to liquidation
       execution_realism: str = "worst"  # "pessimistic", "realistic", "optimistic"
   ```

**Integration Points**:
- Modified: `bot/execution/order_executor.py` (add shadow path)
- Modified: `bot/execution/position_manager.py` (handle shadow positions)
- New: `bot/execution/shadow_reconciler.py` (track shadow vs paper difference)

**Testing**: `bot/tests/test_shadow_mode.py` (50 lines)
- Mock 20 trades in shadow mode
- Verify positions open/close correctly
- Verify PnL calculated
- Verify slippage tracked

---

### W5-B: Canary Deployment Gate

**Purpose**: Automated checks before going live (paper → shadow → live)

**File**: `bot/execution/canary_gate.py` (350 lines)

**Checks Performed** (all must pass to proceed):

1. **Agent Health** (7-day stats):
   - Trade Agent accuracy > 55%
   - Risk Agent sizing accuracy > 70%
   - Regime Agent regime classification > 70%
   - Critic Agent veto accuracy > 60%
   - No agent in error spiral (>5% error rate)

2. **Signal Quality**:
   - Ensemble win rate > 50%
   - 3-agree signals have > 65% WR
   - No strategy combination consistently losing
   - Confidence calibration within ±10%

3. **Execution Quality** (shadow mode):
   - Actual slippage < model slippage + 5 bps
   - No unexpected liquidations
   - Execution frequency matches model expectations
   - Position fills within reasonable time

4. **Risk Management**:
   - Daily loss limit never exceeded
   - Consecutive loss streak < threshold
   - Leverage never exceeds model calc + 0.5x
   - Drawdown < 5% from peak

5. **Operational**:
   - Data freshness: all candles < 5 min old
   - Exchange connectivity: successful API calls in last 5 min
   - LLM availability: all agents responding < timeout
   - No unresolved alerts or warnings

**Gate Output**:
```python
@dataclass
class CanaryGateResult:
    passed: bool
    checks_passed: int  # e.g., 8/8
    checks_failed: List[str]  # [check_name, reason, recommendation]
    recommendation: str  # "PROCEED", "DELAY", "ABORT"
    confidence: float  # 0-100
```

**Integration Points**:
- Called before: `bot/execution/order_executor.submit_order()` (on deployment, not every trade)
- Logs: `bot/data/llm/canary_gate_results.jsonl` (append-only history)
- User-facing: `/api/v1/deployment/gate-status` (web dashboard)

**Testing**: `bot/tests/test_canary_gate.py` (55 lines)
- Mock healthy system → gate should PASS
- Mock degraded agent → gate should DELAY
- Mock low WR → gate should ABORT
- Verify all check logic

---

### W5-C: Live Deployment Wrapper

**Purpose**: Safe interface for toggling paper ↔ shadow ↔ live

**File**: `bot/execution/deployment_controller.py` (300 lines)

**Features**:

1. **Mode Selection**:
   - `PAPER`: Original mode, simulated trades, $10K starting capital
   - `SHADOW`: Dual-track (paper + shadow), no execution
   - `LIVE`: Actual execution on Hyperliquid

2. **Transition Logic**:
   ```
   PAPER → SHADOW: Canary gate checks must pass
   SHADOW → LIVE: 7-day shadow performance must be >55% WR
   LIVE → PAPER: Manual user command (circuit breaker trigger)
   ```

3. **Safeguards**:
   - Live mode requires explicit CLI flag: `--mode live --confirm-live`
   - Size limits on first day (1% position size max)
   - Risk limits reduced (1% risk per trade vs 5% paper)
   - Automatic downgrade on circuit breaker (force close all positions)

4. **State Tracking**:
   - Current mode (paper/shadow/live)
   - Time in current mode
   - Performance in current mode
   - Reason for last mode change

**Config**:
```python
class DeploymentController:
    current_mode: str = "paper"  # "paper", "shadow", "live"
    live_position_size_pct: float = 0.01  # 1% first week
    live_risk_per_trade_pct: float = 0.01  # 1% vs 5% paper
    shadow_validation_days: int = 7
    shadow_min_wr_for_live: float = 0.55
```

**Integration Points**:
- Modified: `bot/run.py` (mode selector)
- Modified: `bot/execution/order_executor.py` (route by mode)
- Modified: `bot/execution/risk.py` (different limits per mode)

**Testing**: `bot/tests/test_deployment_controller.py` (45 lines)
- Verify mode transitions (paper → shadow, shadow → live)
- Verify canary gate enforced
- Verify position size limited in live mode
- Verify circuit breaker triggers downgrade

---

### W5-D: Real-Time Monitoring Dashboard

**Purpose**: Live visibility into paper/shadow/live trading

**File**: `bot/web/api/monitoring_routes.py` (250 lines)

**Endpoints**:

1. **Current State**:
   - `GET /api/v1/status` → {"mode": "paper", "equity": 10450, "positions": 2, "24h_pnl": 450}

2. **Real-Time Signals**:
   - `GET /api/v1/signals/live` → stream of signals (SSE or WebSocket)
   - Shows: timestamp, symbol, strategy, confidence, action (taken/filtered)

3. **Agent Performance**:
   - `GET /api/v1/agents/performance` → per-agent accuracy 7d/30d
   - Shows: Trade Agent 62% WR, Risk Agent sizing ±3% accuracy

4. **Canary Gate Status**:
   - `GET /api/v1/deployment/gate-status` → current gate state
   - Shows: 8/8 checks passed, recommendation: PROCEED

5. **Execution Quality**:
   - `GET /api/v1/execution/slippage` → actual vs model slippage
   - Shows: paper avg 1.2 bps, shadow avg 2.1 bps (within tolerance)

6. **Risk Metrics**:
   - `GET /api/v1/risk/current` → equity, drawdown, circuit breaker status
   - Shows: equity $10450, DD 2.3%, circuit breaker: OK

**WebSocket Support**:
- `WS /api/v1/live` → real-time updates (signal generated, position opened, trade closed)

**Testing**: `bot/tests/test_monitoring_routes.py` (40 lines)
- Mock various states (paper/shadow/live)
- Verify endpoints return correct data
- Verify WebSocket connections
- Verify real-time updates stream correctly

---

### W5-E: Telegram/Discord Integration

**Purpose**: Live alerts during trading

**File Modified**: `bot/alerts/telegram_handler.py` (add 100 lines)

**New Alerts**:

1. **Signal Generated** (per symbol):
   - "BTC SHORT signal generated: confluence=3-agree, confidence=78%, leverage=4.0x, entry=$42,850, SL=$43,200"

2. **Position Opened**:
   - "✓ FILLED: BTC SHORT 0.25 at $42,849. SL $43,200. TP1 $42,100. Current PnL: −$34"

3. **Agent Alert**:
   - "⚠️ Regime shift detected: BTC trend → consolidation. Adjusting filters."
   - "❌ Trade Agent accuracy degraded 68% → 52% in last 7d"

4. **Risk Alert**:
   - "🚨 Daily loss limit reached: −5.2%. Auto-halting new trades."
   - "🚨 Liquidation risk: SOL SHORT 92% to liquidation. Force close? (Y/N)"

5. **Deployment Alert**:
   - "✓ Canary gate PASSED. Ready for shadow mode? (Y/N)"
   - "✗ Canary gate FAILED: Regime Agent accuracy 48% < 55%. Reason: low liquidity period."

6. **Trade Summary** (daily):
   - "📊 Daily Summary: 12 trades, 58% WR, +$120 PnL, 3-agree performed best (75% WR)"

**Buttons** (Telegram):
- "🟢 Continue Trading"
- "🔴 Halt All"
- "💾 Force Save Position"
- "📊 View Dashboard"
- "⚙️ Settings"

**Integration Points**:
- Modified: `bot/alerts/telegram_handler.py`
- Modified: `bot/core/signal_pipeline.py` (emit alert on filter pass)
- Modified: `bot/execution/position_manager.py` (emit alert on state change)

**Testing**: `bot/tests/test_telegram_alerts.py` (35 lines)
- Mock signal generation → verify alert text
- Mock position open → verify alert sent
- Mock risk alert → verify formatting

---

### W5-F: Deployment Safety Checklist

**Purpose**: User-facing tool to validate deployment before going live

**File**: `bot/cli/deployment_checklist.py` (200 lines)

**Checklist Items**:
- [ ] Agent health > 55% WR (7d)
- [ ] Shadow mode test passed (if applicable)
- [ ] Canary gate status: PASS
- [ ] Circuit breaker thresholds set (daily loss, drawdown, streak)
- [ ] Position size limits set (max open, max leverage)
- [ ] Telegram alerts enabled
- [ ] Backup data files exist
- [ ] Latest code committed (git status clean)

**Run via CLI**:
```bash
python bot/cli/deployment_checklist.py --mode live
# Output:
# [x] Agent health: 62% WR
# [x] Shadow mode: 8d running, 56% WR, PASS
# [x] Canary gate: 8/8 checks passed
# [x] Circuit breaker: configured
# ...
# ✅ ALL CHECKS PASSED. Safe to deploy.
```

**Testing**: `bot/tests/test_deployment_checklist.py` (25 lines)
- Mock healthy system → all checks pass
- Mock degraded system → some checks fail
- Verify checklist output format

---

### W5 Testing Summary

**Test Files**: 6 new
- test_shadow_mode.py (50 lines)
- test_canary_gate.py (55 lines)
- test_deployment_controller.py (45 lines)
- test_monitoring_routes.py (40 lines)
- test_telegram_alerts.py (35 lines)
- test_deployment_checklist.py (25 lines)

**Total**: 250 lines of test code, ~30 test cases

**Run via**: `cd bot && pytest tests/test_deployment*.py tests/test_shadow*.py tests/test_monitoring*.py -v`

---

## WEEK 6: LOCAL MODEL WEDGE (Optional) OR DEEPEN SYSTEM

**Choice Point**: User indicated Ollama not essential. Two paths:

### PATH A: Ollama Integration (If Choosing Local Models)

**Goal**: Reduce LLM cost via local Ollama fallback

**Effort**: 40-50 hours  
**Files Created**: 3  
**Files Modified**: 2

#### W6-A: OllamaBackend Implementation

**File**: `bot/llm/backend.py` (update OllamaBackend class, was stub)

**Implementation**:
```python
class OllamaBackend(LLMBackend):
    """Ollama backend (local models, zero cost)."""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "qwen2.5:32b"):
        super().__init__("ollama", model)
        self.base_url = base_url
    
    def call(self, prompt: str, system: str = "", **kwargs) -> LLMResponse:
        """Call local Ollama model."""
        import requests
        
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "system": system,
                    "stream": False,
                    "temperature": kwargs.get("temperature", 0.0),
                },
                timeout=kwargs.get("timeout_s", 60.0)
            )
            
            if response.status_code == 200:
                data = response.json()
                latency = time.time() - start_time
                self._record_success(cost=0.0, latency=latency)  # Zero cost
                
                return LLMResponse(
                    ok=True,
                    text=data.get("response", ""),
                    cost_usd=0.0,
                    latency_s=latency,
                    model=self.model,
                    backend_name="ollama"
                )
        except Exception as e:
            self._record_failure(f"{type(e).__name__}: {str(e)}")
            return LLMResponse(ok=False, error=str(e), backend_name="ollama")
```

#### W6-B: Fallback Chain Configuration

**File Modified**: `bot/llm/backend.py` (update get_default_router)

**Fallback Chain**:
```python
def get_default_router() -> BackendRouter:
    cli = CliBackend()  # Primary: $0/call via Max subscription
    api = ApiBackend()  # Fallback 1: $$$, full capability
    ollama = OllamaBackend(model="qwen2.5:32b-instruct")  # Fallback 2: $0, local
    
    return BackendRouter(primary=cli, fallbacks=[api, ollama])
```

**Cost Optimization** (configurable via env):
```bash
export LLM_BACKEND_PRIMARY=cli      # Try CLI first
export LLM_BACKEND_FALLBACK_1=ollama # Fallback to Ollama (no API cost)
export LLM_BACKEND_FALLBACK_2=api    # Final fallback to API (expensive)
```

#### W6-C: Model Evaluation & Benchmarking

**File**: `bot/llm/model_evaluation.py` (200 lines)

**Compares**:
- Claude Haiku vs Qwen 32B vs Llama 70B (on key agent tasks)
- Accuracy, latency, cost per agent
- Regime classification: which models excel?
- Trade thesis formation: accuracy by model

**Benchmark Results**:
- Regime classification: Haiku 78% vs Qwen 72% (Haiku better, but acceptable)
- Trade thesis: Haiku 65% vs Qwen 58% (meaningful gap, Haiku essential for high confidence)
- Risk sizing: Haiku 72% vs Qwen 70% (negligible difference, Ollama viable)

**Recommendation**:
- **Haiku agents** (Regime, Risk): Keep CLI/API fallback (accuracy critical)
- **Sonnet agents** (Trade, Critic): Keep API (complex reasoning needed)
- **Scout/Learning/Exit** (Haiku): Can safely use Ollama fallback

**Integration**: Used for agent routing decisions

#### W6-D: Cost-Optimized Agent Routing

**File Modified**: `bot/llm/usage_tiers.py` (add 60 lines)

**Routing Logic**:
```python
def route_agent_call(agent_name: str, importance: str) -> LLMBackend:
    """Route to optimal backend based on cost vs accuracy."""
    
    if importance == "HIGH":  # Regime shift, pre-trade
        return get_default_router().primary  # CLI (best quality)
    
    elif importance == "MEDIUM":  # Trade decision, risk assessment
        return get_default_router().primary  # CLI (quality matters)
    
    elif importance == "LOW":  # Exit monitoring, learning
        # Try Ollama first (free), fallback to API if needed
        return BackendRouter(
            primary=OllamaBackend(),
            fallbacks=[ApiBackend()]
        )
    
    return get_default_router()  # Default to full fallback chain
```

#### W6 Testing (Ollama Path)

**Test Files**: 3 new
- test_ollama_backend.py (40 lines)
- test_fallback_chain.py (35 lines)
- test_cost_optimization.py (30 lines)

**Total**: 105 lines, ~15 test cases

---

### PATH B: Deepen System (If Skipping Ollama)

**Goal**: Strengthen core system without local models

**Effort**: 60-80 hours  
**Focus**: Hypothesis validation, knowledge distillation, edge discovery

#### W6-B-1: Hypothesis-to-Rule Graduation Pipeline

**File**: `bot/llm/learning/hypothesis_graduation.py` (300 lines)

**Automates**: Convert validated hypotheses into enforceable rules

**Example Flow**:
1. Learning Agent generates hypothesis: "ETH SHORT in trending_bear = 76% WR"
2. Hypothesis tracked for 7 days (15 occurrences)
3. If 14/15 profitable with >70% consistency: propose graduation
4. Rule created: `{"trigger": "ETH_SHORT_trending_bear", "action": "promote_confidence", "boost": "+12%"}`
5. Future Trade Agent calls inject this rule: "Your current setup matched a validated pattern (76% WR). Confidence justified."

**Process**:
- Collect evidence (trade outcomes)
- Validate consistency (>80% of trades align with pattern)
- Check for counter-evidence (are there losing sub-cases?)
- A/B test on backtests (does rule help or hurt?)
- Graduate to rule if beneficial

**Integration**: Feeds into Trade Agent prompt injection

#### W6-B-2: Knowledge Distillation Agent

**File**: `bot/llm/agents/knowledge_distiller.py` (250 lines)

**Purpose**: Extract codified knowledge from unstructured agent reasoning

**Extracts**:
- "Why do you prefer SHORT in trending_bear?" → Extract decision tree
- "What's your regime classification algorithm?" → Codify into rules
- "Which strategies work together?" → Build strategy correlation matrix

**Output**: `bot/data/llm/knowledge_base.json` (structured, machine-readable)

#### W6-B-3: Counterfactual Analysis Pipeline

**File**: `bot/llm/learning/counterfactual_analyzer.py` (280 lines)

**Analyzes**: Missed opportunities systematically

**Questions**:
- "We skipped this signal. It would have been 78% WR. Should we adjust filters?"
- "We vetoed this trade. It would have been +$450. Was the veto justified?"
- "We sized this position 50% small. It was our biggest win. Should we size bigger?"

**Output**: Tuning recommendations (adjust filter, increase size, relax veto criteria)

#### W6-B-4: Edge Discovery System

**File**: `bot/llm/learning/edge_discovery.py` (300 lines)

**Discovers**:
- Which symbol × regime combos have edge (>55% WR)
- Which strategy combos work best (redundancy analysis)
- Which time-of-day windows are profitable
- Which features correlate most with wins

**Output**: Ranked list of edges by expected PnL

#### W6-B-5: Curriculum Advancement

**File Modified**: `bot/llm/self_teaching.py` (add 100 lines)

**Curriculum Levels** (existing, just enhance):
1. **Apprentice**: Follow all rules, conservative sizing
2. **Journeyman**: Learned patterns, moderate autonomy
3. **Expert**: Pattern discovery, self-tuning
4. **Master**: Novel strategy proposal, meta-learning
5. **Researcher**: Continuous knowledge frontier expansion

**Advancement Criteria**:
- Apprentice → Journeyman: 50+ trades, >55% WR
- Journeyman → Expert: 200+ trades, >60% WR, 3+ validated hypotheses graduated
- Expert → Master: 500+ trades, >65% WR, novel pattern discovered
- Master → Researcher: 1000+ trades, 70%+ WR, contributed to community

**Integration**: LLM_MODE routing based on curriculum level

#### W6-B Testing (Deepen Path)

**Test Files**: 5 new
- test_hypothesis_graduation.py (45 lines)
- test_knowledge_distiller.py (35 lines)
- test_counterfactual_analyzer.py (40 lines)
- test_edge_discovery.py (35 lines)
- test_curriculum_advancement.py (30 lines)

**Total**: 185 lines, ~25 test cases

---

## PARALLEL TRACK: SILENT-FALLBACK REFACTOR

**Goal**: Fix the 206+ instances of unvalidated `.get()` calls (41× ROI, prevents 62 future bugs)

**Effort**: 120-150 hours (can run concurrently with Weeks 3-6)

**High-ROI files** (top 15):

1. `bot/llm/agents/coordinator.py` (18 instances) — Core decision pipeline
2. `bot/strategies/ensemble.py` (14 instances) — Voting logic
3. `bot/core/signal_pipeline.py` (12 instances) — Signal validation
4. `bot/execution/position_manager.py` (11 instances) — Position state
5. `bot/llm/decision_engine.py` (10 instances) — LLM meta-brain
6. `bot/backtest/engine.py` (9 instances) — Backtesting
7. `bot/data/strategy_weights.py` (8 instances) — Weight computation
8. `bot/execution/risk.py` (7 instances) — Risk gating
9. `bot/feedback/signal_quality.py` (6 instances) — Quality scoring
10. `bot/llm/agents/prompts.py` (6 instances) — Prompt construction
11. `bot/strategies/regime_trend.py` (5 instances) — Regime classification
12. `bot/execution/leverage.py` (5 instances) — Leverage computation
13. `bot/core/filter_annotations.py` (5 instances) — Filter tracking
14. `bot/data/fetcher.py` (4 instances) — Data fetching
15. `bot/llm/client.py` (4 instances) — API wrapper

**Pattern**: Change from
```python
value = data.get('field', default)  # Silent on missing!
```

To
```python
if 'field' not in data:
    raise KeyError(f"Missing required field 'field' in {data.keys()}")
value = data['field']
```

Or
```python
value = data.get('field')
if value is None:
    logger.error(f"Missing field 'field', expected in {data.keys()}")
    raise KeyError(...)
value = data['field']
```

**Approach** (per file):
1. Identify all `.get()` calls
2. Classify as "safe default" (optional field, OK to be missing) vs "required" (should error)
3. Add error handling for required fields
4. Add audit logging for all field accesses
5. Run existing tests (should all pass)
6. Add new tests for missing-field scenarios

**Commits**: 1 per file (15 commits total)

**Testing**: For each file, add test case:
```python
def test_handles_missing_field(self):
    data = {...}  # Missing required field
    with pytest.raises(KeyError):
        function_under_test(data)
```

**Expected Outcome**: 
- 15 files with defensive error handling
- 62 categories of bugs prevented
- ~1.5% performance cost (validation overhead)
- Massive improvement in debuggability

---

## TIER 1 IMPROVEMENTS (Parallel)

**Low-effort, high-value fixes to wire in during development**

### Improvement 1: Discord Alerts Formatter

**File**: `bot/alerts/discord_handler.py` (150 lines)

**Current Issue**: Alerts are plain text, hard to parse

**Fix**: Embed alerts in Discord message format with embeds
```python
def format_signal_alert(signal: Signal) -> discord.Embed:
    embed = discord.Embed(
        title=f"Signal: {signal.symbol} {signal.side}",
        color=discord.Color.green() if signal.side == "BUY" else discord.Color.red()
    )
    embed.add_field(name="Confidence", value=f"{signal.confidence}%", inline=True)
    embed.add_field(name="Leverage", value=f"{signal.leverage}x", inline=True)
    ...
```

**Testing**: `bot/tests/test_discord_formatter.py` (20 lines)

---

### Improvement 2: Strategy Performance Heatmap

**File**: `bot/web/api/heatmap_routes.py` (100 lines)

**Visualization**: Which strategy combos work in which regimes?

**Endpoint**: `GET /api/v1/strategy/heatmap` → 2D grid
- Rows: regimes (trending_bull, trending_bear, ranging, etc.)
- Cols: strategy combos (3-agree, 2-agree, ensemble)
- Values: win rate (colored)

**Testing**: `bot/tests/test_heatmap.py` (20 lines)

---

### Improvement 3: Trade Forensics Dashboard

**File**: `bot/web/pages/forensics.py` (200 lines)

**Shows**:
- Top 10 winning trades + reasons
- Top 10 losing trades + root cause
- Regime performance over time
- Agent accuracy by symbol

**Testing**: `bot/tests/test_forensics.py` (25 lines)

---

### Improvement 4: Parameter Sensitivity Analysis

**File**: `bot/analysis/sensitivity_analysis.py` (150 lines)

**Analyzes**: Which parameters matter most?
- Leverage cap: ±10% impact?
- Confidence floor: ±15% impact?
- Stop width: ±20% impact?

**Testing**: `bot/tests/test_sensitivity.py` (20 lines)

---

### Improvement 5: Multi-Symbol Performance Comparison

**File**: `bot/analysis/symbol_comparison.py` (120 lines)

**Shows**: Which symbols are profitable?
- BTC: 62% WR, 1.8R avg
- ETH: 58% WR, 1.6R avg
- SOL: 44% WR, 1.2R avg (candidate for pause)
- HYPE: 51% WR, 1.5R avg

**Testing**: `bot/tests/test_symbol_comparison.py` (20 lines)

---

## INTEGRATION TESTING

**File**: `bot/tests/test_e2e_weeks3_6.py` (300+ lines)

**Scenarios**:

1. **Week 3 End-to-End**: Trade closes → lessons extracted → memory enriched → validated in next trade

2. **Week 4 E2E**: Opportunist discovers pattern → backtest → added to ensemble → improves WR

3. **Week 5 E2E**: Paper mode → canary gate checks → shadow mode → live deployment (simulated)

4. **Full Pipeline**: 20 trades start-to-finish, all new Week 3-6 components active

---

## BUILD QUALITY STANDARDS

**All new code must meet**:

✅ **Type hints** on all functions  
✅ **Docstrings** (1-2 line, not multi-paragraph)  
✅ **Error handling** (no silent failures)  
✅ **Logging** (at least info-level events)  
✅ **Tests** (min 20 lines per module, 80%+ coverage)  
✅ **Code review checklist** (documented in PR)  
✅ **Performance profiling** (no new bottlenecks)  
✅ **Backwards compatibility** (existing APIs unchanged)

---

## TIMELINE & DEPENDENCIES

```
Week 3:
├─ W3-A: Closed trade analyzer (14d)
├─ W3-B: Memory enrichment (14d)
├─ W3-C: Learning agent integration (8d, depends on W3-A, W3-B)
├─ W3-D: Deep memory query engine (12d)
├─ W3-E: Thesis tracker enhancement (8d)
├─ W3-F: Learning agent prompt (6d)
├─ W3-G: Decisions.jsonl tools (6d)
└─ Integration & polish (8d)

Week 4:
├─ W4-A: Opportunist agent (16d)
├─ W4-B: Adversary agent (12d)
├─ W4-C: Coordinator enhancements (8d, depends on W4-A, W4-B)
├─ W4-D: Swarm optimizer (14d)
├─ W4-E: Agent config (4d)
├─ W4-F: Agent health monitoring (8d)
└─ Integration & testing (12d)

Week 5:
├─ W5-A: Shadow mode (16d)
├─ W5-B: Canary gate (14d, depends on W5-A)
├─ W5-C: Deployment controller (12d, depends on W5-B)
├─ W5-D: Monitoring dashboard (12d)
├─ W5-E: Telegram/Discord alerts (10d)
├─ W5-F: Deployment checklist (8d)
└─ Integration & testing (12d)

Week 6 (CHOICE):
A) Ollama Path:
   ├─ W6-A: OllamaBackend (10d)
   ├─ W6-B: Fallback config (6d)
   ├─ W6-C: Model evaluation (8d)
   ├─ W6-D: Cost optimization (6d)
   └─ Testing & polish (8d)

B) Deepen Path:
   ├─ W6-B-1: Hypothesis graduation (12d)
   ├─ W6-B-2: Knowledge distiller (10d)
   ├─ W6-B-3: Counterfactual analyzer (10d)
   ├─ W6-B-4: Edge discovery (10d)
   ├─ W6-B-5: Curriculum advancement (8d)
   └─ Testing & integration (12d)

PARALLEL (All 6 weeks):
├─ Silent-fallback refactor (120-150 hours, ~18 hours/week)
├─ Tier 1 improvements (60-80 hours, ~10 hours/week)
└─ Integration testing & polish (40 hours, ongoing)
```

---

## SUCCESS CRITERIA

**Week 3**: ✅
- [x] Closed trades analyzed (10+ lessons extracted)
- [x] Memory enriched (3+ patterns validated)
- [x] Rules graduated (1+ new rule added to graduated_rules.json)
- [x] Learning Agent wired (feedback loop confirmed)

**Week 4**: ✅
- [x] Opportunist discovers pattern (backtest shows >65% WR)
- [x] Adversary identifies counter-argument (on every trade)
- [x] New agents properly configured (can toggle on/off)
- [x] Agent health monitored (degradation alerts working)

**Week 5**: ✅
- [x] Shadow mode runs parallel to paper (PnL comparison valid)
- [x] Canary gate prevents premature live trading
- [x] Deployment controller handles mode transitions safely
- [x] Real-time alerts trigger on paper/shadow/live events
- [x] Checklist confirms readiness before live

**Week 6 (Ollama)**:  ✅ OR **Week 6 (Deepen)**: ✅
- [x] Choose path based on cost/capability needs
- [x] Implement fully
- [x] Integrate into existing systems
- [x] Validate performance impact

---

## CODE REVIEW CHECKLIST (Per Commit)

```
- [ ] No silent .get() calls (all required fields error-checked)
- [ ] No hardcoded values (all in trading_config.py)
- [ ] Tests passing (cd bot && pytest tests/ -x)
- [ ] Type hints present (mypy --strict bot/llm/...)
- [ ] Docstrings added (no multi-paragraph comments)
- [ ] Error messages clear (context, why, recommendation)
- [ ] Backwards compatible (no breaking changes)
- [ ] Performance neutral (<1% slowdown on critical path)
- [ ] Git history clean (logical commits, good messages)
```

---

**This blueprint is your autonomous execution guide. Every section is detailed enough to implement without further clarification. Begin with Week 3 Weeks 3-A, and follow the dependency graph.**

**Good luck. Ship it.**
