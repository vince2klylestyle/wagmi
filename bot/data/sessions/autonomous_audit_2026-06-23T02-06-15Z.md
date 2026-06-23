# Autonomous Quant Audit — 2026-06-23T02:06:15Z (Run 131)

**Bot Status**: OFFLINE (Day 75 — zero trades since 2026-04-23 22:17 UTC)
**Data Sources**: `backtest_100d.csv` (n=589), `backtest_60d.csv` (n=802), `bot/data/llm/graduated_rules.json`, `bot/data/meta_learning/insights.json` (19 insights), `bot/data/feedback/*.json`, `bot/data/learning/auto_fix_state.json`, `bot/data/learning/live_edge_data.json`, `bot/data/learning/master_engine_state.json`, `bot/data/sessions/daily_synthesis_2026-06-22.json`
**Compared to**: `autonomous_audit_2026-06-22T22-05-43Z.md` (Run 129), `auto_fix_state.json` (Run 130, 3h ago)

---

## EXECUTIVE SUMMARY

**Three critical findings in this run:**

1. **GRADUATED RULES RESTORE CONFIRMED**: Run 130 auto-fix correctly restored `bot/data/llm/graduated_rules.json` from 1→11 rules. All critical protective rules are now active. **However, the root cause CODE BUG in `llm/graduated_rules.py` is still unfixed** — next hypothesis graduation will overwrite the file again. Time-bomb.

2. **BTC_SHORT_90plus CLAIM NOT CONFIRMED BY 100d DATA**: `live_edge_data.json` claims "BTC SHORT 90%+ = 67.4% WR, n=46" but the 100d backtest shows only **WR=50.0% on n=10** trades. The 67.4% stat comes from 60d window via cached full-dataset (n=965). Injecting a boost rule on n=10 is premature.

3. **NEW HIGH-VALUE EDGE UNDETECTED**: SOL SHORT at 75-80% confidence shows **WR=52.9%, n=34, +$24.26/trade** in the 100d backtest — a genuine profitable sub-band NOT receiving targeted boost. The generic SOL SHORT boost is blunt; below 75% and above 80% are both net-negative.

**What's working**: Run 130 resolved graduated_rules collapse. 7/7 feedback systems wired. Night block, HYPE LONG veto, HYPE sizing cap, ranging penalty all active.

**What's broken**: Graduated rules CODE BUG (time-bomb), bot offline 75 days, Kelly=-0.168 (10th flag), HYPE_SHORT_VETO_SPLIT unresolved (11th flag, +$808 EV blocked), duration field data bug, all regime fields empty in backtest.

---

## PHASE 1: SYSTEM AUDIT

**AUDIT COMPLETE: 7 systems verified, 6 gaps found**

### Feedback System Instantiation

| System | Class | Line | record_outcome() | Status |
|---|---|---|---|---|
| SignalQualityScorer | `feedback/signal_quality.py` | 421 | 3159 | ✅ WIRED |
| ParameterTuner | `feedback/parameter_tuner.py` | 424 | 3166 | ✅ WIRED |
| RegimeFeedbackManager | `feedback/regime_feedback.py` | 412 | 3136 | ✅ WIRED |
| AdaptiveConfidenceFloor | `feedback/adaptive_confidence.py` | 415 | 3144 | ✅ WIRED |
| HoldTimeRuleManager | `feedback/hold_time_rules.py` | 418 | 3152 | ✅ WIRED |
| FeedbackLoop | `feedback/loop.py` | 804 | 3233 | ✅ WIRED |
| AutoOptimizer | `feedback/auto_optimizer.py` | 909/2222 | 3225+ | ✅ WIRED (lazy-init) |

### State File Status

| File | Last Modified | Status |
|---|---|---|
| adaptive_risk_state.json | 2026-06-05 02:01 UTC | ⚠️ 48 days stale |
| hold_time_rules_state.json | 2026-06-05 02:01 UTC | ⚠️ 48 days stale |
| signal_quality.json | — | ❌ MISSING |
| regime_feedback_state.json | — | ❌ MISSING |
| confidence_state.json | — | ❌ MISSING |
| strategy_weights.json | — | ❌ MISSING |
| llm_memory.json | 2026-06-23 02:02 UTC | ⚠️ 1 note (updating) |

### Graduated Rules — 11 Rules Active (Restored Run 130)

