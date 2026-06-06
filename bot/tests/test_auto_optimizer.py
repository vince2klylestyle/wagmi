"""
Smoke tests for feedback/auto_optimizer.py (AutoOptimizer).

Covers:
  - Constructor init with fake tuner + evolution
  - record_trade updates counters + consecutive losses
  - _should_trigger returns expected reasons
  - get_status() returns expected keys
  - _save_state / _load_state round-trip
  - tick() cooldown suppresses back-to-back reviews
  - _update_adaptive_interval responds to win rate delta
"""
import json
import os
import sys
import tempfile
import time
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from feedback.auto_optimizer import AutoOptimizer


class FakeTuner:
    """Minimal stand-in for ParameterTuner."""


class FakeReport:
    total_trades = 0
    total_decisions = 0
    lessons = []
    win_rate_trajectory = []


class FakeEvolution:
    """Minimal stand-in for EvolutionTracker."""

    def __init__(self):
        self.applied_count = 0

    def generate_report(self):
        return FakeReport()

    def apply_lessons_to_tuner(self, report, tuner):
        self.applied_count += 1
        return 3


# ── Constructor ──────────────────────────────────────────

def test_construct_defaults():
    with tempfile.TemporaryDirectory() as d:
        opt = AutoOptimizer(FakeEvolution(), FakeTuner(), data_dir=d)
        assert opt._state["total_trades"] == 0
        assert opt._state["total_reviews"] == 0
        assert opt._state["consecutive_losses"] == 0
        assert os.path.exists(d)


def test_construct_llm_disabled():
    with tempfile.TemporaryDirectory() as d:
        opt = AutoOptimizer(
            FakeEvolution(), FakeTuner(),
            data_dir=d, llm_review_enabled=False,
        )
        assert opt._llm_review_enabled is False


# ── record_trade ─────────────────────────────────────────

def test_record_trade_win_resets_consec_losses():
    with tempfile.TemporaryDirectory() as d:
        opt = AutoOptimizer(FakeEvolution(), FakeTuner(), data_dir=d)
        opt.record_trade(-5, False)
        opt.record_trade(-3, False)
        assert opt._state["consecutive_losses"] == 2
        opt.record_trade(10, True)
        assert opt._state["consecutive_losses"] == 0


def test_record_trade_increments_total():
    with tempfile.TemporaryDirectory() as d:
        opt = AutoOptimizer(FakeEvolution(), FakeTuner(), data_dir=d)
        for _ in range(5):
            opt.record_trade(1, True)
        assert opt._state["total_trades"] == 5


def test_record_trade_updates_ema_baseline():
    with tempfile.TemporaryDirectory() as d:
        opt = AutoOptimizer(FakeEvolution(), FakeTuner(), data_dir=d)
        initial_wr = opt._state["performance_baseline"]["win_rate"]
        # 10 losses in a row should pull the EMA down
        for _ in range(10):
            opt.record_trade(-1, False)
        assert opt._state["performance_baseline"]["win_rate"] < initial_wr


# ── _should_trigger ──────────────────────────────────────

def test_should_trigger_scheduled_fires_on_fresh_state():
    with tempfile.TemporaryDirectory() as d:
        opt = AutoOptimizer(FakeEvolution(), FakeTuner(), data_dir=d)
        # Fresh state has last_scheduled_review_ts=0, so scheduled should fire
        r = opt._should_trigger(trade_count=0, recent_win_rate=50)
        assert r is not None
        assert "scheduled" in r


def test_should_trigger_suppressed_after_recent_review():
    with tempfile.TemporaryDirectory() as d:
        opt = AutoOptimizer(FakeEvolution(), FakeTuner(), data_dir=d)
        opt._state["last_scheduled_review_ts"] = time.time()
        opt._state["last_trade_count_review"] = 0
        # No triggers should fire
        r = opt._should_trigger(trade_count=0, recent_win_rate=50)
        assert r is None


def test_should_trigger_trade_count_fires():
    with tempfile.TemporaryDirectory() as d:
        opt = AutoOptimizer(
            FakeEvolution(), FakeTuner(),
            data_dir=d, trades_per_review=5,
        )
        # Bypass scheduled by setting a recent review
        opt._state["last_scheduled_review_ts"] = time.time()
        opt._state["total_trades"] = 10
        opt._state["last_trade_count_review"] = 0
        r = opt._should_trigger(trade_count=10, recent_win_rate=50)
        assert r is not None
        assert "trade_count" in r


