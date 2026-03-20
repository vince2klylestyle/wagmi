# Interactive Trade-Critic Debate Implementation

## Overview

This implementation adds a sophisticated 2-round debate mechanism between the Trade Agent and Critic Agent, based on research into multi-agent decision-making systems. The debate is designed to improve decision quality by:

1. **Preventing anchoring bias** — Critic evaluates Trade thesis WITHOUT seeing confidence score
2. **Encouraging rigorous defense** — Trade Agent must rebut specific objections
3. **Score-based resolution** — Uses FREE-MAD (Free-form Multi-Agent Debate) scoring instead of simple veto

## Architecture

### Key Components

**Interactive Debate Module** (`bot/llm/agents/interactive_debate.py`)
- `ThesisProposal`: Trade Agent's initial decision
- `CounterThesis`: Critic's response with structured objections
- `Rebuttal`: Trade Agent's Round 2 response
- `DebateResolution`: Final outcome with scores
- `InteractiveDebater`: Orchestrator managing debate flow

**Debate Prompts** (in `bot/llm/agents/prompts.py`)
- `CRITIC_ROUND1_PROMPT`: Critic evaluates without anchoring
- `TRADE_REBUTTAL_PROMPT`: Trade Agent responds to objections

**Pipeline Integration** (via `bot/llm/agents/pipeline_extensions.py`)
- `run_interactive_debate_if_enabled()`: Orchestrates the debate in the pipeline

## Debate Flow

### Round 1: Proposal & Counter-Thesis

```
Trade Agent Output → Extract ThesisProposal (thesis, evidence, confidence)
                  ↓
Critic sees thesis WITHOUT confidence (hidden to prevent anchoring)
                  ↓
Critic provides CounterThesis with specific, evidence-based objections:
  - reason: specific concern with cited evidence
  - likelihood: probability the objection materializes (0-1)
  - impact: severity (thesis_invalid / timing_wrong / size_wrong)
```

### Round 2: Rebuttal & Resolution

```
Trade Agent sees Critic's objections
                  ↓
Trade Agent can:
  - DEFEND: Explain why objection doesn't invalidate thesis
  - CONCEDE: Acknowledge objection and adjust decision
  - REINTERPRET: Show how thesis is consistent with concern
                  ↓
Produces Rebuttal with adjusted action/confidence
                  ↓
Debate Scorer rates both sides:
  - trade_score: How well thesis held up (0-1)
  - critic_score: How valid objections were (0-1)
  - debate_winner: "trade" / "critic" / "consensus"
                  ↓
Final DebateResolution adjusts confidence and may flip action
```

## Scoring System (FREE-MAD)

**Trade Score** (how well thesis holds up):
- Maintains thesis without concessions: 0.70-0.80
- Maintains thesis with minor concessions: 0.60-0.70
- Adjusts thesis but action unchanged: 0.50-0.60
- Reverses action entirely: 0.20-0.30

**Critic Score** (validity of objections):
- Trade Agent concedes to objections: 0.70-0.90
- Trade Agent acknowledges objections but defends: 0.40-0.60
- Trade Agent dismisses/ignores objections: 0.10-0.30

**Resolution Logic:**
- If trade_score > critic_score + 0.2 → Trade wins, action/confidence maintained
- If critic_score > trade_score + 0.2 → Critic wins, action becomes "skip" or reduced
- Otherwise → Consensus, confidence slightly reduced (0.95x)

## Configuration

### Enable Interactive Debate

```bash
export LLM_INTERACTIVE_DEBATE=true
```

Default: `false` (uses post-hoc debate synthesis instead)

### Per-Agent Configuration

Override Critic model for more rigorous debate:
```bash
export AGENT_CRITIC_MODEL=claude-opus-4-6  # Use Opus for high-stakes decisions
```

## Usage in Coordinator Pipeline

The interactive debate runs automatically when enabled:

```
get_trading_decision()
  ├── Regime Agent
  ├── Quant Agent (optional)
  ├── Trade Agent
  ├── Risk Agent (optional)
  ├── Critic Agent
  ├── → Interactive Debate (if enabled)
  │   ├── Round 1: Critic evaluates without confidence
  │   ├── Round 2: Trade Agent rebuts (MVP: simulated from confidence drop)
  │   └── Resolution: Score-based outcome
  └── Merge outputs into final decision
```

## Research Basis

The implementation is based on three key research areas:

### 1. Multi-Agent Debate Research (MIT, 2023-2025)
- **Finding**: Multi-AI debate improves accuracy by 13.2% (voting vs consensus)
- **Key principle**: Forced disagreement surfaces tradeoffs better than consensus-seeking
- **Our application**: Structured debate between Trade (proposer) and Critic (skeptic)

### 2. Anchor Bias Prevention (Psychology, Neuroscience)
- **Finding**: Seeing a number first biases subsequent judgments (Tversky & Kahneman)
- **Our solution**: Critic doesn't see Trade confidence in Round 1
- **Result**: Critic forms independent assessment before seeing how confident Trade is

