# Spong — Style Codex

> **Status:** SKELETON. The real codex will be seeded from the
> `@ghostmemes` / `memedepot.com/d/spong` corpus the same way the
> $MOTION codex was reverse-engineered from 47 reference videos.
>
> Until the corpus is ingested, the Director should treat this codex as
> an empty-handed brief and rely on craft playbooks only. Do NOT invent
> Spong signature moves — if you don't know, ASK THE OPERATOR.

## What we know so far

- Creator / operator: `@ghostmemes` on X.
- Home: `memedepot.com/d/spong` (depot #1401).
- Not to be confused with `$SPONGE` (the SpongeBob memecoin on Uniswap).
  Spong ≠ Sponge.

## Ingest workflow (the operator runs this once a corpus exists)

```
memegine project use spong
# drop 20-50 representative stills / videos into memegine-inbox/spong/
memegine corpus ingest memegine-inbox/spong/
memegine corpus reverse-local          # patterns per frame, no API
memegine corpus apply <patterns.json>  # propagate into refs/codex
```

Once the corpus is ingested, the Director will:

1. Identify recurring subject archetypes (pull into `brand.yaml:subject_archetypes`)
2. Extract the typography register(s) used
3. Extract the color palette
4. Name 5-10 signature moves
5. Update this codex with the actual ground-truth patterns

## Compounded Patterns

*(empty — ingest corpus first)*
