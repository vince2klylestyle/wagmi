# /preflight — one-command pre-ship gate for any prompt

## Description

Before the operator pastes a prompt into Grok, run this to get ONE
verdict: PASS / WARN / FAIL. Combines lint + craft score + consistency
with the codex, so the operator doesn't run three commands.

## Arguments

`$ARGUMENTS` — the prompt to check. Optionally `--motion` for video.

## Workflow

### 1. Run the combined preflight
```bash
cd memegine && python -m memegine.cli preflight "$PROMPT"
```

### 2. Interpret

- **FAIL**: the prompt has banned words, or craft score < 50, or a
  motion prompt is missing a camera move. Operator fixes the issue
  before the brief reaches Grok.
- **WARN**: craft score 50-69, or codex says certain Core Patterns
  should be here but aren't. Operator CAN proceed, but it's probably
  worth running `fix-prompt` first.
- **PASS**: craft >= 70 AND no errors AND codex alignment OK. Ship it.

### 3. Next action recommendations

- FAIL → `memegine fix-prompt "$PROMPT"` often converts FAIL → WARN/PASS
  by auto-inserting the missing craft fragments.
- WARN → mention the specific missed tokens from the consistency report
  (these come from the codex). The operator can manually add them.
- PASS → paste into Grok directly.

## When to skip

If the project codex is empty (no Core Patterns / Visual DNA entries),
consistency scoring is meaningless. In that case run the base
`memegine score` instead — it only requires craft coverage. Once the
codex has real entries (from `corpus distill` or manual tagging),
`/preflight` becomes the default gate.
