from __future__ import annotations

from pathlib import Path

import pytest

from memegine import corpus, reference_lib


@pytest.fixture
def isolated_refs(tmp_path, monkeypatch):
    from memegine.config import settings
    monkeypatch.setattr(settings, "references_dir", tmp_path / "refs", raising=False)
    (tmp_path / "refs").mkdir()
    yield tmp_path


def _mk_img(path: Path, marker: str) -> None:
    """Create a unique 'image' file (PNG header + marker bytes)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + marker.encode())


def test_ingest_empty_folder_returns_clean_result(isolated_refs, tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    r = corpus.ingest(src, frames_per_video=0)
    assert r.images_seen == 0
    assert r.videos_seen == 0
    assert r.errors == []


def test_ingest_raises_on_missing_folder(isolated_refs):
    r = corpus.ingest("/does-not-exist-xyz", frames_per_video=0)
    assert r.errors


def test_ingest_imports_images(isolated_refs, tmp_path):
    src = tmp_path / "src"
    _mk_img(src / "portrait.png", "A")
    _mk_img(src / "chart.jpg", "B")
    _mk_img(src / "meme.webp", "C")
    r = corpus.ingest(src, frames_per_video=0)
    assert r.images_seen == 3
    assert r.images_imported == 3


def test_ingest_tags_from_folder_hierarchy(isolated_refs, tmp_path):
    src = tmp_path / "src"
    _mk_img(src / "photoreal" / "portraits" / "3am_trader.png", "X")
    r = corpus.ingest(src, frames_per_video=0)
    assert r.images_imported == 1
    ref_id = r.imported_ref_ids[0]
    refs = reference_lib._load_index()
    entry = next(e for e in refs if e["id"] == ref_id)
    assert "photoreal" in entry["tags"]
    assert "portraits" in entry["tags"]
    # Tokens from filename.
    assert "trader" in entry["tags"]


def test_ingest_reads_sidecar_as_prompt(isolated_refs, tmp_path):
    src = tmp_path / "src"
    _mk_img(src / "hero.png", "H")
    (src / "hero.txt").write_text("trader, 35mm, Portra 400", encoding="utf-8")
    r = corpus.ingest(src, frames_per_video=0)
    refs = reference_lib._load_index()
    entry = next(e for e in refs if e["id"] == r.imported_ref_ids[0])
    assert "Portra 400" in entry["prompt"]


def test_ingest_dedupes_identical_files(isolated_refs, tmp_path):
    src = tmp_path / "src"
    _mk_img(src / "a.png", "SAMEBYTES")
    _mk_img(src / "b.png", "SAMEBYTES")
    r = corpus.ingest(src, frames_per_video=0)
    # Both files hash identically → one ref id, one import, one "skip".
    assert r.images_seen == 2
    assert r.images_imported + r.skipped_duplicates == 2
    assert r.images_imported == 1


def test_ingest_tag_prefix_applied(isolated_refs, tmp_path):
    src = tmp_path / "src"
    _mk_img(src / "x.png", "T")
    r = corpus.ingest(src, frames_per_video=0, tag_prefix="batch-2026-04")
    refs = reference_lib._load_index()
    entry = next(e for e in refs if e["id"] == r.imported_ref_ids[0])
    assert "batch-2026-04" in entry["tags"]


def test_infer_tags_skips_wrapper_dirs():
    # Files inside a wrapper named "memegine_ingest" shouldn't tag
    # the wrapper as a meaningful label.
    from memegine.corpus import _infer_tags
    base = Path("/x")
    file_path = Path("/x/memegine_ingest/photoreal/3am_trader.png")
    tags = _infer_tags(file_path, base)
    assert "memegine_ingest" not in tags
    assert "photoreal" in tags


def test_infer_tags_strips_numeric_only_tokens():
    from memegine.corpus import _infer_tags
    base = Path("/x")
    file_path = Path("/x/0001.png")
    tags = _infer_tags(file_path, base)
    # "0001" is purely numeric → excluded
    assert "0001" not in tags


def test_as_text_formats_cleanly(isolated_refs, tmp_path):
    src = tmp_path / "src"
    _mk_img(src / "a.png", "A")
    r = corpus.ingest(src, frames_per_video=0)
    text = r.as_text()
    assert "corpus ingest" in text
    assert "images imported" in text
