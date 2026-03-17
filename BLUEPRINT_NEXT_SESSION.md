# NEXT SESSION BLUEPRINT
**Created:** 2026-03-17 | **Priority:** Get the bot actually trading

---

## THE ROOT PROBLEM: Why We're Not Trading

The bot generates signals but **multiple compounding filters kill them all**. Here's the kill chain from your logs:

```
HYPE: ADX 9.8 < 10.0 → regime_trend skips entirely
HYPE: BUY hist WR=1% → -14.8 adjustment + -15 penalty = -29.8 points lost
SOL:  Only 1 BUY signal → need 2+ same-side (ensemble rejects)
SOL:  Blocked losing combo [bollinger_squeeze, multi_tier_quality]
BTC:  CHOP DETECTED score=0.63 → confidence floor rises to 68-93%
BTC:  Only 1 BUY signal → need 2+ same-side
```

**Three things are compounding to zero trades:**
1. **WR penalty with poisoned history** — old strategy data gives 0-1% WR → -30 confidence
2. **Chop detection too aggressive** — floor rises to 68-93% in range markets, nothing clears it
3. **Losing combo blocker** — `multi_tier_quality` poisons 4 of 5 blocked combos, but its presence in the combo set also blocks valid signals from other strategies

---

## TASK 1: Fix WR Penalty System (CRITICAL - Do First)

### Problem
`bot/strategies/confidence_scorer.py` lines 398-411:
- Formula: `adjustment = (hist_conf - 0.5) * 30` → range -15 to +15
- PLUS if WR < 15%: additional -15 penalty (lines 408-411)
- **Total possible penalty: -30 points** from a metric based on 5-10 old trades

### The Data
- Signal log: `bot/ml_data/confidence_signal_log.json` (if it exists on Windows)
- Success criteria is absurdly strict: BUY needs +0.5% move, STRONG_BUY needs +1.0%
- With few trades evaluated, getting 0-1% WR is inevitable

### Fix Options (Pick One)

**Option A: Raise minimum sample size** (Safest)
```python
# Line 166: Change from 5 to 30
if len(evaluated) < 30:
    return None  # Don't penalize until we have real data
```

**Option B: Grace period with soft dampening** (Recommended)
```python
# Replace lines 398-411 with:
hist_conf = self._get_historical_confidence(symbol, action)
if hist_conf is not None:
    n_trades = len([e for e in self.signal_log.get(symbol, [])
                    if e.get("evaluated") and e["signal"] == action])
    # Scale penalty by sample size: 0% at 5 trades, 100% at 50 trades
    weight = min(1.0, max(0.0, (n_trades - 5) / 45))
    adjustment = (hist_conf - 0.5) * 30 * weight
    confidence += adjustment
    # Remove the extra -15 penalty entirely (double punishment)
```

**Option C: Nuke it for now** (Quick and dirty)
```python
# Just return None always until we have 50+ trades
if len(evaluated) < 50:
    return None
```

### Also Clear Old Data
On Windows, find and delete these files if they exist:
- `bot/ml_data/confidence_signal_log.json`
- `bot/ml_data/strategy_weights.json`
- `bot/ml_data/bot.db` (SQLite database with old outcomes)

---

## TASK 2: Fix Losing Combo Blocker

### Problem
`bot/strategies/ensemble.py` lines 1140-1162:
```python
_LOSING_COMBOS = {
    frozenset({"confidence_scorer", "multi_tier_quality"}),       # PF 0.08
    frozenset({"multi_tier_quality", "regime_trend"}),            # PF 0.82
    frozenset({"bollinger_squeeze", "multi_tier_quality"}),       # PF 0.37
    frozenset({"lead_lag", "multi_tier_quality"}),                # PF 0.00
    frozenset({"bollinger_squeeze", "confidence_scorer", "multi_tier_quality"}),
}
```

**`multi_tier_quality` is in ALL 5 combos** but it's already DISABLED in config. Yet the combo blocker still fires because subset matching catches any pair that includes it.

