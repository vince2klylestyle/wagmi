# Failure Mode & Effects Analysis (FMEA)

## Quick Reference: Which Failures Stop Trading?

| Component | Failure | Trading Stops? | Operator Knows? | Data Lost? | Recovery Automatic? |
|---|---|---|---|---|---|
| Exchange API | Times out | ❌ No (after grace period) | ✅ Yes (watchdog) | ❌ No | ✅ Yes (retry) |
| Market data | Stale (>5min) | ✅ Yes (skips signals) | ❌ No (silent) | ❌ No | ✅ Yes (next candle) |
| Strategy crashes | Exception thrown | ❌ No (skipped) | ❌ No (debug log) | ❌ No | ✅ Yes (auto) |
| Ensemble voting | All strategies fail | ✅ Yes (no vote) | ❌ No | ❌ No | ✅ Yes (retry) |
| Circuit breaker | Check fails (exception) | ❌ **NO** (RISKY) | ❌ No | ❌ No | ❌ No |
| Position manager | State corruption | ❌ No (continues) | ❌ No | ⚠️ Maybe | ❌ No |
| Database | Write timeout | ❌ No (continues) | ❌ No | ✅ Yes | ❌ No |
| Database | Corruption | ❌ No (continues) | ❌ No | ✅ Yes | ⚠️ Partial |
| LLM API | Unavailable | ❌ No (mechanical fallback) | ❌ No | ❌ No | ⚠️ Maybe |
| LLM response | Invalid JSON | ✅ Yes (trade rejected) | ❌ No | ❌ No | ✅ Yes |
| Alerts | Delivery fails | ❌ No (continues) | ❌ **NO** | ❌ No | ⚠️ Maybe |
| Watchdog | Thread dies | ❌ No (continues) | ✅ Eventually | ❌ No | ❌ No |
| Reconciliation | Fails on startup | ❌ No (continues) | ⚠️ Logged | ❌ No | ❌ No |
| Mechanical bot | Instrumentation fails | ❌ No (continues) | ❌ No (debug log) | ✅ Yes | ✅ Yes (retry) |
| TIER 5 Perception | System dies | ❌ No (continues) | ❌ No | ✅ Yes | ❌ No |

---

## Detailed Failure Scenarios

### Scenario 1: "Silent Exchange Failure"
**Start:** Exchange API returns 503 (maintenance)

| Time | Event | Bot State | Operator Awareness |
|---|---|---|---|
| T+0s | API call returns 503 | Logs warning | ❌ No alert |
| T+60s | 10th consecutive failure | `degradation.halt_entries = true` | ❌ No alert |
| T+120s | No new signals for 2 min | Watchdog checks stall | ✅ Watchdog alerts |
| T+300s | Open positions managed (SL/TP still work) | Partial degradation | ✅ Alert sent if configured |
| T+600s | Operator sees alert, manually restarts | Bot recovers | ✅ Manual intervention |

**Points of no return:** Once degradation halts entries (after ~10 failures), operator must explicitly reset.

**Data lost:** None (market data cached)

---

### Scenario 2: "Database Write Cascade"
**Start:** Disk becomes full (`bot/data/ml_data/bot.db` write fails)

| Time | Event | Bot State | Operator Awareness |
|---|---|---|---|
| T+0s | Trade closes, closes normally | Trade removed from exchange | ✅ Position manager updated |
| T+1s | Feedback loop tries to record outcome | DB write timeout (10s) | ❌ No error logged (best-effort) |
| T+11s | Feedback timeout expires | Strategy weights NOT updated | ❌ No alert |
| T+30s | Next trade evaluated with stale weights | Suboptimal signal confidence | ❌ Silent degradation |
| T+1h | Performance drift becomes visible in metrics | Bot trades with poor signal quality | ⚠️ Maybe noticed in analysis |
| T+restart | Bot restarts, weights reset to defaults | Equity calculation may diverge | ✅ Operator sees in logs |

**Points of no return:** Data loss is permanent unless DB can be recovered.

**Data lost:** All trades since disk became full (not logged to DB).

---

### Scenario 3: "LLM Failure with Mechanical Fallback"
**Start:** Anthropic API becomes unavailable

| Time | Event | Bot State | Operator Awareness |
|---|---|---|---|
| T+0s | LLM call thrown exception | `get_trading_decision()` catches it | ❌ No global flag set |
| T+5s | Trade evaluated mechanically (fallback) | Trade proceeds without LLM review | ❌ No indication LLM failed |
| T+1m | Another signal → same fallback | Bot trades mechanically | ❌ Silent mode switch |
| T+5m | All trades in this period are mechanical | Performance depends only on mechanical system | ⚠️ Maybe visible in uplift metrics |
| T+recovery | LLM comes back online | Bot switches to normal mode | ❌ Operator doesn't know it switched back |

**Points of no return:** No explicit record of "LLM was unavailable during T+0 to T+recovery"

**Data lost:** None (trades logged), but context lost.

---

### Scenario 4: "Circuit Breaker Exception"
**Start:** Circuit breaker.check_daily_loss() throws exception

