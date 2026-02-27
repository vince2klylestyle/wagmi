"""
CSV Trade Logger with full dual-entry schema.

Logs every trade with all required fields from the execution spec:
- snapshot_entry, live_entry, effective_entry
- snapshot_timestamp, execution_timestamp, snapshot_age_seconds
- slippage_pct, spread_pct, liquidity
- human_copy_tradable, stale, outcome, state_path
- veto/downgrade reasons
"""

import csv
import logging
import os
from typing import Dict, Any, Optional

logger = logging.getLogger("bot.data.storage.csv_logger")

_LOG_DIR = os.path.join("data", "logs")
_TRADE_LOG = os.path.join(_LOG_DIR, "trades_enhanced.csv")

TRADE_CSV_COLUMNS = [
    "timestamp",
    "symbol",
    "side",
    "entry_type",
    "primary_driver",
    "regime",
    "volatility_band",
    "snapshot_entry",
    "live_entry",
    "effective_entry",
    "snapshot_ts",
    "execution_ts",
    "snapshot_age_seconds",
    "slippage_pct",
    "spread_pct",
    "liquidity_usd",
    "confidence",
    "leverage",
    "size_usd",
    "rr1",
    "rr2",
    "sl_price",
    "tp1_price",
    "tp2_price",
    "human_copy_tradable",
    "stale",
    "outcome",
    "realized_pnl",
    "close_reason",
    "state_path",
    "veto_reasons",
    "downgrade_reasons",
    "llm_action",
    "llm_confidence",
    "llm_regime",
]


def _ensure_log():
    os.makedirs(_LOG_DIR, exist_ok=True)
    if not os.path.exists(_TRADE_LOG):
        with open(_TRADE_LOG, "w", newline="") as f:
            csv.writer(f).writerow(TRADE_CSV_COLUMNS)


def log_trade(trade: Dict[str, Any], path: Optional[str] = None) -> None:
    """Log a trade record to CSV with all required fields."""
    target = path or _TRADE_LOG
    if not path:
        _ensure_log()
    else:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if not os.path.exists(target):
            with open(target, "w", newline="") as f:
                csv.writer(f).writerow(TRADE_CSV_COLUMNS)

    try:
        with open(target, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                trade.get(col, "") for col in TRADE_CSV_COLUMNS
            ])
    except Exception as e:
        logger.warning(f"[CSV] Failed to log trade: {e}")


def load_trades(path: Optional[str] = None) -> list:
    """Load trade records from CSV."""
    target = path or _TRADE_LOG
    if not os.path.exists(target):
        return []
    trades = []
    with open(target, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            trades.append(row)
    return trades
