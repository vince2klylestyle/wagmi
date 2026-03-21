"""
Master Swarm Orchestrator.

Daily/weekly master loop that:
1. Audits single-signal trade performance
2. Runs 6-agent swarm to find improvements
3. Applies top recommendations to live config
4. Measures impact and calibrates agent accuracy

This is the autonomous improvement engine that continuously strengthens
the bot's profitability.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("bot.llm.agents.swarm_master")


class SwarmMaster:
    """Master orchestrator for autonomous bot improvement."""

    def __init__(self, data_dir: str = "bot/data"):
        self.data_dir = Path(data_dir)
        (self.data_dir / "feedback" / "swarm").mkdir(parents=True, exist_ok=True)

        # Lazy imports to avoid circular dependencies
        self.audit = None
        self.swarm = None
        self.feedback_loop = None

    def _lazy_import_modules(self):
        """Import heavy modules only when needed."""
        if self.audit is None:
            from feedback.single_signal_audit import SingleSignalAudit
            self.audit = SingleSignalAudit(str(self.data_dir))

        if self.swarm is None:
            from llm.agents.swarm_optimizer import SwarmOptimizer
            self.swarm = SwarmOptimizer()

        if self.feedback_loop is None:
            from feedback.swarm_feedback_loop import SwarmFeedbackLoop
            self.feedback_loop = SwarmFeedbackLoop(str(self.data_dir))

    def daily_optimization_run(
        self,
        lookback_days: int = 7,
        min_confidence: float = 0.65,
        min_impact_pct: float = 3.0,
    ) -> Dict[str, Any]:
        """Run the daily optimization cycle.

        Args:
            lookback_days: How many days of trades to analyze
            min_confidence: Only apply recommendations if confidence >= this
            min_impact_pct: Only apply if estimated impact >= this %

        Returns:
            Status dict with results
        """
        self._lazy_import_modules()

        logger.info("[SWARM MASTER] Starting daily optimization run...")
        start_time = datetime.now()

        result = {
            "timestamp": start_time.timestamp(),
            "status": "running",
            "stage": "audit",
            "trades_analyzed": 0,
            "recommendations_generated": 0,
            "recommendations_applied": 0,
            "errors": [],
        }

        try:
            # STAGE 1: AUDIT
            logger.info(f"[SWARM MASTER] Stage 1: Analyzing last {lookback_days} days...")
            trades = self.audit.extract_single_signals(lookback_days=lookback_days)
            result["trades_analyzed"] = len(trades)

            if len(trades) == 0:
                logger.warning("[SWARM MASTER] No single-signal trades found in period")
                result["status"] = "no_trades"
                return result

            # Compute metrics for swarm to analyze
            metrics = self.audit.compute_metrics()
            sniper_setups = self.audit.find_sniper_setups()
            losers = self.audit.identify_losers()

            audit_data = {
                "trades": [self._trade_to_dict(t) for t in trades],
                "metrics": self._metrics_to_dict(metrics),
                "sniper_setups": [self._sniper_to_dict(s) for s in sniper_setups],
                "losers": losers,
            }

            # STAGE 2: SWARM OPTIMIZATION
            logger.info("[SWARM MASTER] Stage 2: Running 6-agent swarm...")
            result["stage"] = "swarm"

            # Run swarm (synchronously for now)
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                swarm_result = loop.run_until_complete(
                    self.swarm.optimize_single_signals(audit_data, timeout_seconds=120)
                )
                loop.close()
            except Exception as e:
                logger.error(f"Error running swarm: {e}")
                result["errors"].append(f"Swarm execution error: {str(e)}")
                swarm_result = None

            if not swarm_result or not swarm_result.recommendations:
                logger.warning("[SWARM MASTER] No recommendations from swarm")
                result["recommendations_generated"] = 0
                result["status"] = "completed_no_recs"
                self._save_run_result(result)
                return result

            result["recommendations_generated"] = len(swarm_result.recommendations)

            # STAGE 3: APPLY RECOMMENDATIONS
            logger.info("[SWARM MASTER] Stage 3: Applying top recommendations...")
            result["stage"] = "apply"

            try:
                self.feedback_loop.process_recommendations(
                    swarm_result.recommendations,
                    min_confidence=min_confidence,
                    min_impact_pct=min_impact_pct,
                )
                result["recommendations_applied"] = len([
                    r for r in swarm_result.recommendations
                    if r.confidence >= min_confidence and r.estimated_impact_pct >= min_impact_pct
                ])
            except Exception as e:
                logger.error(f"Error applying recommendations: {e}")
                result["errors"].append(f"Application error: {str(e)}")

            # STAGE 4: REPORT
            logger.info("[SWARM MASTER] Stage 4: Generating report...")
            result["stage"] = "report"

            elapsed = (datetime.now() - start_time).total_seconds()
            result["elapsed_seconds"] = elapsed
            result["status"] = "completed"

            # Generate summary
            summary = self._generate_summary(audit_data, swarm_result, result)
            result["summary"] = summary

            logger.info(f"[SWARM MASTER] Daily run completed in {elapsed:.1f}s")
            logger.info(summary)

            self._save_run_result(result)
            return result

        except Exception as e:
            logger.error(f"[SWARM MASTER] Unexpected error: {e}")
            result["status"] = "error"
            result["errors"].append(str(e))
            self._save_run_result(result)
            return result

    def weekly_hypothesis_graduation(self) -> Dict[str, Any]:
        """Run weekly hypothesis graduation process.

        Promote high-accuracy recommendations to permanent rules.
        Demote low-accuracy ones to anti-patterns.
        """
        self._lazy_import_modules()

        logger.info("[SWARM MASTER] Starting weekly hypothesis graduation...")

        agent_accuracy = self.feedback_loop.get_agent_accuracy()
        promoted_rules = self.feedback_loop.promoted_rules

        result = {
            "timestamp": datetime.now().timestamp(),
            "agent_accuracy": agent_accuracy,
            "graduated_rules": [],
            "demoted_rules": [],
        }

        # Promote rules with high accuracy
        for rule_id, rule in promoted_rules.items():
            if rule.status == "active" and rule.measured_impact_pct and rule.measured_impact_pct > 5.0:
                result["graduated_rules"].append({
                    "rule_id": rule_id,
                    "agent": rule.agent_role,
                    "pattern": rule.pattern,
                    "impact": rule.measured_impact_pct,
                })
                logger.info(f"Graduated rule {rule_id}: {rule.pattern} ({rule.measured_impact_pct:.1f}%)")

        # Demote rules with low accuracy
        for rule_id, rule in promoted_rules.items():
            if rule.status == "degraded" and rule.measured_impact_pct and rule.measured_impact_pct < -2.0:
                result["demoted_rules"].append({
                    "rule_id": rule_id,
                    "agent": rule.agent_role,
                    "pattern": rule.pattern,
                    "impact": rule.measured_impact_pct,
                })
                rule.status = "reverted"
                logger.warning(f"Reverted rule {rule_id}: {rule.pattern} ({rule.measured_impact_pct:.1f}%)")

        self.feedback_loop._save_promoted_rules()

        logger.info(f"[SWARM MASTER] Weekly graduation: promoted {len(result['graduated_rules'])}, "
                   f"demoted {len(result['demoted_rules'])}")

        return result

    def _trade_to_dict(self, trade) -> Dict[str, Any]:
        """Convert trade object to dict."""
        from dataclasses import asdict
        return asdict(trade)

    def _metrics_to_dict(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Convert metrics to dict."""
        from dataclasses import asdict

        result = {}
        for key, metric in metrics.items():
            if hasattr(metric, '__dataclass_fields__'):
                result[key] = asdict(metric)
            elif isinstance(metric, dict):
                result[key] = {
                    k: asdict(v) if hasattr(v, '__dataclass_fields__') else v
                    for k, v in metric.items()
                }
            else:
                result[key] = metric

        return result

    def _sniper_to_dict(self, setup) -> Dict[str, Any]:
        """Convert sniper setup to dict."""
        from dataclasses import asdict
        return asdict(setup)

    def _generate_summary(
        self,
        audit_data: Dict[str, Any],
        swarm_result: Any,
        run_result: Dict[str, Any]
    ) -> str:
        """Generate human-readable summary."""
        lines = [
            "=" * 70,
            "DAILY SWARM OPTIMIZATION SUMMARY",
            "=" * 70,
            f"Timestamp: {datetime.now().isoformat()}",
            "",
            "AUDIT RESULTS:",
            f"  Single-signal trades analyzed: {run_result['trades_analyzed']}",
            f"  Sniper setups found: {len(audit_data.get('sniper_setups', []))}",
            f"  Losing patterns identified: {len(audit_data.get('losers', []))}",
            "",
            "SWARM RESULTS:",
            f"  Total recommendations: {run_result['recommendations_generated']}",
            f"  Applied recommendations: {run_result['recommendations_applied']}",
            "",
        ]

        if swarm_result and swarm_result.recommendations:
            lines.append("TOP 3 RECOMMENDATIONS:")
            for i, rec in enumerate(swarm_result.recommendations[:3], 1):
                lines.append(
                    f"  {i}. {rec.agent_role}: {rec.pattern} "
                    f"({rec.estimated_impact_pct:.1f}% impact, {rec.confidence:.0%} confidence)"
                )

        agent_accuracy = self.feedback_loop.get_agent_accuracy()
        if agent_accuracy:
            lines.append("")
            lines.append("AGENT ACCURACY TRACKING:")
            for agent, stats in agent_accuracy.items():
                lines.append(
                    f"  {agent}: {stats['accuracy']:.0%} "
                    f"({stats['positive_impact']}/{stats['recommendations']}, "
                    f"avg impact {stats['average_impact_pct']:+.1f}%)"
                )

        lines.append("")
        lines.append(f"Elapsed time: {run_result.get('elapsed_seconds', 0):.1f}s")
        lines.append("=" * 70)

        return "\n".join(lines)

    def _save_run_result(self, result: Dict[str, Any]):
        """Save run result to file."""
        try:
            filepath = self.data_dir / "feedback" / "swarm" / "daily_runs.jsonl"
            with open(filepath, "a") as f:
                f.write(json.dumps(result) + "\n")
        except Exception as e:
            logger.error(f"Error saving run result: {e}")


# Convenience functions
def run_daily_swarm():
    """Run the daily swarm optimization (call from cron or scheduler)."""
    master = SwarmMaster()
    return master.daily_optimization_run()


def run_weekly_graduation():
    """Run weekly hypothesis graduation (call from cron or scheduler)."""
    master = SwarmMaster()
    return master.weekly_hypothesis_graduation()


__all__ = [
    "SwarmMaster",
    "run_daily_swarm",
    "run_weekly_graduation",
]
