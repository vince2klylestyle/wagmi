"""
TIER 2.1: Agent Pipeline Visibility

Logs individual agent outputs (Regime, Trade, Risk, Critic, Exit agents)
to enable analysis of multi-agent decision-making.

Currently, only the final merged decision is logged. This module captures
what each agent said, enabling:
  1. Agent accuracy tracking (thesis correctness per agent)
  2. Cross-agent consistency checking (do they agree on regime?)
  3. Bottleneck identification (where do good decisions become bad ones?)
  4. Prompt tuning validation (did prompt change improve accuracy?)

Expected impact: +0.3-0.5% daily through better agent calibration.
"""

import json
import logging
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime
import time

logger = logging.getLogger("bot.llm.agent_output_logger")


@dataclass
class AgentOutput:
    """Output from a single agent in the pipeline."""
    agent_name: str                # "regime", "trade", "risk", "critic", "exit", "scout"
    timestamp: float               # When did this agent run?
    input_context: Dict[str, Any] = field(default_factory=dict)  # What did the agent see?
    reasoning: str = ""            # Agent's reasoning (from thought_protocol)
    decision: str = ""             # Agent's decision/action
    confidence: float = 0.5        # Agent's confidence (0-1)
    metadata: Dict[str, Any] = field(default_factory=dict)  # Extra context
    error: Optional[str] = None    # If agent failed, why?


@dataclass
class AgentPipelineLog:
    """Log of all agents in a single decision cycle."""
    decision_id: str               # Unique ID for this decision
    symbol: str                    # Which symbol?
    timestamp: float               # When was decision made?
    market_regime: Optional[str]   # From regime agent
    trade_thesis: Optional[str]    # From trade agent
    risk_assessment: Optional[str] # From risk agent
    critic_veto: Optional[str]     # From critic agent (if any)
    exit_recommendation: Optional[str] = None  # From exit agent

    # Agent outputs (detailed)
    regime_agent_output: Optional[AgentOutput] = None
    trade_agent_output: Optional[AgentOutput] = None
    risk_agent_output: Optional[AgentOutput] = None
    critic_agent_output: Optional[AgentOutput] = None
    exit_agent_output: Optional[AgentOutput] = None
    scout_agent_output: Optional[AgentOutput] = None

    # Final outcome
    final_decision: str = ""       # What did LLM decide?
    final_confidence: float = 0.5
    veto_applied: bool = False     # Did critic veto override trade agent?

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "decision_id": self.decision_id,
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "market_regime": self.market_regime,
            "trade_thesis": self.trade_thesis,
            "risk_assessment": self.risk_assessment,
            "critic_veto": self.critic_veto,
            "exit_recommendation": self.exit_recommendation,
            "regime_agent_output": asdict(self.regime_agent_output) if self.regime_agent_output else None,
            "trade_agent_output": asdict(self.trade_agent_output) if self.trade_agent_output else None,
            "risk_agent_output": asdict(self.risk_agent_output) if self.risk_agent_output else None,
            "critic_agent_output": asdict(self.critic_agent_output) if self.critic_agent_output else None,
            "exit_agent_output": asdict(self.exit_agent_output) if self.exit_agent_output else None,
            "scout_agent_output": asdict(self.scout_agent_output) if self.scout_agent_output else None,
            "final_decision": self.final_decision,
            "final_confidence": self.final_confidence,
            "veto_applied": self.veto_applied,
        }


