"""
TIER 5.2: Bot Perception Aggregator

Combines API perception with mechanical bot instrumentation.
Creates unified view of everything the bot sees, thinks, and does.

Architecture:
- Fetch API perception (what bot reads)
- Combine with mechanical bot state (what bot does)
- Track perception evolution over time
- Enable comparison: perception vs reality
- Identify mismatches (perception bias)
"""

import logging
import json
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime
import time
from collections import defaultdict

from bot_perception_api import (
    get_bot_perception_api_client,
    BotSummarySnapshot,
    StrategySnapshot,
    LLMDecisionSnapshot,
    AgentBrainSnapshot,
    AgentDebate,
    PipelineTelemetry,
)

logger = logging.getLogger("bot.llm.bot_perception_aggregator")


@dataclass
class UnifiedBotPercept:
    """
    Complete unified view of bot's perception + state + decisions.

    Everything the bot sees/thinks/does at a moment in time.
    """
    percept_id: str
    timestamp: float

    # System State (from API)
    system_summary: Optional[BotSummarySnapshot] = None

    # Strategy Perception (from API)
    strategy_summaries: Dict[str, StrategySnapshot] = field(default_factory=dict)

    # LLM Perception (from API)
    llm_latest_decision: Optional[LLMDecisionSnapshot] = None
    llm_market_view: Optional[Dict[str, Any]] = None

    # Agent Perception (from API)
    agent_brains: Dict[str, AgentBrainSnapshot] = field(default_factory=dict)
    agent_debate: Optional[AgentDebate] = None
    pipeline_health: Optional[PipelineTelemetry] = None

    # Mechanical Bot State (from instrumentation)
    mechanical_signals: List[Dict[str, Any]] = field(default_factory=list)
    mechanical_open_positions: List[Dict[str, Any]] = field(default_factory=list)

    # Analysis
    perception_quality_score: float = 0.0  # How confident in the perception?
    perception_consistency_score: float = 0.0  # How aligned are different agents?
    perception_vs_reality_gap: float = 0.0  # Perception bias?

    # Metadata
    data_freshness: Dict[str, float] = field(default_factory=dict)  # Age of each data source


@dataclass
class PerceptionEvolution:
    """Track how bot's perception evolves over time."""
    symbol: str
    time_window_minutes: int

    # Perception trend
    regime_sequence: List[Tuple[float, str]] = field(default_factory=list)  # timestamp, regime
    confidence_sequence: List[Tuple[float, float]] = field(default_factory=list)  # timestamp, confidence
    agent_agreement_trend: List[Tuple[float, float]] = field(default_factory=list)  # timestamp, agreement_score

    # Decision frequency
    num_decisions: int = 0
    decisions_per_hour: float = 0.0

    # Perception stability
    regime_changes: int = 0
    confidence_swings: float = 0.0  # std dev of confidence
    agent_disagreement_events: int = 0


