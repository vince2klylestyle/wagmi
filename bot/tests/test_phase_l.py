"""Tests for PHASE L: Autonomous Strategy Discovery."""

import os
import sys
import json
import time
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from llm.strategy_discovery.corpus import (
    add_observation, load_observations, get_corpus_summary,
    trim_corpus, PATTERN_TEMPLATES,
)
from llm.strategy_discovery.proposals import (
    StrategyProposal, ProposalStatus,
)
from llm.strategy_discovery.research_agent import (
    build_research_prompt, parse_research_output,
    create_proposals_from_research, save_proposal, load_proposal,
    list_proposals, format_proposals_telegram,
)
from llm.strategy_discovery.sandbox import (
    evaluate_proposal, _compute_metrics, _filter_matching_trades,
)


# ── Corpus Tests ────────────────────────────────────────────


def test_pattern_templates_structure():
    assert len(PATTERN_TEMPLATES) >= 5
    for name, p in PATTERN_TEMPLATES.items():
        assert "description" in p
        assert "entry_conditions" in p
        assert "exit_conditions" in p
        assert "best_regimes" in p


def test_add_and_load_observations(tmp_path, monkeypatch):
    obs_file = str(tmp_path / "obs.jsonl")
    monkeypatch.setattr("llm.strategy_discovery.corpus._OBSERVATIONS_FILE", obs_file)
    monkeypatch.setattr("llm.strategy_discovery.corpus._CORPUS_DIR", str(tmp_path))

    add_observation("trade_outcome", "BTC", "trend", "BTC broke resistance with volume")
    add_observation("anomaly", "ETH", "range", "ETH diverged from BTC")

    obs = load_observations()
    assert len(obs) == 2
    assert obs[0]["category"] == "trade_outcome"
    assert obs[1]["symbol"] == "ETH"


def test_load_observations_filtered(tmp_path, monkeypatch):
    obs_file = str(tmp_path / "obs.jsonl")
    monkeypatch.setattr("llm.strategy_discovery.corpus._OBSERVATIONS_FILE", obs_file)
    monkeypatch.setattr("llm.strategy_discovery.corpus._CORPUS_DIR", str(tmp_path))

    add_observation("trade_outcome", "BTC", "trend", "obs1")
    add_observation("anomaly", "ETH", "range", "obs2")

    assert len(load_observations(category="anomaly")) == 1
    assert len(load_observations(symbol="BTC")) == 1


def test_corpus_summary(tmp_path, monkeypatch):
    obs_file = str(tmp_path / "obs.jsonl")
    monkeypatch.setattr("llm.strategy_discovery.corpus._OBSERVATIONS_FILE", obs_file)
    monkeypatch.setattr("llm.strategy_discovery.corpus._CORPUS_DIR", str(tmp_path))

    add_observation("trade_outcome", "BTC", "trend", "test")
    summary = get_corpus_summary()
    assert summary["total_observations"] == 1
    assert "momentum_breakout" in summary["known_patterns"]


def test_trim_corpus(tmp_path, monkeypatch):
    obs_file = str(tmp_path / "obs.jsonl")
    monkeypatch.setattr("llm.strategy_discovery.corpus._OBSERVATIONS_FILE", obs_file)
    monkeypatch.setattr("llm.strategy_discovery.corpus._CORPUS_DIR", str(tmp_path))

    for i in range(20):
        add_observation("test", "BTC", "trend", f"obs_{i}")

    trimmed = trim_corpus(max_entries=10)
    assert trimmed == 10
    obs = load_observations()
    assert len(obs) == 10


# ── Proposals Tests ─────────────────────────────────────────


def test_proposal_creation():
    p = StrategyProposal(
        proposal_id="test_1",
        name="Test Strategy",
        description="A test",
        rationale="Testing",
        entry_conditions=["price > SMA"],
        exit_conditions=["trailing stop"],
        best_regimes=["trend"],
        avoid_regimes=["panic"],
    )
    assert p.status == ProposalStatus.DRAFT
    assert p.is_safe()


def test_proposal_safety_checks():
    # Too much leverage
    p = StrategyProposal(
        proposal_id="unsafe_1", name="x", description="x", rationale="x",
        entry_conditions=["x"], exit_conditions=["x"],
        best_regimes=[], avoid_regimes=[],
        max_leverage=30.0,
    )
    assert not p.is_safe()

    # No entry conditions
    p2 = StrategyProposal(
        proposal_id="unsafe_2", name="x", description="x", rationale="x",
        entry_conditions=[], exit_conditions=["x"],
        best_regimes=[], avoid_regimes=[],
    )
    assert not p2.is_safe()


def test_proposal_serialization():
    p = StrategyProposal(
        proposal_id="ser_1", name="Momentum", description="desc",
        rationale="reason",
        entry_conditions=["c1"], exit_conditions=["c2"],
        best_regimes=["trend"], avoid_regimes=["panic"],
        status=ProposalStatus.SANDBOX_PASSED,
    )
    d = p.to_dict()
    p2 = StrategyProposal.from_dict(d)
    assert p2.proposal_id == "ser_1"
    assert p2.status == ProposalStatus.SANDBOX_PASSED


