"""Brand plate — per-project identity that auto-injects into every brief.

Each project can carry a `brand.yaml` at the root of its workspace:

    data/projects/<name>/brand.yaml

Fields (all optional — missing ones are skipped in the rendered plate):

    name: short display name ("$MOTION")
    tagline: one-line motto ("God forbid a white boy got motion")
    aliases: ["motion", "$MOTION", "motion team"]  # ways the brand is referred to
    palette: ["film-black", "cream-white", "ice-blue"]
    signature_moves:
      - "serif title cards over a cinematic still"
      - "vacuum-sealed cash bricks as the hero object"
    banned_words: ["cinematic", "epic", "crypto bro"]
    kill_list:
      - "any phrase that reads like a Grok system message"
    co_signers:
      - "@stayblessed"
      - "@auvirox"
    voice: "terse, observational, refuses to explain the joke"
    subject_archetypes:
      - "the trader at 3am"
      - "the cartel accountant"
    typography_registers:
      - "Blackletter headline, white-on-black"
      - "90s VHS subtitle, yellow serif"

Loaded lazily. If brand.yaml is absent, the plate is empty and the
Director falls back to universal craft rules + the codex alone.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .config import settings


@dataclass
class BrandPlate:
    name: str = ""
    tagline: str = ""
    aliases: list[str] = field(default_factory=list)
    palette: list[str] = field(default_factory=list)
    signature_moves: list[str] = field(default_factory=list)
    banned_words: list[str] = field(default_factory=list)
    kill_list: list[str] = field(default_factory=list)
    co_signers: list[str] = field(default_factory=list)
    voice: str = ""
    subject_archetypes: list[str] = field(default_factory=list)
    typography_registers: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not any([
            self.name, self.tagline, self.aliases, self.palette,
            self.signature_moves, self.banned_words, self.kill_list,
            self.co_signers, self.voice, self.subject_archetypes,
            self.typography_registers,
        ])

    def as_prompt_plate(self) -> str:
        """Render this brand as a compact markdown section for a brief.

        Returns an empty string if no fields are populated, so callers can
        always `if plate: ...` without extra checks.
        """
        if self.is_empty:
            return ""
        lines = ["## Brand plate"]
        if self.name:
            lines.append(f"name: {self.name}")
        if self.tagline:
            lines.append(f'tagline: "{self.tagline}"')
        if self.voice:
            lines.append(f"voice: {self.voice}")
        if self.palette:
            lines.append(f"palette: {', '.join(self.palette)}")
        if self.signature_moves:
            lines.append("signature moves:")
            for m in self.signature_moves:
                lines.append(f"  - {m}")
        if self.typography_registers:
            lines.append("typography registers:")
            for t in self.typography_registers:
                lines.append(f"  - {t}")
        if self.subject_archetypes:
            lines.append("subject archetypes:")
            for a in self.subject_archetypes:
                lines.append(f"  - {a}")
        if self.banned_words:
            lines.append(f"banned words: {', '.join(self.banned_words)}")
        if self.kill_list:
            lines.append("kill list:")
            for k in self.kill_list:
                lines.append(f"  - {k}")
        if self.co_signers:
            lines.append(f"co-signers: {', '.join(self.co_signers)}")
        return "\n".join(lines)

    def as_human_summary(self) -> str:
        """Human-readable print for `memegine brand show`."""
        if self.is_empty:
            return f"(no brand.yaml at {_brand_path()} — brand plate is empty)"
        parts = []
        if self.name:
            parts.append(f"# {self.name}")
        if self.tagline:
            parts.append(f'  "{self.tagline}"')
        if self.voice:
            parts.append(f"voice: {self.voice}")
        if self.signature_moves:
            parts.append("signature moves:")
            parts.extend(f"  - {m}" for m in self.signature_moves)
        if self.palette:
            parts.append(f"palette: {', '.join(self.palette)}")
        if self.banned_words:
            parts.append(f"banned words: {', '.join(self.banned_words)}")
        if self.co_signers:
            parts.append(f"co-signers: {', '.join(self.co_signers)}")
        return "\n".join(parts)


def _brand_path() -> Path:
    return settings.data_dir / "brand.yaml"


def _coerce_list(v: Any) -> list[str]:
    if not v:
        return []
    if isinstance(v, str):
        return [v]
    if isinstance(v, list):
        return [str(x) for x in v if str(x).strip()]
    return []


def load(path: Path | None = None) -> BrandPlate:
    """Load the active project's brand.yaml. Missing file = empty plate."""
    p = path or _brand_path()
    if not p.exists():
        return BrandPlate()
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError):
        return BrandPlate()
    if not isinstance(raw, dict):
        return BrandPlate()
    return BrandPlate(
        name=str(raw.get("name", "")).strip(),
        tagline=str(raw.get("tagline", "")).strip(),
        aliases=_coerce_list(raw.get("aliases")),
        palette=_coerce_list(raw.get("palette")),
        signature_moves=_coerce_list(raw.get("signature_moves")),
        banned_words=_coerce_list(raw.get("banned_words")),
        kill_list=_coerce_list(raw.get("kill_list")),
        co_signers=_coerce_list(raw.get("co_signers")),
        voice=str(raw.get("voice", "")).strip(),
        subject_archetypes=_coerce_list(raw.get("subject_archetypes")),
        typography_registers=_coerce_list(raw.get("typography_registers")),
    )


def current_plate() -> BrandPlate:
    """Load the currently-active project's brand plate (re-resolves path)."""
    return load()
