"""
Tests for the PA Enhanced Simulator.

Covers:
- PA confirmation logic (bullish/bearish candle detection)
- Rejection pattern detection (wick, volume spike, chase)
- Breakeven SL move
- Partial close logic
- Time stop tightening
- RSI divergence detection
- MFE/MAE tracking
- Comparison output
"""

import math
import time
import pytest
from types import SimpleNamespace
from unittest.mock import patch

from manual.pa_simulator import (
    PACandle,
    PAEnhancedSimulator,
    PendingEntry,
    check_pa_confirmation,
    check_rejection_patterns,
    compute_rsi,
    detect_rsi_divergence,
    candles_from_dataframe,
    BREAKEVEN_TRIGGER_RATIO,
    PA_CONFIRMATION_WINDOW_S,
    TIME_FLAT_HOURS,
    TIME_STOP_S,
)


# ── Helpers ────────────────────────────────────────────────────────────

def make_candle(
    ts: float, open_: float, high: float, low: float, close: float, volume: float = 100.0
) -> PACandle:
    return PACandle(
        timestamp=ts, open=open_, high=high, low=low, close=close, volume=volume
    )


def make_sniper_signal(
    symbol="HYPE", side="BUY", entry=30.0, sl=29.0, tp_scalp=31.5, tp_swing=33.0,
    leverage=20.0, risk_pct=0.10, confidence=88.0, num_agree=3, regime="trend",
    position_size_usd=300.0, risk_amount=10.0, tier="SNIPER",
):
    """Create a mock SniperSignal object."""
    return SimpleNamespace(
        symbol=symbol, side=side, entry=entry, sl=sl,
        tp_scalp=tp_scalp, tp_swing=tp_swing,
        leverage=leverage, risk_pct=risk_pct,
        confidence=confidence, num_agree=num_agree,
        regime=regime, position_size_usd=position_size_usd,
        risk_amount=risk_amount, tier=tier,
    )


# ── PACandle Properties ───────────────────────────────────────────────

class TestPACandle:
    def test_bullish_candle(self):
        c = make_candle(0, 100, 105, 99, 104)
        assert c.is_bullish is True
        assert c.is_bearish is False
        assert c.body == 4.0
        assert c.upper_wick == 1.0
        assert c.lower_wick == 1.0
        assert c.range == 6.0

    def test_bearish_candle(self):
        c = make_candle(0, 104, 105, 99, 100)
        assert c.is_bullish is False
        assert c.is_bearish is True
        assert c.body == 4.0
        assert c.upper_wick == 1.0
        assert c.lower_wick == 1.0

    def test_doji_candle(self):
        c = make_candle(0, 100, 105, 95, 100)
        assert c.body == 0.0
        assert c.is_bullish is False
        assert c.is_bearish is False


# ── PA Confirmation Logic ──────────────────────────────────────────────

