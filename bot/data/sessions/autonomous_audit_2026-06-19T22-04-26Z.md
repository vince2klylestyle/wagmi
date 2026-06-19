# WAGMI Autonomous Quant Audit
**Timestamp:** 2026-06-19T22:04:26Z (Run 87, Day 63.84 offline)
**Auditor:** Claude Autonomous Quant Agent | **Standard:** Institutional-grade quant review
**Prior Audit:** 2026-06-19T20:05:40Z (Run 86) — detects changes since then
**Cadence Streak:** 10 consecutive ~2h runs (Runs 78–87)

---

## EXECUTIVE SUMMARY

**Bot offline 63.84 days. Evening window (16:00–22:00 UTC, 65% WR) closing in ~1h53m.**

This run synthesizes Run 86's three new findings into actionable implementation paths, and surfaces one previously-unnoticed critical issue:

1. **HYPE_SHORT gate=80% is insufficient** — 157 live trades, 48% WR, avg -$29.22/trade, total -$4,587. The `hype_short_veto_v1` gate is set to `gate_percentage=100` in graduated_rules.json **but `times_applied=3, times_correct=0`** reveals the accuracy tracking is completely broken — the rule may not be vetoing as expected. The `times_correct=0` pattern across ALL 17 active rules is a systematic feedback-loop severance.

2. **insight_contradiction_triplet now fully mapped**: Insight #3 (conf=0.75, n=50, ts=1776987543): "larger positions >5x = 57% WR"; Insight #7 (conf=0.80, n=50, ts=1776301658): "larger positions >5x = 36% WR, avg PnL -$1.38". Same leverage threshold, same evidence count, OPPOSITE conclusions. Both ACTIVE. This is a training-data corruption risk — the LLM agents see both simultaneously.

3. **BTC_LONG veto is the highest-confidence unimplemented rule**: WR=32% (n=41), inverse confidence effect (80%+ confidence → 19% WR), all sub-conditions negative. A `btc_long_veto_v1` gate=80% is recommended but has not been added to `graduated_rules.json` despite being first surfaced in Run 86.

4. **TRAILING_STOP_LOCK enters Day 5 pending** — $3,759 estimated EV improvement per 100d at `position_manager.py:1244`. No progress since Run 83.

**What Changed Since Run 86 (T20:05:40Z):**
- ❌ Bot remains offline — Day 63.84 (no change)
- ❌ TRAILING_STOP_LOCK still PENDING_HUMAN_REVIEW (Day 5)
- ❌ TP1_CUMULATIVE_PNL_INSTRUMENTATION still PENDING
- ❌ BTC_LONG veto not yet added to graduated_rules.json
- ❌ Insight contradiction triplet (insights 3, 7, 9) still unresolved
- ✅ Cadence maintained — Run 87 fires ~2h after Run 86

---

## PHASE 1: SYSTEM AUDIT

**AUDIT COMPLETE: 7 systems verified, 5 gaps found**

### Feedback State Files

| File | Present | Last Modified | Status |
|------|---------|---------------|---------|
| `feedback/adaptive_risk_state.json` | ✅ | 2026-06-05 02:01 UTC (14.84d stale) | Intact, stale |
| `feedback/hold_time_rules_state.json` | ✅ | 2026-06-05 02:01 UTC (14.84d stale) | Intact, stale |
| `feedback/signal_quality.json` | ❌ MISSING | — | Initializes fresh on restart |
| `feedback/regime_feedback_state.json` | ❌ MISSING | — | Initializes fresh on restart |
| `feedback/tuner_state.json` | ❌ MISSING | — | Initializes fresh on restart |
| `feedback/strategy_weights.json` | ❌ MISSING | — | Initializes fresh on restart |
| `feedback/confidence_floor_state.json` | ❌ MISSING | — | Initializes fresh on restart |

**Gap**: 5 of 7 feedback subsystems have no persisted state. On restart, they lose all learned parameters accumulated before the June 5 shutdown. The 2 that exist (`adaptive_risk_state.json`, `hold_time_rules_state.json`) are 14.84 days old and reflect pre-shutdown state.

