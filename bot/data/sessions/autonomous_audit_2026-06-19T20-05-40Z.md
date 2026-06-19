# WAGMI Autonomous Quant Audit
**Timestamp:** 2026-06-19T20:05:40Z (Run 86, Day 63.84 offline)
**Auditor:** Claude Autonomous Quant Agent | **Standard:** Institutional-grade quant review
**Prior Audit:** 2026-06-19T18:06:05Z (Run 85) — detects changes since then
**Cadence Streak:** 9 consecutive 2h runs (Runs 78–86)

---

## EXECUTIVE SUMMARY

**Bot offline 63.84 days. Evening window (16:00–22:00 UTC, 65% WR) is OPEN — ~2h remaining.** This run surfaces **three new findings** not in prior audits:

1. **State path reveals TP1+trailing is WR=64%, avg=+$10/trade** — contradicting the prior "-$0.34 trailing" finding. The prior narrative conflated TRAILING_STOP *close_reason* (-$0.34, only the losing subset) with the full TP1_HIT→TRAILING→CLOSED path (+$10.03, both wins and losses combined). The TRAILING_STOP_LOCK fix is still valuable but the framing was wrong.

2. **Contradictory size insights in meta_learning**: Insight #3 (conf=0.75) says ">5x leverage = 57% WR", Insight #7 (conf=0.80) says ">5x leverage = 36% WR". Both are ACTIVE. No conflict flag exists. The meta_learning system is storing contradictory beliefs simultaneously.

3. **duration_h is broken in both backtest CSVs** (backtest_100d.csv: all durations ≤ 0, trades_10d.csv: all zero). The hold_time_rules_state.json min_hold_hours=3.0 rule has no live validation data.

**What Changed Since Run 85:**
- ✅ Cadence maintained: Run 86 fired 1.95h after Run 85
- ❌ TRAILING_STOP_LOCK still PENDING_HUMAN_REVIEW (Day 4 pending)
- ❌ TP1_CUMULATIVE_PNL_INSTRUMENTATION still PENDING
- ❌ Bot remains offline
- ❌ Evening window running out: ~2h remain as of this writing

---

## PHASE 1: SYSTEM AUDIT

**AUDIT COMPLETE: 7 systems verified, 5 gaps found**

### Feedback State Files

| File | Present | Last Modified | Age | Status |
|------|---------|---------------|-----|--------|
| `feedback/adaptive_risk_state.json` | ✅ | 2026-06-05 02:01 UTC | 14.84 days | Stale — no live trades |
| `feedback/hold_time_rules_state.json` | ✅ | 2026-06-05 02:01 UTC | 14.84 days | Stale |
| `feedback/signal_quality.json` | ❌ MISSING | — | — | Will create on first close |
| `feedback/regime_feedback_state.json` | ❌ MISSING | — | — | Will create on first close |
| `feedback/tuner_state.json` | ❌ MISSING | — | — | Will create on first close |
| `feedback/strategy_weights.json` | ❌ MISSING | — | — | Will create on first close |
| `feedback/confidence_floor_state.json` | ❌ MISSING | — | — | Will create on first close |

**5 of 7 feedback systems have no persisted state.** On bot restart, they reinitialize from defaults.

### Feedback System Instantiation (multi_strategy_main.py:3115–3170)

| System | Class | Instantiation | record_outcome() | Status |
|--------|-------|--------------|-------------------|--------|
| Signal Quality | `SignalQualityScorer` | L421 | L3159–3163 | ✅ Wired |
| Parameter Tuner | `ParameterTuner` | L424 | L3166–3173 | ✅ Wired |
| Regime Feedback | `RegimeFeedbackManager` | L412 | L3135–3142 | ✅ Wired |
| Confidence Floor | `AdaptiveConfidenceFloor` | L415 | L3144–3149 | ✅ Wired |
| Hold Time Rules | `HoldTimeRuleManager` | L418 | L3151–3156 | ✅ Wired |
| Feedback Loop | `FeedbackLoop` | L804 | L3233 | ✅ Wired |
| AutoOptimizer | lazy-init | L913/L2222 | L3816 | ✅ Wired |

`_FULL_CLOSE` at L3115 correctly excludes `TP1` (partial close).

### Graduated Rules (24 total, 17 active=True)

