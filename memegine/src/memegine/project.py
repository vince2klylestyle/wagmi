"""Project archive — snapshot the whole memegine state into a single zip.

Full state = codex + references + formats + fragments + playbooks +
logs + posts + performance + sessions + scheduler + topics + trends.

Use cases:
- Backup before experimenting
- Share project state with a collaborator
- Migrate to a new machine / phone
- Restore after accidentally corrupting the codex

Archive format: a regular .zip of the entire `data/` directory
relative to the memegine install.
"""
from __future__ import annotations

import datetime as dt
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

from ._time import now_naive_utc as _now_naive_utc
from .config import settings


SNAPSHOT_DIRS = (
    "codex", "references", "formats", "fragments", "playbooks", "logs",
    "posts", "performance", "sessions", "scheduler", "topics", "trends",
    "outputs", "lookbooks",
)


@dataclass
class ArchiveResult:
    destination: str
    bytes_written: int
    files_included: int


def archive(destination: Path | None = None) -> ArchiveResult:
    """Create a .zip of the memegine data dir."""
    if destination is None:
        stamp = _now_naive_utc().strftime("%Y%m%d-%H%M%S")
        destination = settings.data_dir.parent / f"memegine-snapshot-{stamp}.zip"
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    files_included = 0
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as zf:
        for sub in SNAPSHOT_DIRS:
            root = settings.data_dir / sub
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if path.is_file():
                    arcname = path.relative_to(settings.data_dir)
                    zf.write(path, str(arcname))
                    files_included += 1

    return ArchiveResult(
        destination=str(destination),
        bytes_written=destination.stat().st_size,
        files_included=files_included,
    )


@dataclass
class RestoreResult:
    source: str
    restored_files: int
    overwrote_existing: bool


def restore(source: Path | str, *, force: bool = False) -> RestoreResult:
    """Extract a memegine snapshot zip into `data_dir`.

    force=False (default): if the data_dir has anything, refuse unless
    the operator passes force=True. Prevents accidental overwrite.
    """
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(source)

    data_dir = settings.data_dir
    overwrote = False
    if data_dir.exists() and any(data_dir.iterdir()):
        if not force:
            raise ValueError(
                f"data_dir {data_dir} is not empty. Pass force=True to overwrite "
                "or move the existing data_dir out of the way first."
            )
        overwrote = True

    data_dir.mkdir(parents=True, exist_ok=True)

    restored = 0
    with zipfile.ZipFile(source, "r") as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            target = data_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(name) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            restored += 1

    return RestoreResult(
        source=str(source),
        restored_files=restored,
        overwrote_existing=overwrote,
    )
