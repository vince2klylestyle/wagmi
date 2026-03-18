"""
Trade history + equity curve API routes.
Reads bot/trades.csv and backtest equity curve CSVs as JSON.
All operations are strictly READ-ONLY — no writes to any bot data file.
"""
import os
import csv
import json
import glob
from typing import List, Optional

from fastapi import APIRouter, Query, HTTPException

router = APIRouter(prefix="/v1/trades", tags=["trades"])

# ---------------------------------------------------------------------------
# Paths (configurable via env, defaulting to relative paths from api/ dir)
# ---------------------------------------------------------------------------
_BOT_ROOT = os.environ.get(
    "BOT_ROOT",
    os.path.join(os.path.dirname(__file__), "..", "..", "bot"),
)
_TRADES_CSV = os.path.join(_BOT_ROOT, "trades.csv")
_BACKTEST_ROOT = os.path.join(_BOT_ROOT, "backtest_results")

# Expected trades.csv columns (in order)
_TRADE_COLS = [
    "symbol", "side", "strategy", "close_reason", "entry", "exit",
    "sl", "tp1", "tp2", "pnl", "fee", "leverage", "confidence",
    "rr_achieved", "duration_h", "state_path", "outcome",
    "llm_action", "llm_regime", "llm_confidence",
]


def _parse_float(val: str) -> Optional[float]:
    try:
        return float(val) if val and val.strip() != "" else None
    except ValueError:
        return None


def _parse_trade_row(row: dict) -> dict:
    """Normalise a row from trades.csv into a clean dict."""
    return {
        "symbol": row.get("symbol", ""),
        "side": row.get("side", ""),
        "strategy": row.get("strategy", ""),
        "close_reason": row.get("close_reason", ""),
        "entry": _parse_float(row.get("entry", "")),
        "exit": _parse_float(row.get("exit", "")),
        "sl": _parse_float(row.get("sl", "")),
        "tp1": _parse_float(row.get("tp1", "")),
        "tp2": _parse_float(row.get("tp2", "")),
        "pnl": _parse_float(row.get("pnl", "")),
        "fee": _parse_float(row.get("fee", "")),
        "leverage": _parse_float(row.get("leverage", "")),
        "confidence": _parse_float(row.get("confidence", "")),
        "rr_achieved": _parse_float(row.get("rr_achieved", "")),
        "duration_h": _parse_float(row.get("duration_h", "")),
        "outcome": row.get("outcome", ""),
        "llm_action": row.get("llm_action", "") or None,
        "llm_regime": row.get("llm_regime", "") or None,
        "llm_confidence": _parse_float(row.get("llm_confidence", "")),
    }


@router.get("/history")
def get_trade_history(
    limit: int = Query(default=100, ge=1, le=500),
    symbol: Optional[str] = Query(default=None),
    outcome: Optional[str] = Query(default=None),
):
    """
    Return the last N trades from bot/trades.csv as JSON.
    Optionally filter by symbol or outcome (WIN/LOSS).
    Returns newest first.
    """
    if not os.path.exists(_TRADES_CSV):
        return {"trades": [], "total": 0, "has_data": False}

    trades = []
    try:
        with open(_TRADES_CSV, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                t = _parse_trade_row(row)
                # Apply filters
                if symbol and t["symbol"].upper() != symbol.upper():
                    continue
                if outcome and t["outcome"].upper() != outcome.upper():
                    continue
                trades.append(t)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read trades.csv: {e}")

    # Reverse to newest-first (CSV is append-only so newest = last)
    trades.reverse()
    total = len(trades)
    trades = trades[:limit]

    return {
        "trades": trades,
        "total": total,
        "has_data": total > 0,
    }


@router.get("/equity-curve")
def get_equity_curve(run: str = Query(default="latest")):
    """
    Return equity curve data points from a backtest CSV.
    Param `run`: filename base without extension (e.g. "latest", "backtest_60d").
    Returns [{ts, equity, drawdown_pct}] sorted oldest-first.
    """
    # Try backtest_results/ directory first (for named JSON runs)
    # Also try bot root for legacy CSV files
    candidate_paths = [
        os.path.join(_BACKTEST_ROOT, f"{run}_equity_curve.csv"),
        os.path.join(_BOT_ROOT, f"{run}_equity_curve.csv"),
        os.path.join(_BOT_ROOT, f"{run}.csv"),
    ]

    csv_path = None
    for p in candidate_paths:
        if os.path.exists(p):
            csv_path = p
            break

    # Special case: "latest" — find most recent equity curve CSV
    if csv_path is None and run == "latest":
        pattern = os.path.join(_BOT_ROOT, "*_equity_curve.csv")
        files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
        if files:
            csv_path = files[0]

    if csv_path is None or not os.path.exists(csv_path):
        return {"points": [], "has_data": False, "run": run}

    points = []
    try:
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts_str = row.get("time") or row.get("ts") or row.get("timestamp") or ""
                equity = _parse_float(row.get("equity") or row.get("equity_usd") or "")
                drawdown = _parse_float(row.get("drawdown_pct") or row.get("drawdown") or "")
                if ts_str and equity is not None:
                    points.append({
                        "ts": ts_str,
                        "equity": equity,
                        "drawdown_pct": drawdown or 0.0,
                    })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read equity curve: {e}")

    return {
        "points": points,
        "has_data": len(points) > 0,
        "run": run,
        "file": os.path.basename(csv_path),
    }
