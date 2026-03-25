"""
Tests for Monte Carlo Ruin Probability Checker.

Covers:
- Known safe sizing scenarios
- Known dangerous sizing scenarios
- Edge cases (100% WR, 0% WR, tiny/huge risk)
- Performance (<1 second for 1000 sims)
- is_size_safe convenience function
"""

import time
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from execution.monte_carlo_ruin import simulate_ruin, is_size_safe, RuinSimulationResult


# ---------------------------------------------------------------------------
# Known safe sizing
# ---------------------------------------------------------------------------

class TestSafeSizing:
    """50% WR, 2:1 payoff, 5% risk -> positive expectancy, near-zero ruin."""

    def test_low_ruin_probability(self):
        result = simulate_ruin(
            win_rate=0.50, payoff_ratio=2.0, risk_per_trade_pct=5.0,
            num_simulations=2000, num_trades=50, seed=42,
        )
        # With positive expectancy and moderate risk, ruin should be very low
        assert result.ruin_probability < 0.05, (
            f"Expected near-zero ruin, got {result.ruin_probability:.4f}"
        )

    def test_median_equity_grows(self):
        result = simulate_ruin(
            win_rate=0.50, payoff_ratio=2.0, risk_per_trade_pct=5.0,
            num_simulations=2000, num_trades=50, seed=42,
        )
        # Positive expectancy should grow median equity above starting 1.0
        assert result.median_equity > 1.0, (
            f"Expected median equity > 1.0, got {result.median_equity:.4f}"
        )

    def test_conservative_sizing_zero_ruin(self):
        """Very conservative: 60% WR, 2:1 payoff, 2% risk."""
        result = simulate_ruin(
            win_rate=0.60, payoff_ratio=2.0, risk_per_trade_pct=2.0,
            num_simulations=2000, num_trades=50, seed=42,
        )
        assert result.ruin_probability == 0.0, (
            f"Conservative sizing should have 0% ruin, got {result.ruin_probability:.4f}"
        )


# ---------------------------------------------------------------------------
# Known dangerous sizing
# ---------------------------------------------------------------------------

class TestDangerousSizing:
    """50% WR, 1:1 payoff, 30% risk -> zero-edge with huge risk = high ruin."""

    def test_high_ruin_probability(self):
        result = simulate_ruin(
            win_rate=0.50, payoff_ratio=1.0, risk_per_trade_pct=30.0,
            num_simulations=2000, num_trades=50, seed=42,
        )
        # No edge + 30% risk per trade = most paths should hit ruin
        assert result.ruin_probability > 0.30, (
            f"Expected high ruin, got {result.ruin_probability:.4f}"
        )

    def test_negative_expectancy_high_ruin(self):
        """40% WR, 1:1 payoff, 20% risk -> negative edge, big risk."""
        result = simulate_ruin(
            win_rate=0.40, payoff_ratio=1.0, risk_per_trade_pct=20.0,
            num_simulations=2000, num_trades=50, seed=42,
        )
        assert result.ruin_probability > 0.50, (
            f"Negative edge + big risk should ruin often, got {result.ruin_probability:.4f}"
        )

    def test_worst_path_is_devastating(self):
        result = simulate_ruin(
            win_rate=0.50, payoff_ratio=1.0, risk_per_trade_pct=30.0,
            num_simulations=2000, num_trades=50, seed=42,
        )
        assert result.worst_path_equity < 0.10, (
            f"Worst path should be near zero, got {result.worst_path_equity:.4f}"
        )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_100pct_win_rate(self):
        """100% WR = zero ruin no matter what."""
        result = simulate_ruin(
            win_rate=1.0, payoff_ratio=1.0, risk_per_trade_pct=50.0,
            num_simulations=500, num_trades=50, seed=42,
        )
        assert result.ruin_probability == 0.0
        assert result.median_equity > 1.0
        assert result.worst_path_equity > 1.0

    def test_0pct_win_rate(self):
        """0% WR = guaranteed ruin with any meaningful risk."""
        result = simulate_ruin(
            win_rate=0.0, payoff_ratio=2.0, risk_per_trade_pct=10.0,
            num_simulations=500, num_trades=50, seed=42,
        )
        assert result.ruin_probability == 1.0
        assert result.worst_path_equity < 0.10

    def test_tiny_risk(self):
        """0.1% risk per trade -> virtually impossible to ruin even with no edge."""
        result = simulate_ruin(
            win_rate=0.50, payoff_ratio=1.0, risk_per_trade_pct=0.1,
            num_simulations=1000, num_trades=50, seed=42,
        )
        assert result.ruin_probability == 0.0

    def test_huge_risk_100pct(self):
        """100% risk per trade = single loss = ruin."""
        result = simulate_ruin(
            win_rate=0.50, payoff_ratio=2.0, risk_per_trade_pct=100.0,
            num_simulations=1000, num_trades=50, seed=42,
        )
        # Very first loss wipes account
        assert result.ruin_probability > 0.90

    def test_zero_risk(self):
        """0% risk -> equity never changes, no ruin."""
        result = simulate_ruin(
            win_rate=0.50, payoff_ratio=2.0, risk_per_trade_pct=0.0,
            num_simulations=100, num_trades=50, seed=42,
        )
        assert result.ruin_probability == 0.0
        assert result.median_equity == 1.0

    def test_single_simulation(self):
        """Edge case: only 1 sim path."""
        result = simulate_ruin(
            win_rate=0.50, payoff_ratio=2.0, risk_per_trade_pct=5.0,
            num_simulations=1, num_trades=50, seed=42,
        )
        assert result.num_simulations == 1
        assert result.ruin_probability in (0.0, 1.0)

    def test_single_trade(self):
        """Edge case: only 1 trade per path."""
        result = simulate_ruin(
            win_rate=0.50, payoff_ratio=2.0, risk_per_trade_pct=5.0,
            num_simulations=1000, num_trades=1, seed=42,
        )
        assert result.num_trades == 1
        # 5% risk on 1 trade can't cause ruin (equity stays above 10%)
        assert result.ruin_probability == 0.0

    def test_zero_payoff_ratio(self):
        """0 payoff ratio: wins gain nothing, losses lose risk. Always bleeds."""
        result = simulate_ruin(
            win_rate=0.50, payoff_ratio=0.0, risk_per_trade_pct=10.0,
            num_simulations=500, num_trades=50, seed=42,
        )
        # Wins gain nothing, losses lose 10% -> guaranteed decline
        assert result.ruin_probability > 0.5


