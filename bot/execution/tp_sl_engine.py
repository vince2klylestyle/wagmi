"""
TP/SL Computation Engine.

Computes stop-loss and take-profit levels using the effective_entry
(live_entry preferred, snapshot_entry fallback).

All levels are computed from the actual execution price, not the snapshot.
"""

import logging
from typing import Optional

logger = logging.getLogger("bot.execution.tp_sl_engine")


def compute_tp_sl(
    effective_entry: float,
    side: str,
    atr: float,
    rr1: float = 1.5,
    rr2: float = 2.5,
    sl_atr_mult: float = 1.5,
) -> dict:
    """Compute TP/SL levels from effective entry price.

    Args:
        effective_entry: The actual entry price (live preferred, snapshot fallback)
        side: "LONG" or "SHORT"
        atr: Average True Range value
        rr1: Risk-reward ratio for TP1
        rr2: Risk-reward ratio for TP2
        sl_atr_mult: ATR multiplier for SL distance

    Returns:
        dict with sl_price, tp1_price, tp2_price
    """
    if effective_entry <= 0 or atr <= 0:
        return {"sl_price": 0.0, "tp1_price": 0.0, "tp2_price": 0.0}

    sl_distance = atr * sl_atr_mult

    if side.upper() == "LONG":
        sl = effective_entry - sl_distance
        tp1 = effective_entry + (sl_distance * rr1)
        tp2 = effective_entry + (sl_distance * rr2)
    elif side.upper() == "SHORT":
        sl = effective_entry + sl_distance
        tp1 = effective_entry - (sl_distance * rr1)
        tp2 = effective_entry - (sl_distance * rr2)
    else:
        return {"sl_price": 0.0, "tp1_price": 0.0, "tp2_price": 0.0}

    return {
        "sl_price": round(sl, 8),
        "tp1_price": round(tp1, 8),
        "tp2_price": round(tp2, 8),
    }


def recompute_from_live_entry(
    snapshot_entry: float,
    live_entry: float,
    side: str,
    original_sl: float,
    original_tp1: float,
    original_tp2: float,
) -> dict:
    """Recompute TP/SL when live entry differs from snapshot.

    Shifts levels proportionally based on the entry difference.
    """
    if snapshot_entry <= 0 or live_entry <= 0:
        return {
            "sl_price": original_sl,
            "tp1_price": original_tp1,
            "tp2_price": original_tp2,
        }

    diff = live_entry - snapshot_entry

    return {
        "sl_price": round(original_sl + diff, 8),
        "tp1_price": round(original_tp1 + diff, 8),
        "tp2_price": round(original_tp2 + diff, 8),
    }
