# Audit Index — 2026-04-29 Session

This session produced 10 audit documents totaling ~2,500 lines of analysis.
They form a coherent picture of the project's state: where the wiring is
solid, where it's broken, what's been built and forgotten, and what to fix
in what order.

Read this file first. Each section below links the relevant audit + key finding.

---

## The Big Picture

WAGMI is a **mature codebase with three distinct dead-code patterns** that
together account for a significant fraction of "intelligence" written but
never invoked:

| Pattern | Surface | Audit |
|---|---|---|
| Writes-only / no read path | 2 systems (graduated_rules, swarm_feedback) | §02, §08 |
| Built but unwired | 13 of 23 LLM agent roles, ~1,100 lines | §09 |
| Alternate implementations parked | 3 strategy files, ~760 lines | §10 |

Combined: **~3,500 lines of "complete but inert" code**. The good news is
each is well-scoped to fix. None require architectural rewrites.

---

## The Audits (read in order if going deep)

### 01 — `01_counterfactual_summary.md`
Counterfactual deltas across 134 closed-trade scenarios.
- **Key finding:** TP1 underweighting universal — exit_at_tp1 beats actual 81% of time, +$477 left on the table aggregate.
- **Implication:** raise TP1 partial-close fraction. Highest-EV mechanical change.

