# Wider Wiring Audit — 2026-04-29

**Companion to:** `02_rules_enforcement_audit.md` (§7.7 finding that graduated_rules was cosmetic)

**Question:** does the §7.7 wiring bug (subsystem writes to disk but nothing reads at decision time) generalize to other feedback/learning subsystems?

**Method:** for each subsystem, trace from (a) where it writes its state, to (b) where that state is read at runtime by the trading loop. If no read path exists, the subsystem is cosmetic.

**Headline:** 16 of 18 subsystems are wired correctly. The §7.7 finding is **not** a systemic problem — it's two specific outliers. Both are documented below.

---

## ✅ Wired Correctly (16)

| Subsystem | Read site at runtime |
|---|---|
| **ParameterTuner** (`feedback/parameter_tuner.py`) | `feedback/loop.py:141` reads `get_calibration_offset()` and applies to `adjusted_conf` at line 142, used in pass/reject gate at 159 |
| **StrategyWeightManager** (`data/strategy_weights.py`) | `strategies/ensemble.py:1915,1985,1962-63,2027,2036,2039,2146` — used in confidence weighting, vote tallying, weighted SL aggregation |
| **memory_store** (`llm/memory_store.py`) | `llm/decision_engine.py:320` reads `get_memory_summary()` at decision time, line 861 writes after decision |
| **deep_memory** (`llm/deep_memory.py`) | `llm/snapshot_builder.py:345-346, 492-493` injects into agent context; `llm/learning_integrator.py:205,410` reads insights |
| **cost_tracker** (`llm/cost_tracker.py`) | `llm/client.py:76` gates LLM calls (`get_budget_used_pct() >= 1.0` rejects); `decision_engine.py:482` downgrades model via `get_safe_model()` |
| **evolution_tracker** (`feedback/evolution_tracker.py`) | Consumed by `cli.py:198`, `multi_strategy_main.py:2219`, `learning_integrator.py:270`, `snapshot_builder.py:306` |
| **continuous_backtest** (`feedback/continuous_backtest.py`) | Wired through `FeedbackLoop` and instantiated by `multi_strategy_main.py:95` |
| **ic_tracker** (`feedback/ic_tracker.py`) | Live in `multi_strategy_main.py:812` and CLI `cli.py:341` |
| **ev_calibrator** (`feedback/ev_calibrator.py`) | `multi_strategy_main.py:853` and `backtest/engine.py:274` |
| **kelly_engine** (`feedback/kelly_engine.py`) | `multi_strategy_main.py:813` |
| **missed_trade_tracker** (`feedback/missed_trade_tracker.py`) | `multi_strategy_main.py:835`, `backtest/engine.py:39` |
| **hold_time_rules** (`feedback/hold_time_rules.py`) | **Position manager actively gates on this.** `execution/position_manager.py:960` calls `should_block_early_exit(regime, hold_hours)` to prevent premature trail-to-stop-out |
| **adaptive_confidence** (`feedback/adaptive_confidence.py`) | `multi_strategy_main.py:32`, `backtest/engine.py:176`, `learning_integrator.py:114` |
| **rejection_tracker** (`feedback/rejection_tracker.py`) | `multi_strategy_main.py:844`, `backtest/engine.py:273` |
| **correlation_boost** (`feedback/correlation_boost.py`) | `multi_strategy_main.py:874`, `backtest/engine.py:275` |
| **growth/orchestrator** (`llm/growth/orchestrator.py`) | `multi_strategy_main.py:916` instantiates singleton via `get_growth_orchestrator()`; veto tracking lives there |

For any of these, the pattern is: **bot starts → subsystem instantiated → write/read paths used during normal trading**. If you turn the subsystem off (rename the file), the bot would fail or lose a feature, not silently continue.

---

## ❌ Cosmetic / Dead (2)

### 1. graduated_rules.json — already documented in `02_rules_enforcement_audit.md`

**Recap:** the perpetual improvement loop writes to `bot/feedback/graduated_rules.json` (49 rules); the runtime engine reads from `bot/data/llm/graduated_rules.json` (does not exist). Schemas are also incompatible — even copying the file across would not work. Need translator + startup self-check (see §7.7 for the full prescription).

### 2. SwarmFeedbackLoop — writes override configs nothing reads

**Symptom:** `feedback/swarm_feedback_loop.py:241` saves an "override config" to disk via `_save_override_config(config, override_file)`. The config contains optimization recommendations from the 6-agent swarm (entry, exit, sizing, regime tuning, pattern discovery).

**Bug:** zero runtime reads of the override files exist. Confirmed by:

```
$ grep -rn "config_overrides_\|override_config" bot/ --include="*.py" \
    | grep -v test_ | grep -v swarm_feedback_loop
(empty)
```

**Tracing the chain:**

1. The swarm itself runs only when `SwarmMaster()` is explicitly instantiated — it is not invoked from `multi_strategy_main.py`, `run.py`, or `cli.py`. So the swarm is dormant unless someone runs a separate script.
2. Even if invoked, the recommendations land in override files that the trading loop never consults.
3. `process_recommendations()` mutates `self.promoted_rules` (in-memory), which `swarm_master.py` queries — but this state lives entirely inside the swarm subsystem and never escapes to the bot.

**Effect:** the entire 6-agent swarm optimizer (Entry Optimizer, Exit Specialist, Sizing Specialist, Risk Guard, Hypothesis Generator, Feedback Loop) is currently a paperweight. Any time spent invoking it produces JSON files that the bot ignores.

**Fix options** (pick one):

- **(a) Wire the override config consumer.** When the bot starts, read all `bot/data/feedback/swarm/config_overrides_*.json` files and merge into the active config. Mirror the rule_compiler approach from §7.7. ~2 hours.
- **(b) Route swarm recommendations through ParameterTuner.** Instead of writing override files, the swarm should call `tuner.update(...)` with appropriate params. This routes through the same trust-gated path the rest of the system uses. ~3 hours.
- **(c) Document as offline/aspirational** and stop running it until wired. Lowest effort, but wastes the work already done.

I lean (b) — fewer moving parts, reuses an already-wired system.

---

## ⚠️ Dormant (probably-dead, low-confidence flag)

### filter_accuracy

**Symptom:** `feedback/filter_accuracy.py` defines `FilterAccuracyTracker` and exposes `get_filter_accuracy_tracker()` singleton. Searching for consumers:

```
$ grep -rn "filter_accuracy\|FilterAccuracyTracker" bot/ --include="*.py" \
    | grep -v test_ | grep -v "filter_accuracy.py"
(empty)
```

**Possible reasons:**
- Genuinely dead code — wrote, never wired
- Used through a singleton call site I missed (e.g., `get_filter_accuracy_tracker()` called via `getattr` or imported dynamically)
- Used in tools/scripts not in `bot/` proper

**Recommended action:** before fixing, verify by `grep -rn "get_filter_accuracy_tracker"` across the whole repo (including `tools/`, `scripts/`). If still empty, treat as dead and either delete or wire to the rejection_tracker pipeline (which it conceptually parallels).

---

## What This Audit Confirms

1. **The §7.7 finding does not generalize.** Most subsystems are wired correctly. The bot has not been suffering from systemic dead-code rot.
2. **Two specific subsystems need attention:** graduated_rules (§7.7) and swarm_feedback_loop (§this doc, item 2).
3. **One cleanup candidate:** filter_accuracy.

The §7.7 fix (rule compiler + startup self-check) and the swarm fix (route through ParameterTuner) together would close ~5–6 hours of work. After that the feedback graph is clean.

---

## Ranked Fix List (after this audit)

1. **§7.7 rule compiler** (2–3h) — translate `feedback/graduated_rules.json` → `data/llm/graduated_rules.json`. Highest impact: makes weeks of perpetual-loop work actually take effect. The 49 rules go live the moment this lands.
2. **Wire swarm recommendations to ParameterTuner** (2–3h) — route the swarm's entry/exit/sizing recommendations through the existing trust-gated tuner path. Makes the offline 6-agent optimizer's output finally land.
3. **A/B treatment_wr collection** (1.5h) — closes the feedback loop on rule effectiveness once #1 is done. Without #1 there's nothing to measure; without this every rule is unverifiable.
4. **filter_accuracy cleanup** (30min) — verify dormant, then either wire or delete.
5. **Startup self-check** (30min) — `[RULES] Loaded N runtime rules` warning when count is zero with feedback file present. Prevents this category of silent-failure from re-emerging.

Total: **~6–8 hours** to close every wiring gap currently found in the system.

---

## Methodology Note (for future audits)

The grep pattern that surfaced both findings was:

```bash
# 1. Find all writes to a JSON/state file
grep -rn "json.dump\|_save\|.write(" bot/feedback/{X}.py

# 2. Find all reads of that file
grep -rn "{filename or class name}" bot/ --include="*.py" \
    | grep -v test_ | grep -v "{X}.py"

# 3. If any consumer is just inside feedback/ itself, the system is
#    self-contained and likely cosmetic at the bot level.
```

Worth running this routinely — every new subsystem should pass this check at PR review time.
