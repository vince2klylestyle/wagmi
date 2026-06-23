# Autonomous Quant Audit — 2026-06-23T10:05:44Z (Run 136)

**Bot Status**: OFFLINE (Day 75 — zero live trades since 2026-04-23 22:17 UTC)
**Data Sources**: `bot/trades_10d.csv` (n=965 full dataset), `bot/data/feedback/adaptive_risk_state.json`, `bot/data/feedback/hold_time_rules_state.json`, `bot/data/meta_learning/insights.json` (19 insights), `bot/data/learning/auto_fix_state.json`, `bot/data/learning/live_edge_data.json`, `bot/data/learning/master_engine_state.json`, `bot/data/sessions/daily_synthesis_2026-06-23.json`, `bot/data/llm/graduated_rules.json` (11 rules)
**Compared to**: `autonomous_audit_2026-06-23T06-09-25Z.md` (Run 134), `master_engine_state.json` (Run 135, 07:10 UTC)
**Last auto-fix**: BTC_LONG_BOOST_DEACTIVATION applied Run 135 (07:10 UTC, conf=86%)

---

## EXECUTIVE SUMMARY

**Three critical findings in this run — one of them CONTRADICTS a pending approval:**

1. **HYPE SHORT <75% APPROVAL SHOULD BE BLOCKED** (new finding, contradicts 15-run flag): Full 965-trade dataset shows HYPE SHORT <75% = WR=56.2% (n=105) but PnL=**-$463.50** (avg **-$4.41/trade**). The 100d backtest claim of +$808/80 trades was a favorable sub-window. Full dataset confirms this setup has negative expected value. The 15-run approval request for `hype_short_sub75_boost_v1` should be **rejected**.

2. **70-80% CONFIDENCE BAND IS THE PRIMARY LOSS CENTER** (new finding, 1st flag): Recent 200 trades show 70-80% confidence = WR=47.6%, avg=-$86.67/trade. This single band accounts for the bulk of recent PnL destruction. The `restored_confidence_paradox_sizing_v1` rule (penalizes 85-90% only) does not address this — it's targeting the wrong confidence tier.

3. **BTC SHORT 90%+ EDGE IS REAL** (reclassification): Full dataset confirms BTC SHORT 90%+ = WR=67.4% (n=43, +$4,425.60 total). Previous audits marked this as "SUSPECT" due to n=10 in 100d window. The 100d sample was too small. Full dataset upgrades this to a **candidate edge**.

**What changed since Run 135**: BTC_LONG_BOOST_DEACTIVATION applied. A/B gate 20% active. HYPE_SHORT_VETO_SPLIT escalated to 15th flag.

**What's working**: SOL SHORT is the cleanest edge across ALL confidence levels (WR=53-76% across all bins). Night block, HYPE LONG veto, illiquid veto, ranging penalty, HYPE SHORT >=75 veto, BTC trend-regime boost — all active, all confirmed by data.

**What's broken**: Bot offline Day 75. Kelly=-0.168 (100d). 4/6 feedback state files missing. HYPE SHORT <75 boost approval pending (should be REJECTED per full dataset). 70-80% confidence band not addressed.

---

## PHASE 1: SYSTEM AUDIT

**AUDIT COMPLETE: 7 systems verified, 4 gaps found**

### Feedback System State Files

| File | Last Modified | Status |
|---|---|---|
| `feedback/adaptive_risk_state.json` | 2026-06-05 02:01 UTC | ⚠️ 48 days stale (bot offline) |
| `feedback/hold_time_rules_state.json` | 2026-06-05 02:01 UTC | ⚠️ 48 days stale (bot offline) |
| `feedback/signal_quality.json` | — | ❌ MISSING (2nd flag) |
| `feedback/regime_feedback_state.json` | — | ❌ MISSING (2nd flag) |
| `feedback/confidence_state.json` | — | ❌ MISSING (2nd flag) |
| `feedback/strategy_weights.json` | — | ❌ MISSING (2nd flag) |
| `llm/llm_memory.json` | 2026-06-23 06:03 UTC | ✅ Active |
| `llm/graduated_rules.json` | 2026-06-23 07:10 UTC | ✅ Active (11 rules, 10 active) |

### Feedback System Instantiation (multi_strategy_main.py)