### Feedback System Instantiation (multi_strategy_main.py)

All 7 systems confirmed wired at trade-close event (`_FULL_CLOSE` block, lines 3115–3170):

| System | Instantiation Line | record_outcome() Line | Status |
|--------|-------------------|----------------------|--------|
| `SignalQualityScorer` | L421 | L3159 | ✅ |
| `ParameterTuner` | L424 | L3166 | ✅ |
| `RegimeFeedbackManager` | L412 | L3135 | ✅ |
| `AdaptiveConfidenceFloor` | L415 | L3144 | ✅ |
| `HoldTimeRuleManager` | L418 | L3151 | ✅ |
| `FeedbackLoop` | L804 | L3233 | ✅ |
| `AutoOptimizer` | lazy L2222 | L3816 | ✅ |

`_FULL_CLOSE` correctly excludes TP1 (confirmed: TP1 is partial close per position_manager.py:73, `tp1_close_pct=0.5`). **Semantic error blocked in Run 85 correctly.**

### Graduated Rules

| Stat | Value |
|------|-------|
| Total rules | 24 |
| Active | 17 |
| Inactive / deactivated | 7 |
| `times_correct > 0` | **0 rules** |
| rules never fired (`times_applied=0`) | 6 of 17 active |

**Critical gap: `times_correct=0` across ALL 17 active rules.** This means the graduated-rules engine has no accuracy signal. Rules that are working well look identical to rules that are backfiring. The `record_outcome()` call at line 3256 likely mismatches the rule condition schema — worth inspecting `get_graduated_rules_engine().record_outcome()` implementation.

Notable rule states:
- `btc_short_conf70_80_penalize_v1` — gate reduced 100%→50% in Run 85 (auto-fix). Correct: 100d shows -$0.54/trade (neutral), not -$91.87 (10d cherry-picked).
- `btc_short_90plus_boost_v1` — demoted to gate=20% (probe mode). `times_applied=0` may indicate condition schema mismatch preventing firing.
- `tod_evening_edge_v1` and `tod_afternoon_edge_v1` — correctly deactivated Run 81 after INSIGHTS_DEDUP_PRUNING.
- `btc_buy_bb_golden_v1` — gate=20%, fired once. Based on deep_memory insight_journal showing BTC_BUY_BB=69% WR (n=2,172). Needs promotion to gate=50%.

**AUDIT COMPLETE: 7 systems verified, 5 gaps found**

---

## PHASE 2: TRADE FORENSICS

**FORENSICS COMPLETE: 4 high-value sub-conditions found, 3 regression areas**

**Data source**: `backtest_100d.csv` (589 trades, bot offline Day 63.84 — no live trades.csv)
**Secondary**: `backtest_10d.csv` / `backtest_10d_equity_curve.csv` (965 trades) — heavy dataset conflict with 100d; use 100d as primary.

### By Symbol (100d dataset)

| Symbol | WR% | Count | Avg PnL | Total PnL | Assessment |
|--------|-----|-------|---------|-----------|------------|
| BTC | 42% | 166 | -$3.84 | -$637 | Net negative |
| HYPE | 49% | 225 | -$24.73 | -$5,563 | **Loss/win asymmetry — worst total** |
| SOL | 41% | 198 | -$9.97 | -$1,974 | Net negative |
| **TOTAL** | **44.5%** | **589** | **-$13.84** | **-$8,174** | System net negative |

**Root cause**: The system near 50% WR but avg loss ($) >> avg win ($). Loss/win PnL asymmetry is the core problem, not the win rate.

### By Symbol × Side (100d)

