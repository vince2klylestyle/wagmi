"""memegine — director's assistant.

Auto-loads .env into os.environ on import so Telegram bot config,
BlueStacks ADB settings, etc. all see the expected variables without
requiring the operator to export them manually every shell session.
"""
from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv_once() -> None:
    """Minimal dotenv loader — no pip dep. Silent on failure."""
    # Find .env walking up from this file; supports both installed and
    # editable-install layouts.
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / ".env"
        if candidate.exists():
            try:
                for line in candidate.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = val
            except OSError:
                pass
            return


_load_dotenv_once()
