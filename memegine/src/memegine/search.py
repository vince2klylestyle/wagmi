"""Unified search — one query across every memegine store.

Answers "when did I brief this?" "which winner was about X?" in one
command instead of four. Returns structured hits so CLI and bot can
render the same results.

Scope:
- brief archive: intent + user-message substring
- refs: notes + prompt + tags substring
- posts: caption substring
- codex entries: bullet body substring
- topic queue: topic text substring
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import archive, codex_audit, export as export_mod, reference_lib, style_codex, topics


@dataclass
class SearchHit:
    store: str                    # "brief" | "ref" | "post" | "codex" | "topic"
    id: str
    at: str                       # ISO timestamp when available
    summary: str

    def as_line(self) -> str:
        stamp = (self.at or "-")[:19].replace("T", " ")
        return f"{stamp}  [{self.store:<7}]  {self.summary[:120]}"


@dataclass
class SearchResult:
    query: str
    hits: list[SearchHit] = field(default_factory=list)

    def as_text(self) -> str:
        if not self.hits:
            return f"no hits for '{self.query}'"
        lines = [f"=== search '{self.query}' — {len(self.hits)} hits ==="]
        for h in self.hits:
            lines.append(h.as_line())
        return "\n".join(lines)


def _substring_hit(needle: str, *haystacks: str) -> bool:
    low = needle.lower()
    return any(h and low in h.lower() for h in haystacks)


def run(query: str, *, stores: list[str] | None = None, limit: int = 50) -> SearchResult:
    """Search `query` across all stores. stores filters which to search."""
    query = query.strip()
    if not query:
        return SearchResult(query=query)
    stores = stores or ["brief", "ref", "post", "codex", "topic"]
    hits: list[SearchHit] = []

    if "brief" in stores:
        for rec in archive.read_recent(n=500):
            if _substring_hit(query, rec.get("intent", ""), rec.get("user", "")):
                hits.append(SearchHit(
                    store="brief",
                    id=rec.get("id", "")[:10],
                    at=rec.get("created_at", ""),
                    summary=f"{rec.get('kind', '?')}: {rec.get('intent', '')[:100]}",
                ))

    if "ref" in stores:
        for r in reference_lib._load_index():
            if _substring_hit(
                query, r.get("notes", ""), r.get("prompt", ""),
                " ".join(r.get("tags", [])),
            ):
                hits.append(SearchHit(
                    store="ref",
                    id=r.get("id", ""),
                    at=r.get("added_at", ""),
                    summary=(r.get("notes") or r.get("prompt", ""))[:100],
                ))

    if "post" in stores:
        for p in export_mod.list_recent(n=200):
            if _substring_hit(query, p.get("caption", ""), p.get("alt_text", "")):
                hits.append(SearchHit(
                    store="post",
                    id=p.get("id", ""),
                    at=p.get("created_at", ""),
                    summary=p.get("caption", "")[:100],
                ))

    if "codex" in stores:
        sections = codex_audit._parse_sections(style_codex.read())
        for section_name, entries in sections:
            for body in entries:
                if _substring_hit(query, body):
                    hits.append(SearchHit(
                        store="codex",
                        id=section_name[:20],
                        at="",
                        summary=body[:100],
                    ))

    if "topic" in stores:
        for t in topics._load():
            if _substring_hit(query, t.get("text", ""), " ".join(t.get("tags", []))):
                hits.append(SearchHit(
                    store="topic",
                    id=t.get("id", ""),
                    at=t.get("created_at", ""),
                    summary=f"[{t.get('status', '?')}] {t.get('text', '')[:90]}",
                ))

    # Sort by date desc — most recent hits first.
    hits.sort(key=lambda h: h.at or "", reverse=True)
    return SearchResult(query=query, hits=hits[:limit])
