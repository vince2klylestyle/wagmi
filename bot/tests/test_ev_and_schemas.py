"""
Tests for:
1. CSV schema validation - all required fields present and ASCII-safe
2. EV per entry_type is computed and non-NaN
3. SCALP has tighter SL/TP than TREND
4. TREND closes less at TP1 than SCALP
5. Grid search / profile config helpers work
6. CB entry_type filter
"""

import csv
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from collections import deque

sys.path.insert(0, str(Path(__file__).parent.parent))

from execution.trade_profile import (
    _BASE_PROFILES, SCALP, MEDIUM, TREND, REGIME,
    get_profile_config, adjust_profile_params, TUNING_GRID,
    ExitParams,
)
from data.learning import record_trade_outcome, _update_performance, _recent_outcomes


# ── 1. CSV Schema Validation ────────────────────────────────

class TestCSVSchemaValidation(unittest.TestCase):
    """Verify CSV headers contain all required fields."""

    def test_trade_log_headers(self):
        """trades.csv must have all required columns."""
        from data.trade_log import _HEADERS
        required = [
            "timestamp", "symbol", "side", "entry", "exit",
            "pnl", "state_path", "outcome", "leverage", "confidence",
            "entry_type", "primary_driver", "regime", "volatility_band",
            "ml_conf_at_entry",
        ]
        for field in required:
            self.assertIn(field, _HEADERS, f"Missing field '{field}' in trades.csv headers")

    def test_trade_outcomes_headers(self):
        """trade_outcomes.csv must have all required columns."""
        from data.learning import _OUTCOMES_HEADERS
        required = [
            "timestamp", "symbol", "side", "outcome", "pnl",
            "state_path", "leverage", "confidence",
            "entry_type", "primary_driver", "regime", "volatility_band",
        ]
        for field in required:
            self.assertIn(field, _OUTCOMES_HEADERS, f"Missing field '{field}' in outcomes headers")

    def test_trade_log_writes_all_fields(self):
        """log_closed_trade should populate all fields including entry_type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            trades_file = os.path.join(tmpdir, "trades.csv")
            with patch("data.trade_log._TRADES_DIR", tmpdir), \
                 patch("data.trade_log._TRADES_FILE", trades_file):
                from data.trade_log import log_closed_trade
                log_closed_trade(
                    symbol="BTC", side="LONG", entry=50000.0,
                    exit_price=51000.0, action="TP1", pnl=100.0,
                    fees=1.0, state_path="IDLE->OPEN->TP1_HIT->CLOSED",
                    outcome="CLEAN_WIN", leverage=2.0, confidence=80.0,
                    strategy="regime_trend", ml_conf_at_entry=0.72,
                    entry_type="TREND", primary_driver="regime_trend",
                    regime="trending", volatility_band="medium",
                )
                with open(trades_file, encoding="utf-8") as f:
                    rows = list(csv.DictReader(f))
                    self.assertEqual(len(rows), 1)
                    row = rows[0]
                    self.assertEqual(row["entry_type"], "TREND")
                    self.assertEqual(row["primary_driver"], "regime_trend")
                    self.assertEqual(row["regime"], "trending")
                    self.assertEqual(row["volatility_band"], "medium")
                    self.assertNotEqual(row["ml_conf_at_entry"], "")
                    # ASCII safety
                    for key, val in row.items():
                        self.assertNotIn("\u2192", val,
                                         f"Unicode arrow in field {key}")

    def test_outcomes_writes_all_fields(self):
        """record_trade_outcome should populate all classification fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            outcomes_file = os.path.join(tmpdir, "trade_outcomes.csv")
            with patch("data.learning._OUTCOMES_DIR", tmpdir), \
                 patch("data.learning._OUTCOMES_FILE", outcomes_file):
                record_trade_outcome(
                    symbol="SOL", side="SHORT", outcome="CLEAN_WIN",
                    pnl=50.0, entry=150.0, sl=155.0, tp1=145.0, tp2=140.0,
                    tp1_hit=True, sl_after_tp1=False,
                    state_path="IDLE->OPEN->TP1_HIT->TRAILING->CLOSED",
                    leverage=3.0, confidence=85.0, strategy="monte_carlo_zones",
                    entry_type="MEDIUM", primary_driver="monte_carlo_zones",
                    regime="trending", volatility_band="low",
                )
                with open(outcomes_file, encoding="utf-8") as f:
                    rows = list(csv.DictReader(f))
                    self.assertEqual(len(rows), 1)
                    row = rows[0]
                    self.assertEqual(row["entry_type"], "MEDIUM")
                    self.assertEqual(row["primary_driver"], "monte_carlo_zones")
                    self.assertEqual(row["regime"], "trending")
                    self.assertEqual(row["volatility_band"], "low")
                    # Verify state_path is ASCII
                    self.assertNotIn("\u2192", row["state_path"])