def test_should_trigger_consec_loss_alert():
    with tempfile.TemporaryDirectory() as d:
        opt = AutoOptimizer(
            FakeEvolution(), FakeTuner(),
            data_dir=d, consec_loss_alert=3,
        )
        opt._state["last_scheduled_review_ts"] = time.time()
        opt._state["last_trade_count_review"] = 0
        opt._state["consecutive_losses"] = 4
        r = opt._should_trigger(trade_count=0, recent_win_rate=50)
        assert r is not None
        assert "consec_losses" in r


# ── get_status ───────────────────────────────────────────

def test_get_status_keys():
    with tempfile.TemporaryDirectory() as d:
        opt = AutoOptimizer(FakeEvolution(), FakeTuner(), data_dir=d)
        s = opt.get_status()
        assert "total_reviews" in s
        assert "total_trades" in s
        assert "adaptive_interval_h" in s
        assert "performance_baseline" in s


# ── Save / load round-trip ───────────────────────────────

def test_save_load_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        opt1 = AutoOptimizer(FakeEvolution(), FakeTuner(), data_dir=d)
        opt1.record_trade(10, True)
        opt1.record_trade(-2, False)
        opt1._save_state()

        # Fresh instance from same dir should load the same state
        opt2 = AutoOptimizer(FakeEvolution(), FakeTuner(), data_dir=d)
        assert opt2._state["total_trades"] == 2
        assert opt2._state["consecutive_losses"] == 1


def test_load_state_handles_corrupted_file():
    with tempfile.TemporaryDirectory() as d:
        state_path = os.path.join(d, "auto_optimizer_state.json")
        with open(state_path, "w") as f:
            f.write("{corrupted")
        # Should fall back to defaults, not crash
        opt = AutoOptimizer(FakeEvolution(), FakeTuner(), data_dir=d)
        assert opt._state["total_trades"] == 0


# ── _update_adaptive_interval ───────────────────────────

def test_adaptive_interval_shortens_on_degradation():
    with tempfile.TemporaryDirectory() as d:
        opt = AutoOptimizer(FakeEvolution(), FakeTuner(), data_dir=d)
        opt._state["performance_baseline"]["win_rate"] = 60
        opt._update_adaptive_interval(recent_win_rate=40)
        # Large degradation (delta=-20) should shorten to 6h
        assert opt._state["adaptive_interval_s"] == 6 * 3600


def test_adaptive_interval_lengthens_on_strong_performance():
    with tempfile.TemporaryDirectory() as d:
        opt = AutoOptimizer(FakeEvolution(), FakeTuner(), data_dir=d)
        opt._state["performance_baseline"]["win_rate"] = 50
        opt._update_adaptive_interval(recent_win_rate=70)
        # Strong uplift (delta=+20) should lengthen to 18h
        assert opt._state["adaptive_interval_s"] == 18 * 3600


# ── tick() cooldown ──────────────────────────────────────

def test_tick_cooldown_suppresses_second_review():
    with tempfile.TemporaryDirectory() as d:
        opt = AutoOptimizer(
            FakeEvolution(), FakeTuner(),
            data_dir=d, llm_review_enabled=False,
        )
        # First tick should trigger (fresh scheduled)
        opt.tick(trade_count=0, recent_win_rate=50, recent_avg_pnl=0)
        reviews_after_first = opt._state["total_reviews"]
        # Second tick immediately after — should be cooled down
        opt._state["last_scheduled_review_ts"] = 0  # force scheduled again
        opt.tick(trade_count=0, recent_win_rate=50, recent_avg_pnl=0)
        # With the 1-hour cooldown, no new review
        assert opt._state["total_reviews"] == reviews_after_first


# ── set_feedback_loop smoke ──────────────────────────────

def test_set_feedback_loop_stores_reference():
    with tempfile.TemporaryDirectory() as d:
        opt = AutoOptimizer(FakeEvolution(), FakeTuner(), data_dir=d)
        sentinel = object()
        opt.set_feedback_loop(sentinel)
        assert opt._feedback_loop is sentinel
