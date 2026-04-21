"""
Smoke tests for llm/agents/comprehensive_snapshot.py.

Covers:
  - Technical indicator helpers (_ema, _rsi, _atr, _adx, _macd_hist, _bb_position)
  - _extract_ohlcv with different shapes
  - _price_decimals sizing
  - build_comprehensive_snapshot minimal + full
  - snapshot_to_compact_json round-trip
  - extract_layer
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from llm.agents.comprehensive_snapshot import (
    _adx,
    _atr,
    _bb_position,
    _ema,
    _extract_ohlcv,
    _macd_hist,
    _price_decimals,
    _rsi,
    build_comprehensive_snapshot,
    extract_layer,
    snapshot_to_compact_json,
)


# ── Technical indicator helpers ────────────────────────

def test_ema_empty():
    assert _ema([], 5) == 0.0


def test_ema_single_value():
    assert _ema([100.0], 5) == 100.0


def test_ema_monotonic_input():
    # EMA of [1, 2, 3, 4, 5] with span 3 should be between min and max
    result = _ema([1.0, 2.0, 3.0, 4.0, 5.0], 3)
    assert 1.0 <= result <= 5.0


def test_rsi_insufficient_data_returns_50():
    # Fewer than period+1 points → RSI returns neutral 50
    assert _rsi([100.0, 101.0, 102.0], period=14) == 50.0


def test_rsi_all_gains_returns_100():
    # Strictly increasing closes → RSI = 100
    closes = [float(i) for i in range(1, 30)]
    result = _rsi(closes, period=14)
    assert result == 100.0


def test_atr_zero_when_no_data():
    # ATR with no data should return 0 or small
    val = _atr([], [], [], period=14)
    assert val == 0.0


def test_atr_positive_with_volatility():
    highs = [105.0] * 20
    lows = [95.0] * 20
    closes = [100.0] * 20
    result = _atr(highs, lows, closes)
    # ATR is generic TR mean; should be >= 0
    assert result >= 0


def test_adx_insufficient_data():
    # Too-short input should not crash
    val = _adx([1.0, 2.0], [1.0, 2.0], [1.0, 2.0])
    assert isinstance(val, (int, float))


def test_macd_hist_insufficient_data():
    val = _macd_hist([1.0, 2.0])
    assert isinstance(val, (int, float))


def test_bb_position_flat_prices():
    bb = _bb_position([100.0] * 25)
    assert bb["w"] == 0.0
    assert bb["pos"] == 0.0


def test_bb_position_rising_prices():
    closes = [100.0 + i for i in range(25)]
    bb = _bb_position(closes)
    assert "w" in bb
    assert "pos" in bb


# ── _extract_ohlcv ─────────────────────────────────────

def test_extract_ohlcv_none_when_missing():
    o, h, l, c, v = _extract_ohlcv({}, "1h")
    assert o is None


def test_extract_ohlcv_list_of_candles():
    data = {"1h": [[0, 100, 110, 90, 105, 1000], [0, 105, 115, 95, 110, 1500]]}
    o, h, l, c, v = _extract_ohlcv(data, "1h")
    assert o == [100.0, 105.0]
    assert h == [110.0, 115.0]
    assert l == [90.0, 95.0]
    assert c == [105.0, 110.0]
    assert v == [1000.0, 1500.0]


def test_extract_ohlcv_dict_shape():
    data = {"1h": {"close": [100, 105, 110], "high": [110, 115, 120], "low": [90, 95, 100]}}
    o, h, l, c, v = _extract_ohlcv(data, "1h")
    assert c == [100.0, 105.0, 110.0]


# ── _price_decimals ────────────────────────────────────

def test_price_decimals_large_to_small():
    assert _price_decimals(75000) == 1
    assert _price_decimals(500) == 2
    assert _price_decimals(10) == 3
    assert _price_decimals(0.5) == 5
    assert _price_decimals(0.0001) == 8


# ── build_comprehensive_snapshot ───────────────────────

def test_snapshot_minimal_fields():
    snap = build_comprehensive_snapshot(
        symbol="BTC", data={}, current_price=75000.0,
    )
    assert "market" in snap
    assert "signals" in snap
    assert "positions" in snap
    assert "system" in snap
    assert "memory" in snap
    assert "time" in snap
    # Symbol should be preserved
    assert snap["market"]["sym"] == "BTC"


def test_snapshot_empty_inputs_no_crash():
    snap = build_comprehensive_snapshot(
        symbol="ETH",
        data={},
        current_price=2100.0,
        all_prices=None,
        funding_rates=None,
        open_interest=None,
        strategy_signals=None,
        positions=None,
        strategy_weights=None,
        kelly_fractions=None,
        tuner_state=None,
        ic_values=None,
        recent_trades=None,
        rejection_counts=None,
        lessons=None,
        hypotheses=None,
        trade_dna=None,
    )
    assert snap["market"]["sym"] == "ETH"


def test_snapshot_with_populated_inputs():
    data = {
        "1h": [
            [0, 100.0, 110.0, 95.0, 105.0, 1000.0]
            for _ in range(30)
        ]
    }
    snap = build_comprehensive_snapshot(
        symbol="BTC",
        data=data,
        current_price=75000.0,
        all_prices={"BTC": 75000.0, "ETH": 2100.0},
        funding_rates={"BTC": 0.0005},
        strategy_signals={
            "regime_trend": {"side": "BUY", "confidence": 72.0, "fired": True},
        },
        positions=None,
        strategy_weights={"regime_trend": 1.0, "mtf": 0.8},
        equity=1000.0,
        daily_pnl=5.0,
        consecutive_losses=0,
        lessons=["BTC trends strong in Asia session"],
        hypotheses=["High funding suggests reversal"],
    )
    # Basic shape
    assert "market" in snap
    assert snap["market"]["sym"] == "BTC"


def test_snapshot_time_layer_explicit():
    snap = build_comprehensive_snapshot(
        symbol="BTC", data={}, current_price=75000.0,
        current_utc_hour=10, day_of_week="Monday", session="london",
    )
    assert snap["time"]["utc_h"] == 10
    assert snap["time"]["sess"] == "london"
    # Day truncated to 3 chars
    assert snap["time"]["day"] == "Mon"


def test_snapshot_time_inferred_session_asia():
    snap = build_comprehensive_snapshot(
        symbol="BTC", data={}, current_price=75000.0,
        current_utc_hour=2, day_of_week="Tuesday",
    )
    assert snap["time"]["sess"] == "asia"


# ── snapshot_to_compact_json ───────────────────────────

def test_snapshot_compact_json_roundtrip():
    snap = build_comprehensive_snapshot(
        symbol="BTC", data={}, current_price=75000.0,
    )
    s = snapshot_to_compact_json(snap)
    assert isinstance(s, str)
    # Must be valid JSON and round-trip
    reloaded = json.loads(s)
    assert reloaded["market"]["sym"] == "BTC"
    # Compact form should have no whitespace between keys
    assert ", " not in s
    assert ": " not in s


def test_snapshot_compact_json_handles_non_serializable():
    # default=str fallback should catch any weird objects
    snap = {"extra": object()}
    s = snapshot_to_compact_json(snap)
    assert isinstance(s, str)


# ── extract_layer ───────────────────────────────────────

def test_extract_layer_returns_requested():
    snap = build_comprehensive_snapshot(
        symbol="BTC", data={}, current_price=75000.0,
    )
    sub = extract_layer(snap, "market", "time")
    assert set(sub.keys()) == {"market", "time"}


def test_extract_layer_ignores_missing():
    snap = {"market": {"sym": "BTC"}}
    sub = extract_layer(snap, "market", "nonexistent")
    assert set(sub.keys()) == {"market"}


def test_extract_layer_empty_args():
    snap = {"market": {"sym": "BTC"}}
    sub = extract_layer(snap)
    assert sub == {}