class AgentOutputLogger:
    """
    Logs individual agent outputs for analysis and auditing.

    Writes to: bot/data/llm/agent_outputs.jsonl (append-only log)
    """

    def __init__(self, output_dir: str = "data/llm"):
        """
        Args:
            output_dir: Directory for storing logs
        """
        self.output_dir = output_dir
        self.output_file = os.path.join(output_dir, "agent_outputs.jsonl")
        os.makedirs(output_dir, exist_ok=True)

        # In-memory cache for quick access
        self.recent_logs: List[AgentPipelineLog] = []
        self._load_recent_logs()

    def _load_recent_logs(self) -> None:
        """Load recent logs from disk."""
        if not os.path.exists(self.output_file):
            return

        try:
            with open(self.output_file, "r") as f:
                lines = f.readlines()
                # Keep last 100 logs in memory
                for line in lines[-100:]:
                    try:
                        data = json.loads(line.strip())
                        # Convert back to dataclass
                        log = AgentPipelineLog(
                            decision_id=data["decision_id"],
                            symbol=data["symbol"],
                            timestamp=data["timestamp"],
                            market_regime=data.get("market_regime"),
                            trade_thesis=data.get("trade_thesis"),
                            risk_assessment=data.get("risk_assessment"),
                            critic_veto=data.get("critic_veto"),
                            exit_recommendation=data.get("exit_recommendation"),
                            final_decision=data.get("final_decision", ""),
                            final_confidence=data.get("final_confidence", 0.5),
                            veto_applied=data.get("veto_applied", False),
                        )
                        self.recent_logs.append(log)
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Failed to load recent agent logs: {e}")

    def log_pipeline(self, pipeline_log: AgentPipelineLog) -> None:
        """
        Log a complete agent pipeline execution.

        Args:
            pipeline_log: AgentPipelineLog with all agent outputs
        """
        # Store in memory
        self.recent_logs.append(pipeline_log)
        if len(self.recent_logs) > 1000:
            self.recent_logs = self.recent_logs[-1000:]

        # Write to disk (append-only)
        try:
            with open(self.output_file, "a") as f:
                f.write(json.dumps(pipeline_log.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"Failed to log agent pipeline: {e}")

    def log_agent_output(
        self,
        decision_id: str,
        agent_name: str,
        output: AgentOutput,
    ) -> None:
        """
        Log a single agent's output.

        Args:
            decision_id: ID of the decision this output belongs to
            agent_name: Name of the agent
            output: AgentOutput from that agent
        """
        # Find the pipeline log for this decision
        log = None
        for l in reversed(self.recent_logs):
            if l.decision_id == decision_id:
                log = l
                break

        if not log:
            logger.warning(f"No pipeline log found for decision {decision_id}")
            return

        # Attach output to pipeline log
        if agent_name == "regime":
            log.regime_agent_output = output
            log.market_regime = output.decision
        elif agent_name == "trade":
            log.trade_agent_output = output
            log.trade_thesis = output.decision
        elif agent_name == "risk":
            log.risk_agent_output = output
            log.risk_assessment = output.decision
        elif agent_name == "critic":
            log.critic_agent_output = output
            log.critic_veto = output.decision
        elif agent_name == "exit":
            log.exit_agent_output = output
            log.exit_recommendation = output.decision
        elif agent_name == "scout":
            log.scout_agent_output = output

        # Re-write the updated log (this is a simplification;
        # in production, use a proper update mechanism)

    def get_recent_logs(self, limit: int = 100) -> List[AgentPipelineLog]:
        """Get recent agent pipeline logs."""
        return self.recent_logs[-limit:]

    def get_logs_by_agent(self, agent_name: str, limit: int = 50) -> List[Dict]:
        """Get recent outputs from a specific agent."""
        results = []
        for log in self.recent_logs[-limit:]:
            output = None
            if agent_name == "regime":
                output = log.regime_agent_output
            elif agent_name == "trade":
                output = log.trade_agent_output
            elif agent_name == "risk":
                output = log.risk_agent_output
            elif agent_name == "critic":
                output = log.critic_agent_output
            elif agent_name == "exit":
                output = log.exit_agent_output
            elif agent_name == "scout":
                output = log.scout_agent_output

            if output:
                results.append({
                    "decision_id": log.decision_id,
                    "symbol": log.symbol,
                    "timestamp": log.timestamp,
                    "agent_output": asdict(output),
                })

        return results

    def get_agent_consistency_report(self) -> Dict[str, Any]:
        """
        Analyze cross-agent consistency.

        Returns:
            Report showing:
            - Do all agents agree on the regime?
            - Does critic agree with trade agent?
            - Are there systematic disagreements?
        """
        if not self.recent_logs:
            return {"status": "no_data"}

        recent = self.recent_logs[-50:]

        # Check regime agreement
        regimes_seen = {}
        trade_vetoed_count = 0
        critic_confident_count = 0

        for log in recent:
            if log.regime_agent_output and log.regime_agent_output.decision:
                regime = log.regime_agent_output.decision
                regimes_seen[regime] = regimes_seen.get(regime, 0) + 1

            if log.veto_applied and log.critic_agent_output:
                trade_vetoed_count += 1

            if log.critic_agent_output and log.critic_agent_output.confidence > 0.7:
                critic_confident_count += 1

        return {
            "regimes_identified": regimes_seen,
            "trade_vetoes": {
                "count": trade_vetoed_count,
                "veto_rate": trade_vetoed_count / len(recent) if recent else 0,
            },
            "critic_confidence": {
                "high_confidence_count": critic_confident_count,
                "high_confidence_rate": critic_confident_count / len(recent) if recent else 0,
            },
        }


# Global logger instance
_global_logger: Optional[AgentOutputLogger] = None


def get_agent_output_logger() -> AgentOutputLogger:
    """Get or create the global agent output logger."""
    global _global_logger
    if _global_logger is None:
        _global_logger = AgentOutputLogger()
    return _global_logger
