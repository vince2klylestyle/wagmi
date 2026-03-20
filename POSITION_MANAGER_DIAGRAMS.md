# Position Manager Visual Reference & Diagrams

## 1. PnL CALCULATION FLOWS

### LONG Position Full Lifecycle
```
ENTRY PHASE:
  Signal arrives with entry, qty, sl, tp1, tp2, leverage
  │
  ├─ Precision rounding applied (round_price, round_qty)
  │
  ├─ Position created with state=OPEN
  │
  └─ Entry fee deducted from notional
     fee = entry * qty * (taker_fee_bps / 10000)
     fees_paid += fee

OPEN PHASE (monitoring):
  Each tick: update_price(symbol, current_price)
  │
  ├─ MFE/MAE tracking: highest_price, lowest_price updated
  │
  ├─ Check exits in order:
  │  1. SL hit? → _close_position(price, "SL")
  │  2. Time stop? → _close_position(price, "TIME_STOP")
  │  3. Early exit? → _close_position(price, "EARLY_EXIT")
  │  4. TP1 hit? → _partial_close_tp1(price)
  │
  └─ Continue until state != OPEN

TP1 PARTIAL CLOSE:
  price >= tp1 (LONG)
  │
  ├─ Calculate close_qty = qty * dynamic_close_pct
  │  (with overshoot & speed scaling adjustments)
  │
  ├─ Calculate PnL on closed portion:
  │  pnl_tp1 = (price - entry) * close_qty * leverage
  │  fee_tp1 = price * close_qty * (taker_fee_bps / 10000)
  │  funding_share = funding_costs * (close_qty / qty)
  │
  ├─ Update realized_pnl:
  │  realized_pnl += pnl_tp1 - fee_tp1 - funding_share
  │  fees_paid += fee_tp1
  │  funding_costs -= funding_share
  │
  ├─ Move SL to breakeven+:
  │  profit_cushion = realized_pnl / (remaining_qty * leverage)
  │  new_sl = entry - profit_cushion + fee_buffer
  │  sl = round_price(symbol, new_sl)
  │
  ├─ Reduce qty:
  │  qty = round_qty(symbol, qty - close_qty)
  │
  ├─ Set peak_price = current_price (for trailing)
  │
  ├─ State transition: OPEN → TP1_HIT → TRAILING
  │
  └─ Log TP1 event with metadata

TRAILING PHASE:
  Each tick: _update_trailing_stop(pos, current_price)
  │
  ├─ Update peak_price if new high (LONG) or new low (SHORT)
  │
  ├─ Calculate progress toward TP2:
  │  progress = min(peak_move / total_range, 1.0)
  │
  ├─ Calculate tighten factor:
  │  tighten_factor = max(
  │    tighten_start - progress * (tighten_start - tighten_end),
  │    tighten_end
  │  )
  │
  ├─ Calculate effective trailing distance:
  │  effective_distance = trailing_distance * tighten_factor
  │
  ├─ Calculate trailing SL:
  │  trailing_sl = peak_price - effective_distance (LONG)
  │
  ├─ Calculate floor SL (profit lock):
  │  if progress > floor_start:
  │    lock_pct = min(floor_lock_start + (progress - floor_start)*0.5, floor_lock_max)
  │    floor_sl = entry + peak_move * lock_pct (LONG)
  │
  ├─ Take tighter of trailing vs floor:
  │  new_sl = max(trailing_sl, floor_sl) [LONG]
  │
  ├─ Only move SL in protective direction:
  │  if new_sl > old_sl (LONG): sl = new_sl
  │
  └─ Continue until exit condition

CLOSE PHASE (triggered by SL, TP2, or trailing stop):
  price hits sl OR price >= tp2
  │
  ├─ Calculate PnL on remaining qty:
  │  pnl_close = (price - entry) * remaining_qty * leverage
  │  fee_close = price * remaining_qty * (taker_fee_bps / 10000)
  │
  ├─ Calculate final realized_pnl:
  │  realized_pnl += pnl_close - fee_close - remaining_funding_costs
  │  fees_paid += fee_close
  │
  ├─ Classify outcome (CLEAN_WIN, TP1_THEN_SL, etc.)
  │
  ├─ State transition: TRAILING/TP1_HIT/OPEN → CLOSED
  │
  ├─ Invoke TIER 4 hook: on_position_closed()
  │
  └─ Log close event with all context

FINAL PnL:
  Total realized_pnl = TP1_leg + Trailing_leg - total_fees - total_funding
```

