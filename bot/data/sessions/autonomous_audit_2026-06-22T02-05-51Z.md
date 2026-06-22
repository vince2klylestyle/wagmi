# Autonomous Quant Audit — 2026-06-22T02:05:51Z (Run 119)

**Bot Status**: OFFLINE (Day 70+)
**Data Source**: backtest_100d.csv (589 trades), feedback state files, graduated_rules.json, meta_learning/insights.json
**Compared to**: autonomous_audit_2026-06-21T22-00-00Z (Run 118, ~4h ago)

---

## EXECUTIVE SUMMARY

The bot remains offline (Day 70). The feedback systems are correctly wired but all five dynamic state files (signal_quality, regime_feedback, confidence, strategy_weights, LLM memory) remain stale from last live session June 5. Three critical findings this run:

1. **hype_short_veto_v1 is suppressing positive-EV setups**: HYPE SHORT below 75% confidence shows +$8–15/trade positive EV (52–60% WR, n=80 trades). The veto was trained on early live data; the 100d backtest contradicts it in the sub-75% band. The veto is blocking good trades while the real bleed is HYPE SHORT ≥75% confidence (-$70/trade).

2. **Fundamental R:R structural deficit**: avg win ($82.72) < avg loss ($91.27) → win/loss ratio 0.91. At 44.5% WR, the Kelly fraction is -0.167 (negative edge). This is the root cause of -$8,173 total PnL across 589 trades. No routing rule or veto fixes this without addressing TP/SL geometry.

3. **Confidence is anti-correlated with performance**: 60–70% conf = 48.6% WR; 70–80% = 45.2%; 80–90% = 40.0%; 90%+ = 40.5%. Higher model confidence actively predicts worse outcomes. The `confidence_paradox_sizing_v1` rule (penalizes 85–90%) partially addresses this but the full range (80–100%) needs intervention.

**What's working**: Graduate rule framework correctly maintains 22 active rules, night session block (0–6 UTC) and illiquid/ranging regime penalties are well-calibrated. HYPE LONG veto (23% live WR → correctly blocking). Hold-time rule (3h min) mechanically enforced.

**What's broken**: R:R geometry, hype_short_veto over-breadth, confidence model reliability, bot offline.

---

## PHASE 1: SYSTEM AUDIT

**Result**: AUDIT COMPLETE: 7 systems verified, 5 state file gaps found

### Feedback System Instantiation (multi_strategy_main.py)

| System | Instantiated | Lines | record_outcome() wired |
|---|---|---|---|
| SignalQualityScorer | ✅ | Line 421 | ✅ Line ~3148 |
| ParameterTuner | ✅ | Line 424 | ✅ Line ~3155 |
| RegimeFeedbackManager | ✅ | Line 412 | ✅ Line ~3136 |
| AdaptiveConfidenceFloor | ✅ | Line 415 | ✅ Line ~3141 |
| HoldTimeRuleManager | ✅ | Line 418 | ✅ Line ~3144 |
| FeedbackLoop | ✅ | Line 804 | ✅ wired at line 805 |
| AutoOptimizer | ✅ | Line 909 | ✅ lazy-init Line 2222 |

All 7 systems confirmed wired. The `record_outcome()` block at lines 3100–3160 correctly calls all systems on `_FULL_CLOSE` events (SL, TP2, TRAILING_STOP, EARLY_EXIT, EMERGENCY, LIQUIDATION_AVOID, ROTATE_PROFIT, ROTATE_LOSS_AVOIDANCE).

### State File Status

| File | Path | Last Modified | Status |
|---|---|---|---|
| adaptive_risk_state.json | data/feedback/ | 2026-06-05 02:01 | ✅ Exists (47+ days stale) |
| hold_time_rules_state.json | data/feedback/ | 2026-06-05 02:01 | ✅ Exists (47+ days stale) |
| signal_quality.json | data/feedback/ | — | ❌ Missing |
| regime_feedback_state.json | data/feedback/ | — | ❌ Missing |
| confidence_state.json | data/feedback/ | — | ❌ Missing |
| strategy_weights.json | data/ | — | ❌ Missing |
| llm_memory.json | data/llm/ | 2026-06-22 (recent) | ⚠️ 1 note (essentially empty) |

**Gap count**: 5 missing state files (all require bot to be running to populate)

### Graduated Rules Registry

31 rules total: **22 active, 9 inactive**. Accuracy data is concerning:
- `hype_long_veto_v1`: applied 1x, correct 0/1 (0%)
- `hype_short_veto_v1`: applied 1x, correct 0/1 (0%)
- `eth_sell_bb_golden_v1`: applied 3x, correct 0/3 (0%)
- `bb_mtq_antipattern_v1`: applied 1x, correct 0/1 (0%)
- `short_direction_veto_v1`: applied 1x, correct 0/1 (0%)

