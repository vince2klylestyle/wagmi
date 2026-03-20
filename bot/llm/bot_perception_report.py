"""
TIER 5.4: Bot Perception Report Generator

Generates comprehensive reports on what the bot perceives, thinks, and decides.

Reports show:
1. What does the bot see? (API perception data)
2. How confident is the bot? (Agent confidence analysis)
3. How aligned are agents? (Consensus analysis)
4. Does perception match reality? (Bias detection)
5. What decisions follow perception? (Correlation analysis)
6. Is the perception system healthy? (Health score)
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import json
import os

from bot_perception_aggregator import get_bot_perception_aggregator
from bot_perception_analyzer import get_bot_perception_analyzer

logger = logging.getLogger("bot.llm.bot_perception_report")


class BotPerceptionReportGenerator:
    """
    Generates comprehensive perception reports.
    """

    def __init__(self, report_dir: str = "data/llm/reports"):
        self.aggregator = get_bot_perception_aggregator()
        self.analyzer = get_bot_perception_analyzer()
        self.report_dir = report_dir
        os.makedirs(report_dir, exist_ok=True)

    def generate_perception_snapshot(self) -> Dict[str, Any]:
        """Generate current perception state snapshot."""
        summary = self.aggregator.get_perception_summary()

        return {
            "report_type": "PERCEPTION_SNAPSHOT",
            "timestamp": datetime.now().isoformat(),
            "current_state": summary,
            "drift_analysis": self.aggregator.analyze_perception_drift(window_minutes=60),
            "vs_mechanical": self.aggregator.compare_perception_vs_mechanical(),
        }

    def generate_pattern_report(self) -> Dict[str, Any]:
        """Report on recurring perception patterns."""
        patterns = self.analyzer.identify_perception_patterns()

        pattern_list = []
        for pattern in patterns[:10]:  # Top 10
            pattern_list.append({
                "pattern_id": pattern.pattern_id,
                "regime": pattern.regime,
                "agent_confidence": f"{pattern.agent_confidence_min:.0f}-{pattern.agent_confidence_max:.0f}%",
                "occurrences": pattern.occurrences,
                "decisions": pattern.decisions_made,
                "accuracy": f"{pattern.accuracy:.1%}",
                "reliability": "high" if pattern.is_reliable else "low",
                "recommendation": "use" if pattern.is_reliable else "avoid",
            })

        return {
            "report_type": "PERCEPTION_PATTERNS",
            "timestamp": datetime.now().isoformat(),
            "total_patterns": len(patterns),
            "reliable_patterns": sum(1 for p in patterns if p.is_reliable),
            "patterns": pattern_list,
            "key_insight": (
                f"Found {sum(1 for p in patterns if p.is_reliable)} reliable perception patterns. "
                f"Use these for confident decision-making."
            ),
        }

    def generate_bias_report(self) -> Dict[str, Any]:
        """Report on detected perception biases."""
        biases = self.analyzer.detect_perception_biases()

        bias_list = []
        for bias in biases:
            bias_list.append({
                "type": bias.bias_type,
                "severity": bias.severity,
                "description": bias.description,
                "evidence": bias.evidence_count,
            })

        # Recommendations
        recommendations = []
        for bias in biases:
            if bias.bias_type == "overconfident":
                recommendations.append("Lower confidence thresholds or add validation steps")
            elif bias.bias_type == "underconfident":
                recommendations.append("Increase confidence in successful scenarios")
            elif bias.bias_type == "regime_bias":
                recommendations.append("Optimize perception for weaker-performing regimes")
            elif bias.bias_type == "agent_bias":
                recommendations.append("Review or retrain underperforming agents")

        return {
            "report_type": "PERCEPTION_BIASES",
            "timestamp": datetime.now().isoformat(),
            "total_biases_detected": len(biases),
            "critical_biases": sum(1 for b in biases if b.severity == "high"),
            "biases": bias_list,
            "recommendations": recommendations,
            "action_needed": len(biases) > 0,
        }

    def generate_agent_report(self) -> Dict[str, Any]:
        """Report on individual agent contributions."""
        contributions = self.analyzer.analyze_agent_contributions()

        agent_list = []
        for contrib in contributions:
            agent_list.append({
                "agent": contrib.agent_role,
                "contribution": f"{contrib.decision_contribution:.1%}",
                "accuracy": f"{contrib.accuracy:.1%}",
                "reliability": f"{contrib.reliability:.1%}",
                "bias": contrib.bias,
                "status": "high_value" if contrib.accuracy > 0.6 else "needs_review" if contrib.accuracy < 0.4 else "normal",
            })

        return {
            "report_type": "AGENT_CONTRIBUTIONS",
            "timestamp": datetime.now().isoformat(),
            "agents": agent_list,
            "top_agent": agent_list[0]["agent"] if agent_list else "unknown",
            "top_agent_accuracy": agent_list[0]["accuracy"] if agent_list else "N/A",
            "team_average_accuracy": (
                f"{sum(c.accuracy for c in contributions) / len(contributions):.1%}"
                if contributions else "N/A"
            ),
        }

    def generate_correlation_report(self) -> Dict[str, Any]:
        """Report on perception → decision correlations."""
        correlations = self.analyzer.correlate_perception_to_outcomes()

        correlation_list = []
        for corr in correlations:
            correlation_list.append({
                "perception_state": corr.perception_state,
                "num_decisions": corr.num_decisions,
                "win_rate": f"{corr.win_rate:.1%}",
                "wins": corr.num_wins,
                "losses": corr.num_losses,
                "confidence": f"{corr.confidence:.0%}",
                "sample_sufficient": corr.sample_size_sufficient,
                "recommendation": (
                    "strong_buy" if corr.win_rate > 0.65 and corr.sample_size_sufficient
                    else "moderate_buy" if corr.win_rate > 0.55 and corr.sample_size_sufficient
                    else "neutral"
                ),
            })

        return {
            "report_type": "PERCEPTION_CORRELATIONS",
            "timestamp": datetime.now().isoformat(),
            "total_states": len(correlation_list),
            "correlations": correlation_list,
            "best_state": correlation_list[0]["perception_state"] if correlation_list else "unknown",
            "best_win_rate": correlation_list[0]["win_rate"] if correlation_list else "N/A",
            "insight": "High-confidence + high-agreement decisions show strongest win rates",
        }

    def generate_sweet_spots_report(self) -> Dict[str, Any]:
        """Report on best perception combinations."""
        sweet_spots = self.analyzer.find_perception_sweet_spots()

        spot_list = []
        for spot in sweet_spots[:10]:
            spot_list.append({
                "condition": spot["perception_combo"],
                "win_rate": f"{spot['win_rate']:.1%}",
                "decisions": spot["num_decisions"],
                "reliability": spot["reliability"],
            })

        return {
            "report_type": "PERCEPTION_SWEET_SPOTS",
            "timestamp": datetime.now().isoformat(),
            "total_sweet_spots": len(sweet_spots),
            "spots": spot_list,
            "recommendation": (
                f"Execute trades when bot perceives these combinations. "
                f"Top condition has {sweet_spots[0]['win_rate']:.0%} win rate."
                if sweet_spots else "No reliable sweet spots identified yet."
            ),
        }

    def generate_health_report(self) -> Dict[str, Any]:
        """Report on overall perception system health."""
        health = self.analyzer.get_perception_health_score()

        # Get drift analysis
        drift = self.aggregator.analyze_perception_drift(window_minutes=60)

        # Get latest perception
        latest = self.aggregator.get_latest_percept()

        return {
            "report_type": "PERCEPTION_HEALTH",
            "timestamp": datetime.now().isoformat(),
            "overall_health": f"{health['overall_health']:.0%}",
            "components": {
                "data_quality": f"{health.get('data_quality', 0):.0%}",
                "agent_consistency": f"{health.get('agent_consistency', 0):.0%}",
                "perception_gap": f"{health.get('perception_gap', 0):.0%}",
                "pipeline_health": f"{health.get('pipeline_health', 0):.0%}",
            },
            "stability": {
                "regime_stability": f"{drift.get('regime_stability', 0):.0%}",
                "confidence_drift": f"{drift.get('confidence_drift', 0):.0f}%",
                "agent_agreement": f"{drift.get('avg_agent_agreement', 0):.0%}",
            },
            "recommendation": health.get("recommendation", "unknown"),
            "samples": health.get("samples", 0),
            "status": "healthy" if health.get("overall_health", 0) > 0.6 else "needs_attention",
        }

    def generate_comprehensive_report(self) -> Dict[str, Any]:
        """Generate complete perception analysis."""
        return {
            "report_type": "COMPREHENSIVE_PERCEPTION_ANALYSIS",
            "timestamp": datetime.now().isoformat(),
            "snapshot": self.generate_perception_snapshot(),
            "patterns": self.generate_pattern_report(),
            "biases": self.generate_bias_report(),
            "agents": self.generate_agent_report(),
            "correlations": self.generate_correlation_report(),
            "sweet_spots": self.generate_sweet_spots_report(),
            "health": self.generate_health_report(),
            "executive_summary": self._generate_executive_summary(),
        }

    def save_report(self, report: Dict, filename: str = None) -> str:
        """Save report to file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.report_dir}/perception_{timestamp}.json"

        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "w") as f:
                json.dump(report, f, indent=2)
            logger.info(f"Perception report saved to {filename}")
            return filename
        except Exception as e:
            logger.error(f"Failed to save report: {e}")
            return ""

    def print_summary(self, report: Dict = None) -> str:
        """Print human-readable report summary."""
        if report is None:
            report = self.generate_comprehensive_report()

        output = []
        output.append("\n" + "=" * 80)
        output.append("BOT PERCEPTION ANALYSIS REPORT")
        output.append("=" * 80)

        # Health
        health = report["health"]
        output.append(f"\n🏥 PERCEPTION SYSTEM HEALTH: {health['overall_health']}")
        output.append(f"   Status: {health['status']}")
        output.append(f"   Recommendation: {health['recommendation']}")

        # Current state
        snapshot = report["snapshot"]
        if "current_state" in snapshot and snapshot["current_state"]:
            state = snapshot["current_state"]
            output.append(f"\n📊 CURRENT PERCEPTION STATE")
            output.append(f"   Equity: ${state.get('system', {}).get('equity', 0):.2f}")
            output.append(f"   Regime: {state.get('llm', {}).get('regime', 'unknown')}")
            output.append(f"   LLM Confidence: {state.get('llm', {}).get('confidence', 0):.0f}%")
            output.append(f"   Positions: {state.get('system', {}).get('positions', 0)}")

        # Patterns
        patterns = report["patterns"]
        output.append(f"\n🔄 PERCEPTION PATTERNS")
        output.append(f"   Total discovered: {patterns['total_patterns']}")
        output.append(f"   Reliable patterns: {patterns['reliable_patterns']}")
        if patterns["patterns"]:
            top_pattern = patterns["patterns"][0]
            output.append(f"   Best pattern: {top_pattern['pattern_id']}")
            output.append(f"   Accuracy: {top_pattern['accuracy']}")

        # Biases
        biases = report["biases"]
        if biases["total_biases_detected"] > 0:
            output.append(f"\n⚠️  DETECTED BIASES: {biases['total_biases_detected']}")
            output.append(f"   Critical: {biases['critical_biases']}")
            for bias in biases["biases"][:3]:
                output.append(f"   • {bias['type']}: {bias['description']}")

        # Sweet spots
        spots = report["sweet_spots"]
        if spots["total_sweet_spots"] > 0:
            output.append(f"\n✨ PERCEPTION SWEET SPOTS: {spots['total_sweet_spots']}")
            if spots["spots"]:
                best = spots["spots"][0]
                output.append(f"   Best condition: {best['condition']}")
                output.append(f"   Win rate: {best['win_rate']}")

        # Agents
        agents = report["agents"]
        output.append(f"\n👥 AGENT PERFORMANCE")
        if agents["agents"]:
            top_agent = agents["agents"][0]
            output.append(f"   Top agent: {top_agent['agent']}")
            output.append(f"   Accuracy: {top_agent['accuracy']}")
            output.append(f"   Team average: {agents['team_average_accuracy']}")

        output.append("\n" + "=" * 80)

        return "\n".join(output)

    def _generate_executive_summary(self) -> Dict[str, Any]:
        """Generate executive summary of perception state."""
        health = self.analyzer.get_perception_health_score()
        biases = self.analyzer.detect_perception_biases()
        patterns = self.analyzer.identify_perception_patterns()

        return {
            "perception_status": (
                "Excellent" if health.get("overall_health", 0) > 0.8
                else "Good" if health.get("overall_health", 0) > 0.6
                else "Fair" if health.get("overall_health", 0) > 0.4
                else "Poor"
            ),
            "key_strengths": [
                f"Consistent agent agreement ({health.get('agent_consistency', 0):.0%})",
                f"{sum(1 for p in patterns if p.is_reliable)} reliable perception patterns found",
            ],
            "key_weaknesses": [
                bias.description for bias in biases
            ] if biases else ["No significant weaknesses detected"],
            "immediate_actions": [
                "Lower confidence thresholds" if any(b.bias_type == "overconfident" for b in biases) else None,
                "Review weak-performing regimes" if any(b.bias_type == "regime_bias" for b in biases) else None,
            ],
            "overall_recommendation": health.get("recommendation", "unknown"),
        }


# Global reporter
_global_reporter: Optional[BotPerceptionReportGenerator] = None


def get_bot_perception_report_generator() -> BotPerceptionReportGenerator:
    """Get or create global reporter."""
    global _global_reporter
    if _global_reporter is None:
        _global_reporter = BotPerceptionReportGenerator()
    return _global_reporter
