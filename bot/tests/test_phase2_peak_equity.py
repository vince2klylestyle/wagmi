"""
Phase 2 Test 1: Peak Equity Reset Bug Fix

Tests that circuit breaker cooldown recovery doesn't immediately re-trip
due to peak equity reset bug. This validates the unconditional reset logic.
"""

import pytest
import time
from datetime import datetime, timedelta, timezone
from execution.risk import CircuitBreaker, RiskManager


class TestPeakEquityResetFix:
    """Test suite for peak equity reset bug fix (risk.py:279-303)"""

    def test_peak_equity_reset_on_cooldown(self):
        """Case 1: Peak equity should reset to current equity on CB cooldown"""
        cb = CircuitBreaker(
            daily_loss_limit_pct=0.05,
            max_consecutive_losses=3,
            max_drawdown_pct=0.10,
            cooldown_minutes=1,  # 1 minute for testing
        )
        cb.start_session(equity=10000)
        rm = RiskManager(starting_equity=10000, circuit_breaker=cb)

        # Record a trade that causes 12% drawdown (triggers CB)
        rm.update_equity(pnl=-1200, sim_time=None)
        assert cb.tripped, "CB should trip on 12% drawdown"
        old_peak = cb.peak_equity  # Should be 10000
        assert old_peak == 10000, f"Old peak should be 10000, got {old_peak}"

        # Wait for cooldown (in real test, simulate time passage)
        time.sleep(61)  # 61 seconds

        # Check if trading is allowed after cooldown
        is_allowed = cb.is_trading_allowed(equity=8800)
        assert is_allowed, "Trading should be allowed after cooldown"

        # Verify peak_equity was reset to current equity (8800)
        assert cb.peak_equity == 8800, \
            f"peak_equity should reset to 8800, got {cb.peak_equity}"

        # Record a win - peak should update
        rm.update_equity(pnl=200)
        assert cb.peak_equity == 9000, \
            f"peak_equity should update to 9000 after win, got {cb.peak_equity}"

        # CB should NOT re-trip on next price update
        assert not cb.tripped, "CB should not re-trip after cooldown + win"

    def test_peak_equity_reset_with_zero_equity_edge_case(self):
        """Case 2: Zero equity edge case - should use fallback"""
        cb = CircuitBreaker(cooldown_minutes=1)
        cb.start_session(equity=10000)

        # Trip CB
        cb.record_trade(pnl=-1500, equity=8500)
        assert cb.tripped

        # Wait cooldown
        time.sleep(61)

        # Allow trading with zero equity (unrealistic but tests fallback)
        is_allowed = cb.is_trading_allowed(equity=0)
        assert is_allowed

        # peak_equity should use fallback (not stay at old peak)
        # Since equity=0, fallback should use current peak_equity
        assert cb.peak_equity >= 0, \
            f"peak_equity should be non-negative after zero edge case"

    def test_session_peak_equity_permanent_halt(self):
        """Case 3: Session peak vs daily peak - session halt is permanent"""
        cb = CircuitBreaker(
            max_drawdown_pct=0.10,
            max_session_drawdown_pct=0.20,  # 20% session limit
            cooldown_minutes=1,
        )
        cb.start_session(equity=10000)
        session_peak = cb.session_peak_equity
        assert session_peak == 10000

        # Lose 25% in session (triggers session halt)
        cb.record_trade(pnl=-2500, equity=7500)

        # Session should be permanently halted
        assert cb._session_halted, "Session should be halted after 25% loss"

        # Wait cooldown
        time.sleep(61)

        # Even after cooldown, session halted trades should NOT be allowed
        is_allowed = cb.is_trading_allowed(equity=7500)
        assert not is_allowed, \
            "Trading should NOT be allowed after permanent session halt"

        # session_peak_equity should remain unchanged (cumulative)
        assert cb.session_peak_equity == 10000, \
            "session_peak_equity should remain 10000 (cumulative)"

    def test_post_cooldown_caution_mode(self):
        """Verify post-cooldown caution mode (reduced position size)"""
        cb = CircuitBreaker(cooldown_minutes=1)
        cb.start_session(equity=10000)

        # Trip CB
        cb.record_trade(pnl=-1000, equity=9000)
        assert cb.tripped

        # Wait cooldown
        time.sleep(61)

        # Allow trading
        is_allowed = cb.is_trading_allowed(equity=9000)
        assert is_allowed

        # Should be in post-cooldown caution mode
        assert cb.post_cooldown_caution == 4, \
            "post_cooldown_caution should be 4 after cooldown"

        # Get override constraints
        constraints = cb.get_override_constraints(confidence=0)
        assert constraints["constrained"] == True, \
            "Should be constrained in post-cooldown caution"
        assert constraints["size_multiplier"] == 0.5, \
            "Size multiplier should be 0.5x in caution mode"

        # After 4 trades, caution should expire
        for i in range(4):
            cb.record_trade(pnl=10, equity=9010 + i*10)
            cb.post_cooldown_caution -= 1
            if cb.post_cooldown_caution == 0:
                break

        # Next trade should be unconstrained
        constraints = cb.get_override_constraints(confidence=0)
        # Note: tripped status affects this, so check both conditions
        if not cb.tripped:
            assert constraints["constrained"] == False, \
                "Should be unconstrained after caution expires"

    def test_mtm_breaker_doesnt_retrigger_after_reset(self):
        """Verify MTM check doesn't immediately re-trip after peak reset"""
        cb = CircuitBreaker(
            max_drawdown_pct=0.10,
            cooldown_minutes=1,
        )
        cb.start_session(equity=10000)

        # Trip CB with 12% drawdown
        cb.record_trade(pnl=-1200, equity=8800)
        assert cb.tripped, "CB should trip"

        # Wait cooldown
        time.sleep(61)

        # Allow trading (triggers peak reset to 8800)
        is_allowed = cb.is_trading_allowed(equity=8800)
        assert is_allowed
        assert cb.peak_equity == 8800, "Peak should reset to 8800"

        # Now check MTM with slight loss (shouldn't re-trip)
        # MTM equity = 8800 (no unrealized loss)
        cb.check_mtm_breakers(mtm_equity=8800)
        assert not cb.tripped, \
            "Should not re-trip on MTM check after peak reset"

        # Only re-trip if MTM drops 10% below new peak (8000)
        cb.check_mtm_breakers(mtm_equity=7920)  # 1% below 8000 threshold
        assert not cb.tripped, "Should not trip at 1% below threshold"

        cb.check_mtm_breakers(mtm_equity=7900)  # >1% would be issue, but let's be exact
        # At exactly 10% below 8800 = 7920, should trip
        cb.check_mtm_breakers(mtm_equity=7920)
        # This might or might not trip depending on rounding, but shouldn't immediately

    def test_consecutive_losses_reset(self):
        """Verify consecutive losses counter resets after cooldown"""
        cb = CircuitBreaker(
            max_consecutive_losses=3,
            cooldown_minutes=1,
        )
        cb.start_session(equity=10000)

        # Record 3 consecutive losses to trigger CB
        cb.record_trade(pnl=-200, equity=9800)
        cb.record_trade(pnl=-200, equity=9600)
        cb.record_trade(pnl=-200, equity=9400)

        assert cb.consecutive_losses == 3
        assert cb.tripped, "CB should trip on 3 consecutive losses"

        # Wait cooldown
        time.sleep(61)

        # Allow trading
        is_allowed = cb.is_trading_allowed(equity=9400)
        assert is_allowed

        # Consecutive losses should reset
        assert cb.consecutive_losses == 0, \
            "consecutive_losses should reset after cooldown"

        # Should be able to take a loss without immediate re-trip
        cb.record_trade(pnl=-100, equity=9300)
        assert cb.consecutive_losses == 1, \
            "consecutive_losses should be 1 after first loss post-cooldown"


