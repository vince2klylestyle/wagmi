"""
TIER 4.6: Mechanical Bot Data Stream Capture

Captures market snapshot data that the mechanical bot sees.
Used to build comprehensive market context history.
"""

import logging
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime
import json
import os

logger = logging.getLogger("bot.llm.mechanical_bot_data_stream")


@dataclass
class MarketSnapshot:
    """Snapshot of market state the bot sees."""
    symbol: str
    timestamp: float
    current_price: float
    price_change_1h_pct: float
    price_change_24h_pct: float
    atr: float
    volatility_percentile: float
    regime: str
    regime_confidence: float
    regime_momentum: Optional[str]
    alignment_5m_1h: float
    alignment_1h_6h: float
    alignment_6h_1d: float
    support_level: Optional[float]
    resistance_level: Optional[float]
    btc_price: Optional[float]
    btc_change_1h_pct: float
    correlation_with_btc_1h: float
    correlation_with_btc_6h: float
    time_of_day: int
    day_of_week: int
    trading_session: str
    rsi_14: Optional[float]
    macd_histogram: Optional[float]
    momentum_direction: Optional[str]
    volume_profile: Optional[str]
    liquidity_rating: float


class MechanicalDataStreamCapture:
    """Captures and tracks market snapshots over time."""

    def __init__(self):
        self.snapshots: List[MarketSnapshot] = []
        self.symbol_history: Dict[str, List[MarketSnapshot]] = {}
        self.max_snapshots = 1000  # Keep last 1000 snapshots per symbol

    def capture_snapshot(
        self,
        symbol: str,
        current_price: float,
        price_change_1h_pct: float,
        price_change_24h_pct: float,
        atr: float,
        volatility_percentile: float,
        regime: str,
        regime_confidence: float,
        regime_momentum: Optional[str],
        alignment_5m_1h: float,
        alignment_1h_6h: float,
        alignment_6h_1d: float,
        support_level: Optional[float],
        resistance_level: Optional[float],
        btc_price: Optional[float],
        btc_change_1h_pct: float,
        correlation_with_btc_1h: float,
        correlation_with_btc_6h: float,
        time_of_day: int,
        day_of_week: int,
        trading_session: str,
        rsi_14: Optional[float],
        macd_histogram: Optional[float],
        momentum_direction: Optional[str],
        volume_profile: Optional[str],
        liquidity_rating: float,
    ) -> MarketSnapshot:
        """Capture a market snapshot."""
        try:
            snapshot = MarketSnapshot(
                symbol=symbol,
                timestamp=datetime.now().timestamp(),
                current_price=current_price,
                price_change_1h_pct=price_change_1h_pct,
                price_change_24h_pct=price_change_24h_pct,
                atr=atr,
                volatility_percentile=volatility_percentile,
                regime=regime,
                regime_confidence=regime_confidence,
                regime_momentum=regime_momentum,
                alignment_5m_1h=alignment_5m_1h,
                alignment_1h_6h=alignment_1h_6h,
                alignment_6h_1d=alignment_6h_1d,
                support_level=support_level,
                resistance_level=resistance_level,
                btc_price=btc_price,
                btc_change_1h_pct=btc_change_1h_pct,
                correlation_with_btc_1h=correlation_with_btc_1h,
                correlation_with_btc_6h=correlation_with_btc_6h,
                time_of_day=time_of_day,
                day_of_week=day_of_week,
                trading_session=trading_session,
                rsi_14=rsi_14,
                macd_histogram=macd_histogram,
                momentum_direction=momentum_direction,
                volume_profile=volume_profile,
                liquidity_rating=liquidity_rating,
            )

            # Store in global list
            self.snapshots.append(snapshot)
            if len(self.snapshots) > self.max_snapshots:
                self.snapshots.pop(0)

            # Store in symbol history
            if symbol not in self.symbol_history:
                self.symbol_history[symbol] = []
            self.symbol_history[symbol].append(snapshot)
            if len(self.symbol_history[symbol]) > self.max_snapshots:
                self.symbol_history[symbol].pop(0)

            logger.debug(f"Captured snapshot for {symbol} at {current_price}")
            return snapshot

        except Exception as e:
            logger.error(f"Error capturing snapshot: {e}")
            raise

    def get_latest_snapshot(self, symbol: str) -> Optional[MarketSnapshot]:
        """Get latest snapshot for a symbol."""
        if symbol not in self.symbol_history or not self.symbol_history[symbol]:
            return None
        return self.symbol_history[symbol][-1]

    def get_snapshot_history(self, symbol: str, limit: int = 100) -> List[MarketSnapshot]:
        """Get snapshot history for a symbol."""
        if symbol not in self.symbol_history:
            return []
        return self.symbol_history[symbol][-limit:]


# Global instance
_global_data_stream: Optional[MechanicalDataStreamCapture] = None


def get_mechanical_data_stream_capture() -> MechanicalDataStreamCapture:
    """Get or create global data stream capture."""
    global _global_data_stream
    if _global_data_stream is None:
        _global_data_stream = MechanicalDataStreamCapture()
    return _global_data_stream
