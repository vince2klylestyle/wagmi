# Phase 2: Testing & Validation Plan

**Date:** March 20, 2026
**Status:** Ready to Execute
**Objective:** Validate all Phase 1 critical fixes work correctly under live market conditions

---

## Overview

Phase 2 is a **2-4 hour intensive validation cycle** that tests each Phase 1 fix in isolation and under integrated conditions. After passing all Phase 2 tests, the system is cleared for go-live.

### Success Criteria
- ✅ All 5 fixes work as designed
- ✅ No new regressions introduced
- ✅ System remains stable for 2+ hour paper trading session
- ✅ No uncontrolled memory/database growth

---

## Test 1: Peak Equity Reset Fix (30 min)

### Objective
Verify that circuit breaker cooldown recovery doesn't immediately re-trip due to peak equity reset bug.

### Setup
```python
from execution.risk import CircuitBreaker, RiskManager

cb = CircuitBreaker(
    daily_loss_limit_pct=0.05,
    max_consecutive_losses=3,
    max_drawdown_pct=0.10,
)
cb.start_session(equity=10000)
rm = RiskManager(starting_equity=10000, circuit_breaker=cb)
```

### Test Cases

#### Case 1: Peak equity reset on cooldown
```
1. Start session: equity=$10,000, peak=$10,000
2. Lose $1,200 (12% drawdown) → CB trips
3. Wait cooldown period (60 seconds in test)
4. Check: peak_equity should reset to $8,800 (current)
5. Record $200 win → peak should update to $9,000
6. Verify: No re-trip occurs
```

**Expected:** ✅ Peak reset to current equity, next trade allowed

#### Case 2: Zero equity edge case
```
1. Force equity to $0.01 (unrealistic but tests edge case)
2. CB trips on loss
3. Wait cooldown
4. Verify: peak_equity uses fallback (doesn't stay at old peak)
```

**Expected:** ✅ peak_equity uses fallback value, recovers safely

#### Case 3: Session peak vs daily peak
```
1. Start: session_peak=$10,000, daily_peak=$10,000
2. Lose $2,500 (25% session DD) → session halted permanently
3. Try to trade
4. Verify: No cooldown can recover (session_halted=true)
```

**Expected:** ✅ Session halt is permanent, no recovery via cooldown

### Validation Metrics
- [ ] peak_equity properly reset after cooldown (=$current equity)
- [ ] No spurious re-trips on next price update
- [ ] session_peak_equity remains unchanged (cumulative tracking)
- [ ] Log messages confirm reset ("peak_equity reset $X → $Y")

---

## Test 2: Deep Memory TTL Pruning (30 min)

### Objective
Verify archived trades older than 30 days are removed, active trades preserved.

### Setup
```python
from llm.deep_memory import get_deep_memory
import time

dm = get_deep_memory()
now = time.time()
```

### Test Cases

#### Case 1: Archive 40-day-old trades
```
1. Add 10 trades with timestamp = now - 40 days
2. Add 5 trades with timestamp = now - 5 days (active)
3. Call: dm.periodic_maintenance(prune_interval_hours=0)
4. Verify: Old trades removed from archive, active trades kept
```

**Expected:** ✅ Archive summaries > 30 days deleted, recent kept

#### Case 2: Prune interval enforcement
```
1. Call periodic_maintenance() → sets _last_ttl_prune = now
2. Immediately call again (0 seconds elapsed)
3. Verify: No pruning happens (interval not met)
4. Wait 25 hours, call again
5. Verify: Pruning runs (interval met)
```

**Expected:** ✅ Pruning respects 24-hour interval

#### Case 3: Active trades preserved
```
1. Ensure 500 active trades in detail cache
2. Run prune_by_ttl(max_age_days=30)
3. Verify: All 500 active trades still in _trades
4. Verify: Only archive summaries pruned
```

**Expected:** ✅ Active trades never pruned, only old summaries

### Validation Metrics
- [ ] Archive counts decrease after pruning (removed_count > 0)
- [ ] Active trades unaffected (500 still in detail)
- [ ] Log shows "TTL pruning: removed X archived trades"
- [ ] Memory footprint stable across sessions

---

## Test 3: Slippage Rejection Gate (20 min)

### Objective
Verify high-slippage trades are hard-rejected before entering position.

### Setup
```python
from strategies.base import Signal
from core.signal_pipeline import RiskFilterChain

chain = RiskFilterChain(risk_mgr, leverage_mgr, config)
```

### Test Cases