| System | Class | Init Line | record_outcome() Line | Status |
|---|---|---|---|---|
| RegimeFeedbackManager | `feedback/regime_feedback.py` | 412 | 3135 | ✅ WIRED |
| AdaptiveConfidenceFloor | `feedback/adaptive_confidence.py` | 415 | 3144 | ✅ WIRED |
| HoldTimeRuleManager | `feedback/hold_time_rules.py` | 418 | 3152 | ✅ WIRED |
| SignalQualityScorer | `feedback/signal_quality.py` | 421 | 3159 | ✅ WIRED |
| ParameterTuner | `feedback/parameter_tuner.py` | 424 | 3166 | ✅ WIRED |
| FeedbackLoop | `feedback/loop.py` | 804 | 3233 | ✅ WIRED |
| AutoOptimizer | `feedback/auto_optimizer.py` | 909/2231 | lazy-init | ✅ WIRED (lazy) |

### Graduated Rules Status (as of Run 135)

| Rule | Action | Status |
|---|---|---|
| `rule_1782144529_0` (BTC+trend) | boost +8 | ✅ ACTIVE |
| `restored_night_session_block_v1` | veto 00-06 UTC | ✅ ACTIVE |
| `restored_hype_long_block_v1` | veto HYPE LONG | ✅ ACTIVE |
| `restored_illiquid_regime_block_v1` | veto illiquid | ✅ ACTIVE |
| `restored_ranging_regime_penalty_v1` | penalize -15 | ✅ ACTIVE |
| `restored_hype_short_highconf_veto_v1` | veto HYPE SHORT ≥75% | ✅ ACTIVE |
| `restored_hype_sizing_cap_v1` | size -0.5x HYPE | ✅ ACTIVE |
| `restored_sol_short_boost_v1` | boost +8 SOL SHORT | ✅ ACTIVE |
| `restored_btc_long_boost_v1` | boost +8 BTC LONG | ❌ DEACTIVATED (Run 135) |
| `restored_confidence_paradox_sizing_v1` | size -0.25x at 85-90% | ✅ ACTIVE |
| `restored_instant_sl_buffer_v1` | size -0.1x all | ✅ ACTIVE |

**Note**: `times_applied=0` for all rules — bot offline since rules restored. No live confirmation yet.

**GAP 1**: 4/6 feedback state files not persisting to disk (2nd consecutive flag).
**GAP 2**: Bot offline 75 days — no live validation of restored rules.
**GAP 3**: Duration bug: 537/589 backtest trades show duration_h=0, 52 negative. HoldTimeRuleManager ML compromised.
**GAP 4**: `llm_regime` field empty in all CSV records — regime-specific ML can only use adaptive_risk_state.json.

**AUDIT COMPLETE: 7 systems verified, 4 gaps found**

---

## PHASE 2: TRADE FORENSICS

**FORENSICS COMPLETE: 6 high-value sub-conditions found, 3 regression areas (new: 70-80% confidence band)**

### Overall Statistics

| Window | WR | n | Total PnL | EV/Trade | Verdict |
|---|---|---|---|---|---|
| Full dataset (all time) | 57.0% | 965 | +$905.23 | +$0.94 | ⚠️ Marginally positive |
| Recent 200 trades | 53.5% | 200 | -$6,211.34 | -$31.06 | ❌ Deteriorating |
| Recent 100 trades | 48.0% | 100 | -$7,804.00 | -$78.04 | ❌ Structural loss |
| 100d backtest | 44.5% | 589 | -$8,173.52 | -$13.88 | ❌ Negative Kelly |

**Performance decay is accelerating**: Full history barely positive; recent 100 trades lose $78/trade.

### By Symbol + Side (Full Dataset, n=965)

| Cell | WR | n | Total PnL | Avg/Trade | Verdict |
|---|---|---|---|---|---|
| SOL SHORT | **63.7%** | 179 | **+$5,807.40** | **+$32.44** | ✅ PRIMARY ALPHA |
| BTC LONG | 63.9% | 72 | +$1,839.45 | +$25.55 | ✅ HISTORICALLY STRONG (boost deactivated Run 135) |
| BTC SHORT | 53.8% | 195 | -$1,407.62 | -$7.22 | ⚠️ Has 90%+ profitable sub-band |
| SOL LONG | 53.3% | 122 | -$320.09 | -$2.62 | ⚠️ Near-zero drag |
| HYPE LONG | 57.0% | 158 | -$1,034.66 | -$6.55 | ❌ Vetoed (correct) |
| HYPE SHORT | 54.4% | 239 | -$3,979.25 | -$16.65 | ❌ Negative despite 54% WR — size asymmetry |

