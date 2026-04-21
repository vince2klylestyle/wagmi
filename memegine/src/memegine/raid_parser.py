"""Raid syntax parser — terse command grammar for TG messages.

Examples the operator speaks fluently:

    <tweet-url> raid kilroy
    <tweet-url> spongify
    <tweet-url> spongify raid spong
    <tweet-url> motion video + caption
    <tweet-url> kilroy
    <tweet-url> video
    <tweet-url> motion
    <tweet-url>   (← no keywords = show the tap-card, existing behavior)

This parser is deliberately forgiving — word order doesn't matter,
casing doesn't matter, extra words are ignored.

Grammar:
    URL       = twitter/x status URL
    BRAND     = kilroy | motion | spong
    ACTION    = raid | spongify | kilroy | spong(ify) | video | still
                | image | caption | brief
    EXTRAS    = "+ caption" | with-caption

Routing:
    has BRAND keyword        → use that brand
    has 'spongify'           → face-swap the tweet author
    has 'raid'               → run raid pack (flow_post.raid)
    has 'video'              → video brief (kind=video)
    has 'kilroy' keyword     → kilroy composite over tweet media (if any)
    otherwise + URL only     → default: tap-card flow
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:twitter|x)\.com/[^/\s]+/status/\d+",
    re.IGNORECASE,
)

BRANDS = {"kilroy", "motion", "spong"}

ACTION_KEYWORDS = {
    "raid": "raid",
    "spongify": "spongify",
    "sponge": "spongify",
    "video": "video",
    "vid": "video",
    "still": "still",
    "image": "still",
    "img": "still",
    "caption": "caption",
    "cap": "caption",
    "brief": "brief",
}


@dataclass
class RaidCommand:
    """Parsed structure of a raid-syntax message."""
    raw: str
    url: Optional[str] = None
    brand: Optional[str] = None          # kilroy / motion / spong
    brand_explicit: bool = False         # did user TYPE a brand word?
    actions: list[str] = field(default_factory=list)
    include_caption: bool = False
    custom_note: str = ""                # free-text leftover

    @property
    def is_raid_command(self) -> bool:
        """True if the operator gave ANY keyword (brand or action).

        Bare URL — no raid-command → falls through to tap-card handler.
        """
        return bool(self.url) and (bool(self.actions) or self.brand_explicit)

    def as_summary(self) -> str:
        parts = []
        if self.brand:
            parts.append(f"brand={self.brand}")
        if self.actions:
            parts.append(f"actions={','.join(self.actions)}")
        if self.include_caption:
            parts.append("+caption")
        return " ".join(parts) or "(url only — default card flow)"


def parse(text: str) -> RaidCommand:
    """Parse a TG message into a RaidCommand."""
    cmd = RaidCommand(raw=text or "")
    if not text:
        return cmd
    # URL first
    m = _URL_RE.search(text)
    if m:
        cmd.url = m.group(0)
        text = text.replace(m.group(0), "")
    # Tokenize what's left
    tokens = [t.strip().lower() for t in re.split(r"\s+", text) if t.strip()]
    leftover: list[str] = []
    for tok in tokens:
        if tok in BRANDS:
            cmd.brand = tok
            cmd.brand_explicit = True
            continue
        mapped = ACTION_KEYWORDS.get(tok)
        if mapped and mapped not in cmd.actions:
            cmd.actions.append(mapped)
            continue
        if tok in {"+", "with", "plus", "and", "&"}:
            continue
        leftover.append(tok)
    # +caption shorthand
    if "caption" not in cmd.actions and any(
        " + caption" in text.lower() or "+caption" in text.lower()
        for text in [cmd.raw.lower()]
    ):
        cmd.actions.append("caption")
    if "caption" in cmd.actions:
        cmd.include_caption = True
    cmd.custom_note = " ".join(leftover).strip()
    return cmd


def _normalize(cmd: RaidCommand, *, default_brand: Optional[str] = None) -> RaidCommand:
    """Fill in sensible defaults on an otherwise-parsed command."""
    # If brand typed explicitly but no action, default to a still brief
    if cmd.brand_explicit and not cmd.actions:
        cmd.actions = ["still"]
    # Fill in brand from default if none was typed — but brand_explicit stays
    # False so is_raid_command still returns False for bare URLs.
    if cmd.brand is None and default_brand:
        cmd.brand = default_brand
    return cmd


def parse_and_normalize(text: str, *, default_brand: Optional[str] = None) -> RaidCommand:
    return _normalize(parse(text), default_brand=default_brand)