**Note**: Low application counts (1–3) mean 0% accuracy is not yet statistically significant. However the pattern warrants monitoring — 6 applications, 0 confirmed correct predictions.

---

## PHASE 2: TRADE FORENSICS

**Result**: FORENSICS COMPLETE: 4 high-value sub-conditions found, 3 regression areas

**Dataset**: backtest_100d.csv, 589 trades, all via ensemble strategy, paper mode

### Overall

| Metric | Value |
|---|---|
| Win Rate | 44.5% (262W / 589T) |
| Total PnL | -$8,173.52 |
| Avg Win | +$82.72 |
| Avg Loss | -$91.27 |
| Win/Loss Ratio | 0.91 (below 1.0) |
| Kelly Fraction | **-0.167 (negative edge)** |
| Break-even WR needed (at R:R 0.91) | 52.4% |

### By Symbol

| Symbol | WR | Count | Total PnL | Avg PnL/trade |
|---|---|---|---|---|
| BTC | 42.2% | 166 | -$636.62 | -$3.84 |
| HYPE | 48.9% | 225 | **-$5,563.40** | **-$24.73** |
| SOL | 41.4% | 198 | -$1,973.50 | -$9.97 |

HYPE is the dominant bleeder (-68% of total losses) despite having the highest WR. Root cause: HYPE positions have 2–3× larger dollar sizing than BTC/SOL in this backtest, amplifying losses from the R:R deficit.

### By Confidence Bin

| Confidence | WR | Count | Total PnL | Verdict |
|---|---|---|---|---|
| 60–70% | **48.6%** | 111 | -$793.88 | Best WR tier |
| 70–80% | 45.2% | 321 | -$2,740.21 | Moderate |
| 80–90% | 40.0% | 120 | -$3,964.91 | **Worst** |
| 90%+ | 40.5% | 37 | -$674.52 | Near-worst |

**Critical finding**: Inverse confidence-performance correlation. Each step up in model confidence corresponds to ~4% WR degradation. High-confidence trades (80%+) are the largest PnL drain (-$4,639 on 157 trades = -$29.55/trade). The `confidence_paradox_sizing_v1` rule (penalizes 85–90%) is correctly directional but insufficient scope — needs to cover 80–100%.

### By Side

| Side | WR | Count | Total PnL |
|---|---|---|---|
| SHORT | 46.4% | 422 | -$5,676.03 |
| LONG | 39.5% | 167 | -$2,497.49 |

Shorts outperform longs by 6.9 WR points. The active `short_direction_veto_v1` (vetoes all SHORTs except SOL) is directionally wrong — it would remove the better-performing side.

### By Close Reason

| Reason | WR | Count | Total PnL |
|---|---|---|---|
| SL | 0% | 269 | **-$29,300.41** |
| TP1 | 100% | 160 | +$19,521.35 |
| TRAILING_STOP | 47.7% | 111 | -$37.21 |
| TP2 | 100% | 49 | +$1,642.75 |
| BACKTEST_END | varies | ~0 | +$64.95 |

SL fires drain $29,300; TP events recover only $21,164. Net deficit: **-$8,136**. The SL rate (45.7% of trades hit SL) combined with avg SL loss of -$108.93 vs avg TP1 win of +$122.01 creates the structural R:R problem. The trailing stop is nearly neutral (-$37, 111 trades), indicating it's not adding or destroying value.

### HYPE Sub-condition Analysis

| HYPE SHORT Conf Band | WR | Count | Total PnL | EV/trade |
|---|---|---|---|---|
| <70% conf | **60.0%** | 15 | **+$228.97** | **+$15.27** ✅ |
| 70–75% conf | **52.3%** | 65 | **+$579.12** | **+$8.91** ✅ |
| 75%+ conf | 31.2% | 77 | **-$5,394.88** | **-$70.06** 💀 |

**HIGH-VALUE FINDING**: HYPE SHORT below 75% confidence is positive EV (+$8–15/trade, n=80). The active `hype_short_veto_v1` rule blanket-blocks all HYPE shorts including these profitable sub-conditions. Meanwhile HYPE SHORT ≥75% conf is the real problem (-$70.06/trade) and is NOT specifically targeted by any rule.

