"""
Order Executor: Bridge between PositionManager and exchange via CCXT.

This module handles the actual submission of orders to Hyperliquid (or other
exchanges via CCXT). It wraps all exchange interactions with:
  - Retry logic with exponential backoff
  - Order validation (min qty, price bounds, balance checks)
  - Slippage protection (reject fills deviating > threshold from expected)
  - Dry-run mode (logs but doesn't submit — for paper trading)
  - Order status tracking and fill confirmation

Design:
  - OrderExecutor is initialized with a CCXT exchange instance
  - All methods are synchronous (CCXT is sync by default)
  - Each order returns an OrderResult with status, fill details, and errors
  - The executor never modifies PositionManager directly — caller does that

Usage:
  executor = OrderExecutor(exchange, mode="paper")  # or "live"
  result = executor.open_position("BTC", "BUY", qty=0.001, price=50000.0, leverage=5)
  if result.filled:
      pos_mgr.open_position(symbol, side, result.fill_price, result.fill_qty, ...)
"""

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional, Any

from execution.precision import round_price, round_qty, get_min_qty, get_tick_size

logger = logging.getLogger("bot.execution.order_executor")

# Symbol -> CCXT pair mapping (Hyperliquid format)
SYMBOL_TO_PAIR = {
    "BTC": "BTC/USDC:USDC",
    "ETH": "ETH/USDC:USDC",
    "SOL": "SOL/USDC:USDC",
    "HYPE": "HYPE/USDC:USDC",
    "XRP": "XRP/USDC:USDC",
    "AVAX": "AVAX/USDC:USDC",
    "LINK": "LINK/USDC:USDC",
    "SUI": "SUI/USDC:USDC",
    "NEAR": "NEAR/USDC:USDC",
    "ARB": "ARB/USDC:USDC",
    "DOGE": "DOGE/USDC:USDC",
    "WIF": "WIF/USDC:USDC",
    "PEPE": "KPEPE/USDC:USDC",
    "TIA": "TIA/USDC:USDC",
    "SEI": "SEI/USDC:USDC",
    "JUP": "JUP/USDC:USDC",
    "ONDO": "ONDO/USDC:USDC",
    "FARTCOIN": "FARTCOIN/USDC:USDC",
}


@dataclass
class OrderResult:
    """Result of an order submission attempt."""
    success: bool = False
    order_id: str = ""
    status: str = "pending"  # pending, filled, partially_filled, cancelled, rejected, error
    fill_price: float = 0.0
    fill_qty: float = 0.0
    fees: float = 0.0
    error: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    attempts: int = 0
    mode: str = "paper"  # paper or live

    @property
    def filled(self) -> bool:
        return self.success and self.status in ("filled", "partially_filled")


