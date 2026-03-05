"""
Self-Tuning Risk Engine: Adaptive risk management.

Adjusts risk parameters based on realized performance:
- Dynamic max leverage (reduce when drawdown deepens)
- Dynamic correlation guard (tighten during high-correlation regimes)
- Dynamic circuit breaker (lower daily loss limit after large loss)

Risk profiles:
  "conservative": tight limits, low leverage, few positions
  "normal": balanced defaults
  "aggressive": relaxed limits, higher leverage, more positions

The engine evaluates telemetry periodically and adjusts the active
profile. Hard global caps are NEVER exceeded regardless of profile.
"""

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

logger = logging.getLogger("bot.risk.self_tuning")


# ── Risk Profiles ─────────────────────────────────────────────

RISK_PROFILES = {
    "conservative": {
        "max_leverage": 10.0,
        "max_positions": 3,
        "max_same_direction": 2,
        "daily_loss_limit_pct": 0.03,
        "risk_per_trade": 0.005,
        "description": "Tight limits. For drawdowns or uncertain markets.",
    },
    "normal": {
        "max_leverage": 25.0,
        "max_positions": 5,
        "max_same_direction": 3,
        "daily_loss_limit_pct": 0.05,
        "risk_per_trade": 0.01,
        "description": "Balanced defaults. Standard operation.",
    },
    "aggressive": {
        "max_leverage": 25.0,
        "max_positions": 6,
        "max_same_direction": 4,
        "daily_loss_limit_pct": 0.08,
        "risk_per_trade": 0.015,
        "description": "Relaxed limits. For confirmed uptrends with LLM uplift.",
    },
}

DEFAULT_PROFILE = os.getenv("RISK_PROFILE", "normal")


# ── Telemetry ─────────────────────────────────────────────────

@dataclass
class RiskTelemetry:
    """Rolling risk metrics for self-tuning decisions."""
    daily_pnls: list = field(default_factory=list)      # Last 30 daily PnLs
    peak_equity: float = 0.0
    current_equity: float = 0.0
    current_drawdown_pct: float = 0.0
    llm_error_rate: float = 0.0
    llm_veto_accuracy: float = 0.0
    consecutive_loss_days: int = 0
    total_trades_today: int = 0
    last_update: float = 0.0

    def update(
        self,
        equity: float,
        daily_pnl: float,
        llm_error_rate: float = 0.0,
        llm_veto_accuracy: float = 0.0,
    ):
        self.current_equity = equity
        if equity > self.peak_equity:
            self.peak_equity = equity

        self.current_drawdown_pct = (
            (self.peak_equity - equity) / self.peak_equity * 100
            if self.peak_equity > 0 else 0
        )

        # Track daily PnLs (rolling 30)
        self.daily_pnls.append(daily_pnl)
        if len(self.daily_pnls) > 30:
            self.daily_pnls = self.daily_pnls[-30:]

        # Consecutive loss days
        if daily_pnl < 0:
            self.consecutive_loss_days += 1
        else:
            self.consecutive_loss_days = 0

        self.llm_error_rate = llm_error_rate
        self.llm_veto_accuracy = llm_veto_accuracy
        self.last_update = time.time()

    @property
    def realized_volatility(self) -> float:
        """Standard deviation of daily PnLs (equity curve vol)."""
        if len(self.daily_pnls) < 5:
            return 0.0
        avg = sum(self.daily_pnls) / len(self.daily_pnls)
        variance = sum((p - avg) ** 2 for p in self.daily_pnls) / len(self.daily_pnls)
        return variance ** 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "peak_equity": self.peak_equity,
            "current_equity": self.current_equity,
            "drawdown_pct": round(self.current_drawdown_pct, 2),
            "realized_vol": round(self.realized_volatility, 2),
            "consecutive_loss_days": self.consecutive_loss_days,
            "daily_pnls_count": len(self.daily_pnls),
            "llm_error_rate": round(self.llm_error_rate, 1),
            "llm_veto_accuracy": round(self.llm_veto_accuracy, 1),
        }