class BotPerceptionAggregator:
    """
    Aggregates all bot perception sources.
    """

    def __init__(self, data_dir: str = "data/llm"):
        self.api_client = get_bot_perception_api_client()
        self.data_dir = data_dir
        self.perception_dir = os.path.join(data_dir, "bot_perception")
        os.makedirs(self.perception_dir, exist_ok=True)

        # Store percepts
        self.percepts: Dict[str, UnifiedBotPercept] = {}
        self.percepts_file = os.path.join(self.perception_dir, "percepts.jsonl")

        # Track evolution
        self.evolution_by_symbol: Dict[str, PerceptionEvolution] = {}

        # Statistics
        self.stats = {
            "total_percepts_captured": 0,
            "avg_perception_quality": 0.0,
            "avg_agent_agreement": 0.0,
            "perception_bias_detections": 0,
        }

        # Load existing data
        self._load_percepts()

    def capture_unified_perception(
        self,
        system_summary: Optional[BotSummarySnapshot] = None,
        strategy_summaries: Optional[Dict[str, StrategySnapshot]] = None,
        llm_decision: Optional[LLMDecisionSnapshot] = None,
        llm_market_view: Optional[Dict[str, Any]] = None,
        agent_brains: Optional[Dict[str, AgentBrainSnapshot]] = None,
        agent_debate: Optional[AgentDebate] = None,
        pipeline_health: Optional[PipelineTelemetry] = None,
        mechanical_signals: Optional[List[Dict[str, Any]]] = None,
        mechanical_positions: Optional[List[Dict[str, Any]]] = None,
    ) -> UnifiedBotPercept:
        """
        Capture complete unified perception snapshot.
        """
        percept = UnifiedBotPercept(
            percept_id=f"percept_{int(time.time() * 1000) % 1000000}",
            timestamp=time.time(),
            system_summary=system_summary,
            strategy_summaries=strategy_summaries or {},
            llm_latest_decision=llm_decision,
            llm_market_view=llm_market_view,
            agent_brains=agent_brains or {},
            agent_debate=agent_debate,
            pipeline_health=pipeline_health,
            mechanical_signals=mechanical_signals or [],
            mechanical_open_positions=mechanical_positions or [],
        )

        # Calculate quality scores
        percept.perception_quality_score = self._calculate_perception_quality(percept)
        percept.perception_consistency_score = self._calculate_agent_consistency(percept)
        percept.perception_vs_reality_gap = self._calculate_perception_gap(percept)

        # Track data freshness
        percept.data_freshness = self._calculate_data_freshness(percept)

        # Store
        self.percepts[percept.percept_id] = percept
        self.stats["total_percepts_captured"] += 1

        # Update running averages
        if self.stats["total_percepts_captured"] > 0:
            self.stats["avg_perception_quality"] = (
                self.stats["avg_perception_quality"] * (self.stats["total_percepts_captured"] - 1)
                + percept.perception_quality_score
            ) / self.stats["total_percepts_captured"]

            self.stats["avg_agent_agreement"] = (
                self.stats["avg_agent_agreement"] * (self.stats["total_percepts_captured"] - 1)
                + percept.perception_consistency_score
            ) / self.stats["total_percepts_captured"]

        # Persist
        self._save_percept(percept)

        # Update evolution
        if system_summary:
            self._update_evolution(percept)

        logger.debug(f"Captured perception {percept.percept_id}: quality={percept.perception_quality_score:.2f}, consistency={percept.perception_consistency_score:.2f}")
        return percept

    def get_latest_percept(self) -> Optional[UnifiedBotPercept]:
        """Get most recent perception snapshot."""
        if not self.percepts:
            return None
        return max(self.percepts.values(), key=lambda p: p.timestamp)

    def get_perception_by_symbol(self, symbol: str) -> Optional[PerceptionEvolution]:
        """Get perception evolution for a symbol."""
        return self.evolution_by_symbol.get(symbol)

    def analyze_perception_drift(self, window_minutes: int = 60) -> Dict[str, Any]:
        """
        Analyze how bot's perception has drifted over time window.

        Detects:
        - Frequent regime changes (instability)
        - Wildly changing confidence (uncertainty)
        - Agent disagreement (internal conflict)
        """
        recent_percepts = [
            p for p in self.percepts.values()
            if time.time() - p.timestamp < window_minutes * 60
        ]

        if not recent_percepts:
            return {"status": "no_data"}

        # Sort by timestamp
        recent_percepts.sort(key=lambda p: p.timestamp)

        # Analyze regime changes
        regimes = []
        for p in recent_percepts:
            if p.llm_latest_decision:
                regimes.append((p.timestamp, p.llm_latest_decision.regime))

        regime_changes = 0
        for i in range(1, len(regimes)):
            if regimes[i][1] != regimes[i-1][1]:
                regime_changes += 1

        # Analyze confidence drift
        confidences = [p.llm_latest_decision.confidence for p in recent_percepts
                       if p.llm_latest_decision]
        confidence_drift = max(confidences) - min(confidences) if confidences else 0

        # Analyze agent agreement
        agreements = [p.perception_consistency_score for p in recent_percepts]
        avg_agreement = sum(agreements) / len(agreements) if agreements else 0

        # Detect perception bias
        perception_gaps = [p.perception_vs_reality_gap for p in recent_percepts]
        avg_gap = sum(perception_gaps) / len(perception_gaps) if perception_gaps else 0

        if avg_gap > 0.2:
            self.stats["perception_bias_detections"] += 1

        return {
            "window_minutes": window_minutes,
            "num_percepts": len(recent_percepts),
            "regime_changes": regime_changes,
            "regime_stability": 1.0 - min(1.0, regime_changes / len(recent_percepts)) if recent_percepts else 0,
            "confidence_drift": confidence_drift,
            "avg_agent_agreement": avg_agreement,
            "perception_vs_reality_gap": avg_gap,
            "perception_bias_detected": avg_gap > 0.2,
        }

    def compare_perception_vs_mechanical(self) -> Dict[str, Any]:
        """
        Compare LLM perception vs mechanical bot reality.

        Detects:
        - Perception bias (LLM thinks differently than mechanical)
        - Prediction accuracy (LLM confident in X, but Y happened)
        - Information gap (LLM doesn't see what mechanical sees)
        """
        latest = self.get_latest_percept()
        if not latest:
            return {"status": "no_data"}

        comparison = {
            "timestamp": latest.timestamp,
            "llm_perception": {},
            "mechanical_reality": {},
            "alignment": {},
            "gaps": [],
        }

        # LLM perception
        if latest.llm_latest_decision:
            comparison["llm_perception"] = {
                "regime": latest.llm_latest_decision.regime,
                "confidence": latest.llm_latest_decision.confidence,
                "action": latest.llm_latest_decision.action,
                "symbol": latest.llm_latest_decision.symbol,
            }

        # Mechanical reality
        if latest.system_summary:
            comparison["mechanical_reality"] = {
                "equity": latest.system_summary.equity,
                "num_open_positions": latest.system_summary.num_open_positions,
                "unrealized_pnl": latest.system_summary.unrealized_pnl,
                "portfolio_heat": latest.system_summary.portfolio_heat,
            }

        # Alignment analysis
        agent_alignments = []
        for agent_name, brain in latest.agent_brains.items():
            alignment = {
                "agent": agent_name,
                "active": brain.is_active,
                "confidence": brain.confidence,
                "accuracy": brain.accuracy,
            }
            agent_alignments.append(alignment)

        comparison["alignment"] = {
            "agent_agreement": latest.perception_consistency_score,
            "agents": agent_alignments,
        }

        # Gaps
        if latest.mechanical_signals and not latest.llm_latest_decision:
            comparison["gaps"].append("Mechanical signals generated but LLM decision missing")

        if latest.pipeline_health and not latest.pipeline_health.all_agents_healthy:
            comparison["gaps"].append(f"Failed agents: {latest.pipeline_health.failed_agents}")

        return comparison

    def get_perception_summary(self) -> Dict[str, Any]:
        """Get summary of current perception state."""
        latest = self.get_latest_percept()
        if not latest:
            return {"status": "no_data"}

        return {
            "timestamp": latest.timestamp,
            "percept_id": latest.percept_id,
            "quality": {
                "perception_quality_score": latest.perception_quality_score,
                "consistency_score": latest.perception_consistency_score,
                "perception_gap": latest.perception_vs_reality_gap,
            },
            "system": {
                "equity": latest.system_summary.equity if latest.system_summary else 0,
                "positions": latest.system_summary.num_open_positions if latest.system_summary else 0,
                "mode": latest.system_summary.mode if latest.system_summary else "unknown",
            },
            "llm": {
                "latest_action": latest.llm_latest_decision.action if latest.llm_latest_decision else "unknown",
                "confidence": latest.llm_latest_decision.confidence if latest.llm_latest_decision else 0,
                "regime": latest.llm_latest_decision.regime if latest.llm_latest_decision else "unknown",
            },
            "agents": {
                "total": len(latest.agent_brains),
                "active": sum(1 for b in latest.agent_brains.values() if b.is_active),
                "avg_confidence": sum(b.confidence for b in latest.agent_brains.values()) / len(latest.agent_brains) if latest.agent_brains else 0,
            },
            "pipeline": {
                "healthy": latest.pipeline_health.all_agents_healthy if latest.pipeline_health else True,
                "latency_ms": latest.pipeline_health.avg_decision_latency_ms if latest.pipeline_health else 0,
            },
        }

    # Helper methods

    def _calculate_perception_quality(self, percept: UnifiedBotPercept) -> float:
        """Calculate how good the perception is."""
        quality = 0.0
        components = 0

        # API data quality
        if percept.system_summary:
            quality += 0.2
            components += 1

        if percept.strategy_summaries:
            quality += 0.2
            components += 1

        if percept.agent_brains:
            quality += 0.2
            components += 1

        if percept.pipeline_health and percept.pipeline_health.all_agents_healthy:
            quality += 0.2
            components += 1

        if percept.llm_latest_decision:
            quality += 0.2
            components += 1

        return quality / 5.0 if components > 0 else 0.0

    def _calculate_agent_consistency(self, percept: UnifiedBotPercept) -> float:
        """Calculate how much agents agree."""
        if not percept.agent_brains:
            return 0.0

        confidences = [b.confidence for b in percept.agent_brains.values()]
        if not confidences:
            return 0.0

        # Consistency = 1.0 if all similar confidence, 0.0 if very different
        max_conf = max(confidences)
        min_conf = min(confidences)
        spread = max_conf - min_conf

        return max(0.0, 1.0 - (spread / 100.0))

    def _calculate_perception_gap(self, percept: UnifiedBotPercept) -> float:
        """Calculate gap between perception and mechanical reality."""
        gap = 0.0

        # If LLM has high confidence but mechanical has losses, that's a gap
        if (percept.llm_latest_decision and percept.system_summary and
            percept.llm_latest_decision.confidence > 70 and
            percept.system_summary.daily_loss_pct > 2):
            gap += 0.3

        # If pipeline is unhealthy but LLM decision exists, that's suspicious
        if (percept.pipeline_health and not percept.pipeline_health.all_agents_healthy and
            percept.llm_latest_decision):
            gap += 0.2

        # If agents disagree but LLM has high confidence, that's a gap
        consistency = self._calculate_agent_consistency(percept)
        if (percept.llm_latest_decision and
            percept.llm_latest_decision.confidence > 70 and
            consistency < 0.5):
            gap += 0.2

        return min(1.0, gap)

    def _calculate_data_freshness(self, percept: UnifiedBotPercept) -> Dict[str, float]:
        """Calculate how fresh each data source is."""
        freshness = {}

        if percept.system_summary:
            freshness["system_summary"] = time.time() - percept.system_summary.timestamp

        if percept.llm_latest_decision:
            freshness["llm_decision"] = time.time() - percept.llm_latest_decision.timestamp

        if percept.agent_brains:
            for role, brain in percept.agent_brains.items():
                freshness[f"agent_{role}"] = time.time() - brain.timestamp

        if percept.pipeline_health:
            freshness["pipeline"] = time.time() - percept.pipeline_health.timestamp

        return freshness

    def _update_evolution(self, percept: UnifiedBotPercept) -> None:
        """Update perception evolution tracking."""
        if not percept.llm_latest_decision or not percept.llm_latest_decision.symbol:
            return

        symbol = percept.llm_latest_decision.symbol
        if symbol not in self.evolution_by_symbol:
            self.evolution_by_symbol[symbol] = PerceptionEvolution(
                symbol=symbol,
                time_window_minutes=60,
            )

        evo = self.evolution_by_symbol[symbol]

        # Add to sequences
        if percept.llm_latest_decision:
            evo.regime_sequence.append((percept.timestamp, percept.llm_latest_decision.regime))
            evo.confidence_sequence.append((percept.timestamp, percept.llm_latest_decision.confidence))

        evo.agent_agreement_trend.append((percept.timestamp, percept.perception_consistency_score))

        evo.num_decisions += 1

        # Track regime changes
        if len(evo.regime_sequence) > 1:
            if evo.regime_sequence[-1][1] != evo.regime_sequence[-2][1]:
                evo.regime_changes += 1

        # Track agent disagreement
        if percept.perception_consistency_score < 0.5:
            evo.agent_disagreement_events += 1

    def _save_percept(self, percept: UnifiedBotPercept) -> None:
        """Persist percept to disk."""
        try:
            with open(self.percepts_file, "a") as f:
                # Only save essential fields to avoid huge file
                data = {
                    "percept_id": percept.percept_id,
                    "timestamp": percept.timestamp,
                    "quality_score": percept.perception_quality_score,
                    "consistency_score": percept.perception_consistency_score,
                    "gap": percept.perception_vs_reality_gap,
                }
                f.write(json.dumps(data) + "\n")
        except Exception as e:
            logger.error(f"Error saving percept: {e}")

    def _load_percepts(self) -> None:
        """Load existing percepts from disk."""
        try:
            if os.path.exists(self.percepts_file):
                with open(self.percepts_file, "r") as f:
                    for line in f:
                        try:
                            # Note: Only metadata is saved, full percepts kept in memory
                            data = json.loads(line)
                            # Could reconstruct if needed
                        except Exception as e:
                            logger.debug(f"Error loading percept: {e}")
        except Exception as e:
            logger.debug(f"Error loading percepts: {e}")


# Global aggregator
_global_aggregator: Optional[BotPerceptionAggregator] = None


def get_bot_perception_aggregator() -> BotPerceptionAggregator:
    """Get or create global aggregator."""
    global _global_aggregator
    if _global_aggregator is None:
        _global_aggregator = BotPerceptionAggregator()
    return _global_aggregator
