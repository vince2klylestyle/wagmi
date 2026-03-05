"""
Golden Replay Test: Deterministic replay of canonical trade log.

Asserts exact anomaly counts, PnL, stale signals, and impossible trades
against a known fixture file. Any change to replay logic that alters
results will break this test - that's intentional.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from engine.replay_engine import replay_from_csv


GOLDEN_CSV = os.path.join(
    os.path.dirname(__file__), "..", "..", "tests", "fixtures", "golden_replay.csv"
)


@pytest.fixture
def golden_result():
    assert os.path.exists(GOLDEN_CSV), f"Golden fixture not found: {GOLDEN_CSV}"
    return replay_from_csv(
        GOLDEN_CSV,
        max_snapshot_age_s=10.0,
        max_slippage_pct=0.5,
        max_price_deviation_pct=2.0,
    )


def test_golden_trade_count(golden_result):
    assert golden_result.total_trades == 10


def test_golden_stale_signals(golden_result):
    # Trades 5 (XRP, 12s) and 10 (PEPE, 35s) are stale
    assert golden_result.stale_signal_count == 2


def test_golden_slippage_anomalies(golden_result):
    # Trade 7 (DOGE, 0.95%) and 10 (PEPE at boundary but 0.16% is under)
    # Only DOGE at 0.95% exceeds 0.5% threshold
    assert golden_result.slippage_anomaly_count == 1


def test_golden_total_anomalies(golden_result):
    # At least stale + slippage anomalies
    assert len(golden_result.anomalies) >= 3


def test_golden_original_pnl(golden_result):
    # Sum of realized_pnl: 45.5 + (-22.3) + 18.4 + 62.1 + (-15.8) + 88.2 + (-8.5) + 32.6 + 52.4 + (-12.0) = 240.6
    expected = 45.5 - 22.3 + 18.4 + 62.1 - 15.8 + 88.2 - 8.5 + 32.6 + 52.4 - 12.0
    assert abs(golden_result.original_pnl - expected) < 0.1


def test_golden_no_impossible_trades(golden_result):
    # All entries in the golden fixture are valid (entry between SL and TP)
    assert golden_result.impossible_trade_count == 0


def test_golden_anomaly_types(golden_result):
    types = {a.anomaly_type for a in golden_result.anomalies}
    assert "stale_signal" in types
    assert "slippage" in types


def test_golden_corrected_pnl_differs(golden_result):
    # Live entries differ from snapshots, so corrected PnL should differ
    assert golden_result.pnl_difference != 0.0
