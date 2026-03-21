# System Integration Audit — Quick Reference

**Full Reports Available:**
- `SYSTEM_INTEGRATION_AUDIT.md` — Comprehensive 1100-line audit
- `FAILURE_MODE_ANALYSIS.md` — Detailed FMEA with scenarios

---

## The 8 Critical Risks (Summary)

| Risk | Severity | Trading Stops? | Operator Knows? | Impact |
|---|---|---|---|---|
| Circuit breaker exception | 🔴 HIGH | ❌ No | ❌ No | Loss limits bypassed |
| LLM unavailable | 🟡 MEDIUM | ❌ No | ❌ No | Silent mode switch (mechanical-only) |
| Reconciliation fails | 🟡 MEDIUM | ❌ No | ⚠️ Maybe | Position limits exceeded |
| Database write fails | 🟡 MEDIUM | ❌ No | ❌ No | Strategy weights stale, data loss |
| TIER 4/5 hooks fail | 🟡 MEDIUM | ❌ No | ❌ No | Perception data lost |
| Alert delivery fails | 🟡 MEDIUM | ❌ No | ❌ **No** | Operator blind |
| Position crash loss | 🟡 MEDIUM | ❌ No | ❌ No | SL/TP levels lost forever |
| Signal mutation | 🟢 LOW-MEDIUM | ❌ No | ❌ No | Metadata corruption |

---

## Decision Tree: Will This Stop Trading?

```
Did system fail?
├─ Exchange API → YES (after grace period, degradation halts)
├─ Market data stale → YES (signals skipped)
├─ Strategy exception → NO (skipped, ensemble continues)
├─ Ensemble voting fails → YES (no vote)
├─ Circuit breaker exception → NO (RISKY!)
├─ LLM unavailable → NO (silent mechanical fallback)
├─ Database inaccessible → NO (continues unlogged)
├─ Alert delivery fails → NO (operator blinded)
├─ Reconciliation fails → NO (starts without positions)
└─ Watchdog dies → NO (no stall detection)
```

---

## The 5 Most Dangerous Silent Failures

### 1. Circuit Breaker Bypass
**How:** CB check throws exception → caught → trade proceeds unchecked
**Impact:** Loss limits violated, unlimited losses possible
**Likelihood:** Medium (depends on CB state corruption)
**Detection:** Only in post-incident review

### 2. LLM Unavailable (Silent Mode Switch)
**How:** LLM API fails → fallback to mechanical → no operator notification
**Impact:** Performance depends only on mechanical strategies
**Likelihood:** High (API rate limits, timeouts)
**Detection:** Not obvious in trading output

### 3. Database Corruption Cascade
**How:** Disk full → writes timeout → weights not updated → cascades
**Impact:** Strategy weights stale, signal quality degrades
**Likelihood:** Low (depends on disk health)
**Detection:** Only if weights explicitly checked

### 4. Position State Mismatch (Post-Crash)
**How:** Crash during position opening → SL/TP lost → ATR estimate wrong
**Impact:** Risk profile changed 5-15% after crash
**Likelihood:** Low (depends on crash timing)
**Detection:** Visible in reconciliation margin check

### 5. Alert System Failure
**How:** Webhook fails → no alert → operator never knows
**Impact:** High-risk trading without oversight
**Likelihood:** Medium (network issues, webhook server down)
**Detection:** Not obvious (no confirmation of delivery)

---

## Red Flags to Watch For

In production, if you see ANY of these:
- ⚠️ **"Circuit breaker check failed"** → STOP trading immediately
- ⚠️ **"Database write timeout"** repeated → Check disk space, stop if persists
- ⚠️ **"LLM decision failed"** → Confirm LLM is up, track mechanical-only duration
- ⚠️ **"Reconciliation failed"** on startup → Check exchange connectivity before trading
- ⚠️ **No alerts for >1 hour** → Test webhook, verify alert system alive
- ⚠️ **Strategy weights identical** → DB may be corrupted, check integrity
- ⚠️ **Position margins different after reconciliation** → SL/TP were re-estimated

