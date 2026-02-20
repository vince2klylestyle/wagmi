"""
Per-symbol precision rounding for prices and quantities.

Uses Decimal for exact math — no more 0.000000 TP/SL on microcaps.
Config loaded from config/symbol_precision.json.
"""

import json
import logging
import os
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import Dict

logger = logging.getLogger("bot.execution.precision")

_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "config", "symbol_precision.json"
)

# Default precision if symbol not in config
_DEFAULT = {"price": 2, "qty": 4}

_precision_cache: Dict[str, dict] = {}


def _load_config() -> Dict[str, dict]:
    """Load precision config (cached after first call)."""
    global _precision_cache
    if _precision_cache:
        return _precision_cache
    try:
        with open(_CONFIG_PATH) as f:
            _precision_cache = json.load(f)
        logger.info(f"Loaded precision config for {list(_precision_cache.keys())}")
    except FileNotFoundError:
        logger.warning(f"Precision config not found at {_CONFIG_PATH}, using defaults")
        _precision_cache = {}
    return _precision_cache


def _get_precision(symbol: str) -> dict:
    cfg = _load_config()
    return cfg.get(symbol, _DEFAULT)


def round_price(symbol: str, price: float) -> float:
    """Round a price to the correct decimal places for a symbol."""
    prec = _get_precision(symbol)["price"]
    d = Decimal(str(price)).quantize(
        Decimal(10) ** -prec, rounding=ROUND_HALF_UP
    )
    return float(d)


def round_qty(symbol: str, qty: float) -> float:
    """Round a quantity to the correct decimal places for a symbol."""
    prec = _get_precision(symbol)["qty"]
    d = Decimal(str(qty)).quantize(
        Decimal(10) ** -prec, rounding=ROUND_DOWN  # always round qty down (safer)
    )
    return float(d)


def format_price(symbol: str, price: float) -> str:
    """Format a price with correct precision for display."""
    prec = _get_precision(symbol)["price"]
    return f"{price:.{prec}f}"
