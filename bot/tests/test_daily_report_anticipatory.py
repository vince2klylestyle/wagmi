"""
Tests for the Anticipatory Entry Hit Rate metric (daily_report metric #7).

Verifies that daily_report consumes the previously-unread
data/manual/anticipatory_history.jsonl stream and surfaces hit rate,
per-setup breakdown, and alerts.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

# Ensure bot/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from feedback.daily_report import DailyReporter, ANTICIPATORY_HIT_RATE_ALERT  # noqa: E402


class MockLedger:
    def get_trades(self, lookback_days=30):
        return []

    def get_agreement_breakdown(self, lookback_days=7):
        return {}

    def get_regime_breakdown(self, lookback_days=7):
        return {}


def _write_history(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


class TestAnticipatoryMetric:
    def test_no_file_returns_empty_metric(self, tmp_path):
        reporter = DailyReporter(
            trade_ledger=MockLedger(),
            anticipatory_history_path=str(tmp_path / "missing.jsonl"),
        )
        report = reporter.generate_report()
        ant = report["metrics"]["anticipatory"]
        assert ant["total"] == 0
        assert ant["hit_rate"] == 0.0
        assert ant["status"].startswith("no anticipatory_history")

    def test_basic_hit_rate(self, tmp_path):
        hist = tmp_path / "anticipatory_history.jsonl"
        now = datetime.now(timezone.utc)
        records = [
            {"outcome": "triggered", "setup_type": "bb_upper_rejection",
             "resolved_at": now.isoformat(), "symbol": "SOL"},
            {"outcome": "triggered", "setup_type": "bb_upper_rejection",
             "resolved_at": now.isoformat(), "symbol": "SOL"},
            {"outcome": "expired", "setup_type": "bb_upper_rejection",
             "resolved_at": now.isoformat(), "symbol": "SOL"},
            {"outcome": "invalidated", "setup_type": "session_high_rejection",
             "resolved_at": now.isoformat(), "symbol": "BTC"},
        ]
        _write_history(hist, records)

        reporter = DailyReporter(
            trade_ledger=MockLedger(),
            anticipatory_history_path=str(hist),
        )
        report = reporter.generate_report()
        ant = report["metrics"]["anticipatory"]
        assert ant["total"] == 4
        assert ant["triggered"] == 2
        assert ant["expired"] == 1
        assert ant["invalidated"] == 1
        assert ant["hit_rate"] == 0.5
        # Per-setup breakdown
        assert ant["by_setup"]["bb_upper_rejection"]["total"] == 3
        assert ant["by_setup"]["bb_upper_rejection"]["triggered"] == 2
        assert abs(ant["by_setup"]["bb_upper_rejection"]["hit_rate"] - 0.667) < 0.01

    def test_excludes_old_records(self, tmp_path):
        hist = tmp_path / "anticipatory_history.jsonl"
        old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        new = datetime.now(timezone.utc).isoformat()
        records = [
            # Older than 7 days — excluded
            {"outcome": "triggered", "setup_type": "X", "resolved_at": old},
            {"outcome": "triggered", "setup_type": "X", "resolved_at": old},
            # Within window
            {"outcome": "expired", "setup_type": "X", "resolved_at": new},
        ]
        _write_history(hist, records)

        reporter = DailyReporter(
            trade_ledger=MockLedger(),
            anticipatory_history_path=str(hist),
        )
        ant = reporter.generate_report()["metrics"]["anticipatory"]
        assert ant["total"] == 1
        assert ant["expired"] == 1
        assert ant["triggered"] == 0

    def test_alert_fires_when_hit_rate_low(self, tmp_path):
        hist = tmp_path / "anticipatory_history.jsonl"
        now = datetime.now(timezone.utc).isoformat()
        # 20 records — 2 triggered (10% hit rate, well below 30% threshold)
        records = [
            {"outcome": "triggered" if i < 2 else "expired",
             "setup_type": "bb_upper_rejection",
             "resolved_at": now}
            for i in range(20)
        ]
        _write_history(hist, records)

        reporter = DailyReporter(
            trade_ledger=MockLedger(),
            anticipatory_history_path=str(hist),
        )
        report = reporter.generate_report()
        alerts = [a for a in report["alerts"] if "ANTICIPATORY" in a]
        assert len(alerts) == 1
        assert "10" in alerts[0]  # "10.0%" in alert message

    def test_no_alert_when_sample_too_small(self, tmp_path):
        """Below 10 entries we don't trust the hit rate enough to alert."""
        hist = tmp_path / "anticipatory_history.jsonl"
        now = datetime.now(timezone.utc).isoformat()
        records = [
            {"outcome": "expired", "setup_type": "X", "resolved_at": now}
            for _ in range(5)
        ]
        _write_history(hist, records)

        reporter = DailyReporter(
            trade_ledger=MockLedger(),
            anticipatory_history_path=str(hist),
        )
        report = reporter.generate_report()
        alerts = [a for a in report["alerts"] if "ANTICIPATORY" in a]
        assert len(alerts) == 0

    def test_malformed_lines_skipped(self, tmp_path):
        hist = tmp_path / "anticipatory_history.jsonl"
        now = datetime.now(timezone.utc).isoformat()
        with open(hist, "w") as f:
            f.write("not json\n")
            f.write(json.dumps({
                "outcome": "triggered",
                "setup_type": "X",
                "resolved_at": now,
            }) + "\n")
            f.write("also not json\n")

        reporter = DailyReporter(
            trade_ledger=MockLedger(),
            anticipatory_history_path=str(hist),
        )
        ant = reporter.generate_report()["metrics"]["anticipatory"]
        assert ant["total"] == 1
        assert ant["triggered"] == 1
        assert ant["parse_errors"] == 2

    def test_format_report_includes_section(self, tmp_path):
        hist = tmp_path / "anticipatory_history.jsonl"
        now = datetime.now(timezone.utc).isoformat()
        records = [
            {"outcome": "triggered", "setup_type": "bb_upper_rejection",
             "resolved_at": now}
        ]
        _write_history(hist, records)

        reporter = DailyReporter(
            trade_ledger=MockLedger(),
            anticipatory_history_path=str(hist),
        )
        report = reporter.generate_report()
        text = reporter.format_report(report)
        assert "ANTICIPATORY ENTRY HIT RATE" in text
        assert "bb_upper_rejection" in text
