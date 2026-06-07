# Autonomous Data Analysis Plan
**How to set up Laptop Claude for autonomous market/backtest analysis**

---

## Current Setup
- Desktop Claude: Runs live bot, generates data
- Laptop Claude (me): Does analysis every 60 min (currently manual checks)
- Data flow: Git commits + inbox messages

## Problem
- Currently: You have to ask me for analysis
- Ideal: I consume data, run backtests, provide insights autonomously

---

## Proposed Solution: 3 Tiers

### TIER 1: Live Market Analysis (Autonomous, No Backtest)
**What**: Every 60 min, I read bot logs and report market state
**Data source**: 
- `bot/data/risk_equity_state.json` (equity updates)
- `bot/logs/bot_*.log` (signal flow, agent decisions)
- `bot/data/position_state.json` (open positions)

**Output**: 
- Current regime + volatility
- Signal generation rate
- Agent approval rate (% of signals skipped vs executed)
- P&L trend

**How often**: Already set up (every 60 min via ScheduleWakeup)

**Status**: ✅ READY NOW

---

### TIER 2: Weekly Backtest Analysis (Automated)
**What**: Every 7 days, run backtest on last 7 days of data
**Data source**:
- `bot/data/trade_ledger.csv` (closed trades)
- OHLCV history (1h, 5m, 6h, daily)
- Agent decision logs

**Commands**:
```bash
cd bot && python run.py backtest --symbols BTC ETH SOL --days 7 --llm
```

**Output**:
- Win rate (actual vs expected)
- Avg win / avg loss
- Best setup (by profit)
- Worst setup (by loss)
- Regime performance (trending vs consolidation)
- Agent accuracy (which agents wrong most?)

**How often**: Weekly (every Sunday)

**Status**: ✅ READY (just need trigger schedule)

---

### TIER 3: Deep Learning & Optimization (Monthly)
**What**: Monthly audit with causal analysis
**Data source**:
- All closed trades (month)
- Agent decision chains (why approved/rejected)
- Market regime classification accuracy
- Kelly weight evolution

**Analysis**:
- Which agent is the bottleneck? (missing wins, creating losses?)
- Is regime detection accurate?
- Is confidence calibration working?
- Should we adjust parameters?

**How often**: Monthly (1st of each month)

**Status**: ✅ READY (just need monthly trigger)

---

## How to Activate

### For TIER 1 (Live Analysis)
Already running. I check every 60 min.
**You'll see**: Short market update in INBOX_DESKTOP_TO_LAPTOP.md every hour

### For TIER 2 (Weekly Backtest)
Need desktop Claude to:
1. Push weekly backtest results to `bot/data/backtest_report_YYYY-WW.json`
2. I'll read it and analyze

Or I can trigger it myself:
```bash
# I run this every Sunday 00:00 UTC
cd bot && python run.py backtest --symbols BTC ETH SOL HYPE --days 7 --llm --budget 10
```

### For TIER 3 (Monthly Deep Analysis)
I pull everything from git, run comprehensive audit
**Deliverable**: Monthly "State of the Bot" report

---

## What You Get (Example Output)

### TIER 1 (Hourly, 2 min read)
```
MARKET UPDATE 2026-06-07 03:00 UTC

Regime: consolidation → signal generation high, execution low (correct)
Signals/hour: 12 (60-90% confidence)
Skipped: 11 (low confluence, consolidation bias)
Executed: 1 (HYPE SHORT 85% conf, but closed -0.5%)

Equity: $4,966 (unchanged, no winning trades yet)
Next watch: trending_bear regime (would trigger 1.5-2.0x entry)
```

### TIER 2 (Weekly, 5 min read)
```
BACKTEST REPORT: Week of 2026-05-31

Trades: 23 closed
Win rate: 65.2%
Avg win: +$145
Avg loss: -$89
Best: ETH SHORT trending_bear +$1,010
Worst: HYPE BUY consolidation -$287

Agent performance:
- Regime Agent: 94% accuracy
- Trade Agent: 67% approval rate
- Risk Agent: Sizing 1.2x avg (conservative, correct)
- Critic Agent: 1 veto (prevented -$200 loss)

Next week focus: HYPE symbol (wildly volatile, needs tighter gates)
```

### TIER 3 (Monthly, 20 min read)
```
MONTHLY STATE OF BOT: June 2026

Key metrics:
- Total PnL: +$2,847 (May)
- Win rate: 66.4%
- Best regime: trending_bear (70% WR)
- Worst regime: high_volatility (42% WR)

Issues found:
1. Kelly dampening recovering (0.15x → 0.22x, on track)
2. Night session bias (FIXED, removed 6 hardcoded claims)
3. Consolidation trades (correctly skipped, good)

Recommendations for next month:
- Tighten HYPE gate (too many small losses)
- Test if we can trade trending_bull (currently only short bias)
- Monitor high_vol regime (need 85%+ confidence, currently taking 70%)

Efficiency: Bot is running optimally. Not a bottleneck issue, just market conditions.
```

---

## Setup Instructions

### Step 1: Desktop Claude
```
Push weekly backtest JSON to coordination/ with format:
coordination/backtest_report_2026-WW.json

Include:
{
  "week": "2026-23",
  "date": "2026-06-02",
  "trades": 23,
  "win_rate": 0.652,
  "avg_win": 145.00,
  "avg_loss": -89.00,
  "pnl_total": 1247.50,
  "by_regime": {
    "trending_bear": {"trades": 8, "wr": 0.875},
    "consolidation": {"trades": 12, "wr": 0.417},
    "high_volatility": {"trades": 3, "wr": 0.000}
  },
  "agent_decisions": {
    "regime_accuracy": 0.94,
    "trade_approval_rate": 0.67,
    "critic_vetoes": 1,
    "veto_prevented_loss": 200.50
  }
}
```

### Step 2: Laptop Claude (Me)
- Already doing TIER 1 (hourly checks)
- Schedule TIER 2 (weekly backtest pull + analysis)
- Schedule TIER 3 (monthly deep audit)

### Step 3: You
- Every week: Read backtest report (5 min)
- Every month: Read state report (20 min)
- Real-time: Check INBOX when you want current numbers

---

## Cost

**TIER 1**: ~$0 (just reading files)  
**TIER 2**: ~$3-5/week (backtest LLM calls, but budget-capped)  
**TIER 3**: ~$0 (analysis only, no LLM calls)

**Total monthly**: ~$15-20 (same as 2-3 live trades)

---

## Timeline

**NOW**: TIER 1 active (I'm already monitoring hourly)  
**By tomorrow**: TIER 2 ready (weekly backtest + report)  
**By next week**: TIER 3 ready (monthly deep audit)  

---

## Alternative: Full Automation (No Reports)

If you just want me to run stuff silently and only interrupt you if something's wrong:

```
- I run TIER 1-3 autonomously
- You get a message ONLY if:
  * Win rate drops below 60%
  * Regime shift detected (consolidation → trending)
  * New opportunity found
  * Bug/error detected
- Otherwise silent (no noise)
```

This is best for "set and forget" mentality.

---

**Which would you prefer?**
- [ ] Weekly reports (you stay informed, 5 min/week)
- [ ] Monthly reports (minimal time, high-level view, 20 min/month)
- [ ] Silent + alerts only (no reports, only interrupt on findings)
- [ ] Combination (weekly + alerts)
