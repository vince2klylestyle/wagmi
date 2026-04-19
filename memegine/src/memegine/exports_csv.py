"""CSV exports — dump each store to CSV for external analysis.

Operator wants to chart performance in Excel, feed refs into a notebook,
or pipe the archive into a one-off pandas analysis. These helpers flatten
the stores into tabular CSVs.

CSV dialect: quoted strings, UTF-8, comma separator, stdlib csv.
"""
from __future__ import annotations

import csv
from pathlib import Path

from . import archive, performance, reference_lib


def export_archive(destination: Path, limit: int = 5000) -> int:
    """Dump the last `limit` briefs to CSV. Returns row count."""
    rows = archive.read_recent(n=limit)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "created_at", "kind", "format", "intent", "system_len", "user_len"])
        for r in rows:
            writer.writerow([
                r.get("id", ""),
                r.get("created_at", ""),
                r.get("kind", ""),
                r.get("format", "") or "",
                r.get("intent", "")[:300],
                len(r.get("system", "") or ""),
                len(r.get("user", "") or ""),
            ])
    return len(rows)


def export_refs(destination: Path) -> int:
    """Dump the reference library index to CSV."""
    rows = reference_lib._load_index()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "filename", "added_at", "tags", "is_winner", "source",
            "prompt_first_120", "notes",
        ])
        for r in rows:
            tags = r.get("tags", []) or []
            writer.writerow([
                r.get("id", ""),
                r.get("filename", ""),
                r.get("added_at", ""),
                "|".join(tags),
                "winner" in tags,
                r.get("source", ""),
                (r.get("prompt", "") or "")[:120],
                r.get("notes", ""),
            ])
    return len(rows)


def export_performance(destination: Path) -> int:
    """Dump performance entries to CSV, latest per bundle kept."""
    entries = performance._all_entries()
    entries = performance._latest_per_bundle(entries)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "recorded_at", "post_bundle_id", "format", "posted_at",
            "likes", "reposts", "replies", "quotes", "impressions", "bookmarks",
            "score", "url", "patterns", "window", "notes",
        ])
        for e in entries:
            writer.writerow([
                e.get("id", ""),
                e.get("recorded_at", ""),
                e.get("post_bundle_id", "") or "",
                e.get("format_slug", "") or "",
                e.get("posted_at", ""),
                e.get("likes", 0),
                e.get("reposts", 0),
                e.get("replies", 0),
                e.get("quotes", 0),
                e.get("impressions", 0),
                e.get("bookmarks", 0),
                performance._score_entry(e),
                e.get("post_url", ""),
                "|".join(e.get("patterns", []) or []),
                e.get("window", ""),
                e.get("notes", ""),
            ])
    return len(entries)
