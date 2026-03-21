"""
Debate Mechanism: diverse viewpoint synthesis for agent decisions.

The user's vision: agents should be like a "diverse research team" with
different viewpoints, NOT a unified mind. This module enables:
1. Challenge — agents can challenge each other's conclusions
2. Corroborate — agents strengthen conclusions with independent evidence
3. Synthesize — combine diverse viewpoints into weighted consensus

The debate runs AFTER all agents produce output, BEFORE the final merge.
"""

import json
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("bot.llm.agents.debate")


# ─────────────────────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Position:
    """An agent's position on a question."""
    agent: str
    stance: str  # "bullish", "bearish", "neutral", "skip"
    confidence: float  # 0-1
    reasoning: str = ""
    evidence: List[str] = field(default_factory=list)
    counter_arguments: List[str] = field(default_factory=list)


@dataclass
class Challenge:
    """A challenge from one agent to another."""
    challenger: str
    target_agent: str
    challenge_type: str  # "contradicting_evidence", "overconfidence", "missing_context", "logical_flaw"
    argument: str = ""
    evidence: List[str] = field(default_factory=list)


@dataclass
class DebateOutcome:
    """Final outcome after debate synthesis."""
    consensus_direction: str  # "bullish", "bearish", "neutral", "no_consensus"
    consensus_confidence: float
    agreement_score: float  # 0-1, how much agents agreed
    dissenting_agents: List[str] = field(default_factory=list)
    key_arguments_for: List[str] = field(default_factory=list)
    key_arguments_against: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    debate_rounds: int = 1


# ─────────────────────────────────────────────────────────────────────────────
# DEBATE MANAGER
# ─────────────────────────────────────────────────────────────────────────────

