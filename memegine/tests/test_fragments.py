from __future__ import annotations

import pytest

from memegine import fragments


def test_library_loads():
    lib = fragments.load()
    assert lib
    # Core categories we seeded.
    for cat in ("LENS", "FILM", "LIGHTING", "TIME_OF_DAY", "COMPOSITION"):
        assert cat in lib


def test_get_existing_fragment():
    body = fragments.get("LENS", "35mm_1_4")
    assert body
    assert "35mm" in body


def test_get_missing_returns_none():
    assert fragments.get("LENS", "not_a_real_one") is None
    assert fragments.get("NOPE", "x") is None


def test_expand_resolves_tokens():
    text = "Trader, LENS.35mm_1_4, TIME_OF_DAY.3am"
    out = fragments.expand(text)
    assert "35mm" in out
    assert "3am" in out
    # Token syntax should be gone.
    assert "LENS.35mm_1_4" not in out


def test_expand_keeps_unknown_by_default():
    out = fragments.expand("LENS.unknown_fragment")
    assert "LENS.unknown_fragment" in out


def test_expand_drops_unknown_when_requested():
    out = fragments.expand("Text LENS.unknown_fragment tail", missing="drop")
    assert "unknown_fragment" not in out
    # The rest of the text survives
    assert "Text" in out
    assert "tail" in out


def test_expand_errors_on_unknown_when_requested():
    with pytest.raises(KeyError):
        fragments.expand("LENS.unknown_fragment", missing="error")


def test_find_tokens():
    tokens = fragments.find_tokens("a LENS.35mm_1_4 b FILM.portra_400 c")
    assert ("LENS", "35mm_1_4") in tokens
    assert ("FILM", "portra_400") in tokens


def test_validate_returns_unknowns():
    unknown = fragments.validate("LENS.35mm_1_4 FILM.not_a_stock")
    assert ("FILM", "not_a_stock") in unknown
    assert not any(t == ("LENS", "35mm_1_4") for t in unknown)


def test_custom_library_path(tmp_path):
    custom = tmp_path / "custom.yaml"
    custom.write_text("TEST:\n  foo: bar\n")
    assert fragments.get("TEST", "foo", path=custom) == "bar"
    assert "bar" in fragments.expand("TEST.foo", path=custom)


def test_token_regex_only_matches_valid_syntax():
    # Lowercase category shouldn't match; nor snake-case-with-hyphens.
    tokens = fragments.find_tokens("lens.35mm (LENS-35)")
    assert tokens == []
