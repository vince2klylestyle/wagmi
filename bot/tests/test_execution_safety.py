"""Tests for execution safety: dual-entry, price guard, human copy classifier, replay, telemetry."""

import os
import sys
import time
import tempfile
import csv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from models.trade_candidate import EnhancedTradeCandidate
from execution.price_guard import (
    validate_execution_price, pre_execution_guard, GuardResult,
)
from classification.human_copy_classifier import (
    classify_human_copy_tradable, CopyTradeResult, format_copy_trades_telegram,
)
from engine.replay_engine import (
    replay_from_csv, ReplayResult, ReplayAnomaly,
    format_replay_report,
)
from data.price_store import PriceStore, PriceSnapshot
from data.fetchers.telemetry import Telemetry
from execution.tp_sl_engine import compute_tp_sl, recompute_from_live_entry
from execution.pnl_engine import compute_pnl, compute_r_multiple


# ── Dual-Entry System ───────────────────────────────────────


class TestDualEntry:

    def test_effective_entry_prefers_live(self):
        c = EnhancedTradeCandidate(
            symbol="BTC", side="LONG", entry_type="TREND",
            primary_driver="regime_trend", regime="trend",
            snapshot_entry=100.0, live_entry=101.0,
        )
        assert c.effective_entry() == 101.0

    def test_effective_entry_falls_back_to_snapshot(self):
        c = EnhancedTradeCandidate(
            symbol="BTC", side="LONG", entry_type="TREND",
            primary_driver="regime_trend", regime="trend",
            snapshot_entry=100.0, live_entry=None,
        )
        assert c.effective_entry() == 100.0

    def test_snapshot_age_computation(self):
        now = time.time()
        c = EnhancedTradeCandidate(
            symbol="BTC", side="LONG", entry_type="TREND",
            primary_driver="regime_trend", regime="trend",
            snapshot_entry=100.0, snapshot_ts=now - 5.0,
            execution_ts=now,
        )
        age = c.compute_snapshot_age()
        assert 4.9 < age < 5.1

    def test_slippage_computation(self):
        c = EnhancedTradeCandidate(
            symbol="BTC", side="LONG", entry_type="TREND",
            primary_driver="regime_trend", regime="trend",
            snapshot_entry=100.0, live_entry=100.5,
        )
        slip = c.compute_slippage()
        assert abs(slip - 0.5) < 0.01  # 0.5%

    def test_log_dict_has_all_fields(self):
        c = EnhancedTradeCandidate(
            symbol="ETH", side="SHORT", entry_type="SCALP",
            primary_driver="monte_carlo_zones", regime="range",
            snapshot_entry=3000.0, live_entry=3010.0,
        )
        d = c.to_log_dict()
        assert d["snapshot_entry"] == 3000.0
        assert d["live_entry"] == 3010.0
        assert d["effective_entry"] == 3010.0
        assert "human_copy_tradable" in d
        assert "stale" in d


# ── Price Guard ─────────────────────────────────────────────


class TestPriceGuard:

    def test_validate_execution_price_within_tolerance(self):
        assert validate_execution_price(100.0, 100.5, 0.01)

    def test_validate_execution_price_out_of_tolerance(self):
        assert not validate_execution_price(100.0, 102.0, 0.01)

    def test_guard_all_pass(self):
        result = pre_execution_guard(
            snapshot_entry=100.0, live_price=100.1,
            snapshot_age_s=3.0, slippage_pct=0.1,
            spread_pct=0.1, liquidity_usd=100_000,
        )
        assert result.passed
        assert result.action == "proceed"

    def test_guard_stale_signal_downgrades(self):
        result = pre_execution_guard(
            snapshot_entry=100.0, live_price=100.0,
            snapshot_age_s=15.0, on_stale="downgrade",
        )
        assert result.passed  # downgrade still proceeds
        assert result.action == "downgrade"
        assert "snapshot_age" in result.downgrade_reasons

    def test_guard_high_slippage_vetoes(self):
        result = pre_execution_guard(
            snapshot_entry=100.0, live_price=100.0,
            snapshot_age_s=1.0, slippage_pct=2.0,
        )
        assert not result.passed
        assert result.action == "veto"
        assert "slippage" in result.veto_reasons

    def test_guard_circuit_breaker_vetoes(self):
        result = pre_execution_guard(
            snapshot_entry=100.0, live_price=100.0,
            snapshot_age_s=1.0, circuit_breaker_active=True,
        )
        assert not result.passed
        assert "circuit_breaker" in result.veto_reasons

    def test_guard_low_liquidity_vetoes(self):
        result = pre_execution_guard(
            snapshot_entry=100.0, live_price=100.0,
            snapshot_age_s=1.0, liquidity_usd=10_000,
        )
        assert not result.passed
        assert "liquidity" in result.veto_reasons

    def test_guard_price_deviation_vetoes(self):
        result = pre_execution_guard(
            snapshot_entry=100.0, live_price=102.0,
            snapshot_age_s=1.0,
        )
        assert not result.passed
        assert "price_deviation" in result.veto_reasons