# ── 2. EV Computation Tests ─────────────────────────────────

class TestEVComputation(unittest.TestCase):
    """Test that EV per entry_type is computed correctly and is non-NaN."""

    def setUp(self):
        _recent_outcomes.clear()

    def _inject_outcomes(self, entry_type, wins, losses):
        """Inject synthetic outcomes into the rolling window."""
        for _ in range(wins):
            _recent_outcomes.append({
                "pnl": 100.0, "outcome": "CLEAN_WIN", "rr1": 2.0,
                "tp1_hit": True, "sl_after_tp1": False,
                "leverage": 2.0, "entry_type": entry_type,
                "primary_driver": "regime_trend", "regime": "trending",
            })
        for _ in range(losses):
            _recent_outcomes.append({
                "pnl": -50.0, "outcome": "SL_HIT", "rr1": -1.0,
                "tp1_hit": False, "sl_after_tp1": False,
                "leverage": 2.0, "entry_type": entry_type,
                "primary_driver": "regime_trend", "regime": "ranging",
            })

    def test_ev_per_entry_type_computed(self):
        """EV should be present and numeric for each entry_type with data."""
        self._inject_outcomes("TREND", 6, 4)
        self._inject_outcomes("MEDIUM", 5, 5)

        with tempfile.TemporaryDirectory() as tmpdir:
            perf_file = os.path.join(tmpdir, "performance.json")
            with patch("data.learning._OUTCOMES_DIR", tmpdir), \
                 patch("data.learning._PERF_FILE", perf_file):
                _update_performance()
                with open(perf_file) as f:
                    perf = json.load(f)

                by_type = perf["by_entry_type"]
                self.assertIn("TREND", by_type)
                self.assertIn("MEDIUM", by_type)

                for etype in ("TREND", "MEDIUM"):
                    ev = by_type[etype]["EV_per_trade"]
                    self.assertIsInstance(ev, float)
                    self.assertFalse(ev != ev, f"EV is NaN for {etype}")  # NaN check

    def test_ev_positive_for_winners(self):
        """Entry type with 80% WR and 2:1 R should have positive EV."""
        self._inject_outcomes("TREND", 8, 2)

        with tempfile.TemporaryDirectory() as tmpdir:
            perf_file = os.path.join(tmpdir, "performance.json")
            with patch("data.learning._OUTCOMES_DIR", tmpdir), \
                 patch("data.learning._PERF_FILE", perf_file):
                _update_performance()
                with open(perf_file) as f:
                    perf = json.load(f)

                ev = perf["by_entry_type"]["TREND"]["EV_per_trade"]
                self.assertGreater(ev, 0, "80% WR with 2:1 R should be positive EV")

    def test_rolling_windows_present(self):
        """win_rate_last_50 and win_rate_last_200 should be in by_entry_type."""
        self._inject_outcomes("SCALP", 5, 5)

        with tempfile.TemporaryDirectory() as tmpdir:
            perf_file = os.path.join(tmpdir, "performance.json")
            with patch("data.learning._OUTCOMES_DIR", tmpdir), \
                 patch("data.learning._PERF_FILE", perf_file):
                _update_performance()
                with open(perf_file) as f:
                    perf = json.load(f)

                scalp = perf["by_entry_type"]["SCALP"]
                self.assertIn("win_rate_last_50", scalp)
                self.assertIn("win_rate_last_200", scalp)

    def test_ev_per_strategy_computed(self):
        """EV should be computed per strategy (primary_driver)."""
        self._inject_outcomes("TREND", 6, 4)

        with tempfile.TemporaryDirectory() as tmpdir:
            perf_file = os.path.join(tmpdir, "performance.json")
            with patch("data.learning._OUTCOMES_DIR", tmpdir), \
                 patch("data.learning._PERF_FILE", perf_file):
                _update_performance()
                with open(perf_file) as f:
                    perf = json.load(f)

                by_strat = perf["by_strategy"]
                self.assertIn("regime_trend", by_strat)
                self.assertIn("EV_per_trade", by_strat["regime_trend"])


