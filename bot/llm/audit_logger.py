"""Audit logging for all LLM decisions — enable fail-loud observability.

Every decision point in the coordinator (Regime, Trade, Risk, Critic, Learning,
Exit, Scout) generates an audit log entry. This enables:
1. Full decision traceability (why did we go/skip?)
2. Cost tracking per decision type
3. Latency monitoring per agent
4. Failure detection (parse errors, timeouts, budget exhaustion)
5. Learning from closed trades (post-hoc decision review)
"""

import json
import logging
from typing import Any, Dict, Optional, List
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

DECISIONS_LOG_PATH = Path(__file__).parent.parent / "data" / "llm" / "decisions.jsonl"


def log_decision_audit(
    symbol: str,
    action: str,  # "go", "skip", "flip", "classify"
    regime: str,
    thesis: str = "",
    confidence: float = 0.0,
    leverage: float = 1.0,
    risk_pct: float = 0.0,
    sizing_rationale: str = "",
    risk_flags: Optional[List[str]] = None,
    debate_summary: str = "",
    latency_ms: int = 0,
    cost_usd: float = 0.0,
    parse_success: bool = True,
    error: Optional[str] = None,
    trigger_reason: str = "",
) -> None:
    """Log a decision to decisions.jsonl for audit trail + learning.

    Args:
        symbol: Trading pair (BTC, ETH, SOL, HYPE, etc.)
        action: go/skip/flip/classify (decision type)
        regime: Market regime classification
        thesis: Why this action (free text, max 500 chars)
        confidence: Agent confidence 0-100
        leverage: Applied leverage (1-20x)
        risk_pct: % of equity risked (0-1)
        sizing_rationale: Why this size (max 200 chars)
        risk_flags: Any risk flags from Risk Agent
        debate_summary: Bull vs bear synthesis from Critic (max 300 chars)
        latency_ms: How long the decision took
        cost_usd: LLM cost for this decision
        parse_success: Did JSON parsing succeed?
        error: If failed, what was the error?
        trigger_reason: e.g. "pre_trade_veto", "entry_decision", "regime_classification"
    """
    try:
        entry = {
            "ts": datetime.utcnow().isoformat(),
            "symbol": symbol,
            "action": action,
            "regime": regime,
            "thesis": (thesis or "")[:500],
            "confidence": round(confidence, 2),
            "leverage": round(leverage, 2),
            "risk_pct": round(risk_pct, 4),
            "sizing_rationale": (sizing_rationale or "")[:200],
            "risk_flags": risk_flags or [],
            "debate_summary": (debate_summary or "")[:300],
            "latency_ms": latency_ms,
            "cost_usd": round(cost_usd, 6),
            "parse_success": parse_success,
            "error": error,
            "trigger_reason": trigger_reason,
        }

        # Append to decisions.jsonl (create if missing)
        DECISIONS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(DECISIONS_LOG_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")

        logger.debug(f"[AUDIT] {symbol} {action} (regime={regime}, conf={confidence:.0f}%)")
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}", exc_info=True)


def audit_regime_decision(
    symbol: str,
    regime: str,
    confidence: float = 0.0,
    latency_ms: int = 0,
    error: Optional[str] = None
) -> None:
    """Log regime classification decision."""
    log_decision_audit(
        symbol=symbol,
        action="classify",
        regime=regime,
        thesis=f"Classified market as {regime}",
        confidence=confidence,
        latency_ms=latency_ms,
        parse_success=(error is None),
        error=error,
        trigger_reason="regime_classification",
    )


def audit_trade_decision(
    symbol: str,
    action: str,  # go/skip/flip
    regime: str,
    thesis: str,
    confidence: float,
    leverage: float = 1.0,
    risk_pct: float = 0.0,
    sizing_rationale: str = "",
    risk_flags: Optional[List[str]] = None,
    debate_summary: str = "",
    latency_ms: int = 0,
    cost_usd: float = 0.0,
    error: Optional[str] = None,
) -> None:
    """Log trade entry decision with full context."""
    log_decision_audit(
        symbol=symbol,
        action=action,
        regime=regime,
        thesis=thesis,
        confidence=confidence,
        leverage=leverage,
        risk_pct=risk_pct,
        sizing_rationale=sizing_rationale,
        risk_flags=risk_flags or [],
        debate_summary=debate_summary,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        parse_success=(error is None),
        error=error,
        trigger_reason="entry_decision",
    )


def audit_risk_assessment(
    symbol: str,
    regime: str,
    decision: str,
    leverage: float,
    risk_pct: float,
    sizing_rationale: str = "",
    risk_flags: Optional[List[str]] = None,
    latency_ms: int = 0,
    cost_usd: float = 0.0,
    error: Optional[str] = None,
) -> None:
    """Log Risk Agent assessment."""
    log_decision_audit(
        symbol=symbol,
        action="assess_risk",
        regime=regime,
        thesis=f"Risk assessment: leverage={leverage:.1f}x, risk={risk_pct:.2%}",
        leverage=leverage,
        risk_pct=risk_pct,
        sizing_rationale=sizing_rationale,
        risk_flags=risk_flags or [],
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        parse_success=(error is None),
        error=error,
        trigger_reason="risk_assessment",
    )


def audit_critic_veto(
    symbol: str,
    regime: str,
    counter_thesis: str,
    confidence: float = 0.0,
    latency_ms: int = 0,
    cost_usd: float = 0.0,
    error: Optional[str] = None,
) -> None:
    """Log Critic Agent veto decision."""
    log_decision_audit(
        symbol=symbol,
        action="veto",
        regime=regime,
        thesis=counter_thesis,
        confidence=confidence,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        parse_success=(error is None),
        error=error,
        trigger_reason="critic_veto",
    )


def audit_exit_decision(
    symbol: str,
    regime: str,
    decision: str,  # hold/adjust/close
    rationale: str,
    latency_ms: int = 0,
    cost_usd: float = 0.0,
    error: Optional[str] = None,
) -> None:
    """Log Exit Agent decision on open position."""
    log_decision_audit(
        symbol=symbol,
        action=decision,
        regime=regime,
        thesis=rationale,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        parse_success=(error is None),
        error=error,
        trigger_reason="exit_decision",
    )


def audit_backend_failure(
    backend_name: str,
    error_msg: str,
    call_count: int = 1,
) -> None:
    """Log LLM backend failures for monitoring."""
    try:
        entry = {
            "ts": datetime.utcnow().isoformat(),
            "symbol": "SYSTEM",
            "action": "backend_failure",
            "regime": "unknown",
            "error": error_msg,
            "backend": backend_name,
            "call_count": call_count,
        }

        DECISIONS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(DECISIONS_LOG_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")

        logger.warning(f"[BACKEND] {backend_name} failure: {error_msg}")
    except Exception as e:
        logger.error(f"Failed to log backend failure: {e}")
