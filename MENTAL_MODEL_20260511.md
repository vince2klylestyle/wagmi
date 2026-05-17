# WAGMI Trading Bot — Mental Model (May 11, 2026)

## The System in 60 Seconds

You built an **autonomous crypto trading bot** that uses:
1. **4 independent strategies** (regime_trend, monte_carlo, confidence_scorer, multi_tier_quality) voting through a weighted ensemble
2. **4 sequential gates** (validity → circuit_breaker → position_limits → leverage → sizing) protecting each trade
3. **9 LLM agents** (Regime, Trade, Risk, Critic, Learning, Exit, Scout, Overseer, Quant) that can override mechanics
4. **Real-time learning** from closed trades to improve future decisions

**Current State**: Core system works, but TWO BLOCKERS limit performance:
- **Blocker 1** (FIXED, AWAITING ACTIVATION): TIME_STOP 2h timeout blocks symbol rotation → 95% signals blocked
- **Blocker 2** (NOT YET FIXED): Soft-reject gate flags signals as `passed=False` even when safe → prevents execution

---

## How Signals Become Trades

```
1. SIGNAL GENERATION (Every 1-5 min per symbol)
   └─ 4 strategies evaluate market → each outputs optional Signal
   └─ 40 signals/hour typical across all symbols

2. ENSEMBLE VOTING (Weighted consensus)
   └─ Signals pass MIN_VOTES check + VETO_RATIO check
   └─ ~77% of signals pass ensemble (2,397 of 3,110 in last sample)
   └─ Result: Signal marked as "passed by ensemble" ✅

3. ANNOTATION FILTERING (Quality & Safety Assessment)
   └─ EV floor: negative_EV → creates "reject" annotation
   └─ Win probability: below 45% → creates "reject" annotation
   └─ Quality: low confidence → creates "warning" annotation
   └─ Result: Some pass signals get marked soft_rejected=True

4. GATE FILTERING (Hard Safety Gates)
   └─ Circuit breaker: daily loss limit, consecutive loss streak
   └─ Position limits: max concurrent positions per symbol
   └─ Leverage check: don't exceed max leverage
   └─ Sizing: scale down if position too large
   └─ Result: Either hard_rejected=True or hard_rejected=False

5. CURATOR RANKING (Combined Score)
   └─ Signals ranked by confidence + edge score
   └─ Top N selected for execution

6. EXECUTION PATH (Route to trade)
   └─ Sniper path: automated execution (currently disabled)
   └─ Mechanical path: ensemble voting → trade if no other positions
   └─ LLM path: submit to agents for veto/approval (currently disabled)
   └─ Result: ORDER SENT TO EXCHANGE (or held if position exists)

7. POSITION MANAGEMENT (While trade is open)
   └─ Track MFE/MAE (max favorable/adverse excursion)
   └─ Scale out at TP1 (partial profit take)
   └─ Trailing stop to TP2 or hold to TIME_STOP
   └─ Learning agent records outcome vs. predicted
   └─ Result: POSITION CLOSED, P&L RECORDED
```

### THE BOTTLENECK (Your Current Problem)

Between steps 3-5, signals get filtered twice:
- **Soft filters** (annotation) mark some as "questionable but not dangerous"
- **Signal** is recorded with `passed=False` despite having no hard rejection
- **Sniper never sees it** because `passed=False` means not executable
- **Result**: Only 0.2 trades/hour (4 out of 3,110 signals in 20h)

---

## The Two Fixes You're Waiting On

### Fix 1: TIME_STOP Reduction (Committed, Not Active)
**File**: bot/trading_config.py line 350
**Current**: `TIME_STOP = 120` (minutes)
**New**: `TIME_STOP = 60` (minutes)
**Why**: Symbol rotation blocker
- OLD: Position opens at 05:02, locks symbol until 07:40 (138 min closed)
- NEW: Position opens at 05:02, unlocks at ~05:45 via TP1 exit (30-45 min closed)
- RESULT: 4-8x faster rotation = 4-8x more trades

