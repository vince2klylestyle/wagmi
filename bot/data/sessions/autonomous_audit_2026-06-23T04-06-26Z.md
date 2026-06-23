# Autonomous Quant Audit — 2026-06-23T04:06:26Z (Run 132)

**Bot Status**: OFFLINE (Day 76 — zero live trades since 2026-04-23 22:17 UTC)
**Data Sources**: `backtest_100d.csv` (n=589), `backtest_60d.csv` (n=802), `graduated_rules.json` (11 rules), `meta_learning/insights.json` (19 insights, 4 active), `feedback/*.json`, `auto_fix_state.json`, `live_edge_data.json`, `daily_synthesis_2026-06-22.json`
**Compared to**: `autonomous_audit_2026-06-23T02-06-15Z.md` (Run 131, 2h ago)

---

## EXECUTIVE SUMMARY

**Three critical findings this run, one is NEW and actionable:**

1. **⚠️ BTC LONG BOOST RULE IS COUNTERPRODUCTIVE (NEW FINDING)**: `restored_btc_long_boost_v1` claims 63.9% WR and boosts BTC LONG signals +8 confidence. The 100d backtest shows BTC LONG has **WR=31.7%, EV=-$13.42/trade on n=41 trades**. The rule was derived from stale data; it is now actively promoting a losing setup. Must be deactivated and reversed.

2. **✅ HYPE LONG VETO IS CORRECT (PRIOR CLAIM REVISED)**: Despite 50% WR (Run 131 questioned this), per-trade EV for HYPE LONG is **-$14.36** due to asymmetric losses (avg win $96 vs avg loss -$125). The veto stands. Claim of 23% WR was wrong but the economic conclusion is right.

3. **✅ GRADUATED RULES CODE BUG IS FIXED (PRIOR CLAIM REVISED)**: `graduate_hypothesis()` in `llm/graduated_rules.py` now forces `self._loaded = False; self._ensure_loaded()` before writing — the time-bomb mentioned in Runs 129-131 is patched in the codebase. NOT a live issue.

**Persistent flags** (unchanged since Run 131):
- Bot offline Day 76 — all feedback loops frozen, zero revenue
- HYPE SHORT <75% awaiting human approval for 12 consecutive runs (+$808 EV blocked)
- System EV=-$13.88/trade, needs 8.0pp WR improvement to break even
- Kelly=-0.168 (negative edge confirmed)

**AUDIT COMPLETE: 7 systems verified, 6 gaps found**
**FORENSICS COMPLETE: 3 high-value sub-conditions found, 4 regression areas**
**VALIDATION COMPLETE: 1 confirmed, 2 partially hold, 1 broken rule (BTC LONG boost), 15 stale/invalidated**
**LOOP CLOSURE: 0 trades propagated (bot offline — no new trades)**
**RECOMMENDATIONS: 3 changes proposed, ~$1,800+ total impact per 100-day window**

---

## PHASE 1: SYSTEM AUDIT

**AUDIT COMPLETE: 7 systems verified, 6 gaps found**

### Feedback System Instantiation (`multi_strategy_main.py`)

| System | Class | Instantiation Line | record_outcome() Line | Status |
|---|---|---|---|---|
| SignalQualityScorer | `feedback/signal_quality.py` | 421 | 3159 | ✅ WIRED |
| ParameterTuner | `feedback/parameter_tuner.py` | 424 | 3166 | ✅ WIRED |
| RegimeFeedbackManager | `feedback/regime_feedback.py` | 412 | 3136 | ✅ WIRED |
| AdaptiveConfidenceFloor | `feedback/adaptive_confidence.py` | 415 | 3144 | ✅ WIRED |
| HoldTimeRuleManager | `feedback/hold_time_rules.py` | 418 | 3152 | ✅ WIRED |
| FeedbackLoop | `feedback/loop.py` | 804 | 3233 | ✅ WIRED |
| AutoOptimizer | (lazy-init via FeedbackLoop) | 909/2222 | 3225+ | ✅ WIRED (lazy-init) |

### State File Status

