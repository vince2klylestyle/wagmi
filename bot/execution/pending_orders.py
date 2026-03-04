"""
Pending (limit) order manager for paper trading.

Instead of rejecting signals when live price diverges from entry,
place a pending order at the strategy-computed entry price. If price
returns to the entry within the expiry window, the order fills.

This eliminates the PRE-LLM REJECT problem: strategies compute a good
entry level, the LLM validates the thesis, and we wait for price to
come to us rather than chasing or abandoning the setup.

Flow:
1. Strategy computes entry at $0.1568 from candle data
2. Live price is $0.1662 (too far for market order)
3. LLM validates the trade thesis → approved
4. PendingOrderManager.place() stores limit order at $0.1568
5. Every tick: check_fills(current_prices) → fills if price crosses entry
6. Expiry: order cancelled after max_age (default 15 min for scalps, 60 min for trends)

Order lifecycle: PENDING → FILLED / EXPIRED / CANCELLED
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, List, Callable, Any

logger = logging.getLogger("bot.execution.pending_orders")


@dataclass
class PendingOrder:
    """A limit order waiting for fill."""
    order_id: str
    symbol: str
    side: str               # "LONG" or "SHORT"
    entry_price: float      # limit price (where we want to enter)
    qty: float
    sl: float
    tp1: float
    tp2: float
    atr: float
    leverage: float
    strategy: str
    confidence: float
    trade_profile: Any      # TradeProfile object
    entry_reasons: Dict[str, Any] = field(default_factory=dict)

    # Expiry
    created_at: float = field(default_factory=time.time)
    max_age_s: float = 900.0  # 15 minutes default
    status: str = "PENDING"   # PENDING, FILLED, EXPIRED, CANCELLED

    # Thesis validation
    thesis: str = ""          # LLM reasoning for this trade
    regime_at_creation: str = ""

    # Fill tracking
    filled_at: Optional[float] = None
    fill_price: Optional[float] = None
    cancel_reason: str = ""

    @property
    def age_s(self) -> float:
        return time.time() - self.created_at

    @property
    def is_expired(self) -> bool:
        return self.age_s > self.max_age_s

    @property
    def time_remaining_s(self) -> float:
        return max(0, self.max_age_s - self.age_s)


# Expiry defaults by trade profile entry_type
EXPIRY_BY_PROFILE = {
    "SCALP": 600,     # 10 min — scalps need fast fills
    "MEDIUM": 900,    # 15 min
    "TREND": 1800,    # 30 min — trend entries can wait longer
    "REGIME": 1800,   # 30 min
}


class PendingOrderManager:
    """Manages pending limit orders for paper trading.

    Tracks orders, checks for fills each tick, expires stale orders,
    and prevents duplicate orders for the same symbol.
    """

    def __init__(self, max_pending: int = 5):
        self._orders: Dict[str, PendingOrder] = {}  # order_id -> PendingOrder
        self._max_pending = max_pending
        self._fill_count = 0
        self._expire_count = 0
        self._cancel_count = 0

    def place(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        qty: float,
        sl: float,
        tp1: float,
        tp2: float,
        atr: float,
        leverage: float,
        strategy: str,
        confidence: float,
        trade_profile: Any,
        entry_reasons: Optional[Dict] = None,
        thesis: str = "",
        regime: str = "",
    ) -> Optional[str]:
        """Place a pending limit order.

        Returns order_id if placed, None if rejected (duplicate/max reached).
        """
        # Don't allow duplicate pending orders for same symbol
        for oid, order in self._orders.items():
            if order.symbol == symbol and order.status == "PENDING":
                logger.info(
                    f"[PENDING] {symbol} already has pending order {oid}, "
                    f"skipping duplicate"
                )
                return None

        # Enforce max pending orders
        active = sum(1 for o in self._orders.values() if o.status == "PENDING")
        if active >= self._max_pending:
            logger.info(
                f"[PENDING] Max pending orders reached ({self._max_pending}), "
                f"rejecting {symbol}"
            )
            return None

        # Determine expiry from trade profile
        entry_type = getattr(trade_profile, "entry_type", "MEDIUM") if trade_profile else "MEDIUM"
        max_age = EXPIRY_BY_PROFILE.get(entry_type, 900)

        order_id = f"po_{symbol}_{int(time.time() * 1000) % 1_000_000}"
        order = PendingOrder(
            order_id=order_id,
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            qty=qty,
            sl=sl,
            tp1=tp1,
            tp2=tp2,
            atr=atr,
            leverage=leverage,
            strategy=strategy,
            confidence=confidence,
            trade_profile=trade_profile,
            entry_reasons=entry_reasons or {},
            max_age_s=max_age,
            thesis=thesis,
            regime_at_creation=regime,
        )

        self._orders[order_id] = order
        logger.info(
            f"[PENDING] Placed {side} {symbol} limit @ {entry_price:.6f} "
            f"qty={qty:.4f} conf={confidence:.0f}% "
            f"expiry={max_age}s ({entry_type})"
        )
        return order_id

    def check_fills(self, current_prices: Dict[str, float]) -> List[PendingOrder]:
        """Check all pending orders against current prices.

        Returns list of orders that just filled.
        For LONG: fills if price <= entry_price (price came down to our bid)
        For SHORT: fills if price >= entry_price (price came up to our ask)
        """
        filled = []

        for oid, order in list(self._orders.items()):
            if order.status != "PENDING":
                continue

            # Check expiry first
            if order.is_expired:
                order.status = "EXPIRED"
                order.cancel_reason = f"expired after {order.max_age_s:.0f}s"
                self._expire_count += 1
                logger.info(
                    f"[PENDING] EXPIRED: {order.side} {order.symbol} "
                    f"@ {order.entry_price:.6f} (age={order.age_s:.0f}s)"
                )
                continue

            price = current_prices.get(order.symbol)
            if price is None:
                continue

            # Check fill condition
            should_fill = False
            if order.side == "LONG" and price <= order.entry_price:
                should_fill = True
            elif order.side == "SHORT" and price >= order.entry_price:
                should_fill = True

            if should_fill:
                order.status = "FILLED"
                order.filled_at = time.time()
                order.fill_price = order.entry_price  # limit order fills at limit price
                self._fill_count += 1
                filled.append(order)
                logger.info(
                    f"[PENDING] FILLED: {order.side} {order.symbol} "
                    f"@ {order.entry_price:.6f} (waited {order.age_s:.0f}s, "
                    f"live={price:.6f})"
                )

        return filled

    def cancel(self, symbol: str, reason: str = "manual") -> bool:
        """Cancel pending order for a symbol."""
        for oid, order in self._orders.items():
            if order.symbol == symbol and order.status == "PENDING":
                order.status = "CANCELLED"
                order.cancel_reason = reason
                self._cancel_count += 1
                logger.info(f"[PENDING] CANCELLED: {order.symbol} — {reason}")
                return True
        return False

    def cancel_all(self, reason: str = "manual"):
        """Cancel all pending orders."""
        for order in self._orders.values():
            if order.status == "PENDING":
                order.status = "CANCELLED"
                order.cancel_reason = reason
                self._cancel_count += 1

    def get_pending(self) -> List[PendingOrder]:
        """Get all currently pending orders."""
        return [o for o in self._orders.values() if o.status == "PENDING"]

    def get_pending_for_symbol(self, symbol: str) -> Optional[PendingOrder]:
        """Get pending order for a specific symbol (if any)."""
        for o in self._orders.values():
            if o.symbol == symbol and o.status == "PENDING":
                return o
        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get pending order statistics."""
        pending = [o for o in self._orders.values() if o.status == "PENDING"]
        return {
            "pending": len(pending),
            "filled": self._fill_count,
            "expired": self._expire_count,
            "cancelled": self._cancel_count,
            "symbols": [o.symbol for o in pending],
        }

    def cleanup_old(self, max_history: int = 100):
        """Remove old completed/expired/cancelled orders from memory."""
        completed = {
            oid: o for oid, o in self._orders.items()
            if o.status in ("FILLED", "EXPIRED", "CANCELLED")
        }
        if len(completed) > max_history:
            # Keep only most recent
            sorted_ids = sorted(completed, key=lambda k: completed[k].created_at)
            for oid in sorted_ids[:-max_history]:
                del self._orders[oid]
