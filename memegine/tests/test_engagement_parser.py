from __future__ import annotations

import pytest

from memegine import engagement_parser, performance


@pytest.fixture
def isolated_perf(tmp_path, monkeypatch):
    monkeypatch.setattr(performance, "_store_path", lambda: tmp_path / "perf.jsonl")
    yield tmp_path


def test_parse_vertical_layout():
    p = engagement_parser.parse("820 Likes\n140 Reposts\n35 Replies\n12.4K Views")
    assert p.likes == 820
    assert p.reposts == 140
    assert p.replies == 35
    assert p.impressions == 12400


def test_parse_inline_separator():
    p = engagement_parser.parse("820 likes · 140 retweets · 35 replies")
    assert p.likes == 820
    assert p.reposts == 140
    assert p.replies == 35


def test_parse_horizontal_all_fields():
    p = engagement_parser.parse(
        "12.4K views  820 likes  140 retweets  35 replies  2 bookmarks  4 quotes"
    )
    assert p.likes == 820
    assert p.reposts == 140
    assert p.replies == 35
    assert p.quotes == 4
    assert p.bookmarks == 2
    assert p.impressions == 12400


def test_k_m_suffix_expansion():
    p = engagement_parser.parse("1.2M views, 45K likes, 2.3K retweets")
    assert p.impressions == 1_200_000
    assert p.likes == 45_000
    assert p.reposts == 2300


def test_emoji_labels():
    p = engagement_parser.parse("❤ 820  🔁 140  💬 35  📊 12.4K")
    assert p.likes == 820
    assert p.reposts == 140
    assert p.replies == 35
    assert p.impressions == 12400


def test_comma_thousands_separator():
    p = engagement_parser.parse("12,400 views  1,234 likes")
    assert p.impressions == 12400
    assert p.likes == 1234


def test_singular_forms():
    p = engagement_parser.parse("1 like, 1 repost, 1 reply")
    assert p.likes == 1
    assert p.reposts == 1
    assert p.replies == 1


def test_empty_string_returns_empty():
    p = engagement_parser.parse("")
    assert not p.any_found()


def test_no_numbers_returns_empty():
    p = engagement_parser.parse("just text no numbers here")
    assert not p.any_found()


def test_unlabeled_number_not_assigned():
    # A bare "42" with no label nearby should NOT land in any field.
    p = engagement_parser.parse("something random 42 yeah")
    assert not p.any_found()
    assert p.unmatched_numbers >= 1


def test_retweet_synonym():
    p = engagement_parser.parse("500 RT")
    assert p.reposts == 500


def test_views_synonym():
    p = engagement_parser.parse("1000 impressions")
    assert p.impressions == 1000


def test_max_taken_when_multiple_hits_for_same_field():
    # X sometimes shows "820" on one line and "820 likes" on another.
    p = engagement_parser.parse("820\n820 likes")
    # Both labeled as likes → max is 820.
    assert p.likes == 820


def test_log_from_paste_writes_perf_entry(isolated_perf):
    entry, parsed = engagement_parser.log_from_paste(
        "820 likes, 140 retweets, 35 replies",
        post_bundle_id="b1", format_slug="meme_two_panel",
    )
    assert entry is not None
    assert entry.likes == 820
    assert entry.reposts == 140
    # It actually persisted.
    recorded = performance._all_entries()
    assert len(recorded) == 1
    assert recorded[0]["post_bundle_id"] == "b1"


def test_log_from_paste_noop_on_empty(isolated_perf):
    entry, parsed = engagement_parser.log_from_paste("")
    assert entry is None
    assert not parsed.any_found()
    assert performance._all_entries() == []


def test_label_priority_with_ambiguous_neighbor():
    # "views" and "likes" both in the window — the closer wins.
    p = engagement_parser.parse("820 likes 1000 views")
    assert p.likes == 820
    assert p.impressions == 1000