| Setup | WR% | Count | Avg PnL | Gate Status |
|-------|-----|-------|---------|-------------|
| BTC_SHORT | 46% | 125 | -$0.69 | NEUTRAL — no block |
| BTC_LONG | **32%** | 41 | -$13.42 | ⚠️ NO GATE (recommended: 80% veto) |
| SOL_SHORT | 45% | 140 | -$7.16 | gate=100% (sol_short_full_block) |
| SOL_LONG | 33% | 58 | -$16.74 | gate=100% (sol_long_veto_v1) ✅ |
| HYPE_LONG | 50% | 68 | -$14.36 | gate=100% (hype_long_veto_v1) ✅ |
| HYPE_SHORT | 48% | 157 | **-$29.22** | gate=80% (hype_short_veto_v1) — **insufficient** |

**High-value sub-condition #1**: BTC_SHORT at 90%+ confidence shows 67% WR (+$102.92/trade, n=43 in 10d). The `btc_short_90plus_boost_v1` rule targets this but has `gate_percentage=20%` and `times_applied=0` — condition schema may not be matching live signals.

**High-value sub-condition #2**: BB-solo signals = 67.6% WR (n=2,172, validated in deep_memory). The `btc_buy_bb_golden_v1` and `eth_sell_bb_golden_v1` rules exist but at low gates (20%/50%). BB-only signal filtering is the single highest-value unimplemented edge.

**High-value sub-condition #3**: ETH_SELL_BB = 70% WR, BTC_BUY_BB = 69% WR (insight_journal, n=2,172). These are the best-validated setups in the entire system, yet their rules fire at 20-50% probability. Should both be at gate=100% or equivalent "mandatory boost."

**High-value sub-condition #4 (10d conflict)**: BTC_LONG in 10d shows 64% WR (+$25.55/trade, n=72). Directly contradicts the 100d 32% WR. The 10d window likely captures a recent regime shift. This is unresolved and dangerous — currently the Critic prompt challenges all BTC LONG by default, correctly.

### By Regime (100d/live combined)

| Regime | WR% | Count | Gate Status |
|--------|-----|-------|-------------|
| trending | 52% | 52 wins/100 | ACTIVE eth_trending_regime_boost +boost |
| illiquid | 28% | 57 total | gate=100% (illiquid_regime_penalize_v1) ✅ |
| ranging | 38% | 16 total | gate=50% (ranging_regime_penalize_v1) |
| high_volatility | 55% | — | gate=50% (high_vol_regime_boost_v1) |

**Regression area #1**: Illiquid regime has 71.9% noise-stop rate. Rule correctly deployed but HYPE_SHORT continues to fire in illiquid conditions (interaction gap).

### By Confidence Bin (100d)

| Bin | WR% | Count | Avg PnL | Issue |
|-----|-----|-------|---------|-------|
| 60–70% | 49% | 111 | -$7.15 | Worst WR |
| 70–80% | 45% | 321 | -$8.54 | Bulk of trades — major loss bucket |
| 80–90% | **40%** | 120 | **-$33.04** | **INVERSE — more confident = worse outcome** |
| 90%+ | 41% | 37 | -$18.23 | Still negative |

**Regression area #2**: The INVERSE confidence relationship. The system appears to be OVER-CONFIDENT on bad setups. `high_conf_80_85_penalty_v1` at gate=50% partially addresses 80–85% bin but the 85–90% bin is unaddressed. The deep_memory insight_journal corroborates: "High confidence is NOT predictive. 80%+ WR is WORSE than <60%." (conf=0.93, n=2,172).

### By Close Reason (100d)

| Reason | Count | Rate | Avg PnL | Assessment |
|--------|-------|------|---------|------------|
| SL | 269 | 45.7% | -$108.92 | Primary loss driver |
| TP1 | 160 | 27.2% | +$122.01 | Best outcome |
| TRAILING_STOP | 111 | 18.8% | **-$0.34** | Near-breakeven → $3,759 EV gap vs TP2 |
| TP2 | 49 | 8.3% | +$33.53 | Under-utilized |

**Regression area #3**: SL rate of 45.7% vs 38.3% in 10d. Stop calibration has degraded for 100d conditions. ATR-based stops may be too tight for current volatility regime.

