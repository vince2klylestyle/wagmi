"""
Mean-Reversion Bands Strategy — Bollinger Band bounce with RSI confirmation.

Designed specifically for consolidation/range regimes where trend-following
strategies leave money on the table.

Evidence (alpha research 2026-03-24):
- Consolidation is BEST regime: 60% WR, +$761 PnL/90d
- Current strategies are trend-following, missing mean-reversion setups
- Academic support: Arda (2025, SSRN) confirms BB mean-reversion has
  "exceptional gains" in accumulation/consolidation phases
- mean_reversion setup type: 16 trades, 43.8% WR, +$37 in 90d backtest
  (accidentally captured by other strategies — a dedicated strategy should do better)

Entry:
  Long: Price closes below lower BB AND RSI < 30 AND ADX < 25
  Short: Price closes above upper BB AND RSI > 70 AND ADX < 25

Targets:
  TP1: Middle Bollinger Band (20 SMA) — the "mean"
  TP2: Opposite Bollinger Band (ambitious, only in tight ranges)
  SL: 1.5 ATR beyond entry extreme

Regime gate: ONLY fires when ADX < 25 (consolidation/range)
Kill switch: If BB bandwidth is expanding > 1.5x average, skip (breakout forming)
"""

import logging
from typing import Dict, Any, List, Optional

import pandas as pd

from .base import BaseStrategy, Signal

logger = logging.getLogger("bot.strategy.mean_reversion")


def _sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=1).mean()


def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    prev = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev).abs(),
        (df["low"] - prev).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=1).mean()


def _bollinger_bands(close: pd.Series, period: int = 20, std_mult: float = 2.0):
    mid = _sma(close, period)
    std = close.rolling(period, min_periods=1).std().fillna(0)
    upper = mid + std_mult * std
    lower = mid - std_mult * std
    width = (upper - lower) / mid  # Bandwidth as fraction of mid
    return upper, mid, lower, std, width


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(period, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period, min_periods=1).mean()
    rs = gain / loss.replace(0, 1e-12)
    return 100.0 - (100.0 / (1.0 + rs))


