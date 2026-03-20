"""
TIER 5.3: Bot Perception Analyzer & Decision Correlator

Extracts insights from perception data and correlates perception → decisions → outcomes.

Why: Understanding what perception leads to what decisions is the key to:
- Identifying when bot is confused/uncertain
- Finding perception blind spots
- Detecting overfitting (high confidence despite poor results)
- Finding perception-decision mismatches
- Optimizing which perception signals matter most
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from collections import defaultdict
import statistics

from llm.bot_perception_aggregator import get_bot_perception_aggregator

logger = logging.getLogger("bot.llm.bot_perception_analyzer")


@dataclass
class PerceptionPattern:
    """Recurring pattern in bot's perception."""
    pattern_id: str
    regime: str
    agent_confidence_min: float
    agent_confidence_max: float
    pipeline_latency_max: float  # ms

    # Occurrence
    occurrences: int = 0

    # Decision outcomes
    decisions_made: int = 0
    positive_decisions: int = 0
    negative_decisions: int = 0
    accuracy: float = 0.0

    # Recommendation
    is_reliable: bool = False
    reliability_score: float = 0.0


@dataclass
class PerceptionBias:
    """Detected bias in bot's perception."""
    bias_type: str  # "overconfident", "underconfident", "regime_bias", "agent_bias"
    severity: str  # "low", "medium", "high"
    description: str

    # Evidence
    evidence_count: int = 0
    examples: List[Dict[str, Any]] = None


@dataclass
class AgentContribution:
    """How much each agent contributes to decisions."""
    agent_role: str
    decision_contribution: float  # 0-1 (how much this agent influenced decision)
    accuracy: float  # accuracy when this agent was high confidence
    reliability: float  # consistency of influence
    bias: str  # "optimistic", "pessimistic", "balanced"


@dataclass
class PerceptionDecisionCorrelation:
    """Correlation between perception state and decision outcomes."""
    perception_state: str  # regime, confidence level, agent agreement, etc
    num_decisions: int
    num_wins: int
    num_losses: int
    win_rate: float
    avg_pnl: float

    # Confidence in correlation
    confidence: float  # How sure we are about this correlation?
    sample_size_sufficient: bool


