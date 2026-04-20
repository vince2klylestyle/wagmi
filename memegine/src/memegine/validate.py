"""Config validator — fail-fast check of YAML configs and their shape.

Runs at startup (via `memegine validate`) to catch:
- malformed library.yaml (missing slug, bad kind, missing scaffolds)
- malformed fragments library (empty category, non-string body)
- malformed playbooks (empty file, unreadable)
- malformed scheduler jobs / topic queue / trend feeds
- malformed post bundles (missing meta.json, missing media)

Each issue is a Problem with severity / path / message. The validator
never modifies anything; it surfaces issues for the operator to fix.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .config import settings


@dataclass
class Problem:
    severity: str         # "ERROR" | "WARN"
    where: str            # path or identifier
    message: str


@dataclass
class ValidationReport:
    problems: list[Problem] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for p in self.problems if p.severity == "ERROR")

    @property
    def warn_count(self) -> int:
        return sum(1 for p in self.problems if p.severity == "WARN")

    @property
    def ok(self) -> bool:
        return self.error_count == 0

    def add(self, severity: str, where: str, message: str) -> None:
        self.problems.append(Problem(severity, where, message))

    def as_text(self) -> str:
        lines = [
            f"=== validate — {len(self.problems)} issues "
            f"({self.error_count} errors, {self.warn_count} warnings) ==="
        ]
        for p in self.problems:
            sigil = "[ERR] " if p.severity == "ERROR" else "[warn]"
            lines.append(f"  {sigil} {p.where}: {p.message}")
        if not self.problems:
            lines.append("  all clean")
        return "\n".join(lines)


def _validate_formats(report: ValidationReport) -> None:
    # Formats library is SHARED across projects — check data_root.
    path = settings.data_root / "formats" / "library.yaml"
    if not path.exists():
        report.add("ERROR", str(path), "formats library.yaml missing")
        return
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        report.add("ERROR", str(path), f"YAML parse error: {exc}")
        return
    if not isinstance(data, dict) or "formats" not in data:
        report.add("ERROR", str(path), "expected top-level 'formats:' list")
        return
    formats = data.get("formats") or []
    if not formats:
        report.add("WARN", str(path), "library has no formats")
        return
    slugs: set[str] = set()
    for i, f in enumerate(formats):
        loc = f"formats[{i}] '{f.get('slug', '?')}'"
        if not f.get("slug"):
            report.add("ERROR", loc, "missing slug")
            continue
        if f["slug"] in slugs:
            report.add("ERROR", loc, "duplicate slug")
        slugs.add(f["slug"])
        if f.get("kind") not in ("image", "video"):
            report.add("ERROR", loc, f"kind must be 'image' or 'video', got {f.get('kind')!r}")
        has_scaffold = (
            f.get("prompt_scaffold") or f.get("prompt_scaffold_still")
            or f.get("prompt_scaffold_motion")
        )
        if not has_scaffold:
            report.add("ERROR", loc, "no prompt scaffold present")
        models = (f.get("good_models") or []) + (f.get("good_models_still") or []) + (f.get("good_models_motion") or [])
        if not models:
            report.add("WARN", loc, "no good_models entries — downstream model routing will be ambiguous")
        if not (f.get("description") or "").strip():
            report.add("WARN", loc, "description is empty")


def _validate_fragments(report: ValidationReport) -> None:
    # Fragments library is SHARED across projects — check data_root.
    path = settings.data_root / "fragments" / "library.yaml"
    if not path.exists():
        report.add("WARN", str(path), "fragments library missing (fragments feature disabled)")
        return
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        report.add("ERROR", str(path), f"YAML parse error: {exc}")
        return
    if not isinstance(data, dict):
        report.add("ERROR", str(path), "expected top-level mapping of categories")
        return
    for cat, items in data.items():
        if not str(cat).replace("_", "").isalpha() or not str(cat).isupper():
            report.add("WARN", f"fragments[{cat}]", "category should be UPPERCASE_SNAKE_CASE")
        if not isinstance(items, dict):
            report.add("ERROR", f"fragments[{cat}]", "value must be a mapping of name → body")
            continue
        if not items:
            report.add("WARN", f"fragments[{cat}]", "empty category")
            continue
        for name, body in items.items():
            loc = f"fragments[{cat}.{name}]"
            if not isinstance(body, str):
                report.add("ERROR", loc, f"body must be a string, got {type(body).__name__}")
            elif not body.strip():
                report.add("WARN", loc, "body is empty")


def _validate_playbooks(report: ValidationReport) -> None:
    # Playbooks are SHARED — check data_root.
    path = settings.data_root / "playbooks"
    if not path.exists():
        report.add("WARN", str(path), "playbooks dir missing (prompts won't have craft context)")
        return
    md_files = list(path.glob("*.md"))
    if not md_files:
        report.add("WARN", str(path), "no *.md playbook files")
        return
    for p in md_files:
        if p.stat().st_size == 0:
            report.add("WARN", str(p), "playbook is empty")
        elif p.stat().st_size < 200:
            report.add("WARN", str(p), "playbook is very short (<200 bytes)")


def _validate_scheduler_jobs(report: ValidationReport) -> None:
    path = settings.data_dir / "scheduler" / "jobs.yaml"
    if not path.exists():
        return  # OK — no scheduled jobs yet
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        report.add("ERROR", str(path), f"YAML parse error: {exc}")
        return
    for i, job in enumerate(data.get("jobs", []) or []):
        loc = f"jobs[{i}] '{job.get('name', '?')}'"
        hour = job.get("hour", -1)
        minute = job.get("minute", -1)
        if not (0 <= int(hour) <= 23):
            report.add("ERROR", loc, f"hour {hour} out of range")
        if not (0 <= int(minute) <= 59):
            report.add("ERROR", loc, f"minute {minute} out of range")


def _validate_trend_feeds(report: ValidationReport) -> None:
    path = settings.data_dir / "trends" / "feeds.yaml"
    if not path.exists():
        return
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        report.add("ERROR", str(path), f"YAML parse error: {exc}")
        return
    valid_kinds = {"rss", "atom", "jsonl", "json"}
    for i, feed in enumerate(data.get("feeds", []) or []):
        loc = f"feeds[{i}] '{feed.get('name', '?')}'"
        if not feed.get("url", "").startswith(("http://", "https://")):
            report.add("ERROR", loc, f"url must be http(s), got {feed.get('url', '')[:40]!r}")
        if feed.get("kind") not in valid_kinds:
            report.add("ERROR", loc, f"kind must be one of {valid_kinds}")


def _validate_topics_queue(report: ValidationReport) -> None:
    path = settings.data_dir / "topics" / "queue.yaml"
    if not path.exists():
        return
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        report.add("ERROR", str(path), f"YAML parse error: {exc}")
        return
    for i, t in enumerate(data.get("topics", []) or []):
        loc = f"topics[{i}] '{t.get('id', '?')}'"
        if t.get("status") not in (None, "queued", "used", "skipped"):
            report.add("ERROR", loc, f"unknown status {t.get('status')!r}")
        prio = t.get("priority", 3)
        if not (1 <= int(prio) <= 5):
            report.add("ERROR", loc, f"priority {prio} out of 1-5")


def _validate_post_bundles(report: ValidationReport) -> None:
    path = settings.data_dir / "posts"
    if not path.exists():
        return
    for folder in path.iterdir():
        if not folder.is_dir():
            continue
        meta = folder / "meta.json"
        if not meta.exists():
            report.add("WARN", str(folder), "post bundle missing meta.json")
            continue
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            report.add("ERROR", str(meta), f"JSON parse error: {exc}")
            continue
        media_name = data.get("media", "")
        if media_name and not (folder / media_name).exists():
            report.add("ERROR", str(folder), f"meta.media '{media_name}' does not exist")


def run() -> ValidationReport:
    """Run every validator and return the combined report."""
    report = ValidationReport()
    _validate_formats(report)
    _validate_fragments(report)
    _validate_playbooks(report)
    _validate_scheduler_jobs(report)
    _validate_trend_feeds(report)
    _validate_topics_queue(report)
    _validate_post_bundles(report)
    return report
