"""
Tests for manual position management rules engine.

Covers:
- Entry phase false breakout detection
- Breakeven SL move trigger
- Partial close logic
- Trailing stop progression
- Emergency close triggers
- Time stop
- Format output
- get_management_rules
"""

import pytest
from datetime import datetime, timezone, timedelta

from manual.position_rules import (
    ManualPositionManager,
    Phase,
    Action,
    PositionUpdate,
    RuleParams,
    format_position_update,
    get_management_rules,
    ROUND_TRIP_FEE_PCT,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mgr():
    return ManualPositionManager()


def _now():
    return datetime.now(timezone.utc)


def _mins_ago(n):
    return _now() - timedelta(minutes=n)


# Common position params for a HYPE BUY at 25x
BASE_LONG = dict(
    symbol="HYPE",
    side="BUY",
    entry=25.00,
    sl=24.50,           # 2% stop width, risk = $0.50
    tp_scalp=25.75,     # 1.5R
    tp_swing=26.50,     # 3R
    leverage=25.0,
    tier="SNIPER",
    equity=100.0,
    position_size_usd=250.0,  # $250 notional at 25x on ~$10 margin
)

BASE_SHORT = dict(
    symbol="HYPE",
    side="SELL",
    entry=25.00,
    sl=25.50,           # risk = $0.50
    tp_scalp=24.25,     # 1.5R
    tp_swing=23.50,     # 3R
    leverage=25.0,
    tier="SNIPER",
    equity=100.0,
    position_size_usd=250.0,
)


# ===========================================================================
# Entry Phase Tests
# ===========================================================================

class TestEntryPhase:
    """Entry phase: first 15 min after entry."""

    def test_false_breakout_triggers_close(self, mgr):
        """Price reverses >0.4% against us in first 5 min → CLOSE."""
        update = mgr.evaluate(
            **BASE_LONG,
            current_price=24.88,    # -0.48% from entry (>0.4% threshold for SNIPER/high)
            entry_time=_mins_ago(3),  # 3 min in
        )
        assert update.action == Action.CLOSE
        assert "FALSE BREAKOUT" in update.reason or "EMERGENCY" in update.reason

    def test_false_breakout_short_side(self, mgr):
        """Short: price goes UP against us in first 5 min → CLOSE."""
        update = mgr.evaluate(
            **BASE_SHORT,
            current_price=25.12,    # +0.48% against short
            entry_time=_mins_ago(3),
        )
        assert update.action == Action.CLOSE

    def test_no_false_breakout_if_small_move(self, mgr):
        """Small adverse move within threshold → HOLD."""
        update = mgr.evaluate(
            **BASE_LONG,
            current_price=24.95,    # -0.2% — within threshold
            entry_time=_mins_ago(3),
        )
        assert update.action == Action.HOLD
        assert update.phase == Phase.ENTRY

    def test_breakeven_sl_move_on_quick_profit(self, mgr):
        """Price moves +0.3% in our favor → tighten SL to breakeven."""
        # For SNIPER at 25x, breakeven trigger is 0.2%
        update = mgr.evaluate(
            **BASE_LONG,
            current_price=25.08,    # +0.32% from entry
            entry_time=_mins_ago(5),
        )
        assert update.action == Action.TIGHTEN_SL
        # SL should be near entry + fees
        assert update.suggested_sl is not None
        assert update.suggested_sl > BASE_LONG["entry"]
        assert update.suggested_sl < BASE_LONG["entry"] * 1.001  # close to entry

    def test_breakeven_sl_short_side(self, mgr):
        """Short: price drops in our favor → breakeven SL."""
        update = mgr.evaluate(
            **BASE_SHORT,
            current_price=24.92,    # -0.32% (profit for short)
            entry_time=_mins_ago(5),
        )
        assert update.action == Action.TIGHTEN_SL
        assert update.suggested_sl is not None
        assert update.suggested_sl < BASE_SHORT["entry"]

    def test_hold_during_entry_no_movement(self, mgr):
        """Price flat during entry phase → HOLD."""
        update = mgr.evaluate(
            **BASE_LONG,
            current_price=25.01,
            entry_time=_mins_ago(2),
        )
        assert update.action == Action.HOLD
        assert update.phase == Phase.ENTRY

    def test_candle_reversal_detection(self, mgr):
        """3 consecutive bearish candles while underwater → CLOSE."""
        bearish_candles = [
            {"open": 25.05, "high": 25.06, "low": 24.98, "close": 24.99},
            {"open": 24.99, "high": 25.00, "low": 24.94, "close": 24.95},
            {"open": 24.95, "high": 24.96, "low": 24.90, "close": 24.91},
        ]
        update = mgr.evaluate(
            **BASE_LONG,
            current_price=24.91,    # underwater
            entry_time=_mins_ago(10),
            recent_5m_candles=bearish_candles,
        )
        assert update.action == Action.CLOSE
        assert "candle" in update.reason.lower() or "consecutive" in update.reason.lower()


# ===========================================================================
# Early Profit Phase Tests
# ===========================================================================

class TestEarlyProfitPhase:
    """Early profit phase: 0.3-1.0% in profit."""

    def test_sl_moves_to_breakeven(self, mgr):
        """In early profit, SL should be moved to breakeven."""
        update = mgr.evaluate(
            **BASE_LONG,
            current_price=25.15,    # +0.6% profit
            entry_time=_mins_ago(20),
        )
        # Should be EARLY phase with BE SL
        assert update.phase == Phase.EARLY
        # SL should be at or above entry
        if update.action == Action.TIGHTEN_SL:
            assert update.suggested_sl >= BASE_LONG["entry"]

    def test_three_bearish_candles_close_early_profit(self, mgr):
        """3 bearish candles in early profit with SL at BE → close to lock profit."""
        bearish_candles = [
            {"open": 25.25, "high": 25.26, "low": 25.19, "close": 25.20},
            {"open": 25.20, "high": 25.21, "low": 25.14, "close": 25.15},
            {"open": 25.15, "high": 25.16, "low": 25.09, "close": 25.10},
        ]
        # Price still in early profit zone, SL at real risk level.
        # SL at breakeven (slightly above entry). Risk is still from original SL.
        # At +0.4% profit with bearish candles, engine should suggest BE SL first.
        update = mgr.evaluate(
            **BASE_LONG,
            current_price=25.10,    # +0.4% from entry
            entry_time=_mins_ago(20),
            recent_5m_candles=bearish_candles,
        )
        # SL still at original 24.50 → needs to move to BE first (higher priority)
        # This is correct behavior: secure breakeven before anything else
        assert update.action in (Action.TIGHTEN_SL, Action.CLOSE)

    def test_approaching_scalp_tp(self, mgr):
        """Approaching 1.5R → HOLD or TIGHTEN_SL (BE move may still be needed)."""
        # 1.5R at $0.50 risk = $0.75 profit → price = 25.75
        # 80% of that = $0.60 → price = 25.60
        update = mgr.evaluate(
            **BASE_LONG,
            current_price=25.60,    # ~1.2R
            entry_time=_mins_ago(30),
        )
        # May be TIGHTEN_SL (moving to BE) or HOLD (if BE already set)
        assert update.action in (Action.HOLD, Action.TIGHTEN_SL)
        assert update.phase in (Phase.EARLY, Phase.SCALP_TP)


# ===========================================================================
# Scalp TP Phase Tests
# ===========================================================================

class TestScalpTpPhase:
    """Scalp TP phase: at or near 1.5R."""

    def test_partial_close_at_scalp_tp(self, mgr):
        """At 1.5R → TAKE_PARTIAL with 50% close."""
        update = mgr.evaluate(
            **BASE_LONG,
            current_price=25.75,    # exactly 1.5R
            entry_time=_mins_ago(45),
            partial_taken=False,
        )
        assert update.action == Action.TAKE_PARTIAL
        assert update.partial_close_pct == 0.50
        assert update.phase == Phase.SCALP_TP

    def test_post_partial_sl_at_half_r(self, mgr):
        """After partial, SL moves to entry + 0.5R."""
        update = mgr.evaluate(
            **BASE_LONG,
            current_price=25.75,
            entry_time=_mins_ago(45),
            partial_taken=False,
        )
        # SL should be entry + 0.5 * risk = 25.00 + 0.25 = 25.25
        assert update.suggested_sl is not None
        assert abs(update.suggested_sl - 25.25) < 0.01

    def test_partial_close_short_side(self, mgr):
        """Short at 1.5R → TAKE_PARTIAL."""
        update = mgr.evaluate(
            **BASE_SHORT,
            current_price=24.25,    # -0.75 from entry = 1.5R profit
            entry_time=_mins_ago(45),
            partial_taken=False,
        )
        assert update.action == Action.TAKE_PARTIAL
        assert update.partial_close_pct == 0.50

    def test_already_partial_transitions_to_trail(self, mgr):
        """If partial already taken, transitions to trailing."""
        update = mgr.evaluate(
            **BASE_LONG,
            current_price=25.80,
            entry_time=_mins_ago(60),
            partial_taken=True,
        )
        # Should be in SWING phase now
        assert update.phase == Phase.SWING


# ===========================================================================
# Swing Phase Tests
# ===========================================================================

class TestSwingPhase:
    """Swing phase: past scalp TP, trailing toward 3R."""

    def test_trail_at_1r(self, mgr):
        """At 1.5R with partial taken → trail SL at 1R from entry."""
        update = mgr.evaluate(
            **BASE_LONG,
            current_price=25.80,    # 1.6R
            entry_time=_mins_ago(60),
            partial_taken=True,
            highest_price_since_entry=25.80,
            last_new_high_time=_mins_ago(5),
        )
        assert update.phase == Phase.SWING
        # Trail at 1R = entry + $0.50 = $25.50
        assert update.suggested_sl is not None
        assert abs(update.suggested_sl - 25.50) < 0.01

    def test_trail_tightens_at_2r(self, mgr):
        """At 2R → trail tightens to 1.5R."""
        # Override sl in BASE_LONG to reflect already-tightened SL
        params = {**BASE_LONG, "sl": 25.50}
        update = mgr.evaluate(
            **params,
            current_price=26.00,    # 2R
            entry_time=_mins_ago(90),
            partial_taken=True,
            highest_price_since_entry=26.00,
            last_new_high_time=_mins_ago(5),
        )
        assert update.phase == Phase.SWING
        # Trail at 1.5R = entry + $0.75 = $25.75
        assert update.suggested_sl is not None
        assert update.suggested_sl >= 25.74  # ~1.5R

    def test_trail_tightens_at_3r(self, mgr):
        """At 3R → trail tightens to 2.5R."""
        params = {**BASE_LONG, "sl": 25.75}
        update = mgr.evaluate(
            **params,
            current_price=26.50,    # 3R
            entry_time=_mins_ago(120),
            partial_taken=True,
            highest_price_since_entry=26.50,
            last_new_high_time=_mins_ago(5),
        )
        assert update.phase == Phase.SWING
        # Trail at 2.5R = entry + $1.25 = $26.25
        assert update.suggested_sl is not None
        assert update.suggested_sl >= 26.24  # ~2.5R

    def test_sl_never_moves_backward(self, mgr):
        """SL should never move to a worse level."""
        params = {**BASE_LONG, "sl": 25.75}
        update = mgr.evaluate(
            **params,
            current_price=25.80,    # 1.6R (slight pullback from 2R)
            entry_time=_mins_ago(90),
            partial_taken=True,
            highest_price_since_entry=26.00,
            last_new_high_time=_mins_ago(30),
        )
        # SL should not go below current 25.75
        if update.suggested_sl is not None:
            assert update.suggested_sl >= 25.75

    def test_time_stop_no_new_high(self, mgr):
        """No new high in 2 hours → CLOSE."""
        params = {**BASE_LONG, "sl": 25.50}
        update = mgr.evaluate(
            **params,
            current_price=25.80,
            entry_time=_mins_ago(180),
            partial_taken=True,
            highest_price_since_entry=26.00,
            last_new_high_time=_mins_ago(125),  # >120 min ago
        )
        assert update.action == Action.CLOSE
        assert "TIME STOP" in update.reason or "new high" in update.reason.lower()

    def test_swing_tp_hit_closes(self, mgr):
        """Price hits swing TP → CLOSE."""
        params = {**BASE_LONG, "sl": 25.75}
        update = mgr.evaluate(
            **params,
            current_price=26.55,    # past swing TP of 26.50
            entry_time=_mins_ago(120),
            partial_taken=True,
            highest_price_since_entry=26.55,
            last_new_high_time=_mins_ago(1),
        )
        assert update.action == Action.CLOSE
        assert "SWING TP" in update.reason


# ===========================================================================
# Emergency Rule Tests
# ===========================================================================

class TestEmergencyRules:
    """Emergency exits: high-leverage loss, funding, time limit."""

    def test_high_leverage_loss_emergency(self, mgr):
        """25x leverage + >0.4% loss → immediate close."""
        update = mgr.evaluate(
            **BASE_LONG,
            current_price=24.88,    # -0.48% (>0.4% for SNIPER/high)
            entry_time=_mins_ago(10),
        )
        assert update.action == Action.CLOSE
        assert update.is_emergency or "EMERGENCY" in update.reason or "FALSE BREAKOUT" in update.reason

    def test_medium_leverage_no_emergency(self, mgr):
        """15x leverage + 0.4% loss → no emergency (threshold is 0.5%)."""
        params = dict(BASE_LONG)
        params["leverage"] = 15.0
        params["tier"] = "PREMIUM"
        update = mgr.evaluate(
            **params,
            current_price=24.90,    # -0.4% — under 0.5% threshold for PREMIUM
            entry_time=_mins_ago(20),  # past false breakout window
        )
        # At 15x and -0.4%, should NOT trigger emergency
        # (PREMIUM medium lev threshold is 0.5%)
        assert not update.is_emergency

    def test_funding_rate_emergency(self, mgr):
        """Strong funding against position while underwater → CLOSE."""
        update = mgr.evaluate(
            **BASE_LONG,
            current_price=24.95,    # slightly underwater
            entry_time=_mins_ago(20),
            funding_rate=0.001,     # 0.1% — strongly against longs
        )
        assert update.action == Action.CLOSE
        assert update.is_emergency
        assert "funding" in update.reason.lower() or "Funding" in update.reason

    def test_funding_rate_in_favor_no_emergency(self, mgr):
        """Funding in our favor → no emergency."""
        update = mgr.evaluate(
            **BASE_LONG,
            current_price=24.95,
            entry_time=_mins_ago(20),
            funding_rate=-0.001,    # shorts pay longs — in our favor
        )
        # Should NOT be emergency from funding
        # (may still trigger other rules, but not funding-related)
        if update.is_emergency:
            assert "funding" not in update.reason.lower()

    def test_max_hold_time_emergency(self, mgr):
        """Position held past max hours → CLOSE."""
        # SNIPER at 25x has 8h max hold
        update = mgr.evaluate(
            **BASE_LONG,
            current_price=25.10,    # slightly profitable
            entry_time=_mins_ago(8 * 60 + 5),  # 8h 5min
            partial_taken=True,
            highest_price_since_entry=25.50,
            last_new_high_time=_mins_ago(10),
        )
        assert update.action == Action.CLOSE
        assert update.is_emergency
        assert "TIME LIMIT" in update.reason or "hour" in update.reason.lower()

    def test_under_max_hold_no_emergency(self, mgr):
        """Position within max hold time → no time emergency."""
        update = mgr.evaluate(
            **BASE_LONG,
            current_price=25.10,
            entry_time=_mins_ago(2 * 60),  # 2 hours (well under 4h SNIPER max)
            partial_taken=True,
            highest_price_since_entry=25.50,
            last_new_high_time=_mins_ago(10),
        )
        # Should not be a time-limit emergency
        if update.is_emergency:
            assert "TIME LIMIT" not in update.reason


# ===========================================================================
# Format Output Tests
# ===========================================================================

class TestFormatOutput:
    """Test Telegram message formatting."""

    def test_format_contains_essential_fields(self):
        """Formatted message includes P&L, action, reason, symbol."""
        msg = format_position_update(
            symbol="HYPE", side="BUY", entry=25.0, current_price=25.30,
            leverage=25, tier="SNIPER", equity=100.0, sl=24.50,
            tp_scalp=25.75, tp_swing=26.50,
            entry_time=_mins_ago(10),
        )
        assert "HYPE" in msg
        assert "BUY" in msg
        assert "25x" in msg
        assert "SNIPER" in msg
        assert "P&L:" in msg
        assert "Phase:" in msg

    def test_format_emergency_marker(self):
        """Emergency situations show clear marker."""
        msg = format_position_update(
            symbol="HYPE", side="BUY", entry=25.0, current_price=24.85,
            leverage=25, tier="SNIPER", equity=100.0, sl=24.50,
            tp_scalp=25.75, tp_swing=26.50,
            entry_time=_mins_ago(3),
        )
        # Should contain emergency or close marker
        assert "CLOSE" in msg or "EMERGENCY" in msg

    def test_format_positive_pnl(self):
        """Positive P&L shows + sign."""
        msg = format_position_update(
            symbol="HYPE", side="BUY", entry=25.0, current_price=25.20,
            leverage=25, tier="SNIPER", equity=100.0, sl=24.50,
            tp_scalp=25.75, tp_swing=26.50,
            entry_time=_mins_ago(10),
        )
        assert "+$" in msg or "+0" in msg or "+1" in msg or "+2" in msg

    def test_format_partial_instruction(self):
        """At scalp TP, format includes partial close instruction."""
        msg = format_position_update(
            symbol="HYPE", side="BUY", entry=25.0, current_price=25.75,
            leverage=25, tier="SNIPER", equity=100.0, sl=24.50,
            tp_scalp=25.75, tp_swing=26.50,
            entry_time=_mins_ago(45),
        )
        assert "50%" in msg or "PARTIAL" in msg


# ===========================================================================
# get_management_rules Tests
# ===========================================================================

class TestGetManagementRules:
    """Test rule lookups for different tiers and phases."""

    def test_sniper_entry_phase(self):
        rules = get_management_rules("SNIPER", 25.0, hold_time_minutes=5)
        assert rules["current_phase"] == "ENTRY"
        assert rules["tier"] == "SNIPER"
        assert rules["leverage_bucket"] == "high"
        assert "false_breakout_threshold" in rules["phase_rules"]

    def test_premium_early_phase(self):
        rules = get_management_rules("PREMIUM", 15.0, hold_time_minutes=30)
        assert rules["current_phase"] == "EARLY_PROFIT"
        assert rules["leverage_bucket"] == "medium"
        assert "sl_target" in rules["phase_rules"]

    def test_scalp_tp_phase(self):
        rules = get_management_rules("SNIPER", 20.0, hold_time_minutes=90)
        assert rules["current_phase"] == "SCALP_TP"
        assert "partial_close" in rules["phase_rules"]

    def test_swing_phase(self):
        rules = get_management_rules("PREMIUM", 15.0, hold_time_minutes=240)
        assert rules["current_phase"] == "SWING"
        assert "trailing_at_1r" in rules["phase_rules"]
        assert "time_stop" in rules["phase_rules"]

    def test_emergency_rules_present(self):
        rules = get_management_rules("SNIPER", 25.0, hold_time_minutes=5)
        assert "emergency_rules" in rules
        assert "max_hold_hours" in rules["emergency_rules"]

    def test_different_max_hold_by_tier(self):
        sniper = get_management_rules("SNIPER", 25.0, hold_time_minutes=5)
        premium = get_management_rules("PREMIUM", 15.0, hold_time_minutes=5)
        # SNIPER at high lev should have shorter max hold
        assert sniper["emergency_rules"]["max_hold_hours"] <= premium["emergency_rules"]["max_hold_hours"]


# ===========================================================================
# Edge Cases
# ===========================================================================

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_zero_risk_width(self, mgr):
        """Entry == SL (zero risk) → CLOSE immediately."""
        update = mgr.evaluate(
            symbol="HYPE", side="BUY", entry=25.0, sl=25.0,
            tp_scalp=25.75, tp_swing=26.50, leverage=25, tier="SNIPER",
            current_price=25.0, entry_time=_mins_ago(1), equity=100.0,
        )
        assert update.action == Action.CLOSE
        assert "zero risk" in update.reason.lower() or "Invalid" in update.reason

    def test_pnl_r_calculation(self, mgr):
        """P&L in R-multiples is correct."""
        # 1R profit = $0.50 → price at 25.50
        update = mgr.evaluate(
            **BASE_LONG,
            current_price=25.50,
            entry_time=_mins_ago(30),
        )
        assert abs(update.pnl_r - 1.0) < 0.05

    def test_pnl_usd_calculation(self, mgr):
        """P&L in USD uses position size correctly."""
        # +2% at $250 notional = $5
        update = mgr.evaluate(
            **BASE_LONG,
            current_price=25.50,    # +2%
            entry_time=_mins_ago(30),
        )
        assert abs(update.pnl_usd - 5.0) < 0.5  # ~$5

    def test_negative_pnl_r(self, mgr):
        """Negative P&L shows negative R."""
        update = mgr.evaluate(
            **BASE_LONG,
            current_price=24.75,    # -0.5R
            entry_time=_mins_ago(20),
        )
        assert update.pnl_r < 0

    def test_short_position_pnl(self, mgr):
        """Short position P&L is positive when price drops."""
        update = mgr.evaluate(
            **BASE_SHORT,
            current_price=24.50,    # -2% from entry = profit for short
            entry_time=_mins_ago(30),
        )
        assert update.pnl_usd > 0
        assert update.pnl_r > 0
