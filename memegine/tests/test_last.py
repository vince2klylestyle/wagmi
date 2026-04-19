from __future__ import annotations

import datetime as dt
import json

import pytest

from memegine import last


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    from memegine import reference_lib, export as export_mod, session
    from memegine.config import settings
    monkeypatch.setattr(settings, "logs_dir", tmp_path / "logs", raising=False)
    (tmp_path / "logs").mkdir()
    monkeypatch.setattr(settings, "references_dir", tmp_path / "refs", raising=False)
    (tmp_path / "refs").mkdir()
    monkeypatch.setattr(export_mod, "_posts_dir", lambda: tmp_path / "posts")
    monkeypatch.setattr(session, "_events_path", lambda: tmp_path / "events.jsonl")
    yield tmp_path


def test_all_empty(isolated):
    snap = last.compute()
    assert snap.last_brief is None
    assert snap.last_winner is None
    assert snap.last_post is None
    assert snap.last_session is None


def test_last_brief(isolated):
    logs = isolated / "logs"
    today = dt.datetime.utcnow().date().isoformat()
    rec = {
        "id": "b1", "created_at": f"{today}T00:10:00Z",
        "kind": "prompt", "intent": "my intent", "system": "s", "user": "u",
    }
    (logs / f"briefs-{today}.jsonl").write_text(json.dumps(rec) + "\n")
    snap = last.compute()
    assert snap.last_brief is not None
    assert snap.last_brief["intent"] == "my intent"


def test_last_winner(isolated):
    from memegine import reference_lib
    img = isolated / "x.png"
    img.write_bytes(b"PNG")
    reference_lib.add(img, tags=["winner"], notes="first")
    img2 = isolated / "y.png"
    img2.write_bytes(b"PNG2")
    reference_lib.add(img2, tags=["winner"], notes="second")
    snap = last.compute()
    # Most recent winner.
    assert "second" in (snap.last_winner.get("notes") or "")


def test_last_session(isolated):
    from memegine import session
    session.start(name="morning")
    snap = last.compute()
    assert snap.last_session is not None
    assert snap.last_session["name"] == "morning"


def test_as_text_handles_all_empty():
    snap = last.LastSnapshot()
    text = snap.as_text()
    assert "last activity" in text
    assert "brief   (none)" in text
    assert "winner  (none)" in text
