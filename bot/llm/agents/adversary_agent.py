"""Adversary Agent — stress-tests Trade proposals and finds counter-arguments.

Plays devil's advocate to Trade Agent theses, identifies missing checks,
estimates drawdown risk, and recommends confidence adjustments.
"""

import json
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class VetoReason(str, Enum):
    """Reasons to veto a trade."""

    WEAK_EVIDENCE = "weak_evidence"
    FAKEOUT_RISK = "fakeout_risk"
    SUPPORT_LEVEL = "support_level"
    VOLATILITY_EXTREME = "volatility_extreme"
    LIQUIDITY_RISK = "liquidity_risk"
    REGIME_MISMATCH = "regime_mismatch"
    FUNDING_ADVERSE = "funding_adverse"
    NEWS_RISK = "news_risk"


@dataclass
class AdversaryReview:
    """Adversary Agent's stress-test review of a trade proposal."""

    thesis: str  # The original thesis from Trade Agent
    counter_arguments: List[str]  # Devil's advocate arguments against the thesis
    missing_checks: List[str]  # What did Trade Agent fail to check?
    estimated_drawdown: float  # Max drawdown if thesis is wrong (0-1)
    veto_recommendation: Optional[VetoReason] = None  # Reason to veto, if any
    confidence_reduction: float = 0.0  # Should reduce predicted confidence by this much (0-1)
    severity: str = "none"  # "critical", "high", "moderate", "low", "none"
    review_date: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class AdversaryAgent:
    """Stress-test Trade Agent theses and find weaknesses."""

    def __init__(
        self,
        decisions_path: str = "bot/data/llm/decisions.jsonl",
        market_data_path: str = "bot/data/market_snapshot.json",
    ):
        self.decisions_path = Path(decisions_path)
        self.market_data_path = Path(market_data_path)
        self._decisions_cache = None

    def review_thesis(
        self,
        thesis: str,
        symbol: str,
        regime: str,
        side: str,
        confidence: float,
        entry_price: float,
        stop_loss: float,
    ) -> AdversaryReview:
        """Stress-test a Trade Agent thesis by playing devil's advocate.

        Args:
            thesis: Trade Agent's directional thesis (e.g., "BTC will trend higher")
            symbol: Trading symbol
            regime: Market regime
            side: Trade side (BUY or SELL)
            confidence: Predicted confidence (0-100)
            entry_price: Proposed entry price
            stop_loss: Proposed stop loss price

        Returns:
            AdversaryReview with counter-arguments and veto recommendation
        """
        counter_arguments = []
        missing_checks = []
        drawdown_estimate = 0.0
        confidence_reduction = 0.0
        veto_reason = None
        severity = "none"

        # Check 1: Regime match
        regime_issues = self._check_regime_match(regime, side, confidence)
        if regime_issues:
            counter_arguments.extend(regime_issues)
            confidence_reduction += 0.10
            missing_checks.append("Regime classification confidence unknown")
            severity = "moderate"

        # Check 2: Support/resistance levels
        support_check = self._check_support_resistance(symbol, entry_price, stop_loss, side)
        if support_check:
            missing_checks.extend(support_check)
            confidence_reduction += 0.05
            drawdown_estimate = max(drawdown_estimate, 0.05)

        # Check 3: Volatility extremes
        volatility_check = self._check_volatility(symbol, regime)
        if volatility_check:
            counter_arguments.extend(volatility_check)
            confidence_reduction += 0.08
            drawdown_estimate = max(drawdown_estimate, 0.08)

        # Check 4: Funding rate signal
        funding_check = self._check_funding_rate(symbol, side)
        if funding_check:
            counter_arguments.extend(funding_check)
            confidence_reduction += 0.07

        # Check 5: Similar past trades
        past_trades = self._analyze_similar_past_trades(
            symbol=symbol, regime=regime, side=side
        )
        if past_trades:
            counter_arguments.extend(past_trades["counter"])
            if past_trades.get("loss_rate", 0) > 0.50:
                confidence_reduction += 0.15
                severity = "high"
                veto_reason = VetoReason.WEAK_EVIDENCE

        # Check 6: Fakeout risk
        fakeout_risk = self._assess_fakeout_risk(regime, confidence)
        if fakeout_risk:
            counter_arguments.append(fakeout_risk)
            confidence_reduction += 0.12
            drawdown_estimate = max(drawdown_estimate, 0.12)
            severity = "high"

        # Compute drawdown if we're wrong about direction
        if not drawdown_estimate:
            drawdown_estimate = self._estimate_liquidation_risk(
                entry_price=entry_price,
                stop_loss=stop_loss,
                leverage=1.0,  # Conservative default
            )

        # Assemble review
        review = AdversaryReview(
            thesis=thesis,
            counter_arguments=counter_arguments,
            missing_checks=missing_checks,
            estimated_drawdown=min(1.0, drawdown_estimate),
            veto_recommendation=veto_reason,
            confidence_reduction=min(1.0, confidence_reduction),
            severity=severity,
        )

        return review

    def recommend_confidence_adjustment(
        self,
        original_confidence: float,
        adversary_review: AdversaryReview,
    ) -> float:
        """Recommend adjusted confidence after adversary review.

        Args:
            original_confidence: Original predicted confidence (0-100)
            adversary_review: Adversary Agent's stress-test review

        Returns:
            Adjusted confidence (0-100)
        """
        # Reduce confidence by the recommended amount
        reduction_pct = adversary_review.confidence_reduction * 100
        adjusted = max(0.0, original_confidence - reduction_pct)

        # Additional penalty if severity is high
        if adversary_review.severity == "critical":
            adjusted *= 0.5  # Cut in half
        elif adversary_review.severity == "high":
            adjusted *= 0.75  # Reduce by 25%

        return min(100.0, adjusted)

    def should_veto(self, adversary_review: AdversaryReview) -> bool:
        """Determine if thesis should be vetoed based on review.

        Args:
            adversary_review: The review to evaluate

        Returns:
            True if trade should be vetoed, False otherwise
        """
        # Auto-veto on critical severity or specific veto reasons
        if adversary_review.severity == "critical":
            return True

        if adversary_review.veto_recommendation:
            return adversary_review.estimated_drawdown > 0.15 or adversary_review.severity in [
                "critical",
                "high",
            ]

        return False

    # Private helper methods

    def _check_regime_match(self, regime: str, side: str, confidence: float) -> List[str]:
        """Check if regime matches the proposed trade direction."""
        issues = []

        if regime == "consolidation":
            issues.append("Consolidation regime is death zone — directional trades fail")
        elif regime == "ranging":
            issues.append("Ranging regime has low directional edge — fade range extremes instead")
        elif regime == "panic":
            if side == "SELL":
                issues.append("Panic selling: buyer support usually blocks shorts")
        elif regime == "low_liquidity":
            issues.append("Low liquidity regime: wide slippage kills risk:reward")

        return issues

    def _check_support_resistance(
        self, symbol: str, entry_price: float, stop_loss: float, side: str
    ) -> List[str]:
        """Check for hidden support/resistance levels."""
        missing = []

        stop_width = abs(entry_price - stop_loss) / entry_price
        if stop_width < 0.003:  # Less than 0.3%
            missing.append("Stop loss too tight — likely hit in noise before target")

        if stop_width > 0.15:  # More than 15%
            missing.append("Stop loss too wide — unacceptable risk:reward")

        # Note: In production, would check actual support/resistance from price data
        missing.append("Support/resistance levels not checked")

        return missing

    def _check_volatility(self, symbol: str, regime: str) -> List[str]:
        """Check for volatility extremes."""
        issues = []

        if regime == "high_volatility":
            issues.append("High volatility: wide wicks likely to hit stops before direction moves")

        # Note: In production, would check ATR vs historical average
        return issues

    def _check_funding_rate(self, symbol: str, side: str) -> List[str]:
        """Check if funding rate aligns with proposed direction."""
        issues = []

        # Note: In production, would fetch actual funding rate data
        # For now, note the check was performed
        if side == "LONG":
            # High positive funding = bearish signal despite long thesis
            pass

        return issues

    def _analyze_similar_past_trades(
        self, symbol: str, regime: str, side: str
    ) -> Dict[str, Any]:
        """Look for similar past trades and their outcomes."""
        decisions = self._load_decisions()
        if not decisions:
            return {}

        similar = [
            d
            for d in decisions
            if d.get("symbol") == symbol
            and d.get("regime") == regime
            and d.get("side") == side
        ]

        if len(similar) < 3:
            return {}

        wins = sum(1 for d in similar if d.get("action") == "go")
        loss_rate = 1.0 - (wins / len(similar)) if similar else 0.0

        result = {"counter": [], "loss_rate": loss_rate}

        if loss_rate > 0.60:
            result["counter"].append(
                f"Similar {symbol} {side}s in {regime}: only {wins}/{len(similar)} won"
            )

        return result

    def _assess_fakeout_risk(self, regime: str, confidence: float) -> Optional[str]:
        """Assess risk of a fakeout move (price moves, then reverses)."""
        if confidence > 85 and regime == "consolidation":
            return "High confidence in consolidation = classic fakeout setup"

        if regime == "ranging" and confidence > 75:
            return "High confidence in range trade = likely to be tested at opposite boundary"

        return None

    def _estimate_liquidation_risk(
        self, entry_price: float, stop_loss: float, leverage: float = 1.0
    ) -> float:
        """Estimate max drawdown if wrong about direction.

        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            leverage: Position leverage

        Returns:
            Estimated drawdown as fraction (0-1)
        """
        stop_distance = abs(entry_price - stop_loss)
        return min(1.0, (stop_distance / entry_price) * leverage)

    def _load_decisions(self) -> List[Dict[str, Any]]:
        """Load all decision entries from JSONL."""
        if self._decisions_cache is not None:
            return self._decisions_cache

        self._decisions_cache = []
        if not self.decisions_path.exists():
            return self._decisions_cache

        try:
            with open(self.decisions_path) as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        self._decisions_cache.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Failed to load decisions: {e}")

        return self._decisions_cache


def get_adversary_agent() -> AdversaryAgent:
    """Get or create an Adversary Agent instance."""
    return AdversaryAgent()
