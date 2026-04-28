"""Tests for Closed Trade Analyzer (W3-A)."""

import pytest
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from llm.learning.closed_trade_analyzer import (
    ClosedTradeAnalyzer,
    TradeLesson,
    SetupPattern,
)


class TestClosedTradeAnalyzer:
    """Test closed trade analysis."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return ClosedTradeAnalyzer()

    @pytest.fixture
    def decisions_file(self, tmp_path):
        """Create mock decisions.jsonl file."""
        decisions_path = tmp_path / "decisions.jsonl"

        # Write sample decisions
        now = datetime.utcnow()
        decisions = [
            {
                "timestamp": (now - timedelta(hours=1)).isoformat(),
                "symbol": "BTC",
                "action": "go",
                "regime": "trending_bear",
                "thesis": "Strong downtrend on 1h",
                "confidence": 82.0,
                "n_agree": 3,
                "leverage": 4.0,
            },
            {
                "timestamp": (now - timedelta(hours=2)).isoformat(),
                "symbol": "ETH",
                "action": "go",
                "regime": "ranging",
                "thesis": "Consolidation pattern",
                "confidence": 65.0,
                "n_agree": 2,
                "leverage": 2.0,
            },
        ]

        with open(decisions_path, "w") as f:
            for decision in decisions:
                f.write(json.dumps(decision) + "\n")

        return decisions_path

    def test_analyzer_initialization(self, analyzer):
        """Analyzer should initialize with empty patterns."""
        assert analyzer.patterns == {}
        assert analyzer.decisions_log_path is not None

    def test_analyze_profitable_trade(self, analyzer, decisions_file):
        """Analyze a profitable BTC SHORT trade."""
        analyzer.decisions_log_path = decisions_file

        entry_time = datetime.utcnow() - timedelta(hours=1)
        exit_time = datetime.utcnow()

        lesson = analyzer.analyze(
            trade_id="trade_001",
            symbol="BTC",
            entry_price=42000.0,
            exit_price=41000.0,  # Profitable SHORT
            entry_time=entry_time,
            exit_time=exit_time,
            position_size=0.1,
            entry_risk_pct=0.02,  # 2% stop
            regime="trending_bear",
            side="SELL",
        )

        assert lesson is not None
        assert lesson.trade_id == "trade_001"
        assert lesson.symbol == "BTC"
        assert lesson.pnl_usd > 0  # Profitable
        assert lesson.pnl_pct > 0
        assert lesson.r_multiple > 0
        assert lesson.setup_type == "trending_bear+3-agree+80conf"
        assert lesson.confidence_predicted == 82.0

    def test_analyze_losing_trade(self, analyzer, decisions_file):
        """Analyze a losing trade."""
        analyzer.decisions_log_path = decisions_file

        entry_time = datetime.utcnow() - timedelta(hours=1)
        exit_time = datetime.utcnow()

        lesson = analyzer.analyze(
            trade_id="trade_002",
            symbol="BTC",
            entry_price=42000.0,
            exit_price=43000.0,  # Losing SHORT
            entry_time=entry_time,
            exit_time=exit_time,
            position_size=0.1,
            entry_risk_pct=0.02,
            regime="trending_bear",
            side="SELL",
        )

        assert lesson is not None
        assert lesson.pnl_usd < 0  # Loss
        assert lesson.pnl_pct < 0
        assert lesson.confidence_correct is False

    def test_overconfidence_detection(self, analyzer, decisions_file):
        """Should detect overconfident predictions."""
        analyzer.decisions_log_path = decisions_file

        entry_time = datetime.utcnow() - timedelta(hours=1)
        exit_time = datetime.utcnow()

        lesson = analyzer.analyze(
            trade_id="trade_003",
            symbol="BTC",
            entry_price=42000.0,
            exit_price=43000.0,  # Losing despite high confidence
            entry_time=entry_time,
            exit_time=exit_time,
            position_size=0.1,
            entry_risk_pct=0.02,
            regime="trending_bear",
            side="SELL",
        )

        assert lesson is not None
        # Should have overconfidence lesson (82% confidence but lost)
        assert any("OVERCONFIDENT" in l for l in lesson.lessons)

    def test_pattern_tracking(self, analyzer, tmp_path):
        """Should track patterns after multiple trades."""
        # Create decisions file with matching timestamps
        decisions_path = tmp_path / "decisions.jsonl"
        base_time = datetime.utcnow()

        decisions = []
        for i in range(3):
            decisions.append({
                "timestamp": (base_time - timedelta(hours=i)).isoformat(),
                "symbol": "BTC",
                "action": "go",
                "regime": "trending_bear",
                "thesis": "Strong downtrend",
                "confidence": 82.0,
                "n_agree": 3,
                "leverage": 4.0,
            })

        with open(decisions_path, "w") as f:
            for decision in decisions:
                f.write(json.dumps(decision) + "\n")

        analyzer.decisions_log_path = decisions_path

        # Analyze 3 trades with same setup
        for i in range(3):
            entry_time = base_time - timedelta(hours=i)
            exit_time = entry_time + timedelta(hours=1)
            analyzer.analyze(
                trade_id=f"trade_{i:03d}",
                symbol="BTC",
                entry_price=42000.0,
                exit_price=41000.0 if i < 2 else 43000.0,  # 2 wins, 1 loss
                entry_time=entry_time,
                exit_time=exit_time,
                position_size=0.1,
                entry_risk_pct=0.02,
                regime="trending_bear",
                side="SELL",
            )

        # Check pattern
        patterns = analyzer.get_patterns()
        assert "trending_bear+3-agree+80conf" in patterns

        pattern = patterns["trending_bear+3-agree+80conf"]
        assert pattern.sample_size == 3
        assert pattern.win_count == 2
        assert pattern.loss_count == 1
        assert pattern.total_pnl_usd > 0

    def test_confidence_bin_tracking(self, analyzer, decisions_file):
        """Should track win rates per confidence bin."""
        analyzer.decisions_log_path = decisions_file

        entry_time = datetime.utcnow() - timedelta(hours=1)

        lesson = analyzer.analyze(
            trade_id="trade_bin_001",
            symbol="BTC",
            entry_price=42000.0,
            exit_price=41000.0,
            entry_time=entry_time,
            exit_time=entry_time + timedelta(hours=1),
            position_size=0.1,
            entry_risk_pct=0.02,
            regime="trending_bear",
            side="SELL",
        )

        pattern = analyzer.get_pattern("trending_bear+3-agree+80conf")
        assert pattern is not None
        assert 80 in pattern.confidence_bins  # 80-90 bin
        assert pattern.confidence_bins[80]["wins"] == 1

    def test_hold_duration_calculation(self, analyzer, decisions_file):
        """Should correctly calculate hold duration."""
        analyzer.decisions_log_path = decisions_file

        entry_time = datetime.utcnow() - timedelta(minutes=30)
        exit_time = datetime.utcnow()

        lesson = analyzer.analyze(
            trade_id="trade_duration",
            symbol="BTC",
            entry_price=42000.0,
            exit_price=41000.0,
            entry_time=entry_time,
            exit_time=exit_time,
            position_size=0.1,
            entry_risk_pct=0.02,
            regime="trending_bear",
            side="SELL",
        )

        assert lesson is not None
        assert 25 <= lesson.hold_duration_minutes <= 35  # ~30 min

    def test_large_loss_detection(self, analyzer, tmp_path):
        """Should flag large losses as risk."""
        # Create decisions file
        decisions_path = tmp_path / "decisions.jsonl"
        entry_time = datetime.utcnow() - timedelta(hours=1)

        with open(decisions_path, "w") as f:
            f.write(json.dumps({
                "timestamp": entry_time.isoformat(),
                "symbol": "BTC",
                "action": "go",
                "regime": "trending_bear",
                "thesis": "Expected downtrend",
                "confidence": 82.0,
                "n_agree": 3,
                "leverage": 4.0,
            }) + "\n")

        analyzer.decisions_log_path = decisions_path

        lesson = analyzer.analyze(
            trade_id="trade_large_loss",
            symbol="BTC",
            entry_price=42000.0,
            exit_price=45000.0,  # Large loss on SHORT (7.1% loss)
            entry_time=entry_time,
            exit_time=entry_time + timedelta(hours=1),
            position_size=1.0,  # Large position
            entry_risk_pct=0.02,
            regime="trending_bear",
            side="SELL",
        )

        assert lesson is not None
        assert lesson.pnl_pct < -0.05  # Large loss
        assert "large_loss" in lesson.risk_flags

    def test_instant_stop_detection(self, analyzer, decisions_file):
        """Should flag immediate stops."""
        analyzer.decisions_log_path = decisions_file

        entry_time = datetime.utcnow()

        lesson = analyzer.analyze(
            trade_id="trade_instant",
            symbol="BTC",
            entry_price=42000.0,
            exit_price=42840.0,  # Hit stop immediately
            entry_time=entry_time,
            exit_time=entry_time + timedelta(seconds=30),
            position_size=0.1,
            entry_risk_pct=0.02,
            regime="trending_bear",
            side="SELL",
        )

        assert lesson is not None
        assert "instant_stop" in lesson.risk_flags

    def test_missing_decision_handling(self, analyzer):
        """Should handle missing decisions gracefully."""
        analyzer.decisions_log_path = Path("/nonexistent/path.jsonl")

        entry_time = datetime.utcnow() - timedelta(hours=1)

        lesson = analyzer.analyze(
            trade_id="trade_no_decision",
            symbol="BTC",
            entry_price=42000.0,
            exit_price=41000.0,
            entry_time=entry_time,
            exit_time=entry_time + timedelta(hours=1),
            position_size=0.1,
            entry_risk_pct=0.02,
            regime="trending_bear",
            side="SELL",
        )

        # Should still create lesson, but with default values
        assert lesson is not None
        assert lesson.confidence_predicted == 0.0

    def test_r_multiple_calculation(self, analyzer, decisions_file):
        """Should correctly calculate R-multiple."""
        analyzer.decisions_log_path = decisions_file

        entry_price = 42000.0
        exit_price = 41000.0
        entry_risk_pct = 0.02  # 2% of entry

        lesson = analyzer.analyze(
            trade_id="trade_r_calc",
            symbol="BTC",
            entry_price=entry_price,
            exit_price=exit_price,
            entry_time=datetime.utcnow() - timedelta(hours=1),
            exit_time=datetime.utcnow(),
            position_size=0.1,
            entry_risk_pct=entry_risk_pct,
            regime="trending_bear",
            side="SELL",
        )

        # Move = 1000, Stop = 840, R = 1000/840 ≈ 1.19
        assert lesson is not None
        assert lesson.r_multiple > 1.0

    def test_pnl_calculation_buy_side(self, analyzer, decisions_file):
        """Should correctly calculate PnL for BUY trades."""
        analyzer.decisions_log_path = decisions_file

        entry_price = 42000.0
        exit_price = 43000.0
        position_size = 0.1
        expected_pnl = (exit_price - entry_price) * position_size

        lesson = analyzer.analyze(
            trade_id="trade_buy_pnl",
            symbol="BTC",
            entry_price=entry_price,
            exit_price=exit_price,
            entry_time=datetime.utcnow() - timedelta(hours=1),
            exit_time=datetime.utcnow(),
            position_size=position_size,
            entry_risk_pct=0.02,
            regime="trending_bull",
            side="BUY",
        )

        assert lesson is not None
        assert abs(lesson.pnl_usd - expected_pnl) < 0.01

    def test_pnl_calculation_sell_side(self, analyzer, decisions_file):
        """Should correctly calculate PnL for SELL trades."""
        analyzer.decisions_log_path = decisions_file

        entry_price = 42000.0
        exit_price = 41000.0
        position_size = 0.1
        expected_pnl = (entry_price - exit_price) * position_size

        lesson = analyzer.analyze(
            trade_id="trade_sell_pnl",
            symbol="BTC",
            entry_price=entry_price,
            exit_price=exit_price,
            entry_time=datetime.utcnow() - timedelta(hours=1),
            exit_time=datetime.utcnow(),
            position_size=position_size,
            entry_risk_pct=0.02,
            regime="trending_bear",
            side="SELL",
        )

        assert lesson is not None
        assert abs(lesson.pnl_usd - expected_pnl) < 0.01


class TestSetupPattern:
    """Test setup pattern dataclass."""

    def test_pattern_initialization(self):
        """Pattern should initialize with correct defaults."""
        pattern = SetupPattern(setup_type="trending_bear+3-agree+80conf")

        assert pattern.setup_type == "trending_bear+3-agree+80conf"
        assert pattern.win_count == 0
        assert pattern.loss_count == 0
        assert pattern.sample_size == 0
        assert pattern.confidence_bins == {}
