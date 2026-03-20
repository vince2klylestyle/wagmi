# Phase 1 Audit Checklist - Complete System Verification

## Pre-Audit: What We Built

- ✅ `bot/feedback/single_signal_audit.py` (500 lines)
- ✅ `bot/llm/agents/swarm_optimizer.py` (400 lines)
- ✅ `bot/llm/agents/swarm_agent_prompts.py` (400 lines)
- ✅ `bot/feedback/swarm_feedback_loop.py` (350 lines)
- ✅ `bot/llm/agents/swarm_master.py` (300 lines)

**Total: ~2,100 lines of code**

---

## Audit 1: Code Quality & No Hallucinations

### 1.1 Import Verification ✓

**Test**: All imports must resolve without ModuleNotFoundError

```python
# MUST VERIFY:
from feedback.single_signal_audit import SingleSignalAudit
from llm.agents.swarm_optimizer import SwarmOptimizer
from llm.agents.swarm_master import SwarmMaster
from feedback.swarm_feedback_loop import SwarmFeedbackLoop
```

**Status**: Need to verify paths work when called from `bot/` directory

### 1.2 Dataclass Definitions ✓

**Verify all dataclasses are properly defined:**
- `SingleSignalTrade` - 15+ fields defined ✓
- `PerformanceMetrics` - 14+ fields defined ✓
- `SniperSetup` - 10+ fields defined ✓
- `Recommendation` - 7+ fields defined ✓
- `SwarmRecommendations` - 5+ fields defined ✓
- `PromotedRule` - 6+ fields defined ✓

### 1.3 Method Signatures ✓

**Verify all methods have correct signatures and return types:**

| Module | Method | Returns | Status |
|--------|--------|---------|--------|
| SingleSignalAudit | extract_single_signals() | List[SingleSignalTrade] | ✓ |
| SingleSignalAudit | compute_metrics() | Dict[str, PerformanceMetrics] | ✓ |
| SingleSignalAudit | find_sniper_setups() | List[SniperSetup] | ✓ |
| SingleSignalAudit | identify_losers() | List[Tuple] | ✓ |
| SwarmOptimizer | optimize_single_signals() | SwarmRecommendations | ✓ |
| SwarmFeedbackLoop | process_recommendations() | None | ✓ |
| SwarmMaster | daily_optimization_run() | Dict[str, Any] | ✓ |

### 1.4 Error Handling ✓

**Verify try-catch blocks:**
- [ ] TradeLogger.read_recent() has try-catch
- [ ] JSON parsing has try-catch
- [ ] File I/O has try-catch
- [ ] LLM calls have try-catch
- [ ] Config updates have try-catch

### 1.5 Configuration Files ✓

**Verify all config file operations:**
- [ ] Files created in correct directory (bot/data/feedback/swarm/)
- [ ] Directories created with mkdir(parents=True)
- [ ] Append-only logging (no truncation)
- [ ] JSON files have valid structure
- [ ] Config overrides don't break existing code

---

## Audit 2: Wiring Verification - End-to-End Flow

### 2.1 Data Flow: Extract → Analyze → Recommend

```
SingleSignalAudit.extract_single_signals()
    ↓ Returns: List[SingleSignalTrade]
SingleSignalAudit.compute_metrics()
    ↓ Returns: Dict[str, PerformanceMetrics]
SwarmOptimizer.optimize_single_signals(audit_data)
    ↓ Returns: SwarmRecommendations
SwarmFeedbackLoop.process_recommendations()
    ↓ Applies to: trading_config_swarm_overrides.py
```

**Verification needed:**
- [ ] audit_data dict has all required keys
- [ ] SwarmOptimizer receives audit_data correctly
- [ ] Each agent receives correct context
- [ ] Recommendations have all required fields
- [ ] SwarmFeedbackLoop._apply_recommendation_to_config() works

### 2.2 Agent Context Building

**Verify each agent gets the right data:**

```python
# Entry Optimizer should see:
agent_input = {
    "summary": "audit summary",
    "trades_analysis": "trade breakdown",
    "metrics": metrics.get("by_entry_adjustment"),
    "focus": "entry timing"
}
```

- [ ] Entry Optimizer sees entry_adjustment metrics
- [ ] Exit Specialist sees exit_type metrics
- [ ] Sizing Specialist sees regime_1h metrics
- [ ] Regime Tuner sees regime_1h metrics
- [ ] Pattern Discoverer sees by_symbol metrics
- [ ] Multi-Signal Comparator sees comparison data

### 2.3 Recommendation Parsing

**Verify agent output is parsed correctly:**

```json
{
  "recommendations": [
    {
      "pattern": "string",
      "action": "string or proposed_change",
      "rationale": "string",
      "estimated_impact_pct": float,
      "confidence": float,
      "test_duration_days": int
    }
  ]
}
```