| Time | Event | Bot State | Operator Awareness |
|---|---|---|---|
| T+0s | Daily loss check: `max_consecutive_losses` corrupted | Exception thrown in check | ❌ Silent exception |
| T+1s | Exception is NOT caught (depends on code path) | Trade proceeds WITHOUT loss check | ⚠️ **CRITICAL** |
| T+2s | Trade opens, immediately loses money | Daily loss increases | ❌ No circuit breaker interference |
| T+3s | Next trade → same circuit breaker exception | Another trade opens | ❌ Circuit breaker bypassed |
| T+10s | 3x losses in a row | Bot should have tripped CB but didn't | ✅ Equity alert (if configured) |
| T+1h | Daily loss exceeds limit | CB should have triggered 30 minutes ago | ❌ **Bot kept trading** |

**Points of no return:** Once CB is corrupted, **no manual fix** without restarting.

**Data lost:** None, but risk limit violated.

**ROOT CAUSE:** No exception handling in circuit breaker check path (or incorrect exception handling).

---

### Scenario 5: "Position State Mismatch Post-Crash"
**Start:** Bot crashes while opening a position

| Time | Event | Bot State | Exchange State |
|---|---|---|---|
| T+0s | Signal approved, trade execution begins | Entry order sent to Hyperliquid | Pending |
| T+1s | Exchange confirms order, position opened | PositionManager creates Position object | Open: BTC 0.5, $42,000 entry |
| T+2s | Trade logged to DB | DB write in progress | Position still open |
| T+3s | **CRASH** (kill -9) | PositionManager in memory lost | Position remains open: 0.5 BTC |
| T+60s | Operator restarts bot | PositionManager is empty | Exchange still has 0.5 BTC |
| T+65s | Reconciliation queries exchange | Finds 0.5 BTC position | Entry: $42,000, estimated SL: $41,500 |
| T+70s | Position restored in PositionManager | SL estimated from ATR (may be $41,000) | Original SL unknown |
| T+duration | Bot manages position with wrong SL | Position stops out 5% earlier than expected | Bot got liquidated, should have survived |

**Points of no return:** Original SL/TP levels cannot be recovered.

**Data lost:** Original SL/TP, trade profile, entry type.

**Risk:** SL/TP levels may be off by 5-15%, changing risk profile.

---

### Scenario 6: "Alert System Failure"
**Start:** Discord webhook network error

| Time | Event | Signal → Bot → Exchange | Operator Notification |
|---|---|---|---|
| T+0s | High-confidence BUY signal generated | ✅ Approved by all gates | ❌ Alert POST fails (timeout) |
| T+5s | Position opens on Hyperliquid | ✅ $50k notional, 5x leverage | ❌ No notification sent |
| T+10s | Alert retry? | (depends on implementation) | ❌ **No retry in current code** |
| T+30s | Market moves 2% against position | Position is underwater | ❌ Operator still unaware |
| T+60s | Circuit breaker alert? | (should trigger) | ⚠️ Maybe, if alert system recovers |
| T+5m | Position closes at SL, loss realized | -$1,250 loss | ❌ **Operator never knew position existed** |

**Points of no return:** No fallback alert channel.

**Data lost:** None (trades logged), but operator blinded.

**Risk:** High-risk trading without operator oversight.

---

## Root Causes by Category

### Design Issues
1. **No explicit "LLM unavailable" state** → silent mechanical fallback
2. **No mandatory reconciliation** → can start without knowing exchange positions
3. **Alert failures non-blocking** → operator doesn't know if trade happened
4. **TIER 4/5 failures non-critical** → perception system can die silently

### Implementation Issues
1. **Circuit breaker exception not caught** → loss limits can be bypassed
2. **Database write timeout silent** → trades may not be logged
3. **Stale data check can fail silently** → stale signals may be accepted
4. **Strategy mutation in-place** → shared metadata can be corrupted

### Monitoring Issues
1. **No health metric for LLM availability** → operator doesn't know when it fails
2. **No database health check** → operator doesn't know when DB is down
3. **No alert delivery success rate** → operator doesn't know if alerts work
4. **No strategy weight drift detection** → operator doesn't know when weights are stale

---

## Silent Failure Risks (Most Dangerous)

### 1. Circuit Breaker Bypass
**Probability:** Medium (depends on exception handling)
**Impact:** Catastrophic (loss limits violated)
**Detection:** Only in post-incident analysis

### 2. Database Corruption
**Probability:** Low (depends on disk health)
**Impact:** High (strategy weights reset, performance degradation)
**Detection:** Only if DB is explicitly checked

### 3. LLM Unavailability
**Probability:** Medium (API unavailability, rate limits)
**Impact:** Medium (signal quality depends on LLM contributions)
**Detection:** Not obvious in trading output (no explicit mode tracking)

### 4. Reconciliation Failure
**Probability:** Medium (exchange API timeout)
**Impact:** High (risk limits may be exceeded)
**Detection:** Logged, but may be missed

