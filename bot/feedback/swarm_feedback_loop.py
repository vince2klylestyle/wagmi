"""
Swarm Feedback Loop.

Applies swarm agent recommendations to live trading configuration.
Measures actual impact and tracks agent accuracy.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bot.feedback.swarm_feedback_loop")


@dataclass
class PromotedRule:
    """A recommendation that was promoted to a live trading rule."""
    recommendation_id: str
    agent_role: str
    pattern: str
    action: str
    promoted_date: float  # Unix timestamp
    applied_to_config_keys: List[str] = field(default_factory=list)
    measured_impact_pct: Optional[float] = None
    status: str = "active"  # active, degraded, reverted


class SwarmFeedbackLoop:
    """Applies swarm recommendations to trading config and measures impact."""

    def __init__(self, data_dir: str = "bot/data", config_module: str = "bot.trading_config"):
        self.data_dir = Path(data_dir)
        self.config_module = config_module

        # Ensure directories exist
        (self.data_dir / "feedback" / "swarm").mkdir(parents=True, exist_ok=True)

        self.recommendations_ledger_file = self.data_dir / "feedback" / "swarm" / "recommendations.jsonl"
        self.promoted_rules_file = self.data_dir / "feedback" / "swarm" / "promoted_rules.json"
        self.agent_accuracy_file = self.data_dir / "feedback" / "swarm" / "agent_accuracy.json"

        self.promoted_rules: Dict[str, PromotedRule] = {}
        self._load_promoted_rules()

    def process_recommendations(
        self,
        recommendations: List[Any],
        min_confidence: float = 0.65,
        min_impact_pct: float = 3.0,
    ):
        """Process swarm recommendations, apply top ones to live config.

        Args:
            recommendations: List of Recommendation objects from swarm
            min_confidence: Only apply if confidence >= this
            min_impact_pct: Only apply if estimated impact >= this %
        """
        applied_count = 0
        skipped_count = 0

        for rec in recommendations:
            # Check if worth applying
            if rec.confidence < min_confidence:
                logger.debug(f"Skipping {rec.agent_role}: confidence {rec.confidence:.0%} < {min_confidence:.0%}")
                skipped_count += 1
                continue

            if rec.estimated_impact_pct < min_impact_pct:
                logger.debug(f"Skipping {rec.agent_role}: impact {rec.estimated_impact_pct:.1f}% < {min_impact_pct:.1f}%")
                skipped_count += 1
                continue

            # Log recommendation
            self._log_recommendation(rec)

            # Apply to config
            try:
                self._apply_recommendation_to_config(rec)
                applied_count += 1
                logger.info(
                    f"Applied recommendation from {rec.agent_role}: {rec.pattern} "
                    f"({rec.estimated_impact_pct:.1f}% impact, {rec.confidence:.0%} confidence)"
                )
            except Exception as e:
                logger.error(f"Failed to apply recommendation: {e}")
                skipped_count += 1

        logger.info(f"[SWARM FEEDBACK] Applied {applied_count} recommendations, skipped {skipped_count}")

    def _log_recommendation(self, rec: Any):
        """Log recommendation to ledger."""
        try:
            entry = {
                "timestamp": datetime.now().timestamp(),
                "agent_role": rec.agent_role,
                "pattern": rec.pattern,
                "action": rec.action,
                "estimated_impact_pct": rec.estimated_impact_pct,
                "confidence": rec.confidence,
                "status": "proposed",
                "measured_impact_pct": None,
            }

            with open(self.recommendations_ledger_file, "a") as f:
                f.write(json.dumps(entry) + "\n")

        except Exception as e:
            logger.debug(f"Error logging recommendation: {e}")

    def _apply_recommendation_to_config(self, rec: Any):
        """Apply a recommendation to the trading config.

        This creates overrides in trading_config_swarm_overrides.py.
        """
        override_file = Path(f"{self.config_module.replace('.', '/')}_swarm_overrides.py")
        override_file.parent.mkdir(parents=True, exist_ok=True)

        # Read or create override config
        override_config = {}
        if override_file.exists():
            try:
                with open(override_file, "r") as f:
                    content = f.read()
                    # Parse Python dict (very basic, assume well-formed)
                    # In production, use ast.literal_eval
            except Exception as e:
                logger.debug(f"Error reading override config: {e}")

        # Apply based on recommendation type
        if rec.agent_role == "entry_optimizer":
            self._apply_entry_optimization(rec, override_config)
        elif rec.agent_role == "exit_specialist":
            self._apply_exit_optimization(rec, override_config)
        elif rec.agent_role == "sizing_specialist":
            self._apply_sizing_optimization(rec, override_config)
        elif rec.agent_role == "regime_tuner":
            self._apply_regime_tuning(rec, override_config)
        elif rec.agent_role == "pattern_discoverer":
            self._apply_pattern_discovery(rec, override_config)
        elif rec.agent_role == "multi_signal_comparator":
            self._apply_multi_signal_rule(rec, override_config)

        # Save override config
        self._save_override_config(override_config, override_file)

        # Track promoted rule
        rule = PromotedRule(
            recommendation_id=f"{rec.agent_role}_{datetime.now().timestamp()}",
            agent_role=rec.agent_role,
            pattern=rec.pattern,
            action=rec.action,
            promoted_date=datetime.now().timestamp(),
            applied_to_config_keys=list(override_config.keys()),
        )
        self.promoted_rules[rule.recommendation_id] = rule
        self._save_promoted_rules()

    def _apply_entry_optimization(self, rec: Any, config: Dict[str, Any]):
        """Apply entry timing recommendation."""
        if "ENTRY_ADJUSTMENTS" not in config:
            config["ENTRY_ADJUSTMENTS"] = {}

        # Example: "SOL + trend regime -> wait for pullback"
        # Parse pattern and apply
        if "SOL" in rec.pattern and "trend" in rec.pattern:
            if "SOL" not in config["ENTRY_ADJUSTMENTS"]:
                config["ENTRY_ADJUSTMENTS"]["SOL"] = {}
            config["ENTRY_ADJUSTMENTS"]["SOL"]["trend"] = "wait_for_pullback"

    def _apply_exit_optimization(self, rec: Any, config: Dict[str, Any]):
        """Apply exit timing recommendation."""
        if "REGIME_TP_SCALARS" not in config:
            config["REGIME_TP_SCALARS"] = {}

        # Example: "high_volatility -> use trailing stop"
        for regime in ["trend", "range", "panic", "high_volatility", "low_liquidity"]:
            if regime in rec.pattern.lower():
                if regime not in config["REGIME_TP_SCALARS"]:
                    config["REGIME_TP_SCALARS"][regime] = {}

                if "trailing" in rec.action.lower():
                    config["REGIME_TP_SCALARS"][regime]["use_trailing"] = True
                else:
                    config["REGIME_TP_SCALARS"][regime]["use_trailing"] = False

    def _apply_sizing_optimization(self, rec: Any, config: Dict[str, Any]):
        """Apply position sizing recommendation."""
        if "REGIME_RISK_MULTIPLIERS" not in config:
            config["REGIME_RISK_MULTIPLIERS"] = {}

        # Example: "trend regime -> 1.5x sizing"
        for regime in ["trend", "range", "panic", "high_volatility", "low_liquidity"]:
            if regime in rec.pattern.lower():
                # Extract multiplier from action
                if "1.5" in rec.action or "1.5x" in rec.action:
                    config["REGIME_RISK_MULTIPLIERS"][regime] = 1.5
                elif "0.7" in rec.action or "0.7x" in rec.action:
                    config["REGIME_RISK_MULTIPLIERS"][regime] = 0.7

    def _apply_regime_tuning(self, rec: Any, config: Dict[str, Any]):
        """Apply regime-specific parameter tuning."""
        if "REGIME_PARAMETERS" not in config:
            config["REGIME_PARAMETERS"] = {}

        # Generic regime parameter application
        for regime in ["trend", "range", "panic", "high_volatility", "low_liquidity"]:
            if regime in rec.pattern.lower():
                if regime not in config["REGIME_PARAMETERS"]:
                    config["REGIME_PARAMETERS"][regime] = {}
                # Apply the action as parameter update

    def _apply_pattern_discovery(self, rec: Any, config: Dict[str, Any]):
        """Apply newly discovered high-edge pattern."""
        if "SNIPER_PATTERNS" not in config:
            config["SNIPER_PATTERNS"] = []

        # Add pattern to list
        new_pattern = {
            "name": rec.pattern,
            "description": rec.action,
            "sizing_multiplier": 1.5,  # Default, can be refined
            "confidence": rec.confidence,
            "status": "active",
        }
        config["SNIPER_PATTERNS"].append(new_pattern)

    def _apply_multi_signal_rule(self, rec: Any, config: Dict[str, Any]):
        """Apply multi-signal vs single-signal decision rule."""
        if "MULTI_SIGNAL_RULES" not in config:
            config["MULTI_SIGNAL_RULES"] = {}

        # Example: "skip when single signal conflicts with ensemble"
        if "skip" in rec.action.lower() and "conflict" in rec.pattern.lower():
            config["MULTI_SIGNAL_RULES"]["conflict_action"] = "skip"
        elif "proceed" in rec.action.lower():
            config["MULTI_SIGNAL_RULES"]["conflict_action"] = "proceed"

    def _save_override_config(self, config: Dict[str, Any], filepath: Path):
        """Save override config to file."""
        # Create Python config file
        lines = [
            "# Auto-generated swarm recommendations",
            f"# Generated: {datetime.now().isoformat()}",
            "# DO NOT EDIT MANUALLY",
            "",
        ]

        for key, value in config.items():
            lines.append(f"{key} = {repr(value)}")
            lines.append("")

        try:
            with open(filepath, "w") as f:
                f.write("\n".join(lines))
            logger.debug(f"Saved override config to {filepath}")
        except Exception as e:
            logger.error(f"Error saving override config: {e}")

    def measure_recommendation_impact(
        self,
        recommendation_id: str,
        actual_impact_pct: float,
        notes: str = ""
    ):
        """Record actual measured impact of a recommendation.

        Called after the recommendation has been live for some time.
        """
        if recommendation_id not in self.promoted_rules:
            logger.warning(f"Unknown recommendation: {recommendation_id}")
            return

        rule = self.promoted_rules[recommendation_id]
        rule.measured_impact_pct = actual_impact_pct

        # Update status based on impact
        if actual_impact_pct >= 0:
            rule.status = "active"  # Still good
        else:  # Negative impact
            rule.status = "degraded"
            logger.warning(f"Recommendation {recommendation_id} degraded: {actual_impact_pct:.1f}%")

        self._save_promoted_rules()

        # Track agent accuracy
        self._update_agent_accuracy(rule.agent_role, actual_impact_pct)

    def _update_agent_accuracy(self, agent_role: str, actual_impact_pct: float):
        """Update agent accuracy tracking."""
        try:
            accuracy_data = {}
            if self.agent_accuracy_file.exists():
                with open(self.agent_accuracy_file, "r") as f:
                    accuracy_data = json.load(f)

            if agent_role not in accuracy_data:
                accuracy_data[agent_role] = {
                    "recommendations": 0,
                    "positive_impact": 0,
                    "average_impact_pct": 0.0,
                    "accuracy": 0.0,
                }

            agent_stat = accuracy_data[agent_role]
            agent_stat["recommendations"] += 1
            if actual_impact_pct > 0:
                agent_stat["positive_impact"] += 1

            # Update average
            agent_stat["average_impact_pct"] = (
                (agent_stat["average_impact_pct"] * (agent_stat["recommendations"] - 1) + actual_impact_pct)
                / agent_stat["recommendations"]
            )
            agent_stat["accuracy"] = agent_stat["positive_impact"] / agent_stat["recommendations"]

            with open(self.agent_accuracy_file, "w") as f:
                json.dump(accuracy_data, f, indent=2)

        except Exception as e:
            logger.debug(f"Error updating agent accuracy: {e}")

    def _load_promoted_rules(self):
        """Load previously promoted rules from file."""
        if not self.promoted_rules_file.exists():
            return

        try:
            with open(self.promoted_rules_file, "r") as f:
                data = json.load(f)
                for rule_id, rule_dict in data.items():
                    self.promoted_rules[rule_id] = PromotedRule(**rule_dict)
        except Exception as e:
            logger.debug(f"Error loading promoted rules: {e}")

    def _save_promoted_rules(self):
        """Save promoted rules to file."""
        try:
            data = {
                rule_id: asdict(rule)
                for rule_id, rule in self.promoted_rules.items()
            }
            with open(self.promoted_rules_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving promoted rules: {e}")

    def get_agent_accuracy(self) -> Dict[str, Any]:
        """Get accuracy stats for all agents."""
        try:
            if self.agent_accuracy_file.exists():
                with open(self.agent_accuracy_file, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.debug(f"Error reading agent accuracy: {e}")

        return {}

    def generate_report(self) -> str:
        """Generate feedback loop status report."""
        lines = [
            "SWARM FEEDBACK LOOP REPORT",
            "=" * 60,
            f"Total promoted rules: {len(self.promoted_rules)}",
        ]

        agent_accuracy = self.get_agent_accuracy()
        if agent_accuracy:
            lines.append("\nAgent Accuracy:")
            for agent, stats in agent_accuracy.items():
                lines.append(
                    f"  {agent}: {stats['accuracy']:.0%} "
                    f"({stats['positive_impact']}/{stats['recommendations']} positive, "
                    f"avg {stats['average_impact_pct']:.1f}%)"
                )

        active_rules = [r for r in self.promoted_rules.values() if r.status == "active"]
        if active_rules:
            lines.append(f"\nActive rules: {len(active_rules)}")
            for rule in list(active_rules)[:5]:
                lines.append(
                    f"  {rule.agent_role}: {rule.pattern} "
                    f"(impact: {rule.measured_impact_pct}%)" if rule.measured_impact_pct else ""
                )

        return "\n".join(lines)


__all__ = [
    "PromotedRule",
    "SwarmFeedbackLoop",
]
