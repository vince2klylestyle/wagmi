"""
Interactive Trade-Critic Debate Mechanism.

Implements FREE-MAD (Free-form Multi-Agent Debate) for the Trade-Critic interaction:
- Round 1: Trade Agent proposes thesis (confidence hidden) → Critic provides counter-thesis + objections
- Round 2: Trade Agent rebuts Critic's objections → Resolution via score-based evaluation

Key features:
- Confidence scores are hidden from Critic in Round 1 to prevent anchoring bias
- Critic must provide specific, evidence-based objections (not just "I disagree")
- Trade Agent can defend, concede, or adjust confidence in Round 2
- Final score considers all intermediate outputs (not just final decision)
- Outcome is tracked for calibration of debate mechanism accuracy
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("bot.llm.agents.interactive_debate")


@dataclass
class ThesisProposal:
    """Trade Agent's initial thesis proposal."""
    action: str  # "go", "skip", "flip"
    thesis: str  # Directional prediction with evidence
    evidence: List[str] = field(default_factory=list)  # Key supporting points
    confidence: float = 0.5  # 0-1 scale (hidden from Critic in Round 1)
    entry_adjustment: Optional[str] = None
    setup_type: Optional[str] = None


@dataclass
class CounterThesis:
    """Critic Agent's counter-thesis and objections."""
    verdict: str  # "approve", "challenge"
    counter_thesis: Optional[str] = None  # If challenging, what does Critic think?
    objections: List[Dict[str, Any]] = field(default_factory=list)  # [{"reason": str, "likelihood": float, "impact": str}]
    red_flags: List[str] = field(default_factory=list)  # Specific concerns
    confidence_in_challenge: float = 0.5  # How confident is Critic in its counter-thesis?


@dataclass
class Rebuttal:
    """Trade Agent's rebuttal to Critic's objections."""
    action: str  # Can be same or adjusted from original
    adjusted_confidence: float  # Confidence after considering objections
    rebuttal_points: List[str] = field(default_factory=list)  # Responses to each objection
    concessions: List[str] = field(default_factory=list)  # What Trade Agent concedes to
    maintains_thesis: bool = True  # Does Trade Agent maintain original thesis?


@dataclass
class DebateResolution:
    """Final resolution after 2-round debate."""
    final_action: str  # "go", "skip", "flip"
    final_confidence: float  # 0-1
    debate_winner: str  # "trade", "critic", "consensus"
    trade_score: float  # How well Trade's thesis held up (0-1)
    critic_score: float  # How valid were Critic's objections (0-1)
    key_turning_points: List[str] = field(default_factory=list)  # What changed minds?
    risk_flags: List[str] = field(default_factory=list)  # Unresolved risks
    recommendation: str = "proceed"  # "proceed", "reduce_size", "skip"
    rounds_used: int = 1


