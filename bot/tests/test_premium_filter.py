"""Tests for the premium alert filter.

Verifies that low-quality signals (like tonight's ETH SHORT 67% 1/9 alert)
get filtered out, and shadow-ledger-verified edges get promoted appropriately.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Make bot/ imports work in tests (same pattern as other test files)
_BOT_ROOT = Path(__file__).resolve().parent.parent
if str(_BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOT_ROOT))

from alerts.premium_filter import (
    AlertTier,
    AlertDecision,
    evaluate_for_alert,
    _SHADOW_EDGES,
    _SHADOW_BLOCKS,
)
from alerts.premium_telegram import (
    format_premium_execute_alert,
    format_premium_watch_alert,
)


# ─── Hard block tests ────────────────────────────────────────────────

def test_sol_sell_regime_trend_always_blocked():
    """0% WR on 149 samples — the worst combo in the book."""
    d = evaluate_for_alert(
        symbol="SOL", side="SELL", strategy="regime_trend",
        confidence=99.0, num_agree=9, regime="trending_bear",
        entry=85.0, sl=86.0, tp1=82.0, tp2=80.0, leverage=5.0,
    )
    assert d.tier == AlertTier.NONE
    assert "shadow-blocked" in d.reason


def test_hype_buy_mtq_always_blocked():
    """36.8% WR. The HYPE #3 money loser from Apr 15 overnight."""
    d = evaluate_for_alert(
        symbol="HYPE", side="BUY", strategy="multi_tier_quality",
        confidence=85.0, num_agree=3, regime="trending_bull",
        entry=44.5, sl=44.0, tp1=45.5, tp2=46.5, leverage=5.0,
    )
    assert d.tier == AlertTier.NONE
    assert "shadow-blocked" in d.reason


def test_eth_sell_regime_trend_always_blocked():
    """23.1% WR on 65 samples."""
    d = evaluate_for_alert(
        symbol="ETH", side="SELL", strategy="regime_trend",
        confidence=80.0, num_agree=3, regime="trending_bear",
        entry=2350.0, sl=2400.0, tp1=2250.0, tp2=2150.0, leverage=5.0,
    )
    assert d.tier == AlertTier.NONE


# ─── Adverse regime tests ────────────────────────────────────────────

def test_hype_buy_illiquid_regime_blocked():
    """8.3% WR on 12 trades — regime is adverse even on a good setup."""
    d = evaluate_for_alert(
        symbol="HYPE", side="BUY", strategy="bollinger_squeeze",
        confidence=88.0, num_agree=3, regime="illiquid",
        entry=44.5, sl=44.0, tp1=45.5, tp2=46.5, leverage=5.0,
    )
    assert d.tier == AlertTier.NONE
    assert "adverse regime" in d.reason


# ─── Premium edge EXECUTE tests ──────────────────────────────────────

def test_hype_buy_bb_premium_execute():
    """HYPE_BUY_bollinger_squeeze (61% WR, 196 samples) with strong consensus."""
    d = evaluate_for_alert(
        symbol="HYPE", side="BUY", strategy="bollinger_squeeze",
        confidence=80.0, num_agree=3, regime="trending_bull",
        entry=44.5, sl=44.0, tp1=45.5, tp2=46.5, leverage=5.0,
        equity=500.0,
    )
    assert d.tier == AlertTier.EXECUTE
    assert d.shadow_wr is not None and 0.6 < d.shadow_wr < 0.65
    assert d.shadow_n == 196
    assert d.size_suggestion_notional is not None
    assert d.size_suggestion_notional > 0


def test_eth_buy_regime_trend_premium_execute():
    """ETH_BUY_regime_trend (100% WR, 135 samples) — premium alpha."""
    d = evaluate_for_alert(
        symbol="ETH", side="BUY", strategy="regime_trend",
        confidence=85.0, num_agree=4, regime="trending_bull",
        entry=2356.0, sl=2310.0, tp1=2450.0, tp2=2550.0, leverage=5.0,
    )
    assert d.tier == AlertTier.EXECUTE
    assert d.shadow_wr == 1.00


# ─── Premium edge WATCH tests ────────────────────────────────────────

