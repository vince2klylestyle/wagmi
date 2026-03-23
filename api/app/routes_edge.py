"""
Edge intelligence API: expose quant edge data for manual traders.

Endpoints:
- GET /v1/edge/setup-types — WR and PnL by setup type
- GET /v1/edge/regimes — WR and PnL by regime
- GET /v1/edge/sessions — WR and PnL by hour of day
- GET /v1/edge/strategies — WR and PnL by strategy combo
- GET /v1/edge/symbols — WR and PnL by symbol
"""

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter

router = APIRouter(prefix="/v1/edge", tags=["edge"])

# Data sources
_TRADE_DNA_PATH = os.path.join("bot", "data", "llm", "deep_memory", "trade_dna.json")
_OUTCOMES_PATH = os.path.join("bot", "data", "analysis", "trade_outcomes.csv")


def _load_trades() -> List[Dict]:
    """Load trade history from trade_dna.json or trade_outcomes.csv."""
    dna_path = Path(_TRADE_DNA_PATH)
    if dna_path.exists():
        try:
            with open(dna_path) as f:
                data = json.load(f)
            return data.get("trades", [])
        except Exception:
            pass

    outcomes_path = Path(_OUTCOMES_PATH)
    if outcomes_path.exists():
        try:
            import csv
            trades = []
            with open(outcomes_path) as f:
                for row in csv.DictReader(f):
                    trades.append(row)
            return trades
        except Exception:
            pass

    return []


def _compute_stats(trades: List[Dict], group_key: str) -> Dict[str, Any]:
    """Group trades by a key and compute WR/PnL stats."""
    groups: Dict[str, Dict] = defaultdict(lambda: {"trades": 0, "wins": 0, "pnl": 0.0})
    for t in trades:
        key = t.get(group_key, "unknown") or "unknown"
        g = groups[key]
        g["trades"] += 1
        pnl = float(t.get("pnl", 0) or 0)
        outcome = t.get("outcome", "")
        if outcome == "WIN" or pnl > 0:
            g["wins"] += 1
        g["pnl"] += pnl

    result = {}
    for key, g in sorted(groups.items(), key=lambda x: -x[1]["pnl"]):
        t = g["trades"]
        result[key] = {
            "trades": t,
            "wins": g["wins"],
            "win_rate": round(g["wins"] / t * 100, 1) if t > 0 else 0,
            "pnl": round(g["pnl"], 2),
            "avg_pnl": round(g["pnl"] / t, 2) if t > 0 else 0,
            "edge": "PROFITABLE" if g["pnl"] > 0 else "LOSING",
        }
    return result


@router.get("/setup-types")
def get_setup_type_edge():
    """WR and PnL by setup type (trend_follow, mean_reversion, etc.)."""
    trades = _load_trades()
    return _compute_stats(trades, "setup_type")


@router.get("/regimes")
def get_regime_edge():
    """WR and PnL by market regime."""
    trades = _load_trades()
    return _compute_stats(trades, "regime")


@router.get("/strategies")
def get_strategy_edge():
    """WR and PnL by primary strategy."""
    trades = _load_trades()
    return _compute_stats(trades, "strategy")


@router.get("/symbols")
def get_symbol_edge():
    """WR and PnL by symbol."""
    trades = _load_trades()
    return _compute_stats(trades, "symbol")


@router.get("/summary")
def get_edge_summary():
    """Comprehensive edge summary: all dimensions in one response."""
    trades = _load_trades()
    return {
        "total_trades": len(trades),
        "by_setup_type": _compute_stats(trades, "setup_type"),
        "by_regime": _compute_stats(trades, "regime"),
        "by_strategy": _compute_stats(trades, "strategy"),
        "by_symbol": _compute_stats(trades, "symbol"),
    }
