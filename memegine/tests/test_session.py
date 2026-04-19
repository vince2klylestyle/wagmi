from __future__ import annotations

import pytest

from memegine import session


@pytest.fixture
def isolated_events(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "_events_path", lambda: tmp_path / "events.jsonl")
    yield tmp_path


def test_start_creates_event(isolated_events):
    e = session.start(name="morning")
    assert e.kind == "start"
    assert e.name == "morning"
    assert session.current() is not None


def test_end_closes_session(isolated_events):
    session.start(name="x")
    end = session.end()
    assert end is not None
    assert end.kind == "end"
    assert session.current() is None


def test_end_noop_when_no_open_session(isolated_events):
    assert session.end() is None


def test_starting_new_session_auto_closes_old(isolated_events):
    session.start(name="first")
    session.start(name="second")
    current = session.current()
    assert current["name"] == "second"


def test_list_sessions_orders_newest_first(isolated_events):
    session.start(name="a"); session.end()
    session.start(name="b"); session.end()
    session.start(name="c")
    lst = session.list_sessions()
    assert len(lst) == 3
    # Newest first:
    assert lst[0]["name"] == "c"


def test_duration_computed_when_closed(isolated_events):
    import time
    session.start(name="x")
    time.sleep(0.01)
    session.end()
    lst = session.list_sessions()
    assert lst[0]["duration_sec"] is not None
    assert lst[0]["duration_sec"] >= 0


def test_duration_none_when_open(isolated_events):
    session.start(name="open")
    lst = session.list_sessions()
    assert lst[0]["duration_sec"] is None