# ── Research Agent Tests ────────────────────────────────────


def test_build_research_prompt():
    summary = {
        "total_observations": 5,
        "by_regime": {"trend": 3, "range": 2},
        "known_patterns": ["momentum_breakout"],
        "recent_observations": [
            {"category": "trade_outcome", "symbol": "BTC", "regime": "trend", "observation": "test"},
        ],
    }
    prompt = build_research_prompt(summary)
    assert "STRATEGY RESEARCH AGENT" in prompt
    assert "momentum_breakout" in prompt
    assert "BTC" in prompt


def test_parse_research_output():
    raw = '{"insights": ["BTC is strong"], "proposed_strategies": []}'
    result = parse_research_output(raw)
    assert result["insights"] == ["BTC is strong"]


def test_parse_research_output_invalid():
    result = parse_research_output("not json at all")
    assert "error" in result


def test_create_proposals_from_research(tmp_path, monkeypatch):
    monkeypatch.setattr("llm.strategy_discovery.research_agent._PROPOSALS_DIR", str(tmp_path))
    monkeypatch.setattr("llm.strategy_discovery.corpus._OBSERVATIONS_FILE",
                        str(tmp_path / "obs.jsonl"))
    monkeypatch.setattr("llm.strategy_discovery.corpus._CORPUS_DIR", str(tmp_path))

    research = {
        "insights": ["test insight"],
        "proposed_strategies": [
            {
                "name": "funding_fade",
                "description": "Fade extreme funding",
                "rationale": "Funding mean-reverts",
                "entry_conditions": ["funding > 0.05%"],
                "exit_conditions": ["funding normalizes"],
                "best_regimes": ["range"],
                "avoid_regimes": ["trend"],
                "expected_rr": 1.5,
                "expected_win_rate": 0.55,
            }
        ],
    }
    proposals = create_proposals_from_research(research)
    assert len(proposals) == 1
    assert proposals[0].name == "funding_fade"


def test_save_and_load_proposal(tmp_path, monkeypatch):
    monkeypatch.setattr("llm.strategy_discovery.research_agent._PROPOSALS_DIR", str(tmp_path))

    p = StrategyProposal(
        proposal_id="load_test", name="Test", description="d",
        rationale="r", entry_conditions=["c"], exit_conditions=["c"],
        best_regimes=["trend"], avoid_regimes=[],
    )
    save_proposal(p)
    loaded = load_proposal("load_test")
    assert loaded is not None
    assert loaded.name == "Test"


def test_format_proposals_telegram():
    p = StrategyProposal(
        proposal_id="fmt_1", name="Momentum", description="Buy breakouts",
        rationale="r", entry_conditions=["c"], exit_conditions=["c"],
        best_regimes=["trend"], avoid_regimes=[],
        expected_rr=2.0, expected_win_rate=0.55,
    )
    text = format_proposals_telegram([p])
    assert "Momentum" in text
    assert "trend" in text


# ── Sandbox Tests ───────────────────────────────────────────


def test_filter_matching_trades():
    trades = [
        {"regime": "trend", "symbol": "BTC", "pnl": 100},
        {"regime": "range", "symbol": "ETH", "pnl": -50},
        {"regime": "panic", "symbol": "SOL", "pnl": -200},
    ]
    proposal = StrategyProposal(
        proposal_id="x", name="x", description="x", rationale="x",
        entry_conditions=["x"], exit_conditions=["x"],
        best_regimes=["trend", "range"], avoid_regimes=["panic"],
    )
    matching = _filter_matching_trades(trades, proposal)
    assert len(matching) == 2  # BTC(trend) + ETH(range), not SOL(panic)


def test_compute_metrics():
    trades = [
        {"pnl": 100}, {"pnl": -50}, {"pnl": 200},
        {"pnl": -30}, {"pnl": 150},
    ]
    m = _compute_metrics(trades)
    assert m["total_trades"] == 5
    assert m["wins"] == 3
    assert m["losses"] == 2
    assert m["win_rate"] == 0.6
    assert m["profit_factor"] > 1.0


def test_evaluate_proposal_insufficient_data(tmp_path, monkeypatch):
    monkeypatch.setattr("llm.strategy_discovery.research_agent._PROPOSALS_DIR", str(tmp_path))

    p = StrategyProposal(
        proposal_id="eval_1", name="x", description="x", rationale="x",
        entry_conditions=["x"], exit_conditions=["x"],
        best_regimes=["trend"], avoid_regimes=[],
    )
    result = evaluate_proposal(p, historical_trades=[])
    assert not result["passed"]
    # Accept either "Insufficient" or "Only N matching trades" wording
    assert ("Insufficient" in result["reason"]) or ("matching trades" in result["reason"])
