"""
Smoke tests for llm/growth/hypothesis_tracker.py.

Covers:
- Hypothesis + EvidenceEntry dataclasses (init + serialization round-trip)
- Tracker propose / dedup / start_testing
- add_evidence updates confidence + counts
- add_evidence_by_trade matches symbol/regime/side hypotheses
- Graduation rules (standard and fast-track)
- get_active / get_graduated / get_stats
- format_telegram + format_for_llm_prompt
- Persistence round-trip via temp data dir
"""

import json
import os
import time

import pytest

from llm.growth.hypothesis_tracker import (
    Hypothesis,
    EvidenceEntry,
    HypothesisTracker,
    HypothesisStage,
)


@pytest.fixture
def tracker(tmp_path):
    t = HypothesisTracker(data_dir=str(tmp_path))
    return t


# ── Dataclasses ──────────────────────────────────────────────


class TestEvidenceEntry:
    def test_round_trip(self):
        e = EvidenceEntry(
            timestamp=1_700_000_000.0,
            supporting=True,
            description="test evidence",
            source="trade_outcome",
            strength=1.5,
        )
        d = e.to_dict()
        e2 = EvidenceEntry.from_dict(d)
        assert e2.supporting == e.supporting
        assert e2.description == e.description
        assert e2.strength == e.strength

    def test_from_dict_ignores_unknown(self):
        e = EvidenceEntry.from_dict({
            "timestamp": 1.0,
            "supporting": False,
            "description": "x",
            "extra_field": "ignored",
        })
        assert e.supporting is False
        assert e.description == "x"


class TestHypothesisDataclass:
    def test_init_and_properties(self):
        h = Hypothesis(
            hypothesis_id="h1",
            statement="test statement",
            test_criteria="criteria",
            category="timing",
        )
        assert h.stage == "proposed"
        assert h.supporting_count == 0
        assert h.contradicting_count == 0
        assert h.total_evidence == 0
        assert h.evidence_ratio == 0.5
        assert h.is_ready_for_graduation is False

    def test_evidence_counts(self):
        h = Hypothesis(
            hypothesis_id="h2",
            statement="x",
            test_criteria="y",
            category="z",
            evidence=[
                {"supporting": True},
                {"supporting": True},
                {"supporting": False},
            ],
        )
        assert h.supporting_count == 2
        assert h.contradicting_count == 1
        assert h.total_evidence == 3
        assert abs(h.evidence_ratio - 2 / 3) < 1e-9

    def test_graduation_ready_standard(self):
        h = Hypothesis(
            hypothesis_id="h3",
            statement="x",
            test_criteria="y",
            category="z",
            stage="testing",
            evidence=[{"supporting": True}] * 8 + [{"supporting": False}] * 2,
        )
        # 10 evidence, 80% support -> ready
        assert h.is_ready_for_graduation is True

    def test_graduation_ready_fast_track(self):
        h = Hypothesis(
            hypothesis_id="h4",
            statement="x",
            test_criteria="y",
            category="z",
            stage="testing",
            evidence=[{"supporting": True}] * 7,
        )
        # 7 evidence, 100% support -> fast-track
        assert h.is_ready_for_graduation is True

    def test_graduation_requires_testing_stage(self):
        h = Hypothesis(
            hypothesis_id="h5",
            statement="x",
            test_criteria="y",
            category="z",
            stage="proposed",
            evidence=[{"supporting": True}] * 10,
        )
        assert h.is_ready_for_graduation is False

    def test_round_trip(self):
        h = Hypothesis(
            hypothesis_id="h6",
            statement="test",
            test_criteria="crit",
            category="cat",
            stage="testing",
            confidence=0.75,
            tags=["t1", "t2"],
        )
        d = h.to_dict()
        h2 = Hypothesis.from_dict(d)
        assert h2.hypothesis_id == "h6"
        assert h2.stage == "testing"
        assert h2.tags == ["t1", "t2"]


# ── Tracker lifecycle ────────────────────────────────────────


