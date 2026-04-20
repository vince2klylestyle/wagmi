from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"
PROJECTS_ROOT = DATA_ROOT / "projects"
ACTIVE_PROJECT_FILE = DATA_ROOT / "active_project"


def _read_active_project() -> str:
    """Resolve the active project name.

    Priority:
    1. MEMEGINE_PROJECT env var (one-shot override from shell)
    2. data/active_project file (persistent across shells, settable via
       `memegine project use <name>`)
    3. "default" — preserves single-project behaviour on fresh installs
    """
    env = os.environ.get("MEMEGINE_PROJECT", "").strip()
    if env:
        return env
    try:
        if ACTIVE_PROJECT_FILE.exists():
            name = ACTIVE_PROJECT_FILE.read_text(encoding="utf-8").strip()
            if name:
                return name
    except OSError:
        pass
    return "default"


def _project_dir(name: str) -> Path:
    """Return the per-project data root. 'default' uses data/ directly for
    backwards compatibility with single-project installs; any other name
    lives under data/projects/<name>/."""
    if name == "default":
        return DATA_ROOT
    return PROJECTS_ROOT / name


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_prefix="MEMEGINE_",
        extra="ignore",
    )

    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")

    ideation_model: str = "claude-opus-4-7"
    utility_model: str = "claude-sonnet-4-6"

    # Active project — resolved at settings-construction time from env
    # var or active_project state file. Re-resolve via refresh_project().
    project: str = Field(default_factory=_read_active_project)

    # The overall data root (shared across projects — formats library,
    # fragments library, playbooks live here). Does NOT change per project.
    data_root: Path = DATA_ROOT

    # Per-project paths — initialised from the resolved project name.
    data_dir: Path = Field(default_factory=lambda: _project_dir(_read_active_project()))
    codex_path: Path = Field(
        default_factory=lambda: _project_dir(_read_active_project()) / "codex" / "style.md"
    )
    references_dir: Path = Field(
        default_factory=lambda: _project_dir(_read_active_project()) / "references"
    )
    outputs_dir: Path = Field(
        default_factory=lambda: _project_dir(_read_active_project()) / "outputs"
    )
    logs_dir: Path = Field(
        default_factory=lambda: _project_dir(_read_active_project()) / "logs"
    )

    def ensure_dirs(self) -> None:
        for p in [self.data_dir, self.codex_path.parent, self.references_dir,
                  self.outputs_dir, self.logs_dir]:
            p.mkdir(parents=True, exist_ok=True)

    def refresh_project(self, name: str | None = None) -> None:
        """Swap the active project without restarting.

        If `name` is None, re-read from env/state file. Otherwise use the
        supplied name directly. Updates every per-project path field on
        the settings instance in place.
        """
        resolved = name if name is not None else _read_active_project()
        base = _project_dir(resolved)
        self.project = resolved
        self.data_dir = base
        self.codex_path = base / "codex" / "style.md"
        self.references_dir = base / "references"
        self.outputs_dir = base / "outputs"
        self.logs_dir = base / "logs"


settings = Settings()
