# Comprehensive System Audit — May 6, 2026
## Complete Technical State, Architecture, and Recovery Plan

---

## Executive Summary

**Project Status**: OPERATIONAL BUT UNTESTED
- **Codebase**: 773 Python files, 4.2GB, highly complex multi-agent trading system
- **Subsystems**: LLM (172 files), Execution (45), Strategies (25), Feedback (22), Core (11), Backtest (11)
- **Current Situation**: Phase 2 baseline restored (safe config), but Phase 3.2 never validated in paper trading
- **Key Issue**: Backtest-to-live gap not understood; paper trading infrastructure exists but wasn't used to validate configs
- **Recovery Path**: Paper trade Phase 2 for 50-100 trades, forensic analysis of May 1 collapse, then safe Phase 3.2 re-entry

---

## Part 1: Architecture Overview

### System Layers

```
┌─────────────────────────────────────────────────────────┐
│ PAPER TRADING MODE (Simulation)                         │
├─────────────────────────────────────────────────────────┤
│ Entry Layer: run.py (paper | backtest | signals)        │
├─────────────────────────────────────────────────────────┤
│ Multi-Strategy Bot (multi_strategy_main.py)             │
│  ├─ 4 Trading Strategies (ensemble voting)              │
│  ├─ 9-Agent LLM System (regime/trade/risk/critic/etc)  │
│  ├─ Execution Engine (position sizing & orders)         │
│  └─ Feedback Loops (learning & parameter tuning)        │
├─────────────────────────────────────────────────────────┤
│ Data Pipeline                                            │
│  ├─ CCXT Multi-Exchange Fetcher                         │
│  ├─ SQLite Database (persistent state)                  │
│  └─ Memory Systems (short-term + deep learning)         │
├─────────────────────────────────────────────────────────┤
│ Monitoring & Alerts                                      │
│  ├─ Discord/Telegram notifications                      │
│  ├─ Prometheus metrics                                   │
│  └─ Real-time dashboard (web)                           │
└─────────────────────────────────────────────────────────┘
```

### 4 Core Trading Strategies

| Strategy | Location | Status | Edge | Notes |
|----------|----------|--------|------|-------|
| **regime_trend** | `strategies/regime_trend.py` | ✅ WORKING | Varies by symbol | 100% WR on ETH/HYPE, 0% on SOL (per-symbol weights critical) |
| **monte_carlo_zones** | `strategies/monte_carlo_zones.py` | ✅ WORKING | ~57% WR | Solo edge in 408 signals (from Apr 28 analysis) |
| **bollinger_squeeze** | `strategies/bollinger_squeeze.py` | ✅ WORKING | 80% WR (solo) | Strong edge when used alone; ensemble weakens it |
| **multi_tier_quality** | `strategies/multi_tier_quality.py` | ✅ WORKING | Mixed | ~50% WR; less consistent than others |
| **confidence_scorer** | `strategies/confidence_scorer.py` | ✅ WORKING | ~50% WR | Meta-strategy, doesn't have standalone edge |

**Key Insight from Memory**: Global strategy weights DON'T WORK. Need per-symbol weights:
- BTC: regime_trend = 0% WR (dead in BTC)
- ETH: regime_trend = 100% WR (perfect in ETH)
- SOL: regime_trend = 0% WR (dead in SOL)
- Same signal can be 100% or 0% depending on symbol

### Ensemble Voting (Strategy Integration)

