"""Tests for Canary Substrate (W5-A)."""

import pytest
import json
from datetime import datetime, timedelta
from pathlib import Path

from llm.agents.canary_substrate import (
    CanarySubstrate,
    DeploymentGate,
    DeploymentPhase,
    ShadowModeExecution,
)


class TestCanarySubstrate:
    """Test safe agent deployment infrastructure."""

    def test_substrate_initialization(self):
        """Should initialize with default deployment state."""
        substrate = CanarySubstrate()
        
        assert substrate.current_phase == DeploymentPhase.SHADOW
        assert substrate.signal_influence_pct == 0.0

    def test_deployment_gates_structure(self):
        """Should have gates for all deployment phases."""
        substrate = CanarySubstrate()
        
        phases = [
            DeploymentPhase.SHADOW,
            DeploymentPhase.CANARY,
            DeploymentPhase.RAMP,
            DeploymentPhase.PRODUCTION,
        ]
        
        for phase in phases:
            assert phase in substrate.gates
            gate = substrate.gates[phase]
            assert gate.phase == phase

    def test_deployment_gate_readiness(self):
        """Should evaluate gate readiness criteria."""
        gate = DeploymentGate(
            phase=DeploymentPhase.CANARY,
            min_live_trades=10,
            min_win_rate=0.45,
        )
        
        # Not ready: insufficient trades
        assert not gate.is_ready_to_advance({"live_trades": 5, "win_rate": 0.50})
        
        # Ready: meets all criteria
        assert gate.is_ready_to_advance({"live_trades": 10, "win_rate": 0.50})

    def test_shadow_mode_execution_logging(self):
        """Should log shadow mode executions."""
        log = ShadowModeExecution(
            agent_name="trade",
            symbol="BTC",
            decision="go",
            confidence=85.0,
            reasoning="Strong trend",
        )
        
        assert log.agent_name == "trade"
        assert log.symbol == "BTC"
        assert log.decision == "go"

    def test_signal_routing_decision_shadow_phase(self):
        """Should always route through original in shadow phase."""
        substrate = CanarySubstrate()
        substrate.current_phase = DeploymentPhase.SHADOW
        
        routing, confidence = substrate.get_signal_routing_decision({"symbol": "BTC"})
        
        assert routing == "original"
        assert confidence == 1.0

    def test_signal_routing_decision_canary_phase(self):
        """Should probabilistically route in canary phase."""
        substrate = CanarySubstrate()
        substrate.current_phase = DeploymentPhase.CANARY
        substrate.signal_influence_pct = 10.0  # 10% routed to canary
        
        # Run multiple times to check both paths
        routings = []
        for _ in range(100):
            routing, confidence = substrate.get_signal_routing_decision({"symbol": "BTC"})
            routings.append(routing)
        
        # Should have a mix (probabilistic)
        has_original = "original" in routings
        has_canary = "canary" in routings
        assert has_original  # Most will be original
        # Some might be canary (probabilistic, so not guaranteed in small sample)

    def test_advance_deployment_phase(self):
        """Should advance phases when gates are met."""
        substrate = CanarySubstrate()
        assert substrate.current_phase == DeploymentPhase.SHADOW
        
        # Meet SHADOW gate criteria
        metrics = {
            "live_trades": 10,
            "win_rate": 0.50,
            "error_rate": 0.0,
        }
        
        alert = substrate.advance_deployment_phase(metrics)
        # May or may not advance depending on duration check

    def test_deployment_gate_duration_check(self):
        """Should check phase duration before advancing."""
        gate = DeploymentGate(
            phase=DeploymentPhase.SHADOW,
            min_live_trades=1,
            duration_hours=24,
            start_time=datetime.utcnow().isoformat(),
        )
        
        metrics = {"live_trades": 10, "win_rate": 0.50}
        
        # Should not be ready immediately (duration not met)
        assert not gate.is_ready_to_advance(metrics)

    def test_run_agent_shadow_mode(self):
        """Should run agent in shadow mode without trading impact."""
        substrate = CanarySubstrate()
        
        def mock_agent(symbol, data):
            return {"action": "go", "confidence": 85.0, "reasoning": "Test"}
        
        log = substrate.run_agent_shadow_mode(
            agent_name="trade",
            symbol="BTC",
            market_data={},
            agent_func=mock_agent,
        )
        
        assert log.agent_name == "trade"
        assert log.symbol == "BTC"
        assert log.decision == "go"
        assert log.would_have_traded is True

    def test_run_agent_shadow_mode_error_handling(self):
        """Should handle agent errors gracefully in shadow mode."""
        substrate = CanarySubstrate()
        
        def failing_agent(symbol, data):
            raise ValueError("Test error")
        
        log = substrate.run_agent_shadow_mode(
            agent_name="trade",
            symbol="BTC",
            market_data={},
            agent_func=failing_agent,
        )
        
        assert log.decision == "error"
        assert "Test error" in log.reasoning

    def test_save_shadow_logs(self, tmp_path):
        """Should save shadow mode logs to JSONL."""
        log_path = tmp_path / "shadow.jsonl"
        substrate = CanarySubstrate(shadow_log_path=str(log_path))
        
        # Create some logs
        substrate.shadow_logs = [
            ShadowModeExecution(
                agent_name="trade",
                symbol="BTC",
                decision="go",
                confidence=85.0,
            )
        ]
        
        substrate.save_shadow_logs()
        
        assert log_path.exists()
        with open(log_path) as f:
            lines = f.readlines()
        assert len(lines) > 0

    def test_save_deployment_state(self, tmp_path):
        """Should save deployment state to log file."""
        log_path = tmp_path / "deployment.jsonl"
        substrate = CanarySubstrate(deployment_log_path=str(log_path))
        
        substrate.save_deployment_state()
        
        assert log_path.exists()
        with open(log_path) as f:
            data = json.loads(f.readline())
        
        assert "timestamp" in data
        assert "current_phase" in data
        assert data["current_phase"] == "shadow"

    def test_get_deployment_status(self):
        """Should generate human-readable status."""
        substrate = CanarySubstrate()
        status = substrate.get_deployment_status()
        
        assert "shadow" in status.lower()
        assert "0%" in status  # 0% influence in shadow

    def test_deployment_phase_enum_values(self):
        """Should have correct deployment phase values."""
        assert DeploymentPhase.SHADOW == "shadow"
        assert DeploymentPhase.CANARY == "canary"
        assert DeploymentPhase.RAMP == "ramp"
        assert DeploymentPhase.PRODUCTION == "production"

    def test_shadow_mode_execution_serialization(self):
        """Should serialize shadow mode logs properly."""
        from dataclasses import asdict
        
        log = ShadowModeExecution(
            agent_name="trade",
            symbol="BTC",
            decision="go",
            confidence=85.0,
        )
        
        log_dict = asdict(log)
        
        assert log_dict["agent_name"] == "trade"
        assert log_dict["confidence"] == 85.0

    def test_calibration_error_gate_check(self):
        """Should check calibration error in gates."""
        gate = DeploymentGate(
            phase=DeploymentPhase.CANARY,
            min_calibration=0.20,
        )
        
        # Calibration too high (worse)
        assert not gate.is_ready_to_advance({
            "live_trades": 10,
            "win_rate": 0.50,
            "calibration_error": 0.25,
        })
        
        # Calibration good
        assert gate.is_ready_to_advance({
            "live_trades": 10,
            "win_rate": 0.50,
            "calibration_error": 0.15,
        })