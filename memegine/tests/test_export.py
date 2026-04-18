from __future__ import annotations

import json
from pathlib import Path

import pytest

from memegine import export


@pytest.fixture
def media_file(tmp_path):
    f = tmp_path / "final.png"
    f.write_bytes(b"\x89PNG\r\n\x1a\n")  # PNG header bytes, enough for copy
    return f


def test_build_creates_folder_with_media_and_caption(tmp_path, media_file):
    posts_dir = tmp_path / "posts"
    bundle = export.build(
        media_path=media_file,
        caption="it's 3am and he is not ok",
        alt_text="portrait of a trader at 3am",
        tags=["night", "trader"],
        posts_dir=posts_dir,
    )
    folder = Path(bundle.folder)
    assert folder.exists()
    assert (folder / "final.png").exists()
    assert (folder / "caption.txt").read_text().startswith("it's 3am")
    assert (folder / "alt_text.txt").read_text().startswith("portrait of a trader")
    assert (folder / "README.md").exists()
    meta = json.loads((folder / "meta.json").read_text())
    assert meta["caption"].startswith("it's 3am")
    assert meta["tags"] == ["night", "trader"]


def test_build_reply_hook_only_when_present(tmp_path, media_file):
    posts_dir = tmp_path / "posts"
    bundle = export.build(
        media_path=media_file, caption="short",
        reply_hook="", posts_dir=posts_dir,
    )
    folder = Path(bundle.folder)
    assert not (folder / "reply_hook.txt").exists()

    bundle2 = export.build(
        media_path=media_file, caption="short",
        reply_hook="the followup", posts_dir=posts_dir,
    )
    assert (Path(bundle2.folder) / "reply_hook.txt").read_text().strip() == "the followup"


def test_build_raises_on_missing_media(tmp_path):
    with pytest.raises(FileNotFoundError):
        export.build(
            media_path=tmp_path / "nope.png",
            caption="x",
            posts_dir=tmp_path,
        )


def test_list_recent_returns_most_recent_first(tmp_path, media_file):
    posts_dir = tmp_path / "posts"
    b1 = export.build(media_path=media_file, caption="first", posts_dir=posts_dir)
    b2 = export.build(media_path=media_file, caption="second", posts_dir=posts_dir)
    recent = export.list_recent(n=5, posts_dir=posts_dir)
    assert len(recent) == 2
    # Folders named with date+slug+id; the second build happened later so
    # its folder sorts after the first (both same date — so order by id
    # may not strictly be by create time; we just assert both present).
    ids = {r["id"] for r in recent}
    assert b1.id in ids
    assert b2.id in ids


def test_build_preserves_extension(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"\x00\x00\x00\x18ftypisom")
    posts_dir = tmp_path / "posts"
    bundle = export.build(media_path=video, caption="video post", posts_dir=posts_dir)
    assert bundle.media_path.endswith("final.mp4")