### SHORT Position PnL Formulas
```
PnL Calculation:
  TP1_leg:
    pnl_tp1 = (entry - price_tp1) * close_qty * leverage

  Trailing_leg:
    pnl_trailing = (entry - price_close) * remaining_qty * leverage

Fee Deduction:
  Each leg: fee_leg = price * qty * (taker_fee_bps / 10000)

Funding Cost Deduction:
  proportional_funding = total_funding * (leg_qty / original_qty)

  For SHORT: both legs deducted same way (cost paid either way)
```

---

## 2. TRAILING STOP TIGHTENING CURVES

### SCALP Profile Tightening
```
100%  ╱─────╲
      │     │
 80%  ├─╱────╲─ tighten_start = 0.80
      │ │    │
 60%  │ │ ╱──╲─ tighten_end = 0.60
      │ │ │  │
 40%  │ │ │  │
      │ │ │  │
  0%  └─┴─┴──┘
      0% progress toward TP2 → 100%

At progress=50%:
  factor = 0.80 - 0.50*(0.80-0.60) = 0.80 - 0.10 = 0.70
  effective_distance = trailing_distance * 0.70

With style_mult=0.8 (tight):
  final_trailing = atr*1.5*0.8*0.70 = atr*0.84
```

### MEDIUM Profile Tightening
```
100%  ╱────────╲
      │        │
 67%  ├─╱──────╲─ tighten_start = 0.67
      │ │      │
 45%  │ │╱─────╲ tighten_end = 0.45
      │ │ │    │
 25%  │ │ │    │
      │ │ │    │
  0%  └─┴─┴────┘
      0% progress toward TP2 → 100%

At progress=50%:
  factor = 0.67 - 0.50*(0.67-0.45) = 0.67 - 0.11 = 0.56
  effective_distance = trailing_distance * 0.56
```

### TREND Profile Tightening (Loose)
```
100%  ╱────────────╲
      │            │
 55%  ├─╱──────────╲ tighten_start = 0.55
      │ │          │
 45%  │ │╱────────╲ tighten_end = 0.45
      │ │ │       │
 25%  │ │ │       │
      │ │ │       │
  0%  └─┴─┴───────┘
      0% progress toward TP2 → 100%

At progress=50%:
  factor = 0.55 - 0.50*(0.55-0.45) = 0.55 - 0.05 = 0.50
  effective_distance = trailing_distance * 0.50

TREND gives most room for pullbacks (0.10 point range vs 0.22 for MEDIUM)
```

---

## 3. PROFIT LOCK FLOOR CURVE

### MEDIUM Profile Floor Activation
```
% of peak_move
      100│
         │
   60%   ├──────────╲─ floor_lock_max = 0.60
         │         │ \
   30%   │         │  ╲ floor_lock_start = 0.25
         │         │   ╲
   25%   │  ╱──────┼────╲ increases at rate 0.5 per progress unit
         │ ╱       │     ╲
    0%   ├─────────┼──────╲
         └─────────┼───────╲─── progress
         0%   35%  50%   100%
              floor_progress_start = 0.35
```

**Calculation:**
```
At progress = 0%:  lock_pct = 0%      (no floor)
At progress = 35%: lock_pct = 0%      (threshold, not yet active)
At progress = 50%: lock_pct = 0.25 + (0.50-0.35)*0.5 = 0.325 = 32.5%
At progress = 70%: lock_pct = 0.25 + (0.70-0.35)*0.5 = 0.425 = 42.5%
At progress = 100%: lock_pct = 0.25 + (1.00-0.35)*0.5 = 0.575, capped at 0.60 = 60%
```

