"""
Smoke tests for llm/learning_integrator.py.

Covers:
  - Constructor / singleton
  - Happy-path dispatch_proposal
  - Empty / None input handling
  - tick() rate-limiting
  - get_enriched_llm_context() no-crash
  - on_trade_closed() no-crash
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from llm.learning_integrator import LearningIntegrator, get_learning_integrator


class FakeProposal:
    """Minimal stand-in for SelfImprovementProposal."""

    def __init__(self, action=None, title="test"):
        self.suggested_action = action
        self.title = title


# ── Constructor / singleton ─────────────────────────────

def test_construct():
    li = LearningIntegrator()
    assert li is not None
    assert li._last_tick_time == 0
    assert li._tick_interval_s > 0


def test_singleton_returns_same_instance():
    a = get_learning_integrator()
    b = get_learning_integrator()
    assert a is b


# ── dispatch_proposal happy-path ────────────────────────

def test_dispatch_proposal_empty_action():
    li = LearningIntegrator()
    p = FakeProposal(action=None)
    assert li.dispatch_proposal(p) is False


def test_dispatch_proposal_empty_dict():
    li = LearningIntegrator()
    p = FakeProposal(action={})
    assert li.dispatch_proposal(p) is False


def test_dispatch_proposal_unknown_action():
    li = LearningIntegrator()
    p = FakeProposal(action={"parameter": "nonexistent_foo", "proposed": 1.0})
    result = li.dispatch_proposal(p)
    # Should return False without raising
    assert result is False


def test_dispatch_proposal_max_leverage_never_auto_applies():
    li = LearningIntegrator()
    p = FakeProposal(action={"parameter": "max_leverage", "proposed": 5})
    # Max leverage is never auto-applied per the implementation
    assert li.dispatch_proposal(p) is False


def test_dispatch_proposal_symbol_pause_never_auto_applies():
    li = LearningIntegrator()
    p = FakeProposal(action={"action": "pause_symbol", "symbol": "BTC"})
    assert li.dispatch_proposal(p) is False


def test_dispatch_proposal_weight_adjustment_noop_when_multiplier_is_one():
    li = LearningIntegrator()
    p = FakeProposal(action={
        "action": "adjust_weight",
        "strategy": "regime_trend",
        "weight_multiplier": 1.0,
    })
    assert li.dispatch_proposal(p) is False


def test_dispatch_proposal_weight_adjustment_missing_strategy():
    li = LearningIntegrator()
    p = FakeProposal(action={
        "action": "adjust_weight",
        "strategy": "",
        "weight_multiplier": 1.2,
    })
    assert li.dispatch_proposal(p) is False


# ── validate_insights_from_trade ────────────────────────

def test_validate_insights_empty_trade_data():
    li = LearningIntegrator()
    # Should not crash on empty trade data
    li.validate_insights_from_trade({})


def test_validate_insights_missing_fields():
    li = LearningIntegrator()
    # Fields missing should not crash
    li.validate_insights_from_trade({"symbol": "BTC"})


# ── tick() rate limiting ────────────────────────────────

def test_tick_rate_limited():
    """tick() should be a no-op on rapid consecutive calls."""
    li = LearningIntegrator()
    # Force last-tick-time to now so that tick is suppressed
    li._last_tick_time = time.time()
    # Invoke tick — should return quickly without touching the interval work
    before = li._last_evolution_feed
    li.tick()
    after = li._last_evolution_feed
    # Nothing should have been scheduled because of rate limit
    assert after == before


# ── on_trade_closed no-crash ────────────────────────────

def test_on_trade_closed_smoke():
    li = LearningIntegrator()
    # Should not crash even with minimal input
    li.on_trade_closed({"symbol": "BTC", "outcome": "WIN", "strategy": "regime_trend"})


def test_on_trade_closed_empty_dict():
    li = LearningIntegrator()
    li.on_trade_closed({})


# ── get_enriched_llm_context ────────────────────────────

def test_get_enriched_llm_context_returns_string():
    li = LearningIntegrator()
    # Even if all sub-systems fail, the method returns a string (possibly empty)
    ctx = li.get_enriched_llm_context(symbol="BTC", regime="trend")
    assert isinstance(ctx, str)


def test_get_enriched_llm_context_no_symbol():
    li = LearningIntegrator()
    ctx = li.get_enriched_llm_context()
    assert isinstance(ctx, str)
