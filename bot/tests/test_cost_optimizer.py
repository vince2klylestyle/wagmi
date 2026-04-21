"""
Smoke tests for llm/agents/cost_optimizer.py.

Covers:
- AgentCostOptimizer init / budget gating
- Pipeline selection (fast_path / standard / full / deep)
- Cost + outcome recording + ROI analytics
- Budget exhaustion
- State serialization round-trip via file path redirection
- Model routing helpers
- Signal importance classification
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

import llm.agents.cost_optimizer as cost_mod
from llm.agents.cost_optimizer import (
    AgentCostOptimizer,
    PIPELINE_CONFIGS,
    MODEL_HAIKU,
    MODEL_SONNET,
    get_optimal_model,
    classify_signal_importance,
    get_cost_optimizer,
)


@pytest.fixture
def tmp_data_path(monkeypatch, tmp_path):
    """Redirect DATA_PATH to a temp file so tests don't touch real data."""
    p = tmp_path / "agent_costs.json"
    monkeypatch.setattr(cost_mod, "DATA_PATH", p)
    # Reset module singleton as well
    monkeypatch.setattr(cost_mod, "_optimizer", None)
    return p


# ── Init ─────────────────────────────────────────────────────


class TestInit:
    def test_constructor_defaults(self, tmp_data_path):
        opt = AgentCostOptimizer()
        assert opt.daily_budget == 0.50
        assert opt.min_roi == 2.0
        assert "today_spend" in opt.state
        assert opt.state["today_spend"] == 0.0

    def test_constructor_custom(self, tmp_data_path):
        opt = AgentCostOptimizer(daily_budget_usd=1.0, min_roi_threshold=3.0)
        assert opt.daily_budget == 1.0
        assert opt.min_roi == 3.0

    def test_loads_corrupt_state(self, tmp_data_path):
        tmp_data_path.write_text("not json")
        # Should recover with empty state
        opt = AgentCostOptimizer()
        assert opt.state["today_spend"] == 0.0


# ── should_call_agents decision matrix ───────────────────────


class TestShouldCallAgents:
    def test_low_conf_no_agree_rejected(self, tmp_data_path):
        opt = AgentCostOptimizer(daily_budget_usd=1.0)
        call, reason = opt.should_call_agents(
            signal_confidence=20, num_strategies_agree=0, regime="trend"
        )
        assert call is False
        assert reason == "below_threshold"

    def test_budget_exhausted(self, tmp_data_path):
        opt = AgentCostOptimizer(daily_budget_usd=1.0)
        opt.state["today_spend"] = 1.0  # used full budget
        call, reason = opt.should_call_agents(
            signal_confidence=70, num_strategies_agree=2, regime="trend"
        )
        assert call is False
        assert reason == "budget_exhausted"

    def test_panic_triggers_deep(self, tmp_data_path):
        opt = AgentCostOptimizer(daily_budget_usd=1.0)
        call, reason = opt.should_call_agents(
            signal_confidence=60, num_strategies_agree=2, regime="panic"
        )
        assert call is True
        # Either deep_analysis or full_pipeline depending on remaining budget
        assert reason in ("deep_analysis", "full_pipeline")

    def test_very_high_conf_fast_path(self, tmp_data_path):
        opt = AgentCostOptimizer(daily_budget_usd=1.0)
        call, reason = opt.should_call_agents(
            signal_confidence=85, num_strategies_agree=4, regime="trend"
        )
        assert call is True
        assert reason == "fast_path"

    def test_borderline_uses_full_pipeline(self, tmp_data_path):
        opt = AgentCostOptimizer(daily_budget_usd=1.0)
        call, reason = opt.should_call_agents(
            signal_confidence=55, num_strategies_agree=1, regime="trend"
        )
        assert call is True
        # Borderline hits full_pipeline when budget permits
        assert reason in ("full_pipeline", "standard", "fast_path")

    def test_high_conf_standard(self, tmp_data_path):
        opt = AgentCostOptimizer(daily_budget_usd=1.0)
        call, reason = opt.should_call_agents(
            signal_confidence=70, num_strategies_agree=2, regime="trend"
        )
        assert call is True
        assert reason in ("standard", "fast_path")


# ── Pipeline config ──────────────────────────────────────────


class TestPipelineConfig:
    def test_all_pipelines_valid(self, tmp_data_path):
        opt = AgentCostOptimizer()
        for name in ("fast_path", "standard", "full_pipeline", "deep_analysis"):
            cfg = opt.get_pipeline_config(name)
            assert "agents" in cfg
            assert "models" in cfg
            assert cfg["estimated_cost"] > 0
            assert cfg["timeout_s"] > 0

    def test_unknown_pipeline_defaults(self, tmp_data_path):
        opt = AgentCostOptimizer()
        cfg = opt.get_pipeline_config("does_not_exist")
        # Falls back to "standard"
        assert cfg["estimated_cost"] == PIPELINE_CONFIGS["standard"]["estimated_cost"]


# ── Cost / outcome recording ─────────────────────────────────


