# AUTONOMY.md - LLM Autonomy Governance

## Autonomy Levels

| Level | Name | What LLM Controls | Risk |
|-------|------|-------------------|------|
| 0 | OFF | Nothing | None |
| 1 | ADVISORY | Suggestions only (logged, not acted on) | None |
| 2 | VETO_ONLY | Can veto trades (block bad setups) | Low |
| 3 | SIZING | Veto + position size adjustment (0-2x) | Medium |
| 4 | DIRECTION | Sizing + can flip trade direction | Medium-High |
| 5 | FULL | Direction + confidence/regime override | High |

## Progression Gates

Promotion from one level to the next requires passing ALL gates:

### VETO_ONLY -> SIZING
- 100+ evaluation events
- >55% veto accuracy
- <5% API error rate
- No error bursts (3+ in 5 min)
- Positive net value (saved PnL > missed PnL)

### SIZING -> DIRECTION
- 50+ trades with LLM sizing
- Positive uplift (LLM-filtered PnL > baseline)
- <5% API error rate
- Stable win rate (no deterioration)

### DIRECTION -> FULL
- 70+ trades with LLM direction
- Positive uplift
- Zero recent API errors
- Profit factor stable
- <5% error rate overall

## Safety Invariants (NEVER removed)

1. Circuit breaker always enforced
2. Correlation guard always enforced
3. Max leverage caps always enforced
4. Kill switch always available
5. All LLM decisions logged with reasoning
6. Human can override any LLM decision via Telegram
7. LLM proposals require sandbox + human approval before activation

## Config Flags

```env
# LLM proposal controls
ALLOW_LLM_PROPOSALS=true       # LLM can suggest strategies
ALLOW_LLM_FILTERING=true       # LLM can veto/filter trades
ALLOW_LLM_AUTONOMOUS_TRADES=false  # LLM CANNOT execute trades on its own
```

## Incident Response

When an LLM decision leads to a loss:
1. Log the decision, reasoning, and market context
2. Add entry to LEARNINGS.md
3. Evaluate if progression gates should be tightened
4. Consider temporary mode downgrade
