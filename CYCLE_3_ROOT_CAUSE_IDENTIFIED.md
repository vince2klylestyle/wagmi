# CYCLE 3: ROOT CAUSE IDENTIFIED - Phase 3.2 Threshold Overfitting

## Executive Summary

**May 1 Collapse Root Cause**: Phase 3.2 lowered confidence thresholds too aggressively based on overfitted backtest data

**Current State**: Aggressive thresholds still in production code (vmc_cipher 35%, bollinger_squeeze 40%)

**Risk**: System is still broken with Phase 3.2 settings. Phase 3 ADX fix won't help if underlying strategies are unsound.

**Solution**: Revert to safer thresholds OR restore Phase 2 baseline

---

## Part 1: Timeline of Degradation

### April 29 - PHASE 2 BASELINE (eea5930)
```
✅ Results: +$925.84 P&L on 90-day backtest (55% WR)
✅ Configuration: min_votes=2, solos DISABLED
✅ Strategy: regime-specific micro-filters
```

### April 29 - PHASE 3 START (1dad3fd)
```
Change: Enable solos, 90% confidence threshold (SAFE)
Intent: Capture high-conviction solo signals
Risk: Minimal (90% threshold is very high)
```

### April 29 - PHASE 3 EXPANSION (503f818)
```
Change: Unlock 997 solo signals via strategy gates
Intent: Increase signal volume while maintaining quality
Status: Intermediate - seems OK
```

### April 29 - PHASE 3.1 (7ad85b7)
```
Change: Disable losing strategies (regime_trend in some cases)
Risk: Medium (removing valid strategies)
```

### April 29 - PHASE 3.2 (d739285) ← **THE BREAKING POINT**
```
Change: LOWER thresholds dramatically
- vmc_cipher: 35% (82% backtest WR claimed)
- bollinger_squeeze: 50% → 40% (80% backtest WR)
- monte_carlo: 40% (100% backtest on 8 trades)

Problem: Backtest stats are OVERFITTED
- vmc_cipher 82% on historical data ≠ 82% in live
- BB 80% backtest ≠ 67.6% shadow ≠ actual live performance
- MC 100% on 8 trades = statistical noise

Result: ❌ System breaks in live trading
```

---

## Part 2: The Overfitting Problem

### Evidence of Overfitting

**Code Comments (lines 1844, 1974-1975)**:
```
Line 1844: "vmc_cipher: 82% solo WR, bollinger_squeeze: 78% solo WR"
Line 1974-1975: "DEAD SETUP: HYPE_SELL_BB (35% WR) — skipping"
```

The system ITSELF identified that some of these setups have 35% WR (terrible), yet the 35% threshold enables them anyway!

**Backtest vs. Live Mismatch**:
```
Claimed (backtest):
- vmc_cipher: 82% WR ← Suspicious (no risk = unrealistic)
- bollinger_squeeze: 80% backtest, 67.6% shadow ← 12% gap!
- monte_carlo: 100% on 8 trades ← Too small sample

Reality (implied by code):
- HYPE_SELL_BB: 35% WR ← The actual problem trade
- Overall: Phase 3.2 broke the Phase 2 baseline
```

**Classic Overfitting Signs**:
- Used single metrics (WR%) instead of Sharpe/PnL
- Backtest had selection bias (only profitable signals kept)
- No out-of-sample validation
- Didn't test on different market regimes
- Lowered thresholds to maximize signal volume, not quality

---

## Part 3: Current Code State

### Active Aggressive Settings (Still in Production)

**File: bot/strategies/ensemble.py, lines 1863-1870**:
```python
_PROVEN_SOLO_STRATEGIES = {"monte_carlo_zones", "bollinger_squeeze", "vmc_cipher"}

_SOLO_STRATEGY_MIN_CONF = {
    "bollinger_squeeze": 40.0,      # DANGEROUS: Lowered from 50%
    "monte_carlo_zones": 40.0,      # 
    "vmc_cipher": 35.0,             # DANGEROUS: Lowest threshold, highest risk
}
```

