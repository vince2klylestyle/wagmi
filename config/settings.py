"""
Centralized safety and execution settings.

All thresholds are config-driven - never hardcoded in logic modules.
These supplement trading_config.py with execution/safety-specific flags.
"""

import os


def _env(key: str, default: str) -> str:
    return os.getenv(key, default)


def _env_float(key: str, default: float) -> float:
    return float(os.getenv(key, str(default)))


def _env_int(key: str, default: int) -> int:
    return int(os.getenv(key, str(default)))


def _env_bool(key: str, default: bool) -> bool:
    return os.getenv(key, str(default)).lower() in ("1", "true", "yes")


def _env_list(key: str, default: str) -> list:
    raw = os.getenv(key, default)
    return [x.strip() for x in raw.split(",") if x.strip()]


class Settings:
    """Execution and safety configuration."""

    # ── Dual Entry System ───────────────────────────────────
    USE_LIVE_ENTRY_AT_EXECUTION: bool = _env_bool("USE_LIVE_ENTRY_AT_EXECUTION", True)
    MAX_SNAPSHOT_AGE_SECONDS: int = _env_int("MAX_SNAPSHOT_AGE_SECONDS", 10)

    # ── Execution Sanity Checks ─────────────────────────────
    MAX_SLIPPAGE_PCT: float = _env_float("MAX_SLIPPAGE_PCT", 0.5)
    MAX_SPREAD_PCT: float = _env_float("MAX_SPREAD_PCT", 0.3)
    MIN_LIQUIDITY_USD: float = _env_float("MIN_LIQUIDITY_USD", 50000.0)
    MAX_PRICE_DEVIATION_PCT: float = _env_float("MAX_PRICE_DEVIATION_PCT", 1.0)
    MAX_VOLATILITY_SPIKE_MULT: float = _env_float("MAX_VOLATILITY_SPIKE_MULT", 3.0)

    # ── Human Copy-Trade ────────────────────────────────────
    ENABLE_HUMAN_COPY_TRADES: bool = _env_bool("ENABLE_HUMAN_COPY_TRADES", True)
    HUMAN_COPY_CONFIDENCE_THRESHOLD: float = _env_float("HUMAN_COPY_CONFIDENCE_THRESHOLD", 85.0)
    HUMAN_COPY_MIN_RR: float = _env_float("HUMAN_COPY_MIN_RR", 1.0)
    HUMAN_COPY_MAX_SNAPSHOT_AGE: int = _env_int("HUMAN_COPY_MAX_SNAPSHOT_AGE", 5)
    HUMAN_COPY_MAX_LEVERAGE: float = _env_float("HUMAN_COPY_MAX_LEVERAGE", 5.0)
    HUMAN_COPY_ALLOWED_ENTRY_TYPES: list = _env_list(
        "HUMAN_COPY_ALLOWED_ENTRY_TYPES", "TREND,MEDIUM"
    )
    HUMAN_COPY_ALLOWED_DRIVERS: list = _env_list(
        "HUMAN_COPY_ALLOWED_DRIVERS",
        "multi_tier_quality,regime_trend,monte_carlo_zones",
    )
    HUMAN_COPY_STABLE_REGIMES: list = _env_list(
        "HUMAN_COPY_STABLE_REGIMES", "trend,range"
    )
    HUMAN_COPY_ALLOWED_VOL_BANDS: list = _env_list(
        "HUMAN_COPY_ALLOWED_VOL_BANDS", "low,medium"
    )

    # ── Stale Signal ────────────────────────────────────────
    STALE_SIGNAL_CONFIDENCE_PENALTY: float = _env_float("STALE_SIGNAL_CONFIDENCE_PENALTY", 0.15)
    STALE_SIGNAL_HARD_VETO_AGE: int = _env_int("STALE_SIGNAL_HARD_VETO_AGE", 30)

    # ── Execution Guard Actions ─────────────────────────────
    # "veto", "downgrade", "proceed"
    ON_STALE_SIGNAL: str = _env("ON_STALE_SIGNAL", "downgrade")
    ON_HIGH_SLIPPAGE: str = _env("ON_HIGH_SLIPPAGE", "veto")
    ON_WIDE_SPREAD: str = _env("ON_WIDE_SPREAD", "downgrade")
    ON_LOW_LIQUIDITY: str = _env("ON_LOW_LIQUIDITY", "veto")


settings = Settings()