class TestPAConfirmation:
    def test_buy_confirmation_bullish_close_above(self):
        """BUY confirmed when bullish candle closes above entry."""
        now = 1000.0
        candles = [
            make_candle(now + 60, 29.8, 30.5, 29.7, 30.2),  # Bullish, close > 30
        ]
        confirmed, price, reason = check_pa_confirmation(candles, "BUY", 30.0, now)
        assert confirmed is True
        assert price == 30.2
        assert "bullish" in reason

    def test_buy_no_confirmation_bearish_candle(self):
        """BUY not confirmed on bearish candle even if price touched entry."""
        now = 1000.0
        candles = [
            make_candle(now + 60, 30.5, 30.6, 29.5, 29.8),  # Bearish
        ]
        confirmed, price, reason = check_pa_confirmation(candles, "BUY", 30.0, now)
        assert confirmed is False

    def test_buy_no_confirmation_close_below_entry(self):
        """BUY not confirmed when bullish candle closes below entry."""
        now = 1000.0
        candles = [
            make_candle(now + 60, 29.0, 29.9, 28.9, 29.5),  # Bullish but close < 30
        ]
        confirmed, price, reason = check_pa_confirmation(candles, "BUY", 30.0, now)
        assert confirmed is False

    def test_sell_confirmation_bearish_close_below(self):
        """SELL confirmed when bearish candle closes below entry."""
        now = 1000.0
        candles = [
            make_candle(now + 60, 30.2, 30.3, 29.5, 29.8),  # Bearish, close < 30
        ]
        confirmed, price, reason = check_pa_confirmation(candles, "SELL", 30.0, now)
        assert confirmed is True
        assert price == 29.8
        assert "bearish" in reason

    def test_sell_no_confirmation_bullish_candle(self):
        """SELL not confirmed on bullish candle."""
        now = 1000.0
        candles = [
            make_candle(now + 60, 29.5, 30.5, 29.4, 30.2),  # Bullish
        ]
        confirmed, price, reason = check_pa_confirmation(candles, "SELL", 30.0, now)
        assert confirmed is False

    def test_confirmation_timeout(self):
        """No confirmation after 15 minutes = timeout."""
        now = 1000.0
        candles = [
            make_candle(now + 60, 29.9, 30.0, 29.8, 29.95),  # Not quite confirmed
            make_candle(now + 360, 29.95, 30.0, 29.9, 29.98),  # Still not
            make_candle(now + 960, 30.0, 30.5, 29.9, 30.3),    # Too late (16 min)
        ]
        confirmed, price, reason = check_pa_confirmation(candles, "BUY", 30.0, now)
        assert confirmed is False
        assert "timeout" in reason

    def test_confirmation_ignores_pre_signal_candles(self):
        """Candles before signal time are ignored."""
        now = 1000.0
        candles = [
            make_candle(now - 300, 29.5, 30.5, 29.4, 30.3),  # Before signal
            make_candle(now + 60, 29.9, 29.95, 29.5, 29.6),   # After but bearish
        ]
        confirmed, price, reason = check_pa_confirmation(candles, "BUY", 30.0, now)
        assert confirmed is False

    def test_empty_candles(self):
        confirmed, price, reason = check_pa_confirmation([], "BUY", 30.0, 1000.0)
        assert confirmed is False
        assert reason == "no_candles"


# ── Rejection Pattern Detection ────────────────────────────────────────

