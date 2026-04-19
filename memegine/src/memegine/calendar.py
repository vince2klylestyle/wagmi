"""Content calendar — scheduled publish timestamps per topic.

A topic gets a `publish_at` ISO timestamp. The scheduler's new
`calendar_due` action surfaces any topic whose time has come so the
operator can pick it up and produce the brief.

Storage: mutates the existing topic entries in data/topics/queue.yaml
by adding a `publish_at` field. Doesn't introduce a new store —
campaigns are already a store, topics are already a store, calendar
is a projection over topics.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

from ._time import now_naive_utc as _now_naive_utc
from . import topics


@dataclass
class CalendarEntry:
    topic_id: str
    text: str
    publish_at: str
    priority: int
    tags: list[str] = field(default_factory=list)
    status: str = "queued"


def _parse_iso(s: str) -> dt.datetime | None:
    if not s:
        return None
    try:
        parsed = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(dt.timezone.utc).replace(tzinfo=None)
    return parsed


def schedule(topic_id: str, publish_at: str) -> bool:
    """Attach a publish_at ISO timestamp to an existing topic."""
    parsed = _parse_iso(publish_at)
    if parsed is None:
        raise ValueError(f"unparseable ISO timestamp: {publish_at!r}")

    all_topics = topics._load()
    hit = False
    for t in all_topics:
        if t.get("id") == topic_id:
            t["publish_at"] = parsed.isoformat() + "Z"
            hit = True
            break
    if hit:
        topics._save(all_topics)
    return hit


def unschedule(topic_id: str) -> bool:
    all_topics = topics._load()
    hit = False
    for t in all_topics:
        if t.get("id") == topic_id and "publish_at" in t:
            del t["publish_at"]
            hit = True
            break
    if hit:
        topics._save(all_topics)
    return hit


def list_scheduled(
    *,
    future_only: bool = False,
    limit: int | None = None,
) -> list[CalendarEntry]:
    """List topics with a publish_at, soonest first."""
    now = _now_naive_utc()
    all_topics = topics._load()
    out: list[CalendarEntry] = []
    for t in all_topics:
        pub = t.get("publish_at", "")
        if not pub:
            continue
        parsed = _parse_iso(pub)
        if parsed is None:
            continue
        if future_only and parsed < now:
            continue
        out.append(CalendarEntry(
            topic_id=t.get("id", "?"),
            text=t.get("text", ""),
            publish_at=pub,
            priority=int(t.get("priority", 3)),
            tags=t.get("tags", []) or [],
            status=t.get("status", "queued"),
        ))
    out.sort(key=lambda e: e.publish_at)
    return out[:limit] if limit else out


def list_due(
    *,
    grace_minutes: int = 30,
) -> list[CalendarEntry]:
    """Topics whose publish_at has passed (within grace window), status queued."""
    now = _now_naive_utc()
    cutoff_past = now - dt.timedelta(minutes=grace_minutes)
    out: list[CalendarEntry] = []
    for e in list_scheduled():
        if e.status != "queued":
            continue
        parsed = _parse_iso(e.publish_at)
        if parsed is None:
            continue
        if cutoff_past <= parsed <= now + dt.timedelta(minutes=1):
            out.append(e)
    return out


def summary_text(*, future_only: bool = True) -> str:
    entries = list_scheduled(future_only=future_only, limit=20)
    if not entries:
        return "=== calendar — nothing scheduled ==="
    lines = [f"=== calendar — {len(entries)} scheduled ==="]
    for e in entries:
        lines.append(
            f"  {e.publish_at[:19]}  p={e.priority}  [{e.status}]  "
            f"{e.topic_id}  {e.text[:70]}"
        )
    return "\n".join(lines)
