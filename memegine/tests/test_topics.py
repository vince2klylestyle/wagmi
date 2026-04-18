from __future__ import annotations

from pathlib import Path

import pytest

from memegine import topics


@pytest.fixture
def tmp_queue(tmp_path, monkeypatch):
    path = tmp_path / "queue.yaml"
    monkeypatch.setattr(topics, "_queue_path", lambda: path)
    return path


def test_add_appends_to_queue(tmp_queue):
    t = topics.add("trader dumping at 3am", tags=["reaction"], priority=4)
    assert t.id
    assert t.text == "trader dumping at 3am"
    assert t.tags == ["reaction"]
    assert t.priority == 4
    assert t.status == "queued"

    queued = topics.list_queued()
    assert len(queued) == 1
    assert queued[0]["id"] == t.id


def test_priority_ordering(tmp_queue):
    a = topics.add("low prio", priority=1)
    b = topics.add("urgent", priority=5)
    c = topics.add("mid", priority=3)

    queued = topics.list_queued()
    assert [q["id"] for q in queued] == [b.id, c.id, a.id]


def test_pop_marks_used_and_preserves_order(tmp_queue):
    topics.add("a", priority=1)
    b = topics.add("b", priority=5)
    c = topics.add("c", priority=3)

    picked = topics.pop(n=2)
    assert [p["id"] for p in picked] == [b.id, c.id]

    still_queued = topics.list_queued()
    assert len(still_queued) == 1
    assert still_queued[0]["status"] == "queued"

    used = topics.list_queued(status="used")
    assert len(used) == 2


def test_pop_dry_run_does_not_mutate(tmp_queue):
    topics.add("a", priority=3)
    picked = topics.pop(n=1, mark_used=False)
    assert len(picked) == 1
    assert len(topics.list_queued()) == 1  # still queued


def test_mark_used_with_bundle_id(tmp_queue):
    t = topics.add("x")
    assert topics.mark_used(t.id, bundle_id="bundle123")
    used = topics.list_queued(status="used")
    assert used[0]["used_bundle_id"] == "bundle123"


def test_remove_returns_false_on_missing(tmp_queue):
    topics.add("a")
    assert topics.remove("nope") is False


def test_priority_clamped_to_1_5(tmp_queue):
    t1 = topics.add("a", priority=100)
    t2 = topics.add("b", priority=-5)
    assert t1.priority == 5
    assert t2.priority == 1


def test_stats_counts_by_status(tmp_queue):
    topics.add("a")
    topics.add("b")
    topics.pop(n=1)
    st = topics.stats()
    assert st["total"] == 2
    assert st["queued"] == 1
    assert st["used"] == 1


def test_empty_queue_returns_empty(tmp_queue):
    assert topics.list_queued() == []
    assert topics.pop(n=5) == []
    assert topics.stats()["total"] == 0


def test_skip_marks_skipped(tmp_queue):
    t = topics.add("a")
    assert topics.skip(t.id)
    assert not topics.list_queued()
    assert len(topics.list_queued(status="skipped")) == 1
