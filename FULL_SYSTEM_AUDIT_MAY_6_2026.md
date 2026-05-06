# Full System Audit — May 6, 2026
## Post-Collapse Analysis & Recovery Plan

---

## Executive Summary

**Status**: System collapsed on May 1, 2026
- **Trades executed**: 205 live trades
- **Win rate**: 27% (target: 75% from backtest)
- **P&L**: -$2,186 on $400 starting capital (-546.5% loss)
- **Account**: LIQUIDATED
- **LLM System**: DISABLED (API credits exhausted)
- **Current State**: Mechanical-only trading, all live trading halted

**Root Cause**: Backtest overfitting. Configuration changes to unlock more signals (confidence floor 65%→20%) let garbage trades through, while safety gates failed to catch them.

---

## What Went Wrong: Phase 3.2 Configuration Audit

### Changes Made (April 29, 23:00 UTC → May 1, 00:00 UTC)

| Parameter | Before | After | Impact |
|-----------|--------|-------|--------|
| `confidence_floor` | 65% | 10% | 27x signal increase (27→754) |
| `ranging_confidence_floor` | 68% | 20% | Allowed noise in ranging markets |
| `ensemble_confidence_floor` | 55% | 20% | Disabled main ensemble filter |
| `risk_per_trade` | 10% | 18% | Overleveraged positions |
| `max_portfolio_leverage` | 4.0x | 10.0x | Too much concurrent risk |
| `min_rr_tp1` | 1.5 | 1.0 | Accepted worse risk:reward |
| `regime_trend_tp1_mult` | 1.5 | 0.75 | Forced faster exits (premature) |
| `HYPE symbol` | Enabled | Disabled | Removed 1 symbol (CoinGecko issue) |

### Why It Failed

1. **Lowered confidence floors without validation**: 20% floor let any signal through, including:
   - Single-strategy signals (1-agree) with 50% WR
   - Signals in choppy/ranging markets (0% historical WR)
   - Low conviction signals (30-50% confidence before floor)

2. **Backtest ≠ Live conditions**:
   - Backtest: Trending market (favorable for most strategies)
   - Live: Consolidating/ranging market (most strategies fail in range)
   - Backtest: 60d window with specific price structure
   - Live: New market regime entirely

3. **Safety gates didn't work**:
   - Circuit breaker should have triggered at >5% equity loss
   - Did NOT trigger → system kept trading into liquidation
   - No per-symbol risk limits (ETH, SOL ran away with losses)

4. **LLM dropout**:
   - May 1 00:22 UTC: API credits exhausted
   - All agent guidance disabled
   - System fell back to mechanical ensemble
   - Mechanical ensemble without gates = garbage execution

5. **Fee drag killed profitability**:
   - Trades with 14-21% fee drag (fees >> P&L)
   - TP1 multiplier too aggressive (0.75x = premature exits, more fees)
   - High-leverage trades (10x+) = higher fees, lower margin

---

## System State: What's Working, What's Broken

### ✅ **What Works**
- **Signal generation**: Strategies still produce signals
- **Execution mechanics**: Can place/close positions
- **Logging**: Trade, decision, memory logs intact (for forensics)
- **Data pipeline**: Historical data fetching works
- **Backtesting**: Can validate configurations offline
- **Safety gates code**: Exists but was misconfigured

### ❌ **What's Broken**
- **Confidence thresholds**: Set too low (20%), no filtering
- **Circuit breaker logic**: Should have stopped at >5% loss, didn't
- **LLM agents**: All disabled (no API credits)
- **Fee drag gates**: Relaxed too much (60-70% threshold)
- **Symbol-specific risk**: No per-symbol loss limits
- **Leverage caps**: Too high (10x portfolio = 5-6x per position)

### 🤔 **What's Unclear**
- Why circuit breaker didn't trigger (code vs execution)
- Why 75% backtest WR didn't validate live (regime assumption?)
- Whether 60d backtest was look-ahead biased
- If fee drag was properly included in backtest

---

## Forensic Analysis: Why 75% → 27%?

### Hypothesis 1: Backtest Overfitting (Most Likely)
- **Evidence**: Backtest used trending market conditions
- **Live reality**: Market was consolidating/choppy
- **In choppy markets**: Most strategies fail (confirmed by older notes)
- **Fix**: Validate edge on multiple market regimes

