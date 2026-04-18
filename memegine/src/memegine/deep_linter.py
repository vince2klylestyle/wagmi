"""Deep linter — extends the base linter with a 0-100 craft-coverage score
and a detailed breakdown of what a prompt is missing.

The base linter answers "does this prompt avoid AI-slop?" — binary pass/fail.
The deep linter answers "how specific is this prompt?" — quantitative, so
operator can see the score climb as they iterate.

No new deps. Pure python over the regex/keyword helpers in `linter`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import linter


# Each dimension contributes weight points toward a max of 100.
# Weights reflect what actually moves the needle on Grok output quality.
CRAFT_WEIGHTS: dict[str, int] = {
    "no_banned_words": 20,     # biggest signal — banned words actively hurt
    "lens_or_stock": 16,       # named optics or film is the #1 craft lever
    "lighting": 14,
    "time_or_condition": 12,
    "composition": 12,
    "location_or_subject": 10, # names a place or a concrete subject
    "wardrobe_or_props": 8,    # only helpful for photoreal; scored lightly
    "negative_terms": 8,       # explicit "no X" at end of prompt
}


LOCATION_HINTS = (
    # cities / rooms / spaces worth naming by label — expand as needed.
    "nyc", "new york", "tokyo", "shibuya", "shinjuku", "la ", "los angeles",
    "london", "paris", "seoul", "singapore", "hong kong",
    "kitchen", "bedroom", "bathroom", "rooftop", "parking garage",
    "street", "alley", "subway", "train", "trading floor", "desk",
    "office", "bar", "diner", "convenience store", "bodega",
    "hallway", "stairwell", "backseat", "fire escape", "motel",
)

WARDROBE_HINTS = (
    "hoodie", "t-shirt", "jacket", "leather", "trench", "button-up",
    "suit", "tie", "dress", "overcoat", "puffer", "windbreaker", "scarf",
    "cap", "hat", "glasses", "sunglasses", "watch on wrist",
)

NEGATIVE_PROMPT_HINTS = (
    "no extra fingers", "no warped text", "no logo watermarks", "no lens flare",
    "no lens flares", "no cgi", "no text overlay", "no subtitles",
    "no duplicate limbs", "no background blur", "no artificial blur",
)


@dataclass
class CraftScore:
    score: int                 # 0-100
    weights: dict[str, int] = field(default_factory=dict)   # category -> weight available
    hits: dict[str, bool] = field(default_factory=dict)     # category -> satisfied
    base_lint_ok: bool = True
    banned: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)    # operator-facing tips

    def as_text(self) -> str:
        lines = [f"craft score: {self.score}/100"]
        for cat, w in self.weights.items():
            mark = "OK " if self.hits.get(cat) else "MISS"
            lines.append(f"  [{mark}] {cat} ({w} pts)")
        if self.banned:
            lines.append("  banned words: " + ", ".join(self.banned))
        for s in self.suggestions:
            lines.append(f"  tip: {s}")
        return "\n".join(lines)


def _has_location(text: str) -> bool:
    return linter._contains_any(text, LOCATION_HINTS)


def _has_wardrobe(text: str) -> bool:
    return linter._contains_any(text, WARDROBE_HINTS)


def _has_negative_section(text: str) -> bool:
    low = text.lower()
    # Explicit "no X" phrases at end, or our specific negative hint set.
    if linter._contains_any(text, NEGATIVE_PROMPT_HINTS):
        return True
    # Heuristic: a "no X, no Y" clause anywhere in the last 30% of prompt.
    tail = low[int(len(low) * 0.7):]
    return " no " in tail and tail.count(" no ") >= 2


def score(prompt: str, *, kind: str = "image") -> CraftScore:
    """Score a prompt 0-100 across weighted craft dimensions."""
    base = linter.lint(prompt, kind=kind)
    banned = [i.message.split("'")[1] for i in base.errors if "banned word" in i.message]

    low = prompt  # keep original case for error display; helpers lowercase internally
    hits = {
        "no_banned_words": len(banned) == 0,
        "lens_or_stock": base.hits.get("lens_or_stock", False),
        "lighting": base.hits.get("lighting", False),
        "time_or_condition": base.hits.get("time_or_condition", False),
        "composition": base.hits.get("composition", False),
        "location_or_subject": _has_location(low),
        "wardrobe_or_props": _has_wardrobe(low),
        "negative_terms": _has_negative_section(low),
    }

    total = 0
    for cat, w in CRAFT_WEIGHTS.items():
        if hits.get(cat):
            total += w

    suggestions: list[str] = []
    if not hits["no_banned_words"]:
        suggestions.append(
            "remove banned superlatives — they mark output as AI-generated"
        )
    if not hits["lens_or_stock"]:
        suggestions.append(
            "name a lens or film stock (e.g. '35mm f/1.4', 'Portra 400', 'Cinestill 800T')"
        )
    if not hits["lighting"]:
        suggestions.append(
            "name the lighting (e.g. 'hard window light', 'neon + tungsten mix')"
        )
    if not hits["time_or_condition"]:
        suggestions.append(
            "add time/weather (e.g. 'dusk', '3am', 'overcast', 'foggy street')"
        )
    if not hits["composition"]:
        suggestions.append(
            "name the composition rule ('rule of thirds, subject left', 'centered close-up')"
        )
    if not hits["location_or_subject"]:
        suggestions.append(
            "name a location or a concrete subject (room, city, object) — avoid abstract scenes"
        )
    if not hits["wardrobe_or_props"] and kind == "image":
        suggestions.append(
            "for photoreal: name wardrobe or props (adds specificity, kills the AI-avatar feel)"
        )
    if not hits["negative_terms"]:
        suggestions.append(
            "end with a 'no X, no Y' clause (e.g. 'no extra fingers, no warped text, no lens flare')"
        )

    if kind == "motion":
        move_present = any(
            e.message.startswith("motion prompt") for e in base.errors
        )
        # If the motion-specific error fired, base.errors already flagged it;
        # we don't double-penalize since motion-check is a pass/fail gate.
        if move_present:
            suggestions.append(
                "motion prompt must name ONE camera move (push-in, orbit, rack focus, lockoff, Ken Burns, whip pan)"
            )

    return CraftScore(
        score=total,
        weights=dict(CRAFT_WEIGHTS),
        hits=hits,
        base_lint_ok=base.ok,
        banned=banned,
        suggestions=suggestions,
    )


def grade(score_value: int) -> str:
    """Turn a 0-100 score into an A-F letter grade for quick human scan."""
    if score_value >= 90:
        return "A"
    if score_value >= 80:
        return "B"
    if score_value >= 70:
        return "C"
    if score_value >= 60:
        return "D"
    return "F"