**Location**: `strategies/ensemble.py`  
**Mode**: Weighted veto (not simple voting)  
**Current Config** (Phase 2):
- min_votes: 1 (accept solo signals - they're profitable)
- veto_ratio: 1.2 (moderate consensus requirement)
- confidence_floor: 55% (main quality filter)

**What We Know Works**:
- Solo bollinger_squeeze signals: 80% WR ✅
- Solo monte_carlo signals: 57% WR ✅
- 2+ strategy agreement: 45-65% WR (varies)
- Single strategy: Often better than consensus

**What Doesn't Work**:
- Multi-tier consensus (2+ vote requirement) - kills profitability
- Global strategy weights - wrong for most symbols
- Confidence floor too low (<50%) - garbage signals leak through
- Confidence floor too high (>70%) - blocks good signals

### LLM 9-Agent System (172 files, 6.7MB)

**Location**: `bot/llm/`  
**Status**: COMPLETE but OFFLINE (API credits exhausted May 1)

**9 Specialist Agents**:
1. **Regime Agent** (Haiku): Market regime classification → output
2. **Trade Agent** (Sonnet): Forms directional thesis + entry decision
3. **Risk Agent** (Haiku): Position sizing based on risk + regime
4. **Critic Agent** (Sonnet): Stress-tests thesis, can veto with counter-thesis
5. **Learning Agent** (Haiku): Extracts lessons from closed trades
6. **Exit Agent** (Haiku): Monitors open positions, recommends exits
7. **Scout Agent** (Haiku): Idle-time preparation (not always active)
8. **Overseer Agent**: System-level decisions (not always active)
9. **Quantitative Brain** (Haiku): Pre-filter based on rules (zero API cost)

**Key Issues from Memory**:
- ✅ Agents are built and all code exists
- ⚠️ "Signal visibility" issue: LLM only sees ~6% of signals (18 filters kill 94%)
- ⚠️ Exit logic doesn't use signal quality (profile selection strategy-based, not quality-based)
- ❌ **Currently disabled** (no API credits since May 1 00:22 UTC)
- ❌ Was never validated in paper trading before going live

**To Restore LLM**:
1. Add $50+ Anthropic API credits
2. Set `.env`: `LLM_MODE=2` (veto-only, conservative)
3. Run: `python run.py paper`

---

## Part 2: What Actually Works Right Now

### ✅ Paper Trading Infrastructure
- **Entry point**: `python run.py paper`
- **Execution**: Simulated order placement + tracking
- **P&L tracking**: `bot/data/trades.csv` (220 rows from Mar-May)
- **Decision logging**: `bot/data/llm/decisions.jsonl` (901 decisions)
- **State files**: Created + restored correctly

### ✅ Backtesting Engine
- **Location**: `bot/backtest/`
- **Usage**: `python run.py backtest [symbol] [days]`
- **Output**: Signal count, WR%, net P&L, Sharpe ratio
- **Known issue**: Backtest-live gap (75% in test, 27% in live on May 1)

### ✅ Data Pipeline
- **CCXT integration**: Multi-exchange data fetching
- **SQLite DB**: Historical OHLCV persistence
- **Supported exchanges**: Bybit, Hyperliquid, Kraken

### ✅ Configuration System
- **Centralized**: `bot/trading_config.py` (1,200 lines)
- **Environment overrides**: `.env` variables work
- **Per-symbol overrides**: Implemented but not always used correctly

### ✅ Safety Gates
- **Code exists**: Circuit breaker, position limits, risk aggregator
- **Issue**: Didn't trigger on May 1 (needs investigation)

### ❌ What's Broken or Untested

| Component | Status | Issue | Evidence |
|-----------|--------|-------|----------|
| **Paper validation pipeline** | ❌ MISSING | Configs never validated in paper before going live | Phase 3.2 backtest→live collapse |
| **Feedback loops** | ⚠️ PARTIAL | "WR poisoning" found Apr 12 and "fixed", but history shows repeated issues | Multiple audit files flag feedback drift |
| **Confidence calibration** | ⚠️ PARTIAL | Apr 11 found 90-100% conf = 22.7% WR (anti-predictive) | feedback_confidence_calibration.md |
| **Circuit breaker** | ⚠️ UNKNOWN | Should have triggered at >5% loss on May 1, didn't | No evidence of triggering |
| **Signal quality scorer** | ⚠️ PARTIAL | Built (184 historical outcomes) but not integrated into exit logic | project_neural_network_audit_2026_04_26.md |
| **Learning loops** | ⚠️ PARTIAL | Code exists but May 1 system had "0 patterns" (no learning) | EMERGENCY_REPORT_APR30.md |
| **Exit Agent** | ⚠️ UNTESTED | Code exists but strategy-based profile selection, not quality-aware | project_neural_network_audit_2026_04_26.md |

---

## Part 3: May 1 Collapse Post-Mortem

### Timeline
- **Apr 30 21:34 UTC**: Phase 3.2 (aggressive config) deployed → LIVE TRADING
- **May 1 00:22 UTC**: API credits exhausted → LLM agents disabled
- **May 1 00:22-14:30**: 205 trades executed on mechanical-only (no LLM guidance)
- **Result**: 27% WR, -$2,186 loss, account liquidated

### Root Cause Analysis

**Primary**: Backtest overfitting + configuration mistake
```
Phase 3.2 Config Changes (Apr 29 23:00 UTC):
- confidence_floor: 65% → 20% (UNSAFE)
- ensemble_confidence_floor: 55% → 20% (UNSAFE)
- ranging_confidence_floor: 68% → 20% (UNSAFE)
- risk_per_trade: 10% → 18% (AGGRESSIVE)
- max_portfolio_leverage: 4.0x → 10.0x (RISKY)

Result:
- Backtest signals: 27 (filtered, mostly quality)
- Live signals: 754 (27x increase, mostly garbage)
- Backtest WR: 75% (trending market conditions)
- Live WR: 27% (consolidating/ranging market)
```

**Secondary**: No paper trading validation
- Phase 3.2 backtest was never tested in paper
- If it had been, would have caught the config error in 1-2 hours
- Instead, went straight to live trading

**Tertiary**: Market regime mismatch
- Backtest was trending (favorable for all strategies)
- Live was choppy/ranging (most strategies fail)
- No multi-regime backtest validation

**Quaternary**: LLM disabled mid-collapse
- API credits ran out
- No LLM guidance to veto bad signals
- System fell back to mechanical ensemble (already broken)

### Evidence Trail

**204-205 trades at May 1 00:22-14:30** (after API credit exhaustion):
- All with `llm_action: "no_llm"` and `llm_confidence: 0.0`
- Confidence levels: 20-80% (mixture due to 20% floor)
- Strategies: All 4 active (due to phase3_2 config)
- Win rate: 27% across all combinations

**Confidence floor is smoking gun**:
- Signals at 20-30% confidence: 10-20% actual WR
- Signals at 50-60% confidence: 45-55% actual WR
- Signals at 80%+ confidence: 50-60% actual WR
- **No calibration at 20% floor**

---

## Part 4: System Complexity & Technical Debt

### Codebase Scale
- **773 Python files** in bot/
- **4.2GB** total (includes data, logs, ML models)
- **Key subsystems**: 
  - LLM: 172 files (massive, 6.7MB)
  - Execution: 45 files
  - Strategies: 25 files
  - Feedback: 22 files

### Areas of High Complexity

| Area | Risk | Notes |
|------|------|-------|
| **LLM 9-agent system** | HIGH | 172 files, many interdependencies, never validated end-to-end in paper trading, "signal visibility" issue |
| **Feedback loops** | HIGH | "WR poisoning" bug was deep (15 files), implies tight coupling, risk of reappearing bugs |
| **Strategy ensemble** | MEDIUM | Works in isolation (tested), but complex voting logic with per-symbol weight multipliers |
| **Risk/leverage gating** | MEDIUM | Multiple layers (circuit breaker, position limits, liquidation calc), inconsistent application |
| **Data pipeline** | LOW | CCXT → SQLite works reliably, no major issues reported |
| **Paper trading** | LOW | Works, but not integrated into validation workflow |

### Technical Debt / Known Issues

From memory and audit history:

1. **Per-symbol strategy weights not applied consistently** (Apr 11, still unfixed?)
   - regime_trend: 0% WR SOL, 100% WR ETH, 0% WR BTC
   - System using global weights instead of per-symbol
   - Causes wrong strategies on wrong symbols

2. **Confidence calibration drifts** (Apr 11-12 found, "fixed", but history shows pattern)
   - 90-100% confidence had 22.7% WR (anti-predictive)
   - System centering on 50% instead of 35% WR
   - Risk of reappearing after manual trades

3. **LLM signal visibility gap** (Apr 12)
   - LLM only sees ~6% of signals
   - 18 filters kill 94% before LLM
   - LLM can't learn patterns it doesn't see

4. **Exit quality mismatch** (Apr 26)
   - Signal quality measured but not used in exit logic
   - Exit profiles strategy-based, not quality-based
   - SHORTs fail because wrong profile selected

5. **Circuit breaker didn't trigger** (May 1)
   - Code exists, but didn't stop trading at >5% loss
   - Unknown: code bug? configuration? execution gap?

---

## Part 5: Safe Recovery Path

### Phase 1: Baseline Operational (IMMEDIATE)
**Time**: 2-3 hours  
**Goal**: Get paper trading working on Phase 2 (known-good baseline)

Steps:
1. ✅ Config reset to Phase 2 (DONE)
2. ✅ Verify config loads (DONE)
3. ⏳ Run 1-hour paper trade test
4. ⏳ Check no crashes, signals generate normally
5. ⏳ Commit recovery documentation

**Expected**: System runs, signals generated, 3-5 trades/hour, 50%+ WR (not 27%)

### Phase 2: Forensic Analysis (TOMORROW, 6-8 hours)
**Goal**: Understand why backtest said 75% but live was 27%

Tasks:
1. **Analyze 205 May 1 trades**
   - By symbol: Which lost most? (BTC -$78, ETH -$1,989, SOL +$4, HYPE -$122)
   - By strategy: Which strategies failed?
   - By confidence: Did 20% conf signals really have 27% WR?
   - By regime: What market conditions were they in?

2. **A/B backtest Phase 2 vs Phase 3.2 on same 60-day window**
   - Run Phase 2 config backtest → Expected: 60-70% WR
   - Switch to Phase 3.2 config → Expected: ~27% WR (matching live)
   - Proves: "Configuration was the problem, not market"

3. **Check circuit breaker code**
   - Why didn't it trigger at >5% loss?
   - Code bug? Misconfiguration? Execution gap?
   - Add logging to verify triggering on next test

4. **Verify backtest methodology**
   - Was fee drag included? (May 1 trades show 14-21% fee drag)
   - Was slippage included?
   - Was look-ahead bias present?

**Expected Findings**: 
- Phase 3.2 config caused collapse (not market conditions)
- Backtest methodology had gaps (fee drag, slippage)
- Circuit breaker has a bug or misconfiguration

### Phase 3: Paper Validation (WEEK 2, ongoing)
**Goal**: Paper trade Phase 2 to confirm 65%+ WR in current market

Process:
1. Run Phase 2 config paper trading
2. Target: 50-100 trades in real-time market conditions
3. Monitor: WR should be 55-65% (Phase 2 baseline)
4. If <50% WR: Something else is wrong (market regime change, strategy degradation)
5. If >65% WR: Edge is still valid, ready for optimization phase

**Success criteria**:
- ✓ 55-65% WR on 50-100 trades
- ✓ No circuit breaker false positives
- ✓ P&L tracking accurate
- ✓ Ready to proceed to Phase 3.2 safe re-entry

### Phase 4: Safe Phase 3.2 Re-Entry (WEEK 2-3)
**Goal**: Get back to Phase 3.2 edge, but with proper validation

**This time, do it right**:
1. **Hypothesis testing** instead of guess-and-check
   - Hypothesis: "Lowering confidence to 30% filters enough"
   - Test in backtest on trending + ranging + volatile
   - Only deploy if >5% improvement on all regimes

2. **Per-trade changes**
   - Only change 1 parameter at a time
   - A/B test against Phase 2 baseline
   - Validate on 60d backtest before paper trading
   - Paper trade 50 trades before considering live

3. **Staged deployment**
   - Phase 2 (proven) → Phase 2.1 (1 change)
   - Paper trade 50 trades
   - Phase 2.1 → Phase 2.2 (2 changes)
   - Continue until Phase 3.2

4. **Multi-regime testing**
   - Trending market: Expect high WR
   - Ranging market: Expect lower WR
   - Volatile market: Expect medium WR
   - System must maintain >50% WR in all regimes

---

## Part 6: Operational Handbook (Going Forward)

### Command Reference

```bash
# Paper trading (simulated)
python run.py paper                    # Start paper trading

# Backtesting
python run.py backtest                 # Default: BTC,ETH,SOL 30d
python run.py backtest --symbols BTC,HYPE --days 60

# One-shot analysis
python run.py signals                  # Generate all signals, exit
python run.py status                   # Market assessment, exit

# Monitoring
tail -f data/trades.csv               # Watch live trades
tail -f data/llm/decisions.jsonl      # Watch LLM decisions
```

### Configuration Management

**Safe Change Process**:
1. Edit `bot/trading_config.py` or set env vars
2. Run: `python cli.py --mode backtest` on 60d baseline
3. Note: Signal count, WR%, net P&L
4. Change 1 parameter
5. Run: `python cli.py --mode backtest` on same 60d
6. Compare: Is new >5% better? On all market regimes?
7. If YES: Paper trade 50 trades before live
8. If NO: Revert

**Do NOT**:
- Change >1 parameter at a time
- Go live after backtest (always paper trade first)
- Skip multi-regime testing
- Use global strategy weights (per-symbol required)

### Key Metrics to Monitor

**Daily**:
- Win rate (target: 55%+ on Phase 2, 65%+ target on Phase 3.2)
- P&L (should be positive over 7d rolling window)
- Drawdown (circuit breaker should trigger at >5% daily loss)

**Weekly**:
- Strategy breakdown (which strategies executing most? WR?)
- Symbol breakdown (which symbols profitable? which toxic?)
- Confidence distribution (should be >50% for most trades)
- Circuit breaker triggers (count them)

**Monthly**:
- Win rate trend (should be stable or improving)
- Sharpe ratio (should be >1.0 for real money)
- Max drawdown (should never exceed 10%)
- Strategy weights drift (should reflect performance)

---

## Part 7: Decision Framework

### "Is This Safe to Deploy?"

Before ANY config change goes to live trading, ask:

1. **Backtest validated?** ✅ (60d, trending + ranging + volatile)
2. **Paper traded?** ✅ (50+ trades, 55%+ WR)
3. **Single parameter change?** ✅ (not multiple)
4. **A/B tested?** ✅ (vs known-good baseline)
5. **Multi-regime tested?** ✅ (trending, ranging, volatile all >50% WR)
6. **Circuit breaker tested?** ✅ (triggers correctly)
7. **Per-symbol weights correct?** ✅ (not global)

If ANY is ❌: Do NOT deploy.

---

## Part 8: Key Learnings from History

### What the Memory Files Show

**Recurring Patterns** (seen multiple times):
1. **Backtest-live gap**: BTC works in backtest, fails live (happens repeatedly)
2. **Feedback loop bugs**: "Fixed" Apr 12 (WR poisoning), but subsequent audits show issues persisting
3. **Paper trading skipped**: Multiple times configs went live without paper validation
4. **Confidence calibration drifts**: Tracked and "fixed" but history suggests fragility
5. **Per-symbol strategy weights ignored**: Multiple audits flag this, system still doesn't use it

**What Eventually Worked**:
- **Mechanical gating** (Apr 27-28 Phase A breakthrough): regime + setup + hour filters → +252% improvement
- **Quality > quantity**: 12 perfect trades beat 37 mediocre ones
- **Per-symbol approach**: Acknowledging different symbols need different rules
- **LLM as agent** (not oracle): Agent system had better separation of concerns

**What Didn't Work**:
- **Global strategy weights**: Different symbols = different edge
- **High leverage aggressively**: Magnifies losses too quickly
- **Skipping paper trading**: Backtest doesn't reflect live conditions
- **Complex feedback loops**: "Fixed" bugs keep reappearing (tight coupling)

---

## Conclusion: Next Steps

**Immediate** (Next 2 hours):
1. Run 1-hour paper trade test with Phase 2 config
2. Verify: No crashes, signals generate, confidence >50%
3. Commit recovery documentation

**Today** (Next 6-8 hours):
1. Forensic analysis: Why did Phase 3.2 backtest 75% but live 27%?
2. A/B backtest to prove configuration was the problem
3. Check circuit breaker code

**This Week**:
1. Paper trade Phase 2 for 50-100 trades (target: 55-65% WR)
2. Plan safe Phase 3.2 re-entry (hypothesis-driven, not guess-and-check)
3. Implement per-symbol strategy weights (if not already done)
4. Restore LLM system (with API credits)

**Key Commitment**: NEVER skip paper trading again. It's the validation gate.

---

**Document created**: May 6, 2026 (post-collapse audit)  
**Config state**: Phase 2 baseline (safe)  
**System state**: Ready to paper trade, forensics needed, recovery underway