**Example (LONG entry 100, peak 115, entry 100):**
```
peak_move = 15
progress = 50%

floor_sl = entry + peak_move * lock_pct
         = 100 + 15 * 0.325
         = 104.875

# No matter how much price drops, you won't exit below 104.88
# You've locked in at least $4.88 of the $15 peak move (32.5%)
```

---

## 4. EARLY EXIT MOMENTUM CONDITIONS

### Three Consecutive Candles Accelerating
```
LONG Position (price moving down against us):

C3 (most recent)  │  Low
C2 (middle)       │  Mid      C3 < C2 < C1 = Accelerating Down
C1 (oldest)       │  High

SHORT Position (price moving up against us):

C3 (most recent)  │  High
C2 (middle)       │  Mid      C3 > C2 > C1 = Accelerating Up
C1 (oldest)       │  Low
```

### EMA Crossover (Momentum Shift)
```
LONG Position (momentum turning negative):

Price ─┬─────────┬─────────┬─────────┐
       │ EMA5 > EMA13       │ EMA5 < EMA13 ← Bearish cross
       │ (uptrend)         │ (bearish)
       └─────────┼─────────┴─────────┘
                 │
           Momentum Shift
           (early exit trigger)

SHORT Position (momentum turning positive):
  Opposite: EMA5 > EMA13 triggers early exit
```

### SL Progress Extreme (>80%)
```
Entry: 100, SL: 95, Current Price: 95.4

stop_dist = abs(100 - 95) = 5
sl_progress = (100 - 95.4) / 5 = 0.92 = 92%

Close to SL already, even without acceleration conditions
```

---

## 5. PARTIAL CLOSE ROUNDING EDGE CASE

### Normal Case
```
qty = 1.50 BTC, tp1_close_pct = 0.50

close_qty = round_qty(BTC, 1.50 * 0.50)
          = round_qty(BTC, 0.75)
          = 0.75 BTC ✓

remaining = 1.50 - 0.75 = 0.75 BTC ✓
```

### Rounding Problem
```
qty = 0.00001 BTC, tp1_close_pct = 0.50

close_qty = round_qty(BTC, 0.00001 * 0.50)
          = round_qty(BTC, 0.000005)
          = 0 BTC (too small, rounds down!) ✗

remaining = 0.00001 - 0 = 0.00001 BTC ✓

Guard catches: close_qty <= 0
  → convert to full close (TP1_FULL)
  → Position fully closed instead of partial

User expected: 50% partial close
Got: 100% full close (outcome: CLEAN_WIN instead of TP1_HIT→TRAILING)
```

### Rounding Safety Guard
```python
# After calculating close_qty:
remaining_after = round_qty(symbol, pos.qty - close_qty)

# If rounding ate everything:
if remaining_after <= 0 and pos.qty > close_qty:
  close_qty = round_qty(symbol, pos.qty * 0.90)  # Reduce to 90% max

# This prevents zero-qty positions but silently changes intent
```

---

## 6. STATE TRANSITION WITH SIMULTANEOUS TP1 AND TP2

### Price Gap Over TP1 and TP2 in Same Tick
```
Tick N-1: state=OPEN, price=104, qty=10 BTC
          (below TP1=105)

Tick N:   price=106 (gap over TP1 and TP2)
          (TP1=105, TP2=110 in this example)

update_price(BTC, 106):

  1. SL check: 106 >= SL? (assume SL=95, so no)

  2. Early exit check: skipped (SL progress low)

  3. TP1 check: 106 >= 105? YES
     → _partial_close_tp1(pos, 106)
        close_qty = 10 * 0.50 = 5 BTC
        remaining = 5 BTC
        state = OPEN → TP1_HIT → TRAILING
        realized_pnl += (106-100)*5*leverage - fee

  4. TP1 check again? NO (line 404: if pos.state == OPEN)
     Now state is TRAILING, so skipped

  5. Update trailing stop: yes (state == TRAILING)
     _update_trailing_stop(pos, 106)
     (doesn't close, just updates peak_price and SL)

  6. TP2 check: 106 >= 110? NO
     (TP2 is 110, we only reached 106)

Result: Position in TRAILING state, 5 BTC remaining
Events: [TP1_event]
```

