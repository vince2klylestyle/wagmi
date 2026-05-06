# Recovery Action Plan — May 6, 2026
## From -$2,186 Liquidation to Operational Again

**Status**: Configuration reset complete. System ready for validation.
**Next**: Paper trade validation, forensic analysis, safe re-entry planning.

---

## What Happened (Summary)
1. **Apr 30**: Phase 3.2 went live (aggressive config: 75% WR backtest)
2. **May 1**: Live trading collapsed (205 trades, 27% WR, -$2,186 loss, account liquidated)
3. **May 1 00:22**: API credits exhausted → LLM disabled → mechanical-only trading
4. **May 6**: You returned from detox, system in bad state

**Root Cause**: Configuration lowered confidence floors from 65%→20% to unlock signals, but let garbage trades through. Backtest overfitted to trending market; live was ranging/choppy.

---

## Recovery Steps (Do These TODAY)

### Step 1: Verify Configuration Reset ✅ DONE
```
Configuration reverted to Phase 2 safe baseline:
- ranging_confidence_floor: 68% (was 20%)
- ensemble_confidence_floor: 55% (was 20%) 
- risk_per_trade: 10% (was 18%)
- max_portfolio_leverage: 4.0x (was 10.0x)
- HYPE symbol: ENABLED

Status: VERIFIED
```

### Step 2: Test Bot Can Start (30 min)
**Do this now:**
```bash
cd C:\Users\vince\WAGMI PROJECT\WAGMI\bot
python run.py paper  # Start 5-minute paper trading test
# Stop after 3-5 signals generated (Ctrl+C)
```

**What to look for**:
- Bot starts without errors
- Signals generate (should see 10-20 signals/hour in trending market)
- No crashes
- Log shows signal → ensemble decision flow

**Expected**: 5-10 signals, maybe 1-2 trades executed

### Step 3: Quick 1-Hour Paper Trade (1-2 hours)
```bash
cd bot
python run.py paper
# Let it run 1 hour, then stop
```

**Monitor**:
- `tail -f bot/data/trades.csv` in another terminal
- Target: 0-3 trades executed
- Check confidence levels (should be 55%+, not 20%)
- No circuit breaker triggers (should be healthy)

**Success criteria**:
- ✓ No crashes
- ✓ Confidence levels > 50%
- ✓ Execution flow looks normal
- ✓ No weird signal quality issues

### Step 4: Deep Forensic Analysis (4-6 hours, can do tomorrow)
**Analyze the May 1 liquidation:**

```bash
# See which trades lost money
python -c "
import pandas as pd
df = pd.read_csv('data/trades.csv')
df['pnl'] = pd.to_numeric(df['pnl'], errors='coerce')

# By symbol
print('BY SYMBOL:')
for symbol in ['BTC', 'ETH', 'SOL', 'HYPE']:
    symbol_trades = df[df['symbol'] == symbol]
    if len(symbol_trades) > 0:
        wins = len(symbol_trades[symbol_trades['pnl'] > 0])
        losses = len(symbol_trades[symbol_trades['pnl'] < 0])
        net_pnl = symbol_trades['pnl'].sum()
        wr = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0
        print(f'{symbol}: {wr:.1f}% WR ({wins}/{wins+losses}), P&L: \${net_pnl:.2f}')
"
```

**Key questions to answer**:
1. Which symbol lost most? (BTC -$78, ETH -$1,989, SOL +$4, HYPE -$123)
2. Which strategy lost most? (Check strategy column)
3. Are losses in ranging vs trending? (Check regime column)
4. What confidence range did trades execute at? (should be 50-100%)
5. Why didn't circuit breaker trigger? (Code issue?)

### Step 5: A/B Backtest (6-8 hours, do tomorrow)
**Compare Phase 2 vs Phase 3.2 on fresh data:**

```bash
# Run Phase 2 backtest (current config)
python cli.py --mode backtest BTC 60

# Note results: signals, WR, net P&L, avg trade

# Then temporarily change config to Phase 3.2 values
# Edit bot/trading_config.py: Set confidence_floor=20%, ensemble_confidence_floor=20%
# Run backtest again on SAME 60d window

# Compare: Did Phase 3.2 match live results (27% WR)?
```

Expected:
- Phase 2 backtest: 60-70% WR (validates edge still exists)
- Phase 3.2 backtest: ~27% WR (proves configuration was the problem)

---

## Next Steps (This Week)

### Day 1 (TODAY): Validation
- [ ] Run paper trade test (1h)
- [ ] Confirm no crashes/errors
- [ ] Commit recovery documentation