class TestPropose:
    def test_propose_basic(self, tracker):
        h = tracker.propose(
            statement="SOL performs better in Asian hours",
            test_criteria="Compare WR Asia vs other",
            category="timing",
        )
        assert h.hypothesis_id.startswith("hypo_")
        assert h.stage == "proposed"
        assert h.statement == "SOL performs better in Asian hours"

    def test_propose_dedup(self, tracker):
        h1 = tracker.propose("same stmt", "crit1", "cat1")
        h2 = tracker.propose("SAME STMT", "crit2", "cat2")
        # Deduplication is case-insensitive
        assert h1.hypothesis_id == h2.hypothesis_id

    def test_propose_with_tags(self, tracker):
        h = tracker.propose(
            statement="BTC trends well",
            test_criteria="x",
            tags=["BTC", "trend"],
        )
        assert "BTC" in h.tags


class TestStartTesting:
    def test_start_testing_moves_stage(self, tracker):
        h = tracker.propose("stmt", "crit", "cat")
        assert tracker.start_testing(h.hypothesis_id) is True
        # Reload
        hs = tracker.get_active()
        assert any(x.hypothesis_id == h.hypothesis_id and x.stage == "testing"
                   for x in hs)

    def test_start_testing_missing(self, tracker):
        assert tracker.start_testing("does_not_exist") is False


class TestAddEvidence:
    def test_add_supporting(self, tracker):
        h = tracker.propose("stmt", "crit", "cat")
        assert tracker.add_evidence(h.hypothesis_id, True, "won trade") is True
        active = tracker.get_active()
        hx = [x for x in active if x.hypothesis_id == h.hypothesis_id][0]
        assert hx.supporting_count == 1
        assert hx.stage == "testing"  # auto-started

    def test_add_contradicting(self, tracker):
        h = tracker.propose("stmt", "crit", "cat")
        tracker.add_evidence(h.hypothesis_id, False, "lost trade")
        active = tracker.get_active()
        hx = [x for x in active if x.hypothesis_id == h.hypothesis_id][0]
        assert hx.contradicting_count == 1

    def test_add_evidence_missing(self, tracker):
        assert tracker.add_evidence("missing", True, "x") is False

    def test_confidence_moves_with_evidence(self, tracker):
        h = tracker.propose("stmt", "crit", "cat")
        for _ in range(10):
            tracker.add_evidence(h.hypothesis_id, True, "win")
        active = tracker.get_active()
        hx = [x for x in active if x.hypothesis_id == h.hypothesis_id][0]
        assert hx.confidence > 0.6


class TestAddEvidenceByTrade:
    def test_symbol_match(self, tracker):
        h = tracker.propose(
            statement="SOL performs better in bullish markets",
            test_criteria="WR",
            category="symbol",
        )
        tracker.start_testing(h.hypothesis_id)
        tracker.add_evidence_by_trade({
            "symbol": "SOL",
            "regime": "trend",
            "side": "LONG",
            "outcome": "WIN",
            "hour": 5,
            "confidence": 75,
            "num_agree": 3,
        })
        # Should add supporting evidence since SOL + WIN + "performs better"
        active = tracker.get_active()
        hx = [x for x in active if x.hypothesis_id == h.hypothesis_id][0]
        assert hx.total_evidence >= 1

    def test_no_match_no_evidence(self, tracker):
        h = tracker.propose(
            statement="SOL performs better in bullish",
            test_criteria="x",
            category="symbol",
        )
        tracker.start_testing(h.hypothesis_id)
        tracker.add_evidence_by_trade({
            "symbol": "BTC",  # different symbol
            "regime": "range",
            "side": "LONG",
            "outcome": "WIN",
            "hour": 5,
        })
        active = tracker.get_active()
        hx = [x for x in active if x.hypothesis_id == h.hypothesis_id][0]
        assert hx.total_evidence == 0


# ── Graduation ───────────────────────────────────────────────