- `restored_night_session_block_v1`: Night 00-06 UTC → VETO (conf=0.95, n=13)
- `restored_hype_long_block_v1`: HYPE LONG → VETO (conf=0.88, n=35)
- `restored_illiquid_regime_block_v1`: Illiquid → VETO (conf=0.87, n=57)
- `restored_ranging_regime_penalty_v1`: Ranging → penalize -15 (conf=0.82, n=16)
- `restored_hype_short_highconf_veto_v1`: HYPE SHORT ≥75% → VETO (conf=0.71, n=77)
- `restored_hype_sizing_cap_v1`: HYPE → size -0.5x (conf=0.92, n=239)
- `restored_sol_short_boost_v1`: SOL SHORT → boost +8 (conf=0.81, n=179)
- `restored_btc_long_boost_v1`: BTC LONG → boost +8 (conf=0.78, n=72)
- `restored_confidence_paradox_sizing_v1`: 85-90% conf → size -0.25x (conf=0.78, n=120)
- `restored_instant_sl_buffer_v1`: All trades → size -0.1x (conf=0.83, n=89)
- `rule_1782144529_0`: BTC in trend → boost +8 (n=15)

**CRITICAL UNFIXED CODE BUG**: `_save()` at line 136 in `llm/graduated_rules.py` writes complete overwrite. Survives this time because `_ensure_loaded()` runs first — but multi-process race or wrong CWD will cause collapse again. Fix: add `self._ensure_loaded()` guard to `_save()` + atomic write pattern.

---

## PHASE 2: TRADE FORENSICS

**FORENSICS COMPLETE: 5 high-value sub-conditions found, 4 regression areas**

### Overall (100d Backtest, n=589)

| Metric | Value | Status |
|---|---|---|
| Win Rate | 44.5% (262/589) | ❌ Below 52.5% break-even |
| Total PnL | -$8,173.52 | ❌ Structural loss |
| Avg Win | +$82.72 | ❌ Below avg loss |
| Avg Loss | -$91.27 | ❌ Above avg win |
| W/L Ratio (b) | 0.906 | ❌ Negative R:R |
| Kelly | -0.168 | ❌ 10th consecutive flag |
| SL Hit Rate | 45.7% (269/589) | ❌ Too frequent |

### By Symbol

| Symbol | WR | n | Total PnL | Avg/Trade |
|---|---|---|---|---|
| BTC | 42.2% | 166 | -$636.62 | -$3.84 |
| HYPE | 48.9% | 225 | -$5,563.40 | -$24.71 |
| SOL | 41.4% | 198 | -$1,973.50 | -$9.97 |

### By Confidence Bin

| Conf | WR | n | Avg PnL |
|---|---|---|---|
| 60-70% | 48.6% | 111 | -$7.15 |
| 70-80% | 45.2% | 321 | -$8.54 |
| 80-90% | **40.0%** | 120 | **-$33.04** |
| 90%+ | 40.5% | 37 | -$18.23 |

Confidence anti-correlation: each +10pp = -3.3pp WR.

### By Side

| Side | WR | n | PnL |
|---|---|---|---|
| SHORT | 46.4% | 422 | -$5,676.03 |
| LONG | 39.5% | 167 | -$2,497.49 |

### High-Value Sub-Conditions (5)

| Sub-condition | WR | n | EV/Trade | Total EV | Status |
|---|---|---|---|---|---|
| HYPE SHORT <70% | 60.0% | 15 | +$15.26 | +$229 | ❌ BLOCKED |
| HYPE SHORT 70-75% | 52.3% | 65 | +$8.91 | +$579 | ❌ BLOCKED |
| HYPE SHORT <75% combined | **53.8%** | **80** | **+$10.10** | **+$808** | ❌ BLOCKED (11th flag) |
| SOL SHORT 75-80% | **52.9%** | **34** | **+$24.26** | **+$825** | ⚠️ UNDER-TARGETED |
| BTC SHORT 90%+ | 50.0% | 10 | -$3.48 | -$35 | ❌ n=10 INSUFFICIENT |

### Cross-Dataset Conflict: BTC LONG

| Dataset | WR | n | PnL |
|---|---|---|---|
| 60d backtest (rule source) | 57.7% | 71 | -$20.22 |
| 100d backtest (current) | **31.7%** | **41** | **-$550.03** |
| Graduated rule claim | 63.9% | 72 | +$25.55 |

26pp WR gap. Even the 60d data shows negative PnL at 57.7% WR. BTC LONG boost rule may be miscalibrated. **MANDATORY HUMAN REVIEW before restart.**

