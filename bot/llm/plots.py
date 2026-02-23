"""
Optional matplotlib-based plots for LLM evaluation.

All imports are guarded - if matplotlib is not installed,
functions return gracefully with a warning.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger("bot.llm.plots")

_HAS_MPL = False
try:
    import matplotlib
    matplotlib.use("Agg")  # non-interactive backend
    import matplotlib.pyplot as plt
    _HAS_MPL = True
except ImportError:
    pass

from llm.config_eval import CONFIDENCE_BUCKETS, PLOT_DPI, PLOT_FIGSIZE, MIN_SAMPLES_FOR_STATS


def _check_mpl():
    if not _HAS_MPL:
        logger.warning("matplotlib not installed - skipping plots (pip install matplotlib)")
        return False
    return True


def plot_confidence_vs_pnl(result, output_dir: str = "data/llm/plots") -> Optional[str]:
    """Scatter plot: LLM confidence vs trade PnL."""
    if not _check_mpl():
        return None

    os.makedirs(output_dir, exist_ok=True)

    confs = []
    pnls = []
    colors = []

    for jr in result.joined_records:
        if jr.trade and jr.trade.pnl != 0 and jr.decision.confidence > 0:
            confs.append(jr.decision.confidence)
            pnls.append(jr.trade.pnl)
            colors.append("green" if jr.trade.pnl > 0 else "red")

    if len(confs) < 3:
        logger.info("Not enough data points for confidence vs PnL plot")
        return None

    fig, ax = plt.subplots(figsize=PLOT_FIGSIZE)
    ax.scatter(confs, pnls, c=colors, alpha=0.6, edgecolors="black", linewidth=0.5)
    ax.axhline(y=0, color="gray", linestyle="--", linewidth=0.8)
    ax.set_xlabel("LLM Confidence")
    ax.set_ylabel("Trade PnL ($)")
    ax.set_title("LLM Confidence vs Trade PnL")
    ax.set_xlim(0, 1.05)

    path = os.path.join(output_dir, "confidence_vs_pnl.png")
    fig.savefig(path, dpi=PLOT_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Plot saved: {path}")
    return path


def plot_regime_performance(result, output_dir: str = "data/llm/plots") -> Optional[str]:
    """Bar chart: average PnL per regime."""
    if not _check_mpl():
        return None

    os.makedirs(output_dir, exist_ok=True)

    regimes = []
    avg_pnls = []
    counts = []
    bar_colors = []

    for regime, stats in sorted(result.regime_stats.items()):
        if stats.matched < MIN_SAMPLES_FOR_STATS:
            continue
        regimes.append(regime)
        avg_pnls.append(stats.avg_pnl)
        counts.append(stats.matched)
        bar_colors.append("green" if stats.avg_pnl >= 0 else "red")

    if not regimes:
        logger.info("Not enough data for regime performance plot")
        return None

    fig, ax = plt.subplots(figsize=PLOT_FIGSIZE)
    bars = ax.bar(regimes, avg_pnls, color=bar_colors, edgecolor="black", linewidth=0.5)
    ax.axhline(y=0, color="gray", linestyle="--", linewidth=0.8)
    ax.set_xlabel("Regime")
    ax.set_ylabel("Average PnL ($)")
    ax.set_title("Average PnL by LLM Regime Classification")

    # Add count labels on bars
    for bar, count in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                f"n={count}", ha="center", va="bottom", fontsize=8)

    plt.xticks(rotation=30, ha="right")

    path = os.path.join(output_dir, "regime_performance.png")
    fig.savefig(path, dpi=PLOT_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Plot saved: {path}")
    return path


def plot_trigger_performance(result, output_dir: str = "data/llm/plots") -> Optional[str]:
    """Bar chart: win rate and avg PnL per trigger type."""
    if not _check_mpl():
        return None

    os.makedirs(output_dir, exist_ok=True)

    triggers = []
    win_rates = []
    avg_pnls = []

    for trigger, stats in sorted(result.trigger_stats.items()):
        if stats.matched < MIN_SAMPLES_FOR_STATS:
            continue
        triggers.append(trigger[:25])  # truncate long names
        win_rates.append(stats.win_rate)
        avg_pnls.append(stats.avg_pnl)

    if not triggers:
        logger.info("Not enough data for trigger performance plot")
        return None

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(PLOT_FIGSIZE[0] * 1.5, PLOT_FIGSIZE[1]))

    # Win rate bars
    colors1 = ["green" if wr >= 50 else "red" for wr in win_rates]
    ax1.barh(triggers, win_rates, color=colors1, edgecolor="black", linewidth=0.5)
    ax1.axvline(x=50, color="gray", linestyle="--", linewidth=0.8)
    ax1.set_xlabel("Win Rate (%)")
    ax1.set_title("Win Rate by Trigger Type")
    ax1.set_xlim(0, 100)

    # Avg PnL bars
    colors2 = ["green" if p >= 0 else "red" for p in avg_pnls]
    ax2.barh(triggers, avg_pnls, color=colors2, edgecolor="black", linewidth=0.5)
    ax2.axvline(x=0, color="gray", linestyle="--", linewidth=0.8)
    ax2.set_xlabel("Average PnL ($)")
    ax2.set_title("Average PnL by Trigger Type")

    plt.tight_layout()

    path = os.path.join(output_dir, "trigger_performance.png")
    fig.savefig(path, dpi=PLOT_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Plot saved: {path}")
    return path


def plot_confidence_calibration(result, output_dir: str = "data/llm/plots") -> Optional[str]:
    """Bar chart: win rate per confidence bucket."""
    if not _check_mpl():
        return None

    os.makedirs(output_dir, exist_ok=True)

    labels = []
    win_rates = []
    counts = []

    for lo, hi, label in CONFIDENCE_BUCKETS:
        stats = result.confidence_stats.get(label)
        if stats and stats.matched > 0:
            labels.append(f"[{lo:.1f}-{hi:.1f})")
            win_rates.append(stats.win_rate)
            counts.append(stats.matched)

    if not labels:
        logger.info("Not enough data for confidence calibration plot")
        return None

    fig, ax = plt.subplots(figsize=PLOT_FIGSIZE)
    colors = ["green" if wr >= 50 else "orange" if wr >= 40 else "red" for wr in win_rates]
    bars = ax.bar(labels, win_rates, color=colors, edgecolor="black", linewidth=0.5)
    ax.axhline(y=50, color="gray", linestyle="--", linewidth=0.8, label="50% baseline")
    ax.set_xlabel("Confidence Bucket")
    ax.set_ylabel("Win Rate (%)")
    ax.set_title("Confidence Calibration: Win Rate by Confidence Level")
    ax.set_ylim(0, 100)
    ax.legend()

    for bar, count in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"n={count}", ha="center", va="bottom", fontsize=9)

    path = os.path.join(output_dir, "confidence_calibration.png")
    fig.savefig(path, dpi=PLOT_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Plot saved: {path}")
    return path


def plot_decisions_timeline(result, output_dir: str = "data/llm/plots") -> Optional[str]:
    """Timeline: LLM decisions over time with confidence + PnL."""
    if not _check_mpl():
        return None

    os.makedirs(output_dir, exist_ok=True)

    from datetime import datetime, timezone

    timestamps = []
    confidences = []
    pnls = []
    actions = []

    for jr in result.joined_records:
        d = jr.decision
        if d.action in ("api_error", "validation_failed"):
            continue
        if d.ts <= 0:
            continue
        try:
            dt = datetime.fromtimestamp(d.ts, tz=timezone.utc)
        except (ValueError, OSError):
            continue
        timestamps.append(dt)
        confidences.append(d.confidence)
        pnls.append(jr.trade.pnl if jr.trade else 0)
        actions.append(d.action)

    if len(timestamps) < 3:
        logger.info("Not enough data for timeline plot")
        return None

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=PLOT_FIGSIZE, sharex=True)

    # Confidence over time
    action_colors = {"long": "green", "short": "red", "flat": "gray"}
    colors = [action_colors.get(a.lower(), "blue") for a in actions]
    ax1.scatter(timestamps, confidences, c=colors, alpha=0.6, s=20)
    ax1.set_ylabel("Confidence")
    ax1.set_title("LLM Decisions Timeline")
    ax1.set_ylim(0, 1.05)

    # PnL over time
    pnl_colors = ["green" if p > 0 else "red" if p < 0 else "gray" for p in pnls]
    ax2.bar(timestamps, pnls, color=pnl_colors, alpha=0.7, width=0.001)
    ax2.axhline(y=0, color="gray", linestyle="--", linewidth=0.5)
    ax2.set_ylabel("Trade PnL ($)")
    ax2.set_xlabel("Time (UTC)")

    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()

    path = os.path.join(output_dir, "decisions_timeline.png")
    fig.savefig(path, dpi=PLOT_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Plot saved: {path}")
    return path


def generate_all_plots(result, output_dir: str = "data/llm/plots") -> list:
    """Generate all available plots. Returns list of saved paths."""
    if not _check_mpl():
        return []

    paths = []
    for fn in [
        plot_confidence_vs_pnl,
        plot_regime_performance,
        plot_trigger_performance,
        plot_confidence_calibration,
        plot_decisions_timeline,
    ]:
        try:
            path = fn(result, output_dir)
            if path:
                paths.append(path)
        except Exception as e:
            logger.warning(f"Plot generation failed ({fn.__name__}): {e}")
    return paths