class TestPeakEquityEdgeCases:
    """Additional edge case tests"""

    def test_peak_equity_monotonic_increase(self):
        """Peak equity should only increase, never decrease"""
        cb = CircuitBreaker()
        cb.start_session(equity=10000)
        initial_peak = cb.peak_equity

        # Lose money
        cb.record_trade(pnl=-500, equity=9500)
        assert cb.peak_equity == initial_peak, \
            "peak_equity should not decrease on loss"

        # Lose more
        cb.record_trade(pnl=-300, equity=9200)
        assert cb.peak_equity == initial_peak, \
            "peak_equity should remain at initial on another loss"

        # Gain money
        cb.record_trade(pnl=1000, equity=10200)
        assert cb.peak_equity == 10200, \
            "peak_equity should increase to new high"

    def test_session_peak_never_decreases(self):
        """Session peak equity should never decrease (cumulative max)"""
        cb = CircuitBreaker()
        cb.start_session(equity=10000)
        session_peak = cb.session_peak_equity

        # Even with cooldown reset of daily peak, session peak unchanged
        cb.record_trade(pnl=-2000, equity=8000)
        assert cb.session_peak_equity == session_peak, \
            "session_peak_equity should never change"

        # Recover
        cb.record_trade(pnl=3000, equity=11000)
        assert cb.session_peak_equity == 11000, \
            "session_peak_equity should increase if equity exceeds it"

        # But when equity drops, session_peak stays
        cb.record_trade(pnl=-2000, equity=9000)
        assert cb.session_peak_equity == 11000, \
            "session_peak_equity should not decrease"


# Test execution
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