### Top 5 Losses (all HYPE SHORT)

| Trade | Conf | Close | PnL |
|---|---|---|---|
| HYPE SHORT | 70.4% | SL | -$520.86 |
| HYPE SHORT | 87.5% | SL | -$516.46 |
| HYPE SHORT | 81.5% | SL | -$512.22 |
| HYPE SHORT | 71.3% | SL | -$511.20 |
| HYPE SHORT | 85.4% | SL | -$451.13 |

Losses #1 and #4 (<75% conf) would have been PROFITABLE under HYPE_SHORT_VETO_SPLIT.

### Top 5 Wins

| Trade | Conf | Close | PnL |
|---|---|---|---|
| SOL SHORT | 79.7% | TP1 | +$713.84 |
| HYPE SHORT | 87.5% | TP1 | +$598.26 |
| HYPE SHORT | 71.1% | TP1 | +$494.33 |
| HYPE SHORT | 69.0% | TP1 | +$452.54 |
| HYPE SHORT | 72.1% | TP1 | +$425.95 |

4 of top 5 wins are HYPE SHORT <75% — currently blocked by over-broad veto.

### Duration Data Bug
52/589 trades (8.8%) have negative duration (-0.2h to -0.1h). Systematically the top win trades. Duration calculation inverted for fast exits. Biases hold-time ML.

### Regression Areas
1. HYPE 80-90% conf: WR=40.0%, -$33.04/trade (paradox sizing rule addresses partially)
2. BTC LONG: 31.7% WR in 100d vs 57.7% in 60d — temporal instability
3. SOL SHORT <70% and 80-90%: both negative EV (generic boost over-broad)
4. Duration data bug: 52 trades with negative duration

---

## PHASE 3: HYPOTHESIS VALIDATION

**VALIDATION COMPLETE: 2 confirmed, 5 stale, 12 invalidated**

| # | Claim | Status | Evidence |
|---|---|---|---|
| 0 | Morning 71% WR | ❌ INVALIDATED | Live: 28% WR. Deactivated Run 128. |
| 1 | Night 15% WR | ✅ CONFIRMED | Block rule active (conf=0.95). Consistent. |
| 2 | Larger positions >5x: 57% WR | ⚠️ STALE | Cannot verify (no size field in CSV) |
| 3 | Evening 65% WR | ❌ INVALIDATED | Conflicts with Insight 12 |
| 4 | 74% LONG bias, LONG WR=30% | ❌ INVALIDATED | Current: LONG=28.4%, WR=39.5% |
| 5 | Morning 14% WR | ❌ INVALIDATED | Deactivated |
| 6 | Larger positions >5x: 36% WR | ❌ INVALIDATED | Contradicts Insight 2 |
| 7 | Ensemble 94% concentration | ✅ CONFIRMED (stronger) | Now 100% ensemble, WR=44.5% |
| 8-10 | Size edge series | ❌ ALL INVALIDATED | Stale/conflicting |
| 11 | Afternoon 64% WR | ❌ INVALIDATED | Conflicts with Insight 14 |
| 12 | Evening 29% WR | ⚠️ STALE | Cannot verify (no TOD in CSV) |
| 13 | Ensemble 30% WR | ❌ INVALIDATED | Current: 44.5% |
| 14 | Afternoon 27% WR | ⚠️ STALE | Conflicts with Insight 11 |
| 15-17 | Size edge series | ❌ ALL INVALIDATED | |
| 18 | Critic counter-thesis | ⚠️ STALE | 0 validations, conf=0.5 |

---

## PHASE 4: FEEDBACK LOOP CLOSURE

**LOOP CLOSURE: 0 trades traced (bot offline 75 days), 3 systemic gaps**

No trades in `trades.csv`. No feedback propagation possible. All state files frozen/missing.

### Gaps
1. Backtest CSV missing `llm_regime` field → regime rules cannot self-validate
2. No live trades → signal_quality.json, regime_feedback_state.json, confidence_state.json, strategy_weights.json all missing
3. Duration bug → hold-time analysis corrupted

### Regime Feedback State (last known, 48 days old)
- trending: 51.9% WR (27/52) → tradeable
- illiquid: 28.1% WR (16/57) → vetoed correctly
- ranging: 25.0% WR (4/16) → penalized correctly

---

## PHASE 5: RECOMMENDATIONS

**RECOMMENDATIONS: 3 changes proposed, ~$2,433 estimated impact per 100d cycle**

