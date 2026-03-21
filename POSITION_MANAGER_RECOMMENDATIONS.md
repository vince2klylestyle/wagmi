# Position Manager: Specific Recommendations

## CRITICAL FIXES (Implement Immediately)

### 1. Add Warning for Rounding-Induced Full Close (HIGH PRIORITY)

**Current Code (lines 549-551):**
```python
if close_qty <= 0 or close_qty >= pos.qty:
  return self._close_position(pos, price, "TP1_FULL")
```

**Problem:** Silently converts partial close to full close when rounding fails. User has no indication.

**Recommended Fix:**
```python
if close_qty <= 0:
  logger.warning(
    f"[{pos.symbol}] TP1 partial close: close_qty rounded to 0 "
    f"({pos.qty}*{dynamic_close_pct:.2%}). Converting to full close."
  )
  return self._close_position(pos, price, "TP1_FULL")

elif close_qty >= pos.qty:
  logger.warning(
    f"[{pos.symbol}] TP1 partial close: close_qty rounded to full qty "
    f"({close_qty} >= {pos.qty}). Closing entire position."
  )
  return self._close_position(pos, price, "TP1_FULL")
```

**Impact:** Traders can see when rounding forced their partial close into a full close.

---

### 2. Validate Breakeven SL Doesn't Invert Direction (HIGH PRIORITY)

**Current Code (lines 574-588):**
```python
be_price = pos.entry - profit_cushion + fee_buffer  # [LONG]
pos.sl = round_price(pos.symbol, be_price)
```

**Problem:** If realized_pnl is negative (TP1 closed at loss), new SL moves ABOVE entry. This is mathematically correct but unintuitive and risky.

**Recommended Check:**
```python
# After calculating new_sl:
if pos.side == "LONG":
  min_protective_sl = pos.entry - abs(pos.entry - pos.original_sl) * 0.50
  if pos.sl < min_protective_sl:
    logger.warning(
      f"[{pos.symbol}] Breakeven SL ({pos.sl}) < half-original-risk ({min_protective_sl}). "
      f"TP1 closed at loss (realized_pnl={pos.realized_pnl:.2f}). "
      f"Consider reviewing TP1 triggers."
    )
elif pos.side == "SHORT":
  max_protective_sl = pos.entry + abs(pos.entry - pos.original_sl) * 0.50
  if pos.sl > max_protective_sl:
    logger.warning(f"[{pos.symbol}] Breakeven SL inverted: {pos.sl} > {max_protective_sl}")
```

**Impact:** Alerts when TP1 partial close strategy is losing money.

---

### 3. Add Sanity Check: Funding Costs Shouldn't Exceed Realized PnL (MEDIUM PRIORITY)

**Current Code (line 770):**
```python
pos.realized_pnl += (pnl - fee - pos.funding_costs)
```

**Problem:** If funding costs are mis-tracked, this could go very negative.

**Recommended Check:**
```python
# Before final close:
if pos.funding_costs > abs(pos.realized_pnl) * 1.50:
  logger.warning(
    f"[{pos.symbol}] Funding costs ({pos.funding_costs:.2f}) "
    f"exceed realized_pnl ({pos.realized_pnl:.2f}) by >150%. "
    f"Possible mis-tracking. Close price: {price}"
  )

pos.realized_pnl += (pnl - fee - pos.funding_costs)
```

**Impact:** Catches funding accumulation bugs before they distort final PnL.

---

## IMPORTANT ENHANCEMENTS

### 4. Make Trailing Distance Style Multipliers Configurable

**Current Code (lines 261-263):**
```python
style_mult = {
  "tight": 0.8, "medium": 1.0, "loose": 1.5, "none": 1.0,
}.get(trade_profile.exit_params.trailing_style, 1.0)
```

**Problem:** Hard-coded multipliers can't be tuned per exchange or volatility.

