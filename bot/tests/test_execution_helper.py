"""
Tests for Hyperliquid Execution Helper.

Covers:
- Price rounding to tick size
- Quantity rounding to min step
- Limit offset calculation
- SL/TP formatting
- Partial close sizing (50/50 split)
- Leverage capping
- Symbol normalization
- Full integration with alerts
"""

import pytest
from unittest.mock import patch, MagicMock
from manual.execution_helper import (
    HyperliquidOrder,
    HyperliquidOrderBuilder,
    format_quick_entry,
    format_exit_orders,
    format_full_execution_block,
    LIMIT_OFFSET_PCT,
)
from manual.sniper_filter import SniperSignal


def _make_sniper(
    symbol="HYPE",
    side="BUY",
    entry=25.0,
    sl=24.50,
    tp_scalp=25.75,
    tp_swing=26.50,
    leverage=25,
    qty=40.0,
    confidence=90,
    tier="SNIPER",
    **kwargs,
) -> SniperSignal:
    """Create a test SniperSignal with sensible defaults."""
    defaults = dict(
        symbol=symbol,
        side=side,
        tier=tier,
        entry=entry,
        sl=sl,
        tp_scalp=tp_scalp,
        tp_swing=tp_swing,
        leverage=leverage,
        risk_pct=0.10,
        risk_amount=10.0,
        position_size_usd=entry * qty,
        qty=qty,
        margin_required=(entry * qty) / leverage,
        pnl_scalp=30.0,
        pnl_swing=60.0,
        loss_amount=10.0,
        rr_scalp=1.5,
        rr_swing=3.0,
        account_equity=100.0,
        account_after_win=130.0,
        account_after_loss=90.0,
        growth_pct=30.0,
        confidence=confidence,
        num_agree=3,
        strategies=["regime_trend", "monte_carlo_zones", "confidence_scorer"],
        regime="trend",
        ev_per_dollar=0.087,
        signal_context="Strong trend setup",
        timestamp="2026-03-24T12:00:00+00:00",
        daily_target_pct=60.0,
        hold_target_hours="1-4h (scalp)",
    )
    defaults.update(kwargs)
    return SniperSignal(**defaults)


class TestHyperliquidOrderBuilder:
    """Tests for order builder core logic."""

    def test_basic_long_order(self):
        """Builder produces correct long order from sniper signal."""
        signal = _make_sniper(symbol="HYPE", side="BUY", entry=25.0)
        builder = HyperliquidOrderBuilder()
        order = builder.from_sniper_signal(signal)

        assert order.symbol == "HYPE"
        assert order.side == "buy"
        assert order.direction == "LONG"
        assert order.order_type == "limit"
        assert order.reduce_only is False
        assert order.leverage <= 20  # HYPE max is 20x

    def test_basic_short_order(self):
        """Builder produces correct short order."""
        signal = _make_sniper(side="SELL", entry=25.0, sl=25.50, tp_scalp=24.25, tp_swing=23.50)
        builder = HyperliquidOrderBuilder()
        order = builder.from_sniper_signal(signal)

        assert order.side == "sell"
        assert order.direction == "SHORT"
        # Limit price should be above market for shorts
        assert order.price > signal.entry

    def test_symbol_normalization(self):
        """Strips /USDC and :USDC suffixes."""
        builder = HyperliquidOrderBuilder()

        assert builder._normalize_symbol("HYPE/USDC") == "HYPE"
        assert builder._normalize_symbol("BTC/USDC:USDC") == "BTC"
        assert builder._normalize_symbol("SOL") == "SOL"
        assert builder._normalize_symbol("ETH/USD") == "ETH"


