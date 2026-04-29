# Rule Enforcement Audit — 2026-04-29 (§7.7 of OVERNIGHT_BLUEPRINT)

**Severity:** P0 — Structural

## TL;DR

The bot has **two independent "graduated rules" systems with incompatible schemas, no sync between them, and no documentation that they are different.**

- **System A (runtime, what the bot uses):** `bot/data/llm/graduated_rules.json` — **does not exist on disk**. Empty.
- **System B (where the perpetual improvement loop writes):** `bot/feedback/graduated_rules.json` — 49 rules tracked, last update 2026-04-29 19:18 UTC.
- **None of System B's 49 rules are enforced at runtime.** The two files have entirely different schemas (`hypothesis_statement / conditions / adjustment / evidence_ratio` vs `rule_id / description / gate_percentage / baseline_wr / treatment_wr`); even copying the file across would not work without translation.

Yesterday's run (`cf0455c` 2026-04-28 14:30) called this out: *"HYPE EV = -$12.63/trade (-$5,014 total) despite HYPE_EV rule at 100% gate."* The Master Engine noticed the rule wasn't filtering. **It wasn't filtering because the bot has never seen it.**

## Evidence

### 1. The runtime engine reads from `data/llm/graduated_rules.json`

`bot/llm/graduated_rules.py:21`:
```python
_RULES_FILE = os.path.join("data", "llm", "graduated_rules.json")
```

When the bot is launched from `cd bot && python run.py paper`, this resolves to `/home/user/WAGMI/bot/data/llm/graduated_rules.json`. That file does not exist:

```
$ ls /home/user/WAGMI/bot/data/llm/graduated_rules.json
ls: cannot access ...: No such file or directory
```

`GraduatedRulesEngine._ensure_loaded()` silently passes when the file is absent (`if os.path.exists(...)` check at line 86). So the engine starts with an empty rule list. Every call to `evaluate_signal(...)` returns `(vetoed=False, adjustment=0, notes=None)` — a no-op.

### 2. Two runtime call sites depend on this engine

- `bot/strategies/ensemble.py:583` — applies graduated rules **before** the confidence floor gate. With the engine empty, this is dead code at runtime.
- `bot/llm/agents/coordinator.py:4393` — applies graduated rules **after** all agent voting. Also dead code.

Both call sites correctly hook in. They just have nothing to vote on.

### 3. The perpetual improvement loop writes to a different file with a different schema