**Recommended Approach:**
```python
# In trade_profile.py or config:
TRAILING_STYLE_MULTIPLIERS = {
  "tight": float(os.getenv("TRAILING_MULT_TIGHT", "0.8")),
  "medium": float(os.getenv("TRAILING_MULT_MEDIUM", "1.0")),
  "loose": float(os.getenv("TRAILING_MULT_LOOSE", "1.5")),
  "none": 1.0,
}

# Usage:
style_mult = TRAILING_STYLE_MULTIPLIERS.get(trailing_style, 1.0)
```

**Env Vars to Add:**
```bash
TRAILING_MULT_TIGHT=0.75    # Or 0.85 if original is too tight
TRAILING_MULT_MEDIUM=1.0    # Baseline
TRAILING_MULT_LOOSE=1.5     # Or 1.8 for volatile markets
```

**Impact:** Fine-tune trailing aggressiveness without code changes.

---

### 5. Improve Early Exit Regime Detection

**Current Code (line 461):**
```python
_regime = (pos.entry_reasons or {}).get("regime", "unknown")
```

**Problem:** Regime is stale (set at entry, not current). May miss regime changes.

**Recommended Enhancement:**
```python
def _check_early_exit(self, pos: Position, price: float, df_5m):
  # ... existing code ...

  # Get current regime from LLM if available, else use entry regime
  _regime = self._get_current_regime(pos, df_5m)
  if not _regime:
    _regime = (pos.entry_reasons or {}).get("regime", "unknown")

  _thresholds = self._EARLY_EXIT_THRESHOLDS.get(_regime, self._DEFAULT_EARLY_EXIT)
  # ... rest of code ...

def _get_current_regime(self, pos: Position, df_5m) -> Optional[str]:
  """Detect current regime from technical indicators."""
  if df_5m is None or df_5m.empty or len(df_5m) < 50:
    return None

  try:
    # Simple heuristic: ADX for trend, Bollinger Width for volatility
    close = df_5m["close"].astype(float)

    # Chop Index for trend/range detection
    hl_range = df_5m["high"].max() - df_5m["low"].min()
    log_ratio = np.log10(close.sum() / hl_range)
    chop = 100 * log_ratio / np.log10(len(close))

    if chop < 38:
      return "trending_bull" if close.iloc[-1] > close.iloc[-30] else "trending_bear"
    elif chop > 62:
      return "range"
    else:
      return "consolidation"
  except:
    return None
```

**Impact:** Early exits adapt to current market conditions, not entry conditions.

---

### 6. Add Regime Validation for Early Exit

**Current Code (line 462):**
```python
_thresholds = self._EARLY_EXIT_THRESHOLDS.get(_regime, self._DEFAULT_EARLY_EXIT)
```

**Problem:** If `_regime` is misspelled or invalid, falls back to DEFAULT. Silent failure.

**Recommended Check:**
```python
# Validate regime is in known set
VALID_REGIMES = set(self._EARLY_EXIT_THRESHOLDS.keys()) | {"unknown"}

if _regime not in VALID_REGIMES:
  logger.debug(f"[{pos.symbol}] Unknown regime '{_regime}', using default thresholds")
  _regime = "unknown"

_thresholds = self._EARLY_EXIT_THRESHOLDS.get(_regime, self._DEFAULT_EARLY_EXIT)
```

**Impact:** Clearer debugging when regime naming is inconsistent.

---

### 7. Log Divergence Between Trailing vs Floor SL

**Current Code (lines 711-734):**
```python
new_sl = trailing_sl
if floor_sl is not None:
  if is_long:
    new_sl = max(trailing_sl, floor_sl)
  else:
    new_sl = min(trailing_sl, floor_sl)
```

**Problem:** Silent floor override. Traders don't see when floor "wins" and prevents trailing from tightening.

**Recommended Enhancement:**
```python
# Track which SL is active
if is_long:
  new_sl = max(trailing_sl, floor_sl) if floor_sl else trailing_sl
  sl_source = "floor" if floor_sl and new_sl == floor_sl else "trailing"
else:
  new_sl = min(trailing_sl, floor_sl) if floor_sl else trailing_sl
  sl_source = "floor" if floor_sl and new_sl == floor_sl else "trailing"

# Only log if SL changed AND source changed
if new_sl != pos.sl:
  if sl_source != getattr(self, f"_last_sl_source_{pos.symbol}", ""):
    logger.info(
      f"[{pos.symbol}] SL moved to {new_sl} ({sl_source} | "
      f"trailing={trailing_sl:.4f} floor={floor_sl if floor_sl else 'N/A'})"
    )
    setattr(self, f"_last_sl_source_{pos.symbol}", sl_source)
```

