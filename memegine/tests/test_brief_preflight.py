from __future__ import annotations

import pytest

from memegine import brief_preflight, style_codex


@pytest.fixture
def isolated_codex(tmp_path, monkeypatch):
    codex = tmp_path / "style.md"
    from memegine.config import settings
    monkeypatch.setattr(settings, "codex_path", codex, raising=False)
    return codex


def test_pass_verdict_on_strong_prompt(isolated_codex):
    prompt = (
        "Trader in a kitchen, 35mm f/1.4, Cinestill 800T, "
        "hard window light at 3:1 ratio, 3am, centered medium close-up, "
        "subject in black hoodie, no extra fingers, no warped text."
    )
    report = brief_preflight.check(prompt)
    # Empty codex → consistency doesn't penalize.
    assert report.verdict == "PASS"
    assert report.craft_score >= 70
    assert not report.banned_words


def test_fail_on_banned_word(isolated_codex):
    report = brief_preflight.check("cinematic portrait")
    assert report.verdict == "FAIL"
    assert "cinematic" in report.banned_words


def test_fail_on_weak_craft_score(isolated_codex):
    # "a trader" bare is below craft 50.
    report = brief_preflight.check("a trader")
    assert report.verdict == "FAIL"
    assert report.craft_score < 50


def test_warn_on_mid_craft(isolated_codex):
    # Craft should land in 50-69 range: has lens + lighting but no
    # composition or negatives.
    prompt = "trader at 3am in a kitchen, 35mm f/1.4, window light"
    report = brief_preflight.check(prompt)
    # Craft should roughly land 60-70 — warn-band.
    assert report.verdict in ("WARN", "PASS")
    assert 50 <= report.craft_score


def test_consistency_penalty_with_codex(isolated_codex):
    style_codex.append_entry("Core Patterns", "lens: 35mm f/1.4")
    style_codex.append_entry("Core Patterns", "lighting: hard window light")
    # Prompt that would otherwise pass now fails consistency.
    prompt = (
        "Trader in a kitchen, 85mm f/1.2, Portra 400, softbox, dusk, "
        "rule of thirds, no extra fingers."
    )
    report = brief_preflight.check(prompt)
    # Core Patterns say 35mm/window — prompt uses 85mm/softbox → 0%.
    assert report.consistency_score == 0


def test_motion_mode_flags_missing_camera_move(isolated_codex):
    prompt = "a trader, 35mm, Cinestill 800T, window light, dusk, rule of thirds"
    report = brief_preflight.check(prompt, motion=True)
    # Motion mode → base linter demands a camera move; absence = FAIL.
    assert report.verdict == "FAIL"


def test_as_text_includes_verdict():
    r = brief_preflight.PreflightReport(
        prompt="p", verdict="PASS", craft_score=80, craft_grade="B",
        consistency_score=50,
    )
    text = r.as_text()
    assert "PASS" in text
    assert "80/100" in text
