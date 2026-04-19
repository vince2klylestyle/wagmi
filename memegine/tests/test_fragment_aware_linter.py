from __future__ import annotations

from memegine import deep_linter


def test_missing_lens_suggestion_references_fragment():
    """Deep linter should mention fragment slugs when a category is missing."""
    sc = deep_linter.score("a prompt without specifics")
    lens_tips = [s for s in sc.suggestions if "lens" in s.lower() or "stock" in s.lower()]
    assert lens_tips
    # At least one should mention the LENS fragment category.
    joined = " ".join(lens_tips)
    assert "LENS." in joined or "FILM." in joined


def test_missing_lighting_tip_references_lighting_fragment():
    sc = deep_linter.score("a prompt")
    tips = [s for s in sc.suggestions if "lighting" in s.lower()]
    assert tips
    joined = " ".join(tips)
    assert "LIGHTING." in joined


def test_missing_time_of_day_tip_references_fragment():
    sc = deep_linter.score("a prompt")
    tips = [s for s in sc.suggestions if "time" in s.lower() or "weather" in s.lower()]
    assert tips
    joined = " ".join(tips)
    assert "TIME_OF_DAY." in joined


def test_perfect_prompt_has_no_tips():
    prompt = (
        "Trader in a kitchen, 35mm f/1.4, Cinestill 800T, hard window light, "
        "3am, centered medium close-up, subject in black hoodie, "
        "no extra fingers, no warped text, no logo watermarks."
    )
    sc = deep_linter.score(prompt)
    assert sc.score >= 90
    assert not sc.suggestions


def test_fragment_hints_dont_break_when_library_missing(monkeypatch):
    # Simulate fragments library load failure.
    from memegine import deep_linter as dl
    import memegine.fragments as frag
    monkeypatch.setattr(frag, "load", lambda path=None: {})
    sc = dl.score("a prompt")
    # Still returns suggestions, just without fragment codes.
    assert sc.suggestions
