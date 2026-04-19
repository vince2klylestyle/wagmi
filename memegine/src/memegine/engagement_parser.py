"""Engagement paste parser — turn pasted X stats into a perf log entry.

The manual workflow `memegine perf log --likes 820 --rt 140 --replies 35
--impressions 12000` breaks the feedback loop because nobody types that.

Instead: the operator long-presses the stats block in X's analytics view
(or just the counts visible under a post), pastes the whole thing, and
memegine figures out the numbers.

Supported shapes:

    820 Likes
    140 Reposts
    35 Replies
    12.4K Views

    820 likes · 140 retweets · 35 replies

    820
    likes

    12.4K views  820 likes  140 retweets  35 replies  2 bookmarks  4 quotes

    ❤ 820  🔁 140  💬 35  📊 12.4K

K/M suffixes are expanded ("12.4K" → 12400, "1.2M" → 1200000).
Unlabeled numbers aren't guessed — we only assign a number to a field
when a recognizable label sits adjacent to it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from . import performance


# Label synonyms. All lowercase, checked as substring-match but anchored
# with regex word boundaries so "likely" doesn't match "like" (it does
# here because re.search won't word-boundary a noun, so we add explicit
# boundary regex below).
LABEL_SYNONYMS: dict[str, list[str]] = {
    "likes": [
        "like", "likes", "liked", "hearts", "heart", "♥", "❤", "❤️",
        "favourites", "favorites", "faves",
    ],
    "reposts": [
        "repost", "reposts", "retweet", "retweets", "rt", "rts",
        "🔁", "🔄", "reshare", "reshares",
    ],
    "replies": [
        "reply", "replies", "comment", "comments", "💬",
    ],
    "quotes": [
        "quote", "quotes", "qt", "qts", "quote tweet", "quote tweets",
    ],
    "bookmarks": [
        "bookmark", "bookmarks", "saved", "saves", "🔖",
    ],
    "impressions": [
        "impression", "impressions", "view", "views",
        "seen by", "🧿", "👁", "👁️", "📊",
    ],
}


# Build regex pattern once per label for fast lookup.
def _label_pattern(words: list[str]) -> re.Pattern:
    # Sort by length desc so longer phrases match before shorter prefixes
    # ("retweets" before "rt", "quote tweets" before "quotes").
    safe = sorted({re.escape(w) for w in words}, key=len, reverse=True)
    return re.compile(r"(?i)(?:" + "|".join(safe) + r")")


LABEL_PATTERNS: dict[str, re.Pattern] = {
    field: _label_pattern(words) for field, words in LABEL_SYNONYMS.items()
}

# Number pattern: optional decimal, optional K/M/B suffix. Accept comma
# thousands separators and ignore surrounding commas / parens.
NUM_RE = re.compile(
    r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*([KMBkmb])?(?![\w.])"
)


def _expand_number(raw: str, suffix: str | None) -> int:
    """Parse '12.4', 'K' → 12400. Commas stripped first."""
    n = float(raw.replace(",", ""))
    if suffix:
        s = suffix.upper()
        n *= {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[s]
    return int(round(n))


@dataclass
class ParsedEngagement:
    likes: int = 0
    reposts: int = 0
    replies: int = 0
    quotes: int = 0
    bookmarks: int = 0
    impressions: int = 0
    raw_text: str = ""
    unmatched_numbers: int = 0  # numbers we found but couldn't label

    def as_dict(self) -> dict[str, int]:
        return {
            "likes": self.likes, "reposts": self.reposts,
            "replies": self.replies, "quotes": self.quotes,
            "bookmarks": self.bookmarks, "impressions": self.impressions,
        }

    def any_found(self) -> bool:
        return any(v > 0 for v in self.as_dict().values())


def parse(text: str) -> ParsedEngagement:
    """Parse a pasted engagement block into a ParsedEngagement.

    Strategy: find every number in the text, then for each number look
    at its small neighborhood (±30 chars) for a recognizable label.
    The highest-priority label wins. If multiple numbers map to the
    same field, take the maximum (X sometimes shows "820" and "820
    likes" on the same line).
    """
    result = ParsedEngagement(raw_text=text)
    if not text or not text.strip():
        return result

    assigned: dict[str, list[int]] = {f: [] for f in LABEL_SYNONYMS}

    for m in NUM_RE.finditer(text):
        raw, suffix = m.group(1), m.group(2)
        value = _expand_number(raw, suffix)
        start = max(0, m.start() - 30)
        end = min(len(text), m.end() + 30)
        window = text[start:end]

        # Find the closest label within the window; ties broken by field
        # priority (likes > reposts > replies > quotes > bookmarks >
        # impressions) because that's the order of what operators care
        # about most.
        best_field: str | None = None
        best_distance = 10_000
        for field, pat in LABEL_PATTERNS.items():
            for lm in pat.finditer(window):
                abs_pos = start + lm.start()
                dist = abs(abs_pos - m.start())
                if dist < best_distance:
                    best_distance = dist
                    best_field = field

        if best_field is not None:
            assigned[best_field].append(value)
        else:
            result.unmatched_numbers += 1

    # Keep the max seen per field (handles "820" + "820 likes" pairs).
    for field, vals in assigned.items():
        if vals:
            setattr(result, field, max(vals))
    return result


def log_from_paste(
    text: str,
    *,
    post_bundle_id: str | None = None,
    post_url: str = "",
    format_slug: str | None = None,
    patterns: list[str] | None = None,
    posted_at: str = "",
    window: str = "24h",
    notes: str = "",
):
    """Parse `text` and call performance.log() with the extracted numbers.

    Returns (PostPerformance, ParsedEngagement). The performance entry is
    only written if at least one field was parsed (avoids empty rows).
    """
    parsed = parse(text)
    entry = None
    if parsed.any_found():
        entry = performance.log(
            post_bundle_id=post_bundle_id, post_url=post_url,
            format_slug=format_slug, patterns=patterns,
            posted_at=posted_at,
            likes=parsed.likes, reposts=parsed.reposts,
            replies=parsed.replies, quotes=parsed.quotes,
            impressions=parsed.impressions, bookmarks=parsed.bookmarks,
            window=window, notes=notes,
        )
    return entry, parsed
