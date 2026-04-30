# Audit Index — 2026-04-29 Session

This session produced 13 audit documents totaling ~3,300 lines of analysis.
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
| Run-only scripts accumulated | ~70 of 75 in bot/tools/ | §11 |

Combined: **~5,000 lines of "complete but inert" code** across the project.

But importantly, **growth/ is the canonical "done right" example** (§12) that
shows the fix pattern: dispatcher + trust-gated APIs + WARN on unhandled
types. The project has *learned the lesson* in one place; the §02/§08 fixes
just need to propagate it.

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

### 11 — `11_tools_audit.md`
`bot/tools/` directory hygiene.
- **Key finding:** 75 Python files / 29,200 lines, only 4 imported programmatically, only 3 referenced by skills. ~70 are run-only scripts with significant duplicates (3 stop-hunt scripts, 4 backtest tools, 5 edge tools, 3 regime tools).
- **Implication:** ~3.5h manifest + archive pass would dramatically improve discoverability without touching runtime. Two scripts (`thesis_tracker.py`, `regime_detector.py`) need to move *out* of tools/ — they're runtime code or name-collide with strategies.

### 12 — `12_growth_subsystem_audit.md` ✅
The canonical "done right" example.
- **Key finding:** 8 modules / 3,414 lines all wired correctly. `growth.tick()` runs every iteration. `dispatch_proposal()` actually mutates real config (confidence_floor, max_leverage, weights, symbol-pause). 5/tick auto-apply cap.
- **Smoking-gun:** docstring in `learning_integrator.py` documents "PROPOSAL DISPATCHER: Makes self-improvement proposals actually apply changes (previously apply_proposal() only updated JSON status, never mutated config)" — proves the §02/§08 bug pattern was once present here, was fixed, and the lesson should propagate.
- **Three small gaps:** silent display-only fallback, missing dispatchers for tp1_partial_pct / leverage_cap_per_regime / enable_strategy / enable_agent / floor_per_symbol_side, conservative 5/tick cap.
- **Implication:** §02/§08 fixes should pattern after growth, not invent new architectures.

### 13 — `13_skills_audit.md`
`.claude/skills/` directory.
- **Key finding:** 41 skill files, 100% documented in CLAUDE.md, all referenced commands valid. **Best-curated directory in the project.**
- **Gap:** 5-7 of 9 `cli.py` modes have no skill wrapping them (replay, walkforward, gate, compare, tiers).
- **Implication:** ~4-6h to add 5 missing skills + update 3 stale ones (`/add-agent` should include wiring checklist, `/web-dashboard` post-§05, `/babysit` validate tools).

---

## Combined Fix-List, Ranked by Impact-per-Hour

| Priority | Fix | Effort | Source |
|---|---|---|---|
| **1** | Rule compiler (pattern after growth's dispatcher) | 2-3h | §02, §12 |
| **2** | Wire Forecaster agent — daily regime forecast | 2h | §09 |
| **3** | A/B treatment_wr collection | 1.5h | §02, OVERNIGHT §4.3 |
| **4** | Add TP1-partial-fraction dispatcher in growth | 1h | §01, §12 |
| **5** | Counterfactual page hero stat (TP1 underweighting) | 30min | §01 |
| **6** | Backtest 6 candidate strategies (3 default-off + 3 orphan) | 6h | §10 |
| **7** | Wire SwarmFeedbackLoop output via growth-style dispatcher | 2-3h | §08, §12 |
| **8** | Add WARN on growth dispatcher's unhandled-type fallback | 10min | §12 |
| **9** | Wire Portfolio + Correlator agents (informational) | 4h | §09 |
| **10** | Add 5 missing skills (replay, walkforward, gate, compare, tiers) | 4h | §13 |
| **11** | Update `/add-agent` skill with wiring checklist | 30min | §09, §13 |
| **12** | Tools directory manifest + archive pass | 3.5h | §11 |
| **13** | Kill `api/app/` and `bot/dashboard/` legacy backends | 2h | §04 |
| **14** | filter_accuracy: verify dormant, wire or delete | 30min | §08 |
| **15** | Move `thesis_tracker.py` out of tools/ to bot/llm/ | 30min | §11 |
| **16** | Resolve `regime_detector.py` name collision (tools/ vs strategies/) | 30min | §11 |
| **17** | TopBar `<DataSourceBanner />` so backtest vs live is unambiguous | 1h | §03 |

**~32 hours of focused work** to close every gap surfaced this session and
ship the highest-EV improvements.

---

## Things This Session DIDN'T Audit

If a future session goes deeper:

- **Test coverage map** — 113 test files, 3,488 test functions. Which subsystems are untested?
- **Prompt quality** — read each agent's prompt body (not just the header) and grade for clarity, output schema strictness, common failure modes.
- **`bot/data/learning/` (gitignored)** — Master Engine's local outputs. Cannot read from this branch.
- **Strategy-by-strategy backtest performance** — `/strategy-discover` skill is built for this; running it produces the data §10 calls for.
- **Test-file dependencies on dormant code** — if we wire/unwire the dormant agents, which tests break?
- **bot/execution/** — risk gates, position manager, leverage manager — none audited yet, but called out in CLAUDE.md as critical safety surface.
- **Component-level deduplication of `web/components/`** — 24+ files, likely redundancy after page-bloat surfaced in §03.
- **Observability/logging/alerts pipeline** — bot/alerts/, structured_logging, metrics_middleware. Wired correctly?
- **bot/data/ pipeline** — fetcher, db, migrations. The "is the data layer healthy" question.

---

## Bottom Line

The **biggest unlock per hour of fix work** is §02's rule compiler, *patterned after growth's dispatcher* (§12). Until that lands, every "rule promotion" the perpetual loop has logged is fictional.

The wider lesson the audits surface: WAGMI **already learned how to wire feedback loops correctly** (growth subsystem). The remaining dead-code surface (rule compiler, swarm overrides, dormant agents) just needs to follow the same pattern instead of re-inventing.

Coherent ~13-hour roadmap to ship the top-5 fixes:
1. Rule compiler (3h) — §02 + §12 pattern
2. Forecaster wiring (2h) — §09
3. A/B treatment_wr (1.5h) — §02 follow-up
4. TP1 partial dispatcher (1h) — §12 + §01
5. Counterfactual hero stat (30min) — §01
6. 6h backtest of strategy candidates — §10

That converts ~5,000 lines of inert code into actual trading edge.
