# NunuIRL Trading Bot — System Integration & Failure Modes Audit
**Date:** March 20, 2026 | **Version:** Comprehensive Integration Audit

---

## Executive Summary

The NunuIRL bot is a **complex, multi-layered system** with 335+ Python files integrating:
- 11+ trading strategies + weighted-veto ensemble
- LLM meta-brain (multi-agent specialist system)
- Position management, risk gating, leverage, circuit breakers
- Feedback loops (learning, signal quality, strategy weights)
- TIER 4/5 instrumentation hooks (mechanical bot observation)
- Telegram/Discord alerts, watchdog monitoring
- Database persistence, position reconciliation

**Critical Finding:** The bot exhibits **CASCADING FAILURE RISKS** where system component failures don't always fail safely. Most components have defensive error handling, but some failures **propagate silently or stop trading mid-session**.

---

## 1. TIER 4/5 INSTRUMENTATION HOOK INTEGRATION

### Where TIER 4/5 Hooks are Wired

**TIER 4: Mechanical Bot Instrumentation** (Observation-only, non-blocking)
- **File:** `bot/llm/mechanical_bot_instrumentation.py`
- **Integration point:** `multi_strategy_main.py:2783`
- **Hook trigger:** After ensemble produces a signal

```python
# multi_strategy_main.py:2783-2817
if _MECHANICAL_BOT_INSTRUMENTATION_AVAILABLE and signal_result is not None:
    try:
        instr = get_mechanical_bot_instrumentation()
        signal_id = instr.on_signal_generated(
            symbol=symbol,
            side=signal_result.side,
            confidence=signal_result.confidence,
            entry=signal_result.entry,
            sl=signal_result.sl,
            tp1=signal_result.tp1,
            tp2=signal_result.tp2,
            strategy_names=signal_result.metadata.get("strategy_names", []),
            num_strategies=signal_result.metadata.get("num_agree", 1),
            market_context=market_context
        )
        # Store signal_id in metadata for later reference
        if not hasattr(signal_result, 'metadata'):
            signal_result.metadata = {}
        signal_result.metadata['mechanical_signal_id'] = signal_id
    except Exception as e:
        logger.debug(f"[{symbol}] Mechanical bot instrumentation error (signal generation): {e}")
```

**TIER 5: Bot Perception System** (Async perception aggregation)
- **File:** `bot/llm/bot_perception_api.py`, `bot/llm/bot_perception_aggregator.py`
- **Integration point:** `multi_strategy_main.py:926-927` (startup), `766` (async loop)
- **Pattern:** Runs in background thread; imports wrapped in try/except

```python
# multi_strategy_main.py:92-105 (Import pattern - wrapped)
try:
    from llm.mechanical_bot_instrumentation import get_mechanical_bot_instrumentation
    from llm.mechanical_bot_memory import get_mechanical_bot_memory
    _MECHANICAL_BOT_INSTRUMENTATION_AVAILABLE = True
except ImportError:
    _MECHANICAL_BOT_INSTRUMENTATION_AVAILABLE = False

try:
    from llm.bot_perception_api import get_bot_perception_api_client
    from llm.bot_perception_aggregator import get_bot_perception_aggregator
    _BOT_PERCEPTION_SYSTEM_AVAILABLE = True
except ImportError:
    _BOT_PERCEPTION_SYSTEM_AVAILABLE = False
```

### Hook Failure Modes

| Failure Mode | Impact | Current Handling | Risk Level |
|---|---|---|---|
| `get_mechanical_bot_instrumentation()` fails | Signal tracking stops silently | Try/except + debug log only | **MEDIUM** |
| `instr.on_signal_generated()` throws | Signal not tracked, trade proceeds normally | Try/except + debug log | **MEDIUM** |
| Bot Perception async loop stalls | Perception data stops flowing | Daemon thread (not monitored) | **HIGH** |
| Perception memory corruption | Corrupted signal history | No integrity checks | **HIGH** |
| Mechanical bot memory file write fails | Data loss mid-session | No retry, best-effort only | **MEDIUM** |

### Key Finding: "Silent Observer" Design
- **Hooks are observation-only** — cannot block trading
- **No feedback to main loop** — if hooks fail, bot has no way to know
- **Import-time failures caught**, but runtime failures only logged at DEBUG level
- **No health monitoring** for TIER 4/5 systems

---

## 2. DOES TRADING CONTINUE IF HOOKS FAIL?

### Answer: YES (by design, but with blind spots)