| File | Last Modified | Gap |
|---|---|---|
| `feedback/adaptive_risk_state.json` | 2026-06-05 02:01 UTC | ⚠️ 18 days stale (bot offline) |
| `feedback/hold_time_rules_state.json` | 2026-06-05 02:01 UTC | ⚠️ 18 days stale |
| `feedback/signal_quality.json` | MISSING | ❌ Never written |
| `feedback/regime_feedback_state.json` | MISSING | ❌ Never written |
| `feedback/confidence_state.json` | MISSING | ❌ Never written |
| `feedback/strategy_weights.json` | MISSING | ❌ Never written |

**Note**: 4 missing state files write only on trade close. Bot offline = no writes. Not a wiring bug.

### Graduated Rules Code Bug

The "time-bomb" bug mentioned in Runs 129-131 is **CONFIRMED FIXED**. `llm/graduated_rules.py` `graduate_hypothesis()` (line ~150) now executes:
```python
self._loaded = False
self._ensure_loaded()
```
Forces fresh disk read before any graduation write. No action needed.

---

## PHASE 2: TRADE FORENSICS

**FORENSICS COMPLETE: 3 high-value sub-conditions found, 4 regression areas**

**Data**: `backtest_100d.csv` (n=589)

### System-Level Stats

| Metric | Value |
|---|---|
| Total Trades | 589 |
| Win Rate | 44.5% |
| Total PnL | -$8,173 |
| Avg PnL/Trade | -$13.88 |
| Avg Win | +$82.72 |
| Avg Loss | -$91.27 |
| Breakeven WR Required | 52.5% |
| WR Gap | -8.0pp |
| Kelly Fraction | -0.168 (negative edge) |

### By Symbol

| Symbol | WR | Count | Total PnL | Avg PnL |
|---|---|---|---|---|
| HYPE | 48.9% | 225 | -$5,563 | -$24.73 |
| SOL | 41.4% | 198 | -$1,974 | -$9.97 |
| BTC | 42.2% | 166 | -$637 | -$3.84 |

HYPE = 38% of trades, 68% of losses.

### By Side

| Side | WR | Count | Total PnL |
|---|---|---|---|
| SHORT | 46.4% | 422 | -$5,676 |
| LONG | 39.5% | 167 | -$2,497 |

### By Confidence Bin

| Confidence | WR | Count | Avg PnL |
|---|---|---|---|
| 60-70% | 48.6% | 111 | -$7.15 |
| 70-80% | 45.2% | 321 | -$8.54 |
| 80-90% | 40.0% | 120 | -$33.04 |
| 90%+ | 40.5% | 37 | -$18.23 |

High confidence = WORST outcomes. Anti-correlation confirmed 3rd consecutive window.

### By Exit Type

| Exit | Count | Total PnL | Avg PnL |
|---|---|---|---|
| SL | 269 | -$29,300 | -$108.92 |
| TP1 | 160 | +$19,521 | +$122.01 |
| TRAILING_STOP | 111 | -$37 | -$0.34 |
| TP2 | 49 | +$1,643 | +$33.53 |

SL rate = 45.7%. R:R ~1.2:1. Math guarantees negative EV at this hit rate.

### High-Value Sub-Conditions

| Sub-Condition | WR | Count | EV/Trade | Status |
|---|---|---|---|---|
| HYPE SHORT < 75% conf | 53.8% | 80 | +$10.10 | ✅ ALPHA — blocked |
| SOL SHORT 75-80% conf | 52.9% | 34 | +$24.26 | ✅ ALPHA — no rule |
| HYPE LONG 60-70% conf | 60.7% | 28 | +$10.27 | ⚠️ ALPHA — vetoed |

### Regression Areas

| Area | WR | EV/Trade |
|---|---|---|
| BTC LONG (all conf) | 31.7% | -$13.42 |
| HYPE SHORT ≥75% | 42.9% | -$44.43 |
| SOL SHORT >80% | 34.5% | -$25.08 |
| All 80-90% conf | 40.0% | -$33.04 |

### Top 5 Wins

| Symbol | Side | Conf | Close | PnL |
|---|---|---|---|---|
| SOL | SHORT | 79.7% | TP1 | +$714 |
| HYPE | SHORT | 87.5% | TP1 | +$598 |
| HYPE | SHORT | 71.1% | TP1 | +$494 |
| HYPE | SHORT | 69.0% | TP1 | +$453 |
| HYPE | SHORT | 72.1% | TP1 | +$426 |

All wins: SHORT direction, TP1 exit. Pattern is consistent.

