# Remote Work Setup Checklist — May 11, 2026

## ✅ System Status (Pre-Verified)
- Python: 3.14.3 ✓
- .env file: EXISTS ✓
- requirements.txt: EXISTS ✓
- Project root: C:\Users\vince\WAGMI PROJECT\WAGMI ✓

## 📋 SETUP STEPS (Run These First When Connected)

### Step 1: Install Dependencies (2-3 min)
```powershell
cd "C:\Users\vince\WAGMI PROJECT\WAGMI"
pip install -r bot/requirements.txt --upgrade
```

### Step 2: Validate Installation (1 min)
```powershell
cd bot
python -c "import ccxt, anthropic; print('✓ Dependencies OK')"
```

### Step 3: Restart Bot with TIME_STOP Fix (CRITICAL)
```powershell
cd bot
python run.py paper
```
Monitor for 30-60 min:
- [ ] Trade execution (expect 0.8-1.6 trades/hour)
- [ ] Regime field in logs
- [ ] TIME_STOP timeout (should be 1h, not 2h)
- [ ] No errors in console output

---

## 🚀 IF DEPENDENCIES ALREADY INSTALLED

Skip Step 1-2, go straight to **Step 3**:
```powershell
cd "C:\Users\vince\WAGMI PROJECT\WAGMI\bot"
python run.py paper
```

---

## 📊 MONITORING COMMANDS (While Bot Runs)

In a **separate PowerShell window**:

### Check Latest Signals
```powershell
# Last 10 signals
Get-Content "bot\data\signal_outcomes.jsonl" | ConvertFrom-Json | Select-Object -Last 10 | ft timestamp, symbol, side, confidence, passed
```

### Check Trade Execution
```powershell
# Count trades in last hour
$cutoff = (Get-Date).AddHours(-1).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss')
Get-Content "bot\data\trades.csv" | ConvertFrom-Csv | Where-Object {$_.entry_time -gt $cutoff} | Measure-Object
```

### Monitor Logs in Real-Time
```powershell
Get-Content -Path "bot\data\bot.log" -Tail 20 -Wait
```

---

## 🔍 IF BOT FAILS TO START

Check these in order:
1. **Python Path**: `python run.py` should work from bot/ directory
2. **Missing Dependency**: Install with `pip install -r requirements.txt`
3. **API Key Missing**: Check `.env` has ANTHROPIC_API_KEY (can be empty/test key)
4. **Config Error**: Check `bot/trading_config.py` for syntax errors
5. **Port Already In Use**: Check if another bot instance is running

### Emergency Troubleshoot
```powershell
# Kill any stray bot processes
Get-Process python | Where-Object {$_.CommandLine -like '*run.py*'} | Stop-Process -Force

# Check for lock files
ls "bot/data/*.lock"

# Clean startup
cd bot
python run.py paper 2>&1 | head -50
```

---

## 📞 KEY FILES TO MONITOR

**Real-Time Signals**: `bot/data/signal_outcomes.jsonl`
- New line per signal decision
- Fields: timestamp, symbol, side, confidence, passed, hard_rej

**Trade Execution**: `bot/data/trades.csv`
- Row per executed trade
- Fields: entry_time, exit_time, symbol, side, pnl

**System Logs**: `bot/data/bot.log`
- Continuous debug output
- Search for: ERROR, TRADE, SIGNAL, GATE

**Memory/Learning**: `bot/data/llm/llm_memory.json`, `bot/data/llm/deep_memory/`
- Agent learning state
- Hypothesis tracking

---

## 🎯 SUCCESS CRITERIA (After Restart)

You'll know the fixes worked when:
✅ Bot starts cleanly (no import errors)
✅ Signals appear in signal_outcomes.jsonl within first 5 min
✅ Regime field populated (not null)
✅ Trade execution rate > 0.5/hour (vs. 0.2/hour baseline)
✅ Average hold time < 60 min (vs. 160 min baseline)

If you see these → continue monitoring for 1 hour, then review metrics.

---

## 📝 NEXT ACTIONS AFTER BOT VALIDATES

**If metrics improve** (trade velocity up, regime coverage up):
1. Document baseline metrics
2. Run test suite: `pytest tests/ -k "ensemble or strategy"`
3. Proceed to soft-reject gate audit (CYCLE 8 blocker)

**If metrics DON'T improve**:
1. Check bot logs for errors
2. Verify TIME_STOP value in trading_config.py (line 350)
3. Verify regime backfill in signal_outcomes.jsonl
4. Escalate with detailed error logs
