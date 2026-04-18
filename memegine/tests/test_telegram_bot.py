"""Telegram bot tests — import-only, no real bot / no network.

These tests verify:
- The module imports without python-telegram-bot installed
- _chunks() splits long messages correctly
- _parse_prompt_with_format() handles the tiny on-phone syntax

We don't unit-test individual command handlers here because they require
python-telegram-bot's Update/Context machinery. Instead, an integration
test (run manually against a real bot token) is the way to verify those.
"""
from __future__ import annotations

from memegine import telegram_bot


def test_parse_prompt_with_format_no_slug():
    intent, slug = telegram_bot._parse_prompt_with_format("trader at 3am")
    assert intent == "trader at 3am"
    assert slug is None


def test_parse_prompt_with_format_with_slug():
    intent, slug = telegram_bot._parse_prompt_with_format("trader at 3am f:photoreal_portrait")
    assert intent == "trader at 3am"
    assert slug == "photoreal_portrait"


def test_parse_prompt_with_format_empty():
    intent, slug = telegram_bot._parse_prompt_with_format("")
    assert intent == ""
    assert slug is None


def test_parse_prompt_with_format_multiword_slug_takes_first_token():
    intent, slug = telegram_bot._parse_prompt_with_format("x y z f:reaction_shot_meme tail")
    assert intent == "x y z"
    assert slug == "reaction_shot_meme"


def test_chunks_short_text_returns_single():
    chunks = telegram_bot._chunks("hello world")
    assert chunks == ["hello world"]


def test_chunks_long_text_splits():
    long = "abc\n" * 2000  # roughly 8000 chars
    chunks = telegram_bot._chunks(long)
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c) <= telegram_bot.MAX_TELEGRAM_MSG
    # Rejoin preserves content (modulo leading newline stripping).
    rejoined = "\n".join(chunks)
    assert rejoined.replace("\n", "") == long.replace("\n", "")


def test_session_is_per_user():
    s1 = telegram_bot._session(1)
    s2 = telegram_bot._session(2)
    s1.pending_photo_action = "reverse"
    s1.pending_context = "note"
    assert s2.pending_photo_action == ""
    assert telegram_bot._session(1).pending_photo_action == "reverse"


def test_bot_config_from_env_missing(monkeypatch):
    monkeypatch.delenv("MEMEGINE_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("MEMEGINE_TELEGRAM_ALLOWED_USER_IDS", raising=False)
    cfg = telegram_bot.BotConfig.from_env()
    assert cfg.token == ""
    assert cfg.allowed_user_ids == set()


def test_bot_config_from_env_parses_allowlist(monkeypatch):
    monkeypatch.setenv("MEMEGINE_TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("MEMEGINE_TELEGRAM_ALLOWED_USER_IDS", "123, 456,789")
    cfg = telegram_bot.BotConfig.from_env()
    assert cfg.token == "fake-token"
    assert cfg.allowed_user_ids == {123, 456, 789}


def test_bot_config_from_env_negative_chat_id(monkeypatch):
    monkeypatch.setenv("MEMEGINE_TELEGRAM_CHAT_ID", "-1001234567890")
    cfg = telegram_bot.BotConfig.from_env()
    assert cfg.chat_id_for_scheduler == -1001234567890
