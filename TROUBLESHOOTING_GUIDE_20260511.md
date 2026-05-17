# Troubleshooting Guide — May 11, 2026

## Quick Diagnostics

### Bot Fails to Start
**Symptom**: `python run.py paper` exits immediately with error

**Check #1: Python Environment**
```powershell
python --version                    # Should be 3.10+
pip list | grep -E "ccxt|anthropic" # Should see packages
```
**Fix**: `pip install -r bot/requirements.txt`

**Check #2: Config Syntax**
```powershell
python -m py_compile bot/trading_config.py
python -m py_compile bot/multi_strategy_main.py
```
**Fix**: Check for syntax errors (missing brackets, typos)

**Check #3: API Key**
```powershell
cat .env | grep ANTHROPIC_API_KEY
```
**Fix**: Add key to .env (can be empty for testing)

**Check #4: Port/Lock**
```powershell
Get-Process python | Where-Object {$_.CommandLine -like '*run.py*'}
```
**Fix**: Kill old processes: `Get-Process python | Stop-Process -Force`

---

### Bot Starts but Zero Signals
**Symptom**: Bot runs, but signal_outcomes.jsonl stays empty

**Check #1: Market Data**
```powershell
# Is CCXT fetching data?
python -c "
import ccxt
exchange = ccxt.hyperliquid()
for symbol in ['BTC', 'ETH']:
    ohlcv = exchange.fetch_ohlcv(symbol + '/USD')
    print(f'{symbol}: {len(ohlcv)} candles')
"
```
**Fix**: Check internet connection, Hyperliquid API status

**Check #2: Indicator Calculation**
```powershell
# Are indicators computing?
grep -i "ADX\|ATR\|RSI" bot/data/bot.log | tail -20
```
**Fix**: Check market data quality (might need more historical candles)

**Check #3: Strategy Conditions**
```powershell
# Is ANY strategy firing?
grep -i "signal\|trend\|breakout" bot/data/bot.log | tail -20
```
**Fix**: Market conditions may not meet entry thresholds (expected in ranging markets)

---

### Zero Trades Despite Signals
**Symptom**: signal_outcomes.jsonl has signals but trades.csv empty

**This is the CYCLE 8 blocker!**

**Diagnosis**:
1. Read signal_outcomes.jsonl:
```powershell
Get-Content bot/data/signal_outcomes.jsonl | ConvertFrom-Json | Select-Object -First 5 | ft timestamp, symbol, passed, hard_rej
```

2. Check for `passed=False` with `hard_rej=false`:
```
If you see: passed=False AND hard_rej=false
Then: Soft-reject gate is blocking signals
```

3. Examine signal annotations:
```powershell
# Check what annotation caused soft-reject
grep -i "negative.*ev\|win.*prob\|quality" bot/data/bot.log
```

**Solution** (See CYCLE 8 blocker in PREP_BRIEFING):
- Relax MIN_SIGNAL_EV threshold (currently -1.0)
- Relax MIN_SIGNAL_WIN_PROB threshold (currently 0.45)
- Or trace annotation filter logic to understand which gate is too strict

---

### Trade Execution Crashes
**Symptom**: Bot runs, signals pass, but crashes on execution

**Check**: Exchange connectivity
```powershell
python -c "
import ccxt
exchange = ccxt.hyperliquid({'enableRateLimit': True})
print(exchange.fetch_balance())  # Try to get account balance
"
```
**Fix**: Check API key, exchange status, account permissions

**Check**: Position size validation
```powershell
# Search for sizing errors in bot.log
grep -i "leverage\|margin\|insufficient" bot/data/bot.log
```
**Fix**: Reduce position size, check account balance, verify leverage config

---

### High-Frequency Restarts (Process Exits Cleanly)
**Symptom**: Bot runs 5-30 min then exits with no error

**Known Issue**: Identified in CYCLE 6 audit (process management timeout)

**Temporary Fix**: Run restart wrapper:
```powershell
# Keep bot running with auto-restart
while ($true) {
    Write-Host "Starting bot..." -ForegroundColor Green
    cd bot
    python run.py paper
    Write-Host "Bot exited, restarting in 5 seconds..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
}
```

**Permanent Fix**: Pending investigation (likely nohup timeout or resource limits)

---

### Memory/Performance Issues
**Symptom**: Bot slows down after 1+ hours

