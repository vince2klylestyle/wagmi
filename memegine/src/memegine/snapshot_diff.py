"""Snapshot diff — compare two project archive zips.

Useful for "what did I add this week?" or "what changed between
Tuesday's backup and now?". Compares file names and byte sizes; flags
added / removed / changed entries. Keeps it lightweight.
"""
from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DiffReport:
    a_path: str
    b_path: str
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changed: list[tuple[str, int, int]] = field(default_factory=list)  # name, a_size, b_size
    unchanged_count: int = 0

    def as_text(self) -> str:
        lines = [f"=== snapshot diff — a={Path(self.a_path).name}  b={Path(self.b_path).name} ==="]
        lines.append(f"  unchanged: {self.unchanged_count}")
        lines.append(f"  added in b: {len(self.added)}")
        for name in self.added[:20]:
            lines.append(f"    + {name}")
        if len(self.added) > 20:
            lines.append(f"      (... {len(self.added) - 20} more)")
        lines.append(f"  removed in b: {len(self.removed)}")
        for name in self.removed[:20]:
            lines.append(f"    - {name}")
        if len(self.removed) > 20:
            lines.append(f"      (... {len(self.removed) - 20} more)")
        lines.append(f"  changed (size): {len(self.changed)}")
        for name, a_sz, b_sz in self.changed[:20]:
            lines.append(f"    ~ {name}  {a_sz} → {b_sz} bytes")
        return "\n".join(lines)


def _index(path: Path) -> dict[str, int]:
    with zipfile.ZipFile(path) as zf:
        return {
            info.filename: info.file_size
            for info in zf.infolist()
            if not info.filename.endswith("/")
        }


def diff(a_path: str | Path, b_path: str | Path) -> DiffReport:
    a_path = Path(a_path)
    b_path = Path(b_path)
    a_idx = _index(a_path)
    b_idx = _index(b_path)

    report = DiffReport(a_path=str(a_path), b_path=str(b_path))
    all_names = set(a_idx) | set(b_idx)
    for name in sorted(all_names):
        in_a = name in a_idx
        in_b = name in b_idx
        if in_a and in_b:
            if a_idx[name] != b_idx[name]:
                report.changed.append((name, a_idx[name], b_idx[name]))
            else:
                report.unchanged_count += 1
        elif in_b:
            report.added.append(name)
        else:
            report.removed.append(name)

    return report