class DebateManager:
    """Orchestrates multi-agent debate for trade decisions."""

    def __init__(self):
        self.debate_history: List[DebateOutcome] = []

        # Agent weights for consensus (higher = more influence)
        self.default_weights = {
            "regime": 0.8,   # Regime sets the context
            "trade": 1.0,    # Trade Agent is primary decision maker
            "quant": 0.9,    # Quant provides hard math
            "risk": 0.7,     # Risk provides sizing/safety
            "critic": 0.85,  # Critic provides counter-thesis
            "scout": 0.5,    # Scout provides forward intel
            "learning": 0.4, # Learning provides historical context
        }

    def extract_position(self, agent_role: str, agent_data: dict) -> Position:
        """Extract an agent's position from their standard output."""
        # Different agents express positions differently
        if agent_role == "regime":
            bias = agent_data.get("bias", "neutral")
            conf = float(agent_data.get("conf", 0.5))
            stance = bias if bias in ("bullish", "bearish") else "neutral"
            return Position(
                agent=agent_role,
                stance=stance,
                confidence=conf,
                reasoning=agent_data.get("factors", ""),
            )

        elif agent_role == "trade":
            action = agent_data.get("a", agent_data.get("action", "skip"))
            conf = float(agent_data.get("c", agent_data.get("confidence", 0.0)))
            side = agent_data.get("side", agent_data.get("s", ""))

            if action in ("go", "proceed"):
                stance = "bullish" if side.upper() in ("BUY", "LONG") else "bearish"
            elif action == "flip":
                # Flip means opposite of proposed
                stance = "bearish" if side.upper() in ("BUY", "LONG") else "bullish"
            else:
                stance = "neutral"

            return Position(
                agent=agent_role,
                stance=stance,
                confidence=conf,
                reasoning=agent_data.get("thesis", agent_data.get("n", "")),
            )

        elif agent_role == "critic":
            verdict = agent_data.get("verdict", "approve").lower()
            counter = agent_data.get("counter_thesis", "")
            adj_conf = agent_data.get("adjusted_confidence")

            if verdict == "approve":
                stance = "bullish"  # Will be aligned to trade stance later
                conf = float(adj_conf or 0.6)
            else:
                stance = "neutral"  # Challenge / veto
                conf = 0.3

            return Position(
                agent=agent_role,
                stance=stance,
                confidence=conf,
                reasoning=counter or verdict,
                evidence=agent_data.get("red_flags", []),
            )

        else:
            # Generic extraction
            return Position(
                agent=agent_role,
                stance="neutral",
                confidence=0.5,
                reasoning=str(agent_data.get("summary", "")),
            )

    def detect_disagreements(
        self, positions: List[Position]
    ) -> List[Tuple[str, str, str]]:
        """Find pairs of agents that disagree.

        Returns: [(agent1, agent2, nature_of_disagreement)]
        """
        disagreements = []

        for i, p1 in enumerate(positions):
            for p2 in positions[i + 1:]:
                # Direction disagreement
                if _stances_conflict(p1.stance, p2.stance):
                    disagreements.append(
                        (p1.agent, p2.agent, f"direction: {p1.agent}={p1.stance} vs {p2.agent}={p2.stance}")
                    )

                # Confidence gap (same direction but very different confidence)
                elif p1.stance == p2.stance and abs(p1.confidence - p2.confidence) > 0.3:
                    disagreements.append(
                        (p1.agent, p2.agent,
                         f"confidence_gap: {p1.agent}={p1.confidence:.0%} vs {p2.agent}={p2.confidence:.0%}")
                    )

        return disagreements

    def generate_challenges(self, positions: List[Position]) -> List[Challenge]:
        """Auto-generate challenges based on detected disagreements.

        Deterministic (no LLM needed) — fast challenge generation.
        """
        challenges = []
        disagreements = self.detect_disagreements(positions)

        for a1, a2, nature in disagreements:
            p1 = next(p for p in positions if p.agent == a1)
            p2 = next(p for p in positions if p.agent == a2)

            if "direction" in nature:
                # The less confident agent challenges the more confident one
                challenger = p1 if p1.confidence < p2.confidence else p2
                target = p2 if challenger == p1 else p1
                challenges.append(Challenge(
                    challenger=challenger.agent,
                    target_agent=target.agent,
                    challenge_type="contradicting_evidence",
                    argument=f"{challenger.agent} sees {challenger.stance} "
                             f"({challenger.confidence:.0%}) but {target.agent} "
                             f"sees {target.stance} ({target.confidence:.0%})",
                ))
            elif "confidence_gap" in nature:
                # Higher confidence agent may be overconfident
                higher = p1 if p1.confidence > p2.confidence else p2
                lower = p2 if higher == p1 else p1
                challenges.append(Challenge(
                    challenger=lower.agent,
                    target_agent=higher.agent,
                    challenge_type="overconfidence",
                    argument=f"{higher.agent} confidence {higher.confidence:.0%} "
                             f"seems high given {lower.agent} only sees {lower.confidence:.0%}",
                ))

        return challenges

    def weighted_consensus(
        self,
        positions: List[Position],
        agent_weights: Optional[Dict[str, float]] = None,
        require_minimum_agreement: float = 0.6,
    ) -> DebateOutcome:
        """Calculate weighted consensus from all positions.

        Uses Bayesian aggregation with agent-specific weights.
        """
        if not positions:
            return DebateOutcome(
                consensus_direction="no_consensus",
                consensus_confidence=0.0,
                agreement_score=0.0,
            )

        weights = agent_weights or self.default_weights

        # Tally weighted votes per direction
        direction_scores: Dict[str, float] = {"bullish": 0, "bearish": 0, "neutral": 0}
        total_weight = 0

        for p in positions:
            w = weights.get(p.agent, 0.5)
            weighted_conf = p.confidence * w
            direction_scores[p.stance] = direction_scores.get(p.stance, 0) + weighted_conf
            total_weight += w

        if total_weight == 0:
            return DebateOutcome(
                consensus_direction="no_consensus",
                consensus_confidence=0.0,
                agreement_score=0.0,
            )

        # Normalize
        for d in direction_scores:
            direction_scores[d] /= total_weight

        # Winner
        best_direction = max(direction_scores, key=lambda k: direction_scores[k])
        best_score = direction_scores[best_direction]

        # Agreement score: how concentrated are votes?
        # 1.0 = unanimous, 0.0 = perfectly split
        scores = list(direction_scores.values())
        max_score = max(scores)
        second_score = sorted(scores, reverse=True)[1] if len(scores) > 1 else 0
        agreement = max_score - second_score  # Range [0, 1]

        # Dissenting agents
        dissenters = [
            p.agent for p in positions
            if p.stance != best_direction and p.stance != "neutral"
        ]

        # Collect arguments
        args_for = [p.reasoning for p in positions if p.stance == best_direction and p.reasoning]
        args_against = [p.reasoning for p in positions if p.stance != best_direction and p.reasoning and p.stance != "neutral"]

        # Risk flags from all positions
        all_flags = []
        for p in positions:
            all_flags.extend(p.counter_arguments)
            if hasattr(p, 'evidence'):
                # Red flags from evidence (critic uses this)
                for e in p.evidence:
                    if any(word in e.lower() for word in ["risk", "danger", "warning", "flag"]):
                        all_flags.append(e)

        # Check minimum agreement
        if agreement < require_minimum_agreement and best_direction != "neutral":
            consensus_direction = "no_consensus"
        else:
            consensus_direction = best_direction

        outcome = DebateOutcome(
            consensus_direction=consensus_direction,
            consensus_confidence=round(best_score, 3),
            agreement_score=round(agreement, 3),
            dissenting_agents=dissenters,
            key_arguments_for=args_for[:3],
            key_arguments_against=args_against[:3],
            risk_flags=list(set(all_flags))[:5],
            debate_rounds=1,
        )

        self.debate_history.append(outcome)

        return outcome

    def bayesian_consensus(
        self,
        positions: List[Position],
        prior: float = 0.5,
    ) -> Tuple[float, str]:
        """Bayesian aggregation of agent beliefs into posterior probability.

        Each agent's confidence treated as a likelihood ratio.
        Returns (posterior_probability, direction).
        """
        if not positions:
            return (0.5, "neutral")

        # Separate bullish and bearish
        bull_log_odds = math.log(prior / (1 - prior))

        for p in positions:
            if p.stance == "neutral" or p.confidence < 0.1:
                continue

            # Convert confidence to likelihood ratio
            # If bullish: LR = conf / (1-conf)
            # If bearish: LR = (1-conf) / conf (inverse)
            conf = max(0.01, min(0.99, p.confidence))

            if p.stance == "bullish":
                lr = conf / (1 - conf)
            elif p.stance == "bearish":
                lr = (1 - conf) / conf
            else:
                continue

            bull_log_odds += math.log(lr)

        # Convert back to probability
        posterior = 1.0 / (1.0 + math.exp(-bull_log_odds))
        direction = "bullish" if posterior > 0.55 else "bearish" if posterior < 0.45 else "neutral"

        return (round(posterior, 3), direction)

    def format_debate_summary(self, outcome: DebateOutcome) -> str:
        """Format debate results for human consumption."""
        lines = [
            f"DEBATE: consensus={outcome.consensus_direction} "
            f"conf={outcome.consensus_confidence:.0%} "
            f"agreement={outcome.agreement_score:.0%}",
        ]
        if outcome.dissenting_agents:
            lines.append(f"  Dissent: {', '.join(outcome.dissenting_agents)}")
        if outcome.risk_flags:
            lines.append(f"  Risks: {'; '.join(outcome.risk_flags[:3])}")
        return " | ".join(lines)

    def format_debate_for_critic(self, outcome: DebateOutcome) -> str:
        """Format specifically for Critic Agent — highlights disagreements."""
        parts = []
        if outcome.dissenting_agents:
            parts.append(f"DISAGREEMENT: {', '.join(outcome.dissenting_agents)} disagree")
        if outcome.agreement_score < 0.5:
            parts.append(f"LOW AGREEMENT ({outcome.agreement_score:.0%}) — extra scrutiny needed")
        if outcome.risk_flags:
            parts.append(f"RED FLAGS: {'; '.join(outcome.risk_flags[:3])}")
        return " | ".join(parts) if parts else "All agents aligned."

    def should_escalate(self, outcome: DebateOutcome) -> bool:
        """Should this go to the Overseer Agent?

        True if: low agreement, many risk flags, or high-stakes disagreement.
        """
        if outcome.agreement_score < 0.3:
            return True
        if len(outcome.risk_flags) >= 3:
            return True
        if len(outcome.dissenting_agents) >= 2:
            return True
        return False


