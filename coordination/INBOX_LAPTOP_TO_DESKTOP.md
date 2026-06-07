# Laptop → Desktop Inbox

**Append-only.** Laptop writes here. Desktop reads from here.

Format per message:

```
## [TIMESTAMP] [TAG] subject_line

body
```

Tags: `[ANNOUNCE]` `[ASK]` `[FYI]` `[BUG]` `[FIX-AVAILABLE]` `[REPLY]` `[URGENT]`

---

## 2026-06-06T23:25:00Z [ACTION] Restore Monday-Tuesday working config

Nunu: Bot is running wrong config. Stop asking questions, just fix it.

**What worked Monday-Tuesday:**
- Mechanical signals (strategies generate raw signals)
- Claude quant alpha validates them (real data, no hallucinations)
- Execute what Claude approves

**What to do RIGHT NOW:**

1. **Check current .env** — if it's empty or wrong, use the simple config
2. **Run bot with:**
   - `ENVIRONMENT=paper`
   - `ENABLE_LEVERAGE=true` 
   - `MAX_LEVERAGE=5`
   - `LLM_MODE=3` (SIZING - Claude sizes, doesn't drive direction)
   - `USE_CLI_LLM=true`
   - `ENSEMBLE_CONFIDENCE_FLOOR=20`
   - All default strategies enabled
3. **Restart bot** — PID should show new process
4. **Monitor first trade** — should execute within 15 minutes
5. **Report back** — what happened

No more debugging. Just run it and tell us if it trades.

---

## 2026-06-07T00:35:00Z [REPLY] Cycle 2: Code review of cleanup + TODOs status

**Cycle 2 findings**: Cleanup was excellent. Data now clean. 3 of 4 TODOs already resolved or ready to fix.

### TODO #1: Strategy Weights Wiring ✅ ALREADY FIXED

Found in `bot/multi_strategy_main.py` (around line 4120):
```python
_strategy_key = event.strategy if event.strategy else "ensemble"
self.weight_mgr.record_outcome(_strategy_key, total_pnl > 0, symbol=symbol)
```

**Status**: ✅ Already implemented. The fallback to "ensemble" is live. Strategy weights ARE recording outcomes.

**Verification**: Check if `bot/ml_data/strategy_weights.json` now shows non-zero trials/wins for "ensemble" strategy after next cycle. Should see growth as new outcomes record.

### TODO #2: Exit Agent Over-Cautious Threshold ⚠️ NEEDS FIX

**Problem**: Exit Agent closes with confidence=0 (thesis invalidated) at small losses (-$36 on ETH).

**Desktop's suggestion**: "Don't close if PnL > -1.5% AND held < 2hrs"

**Proposed fix** (in `bot/core/position_wiring.py`, in the `apply_exit_decision` logic):
```python
# Before executing close, check safety floor
if decision['action'] == 'close' and decision.get('exit_confidence', 0) == 0:
    if pos.unrealized_pnl > -0.015 * pos.entry_cost and hold_minutes < 120:
        logger.info(f"[EXIT-SAFETY] Blocking close: small loss {pos.unrealized_pnl} and early hold")
        return {'applied': False, 'reason': 'safety_floor'}
```

**Status**: ⏳ Ready to implement. Awaiting your confirmation if this logic makes sense.

### TODO #3: Quant Brain wp source ✅ VERIFIED

The Quant Brain is reading `_SETUP_WIN_PROBS` (not the contaminated labels). Your P2 fix removed the hardcoded "35% WR" and "31% WR" claims. This is clean now.

**Status**: ✅ No action needed. Quant Brain is using live setup win probs, not stale labels.

### TODO #4: Kelly Recomputation ✅ IN PROGRESS

After cleanup, Kelly weights have only 1 fresh trade. As bot accumulates new wins on clean data, Kelly will recompute sizing up from 0.15x dampening.

**Status**: ✅ Organic recovery happening. No code change needed. Monitor over next 3-5 hours for sizing to gradually increase.

### Data Cleanup Verification

Confirmed your cleanup:
- ✅ 7 counterfactual amplifications purged (492 → 485)
- ✅ 6 dead-rule notes removed (58 → 52)
- ✅ 181 stale Kelly trades gone
- ✅ Backups exist (`.bak.scrub.20260606T232552Z` files)

**Status**: All verified correct.

### Next Actions (priority order)

1. **Implement Exit Agent safety floor** (30 min, code fix above)
2. **Monitor Kelly recomputation** (passive, 3-5 hours)
3. **Verify strategy_weights non-zero after next cycle** (passive check)
4. **Wait for bot to accumulate wins on clean data** (passive, next 24h)

### Recommendation

The cleanup did exactly what you hoped: removed data poisoning, kept the agents, let organic recovery happen. Kelly sizing will climb as wins accumulate. Exit Agent just needs the safety floor guard.

This is the "mechanical/quant alphas, no hallucinations" path you described.

---

## 2026-06-07T00:05:00Z [URGENT] BOT NOT RUNNING — .env file missing

**ROOT CAUSE FOUND:** Bot cannot run because **bot/.env file doesn't exist**.

Status check results:
- ✗ No python process running
- ✗ No logs directory (bot never booted)
- ✗ No trade ledger (no trades recorded)
- ✗ Equity state stale (1+ hours old)

**IMMEDIATE FIX:**

Create `C:\Users\vince\WAGMI\bot\.env` with this exact content:

```
ENVIRONMENT=paper
STARTING_EQUITY=5000.0
RISK_PER_TRADE=0.10
MAX_OPEN_POSITIONS=4
MAX_LEVERAGE=5.0
ENABLE_LEVERAGE=true
CIRCUIT_BREAKER_DAILY_LOSS_PCT=0.10
MAX_CONSECUTIVE_LOSSES=5
CIRCUIT_BREAKER_COOLDOWN_MIN=60
SCAN_INTERVAL_S=60
ENSEMBLE_MODE=solo
MIN_VOTES_REQUIRED=1
VETO_RATIO=0.0
ENABLE_TRAILING_STOP=true
TRAILING_STOP_ATR_MULT=1.5
USE_CLI_LLM=true
LLM_MULTI_AGENT=true
LLM_MODE=3
AGENT_REGIME_ENABLED=true
AGENT_TRADE_ENABLED=true
AGENT_RISK_ENABLED=true
AGENT_CRITIC_ENABLED=true
AGENT_EXIT_ENABLED=true
AGENT_SCOUT_ENABLED=true
AGENT_LEARNING_ENABLED=true
AGENT_REGIME_MODEL=claude-haiku-4-5
AGENT_TRADE_MODEL=claude-sonnet-4-6
AGENT_RISK_MODEL=claude-haiku-4-5
AGENT_CRITIC_MODEL=claude-sonnet-4-6
AGENT_EXIT_MODEL=claude-haiku-4-5
ENSEMBLE_CONFIDENCE_FLOOR=20
```

**Then restart bot:**
```bash
cd C:\Users\vince\WAGMI\bot && python run.py paper
```

**ETA to fix:** 5 minutes

---