### Day 2-3: Analysis
- [ ] Forensic analysis of May 1 liquidation
- [ ] A/B backtest Phase 2 vs Phase 3.2
- [ ] Identify root cause (configuration? backtest overfitting? regime?)
- [ ] Document findings in FORENSIC_ANALYSIS.md

### Day 4-7: Safe Optimization
- [ ] Paper trade Phase 2 config (50-100 trades)
- [ ] Validate 65%+ WR in current market
- [ ] Plan Phase 3.2 safe re-entry (hypothesis-driven)
- [ ] Add per-symbol risk limits
- [ ] Get API credits if pursuing LLM-enhanced trading

---

## Key Rules Going Forward

### ❌ NEVER
1. Lower confidence floors below 55% without multi-regime backtest validation
2. Trust backtest results on single market regime (trend-only)
3. Skip paper trading phase (need 50+ trades first)
4. Increase leverage without stress testing circuit breakers
5. Deploy new configuration to live without A/B backtest first

### ✅ ALWAYS
1. A/B backtest: New config vs proven baseline (need >5% WR improvement)
2. Multi-regime validation: Test trending + ranging + volatile
3. Staged deployment: Paper (50 trades) → Small live ($1k) → Full live
4. Monitor circuit breakers on Day 1 (ensure they trigger correctly)
5. Log reasoning: Why this change? What's the hypothesis? What's the validation plan?

---

## LLM System Recovery (Optional)

Current state: **DISABLED** (API credits exhausted May 1 00:22 UTC)

To restore LLM agent guidance:
1. Add $50+ in Anthropic API credits
2. Set in `.env`: `LLM_MODE=2` (veto-only, conservative)
3. Run: `cd bot && python run.py paper`
4. Monitor: Trade quality should improve (agents veto bad signals)

**Note**: LLM is enhancement, not requirement. Mechanical-only trading works, just lower WR.

---

## Current System Health

| Component | Status | Notes |
|-----------|--------|-------|
| **Config** | ✅ SAFE | Phase 2 baseline restored |
| **Execution** | ✅ WORKS | Can place/close positions |
| **Safety Gates** | ⚠️ VERIFY | Code exists, need Day 1 test |
| **Signals** | ✅ WORKS | Strategies generating |
| **LLM Agents** | ❌ OFFLINE | API credits exhausted |
| **Data/Logging** | ✅ INTACT | 205 trades logged for forensics |
| **Tests** | ? UNKNOWN | Need to run full suite |
| **Paper Trading** | ✅ READY | Can start anytime |
| **Live Trading** | 🛑 HALTED | Do NOT enable until validation complete |

---

## File References

**Critical Reading**:
- `FULL_SYSTEM_AUDIT_MAY_6_2026.md` — Complete audit with root cause analysis
- `bot/data/trades.csv` — All 205 trades (for forensics)
- `bot/data/EMERGENCY_REPORT_APR30.md` — Initial failure report
- `WEEK_PLAN_APR30_MAY6.md` — Original plan (what went wrong)

**Configuration**:
- `bot/trading_config.py` — Master config (now Phase 2 safe)
- `.env` — Environment variables (LLM_MODE, etc.)

**Logs** (if needed):
- `bot/data/llm/decisions.jsonl` — 901 LLM decisions (mostly API errors after 00:22)
- Various crash/execution logs in `/tmp/`

---

## Success Criteria

### Phase 1 Complete (By Tonight)
- [ ] Paper trading runs without crashes
- [ ] Config values verified as safe
- [ ] No unusual error patterns
- [ ] Ready for forensic analysis

### Phase 2 Complete (By Day 3)
- [ ] Root cause identified (configuration? regime? backtest?)
- [ ] A/B backtest shows why Phase 3.2 failed
- [ ] Understanding of backtest → live gap
- [ ] Plan for safe re-entry documented

### Phase 3 Complete (By End of Week)
- [ ] 50-100 paper trades at 65%+ WR
- [ ] Phase 3.2 safe re-entry plan ready
- [ ] Per-symbol risk limits implemented
- [ ] Decision on LLM restoration made

---

## Questions?

If bot won't start or tests fail:
1. Check `.env` has valid paths
2. Check `bot/trading_config.py` loads without import errors
3. Check data files exist: `bot/data/trades.csv`, etc.
4. Run: `python -c "from trading_config import TradingConfig; TradingConfig()"`

---

**Status**: RECOVERY PLAN READY
**Next action**: Run 1-hour paper trade test
**Time estimate**: 1-2 hours to get back to "operational" baseline

Go ahead when ready. I'll monitor the run and help debug if needed.
