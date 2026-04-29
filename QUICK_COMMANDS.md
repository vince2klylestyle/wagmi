# WAGMI Trading System - Quick Commands Reference

## Current Status (April 29, 2026)

### Phase 3 Status ✅
- **Confidence Floor**: Lowered from 69% → 20% ✅
- **monte_carlo_zones**: Re-enabled as solo strategy ✅
- **SOL SHORT micro-filter**: 75% → 65% ✅
- **BTC LONG micro-filter**: 80% → 70% ✅
- **Expected Impact**: 3-5x signal throughput increase (4 → 150-300 trades per 60d)

### System Status
- **Paper Trading**: Live (Phase 3 active)
- **Real Candles Loop**: KB v642.6+ (continuously optimizing)
- **Fresh Validated Loop**: KB v1296.0+ (validation baseline)
- **Autonomous Loops**: Both running continuously

---

## Watch System Live (Pick One)

### Option 1: Interactive Dashboard (Recommended)
```bash
# Real-time trading activity
python cli_monitor.py live

# Market analysis & agent decisions
python cli_monitor.py analysis

# Signal rejections breakdown
python cli_monitor.py signals

# Agent reasoning/thinking
python cli_monitor.py thinking

# System health & metrics
python cli_monitor.py health

# Everything combined
python cli_monitor.py full
```

### Option 2: Stream Raw Logs
```bash
# Watch logs update in real-time
tail -f /tmp/phase3_live_paper.log

# Follow with filtering
tail -f /tmp/phase3_live_paper.log | grep "SIGNAL\|TRADE\|GATE"
```

### Option 3: Signal Watcher (Real-time thoughts)
```bash
# Stream what system is thinking about the market
bash watch_signals.sh

# Or with custom refresh rate (5 second example)
bash watch_signals.sh 5
```

---

## Quick Health Checks

### Is paper trading running?
```bash
ps aux | grep "python.*run.py paper"
# Should show a running process. If empty, it crashed.
```

### How many trades have we executed?
```bash
grep -c "TRADE EXECUTED" /tmp/phase3_live_paper.log
```

### What's the current P&L?
```bash
tail -1 /tmp/phase3_live_paper.log | grep "daily_pnl"
```

### Which gate is rejecting most signals?
```bash
# Count rejections by type
grep "REJECTED" /tmp/phase3_live_paper.log | grep -o "gate=[^ ]*" | sort | uniq -c
```

### Is Phase 3 config active?
```bash
grep "confidence_floor.*20" bot/strategies/ensemble.py && echo "✓ Phase 3 Active"
```

---

## Analyze Performance

### Win rate over last N trades
```bash
tail -20 /tmp/phase3_live_paper.log | grep "pnl=" | grep -c "\$[0-9]" && echo "Wins" || echo "Losses"
```

### Signal conversion rate (what % become trades)
```bash
signals=$(grep -c "SIGNAL" /tmp/phase3_live_paper.log)
trades=$(grep -c "TRADE EXECUTED" /tmp/phase3_live_paper.log)
echo "Conversion: $((trades * 100 / signals))%"
```

### Trading volume by symbol
```bash
grep "TRADE EXECUTED" /tmp/phase3_live_paper.log | grep -o "[A-Z]\{3,4\}" | sort | uniq -c
```

### Average confidence on executed trades
```bash
grep "TRADE EXECUTED" /tmp/phase3_live_paper.log | grep -o "confidence=[0-9.]*" | cut -d= -f2 | awk '{sum+=$1; count++} END {print sum/count}'
```

---

## Troubleshooting

### Paper trading crashed
```bash
# Check the error
tail -50 /tmp/phase3_live_paper.log | grep -E "ERROR|Exception|Traceback"

# Restart
cd bot && python run.py paper
```

### No signals generating
```bash
# Check regimes are being classified
tail -100 /tmp/phase3_live_paper.log | grep "\[REGIME\]" | wc -l

# Should see 4+ regime lines. If 0, data fetching is broken.
```

### All signals rejected at confidence floor
```bash
# Lower floor even more (temporary)
# Edit: bot/strategies/ensemble.py, change confidence_floor to 10
# Then restart trading
cd bot && python run.py paper
```

