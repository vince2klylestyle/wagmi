from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from memegine import project


@pytest.fixture
def isolated_data(tmp_path, monkeypatch):
    from memegine.config import settings
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(settings, "data_dir", data_dir, raising=False)
    yield data_dir


def test_archive_empty_data_dir_creates_valid_zip(isolated_data, tmp_path):
    dst = tmp_path / "empty.zip"
    result = project.archive(dst)
    assert Path(result.destination).exists()
    assert result.files_included == 0


def test_archive_includes_expected_dirs(isolated_data, tmp_path):
    codex_path = isolated_data / "codex" / "style.md"
    codex_path.parent.mkdir(parents=True)
    codex_path.write_text("# codex\n", encoding="utf-8")
    refs_path = isolated_data / "references" / "index.json"
    refs_path.parent.mkdir(parents=True)
    refs_path.write_text("[]", encoding="utf-8")

    dst = tmp_path / "snap.zip"
    result = project.archive(dst)
    assert result.files_included == 2
    with zipfile.ZipFile(dst) as zf:
        names = zf.namelist()
        assert any("codex/style.md" in n for n in names)
        assert any("references/index.json" in n for n in names)


def test_archive_default_destination(isolated_data):
    result = project.archive()
    dst = Path(result.destination)
    assert dst.exists()
    assert dst.name.startswith("memegine-snapshot-")


def test_restore_refuses_nonempty_without_force(isolated_data, tmp_path):
    # Populate data_dir.
    (isolated_data / "codex").mkdir()
    (isolated_data / "codex" / "a.md").write_text("x", encoding="utf-8")

    # Make a dummy archive.
    snap = tmp_path / "snap.zip"
    with zipfile.ZipFile(snap, "w") as zf:
        zf.writestr("codex/b.md", "y")

    with pytest.raises(ValueError):
        project.restore(snap)


def test_restore_force_overwrites(isolated_data, tmp_path):
    (isolated_data / "codex").mkdir()
    (isolated_data / "codex" / "a.md").write_text("original", encoding="utf-8")

    snap = tmp_path / "snap.zip"
    with zipfile.ZipFile(snap, "w") as zf:
        zf.writestr("codex/b.md", "restored")

    result = project.restore(snap, force=True)
    assert result.restored_files == 1
    assert (isolated_data / "codex" / "b.md").read_text() == "restored"


def test_round_trip(isolated_data, tmp_path):
    # Populate, archive, wipe, restore.
    codex = isolated_data / "codex" / "style.md"
    codex.parent.mkdir(parents=True)
    codex.write_text("# HI\n", encoding="utf-8")
    dst = tmp_path / "snap.zip"
    project.archive(dst)

    # Wipe.
    import shutil
    shutil.rmtree(isolated_data)
    isolated_data.mkdir()

    project.restore(dst)
    restored = isolated_data / "codex" / "style.md"
    assert restored.exists()
    assert restored.read_text() == "# HI\n"


def test_restore_missing_file_raises(isolated_data, tmp_path):
    with pytest.raises(FileNotFoundError):
        project.restore(tmp_path / "nope.zip")