**TIER 4/5 failures do NOT stop trading:**
```python
# multi_strategy_main.py:2816-2817
except Exception as e:
    logger.debug(f"[{symbol}] Mechanical bot instrumentation error (signal generation): {e}")
    # No re-raise, no stop_event.set() — trading continues
```

**However, this creates detection blind spots:**
1. **No health metric** for instrumentation success/failure rate
2. **No alert to operator** if perception system dies
3. **No fallback** — if mechanical bot memory corrupts, bot doesn't know
4. **Partial state loss** — trades execute, but instrumentation may have gaps

### Specific Risk: Mechanical Bot Memory File Corruption

If `/home/user/WAGMI/bot/data/llm/mechanical_bot_memory/` becomes inaccessible (disk full, permission error, race condition):
- Signal generation continues
- Position management continues
- **BUT:** Mechanical signal history is lost
- **Impact on LLM:** Upstream LLM agents relying on mechanical bot history produce decisions without context

---

## 3. STRATEGY ENSEMBLE INTEGRATION & FAILURE MODES

### How Strategies Integrate with Ensemble

**File:** `bot/strategies/ensemble.py` (1500+ lines)

**Signal flow:**
1. Ensemble calls each strategy's `evaluate()` in sequence
2. If strategy fails → caught + logged, signal skipped (ensemble continues)
3. Final vote count computed (weighted veto mode)
4. Quality scoring applied (if scorer available)
5. Graduated rules applied (if available)
6. Confidence floor applied

```python
# ensemble.py:367-373 — Error handling per strategy
try:
    sig = strategy.evaluate(symbol, data)
    if sig is not None:
        signals.append(sig)
except Exception as e:
    error_count += 1
    logger.warning(f"[{symbol}] {strategy.name} error: {e}")
```

### Can One Strategy Break Ensemble?

**Answer: Partially yes, with escalating failure modes**

| Failure Mode | Impact | Recovery |
|---|---|---|
| Strategy throws exception | Skipped, ensemble continues | Automatic (logged as warning) |
| Strategy returns invalid Signal | Accepted into vote, may produce bad result | **NO VALIDATION** — silent acceptance |
| Strategy mutates shared data (e.g., metadata) | Downstream strategies see corrupted data | **NO DEEP COPY** — in-place mutation bug |
| Strategy returns None consistently | Signals from other strategies ignored (if min_votes unmet) | Ensemble produces no output (OK) |
| Strategy produces extreme confidence (>100 or <0) | Confidence clipping may fail | Depends on validation layer |

### Critical Bug: In-Place Signal Mutation

**File:** `bot/strategies/ensemble.py:368` (deepcopy in disabled strategy path)
```python
if sig is not None:
    signals.append(sig)  # Shallow append, metadata dict is shared reference
```

**Risk:** If a strategy mutates `signal.metadata` (e.g., modifying regime or confidence), **all downstream signals see the mutation**. This is partially mitigated by:
- Quality scorer applies multiplier (creates copy)
- Graduated rules apply adjustment (creates copy)

**But direct metadata access is vulnerable:**
```python
regime = signal_result.metadata.get("regime", "unknown")  # Mutable reference
```

---

## 4. POSITION MANAGEMENT & RISK MANAGEMENT INTERACTION

### Integration Points

```
Signal (from ensemble)
    ↓ (gated by 6-stage risk filter chain)
RiskFilterChain (core/signal_pipeline.py)
    ├─ Gate 1: Signal validity (R:R, stop width)
    ├─ Gate 2: Circuit breaker check (daily loss, streak)
    ├─ Gate 3: Leverage decision
    ├─ Gate 4: Liquidation safety
    ├─ Gate 5: Portfolio risk
    └─ Gate 6: Sizing
    ↓
PositionManager (open_position)
    ├─ State machine: IDLE → OPEN → TP1_HIT → TRAILING → CLOSED
    ├─ Trailing stop logic
    └─ TP1/TP2 execution
    ↓
OrderExecutor (order_executor.py)
    └─ (Paper or Live mode)
```

### Failure Mode: Risk Manager & Position Manager Desync

**Scenario:** Risk manager thinks equity is $10,000; Position manager opened $15,000 notional position

**Root causes:**
1. **No transaction log coordination** — position opening can fail after risk manager approves
2. **Exchange state different from local state** — crash/disconnect leaves stale positions
3. **Multi-leg trades** — if TP1 close fails, risk manager's daily PnL tracking misses it

**Current recovery:**
- **On startup:** `reconcile_positions()` queries exchange for open positions (reconciliation.py)
- **Risk:** If reconciliation fails, bot starts with no knowledge of exchange positions
- **Impact:** Risk manager may approve trades that would exceed notional limits

