from __future__ import annotations

import datetime as dt

import pytest

from memegine import calendar, topics


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(topics, "_queue_path", lambda: tmp_path / "queue.yaml")
    yield tmp_path


def test_schedule_attaches_publish_at(isolated):
    t = topics.add("x")
    assert calendar.schedule(t.id, "2026-04-21T08:00:00Z")
    all_topics = topics._load()
    assert all_topics[0]["publish_at"].startswith("2026-04-21T08:00:00")


def test_schedule_rejects_bad_timestamp(isolated):
    t = topics.add("x")
    with pytest.raises(ValueError):
        calendar.schedule(t.id, "not a timestamp")


def test_schedule_missing_topic_returns_false(isolated):
    assert not calendar.schedule("nope", "2026-04-21T08:00:00Z")


def test_unschedule_removes_publish_at(isolated):
    t = topics.add("x")
    calendar.schedule(t.id, "2026-04-21T08:00:00Z")
    assert calendar.unschedule(t.id)
    all_topics = topics._load()
    assert "publish_at" not in all_topics[0]


def test_list_scheduled_sorted_by_time(isolated):
    t1 = topics.add("late")
    t2 = topics.add("early")
    calendar.schedule(t1.id, "2026-04-25T08:00:00Z")
    calendar.schedule(t2.id, "2026-04-20T08:00:00Z")
    entries = calendar.list_scheduled()
    assert entries[0].topic_id == t2.id  # earlier first


def test_list_scheduled_future_only(isolated):
    past = topics.add("past")
    future = topics.add("future")
    calendar.schedule(past.id, "2020-01-01T00:00:00Z")
    calendar.schedule(future.id, "2099-01-01T00:00:00Z")
    entries = calendar.list_scheduled(future_only=True)
    assert len(entries) == 1
    assert entries[0].topic_id == future.id


def test_list_due_in_grace_window(isolated):
    now = dt.datetime.utcnow()
    # Ten minutes ago; within 30-min grace.
    past = topics.add("due-now")
    ten_min_ago = (now - dt.timedelta(minutes=10)).isoformat() + "Z"
    calendar.schedule(past.id, ten_min_ago)

    # Two days ago; outside grace.
    old = topics.add("way old")
    calendar.schedule(old.id, "2020-01-01T00:00:00Z")

    due = calendar.list_due(grace_minutes=30)
    ids = {e.topic_id for e in due}
    assert past.id in ids
    assert old.id not in ids


def test_summary_text_empty(isolated):
    assert "nothing scheduled" in calendar.summary_text()


def test_summary_text_lists(isolated):
    t = topics.add("launch piece")
    calendar.schedule(t.id, "2099-04-21T08:00:00Z")
    text = calendar.summary_text()
    assert "launch piece" in text
    assert t.id in text