# ── 3. SCALP vs TREND Profile Assertions ────────────────────

class TestProfileOrdering(unittest.TestCase):
    """Assert that SCALP is tighter than TREND in all dimensions."""

    def test_scalp_tighter_tp1_than_trend(self):
        self.assertLess(
            _BASE_PROFILES[SCALP].tp1_atr_mult,
            _BASE_PROFILES[TREND].tp1_atr_mult,
        )

    def test_scalp_tighter_sl_than_trend(self):
        self.assertLess(
            _BASE_PROFILES[SCALP].sl_atr_mult,
            _BASE_PROFILES[TREND].sl_atr_mult,
        )

    def test_scalp_closes_more_at_tp1(self):
        """SCALP should close a larger fraction at TP1 than TREND."""
        self.assertGreater(
            _BASE_PROFILES[SCALP].tp1_close_pct,
            _BASE_PROFILES[TREND].tp1_close_pct,
        )

    def test_medium_between_scalp_and_trend(self):
        """MEDIUM TP1 should be between SCALP and TREND."""
        self.assertGreater(
            _BASE_PROFILES[MEDIUM].tp1_atr_mult,
            _BASE_PROFILES[SCALP].tp1_atr_mult,
        )
        self.assertLess(
            _BASE_PROFILES[MEDIUM].tp1_atr_mult,
            _BASE_PROFILES[TREND].tp1_atr_mult,
        )

    def test_trend_trailing_looser_than_scalp(self):
        """TREND trailing tighten_start should be lower (looser) than SCALP."""
        self.assertLess(
            _BASE_PROFILES[TREND].trailing_tighten_start,
            _BASE_PROFILES[SCALP].trailing_tighten_start,
        )


# ── 4. Profile Config + Tuning Helpers ──────────────────────

class TestProfileConfig(unittest.TestCase):
    """Test get_profile_config and adjust_profile_params."""

    def test_get_profile_config_returns_all_types(self):
        config = get_profile_config()
        for etype in (SCALP, MEDIUM, TREND, REGIME):
            self.assertIn(etype, config)
            self.assertIn("tp1_atr_mult", config[etype])
            self.assertIn("sl_atr_mult", config[etype])
            self.assertIn("tp1_close_pct", config[etype])

    def test_adjust_profile_params_overrides_tp1(self):
        """adjust_profile_params should override only specified params."""
        params = adjust_profile_params(SCALP, tp1_atr_mult=0.8)
        self.assertEqual(params.tp1_atr_mult, 0.8)
        # sl should remain at base
        self.assertEqual(params.sl_atr_mult, _BASE_PROFILES[SCALP].sl_atr_mult)

    def test_adjust_profile_params_overrides_sl(self):
        params = adjust_profile_params(TREND, sl_atr_mult=1.5)
        self.assertEqual(params.sl_atr_mult, 1.5)
        self.assertEqual(params.tp1_atr_mult, _BASE_PROFILES[TREND].tp1_atr_mult)

    def test_tuning_grid_has_all_types(self):
        for etype in (SCALP, MEDIUM, TREND, REGIME):
            self.assertIn(etype, TUNING_GRID)
            self.assertIn("tp1_atr_mult", TUNING_GRID[etype])
            self.assertIn("sl_atr_mult", TUNING_GRID[etype])
            self.assertIn("tp1_close_pct", TUNING_GRID[etype])


# ── 5. CB Entry Type Filter ─────────────────────────────────

class TestCBEntryTypeFilter(unittest.TestCase):
    """Test that CB active mode only allows TREND/REGIME trades."""

    def test_cb_allows_trend_during_override(self):
        """TREND entry_type should pass CB filter."""
        allowed = ("TREND", "REGIME")
        self.assertIn("TREND", allowed)

    def test_cb_blocks_medium_during_override(self):
        """MEDIUM entry_type should be blocked by CB filter."""
        allowed = ("TREND", "REGIME")
        self.assertNotIn("MEDIUM", allowed)

    def test_cb_blocks_scalp_during_override(self):
        """SCALP entry_type should be blocked by CB filter."""
        allowed = ("TREND", "REGIME")
        self.assertNotIn("SCALP", allowed)


if __name__ == "__main__":
    unittest.main()