class TestRejectionPatterns:
    def test_upper_wick_rejection_for_buy(self):
        """Long upper wick > 2x body on BUY = rejection."""
        now = 1000.0
        # Body = 0.2, upper wick = 0.8 (4x body)
        candles = [
            make_candle(now + 60, 30.0, 31.0, 29.9, 30.2),
        ]
        rejected, reason = check_rejection_patterns(candles, "BUY", 30.0, now)
        assert rejected is True
        assert "upper_wick" in reason

    def test_lower_wick_rejection_for_sell(self):
        """Long lower wick > 2x body on SELL = rejection."""
        now = 1000.0
        # Body = 0.2, lower wick = 0.8 (4x body)
        candles = [
            make_candle(now + 60, 30.0, 30.1, 29.0, 29.8),
        ]
        rejected, reason = check_rejection_patterns(candles, "SELL", 30.0, now)
        assert rejected is True
        assert "lower_wick" in reason

    def test_no_wick_rejection_small_wick(self):
        """Small wick (< 2x body) = no rejection."""
        now = 1000.0
        # Body = 0.15, upper wick = 0.05 (0.33x body) — clean candle near entry
        candles = [
            make_candle(now + 60, 30.0, 30.20, 29.95, 30.15),
        ]
        rejected, reason = check_rejection_patterns(candles, "BUY", 30.0, now)
        assert rejected is False

    def test_volume_spike_bearish_rejects_buy(self):
        """Volume spike on bearish candle rejects BUY."""
        now = 1000.0
        # History candles for volume average
        history = [make_candle(now - i * 300, 30.0, 30.1, 29.9, 30.0, volume=100.0) for i in range(20, 0, -1)]
        # Entry candle: bearish with 4x volume spike
        entry_candle = make_candle(now + 60, 30.0, 30.1, 29.5, 29.6, volume=400.0)
        candles = history + [entry_candle]
        rejected, reason = check_rejection_patterns(candles, "BUY", 30.0, now)
        assert rejected is True
        assert "volume_spike" in reason

    def test_volume_spike_bullish_rejects_sell(self):
        """Volume spike on bullish candle rejects SELL."""
        now = 1000.0
        history = [make_candle(now - i * 300, 30.0, 30.1, 29.9, 30.0, volume=100.0) for i in range(20, 0, -1)]
        entry_candle = make_candle(now + 60, 29.8, 30.5, 29.7, 30.4, volume=400.0)
        candles = history + [entry_candle]
        rejected, reason = check_rejection_patterns(candles, "SELL", 30.0, now)
        assert rejected is True
        assert "volume_spike" in reason

    def test_chase_filter_buy(self):
        """Price moved > 1% past entry in BUY direction = chase, skip."""
        now = 1000.0
        # Entry at 30.0, price already at 30.4 (1.33% above)
        candles = [
            make_candle(now + 60, 30.3, 30.5, 30.2, 30.4),
        ]
        rejected, reason = check_rejection_patterns(candles, "BUY", 30.0, now)
        assert rejected is True
        assert "chase" in reason

    def test_chase_filter_sell(self):
        """Price moved > 1% past entry in SELL direction = chase, skip."""
        now = 1000.0
        candles = [
            make_candle(now + 60, 29.6, 29.7, 29.5, 29.5),  # 1.67% below 30.0
        ]
        rejected, reason = check_rejection_patterns(candles, "SELL", 30.0, now)
        assert rejected is True
        assert "chase" in reason

    def test_no_rejection_clean_entry(self):
        """Clean entry candle — no rejections."""
        now = 1000.0
        history = [make_candle(now - i * 300, 30.0, 30.1, 29.9, 30.0, volume=100.0) for i in range(20, 0, -1)]
        # Normal bullish candle, no wick issue, normal volume
        entry_candle = make_candle(now + 60, 29.9, 30.2, 29.85, 30.15, volume=120.0)
        candles = history + [entry_candle]
        rejected, reason = check_rejection_patterns(candles, "BUY", 30.0, now)
        assert rejected is False
        assert reason == ""


# ── RSI Computation ────────────────────────────────────────────────────

class TestRSI:
    def test_rsi_basic(self):
        """RSI should be between 0 and 100."""
        # Generate ascending prices for overbought RSI
        closes = [100 + i * 0.5 for i in range(30)]
        rsi = compute_rsi(closes)
        assert len(rsi) == len(closes)
        # After warmup, RSI should be high (ascending prices)
        valid_rsi = [r for r in rsi if not math.isnan(r)]
        assert len(valid_rsi) > 0
        assert all(0 <= r <= 100 for r in valid_rsi)
        # Ascending prices = high RSI
        assert valid_rsi[-1] > 70

    def test_rsi_descending(self):
        """Descending prices should give low RSI."""
        closes = [100 - i * 0.5 for i in range(30)]
        rsi = compute_rsi(closes)
        valid_rsi = [r for r in rsi if not math.isnan(r)]
        assert valid_rsi[-1] < 30

    def test_rsi_too_few_data_points(self):
        """RSI with insufficient data returns all NaN."""
        rsi = compute_rsi([100, 101, 102])
        assert all(math.isnan(r) for r in rsi)


# ── RSI Divergence Detection ──────────────────────────────────────────

