# LEARNINGS.md - Incident Log & Lessons Learned

Every incident should be documented here with:
1. What happened
2. Root cause
3. Fix applied
4. Test added
5. Preventive measure

---

## Template

### [DATE] - Brief Description
**Severity:** LOW / MEDIUM / HIGH / CRITICAL
**Impact:** What was affected
**Root cause:** Why it happened
**Fix:** PR link or description
**Test added:** Yes/No + test name
**Lesson:** What we learned

---

## Incidents

### [2026-02-27] - Trade log misread errors (impossible entries)
**Severity:** MEDIUM
**Impact:** Some logged trades had entries that could never have happened (entry above TP for longs, etc.)
**Root cause:** PnL and TP/SL calculations were using snapshot_entry (stale price at signal time) instead of live_entry (actual execution price). Price could move significantly between signal and execution.
**Fix:** Implemented dual-entry system (snapshot_entry + live_entry + effective_entry()). All PnL, TP/SL, and logs now use effective_entry. Added replay engine to detect impossible trades retroactively.
**Test added:** Yes - test_golden_replay.py, test_execution_safety.py (impossible entry detection)
**Lesson:** Always distinguish between signal-time price and execution-time price. Log both. Use execution price for all calculations.

### [2026-02-27] - Stale signals executing without penalty
**Severity:** LOW
**Impact:** Signals generated 10+ seconds ago were executing at potentially outdated prices.
**Root cause:** No snapshot age tracking or stale signal detection.
**Fix:** Added snapshot_ts tracking, snapshot_age computation, and configurable stale signal handling (veto/downgrade). Pre-execution guard checks age before every trade.
**Test added:** Yes - test_execution_safety.py (stale signal tests)
**Lesson:** Track the age of every signal. Old signals in fast-moving markets are dangerous.
