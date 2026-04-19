"""Corpus find — targeted search across refs with craft-aware ranking.

The existing `search` module does substring match across briefs / refs /
posts / codex / topics. This module is narrower + smarter: it only
searches refs, but it understands the extracted_patterns fields and
ranks by how many hit.

Call it when the operator asks "show me refs where the lighting was
window light", "show me all the 3am kitchen ones", "where did we use
Cinestill 800T".
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import reference_lib
from .corpus_distill import FIELDS


@dataclass
class FindHit:
    ref_id: str
    filename: str
    score: int
    matched_fields: list[str] = field(default_factory=list)
    prompt: str = ""
    notes: str = ""
    tags: list[str] = field(default_factory=list)


def _score_ref(ref: dict, terms: list[str]) -> tuple[int, list[str]]:
    """Score a ref against lowercase search terms.

    Each term scores +3 if it matches an extracted_patterns field
    (high-signal craft match), +2 for tags match, +1 for notes/prompt
    match. Returns (total_score, list of matched field names).
    """
    score = 0
    matched: list[str] = []
    patterns = ref.get("extracted_patterns") or {}
    if not isinstance(patterns, dict):
        patterns = {}

    for term in terms:
        for f in FIELDS:
            v = patterns.get(f, "")
            if isinstance(v, str) and term in v.lower():
                score += 3
                if f not in matched:
                    matched.append(f)

        tag_text = " ".join(ref.get("tags", []) or []).lower()
        if term in tag_text:
            score += 2
            if "tags" not in matched:
                matched.append("tags")

        notes_text = (ref.get("notes", "") or "").lower()
        prompt_text = (ref.get("prompt", "") or "").lower()
        if term in notes_text:
            score += 1
            if "notes" not in matched:
                matched.append("notes")
        if term in prompt_text:
            score += 1
            if "prompt" not in matched:
                matched.append("prompt")
    return score, matched


def find(
    query: str,
    *,
    limit: int = 20,
    winners_only: bool = False,
) -> list[FindHit]:
    """Return refs ranked by relevance to the query.

    Query is split on whitespace; each token is matched independently
    and scores sum. A ref needs at least one matched term to appear.
    """
    terms = [t.strip().lower() for t in query.split() if t.strip()]
    if not terms:
        return []

    refs = reference_lib._load_index()
    hits: list[FindHit] = []
    for ref in refs:
        if winners_only and "winner" not in ref.get("tags", []):
            continue
        score, matched = _score_ref(ref, terms)
        if score <= 0:
            continue
        hits.append(FindHit(
            ref_id=ref.get("id", ""),
            filename=ref.get("filename", ""),
            score=score,
            matched_fields=matched,
            prompt=(ref.get("prompt", "") or "")[:120],
            notes=ref.get("notes", "") or "",
            tags=ref.get("tags", []) or [],
        ))

    hits.sort(key=lambda h: -h.score)
    return hits[:limit]


def find_text(query: str, *, limit: int = 20, winners_only: bool = False) -> str:
    hits = find(query, limit=limit, winners_only=winners_only)
    if not hits:
        return f"no refs matched '{query}'"
    lines = [f"=== corpus find — '{query}' — {len(hits)} hits ==="]
    for h in hits:
        fields = ",".join(h.matched_fields)
        tags_preview = ",".join(h.tags[:4])
        lines.append(
            f"  [{h.score}] {h.ref_id}  {h.filename}  "
            f"matched:{fields}  tags:[{tags_preview}]"
        )
        summary = h.notes or h.prompt
        if summary:
            lines.append(f"       {summary[:80]}")
    return "\n".join(lines)
