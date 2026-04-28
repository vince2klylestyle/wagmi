# PHASE 2: SNAPSHOT STRUCTURE ANALYSIS
## Critical Finding: Regime Data Location
**Date**: 2026-04-27 14:45 UTC

---

## Problem Discovery

Phase 1 filtering shows 100% veto rate because regime=unknown. Root cause investigation revealed:

1. **Code is deployed** ✓
   - Regime extraction logic is in llm/client.py (lines 98-129)
   - Snapshot parsing fallback is in claude_neural_monitor.py (lines 77-113)

2. **But snapshots lack regime field at root level** ✗
   - Snapshot JSON has NO top-level "regime" field
   - Current code tries: `snapshot.get("regime", "unknown")`
   - Result: Always defaults to "unknown"

---

## Snapshot Structure Analysis

### What the Snapshot CONTAINS

From `llm/decision_types.py:293-349`:

```python
class LLMInputSnapshot:
    markets: List[MarketSnapshot]      # List of trading pairs
    global_context: GlobalContext      # BTC prices, equity, positions, etc.
    memory_summary: Optional[str]      # Short-term memory
    active_positions: List[Dict]       # Open positions
    trigger_reason: str                # Why LLM was called
    trigger_context: str               # Context details

def to_dict() -> Dict:
    result = {
        "markets": [
            {
                "symbol": "ETH",
                "price": 2300.00,
                "signals": [
                    {
                        "strategy": "regime_trend",
                        "side": "SELL",
                        "confidence": 66.0,
                        "regime": 0.45  # <-- PER-SIGNAL regime_score, NOT global
                    }
                ]
            }
        ],
        "global": {
            "timestamp": ...,
            "btc_price": ...,
            "positions": ...,
            "telemetry": {...}  # <-- Might contain regime here?
        },
        "trigger": {...},
        "memory": "...",
        "open_positions": [...]
    }
```

### Where Regime SHOULD Be

**Option 1: In GlobalContext.extra (telemetry)**
```python
global_context.extra = {
    "dominant_regime": "trending_bull",  # <-- SHOULD BE HERE
    "regime_confidence": 0.85,
    ...
}
```

If populated, would appear as:
```json
{
    "global": {
        "telemetry": {
            "dominant_regime": "trending_bull"
        }
    }
}
```

**Option 2: Per-signal (current)**
Each signal has `"regime"` field (actually regime_score):
```json
{
    "markets": [
        {
            "signals": [
                {
                    "regime": 0.45
                }
            ]
        }
    ]
}
```

This is a SCORE (0-1), not a regime NAME ("trending_bull", "range", etc.)

---

## Current Regime Extraction Code Analysis

### What llm/client.py Does (lines 98-119)

```python
regime = "unknown"
strategies = []
try:
    snapshot_data = json.loads(snapshot_json)
    
    if isinstance(snapshot_data, dict):
        regime = snapshot_data.get("regime", "unknown")  # <-- Looks here
        # If no regime, try to get it from market analysis
        if regime == "unknown" and "markets" in snapshot_data:
            markets = snapshot_data.get("markets", [])
            if markets and isinstance(markets, list) and len(markets) > 0:
                market = markets[0]
                # Extract strategy votes as proxy for market context
                if "sigs" in market and isinstance(market["sigs"], list):
                    for sig in market["sigs"]:
                        if sig.get("strategy"):
                            strategies.append(sig["strategy"])
except (json.JSONDecodeError, TypeError, KeyError):
    pass
```

**Problem**: Looks for `snapshot.regime` which doesn't exist at root level

---

## What We Actually Found in Queued Signals

Analyzed 1,540 signals in neural_queue.jsonl:

**Snapshot Structure**:
```json
{
    "markets": [{
        "s": "ETH",
        "sym": "ETH",
        "p": 2289.23,
        "sg": [{
            "sym": "ETH",
            "side": "SELL",
            "c": 0.66,
            "confidence": 66.0,
            "atr": 0,
            "strategy": ""  // empty!
        }],
        "sigs": [...]
    }],
    // ... more fields ...
    // NO TOP-LEVEL "regime" field
    // Ends at 1000 chars (truncated mid-JSON)
}
```

**Key findings**:
1. Snapshot truncated at ~1000 chars (JSON incomplete)
2. "regime" field not in first 1000 chars (either further down or missing)
3. Per-signal strategy fields are EMPTY ("strategy": "")
4. Global telemetry may contain regime, but cut off by truncation

---

## Root Causes (Multiple Issues)

### Issue 1: Snapshot Truncation

**Where**: Unknown (happening before llm/client.py sees it)
**Effect**: Cannot extract regime even if it exists later in JSON
**Evidence**: 1,540/1540 signals are exactly 1000 chars, with unbalanced braces

```
{open: 5, close: 4}  ← JSON incomplete
Last 50 chars: "0\nIC: ensemble=TRACKING(114) sniper_premi=CONSTAN"
```

