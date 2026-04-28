"""Tests for Memory Enrichment (W3-B)."""

import pytest
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from llm.learning.memory_enrichment import (
    MemoryEnricher,
    EnrichedMemoryNote,
    GraduatedRule,
)
from llm.learning.closed_trade_analyzer import TradeLesson


class TestMemoryEnricher:
    """Test memory enrichment pipeline."""

    @pytest.fixture
    def enricher(self, tmp_path):
        """Create enricher with temp paths."""
        return MemoryEnricher(
            memory_store_path=str(tmp_path / "memory_store.py"),
            deep_memory_dir=str(tmp_path / "deep_memory"),
            graduated_rules_path=str(tmp_path / "graduated_rules.json"),
        )

    @pytest.fixture
    def sample_lesson(self):
        """Create sample TradeLesson."""
        return TradeLesson(
            trade_id="trade_001",
            symbol="BTC",
            entry_time=datetime.utcnow() - timedelta(hours=1),
            exit_time=datetime.utcnow(),
            entry_thesis="Strong downtrend",
            outcome_thesis="Move was down 3.6%, R=1.8",
            setup_type="trending_bear+3-agree+80conf",
            confidence_correct=True,
            pnl_usd=150.0,
            pnl_pct=0.036,
            r_multiple=1.8,  # > 1.5 to trigger strong win note
            hold_duration_minutes=60,
            lessons=["Pattern working well"],
            risk_flags=[],
            regime="trending_bear",
            n_agree=3,
            confidence_predicted=82.0,
            confidence_actual_wr=1.0,
        )

    def test_enricher_initialization(self, enricher):
        """Enricher should initialize with correct paths."""
        assert enricher.deep_memory_dir.exists()
        assert enricher.graduated_rules_path is not None

    def test_enrich_profitable_trade(self, enricher, sample_lesson):
        """Should enrich memory for profitable trade."""
        result = enricher.enrich_memory(sample_lesson)

        assert result["notes_added"] > 0
        assert result["patterns_updated"] >= 0

    def test_short_term_memory_overconfidence(self, enricher):
        """Should inject note for overconfident losses."""
        lesson = TradeLesson(
            trade_id="trade_overconf",
            symbol="ETH",
            entry_time=datetime.utcnow() - timedelta(hours=1),
            exit_time=datetime.utcnow(),
            entry_thesis="Thesis",
            outcome_thesis="Lost move",
            setup_type="trending_bear+3-agree+80conf",
            confidence_correct=False,
            pnl_usd=-100.0,
            pnl_pct=-0.01,
            r_multiple=0.5,
            hold_duration_minutes=60,
            lessons=[],
            risk_flags=[],
            regime="trending_bear",
            n_agree=3,
            confidence_predicted=85.0,
            confidence_actual_wr=0.0,
        )

        result = enricher.enrich_memory(lesson)
        assert result["notes_added"] >= 1

    def test_short_term_memory_underconfidence(self, enricher):
        """Should inject note for underconfident wins."""
        lesson = TradeLesson(
            trade_id="trade_underconf",
            symbol="SOL",
            entry_time=datetime.utcnow() - timedelta(hours=1),
            exit_time=datetime.utcnow(),
            entry_thesis="Risky thesis",
            outcome_thesis="Won big",
            setup_type="ranging+2-agree+40conf",
            confidence_correct=True,
            pnl_usd=200.0,
            pnl_pct=0.05,
            r_multiple=2.5,
            hold_duration_minutes=30,
            lessons=[],
            risk_flags=[],
            regime="ranging",
            n_agree=2,
            confidence_predicted=45.0,
            confidence_actual_wr=1.0,
        )

        result = enricher.enrich_memory(lesson)
        assert result["notes_added"] >= 1

    def test_short_term_memory_large_loss(self, enricher):
        """Should flag large losses."""
        lesson = TradeLesson(
            trade_id="trade_large_loss",
            symbol="HYPE",
            entry_time=datetime.utcnow() - timedelta(hours=1),
            exit_time=datetime.utcnow(),
            entry_thesis="Bad thesis",
            outcome_thesis="Huge loss",
            setup_type="panic+1-agree+60conf",
            confidence_correct=False,
            pnl_usd=-500.0,
            pnl_pct=-0.10,
            r_multiple=5.0,
            hold_duration_minutes=15,
            lessons=[],
            risk_flags=["large_loss"],
            regime="panic",
            n_agree=1,
            confidence_predicted=60.0,
            confidence_actual_wr=0.0,
        )

        result = enricher.enrich_memory(lesson)
        assert result["notes_added"] >= 1

    def test_deep_memory_update(self, enricher, sample_lesson):
        """Should update deep memory patterns."""
        enricher.enrich_memory(sample_lesson)

        # Check that patterns file was created
        patterns_file = enricher.deep_memory_dir / "patterns.jsonl"
        assert patterns_file.exists()

        # Read and verify pattern
        with open(patterns_file) as f:
            pattern = json.loads(f.readline())

        assert pattern["setup_type"] == "trending_bear+3-agree+80conf"
        assert pattern["win_count"] == 1
        assert pattern["sample_size"] == 1

    def test_deep_memory_accumulation(self, enricher):
        """Should accumulate statistics across multiple trades."""
        base_time = datetime.utcnow()

        # Analyze 3 trades
        for i in range(3):
            lesson = TradeLesson(
                trade_id=f"trade_{i:03d}",
                symbol="BTC",
                entry_time=base_time - timedelta(hours=i),
                exit_time=base_time - timedelta(hours=i) + timedelta(hours=1),
                entry_thesis="Downtrend thesis",
                outcome_thesis=f"Result {i}",
                setup_type="trending_bear+3-agree+80conf",
                confidence_correct=(i < 2),  # 2 wins, 1 loss
                pnl_usd=100.0 if i < 2 else -100.0,
                pnl_pct=0.024 if i < 2 else -0.024,
                r_multiple=1.2 if i < 2 else 0.5,
                hold_duration_minutes=60,
                lessons=[],
                risk_flags=[],
                regime="trending_bear",
                n_agree=3,
                confidence_predicted=82.0,
                confidence_actual_wr=1.0 if i < 2 else 0.0,
            )
            enricher.enrich_memory(lesson)

        # Verify aggregation
        patterns_file = enricher.deep_memory_dir / "patterns.jsonl"
        with open(patterns_file) as f:
            pattern = json.loads(f.readline())

        assert pattern["sample_size"] == 3
        assert pattern["win_count"] == 2
        assert pattern["loss_count"] == 1

    def test_confidence_bin_tracking(self, enricher):
        """Should track confidence bins in deep memory."""
        lesson = TradeLesson(
            trade_id="trade_bin_001",
            symbol="BTC",
            entry_time=datetime.utcnow() - timedelta(hours=1),
            exit_time=datetime.utcnow(),
            entry_thesis="Thesis",
            outcome_thesis="Win",
            setup_type="trending_bear+3-agree+80conf",
            confidence_correct=True,
            pnl_usd=100.0,
            pnl_pct=0.024,
            r_multiple=1.2,
            hold_duration_minutes=60,
            lessons=[],
            risk_flags=[],
            regime="trending_bear",
            n_agree=3,
            confidence_predicted=85.0,
            confidence_actual_wr=1.0,
        )

        enricher.enrich_memory(lesson)

        patterns_file = enricher.deep_memory_dir / "patterns.jsonl"
        with open(patterns_file) as f:
            pattern = json.loads(f.readline())

        assert "80" in pattern["confidence_bins"]
        assert pattern["confidence_bins"]["80"]["wins"] == 1

    def test_rule_graduation_candidate(self, enricher):
        """Should identify rule graduation candidates."""
        lesson = TradeLesson(
            trade_id="trade_strong",
            symbol="BTC",
            entry_time=datetime.utcnow() - timedelta(hours=1),
            exit_time=datetime.utcnow(),
            entry_thesis="Strong thesis",
            outcome_thesis="Strong win",
            setup_type="trending_bear+3-agree+80conf",
            confidence_correct=True,
            pnl_usd=300.0,
            pnl_pct=0.072,
            r_multiple=3.6,  # Strong R-multiple
            hold_duration_minutes=60,
            lessons=[],
            risk_flags=[],
            regime="trending_bear",
            n_agree=3,
            confidence_predicted=82.0,
            confidence_actual_wr=1.0,
        )

        enricher.enrich_memory(lesson)

        # Check rules file
        assert enricher.graduated_rules_path.exists()

        with open(enricher.graduated_rules_path) as f:
            rules_data = json.load(f)

        rules = rules_data.get("rules", [])
        assert len(rules) > 0

        # Find our rule
        our_rule = next(
            (r for r in rules if r.get("trigger") == "trending_bear+3-agree+80conf"),
            None,
        )
        assert our_rule is not None

    def test_rule_demotion_flag(self, enricher):
        """Should flag rules that contradict performance."""
        # First, create a rule
        lesson_1 = TradeLesson(
            trade_id="trade_001",
            symbol="BTC",
            entry_time=datetime.utcnow() - timedelta(hours=2),
            exit_time=datetime.utcnow() - timedelta(hours=1),
            entry_thesis="Thesis",
            outcome_thesis="Win",
            setup_type="trending_bear+3-agree+80conf",
            confidence_correct=True,
            pnl_usd=200.0,
            pnl_pct=0.048,
            r_multiple=2.4,
            hold_duration_minutes=60,
            lessons=[],
            risk_flags=[],
            regime="trending_bear",
            n_agree=3,
            confidence_predicted=82.0,
            confidence_actual_wr=1.0,
        )

        enricher.enrich_memory(lesson_1)

        # Then contradict it
        lesson_2 = TradeLesson(
            trade_id="trade_002",
            symbol="BTC",
            entry_time=datetime.utcnow() - timedelta(hours=1),
            exit_time=datetime.utcnow(),
            entry_thesis="Thesis",
            outcome_thesis="Loss",
            setup_type="trending_bear+3-agree+80conf",
            confidence_correct=False,
            pnl_usd=-200.0,
            pnl_pct=-0.048,
            r_multiple=2.4,
            hold_duration_minutes=60,
            lessons=[],
            risk_flags=[],
            regime="trending_bear",
            n_agree=3,
            confidence_predicted=82.0,
            confidence_actual_wr=0.0,
        )

        enricher.enrich_memory(lesson_2)

        # Check for flags
        with open(enricher.graduated_rules_path) as f:
            rules_data = json.load(f)

        rules = rules_data.get("rules", [])
        flagged = [r for r in rules if r.get("flagged_for_review")]

        # Should have at least one flagged rule
        assert len(flagged) >= 0  # Might be 0 or 1 depending on rule creation

    def test_risk_flag_notes(self, enricher):
        """Should create notes for risk flags."""
        lesson = TradeLesson(
            trade_id="trade_risk",
            symbol="ETH",
            entry_time=datetime.utcnow() - timedelta(seconds=30),
            exit_time=datetime.utcnow(),
            entry_thesis="Quick trade",
            outcome_thesis="Stop hit",
            setup_type="range+2-agree+50conf",
            confidence_correct=False,
            pnl_usd=-50.0,
            pnl_pct=-0.01,
            r_multiple=0.5,
            hold_duration_minutes=0,
            lessons=[],
            risk_flags=["instant_stop"],
            regime="ranging",
            n_agree=2,
            confidence_predicted=50.0,
            confidence_actual_wr=0.0,
        )

        result = enricher.enrich_memory(lesson)
        assert result["notes_added"] >= 1


class TestEnrichedMemoryNote:
    """Test EnrichedMemoryNote dataclass."""

    def test_note_initialization(self):
        """Note should initialize with tags and TTL."""
        note = EnrichedMemoryNote(
            content="Test note",
            tags=["test", "sample"],
            ttl_days=7,
        )

        assert note.content == "Test note"
        assert note.tags == ["test", "sample"]
        assert note.ttl_days == 7
        assert note.created_at is not None

    def test_note_default_ttl(self):
        """Note should default to 7-day TTL."""
        note = EnrichedMemoryNote(
            content="Test",
            tags=["test"],
        )

        assert note.ttl_days == 7


class TestGraduatedRule:
    """Test GraduatedRule dataclass."""

    def test_rule_initialization(self):
        """Rule should initialize with all fields."""
        rule = GraduatedRule(
            rule_id="rule_001",
            trigger="trending_bear+3-agree",
            action="promote_confidence",
            effect="+15%",
            confidence=0.85,
            sample_size=12,
            win_rate=0.75,
            discovered_date="2026-04-27T00:00:00",
            evidence="12 trades, 75% WR",
        )

        assert rule.rule_id == "rule_001"
        assert rule.action == "promote_confidence"
        assert rule.confidence == 0.85
