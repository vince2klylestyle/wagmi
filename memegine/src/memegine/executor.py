"""Executor — run a brief through Claude (if API key set) and parse the JSON.

The default memegine flow is offline: assemble SYSTEM+USER, print, operator
pastes into Claude Code / Claude.ai. That's the zero-cost path.

Once the operator has an ANTHROPIC_API_KEY they can run briefs directly:
intent → pipeline builds SYSTEM+USER → this module sends it to the API →
returns a `ExecutedBrief` with the parsed JSON plus usage info.

The bot uses this path: `/piece <intent>` with a live key returns the
finished Grok-ready prompt instead of a paste-able block, saving 2-3
manual steps per piece.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import archive
from .config import settings


@dataclass
class ExecutedBrief:
    kind: str                       # "prompt" | "shots" | "copy" | "variants" | "reverse"
    intent: str
    format_slug: str | None
    system: str
    user: str
    json_result: dict[str, Any] = field(default_factory=dict)
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0

    @property
    def prompt(self) -> str:
        """The Grok-ready prompt string (or empty for non-prompt briefs)."""
        return self.json_result.get("prompt", "") or self.json_result.get("still_prompt", "")

    @property
    def captions(self) -> list[dict]:
        return self.json_result.get("post_caption_ideas", []) or self.json_result.get("captions", [])

    @property
    def variants(self) -> list[str]:
        return self.json_result.get("variants_to_try", []) or self.json_result.get("variants", [])


def api_key_available() -> bool:
    """Cheap check — lets the bot skip/advise when the operator has no key."""
    return bool(settings.anthropic_api_key)


def get_client():
    """Build a ClaudeClient. Raises if anthropic SDK isn't installed or key missing."""
    try:
        from .claude_client import ClaudeClient
    except ImportError as exc:
        raise ImportError(
            "anthropic SDK not installed. Run: pip install -e '.[online]'"
        ) from exc
    return ClaudeClient()


def execute_prompt_brief(
    intent: str,
    format_slug: str,
    *,
    model: str | None = None,
    max_tokens: int = 2048,
    temperature: float = 0.8,
) -> ExecutedBrief:
    """Build the prompt brief, send to Claude, return parsed JSON."""
    from . import prompt_engine
    system, user = prompt_engine.assemble_offline_prompt(intent, format_slug)
    client = get_client()
    data = client.complete_json(
        system=system, user=user, model=model,
        max_tokens=max_tokens, temperature=temperature,
    )
    brief = ExecutedBrief(
        kind="prompt",
        intent=intent,
        format_slug=format_slug,
        system=system,
        user=user,
        json_result=data if isinstance(data, dict) else {"result": data},
        model=model or settings.ideation_model,
    )
    archive.save(
        kind="prompt_executed",
        intent=intent,
        system=system,
        user=user,
        format_=format_slug,
        extra={"json_result": brief.json_result, "model": brief.model},
    )
    return brief


def execute_shot_list(
    intent: str,
    *,
    model: str | None = None,
    max_tokens: int = 2048,
    temperature: float = 0.7,
) -> ExecutedBrief:
    from . import shot_list as shot_list_mod
    system, user = shot_list_mod.assemble_offline_shot_list_prompt(intent)
    client = get_client()
    data = client.complete_json(
        system=system, user=user, model=model,
        max_tokens=max_tokens, temperature=temperature,
    )
    brief = ExecutedBrief(
        kind="shots",
        intent=intent,
        format_slug=None,
        system=system,
        user=user,
        json_result=data if isinstance(data, dict) else {"result": data},
        model=model or settings.ideation_model,
    )
    archive.save(
        kind="shots_executed",
        intent=intent,
        system=system,
        user=user,
        extra={"json_result": brief.json_result, "model": brief.model},
    )
    return brief


def execute_copy(
    concept: str,
    asset_kind: str = "image",
    *,
    model: str | None = None,
    max_tokens: int = 1024,
    temperature: float = 0.9,
) -> ExecutedBrief:
    from . import copy_writer
    system, user = copy_writer.assemble_offline_copy_prompt(concept, asset_kind)
    client = get_client()
    data = client.complete_json(
        system=system, user=user, model=model,
        max_tokens=max_tokens, temperature=temperature,
    )
    brief = ExecutedBrief(
        kind="copy",
        intent=concept,
        format_slug=None,
        system=system,
        user=user,
        json_result=data if isinstance(data, dict) else {"result": data},
        model=model or settings.utility_model,
    )
    archive.save(
        kind="copy_executed",
        intent=concept,
        system=system,
        user=user,
        extra={"json_result": brief.json_result, "model": brief.model},
    )
    return brief


def summarize(brief: ExecutedBrief) -> str:
    """Return a compact human-readable digest of an executed brief.

    Used by the Telegram bot as the chat reply after a successful run.
    """
    lines = [f"kind={brief.kind}  model={brief.model}  format={brief.format_slug or '-'}"]
    if brief.prompt:
        lines.append("\n=== prompt (paste into Grok) ===")
        lines.append(brief.prompt)
    if brief.kind == "shots":
        shots = brief.json_result.get("shots", [])
        lines.append(f"\n=== {len(shots)} shot(s) ===")
        for s in shots:
            lines.append(
                f"[{s.get('index')}] {s.get('duration_sec', '?')}s  {s.get('camera_move', '?')}"
            )
            if s.get("still_prompt"):
                lines.append(f"  still: {s['still_prompt']}")
            if s.get("motion_prompt"):
                lines.append(f"  motion: {s['motion_prompt']}")
    if brief.captions:
        lines.append("\n=== captions ===")
        for c in brief.captions[:5]:
            if isinstance(c, dict):
                lines.append(f"- [{c.get('length', '?')}] {c.get('text', '')}")
            else:
                lines.append(f"- {c}")
    if brief.variants:
        lines.append("\n=== variants ===")
        for v in brief.variants[:6]:
            lines.append(f"- {v}")
    return "\n".join(lines)
