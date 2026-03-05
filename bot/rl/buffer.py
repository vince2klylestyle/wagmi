"""
RL Learning Buffer: Store transitions from live trades for offline learning.

Each transition captures:
  - state: compact snapshot hash or key features at decision time
  - action: what the bot + LLM decided (mode, action, size_multiplier, etc)
  - reward: realized R (risk-normalized PnL)
  - next_state: key features after trade closed
  - done: whether the episode (trade) is complete

The buffer supports:
  - Rolling window (configurable max size)
  - Sampling by regime, symbol, mode
  - Persistence to disk (JSONL)

This is deliberately non-destructive: the buffer COLLECTS data.
The offline trainer (train_offline.py) READS it.
Nothing auto-applies.
"""

import json
import logging
import os
import time
from typing import Dict, List, Any, Optional
from collections import defaultdict

logger = logging.getLogger("bot.rl.buffer")

_RL_DIR = os.path.join("data", "rl")
_BUFFER_FILE = os.path.join(_RL_DIR, "transitions.jsonl")
_MAX_BUFFER_SIZE = int(os.getenv("RL_BUFFER_SIZE", "10000"))


def _ensure_dir():
    os.makedirs(_RL_DIR, exist_ok=True)


def append_transition(
    state: Dict[str, Any],
    action: Dict[str, Any],
    reward: float,
    next_state: Optional[Dict[str, Any]] = None,
    done: bool = True,
    metadata: Optional[Dict[str, Any]] = None,
):
    """Append a transition to the buffer.

    Args:
        state: Key features at decision time:
            - symbol, regime, confidence, side, entry, atr, volatility
        action: What was decided:
            - llm_mode, llm_action, size_multiplier, leverage, entry_type
        reward: Realized R (PnL / risk_amount). Positive = profit.
        next_state: Features after trade closed (optional).
        done: Whether this trade is fully resolved.
        metadata: Extra fields (trigger, hold_time_s, outcome, etc).
    """
    _ensure_dir()

    transition = {
        "ts": time.time(),
        "state": state,
        "action": action,
        "reward": round(reward, 4),
        "next_state": next_state or {},
        "done": done,
        "meta": metadata or {},
    }

    try:
        with open(_BUFFER_FILE, "a") as f:
            f.write(json.dumps(transition) + "\n")
    except Exception as e:
        logger.warning(f"[RL-BUFFER] Failed to write transition: {e}")


def load_buffer(path: str = _BUFFER_FILE) -> List[Dict[str, Any]]:
    """Load all transitions from the buffer."""
    if not os.path.exists(path):
        return []

    transitions = []
    try:
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    transitions.append(json.loads(line))
    except Exception as e:
        logger.warning(f"[RL-BUFFER] Failed to load buffer: {e}")

    return transitions


def sample_by(
    transitions: List[Dict[str, Any]],
    key: str,
    value: str,
) -> List[Dict[str, Any]]:
    """Sample transitions by a key in state or metadata.

    Example: sample_by(transitions, 'regime', 'trend')
    """
    result = []
    for t in transitions:
        state_val = t.get("state", {}).get(key)
        meta_val = t.get("meta", {}).get(key)
        if state_val == value or meta_val == value:
            result.append(t)
    return result


def get_buffer_stats(transitions: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get summary statistics of the buffer."""
    if transitions is None:
        transitions = load_buffer()

    if not transitions:
        return {"total": 0}

    rewards = [t.get("reward", 0) for t in transitions]
    wins = [r for r in rewards if r > 0]
    losses = [r for r in rewards if r <= 0]

    # Group by regime
    by_regime = defaultdict(list)
    for t in transitions:
        regime = t.get("state", {}).get("regime", "unknown")
        by_regime[regime].append(t.get("reward", 0))

    # Group by symbol
    by_symbol = defaultdict(list)
    for t in transitions:
        symbol = t.get("state", {}).get("symbol", "unknown")
        by_symbol[symbol].append(t.get("reward", 0))

    return {
        "total": len(transitions),
        "avg_reward": sum(rewards) / len(rewards) if rewards else 0,
        "win_rate": len(wins) / len(rewards) if rewards else 0,
        "total_reward": sum(rewards),
        "by_regime": {
            k: {"count": len(v), "avg_r": sum(v) / len(v) if v else 0}
            for k, v in by_regime.items()
        },
        "by_symbol": {
            k: {"count": len(v), "avg_r": sum(v) / len(v) if v else 0}
            for k, v in sorted(by_symbol.items(), key=lambda x: -sum(x[1]))[:10]
        },
    }


def trim_buffer(max_size: int = _MAX_BUFFER_SIZE):
    """Trim buffer to keep only the most recent transitions."""
    transitions = load_buffer()
    if len(transitions) <= max_size:
        return

    # Keep most recent
    transitions = transitions[-max_size:]
    _ensure_dir()
    with open(_BUFFER_FILE, "w") as f:
        for t in transitions:
            f.write(json.dumps(t) + "\n")

    logger.info(f"[RL-BUFFER] Trimmed buffer to {max_size} transitions")
