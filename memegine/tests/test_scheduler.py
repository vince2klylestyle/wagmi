from __future__ import annotations

import datetime as dt

import pytest

from memegine import scheduler, topics


@pytest.fixture
def isolated_queue(tmp_path, monkeypatch):
    queue_path = tmp_path / "queue.yaml"
    monkeypatch.setattr(topics, "_queue_path", lambda: queue_path)
    yield queue_path


@pytest.fixture
def isolated_jobs(tmp_path, monkeypatch):
    jobs_path = tmp_path / "jobs.yaml"
    monkeypatch.setattr(scheduler, "_jobs_path", lambda: jobs_path)
    yield jobs_path


@pytest.fixture
def isolated_outputs(tmp_path, monkeypatch):
    out = tmp_path / "outputs"
    out.mkdir()
    from memegine import pipeline as pipeline_mod
    from memegine.config import settings
    monkeypatch.setattr(settings, "outputs_dir", out, raising=False)
    yield out


def test_add_and_list_job(isolated_jobs):
    job = scheduler.add(name="morning", hour=8, minute=30, action="daily_batch", n_topics=2)
    assert job.id
    jobs = scheduler.list_jobs()
    assert len(jobs) == 1
    assert jobs[0]["name"] == "morning"


def test_add_rejects_bad_hour(isolated_jobs):
    with pytest.raises(ValueError):
        scheduler.add(name="bad", hour=25)


def test_add_rejects_bad_day_of_week(isolated_jobs):
    with pytest.raises(ValueError):
        scheduler.add(name="bad", hour=8, days_of_week=[7])


def test_remove_job(isolated_jobs):
    job = scheduler.add(name="x", hour=8)
    assert scheduler.remove(job.id)
    assert scheduler.list_jobs() == []


def test_set_enabled(isolated_jobs):
    job = scheduler.add(name="x", hour=8)
    assert scheduler.set_enabled(job.id, False)
    assert scheduler.list_jobs()[0]["enabled"] is False


def test_should_fire_exact_match(isolated_jobs):
    job = scheduler.add(name="x", hour=8, minute=30).id
    now = dt.datetime(2026, 4, 18, 8, 30)
    # Weekday of 2026-04-18 is Saturday=5
    raw = scheduler._load()[0]
    assert scheduler._should_fire(raw, now)


def test_should_not_fire_disabled(isolated_jobs):
    j = scheduler.add(name="x", hour=8, minute=30)
    scheduler.set_enabled(j.id, False)
    now = dt.datetime(2026, 4, 18, 8, 30)
    raw = scheduler._load()[0]
    assert not scheduler._should_fire(raw, now)


def test_should_not_fire_wrong_minute(isolated_jobs):
    scheduler.add(name="x", hour=8, minute=30)
    now = dt.datetime(2026, 4, 18, 8, 31)
    raw = scheduler._load()[0]
    assert not scheduler._should_fire(raw, now)


def test_daily_batch_with_empty_queue(isolated_jobs, isolated_queue):
    job = scheduler.add(name="morning", hour=8, n_topics=3)
    raw = scheduler._load()[0]
    result = scheduler.run_daily_batch(raw)
    assert result.note == "no topics queued"
    assert result.bundles == []


def test_daily_batch_picks_topics_and_marks_used(
    isolated_jobs, isolated_queue, isolated_outputs, monkeypatch
):
    # Stub pipeline.build so we don't actually write pipeline bundles.
    class FakeBundle:
        def __init__(self, i):
            self.id = f"bundle{i}"
            self.folder = f"/fake/{self.id}"

    calls = []
    def fake_build(intent, *, kind, format_slug=None, **kw):
        calls.append({"intent": intent, "kind": kind, "format_slug": format_slug})
        return FakeBundle(len(calls))

    from memegine import pipeline as pipeline_mod
    monkeypatch.setattr(pipeline_mod, "build", fake_build)
    monkeypatch.setattr(scheduler.pipeline_mod, "build", fake_build)

    topics.add("trader at 3am", priority=5)
    topics.add("cope chart about etf flows", priority=4)
    topics.add("lore drop, cryptic alley", priority=3)

    job = scheduler.add(name="morning", hour=8, n_topics=2)
    raw = scheduler._load()[0]
    result = scheduler.run_daily_batch(raw)
    assert len(result.bundles) == 2
    assert len(result.topics_used) == 2
    # Highest priority first:
    assert calls[0]["intent"] == "trader at 3am"

    # Topics were marked used:
    used = topics.list_queued(status="used")
    assert len(used) == 2
    # The 3rd topic is still queued:
    still_queued = topics.list_queued()
    assert len(still_queued) == 1


def test_fire_marks_last_fire_at(isolated_jobs, isolated_queue):
    job = scheduler.add(name="x", hour=8, n_topics=1)
    result = scheduler.fire(job.id)
    assert result.job_id == job.id
    # last_fire_at persisted:
    refreshed = scheduler._load()[0]
    assert refreshed["last_fire_at"] is not None


def test_fire_unknown_job_raises(isolated_jobs):
    with pytest.raises(KeyError):
        scheduler.fire("does-not-exist")
