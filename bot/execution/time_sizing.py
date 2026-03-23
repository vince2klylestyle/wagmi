"""
Time-aware position sizing multipliers.

Data-driven session sizing from 90-day backtest:
- Best sessions: Asia early (03-05 UTC, 86% WR), Late (21-22 UTC, 90% WR)
- Worst: Midnight (00:00, 23:00 UTC, 20% WR)
- Weekends: reduced (lower liquidity, wider spreads)

These are multiplicative on top of normal sizing, NOT replacements.
All multipliers are env-configurable for tuning.
"""

import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger("bot.execution.time_sizing")

# Env-configurable multipliers
WEEKEND_SIZE_MULTIPLIER = float(os.getenv("WEEKEND_SIZE_MULTIPLIER", "0.5"))

# Data-driven session multipliers (from 90d backtest hour-of-day analysis)
# Keys are UTC hours. Values are sizing multipliers (1.0 = normal, >1.0 = size up, <1.0 = size down)
_SESSION_MULTIPLIERS = {
    # Midnight danger zone — 20% WR, -$134 PnL
    0: 0.5,
    23: 0.5,
    # Asia early — moderate
    1: 0.8,
    2: 0.8,
    # Asia prime — 86% WR, +$1,438 PnL (BEST SESSION)
    3: 1.15,
    4: 1.0,
    5: 1.15,
    # Europe open — moderate to good
    6: 0.8,
    7: 0.9,
    8: 0.9,
    9: 1.0,
    10: 0.7,   # 33% WR, -$127 in 90d — still below average
    11: 0.9,
    # US session — solid
    12: 0.8,   # Was 25% WR but small sample (8 trades). Moderate reduction, not aggressive.
    13: 1.1,
    14: 1.15,  # 80% WR, +$143 in 90d
    15: 1.0,
    16: 0.7,   # 0% WR, -$97 in 90d — reduce
    17: 1.0,
    # Late session — strong (90% WR at 21-22)
    18: 0.6,   # 0% WR, -$76 in 90d
    19: 1.0,
    20: 1.15,  # +$983 PnL despite 40% WR — big winners here
    21: 1.2,   # Best hour: +$1,219 from 4 trades
    22: 1.1,
}


def get_time_multiplier(now: datetime = None) -> float:
    """Return the combined time-based sizing multiplier.

    Returns a float in (0.0, 2.0] that should be multiplied into
    the position quantity before opening.

    Args:
        now: Override for testing. Defaults to current UTC time.

    Returns:
        Combined multiplier (weekend * session, whichever apply).
    """
    if now is None:
        now = datetime.now(timezone.utc)

    multiplier = 1.0
    reasons = []

    # Weekend check (Saturday=5, Sunday=6)
    if now.weekday() in (5, 6):
        multiplier *= WEEKEND_SIZE_MULTIPLIER
        reasons.append(f"weekend({WEEKEND_SIZE_MULTIPLIER:.2f}x)")

    # Session-aware hour multiplier (data-driven from backtest)
    session_mult = _SESSION_MULTIPLIERS.get(now.hour, 1.0)
    if session_mult != 1.0:
        multiplier *= session_mult
        reasons.append(f"session_h{now.hour}({session_mult:.2f}x)")

    if reasons:
        logger.info(
            f"[TIME-SIZE] Applying time multiplier: {multiplier:.2f}x "
            f"({', '.join(reasons)})"
        )

    return multiplier


def is_weekend(now: datetime = None) -> bool:
    """Check if current time is weekend (Saturday or Sunday UTC)."""
    if now is None:
        now = datetime.now(timezone.utc)
    return now.weekday() in (5, 6)


def is_low_liquidity_hours(now: datetime = None) -> bool:
    """Check if current time is in low-liquidity window."""
    if now is None:
        now = datetime.now(timezone.utc)
    return now.hour in _LOW_LIQ_HOURS