```python
# reconciliation.py:59-117
def reconcile_positions(pos_mgr, exchanges, last_prices, risk_mgr=None) -> int:
    """Query Hyperliquid and rebuild pos_mgr state."""
    exchange = exchanges.get("hyperliquid")
    if exchange is None:
        logger.warning("[RECONCILE] No Hyperliquid exchange instance, skipping")
        return 0  # SILENT: returns 0 if exchange unavailable
    try:
        raw_positions = exchange.fetch_positions()
    except Exception as e:
        logger.warning(f"[RECONCILE] Failed to fetch positions: {e}")
        return 0  # SILENT: returns 0 if fetch fails
```

### Critical Risk: Trading Can Begin Before Reconciliation Completes

```python
# multi_strategy_main.py:894-895
# Reconciliation called in startup
self._reconcile_exchange_positions()

# But main loop starts immediately after
while not self.stop_event.is_set():
    self._tick_once()  # Can begin trading before reconcile finishes
```

**If reconciliation fails or is slow:**
- Risk manager has no knowledge of open positions
- First trade signal might violate position limits
- Risk manager may approve overlapping positions

---

## 5. LLM AGENT SYSTEM vs. MECHANICAL BOT DISAGREEMENT

### System Architecture

```
Signal from Ensemble (mechanical)
    ↓
Gate by Risk Filter Chain
    ↓
LLM Decision Engine (if LLM_MODE > OFF)
    ├─ Multi-agent pipeline (Regime → Trade → Risk → Critic)
    ├─ Critic Agent can VETO (if LLM_MODE >= VETO_ONLY)
    └─ Return: go/skip/flip or veto
    ↓
Execute or Reject
```

### Failure Mode: LLM Veto Path Not Checked

```python
# multi_strategy_main.py:3922
if llm_has_veto(self.llm_mode):
    # Check if LLM critic vetoed this trade
    if decision_result.vetoed:
        logger.info(f"[LLM VETO] {symbol} — {decision_result.veto_reason}")
        # Trade rejected, continue to next symbol
        continue
```

**Risk:** If `get_trading_decision()` crashes:
```python
# multi_strategy_main.py:5333
result = get_trading_decision(...)  # Can throw exception
```

**Exception handling:**
```python
except Exception as e:
    logger.error(f"LLM decision failed: {e}")
    # No fallback — signal treated as if no LLM override
    # Trade either proceeds (mechanical) or rejected (depends on filter state)
```

### Disagreement Cascades

| Scenario | Mechanical | LLM | Outcome |
|---|---|---|---|
| Strong BUY | High confidence, 4/4 agree | VETO (thesis unstable) | Rejected ✓ |
| Weak BUY | 2/4 agree, fails min_votes | Approves (regime safe) | Rejected (mechanical gate) ⚠️ |
| No signal | Ensemble rejects | Proactively suggests | Queued (LLM Sniper) ⚠️ |
| LLM crashes | Strong signal | Exception → fallback | Proceeds mechanically (risky) ⚠️ |

**Critical gap:** No explicit agreement tracking between LLM and mechanical signals.

---

## 6. FEEDBACK LOOP INTEGRATION WITH STRATEGY WEIGHTS

### Integration Points

```
Closed Trade (position closes at TP1, TP2, or SL)
    ↓
FeedbackLoop (feedback/loop.py)
    ├─ Trade outcome recorded
    ├─ Signal outcome linked
    └─ Metrics computed (win/loss, hold time, PnL)
    ↓
StrategyWeightManager (data/strategy_weights.py)
    ├─ Rolling performance tracked
    ├─ Weights recomputed (exponential decay, recent trades weighted higher)
    └─ Next ensemble vote uses new weights
    ↓
Ensemble (strategies/ensemble.py)
    └─ Uses updated weights in voting
```

### Failure Mode: Feedback Loop Disconnection

**Scenario: What if `FeedbackLoop.record_trade_closed()` fails?**

```python
# In main loop, when position closes:
try:
    self.feedback_loop.record_trade_closed(trade_record)
except Exception as e:
    logger.warning(f"Feedback loop error: {e}")
    # Trade execution continues regardless
```

**Consequences:**
1. Trade closed successfully on exchange ✓
2. Position manager updated ✓
3. Risk manager equity updated ✓
4. **BUT:** Feedback loop never sees this trade
5. Strategy weights not updated with outcome
6. Next similar setup uses outdated weights

**Silent failure pattern:** This can persist undetected if feedback loop fails intermittently.

### Corruption Risk: Database vs. Memory Divergence