### LLM agent failing
```bash
# Check for API errors
grep "API.*FAILED\|Traceback" /tmp/phase3_live_paper.log | tail -5

# System falls back to monolithic LLM, so trading still works
# But less optimized
```

---

## Monitoring During Trading (Your Workflow)

### Every 15 minutes
```bash
python cli_monitor.py live
# • Are signals being generated?
# • Are trades executing?
# • Any error messages?
```

### Every hour
```bash
python cli_monitor.py signals
# • Which gates are most active?
# • What's the execution rate?
# • Any anomalies?
```

### Every 4 hours
```bash
python cli_monitor.py full
# • Full system audit
# • Check P&L trend
# • Verify agent quality
```

---

## Understanding the Autonomous Loops

### Real Candles Loop (KB v642+)
- Tests KB accuracy on REAL Hyperliquid data
- Currently: GO trades 50% WR, SKIP trades 22% WR
- Finding: threshold 45 = 33.6% WR on 143 trades
- **Meaning**: Best decision rule = "GO when KB says go with threshold 45"

### Fresh Validated Loop (KB v1296+)
- Tests new KB versions on recent data
- Currently: 0 fresh trades (waiting for paper trading results)
- Will activate once paper trading generates 30-day data
- **Purpose**: Ensure no data leakage in backtests

### Large Analysis Loop (KB v1169+)
- Analyzes full historical dataset
- Currently: 25.4% baseline win rate (607K wins / 1.78M losses)
- Continues refining edge detection
- **Purpose**: Identify patterns that work across all market conditions

---

## Phase 3 Validation Checklist

Track these metrics over next 48 hours:

| Metric | Target | Status |
|--------|--------|--------|
| Total signals | 50+ | Count: grep -c "SIGNAL" /tmp/phase3_live_paper.log |
| Executed trades | 5-10 | Count: grep -c "TRADE EXECUTED" /tmp/phase3_live_paper.log |
| Signal conversion | > 2% | Calculate from above |
| Daily P&L | Positive | Last: tail -1 /tmp/phase3_live_paper.log \| grep daily_pnl |
| Win rate | > 50% | Count wins: grep pnl /tmp/phase3_live_paper.log \| grep -c "\\$[0-9]" |

---

## Key Files

| File | Purpose |
|------|---------|
| `bot/strategies/ensemble.py` | Core gating logic (Phase 3 config) |
| `/tmp/phase3_live_paper.log` | Paper trading live log |
| `bot/data/decisions.jsonl` | All signals, trades, thoughts |
| `bot/data/kb_v642+_*.json` | Real candles KB versions |
| `bot/data/kb_v1296+_*.json` | Fresh validated KB versions |

---

## Next Actions

### Immediate (now)
1. **Choose your monitoring tool**: `python cli_monitor.py live` is easiest
2. **Watch for 15-30 minutes** to see signal flow
3. **Check paper trading restarted** properly

### Short-term (next 12 hours)
1. Monitor signal generation rate
2. Verify gates are rejecting signals (not executing everything)
3. Check first 10-20 trade P&L

### Medium-term (24-48 hours)
1. Collect 20-50 live trades
2. Analyze symbol/setup breakdown (which combos are profitable?)
3. Identify if any thresholds need further adjustment

### Phase 4 (after 50-100 trades)
1. Measure profit factor by symbol-side combo
2. Implement profit factor gating (reject PF < 1.0)
3. Optimize micro-filter thresholds based on live data

---

## Tips for Manual Trading With System

If you want to use system insights for manual trading:

```bash
# 1. Watch signal generation in real-time
python cli_monitor.py thinking

# 2. When a signal appears, review the agent reasoning
# (OBSERVE → RECALL → REASON → DECIDE → JUSTIFY)

# 3. Check current market regime
python cli_monitor.py analysis

# 4. If regime matches signal strategy, execute manually
# If regime conflicts, skip

# 5. Log result in system for learning
# (system auto-logs everything)
```

System is designed for autonomous trading but can feed manual trading with higher-quality signals.

---

## Support

**Lost?** Review [MONITORING_GUIDE.md](MONITORING_GUIDE.md) for detailed explanations.

**Metrics confusing?** Check the analysis at end of each log file for interpretation.

**System behaving weird?** Check `/tmp/phase3_live_paper.log` for ERROR/Exception entries.