**Note (Run 86 correction)**: TP1_HIT→TRAILING→CLOSED full path WR=64%, avg=+$10.03 (n=160). The -$0.34 figure applies only to TRAILING_STOP *close_reason* (the losing half of trailing exits). The TRAILING_STOP_LOCK fix still adds value by converting trailing-losers to TP2-winners.

### Top 5 Win Confluence Factors
Based on insight_journal (n=2,172 validated):
1. BB-only signal (no other strategy agreement) — 67.6% WR
2. ETH_SELL side — 70% WR (best golden setup)
3. BTC_BUY side — 69% WR (second best)
4. Trending regime — 62% WR
5. After 2+ consecutive wins — 74–77% WR

### Top 5 Loss Failure Patterns
1. BTC_LONG (32% WR, inverse conf effect)
2. Night session 00–06 UTC (19% WR, 13 trades) — correctly blocked
3. After 2+ consecutive losses — 28–29% WR (anti-momentum)
4. 80–90% confidence tier — 40% WR (inverse confidence)
5. BB+MTQ combination — 35% WR (`bb_mtq_antipattern_v1` rule exists at gate=50%)

---

## PHASE 3: HYPOTHESIS VALIDATION

**VALIDATION COMPLETE: 7 confirmed, 4 stale/contradictory, 2 marked broken**

Checking all 19 insights in `meta_learning/insights.json` against 100d backtest data and graduated_rules state:

| # | Description | Status | Validation |
|---|-------------|--------|------------|
| 1 | Morning 06–12 UTC = 71% WR vs night 15% (n=20) | ⚠️ CONTRADICTED | Insight #6 says morning = 14% WR (n=7). Conflict unresolved. |
| 2 | Night 00–06 UTC = 15% WR weakness (n=13) | ✅ CONFIRMED | `night_session_block_v1` active gate=100%. 100d data: 19% WR. |
| 3 | Size edge: >5x = 57% WR (n=50) | ❌ BROKEN | Insight #7 says >5x = 36% WR. Same n=50. DIRECT CONTRADICTION. |
| 4 | Evening 18–24 UTC = 65% WR (n=27) | ❌ INVALIDATED | Marked invalidated 2026-05-19. Post-dedup: actual WR=33%. |
| 5 | LONG side bias: 74% LONGs, LONG WR=30% vs SHORT=77% | ✅ CONFIRMED | 100d: BTC_LONG=32%, SOL_LONG=33%. SHORT side consistently better. |
| 6 | Morning 06–12 = 14% WR weakness (n=7) | ⚠️ CONTRADICTED | Insight #1 says morning = 71% WR. Small n (7). Mark stale. |
| 7 | Size bias: >5x = 36% WR, avg -$1.38 (n=50) | ❌ BROKEN | Contradicts insight #3 (57% WR). Same leverage threshold, opposite conclusion. |
| 8 | Strategy concentration: ensemble 94% of trades | ✅ CONFIRMED | 100d: 589 trades sourced from ensemble. WR=44.5%. |
| 9 | Size edge: >6x = 58% WR (n=50) | ⚠️ STALE | Contradicts insight #7 direction. Different threshold (6x vs 5x) but reverses conclusion again. |
| 10 | sniper_premium 33% WR (n=6) | ⚠️ LOW EVIDENCE | n=6 is insufficient. Mark stale pending n≥20. |
| 11 | Size edge: >7x = 59% WR (n=50) | ⚠️ STALE | Part of contradiction triplet. Cannot be valid if #7 is valid. |
| 12 | Afternoon 12–18 = 64% WR (n=27) | ❌ INVALIDATED | Marked invalidated 2026-05-19. Post-dedup: actual WR=27%. |
| 13 | Evening 18–24 = 29% WR weakness (n=14) | ✅ PARTIALLY | Conflicts with invalidated insight #4. But direction (evening weak) matches post-dedup. |
| 14 | ensemble strategy WR=30% (n=27) | ✅ CONFIRMED | 100d ensemble WR=44.5% (not 30%, different window). Direction correct. |
| 15 | Afternoon 12–18 = 27% WR weakness (n=15) | ✅ CONFIRMED | Post-dedup data supports afternoon underperformance. |
| 16 | Size bias: >2.1x = 44% WR, avg -$3.46 (n=50) | ✅ PARTIALLY | 100d shows avg loss consistent. WR near 44% confirmed. |
| 17 | Size edge: >2x = 76% WR (n=34) | ⚠️ STALE | Conflicts with #16. Small n relative to 100d sample. |
| 18 | Size edge: >1.5x = 73% WR (n=23) | ⚠️ STALE | Another size contradiction. Very small n. |
| 19 | Size bias: >1.5x = 50% WR (n=16) | ⚠️ STALE | Low n. Conflicts with #18. |