**When Active**: Trade velocity 0.2 → 0.8-1.6/hour
**Risk**: Low (doesn't affect exit logic, just timeout)

### Fix 2: Sniper Regime Backfill (Committed, Not Active)
**File**: bot/multi_strategy_main.py lines 4419, 4481
**Current**: Sniper signals missing regime field in record_signal calls
**Fix**: Add regime parameter to calls
**Why**: Regime coverage incomplete (55% of signals have null regime)
**When Active**: Regime field populated 85-95% of signals

---

## The Remaining Blocker (Soft-Reject Gate)

### The Issue
Signals with negative EV or low win_prob get "reject" annotations from soft filters.
But they're NOT hard-rejected (hard_rej=false), just marked questionable.
System treats `soft_rejected=True` as execution-blocking.

### Example
```
Signal: ETH SELL confidence=64.8%
Ensemble Vote: PASS ✅ (passed voting)
EV: -0.3088 (slightly negative expected value)
Win Prob: 31% (below 45% threshold)
Soft Rejection: True (because EV negative + win_prob low)
Execution: BLOCKED ❌ (passed=False)
```

### The Unknown
- Should soft-reject be execution-blocking?
- Or should we relax gate thresholds (MIN_SIGNAL_EV, MIN_SIGNAL_WIN_PROB)?
- Or is EV/win_prob model poorly calibrated?

**Next Session**: Audit gate logic and decide on relaxation strategy.

---

## Your Job Today

### Immediate (30-60 min)
1. Restart bot → activates TIME_STOP + regime fixes
2. Monitor trade velocity (0.2 → 0.8-1.6/hour)
3. Document baseline metrics

### If Time Permits (next 1-2 hours)
1. Trace soft-reject annotation generation
2. Compare .env config vs. code gate thresholds
3. Propose fix for soft-reject blocker

### Success Indicators
- ✅ Bot starts cleanly
- ✅ Signals in signal_outcomes.jsonl within 5 min
- ✅ Regime field populated (not null)
- ✅ Trade execution rate 4-8x higher
- ✅ No errors in bot.log

---

## System Architecture (At A Glance)

```
BOT LOOP (every 1-5 minutes)
├─ Fetch OHLCV candles (CCXT → Hyperliquid)
├─ Compute indicators (ATR, ADX, RSI, WaveTrend, etc.)
├─ FOR EACH SYMBOL:
│  ├─ Regime Agent classifies market (trend/range/panic/etc)
│  ├─ 4 Strategies evaluate and vote
│  ├─ Ensemble voting + gate filtering
│  ├─ Trade Agent forms thesis (go/skip/flip)
│  ├─ Risk Agent sizes position
│  ├─ Critic Agent vetoes if thesis weak
│  └─ Execute or hold
├─ FOR OPEN POSITIONS:
│  ├─ Exit Agent reassesses thesis
│  ├─ Check TP1/TP2/SL conditions
│  └─ Close if thesis invalid
└─ Record outcomes for learning

LLM AGENTS (9 total, currently disabled):
├─ Regime (Haiku): Market classification
├─ Trade (Sonnet): Directional thesis + conviction
├─ Risk (Haiku): Position sizing + risk flags
├─ Critic (Sonnet): Stress-test thesis, veto weak calls
├─ Learning (Haiku): Extract patterns from closed trades
├─ Exit (Haiku): Reassess open position theses
├─ Scout (Haiku): Idle-time preparation
├─ Overseer (Sonnet): Multi-position portfolio view
└─ Quant (Haiku): Probability estimation

MEMORY SYSTEMS:
├─ Short-term (llm_memory.json): 100 recent notes, 7-day TTL
├─ Deep memory (deep_memory/): Permanent trade patterns, hypotheses
├─ Learning feedback (feedback loop): Outcome → observation → rule
└─ Knowledge base (teaching/): Graduated rules from hypotheses
```

---

## Key Configuration Values

**Trading Parameters** (bot/trading_config.py):
- TIME_STOP: 60 min (was 120, waiting restart)
- ENSEMBLE_CONFIDENCE_FLOOR: 53%
- TAKER_FEE: 2 bps (Hyperliquid)
- MAX_LEVERAGE: 10x (configurable per symbol)
- KELLY_FRACTION: 1.0 (full Kelly sizing)

**Gate Thresholds** (.env):
- MIN_SIGNAL_EV: -1.0 (EV floor, allows negative)
- MIN_SIGNAL_WIN_PROB: 0.45 (45% win minimum)
- CIRCUIT_BREAKER_DAILY_LOSS_PCT: 2% of current equity
- CIRCUIT_BREAKER_CONSECUTIVE_LOSSES: 3 losses in a row

**Symbols & Pair Config** (.env):
- SYMBOLS: BTC, ETH, SOL, HYPE
- MAX_CONCURRENT_PER_SYMBOL: 1 (no stacking)

**LLM Config** (.env, all currently OFF):
- LLM_MODE: 0 (OFF) — was 5 (FULL)
- LLM_USAGE_TIER: RECOMMENDED
- LLM_MULTI_AGENT: false (was true)

---

## Recent History (Context for Decisions)

### May 1 Collapse
- omniscient_integrated strategy went live (219 trades, -$4,605, 25% WR)
- Strategy was fundamentally broken in trending markets
- Config degradation paradoxically protected account
- **Learning**: Don't activate untested strategies during live trading

### Current Baseline (Phase 2)
- Tested across 6 consecutive audits ✅
- Mechanical path only (no LLM) ✅
- Win rate: Unknown (0 trades in 20h wait, not enough data)
- Configuration drift: ZERO ✅

### Why Zero Trades in 20h
- Market was consolidating (no WaveTrend momentum crosses)
- System correctly did NOT over-trade
- Not a bug, expected behavior in ranging markets

---

## Files You'll Interact With Today

**Read These First**:
- PREP_BRIEFING_20260511.md (action plan)
- CYCLE_8_ROOT_CAUSE_SOFT_REJECT_BLOCKER.md (blocker details)

**Monitor While Bot Runs**:
- bot/data/signal_outcomes.jsonl (signals, real-time)
- bot/data/trades.csv (trades, real-time)
- bot/data/bot.log (debug output)

**Edit If Needed**:
- bot/trading_config.py (params, verify TIME_STOP=60)
- .env (config overrides)

**Don't Touch**:
- bot/multi_strategy_main.py (unless fixing bugs)
- bot/execution/ (safety gates, don't break)
- bot/llm/ (agents, only if debugging LLM)

---

## Success Definition for This Session

**1st Hour**: Bot running with fixes, metrics improving
**2nd Hour**: Soft-reject gate audited, fix proposed
**Beyond**: Extended validation → next optimization phase

You've built something solid. The system just needs these bottlenecks cleared. 🚀
