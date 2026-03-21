# LLM Decision System — Code Reference Guide

Quick lookup for developers and auditors.

---

## AGENT DEFINITIONS

### Agent Roles Enum
**File**: `bot/llm/agents/base.py:17-43`

```python
class AgentRole(str, Enum):
    REGIME = "regime"              # Market regime analysis
    TRADE = "trade"                # Trade evaluation
    RISK = "risk"                  # Risk & position sizing
    LEARNING = "learning"          # Post-trade learning
    CRITIC = "critic"              # Self-critique / meta-review
    EXIT = "exit"                  # Exit intelligence
    SCOUT = "scout"                # Idle-time preparation
    OVERSEER = "overseer"          # System-level meta-optimizer
    QUANT = "quant"                # Statistical analysis
    # + Phase 3/4 strategic agents
```

### Default Agent Configs
**File**: `bot/llm/agents/base.py:75-211`

Defines max_tokens, timeout_s, and required flag for each agent.

**Required agents**: REGIME, TRADE
**Optional agents**: All others

---

## COORDINATOR ORCHESTRATION

### Entry Point
**File**: `bot/llm/agents/coordinator.py:146-161`

```python
def get_trading_decision(
    snapshot_data: dict,
    trigger_reason: str = "",
    model_for_trigger: Optional[str] = None,
) -> Optional[LLMDecision]:
    """Run the multi-agent pipeline."""
```

### Pipeline Steps
**File**: `bot/llm/agents/coordinator.py:162-400`

1. **Regime Agent Call**: Line 170-198
   - Input building: `_build_regime_input()`
   - Fallback regime: "unknown" with conf=0.3
   - Write to scratchpad: Line 200-210

2. **Quant Agent Call** (Optional): Line 212-234
   - Input: market data + regime
   - Write to scratchpad: Line 222-230

3. **Trade Agent Call**: Line 236-258
   - Input building: `_build_trade_input()`
   - Fallback action: "skip" with conf=0.0
   - Write to scratchpad: Line 254-258

4. **Risk Agent Call** (Optional): Line 260-269
   - Input building: `_build_risk_input()`
   - Graceful degradation: Line 268-269

5. **Consistency Check**: Line 284-320
   - Validator: `check_pipeline_consistency()`
   - On critical issue: Override trade to skip (halve conf)
   - Line 313-320

6. **Quant Adjustment** (Post-consistency): Line 322-365
   - Confidence adjustment: -0.15 to +0.15
   - Clamping: Line 331-332
   - Graduated response: Low confidence = noise flag

7. **Critic Agent Call** (Optional): Line 271-282
   - Input building: `_build_critic_input()`
   - Read all prior outputs for stress-testing

8. **Output Merger**: Line 380-420
   - Synthesize all agents into single LLMDecision
   - Calculate consistency score
   - Return decision or None

### Agent Call Method
**File**: `bot/llm/agents/coordinator.py:1427-1550`

```python
def _call_agent(
    self,
    role: AgentRole,
    input_json: str,
    fallback_model: Optional[str] = None,
) -> AgentOutput:
```

**Key steps**:
1. Check if agent enabled: Line 1435-1436
2. Get prompt from registry: Line 1438-1440
3. Inject protocol + context: Line 1442-1484
4. Call LLM: Line 1488-1495
5. Parse JSON: Line 1522
6. Validate and return: Line 1524+

---

## AGENT PROMPTS

### All 7 Prompts
**File**: `bot/llm/agents/prompts.py`

| Agent | Line | Prompt Size | Key Output |
|-------|------|------------|-----------|
| Regime | 19-51 | ~500 tokens | rg, conf, bias, transition, outlook |
| Trade | 55-400 | ~1400 tokens | a, c, thesis, ea, mu, n |
| Risk | 410-520 | ~300 tokens | position_size, flags |
| Critic | 530-650 | ~400 tokens | verdict, adjusted_action, confidence_adj |
| Learning | 660-770 | ~300 tokens | lesson, category, strength, hypothesis |
| Exit | 780-880 | ~400 tokens | action, new_sl/tp, reason |
| Scout | 998-1054 | ~300 tokens | watchlist, regime_forecast, alerts |