**StrategyWeightManager stores weights in two places:**
1. **SQLite:** `bot/data/bot.db` (trades table, outcomes table)
2. **Memory:** In-process dict loaded at startup

**If database write fails:**
```python
# data/strategy_weights.py (hypothetical)
def record_outcome(...):
    # Write to DB
    try:
        conn.execute("INSERT INTO ...", ...)
        conn.commit()
    except Exception:
        # Rollback? But memory dict already updated
        pass
```

**Risk:** Memory weights diverge from disk. After restart, weights reset but memory retained stale values.

---

## 7. DATABASE CORRUPTION & INACCESSIBILITY

### Database Architecture

**Single SQLite file:** `bot/data/ml_data/bot.db`
- **WAL mode enabled** (better concurrent reads)
- **Thread-safe connections** (per-connection, lock in fetcher)
- **No external transaction coordination** (each module opens its own connection)

**Tables:**
- `signals` (every signal generated)
- `trades` (position open/close events)
- `equity_snapshots` (periodic snapshots)
- `signal_outcomes` (signals linked to trades)
- `signal_rejections` (rejected signals with reasons)

### Failure Mode: Disk Full / Permission Denied

**Scenario:** `/home/user/WAGMI/bot/data/` becomes full or inaccessible

```python
# data/db.py:27-32
def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=10)  # 10-second timeout
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn
```

**Timeout:** Only 10 seconds. If DB is locked or slow:
- Signal logging times out
- Trade logging times out
- **No fallback** — trade proceeds, logging silently fails

**Logging failures are caught but silent:**
```python
# core/signal_pipeline.py:38-55
def _log_rejection(signal, gate, reason):
    """Best-effort rejection log — never raises."""
    if not _rejection_log_enabled:
        return
    try:
        from data import db
        db.log_signal_rejection(...)
    except Exception:
        pass  # Silent failure
```

### Recovery after Corruption

**If bot.db becomes corrupted:**
1. **Startup:** `init_db()` re-creates schema (checks IF NOT EXISTS)
2. **Existing data:** Lost (no migration path)
3. **Strategy weights:** Reset to defaults (equal weights)
4. **Signal history:** Lost

**Impact:** If bot crashes and DB is corrupted, recovering involves:
- Manual repair or deletion
- Restart with clean DB
- Loss of all historical performance data

---

## 8. CRASH RECOVERY & STATE RECONCILIATION

### Startup Sequence

```
1. parse args
   ↓
2. init_db() — create tables if missing
   ↓
3. Load TradingConfig from .env
   ↓
4. Create bot instance (all subsystems initialized)
   ↓
5. run() — main loop begins
   ├─ _run_health_check()
   ├─ _reconcile_exchange_positions()
   ├─ restore_circuit_breaker_state()
   ├─ Start Telegram bot, signal monitor, watchdog
   └─ Enter main loop (_tick_once in while loop)
```

### Failure Mode: Partial State Loss

**Scenario: Bot crashes during position opening**

1. Signal approved by all gates ✓
2. `order_executor.open_position()` called
3. Exchange returns order confirmation ✓
4. Position object created in PositionManager ✓
5. Trade logged to DB
6. **CRASH occurs here** (before returning from `_process_symbol()`)

**On restart:**
- `reconcile_positions()` queries exchange ✓ (finds open position)
- Position restored in PositionManager ✓
- **BUT:** TP1/TP2 levels may differ from original (estimated from ATR instead of original trade)
- **Impact:** SL/TP levels may be off by 5-10%

**Root cause:** PositionManager stores SL/TP in memory only; on crash, original levels are unknown.

### Recovery Without Reconciliation

**If reconciliation.py fails or is skipped:**

```python
# reconciliation.py:76-79 (silent fallback)
exchange = exchanges.get("hyperliquid")
if exchange is None:
    logger.warning("[RECONCILE] No Hyperliquid exchange instance, skipping")
    return 0
```

**Outcome:**
- Bot starts with empty PositionManager
- Risk manager thinks no positions are open
- First new trade might exceed leverage/notional limits
- **Silent risk escalation**

---

## 9. SHARED STATE & THREADING ISSUES

### Threading Model

| Thread | Purpose | Shared State | Synchronization |
|---|---|---|---|
| Main | Signal processing, trade execution | PositionManager, RiskManager, StrategyWeights | None (single-threaded loop) |
| Watchdog | Health monitoring (background) | Equity, error count, last heartbeat | Atomic assignment only |
| Telegram bot | Command handling (background) | Alert router | Thread-safe queues |
| Signal monitor | Telegram signal ingestion (background) | Signal queue | Thread-safe queue |
| Perception (async) | Async perception capture (background) | Mechanical bot memory | File writes, no lock |
| Health server | HTTP health endpoint (background) | Health monitor snapshot | Copy on read |

