"""
Execution Price Guard.

Pre-execution sanity checks that protect against:
- Stale signals (snapshot too old)
- Excessive slippage (live vs snapshot diverged)
- Wide spreads
- Low liquidity
- Volatility spikes
- Price deviation beyond tolerance

Every check logs its reason and returns a verdict.
"""

import logging
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

logger = logging.getLogger("bot.execution.price_guard")


@dataclass
class GuardResult:
    """Result of a pre-execution guard check."""
    passed: bool
    action: str  # "proceed", "downgrade", "veto"
    checks: List[dict]  # Each check: {name, passed, value, threshold, action}

    @property
    def veto_reasons(self) -> List[str]:
        return [c["name"] for c in self.checks if c["action"] == "veto"]

    @property
    def downgrade_reasons(self) -> List[str]:
        return [c["name"] for c in self.checks if c["action"] == "downgrade"]


def validate_execution_price(
    exec_price: float,
    live_price: float,
    max_rel_diff: float = 0.01,
) -> bool:
    """Check if execution price is within tolerance of live price."""
    if live_price <= 0:
        return True
    rel = abs(exec_price - live_price) / live_price
    return rel <= max_rel_diff


def pre_execution_guard(
    snapshot_entry: float,
    live_price: Optional[float],
    snapshot_age_s: float,
    slippage_pct: float = 0.0,
    spread_pct: float = 0.0,
    liquidity_usd: float = 100_000.0,
    volatility_ratio: float = 1.0,
    circuit_breaker_active: bool = False,
    correlation_guard_violated: bool = False,
    # Config thresholds
    max_snapshot_age: float = 10.0,
    max_slippage_pct: float = 0.5,
    max_spread_pct: float = 0.3,
    min_liquidity_usd: float = 50_000.0,
    max_price_deviation_pct: float = 1.0,
    max_vol_spike_mult: float = 3.0,
    # Actions for each violation
    on_stale: str = "downgrade",
    on_slippage: str = "veto",
    on_spread: str = "downgrade",
    on_liquidity: str = "veto",
) -> GuardResult:
    """Run all pre-execution sanity checks.

    Returns a GuardResult with the overall verdict and per-check details.
    """
    checks = []

    # 1. Circuit breaker
    if circuit_breaker_active:
        checks.append({
            "name": "circuit_breaker",
            "passed": False,
            "value": True,
            "threshold": False,
            "action": "veto",
        })

    # 2. Correlation guard
    if correlation_guard_violated:
        checks.append({
            "name": "correlation_guard",
            "passed": False,
            "value": True,
            "threshold": False,
            "action": "veto",
        })

    # 3. Snapshot age (stale signal)
    stale = snapshot_age_s > max_snapshot_age
    checks.append({
        "name": "snapshot_age",
        "passed": not stale,
        "value": round(snapshot_age_s, 1),
        "threshold": max_snapshot_age,
        "action": on_stale if stale else "proceed",
    })

    # 4. Slippage
    slip_violated = slippage_pct > max_slippage_pct
    checks.append({
        "name": "slippage",
        "passed": not slip_violated,
        "value": round(slippage_pct, 4),
        "threshold": max_slippage_pct,
        "action": on_slippage if slip_violated else "proceed",
    })

    # 5. Spread
    spread_violated = spread_pct > max_spread_pct
    checks.append({
        "name": "spread",
        "passed": not spread_violated,
        "value": round(spread_pct, 4),
        "threshold": max_spread_pct,
        "action": on_spread if spread_violated else "proceed",
    })

    # 6. Liquidity
    liq_violated = liquidity_usd < min_liquidity_usd
    checks.append({
        "name": "liquidity",
        "passed": not liq_violated,
        "value": round(liquidity_usd, 0),
        "threshold": min_liquidity_usd,
        "action": on_liquidity if liq_violated else "proceed",
    })

    # 7. Price deviation (live vs snapshot)
    if live_price and snapshot_entry > 0:
        deviation = abs(live_price - snapshot_entry) / snapshot_entry * 100
    else:
        deviation = 0.0
    dev_violated = deviation > max_price_deviation_pct
    checks.append({
        "name": "price_deviation",
        "passed": not dev_violated,
        "value": round(deviation, 4),
        "threshold": max_price_deviation_pct,
        "action": "veto" if dev_violated else "proceed",
    })

    # 8. Volatility spike
    vol_violated = volatility_ratio > max_vol_spike_mult
    checks.append({
        "name": "volatility_spike",
        "passed": not vol_violated,
        "value": round(volatility_ratio, 2),
        "threshold": max_vol_spike_mult,
        "action": "downgrade" if vol_violated else "proceed",
    })

    # Determine overall action
    any_veto = any(c["action"] == "veto" for c in checks)
    any_downgrade = any(c["action"] == "downgrade" for c in checks)

    if any_veto:
        overall = "veto"
        passed = False
    elif any_downgrade:
        overall = "downgrade"
        passed = True  # Proceed but with reduced size/confidence
    else:
        overall = "proceed"
        passed = True

    result = GuardResult(passed=passed, action=overall, checks=checks)

    # Log failures
    for c in checks:
        if not c["passed"]:
            logger.info(
                f"[GUARD] {c['name']}: FAIL "
                f"(value={c['value']}, threshold={c['threshold']}, action={c['action']})"
            )

    return result
