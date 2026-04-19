"""Brief preflight — one-command pre-ship quality gate.

Runs every check against a prompt before it goes to Grok:
- deep_linter: 0-100 craft coverage
- linter: banned-word hard fail
- consistency: codex Core Patterns alignment
- (optional) motion-mode lint for video prompts

Returns an aggregated PreflightReport. Operator gets one PASS / WARN /
FAIL verdict instead of running five commands.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import consistency, deep_linter, linter as base_linter


@dataclass
class PreflightReport:
    prompt: str
    verdict: str                      # "PASS" | "WARN" | "FAIL"
    craft_score: int = 0
    craft_grade: str = ""
    consistency_score: int = 0
    banned_words: list[str] = field(default_factory=list)
    craft_tips: list[str] = field(default_factory=list)
    consistency_missed: list[str] = field(default_factory=list)

    def as_text(self) -> str:
        lines = [
            f"=== preflight — {self.verdict} ===",
            f"  craft:       {self.craft_score}/100 (grade {self.craft_grade})",
            f"  consistency: {self.consistency_score}/100",
        ]
        if self.banned_words:
            lines.append(f"  banned:      {', '.join(self.banned_words)}")
        if self.craft_tips:
            lines.append("  craft tips:")
            for t in self.craft_tips[:5]:
                lines.append(f"    - {t}")
        if self.consistency_missed:
            lines.append("  consistency missed (codex says these should be here):")
            for m in self.consistency_missed[:5]:
                lines.append(f"    - {m}")
        return "\n".join(lines)


def check(prompt: str, *, motion: bool = False) -> PreflightReport:
    """Run all checks and return a combined verdict.

    FAIL: any banned word OR craft score < 50 OR motion-mode hard error.
    WARN: craft score 50-69 or consistency < 30%.
    PASS: craft >= 70 AND no errors AND consistency >= 30% (or codex empty).
    """
    kind = "motion" if motion else "image"
    craft = deep_linter.score(prompt, kind=kind)
    base = base_linter.lint(prompt, kind=kind)
    cons = consistency.check(prompt)

    banned = [i.message.split("'")[1] for i in base.errors if "banned word" in i.message]
    motion_errors = [i.message for i in base.errors if "motion prompt" in i.message]

    # Decide verdict.
    has_error = bool(banned) or bool(motion_errors)
    weak_craft = craft.score < 50
    # Only hold consistency against the prompt if the codex has any patterns
    # at all; a fresh project shouldn't block everything.
    weak_consistency = cons.core_patterns_total > 0 and cons.score < 30

    if has_error or weak_craft:
        verdict = "FAIL"
    elif craft.score < 70 or weak_consistency:
        verdict = "WARN"
    else:
        verdict = "PASS"

    return PreflightReport(
        prompt=prompt,
        verdict=verdict,
        craft_score=craft.score,
        craft_grade=deep_linter.grade(craft.score),
        consistency_score=cons.score,
        banned_words=banned,
        craft_tips=craft.suggestions,
        consistency_missed=cons.missed,
    )