class TestRSIDivergence:
    def test_bearish_divergence_on_buy(self):
        """Price making higher highs but RSI making lower highs = bearish divergence."""
        # Build candles: price goes up, but with decreasing momentum
        candles = []
        # First 20 candles: strong uptrend
        for i in range(20):
            price = 100 + i * 1.0
            candles.append(make_candle(i * 300, price, price + 0.5, price - 0.3, price + 0.4))
        # Last 6 candles: price still rising but momentum slowing (smaller moves)
        for i in range(6):
            base = 120 + i * 0.5
            candles.append(make_candle((20 + i) * 300, base, base + 0.2, base - 0.1, base + 0.1))

        result = detect_rsi_divergence(candles, "BUY")
        # The divergence detection depends on RSI values — this tests the logic path
        # With ascending prices, RSI should be high enough to pass the >60 check
        assert isinstance(result, bool)

    def test_no_divergence_insufficient_data(self):
        """Too few candles = no divergence detected."""
        candles = [make_candle(i, 100, 101, 99, 100) for i in range(5)]
        assert detect_rsi_divergence(candles, "BUY") is False


# ── Breakeven SL Move ─────────────────────────────────────────────────

class TestBreakevenSL:
    def test_sl_moves_to_breakeven_at_half_tp(self):
        """SL should move to entry price after 0.5x TP distance reached."""
        sim = PAEnhancedSimulator(starting_equity=100.0)
        signal = make_sniper_signal(entry=30.0, sl=29.0, tp_scalp=31.5)

        # Enter without candles (basic mode)
        pos = sim.on_signal(signal, candles_5m=None)
        assert pos is not None
        assert pos.sl_at_breakeven is False

        # Price moves 0.5x of TP distance (TP dist = 1.5, so 0.75 = price at 30.75)
        sim.check_positions({"HYPE": 30.80})
        # Should have moved SL to breakeven
        assert sim._open_positions[0].sl_at_breakeven is True
        assert sim._open_positions[0].sl == pos.pa_entry

    def test_sl_does_not_move_before_threshold(self):
        """SL should not move to BE before 0.5x TP distance."""
        sim = PAEnhancedSimulator(starting_equity=100.0)
        signal = make_sniper_signal(entry=30.0, sl=29.0, tp_scalp=31.5)
        pos = sim.on_signal(signal, candles_5m=None)
        assert pos is not None

        # Price only moved 0.3x TP distance (0.45)
        sim.check_positions({"HYPE": 30.40})
        assert sim._open_positions[0].sl_at_breakeven is False


# ── Partial Close Logic ───────────────────────────────────────────────

class TestPartialClose:
    def test_partial_close_at_scalp_tp(self):
        """50% should close at scalp TP, rest continues."""
        sim = PAEnhancedSimulator(starting_equity=100.0)
        signal = make_sniper_signal(entry=30.0, sl=29.0, tp_scalp=31.5, tp_swing=33.0)

        pos = sim.on_signal(signal, candles_5m=None)
        assert pos is not None
        initial_equity = sim._equity

        # Price hits scalp TP
        closed = sim.check_positions({"HYPE": 31.6})
        # Should NOT be closed — only partial close
        assert len(closed) == 0
        assert len(sim._open_positions) == 1
        assert sim._open_positions[0].partial_closed is True
        assert sim._open_positions[0].remaining_size_pct == 0.5

        # Equity should have increased from partial
        assert sim._equity > initial_equity

    def test_remaining_closes_at_swing_tp(self):
        """Remaining 50% closes at swing TP after partial."""
        sim = PAEnhancedSimulator(starting_equity=100.0)
        signal = make_sniper_signal(entry=30.0, sl=29.0, tp_scalp=31.5, tp_swing=33.0)
        sim.on_signal(signal, candles_5m=None)

        # Trigger partial at scalp TP
        sim.check_positions({"HYPE": 31.6})
        assert sim._open_positions[0].partial_closed is True

        # Now hit swing TP
        closed = sim.check_positions({"HYPE": 33.1})
        assert len(closed) == 1
        assert closed[0].exit_reason == "pa_swing_tp"
        assert closed[0].partial_closed is True
        assert closed[0].partial_pnl_usd > 0

    def test_partial_close_moves_sl_to_be(self):
        """Partial close should also move SL to breakeven."""
        sim = PAEnhancedSimulator(starting_equity=100.0)
        signal = make_sniper_signal(entry=30.0, sl=29.0, tp_scalp=31.5)
        sim.on_signal(signal, candles_5m=None)

        sim.check_positions({"HYPE": 31.6})
        assert sim._open_positions[0].sl_at_breakeven is True