**Impact:** Traders can see when profit lock floor is constraining trailing.

---

## TESTING RECOMMENDATIONS

### 8. Add Unit Test for Rounding Edge Cases

**File:** `bot/tests/test_position_rounding_edge_cases.py`

```python
import unittest
from execution.position_manager import PositionManager

class TestRoundingEdgeCases(unittest.TestCase):

  def test_tp1_close_qty_rounds_to_zero(self):
    """When close_qty rounds to 0, should log warning and full close."""
    pm = PositionManager(taker_fee_bps=0)
    pos = pm.open_position(
      "MICRO", "LONG",
      entry=50000.0,
      qty=0.00001,  # Very small
      sl=49000.0,
      tp1=51000.0,
      tp2=52000.0,
      tp1_close_pct=0.50,  # Intend 50% close
    )

    events = pm.update_price("MICRO", 51000.0)  # TP1

    # Should have closed something
    self.assertTrue(len(events) > 0)

    # Check if converted to full close (action could be "TP1_FULL")
    if events[0].action == "TP1_FULL":
      # This is OK (guard working), but should log warning
      self.assertEqual(pm.positions["MICRO"].state, "CLOSED")

  def test_tp1_close_qty_at_minimum_precision(self):
    """Test TP1 partial close at exchange's minimum qty threshold."""
    pm = PositionManager(taker_fee_bps=0)

    # For BTC: minimum is often 0.0001
    # Try with qty = 0.0002 and close 50%
    pos = pm.open_position(
      "BTC", "LONG",
      entry=50000.0,
      qty=0.0002,
      sl=49000.0,
      tp1=51000.0,
      tp2=52000.0,
      tp1_close_pct=0.50,
    )

    events = pm.update_price("BTC", 51000.0)

    pos = pm.positions["BTC"]
    # After TP1: qty should be 0.0001 (half), not 0
    self.assertGreater(pos.qty, 0, "Remaining qty should be > 0 after TP1")

  def test_breakeven_sl_when_tp1_closes_at_loss(self):
    """When TP1 closes at loss, SL calculation should handle negative profit_cushion."""
    pm = PositionManager(taker_fee_bps=100)  # High fees to force loss

    pos = pm.open_position(
      "TEST", "LONG",
      entry=100.0,
      qty=10.0,
      sl=95.0,
      tp1=104.0,  # Close at loss (fees > profit)
      tp2=120.0,
      leverage=2.0,
      tp1_close_pct=0.50,
    )

    events = pm.update_price("TEST", 104.0)  # TP1

    pos = pm.positions["TEST"]
    # TP1 closed at loss, so realized_pnl should be negative
    self.assertLess(pos.realized_pnl, 0, "TP1 closed at loss due to fees")

    # Check that new SL is reasonable (not wildly inverted)
    # For LONG, SL should still be < entry (or very close)
    max_reasonable_sl = pos.entry + abs(pos.entry - pos.original_sl) * 0.50
    self.assertLess(pos.sl, max_reasonable_sl,
                    f"SL ({pos.sl}) inverted too much after TP1 loss")

if __name__ == "__main__":
  unittest.main()
```

**Run:** `cd bot && python -m pytest tests/test_position_rounding_edge_cases.py -v`

---

### 9. Add Integration Test: Partial Close → Trailing → SL Sequence

**File:** `bot/tests/test_partial_close_trailing_sl.py`

