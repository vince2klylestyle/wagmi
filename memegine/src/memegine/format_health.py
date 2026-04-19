"""Format health — detect formats that consistently under-perform.

A format that's used 10+ times and averages bottom-half engagement is a
candidate for deprecation. This module surfaces those formats so the
operator can consciously rotate them out (or decide the low numbers
aren't format-fault and leave them in).

No automatic deprecation — the operator is the only one who can decide
a format is truly dead.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean

from . import performance


@dataclass
class FormatVerdict:
    slug: str
    n_posts: int
    avg_score: float
    verdict: str     # "healthy" | "watch" | "candidate_for_deprecation"


@dataclass
class FormatHealthReport:
    total_formats_with_data: int = 0
    verdicts: list[FormatVerdict] = field(default_factory=list)
    median_score: float = 0.0

    def as_text(self) -> str:
        lines = [
            f"=== format health — {self.total_formats_with_data} formats with data ===",
            f"median avg_score across formats: {self.median_score:.1f}",
            "",
        ]
        for v in self.verdicts:
            lines.append(
                f"  [{v.verdict:<28}] {v.slug:<28} n={v.n_posts:<3}  "
                f"avg={v.avg_score:.1f}"
            )
        return "\n".join(lines)


def evaluate(
    *,
    min_posts_for_verdict: int = 5,
    watch_multiplier: float = 0.75,
    deprecate_multiplier: float = 0.5,
) -> FormatHealthReport:
    """Classify each format by performance relative to the median.

    - avg_score >= median             → healthy
    - median * watch_multiplier ≤ avg < median → watch
    - avg < median * deprecate_multiplier → candidate_for_deprecation

    Formats with fewer than min_posts_for_verdict posts are all "healthy"
    (not enough data to judge). Order of verdicts: worst performers first.
    """
    rows = performance.by_format()
    if not rows:
        return FormatHealthReport()

    # Compute median over formats with enough data.
    qualified = [r for r in rows if r[1] >= min_posts_for_verdict]
    median_source = qualified if qualified else rows
    median_score = (
        mean([r[2] for r in median_source]) if median_source else 0.0
    )  # "median" here loosely — mean as a stable center for few formats

    verdicts: list[FormatVerdict] = []
    for slug, n, avg in rows:
        if n < min_posts_for_verdict:
            verdict = "healthy"   # insufficient data; don't flag
        elif avg < median_score * deprecate_multiplier:
            verdict = "candidate_for_deprecation"
        elif avg < median_score * watch_multiplier:
            verdict = "watch"
        else:
            verdict = "healthy"
        verdicts.append(FormatVerdict(slug, n, avg, verdict))

    # Worst first so operator sees the concerning ones at the top.
    order = {"candidate_for_deprecation": 0, "watch": 1, "healthy": 2}
    verdicts.sort(key=lambda v: (order[v.verdict], v.avg_score))

    return FormatHealthReport(
        total_formats_with_data=len(rows),
        verdicts=verdicts,
        median_score=median_score,
    )