---

## Pre-Production Checklist

Before deploying to production:

### Must Fix (Tier 1)
- [ ] Add exception handling to circuit breaker check (fail-safe)
- [ ] Gate startup on successful reconciliation (abort if fails)
- [ ] Implement database health check (stop if unavailable)
- [ ] Add explicit LLM unavailability state tracking
- [ ] Persist SL/TP to disk when position opens

### Should Fix (Tier 2)
- [ ] Implement alert retry + queueing
- [ ] Add health monitoring for TIER 4/5 systems
- [ ] Deep copy signals before mutation
- [ ] Add thread-safe snapshots for watchdog
- [ ] Implement strategy weight drift detection

### Must Monitor (Tier 3)
- [ ] Exchange health (last fetch, degradation state)
- [ ] LLM health (available, decision success rate)
- [ ] Database health (write latency, disk space)
- [ ] Alert health (delivery success rate, failures)
- [ ] Reconciliation health (success rate, count)
- [ ] Circuit breaker health (state, daily loss %)

---

## The Bot's Dominant Failure Pattern

```
System Failure
    ↓
Exception caught, logged
    ↓
Trading CONTINUES (fail-open)
    ↓
Operator UNAWARE (no alert)
    ↓
Silent degradation (hours/days)
```

**vs. Intended Pattern (fail-safe):**
```
System Failure
    ↓
STOP trading immediately
    ↓
Alert operator
    ↓
Operator investigates & fixes
```

---

## File Locations for Key Systems

| System | File | Function | Risk Level |
|---|---|---|---|
| Circuit Breaker | `execution/risk.py` | `check_daily_loss()` | 🔴 HIGH (no exception handling) |
| Reconciliation | `execution/reconciliation.py` | `reconcile_positions()` | 🟡 MEDIUM (optional) |
| Database | `data/db.py` | `get_connection()` | 🟡 MEDIUM (10s timeout) |
| LLM Pipeline | `llm/decision_engine.py` | `get_trading_decision()` | 🟡 MEDIUM (silent fallback) |
| TIER 4 Hooks | `llm/mechanical_bot_instrumentation.py` | `on_signal_generated()` | 🟡 MEDIUM (fire-and-forget) |
| Alert Router | `alerts/router.py` | `send_signal()` | 🟡 MEDIUM (no retry) |
| Position Manager | `execution/position_manager.py` | `open_position()` | 🟡 MEDIUM (state loss on crash) |
| Watchdog | `monitoring/watchdog.py` | `_run()` | 🟢 LOW (daemon thread) |

---

## Key Metrics to Track

Add these to your health dashboard:

```
LLM_AVAILABLE = true/false
LLM_LAST_SUCCESS_TIME = (epoch)
LLM_DECISION_SUCCESS_RATE = (%)

DB_HEALTHY = true/false
DB_WRITE_LATENCY_P99 = (ms)
DB_DISK_SPACE_AVAILABLE = (GB)

EXCHANGE_DEGRADATION_STATE = ACTIVE/HALTED
EXCHANGE_LAST_FETCH_TIME = (epoch)
EXCHANGE_PREFETCH_FAILURES_1H = (count)

ALERT_DELIVERY_SUCCESS_RATE = (%)
ALERT_FAILURES_1H = (count)

CB_STATE = ACTIVE/TRIPPED/COOLDOWN
CB_DAILY_LOSS_PCT = (%)
CB_CONSECUTIVE_LOSSES = (count)

RECONCILIATION_SUCCESS_RATE = (%)
RECONCILIATION_LAST_SUCCESS = (epoch)
```

---

## Example: What Happens When Disk Fills

