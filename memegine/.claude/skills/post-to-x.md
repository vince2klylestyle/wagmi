# /post-to-x — end-to-end flow: brief → grok → post-ready

## Description

The last-mile skill. Takes the result of a generation (final media
file + prompt + why-it-worked note) and walks the operator through
preflight, post-bundle build, X pre-flight, and engagement log setup.

## Arguments

`$ARGUMENTS` — `<media_path> ||| <caption> ||| <alt_text> ||| <prompt>`
(pipe-separated for easy one-line capture). `<alt_text>` and `<prompt>`
optional.

## Workflow

### 1. Parse pipes
Split on ` ||| `. Required: media + caption. Optional: alt text,
winning prompt (for compounding).

### 2. Caption preflight
```bash
cd memegine && python -m memegine.cli caption-lint "$CAPTION"
```
Fail hard on errors (emojis / hashtags / gm-wagmi / engagement-bait /
over-280-char). Ask the operator to rewrite before proceeding.

### 3. Prompt preflight (if winning prompt supplied)
```bash
memegine preflight "$PROMPT"
```
Warn if craft score < 70 or consistency < 30%. Don't block.

### 4. Build the post bundle
```bash
memegine post build "$MEDIA" \
  --caption "$CAPTION" \
  --alt "$ALT_TEXT"
```
Note the bundle id from the output.

### 5. X prepare
```bash
memegine x prepare <bundle_id>
```
Print the clipboard-ready block (media path + caption + alt + reply
hook). Operator copies this block while posting.

### 6. Remind to log
Explicitly tell the operator: after the post lands, run one of:

```bash
# Phone-friendly (paste the X analytics block directly):
memegine perf paste "820 likes 140 RT 35 replies"

# Or structured:
memegine perf log --likes 820 --rt 140 --replies 35 \
  --format <format_slug> --bundle <bundle_id>
```

### 7. Compound it
If `--prompt` was supplied, immediately log as a winner:

```bash
memegine refs add "$MEDIA" \
  --winner --prompt "$PROMPT" --notes "<why it landed>" \
  --auto-variants --n-variants 3
```

This triggers the compounding chain:
- Appends the prompt to "Proven Prompt Patterns" in the codex
- Auto-extracts named craft tokens to "Compounded Patterns"
- Enqueues 3 variant-intent topics for the next session

## Notes

- If `/post-to-x` is invoked without any winning-prompt context, skip
  the compounding step — but remind the operator to tag as a winner
  once they confirm it's a landed piece (after engagement).
- If `memegine consistency` shows a very-low alignment, mention which
  Core Patterns the prompt missed. This is a nudge, not a block.