---

## AUTONOMY AND MODE HANDLING

### Autonomy Levels (0-5)
**File**: `bot/llm/autonomy.py:30-36`

```python
class LLMMode(IntEnum):
    OFF = 0
    ADVISORY = 1
    VETO_ONLY = 2
    SIZING = 3
    DIRECTION = 4
    FULL = 5
```

### Get Current Mode
**File**: `bot/llm/autonomy.py:39-78`

```python
def get_llm_mode() -> LLMMode:
    """Read from LLM_MODE env, enforce roadmap phase ceiling."""
```

- Reads `LLM_MODE` env var
- Clamps to roadmap phase max (if `ROADMAP_ENFORCE=true`)
- Line 54-76: Phase enforcement logic

### Mode-Specific Routing
**File**: `bot/llm/autonomy_router.py:32-424`

| Function | Lines | What It Does |
|----------|-------|---|
| `apply_autonomy_mode()` | 32-72 | Route to correct mode handler |
| `_mode_off()` | 78-85 | Ignore LLM |
| `_mode_advisory()` | 88-121 | Log LLM, track divergence |
| `_mode_veto_only()` | 124-191 | LLM can reject trades |
| `_mode_sizing()` | 194-253 | LLM scales position size |
| `_mode_direction()` | 256-335 | LLM picks direction |
| `_mode_full()` | 338-424 | LLM drives everything |

**Key safety**: All modes clamp size_multiplier (0.0-2.5), enforce confidence floor (0.60)

---

## RISK GATING

### Main Gate Function
**File**: `bot/llm/risk_gating.py:44-150`

```python
def gate_decision(decision: LLMDecision, risk: RiskContext) -> GatedResult:
    """Apply 11 safety rules."""
```

**Rules** (priority order):
1. Circuit breaker active → reject
2. Confidence < 0.60 → reject
3. Daily loss limit → reject
4. Max positions → reject
5. Volatility cap → reject
6. Panic regime + conf < 0.70 → reject
7. Unknown regime + non-flat → reject
8. Low liquidity + non-flat → reject
9. 4+ consecutive losses + conf < 0.68 → reject
10. Flip + conf < 0.65 → reject
11. Strategy weight sanity → reject

**No exceptions**: All 11 rules are hardcoded, LLM cannot override.

---

## VALIDATION AND ERROR HANDLING

### JSON Parsing
**File**: `bot/llm/validation.py:86-160`

```python
def parse_llm_response(raw_text: str) -> Tuple[Optional[dict], Optional[str]]:
```

Handles:
- Empty responses
- Markdown code fences (```json```)
- Multiple JSON objects (takes first)
- Invalid JSON (returns None)

### Key Expansion
**File**: `bot/llm/validation.py:57-83`

Maps short keys to full:
- `a` → `action`
- `c` → `confidence`
- `rg` → `regime`
- `sz` → `size_multiplier`
- `ea` → `entry_adjustment`

### Schema Validation
**File**: `bot/llm/validator.py` (if exists)

Validates:
- action in {proceed, flat, flip}
- confidence in [0.0, 1.0]
- regime in VALID_REGIMES
- confidence in required field

### Error Recovery
**File**: `bot/llm/recovery.py:29-100`

```python
class ErrorStats:
    total_calls: int
    total_errors: int
    consecutive_errors: int
    error_rate: float
```

If `consecutive_errors >= 3` → disable LLM for 30 min

---

## DECISION ENGINE ENTRY POINT

### Main Function
**File**: `bot/llm/decision_engine.py:197-300`

