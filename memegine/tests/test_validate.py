from __future__ import annotations

import pytest

from memegine import validate


def test_run_on_real_data_is_clean():
    # The checked-in formats/fragments/playbooks should validate cleanly.
    report = validate.run()
    assert report.ok, report.as_text()


def test_report_ok_with_no_errors():
    r = validate.ValidationReport()
    r.add("WARN", "x", "warn-only")
    assert r.ok


def test_report_not_ok_with_any_error():
    r = validate.ValidationReport()
    r.add("ERROR", "x", "bad")
    assert not r.ok


def test_formats_parser_catches_missing_slug(tmp_path, monkeypatch):
    from memegine.config import settings
    monkeypatch.setattr(settings, "data_dir", tmp_path, raising=False)
    formats_dir = tmp_path / "formats"
    formats_dir.mkdir()
    (formats_dir / "library.yaml").write_text(
        "formats:\n  - kind: image\n    description: no slug here\n",
        encoding="utf-8",
    )
    report = validate.run()
    assert any("missing slug" in p.message for p in report.problems)


def test_formats_parser_catches_bad_kind(tmp_path, monkeypatch):
    from memegine.config import settings
    monkeypatch.setattr(settings, "data_dir", tmp_path, raising=False)
    formats_dir = tmp_path / "formats"
    formats_dir.mkdir()
    (formats_dir / "library.yaml").write_text(
        "formats:\n  - slug: x\n    kind: podcast\n    prompt_scaffold: y\n",
        encoding="utf-8",
    )
    report = validate.run()
    assert any("kind must be" in p.message for p in report.problems)


def test_formats_parser_catches_duplicate_slug(tmp_path, monkeypatch):
    from memegine.config import settings
    monkeypatch.setattr(settings, "data_dir", tmp_path, raising=False)
    formats_dir = tmp_path / "formats"
    formats_dir.mkdir()
    (formats_dir / "library.yaml").write_text(
        "formats:\n  - slug: a\n    kind: image\n    prompt_scaffold: y\n"
        "  - slug: a\n    kind: image\n    prompt_scaffold: y\n",
        encoding="utf-8",
    )
    report = validate.run()
    assert any("duplicate slug" in p.message for p in report.problems)


def test_trend_feeds_catches_bad_url(tmp_path, monkeypatch):
    from memegine.config import settings
    monkeypatch.setattr(settings, "data_dir", tmp_path, raising=False)
    formats_dir = tmp_path / "formats"
    formats_dir.mkdir()
    (formats_dir / "library.yaml").write_text("formats: []\n", encoding="utf-8")
    feeds_dir = tmp_path / "trends"
    feeds_dir.mkdir()
    (feeds_dir / "feeds.yaml").write_text(
        "feeds:\n  - name: bad\n    url: ftp://nope\n    kind: rss\n",
        encoding="utf-8",
    )
    report = validate.run()
    assert any("url must be http(s)" in p.message for p in report.problems)


def test_topics_queue_catches_bad_status(tmp_path, monkeypatch):
    from memegine.config import settings
    monkeypatch.setattr(settings, "data_dir", tmp_path, raising=False)
    (tmp_path / "formats").mkdir()
    (tmp_path / "formats" / "library.yaml").write_text("formats: []\n", encoding="utf-8")
    topics_dir = tmp_path / "topics"
    topics_dir.mkdir()
    (topics_dir / "queue.yaml").write_text(
        "topics:\n  - id: x\n    text: y\n    status: deleted\n    priority: 3\n",
        encoding="utf-8",
    )
    report = validate.run()
    assert any("unknown status" in p.message for p in report.problems)
