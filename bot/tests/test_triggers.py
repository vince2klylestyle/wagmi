"""
Smoke tests for llm/triggers.py.

Covers:
- TriggerAccumulator init + add/clear
- should_fire with empty vs populated events
- Priority ordering in get_best
- Cooldown/rate-cap behavior
- Regime shift detection (first call + repeat + change)
- Cross-market divergence
- Strategy disagreement
- Pre-close detection (approaching SL/TP)
- Memory-worthy events (streaks, win-rate thresholds)
- StrategyPerformance record/properties
- Suppression of low-value PERIODIC
"""

import time
import pytest

from llm.triggers import (
    LLMTrigger,
    TriggerEvent,
    StrategyPerformance,
    TriggerAccumulator,
    TRIGGER_COOLDOWNS,
    TRIGGER_LABELS,
)


# ── StrategyPerformance ──────────────────────────────────────


class TestStrategyPerformance:
    def test_init_empty(self):
        sp = StrategyPerformance()
        assert sp.wins == 0
        assert sp.losses == 0
        assert sp.recent_count == 0
        assert sp.recent_win_rate == 0.5  # neutral when no data
        assert sp.streak == 0

    def test_record_wins_and_losses(self):
        sp = StrategyPerformance()
        sp.record(True)
        sp.record(True)
        sp.record(False)
        assert sp.wins == 2
        assert sp.losses == 1
        assert sp.recent_count == 3
        assert abs(sp.recent_win_rate - 2 / 3) < 1e-9

    def test_streak_positive(self):
        sp = StrategyPerformance()
        sp.record(False)
        sp.record(True)
        sp.record(True)
        sp.record(True)
        assert sp.streak == 3

    def test_streak_negative(self):
        sp = StrategyPerformance()
        sp.record(True)
        sp.record(False)
        sp.record(False)
        assert sp.streak == -2

    def test_recent_window_caps(self):
        sp = StrategyPerformance()
        # Push 25 outcomes, only last 20 should remain in recent_outcomes
        for _ in range(25):
            sp.record(True)
        assert sp.recent_count == 20
        assert sp.wins == 25  # lifetime wins unchanged


# ── TriggerAccumulator core ──────────────────────────────────


class TestAccumulatorBasic:
    def test_constructor_empty(self):
        acc = TriggerAccumulator()
        assert acc.event_count == 0
        assert acc.event_summary == "none"
        assert acc.should_fire() is False

    def test_add_and_clear(self):
        acc = TriggerAccumulator()
        acc.add(LLMTrigger.HIGH_CONFIDENCE, "BTC", "high conf BTC")
        assert acc.event_count == 1
        acc.clear()
        assert acc.event_count == 0

    def test_should_fire_none_when_empty(self):
        acc = TriggerAccumulator()
        assert acc.should_fire() is False
        trigger, ctx, reasons = acc.get_best()
        assert trigger is None
        assert ctx == ""
        assert reasons == []

    def test_should_fire_after_add(self):
        acc = TriggerAccumulator()
        acc.add(LLMTrigger.PRE_TRADE, "SOL", "entering LONG")
        assert acc.should_fire() is True

    def test_get_best_picks_highest_priority(self):
        acc = TriggerAccumulator()
        acc.add(LLMTrigger.PERIODIC, "BTC", "tick")
        acc.add(LLMTrigger.PRE_TRADE, "SOL", "entering LONG")
        acc.add(LLMTrigger.HIGH_CONFIDENCE, "ETH", "high conf")
        trigger, ctx, reasons = acc.get_best()
        # PRE_TRADE has value 1 (highest)
        assert trigger == LLMTrigger.PRE_TRADE
        assert "SOL" in ctx or "entering LONG" in ctx
        assert len(reasons) >= 1

    def test_mark_called_starts_cooldown(self):
        acc = TriggerAccumulator()
        acc.add(LLMTrigger.PRE_TRADE, "SOL", "ctx")
        assert acc.should_fire() is True
        acc.mark_called(LLMTrigger.PRE_TRADE)
        acc.clear()
        # Add again: global cooldown should block
        acc.add(LLMTrigger.PRE_TRADE, "SOL", "ctx2")
        assert acc.should_fire() is False

    def test_event_summary(self):
        acc = TriggerAccumulator()
        acc.add(LLMTrigger.HIGH_CONFIDENCE, "BTC", "a")
        acc.add(LLMTrigger.HIGH_CONFIDENCE, "ETH", "b")
        acc.add(LLMTrigger.PERIODIC, "", "tick")
        summary = acc.event_summary
        assert "high_confidence=2" in summary
        assert "periodic=1" in summary

    def test_remove_symbol_events(self):
        acc = TriggerAccumulator()
        acc.add(LLMTrigger.HIGH_CONFIDENCE, "BTC", "a")
        acc.add(LLMTrigger.HIGH_CONFIDENCE, "ETH", "b")
        acc.remove_symbol_events("BTC")
        assert acc.event_count == 1