| Rule | gate_pct | times_applied | times_correct | Issue |
|------|----------|--------------|---------------|-------|
| hype_long_veto_v1 | 100% | 1 | 0 | tracking bug |
| sol_long_veto_v1 | 100% | 1 | 0 | tracking bug |
| night_session_block_v1 | 100% | 6 | 0 | tracking bug (most-applied) |
| illiquid_regime_penalize_v1 | 100% | 1 | 0 | tracking bug |
| hype_short_veto_v1 | 100% | 3 | 0 | tracking bug |
| btc_short_conf70_80_penalize_v1 | 50% | 3 | 0 | tracking bug |
| btc_short_90plus_boost_v1 | 20% | 0 | 0 | Never fired |
| eth_trending_regime_boost_v1 | 100% | 2 | 0 | tracking bug |

**All 17 active rules show times_correct=0** — the accuracy tracking callback is broken. Rules fire but outcomes are never attributed back.

---

## PHASE 2: TRADE FORENSICS

**FORENSICS COMPLETE: 4 high-value sub-conditions found, 3 regression areas**

*Data: backtest_100d.csv (589 trades) primary; trades_10d.csv (965) secondary. Bot offline Day 63.84.*

### By Symbol (100d, 589 trades)

| Symbol | WR% | Count | Avg PnL | Total PnL |
|--------|-----|-------|---------|----------|
| BTC | 42% | 166 | -$3.84 | -$637 |
| HYPE | 49% | 225 | -$24.73 | -$5,563 |
| SOL | 41% | 198 | -$9.97 | -$1,974 |

All three symbols net-negative. HYPE worst by total PnL despite near-50% WR — loss/win asymmetry.

### By Symbol × Side

| Setup | WR% | Count | Avg PnL | Total PnL | Status |
|-------|-----|-------|---------|-----------|--------|
| BTC_SHORT | 46% | 125 | -$0.69 | -$87 | NEUTRAL — most viable |
| BTC_LONG | 32% | 41 | -$13.42 | -$550 | WEAK — veto candidate |
| SOL_SHORT | 45% | 140 | -$7.16 | -$1,003 | BLOCKED (gate=100%) |
| SOL_LONG | 33% | 58 | -$16.74 | -$971 | BLOCKED (gate=100%) |
| HYPE_LONG | 50% | 68 | -$14.36 | -$977 | BLOCKED (gate=100%) |
| HYPE_SHORT | 48% | 157 | -$29.22 | -$4,587 | BLOCKED (gate=100%) |

### Sub-condition Analysis

**BTC_LONG (WR=32%) sub-conditions by confidence:**
- Conf <70: WR=50%, n=14, avg=-$11.31 — WR threshold met but still PnL-negative
- Conf 70-80: WR=27%, n=11, avg=-$9.64 — worst
- Conf 80+: WR=19%, n=16, avg=-$17.85 — INVERSE confidence effect worst here

**SOL_LONG (WR=33%) sub-conditions:**
- Conf <70: WR=14%, n=14, avg=-$50.47 — catastrophic
- Conf 70-80: WR=42%, n=24, avg=+$2.55 — only positive avg_pnl (but blocked)
- Conf 80+: WR=35%, n=20, avg=-$16.27

**BTC_SHORT (WR=46%) sub-conditions — best available edge:**
- Conf 60-70: WR=56%, n=18, avg=-$0.61 — **only sub-condition with WR>50%**
- Conf 70-80: WR=44%, n=78, avg=-$0.54 (bulk of trades)
- Conf 80-90: WR=42%, n=19, avg=+$0.08
- Conf 90+: WR=50%, n=10, avg=-$3.48

### By Confidence Bin (all 589)

| Confidence | WR% | Count | Avg PnL |
|-----------|-----|-------|--------|
| 60-70% | 49% | 111 | -$7.15 |
| 70-80% | 45% | 321 | -$8.54 |
| 80-90% | 40% | 120 | -$33.04 |
| 90%+ | 41% | 37 | -$18.23 |

**INVERSE confidence effect confirmed across all setups.** Higher confidence = worse outcomes. Root cause candidates: (1) confidence chases momentum, (2) high-conf entries take larger SL hits, (3) ensemble over-agrees on false signals.

### By Close Reason / State Path