### Issue 2: Missing Global Regime Field

**Where**: Snapshot build (decision_engine.py or snapshot_builder.py)
**Effect**: No centralized regime classification available
**Current design**: Per-signal regime_score only (0-1 numeric), not global regime name

### Issue 3: Empty Strategy Fields

**Where**: Signal generation in bot.py or strategies
**Effect**: Even when strategies exist, they're not being populated in snapshot
**Current**: `"strategy": ""` in all queued signals
**Expected**: `"strategy": "regime_trend"` or similar

---

## What Happens After Restart (Current Code)

### llm/client.py Behavior:
```
Input: snapshot_json (1000 chars, truncated)
↓
Extract: regime = snapshot.get("regime", "unknown")
Result: "unknown" (field doesn't exist)
↓
signal_obj written to queue WITH regime="unknown"
```

### claude_neural_monitor Behavior:
```
Input: signal from queue with regime="unknown"
↓
Parse: regime = signal.get("regime", "unknown")
Result: "unknown" (got it from top-level)
↓
Try fallback: Parse snapshot JSON
Result: Still can't extract global regime
↓
Final: regime = "unknown"
↓
Agent votes: regime=CAUTION (not ALLOW/VETO, just default caution)
```

---

## Required Fixes (in order of impact)

### 🔴 CRITICAL: Fix Snapshot Truncation

**Problem**: Snapshots are 1000 chars with incomplete JSON
**Solution**: Find where truncation happens and remove it

Search for: `snapshot_json[:1000]` or similar in:
- llm/decision_engine.py (where snapshot is built)
- core/llm_context_builder.py (where context is prepared)
- core/signal_pipeline.py (where signals are queued)

**Impact**: HIGH - Without this, regime extraction cannot work

### 🟠 HIGH: Add Global Regime to Snapshot

**Problem**: No centralized regime classification in snapshot
**Solution**: Modify GlobalContext to include global regime

```python
# In llm/decision_types.py GlobalContext:
@dataclass
class GlobalContext:
    ...
    dominant_regime: str = "unknown"  # NEW: dominant regime classification
    ...

# In snapshot_builder.py _to_compact_dict():
"g": {
    ...
    "regime": snapshot.global_context.dominant_regime,  # NEW
    ...
}
```

**Impact**: MEDIUM - Allows agents to use regime for voting

### 🟡 MEDIUM: Populate Strategy Fields

**Problem**: Strategy fields are empty in signals
**Solution**: Ensure strategies are extracted and included in signals

```python
# In snapshot building:
"strategy": "regime_trend"  # Currently: ""
```

**Impact**: MEDIUM - Needed for trade agent confluence scoring

---

## Testing Plan

### Step 1: Verify Snapshot Size
```bash
# Check if snapshot_json is still 1000 chars after restart
tail -1 bot/data/neural_queue.jsonl | python -c "
import sys, json
sig = json.loads(sys.stdin.read())
print('Snapshot length:', len(sig['snapshot_json']))
print('Complete:', sig['snapshot_json'][-1] == '}')
"
```

Expected: Snapshot > 2000 chars, ends with `}`

### Step 2: Check Regime Field
```bash
tail -1 bot/data/neural_queue.jsonl | python -c "
import sys, json
sig = json.loads(sys.stdin.read())
snap = json.loads(sig['snapshot_json'])
print('Has regime:', 'regime' in snap or any('regime' in str(m) for m in snap.get('markets', [])))
print('Global regime:', snap.get('global', {}).get('regime', 'N/A'))
print('Keys:', list(snap.keys()))
"
```

Expected: `regime` field present and non-"unknown"

---

## Recommendation

**Current strategy (regime extraction) is sound, BUT:**

1. **Must fix snapshot truncation first** - Otherwise regime extraction won't work regardless of code
2. **Must add global regime field** - Per-signal regime_score is not sufficient
3. **Must populate strategy fields** - Trade agent needs this for confluence scoring

**Timeline**:
- **Immediate** (before restart): Fix snapshot truncation in code
- **Before restart**: Add global regime to GlobalContext
- **Before restart**: Populate strategy fields in snapshot
- **After restart**: Verify all three fixes are working
- **Then**: Phase 1 filtering will activate properly

---

## Next Session Tasks

1. [  ] Find and fix snapshot truncation (critical blocker)
2. [  ] Add dominant_regime to GlobalContext and snapshot
3. [  ] Ensure strategies are populated in signals  
4. [  ] Test extraction with full snapshots
5. [  ] Restart bot and monitor
6. [  ] Verify regime != "unknown" in decisions
7. [  ] Measure Phase 1 WR improvement vs Phase 0 baseline

---

**Status**: Root cause identified, fixes needed, strategy sound

**Prepared by**: Claude (Phase 2 Analysis)  
**Date**: 2026-04-27 14:45 UTC