# ── Regime shift detection ───────────────────────────────────


class TestRegimeShift:
    def test_first_call_returns_false(self):
        acc = TriggerAccumulator()
        assert acc.check_regime_shift("BTC", "trend") is False

    def test_no_shift_if_same(self):
        acc = TriggerAccumulator()
        acc.check_regime_shift("BTC", "trend")
        assert acc.check_regime_shift("BTC", "trend") is False

    def test_shift_when_regime_changes(self):
        acc = TriggerAccumulator()
        acc.check_regime_shift("BTC", "trend")
        assert acc.check_regime_shift("BTC", "panic") is True


# ── Cross-market divergence ──────────────────────────────────


class TestCrossMarketDivergence:
    def test_empty_input_returns_none(self):
        acc = TriggerAccumulator()
        assert acc.check_cross_market_divergence({}) is None

    def test_btc_alt_divergence(self):
        acc = TriggerAccumulator()
        result = acc.check_cross_market_divergence(
            {"BTC": 3.0, "SOL": 0.1, "HYPE": 0.2}
        )
        assert result is not None
        assert "BTC" in result

    def test_btc_eth_opposite(self):
        acc = TriggerAccumulator()
        result = acc.check_cross_market_divergence(
            {"BTC": 2.5, "ETH": -1.5}
        )
        assert result is not None
        assert "BTC/ETH" in result or "BTC" in result

    def test_outlier_detection(self):
        acc = TriggerAccumulator()
        result = acc.check_cross_market_divergence(
            {"BTC": 0.2, "ETH": 0.3, "HYPE": 8.0, "SOL": 0.1}
        )
        assert result is not None

    def test_no_divergence_when_flat(self):
        acc = TriggerAccumulator()
        result = acc.check_cross_market_divergence(
            {"BTC": 0.1, "ETH": 0.1, "SOL": 0.1}
        )
        assert result is None


# ── Strategy disagreement ────────────────────────────────────


class TestStrategyDisagreement:
    def test_empty_input(self):
        acc = TriggerAccumulator()
        assert acc.check_strategy_disagreement({}, {}) is None

    def test_strong_conflict(self):
        acc = TriggerAccumulator()
        signals = {
            "a": "long", "b": "long",
            "c": "short", "d": "short",
        }
        confs = {"a": 0.7, "b": 0.7, "c": 0.7, "d": 0.7}
        result = acc.check_strategy_disagreement(signals, confs)
        assert result is not None
        assert "conflict" in result.lower()

    def test_single_outlier(self):
        acc = TriggerAccumulator()
        signals = {"a": "long", "b": "long", "c": "short"}
        confs = {"a": 0.6, "b": 0.6, "c": 0.8}
        result = acc.check_strategy_disagreement(signals, confs)
        assert result is not None

    def test_unanimous_is_not_disagreement(self):
        acc = TriggerAccumulator()
        signals = {"a": "long", "b": "long", "c": "long"}
        confs = {"a": 0.7, "b": 0.7, "c": 0.7}
        assert acc.check_strategy_disagreement(signals, confs) is None


# ── Pre-close detection ──────────────────────────────────────