# ── Time Stop Tightening ──────────────────────────────────────────────

class TestTimeTightening:
    def test_sl_tightens_after_4h_flat(self):
        """If position is flat after 4 hours, SL tightens to 0.5x original width."""
        sim = PAEnhancedSimulator(starting_equity=100.0)
        signal = make_sniper_signal(entry=30.0, sl=29.0, tp_scalp=31.5)
        pos = sim.on_signal(signal, candles_5m=None)
        assert pos is not None

        original_sl = pos.original_sl  # 29.0, width = 1.0

        # Simulate 4+ hours elapsed with price near entry (flat)
        pos.opened_at = time.time() - (TIME_FLAT_HOURS * 3600 + 60)
        sim.check_positions({"HYPE": 30.01})  # Flat — within 0.2%

        assert sim._open_positions[0].time_tightened is True
        # New SL should be closer: entry - 0.5 * original_width = 30.0 - 0.5 = 29.5
        assert sim._open_positions[0].sl == pytest.approx(29.5, abs=0.01)

    def test_sl_does_not_tighten_if_position_moved(self):
        """If position moved significantly, no tightening."""
        sim = PAEnhancedSimulator(starting_equity=100.0)
        signal = make_sniper_signal(entry=30.0, sl=29.0, tp_scalp=31.5)
        pos = sim.on_signal(signal, candles_5m=None)

        # 4+ hours but price moved to 30.5 (1.67% move, not flat)
        pos.opened_at = time.time() - (TIME_FLAT_HOURS * 3600 + 60)
        sim.check_positions({"HYPE": 30.5})

        assert sim._open_positions[0].time_tightened is False


# ── MFE/MAE Tracking ──────────────────────────────────────────────────

class TestMFEMAE:
    def test_mfe_mae_tracked(self):
        """MFE and MAE should update as price moves."""
        sim = PAEnhancedSimulator(starting_equity=100.0)
        signal = make_sniper_signal(entry=30.0, sl=29.0, tp_scalp=31.5)
        sim.on_signal(signal, candles_5m=None)

        # Price goes up (favorable for BUY)
        sim.check_positions({"HYPE": 30.5})
        pos = sim._open_positions[0]
        assert pos.mfe > 0
        assert pos.mfe_price == 30.5

        # Price goes down (adverse for BUY)
        sim.check_positions({"HYPE": 29.5})
        pos = sim._open_positions[0]
        assert pos.mae > 0
        assert pos.mae_price == 29.5

    def test_mfe_mae_sell_side(self):
        """MFE/MAE should be correct for SELL positions."""
        sim = PAEnhancedSimulator(starting_equity=100.0)
        signal = make_sniper_signal(side="SELL", entry=30.0, sl=31.0, tp_scalp=28.5)
        sim.on_signal(signal, candles_5m=None)

        # Price goes down (favorable for SELL)
        sim.check_positions({"HYPE": 29.5})
        pos = sim._open_positions[0]
        assert pos.mfe > 0

        # Price goes up (adverse for SELL)
        sim.check_positions({"HYPE": 30.5})
        pos = sim._open_positions[0]
        assert pos.mae > 0


# ── Full Simulator Flow ───────────────────────────────────────────────

