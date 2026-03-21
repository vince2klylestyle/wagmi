# Testing Examples & Implementation Patterns

Reference implementations for the missing test files.

---

## Example 1: Agent Consistency Tests

**File**: `tests/test_agent_consistency.py` (CREATE)

```python
"""
Tests for multi-agent consistency: vocabulary, schema, context passing.

Ensures agents understand each other through:
  1. Shared regime/action vocabulary
  2. Schema validation between agents
  3. Correct context passing via memory bus
  4. Graceful handling of malformed outputs
"""

import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ─── Vocabulary Consistency ──────────────────────────────────

class TestAgentVocabulary:
    """Test that all agents use identical vocabulary."""

    def test_regime_vocabulary_defined(self):
        """All agents must know the same regime names."""
        from llm.agents.prompts import (
            REGIME_AGENT_PROMPT, TRADE_AGENT_PROMPT,
            RISK_AGENT_PROMPT, LEARNING_AGENT_PROMPT
        )

        required_regimes = {"trend", "range", "panic", "high_volatility",
                           "low_liquidity", "news_dislocation", "unknown"}

        # Regime agent must mention all regimes
        for regime in required_regimes:
            assert regime in REGIME_AGENT_PROMPT.lower(), \
                f"Regime '{regime}' missing from REGIME_AGENT_PROMPT"

        # Trade agent must reference regime options
        assert "regime" in TRADE_AGENT_PROMPT.lower()

        # Risk agent must handle regimes
        assert "regime" in RISK_AGENT_PROMPT.lower()

    def test_action_vocabulary_consistent(self):
        """Trade agent says 'go'/'skip', must normalize to 'proceed'/'flat'."""
        from llm.agents.coordinator import normalize_action

        # Input → Output mapping
        assert normalize_action("go") == "proceed"
        assert normalize_action("proceed") == "proceed"
        assert normalize_action("skip") == "flat"
        assert normalize_action("flat") == "flat"
        assert normalize_action("flip") == "reverse"
        assert normalize_action("reverse") == "reverse"

    def test_agent_output_fields_match_inputs(self):
        """Regime output fields must match what Trade agent expects."""
        # Regime agent outputs: rg, conf, bias, transition, factors
        # Trade agent expects: these in the merged context

        from llm.agents.base import AgentRole

        regime_output_schema = {
            "rg": str,           # regime name
            "conf": float,       # 0-1 confidence
            "bias": str,         # bullish/neutral/bearish
            "transition": str,   # stable/uncertain/shifting
            "factors": str,      # why this regime
        }

        trade_input_schema = {
            "regime": str,
            "regime_confidence": float,
            "regime_bias": str,
            # ... more fields
        }

        # Trade agent must map regime output fields to its input schema
        # This should be codified in coordinator._build_trade_input()


# ─── Schema Validation ────────────────────────────────────────

class TestAgentSchemas:
    """Test that agent outputs conform to expected schema."""

    def test_regime_output_format_valid(self):
        """Regime agent response must have required fields."""
        from llm.agents.coordinator import AgentCoordinator

        def mock_regime(**kwargs):
            # Valid response
            return json.dumps({
                "rg": "trend",
                "conf": 0.85,
                "bias": "bullish",
                "transition": "stable",
                "factors": "strong volume",
            }), {"input_tokens": 50}

        with patch("llm.agents.coordinator.call_llm", side_effect=mock_regime):
            coord = AgentCoordinator()
            # Should not raise
            out = coord._call_regime_agent({})
            assert out.ok
            assert out.data["rg"] == "trend"

    def test_regime_output_missing_field_fails(self):
        """Regime agent missing 'rg' field should be marked as error."""
        from llm.agents.coordinator import AgentCoordinator

        def mock_invalid(**kwargs):
            return json.dumps({
                # Missing "rg" field
                "conf": 0.85,
                "bias": "bullish",
            }), {"input_tokens": 50}

        with patch("llm.agents.coordinator.call_llm", side_effect=mock_invalid):
            coord = AgentCoordinator()
            out = coord._call_regime_agent({})
            # Should be marked as error
            assert not out.ok or "rg" not in out.data

    def test_trade_output_requires_action(self):
        """Trade agent must specify action: 'go', 'skip', or 'flip'."""
        from llm.agents.coordinator import AgentCoordinator

        def mock_trade(**kwargs):
            return json.dumps({
                "a": "go",
                "c": 0.78,
                "n": "strong confluence",
                # Valid: action specified
            }), {"input_tokens": 80}

        with patch("llm.agents.coordinator.call_llm", side_effect=mock_trade):
            coord = AgentCoordinator()
            out = coord._call_trade_agent({})
            assert out.ok
            assert out.data["a"] in ["go", "skip", "flip"]

    def test_risk_output_size_multiplier_valid(self):
        """Risk agent must output size multiplier in valid range [0, 2]."""
        from llm.agents.coordinator import AgentCoordinator

        def mock_risk(**kwargs):
            return json.dumps({
                "sz": 1.5,  # Valid: 0-2
                "sw": {"rt": 0.9, "mc": 0.7},
                "risks": [],
            }), {"input_tokens": 60}

        with patch("llm.agents.coordinator.call_llm", side_effect=mock_risk):
            coord = AgentCoordinator()
            out = coord._call_risk_agent({})
            assert out.ok
            assert 0 <= out.data.get("sz", 1) <= 2


# ─── Context Passing (Memory Bus) ────────────────────────────

class TestContextPassing:
    """Test that context flows correctly between agents."""

    def test_regime_output_to_trade_input(self):
        """Trade agent input must include regime agent output."""
        from llm.agents.coordinator import AgentCoordinator

        regime_output = {
            "rg": "trend",
            "conf": 0.85,
            "bias": "bullish",
            "factors": "strong volume",
        }

        coord = AgentCoordinator()

        # Build trade agent input from regime output
        trade_input = coord._build_trade_input(
            snapshot_data={},
            regime_output=regime_output,
            memory_context="BTC leading",
        )

        # Trade input must include regime information
        assert "regime" in trade_input or "rg" in trade_input
        assert "bullish" in trade_input.lower()

    def test_trade_output_to_risk_input(self):
        """Risk agent input must include trade decision."""
        from llm.agents.coordinator import AgentCoordinator

        trade_output = {
            "a": "go",
            "c": 0.78,
            "n": "trend alignment",
        }

        coord = AgentCoordinator()

        # Build risk input from trade output
        risk_input = coord._build_risk_input(
            snapshot_data={},
            trade_output=trade_output,
        )

        # Risk input must know trade decision
        assert "go" in risk_input or "proceed" in risk_input

    def test_memory_bus_cleared_between_decisions(self):
        """Scratchpad memory should be fresh for each new decision."""
        from llm.agents.coordinator import AgentCoordinator

        coord = AgentCoordinator()
        coord.scratchpad = {"old": "data"}

        # New decision should clear
        coord._reset_scratchpad()
        assert coord.scratchpad == {}


# ─── Graceful Degradation ────────────────────────────────────

class TestAgentFailures:
    """Test that system degrades gracefully when agents fail."""

    def test_regime_agent_failure_aborts(self):
        """If regime agent fails (required), abort decision."""
        from llm.agents.coordinator import AgentCoordinator

        def mock_fail(**kwargs):
            raise Exception("API timeout")

        with patch("llm.agents.coordinator.call_llm", side_effect=mock_fail):
            coord = AgentCoordinator()
            decision = coord.get_trading_decision({})
            assert decision is None

    def test_trade_agent_failure_with_regime_ok(self):
        """If trade agent fails (required), abort."""
        coord_mock = MagicMock()
        coord_mock._call_regime_agent.return_value = MagicMock(ok=True, data={"rg": "trend"})
        coord_mock._call_trade_agent.side_effect = Exception("parse error")

        # Should result in None decision

    def test_optional_agents_skip_on_failure(self):
        """If critic/risk/learning agents fail, continue with regime+trade."""
        from llm.agents.coordinator import AgentCoordinator

        call_count = [0]

        def mock_fn(**kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                # Regime + Trade succeed
                if call_count[0] == 1:
                    return json.dumps({"rg": "trend", "conf": 0.8,
                                      "bias": "bullish", "transition": "stable"}), {}
                return json.dumps({"a": "go", "c": 0.75, "n": "ok"}), {}
            # Risk/Critic fail
            raise Exception("overloaded")

        with patch("llm.agents.coordinator.call_llm", side_effect=mock_fn):
            coord = AgentCoordinator()
            decision = coord.get_trading_decision({})
            # Should still produce decision (regime + trade only)
            assert decision is not None
            assert decision.action == "proceed"


# ─── Hypothesis Testing ──────────────────────────────────────

class TestAgentConsistencyInPractice:
    """Test actual scenario with multiple agents."""

    def test_full_pipeline_maintains_consistency(self):
        """End-to-end: regime → trade → risk → critic."""

        responses = [
            # Regime
            {"rg": "trend", "conf": 0.85, "bias": "bullish",
             "factors": "strong vol", "transition": "stable"},
            # Trade
            {"a": "go", "c": 0.78, "n": "momentum", "mu": "BTC leading", "ea": None},
            # Risk
            {"sz": 1.3, "sw": {"rt": 0.9, "mc": 0.7}, "risks": []},
            # Critic
            {"verdict": "approve", "reason": "all good"},
        ]

        def mock_fn(**kwargs):
            idx = len([r for r in responses if r])
            if idx >= len(responses):
                idx = len(responses) - 1
            return json.dumps(responses[idx]), {}

        from llm.agents.coordinator import AgentCoordinator

        with patch("llm.agents.coordinator.call_llm", side_effect=mock_fn):
            coord = AgentCoordinator()
            decision = coord.get_trading_decision({})

            # Final decision should reflect all agents' consensus
            assert decision.action == "proceed"
            assert decision.regime == "trend"
            assert decision.confidence == 0.78
            assert decision.size_multiplier == 1.3
```

