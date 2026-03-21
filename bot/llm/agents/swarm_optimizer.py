"""
Swarm Optimizer Coordinator.

Manages 6 specialized agent roles running in parallel on single-signal trade data:
1. Entry Optimizer - Find entry timing improvements
2. Exit Specialist - Optimize TP/SL placement and exit timing
3. Sizing Specialist - Apply Kelly Criterion and regime-adaptive sizing
4. Regime Tuner - Find regime-specific parameter adjustments
5. Pattern Discoverer - Mine hidden profitable patterns
6. Multi-Signal Comparator - Evaluate when single-signal outperforms ensemble

The coordinator runs all 6 agents in parallel and ranks recommendations by
estimated impact and confidence.
"""

import json
import logging
import asyncio
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from llm.client import call_llm
from llm.agents.base import AgentConfig, AgentOutput, AgentRole
from llm.agents.swarm_agent_prompts import SWARM_AGENT_PROMPTS

logger = logging.getLogger("bot.llm.agents.swarm_optimizer")


@dataclass
class Recommendation:
    """A recommendation from a swarm agent."""
    agent_role: str  # "entry_optimizer", "exit_specialist", etc.
    pattern: str  # What this recommendation applies to
    action: str  # What to do
    rationale: str  # Why
    estimated_impact_pct: float  # Expected WR or return improvement
    confidence: float  # Agent's confidence (0-1)
    test_duration_days: int = 7
    priority: int = 1  # 1=high, 2=medium, 3=low

    def impact_score(self) -> float:
        """Score for ranking by impact."""
        # Higher WR improvement + higher confidence = higher priority
        return (self.estimated_impact_pct / 100) * self.confidence * self.priority


@dataclass
class SwarmRecommendations:
    """Output from the full swarm run."""
    timestamp: float
    total_agents_run: int
    successful_agents: int
    failed_agents: List[str]
    total_recommendations: int

    recommendations: List[Recommendation] = None  # Sorted by impact score

    def __post_init__(self):
        if self.recommendations is None:
            self.recommendations = []


