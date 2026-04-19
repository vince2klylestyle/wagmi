"""Inspire — photo → piece one-shot.

Given an inspiration image and a new intent, Claude vision extracts
the craft tokens from the inspiration and composes a fresh prompt that
applies those tokens to the operator's new intent.

Flow:
1. Operator: "this photo inspired me; I want to shoot a trader at 3am
   in that style."
2. `memegine inspire ref.png "trader at 3am, quiet dread"`
3. Claude vision pulls lens/film/lighting/palette off the ref.
4. Memegine composes a prompt stitching the new intent with the
   inherited craft tokens.

Requires ANTHROPIC_API_KEY (Claude vision).

Compared to `like-winner`: `like-winner` pulls from the last ref
tagged as a winner; `inspire` works from any arbitrary image the
operator points at (e.g., a photo they saved from somewhere else).
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
from pathlib import Path

from . import deep_linter


EXTRACT_SYSTEM = """You are a craft-extraction assistant. Given a
single reference photograph, identify the named craft tokens a
reproduction prompt would need: lens + aperture, film stock / sensor
look, lighting setup with ratio, time of day, composition rule, color
palette, mood.

Return ONLY JSON:

{
  "lens": "<focal length + aperture, e.g. '35mm f/1.4' or empty string>",
  "film_stock": "<named stock or sensor look or empty>",
  "lighting": "<named setup + ratio or empty>",
  "time_of_day": "<e.g. '3am', 'dusk' or empty>",
  "composition": "<named rule or empty>",
  "color_palette": "<short descriptor or empty>",
  "mood": "<one-word descriptor or empty>"
}

Use empty strings for fields you genuinely can't identify."""


@dataclass
class InspireResult:
    source_path: str
    new_intent: str
    extracted: dict = field(default_factory=dict)
    prompt: str = ""
    craft_score: int = 0
    craft_grade: str = ""
    error: str = ""

    def as_text(self) -> str:
        if self.error:
            return f"ERROR: {self.error}"
        lines = [
            f"=== inspire — from {self.source_path} ===",
            f"new intent: {self.new_intent}",
            "",
            "extracted craft:",
        ]
        for k, v in self.extracted.items():
            if v:
                lines.append(f"  {k}: {v}")
        lines += ["", f"craft score: {self.craft_score}/100  grade {self.craft_grade}", ""]
        lines.append("=== prompt (paste into Grok) ===")
        lines.append(self.prompt)
        return "\n".join(lines)


def _encode(path: Path) -> tuple[str, str]:
    ext = path.suffix.lower()
    media_type = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif",
    }.get(ext)
    if not media_type:
        raise ValueError(f"unsupported image type: {ext}")
    data = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    return media_type, data


def run(image_path: Path | str, new_intent: str, *, model: str | None = None) -> InspireResult:
    from . import executor
    image_path = Path(image_path)
    result = InspireResult(source_path=str(image_path), new_intent=new_intent)

    if not image_path.exists():
        result.error = f"image not found: {image_path}"
        return result
    if not new_intent.strip():
        result.error = "intent is required"
        return result
    if not executor.api_key_available():
        result.error = "ANTHROPIC_API_KEY not set"
        return result

    client = executor.get_client()
    try:
        media_type, b64 = _encode(image_path)
    except Exception as exc:
        result.error = str(exc)
        return result

    try:
        response = client._client.messages.create(
            model=model or "claude-sonnet-4-6",
            max_tokens=800,
            temperature=0.2,
            system=[{"type": "text", "text": EXTRACT_SYSTEM,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": media_type, "data": b64,
                    }},
                    {"type": "text", "text":
                     "Extract the craft tokens from this image. JSON only."},
                ],
            }],
        )
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"
        return result

    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip().rstrip("```").strip()
    try:
        import json
        result.extracted = json.loads(text)
    except Exception as exc:
        result.error = f"parse: {exc}  raw: {text[:200]}"
        return result

    # Compose: new_intent first, then inherited craft tokens, then negatives.
    parts: list[str] = [new_intent.strip().rstrip(" .,")]
    for key in ("lens", "film_stock", "lighting", "time_of_day",
                "composition", "color_palette", "mood"):
        v = result.extracted.get(key, "")
        if isinstance(v, str) and v.strip():
            parts.append(v.strip())
    parts.append(
        "no extra fingers, no warped text, no logo watermarks, "
        "no lens flares unless specified, no CGI look"
    )
    result.prompt = ", ".join(parts)

    score = deep_linter.score(result.prompt)
    result.craft_score = score.score
    result.craft_grade = deep_linter.grade(score.score)

    return result
