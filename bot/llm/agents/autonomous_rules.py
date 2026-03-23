"""
Autonomous Trading Rules: When agents can initiate trades WITHOUT external signals.

The original system is REACTIVE — it waits for signals.
Alpha Quants are PROACTIVE — they trade on conviction when conditions align.

This module defines when the Trade Agent and Scout Agent can form and execute
theses autonomously (without waiting for a signal from the ensemble).

Core Philosophy:
- Risk is capped (0.5x normal size)
- Regime must be favorable (not range/panic/unknown/low_liquidity)
- Scout must confirm thesis is forming (high readiness)
- Conviction must be high (0.65+)
- Portfolio must have room (leverage < 5.0)

Autonomous mode trades are labeled as such in the decision ledger for separate analysis.
"""

import logging
from dataclasses import dataclass
from typing import Optional
from enum import Enum

logger = logging.getLogger("bot.llm.agents.autonomous_rules")


# ─────────────────────────────────────────────────────────────────────────────
# AUTONOMOUS INITIATION CONDITIONS
# ─────────────────────────────────────────────────────────────────────────────

class AutonomousTradeType(str, Enum):
    """Type of autonomous trade initiation."""
    SIGNAL_BASED = "signal"  # Traditional: ensemble signal triggered
    SCOUT_READY = "scout_ready"  # Scout flagged setup as READY
    CONVICTION = "conviction"  # Trade Agent has high conviction, forms thesis
    FORMATION = "formation"  # Setup is forming in real-time


@dataclass
class AutonomousContext:
    """Context for autonomous trade decision."""
    symbol: str
    current_regime: str
    regime_confidence: float
    regime_momentum: str  # "strengthening" | "stable" | "weakening"
    portfolio_leverage: float  # Current portfolio leverage
    open_positions_count: int  # How many trades are open?
    recent_lessons: list  # What did we learn from recent trades?
    scout_flagged: bool  # Did Scout flag this symbol as ready?
    scout_pre_thesis_confidence: float  # Scout's thesis confidence if present


# ─────────────────────────────────────────────────────────────────────────────
# RULES
# ─────────────────────────────────────────────────────────────────────────────

def can_initiate_autonomously(context: AutonomousContext) -> tuple[bool, Optional[str]]:
    """Determine if autonomous trading is allowed in current context.

    Returns:
        (is_allowed, reason_if_denied)
    """

    # Rule 1: Regime must be favorable for autonomous trading
    forbidden_regimes = ["range", "panic", "low_liquidity", "news_dislocation", "unknown"]
    if context.current_regime in forbidden_regimes:
        return False, f"Regime '{context.current_regime}' forbids autonomous trading"

    # Rule 2: Portfolio must have room
    if context.portfolio_leverage >= 5.0:
        return False, f"Portfolio leverage {context.portfolio_leverage:.1f}x too high (max 5.0)"

    # Rule 3: Too many open positions
    if context.open_positions_count >= 5:
        return False, f"Too many open positions ({context.open_positions_count}, max 5)"

    # Rule 4: Regime must be stable or strengthening (not weakening)
    if context.regime_momentum == "weakening":
        return False, "Regime momentum weakening — wait for clarity"

    # Rule 5: Confidence in regime must be reasonably high
    if context.regime_confidence < 0.55:
        return False, f"Regime confidence too low ({context.regime_confidence:.1%})"

    # All checks passed
    return True, None


def get_autonomous_size_multiplier(context: AutonomousContext) -> float:
    """Calculate position size multiplier for autonomous trades.

    Autonomous trades are risky (no signal confirmation), so we size down.
    The multiplier is applied to baseline size (1.0x).

    Returns: Multiplier (0.0-0.5)
    """

    # Base: 0.5x (half of normal)
    multiplier = 0.5

    # Boost if scout confirmed
    if context.scout_flagged:
        multiplier += 0.1  # → 0.6x

    # Boost if regime strong
    if context.regime_confidence > 0.75:
        multiplier += 0.05  # → 0.65x

    # Boost if regime strengthening
    if context.regime_momentum == "strengthening":
        multiplier += 0.05  # → 0.70x

    # Cap at 0.7x
    multiplier = min(multiplier, 0.7)

    # Reduce if scout confidence low
    if context.scout_flagged and context.scout_pre_thesis_confidence < 0.55:
        multiplier -= 0.2  # → 0.45x or lower

    # Don't go below 0.3x
    multiplier = max(multiplier, 0.3)

    logger.info(f"[AUTONOMOUS] Size multiplier for {context.symbol}: {multiplier:.2f}x")
    return multiplier


def get_autonomous_confidence_ceiling(context: AutonomousContext) -> float:
    """Maximum confidence allowed for autonomous theses.

    Autonomous theses can't be TOO confident (we have no signal confirmation).
    This prevents the Trade Agent from being overconfident.

    Returns: Max confidence (0.0-1.0)
    """

    # Base ceiling: 0.70
    ceiling = 0.70

    # If Scout confirmed this is ready, raise ceiling slightly
    if context.scout_flagged and context.scout_pre_thesis_confidence > 0.65:
        ceiling = 0.75  # Can be a bit more confident

    # If regime very strong, raise ceiling
    if context.regime_confidence > 0.85 and context.regime_momentum == "strengthening":
        ceiling = 0.72

    # If we've had losses recently, lower ceiling
    if context.recent_lessons:
        losses_mentioned = sum(1 for lesson in context.recent_lessons if "loss" in lesson.lower())
        if losses_mentioned >= 2:
            ceiling = 0.65

    return ceiling