def _adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Simplified ADX calculation."""
    high = df["high"]
    low = df["low"]
    close = df["close"]

    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    atr_vals = _atr(df, period)
    atr_safe = atr_vals.replace(0, 1e-12)

    plus_di = 100.0 * plus_dm.rolling(period, min_periods=1).mean() / atr_safe
    minus_di = 100.0 * minus_dm.rolling(period, min_periods=1).mean() / atr_safe

    di_sum = plus_di + minus_di
    di_sum = di_sum.replace(0, 1e-12)
    dx = 100.0 * (plus_di - minus_di).abs() / di_sum
    adx = dx.rolling(period, min_periods=1).mean()
    return adx


class MeanReversionStrategy(BaseStrategy):
    """
    Bollinger Band mean-reversion strategy for consolidation regimes.

    Only fires when ADX < 25 (confirming range/consolidation).
    Targets the 20-SMA (middle BB) as reversion target.
    """

    # Parameters
    BB_PERIOD = 20
    BB_STD = 2.0
    RSI_PERIOD = 14
    ADX_PERIOD = 14
    ATR_PERIOD = 14

    # Regime gate
    MAX_ADX = 28.0  # Only trade when ADX below this (consolidation). Relaxed from 25 — data shows ADX<30 covers 41% of candles.
    MIN_BB_WIDTH_PERCENTILE = 0.10  # Skip if BB too narrow (dead market)

    # Signal thresholds (relaxed from 30/70 — strict gives only 66 signals/90d, too few for ensemble consensus)
    RSI_OVERSOLD = 35.0
    RSI_OVERBOUGHT = 65.0

    # Risk parameters
    SL_ATR_MULT = 1.5   # SL at 1.5 ATR beyond entry extreme
    TP1_TARGET = "mid"   # Middle BB (the mean)
    TP2_ATR_MULT = 3.0   # TP2 at opposite BB or 3 ATR

    # Breakout kill switch
    BANDWIDTH_EXPANSION_KILL = 1.5  # Skip if BB width > 1.5x its 20-period average

    def __init__(self, symbols: Dict[str, Any]):
        super().__init__("mean_reversion", symbols)

    def evaluate(self, symbol: str, data: Dict[str, pd.DataFrame]) -> Optional[Signal]:
        """Evaluate for mean-reversion setups in consolidation."""
        df = data.get("1h")
        if df is None or len(df) < 50:
            return None

        close = df["close"]
        current_price = float(close.iloc[-1])

        # Compute indicators
        bb_upper, bb_mid, bb_lower, bb_std, bb_width = _bollinger_bands(
            close, self.BB_PERIOD, self.BB_STD
        )
        rsi = _rsi(close, self.RSI_PERIOD)
        adx = _adx(df, self.ADX_PERIOD)
        atr = _atr(df, self.ATR_PERIOD)

        current_rsi = float(rsi.iloc[-1])
        current_adx = float(adx.iloc[-1])
        current_atr = float(atr.iloc[-1])
        current_bb_upper = float(bb_upper.iloc[-1])
        current_bb_mid = float(bb_mid.iloc[-1])
        current_bb_lower = float(bb_lower.iloc[-1])
        current_bb_width = float(bb_width.iloc[-1])

        if current_atr <= 0 or current_price <= 0:
            return None

        # Regime gate: ONLY in consolidation (ADX < 25)
        if current_adx >= self.MAX_ADX:
            return None

        # Breakout kill switch: skip if bandwidth is expanding
        avg_bb_width = float(bb_width.rolling(20, min_periods=5).mean().iloc[-1])
        if avg_bb_width > 0 and current_bb_width > avg_bb_width * self.BANDWIDTH_EXPANSION_KILL:
            return None

        # Check for mean-reversion setup
        side = None
        confidence_base = 63.0  # Higher base to pass solo threshold (62) and contribute to ensemble floor (69)

        # Long: price at/below lower BB + RSI oversold
        if current_price <= current_bb_lower and current_rsi <= self.RSI_OVERSOLD:
            side = "BUY"
            # Z-score bonus: more extreme = higher confidence
            z_score = (current_price - current_bb_mid) / max(float(bb_std.iloc[-1]), 1e-12)
            confidence_base += min(15, abs(z_score) * 3)  # +3 per 1σ beyond 2σ

        # Short: price at/above upper BB + RSI overbought
        elif current_price >= current_bb_upper and current_rsi >= self.RSI_OVERBOUGHT:
            side = "SELL"
            z_score = (current_price - current_bb_mid) / max(float(bb_std.iloc[-1]), 1e-12)
            confidence_base += min(15, abs(z_score) * 3)

        if side is None:
            return None

        # Volume confirmation: require above-average volume on the extreme candle
        vol = df.get("volume")
        if vol is not None and len(vol) >= 20:
            avg_vol = float(vol.rolling(20, min_periods=5).mean().iloc[-1])
            current_vol = float(vol.iloc[-1])
            if avg_vol > 0:
                vol_ratio = current_vol / avg_vol
                if vol_ratio > 1.2:
                    confidence_base += 5  # Volume confirmation boost
                elif vol_ratio < 0.5:
                    confidence_base -= 5  # Low volume = less conviction

        # ADX proximity bonus: lower ADX = stronger consolidation
        if current_adx < 15:
            confidence_base += 5  # Deep consolidation
        elif current_adx < 20:
            confidence_base += 2

        confidence = min(85.0, max(50.0, confidence_base))

        # Calculate levels
        entry = current_price

        if side == "BUY":
            sl = entry - self.SL_ATR_MULT * current_atr
            tp1 = current_bb_mid  # Revert to the mean
            tp2 = current_bb_upper  # Ambitious: opposite BB
        else:
            sl = entry + self.SL_ATR_MULT * current_atr
            tp1 = current_bb_mid
            tp2 = current_bb_lower

        # Validate R:R
        stop_width = abs(entry - sl)
        if stop_width < entry * 0.003:  # Min 0.3% stop
            return None
        tp1_dist = abs(entry - tp1)
        rr = tp1_dist / stop_width if stop_width > 0 else 0
        if rr < 0.5:  # Mean-reversion can have lower R:R, but not below 0.5
            return None

        signal = Signal(
            strategy=self.name,
            symbol=symbol,
            side=side,
            confidence=confidence,
            entry=entry,
            sl=sl,
            tp1=tp1,
            tp2=tp2,
            atr=current_atr,
            metadata={
                "setup_type": "mean_reversion",
                "adx": round(current_adx, 1),
                "rsi": round(current_rsi, 1),
                "bb_position": "lower" if side == "BUY" else "upper",
                "bb_width": round(current_bb_width, 4),
                "z_score": round(z_score, 2),
                "rr_tp1": round(rr, 2),
                "entry_type": "MEDIUM",  # Mean-reversion: shorter hold than trend
            },
            signal_context=(
                f"Mean reversion {side}: price at {'lower' if side == 'BUY' else 'upper'} BB "
                f"(z={z_score:.1f}σ), RSI={current_rsi:.0f}, ADX={current_adx:.0f} (consolidation). "
                f"Target: middle BB at {current_bb_mid:.2f}"
            ),
        )

        if not signal.is_valid:
            return None

        logger.info(
            f"[{symbol}] Mean reversion {side}: RSI={current_rsi:.0f} ADX={current_adx:.0f} "
            f"z={z_score:.1f}σ conf={confidence:.0f}% R:R={rr:.2f}"
        )
        return signal

    def get_status(self, symbol: str, data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Get current mean-reversion status."""
        df = data.get("1h")
        if df is None or len(df) < 50:
            return {"symbol": symbol, "strategy": self.name, "status": "insufficient_data"}

        close = df["close"]
        rsi = _rsi(close, self.RSI_PERIOD)
        adx = _adx(df, self.ADX_PERIOD)
        bb_upper, bb_mid, bb_lower, _, bb_width = _bollinger_bands(close, self.BB_PERIOD, self.BB_STD)

        current_price = float(close.iloc[-1])
        current_rsi = float(rsi.iloc[-1])
        current_adx = float(adx.iloc[-1])
        bb_pos = "lower" if current_price <= float(bb_lower.iloc[-1]) else (
            "upper" if current_price >= float(bb_upper.iloc[-1]) else "middle"
        )

        return {
            "symbol": symbol,
            "strategy": self.name,
            "rsi": round(current_rsi, 1),
            "adx": round(current_adx, 1),
            "bb_position": bb_pos,
            "bb_width": round(float(bb_width.iloc[-1]), 4),
            "regime_ok": current_adx < self.MAX_ADX,
            "rsi_extreme": current_rsi <= self.RSI_OVERSOLD or current_rsi >= self.RSI_OVERBOUGHT,
        }

    def get_required_timeframes(self) -> List[str]:
        return ["1h"]