class SwarmOptimizer:
    """Orchestrates 6 parallel optimization agents."""

    def __init__(self):
        self.agents_config = {
            "entry_optimizer": {
                "model": "claude-sonnet-4-6",
                "max_tokens": 2048,
                "temperature": 0.7,
            },
            "exit_specialist": {
                "model": "claude-sonnet-4-6",
                "max_tokens": 2048,
                "temperature": 0.7,
            },
            "sizing_specialist": {
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 1024,
                "temperature": 0.6,
            },
            "regime_tuner": {
                "model": "claude-sonnet-4-6",
                "max_tokens": 2048,
                "temperature": 0.7,
            },
            "pattern_discoverer": {
                "model": "claude-sonnet-4-6",
                "max_tokens": 2048,
                "temperature": 0.8,  # More creative for discovery
            },
            "multi_signal_comparator": {
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 1024,
                "temperature": 0.6,
            },
        }

        self.last_run_timestamp = None
        self.last_run_results = None

    async def optimize_single_signals(
        self,
        audit_data: Dict[str, Any],
        timeout_seconds: int = 60
    ) -> SwarmRecommendations:
        """Run all 6 agents in parallel on single-signal trade data.

        Args:
            audit_data: Output from SingleSignalAudit (trades, metrics, sniper setups, etc.)
            timeout_seconds: Max time to wait for all agents

        Returns:
            SwarmRecommendations with ranked recommendations
        """
        start_time = time.time()
        self.last_run_timestamp = datetime.now().timestamp()

        logger.info("[SWARM] Starting parallel agent run with 6 agents...")

        # Prepare tasks for all 6 agents
        tasks = {
            "entry_optimizer": self._run_agent(
                "entry_optimizer",
                audit_data,
                SWARM_AGENT_PROMPTS["entry_optimizer"]
            ),
            "exit_specialist": self._run_agent(
                "exit_specialist",
                audit_data,
                SWARM_AGENT_PROMPTS["exit_specialist"]
            ),
            "sizing_specialist": self._run_agent(
                "sizing_specialist",
                audit_data,
                SWARM_AGENT_PROMPTS["sizing_specialist"]
            ),
            "regime_tuner": self._run_agent(
                "regime_tuner",
                audit_data,
                SWARM_AGENT_PROMPTS["regime_tuner"]
            ),
            "pattern_discoverer": self._run_agent(
                "pattern_discoverer",
                audit_data,
                SWARM_AGENT_PROMPTS["pattern_discoverer"]
            ),
            "multi_signal_comparator": self._run_agent(
                "multi_signal_comparator",
                audit_data,
                SWARM_AGENT_PROMPTS["multi_signal_comparator"]
            ),
        }

        # Run all in parallel with timeout
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks.values(), return_exceptions=True),
                timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            logger.warning(f"[SWARM] Timeout after {timeout_seconds}s, collecting partial results...")
            results = [None] * len(tasks)

        # Process results
        all_recommendations = []
        failed_agents = []
        successful_count = 0

        for agent_name, result in zip(tasks.keys(), results):
            if result is None or isinstance(result, Exception):
                logger.warning(f"[SWARM] Agent {agent_name} failed or timed out")
                failed_agents.append(agent_name)
                continue

            if not isinstance(result, dict):
                logger.warning(f"[SWARM] Agent {agent_name} returned invalid output")
                failed_agents.append(agent_name)
                continue

            successful_count += 1

            # Extract recommendations from agent output
            agent_recs = result.get("recommendations", [])
            for rec in agent_recs:
                try:
                    recommendation = Recommendation(
                        agent_role=agent_name,
                        pattern=rec.get("pattern", ""),
                        action=rec.get("action", rec.get("proposed_change", "")),
                        rationale=rec.get("rationale", ""),
                        estimated_impact_pct=float(rec.get("estimated_impact_pct", rec.get("impact", 0))),
                        confidence=float(rec.get("confidence", 0.5)),
                        test_duration_days=int(rec.get("test_duration_days", 7)),
                    )
                    all_recommendations.append(recommendation)
                except Exception as e:
                    logger.debug(f"Error parsing recommendation from {agent_name}: {e}")

        # Rank recommendations by impact score
        all_recommendations.sort(key=lambda r: r.impact_score(), reverse=True)

        elapsed = time.time() - start_time

        result = SwarmRecommendations(
            timestamp=self.last_run_timestamp,
            total_agents_run=len(tasks),
            successful_agents=successful_count,
            failed_agents=failed_agents,
            total_recommendations=len(all_recommendations),
            recommendations=all_recommendations,
        )

        self.last_run_results = result

        logger.info(
            f"[SWARM] Completed in {elapsed:.1f}s: {successful_count}/{len(tasks)} agents, "
            f"{len(all_recommendations)} recommendations"
        )

        if all_recommendations:
            top_rec = all_recommendations[0]
            logger.info(
                f"[SWARM] Top recommendation: {top_rec.agent_role} - {top_rec.pattern} "
                f"(impact: {top_rec.estimated_impact_pct:.1f}%, conf: {top_rec.confidence:.0%})"
            )

        return result

    async def _run_agent(
        self,
        agent_role: str,
        audit_data: Dict[str, Any],
        prompt_template: str
    ) -> Optional[Dict[str, Any]]:
        """Run a single swarm agent.

        Args:
            agent_role: Which agent to run
            audit_data: Context data for the agent
            prompt_template: Prompt template for the agent

        Returns:
            Agent output dict with recommendations
        """
        try:
            config = self.agents_config[agent_role]

            # Build agent input
            agent_input = self._build_agent_input(agent_role, audit_data)

            # Format the prompt
            prompt = prompt_template.format(
                audit_summary=agent_input.get("summary", ""),
                trades_analysis=agent_input.get("trades_analysis", ""),
                metrics=json.dumps(agent_input.get("metrics", {}), indent=2),
                sniper_setups=json.dumps(agent_input.get("sniper_setups", [])[:5], indent=2),
            )

            # Call LLM (synchronously, but with concurrent ability)
            response = await asyncio.to_thread(
                call_llm,
                model=config["model"],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=config["max_tokens"],
                temperature=config["temperature"],
            )

            # Parse response
            if response and "content" in response:
                # Try to extract JSON from response
                content = response["content"]
                try:
                    # Look for JSON block
                    import re
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        agent_output = json.loads(json_match.group())
                        logger.debug(f"[SWARM] {agent_role} produced {len(agent_output.get('recommendations', []))} recommendations")
                        return agent_output
                except json.JSONDecodeError:
                    logger.warning(f"[SWARM] {agent_role} returned invalid JSON")
                    return None

            return None

        except Exception as e:
            logger.debug(f"[SWARM] Error running {agent_role}: {e}")
            return None

    def _build_agent_input(self, agent_role: str, audit_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build role-specific input context for an agent.

        Each agent sees a different subset of the audit data relevant to their role.
        """
        # Extract from audit_data
        trades = audit_data.get("trades", [])
        metrics = audit_data.get("metrics", {})
        sniper_setups = audit_data.get("sniper_setups", [])
        losers = audit_data.get("losers", [])

        # Build audit summary
        overall_metrics = metrics.get("overall", {})
        summary_lines = [
            f"Total single-signal trades: {overall_metrics.get('trade_count', 0)}",
            f"Overall win rate: {overall_metrics.get('win_rate', 0):.0%}",
            f"Profit factor: {overall_metrics.get('profit_factor', 0):.2f}",
            f"Sharpe ratio: {overall_metrics.get('sharpe_ratio', 0):.2f}",
        ]

        # Role-specific context
        input_data = {
            "summary": "\n".join(summary_lines),
            "trades_analysis": self._summarize_trades(trades),
            "metrics": metrics,
            "sniper_setups": sniper_setups,
            "losers": losers,
        }

        if agent_role == "entry_optimizer":
            input_data["focus"] = "entry timing and entry adjustments"
            input_data["metrics"] = metrics.get("by_entry_adjustment", {})

        elif agent_role == "exit_specialist":
            input_data["focus"] = "take-profit placement and exit timing"
            input_data["metrics"] = metrics.get("by_exit_type", {})

        elif agent_role == "sizing_specialist":
            input_data["focus"] = "position sizing and Kelly Criterion"
            input_data["metrics"] = metrics.get("by_regime_1h", {})

        elif agent_role == "regime_tuner":
            input_data["focus"] = "regime-specific parameter adjustments"
            input_data["metrics"] = metrics.get("by_regime_1h", {})

        elif agent_role == "pattern_discoverer":
            input_data["focus"] = "discovering hidden profitable patterns"
            input_data["metrics"] = metrics.get("by_symbol", {})

        elif agent_role == "multi_signal_comparator":
            input_data["focus"] = "comparing single-signal vs ensemble performance"
            input_data["comparison_data"] = audit_data.get("single_vs_ensemble_comparison", {})

        return input_data

    def _summarize_trades(self, trades: List[Dict[str, Any]]) -> str:
        """Create a summary of trades for agent context."""
        if not trades:
            return "No trades to analyze."

        lines = [
            f"Total trades analyzed: {len(trades)}",
            f"Date range: {trades[0].get('date', 'unknown')} to {trades[-1].get('date', 'unknown')}",
        ]

        # Sample a few trades
        if trades:
            lines.append("\nSample trades:")
            for trade in trades[:3]:
                lines.append(f"  - {trade.get('symbol', '')} {trade.get('side', '')} "
                           f"@ {trade.get('entry_price', 0):.2f}, "
                           f"WR: {trade.get('win_rate', 0):.0%}")

        return "\n".join(lines)

    def get_top_recommendations(self, limit: int = 5) -> List[Recommendation]:
        """Get top N recommendations from the last run."""
        if not self.last_run_results or not self.last_run_results.recommendations:
            return []

        return self.last_run_results.recommendations[:limit]

    def estimate_impact(self, recommendation: Recommendation) -> Dict[str, float]:
        """Estimate potential PnL impact if recommendation is implemented.

        Returns:
            Dict with impact estimates
        """
        # Very simple: project improvement across assumed trade volume
        trades_per_month = 20  # Assume 20 single-signal trades per month
        avg_position_size = 100  # USD notional

        monthly_improvement = (recommendation.estimated_impact_pct / 100) * trades_per_month * avg_position_size

        return {
            "monthly_usd_impact": monthly_improvement,
            "estimated_improvement_pct": recommendation.estimated_impact_pct,
            "confidence": recommendation.confidence,
            "roi_vs_cost": monthly_improvement / 10,  # Assume $10 cost per optimization
        }

    def save_results(self, filepath: str):
        """Save last run results to file."""
        if not self.last_run_results:
            return

        try:
            data = {
                "timestamp": self.last_run_timestamp,
                "successful_agents": self.last_run_results.successful_agents,
                "failed_agents": self.last_run_results.failed_agents,
                "recommendations": [
                    {
                        "agent_role": r.agent_role,
                        "pattern": r.pattern,
                        "action": r.action,
                        "estimated_impact_pct": r.estimated_impact_pct,
                        "confidence": r.confidence,
                        "impact_score": r.impact_score(),
                    }
                    for r in self.last_run_results.recommendations
                ],
            }

            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)

            logger.info(f"[SWARM] Saved results to {filepath}")
        except Exception as e:
            logger.error(f"Error saving results: {e}")


# Synchronous wrapper for backwards compatibility
def run_swarm_optimizer(
    audit_data: Dict[str, Any],
    timeout_seconds: int = 60
) -> SwarmRecommendations:
    """Synchronous entry point for swarm optimization.

    Args:
        audit_data: Output from SingleSignalAudit
        timeout_seconds: Max time to wait

    Returns:
        SwarmRecommendations
    """
    try:
        # Try async if event loop exists
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Running in async context, need to handle differently
            logger.warning("[SWARM] Already in async context, returning empty recommendations")
            return SwarmRecommendations(
                timestamp=datetime.now().timestamp(),
                total_agents_run=0,
                successful_agents=0,
                failed_agents=["all"],
                total_recommendations=0,
            )
    except RuntimeError:
        pass

    # Create new event loop if needed
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        optimizer = SwarmOptimizer()
        result = loop.run_until_complete(
            optimizer.optimize_single_signals(audit_data, timeout_seconds)
        )
        return result
    except Exception as e:
        logger.error(f"[SWARM] Error in synchronous wrapper: {e}")
        return SwarmRecommendations(
            timestamp=datetime.now().timestamp(),
            total_agents_run=0,
            successful_agents=0,
            failed_agents=["all"],
            total_recommendations=0,
        )
    finally:
        loop.close()


__all__ = [
    "Recommendation",
    "SwarmRecommendations",
    "SwarmOptimizer",
    "run_swarm_optimizer",
]