```python
def get_trading_decision(
    markets: List[MarketSnapshot],
    global_context: GlobalContext,
    risk_context: RiskContext,
    active_positions: Optional[List[Dict[str, Any]]] = None,
    mode: Optional[LLMMode] = None,
    use_compact_prompt: bool = False,
    trigger_reason: str = "",
    trigger_context: str = "",
    event_triggered: bool = False,
) -> DecisionResult:
```

**Flow**:
1. Check mode: Line 228-232
2. Build snapshot: Line 235-243
3. Check throttle: Line 245-248
4. Call agent coordinator: Line 260+ (if multi-agent enabled)
5. Apply autonomy mode: Line 320+ (if single-agent path)
6. Risk gate: Line 330+
7. Log audit: Line 340+
8. Return DecisionResult

### Decision Result
**File**: `bot/llm/decision_engine.py:182-195`

```python
@dataclass
class DecisionResult:
    decision: Optional[LLMDecision]  # The LLM decision (or None)
    reason: str                      # "success", "throttled", "off", etc.
    source: str                      # "llm", "cache", "none"
    usage: dict                      # Token usage
    is_veto: bool                    # Was this a veto?
    original_action: str             # Pre-mode-constraint action
```

---

## LEARNING PIPELINE

### Learning Integration
**File**: `bot/llm/agents/learning_integration.py:24-74`

```python
def process_agent_lesson(
    lesson_data: Dict[str, Any],
    trade_data: Dict[str, Any],
) -> None:
```

Injects lesson into:
1. **Post-trade learner**: Line 54
2. **Deep memory**: Line 57
3. **Hypothesis tracker**: Line 61
4. **Knowledge base**: Line 64
5. **Calibration ledger**: Line 73

### Learning Agent Output Format
**File**: `bot/llm/agents/prompts.py` (Learning section)

```json
{
  "lesson": "string describing the lesson",
  "category": "pattern_loss|regime_mismatch|funding_cost|setup_discovery",
  "strength": "weak|medium|strong",
  "applies_to": {
    "symbol": "SOL,BTC,ETH",
    "regime": "trend|range|...",
    "side": "long|short|both"
  },
  "hypothesis": "optional: testable prediction",
  "thesis_correct": true|false
}
```

---

## EXIT INTELLIGENCE

### Exit Engine
**File**: `bot/llm/exit_engine.py:39-83`

```python
class ExitEngine:
    def should_evaluate(self, symbol: str) -> bool:
        """Check 2-min cooldown per symbol."""
    
    def apply_exit_decision(self, decision, position, current_price) -> dict:
        """Apply with safety gating."""
```

### Safety Gates (Non-Negotiable)
**File**: `bot/llm/exit_engine.py:85-150`

1. **SL can only tighten** (move closer to entry)
2. **TP can only widen** (increase profit target)
3. **Early close** requires confidence >= 0.60
4. **Partial close** requires remaining qty > min_qty * 2

### Exit Decision Output
**File**: `bot/llm/exit_types.py` (if exists)

```json
{
  "exit_action": "hold|tighten_sl|widen_tp|partial_close|full_close",
  "confidence": 0.0-1.0,
  "urgency": "low|medium|high|critical",
  "new_sl": null | float,
  "new_tp": null | float,
  "close_qty_pct": null | float,
  "reason": "string",
  "thesis_status": "valid|weakening|invalid"
}
```

---

## SHARED CONTEXT AND SCRATCHPAD

### Shared Context Builder
**File**: `bot/llm/agents/shared_context.py`

```python
def build_shared_context_block(
    agent_role: str,
    scratchpad,
    shared_lessons,
    include_axioms: bool = False,
    include_regime_map: bool = False,
    include_strategy_theory: bool = False,
    current_regime: str = "",
) -> str:
```

Builds context visible to all agents (in scratchpad)

### Pipeline Scratchpad
**File**: `bot/llm/agents/shared_context.py` (if separate file)