# ── Human Copy-Trade Classifier ─────────────────────────────


class TestHumanCopyClassifier:

    def test_perfect_candidate_is_eligible(self):
        result = classify_human_copy_tradable(
            confidence=90.0, regime="trend", volatility_band="low",
            entry_type="TREND", primary_driver="regime_trend",
            leverage=3.0, rr=2.0,
        )
        assert result.eligible
        assert result.score == 100.0

    def test_low_confidence_rejected(self):
        result = classify_human_copy_tradable(
            confidence=70.0, regime="trend", volatility_band="low",
            entry_type="TREND", primary_driver="regime_trend",
            leverage=3.0, rr=2.0,
        )
        assert not result.eligible
        assert "confidence" in result.reasons[0]

    def test_panic_regime_rejected(self):
        result = classify_human_copy_tradable(
            confidence=90.0, regime="panic", volatility_band="low",
            entry_type="TREND", primary_driver="regime_trend",
            leverage=3.0, rr=2.0,
        )
        assert not result.eligible

    def test_high_volatility_rejected(self):
        result = classify_human_copy_tradable(
            confidence=90.0, regime="trend", volatility_band="high",
            entry_type="TREND", primary_driver="regime_trend",
            leverage=3.0, rr=2.0,
        )
        assert not result.eligible

    def test_high_leverage_rejected(self):
        result = classify_human_copy_tradable(
            confidence=90.0, regime="trend", volatility_band="low",
            entry_type="TREND", primary_driver="regime_trend",
            leverage=15.0, rr=2.0,
        )
        assert not result.eligible

    def test_stale_signal_rejected(self):
        result = classify_human_copy_tradable(
            confidence=90.0, regime="trend", volatility_band="low",
            entry_type="TREND", primary_driver="regime_trend",
            leverage=3.0, rr=2.0, stale=True,
        )
        assert not result.eligible

    def test_circuit_breaker_rejected(self):
        result = classify_human_copy_tradable(
            confidence=90.0, regime="trend", volatility_band="low",
            entry_type="TREND", primary_driver="regime_trend",
            leverage=3.0, rr=2.0, circuit_breaker_active=True,
        )
        assert not result.eligible

    def test_conflicting_signals_rejected(self):
        result = classify_human_copy_tradable(
            confidence=90.0, regime="trend", volatility_band="low",
            entry_type="TREND", primary_driver="regime_trend",
            leverage=3.0, rr=2.0, conflicting_signals=True,
        )
        assert not result.eligible

    def test_format_copy_trades_empty(self):
        text = format_copy_trades_telegram([])
        assert "No human copy-tradable" in text

    def test_format_copy_trades_with_data(self):
        trades = [{"human_copy_tradable": True, "symbol": "BTC", "side": "LONG",
                    "confidence": 90, "regime": "trend", "entry_type": "TREND"}]
        text = format_copy_trades_telegram(trades)
        assert "BTC" in text


# ── TP/SL Engine ────────────────────────────────────────────


class TestTPSLEngine:

    def test_long_tp_sl(self):
        levels = compute_tp_sl(100.0, "LONG", atr=2.0, rr1=1.5, rr2=2.5, sl_atr_mult=1.0)
        assert levels["sl_price"] == 98.0  # 100 - 2
        assert levels["tp1_price"] == 103.0  # 100 + 2*1.5
        assert levels["tp2_price"] == 105.0  # 100 + 2*2.5

    def test_short_tp_sl(self):
        levels = compute_tp_sl(100.0, "SHORT", atr=2.0, rr1=1.5, rr2=2.5, sl_atr_mult=1.0)
        assert levels["sl_price"] == 102.0
        assert levels["tp1_price"] == 97.0
        assert levels["tp2_price"] == 95.0

    def test_recompute_from_live(self):
        result = recompute_from_live_entry(
            snapshot_entry=100.0, live_entry=101.0,
            side="LONG",
            original_sl=98.0, original_tp1=103.0, original_tp2=105.0,
        )
        assert result["sl_price"] == 99.0  # Shifted +1
        assert result["tp1_price"] == 104.0
        assert result["tp2_price"] == 106.0


# ── PnL Engine ──────────────────────────────────────────────


class TestPnLEngine:

    def test_long_win(self):
        result = compute_pnl(100.0, 110.0, "LONG", 1000.0, fee_bps=0)
        assert result["pnl"] == 100.0
        assert result["outcome"] == "WIN"

    def test_short_win(self):
        result = compute_pnl(100.0, 90.0, "SHORT", 1000.0, fee_bps=0)
        assert result["pnl"] == 100.0
        assert result["outcome"] == "WIN"

    def test_long_loss_with_fees(self):
        result = compute_pnl(100.0, 99.0, "LONG", 1000.0, fee_bps=5)
        # Raw PnL: (99-100)/100 * 1000 = -10
        # Fees: 1000 * 0.0005 * 2 = 1.0
        # Net: -10 - 1 = -11
        assert result["pnl"] == -11.0
        assert result["outcome"] == "LOSS"

    def test_r_multiple(self):
        r = compute_r_multiple(100.0, 105.0, 98.0, "LONG")
        assert r == 2.5  # 5/2