**NOTE:** If price was 111 (above TP2):
```
  6. TP2 check: 111 >= 110? YES
     → _close_position(pos, 111, "TP2")
        close_qty = 5 BTC (remaining)
        realized_pnl += (111-100)*5*leverage - fee - remaining_funding
        state = TRAILING → CLOSED
        outcome = CLEAN_WIN

Events: [TP1_event, TP2_event]
Final state: CLOSED
```

---

## 7. BREAKEVEN SL CALCULATION EXAMPLE

### LONG Position After TP1 Partial Close
```
Setup:
  Entry: 100
  Original SL: 95 (5 point risk)
  TP1: 105
  Original qty: 10 BTC
  Leverage: 2x
  taker_fee_bps: 4

TP1 Hit at 105:
  Close qty: 5 BTC (50%)
  Remaining: 5 BTC

  Gross PnL: (105-100) * 5 * 2 = 50
  Fee: 105 * 5 * 0.0004 = 0.21
  Net realized_pnl: 50 - 0.21 = 49.79

New SL Calculation:
  profit_cushion = 49.79 / (5 * 2) = 4.979
  fee_buffer = 100 * 0.0008 + 0.001 ≈ 0.081

  new_sl = 100 - 4.979 + 0.081 = 95.102

Result:
  Old SL: 95.0 (breakeven, 5 points below entry)
  New SL: 95.102 (even tighter!)

Why? Because we banked $49.79 profit, that's 4.979 points
of cushion. We can afford to lose 4.979 points and still
break even on the trade. So SL at 95.102 = entry - cushion.

Now the remaining 5 BTC can lose up to 4.979 points per share
and we still profit overall.
```

### Breakeven SL When TP1 Closes at a Loss
```
TP1 Hit at 104 (below entry!):
  Gross PnL: (104-100) * 5 * 2 = 40
  But what if slippage and fees turn this negative?

  realized_pnl: -5 (loss on TP1 partial close!)

  profit_cushion = -5 / (5 * 2) = -0.5

  new_sl = 100 - (-0.5) + 0.081 = 100.581

Result:
  New SL moved ABOVE entry!
  (95 → 100.581)

Why? We lost money closing 50% at TP1. The remaining 50%
needs to recover that loss. To break even on the whole trade,
the remaining 5 BTC need to make +$5. If we close at 101,
we profit 1*5*2 = 10, minus original 5 loss = 5 net.

So SL above entry makes sense mathematically when TP1 closes at loss.
```

---

## 8. FUNDING COST ALLOCATION (TP1 Partial Close)

### Full Lifecycle Example
```
Position Open at 100:
  Hold time: 0-2 hours (accrue 0.10 funding per hour)
  After 2h: funding_costs = 0.20

TP1 Hit at 105 (2h elapsed):
  funding_costs = 0.20

  close_qty = 5 BTC (50% of original)
  funding_share = 0.20 * (5 / 10) = 0.10

  realized_pnl += (pnl_tp1 - fee_tp1 - 0.10)  ← share deducted
  funding_costs -= 0.10  ← remaining balance

  After TP1: funding_costs = 0.10 (only for remaining 5 BTC)

Trailing Phase (2-6h):
  Additional funding accrued: 0.20 (for remaining 5 BTC)
  funding_costs = 0.10 + 0.20 = 0.30

  But wait, second accumulation should only count 5 BTC, not 10
  (assuming accrue_funding() correctly uses pos.qty)

Final Close at 6h:
  funding_costs = 0.30 (all remaining for remaining qty)

  realized_pnl += (pnl_trailing - fee_trailing - 0.30)

Total funding charged:
  TP1 leg: 0.10 (from first 2h, 50% share)
  Trailing leg: 0.20 (new 4h accrual) + 0.10 (remainder of first 2h)
  Total: 0.30

This matches 6h of funding on original qty (approx)
```

---

## 9. OUTCOME CLASSIFICATION MATRIX