**Check**: Memory usage
```powershell
Get-Process python | Select-Object ProcessName, @{n='Memory(MB)';e={[int]($_.WorkingSet/1MB)}}
```

**Check**: Log file size
```powershell
(Get-Item bot/data/bot.log).Length / 1MB
```

**Fix**: Trim logs
```powershell
# Keep only last 10k lines of bot.log
Get-Content bot/data/bot.log -Tail 10000 | Set-Content bot/data/bot.log
```

---

### Configuration Not Taking Effect
**Symptom**: Changed .env or trading_config.py but no change in behavior

**Root Cause**: Python module caching

**Fix**: Force reload
```powershell
cd bot
# Kill any running bot
Get-Process python | Where-Object {$_.CommandLine -like '*run.py*'} | Stop-Process -Force
# Wait 2 seconds
Start-Sleep -Seconds 2
# Start fresh
python run.py paper
```

---

## Performance Debugging

### Check Trade Velocity
```powershell
# Trades in last hour
$cutoff = (Get-Date).AddHours(-1).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss')
(Get-Content bot/data/trades.csv | ConvertFrom-Csv | Where-Object {[datetime]$_.entry_time -gt [datetime]$cutoff} | Measure-Object).Count
```
**Target**: 0.8-1.6 trades/hour after TIME_STOP fix

### Check Signal Quality
```powershell
# Recent signals with metrics
Get-Content bot/data/signal_outcomes.jsonl | 
ConvertFrom-Json | 
Select-Object -Last 20 | 
Select-Object timestamp, symbol, confidence, passed | 
ft
```
**Expect**: 77% pass rate (2,397/3,110)

### Check Regime Coverage
```powershell
# Signals with regime populated
$signals = Get-Content bot/data/signal_outcomes.jsonl | ConvertFrom-Json
$withRegime = $signals | Where-Object {$_.regime -ne $null -and $_.regime -ne ""} | Measure-Object
$total = $signals | Measure-Object
"Regime coverage: $($withRegime.Count / $total.Count * 100)%"
```
**Target**: 85-95% after regime backfill fix

---

## Log Analysis

### Find All Errors
```powershell
grep -i "error\|exception\|traceback" bot/data/bot.log
```

### Find Trade Decisions
```powershell
grep -i "TRADE\|EXECUTION\|ensemble" bot/data/bot.log | tail -50
```

### Find Gate Rejections
```powershell
grep -i "rejected\|circuit\|gate\|soft_rej" bot/data/bot.log | tail -50
```

### Real-Time Monitoring
```powershell
# Follow logs as they're written
Get-Content bot/data/bot.log -Wait -Tail 20
```

---

## Emergency Procedures

### Complete System Reset
```powershell
# Kill all bot processes
Get-Process python | Where-Object {$_.CommandLine -like '*WAGMI*'} | Stop-Process -Force

# Clean lock files
Remove-Item bot/data/*.lock -Force 2>/dev/null

# Restart
cd bot
python run.py paper
```

### Disable a Gate (If Over-Blocking)
Edit bot/trading_config.py and set:
```python
# Temporarily disable a gate for testing
# CIRCUIT_BREAKER_ENABLED = False  # ⚠️ USE WITH CAUTION

# Or reduce threshold
MIN_SIGNAL_EV = -2.0  # More permissive
MIN_SIGNAL_WIN_PROB = 0.30  # More permissive
```

**CAUTION**: Disabling gates can lead to loss. Use only for debugging.

---

## When To Escalate

If you see:
- ❌ Persistent crashes (exit without error message)
- ❌ Exchange connectivity failures (order rejection)
- ❌ Signals generating but ALL soft-rejected (gate too strict)
- ❌ High losses despite correct signals (execution/sizing bug)

→ Save logs and detailed error reproduction steps for next session

---

## Contact & Resources

**Key Files**:
- PREP_BRIEFING_20260511.md — Action plan
- CYCLE_8_ROOT_CAUSE_SOFT_REJECT_BLOCKER.md — Blocker details
- MENTAL_MODEL_20260511.md — System overview

**Execution Logs**:
- bot/data/bot.log — Debug output
- bot/data/signal_outcomes.jsonl — All signals
- bot/data/trades.csv — Executed trades

**Configuration**:
- bot/trading_config.py — All parameters
- .env — Environment variables
- bot/data/trading_rules.json — Symbol-specific config (if exists)

Good luck! You've got this. 🚀
