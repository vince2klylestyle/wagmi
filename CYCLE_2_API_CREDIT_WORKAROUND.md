# CYCLE 2 BLOCKER: API Credit Exhaustion + Workaround

## Issue Found
Bot reached credit exhaustion during second restart at ~17:01-17:02 UTC:
```
[MULTI-AGENT] overseer agent API call FAILED: Credit balance is too low
[MULTI-AGENT] scout agent API call FAILED: Credit balance is too low
```

This caused bot to exit after ~90 seconds.

## Root Cause
LLM agents (overseer, scout) were attempting API calls despite user's explicit CLI-based setup to avoid API consumption.

## Applied Workaround
Restarted bot with **LLM_MODE=0** (OBSERVER mode):
- Disables all LLM agent pipeline
- Runs purely mechanical strategies + ensemble voting
- No API calls required
- Focuses validation on Phase 3 ensemble voting logic (what we need to test)

```bash
LLM_MODE=0 python run.py paper > logs/bot_llm_disabled.log 2>&1 &
```

## Why This Works
Phase 3 ADX-aware voting logic is **mechanical** (not LLM-dependent):
1. Regime detection → ADX values
2. ADX mapping → min_votes calculation
3. Ensemble voting → signal pass/fail
4. Phase 3 filters → applied to passing signals

Our fix is purely in steps 1-3, which don't require LLM agents.

## Expected Behavior (Third Run)
With LLM disabled:
- Bot should run indefinitely (no API calls)
- Regime detection fires every cycle
- Strategies generate signals every few cycles
- Ensemble evaluates signals using FIXED min_votes (from ADX mapping)
- PHASE3-DEBUG logs appear showing:
  - `cached_adx` from regime (5.0, 8.0, 32.0, etc.)
  - `effective_min_votes` correctly set (1 for choppy, 2 for trending)
  - `Phase 3 ADX-aware min_votes` transition logs
- Solo signals now pass ensemble voting
- Phase 3 filters evaluate and pass/reject
- Trades execute

## Validation Checklist

- [ ] Bot runs >5 minutes (no API calls)
- [ ] PHASE3-DEBUG logs appear
- [ ] cached_adx matches regime expectations
- [ ] effective_min_votes = 1 for high_volatility/range
- [ ] "Phase 3 ADX-aware" logs appear
- [ ] trend_breakout solo signals pass ensemble
- [ ] Phase 3 filter logs appear
- [ ] At least 1 trade executes
- [ ] Win rate tracking shows signs of improvement

---

**Status**: WORKAROUND APPLIED, MONITORING ACTIVATION
**Time**: Third run starting ~17:03:30 UTC
**Monitoring**: task btn51iif1 (180s timeout)