class TestPreClose:
    def test_no_proximity_returns_none(self):
        acc = TriggerAccumulator()
        result = acc.check_pre_close(
            symbol="BTC", side="LONG",
            entry=100.0, current_price=110.0,
            sl=95.0, tp1=120.0, tp2=130.0,
            state="OPEN", atr=1.0,
        )
        assert result is None

    def test_approaching_sl_long(self):
        acc = TriggerAccumulator()
        result = acc.check_pre_close(
            symbol="BTC", side="LONG",
            entry=100.0, current_price=95.3,
            sl=95.0, tp1=120.0, tp2=130.0,
            state="OPEN", atr=1.0,
        )
        assert result is not None
        assert "SL" in result

    def test_approaching_tp1_long(self):
        acc = TriggerAccumulator()
        result = acc.check_pre_close(
            symbol="ETH", side="LONG",
            entry=100.0, current_price=119.7,
            sl=90.0, tp1=120.0, tp2=130.0,
            state="OPEN", atr=1.0,
        )
        assert result is not None
        assert "TP1" in result

    def test_approaching_tp2_short(self):
        acc = TriggerAccumulator()
        result = acc.check_pre_close(
            symbol="SOL", side="SHORT",
            entry=100.0, current_price=80.3,
            sl=110.0, tp1=90.0, tp2=80.0,
            state="OPEN", atr=1.0,
        )
        assert result is not None
        assert "TP2" in result


# ── Memory-worthy events ─────────────────────────────────────


class TestMemoryEvents:
    def test_no_events_without_data(self):
        acc = TriggerAccumulator()
        assert acc.check_memory_events() == []

    def test_low_wr_triggers_event(self):
        acc = TriggerAccumulator()
        for _ in range(8):
            acc.record_trade_outcome("momentum", "breakout", win=False)
        for _ in range(2):
            acc.record_trade_outcome("momentum", "breakout", win=True)
        # Reset rate limiter to allow check
        acc._last_perf_check_ts = 0
        events = acc.check_memory_events()
        # 10 trades, 20% WR -> should trigger
        assert any("underperforming" in e for e in events)

    def test_entry_type_loss_streak(self):
        acc = TriggerAccumulator()
        for _ in range(5):
            acc.record_trade_outcome("mean_rev", "fade", win=False)
        acc._last_perf_check_ts = 0
        events = acc.check_memory_events()
        assert any("streak" in e.lower() for e in events)


# ── Suppression ──────────────────────────────────────────────


class TestSuppression:
    def test_suppress_periodic_with_high_prio(self):
        acc = TriggerAccumulator()
        acc.add(LLMTrigger.PERIODIC, "", "tick")
        acc.add(LLMTrigger.PRE_TRADE, "BTC", "entering")
        before = acc.event_count
        acc.suppress_low_value()
        # PERIODIC should be dropped
        assert acc.event_count < before
        remaining_triggers = [e.trigger for e in acc._events]
        assert LLMTrigger.PERIODIC not in remaining_triggers

    def test_no_suppression_when_single_event(self):
        acc = TriggerAccumulator()
        acc.add(LLMTrigger.PERIODIC, "", "tick")
        acc.suppress_low_value()
        assert acc.event_count == 1


# ── Rate stats ──────────────────────────────────────────────


def test_rate_stats_structure():
    acc = TriggerAccumulator()
    stats = acc.rate_stats
    assert "calls_last_hour" in stats
    assert "calls_last_day" in stats
    assert "max_per_hour" in stats
    assert "max_per_day" in stats
    # Before any calls, counts are 0
    assert stats["calls_last_hour"] == 0


def test_trigger_enum_priorities():
    # PRE_TRADE must have the highest priority (lowest int value)
    assert LLMTrigger.PRE_TRADE.value < LLMTrigger.PERIODIC.value
    assert LLMTrigger.PRE_TRADE.value < LLMTrigger.MEMORY_EVENT.value
    # All triggers must have labels and cooldowns
    for t in LLMTrigger:
        assert t in TRIGGER_COOLDOWNS
        assert t in TRIGGER_LABELS