`bot/feedback/graduated_rules.json` (the file we've been editing):
```json
{
  "rule_id": "F11_proven_setup_3tuple",
  "source": "AUTONOMOUS_SESSION_2026_04_15 Finding 11",
  "description": "...",
  "status": "APPLIED",
  "gate_percentage": 100,
  "baseline_wr": 0.337,
  "treatment_wr": null,
  ...
}
```

`bot/llm/graduated_rules.py:GraduatedRule` dataclass:
```python
@dataclass
class GraduatedRule:
    rule_id: str = ""
    hypothesis_statement: str = ""
    action: str = "penalize"  # veto, boost, penalize, size_adjust
    conditions: Dict[str, Any] = field(default_factory=dict)
    adjustment: float = 0.0
    evidence_ratio: float = 0.0
    total_evidence: int = 0
    ...
```

These cannot be merged by file copy. The `feedback/graduated_rules.json` rules describe **proposed gate-percentage rollouts**; the runtime engine expects **deterministic conditions + adjustments**.

### 4. There is no sync script

```
$ grep -rn "feedback/graduated_rules\|sync.*graduat\|migrate.*rule" bot/ --include="*.py"
(empty)
```

No code path copies, translates, or syncs between the two files. The disconnect is total.

### 5. The runtime engine IS being fed — but by hypothesis_tracker, not by us

`bot/llm/graduated_rules.py:graduate_hypothesis(...)` is called from `bot/llm/growth/hypothesis_tracker.py:524,548`. When a hypothesis accumulates 10+ evidence events, the tracker promotes it to a runtime rule and writes to the (missing) `data/llm/graduated_rules.json`.

So the runtime path has been *latently* working — when the bot was running, hypothesis_tracker would graduate hypotheses, the file would be created, and rules would apply. The file currently doesn't exist because the bot has been offline 140+ hours and presumably the previous file was rotated/cleared at some point.

`bot/data/llm/teaching/knowledge_base.json` (200KB, 337 entries) is the *side effect* of that runtime path — every graduated hypothesis writes a `[EDGE] / [CAUTION] / [AVOID]` entry into it, and the prompt enricher injects those into agent prompts. **6 of the 337 entries are hypothesis-graduated.** So six rules survive in agent-prompt form, but they are not the 49 we track in `feedback/graduated_rules.json`.

## Implications

### Implication 1 — Most "rule promotions" did nothing

When the perpetual improvement loop says "promoted X to APPLIED at 100% gate," it means the row was rewritten in `feedback/graduated_rules.json`. **It does not mean the rule is enforced.** The 49 rules tracked there are diagnostic/aspirational — they document what we've decided, but they don't *do* anything when the bot trades.

### Implication 2 — The "$5,014 HYPE bleed despite HYPE_EV rule at 100%" is fully explained

HYPE_EV was promoted in `feedback/graduated_rules.json`. The bot read no rule. HYPE bled.

### Implication 3 — The treatment_wr loop being broken is doubly broken

We established yesterday that 35/49 rules have `treatment_wr=null` because no live trades flow. Even if trades flowed, `treatment_wr` would not update meaningfully because **the treatment is not actually being applied** to those trades. Both arms of every A/B are baseline.

### Implication 4 — The hypothesis_tracker path is the path that actually works

If we want a rule to fire at runtime, we need to either:
- (a) Encode the rule via `hypothesis_tracker → graduate_hypothesis()` so it lands in `data/llm/graduated_rules.json` with the right schema, OR
- (b) Build a translator from `feedback/graduated_rules.json` schema → `data/llm/graduated_rules.json` schema, run it on bot startup.

Option (b) is what the perpetual loop almost certainly intended.

## Required Fixes (in priority order)

### Fix 1 — Add a translator and call it at bot startup (~3h)

Build `bot/feedback/rule_compiler.py`:
- Reads `bot/feedback/graduated_rules.json`.
- For each rule with `status: APPLIED` and `gate_percentage: 100`, produces a `GraduatedRule` dataclass instance (mapping `description` → `hypothesis_statement`, parsing symbol/regime/side/strategy from `description` text or a new explicit `conditions` block, mapping the rule's intent to `action: veto/boost/penalize`).
- Writes to `bot/data/llm/graduated_rules.json` in the runtime schema.
- Called in `MultiStrategyBot.__init__` before `evaluate_signal` is wired up.

This is the highest-leverage single fix in the whole system. It makes weeks of perpetual-loop work *actually take effect.*

### Fix 2 — Schema-extend `feedback/graduated_rules.json` to include explicit conditions (~1h)

Right now rules describe themselves in prose (`"description": "Block all SOL SHORT signals at 100% gate"`). The translator would parse prose, which is fragile. Add explicit fields:

```json
{
  "rule_id": "SOL_SHORT_full_block",
  "conditions": { "symbol": "SOL", "side": "SHORT" },
  "action": "veto",
  "adjustment": 0,
  ...
}
```

For old rules without these fields, the translator falls back to prose parsing (and logs the parse failure for human follow-up).

### Fix 3 — Rationalize the two systems before adding more (~30min decision)

Pick one of:
- **(A) `feedback/graduated_rules.json` is the source of truth, runtime file is generated.** This is what Fix 1 implements.
- **(B) Migrate the perpetual loop to write directly to `data/llm/graduated_rules.json`.** Lose the rich gate-percentage/baseline/treatment metadata in the process unless we also extend the runtime schema.
- **(C) Two systems remain — but with explicit boundary.** Loop file = "human-readable A/B tracking." Runtime file = "active enforcement." Translator is the bridge.

I recommend (C) with (A)'s mechanism. The richer schema in `feedback/` is genuinely useful for human review; the lean schema in `data/llm/` is correct for the hot path. Don't conflate them.

### Fix 4 — Add a startup self-check (~30min)

`MultiStrategyBot.__init__` should log:
```
[RULES] Loaded N runtime rules from data/llm/graduated_rules.json
[RULES] Of M rules in feedback/graduated_rules.json, K compiled to runtime
[RULES] Skipped P rules (status != APPLIED, gate < 100%, or parse failure)
```

If `K == 0` and `M > 0`, the bot should warn loudly. The current silent-empty-engine behavior is what let this bug live for weeks.

## Acceptance Test

After the fixes:

1. Restart bot.
2. Confirm log line: `[RULES] Loaded 6+ runtime rules from data/llm/graduated_rules.json` (the 6 obvious-by-data rules from blueprint §4.4 should compile.)
3. Trigger a HYPE LONG signal (manually via `/signal-check HYPE` or wait for one).
4. Confirm log: `[GRAD-RULES] Signal vetoed for HYPE/LONG: ...` and the signal does not reach execution.

If steps 2–4 don't pass, the fix didn't take.

## Wider Audit Recommendation

This finding suggests that other "rule" systems may have similar wiring gaps. Files to audit before restart:

- `bot/feedback/parameter_tuner.py` — does it actually mutate config that the bot reads?
- `bot/data/strategy_weights.py` — does the ensemble actually consume these weights?
- `bot/llm/memory_store.py`, `bot/llm/deep_memory.py` — do agents actually read from these stores at decision time?
- `bot/llm/cost_tracker.py` — is this just recording, or does it gate?

For each: trace from "where the data is written" to "where it's read at decision time." If there's no read path, it's dead code.

I can do this audit in a follow-up turn — it's roughly the same shape as this one, ~1h per system.