### Top 5 Losses

| Symbol | Side | Conf | Close | PnL |
|---|---|---|---|---|
| HYPE | SHORT | 70.4% | SL | -$521 |
| HYPE | SHORT | 87.5% | SL | -$516 |
| HYPE | SHORT | 81.5% | SL | -$512 |
| HYPE | SHORT | 71.3% | SL | -$511 |
| HYPE | SHORT | 85.4% | SL | -$451 |

All losses: HYPE SHORT SL. High conf dominates the loss list — confirms confidence paradox.

---

## PHASE 3: HYPOTHESIS VALIDATION

**VALIDATION COMPLETE: 1 confirmed, 2 partially hold, 1 broken rule, 15 stale/invalidated**

### Active Insights (4 of 19)

| Insight | Status | Action Taken |
|---|---|---|
| Night 00-06 weakness (15% WR, n=13) | ✅ CONFIRMED | ✅ VETO active |
| Ensemble concentration 94%→44.5% WR | ✅ HOLDS (now 100%) | ❌ No diversification |
| Evening 18-24 weakness (29% WR, n=14) | ⚠️ PARTIAL | ❌ None |
| Afternoon 12-18 weakness (27% WR, n=15) | ⚠️ PARTIAL | ❌ None |

### Graduated Rules Cross-Validation (100d backtest)

| Rule | Claim | Reality | Verdict |
|---|---|---|---|
| HYPE LONG VETO | 23% WR | 50% WR, EV=-$14.36 | ✅ ECONOMICALLY CORRECT |
| HYPE SHORT ≥75% VETO | 31.2% WR | 42.9% WR (n=77) | ✅ DIRECTION CORRECT |
| HYPE sizing cap 0.5x | Negative EV | EV=-$24.73/trade | ✅ CONFIRMED |
| Confidence paradox sizing | 80-90% worst | 40.0% WR, -$33.04 avg | ✅ CONFIRMED |
| **BTC LONG boost +8** | **63.9% WR** | **31.7% WR, EV=-$13.42** | **🔴 BROKEN — REVERSES** |
| SOL SHORT boost +8 | 63.7% WR | 45.0% WR, EV=-$7.16 | ❌ STALE/BLUNT |
| Night/Illiquid/Ranging | Various | No regime/timestamp col | UNTESTED |

---

## PHASE 4: FEEDBACK LOOP CLOSURE

**LOOP CLOSURE: 0 trades propagated (bot offline — no new trades)**

All 7 feedback links confirmed wired at code level. Chain is dormant, will activate on restart.

| Link | Code Location | Status |
|---|---|---|
| signal_quality.record_outcome() | Line 3159 | Wired / dormant |
| regime_feedback.record_trade() | Line 3136 | Wired / dormant |
| confidence_floor.record_outcome() | Line 3144 | Wired / dormant |
| hold_time_rules.record_trade() | Line 3152 | Wired / dormant |
| parameter_tuner.record_outcome() | Line 3166 | Wired / dormant |
| graduated_rules.record_outcome() | Line 3258 | Wired / dormant |
| llm memory (LearningAgent) | coordinator.py | Wired / dormant |

---

## PHASE 5: RECOMMENDATIONS

**RECOMMENDATIONS: 3 changes proposed, ~$1,800+ estimated impact per 100-day window**

### REC1 — CRITICAL: Deactivate BTC LONG Boost, Replace with Penalize

**Problem**: `restored_btc_long_boost_v1` adds +8 conf to BTC LONG. 100d backtest: WR=31.7% (n=41), EV=-$13.42/trade. 2nd worst losing setup. Boost rule derived from stale early-bull window (n=965 combined dataset).

**Evidence**: BTC LONG total=-$550/41 trades. BTC SHORT WR=45.6%, EV=-$0.69 (near neutral — the better direction).

**Fix**: Set `restored_btc_long_boost_v1.active = false`. Add `btc_long_penalize_v1`: penalize -8, conditions={"symbol":"BTC","side":"BUY"}.

**Impact**: +$550/100 days (avoid 41 trades at -$13.42). **A/B**: 30-day penalty, revert if live WR >50% on n≥20. **Rollback**: Remove penalty if live BTC LONG WR >50%. **Confidence**: 72%.

---

