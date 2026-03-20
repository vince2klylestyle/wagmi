"""
TIER 3.6: Adaptive Confidence Thresholds

Dynamically adjusts confidence floors based on current market conditions.

Instead of fixed floor (65%), adjust based on:
- Current volatility: High vol → raise floor (less reliable signals)
- Time of day: Asian hours less reliable → raise floor
- Recent performance: Winning streak → lower floor (on edge)
- Regime transition: Changing regimes → raise floor (uncertain)

Expected impact: +0.1-0.3% daily by trading when conditions favor edge
"""

import logging
from typing import Dict, Optional
from datetime import datetime
import time

logger = logging.getLogger("bot.llm.adaptive_confidence")


class AdaptiveConfidenceThresholds:
    """
    Adjusts confidence floors dynamically based on market conditions.
    """

    def __init__(self):
        """Initialize adaptive thresholds."""
        # Base floors by regime
        self.base_floors = {
            "trend": 55.0,
            "range": 70.0,
            "panic": 80.0,
            "volatile": 75.0,
            "consolidation": 72.0,
            "unknown": 65.0,
        }

    def get_adaptive_floor(
        self,
        regime: str,
        volatility_level: float,  # 0-100 (IV percentile)
        time_of_day: int,  # 0-23 (hour)
        recent_win_rate: Optional[float] = None,  # Last 20 trades
        regime_confidence: Optional[float] = None,  # How sure about regime?
    ) -> float:
        """
        Get adaptive confidence floor for current market conditions.

        Args:
            regime: Current market regime
            volatility_level: Implied volatility (0-100)
            time_of_day: Current hour (0-23)
            recent_win_rate: Win rate on last 20 trades
            regime_confidence: Confidence in regime classification

        Returns:
            Adaptive confidence floor (0-100)
        """
        # Start with base floor for regime
        floor = self.base_floors.get(regime, 65.0)

        # Volatility adjustment
        vol_adjustment = self._get_volatility_adjustment(volatility_level)
        floor += vol_adjustment

        # Time of day adjustment
        tod_adjustment = self._get_time_of_day_adjustment(time_of_day)
        floor += tod_adjustment

        # Recent performance adjustment
        if recent_win_rate is not None:
            perf_adjustment = self._get_performance_adjustment(recent_win_rate)
            floor += perf_adjustment

        # Regime confidence adjustment
        if regime_confidence is not None:
            regime_adj = self._get_regime_confidence_adjustment(regime_confidence)
            floor += regime_adj

        # Clamp to reasonable range (40-90)
        return max(40.0, min(90.0, floor))

    def _get_volatility_adjustment(self, volatility: float) -> float:
        """
        Adjust floor based on volatility.

        High volatility = more noise = raise floor
        """
        if volatility < 25:
            return -5.0  # Low vol → lower floor (signals more reliable)
        elif volatility < 50:
            return 0.0  # Medium vol → no adjustment
        elif volatility < 75:
            return 5.0  # High vol → raise floor
        else:
            return 10.0  # Very high vol → raise floor significantly

    def _get_time_of_day_adjustment(self, hour: int) -> float:
        """
        Adjust floor based on time of day.

        Asia quiet hours (off-US hours) have less reliable signals.
        """
        # US market hours: 9:30-16:00 EST (14:30-21:00 UTC)
        # Europe hours: 8:00-17:00 GMT (8:00-17:00 UTC)
        if 8 <= hour <= 21:
            return 0.0  # Major market hours → no adjustment
        else:
            return 5.0  # Off-hours → raise floor

    def _get_performance_adjustment(self, recent_win_rate: float) -> float:
        """
        Adjust floor based on recent performance.

        Winning streak → lower floor (on an edge)
        Losing streak → raise floor (signal quality degraded)
        """
        if recent_win_rate > 0.65:
            return -3.0  # Winning → more aggressive
        elif recent_win_rate > 0.55:
            return 0.0
        elif recent_win_rate > 0.45:
            return 3.0
        else:
            return 8.0  # Losing streak → much more conservative

    def _get_regime_confidence_adjustment(self, regime_conf: float) -> float:
        """
        Adjust floor based on regime classification confidence.

        Uncertain regime → raise floor
        Confident regime → lower floor
        """
        if regime_conf < 0.6:
            return 8.0  # Very uncertain → raise floor
        elif regime_conf < 0.75:
            return 3.0  # Somewhat uncertain
        elif regime_conf > 0.85:
            return -2.0  # Very confident → lower floor
        else:
            return 0.0

    def get_floor_report(
        self,
        regime: str,
        volatility: float,
        time_of_day: int,
        recent_win_rate: Optional[float] = None,
        regime_confidence: Optional[float] = None,
    ) -> Dict:
        """Get detailed breakdown of floor calculation."""
        base = self.base_floors.get(regime, 65.0)
        vol_adj = self._get_volatility_adjustment(volatility)
        tod_adj = self._get_time_of_day_adjustment(time_of_day)
        perf_adj = self._get_performance_adjustment(recent_win_rate) if recent_win_rate else 0.0
        regime_adj = self._get_regime_confidence_adjustment(regime_confidence) if regime_confidence else 0.0

        floor = self.get_adaptive_floor(
            regime, volatility, time_of_day, recent_win_rate, regime_confidence
        )

        return {
            "base_floor": base,
            "volatility_adjustment": f"{vol_adj:+.0f}%",
            "time_of_day_adjustment": f"{tod_adj:+.0f}%",
            "performance_adjustment": f"{perf_adj:+.0f}%",
            "regime_confidence_adjustment": f"{regime_adj:+.0f}%",
            "final_floor": f"{floor:.0f}%",
            "summary": f"Base {base:.0f}% with {vol_adj:+.0f} vol + {tod_adj:+.0f} time + {perf_adj:+.0f} perf = {floor:.0f}%",
        }


# Global adaptive thresholds
_global_adaptive: Optional[AdaptiveConfidenceThresholds] = None


def get_adaptive_confidence_thresholds() -> AdaptiveConfidenceThresholds:
    """Get or create global thresholds."""
    global _global_adaptive
    if _global_adaptive is None:
        _global_adaptive = AdaptiveConfidenceThresholds()
    return _global_adaptive
