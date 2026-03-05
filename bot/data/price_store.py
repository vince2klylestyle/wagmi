"""
Price Store: In-memory cache of latest prices with staleness detection.

Feeds the dual-entry system: snapshot_entry is recorded when a signal fires,
live_entry is fetched from this store at execution time.
"""

import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger("bot.data.price_store")


@dataclass
class PriceSnapshot:
    """A single price observation."""
    symbol: str
    price: float
    ts: float
    source: str  # "coinbase", "hyperliquid", "coingecko"


class PriceStore:
    """Thread-safe price cache with configurable staleness."""

    def __init__(self, max_age_sec: float = 5.0):
        self._prices: Dict[str, PriceSnapshot] = {}
        self._max_age_sec = max_age_sec

    def update(self, symbol: str, price: float, source: str = "unknown") -> None:
        """Update the price for a symbol."""
        if price <= 0:
            return
        self._prices[symbol.upper()] = PriceSnapshot(
            symbol=symbol.upper(),
            price=float(price),
            ts=time.time(),
            source=source,
        )

    def get(self, symbol: str) -> Optional[PriceSnapshot]:
        """Get the latest price if not stale. Returns None if stale/missing."""
        snap = self._prices.get(symbol.upper())
        if not snap:
            return None
        if time.time() - snap.ts > self._max_age_sec:
            return None
        return snap

    def get_price(self, symbol: str) -> Optional[float]:
        """Convenience: get just the price value."""
        snap = self.get(symbol)
        return snap.price if snap else None

    def get_age(self, symbol: str) -> Optional[float]:
        """Get age of the cached price in seconds."""
        snap = self._prices.get(symbol.upper())
        if not snap:
            return None
        return time.time() - snap.ts

    def is_stale(self, symbol: str) -> bool:
        """Check if a symbol's price is stale or missing."""
        return self.get(symbol) is None

    def all_prices(self) -> Dict[str, float]:
        """Get all non-stale prices."""
        now = time.time()
        return {
            sym: snap.price
            for sym, snap in self._prices.items()
            if now - snap.ts <= self._max_age_sec
        }

    def stats(self) -> Dict[str, int]:
        """Return cache stats."""
        now = time.time()
        total = len(self._prices)
        fresh = sum(1 for s in self._prices.values() if now - s.ts <= self._max_age_sec)
        return {"total": total, "fresh": fresh, "stale": total - fresh}