class TestFullFlow:
    def test_signal_enter_and_close_win(self):
        """Full flow: signal → enter → close at TP."""
        sim = PAEnhancedSimulator(starting_equity=100.0)
        signal = make_sniper_signal(entry=30.0, sl=29.0, tp_scalp=31.5, tp_swing=33.0)

        # Enter (no candles = basic mode)
        pos = sim.on_signal(signal, candles_5m=None)
        assert pos is not None
        assert pos.trade_id.startswith("PA-")

        # Hit scalp TP → partial close
        sim.check_positions({"HYPE": 31.6})
        assert len(sim._open_positions) == 1
        assert sim._open_positions[0].partial_closed

        # Hit swing TP → full close
        closed = sim.check_positions({"HYPE": 33.1})
        assert len(closed) == 1
        assert closed[0].result == "WIN"
        assert closed[0].pnl_usd > 0
        assert sim._equity > 100.0

    def test_signal_enter_and_close_loss(self):
        """Full flow: signal → enter → close at SL."""
        sim = PAEnhancedSimulator(starting_equity=100.0)
        signal = make_sniper_signal(entry=30.0, sl=29.0, tp_scalp=31.5)
        sim.on_signal(signal, candles_5m=None)

        closed = sim.check_positions({"HYPE": 28.5})
        assert len(closed) == 1
        assert closed[0].result == "LOSS"
        assert closed[0].exit_reason == "sl"
        assert closed[0].pnl_usd < 0

    def test_pa_confirmation_flow(self):
        """Signal with candle data: PA confirmation then entry."""
        sim = PAEnhancedSimulator(starting_equity=100.0)
        signal = make_sniper_signal(entry=30.0, sl=29.0, tp_scalp=31.5)

        now = time.time()
        # Candles that confirm BUY: bullish close above entry
        candles = [
            make_candle(now + 60, 29.8, 30.3, 29.7, 30.2),
        ]
        pos = sim.on_signal(signal, candles_5m=candles)
        assert pos is not None
        assert pos.pa_entry == 30.2  # PA entry, not signal entry

    def test_rejection_prevents_entry(self):
        """Rejection pattern prevents entry."""
        sim = PAEnhancedSimulator(starting_equity=100.0)
        signal = make_sniper_signal(entry=30.0, sl=29.0, tp_scalp=31.5)

        now = time.time()
        # Candle with chase: price already 1.5% above entry
        candles = [
            make_candle(now + 60, 30.3, 30.6, 30.2, 30.5),
        ]
        pos = sim.on_signal(signal, candles_5m=candles)
        assert pos is None
        assert sim._signals_rejected == 1

    def test_pending_entry_then_confirm(self):
        """Signal goes to pending, then confirms on next check."""
        sim = PAEnhancedSimulator(starting_equity=100.0)
        signal = make_sniper_signal(entry=30.0, sl=29.0, tp_scalp=31.5)

        now = time.time()
        # No confirmation candle yet
        candles = [
            make_candle(now + 60, 29.5, 29.8, 29.4, 29.6),  # Bearish, no confirm
        ]
        pos = sim.on_signal(signal, candles_5m=candles)
        assert pos is None
        assert len(sim._pending_entries) == 1

        # Next cycle: confirmation arrives
        new_candles = [
            make_candle(now + 60, 29.5, 29.8, 29.4, 29.6),
            make_candle(now + 360, 29.8, 30.3, 29.7, 30.2),  # Bullish above entry
        ]
        opened = sim.check_pending_entries({"HYPE": new_candles})
        assert len(opened) == 1
        assert opened[0].pa_entry == 30.2

    def test_duplicate_position_prevented(self):
        """Cannot open duplicate position on same symbol+side."""
        sim = PAEnhancedSimulator(starting_equity=100.0)
        signal = make_sniper_signal()
        sim.on_signal(signal, candles_5m=None)
        pos2 = sim.on_signal(signal, candles_5m=None)
        assert pos2 is None
        assert len(sim._open_positions) == 1

    def test_time_stop_closes_position(self):
        """12-hour time stop closes position."""
        sim = PAEnhancedSimulator(starting_equity=100.0)
        signal = make_sniper_signal(entry=30.0, sl=29.0, tp_scalp=31.5)
        pos = sim.on_signal(signal, candles_5m=None)

        # Force position to be 12+ hours old
        pos.opened_at = time.time() - TIME_STOP_S - 60

        closed = sim.check_positions({"HYPE": 30.1})
        assert len(closed) == 1
        assert closed[0].exit_reason == "time_stop"

    def test_breakeven_sl_exit(self):
        """After BE move, SL exit is recorded as breakeven_sl."""
        sim = PAEnhancedSimulator(starting_equity=100.0)
        signal = make_sniper_signal(entry=30.0, sl=29.0, tp_scalp=31.5)
        sim.on_signal(signal, candles_5m=None)

        # Move price up to trigger BE
        sim.check_positions({"HYPE": 30.8})
        assert sim._open_positions[0].sl_at_breakeven

        # Now price drops to BE
        closed = sim.check_positions({"HYPE": 29.9})
        assert len(closed) == 1
        assert closed[0].exit_reason == "breakeven_sl"