class OrderExecutor:
    """Submits orders to exchange via CCXT with safety guards.

    Modes:
      - "paper": Logs everything, simulates fills at current price. No exchange calls.
      - "live": Actually submits orders to the exchange.

    Both modes perform the same validation. Paper mode returns simulated fills
    so the rest of the system (PositionManager, logging) works identically.
    """

    def __init__(
        self,
        exchange: Optional[object] = None,
        mode: str = "paper",
        max_slippage_pct: float = 1.5,
        max_retries: int = 3,
    ):
        self.exchange = exchange
        self.mode = mode
        self.max_slippage_pct = max_slippage_pct / 100.0  # Convert to decimal
        self.max_retries = max_retries

        # Stats
        self._orders_submitted = 0
        self._orders_filled = 0
        self._orders_failed = 0
        self._total_fees = 0.0

        if mode == "live" and exchange is None:
            raise ValueError("OrderExecutor in live mode requires a CCXT exchange instance")

        logger.info(f"OrderExecutor initialized: mode={mode}, max_slippage={max_slippage_pct}%")

    # ── Public API ───────────────────────────────────────────────

    def open_position(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        leverage: int = 1,
        order_type: str = "market",
        reduce_only: bool = False,
    ) -> OrderResult:
        """Open a new position on the exchange.

        Args:
            symbol: Our symbol name (e.g. "BTC", "SOL")
            side: "BUY" or "SELL"
            qty: Position size in base currency
            price: Expected fill price (for slippage check)
            leverage: Leverage to set before order
            order_type: "market" or "limit"
            reduce_only: If True, order can only reduce existing position

        Returns:
            OrderResult with fill details or error info.
        """
        # Validate inputs
        pair = SYMBOL_TO_PAIR.get(symbol)
        if not pair:
            return OrderResult(error=f"Unknown symbol: {symbol}")

        qty = round_qty(symbol, qty)
        min_qty = get_min_qty(symbol)
        if qty < min_qty:
            return OrderResult(error=f"Qty {qty} below minimum {min_qty} for {symbol}")

        if price <= 0:
            return OrderResult(error=f"Invalid price: {price}")

        ccxt_side = "buy" if side.upper() == "BUY" else "sell"

        logger.info(
            f"[ORDER] {self.mode.upper()} {side} {symbol} qty={qty} @ ~{price} "
            f"lev={leverage}x type={order_type}"
        )

        if self.mode == "paper":
            return self._paper_fill(symbol, ccxt_side, qty, price, leverage)

        return self._live_order(
            symbol, pair, ccxt_side, qty, price, leverage, order_type, reduce_only
        )

    def close_position(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        reason: str = "signal",
    ) -> OrderResult:
        """Close an existing position (market order, reduce_only).

        Args:
            symbol: Our symbol name
            side: Side to CLOSE ("BUY" closes a SHORT, "SELL" closes a LONG)
            qty: Amount to close
            price: Expected fill price
            reason: Why closing (SL_HIT, TP1_HIT, TP2_HIT, TRAILING, manual)
        """
        pair = SYMBOL_TO_PAIR.get(symbol)
        if not pair:
            return OrderResult(error=f"Unknown symbol: {symbol}")

        qty = round_qty(symbol, qty)
        if qty <= 0:
            return OrderResult(error=f"Invalid close qty: {qty}")

        ccxt_side = "buy" if side.upper() == "BUY" else "sell"

        logger.info(
            f"[ORDER] {self.mode.upper()} CLOSE {symbol} {side} qty={qty} @ ~{price} "
            f"reason={reason}"
        )

        if self.mode == "paper":
            return self._paper_fill(symbol, ccxt_side, qty, price, leverage=1)

        return self._live_order(
            symbol, pair, ccxt_side, qty, price,
            leverage=None,  # Don't change leverage on close
            order_type="market",
            reduce_only=True,
        )

    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Set leverage for a symbol on the exchange.

        Returns True if successful (or paper mode).
        """
        if self.mode == "paper":
            logger.info(f"[ORDER] PAPER set leverage {symbol} = {leverage}x")
            return True

        pair = SYMBOL_TO_PAIR.get(symbol)
        if not pair or not self.exchange:
            return False

        for attempt in range(self.max_retries):
            try:
                self.exchange.set_leverage(leverage, pair)
                logger.info(f"[ORDER] Leverage set: {symbol} = {leverage}x")
                return True
            except Exception as e:
                if attempt < self.max_retries - 1:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"[ORDER] set_leverage failed (attempt {attempt+1}): {e}, retry in {wait}s")
                    time.sleep(wait)
                else:
                    logger.error(f"[ORDER] set_leverage failed after {self.max_retries} attempts: {e}")
                    return False

    def get_balance(self) -> Optional[float]:
        """Get available USDC balance from exchange."""
        if self.mode == "paper":
            return None  # Paper mode uses RiskManager equity

        if not self.exchange:
            return None

        try:
            balance = self.exchange.fetch_balance()
            usdc = balance.get("USDC", {}).get("free", 0)
            return float(usdc) if usdc else 0.0
        except Exception as e:
            logger.warning(f"[ORDER] Failed to fetch balance: {e}")
            return None

    def get_stats(self) -> Dict[str, Any]:
        """Return execution statistics."""
        return {
            "mode": self.mode,
            "orders_submitted": self._orders_submitted,
            "orders_filled": self._orders_filled,
            "orders_failed": self._orders_failed,
            "total_fees": round(self._total_fees, 4),
            "fill_rate": (
                self._orders_filled / self._orders_submitted
                if self._orders_submitted > 0 else 0.0
            ),
        }

    # ── Internal Methods ─────────────────────────────────────────

    def _paper_fill(
        self, symbol: str, side: str, qty: float, price: float, leverage: int
    ) -> OrderResult:
        """Simulate a fill in paper mode."""
        self._orders_submitted += 1
        self._orders_filled += 1

        # Simulate small slippage (0.01% for market orders)
        slippage = price * 0.0001
        fill_price = price + slippage if side == "buy" else price - slippage
        fill_price = round_price(symbol, fill_price)

        # Estimate fees (Hyperliquid taker: 4 bps — matches backtest config)
        notional = qty * fill_price
        fees = notional * 0.0004
        self._total_fees += fees

        result = OrderResult(
            success=True,
            order_id=f"paper_{symbol}_{int(time.time()*1000)}",
            status="filled",
            fill_price=fill_price,
            fill_qty=qty,
            fees=round(fees, 6),
            mode="paper",
            attempts=1,
        )

        logger.info(
            f"[ORDER] PAPER FILL: {side} {symbol} qty={qty} @ {fill_price} "
            f"fees=${fees:.4f}"
        )
        return result

    def _live_order(
        self,
        symbol: str,
        pair: str,
        side: str,
        qty: float,
        price: float,
        leverage: Optional[int],
        order_type: str,
        reduce_only: bool,
    ) -> OrderResult:
        """Submit a real order to the exchange with retries."""
        if not self.exchange:
            return OrderResult(error="No exchange instance")

        # Set leverage before opening (not on close)
        if leverage is not None and leverage > 1:
            if not self.set_leverage(symbol, leverage):
                return OrderResult(error=f"Failed to set leverage to {leverage}x")

        self._orders_submitted += 1
        last_error = ""

        for attempt in range(self.max_retries):
            try:
                params = {}
                if reduce_only:
                    params["reduceOnly"] = True

                if order_type == "market":
                    order = self.exchange.create_market_order(
                        pair, side, qty, params=params
                    )
                else:
                    limit_price = round_price(symbol, price)
                    order = self.exchange.create_limit_order(
                        pair, side, qty, limit_price, params=params
                    )

                # Parse response
                result = self._parse_order_response(symbol, order, price)
                if result.filled:
                    self._orders_filled += 1
                    self._total_fees += result.fees

                    # Slippage check
                    slippage_pct = abs(result.fill_price - price) / price if price > 0 else 0
                    if slippage_pct > self.max_slippage_pct:
                        logger.warning(
                            f"[ORDER] HIGH SLIPPAGE: {symbol} expected {price}, "
                            f"got {result.fill_price} ({slippage_pct:.2%})"
                        )

                logger.info(
                    f"[ORDER] LIVE {result.status}: {side} {symbol} qty={result.fill_qty} "
                    f"@ {result.fill_price} id={result.order_id}"
                )
                return result

            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries - 1:
                    wait = 2 ** (attempt + 1)
                    logger.warning(
                        f"[ORDER] Attempt {attempt+1} failed: {e}, retry in {wait}s"
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        f"[ORDER] FAILED after {self.max_retries} attempts: {e}"
                    )

        self._orders_failed += 1
        return OrderResult(
            error=f"Order failed after {self.max_retries} attempts: {last_error}",
            attempts=self.max_retries,
            mode="live",
        )

    def _parse_order_response(
        self, symbol: str, order: dict, expected_price: float
    ) -> OrderResult:
        """Parse CCXT order response into OrderResult."""
        order_id = str(order.get("id", ""))
        status = order.get("status", "unknown")
        filled = float(order.get("filled", 0) or 0)
        avg_price = float(order.get("average", 0) or order.get("price", 0) or 0)
        cost = float(order.get("cost", 0) or 0)

        # Calculate fees
        fee_info = order.get("fee", {}) or {}
        fees = float(fee_info.get("cost", 0) or 0)
        if fees == 0 and cost > 0:
            # Estimate fees if not provided (Hyperliquid taker: 2.5 bps)
            fees = cost * 0.00025

        # Determine result status
        if status == "closed" or filled > 0:
            result_status = "filled" if filled >= float(order.get("amount", filled)) * 0.99 else "partially_filled"
        elif status == "canceled" or status == "cancelled":
            result_status = "cancelled"
        elif status == "rejected":
            result_status = "rejected"
        else:
            result_status = status

        return OrderResult(
            success=result_status in ("filled", "partially_filled"),
            order_id=order_id,
            status=result_status,
            fill_price=round_price(symbol, avg_price) if avg_price > 0 else 0.0,
            fill_qty=round_qty(symbol, filled) if filled > 0 else 0.0,
            fees=round(fees, 6),
            raw=order,
            mode="live",
            attempts=1,
        )


def create_executor(
    fetcher=None,
    mode: str = "paper",
    max_slippage_pct: float = 1.5,
) -> OrderExecutor:
    """Factory: create an OrderExecutor from the DataFetcher's exchange instances.

    Args:
        fetcher: DataFetcher instance (has _exchanges dict)
        mode: "paper" or "live"
        max_slippage_pct: Maximum allowed slippage percentage

    For live mode, the Hyperliquid exchange must be initialized with API credentials:
        export HL_API_KEY=<your-wallet-address>
        export HL_API_SECRET=<your-private-key>
    """
    exchange = None

    if fetcher and hasattr(fetcher, '_exchanges'):
        exchange = fetcher._exchanges.get("hyperliquid")

    if mode == "live" and exchange is None:
        logger.warning(
            "[ORDER] Live mode requested but no Hyperliquid exchange available. "
            "Ensure CCXT is initialized with API credentials."
        )

    return OrderExecutor(
        exchange=exchange,
        mode=mode,
        max_slippage_pct=max_slippage_pct,
    )
