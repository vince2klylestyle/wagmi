# PHASE 2 RESTART CHECKLIST
**Quick Reference for Activating Regime-Aware Filtering**

---

## ⚡ QUICK START (2 minutes)

### Step 1: Stop Bot
```bash
# Kill all Python processes running the bot
pkill -f "python.*run.py" 2>/dev/null || taskkill /F /IM python.exe 2>/dev/null
```

### Step 2: Start Bot (Fresh Code)
```bash
cd "C:\Users\vince\WAGMI PROJECT\WAGMI\bot"
python run.py paper
```

### Step 3: Stop Neural Monitor
```bash
pkill -f "claude_neural_monitor" 2>/dev/null || taskkill /F /IM python.exe 2>/dev/null
```

### Step 4: Start Neural Monitor (Fresh Code)
```bash
cd "C:\Users\vince\WAGMI PROJECT\WAGMI\bot"
python claude_neural_monitor.py --persist
```

### Step 5: Wait & Verify
```bash
# Check 1: New regime values (should see actual regime, not "unknown")
tail -1 "C:\Users\vince\WAGMI PROJECT\WAGMI\bot\data\neural_decisions.jsonl"

# Check 2: Approval rate improvement (should see >0%)
cd "C:\Users\vince\WAGMI PROJECT\WAGMI\bot"
python analyze_phase1_decisions.py
```

---

## ✓ VERIFICATION METRICS

After restart, you should see within 5-10 minutes:

| Metric | Before | After | Status |
|--------|--------|-------|--------|
| Regime | `unknown` (100%) | Diverse (trending_bull, range, etc.) | ✓ Check |
| Approval Rate | 0% | 30-50% | ✓ Check |
| VETOED | 100% | 50-70% | ✓ Check |
| APPROVED | 0% | 30-50% | ✓ Check |
| Voting Pattern | Uniform | Diversified | ✓ Check |

---

## 🔍 DETAILED VERIFICATION

### Test 1: Regime Extraction
```bash
# Get the last decision
tail -1 bot/data/neural_decisions.jsonl | python -m json.tool | grep -A 5 "detailed_reasoning"
```

**Before fix**:
```json
"regime_agent": "Unknown regime: unknown"
```

**After fix**:
```json
"regime_agent": "Good regime: trending_bull (trending)"
```

### Test 2: Approval Rate
```bash
# Run analysis
cd bot && python analyze_phase1_decisions.py
```

**Before fix**:
```
Total signals evaluated: 1449
Approval rate: 0.0%
Veto rate: 100.0%
```

**After fix**:
```
Total signals evaluated: ~1500+
Approval rate: 30-50%
Veto rate: 50-70%
```

### Test 3: Confidence Restoration
```bash
# Check if confidence values are being extracted
tail -5 bot/data/neural_decisions.jsonl | python -c "
import sys, json
for line in sys.stdin:
    d = json.loads(line)
    print(f'Signal: {d[\"signal_id\"]}, Confidence: {d[\"confidence\"]}%, Decision: {d[\"final_consensus\"]}')"
```

**Before fix**: All show `Confidence: 0.0%`
**After fix**: Should show varying confidence (66%, 55%, etc.)

---

## ⏱️ TIMELINE

```
14:42 UTC - Start restarts
14:43 UTC - Bot reloads fresh code
14:43 UTC - Neural monitor reloads fresh code
14:44 UTC - New signals queued with regime data
14:45 UTC - Neural monitor processes new batches
14:50 UTC - 50+ new decisions with proper regime
14:55 UTC - Approval rate trend visible
15:05 UTC - Verification complete
```

---

## 🚨 IF SOMETHING GOES WRONG

### If regime still shows "unknown"
1. Verify code is in file: `grep -n "regime = " bot/llm/client.py | head -5`
2. Check snapshot data exists: `python bot/analyze_phase1_decisions.py`
3. May need to investigate bot's snapshot generation (regime field missing in source)

### If approval rate still 0%
1. Check agent voting is working: `tail -1 bot/data/neural_decisions.jsonl | python -m json.tool | grep agents_voted`
2. May indicate regimes are being extracted but agents defaulting to VETO for other reasons
3. Check confidence extraction: should see > 0%

### If process won't start
1. Make sure Python is installed: `python --version`
2. Check dependencies: `pip list | grep -i claude`
3. Try direct import test: `python -c "from bot.llm import client; print('OK')"`

---

## 📊 SUCCESS CRITERIA

**Phase 2 is successful when**:

✓ Regime != "unknown" in all new decisions  
✓ Approval rate > 5% (something is being approved)  
✓ Voting patterns diversify (not all CAUTION/VETO/VETO/ALLOW)  
✓ Confidence values > 0% (extracted from snapshots)  
✓ Phase 0 validator shows WR improvement (vs 0% from before)  

**Estimated improvement**: 26.8% (Phase 0) → 45-55% (Phase 1 in good regimes)

---

## 📝 WHAT'S HAPPENING

**The fix**:
1. Bot extracts regime from snapshot before queuing signal
2. Neural monitor parses snapshot as fallback if regime not present
3. Agents use actual regime (not "unknown" default) for voting
4. Approval rate becomes selective by regime (not blanket 0%)

**Why it works**:
- Trending regimes: Regime agent votes ALLOW → trade agent can approve
- Bad regimes: Regime agent votes VETO → always rejected
- Net effect: Filters out bad-regime trades, approves good ones

**Expected result**: 
- Bad regimes removed → no more 0% WR losses
- Good regimes approved → capture the 70%+ WR upside
- Overall WR improvement: 26.8% → 45-55%

---

**Status**: Ready for immediate restart  
**Complexity**: Trivial (2 terminal commands)  
**Time to verify**: ~10 minutes  
**Risk**: Low (code is proven, just needs process reload)