def test_premium_edge_low_confidence_watches():
    """Premium setup but confidence below 75% → WATCH, not EXECUTE."""
    d = evaluate_for_alert(
        symbol="HYPE", side="BUY", strategy="bollinger_squeeze",
        confidence=70.0, num_agree=2, regime="trending_bull",
        entry=44.5, sl=44.0, tp1=45.5, tp2=46.5, leverage=5.0,
    )
    assert d.tier == AlertTier.WATCH
    assert any("confidence" in m for m in d.key_conditions_missing)


def test_premium_edge_solo_watches():
    """Premium setup but only 1 strategy → WATCH, not EXECUTE."""
    d = evaluate_for_alert(
        symbol="HYPE", side="BUY", strategy="bollinger_squeeze",
        confidence=85.0, num_agree=1, regime="trending_bull",
        entry=44.5, sl=44.0, tp1=45.5, tp2=46.5, leverage=5.0,
    )
    assert d.tier == AlertTier.WATCH
    assert any("strategy" in m.lower() or "agreeing" in m for m in d.key_conditions_missing)


# ─── The ETH SHORT 67% alert from Apr 16 ─────────────────────────────

def test_tonights_eth_alert_is_filtered():
    """Replay tonight's actual alert — should get NONE, not a user-facing push."""
    # Signal as it actually fired:
    #   ETH, side=BUY (misreported as SHORT in broken header, but underlying=BUY)
    #   confidence 67%, 1/9 strategies, illiquid regime, driver=confidence_scorer
    d = evaluate_for_alert(
        symbol="ETH", side="BUY", strategy="confidence_scorer",
        confidence=67.0, num_agree=1, regime="illiquid",
        entry=2356.01, sl=2310.44, tp1=2449.83, tp2=2542.76,
        leverage=5.0,
    )
    assert d.tier == AlertTier.NONE
    # Should skip because confidence_scorer is not in the shadow edges list
    # (no shadow data for ETH_BUY_confidence_scorer specifically)
    assert "no shadow edge data" in d.reason


# ─── Standard edge tests ─────────────────────────────────────────────

def test_btc_buy_regime_trend_standard_needs_high_bar():
    """Standard edge needs conf>=82 AND 3+ strategies for EXECUTE."""
    # Weak case: should WATCH
    d_weak = evaluate_for_alert(
        symbol="BTC", side="BUY", strategy="regime_trend",
        confidence=75.0, num_agree=1, regime="trending_bull",
        entry=75000.0, sl=74500.0, tp1=76000.0, tp2=78000.0, leverage=5.0,
    )
    assert d_weak.tier == AlertTier.WATCH

    # Strong case: should EXECUTE
    d_strong = evaluate_for_alert(
        symbol="BTC", side="BUY", strategy="regime_trend",
        confidence=85.0, num_agree=3, regime="trending_bull",
        entry=75000.0, sl=74500.0, tp1=76000.0, tp2=78000.0, leverage=5.0,
    )
    assert d_strong.tier == AlertTier.EXECUTE


# ─── No shadow data ──────────────────────────────────────────────────

def test_unknown_combo_without_anticipatory_gets_nothing():
    """If (symbol, side, strategy) isn't in edges AND not pre-staged → NONE."""
    d = evaluate_for_alert(
        symbol="SOL", side="BUY", strategy="bollinger_squeeze",
        confidence=90.0, num_agree=3, regime="trending_bull",
        entry=85.0, sl=84.0, tp1=86.5, tp2=88.0, leverage=5.0,
    )
    assert d.tier == AlertTier.NONE


def test_unknown_combo_with_anticipatory_watches():
    """Anticipatory pre-stage on unknown setup → WATCH (flagged by engine)."""
    d = evaluate_for_alert(
        symbol="SOL", side="BUY", strategy="bollinger_squeeze",
        confidence=75.0, num_agree=2, regime="trending_bull",
        entry=85.0, sl=84.0, tp1=86.5, tp2=88.0, leverage=5.0,
        anticipatory_prestage=True,
    )
    assert d.tier == AlertTier.WATCH


# ─── Size suggestion math ────────────────────────────────────────────

def test_size_suggestion_uses_max_loss():
    """Size should scale so SL hit = max_loss_usd (when equity cap not binding)."""
    # stop_pct = 1% (44.5 → 44.055), max_loss = $10
    # notional should be ~1000. Use high equity so 40% cap doesn't bind (need >$2500 equity).
    d = evaluate_for_alert(
        symbol="HYPE", side="BUY", strategy="bollinger_squeeze",
        confidence=80.0, num_agree=3, regime="trending_bull",
        entry=44.5, sl=44.055, tp1=45.5, tp2=46.5, leverage=5.0,
        equity=5000.0, max_loss_usd=10.0,
    )
    # loss_at_sl = notional * 0.01 = $10 → notional = 1000
    assert 900 < (d.size_suggestion_notional or 0) < 1100