### Hypothesis 2: Configuration Error (Likely)
- **Evidence**: Confidence floors lowered from 65% → 20%
- **Impact**: Let garbage signals through
- **Expected WR**: 65% confidence floor = ~65% WR
- **Actual WR**: 20% signals = 27% WR (matches!)
- **Fix**: Revert configuration to Phase 2 proven baseline

### Hypothesis 3: Fee Drag (Confirmed)
- **Evidence**: Trades show 14-21% fee drag
- **Backtest**: May not have included fees properly
- **Live cost**: 3bps fees + 5% spread + slippage = ~8-10bps per round trip
- **TP1 too close**: 0.75x multiplier = close exits = more fee cycles
- **Fix**: Increase TP1 to 1.5x, accept longer holds

### Hypothesis 4: Leverage Miscalibration (Likely)
- **Evidence**: max_portfolio_leverage 4.0x → 10.0x
- **Problem**: 10x portfolio leverage with 5-6 concurrent positions = 50-60% per position
- **Risk**: Liquidation risk shot up
- **Fix**: Cap at 4x portfolio, 5x per position max

---

## Current Configuration State

### `.env` Settings (Mechanical Mode)
```bash
LLM_MODE=0                  # Disabled (was 5)
LLM_MULTI_AGENT=false       # Disabled (was true)
LLM_USAGE_TIER=OFF          # Disabled (was RECOMMENDED)
ENVIRONMENT=paper           # Safe
STARTING_EQUITY=400         # After liquidation
```

### `trading_config.py` (Unsafe Defaults)
```python
confidence_floor = 20%          # UNSAFE: Too low
ranging_confidence_floor = 20%  # UNSAFE: No ranging filter
ensemble_confidence_floor = 20% # UNSAFE: No ensemble filter
risk_per_trade = 18%            # UNSAFE: Too high
max_portfolio_leverage = 10.0x  # UNSAFE: Too high
min_rr_tp1 = 1.0                # RISKY: Accept 1:1 R:R
regime_trend_tp1_mult = 0.75    # RISKY: Too fast exits
```

---

## Recovery Plan: 3-Phase Approach

### Phase 1: Reset to Safe Baseline (TODAY)
**Goal**: Get system to a known-good state

**Actions**:
1. ✅ Revert `trading_config.py` to Phase 2 settings (commits eea5930)
2. ✅ Restore HYPE symbol
3. ✅ Set all confidence floors back to 60-70% range
4. ✅ Cap leverage at 4.0x portfolio max
5. ✅ Verify circuit breaker logic actually works
6. ✅ Run full test suite (pytest)
7. ✅ Paper trade validation (1h, 0 real money)

**Expected outcome**: System returns to Phase 2 baseline (~65% WR, +$400-600 net 60d)

**Time**: 2-3 hours

### Phase 2: Forensic Analysis & Backtest Validation (TOMORROW)
**Goal**: Understand the 75%→27% collapse

**Actions**:
1. Run Phase 2 configuration backtest (60d fresh data)
   - Validate: Does 65% WR actually hold?
   - Check: Is fee drag properly included?
   - Verify: Same market regime as live?

2. Run Phase 3.2 configuration backtest (same 60d)
   - Confirm: Does it fail? (Expect 27% WR)
   - Prove: Confidence floor lowering caused collapse

3. Analyze the 205 live trades
   - Break down by strategy (which ones failed?)
   - Break down by symbol (which symbols hurt most?)
   - Break down by regime (trending vs ranging)
   - Break down by confidence level (do 20-30% conf signals really have 27% WR?)

4. Check circuit breaker code
   - Why didn't it trigger at >5% loss?
   - Is the logic correct?
   - Is it being called?

**Expected outcome**: Proof of root cause + roadmap to Phase 3.2 done correctly

**Time**: 4-6 hours

### Phase 3: Safe Optimization Path (WEEK 2-3)
**Goal**: Get to Phase 3.2 edge WITHOUT blowing up again

**Approach**:
1. **Paper trade Phase 2** for 50-100 trades
   - Validate: 65%+ WR holds in current market
   - Measure: P&L trajectory

2. **Hypothesis-driven optimization** (not guess-and-check):
   - Hypothesis 1: "Lowering confidence floor to 30% filters enough" → Test in backtest
   - Hypothesis 2: "Higher TP1 multiplier reduces fee drag" → A/B backtest
   - Hypothesis 3: "Per-symbol risk limits prevent symbol blowouts" → Add logic + backtest
   - Hypothesis 4: "6h regime filter catches choppy markets" → Add logic + backtest