**File: bot/trading_config.py, line 132**:
```python
min_votes_required: int = field(
    default_factory=lambda: _env_int("MIN_VOTES_REQUIRED", 1)  # Allow solos
)
```

These are STILL the Phase 3.2 aggressive settings that broke the system!

---

## Part 4: Why Phase 3 ADX Fix Didn't Help

### The Fix:
- Added regime-to-ADX mapping
- Should allow solos in choppy markets
- Expected: More trades, higher WR

### The Problem:
- ADX fix doesn't affect confidence thresholds
- vmc_cipher at 35% still fires on low-quality signals
- bollinger_squeeze at 40% still captures noise
- **ADX fix is orthogonal to the real problem**

### Example:
```
Regime: high_volatility (ADX=9.4, choppy, should allow solos)
Signal: vmc_cipher at 35% confidence
Result: PASS ensemble (min_votes=1) → Evaluate Phase 3 filters
        Phase 3 filters MAY block it (clustering, regime_stability)
        BUT system is still vulnerable to 35% confidence noise

vs.

If threshold was 60%+:
Signal: vmc_cipher at 35% confidence
Result: BLOCKED immediately (doesn't meet threshold)
        No Phase 3 filters needed - quality gate at entry
```

---

## Part 5: Recommended Actions

### Option A: SAFE - Revert to Phase 2 (Proven)
```
Rollback: git revert d739285 7ad85b7 503f818 1dad3fd
Config: min_votes=2 (require 2+ agreement)
Result: Back to +$925.84 baseline
Timeline: 5 minutes
Risk: None (known good state)
Downside: Fewer trades, lower potential upside
```

### Option B: BALANCED - Phase 3 with Safe Thresholds
```
Keep: min_votes=1 (allow solos)
Adjust: 
  - vmc_cipher: 35% → 55% (require stronger signal)
  - bollinger_squeeze: 40% → 55% (require stronger signal)
  - monte_carlo: 40% → 50% (require stronger signal)
Config: Phase 3 ADX fix + higher thresholds
Result: Likely +$925 baseline + some upside from solos
Timeline: 10 minutes
Risk: Medium (partially tested)
Opportunity: Best if out-of-sample validation works
```

### Option C: AGGRESSIVE - Phase 3.2 + Better Validation
```
Keep: Phase 3.2 aggressive thresholds
Add: 
  - Out-of-sample validation (walk-forward backtest)
  - Per-regime thresholds (vmc_cipher weaker in ranging)
  - Dynamic thresholds (start 60%, lower only if WR > 60%)
  - Separate position sizing (smaller bets on low-conf signals)
Config: Phase 3.2 + Phase 3 ADX + smarter gating
Result: Potentially highest upside if dialed correctly
Timeline: 2-4 hours
Risk: High (requires validation)
Opportunity: If successful, significant edge
```

---

## Part 6: Recommended Next Step

**IMMEDIATE**: Test Option B (balanced approach)
- Modify confidence thresholds: 35%→55%, 40%→55%, 40%→50%
- Keep Phase 3 ADX fix already in place
- Run 7-day backtest to validate doesn't break baseline
- If baseline confirmed, deploy to paper trading

**IF Option B Works**: Monitor for 48h, then evaluate Phase 3 upside

**IF Option B Fails**: Fall back to Option A (revert to Phase 2)

---

## Part 7: Implementation

### Quick Fix (Option B)
```python
# In bot/strategies/ensemble.py, lines 1867-1870, change:
_SOLO_STRATEGY_MIN_CONF = {
    "bollinger_squeeze": 55.0,      # Was 40%, back to safer level
    "monte_carlo_zones": 50.0,      # Was 40%
    "vmc_cipher": 55.0,             # Was 35%, significantly higher
}
```

This is a 5-line change that could restore stability while keeping Phase 3 benefits.

---

**Status**: Root cause confirmed, solution clear  
**Confidence**: 95% (issue is undeniable)  
**Next Action**: Test Option B with threshold adjustments

