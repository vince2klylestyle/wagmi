"""
Main entry point for the multi-strategy auto-trading bot.
Wires together all components: data fetcher, strategies, ensemble,
position management, leverage, risk, ML, and alerts.

Usage:
    python multi_strategy_main.py
    python multi_strategy_main.py paper  # paper trading mode
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple

# ---------------------------------------------------------------------------
# Bootstrap: ensure the bot/ directory (where this file lives) is on sys.path
# so that all sibling packages (core, strategies, llm, execution, …) resolve
# without needing the caller to set PYTHONPATH manually.
# ---------------------------------------------------------------------------
_BOT_DIR = os.path.dirname(os.path.abspath(__file__))
if _BOT_DIR not in sys.path:
    sys.path.insert(0, _BOT_DIR)

from core.signal_pipeline import SignalPipeline
from data.fetcher import MultiExchangeFetcher
from execution.position_manager import PositionManager
from execution.risk import RiskManager
from execution.ops_guard import OpsGuard
from strategies.ensemble import EnsembleStrategy
from trading_config import TradingConfig
from data.db import init_db

logger = logging.getLogger("bot.main")

# ---------------------------------------------------------------------------
# Logging setup — called once at startup
# ---------------------------------------------------------------------------

def setup_logging(level: str = "INFO") -> None:
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), format=fmt)
    # Quiet noisy third-party loggers
    for noisy in ("ccxt", "urllib3", "asyncio", "websockets", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


setup_logging(os.environ.get("LOG_LEVEL", "INFO"))