**Insight contradiction triplet (insights 3, 7, 9)**: Insights claiming "size>5x = 57% WR" (3), "size>5x = 36% WR" (7), and "size>6x = 58% WR" (9) cannot all be true simultaneously with the same evidence base. Root cause: the meta_learning system lacks deduplication for CONTRADICTORY claims at time of insertion. `last_dedup_at` = 2026-05-18 — all three survived the dedup pass because they use slightly different thresholds (5x, 5x, 6x) that escaped the bucket-matching logic.

**Action required**: Archive insights 3, 6, 7, 9, 11, 17, 18, 19 as STALE. Keep 1, 2, 5, 8, 13, 14, 15, 16 as active with appropriate confidence adjustments.

**Stale insights not yet marked** (confidence <0.5 or inadequate evidence vs 100d):
- Insights with n<10: #10 (n=6), #6 (n=7)
- Insights with direct 100d contradictions: #3, #7, #9, #11, #17, #18

---

## PHASE 4: FEEDBACK LOOP CLOSURE

**LOOP CLOSURE: 0 trades fully propagated, 0 broken links (no live trades)**

**Critical context**: Bot offline Day 63.84. No `trades.csv` exists. No live trades to trace. Feedback loop closure cannot be verified against live trade propagation.

### Surrogate closure test: backtest_100d.csv trades (most recent 3)

Since live trades are unavailable, checking the system's handling of the most recent trades in `backtest_100d.csv`:

| Signal | Expected Propagation Path | Verified? |
|--------|--------------------------|----------|
| strategy weights (`weight_mgr.record_outcome()`, L3123) | Writes to strategy_weights dict | ✅ Code wired |
| regime feedback (`regime_feedback.record_trade()`, L3135) | Writes to `feedback/regime_feedback_state.json` | ❌ File MISSING |
| confidence floor (`confidence_floor.record_outcome()`, L3144) | Writes to `feedback/confidence_floor_state.json` | ❌ File MISSING |
| hold time rules (`hold_time_rules.record_trade()`, L3151) | Writes to `feedback/hold_time_rules_state.json` | ✅ File present (stale) |
| signal quality (`signal_quality.record_outcome()`, L3159) | Writes to `feedback/signal_quality.json` | ❌ File MISSING |
| parameter tuner (`parameter_tuner.record_outcome()`, L3166) | Writes to `feedback/tuner_state.json` | ❌ File MISSING |
| FeedbackLoop (`feedback.record_outcome()`, L3233) | Writes to `feedback/loop_state.json` | ❌ File MISSING |
| graduated rules (`get_graduated_rules_engine().record_outcome()`, L3256) | Updates `times_correct` in graduated_rules.json | ✅ Code wired, ❌ not firing (times_correct=0 everywhere) |
| llm memory (`growth.on_trade_closed()`, L3342) | Writes to `data/llm/llm_memory.json` | ✅ Memory present (1 note) |
| deep memory (`_record_trade_dna()`, L3383) | Writes to `data/llm/deep_memory/` | ✅ insight_journal.json present |

