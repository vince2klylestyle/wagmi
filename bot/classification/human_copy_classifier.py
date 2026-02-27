"""
Human Copy-Trade Classifier.

Determines whether a trade is safe enough for humans to copy.
These signals should be:
- RARE (high bar)
- Extremely high confidence
- Extremely high hit-rate
- Safe regime + volatility
- Tight spread, acceptable slippage
- Sufficient liquidity

Every rejection is logged with reason for auditability.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

logger = logging.getLogger("bot.classification.human_copy")


@dataclass
class CopyTradeResult:
    """Result of human copy-trade classification."""
    eligible: bool
    reasons: List[str] = field(default_factory=list)  # Rejection reasons
    score: float = 0.0  # 0-100 copy-trade quality score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "eligible": self.eligible,
            "reasons": self.reasons,
            "score": self.score,
        }


def classify_human_copy_tradable(
    # Trade properties
    confidence: float,
    regime: str,
    volatility_band: str,
    entry_type: str,
    primary_driver: str,
    leverage: float,
    rr: float,
    # Execution properties
    snapshot_age_s: float = 0.0,
    slippage_pct: float = 0.0,
    spread_pct: float = 0.0,
    liquidity_usd: float = 100_000.0,
    # Safety flags
    circuit_breaker_active: bool = False,
    correlation_guard_violated: bool = False,
    conflicting_signals: bool = False,
    stale: bool = False,
    # Config thresholds
    min_confidence: float = 85.0,
    min_rr: float = 1.0,
    max_leverage: float = 5.0,
    max_snapshot_age: int = 5,
    max_slippage: float = 0.5,
    max_spread: float = 0.3,
    min_liquidity: float = 50_000.0,
    allowed_entry_types: Optional[List[str]] = None,
    allowed_drivers: Optional[List[str]] = None,
    stable_regimes: Optional[List[str]] = None,
    allowed_vol_bands: Optional[List[str]] = None,
) -> CopyTradeResult:
    """Classify whether a trade is human copy-tradable.

    All checks are deterministic and config-driven.
    Returns CopyTradeResult with eligibility and rejection reasons.
    """
    if allowed_entry_types is None:
        allowed_entry_types = ["TREND", "MEDIUM"]
    if allowed_drivers is None:
        allowed_drivers = ["multi_tier_quality", "regime_trend", "monte_carlo_zones"]
    if stable_regimes is None:
        stable_regimes = ["trend", "range"]
    if allowed_vol_bands is None:
        allowed_vol_bands = ["low", "medium"]

    reasons = []
    score = 100.0

    # 1. Confidence gate
    if confidence < min_confidence:
        reasons.append(f"confidence {confidence:.1f} < {min_confidence}")
        score -= 30

    # 2. Regime stability
    if regime.lower() not in [r.lower() for r in stable_regimes]:
        reasons.append(f"regime '{regime}' not in stable regimes {stable_regimes}")
        score -= 20

    # 3. Volatility band
    if volatility_band.lower() not in [v.lower() for v in allowed_vol_bands]:
        reasons.append(f"volatility_band '{volatility_band}' not in {allowed_vol_bands}")
        score -= 15

    # 4. Entry type
    if entry_type.upper() not in [e.upper() for e in allowed_entry_types]:
        reasons.append(f"entry_type '{entry_type}' not in {allowed_entry_types}")
        score -= 15

    # 5. Primary driver quality
    if primary_driver.lower() not in [d.lower() for d in allowed_drivers]:
        reasons.append(f"driver '{primary_driver}' not in {allowed_drivers}")
        score -= 10

    # 6. Leverage cap
    if leverage > max_leverage:
        reasons.append(f"leverage {leverage:.1f}x > {max_leverage}x")
        score -= 20

    # 7. Risk-reward
    if rr < min_rr:
        reasons.append(f"R:R {rr:.2f} < {min_rr}")
        score -= 15

    # 8. Stale signal
    if stale or snapshot_age_s > max_snapshot_age:
        reasons.append(f"stale signal (age={snapshot_age_s:.1f}s > {max_snapshot_age}s)")
        score -= 25

    # 9. Slippage
    if slippage_pct > max_slippage:
        reasons.append(f"slippage {slippage_pct:.3f}% > {max_slippage}%")
        score -= 20

    # 10. Spread
    if spread_pct > max_spread:
        reasons.append(f"spread {spread_pct:.3f}% > {max_spread}%")
        score -= 15

    # 11. Liquidity
    if liquidity_usd < min_liquidity:
        reasons.append(f"liquidity ${liquidity_usd:,.0f} < ${min_liquidity:,.0f}")
        score -= 20

    # 12. Circuit breaker
    if circuit_breaker_active:
        reasons.append("circuit breaker active")
        score -= 50

    # 13. Correlation guard
    if correlation_guard_violated:
        reasons.append("correlation guard violated")
        score -= 30

    # 14. Conflicting signals
    if conflicting_signals:
        reasons.append("conflicting strategy signals")
        score -= 15

    eligible = len(reasons) == 0
    score = max(0.0, min(100.0, score))

    if not eligible:
        logger.debug(
            f"[COPY] NOT eligible: {', '.join(reasons[:3])}"
        )

    return CopyTradeResult(
        eligible=eligible,
        reasons=reasons,
        score=score,
    )


def format_copy_trades_telegram(
    recent_trades: List[Dict[str, Any]],
    max_display: int = 10,
) -> str:
    """Format recent copy-tradable signals for Telegram."""
    copy_trades = [t for t in recent_trades if t.get("human_copy_tradable")]

    if not copy_trades:
        return "No human copy-tradable signals recently."

    lines = [f"COPY-TRADE SIGNALS ({len(copy_trades)} found):"]
    for t in copy_trades[-max_display:]:
        lines.append(
            f"\n  {t.get('symbol', '?')} {t.get('side', '?')}"
            f"\n  Entry: {t.get('effective_entry', t.get('entry', '?'))}"
            f"\n  Confidence: {t.get('confidence', '?')}%"
            f"\n  R:R: {t.get('rr1', '?')}"
            f"\n  Regime: {t.get('regime', '?')}"
            f"\n  Type: {t.get('entry_type', '?')}"
        )
    return "\n".join(lines)
