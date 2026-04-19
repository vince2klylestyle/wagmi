"""Fragments — named reusable craft snippets.

Operator writes `LIGHTING.harsh_window` anywhere in a brief and memegine
expands it to the fragment body. This is the fastest compounding loop:
once a snippet consistently produces good Grok output, it's added to
the library and referenced by code forever. No re-typing. No drift.

Storage: `data/fragments/library.yaml` (checked in — it's part of the
style compound). Operator can add new fragments any time; next `memegine
expand ...` call picks them up.

Lookup is token-level, so a prompt can intermix fragments and plain text:

    "Trader, LENS.35mm_1_4, FILM.cinestill_800t, LIGHTING.harsh_window,
     TIME_OF_DAY.3am, COMPOSITION.thirds_left, NEGATIVE.photoreal_defaults"

Expands to a fully fleshed-out prompt ready for Grok.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import yaml

from .config import settings


# Token syntax: CATEGORY.fragment_name (category all-caps, name lowercase).
FRAGMENT_RE = re.compile(r"\b([A-Z][A-Z_]+)\.([a-z0-9_]+)\b")


def _library_path() -> Path:
    return settings.data_dir / "fragments" / "library.yaml"


def load(path: Path | None = None) -> dict[str, dict[str, str]]:
    """Return {CATEGORY: {name: body, ...}, ...} from the library."""
    p = path or _library_path()
    if not p.exists():
        return {}
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    # Normalize: ensure every value is a plain str.
    out: dict[str, dict[str, str]] = {}
    for cat, items in raw.items():
        if not isinstance(items, dict):
            continue
        out[str(cat)] = {
            str(name): str(body).strip() for name, body in items.items()
        }
    return out


def list_categories(path: Path | None = None) -> list[str]:
    return sorted(load(path).keys())


def list_names(category: str, path: Path | None = None) -> list[str]:
    lib = load(path)
    return sorted(lib.get(category, {}).keys())


def get(category: str, name: str, path: Path | None = None) -> str | None:
    return load(path).get(category, {}).get(name)


def expand(text: str, *, path: Path | None = None, missing: str = "keep") -> str:
    """Replace every CATEGORY.name token in `text` with its fragment body.

    missing:
      - "keep" (default): unknown tokens stay as-is
      - "drop": unknown tokens are removed
      - "error": raise KeyError on the first unknown token
    """
    lib = load(path)

    def _repl(m: re.Match) -> str:
        cat, name = m.group(1), m.group(2)
        body = lib.get(cat, {}).get(name)
        if body is None:
            if missing == "error":
                raise KeyError(f"{cat}.{name}")
            if missing == "drop":
                return ""
            return m.group(0)
        return body

    return FRAGMENT_RE.sub(_repl, text)


def find_tokens(text: str) -> list[tuple[str, str]]:
    """Return every CATEGORY.name token present in the text."""
    return [(m.group(1), m.group(2)) for m in FRAGMENT_RE.finditer(text)]


def validate(text: str, *, path: Path | None = None) -> list[tuple[str, str]]:
    """Return the list of unknown fragment tokens referenced in `text`."""
    lib = load(path)
    unknown = []
    for cat, name in find_tokens(text):
        if lib.get(cat, {}).get(name) is None:
            unknown.append((cat, name))
    return unknown


def merge_into_codex_note() -> str:
    """Return a short summary usable as a codex 'available fragments' reminder."""
    lib = load()
    lines = []
    for cat in sorted(lib):
        names = sorted(lib[cat].keys())
        lines.append(f"- {cat}: {', '.join(names)}")
    return "\n".join(lines)