```python
def get_pipeline_scratchpad():
    """Get the shared scratchpad for current pipeline."""
    
def reset_pipeline_scratchpad():
    """Reset scratchpad at start of pipeline."""
```

Agents write to scratchpad:
```
scratchpad.write("regime", "regime", "trend")
scratchpad.write("regime", "regime_conf", 0.85)
scratchpad.write("trade", "action", "go")
```

---

## CONSISTENCY CHECKING

### Consistency Checker
**File**: `bot/llm/agents/consistency_checker.py`

```python
def check_pipeline_consistency(
    regime_data: dict,
    trade_data: dict,
    risk_data: Optional[dict],
    critic_data: Optional[dict],
) -> ConsistencyReport:
```

**Validates**:
- Regime format (rg, conf, bias, etc.)
- Trade action aligns with regime (trend regime → no short flip)
- Risk sizing makes sense (not negative, not extreme)
- Critic challenge is justified

**Report structure**:
```python
@dataclass
class ConsistencyReport:
    is_consistent: bool
    score: float (0.0-1.0)
    issues: List[ConsistencyIssue]
    summary(): str
```

**On critical issue**: Force trade to "skip" (halve confidence)

---

## THOUGHT PROTOCOL INJECTION

### Protocol Builder
**File**: `bot/llm/agents/thought_protocol.py:223-245`

```python
def build_protocol_prefix(agent_role: str) -> str:
    """Build compact reasoning protocol for agent prompt."""
    return "REASONING CHAIN: 1.OBSERVE(...) 2.RECALL(...) 3...."
```

**Per-agent protocols** (Line 47-205):
- REGIME_AGENT_PROTOCOL
- TRADE_AGENT_PROTOCOL
- RISK_AGENT_PROTOCOL
- CRITIC_AGENT_PROTOCOL
- LEARNING_AGENT_PROTOCOL
- EXIT_AGENT_PROTOCOL
- SCOUT_AGENT_PROTOCOL

**Injected into prompt** (coordinator.py:1476-1484):
```python
enhanced_prompt = f"{protocol_prefix}\n\n{enhanced_prompt}\n\nSHARED CONTEXT: {shared_context}"
```

---

## AUDIT LOGGING

### Decisions JSONL Log
**File**: `bot/llm/decision_engine.py:98-111`

```python
def _log_audit(entry: dict):
    """Append to data/llm/decisions.jsonl"""
    with open(_AUDIT_PATH, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")
```

Each entry includes:
- timestamp
- trigger_reason
- mode (LLMMode)
- regime
- action
- confidence
- source
- is_veto
- agent_pipeline_results (all agent outputs)
- risk_gating_result

### Agent Output Logging
**File**: `bot/llm/agents/agent_output_logger.py`

Each agent call logged with:
- timestamp
- agent role
- raw LLM response
- parsed data
- model used
- latency_ms
- input_tokens
- output_tokens
- error (if any)

### Exit Decision Logging
**File**: `bot/llm/exit_engine.py:32-33`

```python
_EXIT_LOG_DIR = os.path.join("data", "logs")
_EXIT_LOG_FILE = os.path.join(_EXIT_LOG_DIR, "exit_decisions.jsonl")
```

Each exit decision logged with:
- timestamp
- symbol, side
- action taken
- old/new levels
- applied (true/false)
- reason
- confidence
- unrealized P&L

---

## COST TRACKING

### Cost Tracker
**File**: `bot/llm/cost_tracker.py`

```python
def get_cost_tracker():
    """Get global cost tracker instance."""

def record_call(input_tokens: int, output_tokens: int, model: str):
    """Record LLM call cost."""
```

Tracks:
- Daily spend
- Per-model distribution
- Budget enforcement

### Usage Tiers (Smart Model Routing)
**File**: `bot/llm/usage_tiers.py`