# ── Price Store ─────────────────────────────────────────────


class TestPriceStore:

    def test_update_and_get(self):
        store = PriceStore(max_age_sec=10)
        store.update("BTC", 50000.0, "test")
        snap = store.get("BTC")
        assert snap is not None
        assert snap.price == 50000.0

    def test_stale_price_returns_none(self):
        store = PriceStore(max_age_sec=0.01)
        store.update("BTC", 50000.0, "test")
        time.sleep(0.02)
        assert store.get("BTC") is None

    def test_case_insensitive(self):
        store = PriceStore()
        store.update("btc", 50000.0, "test")
        assert store.get("BTC") is not None

    def test_all_prices(self):
        store = PriceStore(max_age_sec=10)
        store.update("BTC", 50000.0, "test")
        store.update("ETH", 3000.0, "test")
        prices = store.all_prices()
        assert len(prices) == 2

    def test_stats(self):
        store = PriceStore(max_age_sec=10)
        store.update("BTC", 50000.0, "test")
        s = store.stats()
        assert s["total"] == 1
        assert s["fresh"] == 1


# ── Telemetry ───────────────────────────────────────────────


class TestTelemetry:

    def setup_method(self):
        Telemetry.reset()

    def test_increment(self):
        Telemetry.inc("total_signals")
        Telemetry.inc("total_signals")
        snap = Telemetry.snapshot()
        assert snap["total_signals"] == 2

    def test_record_rolling(self):
        Telemetry.record("snapshot_ages", 3.0)
        Telemetry.record("snapshot_ages", 5.0)
        snap = Telemetry.snapshot()
        assert snap["avg_snapshot_age"] == 4.0

    def test_format_telegram(self):
        Telemetry.inc("total_signals", 10)
        Telemetry.inc("human_copy_trades", 2)
        text = Telemetry.format_telegram()
        assert "TELEMETRY" in text
        assert "10" in text


# ── Replay Engine ───────────────────────────────────────────


class TestReplayEngine:

    def _write_csv(self, tmp_path, rows):
        path = str(tmp_path / "test_trades.csv")
        if not rows:
            return path
        headers = list(rows[0].keys())
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=headers)
            w.writeheader()
            for r in rows:
                w.writerow(r)
        return path

    def test_replay_empty_file(self, tmp_path):
        path = self._write_csv(tmp_path, [])
        result = replay_from_csv(path)
        assert result.total_trades == 0

    def test_replay_detects_stale(self, tmp_path):
        rows = [
            {"symbol": "BTC", "side": "LONG", "entry": "100",
             "snapshot_age_seconds": "15", "slippage_pct": "0.1",
             "realized_pnl": "10"},
        ]
        path = self._write_csv(tmp_path, rows)
        result = replay_from_csv(path, max_snapshot_age_s=10.0)
        assert result.stale_signal_count == 1

    def test_replay_detects_slippage(self, tmp_path):
        rows = [
            {"symbol": "BTC", "side": "LONG",
             "snapshot_entry": "100", "live_entry": "101",
             "slippage_pct": "1.0", "realized_pnl": "5"},
        ]
        path = self._write_csv(tmp_path, rows)
        result = replay_from_csv(path, max_slippage_pct=0.5)
        assert result.slippage_anomaly_count == 1

    def test_replay_detects_impossible_long_entry(self, tmp_path):
        rows = [
            {"symbol": "SOL", "side": "LONG",
             "entry": "100", "sl": "102", "tp1": "110",
             "realized_pnl": "0"},
        ]
        path = self._write_csv(tmp_path, rows)
        result = replay_from_csv(path)
        assert result.impossible_trade_count >= 1

    def test_replay_detects_impossible_short_entry(self, tmp_path):
        rows = [
            {"symbol": "SOL", "side": "SHORT",
             "entry": "100", "sl": "98", "tp1": "90",
             "realized_pnl": "0"},
        ]
        path = self._write_csv(tmp_path, rows)
        result = replay_from_csv(path)
        assert result.impossible_trade_count >= 1

    def test_format_replay_report(self):
        result = ReplayResult(
            total_trades=50, stale_signal_count=3,
            slippage_anomaly_count=2, impossible_trade_count=1,
            original_pnl=100.0, corrected_pnl=95.0,
            pnl_difference=-5.0,
        )
        text = format_replay_report(result)
        assert "50" in text
        assert "Stale" in text