### By Confidence Bin (Full Dataset vs Recent 200)

| Bin | WR (All Time) | Avg/Trade (All) | WR (Recent 200) | Avg/Trade (Recent 200) | Verdict |
|---|---|---|---|---|---|
| 60-70% | 46.3% | -$18.87 | 60.6% | -$6.95 | ❌ Below WR breakeven historically |
| 70-80% | 58.6% | -$0.98 | **47.6%** | **-$86.67** | ❌ PRIMARY LOSS CENTER (recent) |
| 80-90% | 60.2% | +$7.67 | 52.2% | -$37.23 | ⚠️ Degrading |
| 90%+ | 56.0% | +$32.33 | **64.1%** | **+$101.92** | ✅ BEST TIER — improving |

**New finding (1st flag)**: 70-80% confidence band = WR=47.6%, avg=-$86.67/trade in recent 200 trades. `confidence_paradox_sizing` rule targets 85-90% — it's addressing the wrong tier.

### By Close Reason (Full Dataset)

| Reason | WR | n | Total PnL |
|---|---|---|---|
| SL | 0.0% | 370 | **-$83,112.61** |
| TP1 | 100.0% | 297 | +$72,420.11 |
| TRAILING_STOP | 71.1% | 152 | +$1,347.02 |
| TP2 | 100.0% | 145 | +$10,309.53 |

### High-Value Sub-Conditions (WR≥50%, positive PnL, n≥10) — 6 Found

| Cell | WR | n | Avg PnL | Status |
|---|---|---|---|---|
| SOL SHORT 80-90% conf | **76.0%** | 25 | +$53.35 | ✅ High evidence |
| SOL SHORT 75-80% conf | 64.4% | 45 | +$41.39 | ✅ High evidence |
| BTC SHORT 90%+ conf | **67.4%** | 43 | +$102.92 | ✅ UPGRADED from SUSPECT |
| SOL SHORT 70-75% conf | 62.5% | 72 | +$14.27 | ✅ High evidence |
| SOL SHORT 60-70% conf | 53.3% | 30 | +$34.50 | ✅ Moderate |
| 90%+ conf all symbols | 64.1% (recent 200) | 39 | +$101.92 | ✅ Recent |

### Top 5 Wins

| # | Symbol | Side | PnL | Conf | Exit |
|---|---|---|---|---|---|
| 1 | BTC | LONG | +$1,747.15 | 79.7 | TP1 |
| 2 | BTC | SHORT | +$1,379.26 | 85.9 | TP1 |
| 3 | BTC | SHORT | +$1,269.72 | 76.4 | TP1 |
| 4 | BTC | SHORT | +$1,176.71 | 87.5 | TP1 |
| 5 | SOL | SHORT | +$1,164.02 | 69.2 | TP1 |

### Top 5 Losses

| # | Symbol | Side | PnL | Conf | Exit |
|---|---|---|---|---|---|
| 1 | BTC | LONG | -$1,458.52 | 69.0 | SL |
| 2 | BTC | SHORT | -$1,243.25 | 74.4 | SL |
| 3 | BTC | LONG | -$999.90 | 85.4 | SL |
| 4 | BTC | SHORT | -$881.00 | 71.3 | SL |
| 5 | BTC | SHORT | -$822.68 | 85.4 | SL |

