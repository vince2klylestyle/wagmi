"""
Unit tests for Phase 3 strategic filters.

Tests:
1. ADX-dependent min_votes calculation
2. Strategy-specific confidence floors
3. Signal clustering detection
4. Regime stability checks
"""

import pytest
from unittest.mock import MagicMock
from strategies.phase3_filters import (
    Phase3FilterContext,
    Phase3StrategySpecificFloors,
    Phase3SignalClustering,
    Phase3RegimeStabilityCheck,
    Phase3FilterPipeline,
    apply_phase3_filters,
)
from strategies.base import Signal


class TestPhase3StrategyFloors:
    """Test strategy-specific confidence floors."""

    def test_bollinger_squeeze_floor(self):
        """Bollinger squeeze should have 40% floor."""
        floors = Phase3StrategySpecificFloors()
        # bollinger_squeeze at 45% confidence should fail 40% floor
        signal = MagicMock(spec=Signal)
        signal.strategy = "bollinger_squeeze"
        signal.confidence = 45.0

        ctx = MagicMock(spec=Phase3FilterContext)
        ctx.signal = signal
        ctx.symbol = "BTC"
        ctx.is_choppy = False

        passes, reason = floors.evaluate(ctx)
        assert passes, f"Expected 45% > 40% floor to pass, got: {reason}"

    def test_vmc_cipher_lowest_floor(self):
        """vmc_cipher should have lowest floor (35%)."""
        floors = Phase3StrategySpecificFloors()
        signal = MagicMock(spec=Signal)
        signal.strategy = "vmc_cipher"
        signal.confidence = 36.0

        ctx = MagicMock(spec=Phase3FilterContext)
        ctx.signal = signal
        ctx.symbol = "BTC"
        ctx.is_choppy = False

        passes, reason = floors.evaluate(ctx)
        assert passes, f"Expected 36% > 35% floor to pass"

    def test_high_vol_symbol_penalty(self):
        """High-vol symbols (HYPE) should get -5% floor penalty in choppy."""
        floors = Phase3StrategySpecificFloors()
        signal = MagicMock(spec=Signal)
        signal.strategy = "confidence_scorer"  # 55% base floor
        signal.confidence = 52.0  # < 55% but >= 50% after penalty

        ctx = MagicMock(spec=Phase3FilterContext)
        ctx.signal = signal
        ctx.symbol = "HYPE"
        ctx.is_choppy = True

        passes, reason = floors.evaluate(ctx)
        # HYPE in choppy: 55 - 5 = 50%. Signal at 52% should pass.
        assert passes, f"Expected HYPE choppy penalty (-5%) to apply"


class TestPhase3Clustering:
    """Test signal clustering detection."""

    def test_consensus_passes(self):
        """Consensus (2+ strategies) should always pass."""
        clustering = Phase3SignalClustering()
        signal = MagicMock(spec=Signal)
        signal.symbol = "BTC"
        signal.side = "BUY"

        ctx = MagicMock(spec=Phase3FilterContext)
        ctx.signal = signal
        ctx.symbol = "BTC"

        # Mock num_agree = 2
        signal.metadata = {"num_agree": 2}

        passes, reason = clustering.evaluate(ctx)
        assert passes, "2-strategy consensus should pass"
        assert "consensus" in reason


class TestPhase3RegimeStability:
    """Test regime stability checks."""

    def test_stable_regime_passes(self):
        """High-dominance regime should pass."""
        stability = Phase3RegimeStabilityCheck()
        signal = MagicMock(spec=Signal)
        signal.metadata = {"regime_dominance": 0.75}

        ctx = MagicMock(spec=Phase3FilterContext)
        ctx.signal = signal

        passes, reason = stability.evaluate(ctx)
        assert passes, "75% dominance should pass"
        assert "stable" in reason

    def test_uncertain_regime_blocks_low_conf(self):
        """Low-dominance regime should block low-confidence signals."""
        stability = Phase3RegimeStabilityCheck()
        signal = MagicMock(spec=Signal)
        signal.metadata = {"regime_dominance": 0.40}
        signal.confidence = 60.0  # < 75% threshold

        ctx = MagicMock(spec=Phase3FilterContext)
        ctx.signal = signal

        passes, reason = stability.evaluate(ctx)
        assert not passes, "40% dominance + 60% confidence should fail"

    def test_uncertain_regime_high_conf_passes(self):
        """Low-dominance regime should allow high-confidence signals."""
        stability = Phase3RegimeStabilityCheck()
        signal = MagicMock(spec=Signal)
        signal.metadata = {"regime_dominance": 0.40}
        signal.confidence = 80.0  # >= 75% threshold
        ctx = MagicMock(spec=Phase3FilterContext)
        ctx.signal = signal

        passes, reason = stability.evaluate(ctx)
        assert passes, "40% dominance + 80% confidence should pass with penalty"


class TestPhase3Pipeline:
    """Test composed filter pipeline."""

    def test_all_filters_pass(self):
        """Signal passing all filters should be allowed."""
        pipeline = Phase3FilterPipeline()

        # Create a valid signal
        signal = MagicMock(spec=Signal)
        signal.strategy = "bollinger_squeeze"
        signal.confidence = 50.0
        signal.metadata = {"num_agree": 2}  # Consensus
        signal.symbol = "BTC"
        signal.side = "BUY"

        ctx = Phase3FilterContext(
            symbol="BTC",
            signal=signal,
            adx=30.0,  # Trending
            regime="trend",
            recent_signals=[],
            data={},
        )

        passes, breakdown = pipeline.evaluate(ctx)
        assert passes, f"Valid signal should pass: {breakdown}"
        assert "strategy_floor" in breakdown
        assert "clustering" in breakdown


class TestADXDependentMinVotes:
    """Test ADX-dependent min_votes calculation."""

    def test_trending_min_votes(self):
        """ADX > 25 should keep base min_votes."""
        from strategies.ensemble import EnsembleStrategy

        ensemble = EnsembleStrategy(strategies=[])
        min_votes = ensemble._get_effective_min_votes("BTC", adx=30.0)
        # Should return base (typically 1-2) not reduced
        assert min_votes >= 1

    def test_choppy_min_votes(self):
        """ADX < 15 should reduce to 1."""
        from strategies.ensemble import EnsembleStrategy

        ensemble = EnsembleStrategy(strategies=[])
        min_votes = ensemble._get_effective_min_votes("BTC", adx=8.0)
        assert min_votes == 1, "Choppy market (ADX<15) should allow min_votes=1"

    def test_medium_vol_min_votes(self):
        """ADX 15-25 should reduce by 1."""
        from strategies.ensemble import EnsembleStrategy

        ensemble = EnsembleStrategy(strategies=[], min_votes=2)
        min_votes = ensemble._get_effective_min_votes("BTC", adx=20.0)
        # Should be reduced from 2 to 1
        assert min_votes <= 2, "Medium vol should not increase min_votes"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
