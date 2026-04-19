"""Trend reader — pull topic candidates from external feeds.

Offline-first philosophy still applies: this doesn't auto-post. It only
fetches from URLs the operator explicitly configures, extracts
intent-sized strings, dedupes against the topic queue, and appends new
ones for human review via `memegine topics list`.

Feeds are YAML at `data/trends/feeds.yaml`:

    feeds:
      - name: nyt-tech
        url: https://www.nytimes.com/svc/collections/v1/publish/...rss
        kind: rss                  # rss | atom | jsonl | json
        source: nyt                # tag to apply to new topics
        max_items: 5
        priority: 3

No paid APIs. stdlib urllib only. RSS parsing is regex-based (enough to
pull <title> and <link> out; good enough for a signal, not a replacement
for a real RSS lib).
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import topics
from .config import settings


@dataclass
class FeedConfig:
    name: str
    url: str
    kind: str = "rss"              # rss | atom | jsonl | json
    source: str = ""
    max_items: int = 5
    priority: int = 3
    tags: list[str] = field(default_factory=list)


@dataclass
class FeedFetchResult:
    feed: str
    added: int = 0
    skipped: int = 0
    error: str = ""
    titles_added: list[str] = field(default_factory=list)


def _feeds_path() -> Path:
    return settings.data_dir / "trends" / "feeds.yaml"


def load_feeds(path: Path | None = None) -> list[FeedConfig]:
    p = path or _feeds_path()
    if not p.exists():
        return []
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    out: list[FeedConfig] = []
    for f in raw.get("feeds", []):
        out.append(FeedConfig(
            name=str(f.get("name", "?")),
            url=str(f.get("url", "")),
            kind=str(f.get("kind", "rss")).lower(),
            source=str(f.get("source", "")),
            max_items=int(f.get("max_items", 5)),
            priority=int(f.get("priority", 3)),
            tags=list(f.get("tags", []) or []),
        ))
    return out


def save_feeds(feeds: list[FeedConfig], path: Path | None = None) -> None:
    p = path or _feeds_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {"feeds": [
        {
            "name": f.name, "url": f.url, "kind": f.kind,
            "source": f.source, "max_items": f.max_items,
            "priority": f.priority, "tags": f.tags,
        }
        for f in feeds
    ]}
    p.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def add_feed(
    *,
    name: str,
    url: str,
    kind: str = "rss",
    source: str = "",
    max_items: int = 5,
    priority: int = 3,
    tags: list[str] | None = None,
) -> FeedConfig:
    feeds = load_feeds()
    feeds = [f for f in feeds if f.name != name]  # replace
    cfg = FeedConfig(
        name=name, url=url, kind=kind, source=source,
        max_items=max_items, priority=priority, tags=list(tags or []),
    )
    feeds.append(cfg)
    save_feeds(feeds)
    return cfg


def _fetch(url: str, timeout: float = 10.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "memegine/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    # Most feeds are UTF-8; fall back on latin-1 if decode fails.
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1", errors="replace")


_RSS_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def _strip_cdata(s: str) -> str:
    # Strip <![CDATA[...]]> wrappers common in RSS titles.
    m = re.match(r"<!\[CDATA\[(.*?)\]\]>", s, re.DOTALL)
    return m.group(1).strip() if m else s.strip()


def _parse_rss_titles(body: str, max_items: int) -> list[str]:
    titles = _RSS_TITLE_RE.findall(body)
    # First title is usually the feed's own name — skip.
    out = [_strip_cdata(t) for t in titles[1 : max_items + 1]]
    return [t for t in out if t]


def _parse_jsonl_titles(body: str, max_items: int) -> list[str]:
    out: list[str] = []
    for line in body.splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        title = rec.get("title") or rec.get("text") or ""
        if title:
            out.append(str(title).strip())
        if len(out) >= max_items:
            break
    return out


def _parse_json_titles(body: str, max_items: int) -> list[str]:
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        # Try common keys where the list lives.
        for key in ("items", "data", "results", "entries", "posts"):
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
        else:
            return []
    out: list[str] = []
    for item in data:
        if isinstance(item, dict):
            title = item.get("title") or item.get("text") or item.get("name") or ""
        elif isinstance(item, str):
            title = item
        else:
            title = ""
        if title:
            out.append(str(title).strip())
        if len(out) >= max_items:
            break
    return out


def extract_titles(body: str, *, kind: str, max_items: int) -> list[str]:
    kind = kind.lower()
    if kind in ("rss", "atom"):
        return _parse_rss_titles(body, max_items)
    if kind == "jsonl":
        return _parse_jsonl_titles(body, max_items)
    if kind == "json":
        return _parse_json_titles(body, max_items)
    return []


def _already_queued(text: str, existing: list[dict]) -> bool:
    low = text.lower().strip()
    for t in existing:
        if t.get("text", "").lower().strip() == low:
            return True
    return False


def fetch_feed(
    cfg: FeedConfig,
    *,
    fetcher=None,
    dry_run: bool = False,
) -> FeedFetchResult:
    """Fetch a single feed, parse titles, enqueue new ones as topics.

    fetcher: callable taking (url) → body string. Allows tests to stub
    without hitting the network.
    dry_run: if True, don't actually write to the topic queue.
    """
    fetcher = fetcher or _fetch
    result = FeedFetchResult(feed=cfg.name)
    try:
        body = fetcher(cfg.url)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as exc:
        result.error = str(exc)
        return result

    titles = extract_titles(body, kind=cfg.kind, max_items=cfg.max_items)
    existing = topics._load()
    for title in titles:
        if _already_queued(title, existing):
            result.skipped += 1
            continue
        if not dry_run:
            topics.add(
                title,
                tags=list(cfg.tags),
                priority=cfg.priority,
                source=cfg.source or f"trend:{cfg.name}",
            )
        result.added += 1
        result.titles_added.append(title)
    return result


def fetch_all(
    *,
    fetcher=None,
    dry_run: bool = False,
) -> list[FeedFetchResult]:
    return [fetch_feed(cfg, fetcher=fetcher, dry_run=dry_run) for cfg in load_feeds()]