### 02 — `02_rules_enforcement_audit.md` ⚠️ P0
The graduated_rules system is structurally broken.
- **Key finding:** two `graduated_rules.json` files with incompatible schemas. Runtime engine reads `bot/data/llm/graduated_rules.json` (doesn't exist). Perpetual loop writes `bot/feedback/graduated_rules.json` (49 rules tracked). Nothing translates between them.
- **Implication:** every rule ever "promoted to APPLIED 100%" in the loop's tracker has done nothing. Fix: rule_compiler.py + startup self-check (~3h).

### 03 — `03_web_page_audit.md`
Per-page audit of all 18 frontend pages.
- **Key finding:** 6 of 18 pages exceed 2,500 lines. Three "LLM/agent" pages overlap. Three "analytics" pages overlap. Two "education" pages overlap.
- **Implication:** 18 pages → 12 sections. Extraction + MDX migration would shrink ~38,000 lines to ~12,000 with no functional loss. (Superseded by §05 HL-style approach.)

### 04 — `04_infrastructure_reshape_plan.md`
Three competing backends found.
- **Key finding:** `bot/api_server.py` (FastAPI, file-based, ~36 routes) is the de facto winner. `api/app/` (FastAPI + Postgres, partial duplicate) and `bot/dashboard/server.py` (Flask, 9.6KLOC, legacy) should die.
- **Implication:** kill 11K+ lines of legacy backend. Net architectural simplification.

### 05 — `05_ui_reshape_hyperliquid_style.md`
The Hyperliquid-styled scaffolding direction.
- **Key finding:** `theme.ts` had AI-style fingerprints (11 gradient tokens, 7 glass variants, multiple glow shadows, springs). HL convention is the opposite — boring chrome, dense data.
- **§7 addendum:** "Beyond a clone" — eight WAGMI superpowers (bot opinion in order rail, counterfactual diff on closed positions, calibration strip, rule transparency, hover-to-learn tooltips, connect-your-bot, advanced mode, multi-bot selector) that sit naturally inside HL chrome.

### 06 — `06_live_copilot_design.md`
Design spec for `/live` triple-panel + Q&A.
- **Built this session:** all of it. Mechanical | Agentic | Synthesis columns + AskAgentsPanel with rate-limited backend + scoreboard + replay mode. See §07 for what shipped.

### 07 — `07_session_summary.md`
Inventory of what was built in this session.
- **22 commits shipped.** Branch `claude/audit-and-planning-3ocfV` is a complete UI rebuild plus several backend additions (`/v1/agents/ask`, `/v1/decisions/at`, `/v1/synthesis`, agent breakdown join).

### 08 — `08_wider_wiring_audit.md`
Same grep pattern as §02 applied to every feedback/learning subsystem.
- **Key finding:** §02 was an OUTLIER, not a pattern. 16 of 18 subsystems are wired correctly (ParameterTuner, StrategyWeightManager, memory_store, deep_memory, cost_tracker, etc.). Only 2 are cosmetic: graduated_rules and SwarmFeedbackLoop.
- **Implication:** the bot's feedback machinery isn't broken systemically. Fix the 2 outliers and the loop is clean.

### 09 — `09_dormant_agents_audit.md` 🔥
The agent layer's biggest finding.
- **Key finding:** 13 of 23 LLM agent roles are fully implemented (prompts + builders + coordinator accessors) with ZERO external callers. ~1,100 lines of working agent code that nothing in `multi_strategy_main.py` ever invokes.
- **Implication:** big design surface sitting on the shelf — Forecaster (regime transitions), Position Sizer + Risk Guard + Conviction (sizing stack), Agent Router + Consensus Builder (dynamic orchestration), Hypothesis (novel pattern discovery), Scalper + Micro-Trend (HF tier).
- **Recommended next action:** wire Forecaster first (~2h, daily, informational, zero risk).

### 10 — `10_strategies_audit.md`
Strategies layer audit.
- **Key finding:** strategies in much better shape than agents — 13 of 22 active, 5 infrastructure, 3 default-OFF imports, only 3 true orphans.
- **Orphans:** alternate implementations of funding/OI/liquidation (mean-rev / divergence / heatmap-proximity vs the active counter-extreme / delta / event-cascade).
- **Implication:** ~6 hours of backtesting could validate up to 6 new ensemble members (3 default-off flips + 3 orphan wirings).

---

## Combined Fix-List, Ranked by Impact-per-Hour

| Priority | Fix | Effort | Source |
|---|---|---|---|
| **1** | Rule compiler — make the 49 graduated rules actually enforce | 2-3h | §02 |
| **2** | Wire Forecaster agent — daily regime forecast | 2h | §09 |
| **3** | A/B treatment_wr collection — close the rule-validation loop | 1.5h | §02, OVERNIGHT_BLUEPRINT §4.3 |
| **4** | Counterfactual page hero stat (TP1 underweighting) | 30min | §01 |
| **5** | Backtest 6 candidate strategies (3 default-off + 3 orphan) | 6h | §10 |
| **6** | Wire SwarmFeedbackLoop output to ParameterTuner | 2-3h | §08 |
| **7** | Wire Portfolio + Correlator agents (informational) | 4h | §09 |
| **8** | Kill `api/app/` and `bot/dashboard/` legacy backends | 2h | §04 |
| **9** | filter_accuracy: verify dormant, wire or delete | 30min | §08 |
| **10** | TopBar `<DataSourceBanner />` so backtest vs live data is unambiguous | 1h | §03 |

**~22 hours of focused work** to close every gap surfaced this session and
ship the highest-EV improvements.

---

## Things This Session DIDN'T Audit

If a future session goes deeper:

- **Test coverage map** — 113 test files, 3,488 test functions. Which subsystems are untested?
- **Prompt quality** — read each agent's prompt body (not just the header) and grade for clarity, output schema strictness, common failure modes.
- **The growth/ subsystem** — instantiated, but I didn't trace whether its outputs reach trading decisions.
- **`bot/data/learning/` (gitignored)** — Master Engine's local outputs. Cannot read from this branch.
- **Strategy-by-strategy backtest performance** — `/strategy-discover` skill in CLAUDE.md is built for this; running it produces the data §10 calls for.
- **Test-file dependencies on dormant code** — if we wire/unwire the dormant agents, which tests break?

---

## Bottom Line

The **biggest unlock per hour of fix work** is §02's rule compiler. Until that lands, every "rule promotion" the perpetual loop has logged is fictional. Wire that, then Forecaster (§09 #1), then the A/B closure (§02 follow-up), then 6h of strategy backtests (§10).

That's a coherent ~13-hour roadmap that converts ~3,500 lines of inert code into actual trading edge.
