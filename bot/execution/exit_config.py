"""
Per-cell trailing exit configuration — PROPOSAL (feature-flagged).

Derived from `bot/data/sessions/tmp_exit_01_trail_sweep.py` on 2026-04-19.
Companion doc: `bot/data/sessions/PER_CELL_EXIT_RULES_2026_04_19.md`.

DO NOT USE IN PRODUCTION without the feature flag. Currently read-only.
This is a lookup table; wiring into `position_manager.py` is deferred pending
shadow-replay validation.

Activation: when `CELL_EXIT_RULES_ENABLED` env var is truthy AND
            `trade_profile.trailing_style == "medium"` (scoped to MEDIUM only
            in first rollout — SCALP/TREND/REGIME untouched).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CellExitRule:
    """Trailing exit rule parameters (in R-multiples of the cell's Bayes SL)."""
    activate_at_R: float  # trailing arms once favorable move reaches this multiple of R
    trail_width_R: float  # once armed, lock-in at (peak_MFE - trail_width_R * R)
    r_atr: float          # the cell's Bayes-optimal SL width (in ATR units) — R = r_atr * ATR
    n_trades: int         # sample size used to derive the posterior
    ev_atr_per_trade: float  # expected ATR/trade at this (a, t, R)
    ev_delta_vs_baseline_atr: float  # delta vs single-global 0.6R/0.5R baseline


# Per (regime, side) cell with n >= 10 in 2026-04-02..2026-04-19 sample.
# Baseline: single-global MEDIUM profile profit-lock ~ activate=0.6R, trail=0.5R.
#
# Format: (regime, side) -> CellExitRule
_CELL_EXIT_RULES: dict[tuple[str, str], CellExitRule] = {
    ("illiquid", "LONG"): CellExitRule(1.0, 0.25, r_atr=1.08, n_trades=43, ev_atr_per_trade=1.306, ev_delta_vs_baseline_atr=0.050),
    ("ranging",  "LONG"): CellExitRule(1.0, 0.25, r_atr=1.18, n_trades=14, ev_atr_per_trade=-0.286, ev_delta_vs_baseline_atr=0.042),
    ("trending", "LONG"): CellExitRule(2.0, 0.25, r_atr=2.20, n_trades=15, ev_atr_per_trade=4.539, ev_delta_vs_baseline_atr=0.293),
    ("unknown",  "LONG"): CellExitRule(2.0, 0.25, r_atr=1.92, n_trades=16, ev_atr_per_trade=0.776, ev_delta_vs_baseline_atr=0.120),
    ("unknown",  "SHORT"): CellExitRule(1.0, 0.25, r_atr=0.64, n_trades=25, ev_atr_per_trade=3.200, ev_delta_vs_baseline_atr=0.039),
}

# Global fallback when a cell has n < 10 (weak sample). Uses global sweep posterior.
_GLOBAL_FALLBACK = CellExitRule(
    activate_at_R=2.5,
    trail_width_R=0.25,
    r_atr=1.37,
    n_trades=123,
    ev_atr_per_trade=0.606,
    ev_delta_vs_baseline_atr=0.421,
)

# Minimum n for cell-specific rule; below this use global.
MIN_N_FOR_CELL = 10

# Single-global baseline (for reference/A-B comparison).
BASELINE_ACTIVATION_R = 0.6
BASELINE_TRAIL_R = 0.5


def is_enabled() -> bool:
    """Feature flag — default OFF."""
    val = os.getenv("CELL_EXIT_RULES_ENABLED", "").strip().lower()
    return val in ("1", "true", "yes", "on")


def lookup_exit_rule(regime: Optional[str], side: Optional[str]) -> CellExitRule:
    """Return the (activation_R, trail_R) rule for a given (regime, side) cell.

    Falls back to `_GLOBAL_FALLBACK` if:
      - regime or side is None/empty
      - cell not in table (low-n cell)

    Caller is responsible for converting R-multiples to absolute price levels:
        R_in_atr = rule.r_atr
        activate_distance = rule.activate_at_R * R_in_atr * atr_value
        trail_distance = rule.trail_width_R * R_in_atr * atr_value
    """
    if not regime or not side:
        return _GLOBAL_FALLBACK
    return _CELL_EXIT_RULES.get((regime.lower(), side.upper()), _GLOBAL_FALLBACK)


def all_rules() -> dict[tuple[str, str], CellExitRule]:
    """Read-only copy of the full table (for audits/logging)."""
    return dict(_CELL_EXIT_RULES)


# Self-check
if __name__ == "__main__":
    print(f"CELL_EXIT_RULES_ENABLED={is_enabled()}")
    for (r, s), rule in all_rules().items():
        print(f"  {r:10s} {s:5s}  activate={rule.activate_at_R}R trail={rule.trail_width_R}R  "
              f"R={rule.r_atr}xATR  n={rule.n_trades}  "
              f"ev={rule.ev_atr_per_trade:+.2f}ATR  delta_vs_base={rule.ev_delta_vs_baseline_atr:+.3f}")
    print(f"FALLBACK: activate={_GLOBAL_FALLBACK.activate_at_R}R trail={_GLOBAL_FALLBACK.trail_width_R}R R={_GLOBAL_FALLBACK.r_atr}")
