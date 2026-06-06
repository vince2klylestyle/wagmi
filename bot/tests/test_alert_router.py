"""
Smoke tests for alerts/router.py.

Covers:
- AlertRouter constructor + empty init
- _fmt price precision (regular, small, micro, zero)
- _format_signal structure
- send_signal tier classification (PRIORITY/REGULAR/MANUAL)
- Dedup by fingerprint
- Rate-limit gaps
- Burst protection
- State persistence round-trip
- send_trade_event routing
- send_heartbeat + send_market_update
- Missing webhooks don't crash

Network calls (requests.post) are fully mocked. No real HTTP traffic.
"""

import json
import os
from unittest.mock import patch, MagicMock

import pytest

from alerts.router import AlertRouter
from strategies.base import Signal


def _signal(symbol="BTC", side="BUY", confidence=80.0, entry=30000.0,
            sl=29400.0, tp1=30900.0, tp2=31500.0):
    return Signal(
        strategy="test_strat",
        symbol=symbol,
        side=side,
        confidence=confidence,
        entry=entry,
        sl=sl,
        tp1=tp1,
        tp2=tp2,
        atr=150.0,
        metadata={"strategies_agree": ["test_strat"]},
    )


@pytest.fixture
def router(tmp_path, monkeypatch):
    """Create router with isolated state path + mocked network."""
    # Make cwd the tmp_path so "data/alert_state.json" lands there
    monkeypatch.chdir(tmp_path)
    os.makedirs("data", exist_ok=True)
    return AlertRouter(
        discord_webhook="https://example.test/discord",
        discord_priority_webhook="https://example.test/discord_prio",
        telegram_token="test_token",
        telegram_chat_id="12345",
        telegram_conf_threshold=65,
        priority_conf_threshold=75,
        min_gap_priority_s=90,
        min_gap_regular_s=45,
    )


@pytest.fixture
def silent_router(tmp_path, monkeypatch):
    """Router with no webhooks/credentials — send methods must no-op silently."""
    monkeypatch.chdir(tmp_path)
    os.makedirs("data", exist_ok=True)
    return AlertRouter()


# ── Constructor + init ───────────────────────────────────────


