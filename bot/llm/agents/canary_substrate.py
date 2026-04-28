"""Canary Substrate (W5) — Safe agent deployment infrastructure.

Shadow Mode: Run agents in parallel without trading impact.
Deployment Gates: Gradual rollout with quality gates.
A/B Testing: Split signals between original and new agents.
Gradual Rollout: Ramp up agent influence from 0% → 100% over time.
"""

import json
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class DeploymentPhase(str, Enum):
    """Deployment progression phases."""

    SHADOW = "shadow"  # 0% influence: run agents, log, don't trade
    CANARY = "canary"  # 1-10% influence: route small % of signals to new agents
    RAMP = "ramp"  # 10-50% influence: gradually increase agent influence
    PRODUCTION = "production"  # 100% influence: agents fully control signals


@dataclass
class DeploymentGate:
    """Control gate for agent deployment progression."""

    phase: DeploymentPhase
    min_live_trades: int = 0  # Must have N trades in current phase before advancing
    min_win_rate: float = 0.0  # Must achieve WR before advancing
    max_error_rate: float = 1.0  # Must have error rate <= this
    min_calibration: float = -1.0  # Calibration error must be <= this (-1 = no check)
    signal_influence_pct: float = 0.0  # % of signals routed to new agents (0-100)
    
    duration_hours: int = 24  # How long to stay in this phase before advancing
    start_time: Optional[str] = None  # ISO timestamp when phase started
    
    def is_ready_to_advance(self, metrics: Dict[str, Any]) -> bool:
        """Check if gate criteria are met to advance to next phase."""
        # Check trade count
        if metrics.get("live_trades", 0) < self.min_live_trades:
            return False
        
        # Check win rate
        if metrics.get("win_rate", 0.0) < self.min_win_rate:
            return False
        
        # Check error rate
        if metrics.get("error_rate", 1.0) > self.max_error_rate:
            return False
        
        # Check calibration
        if self.min_calibration >= 0:
            if metrics.get("calibration_error", 1.0) > self.min_calibration:
                return False
        
        # Check duration
        if self.start_time:
            elapsed = datetime.utcnow() - datetime.fromisoformat(self.start_time)
            if elapsed < timedelta(hours=self.duration_hours):
                return False
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return asdict(self)


@dataclass
class ShadowModeExecution:
    """Log entry for shadow mode (agent run without trading impact)."""

    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    agent_name: str = ""  # Which agent made this decision
    symbol: str = ""
    decision: str = ""  # "go", "skip", "flip"
    confidence: float = 0.0
    reasoning: str = ""
    
    # What would have happened vs what actually happened
    would_have_traded: bool = False  # Would agent decision have resulted in trade?
    actual_trade: bool = False  # Did signal actually lead to trade?
    match: bool = False  # Did agent agree with actual decision?


