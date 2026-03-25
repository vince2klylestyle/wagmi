"""
Tests for Manual Sniper Health Check module.
"""

import json
import os
import pytest
from manual.health_check import HealthStatus, run_health_check, _count_jsonl_lines, _file_age_minutes


class TestHealthStatus:
    """Test HealthStatus aggregation."""

    def test_overall_ok(self):
        h = HealthStatus()
        h.add_check("test1", "OK", "fine")
        h.add_check("test2", "OK", "good")
        assert h.overall == "OK"
        assert len(h.errors) == 0
        assert len(h.warnings) == 0

    def test_overall_warn(self):
        h = HealthStatus()
        h.add_check("test1", "OK", "fine")
        h.add_check("test2", "WARN", "something")
        assert h.overall == "WARN"
        assert len(h.warnings) == 1

    def test_overall_error(self):
        h = HealthStatus()
        h.add_check("test1", "OK", "fine")
        h.add_check("test2", "ERROR", "bad")
        assert h.overall == "ERROR"
        assert len(h.errors) == 1

    def test_overall_critical(self):
        h = HealthStatus()
        h.add_check("test1", "WARN", "meh")
        h.add_check("test2", "CRITICAL", "very bad")
        assert h.overall == "CRITICAL"

    def test_format_output(self):
        h = HealthStatus()
        h.add_check("test1", "OK", "fine")
        h.add_check("test2", "WARN", "something")
        output = h.format()
        assert "WARN" in output
        assert "test1" in output
        assert "test2" in output

    def test_format_telegram(self):
        h = HealthStatus()
        h.add_check("test1", "OK", "fine")
        h.add_check("test2", "WARN", "something off")
        output = h.format_telegram()
        assert "HEALTH: WARN" in output
        assert "test2" in output
        # OK checks are omitted in telegram format
        assert "test1" not in output

    def test_format_telegram_all_ok(self):
        h = HealthStatus()
        h.add_check("test1", "OK", "fine")
        output = h.format_telegram()
        assert "All checks passed" in output

    def test_to_dict(self):
        h = HealthStatus()
        h.add_check("test1", "OK", "fine")
        d = h.to_dict()
        assert "overall" in d
        assert "checks" in d
        assert "timestamp" in d
        assert d["overall"] == "OK"


class TestHelpers:
    """Test helper functions."""

    def test_count_jsonl_lines(self, tmp_path):
        p = tmp_path / "test.jsonl"
        p.write_text('{"a":1}\n{"b":2}\nbadline\n{"c":3}\n')
        assert _count_jsonl_lines(str(p)) == 3  # Skips bad line

    def test_count_jsonl_missing_file(self):
        assert _count_jsonl_lines("/nonexistent/file.jsonl") == 0

    def test_count_jsonl_empty_file(self, tmp_path):
        p = tmp_path / "empty.jsonl"
        p.write_text("")
        assert _count_jsonl_lines(str(p)) == 0

    def test_file_age_missing(self):
        assert _file_age_minutes("/nonexistent/file") is None

    def test_file_age_exists(self, tmp_path):
        p = tmp_path / "test.txt"
        p.write_text("hi")
        age = _file_age_minutes(str(p))
        assert age is not None
        assert age < 1.0  # Just created, should be < 1 minute


class TestRunHealthCheck:
    """Test the full health check runner."""

    def test_runs_without_crash(self):
        """Health check should never crash, even with missing data."""
        health = run_health_check(quick=True)
        assert health.overall in ("OK", "WARN", "ERROR", "CRITICAL")
        assert len(health.checks) > 0

    def test_quick_mode_skips_config(self):
        """Quick mode should skip config check."""
        health = run_health_check(quick=True)
        config_checks = [c for c in health.checks if c["name"] == "config"]
        assert len(config_checks) == 0

    def test_full_mode_includes_config(self):
        """Full mode should include config check."""
        health = run_health_check(quick=False)
        config_checks = [c for c in health.checks if c["name"] == "config"]
        assert len(config_checks) == 1