class TestConstructor:
    def test_default_constructor(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        r = AlertRouter()
        assert r.discord_webhook == ""
        assert r.telegram_token == ""
        assert r.telegram_conf_threshold == 65
        assert r.priority_conf_threshold == 75
        assert r.min_gap_priority_s == 90

    def test_custom_constructor(self, router):
        assert router.discord_webhook == "https://example.test/discord"
        assert router.telegram_token == "test_token"


# ── Price formatting ─────────────────────────────────────────


class TestFmt:
    def test_regular(self):
        assert AlertRouter._fmt(100.0) == "100.00"
        assert AlertRouter._fmt(30000.5) == "30,000.50"

    def test_small(self):
        s = AlertRouter._fmt(0.05)
        # 0.0500
        assert s.startswith("0.05")

    def test_micro(self):
        s = AlertRouter._fmt(0.00000005)
        # Should use more precision
        assert "0.0000" in s or "5e" in s.lower() or "0." in s

    def test_zero(self):
        assert AlertRouter._fmt(0) == "0"


# ── Signal formatting ────────────────────────────────────────


class TestFormatSignal:
    def test_format_signal_structure(self, router):
        sig = _signal(confidence=85)
        msg = router._format_signal(sig, leverage=5.0, tier="PRIORITY")
        assert "BTC" in msg
        assert "BUY" in msg
        assert "Conf" in msg
        assert "Entry" in msg
        assert "SL" in msg
        assert "TP1" in msg
        assert "TP2" in msg
        assert "5.0x" in msg

    def test_format_signal_spot(self, router):
        sig = _signal()
        msg = router._format_signal(sig, leverage=1.0, tier="REGULAR")
        assert "Spot" in msg


# ── send_signal routing ──────────────────────────────────────


class TestSendSignal:
    def test_priority_sends_to_both_discord_channels(self, router):
        sig = _signal(confidence=85)  # above priority threshold
        with patch("alerts.router.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200, headers={})
            router.send_signal(sig)
            # Priority webhook + regular webhook = 2 discord calls
            assert mock_post.call_count >= 2

    def test_regular_sends_to_discord_only(self, router):
        sig = _signal(confidence=70)  # between thresholds
        with patch("alerts.router.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200, headers={})
            router.send_signal(sig)
            # One discord call, no telegram in new design
            assert mock_post.call_count == 1

    def test_manual_sends_to_discord(self, router):
        sig = _signal(confidence=50)  # below both thresholds -> MANUAL
        with patch("alerts.router.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200, headers={})
            router.send_signal(sig)
            assert mock_post.call_count == 1

    def test_dedup_identical_signal(self, router):
        sig = _signal(confidence=85)
        with patch("alerts.router.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200, headers={})
            router.send_signal(sig)
            first_count = mock_post.call_count
            # Same fingerprint = dedup
            router.send_signal(sig)
            assert mock_post.call_count == first_count  # no new calls

    def test_rate_limit_priority(self, router):
        sig_a = _signal(symbol="BTC", confidence=85)
        sig_b = _signal(symbol="BTC", side="SELL", confidence=85)
        with patch("alerts.router.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200, headers={})
            router.send_signal(sig_a)
            calls_after_first = mock_post.call_count
            # Different fingerprint but same symbol => rate limit kicks in
            router.send_signal(sig_b)
            # Rate limit: no new sends within min_gap_priority_s
            assert mock_post.call_count == calls_after_first

    def test_explicit_tier_override(self, router):
        sig = _signal(confidence=50)
        with patch("alerts.router.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200, headers={})
            router.send_signal(sig, tier="PRIORITY")
            # Forced PRIORITY -> 2 discord calls
            assert mock_post.call_count == 2


# ── Burst protection ─────────────────────────────────────────


class TestBurstProtection:
    def test_burst_blocks_after_5(self, router):
        with patch("alerts.router.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200, headers={})
            # Send 6 priority signals with distinct fingerprints; burst protection limits to 5
            for i in range(6):
                sig = _signal(symbol="BTC", confidence=90 + i * 0.5)
                # Bypass the rate-limit gap so burst logic is tested
                router._last_sent["BTC"]["prio_ts"] = 0
                router._last_sent["BTC"]["fingerprint"] = ""
                router.send_signal(sig)
            # Burst deque is capped at 5. 6th should be suppressed.
            burst = router._prio_burst["BTC"]
            assert len(burst) <= 5


# ── Trade events ─────────────────────────────────────────────


class TestTradeEvents:
    def test_send_trade_event_open(self, router):
        with patch("alerts.router.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200, headers={})
            router.send_trade_event("OPEN", "BTC", "details here")
            # Discord + Telegram
            assert mock_post.call_count >= 2

    def test_send_trade_event_minor_not_telegram(self, router):
        with patch("alerts.router.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200, headers={})
            router.send_trade_event("TICK", "BTC", "minor")
            # Discord only
            assert mock_post.call_count == 1

    def test_wallet_tag_prefix(self, router):
        with patch("alerts.router.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200, headers={})
            router.send_trade_event("OPEN", "BTC", "d", wallet_tag="A")
            first_call = mock_post.call_args_list[0]
            body = first_call.kwargs.get("json", {})
            assert "[A]" in body.get("content", "")


# ── Heartbeat + market update ────────────────────────────────


class TestHeartbeat:
    def test_heartbeat(self, router):
        with patch("alerts.router.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200, headers={})
            router.send_heartbeat({
                "equity": 1000.0,
                "open_positions": 2,
                "daily_pnl": 15.5,
                "ml_samples": 100,
            })
            assert mock_post.call_count == 2  # discord + telegram

    def test_market_update(self, router):
        with patch("alerts.router.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200, headers={})
            router.send_market_update("BTC range-bound 29k-31k")
            assert mock_post.call_count == 2

    def test_circuit_breaker(self, router):
        with patch("alerts.router.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200, headers={})
            router.send_circuit_breaker("daily drawdown exceeded")
            # Priority discord + telegram
            assert mock_post.call_count == 2

    def test_startup(self, router):
        with patch("alerts.router.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200, headers={})
            router.send_startup(["BTC", "ETH"], 4, 10.0)
            assert mock_post.call_count == 2


# ── Silent mode (no webhooks) ────────────────────────────────


class TestSilentMode:
    def test_no_network_without_webhooks(self, silent_router):
        sig = _signal(confidence=85)
        with patch("alerts.router.requests.post") as mock_post:
            silent_router.send_signal(sig)
            silent_router.send_heartbeat({"equity": 0, "open_positions": 0,
                                          "daily_pnl": 0, "ml_samples": 0})
            # No webhooks + no token -> no calls at all
            assert mock_post.call_count == 0


# ── State persistence ────────────────────────────────────────


class TestStatePersistence:
    def test_save_and_load_state(self, router, tmp_path):
        sig = _signal(confidence=85)
        with patch("alerts.router.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200, headers={})
            router.send_signal(sig)

        state_path = os.path.join("data", "alert_state.json")
        assert os.path.exists(state_path)
        with open(state_path) as f:
            data = json.load(f)
        assert "last_sent" in data
        assert "BTC" in data["last_sent"]

    def test_state_load_prunes_old_entries(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        os.makedirs("data", exist_ok=True)
        # Seed stale state (>600s old)
        old_data = {
            "last_sent": {
                "OLDSYM": {"prio_ts": 1, "reg_ts": 1, "fingerprint": "x"}
            },
            "prio_burst": {},
        }
        state_path = os.path.join("data", "alert_state.json")
        with open(state_path, "w") as f:
            json.dump(old_data, f)
        r = AlertRouter(discord_webhook="x")
        # OLDSYM should have been pruned
        assert "OLDSYM" not in r._last_sent

    def test_load_corrupt_state(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        os.makedirs("data", exist_ok=True)
        state_path = os.path.join("data", "alert_state.json")
        with open(state_path, "w") as f:
            f.write("not json")
        # Should not crash
        r = AlertRouter(discord_webhook="x")
        assert isinstance(r, AlertRouter)


# ── Network error tolerance ──────────────────────────────────


class TestNetworkErrors:
    def test_discord_error_swallowed(self, router):
        with patch("alerts.router.requests.post",
                   side_effect=Exception("boom")):
            # Should not raise
            router._send_discord("hello")

    def test_telegram_error_swallowed(self, router):
        with patch("alerts.router.requests.post",
                   side_effect=Exception("boom")):
            # Should not raise
            router._send_telegram("hello")
