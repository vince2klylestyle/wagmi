"""
Strategy: Trend Breakout

Simple trend-following strategy designed to capture momentum in strong trends.
Fires when:
- Market is in trend (ADX > 25, price > EMA20 > EMA50)
- Price breaks above recent resistance (for BUY) or below support (for SELL)
- Entry signal from breakout + momentum confirmation (MACD)

Complements BB Squeeze (which waits for compression) and RT (which waits for changes).
This captures the CURRENT trend before regime shifts.

Data requirements:
- 1h OHLCV for EMA, ATR, MACD
- Trend context from regime detector
"""

import logging
from typing import Optional, Dict, Any

import pandas as pd
import numpy as np

from .base import BaseStrategy, Signal

logger = logging.getLogger("bot.strategy.trend_breakout")


def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """Average True Range"""
    prev = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev).abs(),
        (df["low"] - prev).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=1).mean()


def _ema(s: pd.Series, span: int) -> pd.Series:
    """Exponential Moving Average"""
    return s.ewm(span=max(2, span), adjust=False).mean()


def _sma(s: pd.Series, n: int) -> pd.Series:
    """Simple Moving Average"""
    return s.rolling(n, min_periods=1).mean()


def _macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD with signal line and histogram"""
    macd_line = _ema(close, fast) - _ema(close, slow)
    signal_line = _ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average Directional Index (simplified version)"""
    high = df["high"]
    low = df["low"]
    close = df["close"]

    # True Range
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    # Directional Movement
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

    # Smoothed
    tr_smooth = tr.rolling(period, min_periods=1).sum()
    plus_di = 100 * pd.Series(plus_dm).rolling(period, min_periods=1).sum() / tr_smooth
    minus_di = 100 * pd.Series(minus_dm).rolling(period, min_periods=1).sum() / tr_smooth

    # ADX
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-12)
    adx = dx.rolling(period, min_periods=1).mean()
    return adx


class TrendBreakoutStrategy(BaseStrategy):
    """Trend-following breakout strategy."""

    name = "trend_breakout"

    def __init__(self, symbols: Dict[str, Any]):
        super().__init__(self.name, symbols)
        self.lookback_bars = 10  # Shortened from 20 for more frequent breakouts
        self.min_adx = 20  # Lowered from 25 for more signals

    def evaluate(self, symbol: str, data: Dict[str, pd.DataFrame]) -> Optional[Signal]:
        """Generate trend breakout signals."""
        df_1h = data.get("1h")
        if df_1h is None or len(df_1h) < 50:
            return None

        close = df_1h["close"].astype(float)
        high = df_1h["high"].astype(float)
        low = df_1h["low"].astype(float)

        price = float(close.iloc[-1])
        atr = float(_atr(df_1h).iloc[-1])

        if atr <= 0 or price <= 0:
            return None

        # Trend components
        ema20 = float(_ema(close, 20).iloc[-1])
        ema50 = float(_ema(close, 50).iloc[-1])
        adx = float(_adx(df_1h).iloc[-1])

        # MACD for momentum
        macd_line, macd_signal, macd_hist = _macd(close)
        hist_current = float(macd_hist.iloc[-1])
        hist_prev = float(macd_hist.iloc[-2]) if len(macd_hist) >= 2 else 0

        # Resistance/support from last N bars
        recent_high = float(high.iloc[-self.lookback_bars:].max())
        recent_low = float(low.iloc[-self.lookback_bars:].min())

        side = None
        signal_type = None
        confidence = 55.0

        # BUY: Price breaks above recent resistance in uptrend
        if (price > ema20 > ema50 and  # Trend structure: price > EMA20 > EMA50
            adx > self.min_adx and  # Trend confirmed
            hist_current > 0 and  # MACD positive
            price > recent_high * 0.95):  # Within 5% of recent highs (relaxed from 2%)

            side = "BUY"
            signal_type = "trend_breakout_long"
            confidence = 60.0

            # Confidence boost for strong momentum
            if hist_current > hist_prev * 1.5:
                confidence += 8.0

            # Confidence boost for strong trend
            if adx > 35:
                confidence += 5.0

            logger.info(f"[{symbol}] Trend Breakout BUY: ADX={adx:.1f}, price={price:.2f}, "
                       f"EMA20={ema20:.2f}, recent_high={recent_high:.2f}")

        # SELL: Price breaks below recent support in downtrend
        elif (price < ema20 < ema50 and  # Trend structure: price < EMA20 < EMA50
              adx > self.min_adx and  # Trend confirmed
              hist_current < 0 and  # MACD negative
              price < recent_low * 1.05):  # Within 5% of recent lows (relaxed from 2%)

            side = "SELL"
            signal_type = "trend_breakout_short"
            confidence = 60.0

            # Confidence boost for strong momentum
            if hist_current < hist_prev * 1.5:
                confidence += 8.0

            # Confidence boost for strong trend
            if adx > 35:
                confidence += 5.0

            logger.info(f"[{symbol}] Trend Breakout SELL: ADX={adx:.1f}, price={price:.2f}, "
                       f"EMA20={ema20:.2f}, recent_low={recent_low:.2f}")

        if side is None or signal_type is None:
            return None

        confidence = max(55.0, min(90.0, confidence))

        # Position sizing: wider stops for trend-following
        if side == "BUY":
            sl = price - atr * 2.0  # 2x ATR stop
            tp1 = price + atr * 2.5  # 2.5x ATR target
            tp2 = price + atr * 5.0  # 5x ATR aggressive target
        else:
            sl = price + atr * 2.0
            tp1 = price - atr * 2.5
            tp2 = price - atr * 5.0

        sig = Signal(
            strategy="trend_breakout",
            symbol=symbol,
            side=side,
            confidence=confidence,
            entry=price,
            sl=sl,
            tp1=tp1,
            tp2=tp2,
            atr=atr,
            metadata={
                "signal_type": signal_type,
                "adx": float(adx),
                "ema20": float(ema20),
                "ema50": float(ema50),
                "macd_histogram": hist_current,
                "regime": "trend",  # This strategy fires in trends
            },
            signal_context=f"Trend Breakout | ADX={adx:.1f} (trend strength) | "
                          f"EMA20={ema20:.0f} EMA50={ema50:.0f} | MACD hist={hist_current:.4f}",
        )

        if not sig.is_valid:
            return None

        logger.info(f"[{symbol}] {signal_type} signal generated: conf={confidence:.0f}%")
        return sig

    def get_status(self, symbol: str, data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Return strategy status."""
        df_1h = data.get("1h")
        if df_1h is None or len(df_1h) < 50:
            return {"strategy": self.name, "symbol": symbol, "state": "insufficient_data"}

        close = df_1h["close"].astype(float)
        ema20 = float(_ema(close, 20).iloc[-1])
        ema50 = float(_ema(close, 50).iloc[-1])
        adx = float(_adx(df_1h).iloc[-1])

        return {
            "strategy": self.name,
            "symbol": symbol,
            "trend": "up" if close.iloc[-1] > ema20 > ema50 else "down" if close.iloc[-1] < ema20 < ema50 else "none",
            "adx": float(adx),
            "ema20": float(ema20),
            "ema50": float(ema50),
        }