class TestGraduation:
    def test_fast_track_validation(self, tracker):
        h = tracker.propose("SOL strong in range", "x", "symbol")
        tracker.start_testing(h.hypothesis_id)
        # 7 supporting -> fast-track validate
        for _ in range(7):
            tracker.add_evidence(h.hypothesis_id, True, "w")
        graduated = tracker.check_graduation()
        assert any(x.hypothesis_id == h.hypothesis_id for x in graduated)

    def test_invalidation(self, tracker):
        h = tracker.propose("ETH weak in trend", "x", "symbol")
        tracker.start_testing(h.hypothesis_id)
        for _ in range(10):
            tracker.add_evidence(h.hypothesis_id, False, "contradicts")
        graduated = tracker.check_graduation()
        gs = [g for g in graduated if g.hypothesis_id == h.hypothesis_id]
        assert gs
        assert gs[0].stage == "invalidated"

    def test_not_ready_when_balanced(self, tracker):
        h = tracker.propose("stmt", "x", "cat")
        tracker.start_testing(h.hypothesis_id)
        for _ in range(5):
            tracker.add_evidence(h.hypothesis_id, True, "w")
            tracker.add_evidence(h.hypothesis_id, False, "l")
        graduated = tracker.check_graduation()
        assert not any(x.hypothesis_id == h.hypothesis_id for x in graduated)


# ── Accessors ────────────────────────────────────────────────


class TestAccessors:
    def test_get_active_empty(self, tracker):
        assert tracker.get_active() == []

    def test_get_graduated_empty(self, tracker):
        assert tracker.get_graduated() == []

    def test_get_stats_empty(self, tracker):
        stats = tracker.get_stats()
        assert stats["total"] == 0
        assert stats["avg_evidence_count"] == 0

    def test_get_stats_after_work(self, tracker):
        tracker.propose("s1", "c1", "cat1")
        tracker.propose("s2", "c2", "cat2")
        h3 = tracker.propose("s3", "c3", "cat1")
        tracker.add_evidence(h3.hypothesis_id, True, "w")
        stats = tracker.get_stats()
        assert stats["total"] == 3
        assert stats["by_category"]["cat1"] == 2
        assert stats["by_category"]["cat2"] == 1


# ── Formatting ───────────────────────────────────────────────


class TestFormat:
    def test_format_telegram_empty(self, tracker):
        s = tracker.format_telegram()
        assert "Hypothesis Dashboard" in s

    def test_format_telegram_with_content(self, tracker):
        h = tracker.propose("SOL strong in trend", "x", "symbol")
        tracker.add_evidence(h.hypothesis_id, True, "w1")
        tracker.add_evidence(h.hypothesis_id, True, "w2")
        s = tracker.format_telegram()
        assert "SOL strong" in s

    def test_format_for_llm_prompt_empty(self, tracker):
        assert tracker.format_for_llm_prompt() == ""

    def test_format_for_llm_prompt_with_content(self, tracker):
        h = tracker.propose("regime change matters", "x", "regime")
        tracker.add_evidence(h.hypothesis_id, True, "w")
        s = tracker.format_for_llm_prompt()
        assert "ACTIVE HYPOTHESES" in s
        assert "regime change matters" in s


# ── Persistence ──────────────────────────────────────────────


class TestPersistence:
    def test_save_reload(self, tmp_path):
        t1 = HypothesisTracker(data_dir=str(tmp_path))
        h = t1.propose("persist me", "crit", "cat")
        t1.add_evidence(h.hypothesis_id, True, "w")

        t2 = HypothesisTracker(data_dir=str(tmp_path))
        t2._ensure_loaded()
        active = t2.get_active()
        assert any(x.statement == "persist me" for x in active)

    def test_saved_file_valid_json(self, tmp_path):
        t = HypothesisTracker(data_dir=str(tmp_path))
        t.propose("stmt", "crit", "cat")
        path = os.path.join(str(tmp_path), "hypotheses.json")
        assert os.path.exists(path)
        with open(path) as f:
            data = json.load(f)
        assert "hypotheses" in data
        assert len(data["hypotheses"]) == 1


def test_stage_enum_values():
    assert HypothesisStage.PROPOSED.value == "proposed"
    assert HypothesisStage.VALIDATED.value == "validated"
    assert HypothesisStage.INVALIDATED.value == "invalidated"
    assert HypothesisStage.CODIFIED.value == "codified"
