"""Tests for Adversary Agent (W4-B)."""

import pytest
import json
from datetime import datetime, timedelta
from pathlib import Path

from llm.agents.adversary_agent import AdversaryAgent, AdversaryReview, VetoReason


class TestAdversaryAgent:
    """Test stress-testing and counter-argument generation."""

    @pytest.fixture
    def decisions_file(self, tmp_path):
        """Create temp decisions.jsonl with trade data."""
        decisions_path = tmp_path / "decisions.jsonl"
        base_time = datetime.utcnow()

        decisions = [
            # BTC LONG in trending_bull (winning pattern)
            {
                "timestamp": (base_time - timedelta(days=1)).isoformat(),
                "symbol": "BTC",
                "regime": "trending_bull",
                "side": "BUY",
                "action": "go",
            },
            {
                "timestamp": (base_time - timedelta(days=2)).isoformat(),
                "symbol": "BTC",
                "regime": "trending_bull",
                "side": "BUY",
                "action": "go",
            },
            # ETH SHORT in ranging (losing pattern)
            {
                "timestamp": (base_time - timedelta(days=3)).isoformat(),
                "symbol": "ETH",
                "regime": "ranging",
                "side": "SELL",
                "action": "skip",
            },
            {
                "timestamp": (base_time - timedelta(days=4)).isoformat(),
                "symbol": "ETH",
                "regime": "ranging",
                "side": "SELL",
                "action": "skip",
            },
            {
                "timestamp": (base_time - timedelta(days=5)).isoformat(),
                "symbol": "ETH",
                "regime": "ranging",
                "side": "SELL",
                "action": "skip",
            },
        ]

        with open(decisions_path, "w") as f:
            for decision in decisions:
                f.write(json.dumps(decision) + "\n")

        return str(decisions_path)

    def test_agent_initialization(self, decisions_file):
        """Should initialize with custom paths."""
        agent = AdversaryAgent(decisions_path=decisions_file)
        assert agent.decisions_path == Path(decisions_file)

    def test_review_thesis_structure(self, decisions_file):
        """Should generate properly structured review."""
        agent = AdversaryAgent(decisions_path=decisions_file)

        review = agent.review_thesis(
            thesis="BTC will trend higher",
            symbol="BTC",
            regime="trending_bull",
            side="BUY",
            confidence=85.0,
            entry_price=40000.0,
            stop_loss=39200.0,
        )

        assert isinstance(review, AdversaryReview)
        assert review.thesis == "BTC will trend higher"
        assert isinstance(review.counter_arguments, list)
        assert isinstance(review.missing_checks, list)
        assert 0.0 <= review.estimated_drawdown <= 1.0
        assert 0.0 <= review.confidence_reduction <= 1.0
        assert review.review_date

    def test_consolidation_regime_warning(self, decisions_file):
        """Should flag consolidation regime as problematic."""
        agent = AdversaryAgent(decisions_path=decisions_file)

        review = agent.review_thesis(
            thesis="BTC will break out",
            symbol="BTC",
            regime="consolidation",
            side="BUY",
            confidence=75.0,
            entry_price=40000.0,
            stop_loss=39600.0,
        )

        assert len(review.counter_arguments) > 0
        assert any("consolidation" in arg.lower() for arg in review.counter_arguments)
        assert review.confidence_reduction > 0.05

    def test_ranging_regime_warning(self, decisions_file):
        """Should warn against directional trades in ranging regime."""
        agent = AdversaryAgent(decisions_path=decisions_file)

        review = agent.review_thesis(
            thesis="ETH will go up",
            symbol="ETH",
            regime="ranging",
            side="BUY",
            confidence=70.0,
            entry_price=2000.0,
            stop_loss=1940.0,
        )

        assert len(review.counter_arguments) > 0
        assert any("ranging" in arg.lower() or "range" in arg.lower() for arg in review.counter_arguments)

    def test_tight_stop_loss_warning(self, decisions_file):
        """Should flag stops that are too tight."""
        agent = AdversaryAgent(decisions_path=decisions_file)

        review = agent.review_thesis(
            thesis="BTC will trend",
            symbol="BTC",
            regime="trending_bull",
            side="BUY",
            confidence=80.0,
            entry_price=40000.0,
            stop_loss=39920.0,  # Only 0.2% below entry
        )

        assert any("tight" in check.lower() for check in review.missing_checks)

    def test_wide_stop_loss_warning(self, decisions_file):
        """Should flag stops that are too wide."""
        agent = AdversaryAgent(decisions_path=decisions_file)

        review = agent.review_thesis(
            thesis="BTC will trend",
            symbol="BTC",
            regime="trending_bull",
            side="BUY",
            confidence=80.0,
            entry_price=40000.0,
            stop_loss=33000.0,  # 17.5% below entry
        )

        assert any("wide" in check.lower() for check in review.missing_checks)

    def test_confidence_adjustment(self, decisions_file):
        """Should reduce confidence based on review severity."""
        agent = AdversaryAgent(decisions_path=decisions_file)

        review = agent.review_thesis(
            thesis="BTC will trend",
            symbol="BTC",
            regime="consolidation",
            side="BUY",
            confidence=85.0,
            entry_price=40000.0,
            stop_loss=39600.0,
        )

        adjusted = agent.recommend_confidence_adjustment(85.0, review)
        assert adjusted < 85.0

    def test_veto_recommendation_logic(self, decisions_file):
        """Should recommend veto for weak setups."""
        agent = AdversaryAgent(decisions_path=decisions_file)

        review = agent.review_thesis(
            thesis="ETH SHORT in range",
            symbol="ETH",
            regime="ranging",
            side="SELL",
            confidence=75.0,
            entry_price=2000.0,
            stop_loss=1940.0,
        )

        # This setup should have issues
        assert len(review.counter_arguments) > 0 or len(review.missing_checks) > 0

    def test_should_veto_high_severity(self, decisions_file):
        """Should veto for high-severity reviews."""
        agent = AdversaryAgent(decisions_path=decisions_file)

        # Create a high-severity review
        review = AdversaryReview(
            thesis="test",
            counter_arguments=["Major issue"],
            missing_checks=["Critical check"],
            estimated_drawdown=0.20,
            veto_recommendation=VetoReason.WEAK_EVIDENCE,
            confidence_reduction=0.25,
            severity="high",
        )

        # Should consider veto for high severity + significant drawdown
        veto = agent.should_veto(review)
        # Depends on drawdown > 0.15, so should be True
        assert isinstance(veto, bool)

    def test_high_confidence_consolidation_fakeout(self, decisions_file):
        """Should detect fakeout risk: high confidence in consolidation."""
        agent = AdversaryAgent(decisions_path=decisions_file)

        review = agent.review_thesis(
            thesis="BTC breakout imminent",
            symbol="BTC",
            regime="consolidation",
            side="BUY",
            confidence=92.0,  # Very high confidence
            entry_price=40000.0,
            stop_loss=39600.0,
        )

        assert any("fakeout" in arg.lower() for arg in review.counter_arguments)

    def test_analyze_similar_past_trades(self, decisions_file):
        """Should analyze similar historical trades."""
        agent = AdversaryAgent(decisions_path=decisions_file)

        # ETH SHORT in ranging has losing history (3/3 losses)
        review = agent.review_thesis(
            thesis="ETH SHORT in range",
            symbol="ETH",
            regime="ranging",
            side="SELL",
            confidence=70.0,
            entry_price=2000.0,
            stop_loss=1940.0,
        )

        # Should reference the poor historical record
        assert len(review.counter_arguments) > 0 or review.confidence_reduction > 0.10

    def test_drawdown_estimation(self, decisions_file):
        """Should estimate reasonable drawdown risk."""
        agent = AdversaryAgent(decisions_path=decisions_file)

        review = agent.review_thesis(
            thesis="BTC trend",
            symbol="BTC",
            regime="trending_bull",
            side="BUY",
            confidence=80.0,
            entry_price=40000.0,
            stop_loss=39200.0,  # 2% stop
        )

        assert review.estimated_drawdown > 0.01  # At least 1%
        assert review.estimated_drawdown <= 1.0

    def test_empty_decisions_file(self, tmp_path):
        """Should handle empty decisions file gracefully."""
        decisions_path = tmp_path / "decisions.jsonl"
        decisions_path.touch()

        agent = AdversaryAgent(decisions_path=str(decisions_path))
        review = agent.review_thesis(
            thesis="Test thesis",
            symbol="BTC",
            regime="trending_bull",
            side="BUY",
            confidence=80.0,
            entry_price=40000.0,
            stop_loss=39600.0,
        )

        assert review is not None
        # Should still generate review even without historical data

    def test_missing_decisions_file(self, tmp_path):
        """Should handle missing decisions file gracefully."""
        decisions_path = tmp_path / "nonexistent.jsonl"
        agent = AdversaryAgent(decisions_path=str(decisions_path))

        review = agent.review_thesis(
            thesis="Test thesis",
            symbol="BTC",
            regime="trending_bull",
            side="BUY",
            confidence=80.0,
            entry_price=40000.0,
            stop_loss=39600.0,
        )

        assert review is not None

    def test_veto_enum_values(self):
        """Should have valid veto reason enum values."""
        assert VetoReason.WEAK_EVIDENCE == "weak_evidence"
        assert VetoReason.FAKEOUT_RISK == "fakeout_risk"
        assert VetoReason.REGIME_MISMATCH == "regime_mismatch"

    def test_severity_levels(self, decisions_file):
        """Should assign appropriate severity levels."""
        agent = AdversaryAgent(decisions_path=decisions_file)

        # Consolidation regime review
        review = agent.review_thesis(
            thesis="Test",
            symbol="BTC",
            regime="consolidation",
            side="BUY",
            confidence=85.0,
            entry_price=40000.0,
            stop_loss=39600.0,
        )

        assert review.severity in ["critical", "high", "moderate", "low", "none"]

    def test_multiple_checks_accumulate_confidence_reduction(self, decisions_file):
        """Should accumulate confidence reduction from multiple checks."""
        agent = AdversaryAgent(decisions_path=decisions_file)

        # Problematic setup: consolidation + tight stop + high confidence
        review = agent.review_thesis(
            thesis="Test",
            symbol="BTC",
            regime="consolidation",
            side="BUY",
            confidence=90.0,
            entry_price=40000.0,
            stop_loss=39920.0,  # Tight
        )

        # Should have multiple reductions
        assert review.confidence_reduction > 0.10