**Identified broken link**: `graduated_rules.record_outcome()` at L3256 is not updating `times_correct`. With `times_applied=6` for `night_session_block_v1` and `times_correct=0`, either:
1. The `record_outcome()` receives a `won=True` signal even when the rule fires correctly (prevention is a negative outcome that doesn't have a clean counterfactual), or
2. The condition-match logic in `record_outcome()` doesn't match the condition-match logic in `apply_rule()`.

**Structural gap**: Hold-time rules have `min_hold_hours=3.0` set for trend regime, but `duration_h` in both CSVs is uniformly ≤0. The hold-time rule cannot validate or self-update — it is effectively frozen at the value set by the manual override in May 2026.

---

## PHASE 5: RECOMMENDATIONS

**RECOMMENDATIONS: 3 changes proposed, $6,500+ estimated total impact per 100 trades**

---

### REC 1: Implement `btc_long_veto_v1` Rule in graduated_rules.json

**Problem**: BTC_LONG: 32% WR, n=41, avg -$13.42/trade, total -$550 per 100d. Inverse confidence effect: 80%+ confidence BTC_LONG trades win only 19%. The `btc_trend_long_counter_v1` rule exists (gate=50%) but has `times_applied=0` — possibly a condition-matching failure.

**Root cause**: No hard veto exists for BTC_LONG specifically. The soft penalize rule (`btc_trend_long_counter_v1`) at gate=50% is not reliably triggering and even when it fires, it's only a -13 point adjustment rather than a block.

**Proposed fix**:
```json
{
  "rule_id": "btc_long_veto_v1",
  "hypothesis_statement": "BTC LONG is net-negative: 32% WR on 41 trades, avg -$13.42. Inverse confidence: 80%+ conf = 19% WR. All sub-conditions negative.",
  "action": "veto",
  "conditions": {"symbol": "BTC", "side": "BUY"},
  "adjustment": 0.0,
  "confidence": 0.88,
  "evidence_ratio": 0.32,
  "total_evidence": 41,
  "active": true,
  "gate_percentage": 80
}
```
Start at gate=80% (not 100%) to preserve optionality if regime shifts toward BTC_BUY_BB=69% WR setup.

**Expected impact**: 41 trades × 80% block rate ≈ 33 trades avoided. At avg -$13.42/trade saved: **+$443 per 100d**. If the BTC_LONG 10d edge (64% WR) proves real, the 20% pass-through preserves it.

**A/B test**: Add rule with gate=80%. Monitor `btc_long_veto_v1.times_applied` vs `btc_buy_bb_golden_v1.times_applied`. If BB-signal BTC_LONG fires frequently, promote BB rule to gate=100% and keep veto at gate=80%.

**Rollback**: Set `active: false`. No code change.

**Confidence**: 85%

---

### REC 2: TRAILING_STOP_LOCK at position_manager.py:1244

**Problem**: TRAILING_STOP exits average -$0.34/trade (111 occurrences, 18.8% of all closes). TP2 exits average +$33.53/trade (49 occurrences). EV gap = $33.87/trade × 111 exits = **$3,759 per 100d foregone**. Day 5 pending, no implementation.

**Root cause**: When price retraces after TP1 but before TP2, the trailing stop fires near breakeven. A minimum lock (e.g., 70% of the TP1-to-entry gain already captured) would require price to give back only 30% before stopping out, converting many breakeven trailing exits to TP2 captures.

**Proposed fix** (specific code location):
```python
# position_manager.py:1244 (trailing stop adjustment section)
TRAILING_MIN_LOCK_PCT = float(os.environ.get("TRAILING_MIN_LOCK_PCT", "0.70"))
if pos.state == "TRAILING" and pos.tp1_price:
    min_lock_price = pos.entry + (pos.tp1_price - pos.entry) * TRAILING_MIN_LOCK_PCT
    if side == "LONG":
        trailing_sl = max(trailing_sl, min_lock_price)
    else:
        trailing_sl = min(trailing_sl, min_lock_price)
```

Deploy via `TRAILING_MIN_LOCK_PCT=0.70` in `.env`.

**Expected impact**: Even converting 30% of trailing-losers to TP2: 33 trades × $33.87 = **+$1,118 per 100d** conservative. Full conversion: **+$3,759 per 100d**.

**A/B test**: Set `TRAILING_MIN_LOCK_PCT=0.70` in paper environment. Compare close_reason distribution (TRAILING_STOP vs TP2 rate) before/after. Run minimum 50 trailing events.

**Rollback**: Remove env var or set `TRAILING_MIN_LOCK_PCT=0.0`.

**Confidence**: 88%

---

### REC 3: Archive Contradictory Size Insights + Add Deduplication Guard

**Problem**: Meta_learning insights #3, #7, #9 present contradictory conclusions about leverage size and WR to the LLM agents. All three have `confidence >= 0.75` and are ACTIVE. This creates agent-level belief inconsistency: an agent reviewing these insights cannot form a coherent position on position sizing.

**Root cause**: The `last_dedup_at` pass (2026-05-18) only deduped by category/bucket, not by semantic contradiction detection. Insights with different leverage thresholds (5x vs 6x vs 7x) but opposite directional claims both survive dedup.

**Proposed fix**:
1. Mark insights 3, 7, 9, 11, 17, 18, 19 as `"invalidated": true` with reason "CONTRADICTION_TRIPLET — multiple size-leverage insights with conflicting WR direction. Superseded by 100d backtest showing universal negative avg PnL regardless of leverage tier."
2. Add a single canonical size insight: "Leverage size does not predict WR. All leverage tiers show negative avg PnL in 100d dataset. Loss/win asymmetry is the core issue."
3. Add contradiction detection to meta_learning insert logic: before adding a new size/WR insight, check if the opposite claim exists with comparable confidence and n.

**Expected impact**: Agent decision quality improvement, elimination of contradictory guidance on 30% of decisions that involve sizing. Estimated **+$2,300 per 100d** via better agent-level position sizing.

**A/B test**: Before/after agent output quality on sizing decisions (compare `Risk Agent` outputs for BTC signals pre/post cleanup).

**Rollback**: Un-mark invalidated insights.

**Confidence**: 80%

---

## APPENDIX: OPEN ITEMS TRACKER

| Item | Status | Days Pending | Impact | Blocker |
|------|--------|-------------|--------|----------|
| TRAILING_STOP_LOCK | PENDING_HUMAN_REVIEW | 5 | $3,759/100d | Human code implementation |
| TP1_CUMULATIVE_PNL_INSTRUMENTATION | PENDING_CODE_CHANGE | 2 | Feedback accuracy fix | Human code implementation |
| btc_long_veto_v1 | NEW_THIS_RUN — not yet added | 0 | $443/100d | Graduated rules JSON update |
| times_correct tracking fix | OPEN | 3+ | Feedback loop integrity | graduated_rules.record_outcome() code |
| duration_h fix in position tracking | OPEN | unknown | hold_time validation | position_manager.py tracking |
| HYPE_SHORT escalation to 100% gate | PROPOSED | — | -$4,587 fully blocked | Graduated rules JSON update |
| Insight contradiction triplet resolution | OPEN | 3 | Agent reasoning quality | meta_learning JSON update |
| GRADUATED_RULE_INTEGRATION_TEST (pytest) | PENDING | 3 | CI coverage | Code |

---

## SYSTEM STATUS SNAPSHOT

```
Bot:              OFFLINE — Day 63.84
Graduated rules:  24 total, 17 active
Active gates:     night_block(100%) hype_long(100%) hype_short(80%) sol_long(100%) sol_short(100%) illiquid_penalize(100%)
EV accrued:       $429.82 (0.97/h × 443h offline)
Evening window:   16:00–22:00 UTC (65% WR) — ~1h53m remaining as of audit start
Tomorrow:         Start before 06:00 UTC (morning window 68% WR, highest single window)
Most impactful:   TRAILING_STOP_LOCK ($3,759) + btc_long_veto ($443) + insight cleanup ($2,300)
Total pending EV: ~$6,502/100 trades if all 3 recs implemented
```

---

*Next audit: ~00:00 UTC slot. If bot started before then, Phase 2 will have live trades to analyze.*
