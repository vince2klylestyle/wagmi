from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from memegine import snapshot_diff


def _zip(dst: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(dst, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)


def test_identical_snapshots(tmp_path):
    a = tmp_path / "a.zip"
    b = tmp_path / "b.zip"
    files = {"codex/style.md": b"hi", "refs/index.json": b"[]"}
    _zip(a, files)
    _zip(b, files)
    report = snapshot_diff.diff(a, b)
    assert report.unchanged_count == 2
    assert report.added == []
    assert report.removed == []
    assert report.changed == []


def test_added_files_flagged(tmp_path):
    a = tmp_path / "a.zip"
    b = tmp_path / "b.zip"
    _zip(a, {"codex/style.md": b"x"})
    _zip(b, {"codex/style.md": b"x", "refs/index.json": b"[]"})
    report = snapshot_diff.diff(a, b)
    assert "refs/index.json" in report.added
    assert report.unchanged_count == 1


def test_removed_files_flagged(tmp_path):
    a = tmp_path / "a.zip"
    b = tmp_path / "b.zip"
    _zip(a, {"codex/style.md": b"x", "old/thing.txt": b"y"})
    _zip(b, {"codex/style.md": b"x"})
    report = snapshot_diff.diff(a, b)
    assert "old/thing.txt" in report.removed


def test_changed_files_flagged_by_size(tmp_path):
    a = tmp_path / "a.zip"
    b = tmp_path / "b.zip"
    _zip(a, {"codex/style.md": b"short"})
    _zip(b, {"codex/style.md": b"much longer content now"})
    report = snapshot_diff.diff(a, b)
    assert len(report.changed) == 1
    name, a_sz, b_sz = report.changed[0]
    assert name == "codex/style.md"
    assert a_sz < b_sz


def test_as_text_renders(tmp_path):
    a = tmp_path / "a.zip"
    b = tmp_path / "b.zip"
    _zip(a, {"codex/style.md": b"x"})
    _zip(b, {"codex/style.md": b"x", "refs/index.json": b"[]"})
    text = snapshot_diff.diff(a, b).as_text()
    assert "snapshot diff" in text
    assert "added in b: 1" in text
