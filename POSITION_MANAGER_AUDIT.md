# Position Manager Audit Report
**Audit Date:** 2025-03-20
**Focus:** State machine, TP1 logic, trailing stops, PnL calculations, edge cases

---

## 1. STATE MACHINE ARCHITECTURE

### State Definitions
```
States: IDLE, OPEN, TP1_HIT, TRAILING, CLOSED

State Path Tracking: [IDLE] -> [OPEN] -> [TP1_HIT, TRAILING, or CLOSED]
```

### Valid Transitions (from position_state.py)
```
IDLE     -> OPEN
OPEN     -> {TP1_HIT, CLOSED}        # TP1 hit OR SL/EARLY_EXIT
TP1_HIT  -> {TRAILING, CLOSED}       # Activate trailing OR direct close (edge case)
TRAILING -> CLOSED                   # Only terminal state
CLOSED   -> (terminal state)         # No outgoing transitions
```

### Transition Validation
- **File:** `bot/execution/position_state.py:51-88`
- **Mechanism:** `is_valid_transition(from_state, to_state)` checks against `VALID_TRANSITIONS` dict
- **Logging:** All transitions logged to `data/logs/state_transitions.csv` with timestamp, symbol, old/new state, reason
- **Error Handling:** Invalid transitions log warning and REJECT (return current state, don't advance)
- **Properties for State Checking:**
  - `Position.filled_tp1`: True if `TP1_HIT` in state_path
  - `Position.trailing_active`: True if state == TRAILING
  - `Position.state_path_str`: Human-readable path like "IDLE->OPEN->TP1_HIT->TRAILING->CLOSED"

### State Machine Diagram (Text Format)
```
    ┌─────────────────────────────────────────────────┐
    │          POSITION LIFECYCLE                     │
    │                                                 │
    │   IDLE                                          │
    │    │                                            │
    │    │ open_position()                            │
    │    ↓                                            │
    │   OPEN ◄─────────────────────────────────────┐ │
    │    │                                         │ │
    │    ├─ SL hit ───────┐                        │ │
    │    │                ├──→ CLOSED              │ │
    │    ├─ EARLY_EXIT ──┤    (SL action)         │ │
    │    │                ├──→ CLOSED              │ │
    │    ├─ TIME_STOP ───┤    (EARLY_EXIT action) │ │
    │    │                └──→ CLOSED              │ │
    │    │                    (TIME_STOP action)   │ │
    │    │                                         │ │
    │    ├─ TP1 hit (dynamic partial close)       │ │
    │    └─→ TP1_HIT                              │ │
    │        │                                    │ │
    │        │ _partial_close_tp1()               │ │
    │        │  • Close tp1_close_pct of qty     │ │
    │        │  • Lock in TP1 PnL                │ │
    │        │  • Move SL to breakeven+          │ │
    │        │  • Set peak_price = current_price │ │
    │        │                                    │ │
    │        └─→ TRAILING                         │ │
    │            │                                │ │
    │            ├─ SL hit ────┐                  │ │
    │            │              ├──→ CLOSED       │ │
    │            ├─ TP2 hit ───┤    (TRAILING_STOP)
    │            │              │                 │ │
    │            └─ Trailing tightens             │ │
    │               _update_trailing_stop()       │ │
    │                                             │ │
    │                         CLOSED ────────────┘ │
    │                         (terminal)           │
    └─────────────────────────────────────────────────┘

    Note: CLOSED is reachable from OPEN, TP1_HIT, or TRAILING
    Exit actions: SL, TP2, TRAILING_STOP, EARLY_EXIT, TIME_STOP, EMERGENCY, HOLD_LIMIT
```

---

## 2. TP1 PARTIAL CLOSE LOGIC

### TP1 Close Percentage Calculation (`_partial_close_tp1`, lines 506-646)

#### Static Component
```python
tp1_close_pct: float = 0.5  # Default MEDIUM profile
# Per entry_type:
#   SCALP:  0.90 (close 90%, let 10% trail to TP2)
#   MEDIUM: 0.50 (close 50%, keep 50% for trailing)
#   TREND:  0.40 (close 40%, keep 60% for trends)
#   REGIME: 0.55 (close 55%)
```

#### Dynamic Scaling (if `DYNAMIC_TP_SCALING=true`)

**1. Overshoot Scaling** (lines 514-523)
```
When price overshoots TP1 toward TP2:
  tp_range = abs(tp2 - tp1)
  if tp_range > 0:
    overshoot = (price - tp1) / tp_range  [LONG]
                (tp1 - price) / tp_range  [SHORT]

    if overshoot > 0.5 (price moved >50% from TP1 to TP2):
      dynamic_close_pct = min(close_pct * 1.20, 0.90)
      # Increase close% to lock in more profit
```

**2. Move Speed Scaling** (lines 525-535)
```
time_to_tp1_s = (now - open_time).total_seconds()

if time_to_tp1_s > 60s (avoid test artifacts):
  if time_to_tp1_s < 1800s (< 30 min):
    dynamic_close_pct *= 0.85  # Fast runner, let it run (close LESS)

  elif time_to_tp1_s > 14400s (> 4 hours):
    # Slow grind — normally close more
    regime = entry_reasons.get("regime")
    if regime NOT in ("trending_bull", "trending_bear", "trend"):
      dynamic_close_pct = min(close_pct * 1.10, 0.85)
      # Close up to 10% more (but cap at 85%)
```

**Net Effect:**
- Fast moves to TP1: close 42-50% (let winners run)
- Slow grinds in range/range-like: close 55-60% (take profits, reduce bleed)
- Overshoots toward TP2: close up to 90% (momentum trade)

#### Rounding Guard (lines 543-551)
```python
close_qty = round_qty(symbol, pos.qty * dynamic_close_pct)
remaining_after = round_qty(symbol, pos.qty - close_qty)

# CRITICAL GUARD: If rounding ate all remaining qty:
if remaining_after <= 0 and pos.qty > close_qty:
  close_qty = round_qty(symbol, pos.qty * 0.90)  # Reduce to 90% max

# Degenerate case: if close_qty <= 0 or >= full qty:
if close_qty <= 0 or close_qty >= pos.qty:
  return self._close_position(pos, price, "TP1_FULL")  # Close entire position
```

**Purpose:** Prevents leaving zero qty positions hanging or closing the entire position when only partial was intended.

---

## 3. BREAKEVEN SL CALCULATION (After TP1)

### Lines 567-588: Profit Cushion Formula

**Goal:** After closing TP1 portion, remaining position gets "free room" from the locked-in profit.

#### LONG Position (lines 574-579)
```python
remaining_qty = pos.qty
profit_cushion = pos.realized_pnl / (remaining_qty * pos.leverage)

# Entry - cushion = adjusted breakeven (LOWER = more room downside)
be_price = pos.entry - profit_cushion + fee_buffer
pos.sl = round_price(symbol, be_price)

fee_buffer = entry * (taker_fee_bps * 2 / 10000.0 + 0.001)
```

**Example:**
```
Entry: 100, Qty: 10, Leverage: 2x, TP1_close: 50%
Closed at TP1: 105
TP1 PnL (before fees): (105-100)*5*2 = 50
TP1 fees: ~0.01 (negligible)
Realized PnL: ~50

remaining_qty: 5
profit_cushion: 50 / (5 * 2) = 5.0

be_price: 100 - 5.0 + 0.01 = 95.01
New SL: 95.01 (3% below entry, protected by TP1 profit)
```

#### SHORT Position (lines 580-582)
```python
be_price = pos.entry + profit_cushion - fee_buffer
pos.sl = round_price(symbol, be_price)
```

**Critical Property:** SL can move BELOW entry (LONG) or ABOVE entry (SHORT) as long as the locked-in TP1 profit is sufficient to cover it.

### Fee Buffer Component
```python
fee_buffer = entry * (taker_fee_bps * 2 / 10000.0 + 0.001)
             = entry * 0.001  [for 4 bps fee]

# 0.1% margin to cover:
# - Exit fee on remaining qty
# - Slippage/rounding errors
```

---

## 4. TRAILING STOP MECHANICS

### Activation
- Triggered when TP1 is hit and position transitions to TRAILING state
- Called every tick via `_update_trailing_stop(pos, current_price)` (line 412)

### Progressive Tightening Curve (lines 648-735)

#### Step 1: Measure Progress from Entry to TP2
```python
is_long = pos.side == "LONG"

if is_long:
  total_range = tp2 - entry
  peak_move = peak_price - entry
else:
  total_range = entry - tp2
  peak_move = entry - peak_price

progress = min(peak_move / total_range, 1.0)  # 0.0 to 1.0
```

**Example (LONG):**
```
Entry: 100, TP2: 120, Current Peak: 110
total_range: 120-100 = 20
peak_move: 110-100 = 10
progress: 10/20 = 0.50 (50% of way from entry to TP2)
```

#### Step 2: Tighten Factor Curve (lines 674-680)
```python
ep = trade_profile.exit_params if profile else MEDIUM defaults

tighten_start = ep.trailing_tighten_start  # e.g., 0.67 for MEDIUM
tighten_end   = ep.trailing_tighten_end    # e.g., 0.45 for MEDIUM
tighten_range = tighten_start - tighten_end  # 0.22

tighten_factor = max(tighten_start - progress * tighten_range, tighten_end)
                = max(0.67 - 0.50*0.22, 0.45)
                = max(0.56, 0.45)
                = 0.56

effective_distance = trailing_distance * tighten_factor
                   = 1.5*ATR * 0.56
```

**Tighten Curves by Profile:**
```
SCALP:  0.80 → 0.60 (tightens 20 percentage points)
MEDIUM: 0.67 → 0.45 (tightens 22 percentage points)
TREND:  0.55 → 0.45 (tightens 10 percentage points — trends need room)
```

**Effect:** As price moves from entry toward TP2, trailing distance shrinks:
- At entry (progress=0%): tighten_factor is highest (wide trailing)
- At TP2 (progress=100%): tighten_factor is lowest (tight trailing)

#### Step 3: Calculate Trailing SL
```python
if is_long:
  trailing_sl = peak_price - effective_distance
else:
  trailing_sl = peak_price + effective_distance
```

#### Step 4: Profit Lock Floor (lines 687-710)
```python
floor_start    = ep.floor_progress_start    # e.g., 0.35 for MEDIUM
floor_lock_start = ep.floor_lock_start      # e.g., 0.25 for MEDIUM
floor_lock_max = ep.floor_lock_max          # e.g., 0.60 for MEDIUM

floor_sl = None
if progress > floor_start and peak_move > 0:
  lock_pct = min(
    floor_lock_start + (progress - floor_start) * 0.5,
    floor_lock_max
  )

  if is_long:
    floor_sl = entry + peak_move * lock_pct
```

**Example (LONG):**
```
Entry: 100, Peak: 115, Entry: 100
peak_move: 15
progress: 0.50 (50% of way to TP2)

floor_start: 0.35 (only activates after 35% progress)
At progress=50%:
  lock_pct = min(0.25 + (0.50-0.35)*0.5, 0.60)
           = min(0.325, 0.60) = 0.325

  floor_sl = 100 + 15*0.325 = 104.875

# Floor locks in 32.5% of the $15 peak move as profit
# Even if price falls to $104.88, we exit profitably
```

**Floor Timeline:**
```
progress  lock_pct  example_floor (entry=100, peak_move=15)
--------  --------  ---------
  0%      0%        100 (no floor yet)
 35%      0%        100 (threshold)
 50%      3.25%     104.88
 60%      4.75%     105.71
 80%      6%        106.9
100%      6%+       106.9 (max out at 60% of peak_move)
```

#### Step 5: Take the Tighter of Trailing vs Floor
```python
new_sl = trailing_sl
if floor_sl is not None:
  if is_long:
    new_sl = max(trailing_sl, floor_sl)  # LONG: higher SL is tighter
  else:
    new_sl = min(trailing_sl, floor_sl)  # SHORT: lower SL is tighter

new_sl = round_price(symbol, new_sl)
```

#### Step 6: Only Move SL in Protective Direction
```python
# LONG: SL can only move UP (tighten)
if is_long and new_sl > pos.sl:
  pos.sl = new_sl
  logger.info(f"Trail SL: {old_sl} -> {new_sl}")

# SHORT: SL can only move DOWN (tighten)
elif not is_long and new_sl < pos.sl:
  pos.sl = new_sl
  logger.info(f"Trail SL: {old_sl} -> {new_sl}")
```

### Trailing Distance Initialization (lines 254-268)
```python
trailing_distance = atr * trailing_atr_mult * style_mult

where:
  ATR = volatility measure at entry
  trailing_atr_mult = 1.5 (configurable)
  style_mult = {
    "tight": 0.8   (SCALP)
    "medium": 1.0  (MEDIUM)
    "loose": 1.5   (TREND)
  }

Fallback (if ATR=0):
  style_fallback_pct = {"tight": 0.006, "medium": 0.01, "loose": 0.015}
  trailing_distance = entry * pct
```

**Examples:**
```
Entry: 100, ATR: 2, mult: 1.5
  SCALP:   trailing_distance = 2*1.5*0.8 = 2.4
  MEDIUM:  trailing_distance = 2*1.5*1.0 = 3.0
  TREND:   trailing_distance = 2*1.5*1.5 = 4.5
```

---

## 5. FEE AND FUNDING COST DEDUCTIONS

### Entry Fee (line 296-297)
```python
fee = self._fee(entry, qty)
    = entry * qty * (taker_fee_bps / 10000.0)
pos.fees_paid += fee
```

### TP1 Partial Close Fee (line 552-553)
```python
fee = self._fee(price, close_qty)  # Fee on portion being closed
pos.fees_paid += fee

# PnL deduction (line 563):
pos.realized_pnl += (pnl - fee - funding_share)
```

### TP1 Partial Funding Cost Allocation (line 562-564)
```python
# Proportionally allocate funding to closed portion
funding_share = pos.funding_costs * (close_qty / pos.qty) if pos.qty > 0 else 0.0
pos.realized_pnl += -funding_share  # Deduct from current PnL
pos.funding_costs -= funding_share  # Reduce remaining balance for final close
```

**Purpose:** Prevents dumping all funding costs onto final close leg, distorting per-leg PnL.

### Final Close Fee (line 761-762)
```python
fee = self._fee(price, qty)  # Fee on remaining qty
pos.fees_paid += fee
```

### Final Close PnL with Funding (line 770)
```python
pos.realized_pnl += (pnl - fee - pos.funding_costs)
#                        ↑         ↑
#                      exit fee   all remaining funding
```

### Funding Cost Accrual (lines 191-215)
```python
# Called each tick during position hold
def accrue_funding(symbol, funding_rate, interval_hours=8):
  if symbol not in positions:
    return

  pos = positions[symbol]
  if pos.state == CLOSED or pos.qty <= 0:
    return

  # Funding cost = rate * notional * (time_elapsed / interval)
  scan_interval_s = 30.0  # Typical tick duration
  fraction_of_interval = scan_interval_s / (interval_hours * 3600)

  notional = pos.entry * pos.qty * pos.leverage
  cost = abs(funding_rate) * notional * fraction_of_interval

  pos.funding_costs += cost
```

**Example:**
```
Notional: $100k, funding_rate: 0.0001 (0.01% per 8h), tick: 30s
cost = 0.0001 * 100000 * (30 / 28800)
     = 10 * 0.00104
     = 0.0104 per tick
     ≈ $0.01 per 30-second scan

After 8 hours (960 ticks):
  Total funding = 0.01 * 960 = $9.6
```

---

## 6. EARLY EXIT TRIGGER LOGIC

### Overview
- **When:** OPEN state only (after TP1, breakeven SL protects us)
- **Trigger:** `_check_early_exit(pos, price, df_5m)` (lines 436-504)
- **Condition:** Momentum reversing hard toward SL

### Regime-Adaptive Thresholds (lines 422-434)
```python
_EARLY_EXIT_THRESHOLDS = {
    "high_volatility": {"sl_progress": 0.40, "conditions": 1},
    "panic":           {"sl_progress": 0.35, "conditions": 1},
    "range":           {"sl_progress": 0.45, "conditions": 2},
    "consolidation":   {"sl_progress": 0.50, "conditions": 2},
    "trending_bull":   {"sl_progress": 0.70, "conditions": 3},
    "trending_bear":   {"sl_progress": 0.70, "conditions": 3},
    "trend":           {"sl_progress": 0.70, "conditions": 3},
}
_DEFAULT_EARLY_EXIT = {"sl_progress": 0.65, "conditions": 3}
```

**Interpretation:**
- High-vol/panic: cut losers when 35-40% of way to SL if momentum is against us
- Range-bound: cut when 45-50% of way to SL with 2 confirmation conditions
- Trending: let trades breathe (70% of way to SL, require 3 conditions)

### SL Progress Calculation (lines 447-454)
```python
stop_dist = abs(entry - original_sl)
if stop_dist == 0:
  return False  # No SL, no early exit

if is_long:
  sl_progress = (entry - price) / stop_dist
else:
  sl_progress = (price - entry) / stop_dist
```

**Example (LONG):**
```
Entry: 100, SL: 95, Current: 98
stop_dist: 5
sl_progress: (100-98) / 5 = 0.40 (40% of way to SL)
```

### Momentum Confirmation Conditions (lines 469-492)

**Condition 1: Three Candles Accelerating Against Position** (lines 475-481)
```python
c = df_5m["close"].astype(float)
last3 = c.iloc[-3:].values

if is_long:
  accelerating = last3[2] < last3[1] < last3[0]
  # Most recent candle is lowest (downward acceleration)
else:
  accelerating = last3[2] > last3[1] > last3[0]
  # Most recent candle is highest (upward acceleration)
```

**Condition 2: EMA5 Crossed Against Position** (lines 483-488)
```python
ema5 = c.ewm(span=5, adjust=False).mean().iloc[-1]
ema13 = c.ewm(span=13, adjust=False).mean().iloc[-1]

if is_long:
  ema_cross = ema5 < ema13  # Short-term below long-term (bearish)
else:
  ema_cross = ema5 > ema13  # Short-term above long-term (bullish)
```

**Condition 3: SL Progress Extreme** (lines 490-492)
```python
if sl_progress >= 0.80:  # Already 80% of way to SL
  _conditions_met += 1
```

### Exit Decision (lines 494-498)
```python
if _conditions_met >= _min_conditions:
  logger.info(f"EARLY EXIT ({regime}): {sl_progress:.0%} toward SL, "
              f"{_conditions_met}/{_min_conditions} conditions met")
  return True
```

---

## 7. OUTCOME CLASSIFICATION

### Function: `_classify_outcome(pos, action)` (lines 736-756)

```python
def _classify_outcome(self, pos: Position, action: str) -> str:
  tp1_was_hit = TP1_HIT in pos.state_path
  win = pos.realized_pnl > 0

  if action == "TP2":
    return "CLEAN_WIN"

  elif action == "EARLY_EXIT":
    return "EARLY_EXIT_SAVE" if pos.realized_pnl > -(risk_amount*0.25) else "EARLY_EXIT_FAIL"

  elif action == "TRAILING_STOP":
    return "TRAILING_WIN" if win else "TRAILING_FAIL"

  elif action in ("ROTATE_PROFIT", "ROTATE_LOSS_AVOIDANCE"):
    return "ROTATION_WIN" if win else "ROTATION_LOSS_AVOIDANCE"

  elif action == "SL":
    if tp1_was_hit:
      return "TP1_THEN_SL"
    return "CLEAN_LOSS"

  elif tp1_was_hit and not win:
    return "TP1_ONLY"

  else:
    return "CLEAN_LOSS" if not win else "CLEAN_WIN"
```

### Outcome Types
| Outcome | Trigger | State Path | Meaning |
|---------|---------|-----------|---------|
| CLEAN_WIN | TP2 hit | IDLE→OPEN→(TP1_HIT)?→TRAILING→CLOSED | Reached TP2, max profit |
| CLEAN_LOSS | SL hit (no TP1) | IDLE→OPEN→CLOSED | Hit stop before any profit |
| TP1_THEN_SL | SL hit (after TP1) | IDLE→OPEN→TP1_HIT→TRAILING→CLOSED | Partial profit taken, rest lost |
| TP1_ONLY | Closed (not TP2, TP1 was hit) | IDLE→OPEN→TP1_HIT→TRAILING→CLOSED | Closed trailing, banked TP1 |
| TRAILING_WIN | Trailing stop (win) | IDLE→OPEN→TP1_HIT→TRAILING→CLOSED | Trailing stop triggered profitably |
| TRAILING_FAIL | Trailing stop (loss) | IDLE→OPEN→TP1_HIT→TRAILING→CLOSED | Trailing stop triggered at loss |
| EARLY_EXIT_SAVE | Early exit, limited loss | IDLE→OPEN→CLOSED | Cut loser early, saved capital |
| EARLY_EXIT_FAIL | Early exit, still lost | IDLE→OPEN→CLOSED | Cut early, still took loss |
| ROTATION_WIN | Rotation (profit) | IDLE→OPEN→CLOSED | Rotated out at profit |
| TIME_STOP | 8h elapsed (no TP1) | IDLE→OPEN→CLOSED | Bleed-out exit |

---

## 8. EXIT TYPES AND SCENARIOS

### Complete Exit Event Matrix

```
State       Action           Trigger                  Outcome Type        Remaining Qty
────────────────────────────────────────────────────────────────────────────────────────
OPEN        SL               Price hits SL            CLEAN_LOSS          0 (full close)
OPEN        EARLY_EXIT       Momentum accelerates     EARLY_EXIT_SAVE/FAIL 0 (full close)
OPEN        TIME_STOP        8h elapsed no TP1        (uses CLEAN_LOSS)    0 (full close)
OPEN        TP1              Price hits TP1           (state → TP1_HIT)    pos.qty*(1-tp1_close_pct)

TP1_HIT     TRAILING         On TP1 trigger           -                    (from TP1 partial close)
TP1_HIT     CLOSED           Direct close (rare)      TP1_ONLY             0 (full close)

TRAILING    TRAILING_STOP    SL hit after TP1         TRAILING_WIN/FAIL    0 (full close)
TRAILING    TP2              Price hits TP2           CLEAN_WIN            0 (full close)

Any State   SL               Price flash crash        (action-specific)    0 (full close)
Any State   EMERGENCY        Circuit breaker / manual (depends on action)   0 (full close)
Any State   HOLD_LIMIT       12h or more held         CLEAN_LOSS-like      0 (force close)
Any State   CIRCUIT_BREAKER  Daily loss limit reached (depends on action)   0 (force close)
```

### Exit Order of Precedence (in `update_price`, lines 369-419)
```
1. Check SL FIRST (line 371-376)
   → If hit, CLOSE immediately, return
   → Prevents worse-price exits from early exit or momentum logic

2. Time Stop (line 382-392)
   → Only in OPEN state
   → Close if 8h+ without hitting TP1

3. Early Exit (line 396-401)
   → Only in OPEN state
   → Momentum-based cut

4. TP1 Check (line 404-408)
   → Only in OPEN state
   → Dynamic partial close

5. Update Trailing (line 411-412)
   → Only in TRAILING state
   → Tighten SL, but DON'T close (that's done in step 1 on next tick)

6. TP2 Check (line 415-418)
   → Any state except CLOSED
   → Full close at target
```

---

## 9. RACE CONDITIONS AND SEQUENTIAL GUARANTEES

### Potential Race Condition: TP1 → Trailing → SL in Same Tick

**Scenario:** Price jumps from below TP1 to above TP2 in single tick
```
Previous: OPEN state, price = 104 (below TP1=105)
Update:   price = 106 (above both TP1 and TP2)

Execution order:
1. TP1 check (line 404): tp1_hit = True
   → _partial_close_tp1() executed
   → qty reduced, state → TRAILING, returned event

2. TP1 check (line 404): Now state == TRAILING, so NOT re-checked
3. Update trailing (line 411): _update_trailing_stop() called
4. TP2 check (line 415): tp2_hit = True, state != CLOSED
   → _close_position() executed, state → CLOSED
   → Returns TP2 event
```

**Events returned:** [TP1_event, TP2_event]
**Final state:** CLOSED
**No race condition:** Code checks `if pos.state == OPEN` before TP1, preventing double-closes.

### Guaranteed Sequential Processing
- **Within single `update_price()` call:** SL checked first, then early exit, then TP1, then trailing update, then TP2
- **Across multiple calls:** Position state prevents re-entering same transition path
- **Thread safety:** Position dict access is single-threaded (typical bot architecture), no mutex needed

### Potential Issue: TP1 Partial Close with Zero Remaining

**Scenario:** Rounding causes close_qty == original qty
```python
qty = 0.0001 BTC
tp1_close_pct = 0.50
close_qty = round_qty(BTC, 0.0001 * 0.50) = 0.00005

# If rounding rules say 0.00005 < min_qty:
close_qty = 0  # Rounds to zero!
remaining = 0.0001 - 0 = 0.0001  # OK

# But if close_qty = 0 and qty > 0:
if close_qty <= 0:
  return self._close_position(pos, price, "TP1_FULL")  # Full close!
```

**Guard in place:** Lines 549-551
```python
if close_qty <= 0 or close_qty >= pos.qty:
  return self._close_position(pos, price, "TP1_FULL")
```

**Risk:** Silently converts intended partial close to full close. No warning logged.

---

## 10. PARTIAL CLOSE FOLLOWED BY SL

### Scenario: Close TP1, then SL hits remaining qty

**Timeline:**
```
Tick 1: Price = 105 (TP1)
  → _partial_close_tp1(): close 50% of qty
  → pos.qty = 50% of original
  → pos.sl = breakeven+
  → state = TRAILING

Tick 2: Price = 94 (hits breakeven SL)
  → SL check: current_price <= pos.sl = True
  → _close_position(): close remaining qty at 94
  → action = "TRAILING_STOP" (because state == TRAILING)
  → pnl = (94 - entry) * remaining_qty * leverage - fee - remaining_funding
  → outcome = "TRAILING_WIN" if pnl > 0 else "TRAILING_FAIL"
```

**Key:** Outcome class is `TRAILING_FAIL`, not `CLEAN_LOSS`, because TP1 was hit and we're in TRAILING state.

**PnL Calculation:**
```
Total PnL = TP1_PnL + Trailing_PnL - total_fees - total_funding

Where:
  TP1_PnL = realized_pnl accumulated during partial close
  Trailing_PnL = (94 - entry) * remaining_qty * leverage
  total_fees = entry_fee + tp1_fee + trailing_fee
  total_funding = accrued during entire hold
```

---

## 11. TRADE PROFILE BEHAVIOR MATRIX

### Entry Types and Their Profiles

| Aspect | SCALP | MEDIUM | TREND | REGIME |
|--------|-------|--------|-------|--------|
| **Strategy Sources** | (future) | multi_tier, monte_carlo, confidence_scorer | regime_trend | (regime modifier) |
| **TP1 Distance** | 0.5 ATR | 1.0 ATR | 1.2 ATR | 1.2 ATR |
| **TP2 Distance** | 1.0 ATR | 2.0 ATR | 2.5 ATR | 2.5 ATR |
| **SL Distance** | 0.4 ATR | 0.55 ATR | 0.60 ATR | 0.55 ATR |
| **TP1 Close %** | 90% | 50% | 40% | 55% |
| **Trailing Style** | tight | medium | loose | medium |
| **Trail Start** | 0.80 | 0.67 | 0.55 | 0.60 |
| **Trail End** | 0.60 | 0.45 | 0.45 | 0.45 |
| **Floor Progress** | 20% | 35% | 30% | 30% |
| **Floor Lock Min** | 40% | 25% | 30% | 30% |
| **Floor Lock Max** | 75% | 60% | 60% | 60% |
| **Max Hold Hours** | 4h | 12h | 36h | 48h |
| **Expected Behavior** | fast scalps, tight exits | balanced medium-term | let winners run, loose trails | regime plays, conservative |

### Profile Assignment Logic (`trade_profile.py:219-240`)
```python
def _determine_entry_type(primary_driver, strategies_agree):
  primary_type = STRATEGY_ENTRY_TYPE.get(primary_driver, MEDIUM)
  types = [STRATEGY_ENTRY_TYPE.get(s, MEDIUM) for s in strategies_agree]
  unique_types = set(types)

  # Unanimous: use that type
  if len(unique_types) == 1:
    return unique_types.pop()

  # Mixed: be conservative
  if SCALP in unique_types:
    return SCALP  # Any SCALP signal → SCALP treatment

  if TREND in unique_types and MEDIUM in unique_types:
    return primary_type  # Use primary driver's type (not unanimous)

  return primary_type
```

**Behavior:**
- If all strategies agree (e.g., all MEDIUM): use that entry_type
- If mixed TREND + MEDIUM: default to MEDIUM unless primary is TREND
- If ANY signal is SCALP: force SCALP (most conservative)

---

## 12. CALCULATION ERRORS AND ROUNDING EDGE CASES

### Critical Rounding Issues

#### Issue 1: Remainder Preservation in TP1 Partial Close (lines 543-551)
```python
close_qty = round_qty(symbol, pos.qty * dynamic_close_pct)
remaining_after = round_qty(symbol, pos.qty - close_qty)

# GUARD: if remainder rounds to 0:
if remaining_after <= 0 and pos.qty > close_qty:
  close_qty = round_qty(symbol, pos.qty * 0.90)
```

**Problem:** If rounding results in zero remaining qty, the guard reduces close_qty to 90%.
- Silently changes user's intended close percentage
- Could result in partial close of 90% instead of intended 50%
- No warning logged to user

**Impact:** Low (guards prevent larger issue of zero-qty positions)

#### Issue 2: Floating Point Precision in Trailing Update (line 718)
```python
new_sl = round_price(symbol, new_sl)
```

**Problem:** If round_price() uses banker's rounding or has precision limits:
- Example: 99.99999999 rounds to 100.00000
- Tighten curves might over/under-tighten by 1 tick

**Mitigation:** `round_price()` function handles exchange-specific precision

#### Issue 3: Division by Zero in Early Exit (line 447-448)
```python
stop_dist = abs(pos.entry - pos.original_sl)
if stop_dist == 0:
  return False  # Early exit disabled if SL == entry
```

**Problem:** If SL equals entry price (degenerate setup):
- Early exit check short-circuits
- But SL hit logic (line 371) will still trigger

**Risk:** Low (entry == SL is invalid signal)

#### Issue 4: Funding Cost Allocation in Partial Close (line 562)
```python
funding_share = pos.funding_costs * (close_qty / pos.qty) if pos.qty > 0 else 0.0
```

**Problem:** If pos.qty becomes zero before this line:
- Division by zero avoided (guard `if pos.qty > 0`)
- But pos.qty is checked AFTER close_qty calculation, so safe

**Risk:** Low (safe-guarded)

#### Issue 5: Breakeven Calculation with Negative Leverage (line 573)
```python
if remaining_qty > 0 and pos.leverage > 0:
  profit_cushion = pos.realized_pnl / (remaining_qty * pos.leverage)
```

**Problem:** Negative leverage (should never occur) → sign flip
- Tested by guard `pos.leverage > 0`, so safe

**Risk:** Low (guarded)

### Fee Accumulation Precision

**Entry fee:**
```python
fee = entry * qty * (taker_fee_bps / 10000.0)

Example: entry=100, qty=1.5, bps=4
fee = 100 * 1.5 * 0.0004 = 0.06
```

**Rounding:** Depends on `_fee()` function precision (not shown)
- If fees are truncated: cumulative error possible
- If fees are rounded: error < 1 satoshi per trade

**Impact:** Medium (fees compound on many trades, but typically < 0.1%)

---

## 13. TIER 4 MECHANICAL BOT INSTRUMENTATION INTEGRATION

### Hooks Available

**1. Position Opening Hook** (lines 313-332)
```python
if _MECHANICAL_BOT_INSTRUMENTATION_AVAILABLE:
  instr = get_mechanical_bot_instrumentation()
  instr.on_position_opened(
    symbol=symbol,
    side=side,
    entry_price=entry,
    qty=qty,
    sl=sl,
    tp1=tp1,
    tp2=tp2,
    leverage=leverage,
    confidence=confidence,
    strategy=strategy,
    entry_reasons=entry_reasons,
    notes=notes,
    setup_type=setup_type,
  )
```

**2. State Change Hook (TP1_HIT → TRAILING)** (lines 595-614)
```python
instr.on_position_state_change(
  symbol=symbol,
  from_state=TP1_HIT,
  to_state=TRAILING,
  trigger="TP1_HIT",
  price=price,
  context={
    'partial_close_qty': close_qty,
    'partial_close_pct': dynamic_close_pct,
    'realized_pnl': pnl,
    'new_sl': new_sl,
    'remaining_qty': pos.qty,
  }
)
```

**3. Position Closing Hook** (lines 781-801)
```python
instr.on_position_closed(
  symbol=symbol,
  side=side,
  exit_price=price,
  exit_action=action,  # SL, TP2, TRAILING_STOP, EARLY_EXIT, etc.
  exit_qty=qty,
  entry_price=pos.entry,
  pnl=pos.realized_pnl,
  total_fees=pos.fees_paid,
  funding_costs=pos.funding_costs,
  outcome=pos.outcome,
  hold_duration_seconds=(...).total_seconds(),
  entry_reasons=entry_reasons,
  notes=notes,
  setup_type=setup_type,
)
```

### Error Handling
All hooks wrapped in try-except (lines 313-332, 596-614, 782-801):
```python
try:
  instr.on_position_...()
except Exception as e:
  logger.debug(f"[{symbol}] Mechanical bot instrumentation error: {e}")
```

**Policy:** Errors logged as DEBUG, don't crash the bot
**Risk:** Silent failures if instrumentation is misconfigured

---

## 14. CRITICAL EDGE CASES

### Edge Case 1: TP1 == TP2 (No Range)
```python
Entry: 100, SL: 95, TP1: 105, TP2: 105

At price=105:
  TP1 check (line 405): tp1_hit = True → partial close triggered
  → _partial_close_tp1() executes
  → state → TP1_HIT → TRAILING

  TP2 check (line 415): tp2_hit = True, state == TRAILING
  → _close_position() executes
  → state → CLOSED

Events: [TP1_event, TP2_event]
Outcome: CLEAN_WIN
```

**Risk:** Close qty may be zero if rounding (state guard prevents full disaster, but converts to CLEAN_WIN incorrectly)

### Edge Case 2: Entry == TP1
```python
Entry: 100, TP1: 100 (no move needed for partial close)

At price=100:
  tp1_hit = True (price >= tp1, so True)
  → _partial_close_tp1() executes
  → pnl = (100 - 100) * close_qty * leverage = 0
```

**Risk:** PnL is exactly 0, but state still transitions to TRAILING. Breakeven SL moved.

### Edge Case 3: Qty Rounds to Zero on Open
```python
Signal: qty = 0.000001 BTC (after precision rounding)

open_position() (line 250-252):
  if qty <= 0:
    logger.warning(...)
    return None  # Position NOT opened
```

**Risk:** Signal passed all gating but rejected at execution. Reported as "qty rounds to 0".

### Edge Case 4: Entry SL Very Tight
```python
Entry: 100, SL: 99.9 (0.1% risk)

_check_early_exit():
  stop_dist = abs(100 - 99.9) = 0.1
  # Any small deviation → high sl_progress

Regime-adaptive thresholds may be breached quickly
```

**Risk:** Early exit triggered on noise rather than real reversal

### Edge Case 5: Funding Accrual on Closed Position
```python
accrue_funding(symbol, funding_rate):
  if pos.state == CLOSED or pos.qty <= 0:
    return  # Short-circuit, no accrual
```

**Risk:** If state is not properly updated to CLOSED, funding continues accruing.
**Safeguard:** qty <= 0 check provides second layer

### Edge Case 6: Negative Realized PnL in Breakeven Calculation
```python
Entry: 100, Close TP1 at 99 (loss!)
realized_pnl = (99-100)*5*2 - fee = -10.x

profit_cushion = -10.x / 5 / 2 = -1.0

be_price (LONG) = 100 - (-1.0) + fee_buffer = 101.01

# SL moved ABOVE entry (worse for LONG)!
# But this is actually correct: we lost money on TP1 close,
# so SL needs more room to recover.
```

**Risk:** If TP1 closes at a loss, breakeven SL calculation inverts. This is mathematically correct but unintuitive.

### Edge Case 7: Peak Price Never Updated
```python
peak_price initialized to entry (line 106)
_update_trailing_stop() checks:
  if current_price > peak_price:
    peak_price = current_price

If price never exceeds peak:
  trailing_distance always calculated from initial peak (entry)
  tighten_factor stays high (wide trailing)
```

**Risk:** If price drops below entry immediately after TP1, trailing is loose when it should be tight. However, floor SL (line 693) kicks in at 35% progress, protecting against this.

### Edge Case 8: Extreme Slippage on TP1 Close
```python
Entry: 100, TP1: 105, Price spikes to 110

_partial_close_tp1():
  pnl = (110 - 100) * 5 * 2 = 100  # Large profit
  new_sl = 100 - (100 / 10) + fee = 90  # 10 points below entry!

On next down move, breakeven SL is very loose.
```

**Risk:** Extreme slippage gives enormous cushion. Trailing stop may not tighten enough to protect.

---

## SUMMARY OF CRITICAL FINDINGS

### High Priority

1. **Rounding Edge Case in TP1 Partial Close (lines 546-551)**
   - If close_qty rounds to full qty, position is silently converted to full close
   - No warning logged; user expects partial close but gets full
   - **Recommendation:** Add explicit warning log when close_qty >= remaining

2. **Early Exit Condition Complexity (lines 436-504)**
   - 3+ momentum conditions required for trending regimes may miss legitimate reversals
   - Regime detection from entry_reasons["regime"] may be stale
   - **Recommendation:** Add regex-safe regime validation

3. **TP1 == TP2 Edge Case (lines 404-418)**
   - Executes both TP1 and TP2 in same tick, outcome classified as CLEAN_WIN
   - Partial close happens, then immediate full close
   - **Recommendation:** Check if TP1 >= TP2 during signal validation (upstream)

### Medium Priority

4. **Funding Cost Allocation on Partial Close (lines 562-564)**
   - Proportional split is correct, but confusing for analysis
   - If remainder is later closed at loss, negative funding allocation may invert PnL sign
   - **Recommendation:** Clarify in trade logs which leg absorbed funding costs

5. **Trailing Distance Initialization (lines 254-268)**
   - Fallback to % of entry when ATR=0 may be too loose/tight
   - Style multipliers (0.8/1.0/1.5) are hard-coded
   - **Recommendation:** Make multipliers configurable per profile

6. **State Transition Logging (position_state.py:43-67)**
   - CSV log is append-only, no cleanup
   - Could grow unbounded if positions are rapidly opened/closed
   - **Recommendation:** Add optional log rotation (e.g., daily rollover)

### Low Priority

7. **Mechanical Bot Instrumentation Errors Silenced (lines 313-332, 596-614, 782-801)**
   - Exceptions only logged as DEBUG, may hide misconfiguration
   - **Recommendation:** Log as INFO for production issues

8. **Early Exit Math Assumes Monotonic Price (lines 451-454)**
   - If price whipsaws (up/down/up), momentum conditions evaluated once
   - Could miss late reversals
   - **Recommendation:** Track reversal velocity, not just candle count

9. **Fee Precision Loss (line 189)**
   - Depends on _fee() implementation precision
   - Cumulative error on many trades
   - **Recommendation:** Audit _fee() return type and rounding

---

## RECOMMENDATIONS

### Immediate Actions
1. Add log warning when partial close is converted to full close due to rounding
2. Validate TP1 < TP2 in signal validators (upstream, not in position manager)
3. Add sanity check: funding_costs should never exceed realized_pnl by >50%

### Short-term Enhancements
1. Make trailing distance multipliers (0.8/1.0/1.5) configurable per profile
2. Improve regime detection: use latest regime from LLM, not stale entry_reasons
3. Add optional logging of all state transitions to verbose debug file

### Long-term Improvements
1. Refactor early exit conditions into separate exit condition class
2. Add test cases for edge cases (TP1=TP2, SL=entry, qty rounds to 0)
3. Profile funding cost accrual logic to ensure precision across long holds
4. Add integration test for partial close → SL sequence

---

**Audit Completed:** 2025-03-20
**Files Reviewed:**
- `/home/user/WAGMI/bot/execution/position_manager.py` (1016 lines)
- `/home/user/WAGMI/bot/execution/position_state.py` (89 lines)
- `/home/user/WAGMI/bot/execution/trade_profile.py` (250+ lines)
- `/home/user/WAGMI/bot/execution/pnl_engine.py` (100+ lines)
- `/home/user/WAGMI/bot/tests/test_pnl_math.py` (150 lines)