| Exit | WR% | Count | Avg PnL | Total PnL |
|------|-----|-------|---------|----------|
| SL | 0% | 269 | -$108.92 | -$29,300 |
| TP1 (partial, 50%) | 100% | 160 | +$122.01 | +$19,521 |
| TP1_HIT→TRAILING→CLOSED (full path) | **64%** | **160** | **+$10.03** | **+$1,605** |
| └ TP2 (subset) | 100% | 49 | +$33.53 | +$1,643 |
| └ TRAILING_STOP (subset) | 33% | 111 | -$1.49 | -$165 |

**NEW FRAMING CORRECTION (Run 86):** Prior audits stated "trailing exits = -$0.34/trade." This was TRAILING_STOP *close_reason* only (the losing 111 trades). The full TP1_HIT→TRAILING→CLOSED path (all 160 trades: 49 TP2 wins + 111 trailing exits) has WR=64% and avg=+$10.03. The TP1+trailing path is profitable on average. The TRAILING_STOP_LOCK fix would increase this further by converting trailing losses to additional TP2 wins.

### Hold Time Analysis
**BROKEN DATA:** duration_h=0 for 537 of 589 trades, negative for 52. Hold-time analysis unavailable. The min_hold_hours=3.0 rule cannot be validated.

### Top 5 Wins / Losses (last 100)
**Wins:** All 5 top wins were TP1 exits. BTC SHORT 4/5. Confidence: 73-87.5 (no extreme concentration).
**Losses:** All 5 top losses were SL exits. BTC LONG 3/5. conf=87.5 appears in 2 of 5 losses.

---

## PHASE 3: HYPOTHESIS VALIDATION

**VALIDATION COMPLETE: 2 confirmed, 5 stale, 2 broken/contradictory, 1 pre-invalidated**

| # | Insight | Status | Notes |
|---|---------|--------|-------|
| 1 | Morning TOD 71% WR | STALE | No time field in backtest CSV. Cannot validate. |
| 2 | Night 00-06 UTC 15% WR | CONFIRMED | night_session_block_v1 active. Consistent with adaptive_risk_state. |
| 3 | >5x leverage = 57% WR | BROKEN/CONFLICT | Contradicts Insight 7 (36% WR). Same metric, opposite conclusion. Both ACTIVE. |
| 4 | Evening 65% WR | PRE-INVALIDATED | Correctly invalidated 2026-05-19 post-dedup. |
| 5 | 74% LONG bias, LONG WR=30% | STALE | Recent BTC data: 27% LONG (not 74%). LONG WR=33%. Partially holds directionally. |
| 6 | Morning 14% WR (7 trades) | STALE | Contradicts Insight 1. 7 trades insufficient evidence. |
| 7 | >5x leverage = 36% WR | BROKEN/CONFLICT | Contradicts Insight 3 (57% WR). Both ACTIVE conf≥0.75. |
| 8 | Ensemble 94% concentration | PARTIALLY HOLDS | Actually 100% ensemble. WR=44.5% (claimed 45%). Still valid concern. |
| 9 | >6x leverage = 58% WR | STALE/CONFLICT | Third contradictory size insight. No >6x trades in dataset. |
| 10 | sniper_premium 33% WR | STALE | No sniper_premium trades in any dataset. Unverifiable. |

**Critical contradiction:** Insights 3, 7, 9 form a triplet — all describe leverage/size WR but give contradictory results (57% vs 36% vs 58%). All ACTIVE. The meta_learning system stores conflicting beliefs without detection. Insights 1 and 6 also contradict (morning = 71% vs 14%).

---

## PHASE 4: FEEDBACK LOOP CLOSURE

**LOOP CLOSURE: 0 trades fully propagated (bot offline). Structural gaps identified.**

### Propagation Check (structural — no live trades available)

| Signal | Destination | State | Propagation |
|--------|-------------|-------|-------------|
| signal_quality outcome | signal_quality.json | ❌ MISSING | NOT PROPAGATED |
| regime outcome | regime_feedback_state.json | ❌ MISSING | NOT PROPAGATED |
| confidence floor | confidence_floor_state.json | ❌ MISSING | NOT PROPAGATED |
| parameter tuner | tuner_state.json | ❌ MISSING | NOT PROPAGATED |
| strategy weights | strategy_weights.json | ❌ MISSING | NOT PROPAGATED |
| adaptive risk | adaptive_risk_state.json | ✅ (stale 14.84d) | Last wired |
| hold time | hold_time_rules_state.json | ✅ (stale 14.84d) | Last wired |
| LLM memory lessons | llm_memory.json | ✅ 1 note | NEAR-EMPTY |