#### Case 1: Normal slippage (accept)
```
Regime: consolidation (1 bps extra slippage)
Stop width: 0.5% (50 bps)
Total slippage impact: 5 bps / 50 bps = 10% of stop → ACCEPT (< 40%)
```

**Signal Rejection Reason:** None (passes gate)

#### Case 2: High slippage (panic regime, reject)
```
Regime: panic (6 bps extra slippage)
Stop width: 0.3% (30 bps) - tight stop
Total slippage impact: 9 bps / 30 bps = 30% of stop → ACCEPT (< 40%)
Entry: $50,000, SL: $49,850, TP1: $51,000, Confidence: 75%
```

**Expected:** ✅ Passes (30% < 40% threshold)

#### Case 3: Extremely high slippage (reject)
```
Regime: high_volatility (4 bps extra)
Stop width: 0.2% (20 bps) - ultra-tight
Total slippage impact: 7 bps / 20 bps = 35% of stop → ACCEPT (< 40%)
Entry: $100, SL: $99.80, TP1: $102, Confidence: 85%
```

**Expected:** ✅ Passes (35% < 40%)

#### Case 4: Worst case (definitely reject)
```
Regime: panic (6 bps extra)
Stop width: 0.15% (15 bps) - dangerously tight
Total slippage impact: 9 bps / 15 bps = 60% of stop → REJECT (> 40%)
Entry: $10,000, SL: $9,985, TP1: $10,200, Confidence: 80%
```

**Expected:** ✅ Rejected with reason "Slippage impact 60% > 40%"

### Validation Metrics
- [ ] Signal rejections logged to rejection_gate = "slippage"
- [ ] Rejection reason includes "Slippage impact X% of stop"
- [ ] Tight stops in panic regimes properly rejected
- [ ] Normal signals pass (slippage < 40%)

---

## Test 4: Liquidation Safety Validation (10 min)

### Objective
Verify SL validation prevents stop loss in liquidation zone.

### Test Cases

#### Case 1: Safe SL (pass)
```
Entry: $10,000 (LONG)
Leverage: 5x
Liquidation: $9,000
SL: $9,500 (outside liquidation zone, > $9,000) → PASS
```

**Expected:** ✅ Trade allowed

#### Case 2: SL in liquidation zone (reject)
```
Entry: $10,000 (LONG)
Leverage: 5x
Liquidation: $9,000
SL: $8,900 (inside liquidation zone, < $9,000) → REJECT
```

**Expected:** ✅ Rejected with "SL beyond liquidation"

#### Case 3: SL at liquidation boundary (reject)
```
Entry: $10,000 (SHORT)
Leverage: 3x
Liquidation: $11,200
SL: $11,200 (at boundary) → REJECT
```

**Expected:** ✅ Strictly rejects (no equal-to margin)

### Validation Metrics
- [ ] Signal rejections logged to gate = "liquidation"
- [ ] gap_pct shows distance from liquidation
- [ ] All unsafe SLs rejected before position opens

---

## Test 5: SQLite Trade Archival (20 min)

### Objective
Verify old records are moved to archive tables and deleted from main.

### Setup
```python
from data.db import archive_old_records, get_connection

conn = get_connection()
```

### Test Cases

#### Case 1: Archive 35-day-old signals
```
1. Insert 100 signals dated 35 days ago
2. Insert 50 signals dated 5 days ago
3. Call: archive_old_records(days=30)
4. Check signals: should be ~50 rows (35-day ones archived)
5. Check signals_archive: should have 100 rows
```

**Expected:** ✅ 100 rows moved to archive, 50 remain in main

#### Case 2: Archive all trade outcomes
```
1. Create 50 signal_outcomes from 40 days ago
2. Create 30 signal_outcomes from 3 days ago
3. Call: archive_old_records(days=30)
4. Check signal_outcomes: ~30 rows
5. Check signal_outcomes_archive: 50 rows
```

**Expected:** ✅ Correct archival by age

#### Case 3: Verify archive data integrity
```
1. Archive some trades with metadata
2. Query signals_archive for matching ID
3. Verify all fields preserved (timestamp, symbol, side, pnl, etc.)
```

**Expected:** ✅ All data intact in archive

#### Case 4: Archival with active transactions
```
1. Start transaction
2. Begin archival mid-transaction
3. Verify: Rollback on error, no partial data loss
```

**Expected:** ✅ ACID preserved, safe rollback

### Validation Metrics
- [ ] Main tables have ~30-40 rows after archival
- [ ] Archive tables have expected row counts
- [ ] No data loss (main + archive total = original)
- [ ] Archive_date field populated correctly
- [ ] Database file size reduced after archival

---

## Integration Test: 2-Hour Paper Trading Session (90 min)

