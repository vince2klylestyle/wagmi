"""Tag normalizer — canonicalize tags across the reference library.

After corpus ingest from multiple sources, tags drift: "3am", "3AM",
"3-am", "three-am". A "portraits" folder ingest coexists with a
"portrait" folder ingest. "editor:alice" and "editor_alice" refer to
the same editor.

This module:
1. Lowercases everything
2. Normalizes separators (dashes → underscores)
3. Applies an operator-supplied synonym map (e.g., portraits→portrait)
4. Reports outlier tags (seen only on 1-2 refs) as cleanup candidates

Never destructive: `preview()` shows what would change; `apply()` only
mutates when called explicitly.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from . import reference_lib


DEFAULT_SYNONYMS = {
    # Folder / plural normalization
    "portraits": "portrait",
    "memes": "meme",
    "charts": "chart",
    "scenes": "scene",
    # Casing / punctuation variants operators commonly produce
    "three_am": "3am",
    "3-am": "3am",
    "midnight_oil": "3am",
}


@dataclass
class Change:
    ref_id: str
    before: list[str]
    after: list[str]


@dataclass
class NormalizeReport:
    changes: list[Change] = field(default_factory=list)
    outliers: list[tuple[str, int]] = field(default_factory=list)

    def as_text(self) -> str:
        lines = [f"=== tag normalize — {len(self.changes)} refs would change ==="]
        for c in self.changes[:20]:
            lines.append(f"  {c.ref_id}  {c.before}  →  {c.after}")
        if len(self.changes) > 20:
            lines.append(f"  (... {len(self.changes) - 20} more)")
        if self.outliers:
            lines.append("")
            lines.append("outlier tags (seen on 1-2 refs; consider removing or canonicalizing):")
            for tag, n in self.outliers[:20]:
                lines.append(f"  {tag}  (×{n})")
        return "\n".join(lines)


def _normalize_one(tag: str, synonyms: dict[str, str]) -> str:
    t = tag.strip().lower()
    # Preserve explicit "editor:x" / "variant_of:xxx" prefixes.
    if ":" in t:
        prefix, rest = t.split(":", 1)
        prefix = prefix.replace("-", "_")
        rest = rest.replace(" ", "_")
        return f"{prefix}:{rest}"
    # Check synonyms BOTH pre- and post-separator normalization so a
    # synonym map can use either dashes or underscores.
    if t in synonyms:
        return synonyms[t]
    t_under = t.replace("-", "_").replace(" ", "_")
    if t_under in synonyms:
        return synonyms[t_under]
    return t_under


def _normalize_tags(tags: list[str], synonyms: dict[str, str]) -> list[str]:
    seen: list[str] = []
    for t in tags:
        n = _normalize_one(t, synonyms)
        if n and n not in seen:
            seen.append(n)
    return seen


def preview(
    *,
    synonyms: dict[str, str] | None = None,
    outlier_threshold: int = 2,
) -> NormalizeReport:
    """Compute changes without touching the index."""
    synonyms = {**DEFAULT_SYNONYMS, **(synonyms or {})}
    refs = reference_lib._load_index()
    changes: list[Change] = []
    for r in refs:
        before = list(r.get("tags", []) or [])
        after = _normalize_tags(before, synonyms)
        if before != after:
            changes.append(Change(ref_id=r["id"], before=before, after=after))

    # Find outlier tags — post-normalization count across refs.
    counts: Counter[str] = Counter()
    for r in refs:
        normalized = _normalize_tags(r.get("tags", []) or [], synonyms)
        for t in normalized:
            counts[t] += 1
    outliers = sorted(
        [(t, n) for t, n in counts.items() if n <= outlier_threshold],
        key=lambda x: (-x[1], x[0]),
    )
    return NormalizeReport(changes=changes, outliers=outliers)


def apply(
    *,
    synonyms: dict[str, str] | None = None,
) -> NormalizeReport:
    """Normalize every ref's tags. Persists the index."""
    report = preview(synonyms=synonyms)
    if not report.changes:
        return report

    all_syn = {**DEFAULT_SYNONYMS, **(synonyms or {})}
    refs = reference_lib._load_index()
    for r in refs:
        before = list(r.get("tags", []) or [])
        after = _normalize_tags(before, all_syn)
        if before != after:
            r["tags"] = after
    reference_lib._save_index(refs)
    return report