### Critical Shared State: PositionManager

**Accessed by:**
- Main loop (read/write: open, close, update SL/TP)
- Watchdog (read: count positions for alerts)
- Reconciliation (write: restore positions on startup)

**Synchronization:** NONE (global dict, no locks)

**Risk:**
```python
# multi_strategy_main.py — main thread
positions = self.pos_mgr.get_open_positions()  # Dict reference

# Watchdog thread (background)
open_count = len(self.pos_mgr.get_open_positions())  # Iterating same dict
```

**If main thread modifies while watchdog iterates:**
- Python dict iteration may fail with "dictionary changed size during iteration"
- Less likely in practice (CPython handles gracefully), but **not guaranteed**

### StrategyWeightManager Shared State

**Accessed by:**
- Main loop (read: get_rolling_weights())
- Feedback loop (write: record_outcome())
- Background processes (read: get_strategy_performance())

**Synchronization:** In-memory dict, no locks

**Risk:** If feedback loop updates weights while ensemble is voting on them, vote may use stale weights (race condition).

---

## 10. MARKET DATA STALLS & DEGRADATION

### Stale Data Detection

```python
# multi_strategy_main.py:1815-1847
# Check if last candle is >5 min old (+ period tolerance)
_stale_max_s = 300
_stale_check_tf = "5m" if "5m" in data else ("1h" if "1h" in data else None)
if _last_candle_time is not None:
    _candle_age_s = (pd.Timestamp.now(tz="UTC") - _last_candle_time).total_seconds()
    _tf_period_s = {"5m": 300, "1h": 3600}.get(_stale_check_tf, 3600)
    if _candle_age_s > _tf_period_s + _stale_max_s:
        # Skip signal generation
        return
```

### Failure Mode: Exchange Data Feed Dies

**Scenario: Hyperliquid OHLCV endpoint times out persistently**

1. **Prefetch fails:** `prefetch_all_symbols()` times out
2. **Degradation manager records error:** `degradation.record_exchange_error()`
3. **After N failures, degradation halts new entries:**
   ```python
   # multi_strategy_main.py:1777-1781
   if self.degradation.should_halt_entries():
       open_pos = self.pos_mgr.get_open_positions()
       if symbol not in open_pos:
           return  # Skip new signals
   ```
4. **But:** Open positions still managed (SL/TP monitoring continues)

**Risk:** If exchange is down for extended period:
- Bot can't open new trades (intended)
- Bot can't monitor prices → may miss SL/TP hits
- Watchdog detects stall after 5 minutes
- **Alert sent but no action taken** (alerts are non-blocking)

### Silent Failure: Stale Data Accepted

**In rare cases, stale check may miss corrupted candles:**

```python
# If _last_candle_time parsing fails:
if _last_candle_time is not None:  # Checks if not None
    # Proceed with stale check
else:
    # Stale check skipped — proceed to signal generation on stale data!
```

**Root cause:** Timestamp parsing errors are caught but silently ignored; signal generation proceeds.

---

## 11. TELEGRAM/DISCORD ALERTS & FEEDBACK

### Alert Flow

```
Trade Event (signal/open/close)
    ↓
AlertRouter (alerts/router.py)
    ├─ Rate limiting check (dedup, min gap)
    ├─ Route to Discord/Telegram based on confidence
    └─ Webhook POST (async with timeout)
    ↓
Telegram/Discord (external)
```

### Failure Mode: Alert Delivery Failure

**Scenario: Discord webhook times out**

```python
# alerts/router.py (typical implementation)
try:
    response = requests.post(
        webhook_url,
        json=payload,
        timeout=5  # 5-second timeout
    )
except requests.RequestException:
    logger.warning(f"Alert post failed: {e}")
    # No retry, no queuing — alert dropped
```

