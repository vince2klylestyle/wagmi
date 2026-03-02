"""
Liquidity Guard: Pre-trade liquidity and market health validation.

Rejects entries in dead markets (ultra-low volume) and applies
sizing penalties for extreme funding rates or thin order books.

Checks:
  1. Volume dead market: volume_ratio < 0.3 → reject
  2. Extreme funding: abs(rate) > 0.05% → reduce size by 30%
  3. ATR collapse: atr_ratio < 0.3 → reject (no volatility = no edge)
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger("bot.execution.liquidity_guard")


@dataclass
class LiquidityResult:
    """Result of liquidity validation."""
    can_trade: bool
    size_multiplier: float  # 1.0 = normal, <1.0 = reduced
    reason: str


def validate_liquidity(
    symbol: str,
    volume_ratio: float = 1.0,
    funding_rate: float = 0.0,
    atr_ratio: float = 1.0,
) -> LiquidityResult:
    """Validate market liquidity conditions before opening a trade.

    Args:
        symbol: Trading pair symbol
        volume_ratio: Current volume / 20-period avg volume
        funding_rate: Current funding rate (decimal, e.g., 0.0001 = 0.01%)
        atr_ratio: Current ATR / historical avg ATR

    Returns:
        LiquidityResult with can_trade, size_multiplier, reason
    """
    size_mult = 1.0
    warnings = []

    # Dead market: volume too low to trade safely
    if volume_ratio < 0.3:
        logger.info(
            f"[LIQUIDITY][{symbol}] Dead market: volume_ratio={volume_ratio:.2f} < 0.3"
        )
        return LiquidityResult(
            can_trade=False,
            size_multiplier=0.0,
            reason=f"dead_market: volume={volume_ratio:.2f}x avg",
        )

    # Low volume: reduce size
    if volume_ratio < 0.6:
        size_mult *= 0.7
        warnings.append(f"low_vol={volume_ratio:.2f}x")

    # Extreme funding: indicates crowded trade
    abs_funding = abs(funding_rate)
    if abs_funding > 0.0005:  # > 0.05%
        size_mult *= 0.7
        warnings.append(f"extreme_funding={funding_rate:.5f}")
    elif abs_funding > 0.0003:  # > 0.03%
        size_mult *= 0.85
        warnings.append(f"high_funding={funding_rate:.5f}")

    # ATR collapse: no volatility = no edge
    if atr_ratio < 0.3:
        logger.info(
            f"[LIQUIDITY][{symbol}] ATR collapsed: atr_ratio={atr_ratio:.2f} < 0.3"
        )
        return LiquidityResult(
            can_trade=False,
            size_multiplier=0.0,
            reason=f"atr_collapse: atr_ratio={atr_ratio:.2f}",
        )

    if warnings:
        reason = "liquidity_adjusted: " + ", ".join(warnings)
    else:
        reason = "ok"

    return LiquidityResult(
        can_trade=True,
        size_multiplier=size_mult,
        reason=reason,
    )
