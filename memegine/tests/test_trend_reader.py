from __future__ import annotations

import pytest

from memegine import topics, trend_reader


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(trend_reader, "_feeds_path", lambda: tmp_path / "feeds.yaml")
    monkeypatch.setattr(topics, "_queue_path", lambda: tmp_path / "queue.yaml")
    yield tmp_path


def test_add_feed_persists(isolated):
    cfg = trend_reader.add_feed(
        name="test", url="https://example.com/feed", kind="rss",
    )
    assert cfg.name == "test"
    loaded = trend_reader.load_feeds()
    assert len(loaded) == 1
    assert loaded[0].name == "test"


def test_add_feed_replaces_by_name(isolated):
    trend_reader.add_feed(name="same", url="https://a/1", kind="rss")
    trend_reader.add_feed(name="same", url="https://a/2", kind="rss")
    loaded = trend_reader.load_feeds()
    assert len(loaded) == 1
    assert loaded[0].url == "https://a/2"


def test_extract_rss_titles_skips_feed_title():
    body = """
    <rss><channel>
      <title>Feed Name</title>
      <item><title>First item</title></item>
      <item><title>Second item</title></item>
    </channel></rss>
    """
    titles = trend_reader.extract_titles(body, kind="rss", max_items=5)
    # Skips the feed's own title.
    assert "First item" in titles
    assert "Second item" in titles
    assert "Feed Name" not in titles


def test_extract_rss_handles_cdata():
    body = """
    <rss><channel>
      <title>F</title>
      <item><title><![CDATA[ETH broke below 2800]]></title></item>
    </channel></rss>
    """
    titles = trend_reader.extract_titles(body, kind="rss", max_items=5)
    assert "ETH broke below 2800" in titles


def test_extract_jsonl_titles():
    body = '\n'.join([
        '{"title": "item A"}',
        '{"title": "item B"}',
        '{"text": "item C"}',
    ])
    titles = trend_reader.extract_titles(body, kind="jsonl", max_items=5)
    assert "item A" in titles
    assert "item C" in titles


def test_extract_json_list_titles():
    import json
    body = json.dumps([{"title": "A"}, {"title": "B"}])
    titles = trend_reader.extract_titles(body, kind="json", max_items=5)
    assert titles == ["A", "B"]


def test_extract_json_nested_items_key():
    import json
    body = json.dumps({"items": [{"title": "X"}, {"title": "Y"}]})
    titles = trend_reader.extract_titles(body, kind="json", max_items=5)
    assert titles == ["X", "Y"]


def test_fetch_feed_enqueues_new_titles(isolated):
    cfg = trend_reader.FeedConfig(
        name="mock", url="http://fake/", kind="rss", tags=["auto"], priority=4,
    )

    def fake_fetch(url: str) -> str:
        return "<rss><title>F</title><item><title>one</title></item><item><title>two</title></item></rss>"

    result = trend_reader.fetch_feed(cfg, fetcher=fake_fetch)
    assert result.added == 2
    assert result.skipped == 0
    queued = topics.list_queued()
    assert len(queued) == 2
    assert queued[0]["tags"] == ["auto"]
    assert queued[0]["priority"] == 4


def test_fetch_feed_dedupes_existing(isolated):
    topics.add("one")  # already in queue
    cfg = trend_reader.FeedConfig(name="f", url="u", kind="rss")

    def fake_fetch(url: str) -> str:
        return "<rss><title>F</title><item><title>one</title></item><item><title>two</title></item></rss>"

    result = trend_reader.fetch_feed(cfg, fetcher=fake_fetch)
    assert result.added == 1
    assert result.skipped == 1


def test_fetch_feed_handles_network_error(isolated):
    cfg = trend_reader.FeedConfig(name="f", url="u", kind="rss")

    def flaky(url: str):
        raise OSError("no internet")

    result = trend_reader.fetch_feed(cfg, fetcher=flaky)
    assert result.error
    assert result.added == 0


def test_dry_run_does_not_enqueue(isolated):
    cfg = trend_reader.FeedConfig(name="f", url="u", kind="rss")

    def fake(url: str) -> str:
        return "<rss><title>F</title><item><title>one</title></item></rss>"

    result = trend_reader.fetch_feed(cfg, fetcher=fake, dry_run=True)
    assert result.added == 1
    assert topics.list_queued() == []
