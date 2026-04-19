from __future__ import annotations

import pytest

from memegine import doctor


def test_run_returns_report():
    report = doctor.run()
    assert isinstance(report, doctor.DoctorReport)
    assert report.checks
    # Every check must have one of the three statuses.
    for c in report.checks:
        assert c.status in ("PASS", "WARN", "ERROR")


def test_report_ok_when_no_errors():
    report = doctor.DoctorReport(checks=[
        doctor.CheckResult("x", "PASS"),
        doctor.CheckResult("y", "WARN", "meh"),
    ])
    assert report.ok


def test_report_not_ok_on_error():
    report = doctor.DoctorReport(checks=[
        doctor.CheckResult("x", "PASS"),
        doctor.CheckResult("y", "ERROR", "bad"),
    ])
    assert not report.ok


def test_as_text_formats():
    report = doctor.DoctorReport(checks=[
        doctor.CheckResult("x", "PASS"),
        doctor.CheckResult("y", "WARN", "note"),
    ])
    text = report.as_text()
    assert "memegine doctor" in text
    assert "verdict: PASS" in text


def test_format_check_returns_pass_on_healthy_lib():
    result = doctor._check_formats()
    assert result.status == "PASS"


def test_codex_check_reports_char_count():
    result = doctor._check_codex()
    assert result.status in ("PASS", "WARN")


def test_anthropic_check_warns_when_key_unset(monkeypatch):
    from memegine.config import settings
    monkeypatch.setattr(settings, "anthropic_api_key", "", raising=False)
    result = doctor._check_anthropic()
    assert result.status == "WARN"


def test_telegram_check_warns_when_unset(monkeypatch):
    monkeypatch.delenv("MEMEGINE_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("MEMEGINE_TELEGRAM_ALLOWED_USER_IDS", raising=False)
    result = doctor._check_telegram()
    assert result.status == "WARN"


def test_telegram_check_errors_when_token_without_allowlist(monkeypatch):
    monkeypatch.setenv("MEMEGINE_TELEGRAM_BOT_TOKEN", "fake")
    monkeypatch.setenv("MEMEGINE_TELEGRAM_ALLOWED_USER_IDS", "")
    try:
        import telegram  # noqa: F401
    except ImportError:
        pytest.skip("python-telegram-bot not installed")
    result = doctor._check_telegram()
    assert result.status == "ERROR"


def test_discord_check_warns_when_unset(monkeypatch):
    monkeypatch.delenv("MEMEGINE_DISCORD_WEBHOOK_URL", raising=False)
    result = doctor._check_discord()
    assert result.status == "WARN"


def test_discord_check_errors_on_bad_url(monkeypatch):
    monkeypatch.setenv("MEMEGINE_DISCORD_WEBHOOK_URL", "https://evil.com/ingest")
    result = doctor._check_discord()
    assert result.status == "ERROR"
