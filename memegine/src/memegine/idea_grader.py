"""Idea grader — score a topic/intent 0-100 for 'landability'.

Heuristic-only. No LLM. The grader answers "is this a well-formed piece
intent?" not "will this specific take be popular" — that's downstream.

What we reward:
- SPECIFICITY: names a concrete subject, place, time, emotion, or brand.
  Abstract intents ("the vibe of crypto") score low; specific intents
  ("a trader's face at 3am after ETH drops 12%") score high.
- EMOTIONAL VALENCE: a named emotion or state (cope, desperation, glee,
  disgust, reverence, defeat, awe). Memes land when the emotion is sharp.
- FORMAT-FRIENDLINESS: intent keywords trigger at least one format slug.
- LENGTH: 4-30 words is the sweet spot. Too short = under-specified. Too
  long = operator didn't commit.
- HOOK ELEMENTS: numbers, proper nouns, sensory details, time stamps.

What we penalize:
- VAGUE ABSTRACTIONS: "something cool", "vibes", "aesthetic", "general".
- AI-SLOP WORDS (same banned list as the linter): an intent with
  "cinematic" or "epic" in it means operator hasn't done the mental
  work yet.

Output: 0-100 score, letter grade, per-category hits, suggested tweaks.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import format_suggest, linter


# Weighted dimensions summing to 100.
GRADE_WEIGHTS: dict[str, int] = {
    "no_ai_slop": 15,
    "specificity": 22,
    "emotion": 15,
    "format_friendly": 14,
    "length_sweet_spot": 12,
    "concrete_hook": 12,
    "subject_named": 10,
}


# Words that score positively for emotion/valence.
EMOTION_WORDS = (
    "cope", "coping", "copium", "desperation", "desperate", "glee", "gloat",
    "disgust", "revulsion", "reverence", "defeat", "despair", "awe", "dread",
    "envy", "schadenfreude", "euphoria", "panic", "relief", "bliss", "grief",
    "regret", "rage", "resignation", "triumph", "smug", "contempt",
    "nostalgia", "longing", "dread", "malaise", "tired", "exhausted",
    "joyful", "bitter", "cold", "numb", "unbothered", "cooked", "over it",
)

# Concrete hooks: numbers, specific amounts, times, places.
HOOK_PATTERNS = (
    r"\b\d{1,3}am\b",                   # 3am
    r"\b\d{1,3}%\b",                    # 12%
    r"\b\$\d",                          # $420
    r"\b\d{4}\b",                       # 2026
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b",
)

# Abstract words that signal the operator hasn't done the thinking.
VAGUE_WORDS = (
    "something", "some", "thing", "vibes", "vibe", "aesthetic",
    "general", "generic", "overall", "feel", "mood board", "moodboard",
)

# Concrete subject proxies: nouns that usually name a real thing.
# (Crypto/X operator tilt — expand with operator's actual vocabulary.)
CONCRETE_SUBJECT_WORDS = (
    "trader", "farmer", "degen", "whale", "shill", "minter", "developer",
    "founder", "operator", "dev", "retail", "institution", "boomer", "zoomer",
    "wife", "girlfriend", "boyfriend", "kid", "parent", "boss", "intern",
    "character", "face", "guy", "man", "woman", "person", "subject",
    "token", "coin", "chart", "terminal", "laptop", "phone", "screen",
    "market", "exchange", "pool", "liquidation", "wallet", "address",
)


@dataclass
class IdeaGrade:
    score: int                      # 0-100
    weights: dict[str, int] = field(default_factory=dict)
    hits: dict[str, bool] = field(default_factory=dict)
    letter: str = "F"
    banned: list[str] = field(default_factory=list)
    vague: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    format_hits: list[str] = field(default_factory=list)

    def as_text(self) -> str:
        lines = [f"grade {self.letter}  score {self.score}/100"]
        for cat, w in self.weights.items():
            mark = "OK " if self.hits.get(cat) else "MISS"
            lines.append(f"  [{mark}] {cat} ({w} pts)")
        if self.banned:
            lines.append("  banned: " + ", ".join(self.banned))
        if self.vague:
            lines.append("  vague: " + ", ".join(self.vague))
        for s in self.suggestions:
            lines.append(f"  tip: {s}")
        return "\n".join(lines)


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def _has_any(text: str, tokens) -> list[str]:
    low = text.lower()
    return [t for t in tokens if t in low]


def grade(intent: str) -> IdeaGrade:
    banned = linter._find_banned(intent)
    vague = _has_any(intent, VAGUE_WORDS)
    emotion_hits = _has_any(intent, EMOTION_WORDS)
    subject_hits = _has_any(intent, CONCRETE_SUBJECT_WORDS)

    # Hook patterns: any regex match counts.
    hook_hits: list[str] = []
    low = intent.lower()
    for pat in HOOK_PATTERNS:
        m = re.search(pat, low, flags=re.IGNORECASE)
        if m:
            hook_hits.append(m.group(0))

    # Specificity = combination of concrete-subject + non-vague words.
    wordcount = len(_words(intent))
    specificity_ok = bool(subject_hits) and not vague and wordcount >= 4

    # Format-friendliness: does the intent trigger any format?
    picks = format_suggest.suggest(intent, top_n=3)
    format_hit_slugs = [p.slug for p in picks if p.score > 0]
    format_friendly = bool(format_hit_slugs)

    # Length sweet spot: 4-30 words.
    length_sweet_spot = 4 <= wordcount <= 30

    hits = {
        "no_ai_slop": len(banned) == 0,
        "specificity": specificity_ok,
        "emotion": bool(emotion_hits),
        "format_friendly": format_friendly,
        "length_sweet_spot": length_sweet_spot,
        "concrete_hook": bool(hook_hits),
        "subject_named": bool(subject_hits),
    }

    total = sum(w for cat, w in GRADE_WEIGHTS.items() if hits.get(cat))

    suggestions: list[str] = []
    if banned:
        suggestions.append("strip slop words — operator hasn't done the thinking")
    if not emotion_hits:
        suggestions.append(
            "name the emotion (cope, defeat, smug, dread...) — memes land on feelings"
        )
    if not subject_hits:
        suggestions.append(
            "name a subject (trader, chart, terminal, hoodie) — not an abstraction"
        )
    if not hook_hits:
        suggestions.append(
            "add a concrete hook: time ('3am'), number ('12%'), date, or amount"
        )
    if vague:
        suggestions.append(
            f"vague words present ({', '.join(vague)}) — commit to something specific"
        )
    if not length_sweet_spot:
        if wordcount < 4:
            suggestions.append("too short — add one specific detail")
        else:
            suggestions.append("too long — trim to one clean image-worthy beat")
    if not format_friendly:
        suggestions.append(
            "intent doesn't trigger any format — consider reshaping so /suggest can pick one"
        )

    letter = "A" if total >= 90 else "B" if total >= 80 else "C" if total >= 70 else "D" if total >= 60 else "F"
    return IdeaGrade(
        score=total,
        weights=dict(GRADE_WEIGHTS),
        hits=hits,
        letter=letter,
        banned=banned,
        vague=vague,
        suggestions=suggestions,
        format_hits=format_hit_slugs,
    )
