"""
Tests for bot/tools/sniper_counterfactual.py.

Focuses on pure functions (no network/OHLCV fetch):
- Signal loading + test-marker filter
- 30-min dedupe
- Mechanical simulation (SL / TP_scalp / TP_swing / time-stop)
- Summary math (WR, expectancy, compound curve)
- JSON/CSV output writer
"""

import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Ensure bot/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.sniper_counterfactual import (  # noqa: E402
    Signal,
    Outcome,
    _dedupe,
    _load_signals,
    _simulate_signal,
    _summary_dict,
    _write_summaries,
)


def _mk_sig(ts_iso: str, symbol: str = "SOL", side: str = "BUY",
            tier: str = "SNIPER", entry: float = 100.0,
            sl: float = 98.0, tp_scalp: float = 103.0,
            tp_swing: float = 106.0, confidence: float = 70.0,
            regime: str = "trending_bull") -> Signal:
    return Signal(
        ts=datetime.fromisoformat(ts_iso).replace(tzinfo=timezone.utc),
        symbol=symbol, side=side, tier=tier,
        entry=entry, sl=sl, tp_scalp=tp_scalp, tp_swing=tp_swing,
        confidence=confidence, regime=regime,
    )


def _mk_bars(start_iso: str, n: int = 10, step_min: int = 5):
    """Generate n OHLC bars starting at start_iso, step_min apart."""
    t0 = datetime.fromisoformat(start_iso).replace(tzinfo=timezone.utc)
    bars = []
    for i in range(n):
        ts = t0 + timedelta(minutes=i * step_min)
        bars.append((ts, 100.0, 100.5, 99.5, 100.2))
    return bars


class TestLoadSignals:
    def test_filters_test_markers(self, tmp_path):
        path = tmp_path / "sigs.jsonl"
        rows = [
            {"timestamp": "2026-04-17T00:00:00Z", "symbol": "SOL", "side": "BUY",
             "tier": "SNIPER", "entry": 100, "sl": 98, "tp_scalp": 103, "tp_swing": 106,
             "confidence": 70, "regime": "trend", "strategies": ["regime_trend", "BB"]},
            # Test marker — should be dropped
            {"timestamp": "2026-04-17T00:05:00Z", "symbol": "SOL", "side": "BUY",
             "tier": "SNIPER", "entry": 100, "sl": 98, "tp_scalp": 103, "tp_swing": 106,
             "confidence": 70, "regime": "trend", "strategies": ["a", "b", "c"]},
        ]
        with path.open("w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")

        loaded = _load_signals(path, drop_test_markers=True)
        assert len(loaded) == 1
        assert loaded[0].symbol == "SOL"

    def test_skips_malformed_rows(self, tmp_path):
        path = tmp_path / "sigs.jsonl"
        path.write_text(
            "not valid json\n"
            '{"timestamp": "2026-04-17T00:00:00Z", "symbol": "BTC", "side": "SELL", '
            '"tier": "PREMIUM", "entry": 60000, "sl": 61000, "tp_scalp": 59000, '
            '"tp_swing": 58000, "confidence": 80, "regime": "panic"}\n'
        )
        loaded = _load_signals(path)
        assert len(loaded) == 1
        assert loaded[0].symbol == "BTC"


class TestDedupe:
    def test_drops_within_30min(self):
        sigs = [
            _mk_sig("2026-04-17T00:00:00"),
            _mk_sig("2026-04-17T00:20:00"),  # within 30m — should be dropped
            _mk_sig("2026-04-17T00:40:00"),  # > 30m since first kept — should be kept
        ]
        out = _dedupe(sigs)
        assert len(out) == 2
        assert out[0].ts.minute == 0
        assert out[1].ts.minute == 40

    def test_different_symbols_not_deduped(self):
        sigs = [
            _mk_sig("2026-04-17T00:00:00", symbol="SOL"),
            _mk_sig("2026-04-17T00:10:00", symbol="BTC"),
        ]
        out = _dedupe(sigs)
        assert len(out) == 2