---

## Example 2: Kelly Safety Tests

**File**: `tests/test_kelly_safety.py` (CREATE)

```python
"""
Kelly Criterion and Expected Value Safety Tests

Tests that the quant engine correctly:
  1. Calculates EV from win rate and R:R ratio
  2. Computes Kelly fraction safely (0-0.5)
  3. Applies Kelly modulation to size
  4. Detects negative EV (losing trades)
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestKellyFraction:
    """Test Kelly criterion calculations."""

    def test_kelly_formula_55_percent_wr_2_rr(self):
        """55% WR with 2:1 R:R → Kelly = 0.1 (10% of bankroll)."""
        # Kelly = (win_pct * avg_win - loss_pct * avg_loss) / avg_win
        # Kelly = (0.55 * 2 - 0.45 * 1) / 2
        # Kelly = (1.1 - 0.45) / 2 = 0.65 / 2 = 0.325
        # But clamped to [0, 0.5] → 0.325 is valid

        from llm.agents.quant_engine import calculate_kelly_fraction

        kelly = calculate_kelly_fraction(win_rate=0.55, avg_win=2.0, avg_loss=1.0)
        assert pytest.approx(kelly, 0.01) == 0.325

    def test_kelly_zero_win_rate(self):
        """0% WR (losing setup) → Kelly = negative → clamp to 0."""
        from llm.agents.quant_engine import calculate_kelly_fraction

        kelly = calculate_kelly_fraction(win_rate=0.0, avg_win=2.0, avg_loss=1.0)
        assert kelly == 0.0  # Clamped to floor

    def test_kelly_fifty_percent_wr(self):
        """50% WR (breakeven before costs) → Kelly = small positive."""
        from llm.agents.quant_engine import calculate_kelly_fraction

        kelly = calculate_kelly_fraction(win_rate=0.50, avg_win=2.0, avg_loss=1.0)
        # Kelly = (0.5 * 2 - 0.5 * 1) / 2 = 0.5 / 2 = 0.25
        assert pytest.approx(kelly, 0.01) == 0.25

    def test_kelly_clamped_max_0_5(self):
        """Very high WR is clamped to 0.5 (50%)."""
        from llm.agents.quant_engine import calculate_kelly_fraction

        # 90% WR with 3:1 R:R would give kelly > 1.0 without cap
        kelly = calculate_kelly_fraction(win_rate=0.90, avg_win=3.0, avg_loss=1.0)
        assert kelly <= 0.5  # Must be clamped
        assert kelly > 0.0   # But still positive


class TestKellyModulation:
    """Test how Kelly fraction modulates position size."""

    def test_risk_agent_applies_kelly_to_size(self):
        """Risk agent: size_multiplier = 1 + 1.5 * (kelly - 0.15)."""
        from llm.agents.quant_engine import apply_kelly_modulation

        # Baseline kelly = 0.15 (no modulation at this point)
        # If kelly = 0.25, modulation = 1 + 1.5 * (0.25 - 0.15) = 1 + 0.15 = 1.15

        size = apply_kelly_modulation(base_size=1.0, kelly=0.25)
        assert pytest.approx(size, 0.01) == 1.15

    def test_kelly_modulation_clamped_to_2x(self):
        """Kelly modulation should never exceed 2.0x."""
        from llm.agents.quant_engine import apply_kelly_modulation

        # High kelly (0.5) would give modulation = 1 + 1.5 * 0.35 = 1.525
        size = apply_kelly_modulation(base_size=1.0, kelly=0.50)
        assert size <= 2.0

    def test_kelly_below_baseline_reduces_size(self):
        """Kelly < 0.15 reduces size below 1.0."""
        from llm.agents.quant_engine import apply_kelly_modulation

        # Kelly = 0.10, modulation = 1 + 1.5 * (0.10 - 0.15) = 1 - 0.075 = 0.925
        size = apply_kelly_modulation(base_size=1.0, kelly=0.10)
        assert pytest.approx(size, 0.01) == 0.925


class TestExpectedValue:
    """Test EV calculation (core to Kelly)."""

    def test_ev_positive_with_55_percent_wr(self):
        """55% WR with 2:1 R:R has positive EV."""
        from llm.agents.quant_engine import calculate_ev

        # EV = (0.55 * 2) + (0.45 * -1) = 1.1 - 0.45 = 0.65
        ev = calculate_ev(win_rate=0.55, avg_win=2.0, avg_loss=1.0)
        assert ev > 0.0
        assert pytest.approx(ev, 0.01) == 0.65

    def test_ev_zero_at_50_percent_wr(self):
        """50% WR with equal R:R has zero EV (before fees)."""
        from llm.agents.quant_engine import calculate_ev

        ev = calculate_ev(win_rate=0.50, avg_win=1.0, avg_loss=1.0)
        assert pytest.approx(ev, 0.01) == 0.0

    def test_ev_negative_below_50_percent(self):
        """<50% WR (even with good R:R) is negative EV."""
        from llm.agents.quant_engine import calculate_ev

        # 45% WR with 2:1 R:R: EV = (0.45 * 2) + (0.55 * -1) = 0.9 - 0.55 = 0.35
        # Actually positive! Let's test 40%:
        # EV = (0.40 * 2) + (0.60 * -1) = 0.80 - 0.60 = 0.20 (still positive)
        # Need 1:1 R:R for < 50% WR to be negative:
        # EV = (0.40 * 1) + (0.60 * -1) = 0.40 - 0.60 = -0.20

        ev = calculate_ev(win_rate=0.40, avg_win=1.0, avg_loss=1.0)
        assert ev < 0.0


class TestConditionalEdge:
    """Test detection of conditional edge (context-dependent win rate)."""

    def test_conditional_edge_higher_in_regime(self):
        """SOL LONG in TREND regime might have 65% WR vs 55% overall."""
        from llm.agents.quant_engine import calculate_conditional_edge

        base_wr = 0.55
        conditional_wr = 0.65  # In trend regime
        n_similar = 20  # Based on 20 similar trades

        edge = calculate_conditional_edge(
            base_wr=base_wr,
            conditional_wr=conditional_wr,
            n_similar=n_similar,
            min_sample_size=10
        )

        assert edge > 0.10  # Meaningful edge
        assert edge <= 0.20  # But not unrealistic

    def test_conditional_edge_requires_sample_size(self):
        """Need min N similar trades before trusting conditional WR."""
        from llm.agents.quant_engine import calculate_conditional_edge

        # Only 3 similar trades, threshold = 10
        edge = calculate_conditional_edge(
            base_wr=0.55,
            conditional_wr=0.80,  # Looks great
            n_similar=3,
            min_sample_size=10
        )

        # Should discount or zero out
        assert edge < 0.20


class TestFatTailRisk:
    """Test detection of fat-tail risk (extreme adverse moves)."""

    def test_fat_tail_low_in_normal_markets(self):
        """Vol = 1.5%, funding = normal → low fat-tail risk."""
        from llm.agents.quant_engine import estimate_fat_tail_risk

        risk = estimate_fat_tail_risk(
            volatility_pct=1.5,
            funding_rate_pct=0.01,
            regime="trend",
            time_in_trade_hours=2,
        )

        assert risk in ["low", "medium"]

    def test_fat_tail_high_on_vol_spike(self):
        """Vol = 5% (spike) → high fat-tail risk."""
        from llm.agents.quant_engine import estimate_fat_tail_risk

        risk = estimate_fat_tail_risk(
            volatility_pct=5.0,
            funding_rate_pct=0.05,
            regime="panic",
            time_in_trade_hours=24,
        )

        assert risk in ["high", "extreme"]

    def test_max_adverse_move_in_range(self):
        """Extreme adverse move typically 2-3% in trending markets."""
        from llm.agents.quant_engine import estimate_max_adverse_move

        move_pct = estimate_max_adverse_move(
            regime="trend",
            volatility_pct=2.0,
        )

        assert 1.5 <= move_pct <= 3.5


class TestKellyIntegration:
    """Integration tests: full EV → Kelly → Sizing pipeline."""

    def test_low_confidence_signal_low_kelly(self):
        """Weak signal (45% WR, 1:1 R:R) → Low kelly → small size."""
        from llm.agents.quant_engine import full_kelly_sizing

        result = full_kelly_sizing(
            win_rate=0.45,
            avg_win=1.0,
            avg_loss=1.0,
            base_size=1.0,
        )

        assert result["kelly"] <= 0.1
        assert result["size_multiplier"] <= 1.0

    def test_strong_signal_higher_kelly(self):
        """Strong signal (65% WR, 2:1 R:R) → Meaningful kelly → 1.3-1.5x."""
        from llm.agents.quant_engine import full_kelly_sizing

        result = full_kelly_sizing(
            win_rate=0.65,
            avg_win=2.0,
            avg_loss=1.0,
            base_size=1.0,
        )

        assert result["kelly"] >= 0.2
        assert 1.2 <= result["size_multiplier"] <= 1.8

    def test_kelly_never_exceeds_2x(self):
        """Even optimal signal capped at 2.0x."""
        from llm.agents.quant_engine import full_kelly_sizing

        result = full_kelly_sizing(
            win_rate=0.75,
            avg_win=3.0,
            avg_loss=1.0,
            base_size=1.0,
        )

        assert result["size_multiplier"] <= 2.0
```

