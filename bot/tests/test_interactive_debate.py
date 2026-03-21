"""
Tests for the interactive debate mechanism.

Tests the Trade-Critic debate system:
- Round 1: Critic evaluates thesis without confidence anchoring
- Round 2: Trade Agent rebuts objections
- Resolution: Score-based outcome (FREE-MAD)
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from llm.agents.interactive_debate import (
    InteractiveDebater,
    ThesisProposal,
    CounterThesis,
    Rebuttal,
    DebateResolution,
)


class TestThesisProposal:
    """Test Trade Agent proposal extraction."""

    def test_extract_proposal_minimal(self):
        """Extract proposal with minimal fields."""
        debater = InteractiveDebater()

        output = {
            "a": "go",
            "c": 0.65,
            "thesis": "SOL bullish due to regime alignment",
        }

        proposal = debater.round1_extract_proposal(output)

        assert proposal.action == "go"
        assert proposal.confidence == 0.65
        assert proposal.thesis == "SOL bullish due to regime alignment"

    def test_extract_proposal_with_evidence(self):
        """Extract proposal with evidence list."""
        debater = InteractiveDebater()

        output = {
            "a": "go",
            "c": 0.72,
            "thesis": "SOL uptrend",
            "evidence": ["MACD above signal", "4/4 regime align"],
            "ea": "market now",
            "setup_type": "momentum",
        }

        proposal = debater.round1_extract_proposal(output)

        assert proposal.action == "go"
        assert proposal.confidence == 0.72
        assert len(proposal.evidence) == 2
        assert proposal.entry_adjustment == "market now"
        assert proposal.setup_type == "momentum"

    def test_extract_proposal_alternative_field_names(self):
        """Extract proposal with alternative field names (backward compat)."""
        debater = InteractiveDebater()

        output = {
            "action": "skip",
            "confidence": 0.4,
            "n": "Weak setup, risk/reward poor",
        }

        proposal = debater.round1_extract_proposal(output)

        assert proposal.action == "skip"
        assert proposal.confidence == 0.4
        assert proposal.thesis == "Weak setup, risk/reward poor"


class TestCounterThesis:
    """Test Critic Agent counter-thesis extraction."""

    def test_extract_counter_approve(self):
        """Extract Critic output when approving."""
        debater = InteractiveDebater()

        output = {
            "verdict": "approve",
            "adjusted_confidence": 0.68,
            "objections": [],
            "red_flags": [],
        }

        counter = debater.round1_extract_counter_thesis(output)

        assert counter.verdict == "approve"
        assert counter.confidence_in_challenge == 0.68
        assert len(counter.objections) == 0

    def test_extract_counter_challenge(self):
        """Extract Critic output when challenging."""
        debater = InteractiveDebater()

        output = {
            "verdict": "challenge",
            "counter_thesis": "SOL likely to consolidate, not break up",
            "objections": [
                {
                    "reason": "BTC rejected at $75k resistance",
                    "likelihood": 0.85,
                    "impact": "thesis_invalid",
                },
                {
                    "reason": "Funding rate too high, carry cost eats profits",
                    "likelihood": 0.65,
                    "impact": "size_wrong",
                },
            ],
            "red_flags": ["High leverage relative to conviction", "Unfamiliar setup"],
            "adjusted_confidence": 0.45,
        }

        counter = debater.round1_extract_counter_thesis(output)

        assert counter.verdict == "challenge"
        assert counter.counter_thesis is not None
        assert len(counter.objections) == 2
        assert counter.objections[0]["likelihood"] == 0.85
        assert len(counter.red_flags) == 2

    def test_extract_counter_with_missing_fields(self):
        """Objections with missing fields get filled with defaults."""
        debater = InteractiveDebater()

        output = {
            "verdict": "challenge",
            "objections": [
                {"reason": "Setup has low win rate"},
                # Missing likelihood and impact fields
            ],
        }

        counter = debater.round1_extract_counter_thesis(output)

        # Should fill in defaults
        assert len(counter.objections) == 1
        assert counter.objections[0]["reason"] == "Setup has low win rate"
        assert "likelihood" in counter.objections[0]
        assert "impact" in counter.objections[0]


class TestDebateScoring:
    """Test debate outcome scoring (FREE-MAD)."""

    def test_score_trade_maintained_thesis(self):
        """Trade Agent that maintains thesis scores high on trade_side."""
        debater = InteractiveDebater()

        proposal = ThesisProposal(
            action="go",
            thesis="SOL up",
            confidence=0.70,
        )

        counter = CounterThesis(
            verdict="challenge",
            counter_thesis="SOL sideways",
            objections=[
                {"reason": "BTC weak", "likelihood": 0.6, "impact": "thesis_invalid"},
            ],
        )

        rebuttal = Rebuttal(
            action="go",  # Same action
            adjusted_confidence=0.68,  # Slight reduction
            maintains_thesis=True,
            rebuttal_points=["BTC weakness is temporary"],
            concessions=[],
        )

        score = debater._score_trade_side(proposal, rebuttal)

        assert score > 0.65  # High score for maintaining thesis without concessions

    def test_score_trade_reversed_action(self):
        """Trade Agent that reverses action scores low on trade_side."""
        debater = InteractiveDebater()

        proposal = ThesisProposal(
            action="go",
            thesis="SOL up",
            confidence=0.70,
        )

        rebuttal = Rebuttal(
            action="skip",  # Reversed to skip
            adjusted_confidence=0.25,
            maintains_thesis=False,
            rebuttal_points=[],
            concessions=["Risk too high", "BTC not confirming"],
        )

        score = debater._score_trade_side(proposal, rebuttal)

        assert score < 0.4  # Low score for reversing

    def test_score_critic_valid_objections(self):
        """Critic with valid objections that Trade Agent concedes to scores high."""
        debater = InteractiveDebater()

        counter = CounterThesis(
            verdict="challenge",
            objections=[
                {"reason": "Setup historically loses", "likelihood": 0.8, "impact": "thesis_invalid"},
                {"reason": "Volatility spike risk", "likelihood": 0.7, "impact": "size_wrong"},
                {"reason": "Funding rate unsustainable", "likelihood": 0.6, "impact": "size_wrong"},
            ],
        )

        rebuttal = Rebuttal(
            action="skip",
            adjusted_confidence=0.2,
            maintains_thesis=False,
            concessions=["Setup type has poor history", "Volatility risk real"],
        )

        score = debater._score_critic_side(counter, rebuttal)

        assert score > 0.65  # High score for valid, consequential objections

    def test_score_critic_weak_objections(self):
        """Critic with weak objections that Trade Agent defends scores low."""
        debater = InteractiveDebater()

        counter = CounterThesis(
            verdict="challenge",
            objections=[
                {"reason": "I'm not sure", "likelihood": 0.3, "impact": "thesis_invalid"},
            ],
        )

        rebuttal = Rebuttal(
            action="go",  # Maintained action
            adjusted_confidence=0.70,  # No confidence reduction
            maintains_thesis=True,
            rebuttal_points=["Setup type actually has 58% WR"],
            concessions=[],
        )

        score = debater._score_critic_side(counter, rebuttal)

        assert score < 0.45  # Low score for unconvincing objections


class TestDebateResolution:
    """Test full debate resolution."""

    def test_resolve_trade_wins(self):
        """Trade Agent's thesis holds up in debate."""
        debater = InteractiveDebater()

        proposal = ThesisProposal(
            action="go",
            thesis="SOL strong momentum, BTC confirming",
            confidence=0.75,
            setup_type="momentum",
        )

        counter = CounterThesis(
            verdict="approve",
            objections=[
                {"reason": "Okay, thesis is sound", "likelihood": 0.2, "impact": "thesis_invalid"},
            ],
        )

        rebuttal = Rebuttal(
            action="go",
            adjusted_confidence=0.75,
            maintains_thesis=True,
            concessions=[],
        )

        resolution = debater.score_debate(proposal, counter, rebuttal)

        assert resolution.final_action == "go"
        assert resolution.debate_winner == "trade"
        assert resolution.final_confidence >= 0.75

    def test_resolve_critic_wins(self):
        """Critic's objections defeat Trade Agent's thesis."""
        debater = InteractiveDebater()

        proposal = ThesisProposal(
            action="go",
            thesis="SOL breakout",
            confidence=0.70,
        )

        counter = CounterThesis(
            verdict="challenge",
            counter_thesis="SOL will consolidate and drop",
            objections=[
                {"reason": "Setup losing 65% of time", "likelihood": 0.9, "impact": "thesis_invalid"},
                {"reason": "BTC structure bearish", "likelihood": 0.8, "impact": "thesis_invalid"},
                {"reason": "Funding above sustainable level", "likelihood": 0.7, "impact": "size_wrong"},
            ],
        )

        rebuttal = Rebuttal(
            action="skip",
            adjusted_confidence=0.15,
            maintains_thesis=False,
            concessions=["Setup type loses more than wins", "BTC weakness real"],
        )

        resolution = debater.score_debate(proposal, counter, rebuttal)

        assert resolution.final_action == "skip"
        assert resolution.debate_winner == "critic"
        assert resolution.final_confidence < 0.3

    def test_resolve_consensus(self):
        """Agents reach consensus despite initial disagreement."""
        debater = InteractiveDebater()

        proposal = ThesisProposal(
            action="go",
            thesis="SOL likely up if BTC holds",
            confidence=0.60,
        )

        counter = CounterThesis(
            verdict="approve",
            objections=[
                {"reason": "Need BTC confirmation", "likelihood": 0.7, "impact": "timing_wrong"},
            ],
        )

        rebuttal = Rebuttal(
            action="go",
            adjusted_confidence=0.55,
            maintains_thesis=True,
            rebuttal_points=["Agreeing to wait for BTC confirmation"],
            concessions=["Timing dependent on BTC"],
        )

        resolution = debater.score_debate(proposal, counter, rebuttal)

        assert resolution.debate_winner == "consensus"
        assert abs(resolution.trade_score - resolution.critic_score) < 0.3


