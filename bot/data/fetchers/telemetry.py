"""
Telemetry: System-wide counters and metrics.

Tracks execution quality, safety violations, and performance metrics.
Exposed via /telemetry Telegram command.
"""

import logging
import time
import threading
from typing import Dict, Any, List

logger = logging.getLogger("bot.data.fetchers.telemetry")


class Telemetry:
    """Thread-safe telemetry counters and rolling averages."""

    _lock = threading.Lock()

    counters: Dict[str, int] = {
        "total_signals": 0,
        "total_trades": 0,
        "stale_signals": 0,
        "slippage_violations": 0,
        "spread_violations": 0,
        "liquidity_violations": 0,
        "human_copy_trades": 0,
        "human_copy_rejections": 0,
        "execution_anomalies": 0,
        "circuit_breaker_triggers": 0,
        "correlation_guard_blocks": 0,
        "llm_vetoes": 0,
        "llm_errors": 0,
        "price_guard_vetoes": 0,
        "price_guard_downgrades": 0,
    }

    # Rolling values for averages
    _rolling: Dict[str, List[float]] = {
        "snapshot_ages": [],
        "slippages": [],
        "spreads": [],
        "liquidities": [],
        "live_vs_snapshot_diffs": [],
    }
    _rolling_max = 200  # Keep last N values

    @classmethod
    def inc(cls, key: str, amount: int = 1) -> None:
        """Increment a counter."""
        with cls._lock:
            if key in cls.counters:
                cls.counters[key] += amount
            else:
                cls.counters[key] = amount

    @classmethod
    def record(cls, key: str, value: float) -> None:
        """Record a rolling metric value."""
        with cls._lock:
            if key not in cls._rolling:
                cls._rolling[key] = []
            cls._rolling[key].append(value)
            if len(cls._rolling[key]) > cls._rolling_max:
                cls._rolling[key] = cls._rolling[key][-cls._rolling_max:]

    @classmethod
    def snapshot(cls) -> Dict[str, Any]:
        """Get a full telemetry snapshot."""
        with cls._lock:
            result = dict(cls.counters)

            # Compute averages for rolling metrics
            for key, values in cls._rolling.items():
                if values:
                    avg_key = f"avg_{key.rstrip('s')}" if key.endswith("s") else f"avg_{key}"
                    result[avg_key] = round(sum(values) / len(values), 4)
                    result[f"max_{key.rstrip('s')}"] = round(max(values), 4)
                    result[f"count_{key}"] = len(values)

            return result

    @classmethod
    def reset(cls) -> None:
        """Reset all counters (for testing)."""
        with cls._lock:
            for key in cls.counters:
                cls.counters[key] = 0
            for key in cls._rolling:
                cls._rolling[key] = []

    @classmethod
    def format_telegram(cls) -> str:
        """Format telemetry for Telegram display."""
        snap = cls.snapshot()
        lines = ["TELEMETRY:"]

        # Execution quality
        lines.append("\nExecution Quality:")
        lines.append(f"  Signals: {snap.get('total_signals', 0)}")
        lines.append(f"  Trades: {snap.get('total_trades', 0)}")
        lines.append(f"  Stale signals: {snap.get('stale_signals', 0)}")
        lines.append(f"  Slippage violations: {snap.get('slippage_violations', 0)}")
        lines.append(f"  Spread violations: {snap.get('spread_violations', 0)}")
        lines.append(f"  Liquidity violations: {snap.get('liquidity_violations', 0)}")

        # Averages
        if "avg_snapshot_age" in snap:
            lines.append(f"\nAverages:")
            lines.append(f"  Avg snapshot age: {snap.get('avg_snapshot_age', 0):.2f}s")
            lines.append(f"  Avg slippage: {snap.get('avg_slippage', 0):.4f}%")
            lines.append(f"  Avg spread: {snap.get('avg_spread', 0):.4f}%")

        # Safety
        lines.append(f"\nSafety:")
        lines.append(f"  CB triggers: {snap.get('circuit_breaker_triggers', 0)}")
        lines.append(f"  Correlation blocks: {snap.get('correlation_guard_blocks', 0)}")
        lines.append(f"  LLM vetoes: {snap.get('llm_vetoes', 0)}")
        lines.append(f"  Guard vetoes: {snap.get('price_guard_vetoes', 0)}")
        lines.append(f"  Guard downgrades: {snap.get('price_guard_downgrades', 0)}")

        # Human copy
        lines.append(f"\nHuman Copy-Trade:")
        lines.append(f"  Eligible: {snap.get('human_copy_trades', 0)}")
        lines.append(f"  Rejected: {snap.get('human_copy_rejections', 0)}")

        return "\n".join(lines)