# ─────────────────────────────────────────────────────────────────────────────
# STANDALONE FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def _stances_conflict(s1: str, s2: str) -> bool:
    """Check if two stances are in conflict."""
    conflicts = {
        ("bullish", "bearish"),
        ("bearish", "bullish"),
    }
    return (s1, s2) in conflicts


def corroboration_score(positions: List[Position]) -> Dict[str, Any]:
    """Calculate how much independent corroboration exists.

    Healthy debate: some disagreement but convergent conclusions.
    """
    if not positions:
        return {"score": 0, "unique_perspectives": 0}

    # Count stance distribution
    stances = [p.stance for p in positions]
    stance_counts: Dict[str, int] = {}
    for s in stances:
        stance_counts[s] = stance_counts.get(s, 0) + 1

    # Majority stance
    majority = max(stance_counts, key=lambda k: stance_counts[k])
    majority_count = stance_counts[majority]
    total = len(positions)

    # Score: fraction in agreement, weighted by confidence
    weighted_agreement = sum(
        p.confidence for p in positions if p.stance == majority
    )
    total_confidence = sum(p.confidence for p in positions) or 1

    # Unique perspectives: how many different pieces of evidence cited?
    all_evidence = set()
    for p in positions:
        all_evidence.update(p.evidence)

    # Convergent confidence: boost when independent analyses agree
    convergent = weighted_agreement / total_confidence

    return {
        "score": round(majority_count / total, 2),
        "convergent_confidence": round(convergent, 3),
        "unique_perspectives": len(all_evidence),
        "majority_stance": majority,
        "majority_count": majority_count,
        "total_positions": total,
    }