class TestEscalation:
    """Test when debate results should escalate to Overseer Agent."""

    def test_escalate_on_close_disagreement(self):
        """Escalate when Trade and Critic scores are too close."""
        debater = InteractiveDebater()

        resolution = DebateResolution(
            final_action="go",
            final_confidence=0.50,
            debate_winner="consensus",
            trade_score=0.50,
            critic_score=0.48,
            risk_flags=["Moderate concern"],
        )

        should_escalate = debater.should_escalate_to_overseer(resolution)

        # Close agreement on consensus case should escalate
        assert should_escalate

    def test_escalate_on_many_risks(self):
        """Escalate when many risk flags unresolved."""
        debater = InteractiveDebater()

        resolution = DebateResolution(
            final_action="go",
            final_confidence=0.70,
            debate_winner="trade",
            trade_score=0.75,
            critic_score=0.30,
            risk_flags=[
                "BTC divergence",
                "Funding rate high",
                "Setup losing streak",
                "Volatility spike risk",
            ],
        )

        should_escalate = debater.should_escalate_to_overseer(resolution)

        # Many risks despite trade win → escalate
        assert should_escalate


class TestBuildInputs:
    """Test prompt builders for interactive debate."""

    def test_build_critic_round1_input(self):
        """Build Round 1 Critic input without Trade confidence."""
        debater = InteractiveDebater()

        proposal = ThesisProposal(
            action="go",
            thesis="SOL up due to volume expansion",
            evidence=["Volume 2.5x avg", "MACD above signal"],
            confidence=0.80,  # This should NOT appear in Critic input
            setup_type="volume_breakout",
        )

        market_data = {
            "m": [{"s": "SOL/USD"}],
        }

        critic_input = debater.round1_build_critic_input(
            proposal, market_data, "trend"
        )

        # Verify confidence is hidden
        assert "0.80" not in critic_input
        assert "confidence" not in critic_input.lower() or "hidden" in critic_input.lower()

        # Verify thesis and evidence are present
        assert "SOL up" in critic_input
        assert "Volume 2.5x" in critic_input

    def test_build_trade_rebuttal_input(self):
        """Build Round 2 Trade rebuttal input."""
        debater = InteractiveDebater()

        proposal = ThesisProposal(
            action="go",
            thesis="SOL up",
            confidence=0.75,
        )

        counter = CounterThesis(
            verdict="challenge",
            counter_thesis="SOL sideways",
            objections=[
                {"reason": "BTC weak", "likelihood": 0.8, "impact": "thesis_invalid"},
                {"reason": "Overbought RSI", "likelihood": 0.6, "impact": "timing_wrong"},
            ],
            red_flags=["High leverage relative to conviction"],
        )

        rebuttal_input = debater.round2_build_trade_input(proposal, counter)

        # Verify it contains Critic's specific objections
        assert "Counter-thesis" in rebuttal_input or "counter_thesis" in rebuttal_input
        assert "BTC weak" in rebuttal_input
        assert "Obbought RSI" in rebuttal_input or "Overbought" in rebuttal_input or "RSI" in rebuttal_input


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
