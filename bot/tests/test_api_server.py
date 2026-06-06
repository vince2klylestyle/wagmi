"""
Smoke + contract tests for bot/api_server.py.

These tests verify:
- All endpoints register and respond with the expected shape.
- Endpoints degrade gracefully when data files are missing.
- Signals / OHLCV / activity-feed / backtest / agents endpoints return
  reasonable empty payloads when the data files are empty.
"""

import os
import sys
import pytest

# Ensure bot/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from fastapi.testclient import TestClient  # noqa: F401
except ImportError:
    pytest.skip("fastapi not installed — skipping api_server tests", allow_module_level=True)

import api_server  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def client():
    return TestClient(api_server.app)


class TestHealth:
    def test_health_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        assert "ts" in data


class TestCoreEndpoints:
    def test_summary_shape(self, client):
        r = client.get("/v1/summary")
        assert r.status_code == 200
        data = r.json()
        for key in ("equity", "peak_equity", "total_trades", "win_rate", "total_pnl", "open_positions"):
            assert key in data

    def test_strategies_list(self, client):
        r = client.get("/v1/strategies")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data.get("strategies"), list)
        assert len(data["strategies"]) > 0

    def test_agents_overview(self, client):
        r = client.get("/v1/agents/overview")
        assert r.status_code == 200
        data = r.json()
        agents = data.get("agents")
        assert isinstance(agents, list) and len(agents) == 9


class TestNewlyAddedEndpoints:
    """Endpoints added during the half-built-feature sweep."""

    def test_signals_shape(self, client):
        r = client.get("/v1/signals")
        assert r.status_code == 200
        data = r.json()
        assert "signals" in data
        assert "last_updated" in data
        # signals is a dict keyed by symbol (possibly empty if no trade history)
        assert isinstance(data["signals"], dict)

    def test_signals_cache_same_response(self, client):
        """Two calls within TTL should return identical payload."""
        r1 = client.get("/v1/signals")
        r2 = client.get("/v1/signals")
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json()["last_updated"] == r2.json()["last_updated"]

    def test_ohlcv_shape(self, client):
        r = client.get("/v1/ohlcv", params={"symbol": "BTC", "timeframe": "1h", "limit": 10})
        assert r.status_code == 200
        data = r.json()
        assert data.get("symbol") == "BTC"
        assert data.get("timeframe") == "1h"
        assert isinstance(data.get("candles"), list)

    def test_ohlcv_unknown_symbol_empty(self, client):
        r = client.get("/v1/ohlcv", params={"symbol": "NOPE_NOT_A_REAL_SYMBOL"})
        assert r.status_code == 200
        assert r.json().get("candles") == []

    def test_activity_feed_shape(self, client):
        r = client.get("/v1/activity/feed", params={"limit": 10})
        assert r.status_code == 200
        data = r.json()
        assert "feed" in data
        assert isinstance(data["feed"], list)
        assert data["count"] == len(data["feed"])
        # Each item should have kind + ts + symbol
        for item in data["feed"]:
            assert "kind" in item
            assert item["kind"] in ("trade", "sniper_alert")
            assert "ts" in item
            assert "symbol" in item

    def test_backtest_runs_list(self, client):
        r = client.get("/v1/backtest/runs")
        assert r.status_code == 200
        data = r.json()
        assert "results" in data
        assert isinstance(data["results"], list)
        # If any runs exist, verify meta shape
        if data["results"]:
            meta = data["results"][0]
            for key in ("id", "file", "created_at", "size_bytes"):
                assert key in meta

    def test_backtest_results_latest(self, client):
        r = client.get("/v1/backtest/results/latest")
        assert r.status_code == 200
        data = r.json()
        # Either an error or a full detail payload
        assert "error" in data or "results" in data

    def test_backtest_results_unknown_id(self, client):
        r = client.get("/v1/backtest/results/nonexistent_run_id_xyz")
        assert r.status_code == 200
        data = r.json()
        assert "error" in data

    def test_agent_performance_dormant(self, client):
        r = client.get("/v1/agents/regime/performance")
        assert r.status_code == 200
        data = r.json()
        assert data["agent"] == "regime"
        assert "calls" in data
        assert "history" in data

    def test_agent_calibration_dormant(self, client):
        r = client.get("/v1/agents/trade/calibration")
        assert r.status_code == 200
        data = r.json()
        assert data["agent"] == "trade"
        assert "calibration" in data


class TestGracefulDegradation:
    """Every endpoint should return HTTP 200 (never 5xx) for simple shape errors."""

    @pytest.mark.parametrize("path", [
        "/v1/trades/history",
        "/v1/trades/equity-curve",
        "/v1/positions",
        "/v1/account",
        "/v1/signals/funnel",
        "/v1/sniper/recent",
        "/v1/llm/market-view",
        "/v1/llm/feed",
        "/v1/forensics/analysis",
        "/v1/copy/status",
        "/v1/portfolio/allocation",
        "/v1/performance/metrics",
        "/v1/backtest/results",
    ])
    def test_endpoint_returns_200(self, client, path):
        r = client.get(path)
        assert r.status_code == 200, f"{path} returned {r.status_code}"