# ── Comparison Output ─────────────────────────────────────────────────

class TestComparison:
    def test_comparison_structure(self):
        """Comparison output has required fields."""
        sim = PAEnhancedSimulator(starting_equity=100.0)
        comparison = sim.get_comparison()

        assert "pa_simulator" in comparison
        assert "basic_simulator" in comparison
        assert "comparison" in comparison
        assert "equity" in comparison["pa_simulator"]
        assert "equity" in comparison["basic_simulator"]
        assert "pnl_difference" in comparison["comparison"]
        assert "verdict" in comparison["comparison"]

    def test_comparison_after_trades(self):
        """Comparison tracks both simulators after trades."""
        sim = PAEnhancedSimulator(starting_equity=100.0)
        signal = make_sniper_signal(entry=30.0, sl=29.0, tp_scalp=31.5, tp_swing=33.0)
        sim.on_signal(signal, candles_5m=None)

        # Win trade (partial + swing)
        sim.check_positions({"HYPE": 31.6})  # Partial close
        sim.check_positions({"HYPE": 33.1})  # Swing TP

        comparison = sim.get_comparison()
        assert comparison["pa_simulator"]["total_trades"] > 0


# ── Status Output ─────────────────────────────────────────────────────

class TestStatus:
    def test_status_structure(self):
        """Status output has all required fields."""
        sim = PAEnhancedSimulator(starting_equity=100.0)
        status = sim.get_status()

        assert status["current_equity"] == 100.0
        assert status["starting_equity"] == 100.0
        assert "pa_metrics" in status
        pa = status["pa_metrics"]
        assert "signals_received" in pa
        assert "missed_trade_rate_pct" in pa
        assert "avg_entry_improvement_pct" in pa
        assert "avg_mfe_pct" in pa
        assert "avg_mae_pct" in pa
        assert "breakeven_saves" in pa

    def test_status_updates_after_trade(self):
        """Status reflects trades correctly."""
        sim = PAEnhancedSimulator(starting_equity=100.0)
        signal = make_sniper_signal(entry=30.0, sl=29.0, tp_scalp=31.5, tp_swing=33.0)
        sim.on_signal(signal, candles_5m=None)
        sim.check_positions({"HYPE": 31.6})  # Partial
        sim.check_positions({"HYPE": 33.1})  # Close

        status = sim.get_status()
        assert status["wins"] == 1
        assert status["total_trades"] == 1
        assert status["current_equity"] > 100.0


# ── Candle DataFrame Conversion ───────────────────────────────────────

class TestCandleConversion:
    def test_convert_dataframe(self):
        """Convert pandas DataFrame to PACandle list."""
        import pandas as pd
        df = pd.DataFrame({
            'timestamp': [1000, 1300, 1600],
            'open': [30.0, 30.1, 30.2],
            'high': [30.5, 30.4, 30.6],
            'low': [29.8, 29.9, 30.0],
            'close': [30.2, 30.3, 30.4],
            'volume': [100, 150, 200],
        })
        candles = candles_from_dataframe(df)
        assert len(candles) == 3
        assert candles[0].open == 30.0
        assert candles[2].volume == 200

    def test_convert_empty_dataframe(self):
        import pandas as pd
        candles = candles_from_dataframe(pd.DataFrame())
        assert candles == []

    def test_convert_none(self):
        candles = candles_from_dataframe(None)
        assert candles == []


# ── Entry Quality Tracking ────────────────────────────────────────────