```
T+0s   Disk fills up (>99% usage)
T+1s   Trade closes, feedback loop tries to record
T+11s  DB write timeout (10s) — exception caught, logged
T+12s  Feedback loop continues without persisting outcome
T+30s  Strategy weight update skipped (no DB write)
T+60s  Next ensemble vote uses stale/default weights
T+2h   Performance degradation becomes noticeable
T+8h   Operator finally notices bad trades, investigates
T+9h   Root cause: disk full, strategy weights outdated
T+10h  Operator clears disk, restarts bot
```

**Silent window:** 9 hours. Operator unaware entire time.

---

## Example: Circuit Breaker Bypass

```python
# execution/risk.py (current code pattern)
if self.risk_mgr.circuit_breaker.check_daily_loss(daily_pnl, equity):
    # Circuit breaker check PASSED, trade allowed
    trade_signal = signal_result
else:
    # Circuit breaker FAILED, trade rejected
    return None

# RISK: If check_daily_loss() throws exception:
# → Exception not caught
# → Control falls through
# → Trade proceeds WITHOUT any loss limit check
# → Operator has no warning
```

**Fixed version:**
```python
try:
    should_reject = self.circuit_breaker.check_daily_loss(daily_pnl, equity)
except Exception as e:
    logger.critical(f"Circuit breaker check failed: {e}")
    should_reject = True  # FAIL-SAFE: assume breaker is tripped
    self.watchdog.alert_fn("Circuit breaker health compromised")

if should_reject:
    return FilterResult(approved=False, ...)  # Reject trade
```

---

## Production Deployment Recommendations

### Phase 1: Fix Critical Issues (Before Any Trading)
1. Fix circuit breaker exception handling
2. Gate startup on successful reconciliation
3. Implement database health check
4. Add explicit LLM unavailability state

### Phase 2: Add Monitoring (Day 1)
1. Deploy health dashboard with key metrics
2. Set alerts for critical thresholds
3. Test alert delivery (Discord/Telegram)
4. Set up operator on-call rotation

### Phase 3: Graceful Degradation (Week 1)
1. Implement alert retry + queueing
2. Add TIER 4/5 health monitoring
3. Implement strategy weight drift detection
4. Add thread-safe snapshots

### Phase 4: Full Hardening (Week 2+)
1. Deep copy signals before mutation
2. Persist position state to disk
3. Implement database recovery logic
4. Run stress tests (simulate failures)

---

## Questions This Audit Answered

✅ **Where do TIER 4/5 hooks integrate?**
→ Lines 2783 in multi_strategy_main.py; fire-and-forget pattern

✅ **What happens if hooks fail?**
→ Trading continues; failures are silent (debug log only)

✅ **Can one strategy break ensemble?**
→ Partially yes; mutations can corrupt shared metadata

✅ **How do position & risk management interact?**
→ Risk manager approves trades; position manager executes and states; no explicit coordination

✅ **What if LLM and mechanical disagree?**
→ LLM can veto (if enabled); mechanical fallback if LLM fails (silent)

✅ **How does feedback loop integrate with weights?**
→ Trades → Feedback → DB → Strategy weights updated; if DB fails, weights stale

✅ **What if database is corrupted?**
→ Schema recreated but data lost; performance degrades silently

✅ **How does bot recover from crashes?**
→ Reconciliation restores positions but may estimate SL/TP wrong

✅ **Any shared state issues between threads?**
→ PositionManager accessed by main + watchdog; no locks (low risk, not guaranteed)

✅ **What if market data stops?**
→ Degradation halts new entries; open positions still managed

✅ **How do alerts interact with trading?**
→ Non-blocking; failures don't stop trades (operator blinded)

✅ **Missing error handlers?**
→ Circuit breaker exception, database health check, reconciliation retry, alert retry

---

## Need More Detail?

See full reports:
- **SYSTEM_INTEGRATION_AUDIT.md** — Complete technical analysis (37 KB)
- **FAILURE_MODE_ANALYSIS.md** — Detailed scenarios & recommendations (14 KB)

Both in `/home/user/WAGMI/` directory.
