from __future__ import annotations

import pytest

from memegine import reference_lib, tag_normalize


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    from memegine.config import settings
    monkeypatch.setattr(settings, "references_dir", tmp_path / "refs", raising=False)
    (tmp_path / "refs").mkdir()
    yield tmp_path


def _add(tmp_path, marker: str, tags: list[str]) -> str:
    p = tmp_path / f"{marker}.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + marker.encode())
    return reference_lib.add(p, tags=tags).id


def test_normalize_one_lowercases():
    assert tag_normalize._normalize_one("NIGHT", {}) == "night"


def test_normalize_one_dash_to_underscore():
    assert tag_normalize._normalize_one("late-night", {}) == "late_night"


def test_normalize_one_applies_synonym():
    assert tag_normalize._normalize_one("portraits", {"portraits": "portrait"}) == "portrait"


def test_normalize_one_preserves_prefix_value():
    # editor:alice should stay intact.
    assert tag_normalize._normalize_one("editor:alice", {}) == "editor:alice"


def test_preview_flags_changes(isolated, tmp_path):
    _add(tmp_path, "a", ["PORTRAITS", "3-am"])
    report = tag_normalize.preview()
    assert len(report.changes) == 1
    change = report.changes[0]
    assert "portrait" in change.after
    assert "3am" in change.after


def test_apply_persists(isolated, tmp_path):
    rid = _add(tmp_path, "a", ["PORTRAITS"])
    report = tag_normalize.apply()
    assert len(report.changes) == 1
    refs = reference_lib._load_index()
    assert refs[0]["tags"] == ["portrait"]


def test_outliers_reported(isolated, tmp_path):
    # "common" appears 3x, "rare" appears 1x → rare is an outlier.
    _add(tmp_path, "a", ["common"])
    _add(tmp_path, "b", ["common"])
    _add(tmp_path, "c", ["common"])
    _add(tmp_path, "d", ["rare"])
    report = tag_normalize.preview()
    outlier_tags = [t for t, _ in report.outliers]
    assert "rare" in outlier_tags


def test_as_text_renders(isolated, tmp_path):
    _add(tmp_path, "a", ["PORTRAITS", "3-am"])
    text = tag_normalize.preview().as_text()
    assert "would change" in text


def test_custom_synonym_supported(isolated, tmp_path):
    _add(tmp_path, "a", ["dev"])
    report = tag_normalize.apply(synonyms={"dev": "developer"})
    refs = reference_lib._load_index()
    assert refs[0]["tags"] == ["developer"]
