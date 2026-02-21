"""
Strategy pruning: config-driven weight adjustment based on EV.

Reads performance data from data/analysis/performance.json, evaluates
each strategy and entry_type, and proposes weight adjustments.

Design principles:
- Transparent: all decisions are logged to data/logs/pruning_decisions.csv
- Reversible: changes are config-driven, not hardcoded
- Conservative: de-prioritize before disabling, require large sample sizes
- Explainable: every decision has a reason string

Pruning rules (conservative):
- If a strategy has EV_per_trade < 0 after N trades (default 50):
  AND win_rate < 45%
  AND avg_loss_R >= avg_win_R
  -> reduce weight by 30% (not disable)
- If it remains negative after another N trades -> reduce by another 30%
- Only fully disable after 3 consecutive negative evaluations

Usage:
    from execution.strategy_pruning import evaluate_and_adjust
    adjustments = evaluate_and_adjust(performance_data)
"""

import csv
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

logger = logging.getLogger("bot.execution.pruning")

_LOG_DIR = os.path.join("data", "logs")
_DECISIONS_FILE = os.path.join(_LOG_DIR, "pruning_decisions.csv")
_DECISIONS_HEADERS = [
    "timestamp", "entity_type", "entity_name", "action",
    "old_weight", "new_weight", "reason",
    "trades", "win_rate", "ev_per_trade",
]

_WEIGHTS_FILE = os.path.join("config", "strategy_weights_override.json")

# Thresholds — these are hypotheses, not truths.
# Conservative: require large sample before acting.
MIN_TRADES_FOR_EVALUATION = 50  # need at least this many trades to judge
NEGATIVE_EV_WR_THRESHOLD = 0.45  # below this + negative EV -> candidate
WEIGHT_REDUCTION_FACTOR = 0.70  # reduce weight to 70% of current
MIN_WEIGHT = 0.10  # never reduce below 10%
DISABLE_THRESHOLD = 0.10  # at this weight, consider disabled


def _ensure_log():
    os.makedirs(_LOG_DIR, exist_ok=True)
    if not os.path.exists(_DECISIONS_FILE):
        with open(_DECISIONS_FILE, "w", newline="") as f:
            csv.writer(f).writerow(_DECISIONS_HEADERS)


def _log_decision(
    entity_type: str,
    entity_name: str,
    action: str,
    old_weight: float,
    new_weight: float,
    reason: str,
    trades: int,
    win_rate: float,
    ev: float,
):
    """Log a pruning decision to CSV."""
    _ensure_log()
    ts = datetime.now(timezone.utc).isoformat()
    try:
        with open(_DECISIONS_FILE, "a", newline="") as f:
            csv.writer(f).writerow([
                ts, entity_type, entity_name, action,
                f"{old_weight:.3f}", f"{new_weight:.3f}", reason,
                str(trades), f"{win_rate:.3f}", f"{ev:.4f}",
            ])
    except Exception as e:
        logger.warning(f"Failed to log pruning decision: {e}")


