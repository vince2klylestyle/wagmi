from __future__ import annotations

import datetime as dt
import json

import pytest

from memegine import search


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    from memegine import reference_lib, export as export_mod, topics
    from memegine.config import settings
    monkeypatch.setattr(settings, "logs_dir", tmp_path / "logs", raising=False)
    (tmp_path / "logs").mkdir()
    monkeypatch.setattr(settings, "references_dir", tmp_path / "refs", raising=False)
    (tmp_path / "refs").mkdir()
    monkeypatch.setattr(settings, "codex_path", tmp_path / "style.md", raising=False)
    monkeypatch.setattr(export_mod, "_posts_dir", lambda: tmp_path / "posts")
    monkeypatch.setattr(topics, "_queue_path", lambda: tmp_path / "queue.yaml")
    yield tmp_path


def test_empty_query_returns_empty_result(isolated):
    result = search.run("")
    assert result.hits == []


def test_search_brief_by_intent(isolated):
    logs = isolated / "logs"
    today = dt.datetime.utcnow().date().isoformat()
    rec = {
        "id": "b1", "created_at": f"{today}T10:00:00Z",
        "kind": "prompt", "intent": "trader at 3am, quiet dread",
        "system": "s", "user": "u",
    }
    (logs / f"briefs-{today}.jsonl").write_text(json.dumps(rec) + "\n")

    result = search.run("trader")
    assert any(h.store == "brief" for h in result.hits)


def test_search_refs_by_tag_or_notes(isolated):
    from memegine import reference_lib
    img = isolated / "x.png"
    img.write_bytes(b"PNG")
    reference_lib.add(img, tags=["night", "trader"], notes="the quiet-dread one")

    result = search.run("night")
    assert any(h.store == "ref" for h in result.hits)
    result2 = search.run("quiet-dread")
    assert any(h.store == "ref" for h in result2.hits)


def test_search_topics(isolated):
    from memegine import topics
    topics.add("ETH broke below 2800 overnight")
    result = search.run("ETH")
    assert any(h.store == "topic" for h in result.hits)


def test_search_codex_sections(isolated):
    from memegine import style_codex
    style_codex.append_entry("Proven Prompt Patterns", "35mm f/1.4 always works")
    result = search.run("35mm")
    assert any(h.store == "codex" for h in result.hits)


def test_store_filter_limits_search(isolated):
    from memegine import reference_lib, topics
    img = isolated / "x.png"
    img.write_bytes(b"PNG")
    reference_lib.add(img, tags=["trader"])
    topics.add("trader at 3am")

    result = search.run("trader", stores=["topic"])
    stores_hit = {h.store for h in result.hits}
    assert "topic" in stores_hit
    assert "ref" not in stores_hit


def test_no_hits_returns_friendly_message(isolated):
    result = search.run("verylongstringnobodywrote")
    assert "no hits" in result.as_text()


def test_as_text_lists_hits(isolated):
    from memegine import topics
    topics.add("trader at 3am")
    result = search.run("trader")
    text = result.as_text()
    assert "trader" in text.lower()
    assert "hits" in text
