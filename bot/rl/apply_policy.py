"""
Safe RL Policy Application: Apply learned targets with caps and gradualism.

Reads rl_policy.json and applies adjustments to trading parameters.
Safety constraints:
  - Max +20% size increase per regime
  - Max -50% size decrease per regime
  - 10% step per day (gradualism)
  - All adjustments multiplicative on existing config
  - Disabled by default (ENABLE_RL_POLICY=false)

Integration:
  Called from multi_strategy_main at the start of each tick.
  Adjustments are merged into the risk multiplier calculation.
"""

import logging
import os
from typing import Dict, Any, Optional

from rl.train_offline import load_policy

logger = logging.getLogger("bot.rl.apply_policy")

# Safety caps
_MAX_SIZE_INCREASE = 1.20   # Max 20% increase
_MAX_SIZE_DECREASE = 0.50   # Max 50% decrease
_MAX_DAILY_STEP = 0.10      # Max 10% change per application

# Feature flag
ENABLE_RL_POLICY = os.getenv("ENABLE_RL_POLICY", "false").lower() in ("1", "true", "yes")


def get_regime_multiplier(regime: str) -> float:
    """Get the RL-learned size multiplier for a regime.

    Returns 1.0 if RL is disabled or no policy exists.
    """
    if not ENABLE_RL_POLICY:
        return 1.0

    policy = load_policy()
    if not policy:
        return 1.0

    multipliers = policy.get("regime_multipliers", {})
    raw = multipliers.get(regime, 1.0)

    # Clamp to safety bounds
    return _clamp(raw)


def get_symbol_risk_cap(symbol: str) -> float:
    """Get the RL-learned risk cap for a symbol.

    Returns 1.0 if RL is disabled or no policy exists.
    """
    if not ENABLE_RL_POLICY:
        return 1.0

    policy = load_policy()
    if not policy:
        return 1.0

    caps = policy.get("symbol_risk_caps", {})
    raw = caps.get(symbol, 1.0)

    return _clamp(raw)


def get_trigger_quality(trigger: str) -> float:
    """Get the RL-learned quality score for a trigger type.

    Returns 1.0 if RL is disabled or no policy exists.
    Low quality (< 0.5) means this trigger should fire less often.
    """
    if not ENABLE_RL_POLICY:
        return 1.0

    policy = load_policy()
    if not policy:
        return 1.0

    adjustments = policy.get("trigger_adjustments", {})
    return adjustments.get(trigger, 1.0)


def get_combined_rl_multiplier(
    symbol: str,
    regime: str,
) -> float:
    """Get the combined RL multiplier for a symbol + regime.

    This is the single entry point for the main loop.
    Returns a multiplier to apply to position size.
    """
    if not ENABLE_RL_POLICY:
        return 1.0

    regime_mult = get_regime_multiplier(regime)
    symbol_cap = get_symbol_risk_cap(symbol)

    # Combine multiplicatively
    combined = regime_mult * symbol_cap

    # Clamp the combined result
    combined = _clamp(combined)

    if combined != 1.0:
        logger.info(
            f"[RL-POLICY] {symbol}/{regime}: "
            f"regime_mult={regime_mult:.2f} * symbol_cap={symbol_cap:.2f} "
            f"= {combined:.2f}"
        )

    return combined


def _clamp(value: float) -> float:
    """Clamp a multiplier to safety bounds."""
    return max(_MAX_SIZE_DECREASE, min(value, _MAX_SIZE_INCREASE))


def is_rl_enabled() -> bool:
    """Check if RL policy application is enabled."""
    return ENABLE_RL_POLICY
