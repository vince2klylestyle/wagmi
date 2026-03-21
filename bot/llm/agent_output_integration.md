# TIER 2.1: Agent Output Logger Integration Guide

## Overview
The `agent_output_logger.py` module provides infrastructure to log individual agent outputs
from the multi-agent pipeline. This enables:
- Per-agent accuracy tracking
- Cross-agent consistency analysis
- Prompt tuning validation
- Bottleneck identification

## Integration Points

### 1. In `bot/llm/agents/coordinator.py`

After each agent call in the pipeline, log its output:

```python
from llm.agent_output_logger import get_agent_output_logger, AgentOutput

# After regime agent call (around line 200)
if regime_out.ok:
    logger = get_agent_output_logger()
    logger.log_agent_output(
        decision_id=snapshot_data.get("trace_id", ""),
        agent_name="regime",
        output=AgentOutput(
            agent_name="regime",
            timestamp=time.time(),
            input_context={"symbol": snapshot_data.get("symbol"), "price": snapshot_data.get("price")},
            reasoning=regime_out.data.get("reasoning", ""),
            decision=regime_out.data.get("rg", "unknown"),
            confidence=regime_out.data.get("conf", 0.5),
            metadata={"model": regime_out.model},
        )
    )

# Same pattern after trade agent, risk agent, critic agent, etc.
```

### 2. In `bot/llm/decision_engine.py`

Initialize pipeline log at start of decision:

```python
from llm.agent_output_logger import get_agent_output_logger, AgentPipelineLog
import uuid

# At start of make_decision_impl()
decision_id = str(uuid.uuid4())
snapshot_data["trace_id"] = decision_id

logger_inst = get_agent_output_logger()
pipeline_log = AgentPipelineLog(
    decision_id=decision_id,
    symbol=snapshot_data.get("symbol", "unknown"),
    timestamp=time.time(),
)
logger_inst.log_pipeline(pipeline_log)

# ... rest of decision pipeline ...

# At end, after all agents run:
pipeline_log.final_decision = decision.action
pipeline_log.final_confidence = decision.confidence
pipeline_log.veto_applied = (critic vetoed trade agent)
logger_inst.log_pipeline(pipeline_log)  # Re-save with final data
```

### 3. Enable output capture in multi-agent mode

Set environment variable:
```bash
AGENT_LOGGING_ENABLED=true
```

## Data Flow

```
Agent Call
    ↓
AgentOutput (captured)
    ↓
AgentOutputLogger.log_agent_output()
    ↓
Pipeline Log (updated with agent output)
    ↓
Append to agent_outputs.jsonl
    ↓
Append to recent_logs (in-memory cache)
```

## Query Examples

### Get all outputs from regime agent in last 100 decisions:
```python
logger = get_agent_output_logger()
outputs = logger.get_logs_by_agent("regime", limit=100)
for o in outputs:
    print(f"{o['symbol']}: {o['agent_output']['decision']}")
```

### Analyze cross-agent consistency:
```python
report = logger.get_agent_consistency_report()
print(f"Regime agreement: {report['regimes_identified']}")
print(f"Veto rate: {report['trade_vetoes']['veto_rate']:.1%}")
print(f"Critic high-confidence rate: {report['critic_confidence']['high_confidence_rate']:.1%}")
```

### Get recent pipeline logs:
```python
logs = logger.get_recent_logs(limit=50)
for log in logs:
    print(f"{log.symbol}: regime={log.market_regime}, veto={log.veto_applied}")
```

## Output Format

Each line in `agent_outputs.jsonl` contains:
```json
{
  "decision_id": "uuid",
  "symbol": "SOL",
  "timestamp": 1710000000.0,
  "market_regime": "trend",
  "trade_thesis": "Long based on...",
  "risk_assessment": "Position size: 0.1 SOL",
  "critic_veto": null,
  "regime_agent_output": {
    "agent_name": "regime",
    "timestamp": 1710000000.0,
    "reasoning": "...",
    "decision": "trend",
    "confidence": 0.85,
    "metadata": {}
  },
  "trade_agent_output": {...},
  ...
  "final_decision": "go",
  "final_confidence": 0.72,
  "veto_applied": false
}
```

## Analysis Use Cases

### 1. Thesis Accuracy Tracking
```python
# For each closed trade, check if trade_agent_output.decision was correct
correct = 0
total = 0
for log in logs:
    if log.trade_agent_output and log.trade_agent_output.decision in ["go", "proceed"]:
        # Check if trade won/lost
        # Calculate accuracy
```

### 2. Prompt Tuning Validation
```python
# A/B test new regime agent prompt:
# - Run old prompt on recent data
# - Run new prompt on recent data
# - Compare accuracy of regime classifications

logs_before = logger.get_logs_by_agent("regime", limit=50)  # Old prompt
# Deploy new prompt
logs_after = logger.get_logs_by_agent("regime", limit=50)   # New prompt

# Compare accuracy metrics
```

### 3. Bottleneck Identification
```python
# Find where decisions degrade:
# - High-confidence regime classification but low-confidence trade decision
# - High-confidence trade decision but critic vetoes it
# - Pattern: where does confidence drop?

for log in logs:
    if log.regime_agent_output.confidence > 0.8 and log.trade_agent_output.confidence < 0.5:
        print(f"Confidence cliff: regime={log.regime_agent_output.confidence:.2f}, trade={log.trade_agent_output.confidence:.2f}")
```

## Performance Impact

- **Logging overhead**: ~1ms per decision (JSON serialization)
- **Disk I/O**: ~500 bytes per decision (~500 KB per 1000 decisions)
- **Memory**: Last 1000 decisions in memory (~500 MB)
- **Can be disabled**: Set `AGENT_LOGGING_ENABLED=false` to disable logging

## Status

- ✅ Core logger implementation (agent_output_logger.py)
- ⏳ Coordinator integration (awaiting review)
- ⏳ Decision engine integration (awaiting review)
- ⏳ Analysis dashboards (future work)
