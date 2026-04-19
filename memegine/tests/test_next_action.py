from __future__ import annotations

import pytest

from memegine import next_action


@pytest.fixture
def isolated_all(tmp_path, monkeypatch):
    from memegine import (
        performance, reference_lib, session, topics,
    )
    from memegine.config import settings

    monkeypatch.setattr(topics, "_queue_path", lambda: tmp_path / "queue.yaml")
    monkeypatch.setattr(session, "_events_path", lambda: tmp_path / "events.jsonl")
    monkeypatch.setattr(performance, "_store_path", lambda: tmp_path / "perf.jsonl")
    refs_dir = tmp_path / "refs"
    refs_dir.mkdir()
    monkeypatch.setattr(settings, "references_dir", refs_dir, raising=False)
    monkeypatch.setattr(settings, "codex_path", tmp_path / "style.md", raising=False)
    monkeypatch.setattr(settings, "data_dir", tmp_path, raising=False)
    yield tmp_path


def test_empty_environment_generates_suggestions(isolated_all):
    dash = next_action.compute()
    assert dash.queue_count == 0
    assert dash.last_winner is None
    # Recommendations are always present.
    assert dash.recommendations


def test_queue_count_reflected(isolated_all):
    from memegine import topics
    topics.add("first")
    topics.add("second", priority=5)
    dash = next_action.compute()
    assert dash.queue_count == 2
    # Highest-priority topic surfaces first.
    assert dash.top_topics[0]["text"] == "second"


def test_last_winner_populated(isolated_all):
    from memegine import reference_lib
    img = isolated_all / "x.png"
    img.write_bytes(b"PNG")
    reference_lib.add(img, prompt="trader, 35mm", winner=True)
    dash = next_action.compute()
    assert dash.last_winner is not None
    assert "trader" in (dash.last_winner.get("prompt") or "")


def test_top_format_from_perf(isolated_all):
    from memegine import performance
    performance.log(format_slug="meme_two_panel", likes=500)
    performance.log(format_slug="photoreal_portrait", likes=50)
    dash = next_action.compute()
    assert dash.top_format is not None
    assert dash.top_format[0] == "meme_two_panel"


def test_current_session_detected(isolated_all):
    from memegine import session
    session.start(name="test")
    dash = next_action.compute()
    assert dash.current_session is not None
    assert "test" in dash.current_session


def test_as_text_includes_sections(isolated_all):
    dash = next_action.compute()
    text = dash.as_text()
    assert "next moves" in text
    assert "topic queue" in text
    assert "suggested moves" in text


def test_recommendation_for_empty_queue(isolated_all):
    dash = next_action.compute()
    assert any("queue is empty" in r for r in dash.recommendations)


def test_recommendation_uses_top_topic_when_queue_full(isolated_all):
    from memegine import topics
    t = topics.add("an intent that stands alone, 3am, cope", priority=5)
    topics.add("second", priority=3)
    topics.add("third", priority=2)
    dash = next_action.compute()
    # Mentions from-topic with the top-priority topic id.
    assert any(f"from-topic {t.id}" in r for r in dash.recommendations)
