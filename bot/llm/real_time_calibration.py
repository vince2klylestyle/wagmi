"""
TIER 3.5: Real-time Agent Calibration

Tracks agent accuracy in real-time and adjusts confidence/trust.

Why it matters:
- If Trade Agent says 70% confidence on trend + high confidence setups
- But they win only 60% of the time
- Agent is OVERCONFIDENT by 10%
- Adjust: multiply future Trade Agent confidence by 0.85

Per-agent, per-regime, per-setup calibration.

Expected impact: +0.2-0.3% daily by preventing overconfident decisions
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from collections import defaultdict
import time

logger = logging.getLogger("bot.llm.real_time_calibration")


@dataclass
class CalibrationBucket:
    """Calibration data for one (agent, regime, setup) combination."""
    agent_name: str
    regime: str
    setup_type: str

    predictions: int = 0  # Number of predictions
    hits: int = 0  # Number of correct predictions
    accuracy: float = 0.0  # hits / predictions
    predicted_win_rate: float = 0.0  # Agent's avg predicted confidence
    actual_win_rate: float = 0.0  # Actual outcomes

    calibration_factor: float = 1.0  # Multiply agent confidence by this
    confidence_in_calibration: float = 0.0  # How confident are we? (0-1)

    last_updated: float = field(default_factory=time.time)


class RealTimeCalibrator:
    """
    Tracks agent calibration across dimensions:
    - Per agent (Regime, Trade, Risk, Critic)
    - Per regime (trend, range, panic)
    - Per setup type
    """

    def __init__(self):
        """Initialize calibrator."""
        self.buckets: Dict[str, CalibrationBucket] = {}

    def record_prediction(
        self,
        agent_name: str,
        regime: str,
        setup_type: str,
        predicted_confidence: float,  # Agent's predicted confidence (0-1)
        actual_outcome: bool,  # True = win, False = loss
    ) -> None:
        """
        Record an agent's prediction and actual outcome.

        This builds the calibration curve: predicted vs actual.
        """
        bucket_key = f"{agent_name}_{regime}_{setup_type}"

        if bucket_key not in self.buckets:
            self.buckets[bucket_key] = CalibrationBucket(
                agent_name=agent_name,
                regime=regime,
                setup_type=setup_type,
            )

        bucket = self.buckets[bucket_key]
        bucket.predictions += 1
        bucket.predicted_win_rate += predicted_confidence

        if actual_outcome:
            bucket.hits += 1
            bucket.actual_win_rate += 1.0
        else:
            bucket.actual_win_rate += 0.0

        # Compute averages
        if bucket.predictions > 0:
            bucket.accuracy = bucket.hits / bucket.predictions
            bucket.predicted_win_rate = bucket.predicted_win_rate / bucket.predictions
            bucket.actual_win_rate = bucket.actual_win_rate / bucket.predictions

            # Compute calibration factor
            if bucket.predicted_win_rate > 0.5:
                # How much was prediction vs reality?
                bucket.calibration_factor = bucket.actual_win_rate / bucket.predicted_win_rate
                bucket.calibration_factor = min(2.0, max(0.5, bucket.calibration_factor))
            else:
                bucket.calibration_factor = 1.0

            # Confidence in calibration: more predictions = higher confidence
            bucket.confidence_in_calibration = min(1.0, bucket.predictions / 20.0)

        bucket.last_updated = time.time()

    def get_calibration_factor(
        self,
        agent_name: str,
        regime: str,
        setup_type: str,
    ) -> float:
        """
        Get calibration factor for an agent.

        Returns multiplier to apply to agent's confidence.
        Default 1.0 (no adjustment).
        """
        bucket_key = f"{agent_name}_{regime}_{setup_type}"

        if bucket_key not in self.buckets:
            return 1.0

        bucket = self.buckets[bucket_key]

        # Only use calibration if we have sufficient data
        if bucket.predictions < 5:
            return 1.0

        return bucket.calibration_factor

    def get_agent_report(self, agent_name: str) -> Dict:
        """Get calibration report for one agent."""
        agent_buckets = [b for b in self.buckets.values() if b.agent_name == agent_name]

        if not agent_buckets:
            return {"status": "no_data"}

        # Overall stats
        total_predictions = sum(b.predictions for b in agent_buckets)
        total_hits = sum(b.hits for b in agent_buckets)
        overall_accuracy = total_hits / total_predictions if total_predictions > 0 else 0

        # Breakdown by regime
        by_regime = defaultdict(lambda: {"predictions": 0, "hits": 0})
        for b in agent_buckets:
            by_regime[b.regime]["predictions"] += b.predictions
            by_regime[b.regime]["hits"] += b.hits

        regime_accuracy = {
            regime: hits / data["predictions"] if data["predictions"] > 0 else 0
            for regime, data in by_regime.items()
        }

        # Overconfident/underconfident analysis
        overconfident_buckets = [b for b in agent_buckets if b.calibration_factor < 0.9]
        underconfident_buckets = [b for b in agent_buckets if b.calibration_factor > 1.1]

        return {
            "agent": agent_name,
            "total_predictions": total_predictions,
            "overall_accuracy": f"{overall_accuracy:.0%}",
            "accuracy_by_regime": {r: f"{a:.0%}" for r, a in regime_accuracy.items()},
            "overconfident_patterns": len(overconfident_buckets),
            "underconfident_patterns": len(underconfident_buckets),
            "patterns_needing_calibration": len(overconfident_buckets) + len(underconfident_buckets),
        }

    def get_calibration_recommendations(self) -> List[Dict]:
        """
        Get recommendations for agent prompts based on calibration data.

        Returns list of recommendations to improve agent accuracy.
        """
        recommendations = []

        for bucket in self.buckets.values():
            if bucket.predictions < 5:
                continue  # Need more data

            if bucket.calibration_factor < 0.7:
                recommendations.append({
                    "type": "overconfident",
                    "agent": bucket.agent_name,
                    "regime": bucket.regime,
                    "setup": bucket.setup_type,
                    "issue": f"Agent predicts {bucket.predicted_win_rate:.0%} but actual is {bucket.actual_win_rate:.0%}",
                    "recommendation": "Reduce confidence or add more skeptical reasoning to prompt",
                    "severity": "high",
                })
            elif bucket.calibration_factor > 1.3:
                recommendations.append({
                    "type": "underconfident",
                    "agent": bucket.agent_name,
                    "regime": bucket.regime,
                    "setup": bucket.setup_type,
                    "issue": f"Agent predicts {bucket.predicted_win_rate:.0%} but actual is {bucket.actual_win_rate:.0%}",
                    "recommendation": "Increase confidence or provide more assertive decision-making to prompt",
                    "severity": "medium",
                })

        # Sort by severity
        recommendations.sort(key=lambda r: {"high": 0, "medium": 1, "low": 2}.get(r["severity"], 3))

        return recommendations

    def get_full_report(self) -> Dict:
        """Get comprehensive calibration report."""
        by_agent = defaultdict(list)
        for bucket in self.buckets.values():
            by_agent[bucket.agent_name].append(bucket)

        report = {}
        for agent, buckets in by_agent.items():
            report[agent] = {
                "patterns_tracked": len(buckets),
                "total_predictions": sum(b.predictions for b in buckets),
                "overall_accuracy": f"{sum(b.hits for b in buckets) / sum(b.predictions for b in buckets):.0%}" if sum(b.predictions for b in buckets) > 0 else "0%",
            }

        recommendations = self.get_calibration_recommendations()

        return {
            "agents": report,
            "recommendations": recommendations,
            "total_patterns_tracked": len(self.buckets),
        }


# Global calibrator
_global_calibrator: Optional[RealTimeCalibrator] = None


def get_real_time_calibrator() -> RealTimeCalibrator:
    """Get or create global calibrator."""
    global _global_calibrator
    if _global_calibrator is None:
        _global_calibrator = RealTimeCalibrator()
    return _global_calibrator
