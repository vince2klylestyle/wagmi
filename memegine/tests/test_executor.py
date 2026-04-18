"""Executor tests — no real API calls; stub ClaudeClient via monkeypatch."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from memegine import executor


def test_api_key_available_false_when_unset(monkeypatch):
    from memegine.config import settings
    monkeypatch.setattr(settings, "anthropic_api_key", "", raising=False)
    assert executor.api_key_available() is False


def test_api_key_available_true_when_set(monkeypatch):
    from memegine.config import settings
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-fake", raising=False)
    assert executor.api_key_available() is True


def test_execute_prompt_brief_returns_parsed(monkeypatch):
    fake_client = MagicMock()
    fake_client.complete_json.return_value = {
        "format_slug": "photoreal_portrait",
        "model_route": "aurora",
        "prompt": "Trader, 35mm, Portra 400, dusk, rule of thirds, no extra fingers",
        "variants_to_try": ["variant A", "variant B"],
        "rationale": "because",
        "post_caption_ideas": [
            {"length": "short", "text": "3am"},
            {"length": "medium", "text": "kitchen, no one home"},
        ],
    }
    monkeypatch.setattr(executor, "get_client", lambda: fake_client)

    brief = executor.execute_prompt_brief("trader at 3am", "photoreal_portrait")
    assert brief.kind == "prompt"
    assert brief.format_slug == "photoreal_portrait"
    assert brief.prompt.startswith("Trader")
    assert len(brief.variants) == 2
    assert len(brief.captions) == 2


def test_summarize_formats_shots(monkeypatch):
    fake_client = MagicMock()
    fake_client.complete_json.return_value = {
        "total_duration_sec": 6,
        "shots": [
            {
                "index": 1, "scene": "s1", "camera_move": "push-in",
                "duration_sec": 3, "still_prompt": "still1", "motion_prompt": "motion1",
            },
            {
                "index": 2, "scene": "s2", "camera_move": "lockoff",
                "duration_sec": 3, "still_prompt": "still2", "motion_prompt": "motion2",
            },
        ],
        "x_caption_ideas": ["cap1", "cap2"],
    }
    monkeypatch.setattr(executor, "get_client", lambda: fake_client)

    brief = executor.execute_shot_list("trader")
    text = executor.summarize(brief)
    assert "2 shot(s)" in text
    assert "still1" in text
    assert "motion2" in text


def test_summarize_handles_missing_fields(monkeypatch):
    fake_client = MagicMock()
    fake_client.complete_json.return_value = {}
    monkeypatch.setattr(executor, "get_client", lambda: fake_client)

    brief = executor.execute_prompt_brief("x", "photoreal_portrait")
    text = executor.summarize(brief)
    assert "kind=prompt" in text


def test_execute_copy_returns_captions(monkeypatch):
    fake_client = MagicMock()
    fake_client.complete_json.return_value = {
        "captions": [
            {"length": "short", "text": "3am"},
            {"length": "medium", "text": "kitchen light and a hoodie"},
        ],
        "alt_text": "portrait of trader",
    }
    monkeypatch.setattr(executor, "get_client", lambda: fake_client)

    brief = executor.execute_copy("trader at 3am", "image")
    assert brief.kind == "copy"
    assert len(brief.captions) == 2