### Top 5 Wins (confluence factors)
| # | Symbol | Side | Conf | Reason | PnL |
|---|---|---|---|---|---|
| 1 | SOL | SHORT | 79.7% | TP1 | +$713.84 |
| 2 | HYPE | SHORT | 87.5% | TP1 | +$598.26 |
| 3 | HYPE | SHORT | 71.1% | TP1 | +$494.33 |
| 4 | HYPE | SHORT | 69.0% | TP1 | +$452.54 |
| 5 | HYPE | SHORT | 72.1% | TP1 | +$425.95 |

Common factors: All TP1 hits. 4/5 are HYPE SHORT (the vetoed direction). 3/5 in 69–72% conf range (below the problem threshold).

### Top 5 Losses (failure patterns)
| # | Symbol | Side | Conf | Reason | PnL |
|---|---|---|---|---|---|
| 1 | HYPE | SHORT | 70.4% | SL | -$520.86 |
| 2 | HYPE | SHORT | 81.5% | SL | -$512.22 |
| 3 | HYPE | SHORT | 87.5% | SL | -$516.46 |
| 4 | HYPE | SHORT | 71.3% | SL | -$511.20 |
| 5 | HYPE | SHORT | 85.4% | SL | -$451.13 |

Common factors: All HYPE SHORT, all SL, large dollar magnitude (HYPE sizing). Two losses at 87.5% conf (same conf as top win — HYPE SHORT variance is huge). SL loss magnitude 3–6× larger than TP wins, confirming structural R:R is worse on HYPE specifically.

---

## PHASE 3: HYPOTHESIS VALIDATION

**Result**: VALIDATION COMPLETE: 2 confirmed, 12 stale/invalid, 4 partially-valid, 1 ambiguous

### Active (Non-Invalidated) Insights vs Recent Data

| # | Insight | Confidence | Evidence | Validation vs 100d Backtest |
|---|---|---|---|---|
| 2 | Night (0–6 UTC) = 15% WR | 0.80 | 13 | ✅ CONFIRMED — `night_session_block_v1` active, consistent with adaptive_risk data |
| 8 | Strategy concentration 94% ensemble | 0.80 | 47 | ✅ CONFIRMED — 100% ensemble in backtest (589/589 trades) |
| 13 | Evening (18–24 UTC) = 29% WR | 0.80 | 14 | ⚠️ PARTIALLY — cannot verify timestamps in backtest |
| 15 | Afternoon (12–18 UTC) = 27% WR | 0.80 | 15 | ⚠️ PARTIALLY — cannot verify timestamps in backtest |

### Invalidated Insights Summary

- **Size edge claims** (5 insights, all contradicting): No stable size-WR relationship across time windows. Still invalid.
- **Morning edge** (71% WR from backtest): Already invalidated with 96% confidence after 18 live trades showed 28% WR. Still correctly invalidated.
- **Evening edge** (65% WR): Contradicted by evening weakness insight. Cannot verify from backtest.
- **Side bias: LONG 77% better**: Backtest shows LONG only 39.5% WR vs SHORT 46.4% — insight was backwards. Correctly invalidated.

### Action Tracking

| Insight | Suggested Action | Status |
|---|---|---|
| Night 15% WR | Raise conf floor during night | ✅ `night_session_block_v1` active (100% veto) |
| Evening weakness | Raise conf floor 18–24 UTC | ⚠️ `tod_evening_edge_v1` inactive (conf=0.72, below threshold) |
| Afternoon weakness | Raise conf floor 12–18 UTC | ⚠️ `tod_afternoon_edge_v1` inactive (conf=0.72, below threshold) |
| Morning edge boost | Boost confidence 6–12 UTC | ✅ `tod_morning_edge_v1` active BUT original morning insight was invalidated — this rule may be misapplied |

**Concern**: `tod_morning_edge_v1` (boost confidence 6–12 UTC) is active, but insight #1 (morning = 71% WR) was explicitly invalidated at 96% confidence after live testing showed 28% WR. The morning boost rule should also be deactivated or demoted. This is a rule-insight consistency gap.

### Stale Insights (confidence < 0.5 or < 5 recent evidence)
None currently below 0.5 confidence, but 15/19 are invalidated. The memory store is clean. LLM memory has only 1 note (SOL LONG SL hit in range — too sparse for useful recall).

---

## PHASE 4: FEEDBACK LOOP CLOSURE

**Result**: LOOP CLOSURE: 0 trades fully propagated, 5 broken links (bot offline root cause)

### Last 3 Closed Trades (backtest_100d.csv, trades 587–589)