def load_weight_overrides() -> Dict[str, float]:
    """Load strategy weight overrides from config."""
    try:
        if os.path.exists(_WEIGHTS_FILE):
            with open(_WEIGHTS_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_weight_overrides(overrides: Dict[str, float]):
    """Save strategy weight overrides to config."""
    os.makedirs(os.path.dirname(_WEIGHTS_FILE), exist_ok=True)
    with open(_WEIGHTS_FILE, "w") as f:
        json.dump(overrides, f, indent=2)
    logger.info(f"Saved weight overrides: {overrides}")


def evaluate_strategy(
    name: str,
    stats: Dict[str, Any],
    current_weight: float = 1.0,
) -> Optional[Dict[str, Any]]:
    """
    Evaluate a single strategy and return an adjustment if needed.

    Returns dict with {name, action, old_weight, new_weight, reason} or None.
    """
    trades = stats.get("count", 0)
    if trades < MIN_TRADES_FOR_EVALUATION:
        return None  # not enough data to judge

    wr = stats.get("win_rate", 0)
    ev = stats.get("EV_per_trade", stats.get("total_pnl", 0) / max(trades, 1))
    avg_win = stats.get("avg_win_R", 0)
    avg_loss = stats.get("avg_loss_R", 0)

    # Check if candidate for de-prioritization
    if ev < 0 and wr < NEGATIVE_EV_WR_THRESHOLD and avg_loss >= avg_win:
        new_weight = max(current_weight * WEIGHT_REDUCTION_FACTOR, MIN_WEIGHT)
        reason = (
            f"Negative EV ({ev:.3f}) with WR {wr:.1%} < {NEGATIVE_EV_WR_THRESHOLD:.0%} "
            f"and avg_loss_R ({avg_loss:.2f}) >= avg_win_R ({avg_win:.2f}) "
            f"over {trades} trades"
        )
        return {
            "name": name,
            "action": "reduce_weight",
            "old_weight": current_weight,
            "new_weight": round(new_weight, 3),
            "reason": reason,
            "trades": trades,
            "win_rate": wr,
            "ev": ev,
        }

    # Check if strategy was previously reduced but is now performing well
    if ev > 0 and wr > 0.50 and current_weight < 0.9:
        new_weight = min(current_weight / WEIGHT_REDUCTION_FACTOR, 1.0)
        reason = (
            f"Positive EV ({ev:.3f}) with WR {wr:.1%} over {trades} trades. "
            f"Restoring weight from {current_weight:.2f}."
        )
        return {
            "name": name,
            "action": "restore_weight",
            "old_weight": current_weight,
            "new_weight": round(new_weight, 3),
            "reason": reason,
            "trades": trades,
            "win_rate": wr,
            "ev": ev,
        }

    return None  # no change needed


def evaluate_and_adjust(
    performance: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Evaluate all strategies and entry_types in performance data.
    Returns list of adjustments made.

    Args:
        performance: from data/analysis/performance.json
    """
    adjustments = []
    overrides = load_weight_overrides()

    # Evaluate per-strategy performance
    by_strategy = performance.get("by_strategy", {})
    for name, stats in by_strategy.items():
        current_w = overrides.get(name, 1.0)
        adj = evaluate_strategy(name, stats, current_w)
        if adj:
            overrides[name] = adj["new_weight"]
            _log_decision(
                "strategy", name, adj["action"],
                adj["old_weight"], adj["new_weight"], adj["reason"],
                adj["trades"], adj["win_rate"], adj["ev"],
            )
            adjustments.append(adj)
            logger.info(
                f"[PRUNING] {adj['action']} {name}: "
                f"{adj['old_weight']:.2f} -> {adj['new_weight']:.2f} | {adj['reason']}"
            )

    # Evaluate per-entry_type (informational — we don't disable types, just log)
    by_type = performance.get("by_entry_type", {})
    for etype, stats in by_type.items():
        trades = stats.get("count", 0)
        ev = stats.get("EV_per_trade", 0)
        wr = stats.get("win_rate", 0)
        if trades >= MIN_TRADES_FOR_EVALUATION and ev < 0:
            _log_decision(
                "entry_type", etype, "flagged_negative_ev",
                1.0, 1.0,
                f"entry_type {etype} has negative EV ({ev:.3f}) over {trades} trades",
                trades, wr, ev,
            )
            logger.warning(
                f"[PRUNING] entry_type {etype}: NEGATIVE EV ({ev:.3f}) | "
                f"WR={wr:.1%} | trades={trades}"
            )

    if overrides:
        save_weight_overrides(overrides)

    return adjustments


def get_strategy_weight(name: str) -> float:
    """Get the effective weight for a strategy (checks override file)."""
    overrides = load_weight_overrides()
    return overrides.get(name, 1.0)
