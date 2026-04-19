# /full-pipeline — idea-to-brief end-to-end, phone-first

## Description

The master skill for Claude-on-phone (Termux / iSH / a-Shell). Takes
a rough idea the operator just had, walks it through grading →
queuing-or-briefing → preflight → (if API key) executing → ready-to-
paste output. All in one conversation turn.

This is the unlock the operator described: "I just thought of X, tell
me what to do with it, end to end."

## Arguments

`$ARGUMENTS` — rough intent (freeform text). The operator just tells
you what they're thinking. No flags or special syntax.

## Workflow

### 1. Check the doctor (silently)
```bash
cd memegine && python -m memegine.cli doctor 2>&1 | tail -1
```
If it doesn't end in "PASS", surface the broken thing first and stop.
Don't proceed with a broken env.

### 2. Grade the idea
```bash
memegine grade-idea "$INTENT"
```
- **A**: ship it. Go to step 3.
- **B**: worth briefing. Go to step 3.
- **C**: underbaked. Offer 2-3 specific tightenings from the grader's
  tips; if operator accepts one, rerun grade, then proceed.
- **D or F**: stop. Tell operator why. Offer to queue the raw idea
  with `/topic-add` for tomorrow instead.

### 3. Check the queue + dashboard context
```bash
memegine next 2>&1 | tail -20
```
Note the queue count and top-performing format. If this intent
naturally overlaps with an already-queued topic, mention it.

### 4. Pipeline the idea
```bash
memegine piece "$INTENT"
```
Note the bundle folder. Open the first `.md` in the folder:
```bash
cat <bundle_folder>/01-prompt.md
```

### 5. Execute the brief in-session
Claude — that's you — read the SYSTEM + USER blocks and produce the
JSON result per the Director prompt. Don't ask the operator to paste
anywhere; you ARE Claude.

### 6. Preflight the resulting prompt
```bash
memegine preflight "<the prompt field from your JSON>"
```
- **PASS**: go to step 7.
- **WARN**: mention what's missed; if operator wants sharpening, run:
  ```bash
  memegine fix-prompt "<the prompt>"
  ```
- **FAIL**: mandatory fix. Use `fix-prompt` automatically.

### 7. Output the final prompt to operator
Print the finished prompt in the chat so the operator can long-press
to copy it on phone. Include:
- the prompt itself
- 2-3 caption options from the brief
- a one-line "next step" note (usually: "paste into Grok Nano Banana
  via X mobile")

### 8. Set up compounding
After printing the prompt, tell the operator:
> When the piece lands, run:
> `memegine refs add <file> --winner --prompt "<the prompt>" --notes "<why>" --auto-variants`
> and
> `memegine perf paste "<X analytics block>"`

So they compound it without thinking.

## When the intent includes an image

If the operator mentions "like this photo" or pastes/references an
image path, use `/inspire` (memegine inspire <image> "<intent>") instead
of `piece`. That inherits the image's craft tokens into the new intent.

## When the intent references a prior winner

If the operator says "make another like last week's 3am trader one",
use `/like-winner`:

```bash
memegine like-winner "<the new intent>"
```

This inherits the LAST winner's craft tokens automatically.

## Short-circuit paths

If the operator is clearly in a hurry (says "quick", "just", "short
version"), skip steps 3 and 6's warnings — just run `piece` and output
the prompt. The operator will preflight themselves if they want.

## What you should never do

- Never paste the prompt somewhere for them — just print it.
- Never mark a piece as a winner before the operator confirms it
  landed. Winners compound via `refs add --winner`.
- Never run `corpus reverse` as part of this flow — that's a separate
  one-time bootstrap that costs API money.
- Never skip preflight when craft score < 50. That prompt will
  produce bad Grok output.
