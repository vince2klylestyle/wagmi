from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from memegine import batch, batch_exec, executor


@pytest.fixture
def mock_api(monkeypatch, tmp_path):
    """Pretend the API key is set, stub ClaudeClient.complete_json."""
    from memegine.config import settings
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test", raising=False)
    monkeypatch.setattr(settings, "outputs_dir", tmp_path / "outputs", raising=False)

    calls = {"count": 0}
    fake_client = MagicMock()

    def fake_complete_json(**kw):
        calls["count"] += 1
        idx = calls["count"]
        return {
            "format_slug": f"format_{idx}",
            "prompt": (
                f"piece {idx}, shot on 35mm f/1.4, Portra 400, window light, "
                f"dusk, rule of thirds, no extra fingers, no warped text"
            ),
            "variants_to_try": [f"variant {idx}-a", f"variant {idx}-b"],
            "post_caption_ideas": [{"length": "short", "text": "caption " + str(idx)}],
        }
    fake_client.complete_json.side_effect = fake_complete_json
    monkeypatch.setattr(executor, "get_client", lambda: fake_client)
    yield tmp_path


def test_execute_requires_api_key(monkeypatch):
    from memegine.config import settings
    monkeypatch.setattr(settings, "anthropic_api_key", "", raising=False)
    with pytest.raises(RuntimeError):
        batch_exec.execute(theme="x", n=2)


def test_execute_runs_every_item(mock_api):
    result = batch_exec.execute(theme="my theme", n=3)
    assert len(result.items) == 3
    for item in result.items:
        assert item.prompt  # every brief executed
        assert item.score > 0
        assert item.lint_ok


def test_execute_picks_best_by_score(mock_api):
    result = batch_exec.execute(theme="x", n=2)
    best = result.best_item()
    assert best is not None
    # All items have the same score in mock, so any is fine — just non-None.


def test_execute_handles_per_item_errors(mock_api, monkeypatch):
    # Make one call fail, one succeed.
    calls = {"count": 0}
    def flaky(**kw):
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("claude boom")
        return {
            "prompt": "Trader, 35mm f/1.4, Portra 400, window light, dusk, "
                      "rule of thirds, no extra fingers, no warped text",
        }
    from memegine import executor
    client = executor.get_client()
    client.complete_json.side_effect = flaky

    result = batch_exec.execute(theme="x", n=3)
    errors = [i for i in result.items if i.error]
    assert len(errors) == 1
    assert "claude boom" in errors[0].error
    # Other 2 succeeded.
    assert len([i for i in result.items if i.prompt]) == 2


def test_execute_writes_execution_json(mock_api):
    result = batch_exec.execute(theme="x", n=2)
    folder = Path(result.folder)
    assert (folder / "execution.json").exists()
    # Per-item JSONs exist too:
    executed_dir = folder / "executed"
    per_item_files = list(executed_dir.glob("*.json"))
    assert len(per_item_files) == 2


def test_summary_text_flags_winner(mock_api):
    result = batch_exec.execute(theme="x", n=2)
    text = batch_exec.summary_text(result)
    assert "batch execution" in text
    # The winner line is included:
    assert "winner:" in text.lower()