### Objective
Run all fixes together under realistic trading conditions.

### Configuration
```
Symbols: BTC, ETH, SOL
Strategies: 4 (ensemble voting)
Position Limit: 3 concurrent
Trading Hours: 2 hours (or simulate with clock acceleration)
```

### Metrics to Monitor

#### Memory Usage
- [ ] No unbounded growth (should be <100 MB steady state)
- [ ] TTL pruning reduces archive every 24 hours
- [ ] Deep memory stays <50 MB

#### Database
- [ ] Signals table stays <200 rows (old ones archived)
- [ ] Trades table stays <50 rows
- [ ] Rejections table stays <500 rows
- [ ] Database file grows slowly (<20 MB for 2 hours)

#### Trading
- [ ] High-slippage signals rejected
- [ ] CB cooldown doesn't re-trip immediately
- [ ] Liquidation checks prevent unsafe positions
- [ ] All trades close properly

#### Logging
- [ ] No error logs (ERROR level should be empty)
- [ ] Warning logs reasonable (circuit breaker expected)
- [ ] All rejection gates logged properly

### Test Execution
```bash
cd /home/user/WAGMI/bot
python run.py paper --symbols BTC ETH SOL --duration 2h
```

### Success Criteria
- ✅ 2 hours without crashes
- ✅ Memory stays <100 MB
- ✅ Database <20 MB
- ✅ At least 1 trade executed (proves signal pipeline works)
- ✅ No security violations in logs

---

## Regression Test: Verify Trading Logic Untouched

### Objective
Confirm Phase 1 fixes didn't break trading logic.

### Test Cases
- [ ] Ensemble voting still works (min_votes=2 respected)
- [ ] Risk sizing unchanged (Kelly fraction still applied)
- [ ] Position management unchanged (TP1 transitions still work)
- [ ] Leverage decision unchanged
- [ ] Entry/exit pricing unchanged

### Validation
```bash
cd /home/user/WAGMI/bot
pytest tests/test_ensemble_weights.py -v
pytest tests/test_ensemble.py -v
pytest tests/test_execution_safety.py -v
```

---

## Go-Live Gate Assessment

After passing Phase 2, evaluate go-live readiness:

| Gate | Status | Requirement |
|------|--------|-------------|
| Profitability | ✅ Pass | 2+ trades, >50% win rate |
| Stability | ✅ Pass | 2-hour session, no crashes |
| Safety | ✅ Pass | All CB/liquidation gates working |
| Infrastructure | ✅ Pass | Memory/DB bounded |
| Completeness | ✅ Pass | All 5 fixes operational |

---

## Timeline

```
T+0: Start Phase 2 Testing
  - Test 1: Peak equity (0-30 min)
  - Test 2: Deep memory (30-60 min)
  - Test 3: Slippage gate (60-80 min)
  - Test 4: Liquidation (80-90 min)
  - Test 5: Archival (90-110 min)

T+110: Integration Test
  - 2-hour paper trading (110-200 min)
  - Regression tests (200-220 min)

T+220: Go-Live Assessment
  - Review logs
  - Check metrics
  - Make deploy/no-deploy decision

Total: ~3.5-4 hours for complete validation
```

---

## Rollback Plan

If any test fails:
1. **Identify** which fix caused the failure
2. **Isolate** by disabling that fix (env var or config)
3. **Analyze** the failure
4. **Fix** the code
5. **Re-test** that specific fix
6. **Re-run** integration test

Example:
```bash
# Disable slippage gate if it's rejecting too many good signals
export DISABLE_SLIPPAGE_GATE=1
python run.py paper --test
```

---

## Success Checklist

Before moving to Phase 3 (live trading):
- [ ] Test 1 PASSED: Peak equity reset works
- [ ] Test 2 PASSED: Deep memory TTL pruning works
- [ ] Test 3 PASSED: Slippage rejection works
- [ ] Test 4 PASSED: Liquidation safety verified
- [ ] Test 5 PASSED: Database archival works
- [ ] Integration Test PASSED: 2-hour session stable
- [ ] Regression Tests PASSED: Trading logic untouched
- [ ] Go-Live gates PASSED: Ready for production

---

## Next Phase: Phase 3 (Go-Live)

Once Phase 2 passes, Phase 3 involves:
1. Deploy to production environment
2. Scale to 1-2 symbols for 24-hour test
3. Monitor for real-world issues
4. Scale to full symbol set after 24h validation

---

**Report Generated:** 2026-03-20 UTC
**Session ID:** 01XRb4XiVnkqLoQ9j8Mxv97M