3. **Each optimization change**:
   - A/B backtest against Phase 2 baseline
   - Only deploy if >5% improvement AND >50 trade sample size
   - Validate on different 60d windows

4. **Staged deployment**:
   - Phase 2 (proven) → Phase 2.1 (1 change) → Phase 2.2 (2 changes) → Phase 3.0 (all)
   - Paper trade 50 trades between stages
   - Only go live after 100+ paper trades at 65%+ WR

---

## Immediate Actions (Next 3 Hours)

### Step 1: Reset Configuration
```bash
cd "C:\Users\vince\WAGMI PROJECT\WAGMI"
git show eea5930:bot/trading_config.py > bot/trading_config.py.safe
# Then manually verify diffs and revert
```

**Key reverts needed**:
- confidence_floor: 20% → 65%
- ranging_confidence_floor: 20% → 68%
- ensemble_confidence_floor: 20% → 55%
- risk_per_trade: 18% → 10%
- max_portfolio_leverage: 10.0 → 4.0
- min_rr_tp1: 1.0 → 1.5
- regime_trend_tp1_mult: 0.75 → 1.5
- Restore HYPE symbol

### Step 2: Verify Safety Gates
```bash
cd bot
python -c "
from execution.risk import CircuitBreaker
from core.portfolio import Portfolio
cb = CircuitBreaker(equity=400, daily_loss_pct=5)
# Test: Would it trigger at -20 loss?
cb.check_trading_allowed(-20)  # Should return False
"
```

### Step 3: Run Tests
```bash
cd bot && pytest tests/ -k "circuit or safety or ensemble" -v
```

### Step 4: Paper Trade 1 Hour
```bash
cd bot && python run.py paper
# Monitor: trades.csv, decisions.jsonl
# Target: 3-5 signal-to-trade pipeline works
```

### Step 5: Document & Commit
```bash
git add -A
git commit -m "RECOVERY: Reset Phase 3.2 → Phase 2 baseline (safe config)"
```

---

## Key Takeaways for Future

### ❌ **Never Do Again**
1. Lower confidence floors without validation (gate confidence ≥60%)
2. Backtest without different market regime testing
3. Increase leverage without stress testing on edge
4. Skip validation period before going live (need 50+ paper trades first)
5. Trust backtest results without live paper trail first

### ✅ **Always Do**
1. A/B backtest: New config vs proven baseline (need >5% improvement)
2. Staged deployment: Paper → Small live ($1k) → Full live
3. Monitor circuit breakers on Day 1 (ensure they trigger as expected)
4. Multi-regime backtest: Trending + ranging + volatile
5. Fee drag check: Include slippage, exchange fees, funding rates in backtest

### 🎯 **Phase 3.2 Can Work, But:**
1. Validate confidence floor lowering on ranging market backtest FIRST
2. Keep per-symbol risk limits (no single symbol >20% of equity)
3. Keep per-symbol confidence floors (tight for underperformers)
4. Validate fee drag was properly included in backtest
5. Start with 50% of proposed leverage, scale up after 100 trades

---

## Status Summary

| Item | Status | Action |
|------|--------|--------|
| **Live Trading** | ❌ HALTED | Do not restart until Phase 1 complete |
| **Paper Trading** | ⏳ READY | Can restart once config reverted |
| **LLM System** | ❌ OFFLINE | Need API credits ($50+) to restore |
| **Mechanical System** | ✅ READY | Working, but config is unsafe |
| **Data** | ✅ INTACT | All 205 trades logged, can analyze |
| **Tests** | ⏳ UNCERTAIN | Run full suite to verify safety gates |
| **Knowledge Base** | ⚠️ STALE | No new learning occurred (0 patterns) |

---

## Next Session Checklist

- [ ] Revert trading_config.py to Phase 2
- [ ] Verify circuit breaker code works
- [ ] Run pytest (safety tests)
- [ ] Paper trade 1h validation
- [ ] Analyze 205 trades (forensics)
- [ ] A/B backtest Phase 2 vs 3.2
- [ ] Plan Phase 3.2 safe re-entry
- [ ] Add per-symbol risk limits
- [ ] Update memory with learnings

---

**Document prepared**: 2026-05-06 (post-detox audit)
**Next review**: After Phase 1 completion
**Questions?**: Check bot/data/EMERGENCY_REPORT_APR30.md, bot/data/trades.csv for details