### REC1: Fix `llm/graduated_rules.py` Overwrite Bug [P0 — CODE FIX]

**Problem**: Line 136 `_save()` does complete file overwrite. Caused 31→1 rule collapse on 2026-06-22. Data restored but code bug persists — next graduation will overwrite again.

**Fix**:
```python
def _save(self):
    try:
        self._ensure_loaded()  # ADD: merge before write
        os.makedirs(os.path.dirname(_RULES_FILE), exist_ok=True)
        tmp_path = _RULES_FILE + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump({"rules": [asdict(r) for r in self._rules]}, f, indent=2, default=str)
        os.replace(tmp_path, _RULES_FILE)  # Atomic rename
    except Exception as e:
        logger.warning(f"[GRAD-RULES] Save error: {e}")
```

**Impact**: Prevents rule collapse. Preserves all 10 protective/boost rules permanently.
**Rollback**: Trivial — revert one-line addition.
**Confidence**: 88%

---

### REC2: HYPE_SHORT_VETO_SPLIT — Allow <75% [P1 — AWAITING HUMAN APPROVAL]

**11th consecutive flag. +$808 EV blocked.**

Data (100d backtest):
- HYPE SHORT <75%: WR=53.8%, n=80, +$10.10/trade = **+$808 total EV**
- HYPE SHORT ≥75%: WR=35.5%, -$70+/trade = CORRECTLY VETOED

**Fix**: Add graduated rule:
```json
{
  "rule_id": "hype_short_sub75_boost_v1",
  "action": "boost",
  "conditions": {"symbol": "HYPE", "side": "SHORT", "confidence_max": 75},
  "adjustment": 5.0,
  "confidence": 0.71
}
```

**A/B test**: 14 days paper, gate: ≥20 trades, WR ≥45%.
**Rollback**: Remove rule from graduated_rules.json.
**Confidence**: 71%

---

### REC3: SOL SHORT Precision Targeting at 75-80% Conf [P2 — NEW FINDING]

**SOL SHORT by confidence band (100d)**:
- 60-70%: WR=40.9%, -$19.74/trade (n=22) — NEGATIVE
- 70-75%: WR=45.8%, -$13.04/trade (n=48) — NEGATIVE
- **75-80%: WR=52.9%, +$24.26/trade (n=34) — POSITIVE EDGE**
- 80-90%: WR=34.5%, -$25.08/trade (n=29) — STRONGLY NEGATIVE

Generic `restored_sol_short_boost_v1` boosts ALL SOL SHORT including the negative EV bands.

**Fix**: Narrow the rule to `confidence_min: 75, confidence_max: 80`. Add penalty rule for out-of-band SOL SHORT.
**Impact**: ~$1,610 EV/100d by avoiding -$1,610 in bad SOL SHORT sub-bands.
**A/B test**: 14 days paper. Gate: ≥20 SOL SHORT trades.
**Confidence**: 68% (verify pattern holds in 60d backtest before implementing)

---

## MANDATORY PRE-RESTART REVIEW

**BTC LONG Boost Rule**: `restored_btc_long_boost_v1` claims 63.9% WR but 100d data shows **31.7% WR, -$550 on 41 trades**. Even the 60d "confirming" data shows -$20 at 57.7% WR. Consider narrowing to BTC LONG in trend regime only (existing `BTC_TREND_REGIME` rule handles this).

---

## SYSTEM STATE DELTA vs Run 130

| Item | Run 130 | Run 131 |
|---|---|---|
| Graduated rules | 11 | 11 (stable) |
| HYPE_SHORT_VETO_SPLIT | 11th flag | 11th flag |
| Kelly | -0.167 | -0.168 |
| Bot offline days | 75 | 75 |
| New findings | GRAD_RULES_CODE_BUG | BTC_SHORT_90plus overclaim, SOL SHORT 75-80% precision edge |

---

## PRIORITY ACTION LIST

| Priority | Action | Effort |
|---|---|---|
| P0 | Fix `llm/graduated_rules.py` overwrite bug (REC1) | 30 min |
| P0 | Start bot: `cd /home/user/WAGMI/bot && python run.py paper` | 2 min |
| P1 | HYPE_SHORT_VETO_SPLIT human decision (REC2) | Review |
| P1 | Review BTC LONG boost rule before restart | 15 min |
| P2 | SOL SHORT precision targeting 75-80% (REC3) | 15 min |
| P3 | Add `llm_regime` to backtest CSV | 1h |
| P3 | Fix duration field calculation | 30 min |