class CanarySubstrate:
    """Safe deployment infrastructure for new agents."""

    def __init__(
        self,
        deployment_log_path: str = "bot/data/llm/canary_deployment.jsonl",
        shadow_log_path: str = "bot/data/llm/shadow_mode.jsonl",
    ):
        self.deployment_log_path = Path(deployment_log_path)
        self.shadow_log_path = Path(shadow_log_path)
        
        # Current deployment state
        self.current_phase = DeploymentPhase.SHADOW
        self.signal_influence_pct = 0.0  # Current agent influence %
        self.phase_start_time = datetime.utcnow()
        
        # Gates for each phase
        self.gates = self._init_gates()
        
        # Shadow mode logs
        self.shadow_logs: List[ShadowModeExecution] = []

    def run_agent_shadow_mode(
        self,
        agent_name: str,
        symbol: str,
        market_data: Dict[str, Any],
        agent_func,
    ) -> ShadowModeExecution:
        """Run agent in shadow mode (no trading impact, log only).

        Args:
            agent_name: Name of agent ("trade", "risk", "critic", etc.)
            symbol: Trading symbol
            market_data: Current market data
            agent_func: Function to call to run agent

        Returns:
            ShadowModeExecution log entry
        """
        try:
            # Run agent in parallel (doesn't affect actual signal)
            result = agent_func(symbol, market_data)
            
            log = ShadowModeExecution(
                agent_name=agent_name,
                symbol=symbol,
                decision=result.get("action", "unknown"),
                confidence=result.get("confidence", 0.0),
                reasoning=result.get("reasoning", ""),
                would_have_traded=result.get("action") == "go",
            )
            
            self.shadow_logs.append(log)
            return log
            
        except Exception as e:
            logger.error(f"[SHADOW] {agent_name} failed: {e}")
            return ShadowModeExecution(
                agent_name=agent_name,
                symbol=symbol,
                decision="error",
                reasoning=str(e),
            )

    def get_signal_routing_decision(self, signal: Dict[str, Any]) -> Tuple[str, float]:
        """Decide whether to route signal through new agent pipeline.

        Args:
            signal: Original signal object

        Returns:
            (routing_decision, confidence) where routing_decision is "original" or "canary"
        """
        if self.current_phase == DeploymentPhase.SHADOW:
            return ("original", 1.0)  # Always original, no canary influence
        
        # Probabilistically route based on current influence %
        import random
        if random.random() < (self.signal_influence_pct / 100.0):
            return ("canary", 0.5)  # Downweight canary signal confidence
        else:
            return ("original", 1.0)

    def advance_deployment_phase(self, metrics: Dict[str, Any]) -> Optional[str]:
        """Check if ready to advance deployment phase.

        Args:
            metrics: Current performance metrics

        Returns:
            Alert message if advancing, None if staying in current phase
        """
        gate = self.gates[self.current_phase]
        
        if not gate.is_ready_to_advance(metrics):
            return None
        
        # Advance to next phase
        phase_order = [
            DeploymentPhase.SHADOW,
            DeploymentPhase.CANARY,
            DeploymentPhase.RAMP,
            DeploymentPhase.PRODUCTION,
        ]
        
        current_idx = phase_order.index(self.current_phase)
        if current_idx < len(phase_order) - 1:
            next_phase = phase_order[current_idx + 1]
            self.current_phase = next_phase
            self.phase_start_time = datetime.utcnow()
            
            # Update influence %
            self.signal_influence_pct = self.gates[next_phase].signal_influence_pct
            
            alert = f"ADVANCED: {self.current_phase.value} → {next_phase.value} ({self.signal_influence_pct:.0f}% influence)"
            logger.info(f"[CANARY] {alert}")
            return alert
        
        return None

    def save_shadow_logs(self) -> None:
        """Save shadow mode logs to JSONL."""
        self.shadow_log_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.shadow_log_path, "a") as f:
            for log in self.shadow_logs:
                f.write(json.dumps(asdict(log)) + "\n")
        
        logger.info(f"[SHADOW] Saved {len(self.shadow_logs)} logs to {self.shadow_log_path}")
        self.shadow_logs = []

    def save_deployment_state(self) -> None:
        """Save current deployment state."""
        self.deployment_log_path.parent.mkdir(parents=True, exist_ok=True)
        
        state = {
            "timestamp": datetime.utcnow().isoformat(),
            "current_phase": self.current_phase.value,
            "signal_influence_pct": self.signal_influence_pct,
            "phase_start_time": self.phase_start_time.isoformat(),
            "gates": {
                phase.value: gate.to_dict()
                for phase, gate in self.gates.items()
            },
        }
        
        with open(self.deployment_log_path, "a") as f:
            f.write(json.dumps(state) + "\n")

    def get_deployment_status(self) -> str:
        """Get human-readable deployment status."""
        return (
            f"Phase: {self.current_phase.value} | "
            f"Influence: {self.signal_influence_pct:.0f}% | "
            f"Duration: {(datetime.utcnow() - self.phase_start_time).seconds // 3600}h"
        )

    # Private helper methods

    def _init_gates(self) -> Dict[DeploymentPhase, DeploymentGate]:
        """Initialize deployment gates for each phase."""
        return {
            DeploymentPhase.SHADOW: DeploymentGate(
                phase=DeploymentPhase.SHADOW,
                min_live_trades=1,
                min_win_rate=0.0,
                max_error_rate=1.0,
                signal_influence_pct=0.0,
                duration_hours=24,
            ),
            DeploymentPhase.CANARY: DeploymentGate(
                phase=DeploymentPhase.CANARY,
                min_live_trades=10,
                min_win_rate=0.45,
                max_error_rate=0.05,
                min_calibration=0.20,
                signal_influence_pct=0.05,
                duration_hours=48,
            ),
            DeploymentPhase.RAMP: DeploymentGate(
                phase=DeploymentPhase.RAMP,
                min_live_trades=50,
                min_win_rate=0.48,
                max_error_rate=0.02,
                min_calibration=0.15,
                signal_influence_pct=0.50,
                duration_hours=72,
            ),
            DeploymentPhase.PRODUCTION: DeploymentGate(
                phase=DeploymentPhase.PRODUCTION,
                min_live_trades=100,
                min_win_rate=0.50,
                max_error_rate=0.01,
                min_calibration=0.10,
                signal_influence_pct=1.0,
                duration_hours=0,  # No time requirement for production
            ),
        }


def get_canary_substrate() -> CanarySubstrate:
    """Get or create a CanarySubstrate instance."""
    return CanarySubstrate()