```python
def get_active_tier() -> str:
    """Get active LLM usage tier (CONSERVATIVE/RECOMMENDED/AGGRESSIVE/UNLEASHED)"""
```

Routes based on trigger importance:
- HIGH_VALUE (PRE_TRADE, REGIME_SHIFT) → Opus
- MEDIUM (POSITION_CLOSED, HIGH_CONFIDENCE) → Sonnet
- LOW (PERIODIC, MEMORY_EVENT) → Haiku

---

## CONFIGURATION

### Environment Variables

```bash
# Core autonomy
LLM_MODE=0|1|2|3|4|5                    # Autonomy level (default: 0)
ROADMAP_ENFORCE=true|false              # Enforce phase ceiling (default: true)

# Multi-agent system
LLM_MULTI_AGENT=true|false              # Enable agent pipeline (default: false)

# Usage tier system
LLM_USAGE_TIER=CONSERVATIVE|RECOMMENDED|AGGRESSIVE|UNLEASHED

# Per-agent model overrides
AGENT_REGIME_MODEL=claude-haiku-...     # Override Regime Agent model
AGENT_TRADE_MODEL=claude-sonnet-...     # Override Trade Agent model
AGENT_EXIT_MODEL=claude-haiku-...
# ... etc

# Per-agent enable/disable
AGENT_EXIT_ENABLED=true|false
AGENT_SCOUT_ENABLED=true|false
AGENT_CRITIC_ENABLED=true|false
AGENT_QUANT_ENABLED=true|false

# Exit evaluation cooldown
EXIT_EVAL_COOLDOWN_S=120                # Seconds between exit evals per symbol
```

### Roadmap Phase Ceiling

**File**: `bot/llm/knowledge_roadmap.py` (if exists)

```python
PHASE_CONFIGS = {
    0: {"name": "PHASE_0_BASELINE", "llm_mode_max": 0},      # OFF
    1: {"name": "PHASE_1_ADVISORY", "llm_mode_max": 1},      # ADVISORY
    2: {"name": "PHASE_2_VETO", "llm_mode_max": 2},          # VETO_ONLY
    3: {"name": "PHASE_3_SIZING", "llm_mode_max": 3},        # SIZING
    4: {"name": "PHASE_4_DIRECTION", "llm_mode_max": 4},     # DIRECTION
    5: {"name": "PHASE_5_FULL", "llm_mode_max": 5},          # FULL
}
```

Set current phase to control max autonomy level.

---

## QUICK DEBUGGING

### Check If Multi-Agent Enabled
```python
from llm.agents.coordinator import is_multi_agent_enabled

if is_multi_agent_enabled():
    print("Multi-agent mode ACTIVE")
else:
    print("Multi-agent mode OFF, using monolithic pipeline")
```

### Check Current LLM Mode
```python
from llm.autonomy import get_llm_mode, LLMMode

mode = get_llm_mode()
print(f"Current mode: {mode.name} (value={mode.value})")
```

### Check Error Stats
```python
from llm.recovery import get_error_stats

stats = get_error_stats()
print(f"Error rate: {stats.error_rate:.1f}%")
print(f"Consecutive errors: {stats.consecutive_errors}")
if stats.consecutive_errors >= 3:
    print("⚠️ LLM disabled due to error circuit breaker!")
```

### Check Last Decision
```python
from llm.decision_engine import get_cached_decision, get_recent_decisions

decision = get_cached_decision()
if decision:
    print(f"Cached decision: {decision.action} (conf={decision.confidence:.2f})")

recent = get_recent_decisions(5)
for d in recent:
    print(f"  {d.action} @ {d.confidence:.2f}")
```

### Access Audit Log
```bash
tail -f bot/data/llm/decisions.jsonl | jq '.'
```

### Access Agent Logs
```bash
tail -f bot/data/logs/agent_decisions.jsonl | jq '.agent, .parsed_data'
```

---

**End of Code Reference**
