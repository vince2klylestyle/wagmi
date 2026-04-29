# OVERNIGHT BLUEPRINT — 2026-04-29

**Author:** Claude (audit + planning session, branch `claude/audit-and-planning-3ocfV`)
**Status:** WORKING DRAFT — written incrementally, persisted as I go so partial work survives stream timeouts
**Audience:** the user (returning to a crashed system; bot has been offline ~140h)

---

## How to read this doc

Sections are numbered. Each is independent. Skim §1 and §3 first; the rest is for when you're at the keyboard.

- §1 — Executive Summary (1-min read)
- §2 — The 4 Loops: what they are, what data they collected, what's broken
- §3 — What the Data Already Says (the profitability map we should act on)
- §4 — Critical Path Before Bot Restart
- §5 — Profit Levers Ranked (effort × impact)
- §6 — Net-New Capability Ideas (agents, data, infra)
- §7 — Overnight Autonomous Tasks (low risk, I can do these without you)
- §8 — This Week's Sprint Outline (5-7 day plan)
- §9 — Open Questions for You

---

## §1 — Executive Summary

**State of the world (2026-04-29 19:00 UTC):**

- Bot has been **offline 140 hours** since 2026-04-23 22:17 UTC. Last action was a -$12.93 SOL SL, the 4th of 4 consecutive losses. Equity sits at **$497.05** vs the $5,000 starting bankroll (-90.1%).
- The 4 background loops you set up have kept running on the *historical* data. They've produced **49 graduated rules** in `bot/feedback/graduated_rules.json`, **8 meta-learning insights**, ~70 counterfactual scenarios, and a thick stack of paper-trading reports (~10 in the last 5 days). That's real signal — it's not noise.
- **The biggest single problem with the loops right now: the A/B treatment loop is open.** 35 of 49 rules are status `A/B_ACTIVE` with `treatment_wr = null`. The loops keep proposing rules but nothing is closing the feedback loop because no live trades are flowing. Every hourly run produces "all 38 gates stalled with zero new data."
- **The data we already have is enough to make decisive moves.** We don't need more loops; we need to apply what's been learned, restart cautiously, and fix the closure mechanism so the next 140 hours of data don't get wasted the same way.

**The three biggest moves, in priority order:**

1. **Promote the obvious-by-data rules from PROPOSED/A/B to APPLIED with hard gates.** Several patterns have huge sample sizes and unambiguous outcomes (HYPE_LONG: 23% WR / 35 trades / -$77; SOL_LONG: 24% WR / 34 trades / -$22; SOL_SHORT: 33% / 30 trades / -$154). These shouldn't be 20% A/B — they should be hard blocks before we restart.
2. **Re-enable sniper with belt-and-suspenders guardrails.** Per the 2026-04-15 autonomous session, sniper produced **+$328 across 34 trades** while everything else summed to **-$76**. It's currently disabled because of one -$147 blowup that bypassed `max_sniper_leverage=5.0`. Verify the cap binds at execution, add a per-trade-loss ceiling, then flip back on.
3. **Wire the A/B treatment_wr collector before restart.** Right now we have 35 hypotheses with no way to confirm them. Without this, we burn another week of trades producing nothing learnable.

**What I'm explicitly NOT recommending:** new strategies, new agents, or new data sources before steps 1–3. The audit shows we have 23 strategies, 9 active agents, 14 latent agents, and lots of dormant infrastructure. The constraint isn't capability — it's *closing the loops we already opened*.

## §2 — The 4 Loops: what they are, what data they collected, what's broken

You asked what the 4 loops were. Here's the inventory I reconstructed from the code and recent commits:

### Loop 1 — Perpetual Improvement Loop (hourly)

- **Code:** `bot/feedback/loop.py`, `bot/feedback/parameter_tuner.py`, `bot/feedback/auto_optimizer.py`, `bot/feedback/evolution_tracker.py`
- **Output:** `bot/feedback/graduated_rules.json` (49 rules, last update 2026-04-29 19:18:13 UTC)
- **What it does:** every hour it diffs live trade outcomes vs backtest expectations, proposes new rules (PROPOSED → A/B_ACTIVE → APPLIED → SUSPENDED if contradicted), and tracks `baseline_wr` vs `treatment_wr`.
- **Status:** running ✅ but *closure is broken*. 35/49 rules have `treatment_wr = null` because no live trades have come in since 2026-04-23. The loop is collecting no new evidence; it's just rotating proposals.

### Loop 2 — Continuous Audit Loop