**Outcome:**
- Trade executed ✓
- Alert never reaches operator ⚠️
- Operator unaware of position opening
- No feedback loop (operator can't manually intervene)

### Risk: Operator Blindness

**If Telegram/Discord both fail:**
- Operator doesn't see signals
- Paper trading validation reports go unseen
- Go-live gate issues unreported
- **Bot operates in silence**

**Monitoring:** Watchdog can detect stalls, but:
```python
# monitoring/watchdog.py
if not self._exchange_healthy:
    # Alert operator about exchange issues
    self.alert_fn("Exchange down")
else:
    # No alert about alert system health
```

**No health monitoring for alert subsystem itself.**

---

## 12. MISSING ERROR HANDLERS & SILENT FAILURES

### Comprehensive Failure Analysis

#### 1. **Data Fetcher Failures** (data/fetcher.py)

| Failure | Handling | Risk |
|---|---|---|
| API call timeout | Retry with exponential backoff | **OK** |
| Invalid response (non-JSON) | Parse error → exception | Caught in process_symbol |
| Rate limit (429) | Caught, logged as warning | **Proceeds to stale data** |
| Network disconnect | Timeout → exception | Caught |
| Exchange maintenance | 503 response | Treated same as timeout |

**Risk:** If exchange is in maintenance mode and returns 503:
- Prefetch fails, degradation recorded
- Main loop detects it and halts entries
- **But:** Monitoring doesn't distinguish between "exchange down" and "data stale"

#### 2. **Strategy Evaluation Failures** (strategies/*.py)

| Failure | Handling | Risk |
|---|---|---|
| Divide by zero (ATR=0) | Usually caught, returns None | **OK** |
| Insufficient data (NaN) | Depends on strategy implementation | **Variable** |
| Indicator calculation overflow | Caught (usually), returns None | **OK** |
| Custom strategy import fails (config disable) | Caught at init, skipped | **OK** |

**Risk:** Some strategies may not handle NaN gracefully:
```python
# If strategy does: confidence * (high / low) and high=low:
#   Result: nan * nan = nan
# If signal.confidence = nan, downstream validation may miss it
```

#### 3. **Position Manager State Corruption** (execution/position_manager.py)

| Failure | Handling | Risk |
|---|---|---|
| Position.update_tp1() called on closed position | State check (ignore if CLOSED) | **OK** |
| Double-open same symbol | Checked by ops_guard | **OK** |
| SL/TP prices invalid | Validated at entry | **OK** |
| Trailing stop logic fails | Catch exception, log warning | **Silent failure** |

**Risk:** If trailing stop crashes:
```python
try:
    new_sl = self._compute_trailing_sl()
except Exception as e:
    logger.warning(f"Trailing stop error: {e}")
    # Position continues WITHOUT trailing stop
    # Operator doesn't know
```

#### 4. **LLM Decision Engine Failures** (llm/decision_engine.py)

| Failure | Handling | Risk |
|---|---|---|
| API key missing/invalid | Anthropic exception → caught | Trade rejected (fallback to mechanical) |
| Rate limit (429) | Anthropic exception → caught | Trade rejected (fallback) |
| Model unavailable | Anthropic exception → caught | Trade rejected (fallback) |
| Prompt parsing fails | Exception in decision parsing | **Silent failure** |
| Model returns invalid JSON | JSON decode error → exception | Caught, trade rejected |
| Token overflow | Anthropic exception → caught | Trade rejected |

**Risk:** If LLM response is valid JSON but doesn't match expected schema:
```python
try:
    decision = json.loads(response)
    go = decision["go"]  # KeyError if "go" missing
except KeyError:
    logger.error("LLM response missing required field")
    # Trade rejected (OK), but swallows potential bugs
```

#### 5. **Risk Manager / Circuit Breaker** (execution/risk.py)

| Failure | Handling | Risk |
|---|---|---|
| Equity calculation underflow | Clamped to 0 | **OK** |
| Daily PnL tracking error | Logged, continues | **Silent data loss** |
| Circuit breaker activation check fails | Exception caught | **Allows trades through** |
| Daily loss limit corrupted | Validation check (should prevent) | **Variable** |

**Critical:** If circuit breaker check throws exception:
```python
try:
    if self.circuit_breaker.check_daily_loss(daily_pnl, equity):
        # Trade allowed
        pass
except Exception:
    logger.error("Circuit breaker check failed")
    # Falls through — trade may proceed without checking loss limit!
```

---

## SYSTEM INTEGRATION DEPENDENCY GRAPH

```
┌─────────────────────────────────────────────────────────────┐
│                       ENTRY POINT                           │
│                      run.py / run()                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
       ┌───────────────┼───────────────┐
       │               │               │
       ▼               ▼               ▼
    ┌──────┐    ┌──────────┐    ┌──────────┐
    │ Data │    │Strategies│    │   LLM    │
    │Fetch │    │ Ensemble │    │ Meta-    │
    │ (1)  │    │   (2)    │    │ Brain(3) │
    └──┬───┘    └────┬─────┘    └────┬─────┘
       │             │               │
       └─────────────┼───────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │ Risk Filter Chain (6)  │
        │ • Validity             │
        │ • Circuit Breaker      │
        │ • Leverage             │
        │ • Liquidation          │
        │ • Portfolio Risk       │
        │ • Sizing               │
        └────────────┬───────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │ Position Manager (4)   │
        │ • State Machine        │
        │ • TP/SL Management     │
        │ • Trailing Stop        │
        └────────────┬───────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │ Order Executor (5)     │
        │ • Paper / Live Mode    │
        └────────────┬───────────┘
                     │
       ┌─────────────┼─────────────┐
       │             │             │
       ▼             ▼             ▼
   ┌────────┐  ┌──────────┐  ┌──────────┐
   │Database│  │Feedback  │  │ Alerts   │
   │(7)     │  │Loop (8)  │  │(9)       │
   └────────┘  └────┬─────┘  └──────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │ Strategy Weights    │
         │ (weighted veto next)│
         └─────────────────────┘

Side-by-side (non-blocking):
   ┌────────────────┐
   │ Watchdog (10)  │ — Monitors health
   ├────────────────┤
   │ Perception(11) │ — TIER 5 async
   ├────────────────┤
   │ Mechanical Bot │ — TIER 4 observation
   │ Instrumentation│
   └────────────────┘
```

---

## CASCADING FAILURE PATTERNS

### Pattern 1: Silent Exchange Failure

```
Exchange API times out
  ↓
Prefetch fails (returns empty dict)
  ↓
degradation.record_exchange_error()
  ↓
After N errors, degradation.should_halt_entries() → true
  ↓
New signal evaluation skipped (for symbols with no open positions)
  ↓
Bot appears to hang (still looping but no trades)
  ↓
Watchdog detects no signals → may alert operator (depends on config)
```

**Points of no return:** Once degradation halts entries, recovery requires operator action (manual reset).

---

### Pattern 2: Database Corruption Cascade

```
Disk becomes full
  ↓
DB write timeout (10 seconds)
  ↓
Signal logging fails silently (try/except + pass)
  ↓
Trade logging fails silently
  ↓
Feedback loop record_trade_closed() throws
  ↓
Strategy weights never updated
  ↓
All future trades use stale weights
  ↓
Performance degradation (silent)
```

**Points of no return:** Once DB is inaccessible, bot continues trading with degraded signal quality.

---

### Pattern 3: LLM Agent Cascade with Silent Fallback

```
LLM API unavailable
  ↓
get_trading_decision() throws
  ↓
Exception caught, decision_result = None
  ↓
Mechanical signal proceeds to execution
  ↓
Trade executed without LLM review
  ↓
Bot operates in "mechanical only" mode (undetected)
  ↓
Next backtest may not use LLM → results differ
```

**Points of no return:** No explicit state tracking for "LLM currently unavailable" — all decisions assume LLM tried.

---

### Pattern 4: Position State Mismatch

```
Bot opens position on Hyperliquid
  ↓
Exchange confirms, returns order_id
  ↓
Position object created in PositionManager
  ↓
DB write begins
  ↓
CRASH occurs (process killed)
  ↓
On restart: reconcile_positions() queries exchange
  ↓
Exchange has position, reconciliation restores it
  ↓
But SL/TP levels unknown → estimated from ATR
  ↓
SL/TP may be 10% off from original
  ↓
Risk profile changed without operator knowledge
```

**Points of no return:** Original SL/TP levels cannot be recovered once lost.

---

### Pattern 5: Alert System Cascade

```
Discord webhook fails (network issue)
  ↓
Alert post throws requests.RequestException
  ↓
Exception caught, logged as warning
  ↓
Operator never sees signal
  ↓
No manual intervention possible
  ↓
If this is a high-risk trade, no safety net
```

**Points of no return:** No fallback alert channel, no retry logic.

---

## RECOVERY MECHANISMS

### Explicit Recovery

| System | Mechanism | Trigger | Effectiveness |
|---|---|---|---|
| Exchange positions | `reconcile_positions()` | Startup only | **Partial** (SL/TP estimated) |
| Circuit breaker state | `restore_circuit_breaker_state()` | Startup | **Full** (persisted to disk) |
| Database schema | `init_db()` | Startup (IF NOT EXISTS) | **Lossy** (recreates empty schema) |
| Strategy weights | Reload from DB | Startup | **Partial** (depends on DB integrity) |
| Equity tracking | Snapshot from positions | Runtime | **Full** (calculated from positions) |

### Implicit Recovery

| System | Mechanism | Effectiveness |
|---|---|---|
| Stale strategies | Continue evaluating until healthy | **Good** (ensemble continues) |
| Failed alerts | Retry on next cycle | **Variable** (may queue) |
| Mechanical bot memory | File writes retry on next signal | **Lossy** (data may be lost) |
| Stale data | Skip signal generation | **Good** (prevents bad trades) |

---

## CRITICAL RECOMMENDATIONS

### Tier 1: Must Fix (Production Risk)

1. **Add Circuit Breaker Exception Handling**
   ```python
   # execution/risk.py
   try:
       cb_check = self.circuit_breaker.check_daily_loss(...)
   except Exception as e:
       logger.critical(f"Circuit breaker check failed: {e}")
       # FAIL SAFE: assume breaker is tripped
       return False  # Reject trade
   ```

2. **Explicit LLM Failure Mode Tracking**
   ```python
   # llm/decision_engine.py
   if llm_unavailable:
       self.llm_failed_at = time.time()
       logger.warning("LLM unavailable — trading mechanically only")
       # Set global flag so other systems can detect
   ```

3. **Reconciliation Before First Trade**
   ```python
   # multi_strategy_main.py:run()
   self._reconcile_exchange_positions()
   assert self._reconciliation_complete, "Reconciliation failed, aborting"
   # Block trading until reconciliation succeeds
   ```

4. **Database Health Monitoring**
   ```python
   # data/db.py
   def is_healthy() -> bool:
       try:
           conn = get_connection()
           conn.execute("SELECT 1")
           return True
       except Exception:
           return False

   # In main loop, check periodically
   if not db.is_healthy():
       logger.critical("Database unavailable")
       self.stop_event.set()
   ```

5. **Signal Validation After Mutation**
   ```python
   # strategies/ensemble.py
   # After quality scoring or graduated rules modification
   if not result.is_valid():
       logger.warning(f"Signal became invalid after processing: {result}")
       return None
   ```

### Tier 2: Should Fix (Operational Risk)

6. **Health Monitoring for TIER 4/5 Systems**
   - Track `mechanical_bot_instrumentation` success rate
   - Alert if >10% failure rate
   - Track bot perception system uptime

7. **Alert Delivery Retry & Failover**
   - Implement alert queuing (in-memory or disk)
   - Retry failed alerts with exponential backoff
   - Fallback to secondary alert channel

8. **Position State Persistence**
   - Store original SL/TP when position opens
   - Use stored values on reconciliation (not ATR estimate)
   - Add integrity check on startup

9. **Graceful Degradation for LLM**
   ```python
   # When LLM unavailable, log it explicitly
   if not self.llm_available:
       logger.warning("Operating in mechanical-only mode (LLM unavailable)")
   ```

10. **Thread Safety for Shared State**
    - Add RLock to PositionManager (critical section)
    - Snapshot state for watchdog reads
    - Review all background thread accesses

### Tier 3: Should Monitor (Operational Visibility)

11. **Error Rate Thresholds**
    - Track exceptions per system
    - Alert if error rate exceeds threshold
    - Correlate with performance degradation

12. **Reconciliation Success Rate**
    - Log success/failure of each reconciliation
    - Alert if consecutive failures

13. **Database Write Latency**
    - Track DB write times
    - Alert if consistently slow (>500ms)

14. **LLM Decision Quality**
    - Track LLM agree/veto rate
    - Compare mechanical vs. LLM PnL (uplift tracking)

15. **Strategy Weight Drift**
    - Monitor weight changes over time
    - Alert if weights shift unexpectedly (potential data corruption)

---

## CONCLUSION

The NunuIRL bot is a **well-engineered system with thoughtful error handling**, but exhibits several **cascading failure patterns** that can lead to silent failures or degraded performance:

1. **TIER 4/5 hooks are "fire and forget"** — failures don't block trading, but create blind spots
2. **No explicit fallback states** — when systems fail (LLM, DB, exchange), bot continues with implicit fallbacks
3. **Reconciliation is not mandatory** — bot can start without knowing exchange positions
4. **Thread safety relies on GIL** — not explicitly synchronized (low risk, but not guaranteed)
5. **Database errors are silent** — logging failures don't bubble up to operator
6. **Alert failures are non-blocking** — operator may be unaware of critical trades

**Recommended priority:** Fix Tier 1 items (circuit breaker exception handling, reconciliation gating, database health checks) before going to production.

**Monitoring strategy:** Deploy health dashboard with alerts for:
- LLM availability
- Database health
- Exchange connectivity
- Alert delivery success rate
- Reconciliation failures
- Strategy weight drift

