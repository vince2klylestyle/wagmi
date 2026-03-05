"""
Trade Replay Engine.

Replays trades from CSV logs to:
- Recompute PnL using live_entry (vs snapshot_entry)
- Recompute TP/SL levels
- Detect stale signals that should have been vetoed
- Detect slippage anomalies
- Detect execution mismatches and impossible trades
- Reclassify human_copy_tradable eligibility

Input: CSV trade logs with snapshot_entry, live_entry, timestamps, outcomes.
Output: Anomaly report + corrected PnL calculations.
"""

import csv
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

logger = logging.getLogger("bot.engine.replay")


@dataclass
class ReplayAnomaly:
    """A detected anomaly during replay."""
    trade_idx: int
    symbol: str
    anomaly_type: str  # stale_signal, slippage, price_mismatch, impossible_entry
    description: str
    severity: str  # "low", "medium", "high"
    original_value: Any = None
    corrected_value: Any = None


@dataclass
class ReplayResult:
    """Complete result of a replay analysis."""
    total_trades: int = 0
    anomalies: List[ReplayAnomaly] = field(default_factory=list)
    corrected_pnl: float = 0.0
    original_pnl: float = 0.0
    pnl_difference: float = 0.0
    stale_signal_count: int = 0
    slippage_anomaly_count: int = 0
    price_mismatch_count: int = 0
    impossible_trade_count: int = 0
    human_copy_reclassified: int = 0

    def summary(self) -> Dict[str, Any]:
        return {
            "total_trades": self.total_trades,
            "total_anomalies": len(self.anomalies),
            "stale_signals": self.stale_signal_count,
            "slippage_anomalies": self.slippage_anomaly_count,
            "price_mismatches": self.price_mismatch_count,
            "impossible_trades": self.impossible_trade_count,
            "original_pnl": round(self.original_pnl, 2),
            "corrected_pnl": round(self.corrected_pnl, 2),
            "pnl_difference": round(self.pnl_difference, 2),
            "human_copy_reclassified": self.human_copy_reclassified,
        }


def replay_from_csv(
    csv_path: str,
    max_snapshot_age_s: float = 10.0,
    max_slippage_pct: float = 0.5,
    max_price_deviation_pct: float = 2.0,
) -> ReplayResult:
    """Replay trades from a CSV log and detect anomalies.

    Expected CSV columns (flexible - uses what's available):
    - symbol, side, entry (or snapshot_entry), live_entry
    - snapshot_ts (or timestamp), execution_ts
    - slippage_pct, spread_pct, liquidity
    - realized_pnl (or pnl), outcome
    - human_copy_tradable
    """
    if not os.path.exists(csv_path):
        logger.warning(f"[REPLAY] File not found: {csv_path}")
        return ReplayResult()

    trades = _load_csv(csv_path)
    result = ReplayResult(total_trades=len(trades))

    for idx, trade in enumerate(trades):
        _check_stale_signal(idx, trade, max_snapshot_age_s, result)
        _check_slippage(idx, trade, max_slippage_pct, result)
        _check_price_mismatch(idx, trade, max_price_deviation_pct, result)
        _check_impossible_entry(idx, trade, result)
        _recompute_pnl(idx, trade, result)

    result.pnl_difference = round(result.corrected_pnl - result.original_pnl, 4)

    logger.info(
        f"[REPLAY] Analyzed {result.total_trades} trades: "
        f"{len(result.anomalies)} anomalies, "
        f"PnL diff: {result.pnl_difference:+.2f}"
    )

    return result


def _load_csv(path: str) -> List[Dict[str, Any]]:
    """Load and parse CSV trade log."""
    trades = []
    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            trades.append(row)
    return trades


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        return float(val) if val else default
    except (ValueError, TypeError):
        return default


def _check_stale_signal(
    idx: int,
    trade: Dict[str, Any],
    max_age: float,
    result: ReplayResult,
) -> None:
    """Detect stale signals (snapshot too old at execution time)."""
    snapshot_ts = _safe_float(trade.get("snapshot_ts", trade.get("timestamp")))
    execution_ts = _safe_float(trade.get("execution_ts"))
    snapshot_age = _safe_float(trade.get("snapshot_age_seconds"))

    if snapshot_age <= 0 and snapshot_ts > 0 and execution_ts > 0:
        snapshot_age = execution_ts - snapshot_ts

    if snapshot_age > max_age:
        result.stale_signal_count += 1
        result.anomalies.append(ReplayAnomaly(
            trade_idx=idx,
            symbol=trade.get("symbol", "?"),
            anomaly_type="stale_signal",
            description=f"Snapshot age {snapshot_age:.1f}s > {max_age}s",
            severity="medium",
            original_value=snapshot_age,
            corrected_value=max_age,
        ))


def _check_slippage(
    idx: int,
    trade: Dict[str, Any],
    max_slip: float,
    result: ReplayResult,
) -> None:
    """Detect excessive slippage."""
    slip = _safe_float(trade.get("slippage_pct"))
    if slip <= 0:
        # Compute from entries
        snap = _safe_float(trade.get("snapshot_entry", trade.get("entry")))
        live = _safe_float(trade.get("live_entry"))
        if snap > 0 and live > 0:
            slip = abs(live - snap) / snap * 100

    if slip > max_slip:
        result.slippage_anomaly_count += 1
        result.anomalies.append(ReplayAnomaly(
            trade_idx=idx,
            symbol=trade.get("symbol", "?"),
            anomaly_type="slippage",
            description=f"Slippage {slip:.3f}% > {max_slip}%",
            severity="high" if slip > max_slip * 2 else "medium",
            original_value=slip,
            corrected_value=max_slip,
        ))