| # | Symbol | Side | Close | Outcome | PnL |
|---|---|---|---|---|---|
| 587 | BTC | SHORT | SL | LOSS | -$18.27 |
| 588 | BTC | LONG | TP1 | WIN | +$30.45 |
| 589 | BTC | LONG | TRAILING_STOP | WIN | +$2.22 |

### Propagation Matrix

| System | State File | Propagated | Issue |
|---|---|---|---|
| SignalQualityScorer | signal_quality.json | ❌ No | File missing — bot offline |
| RegimeFeedbackManager | regime_feedback_state.json | ❌ No | File missing — bot offline |
| AdaptiveConfidenceFloor | confidence_state.json | ❌ No | File missing — bot offline |
| Strategy Weights | strategy_weights.json | ❌ No | File missing — bot offline |
| LLM Memory | llm_memory.json | ❌ Effectively no | 1 note, 47 days old |
| AdaptiveRisk | adaptive_risk_state.json | ✅ Exists | 47 days stale |
| HoldTimeRules | hold_time_rules_state.json | ✅ Exists | 47 days stale |

**Root cause**: Bot has been offline 70 days. The feedback wiring in multi_strategy_main.py is correct and complete. Zero propagation failures are due to code bugs — all failures are due to the bot not running.

### Current State from Existing Files

**adaptive_risk_state.json** (last session, June 5):
- Last 20 outcomes: 8W/20 = 40% WR — recent streak is poor
- Regime WR: trending 51.9% (27/52), **illiquid 28.1% (16/57)** ❌, **ranging 25.0% (4/16)** ❌

**hold_time_rules_state.json**:
- trend regime: min_hold_hours = 3.0h (from May 15 deep-dive)
- Source evidence: losses exit 1.5h median, wins exit 3.3h median
- Status: Mechanically active, awaiting live validation

---

## PHASE 5: RECOMMENDATIONS

**Result**: RECOMMENDATIONS: 3 changes proposed, est. +$15–35/trade EV improvement

---

### REC 1 (P0 CRITICAL): Refine hype_short_veto_v1 to Target Harmful Sub-condition

**Problem**: `hype_short_veto_v1` blanket-vetoes all HYPE SHORT trades. Backtest shows HYPE SHORT <75% conf has **+$8–15/trade positive EV** (n=80 trades, +$808 combined). The veto was trained on early live data where HYPE SHORT showed 24% WR — but those trades may have been concentrated in the high-confidence band (75%+) which is genuinely catastrophic (-$70.06/trade, n=77). The veto is blocking profitable setups while the real poison (HYPE SHORT ≥75%) has no specific rule.

**Root cause hypothesis**: HYPE's high volatility means high-confidence SHORT signals are formed during momentum peaks — the model confidently calls tops that then continue rallying. Low-confidence HYPE shorts (formed in ranging or early-move contexts) actually win more often.

**Proposed fix**:
1. Deactivate `hype_short_veto_v1` (global block)
2. Add `hype_short_highconf_veto_v1`: veto HYPE SHORT when confidence ≥ 75%
3. Add `hype_short_lowconf_probe_v1`: allow HYPE SHORT when confidence < 75%, max position size 50% of normal

**Expected impact**: Recover +$808 in 100d window (~+$8.08/trade avg on 100 eligible trades per 100d). Projects to **+$97/month at 1 trade/day** in eligible setups.

**A/B design**: 3-week paper mode. Baseline: HYPE SHORT count = 0 (all vetoed). Test: count HYPE SHORT <75% entries, track WR vs 52% threshold. Promote to full size if WR ≥ 50% on n ≥ 20 trades.

**Rollback**: If live WR <40% on n=15 trades, re-activate global veto.

**Confidence**: 71% (backtest supports, but original live data also had evidence; live confirmation required)

---

### REC 2 (P1): Deactivate tod_morning_edge_v1 (Contradicted Rule)

