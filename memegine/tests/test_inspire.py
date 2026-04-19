from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from memegine import inspire


def _make_png(path: Path):
    from PIL import Image
    Image.new("RGB", (128, 128), color=(80, 40, 20)).save(path, "PNG")


def test_missing_image_returns_error(tmp_path):
    r = inspire.run(tmp_path / "nope.png", "intent")
    assert r.error
    assert "not found" in r.error


def test_empty_intent_returns_error(tmp_path):
    p = tmp_path / "x.png"
    _make_png(p)
    r = inspire.run(p, "")
    assert r.error


def test_no_api_key_returns_error(tmp_path, monkeypatch):
    from memegine.config import settings
    monkeypatch.setattr(settings, "anthropic_api_key", "", raising=False)
    p = tmp_path / "x.png"
    _make_png(p)
    r = inspire.run(p, "trader at 3am")
    assert r.error
    assert "API" in r.error.upper() or "ANTHROPIC" in r.error


def test_composes_prompt_from_mocked_extraction(tmp_path, monkeypatch):
    from memegine.config import settings
    from memegine import executor
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-fake", raising=False)

    # Mock the Anthropic client's raw messages.create response shape.
    class _TextBlock:
        def __init__(self, text):
            self.text = text
            self.type = "text"

    class _Resp:
        def __init__(self, text):
            self.content = [_TextBlock(text)]

    fake_client = MagicMock()
    fake_client._client.messages.create.return_value = _Resp(
        '{"lens":"35mm f/1.4","film_stock":"Cinestill 800T",'
        '"lighting":"hard window light","time_of_day":"3am",'
        '"composition":"rule of thirds","color_palette":"cold blue + warm practicals",'
        '"mood":"quiet dread"}'
    )
    monkeypatch.setattr(executor, "get_client", lambda: fake_client)

    p = tmp_path / "x.png"
    _make_png(p)
    result = inspire.run(p, "CEO on a rooftop")

    assert not result.error
    assert "CEO on a rooftop" in result.prompt
    # All extracted tokens should be in the prompt.
    assert "35mm" in result.prompt
    assert "Cinestill 800T" in result.prompt
    assert "hard window light" in result.prompt
    assert "3am" in result.prompt
    # Always includes the photoreal-negative clause.
    assert "no extra fingers" in result.prompt


def test_handles_json_in_code_fences(tmp_path, monkeypatch):
    from memegine.config import settings
    from memegine import executor
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-fake", raising=False)

    class _TextBlock:
        text = '```json\n{"lens":"35mm"}\n```'
        type = "text"

    class _Resp:
        content = [_TextBlock()]

    fake_client = MagicMock()
    fake_client._client.messages.create.return_value = _Resp()
    monkeypatch.setattr(executor, "get_client", lambda: fake_client)

    p = tmp_path / "x.png"
    _make_png(p)
    result = inspire.run(p, "trader")
    assert not result.error
    assert "35mm" in result.prompt


def test_parse_error_on_garbage_response(tmp_path, monkeypatch):
    from memegine.config import settings
    from memegine import executor
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-fake", raising=False)

    class _TextBlock:
        text = "totally not json"
        type = "text"

    class _Resp:
        content = [_TextBlock()]

    fake_client = MagicMock()
    fake_client._client.messages.create.return_value = _Resp()
    monkeypatch.setattr(executor, "get_client", lambda: fake_client)

    p = tmp_path / "x.png"
    _make_png(p)
    result = inspire.run(p, "trader")
    assert result.error
    assert "parse" in result.error.lower()


def test_unsupported_image_type_errors(tmp_path):
    p = tmp_path / "x.svg"
    p.write_text("<svg></svg>", encoding="utf-8")
    r = inspire.run(p, "trader")
    assert r.error