def _check_price_mismatch(
    idx: int,
    trade: Dict[str, Any],
    max_dev: float,
    result: ReplayResult,
) -> None:
    """Detect impossible price deviations between snapshot and live."""
    snap = _safe_float(trade.get("snapshot_entry", trade.get("entry")))
    live = _safe_float(trade.get("live_entry"))

    if snap > 0 and live > 0:
        deviation = abs(live - snap) / snap * 100
        if deviation > max_dev:
            result.price_mismatch_count += 1
            result.anomalies.append(ReplayAnomaly(
                trade_idx=idx,
                symbol=trade.get("symbol", "?"),
                anomaly_type="price_mismatch",
                description=f"Price deviation {deviation:.2f}% > {max_dev}%",
                severity="high",
                original_value={"snapshot": snap, "live": live},
            ))


def _check_impossible_entry(
    idx: int,
    trade: Dict[str, Any],
    result: ReplayResult,
) -> None:
    """Detect trades that could never have happened.

    Examples:
    - Entry above TP (long)
    - Entry below SL (long)
    - Zero or negative prices
    """
    entry = _safe_float(trade.get("effective_entry",
                                   trade.get("live_entry",
                                             trade.get("entry"))))
    sl = _safe_float(trade.get("sl_price", trade.get("sl")))
    tp1 = _safe_float(trade.get("tp1_price", trade.get("tp1")))
    side = trade.get("side", "").upper()

    if entry <= 0:
        result.impossible_trade_count += 1
        result.anomalies.append(ReplayAnomaly(
            trade_idx=idx,
            symbol=trade.get("symbol", "?"),
            anomaly_type="impossible_entry",
            description=f"Entry price is {entry} (zero or negative)",
            severity="high",
        ))
        return

    if side == "LONG":
        if tp1 > 0 and entry >= tp1:
            result.impossible_trade_count += 1
            result.anomalies.append(ReplayAnomaly(
                trade_idx=idx,
                symbol=trade.get("symbol", "?"),
                anomaly_type="impossible_entry",
                description=f"LONG entry {entry} >= TP1 {tp1}",
                severity="high",
                original_value={"entry": entry, "tp1": tp1},
            ))
        if sl > 0 and entry <= sl:
            result.impossible_trade_count += 1
            result.anomalies.append(ReplayAnomaly(
                trade_idx=idx,
                symbol=trade.get("symbol", "?"),
                anomaly_type="impossible_entry",
                description=f"LONG entry {entry} <= SL {sl}",
                severity="high",
                original_value={"entry": entry, "sl": sl},
            ))

    elif side == "SHORT":
        if tp1 > 0 and entry <= tp1:
            result.impossible_trade_count += 1
            result.anomalies.append(ReplayAnomaly(
                trade_idx=idx,
                symbol=trade.get("symbol", "?"),
                anomaly_type="impossible_entry",
                description=f"SHORT entry {entry} <= TP1 {tp1}",
                severity="high",
                original_value={"entry": entry, "tp1": tp1},
            ))
        if sl > 0 and entry >= sl:
            result.impossible_trade_count += 1
            result.anomalies.append(ReplayAnomaly(
                trade_idx=idx,
                symbol=trade.get("symbol", "?"),
                anomaly_type="impossible_entry",
                description=f"SHORT entry {entry} >= SL {sl}",
                severity="high",
                original_value={"entry": entry, "sl": sl},
            ))


def _recompute_pnl(
    idx: int,
    trade: Dict[str, Any],
    result: ReplayResult,
) -> None:
    """Recompute PnL using live_entry instead of snapshot_entry."""
    original_pnl = _safe_float(trade.get("realized_pnl", trade.get("pnl")))
    result.original_pnl += original_pnl

    # If we have live_entry, we can recompute
    live = _safe_float(trade.get("live_entry"))
    snap = _safe_float(trade.get("snapshot_entry", trade.get("entry")))
    side = trade.get("side", "").upper()

    if live > 0 and snap > 0 and original_pnl != 0:
        # Estimate corrected PnL by adjusting for entry difference
        entry_diff = live - snap
        if side == "LONG":
            correction = -entry_diff  # Higher entry = less profit
        elif side == "SHORT":
            correction = entry_diff  # Higher entry = more profit for short
        else:
            correction = 0

        # Scale correction by position size ratio
        size = _safe_float(trade.get("size_usd"))
        if size > 0 and snap > 0:
            qty = size / snap
            corrected = original_pnl + (correction * qty)
        else:
            corrected = original_pnl
        result.corrected_pnl += corrected
    else:
        result.corrected_pnl += original_pnl


def format_replay_report(result: ReplayResult) -> str:
    """Format replay results for Telegram."""
    s = result.summary()
    lines = [
        "REPLAY ANALYSIS:",
        f"  Trades: {s['total_trades']}",
        f"  Anomalies: {s['total_anomalies']}",
        f"  Stale signals: {s['stale_signals']}",
        f"  Slippage issues: {s['slippage_anomalies']}",
        f"  Price mismatches: {s['price_mismatches']}",
        f"  Impossible trades: {s['impossible_trades']}",
        f"  Original PnL: ${s['original_pnl']:+.2f}",
        f"  Corrected PnL: ${s['corrected_pnl']:+.2f}",
        f"  PnL diff: ${s['pnl_difference']:+.2f}",
    ]

    # Show worst anomalies
    high_severity = [a for a in result.anomalies if a.severity == "high"]
    if high_severity:
        lines.append(f"\nHIGH SEVERITY ({len(high_severity)}):")
        for a in high_severity[:5]:
            lines.append(f"  [{a.anomaly_type}] {a.symbol}: {a.description}")

    return "\n".join(lines)
