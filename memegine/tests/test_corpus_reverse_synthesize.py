from __future__ import annotations

from memegine import corpus_reverse


def test_synthesize_prompt_joins_fields():
    patterns = {
        "subject": "trader at laptop, hoodie",
        "location_type": "kitchen at 3am",
        "lens": "35mm f/1.4",
        "film_stock": "Cinestill 800T",
        "lighting": "hard window light",
        "time_of_day": "3am",
        "composition": "rule of thirds",
    }
    prompt = corpus_reverse.synthesize_prompt(patterns)
    assert "trader at laptop" in prompt
    assert "35mm" in prompt
    assert "Cinestill 800T" in prompt
    assert "hard window light" in prompt
    # Always appends the photoreal negative clause.
    assert "no extra fingers" in prompt


def test_synthesize_prompt_empty_returns_empty():
    assert corpus_reverse.synthesize_prompt({}) == ""


def test_synthesize_prompt_ignores_non_string_values():
    # Guard against malformed inputs.
    prompt = corpus_reverse.synthesize_prompt({
        "lens": 35,  # int, should be ignored
        "lighting": None,
        "film_stock": "Portra 400",  # this one survives
    })
    assert "Portra 400" in prompt
    assert "35" not in prompt


def test_synthesize_prompt_ignores_whitespace_only():
    prompt = corpus_reverse.synthesize_prompt({
        "lens": "   ",
        "film_stock": "Portra 400",
    })
    assert "Portra 400" in prompt


def test_synthesize_prompt_handles_non_dict():
    assert corpus_reverse.synthesize_prompt("not a dict") == ""  # type: ignore[arg-type]


def test_subject_and_location_come_first():
    patterns = {
        "subject": "a trader",
        "lens": "35mm",
        "location_type": "kitchen",
    }
    prompt = corpus_reverse.synthesize_prompt(patterns)
    assert prompt.find("a trader") < prompt.find("35mm")
    assert prompt.find("kitchen") < prompt.find("35mm")