# ---------------------------------------------------------------------------
# Result structure
# ---------------------------------------------------------------------------

class TestResultStructure:
    def test_result_dataclass_fields(self):
        result = simulate_ruin(0.5, 2.0, 5.0, num_simulations=10, num_trades=10, seed=1)
        assert isinstance(result, RuinSimulationResult)
        assert hasattr(result, "ruin_probability")
        assert hasattr(result, "median_equity")
        assert hasattr(result, "worst_path_equity")
        assert hasattr(result, "best_path_equity")
        assert hasattr(result, "percentile_5th")
        assert hasattr(result, "percentile_95th")
        assert hasattr(result, "elapsed_ms")

    def test_to_dict(self):
        result = simulate_ruin(0.5, 2.0, 5.0, num_simulations=10, num_trades=10, seed=1)
        d = result.to_dict()
        assert "ruin_probability" in d
        assert "ruin_probability_pct" in d
        assert "median_equity" in d
        assert "elapsed_ms" in d

    def test_percentile_ordering(self):
        result = simulate_ruin(0.5, 2.0, 5.0, num_simulations=500, num_trades=50, seed=42)
        assert result.worst_path_equity <= result.percentile_5th
        assert result.percentile_5th <= result.median_equity
        assert result.median_equity <= result.percentile_95th
        assert result.percentile_95th <= result.best_path_equity


# ---------------------------------------------------------------------------
# is_size_safe convenience function
# ---------------------------------------------------------------------------

class TestIsSizeSafe:
    def test_safe_returns_true(self):
        safe, stats = is_size_safe(
            win_rate=0.55, payoff_ratio=2.0, risk_pct=3.0,
            num_simulations=1000, seed=42,
        )
        assert safe is True
        assert stats["is_safe"] is True

    def test_dangerous_returns_false(self):
        safe, stats = is_size_safe(
            win_rate=0.40, payoff_ratio=1.0, risk_pct=25.0,
            num_simulations=2000, seed=42,
        )
        assert safe is False
        assert stats["is_safe"] is False

    def test_returns_dict_with_stats(self):
        safe, stats = is_size_safe(0.50, 2.0, 5.0, num_simulations=100, seed=1)
        assert isinstance(stats, dict)
        assert "ruin_probability_pct" in stats
        assert "median_equity" in stats
        assert "max_ruin_pct" in stats

    def test_custom_max_ruin(self):
        """With very lax max_ruin, even risky sizing passes."""
        safe, stats = is_size_safe(
            win_rate=0.50, payoff_ratio=1.0, risk_pct=20.0,
            max_ruin_pct=0.99,  # Accept up to 99% ruin
            num_simulations=500, seed=42,
        )
        assert safe is True


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------

class TestPerformance:
    def test_1000_sims_under_1_second(self):
        """1000 simulations x 50 trades must complete in < 1 second."""
        start = time.perf_counter()
        simulate_ruin(
            win_rate=0.50, payoff_ratio=2.0, risk_per_trade_pct=5.0,
            num_simulations=1000, num_trades=50,
        )
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, f"Took {elapsed:.3f}s, must be < 1s"

    def test_result_reports_elapsed_ms(self):
        result = simulate_ruin(0.5, 2.0, 5.0, num_simulations=100, num_trades=50)
        assert result.elapsed_ms > 0
        assert result.elapsed_ms < 5000  # Sanity: shouldn't take 5 seconds


# ---------------------------------------------------------------------------
# Determinism with seed
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_seed_same_result(self):
        r1 = simulate_ruin(0.5, 2.0, 5.0, num_simulations=500, seed=123)
        r2 = simulate_ruin(0.5, 2.0, 5.0, num_simulations=500, seed=123)
        assert r1.ruin_probability == r2.ruin_probability
        assert r1.median_equity == r2.median_equity
        assert r1.worst_path_equity == r2.worst_path_equity

    def test_different_seed_different_result(self):
        r1 = simulate_ruin(0.5, 2.0, 5.0, num_simulations=500, seed=1)
        r2 = simulate_ruin(0.5, 2.0, 5.0, num_simulations=500, seed=999)
        # Could theoretically match, but with 500 sims it's astronomically unlikely
        # Check at least one metric differs
        assert (
            r1.median_equity != r2.median_equity
            or r1.worst_path_equity != r2.worst_path_equity
        )