def diversity_score(positions: List[Position]) -> float:
    """How diverse are the viewpoints?

    0 = everyone says the same thing (suspicious groupthink)
    0.5 = healthy disagreement
    1.0 = total disagreement (concerning)
    """
    if len(positions) < 2:
        return 0.0

    stances = [p.stance for p in positions]
    unique = len(set(stances))
    total = len(stances)

    # Normalized entropy
    from collections import Counter
    counts = Counter(stances)
    probs = [c / total for c in counts.values()]
    entropy = -sum(p * math.log2(p) for p in probs if p > 0)
    max_entropy = math.log2(min(total, 3))  # Max 3 possible stances

    return round(entropy / max_entropy if max_entropy > 0 else 0, 3)


def debate_summary_for_prompt(outcome: DebateOutcome, max_tokens: int = 300) -> str:
    """Token-efficient summary for injection into agent prompts."""
    parts = [
        f"DEBATE: {outcome.consensus_direction}({outcome.consensus_confidence:.0%})",
        f"agree={outcome.agreement_score:.0%}",
    ]
    if outcome.dissenting_agents:
        parts.append(f"dissent=[{','.join(outcome.dissenting_agents)}]")
    if outcome.risk_flags:
        parts.append(f"risks=[{';'.join(outcome.risk_flags[:2])}]")

    result = " | ".join(parts)
    return result[:max_tokens]


__all__ = [
    "Position",
    "Challenge",
    "DebateOutcome",
    "DebateManager",
    "corroboration_score",
    "diversity_score",
    "debate_summary_for_prompt",
]