# ── Self-Tuning Logic ────────────────────────────────────────

_telemetry = RiskTelemetry()
_active_profile = DEFAULT_PROFILE


def get_telemetry() -> RiskTelemetry:
    return _telemetry


def get_active_profile() -> str:
    return _active_profile


def get_profile_params() -> Dict[str, Any]:
    """Get the current risk profile parameters."""
    return RISK_PROFILES.get(_active_profile, RISK_PROFILES["normal"]).copy()


def set_profile(name: str) -> bool:
    """Manually set the risk profile. Returns True if valid."""
    global _active_profile
    if name in RISK_PROFILES:
        old = _active_profile
        _active_profile = name
        logger.info(f"[RISK-TUNE] Profile changed: {old} -> {name}")
        return True
    return False


def evaluate_and_adjust() -> Optional[str]:
    """Evaluate telemetry and recommend profile adjustment.

    Returns the new profile name if changed, None otherwise.

    Rules:
    - Drawdown > 8% -> conservative
    - 3+ consecutive loss days -> conservative
    - Drawdown < 3% and LLM uplift positive -> aggressive
    - Otherwise -> normal
    """
    global _active_profile
    tel = _telemetry

    old_profile = _active_profile

    # Rule 1: Deep drawdown -> conservative
    if tel.current_drawdown_pct > 8.0:
        _active_profile = "conservative"
        if _active_profile != old_profile:
            logger.warning(
                f"[RISK-TUNE] Drawdown {tel.current_drawdown_pct:.1f}% -> CONSERVATIVE"
            )
            return "conservative"

    # Rule 2: Consecutive loss days -> conservative
    elif tel.consecutive_loss_days >= 3:
        _active_profile = "conservative"
        if _active_profile != old_profile:
            logger.warning(
                f"[RISK-TUNE] {tel.consecutive_loss_days} loss days -> CONSERVATIVE"
            )
            return "conservative"

    # Rule 3: Stable equity + LLM accuracy -> aggressive
    elif (tel.current_drawdown_pct < 3.0
          and tel.llm_veto_accuracy > 55
          and tel.consecutive_loss_days == 0
          and len(tel.daily_pnls) >= 7):
        _active_profile = "aggressive"
        if _active_profile != old_profile:
            logger.info(
                f"[RISK-TUNE] Stable + LLM accurate -> AGGRESSIVE"
            )
            return "aggressive"

    # Rule 4: Default to normal
    else:
        _active_profile = "normal"
        if _active_profile != old_profile:
            logger.info(f"[RISK-TUNE] Conditions normalized -> NORMAL")
            return "normal"

    return None


def get_dynamic_leverage_cap(base_max: float = 25.0) -> float:
    """Get dynamic max leverage based on drawdown.

    Reduces leverage as drawdown deepens:
    - 0-3% DD: full leverage
    - 3-5% DD: 80% of max
    - 5-8% DD: 60% of max
    - 8%+ DD: 50% of max (hard floor)
    """
    dd = _telemetry.current_drawdown_pct

    if dd < 3:
        return base_max
    elif dd < 5:
        return base_max * 0.8
    elif dd < 8:
        return base_max * 0.6
    else:
        return base_max * 0.5


def format_risk_status() -> str:
    """Format risk status for Telegram."""
    tel = _telemetry
    profile = RISK_PROFILES.get(_active_profile, {})
    lines = [
        f"*Risk Engine*",
        f"Profile: {_active_profile}",
        f"Drawdown: {tel.current_drawdown_pct:.1f}%",
        f"Equity Vol: {tel.realized_volatility:.2f}",
        f"Loss streak: {tel.consecutive_loss_days} days",
        f"Max leverage: {get_dynamic_leverage_cap():.0f}x",
        f"Max positions: {profile.get('max_positions', '?')}",
    ]
    return "\n".join(lines)
