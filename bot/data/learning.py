"""
Learning hooks: trade outcome classification and rolling performance metrics.

Updates after every trade close:
- data/analysis/trade_outcomes.csv  (per-trade outcomes)
- data/analysis/performance.json    (rolling metrics)
"""

import csv
import json
import logging
import os
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger("bot.data.learning")

_OUTCOMES_DIR = os.path.join("data", "analysis")
_OUTCOMES_FILE = os.path.join(_OUTCOMES_DIR, "trade_outcomes.csv")
_OUTCOMES_HEADERS = [
    "timestamp", "symbol", "side", "outcome", "pnl", "rr1", "rr2",
    "tp1_hit", "sl_after_tp1", "state_path", "leverage", "confidence",
    "strategy", "entry_reasons",
]

_PERF_FILE = os.path.join(_OUTCOMES_DIR, "performance.json")


def _ensure_outcomes_file():
    os.makedirs(_OUTCOMES_DIR, exist_ok=True)
    if not os.path.exists(_OUTCOMES_FILE):
        with open(_OUTCOMES_FILE, "w", newline="") as f:
            csv.writer(f).writerow(_OUTCOMES_HEADERS)


# Rolling window of recent outcomes for metric computation
_recent_outcomes: deque = deque(maxlen=100)


def record_trade_outcome(
    symbol: str,
    side: str,
    outcome: str,
    pnl: float,
    entry: float,
    sl: float,
    tp1: float,
    tp2: float,
    tp1_hit: bool,
    sl_after_tp1: bool,
    state_path: str,
    leverage: float = 1.0,
    confidence: float = 0.0,
    strategy: str = "",
    entry_reasons: Optional[Dict[str, Any]] = None,
):
    """Record a trade outcome to CSV and update rolling metrics."""
    _ensure_outcomes_file()

    stop_width = abs(entry - sl) if abs(entry - sl) > 0 else 1e-9
    rr1 = abs(tp1 - entry) / stop_width
    rr2 = abs(tp2 - entry) / stop_width

    ts = datetime.now(timezone.utc).isoformat()
    row = [
        ts, symbol, side, outcome, f"{pnl:.2f}",
        f"{rr1:.2f}", f"{rr2:.2f}",
        str(tp1_hit), str(sl_after_tp1), state_path,
        f"{leverage:.1f}", f"{confidence:.1f}", strategy,
        json.dumps(entry_reasons or {}),
    ]

    try:
        with open(_OUTCOMES_FILE, "a", newline="") as f:
            csv.writer(f).writerow(row)
    except Exception as e:
        logger.warning(f"Failed to write trade outcome: {e}")

    # Add to rolling window
    _recent_outcomes.append({
        "pnl": pnl, "outcome": outcome, "rr1": rr1,
        "tp1_hit": tp1_hit, "sl_after_tp1": sl_after_tp1,
        "leverage": leverage,
    })

    # Update rolling performance
    _update_performance()


def _update_performance():
    """Compute and save rolling performance metrics."""
    if not _recent_outcomes:
        return

    outcomes = list(_recent_outcomes)
    n = len(outcomes)

    def _window_stats(window):
        if not window:
            return {"win_rate": 0, "count": 0}
        wins = sum(1 for o in window if o["pnl"] > 0)
        return {
            "win_rate": round(wins / len(window), 3),
            "count": len(window),
        }

    last_20 = outcomes[-20:] if n >= 20 else outcomes
    last_50 = outcomes[-50:] if n >= 50 else outcomes

    tp1_hits = [o for o in outcomes if o["tp1_hit"]]
    tp1_then_sl = [o for o in outcomes if o["sl_after_tp1"]]
    early_exits = [o for o in outcomes if "EARLY_EXIT" in o["outcome"]]
    early_saves = [o for o in early_exits if o["pnl"] > -abs(o.get("rr1", 1)) * 0.5]

    avg_rr = sum(o["rr1"] for o in outcomes) / n if n else 0

    perf = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "total_trades": n,
        "win_rate_20": _window_stats(last_20)["win_rate"],
        "win_rate_50": _window_stats(last_50)["win_rate"],
        "avg_rr": round(avg_rr, 2),
        "tp1_success_rate": round(len(tp1_hits) / n, 3) if n else 0,
        "tp1_to_sl_rate": round(len(tp1_then_sl) / max(len(tp1_hits), 1), 3),
        "early_exit_count": len(early_exits),
        "early_exit_success_rate": round(len(early_saves) / max(len(early_exits), 1), 3),
        "total_pnl": round(sum(o["pnl"] for o in outcomes), 2),
        "avg_pnl": round(sum(o["pnl"] for o in outcomes) / n, 2) if n else 0,
    }

    try:
        os.makedirs(_OUTCOMES_DIR, exist_ok=True)
        with open(_PERF_FILE, "w") as f:
            json.dump(perf, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to write performance: {e}")


def get_performance() -> Dict[str, Any]:
    """Read current performance metrics."""
    try:
        if os.path.exists(_PERF_FILE):
            with open(_PERF_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}
