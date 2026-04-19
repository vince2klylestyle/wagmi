"""Brainstorm — Claude-powered topic → 5 spinoff intents.

Operator has a seed thought ("ETF flows got weird this week") and
wants 5 different concrete pieces that could be made off that seed,
each angled differently. Feeds the seed + codex + recent winners to
Claude, returns 5 ready-to-brief intents.

Needs ANTHROPIC_API_KEY.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from . import reference_lib, style_codex


BRAINSTORM_SYSTEM = """You are an ideation partner for a single crypto-
native operator on X. Given a seed idea, produce FIVE distinct
concrete piece ideas that could be made off that seed.

Each idea must:
- Be specific (named subject, emotion, setting). No abstractions.
- Match this project's voice: tired-coded, earned cynicism, deadpan.
- Be ONE piece (not a campaign). Executable in 30-45 minutes.
- Lean a DIFFERENT angle than the other four. Don't give five
  variations of the same shot — give five different takes (meme /
  portrait / chart / lore / reaction).

Return ONLY JSON:

{
  "spinoffs": [
    {"angle": "photoreal-portrait", "intent": "<one sentence>", "why": "<one sentence>"},
    {"angle": "meme-two-panel",   "intent": "...", "why": "..."},
    {"angle": "cope-chart",       "intent": "...", "why": "..."},
    {"angle": "reaction",         "intent": "...", "why": "..."},
    {"angle": "lore-drop",        "intent": "...", "why": "..."}
  ],
  "note": "<one sentence on which angle you'd lead with>"
}
"""


@dataclass
class BrainstormResult:
    seed: str
    spinoffs: list[dict] = field(default_factory=list)
    note: str = ""
    error: str = ""

    def as_text(self) -> str:
        if self.error:
            return f"ERROR: {self.error}"
        lines = [f"=== brainstorm — seed: {self.seed} ==="]
        if self.note:
            lines.append(f"  {self.note}")
            lines.append("")
        for i, s in enumerate(self.spinoffs, 1):
            lines.append(f"{i}. [{s.get('angle', '?')}] {s.get('intent', '')}")
            if s.get("why"):
                lines.append(f"   why: {s['why']}")
        return "\n".join(lines)


def generate(seed: str, *, model: str | None = None) -> BrainstormResult:
    from . import executor
    if not seed.strip():
        return BrainstormResult(seed=seed, error="seed is required")
    if not executor.api_key_available():
        return BrainstormResult(seed=seed, error="ANTHROPIC_API_KEY not set")

    client = executor.get_client()
    codex = style_codex.read()[:3000]
    refs = reference_lib._load_index()
    recent_winners = [
        {"prompt": (w.get("prompt") or "")[:120], "notes": w.get("notes", "")}
        for w in sorted(
            [r for r in refs if "winner" in r.get("tags", [])],
            key=lambda r: r.get("added_at", ""), reverse=True,
        )[:5]
    ]

    user_msg = (
        f"## Seed\n{seed.strip()}\n\n"
        f"## Style codex (first 3k chars)\n{codex or '(empty)'}\n\n"
        f"## Recent winners\n{json.dumps(recent_winners, ensure_ascii=False, indent=2)}\n\n"
        "## Task\nProduce 5 spinoffs per the system rules. JSON only."
    )

    try:
        data = client.complete_json(
            system=BRAINSTORM_SYSTEM, user=user_msg, model=model,
            max_tokens=1500, temperature=0.9,
        )
    except Exception as exc:
        return BrainstormResult(seed=seed, error=f"{type(exc).__name__}: {exc}")

    if not isinstance(data, dict):
        return BrainstormResult(seed=seed, error="unexpected response shape")

    return BrainstormResult(
        seed=seed,
        spinoffs=data.get("spinoffs", []) or [],
        note=data.get("note", "") or "",
    )