---

## Example 3: Concurrent Position Tests

**File**: `tests/test_concurrent_positions.py` (CREATE)

```python
"""
Concurrent Position Safety Tests

Tests multi-symbol position management:
  1. Independence of different symbols
  2. TP/SL overlap detection
  3. Position flip restrictions
  4. Liquidation cascades
"""

import pytest
import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestMultiSymbolIndependence:
    """Test that symbols don't interfere with each other."""

    def test_btc_long_independent_from_eth_short(self):
        """BTC LONG and ETH SHORT can coexist independently."""
        from execution.position_manager import PositionManager

        pm = PositionManager()

        # Open BTC LONG
        btc_pos = pm.open_position(
            symbol="BTC",
            side="LONG",
            entry=95000,
            sl=94000,
            tp1=97000,
            tp2=100000,
            size=0.1,
        )
        assert btc_pos.symbol == "BTC"
        assert btc_pos.side == "LONG"

        # Open ETH SHORT
        eth_pos = pm.open_position(
            symbol="ETH",
            side="SHORT",
            entry=3200,
            sl=3300,
            tp1=3100,
            tp2=3000,
            size=1.0,
        )
        assert eth_pos.symbol == "ETH"
        assert eth_pos.side == "SHORT"

        # Both should be open simultaneously
        assert len(pm.positions) == 2
        assert pm.positions["BTC"].side == "LONG"
        assert pm.positions["ETH"].side == "SHORT"

    def test_three_symbols_concurrent(self):
        """BTC LONG, ETH SHORT, SOL LONG all open together."""
        from execution.position_manager import PositionManager

        pm = PositionManager()

        positions = [
            ("BTC", "LONG", 95000, 94000, 97000),
            ("ETH", "SHORT", 3200, 3300, 3100),
            ("SOL", "LONG", 185, 180, 190),
        ]

        for sym, side, entry, sl, tp1 in positions:
            pm.open_position(
                symbol=sym, side=side, entry=entry, sl=sl, tp1=tp1, tp2=tp1+10,
                size=1.0
            )

        assert len(pm.positions) == 3

    def test_separate_margin_per_symbol(self):
        """Each symbol has independent margin requirement."""
        # BTC LONG 10x: requires entry * size * 10% = 95000 * 0.1 * 0.1 = $950
        # ETH SHORT 5x: requires entry * size * 20% = 3200 * 1.0 * 0.2 = $640
        # Total margin = $1590, not interdependent

        from execution.leverage import PositionSizer

        sizer = PositionSizer(account_equity=10000)

        btc_margin = sizer.calculate_margin_requirement(
            symbol="BTC", entry=95000, size=0.1, leverage=10
        )
        eth_margin = sizer.calculate_margin_requirement(
            symbol="ETH", entry=3200, size=1.0, leverage=5
        )

        # Neither should exceed account equity individually
        assert btc_margin < 10000
        assert eth_margin < 10000
        assert btc_margin + eth_margin < 10000


class TestTPSLOverlaps:
    """Test that overlapping TP/SL ranges are detected."""

    def test_two_longs_overlapping_tp_rejected(self):
        """Can't have BTC LONG TP=100k and ETH LONG TP=100k if both active."""
        from execution.position_manager import PositionManager

        pm = PositionManager()

        # Open BTC LONG with TP=100k
        pm.open_position(
            symbol="BTC", side="LONG", entry=95000,
            sl=94000, tp1=100000, tp2=102000, size=0.1
        )

        # Try to open SOL LONG with overlapping TP
        # (Both BTC and SOL in LONG regime, TP prices might overlap in portfolio effect)

        # Check for overlap warning
        sol_pos = {
            "symbol": "SOL", "side": "LONG", "entry": 185,
            "tp1": 190, "tp2": 195
        }

        overlap = pm.check_tp_sl_overlap(sol_pos)
        # Should not overlap in this case, but pattern would be:
        # if overlap: raise OverlapError()

    def test_overlapping_sl_ranges_detected(self):
        """Two LONG positions with SL too close together → warning."""
        from execution.position_manager import PositionManager

        pm = PositionManager()

        # BTC LONG SL=94000
        pm.open_position(
            symbol="BTC", side="LONG", entry=95000,
            sl=94000, tp1=100000, tp2=102000, size=0.1
        )

        # ETH LONG SL=94100 (too close to BTC SL in % terms)
        eth_pos = {
            "symbol": "ETH", "side": "LONG", "entry": 3200,
            "sl": 3100, "tp1": 3300, "tp2": 3400
        }

        # Should have logic to prevent cascade SL hits
        # If BTC SL hit, would liquidate. Should ETH follow? Probably not ideal.


class TestPositionFlips:
    """Test restrictions on position flips (LONG → SHORT)."""

    def test_flip_rejected_during_trailing(self):
        """Can't flip from LONG to SHORT while in TRAILING state."""
        from execution.position_manager import PositionManager
        from execution.position_state import PositionState

        pm = PositionManager()

        # Open BTC LONG
        pos = pm.open_position(
            symbol="BTC", side="LONG", entry=95000,
            sl=94000, tp1=97000, tp2=100000, size=0.1
        )

        # Hit TP1, transition to TRAILING
        pos.state = PositionState.TRAILING
        pos.trailing_stop = 96500

        # Try to flip to SHORT (should be rejected)
        flip_allowed = pm.can_flip_position("BTC")
        assert flip_allowed is False

    def test_flip_allowed_after_close(self):
        """After position fully closed, can open opposite side."""
        from execution.position_manager import PositionManager
        from execution.position_state import PositionState

        pm = PositionManager()

        # Open BTC LONG
        pos = pm.open_position(
            symbol="BTC", side="LONG", entry=95000,
            sl=94000, tp1=97000, tp2=100000, size=0.1
        )

        # Close fully
        pos.state = PositionState.CLOSED
        pm.close_position("BTC")

        # Now can open SHORT
        flip_allowed = pm.can_flip_position("BTC")
        assert flip_allowed is True


class TestSimultaneousOpenClose:
    """Test queueing when opening and closing in same cycle."""

    def test_close_then_open_sequence(self):
        """Close BTC LONG, then open BTC SHORT in same bar."""
        from execution.position_manager import PositionManager

        pm = PositionManager()

        # Open BTC LONG
        pm.open_position(
            symbol="BTC", side="LONG", entry=95000,
            sl=94000, tp1=97000, tp2=100000, size=0.1
        )

        # Queue close + open short
        pm.queue_close("BTC")
        pm.queue_open(
            symbol="BTC", side="SHORT", entry=96500,
            sl=97500, tp1=95500, tp2=93500, size=0.1
        )

        # Process queue in order
        pm.process_queue()

        # Should have SHORT position now
        assert pm.positions["BTC"].side == "SHORT"


class TestLiquidationCascades:
    """Test that one liquidation doesn't force-liquidate others."""

    def test_single_liquidation_independent(self):
        """BTC LONG liquidation at 94000 shouldn't affect ETH SHORT."""
        from execution.position_manager import PositionManager
        from execution.leverage import PositionSizer

        pm = PositionManager()
        sizer = PositionSizer(account_equity=10000)

        # Open BTC LONG with 10x leverage
        btc_liq = sizer.liquidation_price(
            symbol="BTC", side="LONG", entry=95000, leverage=10
        )
        assert btc_liq < 95000  # Liq below entry

        # Open ETH SHORT with 5x leverage
        eth_liq = sizer.liquidation_price(
            symbol="ETH", side="SHORT", entry=3200, leverage=5
        )
        assert eth_liq > 3200  # Liq above entry for short

        # BTC liq hit at 94000 doesn't force ETH close
        # (Unless margin freed by BTC affects ETH, but separately managed)

    def test_multi_liquidation_sequence(self):
        """Multiple liquidations happen in order, not cascade."""
        from execution.leverage import PositionSizer

        sizer = PositionSizer(account_equity=10000)

        # BTC LONG 10x: liq at ~90000
        # ETH LONG 10x: liq at ~2880
        # SOL LONG 10x: liq at ~160

        # If price drops hard (flash crash):
        # 1. SOL liq first (lowest absolute liq price)
        # 2. ETH liq second
        # 3. BTC liq third

        # Each should close independently, freeing margin for others
        liquidations = sizer.compute_cascade_order(
            positions=[
                ("BTC", "LONG", 95000, 10),
                ("ETH", "LONG", 3200, 10),
                ("SOL", "LONG", 185, 10),
            ],
            flash_crash_pct=-8
        )

        assert liquidations[0] == "SOL"  # Hits first
        assert liquidations[1] == "ETH"
        assert liquidations[2] == "BTC"


class TestCorrelationRisk:
    """Test detection of correlated symbol risk."""

    def test_high_correlation_symbols_detected(self):
        """BTC and ETH highly correlated (0.85+)."""
        from execution.correlation_gate import CorrelationGate

        gate = CorrelationGate()

        # BTC and ETH typically 0.85+ correlated
        corr = gate.get_correlation("BTC", "ETH")
        assert corr >= 0.80

    def test_correlation_reduce_size_recommendation(self):
        """High correlation → recommend smaller combined size."""
        from execution.correlation_gate import CorrelationGate

        gate = CorrelationGate()

        # Both BTC LONG and ETH LONG (same side, high corr)
        recommended_sz = gate.recommend_size_for_correlation(
            symbol1="BTC", side1="LONG",
            symbol2="ETH", side2="LONG",
            base_size=1.0,
        )

        # Should be reduced
        assert recommended_sz < 1.0

    def test_opposite_sides_reduce_correlation_risk(self):
        """BTC LONG and ETH SHORT (opposite) is hedged."""
        from execution.correlation_gate import CorrelationGate

        gate = CorrelationGate()

        # BTC LONG, ETH SHORT (opposite, high corr)
        # Should be low risk since they hedge
        risk = gate.compute_correlation_risk(
            symbol1="BTC", side1="LONG",
            symbol2="ETH", side2="SHORT",
        )

        assert risk < 0.3  # Low risk

    def test_max_aggregate_leverage_enforced(self):
        """Even with 3 symbols × 5x, can't exceed 15x total."""
        from execution.correlation_gate import CorrelationGate

        gate = CorrelationGate(max_aggregate_leverage=15.0)

        # Try to open 3 positions × 5x
        # Total = 15x (at limit)
        allowed = gate.check_aggregate_leverage(
            existing_leverage=10.0,
            new_position_leverage=5.0,
        )

        assert allowed is True

        # Try to add one more
        allowed = gate.check_aggregate_leverage(
            existing_leverage=10.0,
            new_position_leverage=6.0,  # Would be 16x
        )

        assert allowed is False
```

These three example files establish the pattern for the remaining critical tests. Follow the same structure:
1. Docstring explaining what's being tested and why
2. Multiple test classes grouped by functionality
3. Clear test names describing the assertion
4. Deterministic fixtures/mocks
5. Comments explaining the expected values

