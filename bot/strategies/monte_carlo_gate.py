"""
Monte Carlo Zones Gate: Conditional enablement for MC signals.

Based on AUDIT_FINDINGS_AND_ACTIONS.md Phase 1:
- Opportunity: 2,448 disabled signals, 57% WR, ~$600-800 PnL/cycle
- Condition: regime in [ranging, consolidation], confidence >= 65%, drawdown < 3%
- Expected: +2,400 signals/cycle, 55%+ WR, +$600 PnL improvement
"""

import logging
from typing import Optional
from strategies.base import Signal

logger = logging.getLogger("bot.strategies.monte_carlo_gate")


class MonteCarloGate:
    """
    Conditional gate for Monte Carlo Zone signals.

    Filters signals based on:
    1. Regime match (ranging or consolidation)
    2. Minimum confidence (65%)
    3. Maximum recent drawdown (< 3%)
    """

    def __init__(
        self,
        enabled: bool = False,
        regime_whitelist: Optional[list] = None,
        min_confidence: float = 65.0,
        max_drawdown_pct: float = 3.0,
    ):
        self.enabled = enabled
        self.regime_whitelist = regime_whitelist or ["ranging", "consolidation"]
        self.min_confidence = min_confidence
        self.max_drawdown_pct = max_drawdown_pct
        self._rejection_counts = {}

    def should_allow_signal(
        self,
        signal: Signal,
        current_drawdown_pct: float = 0.0,
    ) -> tuple[bool, str]:
        """
        Determine if a Monte Carlo signal should be allowed.

        Args:
            signal: The signal to evaluate
            current_drawdown_pct: Current portfolio drawdown %

        Returns:
            (allowed: bool, reason: str)
        """
        if not self.enabled:
            return False, "monte_carlo_gate_disabled"

        if signal.strategy != "monte_carlo_zones":
            return True, "not_monte_carlo"  # Don't gate non-MC signals

        # Check regime
        regime = (signal.metadata or {}).get("regime", "unknown")
        if regime not in self.regime_whitelist:
            reason = f"regime_mismatch: {regime} not in {self.regime_whitelist}"
            self._record_rejection(signal, reason)
            return False, reason

        # Check confidence
        if signal.confidence < self.min_confidence:
            reason = f"confidence_floor: {signal.confidence:.1f}% < {self.min_confidence:.1f}%"
            self._record_rejection(signal, reason)
            return False, reason

        # Check drawdown
        if current_drawdown_pct >= self.max_drawdown_pct:
            reason = f"drawdown_limit: {current_drawdown_pct:.2f}% >= {self.max_drawdown_pct:.2f}%"
            self._record_rejection(signal, reason)
            return False, reason

        # All checks passed
        return True, "allowed"

    def _record_rejection(self, signal: Signal, reason: str):
        """Track rejection reasons for analysis."""
        key = f"{signal.symbol}_{reason}"
        self._rejection_counts[key] = self._rejection_counts.get(key, 0) + 1

    def get_rejection_summary(self) -> dict:
        """Return summary of rejections for diagnostics."""
        return self._rejection_counts.copy()

    def reset_rejection_counts(self):
        """Reset rejection tracking counters."""
        self._rejection_counts.clear()