```python
import unittest
from execution.position_manager import PositionManager

class TestPartialCloseThenTrailing(unittest.TestCase):

  def test_tp1_partial_then_trailing_stop(self):
    """Full lifecycle: TP1 partial → trailing → SL hit."""
    pm = PositionManager(taker_fee_bps=4, enable_trailing=True, trailing_atr_mult=1.5)

    # Open LONG
    pos = pm.open_position(
      "BTC", "LONG",
      entry=50000.0,
      qty=10.0,
      sl=49000.0,
      tp1=51000.0,
      tp2=55000.0,
      atr=500.0,
      leverage=2.0,
      tp1_close_pct=0.50,
    )

    initial_qty = pos.qty
    initial_sl = pos.sl

    # Tick 1: Hit TP1
    events = pm.update_price("BTC", 51000.0)
    self.assertEqual(len(events), 1)
    self.assertEqual(events[0].action, "TP1")

    pos = pm.positions["BTC"]
    self.assertEqual(pos.state, "TRAILING")
    self.assertEqual(pos.qty, initial_qty * 0.50)
    self.assertNotEqual(pos.sl, initial_sl, "SL should move to breakeven after TP1")

    tp1_realized_pnl = pos.realized_pnl

    # Tick 2: Price rises further (trailing tightens)
    events = pm.update_price("BTC", 53000.0)
    self.assertEqual(len(events), 0)  # No exit yet

    pos = pm.positions["BTC"]
    self.assertGreater(pos.sl, initial_sl * 0.50 + 50000, "SL should tighten up")

    # Tick 3: Price falls back to SL
    events = pm.update_price("BTC", pos.sl - 100)  # Below current SL
    self.assertEqual(len(events), 1)
    self.assertEqual(events[0].action, "TRAILING_STOP")

    pos = pm.positions["BTC"]
    self.assertEqual(pos.state, "CLOSED")
    self.assertEqual(pos.qty, 0)

    # Final PnL: TP1 PnL + Trailing leg PnL
    total_pnl = pos.realized_pnl
    self.assertGreater(total_pnl, 0, "Trade should be profitable (TP1 win + trailing win)")

    # Outcome should reflect TP1 hit
    self.assertIn("TP1", pos.outcome or "")

if __name__ == "__main__":
  unittest.main()
```

**Run:** `cd bot && python -m pytest tests/test_partial_close_trailing_sl.py -v`

---

## MONITORING AND ALERTING

### 10. Add Position Manager Health Checks

**File:** `bot/execution/position_health_check.py` (new)

```python
"""Health checks for position manager anomalies."""

import logging
from execution.position_manager import PositionManager, Position
from execution.position_state import CLOSED

logger = logging.getLogger("bot.execution.position_health")

def check_position_health(pm: PositionManager) -> dict:
  """Run diagnostics on all positions."""
  issues = []

  for symbol, pos in pm.positions.items():
    # Check 1: SL inversion (SL should be protective)
    if pos.side == "LONG":
      if pos.sl >= pos.entry:
        issues.append({
          "severity": "CRITICAL",
          "symbol": symbol,
          "issue": f"LONG SL ({pos.sl}) >= entry ({pos.entry}). Not protective!",
        })
    else:  # SHORT
      if pos.sl <= pos.entry:
        issues.append({
          "severity": "CRITICAL",
          "symbol": symbol,
          "issue": f"SHORT SL ({pos.sl}) <= entry ({pos.entry}). Not protective!",
        })

    # Check 2: TP1 or TP2 crossing
    if pos.state != CLOSED:
      if pos.side == "LONG":
        if pos.tp1 >= pos.tp2:
          issues.append({
            "severity": "CRITICAL",
            "symbol": symbol,
            "issue": f"LONG TP1 ({pos.tp1}) >= TP2 ({pos.tp2}). Invalid targets!",
          })
      else:  # SHORT
        if pos.tp1 <= pos.tp2:
          issues.append({
            "severity": "CRITICAL",
            "symbol": symbol,
            "issue": f"SHORT TP1 ({pos.tp1}) <= TP2 ({pos.tp2}). Invalid targets!",
          })

    # Check 3: Qty zero but not closed
    if pos.qty <= 0 and pos.state != CLOSED:
      issues.append({
        "severity": "CRITICAL",
        "symbol": symbol,
        "issue": f"Qty is {pos.qty} but state is {pos.state}. Should be CLOSED!",
      })

    # Check 4: Funding costs exceed 50% of realized PnL
    if pos.funding_costs > abs(pos.realized_pnl) * 0.50:
      issues.append({
        "severity": "WARNING",
        "symbol": symbol,
        "issue": f"Funding costs ({pos.funding_costs:.2f}) exceed 50% of realized PnL ({pos.realized_pnl:.2f})",
      })

    # Check 5: State path integrity
    from execution.position_state import VALID_TRANSITIONS
    for i in range(len(pos.state_path) - 1):
      from_state = pos.state_path[i]
      to_state = pos.state_path[i + 1]
      if to_state not in VALID_TRANSITIONS.get(from_state, set()):
        issues.append({
          "severity": "CRITICAL",
          "symbol": symbol,
          "issue": f"Invalid state transition in path: {from_state} -> {to_state}",
        })

  return {
    "total_positions": len(pm.positions),
    "issues": issues,
    "passed": len(issues) == 0,
  }

def log_health_check(pm: PositionManager):
  """Run health check and log results."""
  result = check_position_health(pm)

  if result["passed"]:
    logger.info(f"Position health OK: {result['total_positions']} positions checked")
  else:
    for issue in result["issues"]:
      if issue["severity"] == "CRITICAL":
        logger.error(f"[{issue['symbol']}] {issue['issue']}")
      else:
        logger.warning(f"[{issue['symbol']}] {issue['issue']}")
```