class TestSimulateSignal:
    def test_no_data_when_no_bars(self):
        sig = _mk_sig("2026-04-17T00:00:00")
        out = _simulate_signal(sig, bars=[], leverage=5.0, max_hold_hours=8.0)
        assert out.result == "no_data"
        assert out.pnl_pct_on_notional == 0.0

    def test_long_hits_sl(self):
        sig = _mk_sig("2026-04-17T00:00:00", side="BUY",
                      entry=100.0, sl=95.0, tp_scalp=110.0, tp_swing=120.0)
        t0 = datetime(2026, 4, 17, 0, 1, tzinfo=timezone.utc)
        t1 = datetime(2026, 4, 17, 0, 6, tzinfo=timezone.utc)
        # Second bar wicks below SL (need ≥2 bars for _simulate_signal to engage)
        bars = [
            (t0, 100.0, 100.5, 99.5, 100.2),
            (t1, 100.2, 100.5, 94.0, 96.0),
        ]
        out = _simulate_signal(sig, bars, leverage=5.0, max_hold_hours=8.0)
        assert out.result == "sl"
        # Move = -5%, leverage 5x = -25% gross, minus fees (0.08% * 5)
        assert out.pnl_pct_on_notional < -0.24

    def test_long_hits_tp_scalp(self):
        sig = _mk_sig("2026-04-17T00:00:00", side="BUY",
                      entry=100.0, sl=95.0, tp_scalp=103.0, tp_swing=110.0)
        t0 = datetime(2026, 4, 17, 0, 1, tzinfo=timezone.utc)
        t1 = datetime(2026, 4, 17, 0, 6, tzinfo=timezone.utc)
        bars = [
            (t0, 100.0, 100.5, 99.5, 100.2),
            (t1, 100.2, 103.5, 99.5, 103.2),
        ]
        out = _simulate_signal(sig, bars, leverage=5.0, max_hold_hours=8.0)
        assert out.result == "tp_scalp"
        assert out.pnl_pct_on_notional > 0

    def test_long_hits_tp_swing_when_bar_reaches_it(self):
        sig = _mk_sig("2026-04-17T00:00:00", side="BUY",
                      entry=100.0, sl=95.0, tp_scalp=103.0, tp_swing=110.0)
        t0 = datetime(2026, 4, 17, 0, 1, tzinfo=timezone.utc)
        t1 = datetime(2026, 4, 17, 0, 6, tzinfo=timezone.utc)
        bars = [
            (t0, 100.0, 100.5, 99.5, 100.2),
            (t1, 100.2, 112.0, 99.5, 111.5),
        ]
        out = _simulate_signal(sig, bars, leverage=5.0, max_hold_hours=8.0)
        assert out.result == "tp_swing"

    def test_short_hits_sl(self):
        sig = _mk_sig("2026-04-17T00:00:00", side="SELL",
                      entry=100.0, sl=105.0, tp_scalp=97.0, tp_swing=90.0)
        t0 = datetime(2026, 4, 17, 0, 1, tzinfo=timezone.utc)
        t1 = datetime(2026, 4, 17, 0, 6, tzinfo=timezone.utc)
        bars = [
            (t0, 100.0, 100.5, 99.5, 100.2),
            (t1, 100.2, 106.0, 99.5, 105.5),
        ]
        out = _simulate_signal(sig, bars, leverage=5.0, max_hold_hours=8.0)
        assert out.result == "sl"
        assert out.pnl_pct_on_notional < 0

    def test_time_stop_when_no_level_hit(self):
        sig = _mk_sig("2026-04-17T00:00:00", side="BUY",
                      entry=100.0, sl=95.0, tp_scalp=110.0, tp_swing=120.0)
        bars = _mk_bars("2026-04-17T00:01:00", n=3, step_min=5)
        out = _simulate_signal(sig, bars, leverage=5.0, max_hold_hours=0.5)
        assert out.result == "time_stop"


class TestSummaryDict:
    def test_empty_outcomes(self):
        s = _summary_dict([], "empty")
        assert s["total"] == 0
        assert s["playable"] == 0

    def test_basic_math(self):
        sig = _mk_sig("2026-04-17T00:00:00")
        outcomes = [
            Outcome(sig, 5.0, "tp_scalp", 103.0, 1.0, 0.03, 30.0),
            Outcome(sig, 5.0, "tp_scalp", 103.0, 1.0, 0.03, 30.0),
            Outcome(sig, 5.0, "sl", 95.0, 0.5, -0.05, -50.0),
            Outcome(sig, 5.0, "no_data", 0.0, 0.0, 0.0, 0.0),  # ignored
        ]
        s = _summary_dict(outcomes, "test")
        assert s["total"] == 4
        assert s["playable"] == 3
        assert s["no_data"] == 1
        # 2 wins / 3 playable = 66.666…
        assert abs(s["win_rate_pct"] - 66.667) < 0.5
        assert s["wins"] == 2
        assert s["losses"] == 1
        # 30+30-50 = 10 on $1k
        assert abs(s["total_pnl_on_1k"] - 10.0) < 1e-6
        assert s["max_drawdown_pct"] >= 0.0


class TestWriteSummaries:
    def test_json_output(self, tmp_path):
        summaries = [
            {"leverage": 5, "group": "ALL", "label": "ALL (5x)",
             "total": 10, "playable": 9, "win_rate_pct": 55.5,
             "outcomes": {"tp_scalp": 5, "sl": 4}},
        ]
        out_path = tmp_path / "summary.json"
        _write_summaries(str(out_path), summaries)
        data = json.loads(out_path.read_text())
        assert "summaries" in data
        assert len(data["summaries"]) == 1
        assert data["summaries"][0]["leverage"] == 5

    def test_csv_output(self, tmp_path):
        summaries = [
            {"leverage": 5, "group": "ALL", "label": "ALL (5x)",
             "total": 10, "no_data": 0, "playable": 10,
             "win_rate_pct": 55.0, "wins": 5, "losses": 5,
             "total_pnl_on_1k": 50.0, "avg_pnl_on_1k": 5.0,
             "avg_win_on_1k": 20.0, "avg_loss_on_1k": -10.0,
             "avg_hold_hours": 2.0, "compounded_100_final": 150.0,
             "max_drawdown_pct": 5.0,
             "outcomes": {"tp_scalp": 5, "sl": 5}},
        ]
        out_path = tmp_path / "summary.csv"
        _write_summaries(str(out_path), summaries)
        with out_path.open() as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert rows[0]["leverage"] == "5"
        assert rows[0]["group"] == "ALL"
        # outcomes flattened to JSON string
        assert json.loads(rows[0]["outcomes"]) == {"tp_scalp": 5, "sl": 5}

    def test_creates_parent_dirs(self, tmp_path):
        deep_path = tmp_path / "a" / "b" / "c" / "summary.json"
        _write_summaries(str(deep_path), [{"leverage": 5, "group": "X"}])
        assert deep_path.exists()
