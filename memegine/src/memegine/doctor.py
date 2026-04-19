"""Doctor — health check for the memegine environment.

Validates that everything a real operator needs will actually work:
- data dirs exist and are writable
- ffmpeg is on PATH (for the editor module)
- format library loads and has no malformed entries
- playbooks load
- style codex is readable
- optional Anthropic / Telegram / Discord config is internally consistent

Exit code: 0 if everything's PASS, 1 if any ERROR check fails. WARN checks
don't fail the run but surface things the operator should know about.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field

from . import prompt_engine, style_codex
from .config import settings


@dataclass
class CheckResult:
    name: str
    status: str        # "PASS" | "WARN" | "ERROR"
    detail: str = ""


@dataclass
class DoctorReport:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.status != "ERROR" for c in self.checks)

    def as_text(self) -> str:
        lines = ["=== memegine doctor ==="]
        for c in self.checks:
            sigil = {"PASS": "[OK]  ", "WARN": "[warn]", "ERROR": "[ERR] "}[c.status]
            lines.append(f"  {sigil} {c.name}")
            if c.detail:
                lines.append(f"         {c.detail}")
        lines.append("")
        lines.append(f"verdict: {'PASS' if self.ok else 'FAIL'}")
        return "\n".join(lines)


def _check_data_dirs() -> list[CheckResult]:
    out: list[CheckResult] = []
    for name, path in (
        ("data_dir", settings.data_dir),
        ("codex_path", settings.codex_path.parent),
        ("references_dir", settings.references_dir),
        ("outputs_dir", settings.outputs_dir),
        ("logs_dir", settings.logs_dir),
    ):
        try:
            path.mkdir(parents=True, exist_ok=True)
            # Test write.
            test = path / ".memegine-doctor-write-test"
            test.write_text("x", encoding="utf-8")
            test.unlink()
            out.append(CheckResult(f"{name} writable ({path})", "PASS"))
        except Exception as exc:
            out.append(CheckResult(f"{name} writable", "ERROR", str(exc)))
    return out


def _check_ffmpeg() -> CheckResult:
    binary = shutil.which("ffmpeg")
    if not binary:
        return CheckResult("ffmpeg on PATH", "WARN", "not found; editor/grading/music modules won't work")
    try:
        result = subprocess.run(
            [binary, "-version"], capture_output=True, text=True, timeout=5,
        )
        first_line = (result.stdout or "").splitlines()[0] if result.stdout else "?"
        return CheckResult("ffmpeg on PATH", "PASS", first_line)
    except Exception as exc:
        return CheckResult("ffmpeg on PATH", "WARN", f"found but failed: {exc}")


def _check_formats() -> CheckResult:
    try:
        formats = prompt_engine.load_formats()
    except Exception as exc:
        return CheckResult("formats load", "ERROR", str(exc))
    if not formats:
        return CheckResult("formats load", "ERROR", "library is empty")
    bad: list[str] = []
    for f in formats:
        # Each format needs at least one scaffold.
        has_any = (
            f.prompt_scaffold or f.prompt_scaffold_still or f.prompt_scaffold_motion
        )
        if not has_any:
            bad.append(f.slug)
    if bad:
        return CheckResult(
            "formats load", "WARN",
            f"{len(formats)} loaded, {len(bad)} missing scaffold: {bad}",
        )
    return CheckResult("formats load", "PASS", f"{len(formats)} formats")


def _check_playbooks() -> CheckResult:
    playbooks_dir = settings.data_dir / "playbooks"
    if not playbooks_dir.exists():
        return CheckResult("playbooks dir", "WARN", "no playbooks/ directory")
    md_files = list(playbooks_dir.glob("*.md"))
    if not md_files:
        return CheckResult("playbooks dir", "WARN", "no *.md files in playbooks/")
    return CheckResult("playbooks dir", "PASS", f"{len(md_files)} playbooks")


def _check_codex() -> CheckResult:
    try:
        text = style_codex.read()
    except Exception as exc:
        return CheckResult("codex readable", "ERROR", str(exc))
    if not text.strip():
        return CheckResult(
            "codex readable", "WARN",
            f"empty ({settings.codex_path}); seed with 10-20 winners for best results",
        )
    return CheckResult("codex readable", "PASS", f"{len(text)} chars")


def _check_anthropic() -> CheckResult:
    key = settings.anthropic_api_key
    if not key:
        return CheckResult("anthropic api key", "WARN", "unset; `memegine execute` disabled, offline-first still works")
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return CheckResult(
            "anthropic sdk", "WARN",
            "ANTHROPIC_API_KEY set but anthropic SDK not installed (pip install -e '.[online]')",
        )
    return CheckResult("anthropic sdk + key", "PASS")


def _check_telegram() -> CheckResult:
    token = os.environ.get("MEMEGINE_TELEGRAM_BOT_TOKEN", "").strip()
    allowlist = os.environ.get("MEMEGINE_TELEGRAM_ALLOWED_USER_IDS", "").strip()
    if not token and not allowlist:
        return CheckResult("telegram config", "WARN", "unset (bot disabled — ok for CLI-only use)")
    try:
        import telegram  # noqa: F401
    except ImportError:
        return CheckResult(
            "telegram sdk", "WARN",
            "telegram env set but python-telegram-bot not installed (pip install -e '.[telegram]')",
        )
    if not token:
        return CheckResult("telegram config", "ERROR", "allowlist set but no token")
    if not allowlist:
        return CheckResult(
            "telegram allowlist", "ERROR",
            "token set but MEMEGINE_TELEGRAM_ALLOWED_USER_IDS empty — bot will refuse to start",
        )
    return CheckResult("telegram config", "PASS")


def _check_discord() -> CheckResult:
    url = os.environ.get("MEMEGINE_DISCORD_WEBHOOK_URL", "").strip()
    if not url:
        return CheckResult("discord webhook", "WARN", "unset (discord delivery disabled — ok)")
    if not url.startswith("https://discord.com/api/webhooks/"):
        return CheckResult(
            "discord webhook", "ERROR",
            f"URL doesn't look like a discord webhook: {url[:50]}...",
        )
    return CheckResult("discord webhook", "PASS")


def run() -> DoctorReport:
    checks: list[CheckResult] = []
    checks.extend(_check_data_dirs())
    checks.append(_check_ffmpeg())
    checks.append(_check_formats())
    checks.append(_check_playbooks())
    checks.append(_check_codex())
    checks.append(_check_anthropic())
    checks.append(_check_telegram())
    checks.append(_check_discord())
    return DoctorReport(checks=checks)