class TestRecording:
    def test_record_cost_updates_state(self, tmp_data_path):
        opt = AgentCostOptimizer()
        opt.record_cost("standard", 0.005)
        assert opt.state["today_spend"] == pytest.approx(0.005)
        assert opt.state["today_calls"] == 1
        assert opt.state["lifetime"]["total_spend"] == pytest.approx(0.005)
        pp = opt.state["per_pipeline"]["standard"]
        assert pp["calls"] == 1
        assert pp["cost"] == pytest.approx(0.005)

    def test_record_outcome_accumulates(self, tmp_data_path):
        opt = AgentCostOptimizer()
        opt.record_cost("standard", 0.005)
        opt.record_outcome("standard", 0.10)
        assert opt.state["lifetime"]["total_profit"] == pytest.approx(0.10)
        assert opt.state["per_pipeline"]["standard"]["profit"] == pytest.approx(0.10)

    def test_record_agent_cost(self, tmp_data_path):
        opt = AgentCostOptimizer()
        opt.record_agent_cost("trade", 0.003)
        opt.record_agent_cost("trade", 0.003)
        assert opt.state["per_agent"]["trade"]["calls"] == 2
        assert opt.state["per_agent"]["trade"]["cost"] == pytest.approx(0.006)


# ── ROI analytics ────────────────────────────────────────────


class TestROI:
    def test_roi_stats_empty(self, tmp_data_path):
        opt = AgentCostOptimizer(daily_budget_usd=0.50)
        stats = opt.get_roi_stats()
        assert "daily_spend" in stats
        assert "overall_roi" in stats
        assert stats["overall_roi"] == 0.0
        assert stats["total_spend"] == 0.0

    def test_roi_stats_after_trading(self, tmp_data_path):
        opt = AgentCostOptimizer(daily_budget_usd=0.50)
        opt.record_cost("standard", 0.01)
        opt.record_outcome("standard", 0.20)
        stats = opt.get_roi_stats()
        # Profit 0.20 / cost 0.01 = 20x
        assert stats["overall_roi"] > 15

    def test_budget_status_format(self, tmp_data_path):
        opt = AgentCostOptimizer(daily_budget_usd=0.50)
        s = opt.get_budget_status()
        assert isinstance(s, str)
        assert "$" in s
        assert "ROI" in s

    def test_format_for_overseer(self, tmp_data_path):
        opt = AgentCostOptimizer()
        opt.record_cost("standard", 0.005)
        opt.record_outcome("standard", 0.05)
        report = opt.format_for_overseer()
        assert "COST OPTIMIZER REPORT" in report
        assert "standard" in report


# ── Persistence round-trip ───────────────────────────────────


class TestPersistence:
    def test_save_reload(self, tmp_data_path):
        opt = AgentCostOptimizer(daily_budget_usd=0.50)
        opt.record_cost("fast_path", 0.0004)
        opt.record_outcome("fast_path", 0.02)
        # New instance, same path
        opt2 = AgentCostOptimizer(daily_budget_usd=0.50)
        assert opt2.state["lifetime"]["total_spend"] == pytest.approx(0.0004)
        assert opt2.state["per_pipeline"]["fast_path"]["calls"] == 1

    def test_saved_file_valid_json(self, tmp_data_path):
        opt = AgentCostOptimizer()
        opt.record_cost("standard", 0.005)
        data = json.loads(tmp_data_path.read_text())
        assert data["today_spend"] == pytest.approx(0.005)


# ── Module helpers ───────────────────────────────────────────


class TestModelRouting:
    def test_regime_always_haiku(self):
        assert get_optimal_model("regime", "high", 0.5) == MODEL_HAIKU
        assert get_optimal_model("risk", "high", 0.5) == MODEL_HAIKU
        assert get_optimal_model("quant", "high", 0.5) == MODEL_HAIKU

    def test_trade_sonnet_on_high(self):
        assert get_optimal_model("trade", "high", 0.8) == MODEL_SONNET

    def test_trade_haiku_when_accurate(self):
        # Low importance + high accuracy = cheap
        assert get_optimal_model("trade", "low", 0.80) == MODEL_HAIKU

    def test_trade_upgrades_on_low_accuracy(self):
        assert get_optimal_model("trade", "borderline", 0.40) == MODEL_SONNET

    def test_overseer_always_haiku(self):
        assert get_optimal_model("overseer", "high", 0.9) == MODEL_HAIKU

    def test_default_unknown_agent(self):
        assert get_optimal_model("unknown_agent", "low", 0.5) == MODEL_HAIKU


class TestClassifySignalImportance:
    def test_panic_is_high(self):
        assert classify_signal_importance(50, 2, "panic") == "high"

    def test_news_is_high(self):
        assert classify_signal_importance(50, 2, "news_dislocation") == "high"

    def test_very_clear_signal_low(self):
        assert classify_signal_importance(90, 4, "trend") == "low"

    def test_garbage_signal_low(self):
        assert classify_signal_importance(30, 0, "trend") == "low"

    def test_borderline_range(self):
        assert classify_signal_importance(60, 1, "trend") == "borderline"


class TestSingleton:
    def test_singleton_returns_same_instance(self, tmp_data_path):
        a = get_cost_optimizer(daily_budget=0.5)
        b = get_cost_optimizer(daily_budget=0.5)
        assert a is b