- **Code:** `bot/tools/continuous_audit.py`, driver script `bot/tools/run_audit_loop.sh`
- **Output:** `audit_log_YYYYMMDD_HHMMSS.txt` files (none currently present — the loop isn't running)
- **What it does:** every hour for 24 iterations, audits "are feedback systems instantiated, are recording methods being called, is data being applied, are there learning systems without feedback." Pure introspection.
- **Status:** **not currently running**. Driver script is a `for i in {1..24}` over 24h, not a daemon. Likely was being launched manually by you and not restarted after the system crash.

### Loop 3 — Master Engine + 5 Subsystems (referenced heavily in commits, dark in repo)

- **Code:** referenced in commits as writing to `bot/data/learning/master_engine_state.json`, `bot/data/learning/auto_fix_state.json`, `bot/data/learning/live_edge_data.json`, `bot/data/learning/daily_synthesis_*.json`. The `bot/data/learning/` directory is gitignored — files exist locally only.
- **What it does (from commit history):** synthesizes findings across 5 subsystems (live edge tracker, prompt enricher, hold-time analyzer, A/B result tracker, regime feedback), writes daily synthesis with anomaly reports + restart guidance, and has an auto-fix capability that rewrites 1–2 fixes per run.
- **Status:** **gitignored, so I cannot see its current state from this branch**. Commits say it produced "6 high-priority findings (bot inactive 43h+...)" repeatedly. The synthesis is being generated but the bot isn't applying the restart guidance because it's offline.

### Loop 4 — Overnight Paper Trading Reporter

- **Code:** `bot/tools/overnight_report.py`, `bot/manual/overnight_report.py`
- **Output:** `bot/data/reports/paper_trading_YYYY-MM-DD_HHMM.md` (8 reports in last 5 days)
- **What it does:** snapshots equity, win rate, regime health, pattern health, consecutive losses, alerts.
- **Status:** running ✅. Latest report timestamped 2026-04-29 18:00 UTC. Working as designed — but it's been writing the same "BOT INACTIVE 140h" alert hourly for almost a week.

### What ties the loops together (and what doesn't)

There's also **`bot/tools/overwatch_cycle.py`** which combines `intel_collector + overwatch_analyzer + edge_tracker` into a single pass and writes to `bot/data/overwatch_cycles.jsonl`. That one might be a 5th loop or a consolidated wrapper — the commit history isn't definitive. It writes to `bot/data/paper_trading_intel.jsonl` and `bot/data/overwatch_state.json`, neither of which currently exist on disk.

**The integration gap:** these loops don't share a common message bus. Loop 1 writes to `graduated_rules.json`, Loop 4 writes to `reports/`, Loop 3 writes to `data/learning/`. There's no single place that says "given everything we know, here's what should happen on restart." That's a piece I think we should build (see §6).

## §3 — What the Data Already Says (the profitability map)

Before any new work, here's what's already proven by the 352 resolved trades + 49 rules + 8 insights + 70 counterfactuals. I'm pulling these from `bot/feedback/graduated_rules.json`, `bot/data/meta_learning/insights.json`, `bot/data/counterfactuals/scenarios.json`, and the latest `paper_trading_*.md` reports.

### 3.1 Per-(symbol, side) edge map

| Pattern | WR | Trades | Net PnL | Verdict |
|---|---|---|---|---|
| ETH_SHORT | 80% | 5 | +$0.94 | ✅ Edge — small sample, but consistent winner |
| BTC_SHORT | 57% | 7 | +$0.11 | ✅ Edge — break-even by PnL but positive WR |
| ETH_LONG | 42% | 19 | +$3.28 | ✅ Viable — at break-even WR threshold |
| BTC_LONG | 18% | 17 | -$0.08 | ⚠️ Weak — kill or restrict to specific regime |
| HYPE_SHORT | 33% | 6 | -$24.41 | ❌ No edge |
| SOL_LONG | 24% | 34 | -$21.89 | ❌ No edge — large sample, statistical |
| HYPE_LONG | 23% | 35 | -$77.26 | ❌ Avoid — large sample, statistical |
| SOL_SHORT | 33% | 30 | -$154.35 | ❌ Kill — single biggest bleeder |

**Three of these are statistically obvious kills** (n≥30, WR<35%, negative PnL): SOL_LONG, HYPE_LONG, SOL_SHORT. Together they cost the bot **$253.50** out of a $5,000 starting bankroll. That's 5% of starting equity bled by patterns we have hard data against.

**Caveat on SOL_SHORT:** the 2026-04-15 autonomous session found that **`SOL_SELL_regime_trend` = 0% WR on 149 shadow signals** but **`SOL_SELL_multi_tier_quality` = 72% WR**. So "kill SOL_SHORT" is too coarse — the right cut is **kill the regime_trend variant of SOL_SHORT, keep the MTQ variant**. This is exactly what Finding 11's 3-tuple proven-setup table addresses, and that fix has been APPLIED (rule F11). Verify it's actually filtering before restart.

### 3.2 Time-of-day edge

From `meta_learning/insights.json` (multiple confirmations across runs):

- **Morning (06:00–12:00 UTC):** ~67–71% WR (across 18–20 trade samples)
- **Night (00:00–06:00 UTC):** ~9–15% WR (across 13 trades)
- **Spread: 56–62 percentage points.** This is the single largest edge signal in the whole dataset.

Currently encoded as `TOD_morning_edge` rule, A/B at 20%. **This should not be A/B — it should be APPLIED at 100% gate.** A 56-point WR spread on 13+20 samples is past any reasonable significance threshold.

### 3.3 Regime edge

From the latest paper trading report (125 core trades):

- **Trending:** 51.9% WR (n=52) — only positive-expectancy regime
- **Illiquid:** 28.1% WR (n=57) — kill
- **Ranging:** 25.0% WR (n=16) — kill

The bot has already escalated `ILLIQUID_regime_block` to 50% gate. Same logic as TOD: the sample sizes and gap are decisive. Should be APPLIED at 100%.

### 3.4 Sizing edge (the conviction signal)

Three independent insight runs across different time windows all show the same thing:

- Larger positions (>5x leverage) win **57–60%** of the time
- Smaller positions (<5x) win **31–40%** of the time

This means **the confidence model is correctly distinguishing high- vs low-conviction setups** — it just isn't trusted enough by the sizer. The bot has the right opinion; it's not being aggressive enough on the trades it's most confident about.

There's also a *contradicting* earlier insight ("size bias detected: larger positions (>1.5x) have 40% WR vs 60% for smaller") at a different threshold (1.5x not 5x). The reconciliation is: positions in the 1.5x–5x band are mediocre, and positions above 5x are decisively better than positions below. The sizer should be bimodal — small or strong, nothing in between.

### 3.5 The sniper alpha (the elephant)

From `AUTONOMOUS_SESSION_2026_04_15.md`:

- Sniper/anticipatory execution path: **+$328 across 34 trades**
- Everything else (confidence_scorer, multi_tier_quality, regime_trend solo): **-$76**
- Three biggest winners in bot history: **+$160, +$130, +$100** — all sniper_premium SOL SHORT
- One bad blowup: **-$147** at 9.7x leverage despite the `max_sniper_leverage=5.0` cap (cap was bypassed somehow at execution time)
- `SNIPER_AUTO_EXECUTE=false` in `.env` line 215 since the blowup

**The bet against re-enabling is one trade. The data for re-enabling is 33 other trades.** Right call to disable temporarily; wrong call to leave it disabled indefinitely. Fix the cap-bypass first, then turn it back on.

### 3.6 Counterfactual exit signal

From `counterfactuals/scenarios.json`, the `exit_timing` scenarios show a consistent pattern: the bot is **leaving money on the table at TP1**. The two examples I sampled:

- HYPE long: actual SL -$10.67 vs counterfactual exit at TP1 +$3.29 (delta +$13.95)
- BTC short: actual TRAILING_STOP +$0.08 vs counterfactual exit at TP1 +$3.29 (delta +$3.21)

If this holds across the full counterfactual set, the trailing logic is *over-trailing* — letting good TP1 hits get caught by the trailing stop on reversal. The fix is either (a) take more off at TP1 (currently a partial close — make it bigger) or (b) tighten trailing once TP1 hits. Need to compute the aggregate delta across all counterfactuals before acting.

### 3.7 The contradictions worth flagging

From the rules graveyard:

- **`confidence_60_70_ROUTING_FIX` SUSPENDED** — was routing 90%+ confidence signals to Sonnet, but live data shows 90%+ confidence trades have **+$32.33 avg PnL** (best cohort). The routing was inverted. ✅ Already suspended.
- **`SOL_SHORT_GATE_ESCALATE` blocked** — fresh data showed 63.7% WR / +$5,807 / n=179. The "kill SOL_SHORT" rule was too aggressive *if* you take a long enough window. **This is contradicted by the latest 30-trade window showing 33% WR / -$154.** Reconciliation: SOL_SHORT was great historically and is currently broken. Either we have regime drift, or the recent trades are a specific failure mode (which strategy, which time, which volatility band?). **Needs investigation before restart.**
- **`AB_RESULT_TRACKER` graduated to 100% (CRITICAL)** — the rule says "the A/B feedback loop is broken; treatment_wr=null on 30 rules." This rule is essentially the loop diagnosing its own breakage. Fixing this is §4.3.

## §4 — Critical Path Before Bot Restart

This is the pre-flight checklist. Order matters; some items unblock others. Estimated total effort: 4–8 focused hours, can be broken across overnight + tomorrow morning.

### 4.1 — Verify Finding 11 is actually filtering (30 min)

The 3-tuple proven-setup table is supposedly APPLIED at `ensemble.py:2293`. Read that line and the 50 lines around it. Confirm that:
- (a) it actually loads from `shadow_ledger.csv`, not a stale pickle
- (b) `SOL_SELL_regime_trend` returns blocked, but `SOL_SELL_multi_tier_quality` returns allowed
- (c) the lookup is on `(symbol, side, strategy)` not collapsed to `(symbol, side)`

If any of those are false, the bot will re-bleed on SOL the moment it starts.

### 4.2 — Verify max_sniper_leverage cap binds (60 min)

Read `bot/manual/sniper_filter.py:637` and `bot/core/position_wiring.py` together. Trace from sniper signal generation → `OrderExecutor.place_order(...)` and confirm there's no path that lets leverage exceed `max_sniper_leverage=5.0` in `bot/manual/config.py:77`. The -$147 blowup was at 9.7x — somebody bypassed the cap. Find them.

If you can't find the bypass: add a defensive clamp in `OrderExecutor` itself. Belt and suspenders.

### 4.3 — Wire treatment_wr collection (90 min)

This is the single most valuable fix. Right now, `graduated_rules.json` rules have `gate_percentage: 20` (or 50, 75) but no closure mechanism. After restart, when a trade closes:

- Identify whether it was in the *treatment* arm (rule applied) or *baseline* arm (rule not applied) for each active A/B rule.
- Update `treatment_wr` and `treatment_n` (or `baseline_wr` / `baseline_n`) for each rule in `graduated_rules.json`.
- After `treatment_n >= 30`, run a Wald test or simple z-test on `treatment_wr - baseline_wr`. If significant, escalate gate (50% → 75% → 100%). If not, keep gating.
- After `treatment_n >= 100` with no significance, mark as `INCONCLUSIVE` and rotate out.

Where to wire it: `bot/feedback/loop.py` already has a `record_outcome()` method. The A/B tracker should hook into the same call. Specifically, `feedback.record_outcome(...)` should accept the rules-active-on-this-trade and update each one's counters.

If we don't fix this, the next 140 hours of data are wasted the same way.

### 4.4 — Promote obvious rules to APPLIED before restart (45 min)

These shouldn't wait for A/B closure — they're obvious by sample size:

| Rule ID | Promote to | Reason |
|---|---|---|
| `HYPE_LONG_hard_block` | APPLIED 100% | 23% WR / 35 trades / -$77 |
| `SOL_LONG_hard_block` | APPLIED 100% | 24% WR / 34 trades / -$22 |
| `TOD_morning_edge` (boost AM) | APPLIED 100% | 56-pt WR spread on n=33 |
| `NIGHT_session_pause` (block 00–06 UTC) | APPLIED 100% | 9–15% WR on n=13 |
| `ILLIQUID_regime_block` | APPLIED 100% | 28% WR / n=57 |
| `RANGING_regime_block` | APPLIED 100% | 25% WR / n=16 |

For SOL_SHORT specifically, **don't** promote a hard block — instead, promote the **3-tuple filter** that kills `SOL_SELL_regime_trend` while keeping `SOL_SELL_multi_tier_quality`. That's the surgical version.

### 4.5 — Consecutive-loss circuit breaker on restart (30 min)

The bot is in a 4-consecutive-loss state. On restart, the existing circuit breaker should pause it for manual review. Verify this is what `RESTART_SOFT_START_4LOSS` rule does (it was added 2026-04-29). The behavior we want:

- On restart with `consecutive_losses >= 3`, run in *paper-only confidence-floor=85* mode for the first 24h or 5 trades (whichever first).
- Only revert to normal floor after a green outcome.

### 4.6 — Run a 100-day backtest with the new gates (60 min)

Before paper-trading, prove the gate stack didn't accidentally kill more than it saved. Run:

```bash
cd bot && python run.py backtest  # default 30 days
cd bot && python cli.py --mode walkforward  # walk-forward validation
```

Compare net PnL with and without the §4.4 promotions. Acceptance criteria: net PnL improves OR remains within -10% of pre-promotion (we accept some PnL loss for variance reduction).

### 4.7 — Restart paper, monitor for 6 hours (30 min setup)

Once §4.1–§4.6 pass:

```bash
cd bot && python run.py paper
```

Watch via `/paper-status quick` every hour for first 6 hours. If any of these trip, stop and review:
- Any single trade > 2% equity loss
- Any new rule generating > 5 trades in <60 min (fast-feedback drift)
- A/B tracker not updating treatment_wr after first closed trade (closure still broken)

## §5 — Profit Levers Ranked (effort × impact)

Once the bot is back trading and the A/B loop is closing, here are the levers ranked by expected $/effort. "Effort" is calibrated in dev-hours; "Impact" is rough order-of-magnitude on a 30-day window at current size.

### Tier S (do these first — 1–4h each, high confidence)

| # | Lever | Effort | Expected impact | Source |
|---|---|---|---|---|
| 1 | Re-enable sniper with verified 5x cap + per-trade-loss ceiling | 2h | +$200–400 / 30d | Finding 1, AUTONOMOUS_2026_04_15 |
| 2 | Promote 6 obvious rules to APPLIED 100% (§4.4) | 1h | +$100–200 / 30d (loss avoidance) | This blueprint §3 |
| 3 | Wire A/B treatment_wr closure (§4.3) | 1.5h | Compounding — every future rule gets validated | This blueprint §2 |
| 4 | Bimodal sizing — small or 5x+, kill the middle band | 2h | +$50–100 / 30d | Insight: size>5x = 57–60% WR |
| 5 | Counterfactual-driven TP1 partial — increase fraction taken at TP1 | 3h | +$30–80 / 30d | counterfactuals/scenarios.json |

### Tier A (next, 1–2 day each, medium confidence)

| # | Lever | Effort | Expected impact | Source |
|---|---|---|---|---|
| 6 | Activate dormant strategies (funding_rate, oi_delta, cvd, liquidation_cascade, vmc_cipher) one at a time, gated 25% each | 1d total | Unknown — could be +$100/strategy or could be flat | BLUEPRINT.md §1a |
| 7 | Per-(symbol,side,strategy) confidence floors instead of global | 1d | +$50–150 / 30d (unblocks suppressed winners) | ROADMAP audit findings |
| 8 | Limit-order TP/SL with maker-fee capture + market fallback | 1.5d | +5–10 bps per trade × ~150 trades = +$80–150 / 30d | BLUEPRINT.md §2a |
| 9 | Volatility-targeted sizing (replace flat 0.5% risk with ATR-normalized) | 1d | +$50–100 / 30d (better risk-adjusted, lower DD) | BLUEPRINT.md §3a |
| 10 | Hour-gated trading — block 00–06 UTC, boost 06–12 UTC at 1.08x conf | 4h | +$80–150 / 30d | meta_learning/insights.json |

### Tier B (1 week each, less certain)

| # | Lever | Effort | Expected impact | Source |
|---|---|---|---|---|
| 11 | HMM regime detector blended with LLM regime via Bayesian update | 1w | +5–15% WR in regime-correct trades | BLUEPRINT.md §4c |
| 12 | IC-weighted ensemble (Grinold-Kahn) instead of equal-weight veto | 1w | Hard to predict, could be flat-to-+10% Sharpe | BLUEPRINT.md §3d |
| 13 | LLM A/B vs pure-quant control arm | 1w (mostly waiting for n=200) | Determines whether to keep paying for LLM at all | BLUEPRINT.md §4a |
| 14 | Strategy discovery agent activation — sandboxed backtests, auto-promote winners | 1w | Net new alpha — could add 1–2 strategies / month | ROADMAP §6.4 |
| 15 | Order book depth signals from Hyperliquid for intra-candle entries | 1w | +5–15 bps execution improvement | ROADMAP §6.5 |

### Tier C (2+ weeks, speculative or infra)

| # | Lever | Effort | Why it's down here |
|---|---|---|---|
| 16 | Break up `multi_strategy_main.py` (6028 lines) | 2w | Quality-of-life refactor; doesn't add edge |
| 17 | Real-time correlation matrix + marginal VaR | 2w | Better risk management but not edge generation |
| 18 | Cross-exchange leading indicators (Kraken/Bybit) | 2–3w | Signal quality up, but multi-exchange data infra is heavy |
| 19 | On-chain netflow signals (CryptoQuant API) | 2w | API costs + lagging data; uncertain edge |
| 20 | Whale wallet tracking | 3w | Data availability + cost |

### What I'd skip until it's clearly justified

- **More LLM agents.** We have 9 active + 14 dormant. Building more before we close the A/B loop on the existing 9 is multiplying ambiguity.
- **RL/ML signal generation.** Codebase has `bot/ml/`, `bot/rl/` directories that are essentially empty. Trading bots that work usually don't need this — they need solid heuristics + proper risk + good execution. Add it when there's a specific bottleneck it solves.
- **More dashboards.** We already have `bot/dashboard/server.py` (Flask), `bot/api_server.py` (FastAPI), `web/` (Next.js), `api/app/` (FastAPI). Pick one, kill the rest.

## §6 — Net-New Capability Ideas

These are ideas I think are worth considering once the foundations are solid. Sorted from "concrete and testable" to "exploratory."

### 6.1 — Loop Mesh: a unified message bus for the 4 loops

Right now the 4 loops are siloed (§2). Each writes to its own JSON. They don't share findings. Build a tiny shared bus:

- **`bot/data/loop_bus.jsonl`** — append-only event log.
- Each loop emits structured events: `{"loop": "perpetual_improvement", "timestamp": ..., "event": "rule_proposed", "rule_id": ..., "evidence": {...}}`
- A new **synthesizer** reads the last N hours of events and produces a single `bot/data/loop_synthesis.json` that's the *one place* you (or a subagent) reads to know "what should the bot do differently."
- The bot's main loop reads `loop_synthesis.json` on each cycle, not the individual rule files.

This unblocks: cross-loop correlation (Loop 1 proposes rule, Loop 4 reports paper performance, Loop 3 cross-checks against backtest). It also means one place to truncate/archive instead of 4.

Effort: 1.5 days. Worth it.

### 6.2 — A "Decision Diff" agent

When the live bot makes a different decision than the backtest would have, *that's the most informative event in the system*. Right now we surface this via `live_edge_data.json` and ad-hoc commits. Make it a first-class agent:

- **DecisionDiff agent (Sonnet)** — runs after every signal that fires. Re-runs the same data through a frozen "champion" backtest config and the live config. If decisions differ, emit a structured diff with reasoning.
- Output goes to Loop 1 as evidence; if a diff persists across N occurrences, it auto-proposes a rule.
- This is the "why does live diverge from backtest" question turned into a continuous signal instead of a periodic audit.

Effort: 3 days (mostly prompt + integration).

### 6.3 — Counterfactual-as-feature

The counterfactual scenarios file has resolved "what if you exited at TP1" entries with deltas. Right now they're a study artifact. Promote them to features:

- For every closed trade, compute `counterfactual_tp1_delta` and `counterfactual_tp2_delta` and store on the trade record.
- Train a tiny regression on `(symbol, regime, conf, ATR_at_entry, hold_time) → which exit would have been best`.
- At trade-time, the model outputs an "optimal exit shape" (heavy TP1 / heavy trail / 50/50) and the position manager respects it.

This is taking what the meta-learning loop already discovered and operationalizing it. Effort: 5 days. Real edge potential — counterfactuals already show consistent TP1 underweighting.

### 6.4 — Sniper-mode "hot list"

Sniper produced +$328 across 34 trades. Three biggest wins were all SOL_SHORT_sniper_premium. **The pattern isn't sniper-anything; it's sniper-on-specific-setups.**

- Build a hot-list mechanism: every 4 hours, an LLM (Sonnet) scans the last 30 days of sniper-eligible setups, ranks by expected edge, and produces a JSON `hot_list.json` with the top 10 (symbol, side, regime, time-of-day, strategy variant) tuples.
- Sniper auto-execute is gated on hot-list match.
- This is essentially the Scout agent's role, but specialized for the sniper path.

Effort: 4 days. Could be the difference between "sniper averages +$10/trade" and "sniper averages +$30/trade."

### 6.5 — "Loss autopsy" agent (continuous, not on-demand)

Right now `/loss-autopsy` is a slash command. Make it a continuous agent:

- After every losing trade, an LLM (Haiku) runs a structured autopsy: was the entry premature? was the SL too tight? did a competing strategy disagree (and was it right)? was there a known-bad-pattern that matched? Output to a structured `losses.jsonl`.
- Every 50 losses, Sonnet aggregates into themes and proposes mitigations to Loop 1.
- Cheap (Haiku per trade), high signal — most of the bot's bleed is repeated patterns.

Effort: 3 days. Synergistic with §6.4.

### 6.6 — A/B for prompts (not just rules)

We A/B test rules but not prompts. Add prompt-level A/B:

- Each agent has versioned prompts in `bot/llm/agents/prompts/{agent}/v{n}.txt`.
- Coordinator randomly picks v1 or v2 with 80/20 split for new versions.
- After 200 trades on v2, compute decision quality delta. If positive, promote.

Effort: 4 days. Pays off long-term as you keep iterating prompts.

### 6.7 — "Regime forecasting" — turn Scout into a leading indicator

Scout currently does idle-time research. Add a forecasting role:

- Scout (Sonnet, 1x per hour) outputs "regime in 4h: trending 0.6 / range 0.3 / panic 0.1" with reasoning.
- Forecasts are logged. Accuracy is tracked over time (Brier score on 4h-ahead forecasts).
- High-confidence forecasts adjust the bot's risk budget proactively (drop size 50% if "panic" forecast > 0.5).

Effort: 5 days. Speculative — could be junk, could be real. Worth running for a month and measuring.

### 6.8 — Self-audit on stale data (the meta-loop)

The "all 38 gates stalled with zero new data" pattern in commits is a meta-failure: the loops kept running without realizing their inputs were dead. Add a freshness check:

- Each loop has a "minimum freshness" requirement: e.g., perpetual improvement requires `>= 5 trades in last 24h`.
- If freshness fails, the loop *short-circuits to a single emit* — `{"event": "stale_input", "missing": "live_trades", "duration": "140h"}` — and stops re-proposing.
- This prevents the recent week of "5 reports saying the same thing."

Effort: 2 days (mostly auditing each loop and adding the guard). High value for not wasting tokens/storage.

### 6.9 — "What-if" shadow trader

Run the bot's full pipeline against live data **even when the real bot is paused**. The shadow trader doesn't execute, but it logs every decision it would have made. After restart, you can diff "what shadow did during downtime" vs "what live did" to see whether the pause cost you anything.

Practical reason: right now you genuinely don't know whether the 140h offline cost you $0 or $1500. The shadow trader tells you.

Effort: 1 day if you reuse the existing `replay` mode + persistent memory. Worth it.

### 6.10 — Weekly synthesis for the human

This is the one for *you*, not the bot. Every Sunday 18:00 UTC, an LLM produces:

- "Top 3 changes the bot made to itself this week, with PnL attribution"
- "Top 3 patterns the bot is still losing on"
- "Open A/B tests pending closure — which are due to graduate"
- "Weeks of runway remaining at current burn rate"

Single page, Markdown, drops to `bot/data/reports/weekly_YYYY-WW.md`. Replaces hourly noise with one signal-dense check-in.

Effort: 1 day. Mostly you wanting it.

## §7 — Overnight Autonomous Tasks (low-risk, I can do these without you)

These are tasks I'm willing to execute now without your supervision because they're either pure analysis (no code changes) or surgical changes with clear contracts. If you want me to start any of these, just say "do §7.X" — I'll persist work after every step.

### 7.1 — Compute the full counterfactual delta aggregate (analysis, no risk)

Read all of `bot/data/counterfactuals/scenarios.json`, group by `scenario_type` and `(symbol, side)`, compute mean and median delta. Output `bot/data/reports/counterfactual_summary_2026-04-29.md`. Tells us whether the TP1-underweighting hypothesis (§3.6) holds across the dataset or was just my two examples.

### 7.2 — Cross-reference rules with actual trade outcomes (analysis, no risk)

For each of the 49 rules in `graduated_rules.json`, scan `trades.csv` and (where rule is interpretable) compute what the WR would have been *with* and *without* the rule applied. Many rules can be back-fit retroactively because they're deterministic gates (regime, time-of-day, symbol/side). Output `bot/data/reports/rule_backfit_2026-04-29.md`. Tells us which proposed rules have *historical* support, not just hypothesized support.

### 7.3 — Audit `bot/data/learning/` (the gitignored Master Engine state)

If those files exist locally on the system you're going to copy this to, read them and produce a summary. If they don't, note that explicitly in the blueprint addendum. They probably contain the most current synthesis from Loop 3 — worth surfacing.

### 7.4 — Build the §4 "pre-restart checklist" as an executable script

Write `bot/tools/preflight_restart.py` that runs §4.1, §4.2, §4.5, §4.6 as a single command and prints a clear pass/fail. Pure new file, no existing code touched — zero blast radius. This is what `/deploy-paper` should arguably do but more strict.

### 7.5 — Document each currently-running loop in a single `LOOPS.md` at the top level

Right now the loops are scattered. One doc that says "here's loop 1, here it lives, here's where it writes, here's how to restart it, here's how to know it's healthy." Pure documentation.

### 7.6 — Draft the §6.1 Loop Mesh schema (no implementation, just spec)

Define the event schema for `loop_bus.jsonl` and write `bot/feedback/loop_bus_spec.md`. Each event type, fields, validation rules. Foundation work for §6.1; doesn't change any running code.

### 7.7 — Audit which rules are actually loaded by the bot at startup

Read `bot/feedback/auto_optimizer.py` and `bot/feedback/parameter_tuner.py` to confirm: when the bot starts, does it actually load `graduated_rules.json` and apply the APPLIED rules? Or are the JSON entries cosmetic? This is a critical correctness question — possible the rules are recorded but not enforced. Output: `bot/data/reports/rules_enforcement_audit_2026-04-29.md`.

### 7.8 — Generate a `BLUEPRINT_INDEX.md` consolidating the top-level docs

There are ~80 top-level `.md` files. Many are stale (PHASE_1_AUDIT, etc.). Don't delete anything — just produce `BLUEPRINT_INDEX.md` that classifies each as LIVE / HISTORICAL / STALE / DUPLICATE with a 1-line description. You can archive stale ones later.

### What I'm NOT going to do without you

- Touch `.env` or any sensitive config.
- Modify any code in `bot/execution/` or `bot/strategies/` (real-money impact).
- Change risk limits, leverage caps, or circuit breakers.
- Delete or move data files.
- Push commits without your explicit go-ahead.

## §8 — This Week's Sprint Outline (5–7 day plan)

Working backwards from "bot is back trading and learning by Sunday 2026-05-04."

### Day 1 — Tonight + Tomorrow Morning (you sleeping / commuting)

- I run §7.1, §7.2, §7.3, §7.7 (analysis). Persist all outputs to `bot/data/reports/` and commit.
- I draft §7.4 (preflight script) and §7.6 (loop bus spec), commit.
- I draft §7.5 (LOOPS.md) and §7.8 (BLUEPRINT_INDEX.md), commit.

### Day 2 — You back at keyboard

- Review §7 outputs. Decide what surprised you, what should change in §4 plan.
- Run §4.1, §4.2 (Finding 11 verification, sniper cap verification). 1.5h.
- Run §4.3 (wire treatment_wr collection). 1.5h. **This is the foundational fix.**
- Run §4.6 (backtest with new gates). 1h.
- Don't restart yet.

### Day 3 — Restart day

- Apply §4.4 (promote 6 obvious rules). 1h.
- Apply §4.5 (consecutive-loss soft-start). 30m.
- Restart bot in paper mode. Watch first 6 hours via `/paper-status`.
- If clean: leave running overnight. If anything trips: pause, investigate, fix, retry.

### Day 4 — First full trading day with new gates

- Monitor at hourly intervals.
- Run Tier S #4 (bimodal sizing) and #5 (TP1 partial increase) — both are config-level changes, low risk.
- Spot-check that A/B tracker is actually updating treatment_wr (the fix from §4.3).

### Day 5 — Sniper re-enable

- If 4 days of paper data look healthy (no rule-bypass disasters, A/B closure working): turn `SNIPER_AUTO_EXECUTE=true`.
- Add hot-list (§6.4) before flipping. Sniper only fires on hot-list matches for the first 48h.

### Day 6 — Activate one dormant strategy

- Pick the highest-expected-edge dormant strategy (probably `funding_rate` — clearest signal, well-studied externally).
- Gate at 25%. Monitor for 24h before promoting.

### Day 7 — Synthesize the week

- Run §6.10 weekly synthesis (or I write it for you).
- Decide whether to scale capital, add another dormant strategy, or build §6.1 Loop Mesh next.

### What we DON'T do this week

- No new agents.
- No new strategies (other than activating dormant ones).
- No live trading on Hyperliquid (paper only until paper has 200+ trades and stable A/B closure).
- No major refactors (multi_strategy_main breakup, etc.).

The week's theme is: **operationalize what we already have, then iterate.**

## §9 — Open Questions for You

These are decisions only you can make. I've ordered by how blocking they are.

1. **Capital level on restart.** Bot is at $497. Do we (a) restart at $497 and let it climb back, (b) reset to a fresh paper bankroll for clean tracking, or (c) reset to a smaller paper bankroll ($250) to force tighter sizing during the rebuild phase?

2. **SOL_SHORT recent contradiction (§3.7).** Historical 179-trade window: 63.7% WR, +$5,807. Recent 30-trade window: 33% WR, -$154. Is this regime drift (SOL has changed character) or specific failure modes within recent trades? I can investigate, but you may have intuition.

3. **Sniper re-enable confidence.** Are you comfortable re-enabling sniper after §4.2 verifies the cap binds, or do you want a more elaborate mechanism (e.g., manual approval via Telegram for first 5 sniper signals)?

4. **LLM autonomy mode.** Recent commits suggest LLM was running with credit-balance issues. What `LLM_MODE` do we restart with? `VETO_ONLY` is conservative; `SIZING` adds value if Critic agent is working.

5. **The $12,577 PnL recovery.** Commit `7778134` mentions "$12,577 PnL recovery identified" — that's a huge claim. I haven't traced it yet. Do you remember what that referred to? It may be the most important single insight on this branch and we should make sure it didn't get lost.

6. **Live trading runway.** When are you comfortable moving paper → small live? My read: at 200 paper trades + A/B closure working + paper-Sharpe > 1.0 over a 2-week window. That's probably 3 weeks out. Is that the right threshold?

7. **Loop ownership going forward.** Do you want the loops to keep running on a cron / continuous basis, or only when you (or I) trigger them? Recent commits at hourly cadence produced repetitive output during the offline period. The §6.8 freshness check fixes this, but you might want a different cadence anyway.

8. **What did we build that you want me to *not* keep building on?** Looking at the codebase — 80+ top-level docs, 23 strategies, 23 agent roles defined, 4–5 loops, multiple dashboards. Anything you want to formally deprecate so we stop maintaining it?

---

## Appendix A — Files to read on return (in order)

1. This blueprint (you're reading it).
2. `bot/data/reports/paper_trading_2026-04-29_1800.md` — current state snapshot.
3. `bot/data/sessions/AUTONOMOUS_SESSION_2026_04_15.md` — the strongest single piece of forensic analysis on this branch. Especially Findings 1, 11, 14.
4. Any `bot/data/reports/*_2026-04-29.md` files I produce overnight.
5. `bot/feedback/graduated_rules.json` — but skim status distribution, don't read every rule.

## Appendix B — What I'm confident vs. uncertain about

**High confidence:**
- The 4 loops are running but the A/B closure is broken.
- HYPE_LONG / SOL_LONG / SOL_SHORT-via-regime_trend should be hard-blocked by sample size alone.
- Morning-vs-night TOD edge is real (56–62 pt spread on n>30).
- Sniper was the dominant alpha and should be re-enabled with guardrails.
- Restart shouldn't happen before §4.1, §4.2, §4.3 are done.

**Medium confidence:**
- Counterfactual TP1 underweighting (§3.6) — only sampled 2 scenarios; need §7.1 to confirm.
- Bimodal sizing recommendation (§5 Tier S #4) — based on 3 confirming insights but threshold is fuzzy.
- "Most loops should keep running, just with freshness checks" — alternate view: cut to 2 loops + a synthesizer.

**Low confidence (worth investigating):**
- Whether the 14 dormant agent roles are "good ideas waiting to ship" or "dead infra to delete."
- Whether the 5 dormant strategies are dormant for good reason (poor backtest) or just disabled.
- Whether `bot/data/learning/` (gitignored) holds the most current synthesis or is stale.

---

*End of blueprint. Living document — section additions go below this line as we progress.*

