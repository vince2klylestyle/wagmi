"""
Offline RL Trainer: Learn targets from the transition buffer.

Instead of directly training a neural network, this trainer computes
simple, interpretable policy targets:
  - Per-regime size multipliers (which regimes deserve bigger sizes?)
  - Per-symbol risk caps (which symbols are we losing money on?)
  - Per-trigger call frequency (which triggers lead to good decisions?)

These suggestions are written to rl_policy.json but NOT auto-applied.
The apply_policy.py module reads and applies them with safety caps.

This is deliberately conservative and interpretable over complex.
"""

import json
import logging
import os
from typing import Dict, Any, List
from collections import defaultdict

from rl.buffer import load_buffer, get_buffer_stats

logger = logging.getLogger("bot.rl.train_offline")

_RL_DIR = os.path.join("data", "rl")
_POLICY_FILE = os.path.join(_RL_DIR, "rl_policy.json")

# Minimum samples to generate a suggestion
_MIN_SAMPLES_PER_BUCKET = 10


def train(buffer_path: str = None) -> Dict[str, Any]:
    """Train policy targets from the transition buffer.

    Returns the policy dict (also saved to rl_policy.json).
    """
    transitions = load_buffer(buffer_path) if buffer_path else load_buffer()
    if not transitions:
        logger.info("[RL-TRAIN] No transitions in buffer, skipping")
        return {}

    policy = {
        "trained_at": __import__("time").time(),
        "total_transitions": len(transitions),
        "regime_multipliers": _compute_regime_multipliers(transitions),
        "symbol_risk_caps": _compute_symbol_risk_caps(transitions),
        "trigger_adjustments": _compute_trigger_adjustments(transitions),
    }

    # Save
    os.makedirs(_RL_DIR, exist_ok=True)
    with open(_POLICY_FILE, "w") as f:
        json.dump(policy, f, indent=2)

    logger.info(
        f"[RL-TRAIN] Policy trained from {len(transitions)} transitions, "
        f"saved to {_POLICY_FILE}"
    )
    return policy


def _compute_regime_multipliers(transitions: List[dict]) -> Dict[str, float]:
    """Compute per-regime size multipliers.

    Logic:
    - If average R > 0.5 in a regime, suggest increasing size (up to 1.3x)
    - If average R < -0.3 in a regime, suggest decreasing size (down to 0.5x)
    - Otherwise, keep at 1.0x
    """
    by_regime = defaultdict(list)
    for t in transitions:
        regime = t.get("state", {}).get("regime", "unknown")
        by_regime[regime].append(t.get("reward", 0))

    multipliers = {}
    for regime, rewards in by_regime.items():
        if len(rewards) < _MIN_SAMPLES_PER_BUCKET:
            multipliers[regime] = 1.0
            continue

        avg_r = sum(rewards) / len(rewards)
        if avg_r > 0.5:
            mult = min(1.0 + avg_r * 0.3, 1.3)
        elif avg_r < -0.3:
            mult = max(1.0 + avg_r * 0.5, 0.5)
        else:
            mult = 1.0

        multipliers[regime] = round(mult, 2)

    return multipliers


def _compute_symbol_risk_caps(transitions: List[dict]) -> Dict[str, float]:
    """Compute per-symbol risk cap adjustments.

    Logic:
    - If a symbol has consistently negative R, cap its risk
    - If a symbol has consistently positive R, allow more risk
    - Default: 1.0 (normal risk)
    """
    by_symbol = defaultdict(list)
    for t in transitions:
        symbol = t.get("state", {}).get("symbol", "unknown")
        by_symbol[symbol].append(t.get("reward", 0))

    caps = {}
    for symbol, rewards in by_symbol.items():
        if len(rewards) < _MIN_SAMPLES_PER_BUCKET:
            caps[symbol] = 1.0
            continue

        avg_r = sum(rewards) / len(rewards)
        win_rate = len([r for r in rewards if r > 0]) / len(rewards)

        if avg_r < -0.3 and win_rate < 0.4:
            caps[symbol] = max(0.5, 1.0 + avg_r * 0.5)
        elif avg_r > 0.5 and win_rate > 0.6:
            caps[symbol] = min(1.3, 1.0 + avg_r * 0.2)
        else:
            caps[symbol] = 1.0

        caps[symbol] = round(caps[symbol], 2)

    return caps


def _compute_trigger_adjustments(transitions: List[dict]) -> Dict[str, float]:
    """Compute per-trigger quality scores.

    Logic:
    - If trades triggered by a certain event have good R, keep calling
    - If trades triggered by a certain event are noisy/negative, reduce frequency
    """
    by_trigger = defaultdict(list)
    for t in transitions:
        trigger = t.get("meta", {}).get("trigger", "unknown")
        by_trigger[trigger].append(t.get("reward", 0))

    adjustments = {}
    for trigger, rewards in by_trigger.items():
        if len(rewards) < _MIN_SAMPLES_PER_BUCKET:
            adjustments[trigger] = 1.0
            continue

        avg_r = sum(rewards) / len(rewards)
        if avg_r > 0.3:
            adjustments[trigger] = 1.0  # Keep calling
        elif avg_r < -0.2:
            adjustments[trigger] = 0.5  # Reduce frequency
        else:
            adjustments[trigger] = 0.8

    return adjustments


def load_policy(path: str = _POLICY_FILE) -> Dict[str, Any]:
    """Load the current RL policy from disk."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"[RL-TRAIN] Failed to load policy: {e}")
        return {}