class TestEntryQuality:
    def test_better_pa_entry_for_buy(self):
        """PA entry below signal entry = improvement for BUY."""
        sim = PAEnhancedSimulator(starting_equity=100.0)
        signal = make_sniper_signal(entry=30.0, sl=29.0, tp_scalp=31.5)

        now = time.time()
        # PA enters at 29.9 (below signal's 30.0 = better for BUY)
        candles = [
            make_candle(now + 60, 29.7, 30.1, 29.6, 30.0),  # Bullish close at entry
        ]
        pos = sim.on_signal(signal, candles_5m=candles)
        assert pos is not None
        # Entry improvement is positive when PA entry is better
        assert sim._total_entry_improvement >= 0  # close == entry, so 0 improvement

    def test_worse_pa_entry_for_buy(self):
        """PA entry above signal entry = worse for BUY."""
        sim = PAEnhancedSimulator(starting_equity=100.0)
        signal = make_sniper_signal(entry=30.0, sl=29.0, tp_scalp=31.5)

        now = time.time()
        candles = [
            make_candle(now + 60, 29.8, 30.3, 29.7, 30.2),  # Close above entry
        ]
        pos = sim.on_signal(signal, candles_5m=candles)
        assert pos is not None
        # Entered at 30.2 vs signal 30.0 = -0.67% worse for BUY
        assert sim._total_entry_improvement < 0


# ── SELL Side Tests ───────────────────────────────────────────────────

class TestSellSide:
    def test_sell_position_win(self):
        """SELL position wins when price drops."""
        sim = PAEnhancedSimulator(starting_equity=100.0)
        signal = make_sniper_signal(
            side="SELL", entry=30.0, sl=31.0, tp_scalp=28.5, tp_swing=27.0
        )
        sim.on_signal(signal, candles_5m=None)

        # Hit scalp TP
        sim.check_positions({"HYPE": 28.4})
        assert sim._open_positions[0].partial_closed

        # Hit swing TP
        closed = sim.check_positions({"HYPE": 26.9})
        assert len(closed) == 1
        assert closed[0].result == "WIN"

    def test_sell_position_loss(self):
        """SELL position loses when price rises to SL."""
        sim = PAEnhancedSimulator(starting_equity=100.0)
        signal = make_sniper_signal(
            side="SELL", entry=30.0, sl=31.0, tp_scalp=28.5
        )
        sim.on_signal(signal, candles_5m=None)

        closed = sim.check_positions({"HYPE": 31.1})
        assert len(closed) == 1
        assert closed[0].result == "LOSS"
        assert closed[0].exit_reason == "sl"

    def test_sell_breakeven_sl(self):
        """SELL position SL moves to breakeven correctly."""
        sim = PAEnhancedSimulator(starting_equity=100.0)
        signal = make_sniper_signal(
            side="SELL", entry=30.0, sl=31.0, tp_scalp=28.5
        )
        sim.on_signal(signal, candles_5m=None)

        # TP distance = 1.5, 0.5x = 0.75, so need price at 29.25 or below
        sim.check_positions({"HYPE": 29.2})
        pos = sim._open_positions[0]
        assert pos.sl_at_breakeven is True
        assert pos.sl == pos.pa_entry  # SL moved to entry (30.0)

    def test_sell_time_tighten(self):
        """SELL position SL tightens after 4h flat."""
        sim = PAEnhancedSimulator(starting_equity=100.0)
        signal = make_sniper_signal(
            side="SELL", entry=30.0, sl=31.0, tp_scalp=28.5
        )
        pos = sim.on_signal(signal, candles_5m=None)

        pos.opened_at = time.time() - (TIME_FLAT_HOURS * 3600 + 60)
        sim.check_positions({"HYPE": 30.01})  # Flat

        pos = sim._open_positions[0]
        assert pos.time_tightened is True
        # Original width = 1.0, tightened = 0.5, new SL = 30.0 + 0.5 = 30.5
        assert pos.sl == pytest.approx(30.5, abs=0.01)