class TestPriceRounding:
    """Tests for price rounding to Hyperliquid tick sizes."""

    def test_hype_tick_size(self):
        """HYPE tick size is 0.0001 (4 decimal places)."""
        signal = _make_sniper(symbol="HYPE", entry=25.1234567)
        builder = HyperliquidOrderBuilder()
        order = builder.from_sniper_signal(signal)

        # Price should be rounded to 4 decimals
        price_str = f"{order.price:.4f}"
        assert order.price == float(price_str)

    def test_btc_tick_size(self):
        """BTC tick size is 0.1 (1 decimal place)."""
        signal = _make_sniper(
            symbol="BTC", entry=67234.56, sl=66800.0,
            tp_scalp=67600.0, tp_swing=68000.0, qty=0.015, leverage=25,
        )
        builder = HyperliquidOrderBuilder()
        order = builder.from_sniper_signal(signal)

        # Price should be rounded to 1 decimal
        price_str = f"{order.price:.1f}"
        assert order.price == float(price_str)

    def test_sol_tick_size(self):
        """SOL tick size is 0.001 (3 decimal places)."""
        signal = _make_sniper(
            symbol="SOL", entry=185.4567, sl=183.0,
            tp_scalp=187.0, tp_swing=190.0, qty=5.4, leverage=20,
        )
        builder = HyperliquidOrderBuilder()
        order = builder.from_sniper_signal(signal)

        price_str = f"{order.price:.3f}"
        assert order.price == float(price_str)

    def test_sl_tp_rounded_to_tick(self):
        """SL and TP triggers must also be rounded to tick size."""
        signal = _make_sniper(
            symbol="HYPE", entry=25.0, sl=24.44447, tp_scalp=25.77773, tp_swing=26.55559,
        )
        builder = HyperliquidOrderBuilder()
        order = builder.from_sniper_signal(signal)

        # All prices at 4 decimal precision for HYPE
        for price in [order.sl_trigger, order.tp1_trigger, order.tp2_trigger]:
            assert price == round(price, 4)


class TestQuantityRounding:
    """Tests for quantity rounding to Hyperliquid min qty steps."""

    def test_hype_qty_rounding(self):
        """HYPE min_qty=1.0, qty precision=1 decimal."""
        signal = _make_sniper(symbol="HYPE", qty=10.789)
        builder = HyperliquidOrderBuilder()
        order = builder.from_sniper_signal(signal)

        # HYPE qty has 1 decimal precision, rounds down
        assert order.size == 10.7

    def test_btc_qty_rounding(self):
        """BTC min_qty=0.001, qty precision=5 decimals."""
        signal = _make_sniper(
            symbol="BTC", entry=67000.0, sl=66500.0,
            tp_scalp=67500.0, tp_swing=68000.0, qty=0.0149876, leverage=25,
        )
        builder = HyperliquidOrderBuilder()
        order = builder.from_sniper_signal(signal)

        # BTC qty has 5 decimal precision, rounds down
        assert order.size == 0.01498

    def test_xrp_qty_rounding(self):
        """XRP min_qty=10.0, qty precision=0 decimals (integers)."""
        signal = _make_sniper(
            symbol="XRP", entry=0.62, sl=0.60,
            tp_scalp=0.64, tp_swing=0.66, qty=161.29, leverage=20,
        )
        builder = HyperliquidOrderBuilder()
        order = builder.from_sniper_signal(signal)

        # XRP qty is integer (0 decimal precision), rounds down
        assert order.size == 161.0

    def test_min_qty_enforced(self):
        """If rounded qty falls below min, snap up to min_qty."""
        signal = _make_sniper(symbol="HYPE", qty=0.3)  # Below HYPE min of 1.0
        builder = HyperliquidOrderBuilder()
        order = builder.from_sniper_signal(signal)

        assert order.size >= 1.0  # HYPE min_qty is 1.0