### REC2 — HIGH: Unblock HYPE SHORT < 75% Confidence *(Human Approval Required)*

**Problem**: HYPE SHORT <75% conf: WR=53.8%, EV=+$10.10/trade, n=80. Best-sampled alpha in the system. Blocked for 12 consecutive runs. Rule `restored_hype_short_highconf_veto_v1` (confidence_min:75) may be collaterally blocking sub-75% trades.

**Evidence**: avg_win=$148.06, avg_loss=-$150.23, EV=+$10.10. HYPE SHORT ≥75%: EV negative (veto correct). Populations are diametrically opposite.

**Fix**: (1) Verify `evaluate_signal()` correctly gates `confidence_min:75`. (2) Add `hype_short_sub75_allow_v1`: boost +5, conditions={"symbol":"HYPE","side":"SHORT","confidence_max":74}.

**Impact**: +$808/100 days. **A/B**: Paper 20 HYPE SHORT <75% signals over 2 weeks. **Rollback**: Re-veto all HYPE SHORT if live WR <38% on n≥15. **Confidence**: 80%.

---

### REC3 — MEDIUM: Replace Blunt SOL SHORT Boost with 75-80% Confidence Gate

**Problem**: Blanket SOL SHORT boost (+8) promotes losing sub-bands. Only 75-80% conf is alpha.

**Evidence**:
- 60-70%: EV=-$19.74 (n=22)
- 70-75%: EV=-$13.04 (n=48)
- **75-80%: EV=+$24.26 (n=34)** ← the edge
- 80-90%: EV=-$25.08 (n=29)
- 90%+: WR=57.1% but n=7 (insufficient)

**Fix**: Deactivate `restored_sol_short_boost_v1`. Add `sol_short_conf_gate_75_80`: boost +10 at 75-80% conf. Add `sol_short_sub75_penalize`: penalize -10 below 75%.

**Impact**: ~+$1,800/100 days. **A/B**: 30-day gate trial. **Rollback**: Remove gate if 75-80% WR drops below 40% on n≥15. **Confidence**: 68%.

---

## OPEN FLAGS

| Flag | Severity | Consecutive | Action |
|---|---|---|---|
| BOT_OFFLINE | CRITICAL | 64 | `cd /home/user/WAGMI/bot && python run.py paper` |
| BTC_LONG_BOOST_BROKEN | CRITICAL | 1 NEW | Deactivate + penalize -8 |
| NEGATIVE_KELLY_EDGE | CRITICAL | 10 | Need 8pp WR gain to break even |
| HYPE_SHORT_VETO_SPLIT | HIGH | 12 | AWAITING HUMAN APPROVAL |
| CONFIDENCE_ANTI_CORRELATION | HIGH | 10 | Rule active, untested live |
| HYPE_LOSS_DOMINANCE | HIGH | 7 | Sizing cap active |
| SHORT_DIRECTION_VETO_INVERSION | HIGH | 4 | A/B probe active |
| SOL_SHORT_BOOST_BLUNT | MEDIUM | 1 NEW | Split into confidence bands |

## WHAT'S WORKING
- All 7 feedback systems wired, ready to propagate on restart
- Protective vetoes (night, HYPE LONG, illiquid, ranging, HYPE SHORT ≥75%) economically justified
- graduated_rules.py code bug CONFIRMED FIXED
- HYPE sizing cap (0.5x) correctly targets biggest loss source
- Auto-fix system correctly restored rules in Run 130

## WHAT'S BROKEN
1. BTC LONG boost promotes a 31.7% WR loser (new finding, high urgency)
2. SOL SHORT boost too blunt — only 75-80% band is alpha
3. Bot offline Day 76 — no revenue, no live feedback
4. HYPE SHORT <75% alpha (+$808) blocked for 12 runs
5. duration_h field corrupted in backtest (all 0.0/-0.1)

## PRIORITY ORDER
1. `cd /home/user/WAGMI/bot && python run.py paper` (prerequisite for everything)
2. Deactivate `restored_btc_long_boost_v1`, add penalize -8 (10 min, +$550 EV)
3. Approve HYPE SHORT <75% unblock (human decision, +$808 EV)
4. Split SOL SHORT boost into 75-80% gate after live data available

---
*Run 132 | Cadence streak: 49 | Next audit: ~2026-06-23T06:00Z*