### Fix
Since `multi_tier_quality` is disabled (won't generate signals), the combo blocker shouldn't even trigger for it. Check if there's a bug where disabled strategies still appear in the combo set. If SOL's `bollinger_squeeze + multi_tier_quality` is getting blocked, `multi_tier_quality` must still be generating signals somehow.

**Investigation needed:**
1. Is `STRATEGY_MULTI_TIER_QUALITY_ENABLED` actually `False`?
2. If so, why is it still in the signal set?
3. Consider clearing the `_LOSING_COMBOS` entirely and rebuilding after 50+ trades with current strategies

---

## TASK 3: Tune Chop Detection Thresholds

### Problem
`bot/strategies/chop_detector.py` and `ensemble.py`:
- BTC chop score = 0.63, threshold = 0.45 (low volatility)
- This raises ensemble confidence floor from 55% → 68-93%
- In a ranging market, this effectively blocks ALL trades

### Current Thresholds
```python
VOLATILITY_THRESHOLDS = {
    "low": 0.45,     # BTC
    "medium": 0.45,  # SOL
    "high": 0.55,    # HYPE/memes
}
```

### Fix Options
**Option A: Raise thresholds** (let more signals through in chop)
```python
VOLATILITY_THRESHOLDS = {
    "low": 0.55,     # BTC: was 0.45
    "medium": 0.55,  # SOL: was 0.45
    "high": 0.65,    # HYPE: was 0.55
}
```

**Option B: Cap the graduated floor** (don't let it go above 75%)
- In ensemble.py, the chop floor interpolates up to 93% for BTC
- Cap at 75% max so high-confidence signals can still pass

**Option C: Disable chop floor escalation temporarily**
- Set floor to fixed 55% regardless of chop score
- Let other filters (WR, EV, leverage) handle quality control

---

## TASK 4: Clear Historical Data (Fresh Start)

### Files to Clear (Run on Windows)
```powershell
# Trade history (old strategy data poisoning WR)
Remove-Item bot\trades.csv -ErrorAction SilentlyContinue
Remove-Item bot\trades_10d.csv -ErrorAction SilentlyContinue

# Backtest artifacts (not needed for live)
Remove-Item bot\backtest_*.csv -ErrorAction SilentlyContinue
Remove-Item bot\*_equity_curve.csv -ErrorAction SilentlyContinue

# Feedback state (old regime WR = 0% in range is killing signals)
Remove-Item bot\data\feedback\regime_feedback_state.json -ErrorAction SilentlyContinue
Remove-Item bot\data\feedback\adaptive_risk_state.json -ErrorAction SilentlyContinue

# LLM state (survival_state has old consecutive_losses)
Remove-Item bot\data\llm\survival_state.json -ErrorAction SilentlyContinue
Remove-Item bot\data\llm\thesis_history.jsonl -ErrorAction SilentlyContinue
Remove-Item bot\data\llm\cost_tracker.json -ErrorAction SilentlyContinue
Remove-Item bot\data\llm\pattern_cache.json -ErrorAction SilentlyContinue
Remove-Item bot\data\llm\operator_messages.json -ErrorAction SilentlyContinue

# Analytics (A/B tests, counterfactuals from old strategies)
Remove-Item bot\data\ab_tests\* -ErrorAction SilentlyContinue
Remove-Item bot\data\counterfactuals\* -ErrorAction SilentlyContinue
Remove-Item bot\data\meta_learning\* -ErrorAction SilentlyContinue
Remove-Item bot\data\logs\*.csv -ErrorAction SilentlyContinue
Remove-Item bot\data\portfolio_risk\correlation_cache.json -ErrorAction SilentlyContinue

# ML data (confidence signal log - THE WR POISON SOURCE)
Remove-Item bot\ml_data\confidence_signal_log.json -ErrorAction SilentlyContinue
Remove-Item bot\ml_data\strategy_weights.json -ErrorAction SilentlyContinue
Remove-Item bot\ml_data\bot.db -ErrorAction SilentlyContinue
```

### Files to KEEP
- `bot/data/llm/teaching/knowledge_base.json` (169 axioms, valuable)
- `bot/data/llm/deep_memory/insight_journal.json` (domain insights)
- `bot/data/llm/graduated_rules.json` (5 learned rules)
- `bot/data/llm/learning_state.json` (curriculum progress)
- ALL `.py` code files

---

## TASK 5: Manual Trading on Web Dashboard

### Current State
- **Homepage** (`web/pages/index.tsx`): Shows regime, latest signals, strategy cards
- **Strategies page** (`web/pages/strategies/`): Lists strategies, logs, trades
- **Copy trade page** (`web/pages/copy-trade.tsx`): Copy trading subscriber management
- **NO manual trading UI**: No order form, no position closure, no charting

### What to Build (Priority Order)
1. **Signal Action Panel** on homepage — "Take this trade" button next to each signal
   - Pre-fills: symbol, side, entry, SL, TP1, TP2 from bot signal
   - User just confirms and adjusts size
   - Hits existing exchange API (Hyperliquid via CCXT)

2. **Quick Trade Form** on new `/manual-trade` page
   - Symbol selector (BTC/SOL/HYPE)
   - Side toggle (LONG/SHORT)
   - Size input (USD or % of equity)
   - Entry, SL, TP fields (auto-calculated from current signal if available)
   - Confirmation dialog with R:R and liquidation price

3. **Position Manager** — view + close open positions
   - Show current positions with live PnL
   - "Close" button per position
   - "Adjust SL/TP" form

4. **Add charting** — Install `lightweight-charts` (TradingView) in web/
   - Show price action with entry/SL/TP overlay
   - Mark past trades on chart

### API Endpoints Needed
```
POST /v1/manual/order     — Submit manual order
POST /v1/manual/close     — Close position
PATCH /v1/manual/adjust   — Modify SL/TP
GET  /v1/positions/live    — Current open positions with live PnL
```

---

## TASK 6: Quick Wins (Do If Time)

### A. regime_feedback_state.json is Poisoning Range Regime
The file shows `range` regime has: `win_count: 0, loss_count: 2, confidence_floor: 85%`
- This 85% floor means NO signals pass in range markets
- Either clear the file (Task 4) or reset range floor to 60%

### B. Verify multi_tier_quality is Actually Disabled
Check `trading_config.py` for `STRATEGY_MULTI_TIER_QUALITY_ENABLED`
- If it's generating signals despite being "disabled", fix the enable/disable logic
- Its presence in losing combos blocks valid bollinger_squeeze signals

### C. The momentum_scorer WR Shows 1% for HYPE
```
[HYPE] BUY hist WR=1%, adj=-14.8, final=55.2
```
This means the `confidence_signal_log.json` has ~100 evaluated HYPE BUY signals with 1 win.
That's clearly from old strategy runs. **Clearing this file is essential.**

### D. ADX 9.8 for HYPE
HYPE's ADX is 9.8, just under the 10.0 threshold for `regime_trend`.
- Consider lowering to 8.0 for high-volatility symbols
- Or use a per-symbol ADX threshold: BTC=12, SOL=10, HYPE=8

---

## PRIORITY ORDER FOR NEXT SESSION

```
1. Clear all historical data files (5 min)          ← Unblocks everything
2. Fix WR penalty: raise min to 30+ trades (10 min) ← Stops confidence bleed
3. Remove extra -15 penalty (it double-punishes)     ← Paired with #2
4. Review/clear _LOSING_COMBOS for current strategies ← Unblocks SOL signals
5. Cap chop floor at 75% max (not 93%)              ← Lets BTC trade in range
6. Run paper trade, verify signals pass through      ← Validate fixes
7. Start manual trading UI work                      ← Longer-term
```

---

## VERIFICATION CHECKLIST

After making changes, look for these in paper trade logs:
- [ ] No more `WR X% too low, -15 penalty` messages
- [ ] No more `Blocked losing combo` for disabled strategies
- [ ] BTC signals pass through chop floor (floor should be <= 75%)
- [ ] At least 1 trade executes within 30 minutes of paper start
- [ ] Signal pipeline shows signals reaching Gate 3+ (leverage) not dying at ensemble

---

## FILES YOU'LL BE EDITING

| File | What to Change |
|------|---------------|
| `bot/strategies/confidence_scorer.py:166` | Raise min trades from 5 to 30+ |
| `bot/strategies/confidence_scorer.py:408-411` | Remove/soften the extra -15 penalty |
| `bot/strategies/ensemble.py:1140-1162` | Review _LOSING_COMBOS for current strategy set |
| `bot/strategies/chop_detector.py` | Raise thresholds or cap floor |
| `bot/strategies/ensemble.py:508-542` | Cap graduated chop floor at 75% |
| `bot/trading_config.py` | Verify multi_tier_quality disabled |
| `web/pages/manual-trade.tsx` (NEW) | Manual trading UI |
| `api/app/routes_manual.py` (NEW) | Manual order endpoints |

---

## CURRENT TRADE HISTORY (for context)

From `trades.csv` — 19 trades total:
- **SOL**: 2W / 4L = 33% WR, net PnL ~ -$1,260
- **HYPE**: 4W / 8L = 33% WR, net PnL ~ -$1,260
- **BTC**: 0 trades (never gets through filters)
- **Overall**: 6W / 12L = 33% WR

The 33% WR with these strategies at the old leverage was expected to lose.
With the new leverage fixes (1.5-4x range) + proper filtering, the R:R should improve.
But first, the bot needs to actually TAKE trades.