# ─────────────────────────────────────────────────────────────────────────────
# SCOUT READINESS SCORING
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_scout_readiness(
    scout_output: dict,
    current_price: float,
    regime_confidence: float,
) -> tuple[float, Optional[str]]:
    """Evaluate if Scout's preparation is ready for Trade Agent action.

    Returns:
        (readiness_score 0-1, reason_if_not_ready)
    """

    # Must have a watchlist entry for this symbol
    if "watchlist" not in scout_output or not scout_output["watchlist"]:
        return 0.0, "No watchlist entry"

    # Examine the watchlist entry
    entry = scout_output["watchlist"][0] if scout_output["watchlist"] else None
    if not entry:
        return 0.0, "Empty watchlist"

    score = 0.0

    # Priority matters
    if entry.get("priority") == "high":
        score += 0.3
    elif entry.get("priority") == "medium":
        score += 0.15

    # Distance to key level matters (closer = more ready)
    distance_pct = entry.get("distance_pct", 999)
    if distance_pct < 0.5:
        score += 0.25  # Very close
    elif distance_pct < 1.0:
        score += 0.15  # Close
    elif distance_pct < 2.0:
        score += 0.08  # Approaching

    # Pre-thesis confidence
    pre_thesis_conf = entry.get("pre_thesis_confidence", 0.5)
    if pre_thesis_conf > 0.65:
        score += 0.25
    elif pre_thesis_conf > 0.55:
        score += 0.12

    # Conditions met?
    if entry.get("conditions_needed"):
        # Vague conditions = less ready
        conditions = entry["conditions_needed"]
        if len(conditions) > 0 and all(c.lower() in ["buy", "sell", "long", "short"] for c in [conditions]):
            # All conditions met
            score += 0.15
        else:
            # Some conditions still needed
            score += 0.05

    # Readiness assessment
    if score >= 0.70:
        return score, None  # READY
    elif score >= 0.50:
        return score, f"Not yet ready (score {score:.1%})"
    else:
        return score, f"Too early (score {score:.1%})"


# ─────────────────────────────────────────────────────────────────────────────
# THESIS FORMATION GUIDANCE (for Trade Agent)
# ─────────────────────────────────────────────────────────────────────────────

def autonomous_thesis_template() -> str:
    """Template for autonomous thesis formation.

    Trade Agent uses this when forming theses without signals.
    """
    return """## AUTONOMOUS THESIS FORMATION TEMPLATE

When you form a thesis without a signal, structure it as:

**Setup Observation**: What pattern are you seeing? (e.g., "RSI recovering from 28, volume expanding")
**Regime Support**: How does current regime support this? (e.g., "Trend regime with momentum strengthening")
**Price Prediction**: Where will price go? (e.g., "SOL likely +3-4% within next 6 hours")
**Conviction Components**:
  - Direction confidence: 0-1 (are you sure about the direction?)
  - Setup confidence: 0-1 (is the pattern real?)
  - Timing confidence: 0-1 (is NOW the right time?)
**Risk Factors**: What could invalidate this thesis? (cite 2-3 risks)
**Exit Plan**: When will you exit? (cite price levels or time-based)

**Size Constraint**: Position size capped at 0.5-0.7x normal (autonomy carries more risk)
**Confidence Constraint**: Overall confidence capped at 0.70 (no signal = less certain)
**Approval Gate**: Critic Agent will review — expect scrutiny

Example:
{
  "thesis": "SOL forming mean-reversion: RSI dropped to 28 (oversold), volume spike confirmed washout. Trend regime strengthening (ADX 24→28). Support at 24.40 holds. Likely bounce to 25.20 within 4h.",
  "direction_confidence": 0.72,
  "setup_confidence": 0.65,
  "timing_confidence": 0.68,
  "risks": ["BTC could dump again", "Volume could fade"],
  "exit_plan": "TP1 at 25.20 (60%), trail from there"
}
"""


# ─────────────────────────────────────────────────────────────────────────────
# LOGGING & METRICS
# ─────────────────────────────────────────────────────────────────────────────

class AutonomousMetrics:
    """Track autonomous trading performance."""

    def __init__(self):
        self.autonomous_trades = 0
        self.autonomous_wins = 0
        self.autonomous_losses = 0

    def record_autonomous_result(self, pnl: float) -> None:
        """Record outcome of an autonomous trade."""
        self.autonomous_trades += 1
        if pnl > 0:
            self.autonomous_wins += 1
        else:
            self.autonomous_losses += 1

    def win_rate(self) -> float:
        """Win rate on autonomous trades."""
        if self.autonomous_trades == 0:
            return 0.5
        return self.autonomous_wins / self.autonomous_trades

    def __repr__(self) -> str:
        wr = self.win_rate()
        return f"AutonomousMetrics(trades={self.autonomous_trades}, WR={wr:.1%})"


__all__ = [
    "AutonomousTradeType",
    "AutonomousContext",
    "AutonomousMetrics",
    "can_initiate_autonomously",
    "get_autonomous_size_multiplier",
    "get_autonomous_confidence_ceiling",
    "evaluate_scout_readiness",
    "autonomous_thesis_template",
]