class TestLimitOffset:
    """Tests for limit price offset calculation."""

    def test_long_limit_below_market(self):
        """Long limit price should be below market price."""
        signal = _make_sniper(side="BUY", entry=25.0)
        builder = HyperliquidOrderBuilder()
        order = builder.from_sniper_signal(signal)

        assert order.price < order.market_price

    def test_short_limit_above_market(self):
        """Short limit price should be above market price."""
        signal = _make_sniper(side="SELL", entry=25.0, sl=25.50, tp_scalp=24.25, tp_swing=23.50)
        builder = HyperliquidOrderBuilder()
        order = builder.from_sniper_signal(signal)

        assert order.price > order.market_price

    def test_offset_magnitude(self):
        """Offset should be approximately LIMIT_OFFSET_PCT of market price."""
        entry = 25.0
        signal = _make_sniper(side="BUY", entry=entry)
        builder = HyperliquidOrderBuilder()
        order = builder.from_sniper_signal(signal)

        actual_offset = abs(order.market_price - order.price) / order.market_price
        # Allow small rounding error due to tick size quantization
        assert abs(actual_offset - LIMIT_OFFSET_PCT) < 0.001


class TestLeverageCapping:
    """Tests for leverage capping to symbol maximum."""

    def test_hype_max_leverage_20(self):
        """HYPE max leverage is 20x — signal requesting 25x should be capped."""
        signal = _make_sniper(symbol="HYPE", leverage=25)
        builder = HyperliquidOrderBuilder()
        order = builder.from_sniper_signal(signal)

        assert order.leverage == 20

    def test_btc_max_leverage_50(self):
        """BTC allows up to 50x — 25x should pass through."""
        signal = _make_sniper(
            symbol="BTC", entry=67000.0, sl=66500.0,
            tp_scalp=67500.0, tp_swing=68000.0, qty=0.015, leverage=25,
        )
        builder = HyperliquidOrderBuilder()
        order = builder.from_sniper_signal(signal)

        assert order.leverage == 25

    def test_wif_max_leverage_10(self):
        """WIF max leverage is 10x."""
        signal = _make_sniper(
            symbol="WIF", entry=2.50, sl=2.40,
            tp_scalp=2.60, tp_swing=2.70, qty=40.0, leverage=25,
        )
        builder = HyperliquidOrderBuilder()
        order = builder.from_sniper_signal(signal)

        assert order.leverage == 10

    def test_leverage_always_integer(self):
        """Leverage should be an integer."""
        signal = _make_sniper(leverage=22.7)
        builder = HyperliquidOrderBuilder()
        order = builder.from_sniper_signal(signal)

        assert isinstance(order.leverage, int)


class TestPartialCloseSizing:
    """Tests for 50/50 TP split sizing."""

    def test_even_split(self):
        """Size splits evenly for TP1 and TP2."""
        signal = _make_sniper(symbol="HYPE", qty=10.0)
        builder = HyperliquidOrderBuilder()
        order = builder.from_sniper_signal(signal)

        assert order.size_half == 5.0
        assert order.size_remaining == 5.0

    def test_split_respects_min_qty(self):
        """If half is below min_qty, adjust split."""
        signal = _make_sniper(symbol="HYPE", qty=1.0)  # HYPE min_qty=1.0
        builder = HyperliquidOrderBuilder()
        order = builder.from_sniper_signal(signal)

        # Half of 1.0 = 0.5, which is below min_qty of 1.0
        # Should fall back to full size on TP1
        assert order.size_half == 1.0
        assert order.size_remaining == 0.0

    def test_split_sums_to_total(self):
        """Half + remaining should equal total size."""
        signal = _make_sniper(symbol="HYPE", qty=20.0)
        builder = HyperliquidOrderBuilder()
        order = builder.from_sniper_signal(signal)

        assert order.size_half + order.size_remaining == order.size


