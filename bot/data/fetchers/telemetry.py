"""
Telemetry: System-wide counters, rolling averages, and health status.

Tracks execution quality, safety violations, and performance metrics.
Exposed via /telemetry Telegram command with OK/WARN/CRITICAL thresholds.
"""

import json
import logging
import os
import time
import threading
from typing import Dict, Any, List, Tuple

logger = logging.getLogger("bot.data.fetchers.telemetry")

# ── Health Thresholds ────────────────────────────────────────
# Format: (warn_threshold, critical_threshold)
# For "lower is better" metrics (snapshot_age, slippage, etc.)
_THRESHOLDS_UPPER: Dict[str, Tuple[float, float]] = {
    "avg_snapshot_age": (8.0, 15.0),       # seconds
    "avg_slippage": (0.3, 0.8),            # percent
    "avg_spread": (0.2, 0.5),              # percent
    "max_snapshot_age": (15.0, 30.0),       # seconds
    "max_slippage": (0.5, 1.5),            # percent
    "stale_signals": (5, 20),               # count
    "execution_anomalies": (3, 10),         # count
    "circuit_breaker_triggers": (2, 5),     # count
    "llm_errors": (5, 15),                  # count
}

# For "higher is better" metrics (liquidity)
_THRESHOLDS_LOWER: Dict[str, Tuple[float, float]] = {
    "avg_liquidity": (75_000.0, 30_000.0),  # USD (warn below 75k, critical below 30k)
}

_SNAPSHOT_DIR = os.path.join("data", "telemetry")


def _status(value: float, warn: float, critical: float, higher_is_better: bool = False) -> str:
    """Determine OK/WARN/CRITICAL status."""
    if higher_is_better:
        if value < critical:
            return "CRITICAL"
        if value < warn:
            return "WARN"
        return "OK"
    else:
        if value >= critical:
            return "CRITICAL"
        if value >= warn:
            return "WARN"
        return "OK"


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
        "trades_won": 0,
        "trades_lost": 0,
        "throttle_blocks": 0,
    }

    # Rolling values for averages
    _rolling: Dict[str, List[float]] = {
        "snapshot_ages": [],
        "slippages": [],
        "spreads": [],
        "liquidities": [],
        "live_vs_snapshot_diffs": [],
        "pnls": [],
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

            # Win rate
            total = result.get("trades_won", 0) + result.get("trades_lost", 0)
            result["win_rate"] = round(result.get("trades_won", 0) / total, 4) if total > 0 else 0.0

            result["timestamp"] = time.time()
            return result

    @classmethod
    def health_check(cls) -> Dict[str, str]:
        """Run health check against thresholds. Returns metric -> status."""
        snap = cls.snapshot()
        health = {}

        for metric, (warn, crit) in _THRESHOLDS_UPPER.items():
            val = snap.get(metric, 0)
            health[metric] = _status(val, warn, crit)

        for metric, (warn, crit) in _THRESHOLDS_LOWER.items():
            val = snap.get(metric, float("inf"))
            health[metric] = _status(val, warn, crit, higher_is_better=True)

        return health

    @classmethod
    def save_snapshot(cls) -> str:
        """Save telemetry snapshot to disk for dashboards."""
        os.makedirs(_SNAPSHOT_DIR, exist_ok=True)
        snap = cls.snapshot()
        snap["health"] = cls.health_check()
        path = os.path.join(_SNAPSHOT_DIR, "latest.json")
        try:
            with open(path, "w") as f:
                json.dump(snap, f, indent=2)
        except Exception as e:
            logger.warning(f"[TELEMETRY] Failed to save snapshot: {e}")
        return path

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
        """Format telemetry for Telegram with OK/WARN/CRITICAL status."""
        snap = cls.snapshot()
        health = cls.health_check()

        def _icon(status: str) -> str:
            return {"OK": "[OK]", "WARN": "[WARN]", "CRITICAL": "[CRIT]"}.get(status, "[?]")

        lines = ["*TELEMETRY*"]

        # Overall status
        statuses = list(health.values())
        if "CRITICAL" in statuses:
            lines.append("Overall: CRITICAL")
        elif "WARN" in statuses:
            lines.append("Overall: WARN")
        else:
            lines.append("Overall: OK")

        # Execution quality
        lines.append("\n*Execution Quality:*")
        lines.append(f"  Signals: {snap.get('total_signals', 0)}")
        lines.append(f"  Trades: {snap.get('total_trades', 0)}")
        wr = snap.get("win_rate", 0)
        lines.append(f"  Win rate: {wr:.0%}")

        stale = snap.get("stale_signals", 0)
        stale_s = health.get("stale_signals", "OK")
        lines.append(f"  Stale signals: {stale} {_icon(stale_s)}")

        anom = snap.get("execution_anomalies", 0)
        anom_s = health.get("execution_anomalies", "OK")
        lines.append(f"  Anomalies: {anom} {_icon(anom_s)}")

        # Averages with status
        if "avg_snapshot_age" in snap:
            lines.append("\n*Averages:*")
            age = snap["avg_snapshot_age"]
            age_s = health.get("avg_snapshot_age", "OK")
            lines.append(f"  Snapshot age: {age:.2f}s {_icon(age_s)}")

            slip = snap.get("avg_slippage", 0)
            slip_s = health.get("avg_slippage", "OK")
            lines.append(f"  Slippage: {slip:.4f}% {_icon(slip_s)}")

            spread = snap.get("avg_spread", 0)
            spread_s = health.get("avg_spread", "OK")
            lines.append(f"  Spread: {spread:.4f}% {_icon(spread_s)}")

        if "avg_liquidity" in snap:
            liq = snap["avg_liquidity"]
            liq_s = health.get("avg_liquidity", "OK")
            lines.append(f"  Liquidity: ${liq:,.0f} {_icon(liq_s)}")

        # Safety
        lines.append("\n*Safety:*")
        cb = snap.get("circuit_breaker_triggers", 0)
        cb_s = health.get("circuit_breaker_triggers", "OK")
        lines.append(f"  CB triggers: {cb} {_icon(cb_s)}")
        lines.append(f"  Correlation blocks: {snap.get('correlation_guard_blocks', 0)}")
        lines.append(f"  LLM vetoes: {snap.get('llm_vetoes', 0)}")

        llm_err = snap.get("llm_errors", 0)
        llm_s = health.get("llm_errors", "OK")
        lines.append(f"  LLM errors: {llm_err} {_icon(llm_s)}")

        lines.append(f"  Guard vetoes: {snap.get('price_guard_vetoes', 0)}")
        lines.append(f"  Guard downgrades: {snap.get('price_guard_downgrades', 0)}")
        lines.append(f"  Throttle blocks: {snap.get('throttle_blocks', 0)}")

        # Human copy
        hct = snap.get("human_copy_trades", 0)
        hcr = snap.get("human_copy_rejections", 0)
        lines.append(f"\n*Human Copy-Trade:*")
        lines.append(f"  Eligible: {hct}")
        lines.append(f"  Rejected: {hcr}")

        return "\n".join(lines)
