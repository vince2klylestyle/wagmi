from __future__ import annotations

import datetime as dt
import json

import pytest

from memegine import journal


@pytest.fixture
def isolated_all(tmp_path, monkeypatch):
    from memegine import archive, export as export_mod, reference_lib, session
    from memegine.config import settings

    monkeypatch.setattr(settings, "logs_dir", tmp_path / "logs", raising=False)
    (tmp_path / "logs").mkdir()
    monkeypatch.setattr(settings, "references_dir", tmp_path / "refs", raising=False)
    (tmp_path / "refs").mkdir()
    monkeypatch.setattr(session, "_events_path", lambda: tmp_path / "events.jsonl")
    monkeypatch.setattr(export_mod, "_posts_dir", lambda: tmp_path / "posts")
    yield tmp_path


def _write_brief(tmp_path, when: str, intent: str) -> None:
    logs = tmp_path / "logs"
    day = when[:10]
    path = logs / f"briefs-{day}.jsonl"
    rec = {"id": "b1", "created_at": when, "kind": "prompt", "intent": intent, "system": "s", "user": "u"}
    with path.open("a") as f:
        f.write(json.dumps(rec) + "\n")


def test_collect_includes_briefs(isolated_all):
    today = dt.datetime.utcnow().date().isoformat()
    _write_brief(isolated_all, f"{today}T12:00:00Z", "first piece")
    entries = journal.collect()
    kinds = [e.kind for e in entries]
    assert "brief" in kinds


def test_collect_includes_sessions(isolated_all):
    from memegine import session
    session.start(name="test-session")
    entries = journal.collect()
    assert any(e.kind == "session_start" for e in entries)


def test_collect_reverse_chronological(isolated_all):
    today = dt.datetime.utcnow().date().isoformat()
    yday = (dt.datetime.utcnow().date() - dt.timedelta(days=1)).isoformat()
    _write_brief(isolated_all, f"{today}T12:00:00Z", "today")
    _write_brief(isolated_all, f"{yday}T12:00:00Z", "yesterday")
    entries = journal.collect()
    # First entry should be today's (later timestamp).
    ats = [e.at for e in entries]
    assert ats == sorted(ats, reverse=True)


def test_days_filter(isolated_all):
    today = dt.datetime.utcnow().date().isoformat()
    long_ago = (dt.datetime.utcnow().date() - dt.timedelta(days=30)).isoformat()
    _write_brief(isolated_all, f"{today}T12:00:00Z", "recent")
    _write_brief(isolated_all, f"{long_ago}T12:00:00Z", "old")
    entries = journal.collect(days=7)
    # Only one entry is within the last 7 days.
    brief_entries = [e for e in entries if e.kind == "brief"]
    assert len(brief_entries) == 1
    assert "recent" in brief_entries[0].summary


def test_limit_respected(isolated_all):
    today = dt.datetime.utcnow().date().isoformat()
    for i in range(20):
        _write_brief(isolated_all, f"{today}T{i:02d}:00:00Z", f"piece {i}")
    entries = journal.collect(limit=5)
    assert len(entries) == 5


def test_as_text_handles_empty():
    text = journal.as_text([])
    assert "no journal entries" in text
