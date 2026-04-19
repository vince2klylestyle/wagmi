from __future__ import annotations

import json

import pytest

from memegine import performance


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(performance, "_store_path", lambda: tmp_path / "posts.jsonl")
    yield tmp_path


def test_log_writes_entry(isolated_store):
    entry = performance.log(
        post_bundle_id="b1", format_slug="photoreal_portrait",
        likes=100, reposts=20, replies=5,
    )
    assert entry.id
    data = (isolated_store / "posts.jsonl").read_text(encoding="utf-8")
    rec = json.loads(data.strip())
    assert rec["likes"] == 100
    assert rec["format_slug"] == "photoreal_portrait"


def test_score_entry_weights_higher_intent_actions():
    # likes=10, reposts=10, replies=10 → 10 + 30 + 20 = 60
    e = {"likes": 10, "reposts": 10, "replies": 10, "quotes": 0, "bookmarks": 0}
    assert performance._score_entry(e) == 60


def test_by_format_averages_correctly(isolated_store):
    performance.log(format_slug="meme_two_panel", likes=100)
    performance.log(format_slug="meme_two_panel", likes=200)
    performance.log(format_slug="photoreal_portrait", likes=50)
    ranking = performance.by_format()
    slugs = [r[0] for r in ranking]
    assert "meme_two_panel" in slugs
    # meme_two_panel has higher avg score than photoreal_portrait
    meme_idx = slugs.index("meme_two_panel")
    portrait_idx = slugs.index("photoreal_portrait")
    assert ranking[meme_idx][2] > ranking[portrait_idx][2]


def test_by_pattern_collates_tokens(isolated_store):
    performance.log(patterns=["35mm f/1.4", "portra 400"], likes=100)
    performance.log(patterns=["35mm f/1.4"], likes=200)
    performance.log(patterns=["50mm f/1.8"], likes=50)
    ranking = performance.by_pattern()
    tokens = [r[0] for r in ranking]
    assert "35mm f/1.4" in tokens
    # 35mm appears twice, higher avg
    idx_35 = tokens.index("35mm f/1.4")
    idx_50 = tokens.index("50mm f/1.8")
    assert ranking[idx_35][1] == 2
    assert ranking[idx_50][1] == 1


def test_latest_per_bundle_dedupe(isolated_store):
    # Log two entries for the same bundle (24h then 7d).
    performance.log(post_bundle_id="b1", likes=100, window="24h")
    performance.log(post_bundle_id="b1", likes=500, window="7d")
    # Only the latest (higher recorded_at) should count in by_format.
    ranking = performance.by_format()
    # Both entries have format_slug=None → 'unknown' bucket
    unknown_row = [r for r in ranking if r[0] == "unknown"][0]
    assert unknown_row[1] == 1  # dedupe to 1


def test_top_n_by_engagement(isolated_store):
    performance.log(post_bundle_id="a", likes=1, format_slug="f1")
    performance.log(post_bundle_id="b", likes=500, reposts=100, format_slug="f2")
    performance.log(post_bundle_id="c", likes=10, format_slug="f3")
    top = performance.top_n(n=2)
    assert len(top) == 2
    assert top[0]["post_bundle_id"] == "b"  # highest score


def test_by_hour_groups_utc(isolated_store):
    performance.log(posted_at="2026-04-18T03:00:00Z", likes=100)
    performance.log(posted_at="2026-04-18T03:30:00Z", likes=200)
    performance.log(posted_at="2026-04-18T15:00:00Z", likes=50)
    buckets = performance.by_hour()
    hours = [b[0] for b in buckets]
    assert 3 in hours
    assert 15 in hours
    hour3 = [b for b in buckets if b[0] == 3][0]
    assert hour3[1] == 2  # count


def test_summary_text_includes_sections(isolated_store):
    performance.log(format_slug="meme_two_panel", likes=200, patterns=["35mm"])
    text = performance.summary_text()
    assert "by format" in text
    assert "by pattern" in text
    assert "meme_two_panel" in text


def test_empty_store(isolated_store):
    assert performance._all_entries() == []
    assert performance.by_format() == []
    assert performance.top_n() == []