def test_size_capped_at_equity_fraction():
    """Notional never exceeds 40% of equity even with tight stop."""
    d = evaluate_for_alert(
        symbol="HYPE", side="BUY", strategy="bollinger_squeeze",
        confidence=80.0, num_agree=3, regime="trending_bull",
        entry=44.5, sl=44.49, tp1=45.5, tp2=46.5, leverage=5.0,
        equity=500.0, max_loss_usd=10.0,
    )
    # With 0.02% stop, raw sizing would be $50k. Capped at 40% of 500 = $200.
    assert (d.size_suggestion_notional or 0) <= 200.01


# ─── Formatter smoke tests ───────────────────────────────────────────

def test_execute_alert_format_has_direction():
    """Execute alert must clearly state LONG or SHORT first line."""
    d = AlertDecision(
        tier=AlertTier.EXECUTE,
        reason="test",
        shadow_wr=0.61, shadow_n=196, shadow_grade="premium",
        size_suggestion_notional=500.0, max_loss_usd=10.0,
    )
    msg = format_premium_execute_alert(
        symbol="HYPE", side="BUY",
        entry=44.5, sl=44.0, tp1=45.5, tp2=46.5,
        leverage=5.0, confidence=80.0, decision=d,
        strategy="bollinger_squeeze", regime="trending_bull",
        num_agree=3, total_strategies=9,
    )
    # First line is the action + direction
    first = msg.split("\n")[0]
    assert "LONG" in first and "HYPE" in first
    assert "EXECUTE" in first
    # Direction sanity check section is present
    assert "SANITY" in msg
    # Contains shadow evidence
    assert "shadow" in msg.lower() or "% WR" in msg
    # Size section present
    assert "SIZE" in msg or "Notional" in msg
    # Max loss explicit
    assert "Max loss" in msg
    # Ask Claude block present
    assert "ASK CLAUDE" in msg
    # /trade command pre-filled
    assert "/trade HYPE BUY" in msg


def test_watch_alert_format_tells_user_to_wait():
    """Watch alert must say 'don't execute yet'."""
    d = AlertDecision(
        tier=AlertTier.WATCH,
        reason="test",
        shadow_wr=0.61, shadow_n=196, shadow_grade="premium",
        key_conditions_missing=["confidence 70% < 75 needed"],
        key_conditions_met=["premium-edge setup (61% WR on 196)"],
    )
    msg = format_premium_watch_alert(
        symbol="HYPE", side="BUY",
        entry=44.5, sl=44.0, tp1=45.5, tp2=46.5,
        leverage=5.0, confidence=70.0, decision=d,
        strategy="bollinger_squeeze", regime="trending_bull",
        num_agree=1, total_strategies=9,
    )
    assert "WATCH" in msg
    assert "Don't execute yet" in msg or "don't execute" in msg.lower()


def test_short_alert_has_correct_sl_direction():
    """SHORT alert must show SL ABOVE entry, TP BELOW (the bug we fixed today)."""
    d = AlertDecision(
        tier=AlertTier.EXECUTE,
        reason="test",
        shadow_wr=0.72, shadow_n=68, shadow_grade="premium",
    )
    msg = format_premium_execute_alert(
        symbol="SOL", side="SELL",
        entry=85.0, sl=86.0, tp1=83.0, tp2=81.0,  # SHORT: SL above, TP below
        leverage=5.0, confidence=80.0, decision=d,
        strategy="multi_tier_quality", regime="trending_bear",
        num_agree=3, total_strategies=9,
    )
    # Must say SHORT in the header
    assert "SHORT" in msg.split("\n")[0]
    # Direction sanity must include "SL above entry" for a SHORT
    assert "SL above entry" in msg
    # Sanity line says "TP below" (combined)
    assert "TP below" in msg
    # Signed pct on SL must be positive (shows price moving against short)
    assert "Stop   $86.00   (+1.18%)" in msg
    # Signed pct on TP must be negative (price falling = win for short)
    assert "TP1    $83.00   (-2.35%" in msg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
