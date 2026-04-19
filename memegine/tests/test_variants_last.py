from __future__ import annotations

import pytest

from memegine import reference_lib, variants


@pytest.fixture
def isolated_refs(tmp_path, monkeypatch):
    refs_dir = tmp_path / "refs"
    monkeypatch.setattr(reference_lib.settings, "references_dir", refs_dir, raising=False)
    from memegine.config import settings as cfg_settings
    monkeypatch.setattr(cfg_settings, "codex_path", tmp_path / "style.md", raising=False)
    yield tmp_path


def test_raises_when_no_winner_exists(isolated_refs):
    with pytest.raises(ValueError):
        variants.build_from_last_winner(n_variants=6)


def test_uses_latest_winner_prompt(isolated_refs):
    img = isolated_refs / "a.png"
    img.write_bytes(b"\x89PNG1")
    img2 = isolated_refs / "b.png"
    img2.write_bytes(b"\x89PNG2")

    # Add an old winner first.
    reference_lib.add(img, prompt="old prompt, 35mm", winner=True)
    # Then a newer one.
    reference_lib.add(img2, prompt="new prompt, 50mm", winner=True)

    vb = variants.build_from_last_winner(n_variants=6)
    assert "new prompt" in vb.user
    assert "50mm" in vb.user


def test_skips_winners_without_prompt(isolated_refs):
    img = isolated_refs / "c.png"
    img.write_bytes(b"PNG")
    img2 = isolated_refs / "d.png"
    img2.write_bytes(b"PNG2")

    # A winner with a prompt, and a later one without.
    reference_lib.add(img, prompt="with prompt", winner=True)
    reference_lib.add(img2, prompt="", winner=True, notes="just an image")

    vb = variants.build_from_last_winner(n_variants=4)
    assert "with prompt" in vb.user


def test_honors_n_variants(isolated_refs):
    img = isolated_refs / "w.png"
    img.write_bytes(b"PNG")
    reference_lib.add(img, prompt="trader, 35mm", winner=True)
    vb = variants.build_from_last_winner(n_variants=4)
    assert "N variants\n4" in vb.user
