# 🎯 OPUS - START HERE

**Status:** Everything pushed to GitHub  
**Your Mission:** Prove the signals work (or fix them)  
**Timeline:** 2 weeks for validation  
**Success Criteria:** **55%+ win rate on major symbols**

---

## 🚀 IMMEDIATE ACTIONS (Today)

### 1. Pull Latest Code
```bash
cd ~/WAGMI
git pull origin main
```

### 2. Start the Bot (Paper Trading)
```bash
python bot/run.py paper
```

Expected output:
```
✅ Bot starting in PAPER mode
✅ CCXT initialized with 3 exchanges
✅ Scanning every 60 seconds...
```

Let it run. It will:
- Fetch market data from Kraken, Bybit, Hyperliquid
- Run 4 strategies in parallel
- Generate buy/sell signals
- Log everything to CSV files

### 3. Check Daily Performance (In separate terminal)
```bash
python bot/performance_reporter.py
```

Expected output:
```
Trades Today:     0 (it just started)
Win Rate:         -
Net P&L:          $0
```

As trades accumulate, you'll see metrics.

### 4. What You're Validating
Run this at **end of week 2**:
```bash
python -m backtest.runner --days 30
```

This shows:
- How signals performed on **historical data** (last 30 days)
- Compare to **actual paper trades** (did we trade as predicted?)
- If they match → signals are predictive ✅
- If they diverge → something broke ⚠️

---

## 📊 YOUR 2-WEEK PLAN

### Week 1: Collect Data
- **DO:** Let bot run continuously
- **DO:** Check `performance_reporter.py` daily
- **DO:** Watch `/logs/bot_*.csv` accumulating
- **GOAL:** Generate 20+ trades

### Week 2: Validate & Decide
- **DO:** Run backtest on day 10
- **DO:** Analyze which signals made money
- **DO:** Compare paper trades to backtest
- **DECISION:** 
  - Win rate ≥ 55%? → **READY FOR LIVE**
  - 50-55%? → **Iterate one more week**
  - < 50%? → **Debug what broke**

---

## 📁 Key Files You'll Use

```bash
# START HERE - daily commands
QUICK_REFERENCE.md                      

# UNDERSTAND THE SYSTEM - how it all works
ARCHITECTURE_AND_OPERATIONS_GUIDE.md    

# YOUR TASKS - what you need to do
IMPLEMENTATION_SUMMARY_FOR_OPUS.md      

# FUTURE WORK - what comes next
MASTER_IMPROVEMENT_PLAN.md              
```

---

## 💻 Daily Commands (Just 3)

```bash
# 1. Keep running continuously
python bot/run.py paper

# 2. Check stats once per day
python bot/performance_reporter.py

# 3. Watch logs for errors
tail -f logs/bot_$(date +%Y%m%d).log
```

---

## 🎯 Success Criteria

After 2 weeks, check:

| Metric | Target | What It Means |
|--------|--------|---------------|
| **Trades** | 50+ | Enough data |
| **Win Rate** | ≥55% | More wins than losses |
| **Profit Factor** | ≥1.2 | Wins outweigh losses |
| **Backtest Match** | ±5% | Signals are predictive |
| **Crashes** | 0 | System stable |

**If all pass → READY FOR LIVE TRADING** ✅

---

## ⚠️ If Things Go Wrong

### No trades opening?
```bash
tail logs/bot_*.log | grep "ERROR\|WARN"
# Check exchange connectivity
```

### Win rate dropping?
```bash
python bot/performance_reporter.py --symbol BTC
# Which symbols are failing? 
# Run specific analysis
```

### Bot crashed?
```bash
cat logs/bot_*.log | tail -50
# Check last 50 lines for the error
```

---

## 📚 What Exists Now

✅ **Core Bot** (4-strategy ensemble)  
✅ **Trade Logging** (every signal saved)  
✅ **Performance Tracking** (daily stats)  
✅ **Backtesting** (historical validation)  
✅ **Health Monitoring** (auto-alerts)  
✅ **Complete Documentation** (architecture guide included)  

---

## 🎓 If You Want to Understand the System

Read in this order:

1. **QUICK_REFERENCE.md** (5 min) — What commands to run
2. **ARCHITECTURE_AND_OPERATIONS_GUIDE.md** (30 min) — How everything works
3. **IMPLEMENTATION_SUMMARY_FOR_OPUS.md** (20 min) — What was built, what's next
4. **MASTER_IMPROVEMENT_PLAN.md** (45 min) — Future enhancements

---

## 🔥 The Real Question

**Is the bot profitable?**

That's it. Everything else is just measuring whether it is.

- The **trade logger** shows you every signal
- The **performance reporter** shows you the win rate
- The **backtest runner** proves it was predictive
- The **signal validator** shows which types of signals work

**Your job:** Run it for 2 weeks and answer that one question.

---

## 🚀 Right Now

```bash
# Do this NOW:
cd ~/WAGMI
python bot/run.py paper

# Then in another terminal:
python bot/performance_reporter.py

# That's it. Let it run.
```

Come back in 2 weeks with the answer: **Profitable or not?**

---

**Prepared by:** Claude (Haiku)  
**For:** Claude Opus  
**Date:** February 10, 2026  
**Status:** ✅ Ready to validate
