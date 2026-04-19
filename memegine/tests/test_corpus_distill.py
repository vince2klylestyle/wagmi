from __future__ import annotations

from pathlib import Path

import pytest

from memegine import corpus_distill, reference_lib


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    from memegine.config import settings
    monkeypatch.setattr(settings, "references_dir", tmp_path / "refs", raising=False)
    (tmp_path / "refs").mkdir()
    monkeypatch.setattr(settings, "codex_path", tmp_path / "style.md", raising=False)
    yield tmp_path


def _add_ref_with_patterns(tmp_path: Path, marker: str, patterns: dict) -> str:
    """Directly write a ref-index entry with extracted_patterns."""
    img = tmp_path / f"{marker}.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + marker.encode())
    entry = reference_lib.add(img, tags=["corpus"])
    # Update the index in-place with extracted_patterns.
    refs = reference_lib._load_index()
    for r in refs:
        if r["id"] == entry.id:
            r["extracted_patterns"] = patterns
    reference_lib._save_index(refs)
    return entry.id


def test_distill_empty_corpus_returns_empty_report(isolated):
    r = corpus_distill.distill()
    assert r.total_refs == 0
    assert r.refs_with_patterns == 0
    assert not r.promoted_to_visual_dna


def test_tally_groups_by_field(isolated, tmp_path):
    _add_ref_with_patterns(tmp_path, "a", {"lens": "35mm f/1.4", "film_stock": "Portra 400"})
    _add_ref_with_patterns(tmp_path, "b", {"lens": "35mm f/1.4", "film_stock": "Cinestill 800T"})
    _add_ref_with_patterns(tmp_path, "c", {"lens": "50mm f/1.8", "film_stock": "Portra 400"})
    refs = reference_lib._load_index()
    with_patterns, freq = corpus_distill._tally(refs)
    assert with_patterns == 3
    # 35mm f/1.4 appears 2x (dominant); 50mm 1x
    lens_top = freq["lens"][0]
    assert "35mm" in lens_top[0]
    assert lens_top[1] == 2


def test_distill_promotes_dominant_to_visual_dna(isolated, tmp_path):
    # 4 refs, 3 use same lens → 75% share > default 30%.
    for i, lens in enumerate(["35mm f/1.4"] * 3 + ["50mm f/1.8"]):
        _add_ref_with_patterns(tmp_path, f"r{i}", {"lens": lens})
    r = corpus_distill.distill()
    assert any("35mm" in e for e in r.promoted_to_visual_dna)


def test_distill_promotes_to_core_patterns_above_threshold(isolated, tmp_path):
    # 6 refs all share lens → passes core_min=5.
    for i in range(6):
        _add_ref_with_patterns(tmp_path, f"r{i}", {"lens": "35mm f/1.4"})
    r = corpus_distill.distill(core_min_count=5)
    assert any("35mm" in e for e in r.promoted_to_core)


def test_distill_dry_run_does_not_write_codex(isolated, tmp_path):
    for i in range(6):
        _add_ref_with_patterns(tmp_path, f"r{i}", {"lens": "35mm f/1.4"})
    codex_path = isolated / "style.md"
    r = corpus_distill.distill(dry_run=True)
    assert r.promoted_to_core
    # Codex still empty.
    assert not codex_path.exists() or "Core Patterns" not in codex_path.read_text(encoding="utf-8")


def test_distill_writes_codex(isolated, tmp_path):
    for i in range(6):
        _add_ref_with_patterns(tmp_path, f"r{i}", {
            "lens": "35mm f/1.4",
            "lighting": "hard window light",
        })
    r = corpus_distill.distill(core_min_count=5, dna_min_share=0.5)
    codex_path = isolated / "style.md"
    assert codex_path.exists()
    text = codex_path.read_text(encoding="utf-8")
    assert "Visual DNA" in text
    assert "Core Patterns" in text
    assert "35mm" in text


def test_distill_ignores_empty_and_noise_values(isolated, tmp_path):
    _add_ref_with_patterns(tmp_path, "a", {"lens": ""})
    _add_ref_with_patterns(tmp_path, "b", {"lens": "none"})
    _add_ref_with_patterns(tmp_path, "c", {"lens": "N/A"})
    _add_ref_with_patterns(tmp_path, "d", {"lens": "35mm f/1.4"})
    refs = reference_lib._load_index()
    _, freq = corpus_distill._tally(refs)
    # Only the real value survives.
    assert freq["lens"] == [("35mm f/1.4", 1)]


def test_stats_text_includes_counts(isolated, tmp_path):
    _add_ref_with_patterns(tmp_path, "a", {"lens": "35mm f/1.4"})
    text = corpus_distill.stats_text()
    assert "corpus" in text
    assert "extracted data" in text
    assert "35mm" in text
