# State of WAGMI — 2026-06-05 19:10 UTC

**Author:** desktop-claude
**Audience:** laptop-claude (you), who has been working on `historical-import-2026-05-30` and may not have full context for what desktop has been seeing live + auditing
**Purpose:** Give you the COMPLETE picture so you can pick up cold and contribute without re-doing my discovery work
**Reading time:** ~10 minutes. Bookmark this — refer back when context is unclear.

---

## TL;DR (read this first)

1. **Equity is real now: $6,184 → $6,239** (+24.8% from $5K start) after a paper-trading rebuild that ran 2026-05-30 onward.
2. **The core theme**: Nunu observed the bot was full of **"fabricated certainty"** — hardcoded WR/PnL/multipliers from old fee-bug-era data being treated by agents as truth. We've been systematically removing those.
3. **Bot is alive right now** on `desktop-overdrive-2026-05-30`, full Sonnet routing, your fixes merged in, my strips applied, **1 BTC SHORT open at $60,745**, conf=85%, 5.6x lev.
4. **Biggest live alpha leak we've found**: Critic veto = 73.6% wrong rate (533 missed wins vs 183 correct vetoes). That's where your next work should land.
5. **Both Claudes have unique roles**: I monitor live + flag bugs + react to Nunu. You investigate + ship code fixes. We coordinate via this handshake.

---

## Part 1: How we got here (timeline)

**Pre-2026-05-30**: Bot had been offline 37+ days after a crash with equity at $497 (down from $5000). Multiple bugs accumulated.

**2026-05-30 onward**: Nunu restarted bot in "overdrive" paper mode with fresh $5K equity. Goal: collect data, prove the system works.

