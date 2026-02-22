"""
LLM evaluation and tuning configuration.

Centralizes all thresholds used by the analytics suite so they
can be tweaked without touching core metric logic.
"""

# ── Confidence buckets for calibration analysis ──────────────
CONFIDENCE_BUCKETS = [
    (0.0, 0.4, "low"),
    (0.4, 0.6, "medium"),
    (0.6, 0.8, "high"),
    (0.8, 1.01, "very_high"),  # 1.01 to include 1.0
]

# ── Time-based matching windows ──────────────────────────────

# When joining LLM decisions to trades, max seconds between
# the LLM call and the trade open/close for them to be "matched".
PRE_TRADE_MATCH_WINDOW_S = 120   # LLM pre-trade -> trade open within 2 min
PRE_CLOSE_MATCH_WINDOW_S = 120   # LLM pre-close -> trade close within 2 min
GENERAL_MATCH_WINDOW_S = 300     # Any LLM call -> nearest trade within 5 min

# ── Minimum thresholds for reporting ─────────────────────────

# Skip regime/trigger stats with fewer samples than this
MIN_SAMPLES_FOR_STATS = 3

# Ignore dust PnL below this for signal quality analysis
MIN_PNL_ABS_FOR_SIGNAL = 0.01  # $0.01

# ── Regime labels ────────────────────────────────────────────
VALID_REGIMES = [
    "trend",
    "range",
    "panic",
    "high_volatility",
    "low_liquidity",
    "news_dislocation",
    "unknown",
]

# ── Trigger labels (must match triggers.py TRIGGER_LABELS values) ──
VALID_TRIGGERS = [
    "pre-trade validation",
    "pre-close assessment",
    "position closed",
    "regime shift",
    "high-confidence signal",
    "strategy consensus",
    "strategy disagreement",
    "cross-market divergence",
    "memory-worthy event",
    "periodic update",
]

# ── Mode progression thresholds ──────────────────────────────
# Guidance: when these metrics are met over N decisions,
# it's reasonable to consider upgrading to the next mode.

MODE_PROGRESSION = {
    "ADVISORY_to_SIZING": {
        "min_decisions": 200,
        "min_action_accuracy": 0.55,      # LLM action matches trade outcome >55%
        "min_confidence_correlation": 0.1, # positive correlation between conf and PnL
        "max_regime_flip_rate": 0.40,      # regime doesn't flip every call
    },
    "SIZING_to_DIRECTION": {
        "min_decisions": 500,
        "min_sizing_improvement": 0.02,    # 2% better avg PnL vs baseline
        "min_action_accuracy": 0.58,
    },
    "DIRECTION_to_FULL": {
        "min_decisions": 1000,
        "min_veto_accuracy": 0.60,         # flat calls that avoided losses
        "min_flip_accuracy": 0.55,         # direction flips that were correct
    },
}

# ── Plot settings ────────────────────────────────────────────
PLOT_DPI = 150
PLOT_FIGSIZE = (12, 6)
PLOT_STYLE = "seaborn-v0_8-darkgrid"  # matplotlib style
