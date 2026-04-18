from __future__ import annotations

from memegine import idea_grader


def test_high_quality_intent_scores_a():
    intent = "trader at 3am, cope face, 12% drawdown day"
    g = idea_grader.grade(intent)
    assert g.letter == "A"
    assert g.score >= 90
    assert g.hits["specificity"]
    assert g.hits["emotion"]
    assert g.hits["concrete_hook"]


def test_vague_intent_scores_low():
    g = idea_grader.grade("some vibes about crypto")
    assert g.score < 50
    assert "vibes" in g.vague
    assert any("vague" in s.lower() for s in g.suggestions)


def test_banned_words_flagged():
    g = idea_grader.grade("cinematic epic trader portrait")
    assert not g.hits["no_ai_slop"]
    assert "cinematic" in g.banned
    assert any("slop" in s for s in g.suggestions)


def test_missing_emotion_gets_suggestion():
    g = idea_grader.grade("trader looking at his laptop in the kitchen")
    assert not g.hits["emotion"]
    assert any("emotion" in s.lower() for s in g.suggestions)


def test_too_short_intent():
    g = idea_grader.grade("trader")
    assert not g.hits["length_sweet_spot"]
    assert any("too short" in s for s in g.suggestions)


def test_too_long_intent():
    intent = " ".join(["word"] * 50)
    g = idea_grader.grade(intent)
    assert not g.hits["length_sweet_spot"]


def test_weights_sum_to_100():
    assert sum(idea_grader.GRADE_WEIGHTS.values()) == 100


def test_format_hits_returned_when_triggers_match():
    g = idea_grader.grade("two-panel meme setup payoff about etf flows")
    assert "meme_two_panel" in g.format_hits


def test_concrete_hook_detected_for_number_time():
    g = idea_grader.grade("it's 3am and he's 12% down")
    assert g.hits["concrete_hook"]


def test_subject_named_detects_trader():
    g = idea_grader.grade("trader staring at the terminal")
    assert g.hits["subject_named"]


def test_letter_grade_boundaries():
    # Verify boundaries by constructing intents with expected scores.
    # Score of 100 = all categories hit.
    best = "cope-face trader at 3am looking at a chart, 12% drawdown"
    g = idea_grader.grade(best)
    assert g.letter in ("A", "B")  # depending on emotion detection
