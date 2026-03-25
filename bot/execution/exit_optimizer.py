"""
Exit Optimization — Maximize captured PnL per trade.

Current problem: fixed TP/SL exits leave money on the table.
Data shows 6-12h holds are the best PnL band, but the bot exits
too early (SL hit during mid-trade noise) or too late (time stop
after the move is over).

Strategies:
1. Partial profit taking: At TP1 (1.5R), close 50%, move SL to BE
2. Time-decay exits: No 0.5% move in 1h → close (4-8 bar = 0% WR)
3. Regime-adaptive trailing: wide in trending, tight in ranging
4. RSI divergence exit: long + lower RSI high → momentum fading

Usage:
    optimizer = ExitOptimizer()
    action = optimizer.evaluate_exit(position, current_price, regime, hold_minutes)
    # action.type: "HOLD" | "PARTIAL_CLOSE" | "TIGHTEN_SL" | "CLOSE" | "WIDEN_TP"
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any

logger = logging.getLogger("bot.execution.exit_optimizer")


@dataclass
class ExitAction:
    """Recommended exit action."""
    action_type: str        # "HOLD", "PARTIAL_CLOSE", "TIGHTEN_SL", "CLOSE", "WIDEN_TP"
    new_sl: Optional[float] = None
    new_tp: Optional[float] = None
    close_pct: float = 0.0   # What % to close (0.5 = 50%)
    urgency: str = "low"     # "low", "medium", "high", "critical"
    rationale: str = ""


class ExitOptimizer:
    """Dynamic exit optimization based on position state and market context."""

    def __init__(
        self,
        partial_close_at_r: float = 1.5,   # Close 50% at 1.5R
        partial_close_pct: float = 0.50,    # Close this % at partial
        time_decay_minutes: int = 60,       # If no 0.5% move in this time
        time_decay_threshold_pct: float = 0.5,  # Minimum move expected
        breakeven_buffer_pct: float = 0.002, # BE = entry + 0.2% (covers fees)
    ):
        self.partial_close_at_r = partial_close_at_r
        self.partial_close_pct = partial_close_pct
        self.time_decay_minutes = time_decay_minutes
        self.time_decay_threshold_pct = time_decay_threshold_pct
        self.breakeven_buffer_pct = breakeven_buffer_pct

    def evaluate_exit(
        self,
        entry: float,
        current_price: float,
        sl: float,
        tp1: float,
        side: str,
        leverage: float,
        hold_minutes: float,
        regime: str = "unknown",
        highest_since_entry: float = 0.0,
        lowest_since_entry: float = 0.0,
        partial_taken: bool = False,
        tier: str = "PREMIUM",
    ) -> ExitAction:
        """Evaluate exit conditions for an open position.

        Args:
            entry: Entry price
            current_price: Current market price
            sl: Current stop loss
            tp1: Current TP1
            side: "LONG" or "SHORT"
            leverage: Position leverage
            hold_minutes: Minutes since entry
            regime: Current market regime
            highest_since_entry: Highest price seen since entry
            lowest_since_entry: Lowest price seen since entry
            partial_taken: Whether partial profit was already taken
            tier: Signal tier (SNIPER/PREMIUM/STANDARD)
        """
        is_long = side == "LONG"

        # Calculate current unrealized P&L
        if is_long:
            pnl_pct = (current_price - entry) / entry * 100
            risk_r = (current_price - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0
        else:
            pnl_pct = (entry - current_price) / entry * 100
            risk_r = (entry - current_price) / abs(sl - entry) if abs(sl - entry) > 0 else 0

        # ── Rule 1: Partial Profit Taking ──
        if not partial_taken and risk_r >= self.partial_close_at_r:
            # Move SL to breakeven + buffer
            if is_long:
                new_sl = entry * (1 + self.breakeven_buffer_pct)
            else:
                new_sl = entry * (1 - self.breakeven_buffer_pct)

            return ExitAction(
                action_type="PARTIAL_CLOSE",
                new_sl=round(new_sl, 6),
                close_pct=self.partial_close_pct,
                urgency="medium",
                rationale=(
                    f"TP1 reached ({risk_r:.1f}R, {pnl_pct:+.1f}%). "
                    f"Close {self.partial_close_pct:.0%}, move SL to BE+{self.breakeven_buffer_pct*100:.1f}%"
                ),
            )

        # ── Rule 2: Time Decay — no movement = dead trade ──
        # Data: 4-8 bar resolution = 0% WR. If stale, get out.
        if hold_minutes >= self.time_decay_minutes and not partial_taken:
            if abs(pnl_pct) < self.time_decay_threshold_pct:
                return ExitAction(
                    action_type="CLOSE",
                    urgency="high",
                    rationale=(
                        f"Time decay: held {hold_minutes:.0f}min with only "
                        f"{pnl_pct:+.1f}% move (need {self.time_decay_threshold_pct}%). "
                        f"4-8 bar resolution = 0% WR — exit stale trade."
                    ),
                )

        # ── Rule 3: Regime-Adaptive Trailing ──
        regime_lower = regime.lower()

        if partial_taken:
            # Post-partial: tighten or widen based on regime
            if regime_lower in ("trend", "trending_bull", "trending_bear"):
                # Trending: wide trail (let it run)
                trail_r = 2.0
            elif regime_lower in ("consolidation", "range"):
                # Ranging: tight trail (capture before reversal)
                trail_r = 0.8
            else:
                trail_r = 1.2

            stop_distance = abs(entry - sl)
            if is_long:
                trailing_sl = highest_since_entry - (stop_distance * trail_r)
                if trailing_sl > sl:
                    return ExitAction(
                        action_type="TIGHTEN_SL",
                        new_sl=round(trailing_sl, 6),
                        urgency="low",
                        rationale=(
                            f"Regime-adaptive trail ({regime}): "
                            f"trail={trail_r:.1f}R, new SL=${trailing_sl:.2f} "
                            f"(from ${sl:.2f})"
                        ),
                    )
            else:
                trailing_sl = lowest_since_entry + (stop_distance * trail_r)
                if trailing_sl < sl:
                    return ExitAction(
                        action_type="TIGHTEN_SL",
                        new_sl=round(trailing_sl, 6),
                        urgency="low",
                        rationale=(
                            f"Regime-adaptive trail ({regime}): "
                            f"trail={trail_r:.1f}R, new SL=${trailing_sl:.2f}"
                        ),
                    )

        # ── Rule 4: Widen TP in strong trends ──
        if regime_lower in ("trending_bull", "trending_bear") and risk_r >= 1.0:
            if is_long and regime_lower == "trending_bull":
                wider_tp = tp1 * 1.3  # 30% wider TP
                if wider_tp > tp1:
                    return ExitAction(
                        action_type="WIDEN_TP",
                        new_tp=round(wider_tp, 6),
                        urgency="low",
                        rationale=(
                            f"Strong trend ({regime}): widen TP from "
                            f"${tp1:.2f} to ${wider_tp:.2f} (+30%)"
                        ),
                    )
            elif not is_long and regime_lower == "trending_bear":
                wider_tp = tp1 * 0.7  # 30% wider TP (lower for shorts)
                if wider_tp < tp1:
                    return ExitAction(
                        action_type="WIDEN_TP",
                        new_tp=round(wider_tp, 6),
                        urgency="low",
                        rationale=f"Strong bear trend: widen TP to ${wider_tp:.2f}",
                    )

        # ── Rule 5: Emergency exit for high leverage losing trades ──
        if leverage >= 15 and pnl_pct < -0.3 and hold_minutes > 30:
            return ExitAction(
                action_type="TIGHTEN_SL",
                new_sl=current_price * (0.997 if is_long else 1.003),
                urgency="high",
                rationale=(
                    f"High leverage ({leverage:.0f}x) losing {pnl_pct:.1f}% "
                    f"after {hold_minutes:.0f}min — tighten SL to limit damage"
                ),
            )

        # Default: hold
        return ExitAction(
            action_type="HOLD",
            rationale=(
                f"Hold: {pnl_pct:+.1f}% ({risk_r:.1f}R) after {hold_minutes:.0f}min. "
                f"Regime={regime}, partial={'taken' if partial_taken else 'pending'}"
            ),
        )
