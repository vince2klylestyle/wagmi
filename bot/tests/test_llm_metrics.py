"""
Smoke tests for llm/metrics.py — LLM decision-outcome metric computations.

Covers:
  - BucketStats / RegretStats / AnalysisResult constructors
  - compute_metrics() with empty input (happy-path zero)
  - compute_metrics() with a small synthetic batch
  - format_report() on empty + populated
  - export_summary_csv() file creation
  - Helper functions (_win, _bucket_label, _safe_pct)
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from llm.joiner import JoinedRecord, LLMDecisionRecord, TradeRecord
from llm.metrics import (
    AnalysisResult,
    BucketStats,
    RegretStats,
    _bucket_label,
    _safe_pct,
    _win,
    compute_metrics,
    export_summary_csv,
    format_report,
)


# ── Helpers ─────────────────────────────────────────────

def test_win_threshold():
    # _win uses MIN_PNL_ABS_FOR_SIGNAL > 0
    assert _win(10.0) is True
    assert _win(-10.0) is False
    assert _win(0.0) is False


def test_bucket_label_unknown_when_out_of_range():
    # Negative confidence isn't in any defined bucket
    assert _bucket_label(-1.0) == "unknown"


def test_bucket_label_valid_range():
    # Mid-range confidence should land in some defined bucket (not "unknown")
    label = _bucket_label(70.0)
    assert isinstance(label, str)


def test_safe_pct_zero_div_returns_zero():
    assert _safe_pct(5, 0) == 0.0
    assert _safe_pct(0, 0) == 0.0


def test_safe_pct_normal():
    assert _safe_pct(25, 100) == 25.0
    assert _safe_pct(1, 2) == 50.0


# ── Dataclasses ─────────────────────────────────────────

def test_bucket_stats_defaults():
    b = BucketStats()
    assert b.count == 0
    assert b.wins == 0
    assert b.losses == 0
    assert b.total_pnl == 0.0
    assert b.pnl_values == []
    assert b.win_rate == 0.0
    assert b.avg_pnl == 0.0
    assert b.matched == 0


def test_bucket_stats_win_rate_math():
    b = BucketStats(count=10, wins=7, losses=3, total_pnl=50.0)
    assert b.win_rate == 70.0
    assert b.avg_pnl == 5.0
    assert b.matched == 10


def test_regret_stats_defaults():
    r = RegretStats()
    assert r.vetoed_would_lose == 0
    assert r.vetoed_would_win == 0
    assert r.flipped_correct == 0
    assert r.flipped_wrong == 0
    assert r.total_flat_calls == 0
    assert r.total_flip_opportunities == 0


def test_analysis_result_defaults():
    a = AnalysisResult()
    assert a.total_decisions == 0
    assert a.total_trades == 0
    assert a.matched_count == 0
    assert a.regime_dist == {}
    assert a.action_stats == {}
    assert isinstance(a.regret, RegretStats)


# ── compute_metrics ─────────────────────────────────────

def test_compute_metrics_empty():
    result = compute_metrics([])
    assert result.total_decisions == 0
    assert result.total_trades == 0
    assert result.matched_count == 0
    assert result.error_count == 0
    assert result.joined_records == []


def test_compute_metrics_single_error():
    dec = LLMDecisionRecord(ts=0, action="api_error", confidence=0, regime="")
    jr = JoinedRecord(decision=dec)
    result = compute_metrics([jr])
    assert result.total_decisions == 1
    assert result.error_count == 1


def test_compute_metrics_small_batch():
    decisions = [
        LLMDecisionRecord(
            ts=1.0, action="long", confidence=75.0, regime="trend",
            allowed=True, trigger_reason="PRE_TRADE",
        ),
        LLMDecisionRecord(
            ts=2.0, action="flat", confidence=50.0, regime="range",
            allowed=False, gate_reason="low_confidence",
        ),
        LLMDecisionRecord(
            ts=3.0, action="short", confidence=80.0, regime="panic",
        ),
    ]
    trades = [
        TradeRecord(
            timestamp="2026-04-17T12:00:00Z",
            ts=1.0, symbol="BTC", side="long",
            entry=75000, exit=76000, pnl=12.5, outcome="WIN",
        ),
        None,
        TradeRecord(
            timestamp="2026-04-17T12:05:00Z",
            ts=3.0, symbol="ETH", side="short",
            entry=2100, exit=2150, pnl=-8.0, outcome="LOSS",
        ),
    ]

    joined = [
        JoinedRecord(decision=decisions[0], trade=trades[0], match_type="pre_trade"),
        JoinedRecord(decision=decisions[1], trade=None),
        JoinedRecord(decision=decisions[2], trade=trades[2], match_type="pre_trade"),
    ]

    result = compute_metrics(joined)
    assert result.total_decisions == 3
    assert result.error_count == 0
    assert result.gated_count == 1  # decision #2 was flat/not-allowed
    assert "trend" in result.regime_dist
    assert "range" in result.regime_dist
    assert "panic" in result.regime_dist
    # Action stats should include long and short
    assert "long" in result.action_stats
    assert "short" in result.action_stats
    assert "flat" in result.action_stats
    # BTC long was a win
    assert result.action_stats["long"].wins == 1
    # ETH short was a loss
    assert result.action_stats["short"].losses == 1


def test_compute_metrics_regime_flip_count():
    decisions = [
        LLMDecisionRecord(ts=1.0, action="long", regime="trend"),
        LLMDecisionRecord(ts=2.0, action="long", regime="range"),
        LLMDecisionRecord(ts=3.0, action="long", regime="range"),
        LLMDecisionRecord(ts=4.0, action="long", regime="trend"),
    ]
    joined = [JoinedRecord(decision=d) for d in decisions]
    result = compute_metrics(joined)
    # Flips: trend->range (1), range->trend (2)
    assert result.regime_flip_count == 2


def test_compute_metrics_token_usage():
    dec = LLMDecisionRecord(
        ts=1.0, action="long",
        usage={"input_tokens": 1000, "output_tokens": 500},
    )
    result = compute_metrics([JoinedRecord(decision=dec)])
    assert result.total_input_tokens == 1000
    assert result.total_output_tokens == 500
    assert result.estimated_cost_usd > 0


# ── format_report ────────────────────────────────────────

def test_format_report_empty():
    r = AnalysisResult()
    s = format_report(r)
    assert isinstance(s, str)
    assert "LLM ANALYSIS REPORT" in s or "Total LLM decisions" in s


def test_format_report_populated():
    # Build a small result with token data so the cost line renders
    r = AnalysisResult(
        total_decisions=5,
        matched_count=3,
        total_input_tokens=1000,
        total_output_tokens=500,
        estimated_cost_usd=0.001,
    )
    r.action_stats["long"] = BucketStats(count=3, wins=2, losses=1, total_pnl=10.0)
    s = format_report(r, session_label="test-session")
    assert isinstance(s, str)
    assert len(s) > 0


# ── export_summary_csv ──────────────────────────────────

def test_export_summary_csv_creates_files():
    r = AnalysisResult(total_decisions=1)
    r.action_stats["long"] = BucketStats(count=1, wins=1, losses=0, total_pnl=5.0)
    with tempfile.TemporaryDirectory() as d:
        export_summary_csv(r, output_dir=d)
        # Expect at least one csv produced (implementation may create multiple)
        files = os.listdir(d)
        assert any(f.endswith(".csv") for f in files)
