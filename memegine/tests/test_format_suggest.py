from __future__ import annotations

from memegine import format_suggest


def test_infer_kind_defaults_to_image():
    assert format_suggest.infer_kind("random tokens here") == "image"


def test_infer_kind_detects_video():
    assert format_suggest.infer_kind("5 second video of a trader") == "video"
    assert format_suggest.infer_kind("slow push-in on a face") == "video"
    assert format_suggest.infer_kind("animate this still") == "video"


def test_infer_kind_detects_image():
    assert format_suggest.infer_kind("photoreal portrait of a trader") == "image"
    assert format_suggest.infer_kind("chart meme of cope") == "image"


def test_suggest_returns_top_n():
    picks = format_suggest.suggest("two panel meme setup payoff", top_n=3)
    assert len(picks) <= 3
    assert picks[0].slug == "meme_two_panel"
    # Scored > 0 because triggers matched.
    assert picks[0].score > 0


def test_suggest_prefers_matching_kind():
    # ken burns should rank video_kenburns_still first.
    picks = format_suggest.suggest("slow push zoom on a still", top_n=3)
    slugs = [p.slug for p in picks]
    assert "video_kenburns_still" in slugs


def test_best_returns_a_slug():
    slug = format_suggest.best("drake meme preferring X over Y")
    assert slug == "drake_yes_no"


def test_fallback_when_nothing_matches():
    picks = format_suggest.suggest("zxyw qrs abc", top_n=3)
    # No triggers match but we still return sensible defaults.
    assert len(picks) >= 1
    # Defaults must be valid slugs:
    all_slugs = {s.slug for s in picks}
    assert all_slugs.issubset(
        {
            "photoreal_portrait", "reaction_shot_meme", "lore_drop",
            "video_kenburns_still", "photoreal_scene_motion", "video_single_take_reaction",
        }
    )


def test_kind_filter_applied():
    picks = format_suggest.suggest("trader", kind="video", top_n=5)
    for p in picks:
        assert p.kind == "video"


def test_chart_intent_picks_cope_chart():
    assert format_suggest.best("cope chart, line going up") == "cope_chart"