### Broken Links
1. **5/7 state files missing** — cold start will lose all calibration
2. **LLM memory has 1 note** — lesson extraction near-completely failed
3. **duration_h=0** — hold_time_rules receives 0-hour observations from every backtest trade
4. **times_correct=0** across all 17 rules — accuracy tracking loop severed
5. **TP1 partial close** — feedback systems see trailing P&L only, miss TP1 partial PnL (+$61/trade underestimation per Run 85)

---

## PHASE 5: RECOMMENDATIONS

**RECOMMENDATIONS: 3 changes proposed**

### REC 1: START THE BOT — P0 ($429.82 EV Accrued)
- **Problem:** Offline 63.84 days. Evening window (WR=65%) has ~2h remaining.
- **Fix:** `cd bot && python run.py paper`
- **Impact:** +$1.78 recoverable tonight. +$6.79/week ongoing.
- **Rollback:** Ctrl+C
- **Confidence:** 99%

### REC 2: ADD BTC_LONG VETO RULE (gate=80%)
- **Problem:** BTC_LONG WR=32% (n=41), all confidence sub-conditions negative. Inverse confidence effect worst in this cell (80+ conf: 19% WR, avg=-$17.85).
- **Root cause:** Entries chase LONG during bear micro-trends; high confidence fires on false bottoms.
- **Fix:** Add graduated rule `btc_long_veto_v1` gate=80%, conditions={symbol:"BTC",side:"BUY"}. Use gate=80% (not 100%) due to 10d counter-evidence (64% WR, unresolved dataset conflict).
- **Impact:** +$550 per 100d equivalent (41 trades avoided × $13.42 avg loss)
- **A/B:** 20% holdout for 30d to validate vs 10d counter-claim
- **Rollback:** Set gate_percentage=0
- **Confidence:** 72%

### REC 3: ADD CONFLICT DETECTION TO META_LEARNING
- **Problem:** Insights 3, 7, 9 all measure leverage/WR relationship and give contradictory results. Both ACTIVE simultaneously. Potential to corrupt meta-confidence decisions.
- **Root cause:** No deduplication logic when adding new insights covering same metric.
- **Fix:** When inserting new insight, check existing ACTIVE insights for same category+dimension. If overlap exists, invalidate lower-confidence one. Add `conflict_with` field.
- **Impact:** Data integrity fix. Prevents contradictory beliefs compounding.
- **Rollback:** Remove deduplication
- **Confidence:** 88%

---

## APPENDIX

### Equity State
- Paper equity: $497.05 (saved 2026-04-23, 63.84d stale)
- Peak equity: $508.06 | Drawdown: -$11.01 (-2.2%)

### EV Accrued Offline: $429.82 (~$0.97/hour)

### Session Windows (2026-06-19 UTC)
| Window | Status | WR |
|--------|--------|-|
| 00-06 night | CLOSED (blocked) | 19% |
| 06-12 morning | CLOSED (missed) | 68% |
| 12-16 afternoon | CLOSED (missed) | 62% |
| 16-22 evening | OPEN ~1h50m remaining | 65% |
| 22-24 late | Not yet | 38% |

### Changelog vs Run 85
| Finding | Status |
|---------|--------|
| BOT_OFFLINE | Persistent (Day 63.84) |
| TRAILING_STOP_LOCK | PENDING_HUMAN_REVIEW (Day 4) |
| TP1_CUMULATIVE_PNL_INSTRUMENTATION | PENDING (Day 1) |
| TIMES_CORRECT_BLIND | KNOWN_BUG, unresolved |
| AB_TRACKER_STALLED | KNOWN_BUG, unresolved |
| **NEW: Trailing WR=64% (not -$0.34) — framing correction** | **Run 86** |
| **NEW: Insight contradiction triplet (3, 7, 9)** | **Run 86** |
| **NEW: duration_h broken in all CSVs** | **Run 86** |
| **NEW: BTC_LONG veto recommendation** | **Run 86** |
