"""Alpha gate — unified quant signals (shadow mode ship).

Combines Bonferroni-clearing signals into a single decision function.
Shadow mode: logs its verdict per signal but does NOT enforce.

Signals (from Wave 17 synthesis):
  1. btc_4h_return_signed (IC +0.519 universal per BTC_PER_SYMBOL_SIGN study)
  2. rsi_div_1h_6h_aligned (IC +0.456)
  3. chop_score_proxy, inverse (IC -0.384)
  4. conviction_count (trend z=3.615)

Hard floor: conviction_count >= 2. Size boost: conviction_count >= 4.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("bot.alpha_gate")


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name, "").lower()
    return v in ("1", "true", "yes", "on") if v else default


ALPHA_GATE_ENABLED = _env_bool("ALPHA_GATE_ENABLED", False)
ALPHA_GATE_SHADOW = _env_bool("ALPHA_GATE_SHADOW", True)


@dataclass
class AlphaGateVerdict:
    passes: bool
    conviction_count: int
    size_multiplier: float
    reason: str
    btc_4h_aligned: bool
    rsi_div_aligned: bool
    chop_below_threshold: bool
    num_agree: int


def _btc_4h_signed_aligned(context: dict) -> Optional[bool]:
    try:
        v = context.get("btc_4h_return_signed")
        if v is None:
            return None
        return v > 0
    except Exception:
        return None


def _rsi_div_aligned(context: dict) -> Optional[bool]:
    try:
        v = context.get("rsi_div_1h_6h_aligned")
        if v is None:
            return None
        return bool(v)
    except Exception:
        return None


def _chop_ok(context: dict, threshold: float = 0.60) -> Optional[bool]:
    try:
        chop = context.get("chop_score", context.get("chop_score_smoothed"))
        if chop is None:
            return None
        return chop <= threshold
    except Exception:
        return None


def evaluate(signal, context: dict) -> AlphaGateVerdict:
    """Return a verdict given the signal + an evaluation context.

    context keys (when available): num_agree, chop_score,
    btc_4h_return_signed, rsi_div_1h_6h_aligned.
    """
    num_agree = int(context.get("num_agree", 0))
    btc_aligned = _btc_4h_signed_aligned(context)
    rsi_aligned = _rsi_div_aligned(context)
    chop_ok = _chop_ok(context)

    conviction = 0
    reasons = []
    if num_agree >= 2:
        conviction += 1
        reasons.append(f"num_agree>=2 ({num_agree})")
    if btc_aligned is True:
        conviction += 1
        reasons.append("btc_4h_aligned")
    if rsi_aligned is True:
        conviction += 1
        reasons.append("rsi_div_aligned")
    if chop_ok is True:
        conviction += 1
        reasons.append("chop_ok")

    passes = num_agree >= 2
    size_mult = 1.5 if conviction >= 4 else 1.0

    return AlphaGateVerdict(
        passes=passes,
        conviction_count=conviction,
        size_multiplier=size_mult,
        reason="; ".join(reasons) if reasons else "insufficient signals",
        btc_4h_aligned=bool(btc_aligned) if btc_aligned is not None else False,
        rsi_div_aligned=bool(rsi_aligned) if rsi_aligned is not None else False,
        chop_below_threshold=bool(chop_ok) if chop_ok is not None else False,
        num_agree=num_agree,
    )


def log_shadow_verdict(signal, verdict: AlphaGateVerdict, actual_fire_outcome: Optional[bool] = None) -> None:
    """Log the shadow verdict to a dedicated jsonl for post-hoc analysis."""
    try:
        path = os.getenv("ALPHA_GATE_SHADOW_PATH", "data/alpha_gate_shadow.jsonl")
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "symbol": getattr(signal, "symbol", "?"),
            "side": getattr(signal, "side", "?"),
            "strategy": getattr(signal, "strategy", ""),
            "passes": verdict.passes,
            "conviction_count": verdict.conviction_count,
            "size_mult": verdict.size_multiplier,
            "reason": verdict.reason,
            "btc_4h_aligned": verdict.btc_4h_aligned,
            "rsi_div_aligned": verdict.rsi_div_aligned,
            "chop_below_threshold": verdict.chop_below_threshold,
            "num_agree": verdict.num_agree,
            "actual_fired": actual_fire_outcome,
        }
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except Exception as e:
        logger.exception("[ALPHA-GATE-SHADOW] log failure: %s", e)