**Pattern**: 5/5 top losses are BTC SL hits. 70-80% confidence concentration (#2 and #4) consistent with regression finding.

**FORENSICS COMPLETE: 6 high-value sub-conditions found, 3 regression areas**

---

## PHASE 3: HYPOTHESIS VALIDATION

**VALIDATION COMPLETE: 1 confirmed, 3 unverifiable, 15 invalidated, 1 new contradiction**

### NEW CONTRADICTION FOUND THIS RUN

**HYPE SHORT <75% claim vs full dataset**:
- Run 114+ claim: +$808 over 80 trades (+$10.10/trade) — from 100d backtest
- Full dataset (n=965): WR=56.2% (n=105) but PnL=-$463.50 (avg **-$4.41/trade**)

Mark as: **INVALIDATED — FULL_DATASET_CONTRADICTS_100D_SLICE**

---

## PHASE 4: FEEDBACK LOOP CLOSURE

**LOOP CLOSURE: 0 trades propagated (bot offline), 4 broken disk links, 1 rule miscalibration**

| Feedback Sink | Code Wired? | Disk File? |
|---|---|---|
| `weight_mgr.record_outcome()` (line 3123) | ✅ | ❌ MISSING |
| `regime_feedback.record_trade()` (line 3135) | ✅ | ❌ MISSING |
| `confidence_floor.record_outcome()` (line 3144) | ✅ | ❌ MISSING |
| `hold_time_rules.record_trade()` (line 3152) | ✅ | ✅ (stale) |
| `signal_quality.record_outcome()` (line 3159) | ✅ | ❌ MISSING |
| `FeedbackLoop.record_outcome()` (line 3233) | ✅ | ✅ (stale) |

**Rule miscalibration**: `restored_confidence_paradox_sizing_v1` penalizes 85-90% (-0.25x). Full data shows 80-90% WR=60.2% (+$7.67/trade avg). Actual problem is 70-80% (recent 200: WR=47.6%, -$86.67/trade). Rule is targeting the wrong tier.

---

## PHASE 5: RECOMMENDATIONS

**RECOMMENDATIONS: 3 changes proposed**

### REC 1 (89% confidence): REJECT HYPE SHORT <75% Approval
- **Problem**: 15-run approval flag based on 100d window (+$10.10/trade, n=80). Full 965-trade dataset contradicts: PnL=-$463.50, avg=-$4.41/trade (n=105).
- **Fix**: Mark `HYPE_SHORT_VETO_SPLIT` as REJECTED. Do not add `hype_short_sub75_boost_v1`.
- **Impact**: Prevents adding rule with -$4.41/trade EV → saves ~-$88 to -$132/month.
- **Confidence**: 89% — full dataset (n=105) supersedes 100d sub-window (n=80).

### REC 2 (82% confidence): Add 70-80% Confidence Size Reduction
- **Problem**: Recent 200 trades: 70-80% conf = WR=47.6%, avg=-$86.67/trade. ~105 trades × -$86.67 = -$9,100 in last 200. Not addressed by any current rule.
- **Fix**: New graduated rule: `{confidence_min: 70, confidence_max: 80} → size_adjust: -0.3x`
- **Impact**: 30% size reduction → ~+$26/trade improvement on 65% of all signals → +$2,600 per 100 trades.
- **A/B**: 50% gate, 50 trades. Success: treatment EV improves >$20/trade vs baseline.
- **Rollback**: Disable if treatment EV < control.

### REC 3 (82% confidence, ESCALATED 9th flag): Approve RR Geometry A/B Test
- **Problem**: 370 SL hits = -$83,112.61. Kelly=-0.168 (11th flag). 50.8% of SL hits in noise regime.
- **Fix**: A/B test `atr_mult_sl=1.8` on 10% of signals at restart.
- **Impact**: Converting 20% of noise-SLs to holds → ~+$335/month.
- **Blocked on**: Bot restart required.

---

## OPEN ITEMS TRACKER

| Flag ID | Flags | Action |
|---|---|---|
| BOT_OFFLINE | 66 | P0: `cd /home/user/WAGMI/bot && python run.py paper` |
| NEGATIVE_KELLY_EDGE | 11 | REC 3 — dev + restart |
| HYPE_SHORT_VETO_SPLIT | 15 | **CLOSE → REJECT** per REC 1 |
| 70_80_CONFIDENCE_BAND | 1 (NEW) | REC 2: Add -0.3x size rule |
| RR_GEOMETRY_FIX | 9 | Cannot A/B without bot running |
| FEEDBACK_STATE_FILES_MISSING | 3 | Dev: add _save() to 4 managers |
| CONFIDENCE_PARADOX_RULE_MISCAL | 1 (NEW) | Rule targets 85-90%, problem is 70-80% |
| BTC_SHORT_90PLUS_EDGE | 5 | UPGRADED to CANDIDATE (n=43, WR=67.4%) |
| SOL_SHORT_75_80_PRECISION | 6 | WR=64.4% (n=45, +$41.39/trade) — strong candidate |
| DURATION_DATA_BUG | ongoing | Dev required |

---

*Audit generated by Autonomous Quant Audit Agent — Run 136 — 2026-06-23T10:05:44Z*