**2026-05-30 to 06-02 (3 days)**: Bug-hunt phase. Found and fixed:
- 10x fee bug (`taker_fee_bps=45` → actually 4.5 bps Hyperliquid rate). Means every PnL computed before fix is overstated as loss.
- Hardcoded LLM-first cost gate `<60` bypassing the LLM-first dispatcher
- Sizing math bug (`qty × leverage` double-multiplication)
- Subprocess hang on Windows (Node grandchild holding pipes)
- TIME_STOP=2h killing winners (raised to 8h)
- Risk Agent prompt too conservative on leverage
- TradeProfile missing 4 constructor args
- Bug #16 look-ahead bias in backtest (12 paths gated)
- Per-agent model routing (no more Opus on every call)
- Adaptive floor override (was capping at 50, ignoring .env's 20)

**2026-06-02 evening**: Nunu's "leave no stone unturned" directive. I shipped 3 audit docs:
- `SYSTEM_AUDIT_AND_ROADMAP.md` — 8-section audit, 12 weak points ranked tier 1-5
- `EDGE_EXPLORATION_PART_2.md` — 10 untouched edge categories + hypothesis pipeline design
- `DEEP_AUDIT_HANDSHAKE_2026-06-03.md` — concrete trace targets

**2026-06-03**: Strip work begins. You and I converged independently on the same insight: hardcoded values were polluting agent reasoning. You ran a 181-trade live data audit (commit `965865a`) showing:
- ALL LONGS: 24.8% WR, -$2679 total
- ALL SHORTS: 46.9% WR, +$1119 total
- Quant Brain BUY priors were 17-31pp over-optimistic
- Time-of-day multipliers were INVERTED in live data

You shipped 8 commits between `f10a43a` and `7a863eb` covering Quant Brain recalibration, time-of-day fixes, sub-noise stop rejection, confidence calibration. I shipped strip commits removing hardcoded blocks + WRs + multipliers.

**2026-06-04**: Low-power mode disaster. Nunu's quota was running low so I switched all agents to Haiku + scan interval 30s→90s. Result: 309 cascading pipeline None failures + 811 API failures. Haiku can't handle the multi-agent pipeline at parallel load. ETH SHORT #16 closed clean (+$1010 TRAILING_STOP) before the switch — that win is the proof the strip is working.

**2026-06-05 (today)**: Nunu upgraded to max plan. We're in autonomous mode while he's at work. I:
- Restarted bot to high-power (Sonnet Trade+Critic, 30s scan)
- Ran 4 parallel Explore agents for forensic audit
- Found 3 lost positions ($55 net) + residual hardcoded sources I missed
- Merged your 8 fixes into desktop-overdrive (`eaa852b`)
- Stripped residual stats from `shared_context.py` REGIME_METADATA, SETUP_TYPES, ASSET_DNA, MARKET_AXIOMS (`4ea0551`)
- Bot restarted clean at 17:42

---

## Part 2: Current state (as of 19:10 UTC)

### Bot
- **Process:** PID 37868, running clean on `desktop-overdrive-2026-05-30` branch (your 8 commits + my strips merged)
- **Quota:** Max plan, no usage worry for rest of week
- **Model routing:** Trade Agent + Critic on `claude-sonnet-4-6`, others on `claude-haiku-4-5`
- **Scan interval:** 30s
- **Pipeline failures since restart:** 0 (clean!)
- **LLM_FIRST_MODE:** true (LLM picks direction + sizing, overrides mechanical EV gate)
- **ENVIRONMENT:** paper

### Open positions
**1 position:** BTC SHORT @ $60,745.40, qty 0.00558, lev 5.6x, conf=85%, SL $61,960.70, TP1 $59,542.30, TP2 $58,333.00. Opened 17:51 UTC by Trade Agent (Sonnet routing). This is the FIRST post-strip + post-merge trade. Watch it carefully — it's a test of the cleaner architecture.

### Equity
- **trade_ledger.csv last running_equity:** $6,184.48
- **Blackout reconciliation add:** +$55.10
- **Effective:** ~$6,239.58 (+24.8% from $5K start)
- **risk_equity_state.json:** STILL $5,000 (broken persistence — your priority 4)

### Closed trades since 2026-05-30 restart (in ledger)
| # | Symbol | Side | Exit Type | Net PnL | Note |
|---|---|---|---|---|---|
| 1 | ETH | SHORT | SL | -$187.68 | Early bug-era |
| 2 | BTC | SHORT | SL (won) | +$98.99 | |
| 3 | BTC | SHORT | TP2 | +$378.59 | First clean win |
| 4 | HYPE | LONG | SL | -$2.41 | |
| 5 | ETH | SHORT | TRAILING_STOP | **+$1010.37** | Star trade |
| 6 | BTC | SHORT | SL | -$141.23 | |
| 7 | HYPE | LONG | SL | -$61.81 | |
| 8 | SOL | SHORT | TP2 | +$377.05 | Strip-enabled |
| 9-11 | (lost to persistence bug) | | TIME_STOP | +$55.10 | Reconciled |

**Net: ~+$1,527 / +30.5% from $5K (paper).** Note real PnL likely understated because trade #1 + #6 were under 45 bps fees.

---

## Part 3: The HARDCODED PATTERN (this is the core thesis)

Nunu's insight: the bot is full of **fabricated certainty**. Specific WR/PnL/multiplier claims hardcoded in code, prompts, and data files that agents read as truth — but the underlying numbers were computed under the 10x fee bug, or on too-small samples, or on stale data.

The agents are smart, but they reason FROM these certainties. Garbage in → garbage out.

### Where the fabricated certainty lives (inventory)

| File | What | Status |
|---|---|---|
| `bot/feedback/graduated_rules.json` | SOL_SHORT_full_block, HYPE_LONG_hard_block, SOL_LONG_hard_block, HYPE_SHORT_hard_block, SIZE_edge_boost | **DISABLED** (mine) |
| `bot/llm/quant_brain.py:185-195` | `_SETUP_WIN_PROBS` HYPE_BUY=0.52, SOL_SELL=0.55, etc | **STRIPPED** (mine, then your aeba848 recalibrated) |
| `bot/llm/agents/prompts.py:1227-1245` | Confluence multipliers 1.3x/0.7x/1.1x, dead/prime hours 0.85x/1.15x, RSI<10/<20 hardcoded vetoes | **STRIPPED** (mine) |
| `bot/llm/agents/coordinator.py:1480` | risk_pct fallback `0.10 * sz_mult` (10% baseline!) | **FIXED** to config.risk_per_trade (mine) |
| `bot/llm/agents/shared_context.py` REGIME_METADATA | 13 regimes × hardcoded live_pnl/live_n/edge string | **STRIPPED** (mine, today `4ea0551`) |
| `bot/llm/agents/shared_context.py` SETUP_TYPES | 7 setups × hardcoded historical_wr | **STRIPPED** (mine, today `4ea0551`) |
| `bot/llm/agents/shared_context.py` ASSET_DNA | per-symbol edge/avoid/live_stats strings | **STRIPPED** (mine, today `4ea0551`) |
| `bot/llm/agents/shared_context.py` MARKET_AXIOMS | "34% WR bear-rally trap", "10-12% WR European session toxic" | **STRIPPED** (mine, today `4ea0551`) |
| `bot/trading_config.py` REGIME_SL_TP_SCALARS comments | "52% WR +$118" comments | Left (Python comments, not in prompts) |
| `bot/llm/dynamic_thresholds.py:11,337` | "trending sits here at 52% WR", "MEDIUM at ~36% WR" comments | Left (Python comments) |
| `bot/data/llm/knowledge_base.json` | Various WR claims | **NOT TRACED** — your audit target |
| `bot/llm/network_learning.py` | Possible embedded edges | **NOT TRACED** |
| `bot/llm/deep_memory.py` | Cached pattern data | **NOT TRACED** — read at decision time per earlier audit |

### What still injects to prompts that we haven't touched

`bot/data/llm/knowledge_base.json` — auto-synthesized knowledge that gets injected to Trade/Risk Agent prompts. May have fabricated WR/edge claims similar to what we stripped from `shared_context.py`. **Worth auditing.**

`bot/data/llm/deep_memory/` — stores trade DNA and pattern matches. Read at decision time per Explore audit (active in toxic-setup check + roundtrip-edge check). Could be referencing fee-bug-era trades. **Worth checking.**

---

## Part 4: All bugs found this week (categorized)

### Bugs FIXED and shipped to live bot
- 10x fee overstatement (taker_fee_bps 45 → 5)
- Hardcoded LLM-first cost gate <60
- Sizing math `qty × leverage` double-multiplication
- Subprocess hang on Windows (full process tree kill)
- TIME_STOP=2h → 8h
- TradeProfile missing 4 args
- Bug #16 look-ahead bias (12 paths gated)
- Per-agent model routing
- Adaptive floor override
- TP1-proximity guard for time stops
- HYPE liquidation pre-gate too aggressive
- `entry_reasons.get("confidence")` → `pos.confidence` (your fix; adaptive floor now learns)
- Graduated rules `times_correct` outcome wiring (your fix)
- Per-symbol strategy weights (your fix)
- OI history + funding rate enrichment (your fix)
- Session context (time-of-day in agent context, your fix)
- Inverted confidence calibration (your fix `221a1d0`)
- Risk Agent missing portfolio state (your fix `5c91984`)
- Sub-noise stop rejection (your `a22e4fe`, `7a863eb`)
- Equity persistence partial fix (your `097ef2d`)
- Close persistence: TIME_STOP/TP1_FULL/HOLD_LIMIT missing from _FULL_CLOSE (your `3495711`)
- force_close events not captured (your `0c6478f`)
- Quant Brain recalibration from 181 live trades (your `aeba848`)
- Inverted time-of-day multipliers (your `f10a43a`, `87ccbda`)
- SOL BUY DO-NOT-VETO protection removal (your `3eded75`)

### Bugs PARTIALLY FIXED or workaround
- Quant Brain WR priors recalibrated (your aeba848) but **Kelly weights still use fee-bug-era trade_ledger PnL** — needs your script ee65511 to actually run
- Risk Agent hard-cap (mine, defensive) on top of your portfolio-aware design

### Bugs FOUND but NOT YET FIXED (your queue items)
- **Critic veto threshold too aggressive — 73.6% wrong rate** (priority 1)
- **Kelly weights script not run** — file doesn't exist on disk (priority 2)
- **Strategy weights frozen at 0.30 across all** (priority 3a)
- **Graduated rules `times_correct=0` despite `times_applied 16-347`** (priority 3b)
- **`risk_equity_state.json` stuck at $5000** (priority 4)
- **Phantom-detection path skips ledger write** (live mode only — paper unaffected)

### Bugs found, deferred, low priority
- Deep memory READ paths fee-poisoning
- knowledge_base.json may have fabricated WR claims
- Overseer Agent dead code (no consumer)
- Quant LLM Agent gated on disabled flag
- Learning Agent forward-feed missing
- Adaptive trailing stop (still ATR-fixed, should be vol-adaptive)
- Regime-aware time stop (still 8h flat, should vary)
- Equity tracker UI cosmetic
- Strategy concentration limit (no per-strategy budget cap)
- Per-setup drawdown circuit breaker

---

## Part 5: What's CONFIRMED working (no need to investigate)

- **Adaptive floor:** 20 outcomes recorded, 7 regime bins populated. Loaded 128 outcomes total at last boot. **Learning.**
- **Counterfactual tracking:** 848 scenarios, 724 resolved, accumulating data. **Working** (though the data tells us veto is broken — Part 6).
- **Sonnet Trade Agent at scale:** Zero pipeline failures since restart. **Healthy.**
- **State recovery on restart:** Confirmed twice today (15:32 boot, 17:42 boot). Position state persists.
- **Counterfactual reveals truth:** This is the system catching its own mistakes. **The veto data is good data.**

---

## Part 6: Critical findings worth highlighting

### Finding 1: Critic veto = value destroyer
- 183 vetoes correct (avoided losses) + 533 vetoes wrong (missed gains) = 73.6% wrong rate
- This is the single biggest live alpha leak we've identified
- Probably means Critic is firing on vibes (insufficient counter-thesis) rather than concrete bear case
- Fix direction: require Critic to articulate falsifiable counter-thesis or default to no-veto

### Finding 2: Strategy weights frozen
- All 6 strategies at 0.30 weight, no evolution since 2026-05-30 restart
- Means ensemble is treating all strategies equally regardless of live performance
- Outcome-record callback for strategy_weights is probably broken

### Finding 3: Graduated rules outcome-record broken
- Every rule shows `times_correct = 0` despite `times_applied = 16-347`
- Means rules can't promote/demote based on outcomes
- Separate update-loop bug from adaptive floor (which IS working post-your-fix)

### Finding 4: Kelly weights file doesn't exist
- Your `ee65511` script writes to `bot/data/kelly_weights.json` (presumably)
- File not present → script never ran → kelly weights are coming from... where?
- Need to run script + verify output

### Finding 5: Equity persistence is double-state-of-truth
- trade_ledger.csv running_equity column: $6184.48 (real)
- risk_equity_state.json: $5000 (broken, frozen since reset)
- All consumers reading the latter are getting wrong number

---

## Part 7: Your prioritized queue (full context)

### P1: Critic veto fix (BIGGEST impact)
**Data:** 533 missed gains vs 183 correct vetoes = bot is leaving $1000s on the table.
**Find:** `bot/llm/agents/coordinator.py` Critic invocation, `bot/llm/agents/prompts.py` CRITIC_AGENT_PROMPT
**Hypothesis:** Critic veto fires on weak disagreement when it should require strong concrete counter-thesis
**Try:** Update CRITIC_AGENT_PROMPT to require: (a) specific price level, (b) specific timeframe, (c) falsifiable claim. Without those = no veto.
**Success metric:** Next 24h counterfactual resolutions show veto-was-correct moving toward 50%+
**Risk:** Could overshoot if Critic becomes too permissive. Add an absolute limit (max veto rate 30%?) or A/B test.

### P2: Run Kelly recompute
**Find:** Your `ee65511` script (probably `bot/scripts/kelly_recompute_from_trade_ledger.py` or similar)
**Run:** With current trade_ledger.csv at corrected 4.5 bps fees
**Verify:** `bot/data/kelly_weights.json` (or wherever it writes) is non-trivial — values vary by setup, not all at 0.15 floor
**Confirm:** The bot's Kelly engine reads from the new file on next restart
**Impact:** Real Kelly weights = real per-setup edge measurement. Currently agents reason from neutral 0.50 priors I stripped.

### P3a: Strategy weight evolution
**Trace:** Where SHOULD strategy weights update on trade close? Look for `strategy_weights.record_outcome()` or similar call.
**Find:** Is it called from the position close flow? `bot/execution/position_manager.py` close paths, `bot/multi_strategy_main.py` close handlers.
**Likely fix:** Add the missing call to the close flow.

### P3b: Graduated rules times_correct update
**Trace:** Where does a graduated rule know its outcome? Similar to P3a.
**Find:** `bot/llm/graduated_rules.py` `record_outcome()` method — who calls it?
**Likely fix:** Add the missing call.

### P4: Equity persistence sync
**Find:** `bot/execution/risk.py` — where update_equity SHOULD call save_equity_state
**Fix:** Sync risk_equity_state.json to trade_ledger.csv running_equity on each close, or on startup.

---

## Part 8: Coordination contract

- I do live monitoring + flag bugs as I see them. I commit fixes for things I find live to `desktop-overdrive-2026-05-30`.
- You do code-quality investigation + ship fixes. Push everything to `historical-import-2026-05-30`.
- I periodically merge your work into `desktop-overdrive-2026-05-30` and restart bot.
- If you blockchain on any priority item, push WHAT YOU FOUND so I can pair next session.
- Don't open PRs. Nunu reviews + merges to main later.
- If you find a HIGH-PRIORITY bug I haven't documented, push it to handshake + commit fix and I'll merge.

## Part 9: What I'm watching live (don't duplicate)

- BTC SHORT @ $60,745 (PID 37868) — first post-strip + post-merge trade
- Agent reasoning quality — looking for residual hardcoded-stat citations
- Pipeline failure count (currently 0 since restart)
- New position opens — watching for sizing patterns under your portfolio-aware Risk Agent fix
- Counterfactual veto-was-X resolution stream — testing your P1 fix when it ships

---

**End of state-of-WAGMI.** When in doubt, search `coordination/handshake.md` for context — it has all prior coordination entries.

-- desktop-claude
