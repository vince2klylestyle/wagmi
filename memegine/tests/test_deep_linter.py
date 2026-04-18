from __future__ import annotations

from memegine import deep_linter


def test_bare_prompt_scores_low():
    sc = deep_linter.score("a person standing there")
    assert sc.score < 40
    assert len(sc.suggestions) >= 4  # multiple things missing
    assert sc.base_lint_ok  # no banned words


def test_banned_words_flagged():
    sc = deep_linter.score("cinematic epic portrait of a trader")
    assert not sc.base_lint_ok
    assert "cinematic" in sc.banned
    assert "epic" in sc.banned
    assert any("banned superlatives" in s for s in sc.suggestions)


def test_good_prompt_scores_high():
    prompt = (
        "Trader in a kitchen, shot on 35mm f/1.4, Cinestill 800T, "
        "hard window light from camera-right, 3am, centered medium close-up, "
        "subject in black hoodie, leather jacket over shoulder, "
        "no extra fingers, no warped text, no logo watermarks."
    )
    sc = deep_linter.score(prompt)
    assert sc.base_lint_ok
    assert sc.score >= 90
    assert deep_linter.grade(sc.score) in ("A", "B")


def test_missing_negative_terms_penalized():
    prompt = (
        "Trader, 35mm, Portra 400, window light, dusk, rule of thirds, "
        "kitchen, hoodie"
    )
    sc = deep_linter.score(prompt)
    # Has craft coverage but no explicit negatives
    assert not sc.hits["negative_terms"]
    assert any("no X, no Y" in s for s in sc.suggestions)


def test_grade_boundaries():
    assert deep_linter.grade(95) == "A"
    assert deep_linter.grade(85) == "B"
    assert deep_linter.grade(75) == "C"
    assert deep_linter.grade(65) == "D"
    assert deep_linter.grade(50) == "F"


def test_weights_sum_to_100():
    assert sum(deep_linter.CRAFT_WEIGHTS.values()) == 100


def test_motion_lint_penalizes_missing_camera_move():
    # A photoreal prompt without a camera move = motion lint fails base.
    prompt = "Trader, 35mm, Cinestill 800T, window light, dusk, centered"
    sc = deep_linter.score(prompt, kind="motion")
    # Score can still be non-zero but motion-specific suggestion should be present
    assert any("camera move" in s.lower() for s in sc.suggestions)
