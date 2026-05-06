"""
Cached signal loader — serves pre-computed signals from disk.
Enables API-free trading: no live exchange calls needed.

Usage:
    signals = CachedSignalLoader().load_signals(symbol='BTC', limit=10)
    for sig in signals:
        print(f"{sig['symbol']} {sig['side']} @ {sig['entry']}")
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("bot.cli.cached_signals")


class CachedSignalLoader:
    """Load pre-computed signals from disk (no API calls)."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.sources = {
            "complete": self.data_dir / "all_signals_complete_60d.json",
            "extracted": self.data_dir / "extracted_signals.json",
            "backtest": self.data_dir / "backtest_signals_60d.json",
        }
        self._cache = {}

    def load_signals(
        self,
        symbol: Optional[str] = None,
        limit: int = 50,
        source: str = "extracted",
        confidence_min: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Load cached signals, optionally filtered by symbol/confidence.

        Args:
            symbol: Filter by symbol (e.g., 'BTC'), None for all
            limit: Max number of signals to return
            source: 'extracted', 'complete', or 'backtest'
            confidence_min: Only return signals >= this confidence (0-100)

        Returns:
            List of signal dicts, most recent first
        """
        signals = self._load_source(source)
        if not signals:
            logger.warning(f"No signals loaded from {source}")
            return []

        # Filter by symbol
        if symbol:
            signals = [s for s in signals if s.get("symbol") == symbol]

        # Filter by confidence
        if confidence_min > 0:
            signals = [
                s
                for s in signals
                if self._get_confidence(s) >= confidence_min
            ]

        # Return most recent first (limit)
        return signals[:limit]

    def _load_source(self, source: str) -> List[Dict[str, Any]]:
        """Load signals from chosen source (with caching)."""
        if source in self._cache:
            return self._cache[source]

        path = self.sources.get(source)
        if not path or not path.exists():
            logger.error(f"Signal file not found: {path}")
            return []

        try:
            with open(path) as f:
                data = json.load(f)

            # Handle multiple formats
            if isinstance(data, dict):
                # Try common signal list keys
                for key in ["executed_signals", "signals", "data", "records"]:
                    if key in data and isinstance(data[key], list):
                        signals = data[key]
                        break
                else:
                    # Fallback: convert all dict values to list (skip metadata dicts)
                    signals = [v for v in data.values() if isinstance(v, dict) and "symbol" in v]
            else:
                signals = data if isinstance(data, list) else []

            logger.info(f"Loaded {len(signals)} signals from {source}")
            self._cache[source] = signals
            return signals

        except Exception as e:
            logger.error(f"Failed to load signals from {path}: {e}")
            return []

    def _get_confidence(self, sig: Dict[str, Any]) -> float:
        """Extract confidence from signal (handles multiple formats)."""
        conf = sig.get("confidence", 0)
        if isinstance(conf, (int, float)):
            return float(conf)
        return 0.0

    def get_statistics(self, source: str = "extracted") -> Dict[str, Any]:
        """Get summary statistics about cached signals."""
        signals = self._load_source(source)
        if not signals:
            return {}

        symbols = set(s.get("symbol") for s in signals)
        sides = {}
        for s in signals:
            side = s.get("side", "?")
            sides[side] = sides.get(side, 0) + 1

        confidences = [self._get_confidence(s) for s in signals]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0

        return {
            "total_signals": len(signals),
            "unique_symbols": len(symbols),
            "symbols": sorted(list(symbols)),
            "sides": sides,
            "avg_confidence": round(avg_conf, 1),
            "min_confidence": min(confidences) if confidences else 0,
            "max_confidence": max(confidences) if confidences else 0,
        }

    def find_signal(self, signal_id: int, source: str = "extracted") -> Optional[Dict[str, Any]]:
        """Find a specific signal by index."""
        signals = self._load_source(source)
        if 0 <= signal_id < len(signals):
            return signals[signal_id]
        return None


def run_cached_signals_cli(
    symbol: Optional[str] = None,
    limit: int = 50,
    source: str = "extracted",
    stats: bool = False,
):
    """Main entry point for cached signals CLI."""
    loader = CachedSignalLoader()

    if stats:
        # Show statistics
        print("=" * 70)
        print(f"CACHED SIGNAL STATISTICS ({source})")
        print("=" * 70)
        print()
        stats_data = loader.get_statistics(source)
        for key, value in stats_data.items():
            print(f"  {key:20s}: {value}")
        print()
        return

    # Show signals
    signals = loader.load_signals(symbol, limit, source)

    if not signals:
        print(f"No cached signals ({source})")
        return

    print("=" * 70)
    print(f"CACHED SIGNALS ({source}) — {len(signals)} recent")
    if symbol:
        print(f"Filter: {symbol} only")
    print("=" * 70)
    print()

    for i, sig in enumerate(signals):
        symbol_val = sig.get("symbol", "?")
        side = sig.get("side", "?")
        conf = loader._get_confidence(sig)
        entry = sig.get("entry", sig.get("entry_price", "?"))
        sl = sig.get("sl", "?")
        tp1 = sig.get("tp1", "?")
        tp2 = sig.get("tp2", "?")
        strategy = sig.get("strategy", "?")

        print(f"[{i}] {symbol_val:6s} {side:6s} @ {entry:>10} | Conf: {conf:>3.0f}%")
        print(f"    Strategy: {strategy}")
        print(f"    SL: {sl}  TP1: {tp1}  TP2: {tp2}")
        print()

    print("=" * 70)
    print(f"To execute: python cli.py trade execute --signal-id <index> --source {source}")
    print()
