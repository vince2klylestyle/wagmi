# Laptop Claude Autonomous Loop
**Runs independently every 60 minutes**

## What This Does
- Monitors bot health via logs and ledger
- Detects issues (stalls, low profit, data loss)
- Fixes problems autonomously (code, config, cleanup)
- Improves performance (optimize settings, learn from trades)
- Reports status to desktop via inbox

## Loop Cycle (60 min)

### Phase 1: Check Status (5 min)
```
1. Read bot logs (last 1h)
2. Check ledger for recent trades
3. Read desktop's latest handshake entries
4. Detect any issues or anomalies
```

### Phase 2: Diagnose (10 min)
```
If issue detected:
  - Analyze root cause
  - Check git history for related fixes
  - Determine fix severity
```

### Phase 3: Fix (20 min)
```
If fixable:
  - Write code fix
  - Commit to historical-import-2026-05-30
  - Push to GitHub
  - Notify desktop via inbox
```

### Phase 4: Analyze & Learn (15 min)
```
- Parse decisions.jsonl for agent behavior
- Check trade outcomes
- Identify patterns (what works, what doesn't)
- Update deep_memory if needed
```

### Phase 5: Report (10 min)
```
- Write status to inbox
- Tag as [STATUS], [FIX-AVAILABLE], or [ALERT]
- Let desktop pick up findings next cycle
```

## Issues to Watch For
- Bot stalled >5 min
- Trades not executing (signals but no positions)
- Extreme slippage (>5%)
- Memory files corrupted
- Database growing too fast
- Unusual agent decisions (all skips, all goes, etc.)

## Fixes Available (Priority Order)
1. Config corruption → restore from git
2. LLM timeout → fallback to Haiku
3. Data corruption → rebuild from logs
4. Memory bloat → cleanup old records
5. Strategy performance drift → recalibrate

## Safety Rules
- NEVER force-push to main
- NEVER delete production data
- NEVER disable safety gates
- Test all fixes in code before pushing
- Always commit with clear message

## Communication
- Write to: `coordination/INBOX_LAPTOP_TO_DESKTOP.md`
- Read from: `coordination/INBOX_DESKTOP_TO_LAPTOP.md`
- Handshake: for detailed discussions
- Push to: `historical-import-2026-05-30` branch

---

**Status:** Ready to activate
**Schedule:** Every 60 minutes via ScheduleWakeup
**Owner:** Laptop Claude (autonomous analysis)
