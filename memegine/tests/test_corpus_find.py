from __future__ import annotations

from pathlib import Path

import pytest

from memegine import corpus_find, reference_lib


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    from memegine.config import settings
    monkeypatch.setattr(settings, "references_dir", tmp_path / "refs", raising=False)
    (tmp_path / "refs").mkdir()
    yield tmp_path


def _add(tmp_path: Path, marker: str, tags=None, patterns=None, notes="", prompt="") -> str:
    img = tmp_path / f"{marker}.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + marker.encode())
    entry = reference_lib.add(img, tags=tags or [], notes=notes, prompt=prompt)
    if patterns:
        refs = reference_lib._load_index()
        for r in refs:
            if r["id"] == entry.id:
                r["extracted_patterns"] = patterns
        reference_lib._save_index(refs)
    return entry.id


def test_empty_query_returns_empty(isolated):
    _add(isolated, "a", tags=["night"])
    hits = corpus_find.find("")
    assert hits == []


def test_find_matches_extracted_patterns_high_signal(isolated, tmp_path):
    id_a = _add(tmp_path, "a", patterns={"lighting": "hard window light"})
    _add(tmp_path, "b", notes="soft window light")
    hits = corpus_find.find("window light")
    # The extracted_patterns match scores 6 per term, notes scores 1.
    # So "a" should rank higher than "b".
    assert hits
    assert hits[0].ref_id == id_a


def test_find_matches_tags(isolated, tmp_path):
    _add(tmp_path, "a", tags=["3am", "kitchen"])
    hits = corpus_find.find("kitchen")
    assert hits
    assert "tags" in hits[0].matched_fields


def test_multi_term_scoring_additive(isolated, tmp_path):
    # Two terms, both hit extracted_patterns → 6 total.
    id_a = _add(tmp_path, "a", patterns={"location_type": "kitchen at night", "time_of_day": "3am"})
    # Only one term hits.
    _add(tmp_path, "b", patterns={"location_type": "kitchen"})
    hits = corpus_find.find("kitchen 3am")
    assert hits[0].ref_id == id_a


def test_winners_only_filter(isolated, tmp_path):
    id_a = _add(tmp_path, "a", tags=["winner", "kitchen"])
    _add(tmp_path, "b", tags=["kitchen"])
    hits = corpus_find.find("kitchen", winners_only=True)
    assert len(hits) == 1
    assert hits[0].ref_id == id_a


def test_find_text_empty_result_message(isolated):
    text = corpus_find.find_text("nonexistent")
    assert "no refs matched" in text


def test_find_text_formats_hits(isolated, tmp_path):
    _add(tmp_path, "a", tags=["kitchen"], notes="the one")
    text = corpus_find.find_text("kitchen")
    assert "corpus find" in text
    assert "kitchen" in text


def test_limit_respected(isolated, tmp_path):
    for i in range(10):
        _add(tmp_path, f"r{i}", tags=["kitchen"])
    hits = corpus_find.find("kitchen", limit=3)
    assert len(hits) == 3
