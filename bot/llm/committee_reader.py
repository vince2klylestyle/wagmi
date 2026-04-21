"""Committee Reader — bot-facing interface to the live_analyst's thesis output.

This module lets the signal pipeline consult the public committee's verdict
before firing a trade. Read-only, no side effects, safe to import anywhere.

Use cases:
  1. "Does the committee currently VETO this symbol?" — block trade if so.
  2. "What did the committee say most recently?" — for logging/display.
  3. "How stale is the current thesis?" — decide if we should rely on it.

Designed to be flag-gated at call site:
    from llm.committee_reader import committee_veto_reason
    if config.committee_gate_enabled:
        veto = committee_veto_reason(symbol, side="BUY", max_age_s=900)
        if veto:
            logger.info(f"[{symbol}] Committee veto: {veto}")
            return None
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("bot.llm.committee_reader")

# Where live_analyst.py writes thesis.json files
THESIS_ROOT = Path(__file__).resolve().parent.parent.parent / "web" / "public" / "thesis"


def load_thesis(symbol: str) -> Optional[Dict[str, Any]]:
    """Load the most recent thesis.json for a symbol (or None if missing/stale)."""
    path = THESIS_ROOT / symbol.lower() / "thesis.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"[{symbol}] thesis.json parse failed: {e}")
        return None


def thesis_age_seconds(thesis: Dict[str, Any]) -> Optional[float]:
    """Return how old the thesis is in seconds. None if unparseable."""
    ts = thesis.get("updated_at")
    if not ts:
        return None
    try:
        then = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - then).total_seconds()
    except Exception:
        return None


def committee_verdict(symbol: str, max_age_s: int = 900) -> Optional[Dict[str, Any]]:
    """Return the committee verdict if thesis is fresh, else None.

    Args:
        symbol: e.g. "BTC"
        max_age_s: drop if older than this many seconds. Default 15 min.

    Returns:
        dict with keys: regime, trade, critic, age_s, mode. None if missing/stale.
    """
    thesis = load_thesis(symbol)
    if not thesis:
        return None
    age = thesis_age_seconds(thesis)
    if age is None or age > max_age_s:
        return None
    committee = thesis.get("committee", {}) or {}
    return {
        "regime": committee.get("regime", {}),
        "trade": committee.get("trade", {}),
        "critic": committee.get("critic", {}),
        "mode": committee.get("mode", "unknown"),
        "age_s": round(age, 1),
        "symbol": symbol,
    }


def committee_veto_reason(
    symbol: str,
    side: str = "BUY",
    max_age_s: int = 900,
) -> Optional[str]:
    """Return a veto reason string if committee wants to block, else None.

    Logic:
      - Missing/stale thesis: no veto (don't block trades just because analyst is offline)
      - Critic vote=veto: veto with critic's reason
      - Trade agent action=wait + Critic vote=reduce: veto (committee wants to pause)
      - Trade agent recommends OPPOSITE side: veto (directional conflict)
      - Otherwise: no veto
    """
    v = committee_verdict(symbol, max_age_s)
    if not v:
        return None  # no thesis or stale — don't block

    critic = v.get("critic", {}) or {}
    trade = v.get("trade", {}) or {}

    # Explicit veto from Critic agent
    vote = critic.get("vote", "")
    if vote == "veto":
        narrative = (critic.get("narrative") or "")[:200]
        flags = critic.get("risk_flags") or []
        return f"Critic VETO: {narrative} (flags: {', '.join(flags) if flags else 'none'})"

    # Directional conflict: trade says go_short but signal is BUY (or vice versa)
    action = trade.get("action", "")
    side_upper = side.upper()
    if action == "go_short" and side_upper in ("BUY", "LONG"):
        return f"Committee says go_short; signal is {side_upper}. Directional conflict."
    if action == "go_long" and side_upper in ("SELL", "SHORT"):
        return f"Committee says go_long; signal is {side_upper}. Directional conflict."

    # Both wait + reduce = committee is pausing
    if action == "wait" and vote == "reduce":
        return "Committee is in pause mode (trade=wait + critic=reduce)."

    return None


def committee_size_multiplier(symbol: str, max_age_s: int = 900) -> float:
    """How much should position size be scaled based on committee verdict?

    Returns a multiplier 0.0-1.5:
      - 1.0 if no thesis or no modifier
      - 0.5 if critic says reduce
      - 0.0 if critic says veto (caller should also check veto_reason)
      - 1.2 if both trade says go_long/short AND critic says pass AND conviction 4/4
    """
    v = committee_verdict(symbol, max_age_s)
    if not v:
        return 1.0
    critic = v.get("critic", {}) or {}
    vote = critic.get("vote", "")
    if vote == "veto":
        return 0.0
    if vote == "reduce":
        return 0.5
    return 1.0


def committee_snapshot(symbol: str, max_age_s: int = 900) -> Dict[str, Any]:
    """Human-readable snapshot for logging/display.

    Returns:
        {"ok": bool, "symbol": str, "age_s": float or None,
         "regime": str, "action": str, "vote": str, "narrative": str,
         "veto_reason": str or None}
    """
    v = committee_verdict(symbol, max_age_s)
    if not v:
        return {"ok": False, "symbol": symbol, "reason": "no thesis or stale"}
    regime = v.get("regime", {}) or {}
    trade = v.get("trade", {}) or {}
    critic = v.get("critic", {}) or {}
    return {
        "ok": True,
        "symbol": symbol,
        "age_s": v.get("age_s"),
        "mode": v.get("mode"),
        "regime": regime.get("regime_label", "?"),
        "regime_conf": regime.get("confidence"),
        "bias": regime.get("bias"),
        "action": trade.get("action", "?"),
        "action_conf": trade.get("confidence"),
        "vote": critic.get("vote", "?"),
        "veto_reason": committee_veto_reason(symbol, max_age_s=max_age_s),
        "regime_narrative": (regime.get("narrative") or "")[:300],
        "trade_narrative": (trade.get("narrative") or "")[:300],
        "critic_narrative": (critic.get("narrative") or "")[:300],
    }


# Feature flag (off by default — wire into signal_pipeline at user's discretion)
def is_enabled() -> bool:
    return os.getenv("COMMITTEE_GATE_ENABLED", "").lower() in ("1", "true", "yes", "on")


if __name__ == "__main__":
    import sys
    symbols = sys.argv[1:] or ["BTC", "ETH", "SOL", "HYPE"]
    print(f"THESIS_ROOT: {THESIS_ROOT}")
    print(f"COMMITTEE_GATE_ENABLED: {is_enabled()}")
    print()
    for s in symbols:
        snap = committee_snapshot(s)
        print(f"=== {s} ===")
        if not snap.get("ok"):
            print(f"  {snap.get('reason', '?')}")
            continue
        print(f"  age: {snap['age_s']}s  mode: {snap['mode']}")
        print(f"  regime: {snap['regime']} ({snap['regime_conf']}%) bias={snap['bias']}")
        print(f"  trade : {snap['action']} ({snap['action_conf']}%)")
        print(f"  critic: {snap['vote']}")
        if snap['veto_reason']:
            print(f"  VETO: {snap['veto_reason'][:150]}")
        print()
