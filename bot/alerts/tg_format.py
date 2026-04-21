"""Shared Telegram formatting helpers.

Built 2026-04-17 to eliminate duplicated _fmt_price / direction-emoji /
bar-chart helpers that were copy-pasted across 4+ files with slightly
different logic (subtle bugs around HYPE's 4-decimal prices).

All TG messages that need price/pct/direction/bar formatting should
import from here. Additive module — no existing code depends on it
yet, callers migrate at their leisure.
"""
from __future__ import annotations

from typing import Iterable, Optional


def fmt_price(price: float) -> str:
    """Format price with precision scaled by magnitude.

    >=100 -> "1,234.56"; >=1 -> "12.3456"; >=0.001 -> "0.123456";
    else "0.1234567890".
    """
    if price is None:
        return "?"
    if price == 0:
        return "0"
    abs_p = abs(price)
    if abs_p >= 100:
        return f"{price:,.2f}"
    if abs_p >= 1.0:
        return f"{price:.4f}"
    if abs_p >= 0.001:
        return f"{price:.6f}"
    return f"{price:.10f}"


def fmt_pct(pct: float, show_sign: bool = True, decimals: int = 2) -> str:
    if show_sign:
        return f"{pct:+.{decimals}f}%"
    return f"{pct:.{decimals}f}%"


def fmt_usd(amount: float, show_sign: bool = True) -> str:
    if show_sign:
        sign = "+" if amount >= 0 else "-"
        return f"{sign}${abs(amount):,.2f}"
    return f"${amount:,.2f}"


def fmt_hold(seconds: float) -> str:
    """Format a duration: '4h32m', '15m', '45s'."""
    if seconds is None or seconds <= 0:
        return "0s"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    if hours > 0:
        return f"{hours}h{minutes:02d}m"
    if minutes > 0:
        return f"{minutes}m"
    return f"{int(seconds)}s"


def direction_emoji(side: str) -> str:
    """Green circle for BUY/LONG, red for SELL/SHORT. Empty for unknown."""
    s = (side or "").upper()
    if s in ("BUY", "LONG"):
        return "\U0001f7e2"  # green circle
    if s in ("SELL", "SHORT"):
        return "\U0001f534"  # red circle
    return ""


def direction_word(side: str) -> str:
    """Canonical 'LONG'/'SHORT' from any side input."""
    s = (side or "").upper()
    return "LONG" if s in ("BUY", "LONG") else "SHORT"


def tier_badge(tier: str) -> str:
    """Consistent emoji badge for a sniper/alert tier."""
    t = (tier or "").upper()
    return {
        "MICRO_SNIPER": "\U0001f52b",  # gun
        "SNIPER": "\U0001f3af",        # bullseye
        "PREMIUM": "\u26a1",            # bolt
        "STANDARD": "\U0001f4ca",      # bar chart
        "EXECUTE": "\U0001f3af",       # bullseye
        "WATCH": "\U0001f514",         # bell
    }.get(t, "")


def progress_bar(pct: float, width: int = 10, filled: str = "\u2588", empty: str = "\u2591") -> str:
    """Unicode bar for a 0-100 percentage value.

    Clamps out-of-range values. 10 chars default — fits in phone preview.
    """
    try:
        p = max(0.0, min(100.0, float(pct)))
    except Exception:
        p = 0.0
    fill_count = int(round(p / 100 * width))
    return filled * fill_count + empty * (width - fill_count)


def pnl_bar(
    unrealized: float,
    notional: float,
    width: int = 10,
) -> str:
    """Signed PnL bar. Positive fills right, negative fills left.

    Output looks like: `[░░░░░|█████]` for +50% win, `[██████|░░░░]`
    for a 40% loss. Bar is always width*2+3 chars including brackets.
    """
    if notional <= 0:
        return "[" + "\u2591" * width + "|" + "\u2591" * width + "]"
    pct = (unrealized / notional) * 100
    # Cap at +/- 100% for display purposes
    pct_capped = max(-100.0, min(100.0, pct))
    fill_count = int(round(abs(pct_capped) / 100 * width))
    filled = "\u2588" * fill_count
    empty = "\u2591" * (width - fill_count)
    if pct_capped >= 0:
        # Win side (right half): bar fills from center rightward.
        return "[" + ("\u2591" * width) + "|" + filled + empty + "]"
    # Loss side (left half): bar fills from center leftward.
    return "[" + empty + filled + "|" + ("\u2591" * width) + "]"


def distance_pct(current: float, target: float) -> float:
    """Signed % distance from current to target."""
    if current is None or current == 0 or target is None:
        return 0.0
    return (target - current) / current * 100


__all__ = [
    "fmt_price",
    "fmt_pct",
    "fmt_usd",
    "fmt_hold",
    "direction_emoji",
    "direction_word",
    "tier_badge",
    "progress_bar",
    "pnl_bar",
    "distance_pct",
]