```
                   TP1 Hit?    Profit?    Action         Outcome
────────────────────────────────────────────────────────────────
OPEN → CLOSED      No          Loss       SL             CLEAN_LOSS
OPEN → CLOSED      No          Win        (rare)         CLEAN_WIN
OPEN → CLOSED      No          Loss       EARLY_EXIT     EARLY_EXIT_FAIL
OPEN → CLOSED      No          Gain       EARLY_EXIT     EARLY_EXIT_SAVE
OPEN → CLOSED      No          Loss       TIME_STOP      (CLEAN_LOSS)
OPEN → CLOSED      No          Loss       EMERGENCY      (CLEAN_LOSS)

OPEN → TP1_HIT     Yes         Win        TP1 trigger    (state change)
OPEN → TP1_HIT     Yes         Loss       TP1 trigger    (state change)
OPEN → TP1_HIT     Yes         —          —              (state change)

TP1_HIT → TRAILING Yes         —          —              (state change)

TRAILING → CLOSED  Yes         Win        TP2            CLEAN_WIN
TRAILING → CLOSED  Yes         Win        TRAILING_STOP  TRAILING_WIN
TRAILING → CLOSED  Yes         Loss       SL             TRAILING_FAIL
TRAILING → CLOSED  Yes         Loss       TRAILING_STOP  TRAILING_FAIL
TRAILING → CLOSED  Yes         Loss       EMERGENCY      (CLEAN_LOSS)

(After TP1 closed)
TRAILING → CLOSED  Yes         Loss       Any exit       TP1_ONLY
TRAILING → CLOSED  Yes         Loss       SL             TP1_THEN_SL
```

---

## 10. QUICK REFERENCE: PROFILE PARAMETERS

### Parameter Comparison Table
```
Parameter              SCALP    MEDIUM   TREND    REGIME
─────────────────────────────────────────────────────────
TP1 Distance (ATR)     0.5x     1.0x     1.2x     1.2x
TP2 Distance (ATR)     1.0x     2.0x     2.5x     2.5x
SL Distance (ATR)      0.4x     0.55x    0.60x    0.55x
────────────────────────────────────────────────────────────
TP1 Close %            90%      50%      40%      55%
Trailing Style         tight    medium   loose    medium
Tighten Start/End      0.80/60  0.67/45  0.55/45  0.60/45
────────────────────────────────────────────────────────────
Floor Progress         20%      35%      30%      30%
Floor Lock Start       40%      25%      30%      30%
Floor Lock Max         75%      60%      60%      60%
────────────────────────────────────────────────────────────
Max Hold Time          4h       12h      36h      48h
Expected Trade Type    Fast     Medium   Long     Regime
```

---

## KEY FORMULAS QUICK REFERENCE

### PnL Calculations
```
LONG:
  pnl = (exit_price - entry_price) * qty * leverage

SHORT:
  pnl = (entry_price - exit_price) * qty * leverage

Fees:
  fee = price * qty * (taker_fee_bps / 10000) * 2  (entry + exit)

Net PnL:
  realized_pnl = gross_pnl - total_fees - funding_costs
```

### Trailing Stop
```
Trailing Distance Initialization:
  trailing_distance = atr * 1.5 * style_mult
  where style_mult = {tight: 0.8, medium: 1.0, loose: 1.5}

Tighten Factor:
  factor = max(tighten_start - progress * (tighten_start - tighten_end), tighten_end)

Trailing SL:
  trailing_sl = peak_price - (trailing_distance * factor)  [LONG]

Floor SL:
  lock_pct = min(floor_lock_start + (progress - floor_start)*0.5, floor_lock_max)
  floor_sl = entry + peak_move * lock_pct  [LONG]

Final SL:
  new_sl = max(trailing_sl, floor_sl)  [LONG]
```

### Breakeven After TP1
```
profit_cushion = realized_pnl / (remaining_qty * leverage)
be_price = entry - profit_cushion + fee_buffer  [LONG]
fee_buffer = entry * (taker_fee_bps*2/10000 + 0.001)
```

---

**Reference Document Created:** 2025-03-20
