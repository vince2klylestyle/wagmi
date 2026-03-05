"""
Core metric computations for LLM evaluation.

Takes joined records (LLM decisions + trades) and computes:
  - Regime accuracy / distribution
  - Action vs outcome (win rate, avg PnL per LLM action)
  - Confidence calibration
  - Regime-conditioned performance
  - Trigger-conditioned performance
  - Regret analysis (veto value, flip value)
  - Mode comparison (future)
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from llm.joiner import JoinedRecord, LLMDecisionRecord, TradeRecord
from llm.config_eval import (
    CONFIDENCE_BUCKETS,
    MIN_SAMPLES_FOR_STATS,
    MIN_PNL_ABS_FOR_SIGNAL,
    VALID_REGIMES,
    VALID_TRIGGERS,
)

logger = logging.getLogger("bot.llm.metrics")


# ── Helpers ──────────────────────────────────────────────────

def _win(pnl: float) -> bool:
    return pnl > MIN_PNL_ABS_FOR_SIGNAL


def _bucket_label(confidence: float) -> str:
    for lo, hi, label in CONFIDENCE_BUCKETS:
        if lo <= confidence < hi:
            return label
    return "unknown"


def _safe_pct(num: int, den: int) -> float:
    return (num / den * 100) if den > 0 else 0.0


# ── Result data classes ──────────────────────────────────────

@dataclass
class BucketStats:
    """Stats for a confidence bucket or category."""
    count: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    pnl_values: List[float] = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        return _safe_pct(self.wins, self.wins + self.losses)

    @property
    def avg_pnl(self) -> float:
        return self.total_pnl / self.count if self.count > 0 else 0.0

    @property
    def matched(self) -> int:
        return self.wins + self.losses


@dataclass
class RegretStats:
    """Regret analysis: trades LLM would have affected."""
    vetoed_would_lose: int = 0    # flat calls that avoided losses (good veto)
    vetoed_would_win: int = 0     # flat calls that missed wins (bad veto)
    flipped_correct: int = 0      # direction flips that improved outcome
    flipped_wrong: int = 0        # direction flips that worsened outcome
    total_flat_calls: int = 0
    total_flip_opportunities: int = 0


@dataclass
class AnalysisResult:
    """Full analysis result."""
    # Summary
    total_decisions: int = 0
    total_trades: int = 0
    matched_count: int = 0
    error_count: int = 0
    gated_count: int = 0
    modes_used: List[str] = field(default_factory=list)

    # Regime distribution
    regime_dist: Dict[str, int] = field(default_factory=dict)
    regime_flip_count: int = 0    # how many times regime changed vs prior call

    # Action vs outcome
    action_stats: Dict[str, BucketStats] = field(default_factory=dict)

    # Confidence calibration
    confidence_stats: Dict[str, BucketStats] = field(default_factory=dict)

    # Regime-conditioned
    regime_stats: Dict[str, BucketStats] = field(default_factory=dict)

    # Trigger-conditioned
    trigger_stats: Dict[str, BucketStats] = field(default_factory=dict)

    # Regret
    regret: RegretStats = field(default_factory=RegretStats)

    # Token usage
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    estimated_cost_usd: float = 0.0

    # Raw data for downstream
    joined_records: List[JoinedRecord] = field(default_factory=list)


# ── Main analysis function ───────────────────────────────────

def compute_metrics(joined: List[JoinedRecord]) -> AnalysisResult:
    """Compute all metrics from joined records."""
    result = AnalysisResult()
    result.joined_records = joined
    result.total_decisions = len(joined)

    # Track unique trades
    trade_ids = set()
    modes = set()
    prev_regime = None

    for jr in joined:
        dec = jr.decision

        # Count errors
        if dec.action in ("api_error", "validation_failed"):
            result.error_count += 1
            continue

        # Count gated
        if not dec.allowed:
            result.gated_count += 1

        # Mode tracking
        if dec.mode:
            modes.add(dec.mode)

        # Token usage
        if dec.usage:
            result.total_input_tokens += dec.usage.get("input_tokens", 0)
            result.total_output_tokens += dec.usage.get("output_tokens", 0)

        # Regime distribution
        regime = dec.regime or "unknown"
        result.regime_dist[regime] = result.regime_dist.get(regime, 0) + 1

        # Regime flip detection
        if prev_regime is not None and regime != prev_regime:
            result.regime_flip_count += 1
        prev_regime = regime

        # Track trade
        if jr.trade:
            t_id = f"{jr.trade.timestamp}_{jr.trade.symbol}"
            if t_id not in trade_ids:
                trade_ids.add(t_id)
            result.matched_count += 1

        # ── Action vs outcome ──
        action = dec.action.lower() if dec.action else "unknown"
        if action not in result.action_stats:
            result.action_stats[action] = BucketStats()
        result.action_stats[action].count += 1

        if jr.trade and jr.trade.pnl != 0:
            pnl = jr.trade.pnl
            w = _win(pnl)
            result.action_stats[action].total_pnl += pnl
            result.action_stats[action].pnl_values.append(pnl)
            if w:
                result.action_stats[action].wins += 1
            else:
                result.action_stats[action].losses += 1

        # ── Confidence calibration ──
        bucket = _bucket_label(dec.confidence)
        if bucket not in result.confidence_stats:
            result.confidence_stats[bucket] = BucketStats()
        result.confidence_stats[bucket].count += 1

        if jr.trade and jr.trade.pnl != 0:
            pnl = jr.trade.pnl
            w = _win(pnl)
            result.confidence_stats[bucket].total_pnl += pnl
            result.confidence_stats[bucket].pnl_values.append(pnl)
            if w:
                result.confidence_stats[bucket].wins += 1
            else:
                result.confidence_stats[bucket].losses += 1

        # ── Regime-conditioned ──
        if regime not in result.regime_stats:
            result.regime_stats[regime] = BucketStats()
        result.regime_stats[regime].count += 1

        if jr.trade and jr.trade.pnl != 0:
            pnl = jr.trade.pnl
            w = _win(pnl)
            result.regime_stats[regime].total_pnl += pnl
            result.regime_stats[regime].pnl_values.append(pnl)
            if w:
                result.regime_stats[regime].wins += 1
            else:
                result.regime_stats[regime].losses += 1

        # ── Trigger-conditioned ──
        trigger = dec.trigger_reason or "unknown"
        if trigger not in result.trigger_stats:
            result.trigger_stats[trigger] = BucketStats()
        result.trigger_stats[trigger].count += 1

        if jr.trade and jr.trade.pnl != 0:
            pnl = jr.trade.pnl
            w = _win(pnl)
            result.trigger_stats[trigger].total_pnl += pnl
            result.trigger_stats[trigger].pnl_values.append(pnl)
            if w:
                result.trigger_stats[trigger].wins += 1
            else:
                result.trigger_stats[trigger].losses += 1

        # ── Regret analysis ──
        _compute_regret_for_record(jr, result.regret)

    result.total_trades = len(trade_ids)
    result.modes_used = sorted(modes)

    # Estimate cost (Claude Haiku pricing rough estimate)
    # $0.25/M input, $1.25/M output (haiku) - adjust for actual model
    result.estimated_cost_usd = (
        result.total_input_tokens * 0.25 / 1_000_000
        + result.total_output_tokens * 1.25 / 1_000_000
    )

    return result


def _compute_regret_for_record(jr: JoinedRecord, regret: RegretStats):
    """Compute regret metrics for a single joined record."""
    dec = jr.decision
    trade = jr.trade
    action = dec.action.lower() if dec.action else ""

    # Flat calls: what would have happened?
    if action == "flat":
        regret.total_flat_calls += 1
        if trade and trade.pnl != 0:
            if trade.pnl < 0:
                regret.vetoed_would_lose += 1  # good veto
            else:
                regret.vetoed_would_win += 1   # bad veto

    # Direction flip opportunities
    if trade and action in ("long", "short"):
        trade_side = trade.side.lower()
        if action != trade_side:
            regret.total_flip_opportunities += 1
            # If LLM said opposite and trade lost, flip would have been better
            if trade.pnl < 0:
                regret.flipped_correct += 1
            else:
                regret.flipped_wrong += 1


# ── Formatted report ─────────────────────────────────────────

def format_report(result: AnalysisResult, session_label: str = "") -> str:
    """Format a human-readable text report."""
    lines = []
    sep = "-" * 60

    lines.append(sep)
    lines.append(f"LLM ANALYSIS REPORT{f' - SESSION: {session_label}' if session_label else ''}")
    lines.append(sep)

    # Summary
    lines.append("")
    lines.append("Summary:")
    lines.append(f"  Total LLM decisions: {result.total_decisions}")
    lines.append(f"  Errors (API/validation): {result.error_count}")
    lines.append(f"  Risk-gated (rejected): {result.gated_count}")
    lines.append(f"  Modes used: {', '.join(result.modes_used) or 'N/A'}")
    lines.append(f"  Total trades in log: {result.total_trades}")
    lines.append(f"  Decisions matched to trades: {result.matched_count}")
    lines.append(f"  Token usage: {result.total_input_tokens:,} in / {result.total_output_tokens:,} out")
    lines.append(f"  Estimated cost: ${result.estimated_cost_usd:.4f}")

    # Regime distribution
    lines.append("")
    lines.append("Regime distribution:")
    total_regime = sum(result.regime_dist.values())
    for regime in VALID_REGIMES:
        count = result.regime_dist.get(regime, 0)
        pct = _safe_pct(count, total_regime)
        bar = "#" * int(pct / 2)
        lines.append(f"  {regime:20s}: {count:4d} ({pct:5.1f}%) {bar}")
    # Any extra regimes not in the standard list
    for regime, count in result.regime_dist.items():
        if regime not in VALID_REGIMES:
            pct = _safe_pct(count, total_regime)
            lines.append(f"  {regime:20s}: {count:4d} ({pct:5.1f}%)")

    flip_rate = _safe_pct(result.regime_flip_count, max(total_regime - 1, 1))
    lines.append(f"  Regime flip rate: {result.regime_flip_count} flips ({flip_rate:.1f}%)")

    # Confidence calibration
    lines.append("")
    lines.append("Confidence calibration:")
    lines.append(f"  {'Bucket':12s} | {'Count':>5s} | {'Matched':>7s} | {'WinRate':>7s} | {'AvgPnL':>8s}")
    lines.append(f"  {'-'*12}-+-{'-'*5}-+-{'-'*7}-+-{'-'*7}-+-{'-'*8}")
    for lo, hi, label in CONFIDENCE_BUCKETS:
        stats = result.confidence_stats.get(label, BucketStats())
        lines.append(
            f"  {f'[{lo:.1f}-{hi:.1f})':12s} | {stats.count:5d} | {stats.matched:7d} | "
            f"{stats.win_rate:6.1f}% | ${stats.avg_pnl:+7.2f}"
        )

    # Action vs outcome
    lines.append("")
    lines.append("Action vs outcome:")
    lines.append(f"  {'Action':10s} | {'Count':>5s} | {'Matched':>7s} | {'WinRate':>7s} | {'AvgPnL':>8s} | {'TotalPnL':>9s}")
    lines.append(f"  {'-'*10}-+-{'-'*5}-+-{'-'*7}-+-{'-'*7}-+-{'-'*8}-+-{'-'*9}")
    for action in ["long", "short", "flat"]:
        stats = result.action_stats.get(action, BucketStats())
        lines.append(
            f"  {action:10s} | {stats.count:5d} | {stats.matched:7d} | "
            f"{stats.win_rate:6.1f}% | ${stats.avg_pnl:+7.2f} | ${stats.total_pnl:+8.2f}"
        )

    # Regime-conditioned performance
    lines.append("")
    lines.append("Regime-conditioned performance:")
    lines.append(f"  {'Regime':20s} | {'Calls':>5s} | {'Matched':>7s} | {'WinRate':>7s} | {'AvgPnL':>8s}")
    lines.append(f"  {'-'*20}-+-{'-'*5}-+-{'-'*7}-+-{'-'*7}-+-{'-'*8}")
    for regime in VALID_REGIMES:
        stats = result.regime_stats.get(regime, BucketStats())
        if stats.count < MIN_SAMPLES_FOR_STATS:
            continue
        lines.append(
            f"  {regime:20s} | {stats.count:5d} | {stats.matched:7d} | "
            f"{stats.win_rate:6.1f}% | ${stats.avg_pnl:+7.2f}"
        )

    # Trigger-conditioned performance
    lines.append("")
    lines.append("Trigger-conditioned performance:")
    lines.append(f"  {'Trigger':30s} | {'Fired':>5s} | {'Matched':>7s} | {'WinRate':>7s} | {'AvgPnL':>8s}")
    lines.append(f"  {'-'*30}-+-{'-'*5}-+-{'-'*7}-+-{'-'*7}-+-{'-'*8}")
    for trigger in VALID_TRIGGERS:
        stats = result.trigger_stats.get(trigger, BucketStats())
        if stats.count == 0:
            continue
        lines.append(
            f"  {trigger:30s} | {stats.count:5d} | {stats.matched:7d} | "
            f"{stats.win_rate:6.1f}% | ${stats.avg_pnl:+7.2f}"
        )
    # Any extra triggers
    for trigger, stats in result.trigger_stats.items():
        if trigger not in VALID_TRIGGERS and stats.count > 0:
            lines.append(
                f"  {trigger:30s} | {stats.count:5d} | {stats.matched:7d} | "
                f"{stats.win_rate:6.1f}% | ${stats.avg_pnl:+7.2f}"
            )

    # Regret analysis
    lines.append("")
    lines.append("Regret analysis (hypothetical):")
    r = result.regret
    lines.append(f"  Flat (veto) calls:     {r.total_flat_calls}")
    if r.total_flat_calls > 0:
        good = r.vetoed_would_lose
        bad = r.vetoed_would_win
        lines.append(f"    Would-have-lost (good veto): {good}")
        lines.append(f"    Would-have-won (bad veto):   {bad}")
        veto_acc = _safe_pct(good, good + bad)
        lines.append(f"    Veto accuracy: {veto_acc:.1f}%")

    lines.append(f"  Direction flip opportunities: {r.total_flip_opportunities}")
    if r.total_flip_opportunities > 0:
        lines.append(f"    Correct flips: {r.flipped_correct}")
        lines.append(f"    Wrong flips:   {r.flipped_wrong}")
        flip_acc = _safe_pct(r.flipped_correct, r.flipped_correct + r.flipped_wrong)
        lines.append(f"    Flip accuracy: {flip_acc:.1f}%")

    # Observations
    lines.append("")
    lines.append("Key observations:")
    observations = _auto_observations(result)
    for obs in observations:
        lines.append(f"  - {obs}")
    if not observations:
        lines.append("  (insufficient data for automatic observations)")

    lines.append("")
    lines.append(sep)
    return "\n".join(lines)


def _auto_observations(result: AnalysisResult) -> List[str]:
    """Auto-generate notable observations from metrics."""
    obs = []

    # Confidence calibration insight
    high = result.confidence_stats.get("high", BucketStats())
    low = result.confidence_stats.get("low", BucketStats())
    if high.matched >= MIN_SAMPLES_FOR_STATS and low.matched >= MIN_SAMPLES_FOR_STATS:
        if high.win_rate > low.win_rate + 10:
            obs.append(
                f"Higher confidence correlates with better outcomes: "
                f"high={high.win_rate:.0f}% vs low={low.win_rate:.0f}% win rate"
            )
        elif low.win_rate > high.win_rate + 10:
            obs.append(
                f"WARNING: Higher confidence does NOT correlate with better outcomes: "
                f"high={high.win_rate:.0f}% vs low={low.win_rate:.0f}%"
            )

    # Best/worst regime
    best_regime = None
    worst_regime = None
    best_wr = 0
    worst_wr = 100
    for regime, stats in result.regime_stats.items():
        if stats.matched < MIN_SAMPLES_FOR_STATS:
            continue
        wr = stats.win_rate
        if wr > best_wr:
            best_wr = wr
            best_regime = regime
        if wr < worst_wr:
            worst_wr = wr
            worst_regime = regime

    if best_regime:
        obs.append(f"Best regime: '{best_regime}' ({best_wr:.0f}% win rate)")
    if worst_regime and worst_regime != best_regime:
        obs.append(f"Worst regime: '{worst_regime}' ({worst_wr:.0f}% win rate)")

    # Regime flip rate
    total = sum(result.regime_dist.values())
    if total > 10:
        flip_rate = result.regime_flip_count / max(total - 1, 1) * 100
        if flip_rate > 50:
            obs.append(f"High regime instability: {flip_rate:.0f}% flip rate (consider smoothing)")
        elif flip_rate < 10:
            obs.append(f"Very stable regime classification: {flip_rate:.0f}% flip rate")

    # Veto quality
    r = result.regret
    if r.total_flat_calls >= MIN_SAMPLES_FOR_STATS:
        total_matched = r.vetoed_would_lose + r.vetoed_would_win
        if total_matched > 0:
            veto_acc = r.vetoed_would_lose / total_matched * 100
            if veto_acc >= 60:
                obs.append(f"Veto quality is good: {veto_acc:.0f}% of vetoes avoided losses")
            elif veto_acc < 40:
                obs.append(f"Veto quality is poor: only {veto_acc:.0f}% of vetoes avoided losses")

    # Best trigger
    best_trigger = None
    best_t_wr = 0
    for trigger, stats in result.trigger_stats.items():
        if stats.matched >= MIN_SAMPLES_FOR_STATS and stats.win_rate > best_t_wr:
            best_t_wr = stats.win_rate
            best_trigger = trigger
    if best_trigger:
        obs.append(f"Highest-value trigger: '{best_trigger}' ({best_t_wr:.0f}% win rate)")

    # Error rate
    if result.error_count > 0:
        err_rate = result.error_count / max(result.total_decisions, 1) * 100
        obs.append(f"API error rate: {err_rate:.1f}% ({result.error_count} errors)")

    return obs


# ── CSV export ───────────────────────────────────────────────

def export_summary_csv(result: AnalysisResult, output_dir: str = "data/llm/reports"):
    """Export summary CSVs for further analysis."""
    import csv
    import os

    os.makedirs(output_dir, exist_ok=True)

    # 1. Confidence calibration CSV
    path = os.path.join(output_dir, "confidence_calibration.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["bucket", "count", "matched", "wins", "losses", "win_rate", "avg_pnl", "total_pnl"])
        for lo, hi, label in CONFIDENCE_BUCKETS:
            stats = result.confidence_stats.get(label, BucketStats())
            w.writerow([label, stats.count, stats.matched, stats.wins, stats.losses,
                        f"{stats.win_rate:.1f}", f"{stats.avg_pnl:.2f}", f"{stats.total_pnl:.2f}"])

    # 2. Regime stats CSV
    path = os.path.join(output_dir, "regime_stats.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["regime", "count", "matched", "wins", "losses", "win_rate", "avg_pnl", "total_pnl"])
        for regime, stats in sorted(result.regime_stats.items()):
            w.writerow([regime, stats.count, stats.matched, stats.wins, stats.losses,
                        f"{stats.win_rate:.1f}", f"{stats.avg_pnl:.2f}", f"{stats.total_pnl:.2f}"])

    # 3. Trigger stats CSV
    path = os.path.join(output_dir, "trigger_stats.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["trigger", "fired", "matched", "wins", "losses", "win_rate", "avg_pnl", "total_pnl"])
        for trigger, stats in sorted(result.trigger_stats.items()):
            w.writerow([trigger, stats.count, stats.matched, stats.wins, stats.losses,
                        f"{stats.win_rate:.1f}", f"{stats.avg_pnl:.2f}", f"{stats.total_pnl:.2f}"])

    # 4. Action stats CSV
    path = os.path.join(output_dir, "action_stats.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["action", "count", "matched", "wins", "losses", "win_rate", "avg_pnl", "total_pnl"])
        for action, stats in sorted(result.action_stats.items()):
            w.writerow([action, stats.count, stats.matched, stats.wins, stats.losses,
                        f"{stats.win_rate:.1f}", f"{stats.avg_pnl:.2f}", f"{stats.total_pnl:.2f}"])

    # 5. Full joined records CSV (for custom analysis)
    path = os.path.join(output_dir, "joined_decisions.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "ts", "action", "confidence", "regime", "allowed", "gate_reason",
            "mode", "trigger_reason", "notes",
            "trade_symbol", "trade_side", "trade_pnl", "trade_entry_type",
            "trade_strategy", "trade_outcome",
            "match_type", "match_delta_s",
        ])
        for jr in result.joined_records:
            d = jr.decision
            t = jr.trade
            w.writerow([
                f"{d.ts:.0f}", d.action, f"{d.confidence:.3f}", d.regime,
                d.allowed, d.gate_reason, d.mode, d.trigger_reason,
                d.notes[:100] if d.notes else "",
                t.symbol if t else "", t.side if t else "",
                f"{t.pnl:.2f}" if t else "", t.entry_type if t else "",
                t.strategy if t else "", t.outcome if t else "",
                jr.match_type, f"{jr.match_delta_s:.0f}",
            ])

    logger.info(f"Reports written to {output_dir}/")
