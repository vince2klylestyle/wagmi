"""
ML logging: stats snapshots and confidence history.

Files:
- data/ml/ml_stats.jsonl    (append-only, one JSON per heartbeat)
- data/ml/ml_conf_history.csv (per-symbol confidence tracking)
"""

import csv
import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger("bot.data.ml_log")

_ML_DIR = os.path.join("data", "ml")
_STATS_FILE = os.path.join(_ML_DIR, "ml_stats.jsonl")
_CONF_FILE = os.path.join(_ML_DIR, "ml_conf_history.csv")
_CONF_HEADERS = [
    "timestamp", "symbol", "conf_trade", "conf_snapshot", "conf_fast",
]


def _ensure_files():
    os.makedirs(_ML_DIR, exist_ok=True)
    if not os.path.exists(_CONF_FILE):
        with open(_CONF_FILE, "w", newline="") as f:
            csv.writer(f).writerow(_CONF_HEADERS)


def log_ml_stats(
    ml_samples_total: int,
    ml_conf_trade: float,
    ml_conf_snapshot: float,
    ml_conf_fast: float,
    equity: float,
    open_positions: int,
):
    """Append an ML stats snapshot (called on heartbeat)."""
    os.makedirs(_ML_DIR, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ml_samples_total": ml_samples_total,
        "ml_conf_trade": round(ml_conf_trade, 4),
        "ml_conf_snapshot": round(ml_conf_snapshot, 4),
        "ml_conf_fast": round(ml_conf_fast, 4),
        "equity": round(equity, 2),
        "open_positions": open_positions,
    }
    try:
        with open(_STATS_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.warning(f"Failed to write ML stats: {e}")


def log_ml_confidence(
    symbol: str,
    conf_trade: float,
    conf_snapshot: float,
    conf_fast: float,
):
    """Log per-symbol ML confidence (called on each signal evaluation)."""
    _ensure_files()
    ts = datetime.now(timezone.utc).isoformat()
    try:
        with open(_CONF_FILE, "a", newline="") as f:
            csv.writer(f).writerow([
                ts, symbol,
                f"{conf_trade:.4f}", f"{conf_snapshot:.4f}", f"{conf_fast:.4f}",
            ])
    except Exception as e:
        logger.warning(f"Failed to write ML confidence: {e}")