class TestFormatQuickEntry:
    """Tests for Telegram quick entry formatting."""

    def test_contains_essential_fields(self):
        """Quick entry must contain symbol, direction, leverage, price, size, margin."""
        signal = _make_sniper()
        builder = HyperliquidOrderBuilder()
        order = builder.from_sniper_signal(signal)
        text = format_quick_entry(order)

        assert "HYPE" in text
        assert "LONG" in text
        assert "Limit:" in text
        assert "Size:" in text
        assert "Margin:" in text
        assert "SL:" in text
        assert "TP1:" in text
        assert "TP2:" in text
        assert "Cancel if not filled" in text

    def test_short_direction_label(self):
        """Short signals show SHORT in the output."""
        signal = _make_sniper(side="SELL", sl=25.50, tp_scalp=24.25, tp_swing=23.50)
        builder = HyperliquidOrderBuilder()
        order = builder.from_sniper_signal(signal)
        text = format_quick_entry(order)

        assert "SHORT" in text

    def test_no_empty_prices(self):
        """Formatted prices should not contain $0 or $0.00."""
        signal = _make_sniper()
        builder = HyperliquidOrderBuilder()
        order = builder.from_sniper_signal(signal)
        text = format_quick_entry(order)

        assert "$0.00" not in text
        assert "$0," not in text


class TestFormatExitOrders:
    """Tests for exit order formatting."""

    def test_contains_stop_and_tp(self):
        """Exit orders must include stop market and limit TP orders."""
        signal = _make_sniper(qty=20.0)
        builder = HyperliquidOrderBuilder()
        order = builder.from_sniper_signal(signal)
        text = format_exit_orders(order)

        assert "Stop Market" in text
        assert "Limit" in text
        assert "SELL" in text  # Exit side for a long
        assert "full size" in text

    def test_short_exit_uses_buy(self):
        """Exit orders for a short should use BUY."""
        signal = _make_sniper(side="SELL", sl=25.50, tp_scalp=24.25, tp_swing=23.50, qty=20.0)
        builder = HyperliquidOrderBuilder()
        order = builder.from_sniper_signal(signal)
        text = format_exit_orders(order)

        assert "BUY" in text

    def test_small_size_no_split(self):
        """If size too small to split, show single TP order."""
        signal = _make_sniper(symbol="HYPE", qty=1.0)
        builder = HyperliquidOrderBuilder()
        order = builder.from_sniper_signal(signal)
        text = format_exit_orders(order)

        # Should only have 2 orders (SL + single TP), not 3
        assert "1." in text
        assert "2." in text
        assert "3." not in text


class TestFormatFullBlock:
    """Tests for the combined execution block."""

    def test_contains_both_sections(self):
        """Full block must contain both entry and exit sections."""
        signal = _make_sniper(qty=20.0)
        builder = HyperliquidOrderBuilder()
        order = builder.from_sniper_signal(signal)
        text = format_full_execution_block(order)

        assert "QUICK ENTRY" in text
        assert "Set these orders NOW" in text

    def test_separator_lines(self):
        """Block should have visual separators."""
        signal = _make_sniper()
        builder = HyperliquidOrderBuilder()
        order = builder.from_sniper_signal(signal)
        text = format_full_execution_block(order)

        assert "\u2500" in text  # Box drawing character for separator


class TestAlertsIntegration:
    """Tests that execution helper integrates with alerts.py."""

    def test_sniper_alert_includes_execution_block(self):
        """format_sniper_alert should include the execution block."""
        from manual.alerts import format_sniper_alert

        signal = _make_sniper(qty=20.0)
        text = format_sniper_alert(signal)

        assert "QUICK ENTRY" in text
        assert "Set these orders NOW" in text

    def test_alert_still_has_key_sections(self):
        """Alert should contain essential trading info."""
        from manual.alerts import format_sniper_alert

        signal = _make_sniper()
        text = format_sniper_alert(signal)

        # Key info present in simplified alert
        assert "Entry" in text
        assert "Stop" in text
        assert "Margin" in text
        assert "Win" in text
        assert "Loss" in text
        assert "QUICK ENTRY" in text  # Execution block