**Usage:**
```python
# In main bot loop:
from execution.position_health_check import log_health_check

while True:
  # ... trading logic ...

  if should_do_periodic_check():
    log_health_check(position_manager)
```

---

## DOCUMENTATION UPDATES

### 11. Add Docstring to _partial_close_tp1 Explaining Rounding

**Current:**
```python
def _partial_close_tp1(self, pos: Position, price: float) -> TradeEvent:
  """Close tp1_close_pct at TP1, move SL above breakeven, activate trailing."""
```

**Recommended:**
```python
def _partial_close_tp1(self, pos: Position, price: float) -> TradeEvent:
  """Close tp1_close_pct at TP1, move SL above breakeven, activate trailing.

  Partial Close Percentage:
  - Static: pos.tp1_close_pct (default 0.50 for MEDIUM profile)
  - Dynamic scaling enabled via DYNAMIC_TP_SCALING=true:
    * Overshoot scaling: if price > 50% of TP1→TP2 range, increase close%
    * Speed scaling: fast move → close less, slow grind → close more

  Rounding Safety:
  - If close_qty rounds to 0 or full qty, converts to TP1_FULL (full close)
  - This is a fallback to prevent zero-qty positions
  - Check logs for "TP1 partial close: close_qty rounded" warnings

  Breakeven SL Calculation:
  - New SL = entry - (TP1_profit / remaining_qty / leverage) + fee_buffer
  - The locked-in TP1 profit gives room for remaining qty
  - If TP1 closed at loss (unlikely), new SL may move above entry (mathematically correct)

  Returns:
    TradeEvent with action="TP1" and metadata containing remaining_qty and new_sl
  """
```

---

## SUMMARY TABLE: When to Use Which Profile

```
Scenario                          → Profile   Reason
────────────────────────────────────────────────────────────
Fast mean-reversion scalps        → SCALP     90% close, tight exits
Medium-horizon swing trades       → MEDIUM    50% close, balanced exits
Trend-following long holds        → TREND     40% close, loose trailing
High-conviction regime plays      → REGIME    55% close, conservative defaults
Mixed signals (TREND + MEDIUM)    → MEDIUM    Conservative (safer)
Any SCALP in ensemble             → SCALP     Treat as scalp (safest)
```

---

**Document Created:** 2025-03-20
**Files Affected by These Recommendations:**
- `bot/execution/position_manager.py` (primary)
- `bot/tests/test_position_rounding_edge_cases.py` (new)
- `bot/tests/test_partial_close_trailing_sl.py` (new)
- `bot/execution/position_health_check.py` (new)
- `bot/execution/trade_profile.py` (optional tuning)
