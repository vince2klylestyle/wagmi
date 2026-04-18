"""Verify the 6 new formats load cleanly and have required fields."""
from __future__ import annotations

import pytest

from memegine import format_suggest, prompt_engine


NEW_FORMATS = (
    "photoreal_self_avatar",
    "screenshot_terminal",
    "ticker_scroll_overlay",
    "found_footage_still",
    "zine_pullquote",
    "vhs_ad_spoof",
)


def test_new_formats_loaded():
    slugs = {f.slug for f in prompt_engine.load_formats()}
    for slug in NEW_FORMATS:
        assert slug in slugs, f"{slug} not in library"


def test_new_formats_have_scaffolds():
    formats = {f.slug: f for f in prompt_engine.load_formats()}
    for slug in NEW_FORMATS:
        f = formats[slug]
        # Image formats use prompt_scaffold; video uses still + motion.
        if f.kind == "image":
            assert f.prompt_scaffold, f"{slug} missing prompt_scaffold"
        else:
            assert f.prompt_scaffold_still, f"{slug} missing prompt_scaffold_still"


def test_new_formats_have_good_models():
    formats = {f.slug: f for f in prompt_engine.load_formats()}
    for slug in NEW_FORMATS:
        f = formats[slug]
        models = f.good_models + f.good_models_still + f.good_models_motion
        assert models, f"{slug} has no good_models"


def test_terminal_intent_triggers_terminal_format():
    picks = format_suggest.suggest("bloomberg terminal cope screenshot", top_n=3)
    slugs = [p.slug for p in picks]
    assert "screenshot_terminal" in slugs or "cope_chart" in slugs


def test_infomercial_intent_triggers_vhs_ad_spoof():
    assert format_suggest.best("infomercial with an 800 number") == "vhs_ad_spoof"


def test_self_avatar_triggers_self_avatar_format():
    assert format_suggest.best("Kilroy, my recurring character, at the desk") == "photoreal_self_avatar"


def test_all_new_slugs_assembles_a_brief():
    from memegine.prompt_engine import assemble_offline_prompt
    for slug in NEW_FORMATS:
        system, user = assemble_offline_prompt("a trader at 3am", slug)
        assert system
        assert user
        assert slug in user