### 5. Position State Mismatch
**Probability:** Low (only on crash)
**Impact:** High (SL/TP levels wrong, trade profile lost)
**Detection:** Visible in position margins after reconciliation

---

## Recommended Monitoring Dashboard

**Real-time metrics to display:**

1. **Exchange Health**
   - Last successful data fetch: (time)
   - Degradation state: ACTIVE / HALTED
   - Prefetch failures in last 1h: (count)

2. **LLM Health**
   - LLM available: YES / NO
   - Last successful decision: (time)
   - Decision success rate (last 24h): (%)
   - API errors (last 1h): (count)

3. **Database Health**
   - Last successful write: (time)
   - Write latency (p99): (ms)
   - DB file size: (MB)
   - Disk space available: (GB)

4. **Alert Health**
   - Alerts sent (last 1h): (count)
   - Alert delivery success rate: (%)
   - Alert failures (last 1h): (count)

5. **Reconciliation Health**
   - Last reconciliation: (time)
   - Reconciliation success rate: (%)
   - Positions reconciled: (count)

6. **Watchdog Health**
   - Watchdog alive: YES / NO
   - Last heartbeat: (time)
   - Stalls detected: (count)

7. **Circuit Breaker Health**
   - CB state: ACTIVE / TRIPPED / COOLDOWN
   - Daily loss: (%)
   - Consecutive losses: (count)
   - Last check time: (time)

---

## Recovery Time Estimates

| Component Failure | Time to Impact | Recovery Time | Manual Intervention Required? |
|---|---|---|---|
| Exchange API | 5-60 sec | 60-300 sec | No (automatic retry) |
| Market data stale | Immediate | 60 sec (next candle) | No |
| Strategy exception | Immediate (skipped) | Automatic | No |
| Database write fail | Immediate | Depends on disk | Maybe (if disk full) |
| LLM unavailable | Immediate (fallback) | API recovery time | No (but silent) |
| Circuit breaker corrupt | Immediate | Restart bot | Yes |
| Reconciliation fail | Startup only | Restart bot | Yes |
| Alert delivery fail | Immediate (operator blinded) | Manual retry / restart | Yes |
| Watchdog thread dies | 5+ minutes (stall detection) | Restart bot | Yes |
| TIER 5 perception dies | Immediate | Restart bot | Yes |

---

## Fail-Safe vs. Fail-Open Patterns

### Current Implementation

| Component | Pattern | Risk |
|---|---|---|
| Circuit breaker exception | **Open** (lets trades through) | **HIGH** |
| LLM decision failure | **Open** (mechanical fallback) | **MEDIUM** |
| Alert delivery failure | **Open** (continues trading) | **MEDIUM** |
| Database write failure | **Open** (trade proceeds) | **MEDIUM** |
| Reconciliation failure | **Open** (starts without positions) | **MEDIUM** |
| Stale data check fail | **Open** (processes stale signal) | **LOW** |
| Strategy exception | **Closed** (signal skipped) | ✅ Good |
| Ensemble voting fail | **Closed** (no signal) | ✅ Good |

**Recommendation:** Convert HIGH and MEDIUM fail-open patterns to fail-safe (fail-closed).

---

## Cascade Prevention Measures

### Measure 1: Health Check Gating
```python
# At startup, before first trade
if not db.is_healthy():
    raise RuntimeError("Database unavailable, aborting startup")
if not reconcile_positions(...):
    raise RuntimeError("Reconciliation failed, aborting startup")
if not can_call_llm():
    logger.warning("LLM unavailable, starting in mechanical-only mode")
    self.llm_mode = LLMMode.OFF
```

### Measure 2: Explicit State Transitions
```python
# Track when systems become unavailable
class SystemHealth:
    llm_available_since = time.time()
    db_available_since = time.time()
    exchange_available_since = time.time()

    def get_unavailability_duration(self, system: str) -> float:
        return time.time() - getattr(self, f"{system}_available_since")
```

### Measure 3: Circuit Breaker Hardening
```python
try:
    should_reject = self.circuit_breaker.check_daily_loss(...)
except Exception as e:
    logger.critical(f"Circuit breaker check failed: {e}")
    should_reject = True  # FAIL-SAFE: assume we should reject
    self.circuit_breaker_health = "CORRUPTED"
    self.watchdog.alert_fn("Circuit breaker health compromised")

if should_reject:
    return FilterResult(approved=False, ...)
```

### Measure 4: Database Write Verification
```python
# After each critical write
if not verify_write(trade_id):
    logger.critical(f"Trade {trade_id} not in database!")
    self.watchdog.alert_fn(f"Database write verification failed")
    # Implement fallback: retry, or queue in memory
```

### Measure 5: Reconciliation Gating
```python
# In run()
self._reconciliation_required = True
while self._reconciliation_required:
    try:
        reconcile_positions(...)
        self._reconciliation_required = False
        self._reconciliation_complete = True
    except Exception as e:
        logger.error(f"Reconciliation failed: {e}")
        if should_abort:
            raise SystemExit("Reconciliation required but failed")

assert self._reconciliation_complete, "Reconciliation incomplete"
```