- [ ] JSON parsing handles nested fields
- [ ] Missing fields don't crash system
- [ ] Float values are valid (0-100 for %, 0-1 for confidence)
- [ ] Recommendations are ranked by impact_score()

### 2.4 Config Application

**Verify recommendations apply correctly:**

- [ ] ENTRY_ADJUSTMENTS config created
- [ ] REGIME_TP_SCALARS config created
- [ ] REGIME_RISK_MULTIPLIERS config created
- [ ] SNIPER_PATTERNS config created
- [ ] MULTI_SIGNAL_RULES config created

**Test**: Can we import the overrides without error?
```python
from bot.trading_config_swarm_overrides import *
```

---

## Audit 3: Data Integrity & File Operations

### 3.1 File Creation ✓

**Verify all required directories exist:**
```
bot/data/feedback/
├── swarm/
│   ├── recommendations.jsonl
│   ├── agent_accuracy.json
│   ├── promoted_rules.json
│   ├── daily_runs.jsonl
│   └── trading_config_swarm_overrides.py
├── single_signal_audit_state.json
├── single_signal_trades.jsonl
├── sniper_setups.json
└── single_signal_metrics.json
```

- [ ] Directories created with pathlib.Path
- [ ] Parent directories created (mkdir parents=True)
- [ ] Files created with write mode 'w'
- [ ] Append-only files use mode 'a'

### 3.2 Append-Only Ledgers ✓

**Critical: Verify no truncation**

```python
# recommendations.jsonl MUST be append-only
with open(filepath, "a") as f:
    f.write(json.dumps(entry) + "\n")
```

- [ ] recommendations.jsonl uses "a" mode
- [ ] daily_runs.jsonl uses "a" mode
- [ ] single_signal_trades.jsonl uses "a" mode
- [ ] No truncation operations anywhere

### 3.3 JSON Validation ✓

**Verify all JSON files are valid:**

```python
# Test each file format:
SingleSignalTrade(**json_dict)  # Should not raise
PerformanceMetrics(**json_dict)
Recommendation(**json_dict)
```

- [ ] single_signal_trades.jsonl deserializes to SingleSignalTrade
- [ ] recommendations.jsonl deserializes to Recommendation
- [ ] agent_accuracy.json has correct schema
- [ ] promoted_rules.json deserializes to PromotedRule

### 3.4 Backup & Recovery ✓

**Verify backup strategy:**

- [ ] Before major updates, backups created
- [ ] Ledger files are immutable (append-only)
- [ ] Crashes don't corrupt data
- [ ] Last-write-wins is acceptable for most files

---

## Audit 4: Performance & Timeouts

### 4.1 Swarm Execution Time

**Target: Single run <2 minutes**

- [ ] Audit extract: <10 seconds
- [ ] Metrics compute: <10 seconds
- [ ] 6 agents parallel: <60 seconds (each 30s timeout)
- [ ] Recommendation ranking: <5 seconds
- [ ] Config apply: <5 seconds
- **Total: <90 seconds**

### 4.2 Token Usage

**Verify token counts reasonable:**

- [ ] Entry Optimizer max_tokens: 2048 ✓
- [ ] Exit Specialist max_tokens: 2048 ✓
- [ ] Sizing Specialist max_tokens: 1024 ✓
- [ ] Regime Tuner max_tokens: 2048 ✓
- [ ] Pattern Discoverer max_tokens: 2048 ✓
- [ ] Multi-Signal Comparator max_tokens: 1024 ✓
- **Total per run: ~10,000 tokens (~$0.03)**

### 4.3 Memory Usage

**Verify no memory leaks:**

- [ ] SingleSignalAudit doesn't load all trades at once
- [ ] Swarm doesn't store all agent outputs in memory
- [ ] Files closed after write
- [ ] No circular references

---

## Audit 5: Correctness Verification

### 5.1 Win Rate Calculation ✓

**Verify math is correct:**

```python
win_count = len([p for p in pnls if p > 0])
total = len(trades)
win_rate = win_count / total if total > 0 else 0
# Should produce value between 0 and 1
```

- [ ] No division by zero
- [ ] Handles empty lists
- [ ] Returns float 0-1

### 5.2 Profit Factor Calculation ✓

```python
wins = [p for p in pnls if p > 0]
losses = [p for p in pnls if p < 0]
profit_factor = sum(wins) / abs(sum(losses)) if sum(losses) != 0 else 0
# Should be >1 for profitable
```

- [ ] Handles empty wins/losses
- [ ] Correctly uses absolute value
- [ ] Handles division by zero

### 5.3 Sharpe Ratio Calculation ✓