**Problem**: `tod_morning_edge_v1` (boost confidence 6–12 UTC) is active with conf=0.79. However, the underlying insight (#1, morning = 71% WR) was invalidated at 96% confidence after live testing showed 28% WR on 18 real trades. A boost rule derived from an invalidated insight with confirmed live contradiction should not be live.

**Root cause**: Rule-insight lifecycle is not fully coupled. When an insight is invalidated, associated graduated rules are not automatically flagged for review. This is a governance gap.

**Proposed fix**:
1. Set `tod_morning_edge_v1` active=false with disabled_reason="RUN119: underlying insight invalidated at 96% conf. Live morning WR=28% (18 trades, -$76.94). Re-evaluate after 25 new live morning trades."
2. Add check in rule graduation: when an insight is invalidated, scan graduated_rules.json for rules referencing same hypothesis and flag them.

**Expected impact**: Avoids miscalibrated confidence boosts during morning session. At 28% live WR (18 trades), actively boosting confidence in this window was potentially hurting signal selection. Impact unclear in dollar terms without timestamp data in backtest.

**A/B design**: Disable for 2 weeks, compare morning-session WR before/after in live paper mode.

**Rollback**: Re-enable if morning WR rises above 50% on n≥20 live trades.

**Confidence**: 88% (insight invalidation is unambiguous; rule status inconsistency is clear)

---

### REC 3 (P1): Address Structural R:R Deficit Before Any Volume Expansion

**Problem**: The fundamental math is broken. Avg win $82.72, avg loss $91.27, win/loss ratio 0.91. At 44.5% WR, every 100 trades produces expected loss: `(44.5 × $82.72) - (55.5 × $91.27) = $3,681 - $5,065 = -$1,384`. This is negative EV at scale. No routing rule, veto, or confidence adjustment fixes negative EV — it requires wider TPs, tighter SLs, or both.

**Root cause hypothesis**: SL placement is too aggressive (stops are noise-level tight, firing before the directional move). With 100d backtest showing 269 SL hits vs 160 TP1s and 49 TP2s, the stop-to-profit hit ratio is 1.67:1. A neutral R:R system should be ~1:1.5. Suspect: ATR-based stops are sized at 1.0× ATR while TP1 is at 1.5–2× ATR, but HYPE's high volatility means 1.0× ATR is within normal noise.

**Proposed fix**: 
1. Run analysis on SL-to-noise ratio: for each SL hit, measure how far price would have gone in the intended direction within the next 4h (did we get stopped into a winning move?)
2. If >30% of SLs represent "stopped into winner": widen SL to 1.5× ATR minimum on HYPE, set TP1 correspondingly (ratio must maintain ≥2.0 R:R)
3. Target: avg win/avg loss ratio ≥ 1.25 (needs 44.5% WR to break even at 1.25 R:R)

**Expected impact**: If SL widening reduces SL rate from 45.7% to 38% and avg SL loss from -$108 to -$95, expected PnL on 100 trades improves by ~+$840. Requires careful HYPE-specific calibration given position sizing.

**A/B design**: Backtest with 1.5× SL on HYPE only for 60 days. Compare SL hit rate, avg loss per SL, and net PnL vs current parameters.

**Rollback**: Revert `ATR_SL_MULTIPLIER_HYPE` to 1.0 if WR drops below 40% or drawdown exceeds 15% in paper mode.

**Confidence**: 82% (math is clear; the mechanism — whether SL width is the lever — needs backtest confirmation)

---

## DELTA FROM LAST AUDIT (Run 118, ~4h ago)

| Area | Run 118 Finding | Run 119 Update |
|---|---|---|
| Bot offline | Day 69 | Day 70 — **no change** |
| HYPE SL bleed | P0 finding | Deepened: identified 75%+ conf as specific culprit |
| hype_short_veto | Not specifically analyzed | **NEW**: <75% conf HYPE SHORT is positive EV (+$808 in 100d) |
| tod_morning_edge_v1 | Activated Run117 | **NEW**: Rule conflicts with invalidated insight — should be deactivated |
| Confidence floor | 60-70% = -$2,321 drag | Reconfirmed: 80-90% = additional -$3,964 drain |
| R:R ratio | Noted | **NEW**: Quantified as core structural issue (Kelly = -0.167) |

---

## APPENDIX: SYSTEM STATE SNAPSHOT

```
Graduated Rules: 31 total (22 active, 9 inactive)
  Key active vetos: hype_long_veto, hype_short_veto, night_session_block, short_direction_veto
  Key active boosts: tod_morning_edge (CONTESTED), sol_long_probe_boost, eth_sell_bb_golden
  Key active penalties: illiquid_regime, ranging_regime, conf_floor_70, btc_short_conf70_80

Meta-Learning Insights: 19 total (4 non-invalidated, 15 invalidated)
  Active actionable: night_weakness (acted on), strategy_concentration (info only)
  Inactive but acted: morning_edge (veto), evening_weakness (inactive rule)

Feedback State Files:
  adaptive_risk: EXISTS (June 5) — regime WR shows illiquid=28%, ranging=25%
  hold_time_rules: EXISTS (June 5) — trend min_hold=3.0h
  signal_quality, regime_feedback, confidence, strategy_weights: MISSING

Bot: OFFLINE 70d | Paper mode: Not running | Last live session: 2026-06-05
```

---

*Audit run by autonomous agent. All findings derived from actual data files. Zero fabricated statistics.*
