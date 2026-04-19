"""Corpus distill — aggregate reverse-extracted tokens into the codex.

After `corpus ingest` + `corpus reverse`, every ref has an
`extracted_patterns` dict with named craft tokens. This module walks
all refs, tallies the tokens, and writes the dominant patterns to the
codex as:
- "Visual DNA" entries (the defaults this project uses)
- "Core Patterns" entries (the tokens that appear in 5+ refs)

The result: a brand-new codex populated automatically from the
operator's confirmed-good archive. Week-1 briefs get the compounding
that would normally take 10 weeks of manual curation.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from . import reference_lib, style_codex


FIELDS = (
    "lens", "film_stock", "lighting", "time_of_day", "weather",
    "composition", "color_palette", "mood", "location_type",
)


@dataclass
class DistillReport:
    total_refs: int = 0
    refs_with_patterns: int = 0
    frequencies: dict[str, list[tuple[str, int]]] = field(default_factory=dict)
    promoted_to_visual_dna: list[str] = field(default_factory=list)
    promoted_to_core: list[str] = field(default_factory=list)

    def as_text(self) -> str:
        lines = [
            f"=== corpus distill — {self.refs_with_patterns}/{self.total_refs} refs "
            "with extracted patterns ===",
        ]
        for field_name in FIELDS:
            items = self.frequencies.get(field_name, [])
            if not items:
                continue
            top = ", ".join(f"{v}×{c}" for v, c in items[:5])
            lines.append(f"  {field_name:<16} {top}")
        if self.promoted_to_visual_dna:
            lines.append("")
            lines.append("Visual DNA written:")
            for e in self.promoted_to_visual_dna:
                lines.append(f"  - {e}")
        if self.promoted_to_core:
            lines.append("")
            lines.append("Core Patterns written:")
            for e in self.promoted_to_core:
                lines.append(f"  - {e}")
        return "\n".join(lines)


def _tally(refs: list[dict]) -> tuple[int, dict[str, list[tuple[str, int]]]]:
    """For each craft field, return a frequency-sorted list of values."""
    counts: dict[str, Counter] = {f: Counter() for f in FIELDS}
    with_patterns = 0
    for r in refs:
        patterns = r.get("extracted_patterns")
        if not patterns:
            continue
        with_patterns += 1
        for f in FIELDS:
            v = patterns.get(f, "")
            if not isinstance(v, str):
                continue
            v = v.strip().lower()
            if v and v not in ("none", "n/a", "unknown"):
                counts[f][v] += 1
    freq: dict[str, list[tuple[str, int]]] = {}
    for f, ctr in counts.items():
        freq[f] = ctr.most_common()
    return with_patterns, freq


def distill(
    *,
    dna_min_share: float = 0.3,
    core_min_count: int = 5,
    dry_run: bool = False,
) -> DistillReport:
    """Walk refs, tally extracted_patterns, write to codex.

    dna_min_share: a value appears in "Visual DNA" if it's seen in at
    least this fraction of the refs-with-patterns (0.3 = 30%+).
    core_min_count: a value appears in "Core Patterns" if seen in at
    least N refs absolutely (default 5).
    dry_run: compute the report but don't write to the codex.
    """
    refs = reference_lib._load_index()
    with_patterns, freq = _tally(refs)
    report = DistillReport(
        total_refs=len(refs),
        refs_with_patterns=with_patterns,
        frequencies=freq,
    )
    if with_patterns == 0:
        return report

    dna_threshold = max(2, int(with_patterns * dna_min_share))
    visual_dna_entries: list[str] = []
    core_entries: list[str] = []

    for f in FIELDS:
        items = freq.get(f, [])
        if not items:
            continue
        top_value, top_count = items[0]
        # Visual DNA = the dominant value, if dominance is strong enough.
        if top_count >= dna_threshold:
            visual_dna_entries.append(
                f"{f}: {top_value} (dominant, {top_count}/{with_patterns} refs)"
            )
        # Core Patterns = every value seen >= core_min_count times.
        for v, c in items:
            if c >= core_min_count:
                core_entries.append(f"{f}: {v} (×{c})")

    report.promoted_to_visual_dna = visual_dna_entries
    report.promoted_to_core = core_entries

    if not dry_run:
        for entry in visual_dna_entries:
            style_codex.append_entry("Visual DNA", entry)
        for entry in core_entries:
            style_codex.append_entry("Core Patterns", entry)

    return report


def corpus_stats() -> dict:
    """Return a lightweight stats dict summarizing the corpus."""
    refs = reference_lib._load_index()
    with_patterns, freq = _tally(refs)
    out: dict = {
        "total_refs": len(refs),
        "refs_with_patterns": with_patterns,
        "winners": sum(1 for r in refs if "winner" in r.get("tags", [])),
        "video_frames": sum(1 for r in refs if any(t.startswith("video:") for t in r.get("tags", []))),
        "top_tags": Counter(
            t for r in refs for t in r.get("tags", [])
        ).most_common(10),
    }
    for f in FIELDS:
        items = freq.get(f, [])
        if items:
            out[f"top_{f}"] = items[:5]
    return out


def stats_text() -> str:
    stats = corpus_stats()
    lines = [
        f"=== corpus — {stats['total_refs']} refs ===",
        f"  winners:              {stats['winners']}",
        f"  video frames:         {stats['video_frames']}",
        f"  with extracted data:  {stats['refs_with_patterns']}",
    ]
    if stats.get("top_tags"):
        lines.append("  top tags:")
        for tag, n in stats["top_tags"]:
            lines.append(f"    {tag:<20} {n}")
    for f in FIELDS:
        key = f"top_{f}"
        if key not in stats:
            continue
        top = ", ".join(f"{v} ({c})" for v, c in stats[key])
        lines.append(f"  top {f}: {top}")
    return "\n".join(lines)
