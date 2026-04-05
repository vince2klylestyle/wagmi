"""
Cross-agent debate protocol for high-stakes decisions.

Enables structured 2-round argumentation between Trade Agent and Critic
to improve decision quality on important trades. Unlike the simulated
debate in pipeline_extensions, this makes REAL LLM calls for rebuttals.

Protocol:
  1. Trade Agent presents thesis  (already happened in pipeline)
  2. Critic presents counter-thesis (already happened in pipeline)
  3. NEW: Trade Agent rebuts counter-thesis (defends with new evidence)
  4. NEW: Critic responds to rebuttal (final challenge)
  5. Score-based resolution determines confidence adjustment

Trigger criteria (any one triggers debate):
  - Position size > 10% of equity
  - Trade confidence > 75%
  - Trade-Critic confidence gap > 20%
  - Risk Agent flagged any risk

Cost: ~$0.012 per debate (2 Sonnet calls, ~500 tokens each).
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from llm.agents.interactive_debate import (
    CounterThesis,
    DebateResolution,
    InteractiveDebater,
    Rebuttal,
    ThesisProposal,
)
from llm.agents.prompts import AGENT_PROMPTS
from llm.client import call_llm

logger = logging.getLogger("bot.llm.agents.debate_protocol")

# ── Constants ────────────────────────────────────────────────────────
DEBATE_MODEL = os.getenv("AGENT_DEBATE_MODEL", "claude-sonnet-4-5-20250929")
DEBATE_MAX_TOKENS = 512  # Token-efficient: ~500 tokens per round
CONFIDENCE_BOOST_TRADE_WINS = 7    # +7% when Trade defends successfully
CONFIDENCE_CUT_CRITIC_WINS = -12   # -12% when Critic's challenge holds
CONFIDENCE_DRAW = 0                # No change on draw


def _parse_json(raw: str) -> Optional[dict]:
    """Parse JSON from LLM response, handling markdown fences."""
    import re
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
        text = text.strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


class DebateProtocol:
    """Orchestrates real LLM-powered Trade-Critic debate rounds."""

    def __init__(self, coordinator=None):
        self.coordinator = coordinator
        self.debater = InteractiveDebater()
        self._total_debate_tokens = 0

    def should_debate(
        self,
        trade_decision: Dict[str, Any],
        risk_assessment: Dict[str, Any],
        critic_response: Dict[str, Any],
        position_size_pct: float = 0.0,
    ) -> bool:
        """Determine if this decision warrants a full debate.

        Returns True if ANY of these conditions are met:
          1. Position size > 10% of equity
          2. Trade confidence > 75%
          3. Trade-Critic confidence gap > 20%
          4. Risk Agent flagged any risk
        """
        # Gate: must have both trade and critic output
        trade_action = trade_decision.get("a", trade_decision.get("action", "skip"))
        if trade_action in ("skip", "flat"):
            return False  # No point debating a skip

        # 1. Large position
        if position_size_pct > 10.0:
            logger.info(f"[DEBATE] Triggered: position_size={position_size_pct:.1f}% > 10%")
            return True

        # 2. High conviction
        trade_conf = float(trade_decision.get("c", trade_decision.get("confidence", 0)))
        if trade_conf > 0.75:
            logger.info(f"[DEBATE] Triggered: trade_confidence={trade_conf:.0%} > 75%")
            return True

        # 3. Trade-Critic disagreement
        critic_conf = float(critic_response.get("adjusted_confidence",
                           critic_response.get("confidence_in_assessment", 0)))
        conf_gap = abs(trade_conf - critic_conf)
        if conf_gap > 0.20:
            logger.info(f"[DEBATE] Triggered: confidence_gap={conf_gap:.0%} > 20%")
            return True

        # 4. Risk flags
        risk_flags = risk_assessment.get("red_flags", risk_assessment.get("risks", []))
        if risk_flags:
            logger.info(f"[DEBATE] Triggered: {len(risk_flags)} risk flag(s)")
            return True

        return False

    def run_debate(
        self,
        trade_decision: Dict[str, Any],
        critic_response: Dict[str, Any],
        snapshot_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run a 2-round structured debate with real LLM calls.

        Round 3: Trade Agent rebuts Critic's counter-thesis
        Round 4: Critic responds to the rebuttal (final challenge)

        Returns:
            {
                "debate_occurred": True,
                "rounds": 2,
                "trade_rebuttal": {...},
                "critic_final": {...},
                "winner": "trade" | "critic" | "draw",
                "confidence_adjustment": int,
                "final_confidence": float,
                "reasoning": str,
                "cost_tokens": int,
            }
        """
        t0 = time.time()

        # Extract structured data from pipeline outputs
        proposal = self.debater.round1_extract_proposal(trade_decision)
        counter_thesis = self.debater.round1_extract_counter_thesis(critic_response)

        # ── Round 3: Trade Agent rebuttal ──────────────────────
        rebuttal_raw, rebuttal_parsed = self._call_trade_rebuttal(
            proposal, counter_thesis
        )

        if rebuttal_parsed is None:
            # LLM call failed — fall back to simulated rebuttal
            logger.warning("[DEBATE] Trade rebuttal LLM call failed, using simulated")
            return self._fallback_result(proposal, counter_thesis, trade_decision)

        rebuttal = self.debater.round2_extract_rebuttal(rebuttal_parsed)

        # ── Round 4: Critic final response ─────────────────────
        critic_final_raw, critic_final_parsed = self._call_critic_final(
            proposal, counter_thesis, rebuttal
        )

        # Score debate (uses InteractiveDebater's FREE-MAD scoring)
        resolution = self.debater.score_debate(proposal, counter_thesis, rebuttal)

        # Apply critic final response to refine scoring
        if critic_final_parsed:
            resolution = self._refine_with_critic_final(
                resolution, critic_final_parsed, rebuttal
            )

        # Compute confidence adjustment
        winner, conf_adj = self._compute_adjustment(resolution)

        original_conf = proposal.confidence
        final_conf = max(0.05, min(1.0, original_conf + conf_adj / 100.0))

        elapsed_ms = int((time.time() - t0) * 1000)

        result = {
            "debate_occurred": True,
            "rounds": 2,
            "trade_rebuttal": rebuttal_parsed or {},
            "critic_final": critic_final_parsed or {},
            "winner": winner,
            "confidence_adjustment": conf_adj,
            "final_confidence": round(final_conf, 3),
            "original_confidence": round(original_conf, 3),
            "reasoning": self._build_reasoning(resolution, winner),
            "key_turning_points": resolution.key_turning_points,
            "risk_flags": resolution.risk_flags,
            "recommendation": resolution.recommendation,
            "cost_tokens": self._total_debate_tokens,
            "latency_ms": elapsed_ms,
        }

        logger.info(
            f"[DEBATE] Complete: winner={winner} adj={conf_adj:+d}% "
            f"conf={original_conf:.0%}->{final_conf:.0%} "
            f"tokens={self._total_debate_tokens} latency={elapsed_ms}ms"
        )

        return result

    # ── LLM Call: Trade Rebuttal ──────────────────────────────────

    def _call_trade_rebuttal(
        self,
        proposal: ThesisProposal,
        counter_thesis: CounterThesis,
    ) -> tuple:
        """Call Trade Agent to rebut Critic's objections."""
        prompt_template = AGENT_PROMPTS.get("trade_rebuttal", "")
        if not prompt_template:
            return None, None

        # Format objections for prompt
        objections_fmt = "\n".join(
            f"  {i}. {obj['reason']} (likelihood={obj['likelihood']:.0%}, impact={obj['impact']})"
            for i, obj in enumerate(counter_thesis.objections, 1)
        ) or "  (no specific objections)"

        red_flags_fmt = "\n".join(
            f"  - {f}" for f in counter_thesis.red_flags[:3]
        ) or "  (none)"

        system_prompt = prompt_template.format(
            original_thesis=proposal.thesis,
            original_action=proposal.action.upper(),
            critic_counter_thesis=counter_thesis.counter_thesis or "No explicit counter-thesis",
            critic_objections_formatted=objections_fmt,
            critic_red_flags=red_flags_fmt,
        )

        raw_text, usage = call_llm(
            system_prompt=system_prompt,
            snapshot_json="{}",  # Context already in system prompt
            model=DEBATE_MODEL,
            max_tokens=DEBATE_MAX_TOKENS,
            max_retries=1,
            timeout=15,
        )

        in_tok = usage.get("input_tokens", 0)
        out_tok = usage.get("output_tokens", 0)
        self._total_debate_tokens += in_tok + out_tok

        # Track cost
        try:
            from llm.cost_tracker import get_cost_tracker
            get_cost_tracker().record_call(in_tok, out_tok, DEBATE_MODEL)
        except Exception:
            pass

        if raw_text is None:
            return None, None

        parsed = _parse_json(raw_text)
        return raw_text, parsed

    # ── LLM Call: Critic Final Challenge ──────────────────────────

    def _call_critic_final(
        self,
        proposal: ThesisProposal,
        counter_thesis: CounterThesis,
        rebuttal: Rebuttal,
    ) -> tuple:
        """Call Critic Agent for final response to Trade's rebuttal."""
        # Build a focused prompt for Critic's final challenge
        rebuttal_summary = "\n".join(
            f"  - {p}" for p in rebuttal.rebuttal_points[:3]
        ) or "  (no specific rebuttals)"

        concessions_summary = "\n".join(
            f"  - {c}" for c in rebuttal.concessions[:3]
        ) or "  (none)"

        system_prompt = (
            "You are the Critic Agent giving a FINAL assessment after the Trade Agent's rebuttal.\n\n"
            f"ORIGINAL TRADE THESIS: {proposal.thesis}\n"
            f"YOUR COUNTER-THESIS: {counter_thesis.counter_thesis or 'None'}\n"
            f"YOUR OBJECTIONS: {len(counter_thesis.objections)} raised\n\n"
            f"TRADE AGENT'S REBUTTAL:\n"
            f"  Maintains thesis: {rebuttal.maintains_thesis}\n"
            f"  Adjusted confidence: {rebuttal.adjusted_confidence:.0%}\n"
            f"  Defense points:\n{rebuttal_summary}\n"
            f"  Concessions:\n{concessions_summary}\n\n"
            "YOUR FINAL ASSESSMENT (JSON only):\n"
            "```json\n"
            "{\n"
            '  "rebuttal_strength": 0.0-1.0,\n'
            '  "objections_addressed": 0.0-1.0,\n'
            '  "maintains_challenge": true|false,\n'
            '  "final_verdict": "trade_wins|critic_wins|draw",\n'
            '  "unresolved_risks": ["risk1", ...],\n'
            '  "reasoning": "brief final assessment"\n'
            "}\n"
            "```\n"
            "Be concise. ~200 tokens max."
        )

        raw_text, usage = call_llm(
            system_prompt=system_prompt,
            snapshot_json="{}",
            model=DEBATE_MODEL,
            max_tokens=DEBATE_MAX_TOKENS,
            max_retries=1,
            timeout=15,
        )

        in_tok = usage.get("input_tokens", 0)
        out_tok = usage.get("output_tokens", 0)
        self._total_debate_tokens += in_tok + out_tok

        try:
            from llm.cost_tracker import get_cost_tracker
            get_cost_tracker().record_call(in_tok, out_tok, DEBATE_MODEL)
        except Exception:
            pass

        if raw_text is None:
            return None, None

        parsed = _parse_json(raw_text)
        return raw_text, parsed

    # ── Scoring helpers ───────────────────────────────────────────

    def _refine_with_critic_final(
        self,
        resolution: DebateResolution,
        critic_final: Dict[str, Any],
        rebuttal: Rebuttal,
    ) -> DebateResolution:
        """Refine FREE-MAD resolution with Critic's Round 4 assessment."""
        final_verdict = critic_final.get("final_verdict", "draw")
        rebuttal_strength = float(critic_final.get("rebuttal_strength", 0.5))
        objections_addressed = float(critic_final.get("objections_addressed", 0.5))

        # Adjust scores based on Critic's self-assessment
        if final_verdict == "trade_wins":
            resolution.trade_score = min(1.0, resolution.trade_score + 0.1)
            resolution.debate_winner = "trade"
        elif final_verdict == "critic_wins":
            resolution.critic_score = min(1.0, resolution.critic_score + 0.1)
            resolution.debate_winner = "critic"

        # Factor in how well rebuttals addressed objections
        if objections_addressed > 0.7:
            resolution.trade_score = min(1.0, resolution.trade_score + 0.05)
        elif objections_addressed < 0.3:
            resolution.critic_score = min(1.0, resolution.critic_score + 0.05)

        # Add unresolved risks
        unresolved = critic_final.get("unresolved_risks", [])
        for risk in unresolved[:3]:
            if risk not in resolution.risk_flags:
                resolution.risk_flags.append(risk)

        return resolution

    def _compute_adjustment(self, resolution: DebateResolution) -> tuple:
        """Compute winner and confidence adjustment from resolution."""
        if resolution.debate_winner == "trade":
            return "trade", CONFIDENCE_BOOST_TRADE_WINS
        elif resolution.debate_winner == "critic":
            return "critic", CONFIDENCE_CUT_CRITIC_WINS
        else:
            return "draw", CONFIDENCE_DRAW

    def _build_reasoning(self, resolution: DebateResolution, winner: str) -> str:
        """Build human-readable reasoning summary."""
        parts = [f"Debate winner: {winner}"]
        parts.append(
            f"Trade score: {resolution.trade_score:.2f}, "
            f"Critic score: {resolution.critic_score:.2f}"
        )
        if resolution.key_turning_points:
            parts.append(f"Key: {'; '.join(resolution.key_turning_points[:2])}")
        if resolution.risk_flags:
            parts.append(f"Unresolved risks: {'; '.join(resolution.risk_flags[:2])}")
        return " | ".join(parts)

    def _fallback_result(
        self,
        proposal: ThesisProposal,
        counter_thesis: CounterThesis,
        trade_decision: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Fallback when LLM calls fail -- no debate, no adjustment."""
        return {
            "debate_occurred": False,
            "rounds": 0,
            "trade_rebuttal": {},
            "critic_final": {},
            "winner": "draw",
            "confidence_adjustment": 0,
            "final_confidence": proposal.confidence,
            "original_confidence": proposal.confidence,
            "reasoning": "Debate failed (LLM error) -- no adjustment applied",
            "key_turning_points": [],
            "risk_flags": [],
            "recommendation": "proceed",
            "cost_tokens": self._total_debate_tokens,
            "latency_ms": 0,
        }

    def format_debate_for_learning(
        self,
        debate_result: Dict[str, Any],
        trade_outcome: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Format debate + outcome for Learning Agent to study."""
        parts = [
            f"DEBATE: winner={debate_result.get('winner', 'n/a')} "
            f"adj={debate_result.get('confidence_adjustment', 0):+d}%",
            f"Conf: {debate_result.get('original_confidence', 0):.0%} -> "
            f"{debate_result.get('final_confidence', 0):.0%}",
        ]

        if debate_result.get("reasoning"):
            parts.append(f"Reasoning: {debate_result['reasoning'][:200]}")

        if trade_outcome:
            pnl = trade_outcome.get("pnl", trade_outcome.get("realized_pnl", 0))
            parts.append(f"Outcome PnL: ${pnl:.2f}")

            # Was the debate winner correct?
            winner = debate_result.get("winner", "draw")
            if winner == "trade" and pnl > 0:
                parts.append("CALIBRATION: Trade won debate AND was profitable (correct)")
            elif winner == "critic" and pnl < 0:
                parts.append("CALIBRATION: Critic won debate AND trade lost (correct veto)")
            elif winner == "trade" and pnl < 0:
                parts.append("CALIBRATION: Trade won debate BUT lost money (debate failed)")
            elif winner == "critic" and pnl > 0:
                parts.append("CALIBRATION: Critic won debate BUT trade was profitable (overly cautious)")

        return " | ".join(parts)


__all__ = [
    "DebateProtocol",
    "CONFIDENCE_BOOST_TRADE_WINS",
    "CONFIDENCE_CUT_CRITIC_WINS",
]