```python
mean_ret = sum(pnl_pcts) / len(pnl_pcts)
variance = sum((p - mean_ret) ** 2 for p in pnl_pcts) / len(pnl_pcts)
std_ret = variance ** 0.5
sharpe = (mean_ret / std_ret * (252 ** 0.5)) if std_ret > 0 else 0
```

- [ ] Handles zero std dev
- [ ] Annualization factor correct (sqrt(252))
- [ ] Formula matches industry standard

### 5.4 Kelly Criterion ✓

**Verify sizing calculations:**

```python
kelly_f = (WR * AvgWin - (1-WR) * AvgLoss) / AvgWin
# Should be positive for profitable strategies
```

- [ ] Correctly uses win rate
- [ ] Correctly uses win/loss percentages
- [ ] Outputs fraction 0-0.5

---

## Audit 6: Safety & Edge Cases

### 6.1 Edge Cases ✓

Test with:
- [ ] Empty trade list (0 trades)
- [ ] Single trade (1 trade)
- [ ] All winning trades (100% WR)
- [ ] All losing trades (0% WR)
- [ ] No recommendations from agents
- [ ] Agent timeout/failure

### 6.2 Safety Checks ✓

- [ ] No negative position sizes
- [ ] No division by zero
- [ ] No unbounded loops
- [ ] Timeouts on all async operations
- [ ] Exception handling comprehensive

### 6.3 Security ✓

- [ ] No API keys in code
- [ ] No hardcoded URLs
- [ ] No eval/exec
- [ ] No SQL injection (if DB used)
- [ ] No command injection

---

## Audit 7: Documentation & Clarity

### 7.1 Code Comments ✓

- [ ] Each class has docstring
- [ ] Each public method has docstring
- [ ] Complex logic has inline comments
- [ ] Configuration documented

### 7.2 Type Hints ✓

- [ ] Function signatures have type hints
- [ ] Return types documented
- [ ] Complex types clarified

### 7.3 README/Docs ✓

- [ ] SWARM_VISION.md complete ✓
- [ ] SWARM_QUICK_START.md complete ✓
- [ ] PHASES_2_6_ROADMAP.md complete ✓
- [ ] Code comments sufficient

---

## Test Plan: Verify Everything Works

### Test 1: Import Test
```bash
cd /home/user/WAGMI/bot
python -c "
from feedback.single_signal_audit import SingleSignalAudit
from llm.agents.swarm_optimizer import SwarmOptimizer
from llm.agents.swarm_master import SwarmMaster
from feedback.swarm_feedback_loop import SwarmFeedbackLoop
print('✓ All imports successful')
"
```

### Test 2: Audit Test
```bash
python -c "
from feedback.single_signal_audit import SingleSignalAudit
audit = SingleSignalAudit()
trades = audit.extract_single_signals(lookback_days=7)
print(f'✓ Extracted {len(trades)} trades')
metrics = audit.compute_metrics()
print(f'✓ Computed metrics for {len(metrics)} breakdowns')
"
```

### Test 3: Mock Data Test
```bash
python -c "
# Create mock trade data
trades = [
    {'trade_id': 't1', 'pnl': 100},
    {'trade_id': 't2', 'pnl': -50},
    {'trade_id': 't3', 'pnl': 75},
]
# Verify win rate calculation
wins = [p for p in [100, -50, 75] if p > 0]
wr = len(wins) / 3  # Should be 0.667
print(f'✓ Win rate: {wr:.1%}')
"
```

### Test 4: End-to-End Test (Dry Run)
```bash
python -c "
from llm.agents.swarm_master import SwarmMaster
master = SwarmMaster()
# This will fail on real LLM calls, but verify wiring
try:
    result = master.daily_optimization_run(lookback_days=1)
    print(f'✓ Run completed: {result[\"status\"]}')
except Exception as e:
    print(f'✗ Error: {e}')
"
```

---

## Audit Results

Run all tests and record results:

- [ ] Test 1: Import Test - PASS/FAIL
- [ ] Test 2: Audit Test - PASS/FAIL
- [ ] Test 3: Mock Data Test - PASS/FAIL
- [ ] Test 4: End-to-End Test - PASS/FAIL

**Overall Status**:
- [ ] All tests PASS → Phase 1 verified, proceed to Phase 2
- [ ] Some tests FAIL → Fix failures before Phase 2
- [ ] Any hallucinations detected → Rewrite affected module

---

## Sign-Off

Phase 1 is complete when:
1. ✓ All code committed
2. ✓ All documentation written
3. ✓ All tests pass
4. ✓ No hallucinations verified
5. ✓ Wiring end-to-end verified

Then: **Proceed to Phase 2: Knowledge Bases & Live Deployment**
