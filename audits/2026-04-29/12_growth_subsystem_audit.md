# Growth Subsystem Audit — 2026-04-29

**Question:** the `bot/llm/growth/` directory has 8 files / 3,414 lines of self-improvement infrastructure (hypothesis_tracker, recommendation_engine, self_improvement, veto_feedback, growth_report, explainability, orchestrator). Is this another writes-only / unwired pattern, or is it actually closing the loop?

**Headline:** **Growth is correctly wired** — verified by reading actual implementation, not just imports. Of all the candidate "self-improvement" subsystems audited so far, this is the one that consistently demonstrates the *fixed* version of the §7.7 bug pattern.

There's even a smoking-gun comment at the top of `bot/llm/learning_integrator.py` that documents exactly when this got fixed:

```
This module addresses the following gaps identified in the learning system audit:

1. PROPOSAL DISPATCHER: Makes self-improvement proposals actually apply changes
   (previously apply_proposal() only updated JSON status, never mutated config)
```

So the `apply_proposal()` → "no actual effect" bug existed *and was explicitly fixed* by someone before this session. The fix was a `learning_integrator.dispatch_proposal()` method that maps each proposal type to a real config mutation.

The same pattern was *not* applied to `graduated_rules.json` (still broken per §02) or to `SwarmFeedbackLoop` (still broken per §08). The growth subsystem learned the lesson; the others didn't.

---

## Inventory + Status

| File | Lines | Wired | Notes |
|---|---|---|---|
| `orchestrator.py` | 638 | ✅ | `get_growth_orchestrator()` instantiated in `multi_strategy_main.py:916`, `tick()` called every iteration at line 2017 |
| `hypothesis_tracker.py` | 659 | ✅ | Read by coordinator agent (regime forecasts evidence), learning_integrator (records evidence), graduates → graduated_rules.py runtime engine |
| `self_improvement.py` | 587 | ✅ | Auto-applied via dispatch_proposal in orchestrator tick — actually mutates config |
| `recommendation_engine.py` | 397 | ✅ | Wired into orchestrator state; consumed by growth_report |
| `growth_report.py` | 372 | ✅ | Periodic comprehensive reports, gated by `should_generate()` |
| `explainability.py` | 296 | ✅ | Records every parameter change via `on_parameter_change()` callback hook in orchestrator |
| `veto_feedback.py` | 444 | ✅ | Tracks Critic agent vetoes against actual outcomes; canonical veto path |
| `__init__.py` | 21 | ✅ | Exports |

**0 dead modules.** Substantive contrast to the agents directory (§09: 13 of 23 dead) or the swarm system (§08: complete swarm dead).

---

## What the Orchestrator Actually Does Per Tick

`orchestrator.tick()` at line 334 runs on every main loop iteration:

1. **Update trade buffer** — adds recent trades to running window
2. **Hypothesis evidence updates** — for any pending hypotheses, records new outcomes
3. **Learning cycle (if due)** — invokes `_run_learning_cycle()` which calls the self-teaching engine
4. **Auto-apply safe improvement proposals** (lines 416-440) — pulls `_improvement_engine.get_auto_applicable()`, dispatches each via `learning_integrator.dispatch_proposal()`, marks applied with notes capturing whether dispatcher fired or it was display-only
5. **Generate growth report (if due)** — periodic comprehensive snapshot
6. **Run Overseer agent (every 30 min)** — explicitly gated by LLM_MODE=0 check (Finding 5 from 2026-04-15 wired correctly)

**Critical detail:** auto-apply caps at 5 proposals per tick to avoid runaway. Conservative.

---

## What `dispatch_proposal` Actually Mutates

From `learning_integrator.py` lines 66-100:

| Proposal type | Real-world effect |
|---|---|
| `parameter: confidence_floor` | Updates `AdaptiveConfidenceFloor.current_floor`, persists to state file. Reading subsystems (ensemble's pre-merge gate) pick it up next load. |
| `parameter: max_leverage` | Updates global config |
| `action: adjust_weight` | Mutates `StrategyWeightManager` weights |
| `action: pause_symbol` | Adds symbol to disabled list |
| anything else | Logged "No dispatcher for action: {action}. Marking as applied (display-only)." |

**The "display-only" branch is the failure mode to watch for.** When growth proposes a novel action type the dispatcher doesn't handle, the proposal is marked applied but does nothing. Worth instrumenting:

```python
# Suggested addition to learning_integrator.dispatch_proposal:
else:
    logger.warning(
        f"[INTEGRATOR] DISPATCH GAP — proposal type '{action_type or param}' "
        f"has no handler. Add to learning_integrator._apply_*."
    )
```

This converts silent display-only into a loud warning that the dispatcher needs extension.

---

## Where Growth Outputs Go

- **Hypotheses** that graduate (10+ evidence) → `llm/graduated_rules.graduate_hypothesis()` → writes to `data/llm/graduated_rules.json` (the runtime file the bot reads — different from the broken `feedback/graduated_rules.json` per §02)
- **Knowledge base entries** → `data/llm/teaching/knowledge_base.json` (337 entries, 6 graduated). Injected into agent prompts via prompt_enricher.
- **Self-improvement proposals** → `data/llm/proposals/*.json`, applied via dispatcher
- **Growth reports** → `data/llm/growth_reports/*.md`
- **Veto feedback** → `data/llm/veto_log.jsonl`

All these have read paths somewhere. Verified spot-checks for the ones that matter: `knowledge_base.json` is read by `snapshot_builder.py` to inject into agent context (confirmed §08).

---

## How Growth Compares to Other "Improvement" Layers

| Layer | Writes | Reads | Verdict |
|---|---|---|---|
| **growth/** | proposals, reports, hypotheses, KB entries, vetoes | learning_integrator dispatches → real config mutations; KB → agent prompts | ✅ closed loop |
| **graduated_rules.py** (runtime) | `data/llm/graduated_rules.json` via hypothesis graduation | `coordinator.py:4393`, `ensemble.py:583` | ✅ closed loop |
| **graduated_rules.json (loop file, §02)** | `feedback/graduated_rules.json` 49 rules | (NOTHING) | ❌ open loop |
| **swarm_feedback_loop (§08)** | `feedback/swarm/config_overrides_*.json` | (NOTHING) | ❌ open loop |
| **dormant agents (§09)** | (no methods called) | (no methods called) | ❌ open loop |

So the project has **two parallel improvement pathways**:

1. **growth → learning_integrator → config mutations** (works, lesson learned)
2. **perpetual_loop → feedback/graduated_rules.json + swarm overrides** (doesn't work, lesson not yet propagated)

The fix for #2 is to copy #1's pattern: build a dispatcher for each proposed change type, route through the same trust-gated path (ParameterTuner / AdaptiveConfidenceFloor / StrategyWeightManager).

This is exactly what §02's "rule_compiler.py" recommendation describes, just framed differently. The wider lesson:

> **Don't write self-improvement subsystems that only mutate JSON files and hope something reads them. Always pair the writer with an explicit dispatcher that calls existing config-mutation APIs.**

---

## Concrete Gaps Found

Despite the overall positive verdict, three small gaps:

### Gap 1 — Display-only fallback is silent

When `dispatch_proposal` encounters an unknown action type, it logs INFO and returns False. This is silent degradation: proposals get marked "applied" but do nothing, and unless someone reads logs nobody knows the dispatcher fell short.

**Fix:** WARN-level log + emit metric. ~10 minutes.

### Gap 2 — Proposal types not covered

Currently dispatched: confidence_floor, max_leverage, adjust_weight, pause_symbol. Likely missing dispatchers (high-value, easy wins):

- `parameter: leverage_cap_per_regime` (per-regime leverage caps)
- `parameter: tp1_partial_pct` (the TP1 underweighting fix from §01!)
- `action: enable_strategy` / `disable_strategy` (toggle ensemble members)
- `action: enable_agent` / `disable_agent` (toggle dormant agents per §09)
- `parameter: floor_per_symbol_side` (per-(sym,side) floors per BLUEPRINT)

Adding these unblocks the growth subsystem to apply richer proposals it's already capable of generating. ~3 hours total.

### Gap 3 — Apply rate cap of 5/tick may be too conservative

5 auto-applies per tick means catching up after downtime takes a while. If the bot is offline for 7 days and accumulates 200 pending proposals, it'll take 40+ ticks (~10 minutes if tick is 15s) to drain. That's fine in steady-state but slow on restart.

**Fix:** add a `catch_up_mode` parameter that allows higher rate when proposal queue exceeds threshold. ~30 minutes.

---

## Bottom Line

**Growth is the canonical example of "feedback loop done right" in this codebase.** The §02/§08/§09 fixes should pattern after it:

1. Build a dispatcher (`learning_integrator.dispatch_*`) that maps proposal/recommendation types to real config mutations.
2. Route through existing trust-gated APIs (ParameterTuner, AdaptiveConfidenceFloor, StrategyWeightManager) — don't invent new ones.
3. WARN on unhandled types so gaps surface loudly.

If §02's "rule_compiler.py" follows this pattern (instead of inventing yet another translation layer), the resulting system is consistent, debuggable, and harder to regress.

**Scheduling:** the gap-1 + gap-2 fixes (~3.5h) are excellent companion work to the §02 rule compiler — adding TP1 partial fraction as a dispatcher target would directly enable the growth system to act on the §01 counterfactual finding.