class BotPerceptionAnalyzer:
    """
    Analyzes bot's perception patterns and their relationship to decisions.
    """

    def __init__(self):
        self.aggregator = get_bot_perception_aggregator()

    def identify_perception_patterns(self) -> List[PerceptionPattern]:
        """Identify recurring perception patterns."""
        patterns = {}

        # Analyze all stored percepts
        for percept in self.aggregator.percepts.values():
            if not percept.llm_latest_decision:
                continue

            # Create pattern key
            regime = percept.llm_latest_decision.regime
            agent_confs = [b.confidence for b in percept.agent_brains.values()]
            conf_min = min(agent_confs) if agent_confs else 0
            conf_max = max(agent_confs) if agent_confs else 100

            latency = percept.pipeline_health.avg_decision_latency_ms if percept.pipeline_health else 0

            pattern_key = f"{regime}_{int(conf_min/10)*10}_{int(conf_max/10)*10}_{int(latency/100)*100}"

            if pattern_key not in patterns:
                patterns[pattern_key] = PerceptionPattern(
                    pattern_id=pattern_key,
                    regime=regime,
                    agent_confidence_min=conf_min,
                    agent_confidence_max=conf_max,
                    pipeline_latency_max=latency,
                )

            pattern = patterns[pattern_key]
            pattern.occurrences += 1
            pattern.decisions_made += 1

            # Track if decision was positive or negative
            if percept.llm_latest_decision.action in ["go", "proceed"]:
                pattern.positive_decisions += 1
            else:
                pattern.negative_decisions += 1

        # Calculate accuracy and reliability
        for pattern in patterns.values():
            if pattern.decisions_made > 0:
                pattern.accuracy = pattern.positive_decisions / pattern.decisions_made
                pattern.reliability_score = min(1.0, pattern.occurrences / 10.0)  # More occurrences = more reliable
                pattern.is_reliable = pattern.occurrences >= 5 and pattern.accuracy > 0.55

        # Sort by reliability
        sorted_patterns = sorted(
            patterns.values(),
            key=lambda p: (p.is_reliable, p.reliability_score),
            reverse=True
        )

        return sorted_patterns

    def detect_perception_biases(self) -> List[PerceptionBias]:
        """Detect systematic biases in bot's perception."""
        biases = []

        # Get latest percepts
        recent_percepts = sorted(
            self.aggregator.percepts.values(),
            key=lambda p: p.timestamp,
            reverse=True
        )[:100]

        if not recent_percepts:
            return []

        # Bias 1: Overconfidence (high confidence but low accuracy)
        high_conf_decisions = [p for p in recent_percepts
                               if p.llm_latest_decision and p.llm_latest_decision.confidence > 75]

        if high_conf_decisions:
            wins = sum(1 for p in high_conf_decisions if p.perception_vs_reality_gap < 0.1)
            win_rate = wins / len(high_conf_decisions)

            if win_rate < 0.4:
                biases.append(PerceptionBias(
                    bias_type="overconfident",
                    severity="high" if win_rate < 0.3 else "medium",
                    description=f"High confidence (>75%) but only {win_rate:.0%} accuracy",
                    evidence_count=len(high_conf_decisions),
                ))

        # Bias 2: Underconfidence (low confidence but would have been right)
        low_conf_decisions = [p for p in recent_percepts
                              if p.llm_latest_decision and p.llm_latest_decision.confidence < 45]

        if low_conf_decisions:
            could_have_won = sum(1 for p in low_conf_decisions if p.perception_vs_reality_gap < 0.05)
            missed_rate = could_have_won / len(low_conf_decisions)

            if missed_rate > 0.5:
                biases.append(PerceptionBias(
                    bias_type="underconfident",
                    severity="medium",
                    description=f"Low confidence (<45%) but {missed_rate:.0%} would have been correct",
                    evidence_count=len(low_conf_decisions),
                ))

        # Bias 3: Regime bias (performs differently in different regimes)
        regime_performance = defaultdict(lambda: {"wins": 0, "total": 0})

        for p in recent_percepts:
            if p.llm_latest_decision:
                regime = p.llm_latest_decision.regime
                regime_performance[regime]["total"] += 1
                if p.perception_vs_reality_gap < 0.1:
                    regime_performance[regime]["wins"] += 1

        regime_win_rates = {
            regime: stats["wins"] / stats["total"]
            for regime, stats in regime_performance.items()
            if stats["total"] > 0
        }

        if regime_win_rates:
            max_wr = max(regime_win_rates.values())
            min_wr = min(regime_win_rates.values())

            if max_wr - min_wr > 0.3:
                biases.append(PerceptionBias(
                    bias_type="regime_bias",
                    severity="high",
                    description=f"Significant regime variance: {min_wr:.0%} to {max_wr:.0%}",
                    evidence_count=sum(s["total"] for s in regime_performance.values()),
                ))

        # Bias 4: Agent bias (some agents consistently wrong)
        agent_accuracy = {}

        for p in recent_percepts:
            for agent_role, brain in p.agent_brains.items():
                if agent_role not in agent_accuracy:
                    agent_accuracy[agent_role] = {"correct": 0, "total": 0}

                agent_accuracy[agent_role]["total"] += 1
                if brain.accuracy > 0.5:
                    agent_accuracy[agent_role]["correct"] += 1

        for agent_role, stats in agent_accuracy.items():
            if stats["total"] >= 5:
                accuracy = stats["correct"] / stats["total"]
                if accuracy < 0.3:
                    biases.append(PerceptionBias(
                        bias_type="agent_bias",
                        severity="high",
                        description=f"Agent {agent_role} has {accuracy:.0%} accuracy",
                        evidence_count=stats["total"],
                    ))

        return biases

    def analyze_agent_contributions(self) -> List[AgentContribution]:
        """Analyze how much each agent contributes to final decision."""
        agent_contributions = {}

        for percept in self.aggregator.percepts.values():
            if not percept.agent_brains:
                continue

            for agent_role, brain in percept.agent_brains.items():
                if agent_role not in agent_contributions:
                    agent_contributions[agent_role] = {
                        "decisions": 0,
                        "accuracy_sum": 0.0,
                        "confidence_sum": 0.0,
                        "bias": "neutral",
                        "correct": 0,
                    }

                contrib = agent_contributions[agent_role]
                contrib["decisions"] += 1
                contrib["accuracy_sum"] += brain.accuracy
                contrib["confidence_sum"] += brain.confidence

                if brain.accuracy > 0.55:
                    contrib["correct"] += 1

                # Detect bias
                if brain.confidence > 60 and brain.accuracy > 0.6:
                    contrib["bias"] = "optimistic"
                elif brain.confidence < 40 and brain.accuracy < 0.4:
                    contrib["bias"] = "pessimistic"

        # Create contribution objects
        contributions = []
        for agent_role, stats in agent_contributions.items():
            if stats["decisions"] > 0:
                accuracy = stats["accuracy_sum"] / stats["decisions"]
                contribution = AgentContribution(
                    agent_role=agent_role,
                    decision_contribution=min(1.0, stats["decisions"] / 100.0),
                    accuracy=accuracy,
                    reliability=stats["correct"] / stats["decisions"],
                    bias=stats["bias"],
                )
                contributions.append(contribution)

        # Sort by contribution
        contributions.sort(key=lambda c: c.decision_contribution, reverse=True)
        return contributions

    def correlate_perception_to_outcomes(self) -> List[PerceptionDecisionCorrelation]:
        """
        Correlate perception states to decision outcomes.

        Answers: "When bot perceives X, does it usually win or lose?"
        """
        correlations = []

        # Perception states
        perception_states = {
            "high_confidence": lambda p: p.llm_latest_decision and p.llm_latest_decision.confidence > 70,
            "medium_confidence": lambda p: p.llm_latest_decision and 40 <= p.llm_latest_decision.confidence <= 70,
            "low_confidence": lambda p: p.llm_latest_decision and p.llm_latest_decision.confidence < 40,
            "high_agent_agreement": lambda p: p.perception_consistency_score > 0.7,
            "low_agent_agreement": lambda p: p.perception_consistency_score < 0.4,
            "healthy_pipeline": lambda p: p.pipeline_health and p.pipeline_health.all_agents_healthy,
            "unhealthy_pipeline": lambda p: p.pipeline_health and not p.pipeline_health.all_agents_healthy,
        }

        for state_name, state_filter in perception_states.items():
            percepts_in_state = [p for p in self.aggregator.percepts.values() if state_filter(p)]

            if not percepts_in_state:
                continue

            wins = sum(1 for p in percepts_in_state if p.perception_vs_reality_gap < 0.1)
            losses = len(percepts_in_state) - wins
            win_rate = wins / len(percepts_in_state)

            # Calculate average PnL (proxy)
            avg_pnl = -1.0 if win_rate < 0.4 else 1.0 if win_rate > 0.6 else 0.0

            correlation = PerceptionDecisionCorrelation(
                perception_state=state_name,
                num_decisions=len(percepts_in_state),
                num_wins=wins,
                num_losses=losses,
                win_rate=win_rate,
                avg_pnl=avg_pnl,
                confidence=min(1.0, len(percepts_in_state) / 50.0),  # More samples = more confident
                sample_size_sufficient=len(percepts_in_state) >= 10,
            )

            correlations.append(correlation)

        # Sort by win rate
        correlations.sort(key=lambda c: c.win_rate, reverse=True)
        return correlations

    def find_perception_sweet_spots(self) -> List[Dict[str, Any]]:
        """Find combinations of perception that lead to highest win rate."""
        sweet_spots = []

        # Group by multiple factors
        grouping = defaultdict(lambda: {"decisions": 0, "wins": 0})

        for percept in self.aggregator.percepts.values():
            if not percept.llm_latest_decision or not percept.agent_brains:
                continue

            # Create composite key
            regime = percept.llm_latest_decision.regime
            conf = int(percept.llm_latest_decision.confidence / 20) * 20  # Group by 20s
            agreement = "high" if percept.perception_consistency_score > 0.7 else "low"

            key = f"{regime}_{conf}conf_{agreement}_agreement"

            grouping[key]["decisions"] += 1
            if percept.perception_vs_reality_gap < 0.1:
                grouping[key]["wins"] += 1

        # Find sweet spots
        for key, stats in grouping.items():
            if stats["decisions"] >= 5:  # Minimum samples
                win_rate = stats["wins"] / stats["decisions"]

                if win_rate > 0.65:
                    sweet_spots.append({
                        "perception_combo": key,
                        "num_decisions": stats["decisions"],
                        "win_rate": win_rate,
                        "reliability": "high" if stats["decisions"] >= 10 else "medium",
                    })

        # Sort by win rate
        sweet_spots.sort(key=lambda s: s["win_rate"], reverse=True)
        return sweet_spots

    def get_perception_health_score(self) -> Dict[str, Any]:
        """Get overall health score of bot's perception."""
        recent_percepts = sorted(
            self.aggregator.percepts.values(),
            key=lambda p: p.timestamp,
            reverse=True
        )[:50]

        if not recent_percepts:
            return {"status": "no_data"}

        # Calculate components
        avg_quality = sum(p.perception_quality_score for p in recent_percepts) / len(recent_percepts)
        avg_consistency = sum(p.perception_consistency_score for p in recent_percepts) / len(recent_percepts)
        avg_gap = sum(p.perception_vs_reality_gap for p in recent_percepts) / len(recent_percepts)

        # Calculate pipeline health
        pipeline_healthy = sum(1 for p in recent_percepts
                               if p.pipeline_health and p.pipeline_health.all_agents_healthy)
        pipeline_health_pct = pipeline_healthy / len(recent_percepts)

        # Overall score
        overall_score = (avg_quality * 0.3 + avg_consistency * 0.3 +
                        (1 - avg_gap) * 0.2 + pipeline_health_pct * 0.2)

        return {
            "overall_health": overall_score,
            "data_quality": avg_quality,
            "agent_consistency": avg_consistency,
            "perception_gap": avg_gap,
            "pipeline_health": pipeline_health_pct,
            "samples": len(recent_percepts),
            "recommendation": (
                "Excellent - high quality perception" if overall_score > 0.8
                else "Good - perception is reliable" if overall_score > 0.6
                else "Fair - perception needs improvement" if overall_score > 0.4
                else "Poor - significant perception issues"
            ),
        }


# Global analyzer
_global_analyzer: Optional[BotPerceptionAnalyzer] = None


def get_bot_perception_analyzer() -> BotPerceptionAnalyzer:
    """Get or create global analyzer."""
    global _global_analyzer
    if _global_analyzer is None:
        _global_analyzer = BotPerceptionAnalyzer()
    return _global_analyzer
