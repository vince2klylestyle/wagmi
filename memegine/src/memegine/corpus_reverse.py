"""Corpus reverse — Claude vision extracts craft tokens from every ref.

Given a set of reference images, calls Claude vision on each to
identify:
- lens + aperture (e.g., "35mm f/1.4")
- film stock or sensor look (e.g., "Cinestill 800T")
- lighting setup (e.g., "hard window light, 3:1 ratio")
- time of day / weather
- composition rule
- camera move (for video frames)
- subject + wardrobe

The result is stored on the ref's `extracted_patterns` field (new
field added here) so the corpus_distill module can aggregate across
the whole library later.

Requires ANTHROPIC_API_KEY. Costs ~$0.003 per ref via Sonnet vision.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
from pathlib import Path

from . import reference_lib
from .config import settings


REVERSE_SYSTEM = """You are a craft-extraction assistant. Given a
single reference photograph or video frame, identify the named craft
tokens that reproduce its look. You are NOT describing the image — you
are pulling out the ingredients a reproduction prompt would need.

Return ONLY JSON in this exact shape:

{
  "lens": "<focal length + aperture, e.g. '35mm f/1.4' — empty string if indeterminate>",
  "film_stock": "<named film stock or sensor look, e.g. 'Cinestill 800T', 'Kodak Portra 400', 'digital clean'>",
  "lighting": "<named setup + ratio, e.g. 'hard window light, 3:1 ratio'>",
  "time_of_day": "<e.g. '3am', 'dusk', 'overcast noon', 'golden hour'>",
  "weather": "<e.g. 'clear', 'overcast', 'heavy rain', 'fog'>",
  "composition": "<named rule, e.g. 'rule of thirds, subject left', 'centered medium close-up'>",
  "color_palette": "<short descriptor, e.g. 'cold blue + warm practicals', 'teal-orange'>",
  "mood": "<one-word: cope / defeat / dread / contempt / etc.>",
  "subject": "<concrete noun phrase, e.g. 'trader at laptop, hoodie'>",
  "location_type": "<e.g. 'kitchen at night', 'subway platform', 'rooftop'>",
  "notes": "<one sentence: what makes this image land>"
}

Use empty strings for fields you genuinely can't identify. Do not
guess. The goal is to produce tokens that a future brief can cite by
name."""


@dataclass
class ReverseResult:
    ref_id: str
    filename: str
    extracted: dict = field(default_factory=dict)
    error: str = ""


def _encode_image(path: Path) -> tuple[str, str]:
    """Return (media_type, base64_data) for Claude vision."""
    ext = path.suffix.lower()
    if ext in (".jpg", ".jpeg"):
        media_type = "image/jpeg"
    elif ext == ".png":
        media_type = "image/png"
    elif ext == ".webp":
        media_type = "image/webp"
    elif ext == ".gif":
        media_type = "image/gif"
    else:
        raise ValueError(f"unsupported image type: {ext}")
    data = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    return media_type, data


def _extract_one(ref: dict, client, model: str | None) -> ReverseResult:
    from anthropic import Anthropic  # type: ignore  # checked at caller
    result = ReverseResult(ref_id=ref.get("id", "?"), filename=ref.get("filename", ""))
    path = settings.references_dir / ref["filename"]
    if not path.exists():
        result.error = f"missing file: {path}"
        return result
    try:
        media_type, b64 = _encode_image(path)
    except Exception as exc:
        result.error = str(exc)
        return result

    try:
        response = client._client.messages.create(
            model=model or settings.utility_model,
            max_tokens=1024,
            temperature=0.2,
            system=[{"type": "text", "text": REVERSE_SYSTEM,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": media_type, "data": b64,
                    }},
                    {"type": "text", "text":
                     "Reverse-engineer the craft tokens for this reference. "
                     "Return JSON only."},
                ],
            }],
        )
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"
        return result

    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if text.startswith("```"):
        # strip code fences
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


def reverse_all(
    *,
    only_new: bool = True,
    limit: int | None = None,
    model: str | None = None,
) -> list[ReverseResult]:
    """Run Claude vision on every ref and persist extracted tokens.

    only_new: if True, skip refs that already have `extracted_patterns`.
    limit: process at most N refs (to keep costs bounded on first run).
    """
    from . import executor
    if not executor.api_key_available():
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set — corpus reverse needs it. "
            "Use `memegine corpus distill` separately if you've populated "
            "extracted_patterns manually."
        )

    client = executor.get_client()

    refs = reference_lib._load_index()
    todo: list[dict] = []
    for r in refs:
        if only_new and r.get("extracted_patterns"):
            continue
        if r.get("filename", "").lower().endswith(VIDEO_EXT_TUPLE):
            continue  # skip raw videos (they should have frames already)
        todo.append(r)
    if limit:
        todo = todo[:limit]

    results: list[ReverseResult] = []
    for r in todo:
        res = _extract_one(r, client, model)
        results.append(res)
        if res.extracted:
            # Persist extracted_patterns on the ref index entry.
            for existing in refs:
                if existing["id"] == r["id"]:
                    existing["extracted_patterns"] = res.extracted
                    break
            reference_lib._save_index(refs)
    return results


# (Paranoia — corpus already filters these, but double-check in case a
# future caller hands us raw video filenames.)
VIDEO_EXT_TUPLE = (".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv")


def summary(results: list[ReverseResult]) -> str:
    ok = sum(1 for r in results if r.extracted and not r.error)
    errored = sum(1 for r in results if r.error)
    lines = [f"=== corpus reverse — {len(results)} refs processed ==="]
    lines.append(f"  successful:  {ok}")
    lines.append(f"  errored:     {errored}")
    if errored:
        lines.append("  first 5 errors:")
        shown = 0
        for r in results:
            if r.error and shown < 5:
                lines.append(f"    - {r.ref_id}  {r.filename}: {r.error[:80]}")
                shown += 1
    return "\n".join(lines)
