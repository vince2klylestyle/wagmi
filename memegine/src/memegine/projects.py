"""Projects — multi-workspace support.

Each project is an independent workspace under data/projects/<name>/
holding its own codex, references, logs, posts, performance, etc. Shared
assets (formats library, fragments, playbooks) live at the top level of
data/ and are consumed by every project.

The active project is resolved (in priority order) from:
1. MEMEGINE_PROJECT env var
2. data/active_project file (set by `memegine project use <name>`)
3. "default" — legacy single-project behaviour at data/

This module owns the on-disk side of project management. The CLI wires
it up; settings.refresh_project(name) re-reads it in-process.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from .config import ACTIVE_PROJECT_FILE, DATA_ROOT, PROJECTS_ROOT


# Subdirectories that live under each per-project workspace. Mirror the
# path fields on Settings so a new project has the exact same shape as a
# seasoned one from day one.
PROJECT_SUBDIRS = (
    "codex",
    "references",
    "logs",
    "outputs",
    "posts",
    "performance",
    "sessions",
    "topics",
    "scheduler",
    "campaigns",
    "lookbooks",
    "fragments",   # per-project fragment overlays
    "playbooks",   # per-project playbook overlays
)

# Subdirectories that should MOVE when migrating the legacy single-project
# state into a named project. Shared assets (formats, fragments library,
# playbooks library) stay at data/ because they are project-agnostic.
LEGACY_MIGRATE_DIRS = (
    "codex",
    "references",
    "logs",
    "outputs",
    "posts",
    "performance",
    "sessions",
    "topics",
    "scheduler",
    "campaigns",
    "lookbooks",
)

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")


def _validate_name(name: str) -> None:
    if name == "default":
        raise ValueError("'default' is the implicit legacy workspace at data/; pick another name")
    if not _NAME_RE.fullmatch(name or ""):
        raise ValueError(
            f"invalid project name {name!r}: use lowercase a-z, 0-9, - or _, "
            f"1-32 chars, must start with a letter or digit"
        )


def project_path(name: str) -> Path:
    """Return the on-disk path for a project workspace."""
    if name == "default":
        return DATA_ROOT
    return PROJECTS_ROOT / name


def list_projects() -> list[tuple[str, Path]]:
    """Return [(name, path), ...] for every project directory under data/projects/."""
    if not PROJECTS_ROOT.exists():
        return []
    out: list[tuple[str, Path]] = []
    for p in sorted(PROJECTS_ROOT.iterdir()):
        if p.is_dir():
            out.append((p.name, p))
    return out


def create(name: str) -> Path:
    """Create a fresh project workspace. Raises FileExistsError if it exists."""
    _validate_name(name)
    base = project_path(name)
    if base.exists() and any(base.iterdir()):
        raise FileExistsError(f"project '{name}' already exists at {base}")
    base.mkdir(parents=True, exist_ok=True)
    for sub in PROJECT_SUBDIRS:
        (base / sub).mkdir(parents=True, exist_ok=True)
    return base


def set_active(name: str) -> None:
    """Persist `name` as the active project. Requires the project to exist
    (either on-disk or as the implicit 'default')."""
    if name != "default":
        _validate_name(name)
        if not project_path(name).exists():
            raise FileNotFoundError(
                f"project '{name}' does not exist; run `memegine project create {name}` first"
            )
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    ACTIVE_PROJECT_FILE.write_text(name.strip() + "\n", encoding="utf-8")


def current() -> str:
    """Return the currently-active project name (from the state file)."""
    if ACTIVE_PROJECT_FILE.exists():
        name = ACTIVE_PROJECT_FILE.read_text(encoding="utf-8").strip()
        if name:
            return name
    return "default"


def migrate_default_to(name: str) -> list[str]:
    """Move the legacy single-project state at data/ into data/projects/<name>/.

    Shared assets (formats, fragments library, playbooks library) are NOT
    moved — they stay at the data root because every project consumes them.

    Returns the list of subdir names that were moved.
    """
    _validate_name(name)
    dest = project_path(name)
    if dest.exists() and any(dest.iterdir()):
        raise FileExistsError(f"project '{name}' already exists at {dest}")
    dest.mkdir(parents=True, exist_ok=True)

    moved: list[str] = []
    for sub in LEGACY_MIGRATE_DIRS:
        src = DATA_ROOT / sub
        if not src.exists():
            continue
        shutil.move(str(src), str(dest / sub))
        moved.append(sub)

    # Ensure every expected subdir exists on the new project so callers
    # that assume these paths don't KeyError on missing state.
    for sub in PROJECT_SUBDIRS:
        (dest / sub).mkdir(parents=True, exist_ok=True)

    return moved
