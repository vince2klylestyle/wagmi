from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from memegine import brainstorm


def test_empty_seed_returns_error():
    r = brainstorm.generate("")
    assert r.error


def test_no_api_key_returns_error(monkeypatch):
    from memegine.config import settings
    monkeypatch.setattr(settings, "anthropic_api_key", "", raising=False)
    r = brainstorm.generate("x")
    assert r.error


def test_generates_with_mocked_client(monkeypatch, tmp_path):
    from memegine import executor, style_codex
    from memegine.config import settings
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-fake", raising=False)
    monkeypatch.setattr(settings, "codex_path", tmp_path / "style.md", raising=False)
    monkeypatch.setattr(settings, "references_dir", tmp_path / "refs", raising=False)
    (tmp_path / "refs").mkdir()
    style_codex.init_template()

    fake_client = MagicMock()
    fake_client.complete_json.return_value = {
        "spinoffs": [
            {"angle": "photoreal-portrait", "intent": "trader at 3am", "why": "reactive"},
            {"angle": "meme-two-panel",   "intent": "etf flows meme", "why": "topical"},
            {"angle": "cope-chart",       "intent": "absurd ETH chart", "why": "joke"},
            {"angle": "reaction",         "intent": "wojak row", "why": "volume"},
            {"angle": "lore-drop",        "intent": "cryptic alley shot", "why": "mood"},
        ],
        "note": "lead with the photoreal — it compounds the character arc",
    }
    monkeypatch.setattr(executor, "get_client", lambda: fake_client)

    result = brainstorm.generate("etf flows weird this week")
    assert not result.error
    assert len(result.spinoffs) == 5
    assert result.note


def test_exception_handled(monkeypatch, tmp_path):
    from memegine import executor, style_codex
    from memegine.config import settings
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-fake", raising=False)
    monkeypatch.setattr(settings, "codex_path", tmp_path / "style.md", raising=False)
    monkeypatch.setattr(settings, "references_dir", tmp_path / "refs", raising=False)
    (tmp_path / "refs").mkdir()

    fake_client = MagicMock()
    fake_client.complete_json.side_effect = RuntimeError("boom")
    monkeypatch.setattr(executor, "get_client", lambda: fake_client)

    r = brainstorm.generate("x")
    assert r.error
    assert "boom" in r.error


def test_as_text_lists_spinoffs():
    r = brainstorm.BrainstormResult(
        seed="x",
        spinoffs=[
            {"angle": "a", "intent": "one", "why": "because"},
            {"angle": "b", "intent": "two", "why": ""},
        ],
        note="lead with one",
    )
    text = r.as_text()
    assert "seed: x" in text
    assert "one" in text
    assert "lead with one" in text