### 3. FREE-MAD: Consensus-Free Debate (2024)
- **Finding**: Scoring all intermediate outputs (not just final) prevents herding
- **Our application**: trade_score + critic_score → debate_winner (not binary veto)

## Key Features

### Structured Objections
Critic must provide specific, evidence-based objections, not just "I disagree":
```python
# GOOD
{"reason": "BTC rejected at $75k resistance, declining volume",
 "likelihood": 0.85,
 "impact": "thesis_invalid"}

# BAD
{"reason": "I'm worried", "likelihood": 0.5, "impact": "thesis_invalid"}
```

### Debate Tracking
Debate outcomes are logged to `bot/data/llm/debate_telemetry.jsonl`:
```json
{
  "ts": 1711000000,
  "symbol": "SOL",
  "trade_score": 0.75,
  "critic_score": 0.35,
  "winner": "trade",
  "trade_maintained": true,
  "critic_concessions": 0,
  "final_confidence": 0.75
}
```

### Escalation to Overseer
If debate results are inconclusive, escalates to Overseer Agent:
- Low agreement (trade_score ≈ critic_score ± 0.2)
- Multiple unresolved risk flags (>= 4)
- High-stakes decisions (both agents moderate-high confidence)

## MVP vs Full Implementation

### Current MVP
- Round 1: Critic evaluates without confidence ✅
- Round 2: Simulated from confidence drop (no actual LLM rebuttal yet)
- Scoring: Trade score + Critic score → debate winner ✅
- Integration: Adjusts final confidence based on debate ✅

### Future Enhancements (Phase 2)
- **Real Round 2**: Actual LLM call for Trade Agent rebuttal
- **Multi-round debate**: 3+ rounds for high-stakes decisions
- **Calibration tracking**: Build accuracy curves for debate mechanism itself
- **Heterogeneous models**: Use different models for Trade vs Critic to add diversity
- **Caching & replay**: Cache debate results for similar setups

## Testing

### Unit Tests
```bash
cd /home/user/WAGMI
python bot/tests/test_interactive_debate.py
```

Tests cover:
- Proposal extraction with various field names
- Counter-thesis extraction (approve vs challenge)
- Debate scoring logic
- Resolution winner determination
- Escalation conditions

### Integration Tests
Monitor live debate outcomes:
```bash
# Enable interactive debate
export LLM_INTERACTIVE_DEBATE=true

# Run paper trading
cd bot && python run.py paper

# Monitor debate telemetry
tail -f bot/data/llm/debate_telemetry.jsonl
```

## Performance Implications

### Token Cost
- Interactive debate adds ~200 tokens per Critic call (prompt overhead)
- Total cost per debate: ~600 tokens (Trade + Critic + debate processing)
- Frequency: Only runs when Critic is enabled (optional)

### Latency
- Round 1: ~1-2s additional (Critic evaluation)
- Round 2: Simulated (0ms)
- Full (future): ~2-3s additional for real Round 2

### Accuracy Benefit
- Expected: +5-10% on decision quality (based on debate research)
- Measured against: Win rate, profit factor, Sharpe ratio

## Debugging

### Enable Debug Logging
```bash
export LOG_LEVEL=DEBUG
```

Look for lines like:
```
[INTERACTIVE_DEBATE] winner=trade trade_score=0.78 critic_score=0.32 final_action=go final_conf=0.75
```

### Inspect Scratchpad
The debate outcome is written to the pipeline scratchpad:
```python
scratchpad.write("debate", "interactive_outcome", debate_outcome)
```

Access via coordinator telemetry logging.

## Calibration & Learning

Over time, track:
1. **Debate accuracy**: When Trade wins, how often does trade succeed?
2. **Critic accuracy**: When Critic vetoes, how often would trade have failed?
3. **Debate overhead**: Is debate time/cost justified by improved decisions?

Use this data to:
- Adjust debate thresholds (when to escalate, when to short-circuit)
- Fine-tune Critic and Trade prompts
- Potentially demote debate for high-confidence Trade decisions

## Related Components

- **Debate module** (`bot/llm/agents/debate.py`): Post-hoc consensus synthesis
- **Consistency checker** (`bot/llm/agents/consistency_checker.py`): Cross-agent vocabulary validation
- **Agent brains** (`bot/llm/agents/agent_brain.py`): Per-agent belief tracking and calibration
- **Overseer Agent**: Final arbitration for unresolved debates (planned)

## References

- [TradingAgents Paper](https://arxiv.org/abs/2412.20138) - Multi-agent trading framework
- [FREE-MAD Paper](https://arxiv.org/pdf/2509.11035) - Consensus-free debate mechanism
- [MIT Multi-AI Debate](https://news.mit.edu/2023/multi-ai-collaboration-helps-reasoning-factual-accuracy-language-models-0918)
- [Anchor Bias in Decision Making](https://en.wikipedia.org/wiki/Anchoring_(cognitive_bias))