class InteractiveDebater:
    """Orchestrates 2-round Trade-Critic debate."""

    def __init__(self):
        self.debate_history: List[DebateResolution] = []

    def round1_extract_proposal(self, trade_agent_output: Dict[str, Any]) -> ThesisProposal:
        """Extract Trade Agent's proposal from its standard output."""
        return ThesisProposal(
            action=trade_agent_output.get("a", trade_agent_output.get("action", "skip")),
            thesis=trade_agent_output.get("thesis", trade_agent_output.get("n", "")),
            evidence=trade_agent_output.get("evidence", []),
            confidence=float(trade_agent_output.get("c", trade_agent_output.get("confidence", 0.5))),
            entry_adjustment=trade_agent_output.get("ea"),
            setup_type=trade_agent_output.get("setup_type"),
        )

    def round1_build_critic_input(
        self,
        proposal: ThesisProposal,
        market_data: Dict[str, Any],
        regime: str,
    ) -> str:
        """Build Critic Agent's Round 1 input.

        Intentionally HIDES Trade Agent's confidence to prevent anchoring bias.
        """
        parts = [
            f"TRADE PROPOSAL: {proposal.action.upper()}",
            f"Thesis: {proposal.thesis}",
            f"Setup type: {proposal.setup_type or 'unspecified'}",
        ]

        if proposal.evidence:
            parts.append(f"Supporting evidence:\n" + "\n".join(f"  - {e}" for e in proposal.evidence[:3]))

        parts.append(f"\nMarket regime: {regime}")
        parts.append("(Confidence hidden to prevent anchoring — evaluate thesis independently)")

        return "\n".join(parts)

    def round1_extract_counter_thesis(self, critic_agent_output: Dict[str, Any]) -> CounterThesis:
        """Extract Critic Agent's Round 1 counter-thesis and objections."""
        objections = critic_agent_output.get("objections", [])

        # Ensure objections have the required fields
        clean_objections = []
        for obj in objections:
            if isinstance(obj, dict):
                clean_objections.append({
                    "reason": obj.get("reason", ""),
                    "likelihood": float(obj.get("likelihood", 0.5)),
                    "impact": obj.get("impact", "thesis_invalid"),
                })

        return CounterThesis(
            verdict=critic_agent_output.get("verdict", "approve"),
            counter_thesis=critic_agent_output.get("counter_thesis"),
            objections=clean_objections,
            red_flags=critic_agent_output.get("red_flags", []),
            confidence_in_challenge=float(critic_agent_output.get("adjusted_confidence", 0.5)),
        )

    def round2_build_trade_input(
        self,
        proposal: ThesisProposal,
        counter_thesis: CounterThesis,
    ) -> str:
        """Build Trade Agent's Round 2 rebuttal input.

        Now Trade Agent sees Critic's specific objections and can defend or concede.
        """
        parts = [
            "ROUND 2: REBUTTAL OPPORTUNITY",
            f"\nYour original thesis: {proposal.thesis}",
            f"Your action: {proposal.action.upper()}",
        ]

        if counter_thesis.verdict == "challenge":
            parts.append(f"\nCritic's counter-thesis: {counter_thesis.counter_thesis}")

        if counter_thesis.objections:
            parts.append("\nCritic's specific objections:")
            for i, obj in enumerate(counter_thesis.objections, 1):
                parts.append(
                    f"  {i}. {obj['reason']} "
                    f"(likelihood={obj['likelihood']:.0%}, impact={obj['impact']})"
                )

        if counter_thesis.red_flags:
            parts.append("\nRed flags:")
            for flag in counter_thesis.red_flags[:3]:
                parts.append(f"  - {flag}")

        parts.append("\n" + "=" * 60)
        parts.append("YOUR DECISION:")
        parts.append("1. Do you maintain your original thesis?")
        parts.append("2. Respond to each objection (defend or concede)")
        parts.append("3. Adjust your confidence if warranted")
        parts.append("4. Final action (same or adjusted)")

        return "\n".join(parts)

    def round2_extract_rebuttal(self, trade_rebuttal_output: Dict[str, Any]) -> Rebuttal:
        """Extract Trade Agent's Round 2 rebuttal from LLM output."""
        return Rebuttal(
            action=trade_rebuttal_output.get("a", trade_rebuttal_output.get("action", "skip")),
            adjusted_confidence=float(trade_rebuttal_output.get("c", trade_rebuttal_output.get("confidence", 0.5))),
            rebuttal_points=trade_rebuttal_output.get("rebuttal_points", []),
            concessions=trade_rebuttal_output.get("concessions", []),
            maintains_thesis=trade_rebuttal_output.get("maintains_thesis", True),
        )

    def score_debate(
        self,
        proposal: ThesisProposal,
        counter_thesis: CounterThesis,
        rebuttal: Rebuttal,
    ) -> DebateResolution:
        """Score the debate using FREE-MAD principles.

        FREE-MAD (Free-form Multi-Agent Debate) scores all intermediate outputs
        rather than just the final position. This prevents flip-flopping and
        incentivizes consistent reasoning.
        """
        trade_score = self._score_trade_side(proposal, rebuttal)
        critic_score = self._score_critic_side(counter_thesis, rebuttal)

        # Determine winner
        if trade_score > critic_score + 0.2:
            winner = "trade"
            final_action = rebuttal.action
            final_confidence = rebuttal.adjusted_confidence
            confidence_boost = 0.05  # Trade maintained ground
        elif critic_score > trade_score + 0.2:
            winner = "critic"
            final_action = "skip" if rebuttal.action != "skip" else "skip"
            final_confidence = max(0.1, rebuttal.adjusted_confidence - 0.15)
            confidence_boost = 0
        else:
            # Consensus
            winner = "consensus"
            final_action = rebuttal.action
            final_confidence = rebuttal.adjusted_confidence * 0.95  # Slight discount for unresolved disagreement
            confidence_boost = 0.02

        # Build recommendation based on debate outcome
        if final_action == "skip":
            recommendation = "skip"
        elif final_confidence < 0.4:
            recommendation = "reduce_size"
        elif len(counter_thesis.red_flags) >= 3:
            recommendation = "reduce_size"
        else:
            recommendation = "proceed"

        # Collect unresolved risk flags
        risk_flags = counter_thesis.red_flags.copy()
        if rebuttal.concessions:
            risk_flags.extend([f"Conceded: {c}" for c in rebuttal.concessions[:2]])

        resolution = DebateResolution(
            final_action=final_action,
            final_confidence=min(1.0, max(0.0, final_confidence + confidence_boost)),
            debate_winner=winner,
            trade_score=round(trade_score, 3),
            critic_score=round(critic_score, 3),
            key_turning_points=self._extract_turning_points(proposal, counter_thesis, rebuttal),
            risk_flags=risk_flags[:5],
            recommendation=recommendation,
            rounds_used=2,
        )

        self.debate_history.append(resolution)
        return resolution

    def _score_trade_side(
        self,
        proposal: ThesisProposal,
        rebuttal: Rebuttal,
    ) -> float:
        """Score how well Trade Agent's thesis held up.

        Criteria:
        - Maintains thesis without concessions (0.7-0.8)
        - Maintains thesis with minor concessions (0.6-0.7)
        - Adjusts thesis but action unchanged (0.5-0.6)
        - Reverses action entirely (0.2-0.3)
        """
        score = 0.5

        # Consistency with original
        if rebuttal.maintains_thesis and not rebuttal.concessions:
            score += 0.25
        elif rebuttal.maintains_thesis:
            score += 0.15  # Maintained but had to concede points
        elif not rebuttal.concessions:
            score += 0.10
        else:
            score += 0.05

        # Action consistency
        if rebuttal.action == proposal.action:
            score += 0.15
        else:
            score -= 0.1

        # Confidence maintenance (didn't panic)
        if rebuttal.adjusted_confidence >= proposal.confidence - 0.05:
            score += 0.1
        elif rebuttal.adjusted_confidence >= proposal.confidence - 0.3:
            score += 0.05
        else:
            score -= 0.05

        # Penalty for concessions (thesis weakened)
        if rebuttal.concessions:
            score -= min(0.25, len(rebuttal.concessions) * 0.15)

        return min(1.0, max(0.0, score))

    def _score_critic_side(
        self,
        counter_thesis: CounterThesis,
        rebuttal: Rebuttal,
    ) -> float:
        """Score how valid Critic's objections were.

        Criteria:
        - Trade Agent conceded (0.7-0.9)
        - Trade Agent acknowledged objections but defended (0.4-0.6)
        - Trade Agent dismissed/ignored objections (0.1-0.3)
        """
        score = 0.3

        # Factor in objection quality (average likelihood)
        if counter_thesis.objections:
            avg_likelihood = sum(
                o.get("likelihood", 0.5) if isinstance(o, dict) else 0.5
                for o in counter_thesis.objections
            ) / len(counter_thesis.objections)
            score += avg_likelihood * 0.2

        # Did Trade Agent concede to any?
        if rebuttal.concessions:
            score += min(0.25, len(rebuttal.concessions) * 0.1)

        # Did Trade Agent reverse?
        if not rebuttal.maintains_thesis or rebuttal.action == "skip":
            score += 0.15

        # How many objections did Critic raise?
        if len(counter_thesis.objections) >= 3:
            score += 0.1
        elif len(counter_thesis.objections) >= 1:
            score += 0.05

        # Penalty: Trade Agent fully defended with no concessions
        if rebuttal.maintains_thesis and not rebuttal.concessions:
            score -= 0.15

        return min(1.0, max(0.0, score))

    def _extract_turning_points(
        self,
        proposal: ThesisProposal,
        counter_thesis: CounterThesis,
        rebuttal: Rebuttal,
    ) -> List[str]:
        """Extract key moments that shifted the debate."""
        turning_points = []

        # If Trade Agent conceded, that's a turning point
        if rebuttal.concessions:
            turning_points.append(f"Trade Agent conceded on: {rebuttal.concessions[0]}")

        # If action changed, that's significant
        if rebuttal.action != proposal.action:
            turning_points.append(f"Action changed from {proposal.action} to {rebuttal.action}")

        # If confidence dropped significantly
        conf_change = rebuttal.adjusted_confidence - proposal.confidence
        if conf_change < -0.2:
            turning_points.append(f"Confidence dropped {abs(conf_change):.0%} after debate")

        # If Critic's strongest objection was acknowledged
        if counter_thesis.objections and rebuttal.rebuttal_points:
            strongest = max(counter_thesis.objections, key=lambda x: x["likelihood"])
            turning_points.append(f"Acknowledged key risk: {strongest['reason']}")

        return turning_points

    def format_resolution_for_decision(self, resolution: DebateResolution) -> str:
        """Format debate resolution for injection into final decision."""
        parts = [
            f"DEBATE: {resolution.final_action.upper()} (conf={resolution.final_confidence:.0%})",
            f"Winner: {resolution.debate_winner} (trade={resolution.trade_score:.2f}, critic={resolution.critic_score:.2f})",
        ]

        if resolution.key_turning_points:
            parts.append(f"Key points: {'; '.join(resolution.key_turning_points[:2])}")

        if resolution.risk_flags:
            parts.append(f"Risks: {'; '.join(resolution.risk_flags[:2])}")

        return " | ".join(parts)

    def should_escalate_to_overseer(self, resolution: DebateResolution) -> bool:
        """Should this debate result go to Overseer Agent for final arbitration?

        True if:
        - Strong disagreement (debate_winner = "consensus" and both scores in 0.35-0.65 range)
        - Multiple unresolved risks
        - Trade Agent reversed decision
        """
        if resolution.debate_winner == "consensus":
            if 0.35 <= resolution.trade_score <= 0.65 and 0.35 <= resolution.critic_score <= 0.65:
                return True

        if len(resolution.risk_flags) >= 4:
            return True

        if resolution.rounds_used >= 2:
            return True

        return False


__all__ = [
    "ThesisProposal",
    "CounterThesis",
    "Rebuttal",
    "DebateResolution",
    "InteractiveDebater",
]
