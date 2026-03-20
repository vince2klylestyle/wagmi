# Phase 3A: Staging Deployment & Validation

**Start Time:** 2026-03-20T23:40:22 UTC
**Objective:** Validate all Phase 1 fixes under live-like market conditions
**Duration:** 24 continuous hours
**Environment:** Paper trading (safe, no real money)
**Symbols:** BTC, SOL (conservative starter set)

---

## Baseline Metrics (T+0:00)

**Initial State:**
- Memory Usage: Not running yet
- Database Size: 0 bytes (fresh)
- Trades: 0
- Signals: 0
- Errors: 0
- Status: Ready for deployment

---

## Deployment Checklist

- [x] Phase 2 testing complete (12/12 passed)
- [x] All critical files compile successfully
- [x] Configuration template prepared (.env)
- [x] ENVIRONMENT=paper verified
- [x] Monitoring script created and tested
- [ ] Bot process started
- [ ] Market data flowing
- [ ] First signal evaluated
- [ ] First trade executed (target: within 4 hours)

---

## Hourly Health Checkpoints

### T+1:00 (First Hour Checkpoint)
**Targets:**
- Memory: <75 MB
- Database: <1 MB
- At least 1 signal evaluated
- No ERROR logs

**Status:** Pending

---

### T+2:00 (Early Stability)
**Targets:**
- Memory: <80 MB
- Market data flowing
- Ensemble voting working
- LLM decision engine responding

**Status:** Pending

---

### T+4:00 (First Trade Execution)
**Targets:**
- First trade should have executed
- Trade recorded to database
- Position manager working
- Risk sizing applied correctly

**Status:** Pending

---

### T+8:00 (Mid-Session Deep Check)
**Targets:**
- Memory growth rate: <1 MB/hour
- Database growth: <2 MB/hour
- At least 3 trades attempted
- Circuit breaker not triggered
- TTL pruning scheduled

**Status:** Pending

---

### T+12:00 (Halfway Point)
**Targets:**
- Minimum 5 trades executed
- First trade closures occurring
- Deep memory recording trades
- Feedback loop updating weights
- No cascading errors

**Status:** Pending

---

### T+16:00 (Pre-Final)
**Targets:**
- Memory: <100 MB
- Database: <20 MB
- All gates working (slippage, liquidation)
- Alert system verified
- No unhandled exceptions

**Status:** Pending

---

### T+24:00 (Final Assessment)
**GO/NO-GO Decision:**
- All success criteria met?
- Any anomalies detected?
- System performance stable?

**Status:** Pending

---

## Success Criteria (ALL must be met to PASS)

1. ✅ At least 5 trades executed
2. ✅ Memory usage stays <100 MB
3. ✅ Database size stays <20 MB
4. ✅ Circuit breaker NOT falsely re-triggered
5. ✅ Liquidation safety checks preventing unsafe positions
6. ✅ Slippage gate rejecting high-slippage trades
7. ✅ Zero ERROR level logs
8. ✅ TTL pruning/archival running on schedule
9. ✅ No unhandled exceptions
10. ✅ Position manager state machine working
11. ✅ Trade outcomes correctly recorded
12. ✅ Feedback loop updating strategy weights

**Pass Rate Target:** 12/12 (100%)

---

## Real-Time Monitoring Commands

During 24-hour window, use these commands:

```bash
# Memory usage
ps aux | grep 'python.*run.py paper' | grep -v grep | awk '{print $6}' | head -1

# Database status
sqlite3 bot/data/trades.db "SELECT COUNT(*) FROM trades; SELECT COUNT(*) FROM signals;"

# Error count
tail -500 bot/data/logs/*.log | grep ERROR | wc -l

# Trade count
tail -200 bot/data/trades.csv | wc -l

# Circuit breaker status
grep "tripped\|reset\|cooldown" bot/data/logs/*.log | tail -10

# LLM decision status
tail -50 bot/data/llm/decisions.jsonl | python -m json.tool | head -20
```

---

## Risk Assessment

**Critical Risks During Staging:**
- Memory unbounded growth (TESTING THIS)
- Database unbounded growth (TESTING THIS)
- Peak equity reset bug allowing re-trips (TESTING THIS)
- Circuit breaker false re-triggers (TESTING THIS)
- Liquidation checks failing (TESTING THIS)
- Slippage gate not rejecting bad trades (TESTING THIS)

**Mitigation:** All covered by Phase 2 tests, now validating in live conditions.

---

## Next Phase Gate

**Proceeding to Phase 3B-1 (Production) if:**
- Memory <100 MB throughout
- Database <20 MB throughout
- 5+ trades executed
- 0 ERROR logs
- All gates working correctly
- 24 hours stable operation

**Returning to fix if:**
- Any SUCCESS CRITERIA fails
- Any unhandled exception
- Any FAIL CRITERIA triggered

---

## Notes & Observations

(To be filled during 24-hour monitoring)

---

**Monitoring Started:** 2026-03-20T23:40:22 UTC
**Estimated Completion:** 2026-03-21T23:40:22 UTC
