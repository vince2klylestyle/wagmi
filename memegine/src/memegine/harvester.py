"""Handle harvester — discover target accounts for the watchlist.

Two modes:
    harvest_by_query(query) — X search results → handles → filter → add
    harvest_by_handles(seeds, bio_contains=..., ...) — enrich a seed list

Primary use-case the operator described:
    "target small users that use the FOMO trading platform — accumulate
    the floor of our token. few thousand to low-5-figure followers."

Translated to mechanics:
    query = "fomo.xyz"  (or "pump.fun", or the specific platform)
    follower_min = 2_000
    follower_max = 50_000
    verified_only = False
    bio_contains = ["trader", "degen", ""] (optional allow-list)

Every matched handle is added to ops_db.watchlist so the watcher picks
them up on the next cycle.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from . import ops_db


@dataclass
class HarvestFilter:
    follower_min: int = 2_000
    follower_max: int = 50_000
    follower_max_include_above: bool = False
    verified_only: bool = False
    exclude_verified: bool = False
    bio_any_of: list[str] = field(default_factory=list)   # substring match, OR
    bio_none_of: list[str] = field(default_factory=list)  # substring match, NONE
    exclude_handles: list[str] = field(default_factory=list)

    def matches(self, info: dict) -> tuple[bool, str]:
        """Return (pass, reason-if-rejected)."""
        f = info.get("followers", 0)
        if f < self.follower_min:
            return False, f"followers {f:,} < min {self.follower_min:,}"
        if not self.follower_max_include_above and f > self.follower_max:
            return False, f"followers {f:,} > max {self.follower_max:,}"
        if self.verified_only and not info.get("verified"):
            return False, "not verified"
        if self.exclude_verified and info.get("verified"):
            return False, "verified (excluded)"
        bio = (info.get("bio") or "").lower()
        if self.bio_any_of:
            if not any(token.lower() in bio for token in self.bio_any_of):
                return False, "bio has none of: " + ", ".join(self.bio_any_of)
        if self.bio_none_of:
            for token in self.bio_none_of:
                if token.lower() in bio:
                    return False, f"bio contains excluded: {token}"
        handle = (info.get("handle") or "").lower()
        if handle in {h.lower() for h in self.exclude_handles}:
            return False, "handle on exclude list"
        return True, ""


@dataclass
class HarvestRecord:
    handle: str
    accepted: bool
    reason: str = ""
    followers: int = 0
    following: int = 0
    bio: str = ""
    verified: bool = False


@dataclass
class HarvestResult:
    query: str
    candidates: int = 0
    accepted: int = 0
    records: list[HarvestRecord] = field(default_factory=list)

    def as_text(self) -> str:
        lines = [
            f"harvest: {self.query!r}",
            f"  candidates: {self.candidates}",
            f"  accepted:   {self.accepted}",
        ]
        accepted = [r for r in self.records if r.accepted]
        rejected = [r for r in self.records if not r.accepted]
        if accepted:
            lines.append("  accepted handles:")
            for r in accepted:
                lines.append(
                    f"    @{r.handle:<20}  {r.followers:>7,} followers  "
                    f"{'✓' if r.verified else ' '}  {r.bio[:60]}"
                )
        if rejected:
            lines.append(f"  rejected: {len(rejected)}")
            # Show first 5 with reasons for debugging.
            for r in rejected[:5]:
                lines.append(
                    f"    @{r.handle:<20}  {r.followers:>7,}  → {r.reason}"
                )
            if len(rejected) > 5:
                lines.append(f"    ... +{len(rejected) - 5} more")
        return "\n".join(lines)


def harvest_by_query(
    query: str,
    filt: Optional[HarvestFilter] = None,
    *,
    limit_candidates: int = 60,
    add_to_watchlist: bool = True,
) -> HarvestResult:
    """Search X for `query`, filter result authors by HarvestFilter,
    optionally add matches to the watchlist."""
    from . import x_playwright
    filt = filt or HarvestFilter()
    result = HarvestResult(query=query)
    handles = x_playwright.search_handles(query, limit=limit_candidates)
    result.candidates = len(handles)
    for h in handles:
        if h.lower() in {x.lower() for x in filt.exclude_handles}:
            result.records.append(HarvestRecord(handle=h, accepted=False, reason="excluded"))
            continue
        try:
            info = x_playwright.handle_info(h)
        except Exception as exc:
            result.records.append(HarvestRecord(handle=h, accepted=False,
                                                reason=f"info failed: {exc}"))
            continue
        if not info:
            result.records.append(HarvestRecord(handle=h, accepted=False, reason="no info"))
            continue
        ok, reason = filt.matches(info)
        rec = HarvestRecord(
            handle=h, accepted=ok, reason=reason,
            followers=info.get("followers", 0),
            following=info.get("following", 0),
            bio=info.get("bio", ""),
            verified=bool(info.get("verified", False)),
        )
        result.records.append(rec)
        if ok:
            result.accepted += 1
            if add_to_watchlist:
                ops_db.watchlist_add(
                    h, note=f"harvest: {query} ({info.get('followers', 0):,}f)",
                )
    return result


def harvest_by_handles(
    seeds: list[str],
    filt: Optional[HarvestFilter] = None,
    *,
    add_to_watchlist: bool = True,
) -> HarvestResult:
    """Enrich + filter an already-known list of handles.

    Useful for: "I have 80 handles from a leaderboard scrape — keep only
    the ones with 3k-50k followers and 'trader' in bio."
    """
    from . import x_playwright
    filt = filt or HarvestFilter()
    result = HarvestResult(query=f"seed:{len(seeds)}")
    result.candidates = len(seeds)
    for h in seeds:
        h = h.lstrip("@").strip().lower()
        if not h:
            continue
        try:
            info = x_playwright.handle_info(h)
        except Exception as exc:
            result.records.append(HarvestRecord(handle=h, accepted=False,
                                                reason=f"info failed: {exc}"))
            continue
        if not info:
            result.records.append(HarvestRecord(handle=h, accepted=False, reason="no info"))
            continue
        ok, reason = filt.matches(info)
        rec = HarvestRecord(
            handle=h, accepted=ok, reason=reason,
            followers=info.get("followers", 0),
            following=info.get("following", 0),
            bio=info.get("bio", ""),
            verified=bool(info.get("verified", False)),
        )
        result.records.append(rec)
        if ok:
            result.accepted += 1
            if add_to_watchlist:
                ops_db.watchlist_add(h, note=f"harvest-seed ({info.get('followers', 0):,}f)")
    return result
