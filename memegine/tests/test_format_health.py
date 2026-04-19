from __future__ import annotations

import pytest

from memegine import format_health, performance


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(performance, "_store_path", lambda: tmp_path / "perf.jsonl")
    yield tmp_path


def test_empty_store(isolated):
    report = format_health.evaluate()
    assert report.total_formats_with_data == 0
    assert report.verdicts == []


def test_under_threshold_formats_marked_healthy(isolated):
    # Only 1 post → under min_posts_for_verdict=5
    performance.log(format_slug="new_format", likes=0)
    report = format_health.evaluate()
    verdict = next(v for v in report.verdicts if v.slug == "new_format")
    assert verdict.verdict == "healthy"


def test_top_performer_is_healthy(isolated):
    # Two formats, both >= 5 posts. One clearly outperforms.
    for _ in range(6):
        performance.log(format_slug="great", likes=500)
    for _ in range(6):
        performance.log(format_slug="mediocre", likes=10)
    report = format_health.evaluate()
    slug_to_verdict = {v.slug: v.verdict for v in report.verdicts}
    assert slug_to_verdict["great"] == "healthy"
    # Mediocre is heavily under average — deprecation candidate.
    assert slug_to_verdict["mediocre"] in ("watch", "candidate_for_deprecation")


def test_verdicts_sorted_worst_first(isolated):
    for _ in range(6):
        performance.log(format_slug="good", likes=500)
    for _ in range(6):
        performance.log(format_slug="dead", likes=5)
    report = format_health.evaluate()
    # The deprecate/watch candidate appears before "healthy".
    verdicts = [v.verdict for v in report.verdicts]
    if "candidate_for_deprecation" in verdicts or "watch" in verdicts:
        first_non_healthy = next(
            i for i, v in enumerate(verdicts) if v != "healthy"
        )
        first_healthy = next((i for i, v in enumerate(verdicts) if v == "healthy"), len(verdicts))
        assert first_non_healthy < first_healthy


def test_as_text_includes_header(isolated):
    performance.log(format_slug="f", likes=10)
    report = format_health.evaluate()
    text = report.as_text()
    assert "format health" in text
    assert "median" in text.lower()
