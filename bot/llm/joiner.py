"""
Joins LLM decision logs (JSONL) with trade logs (CSV).

Produces a unified view where each LLM decision is optionally
matched to the trade that occurred nearby in time + symbol.
"""

import csv
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from llm.config_eval import (
    PRE_TRADE_MATCH_WINDOW_S,
    PRE_CLOSE_MATCH_WINDOW_S,
    GENERAL_MATCH_WINDOW_S,
)

logger = logging.getLogger("bot.llm.joiner")


# ── Data classes ─────────────────────────────────────────────

@dataclass
class LLMDecisionRecord:
    """One parsed row from decisions.jsonl."""
    ts: float
    action: str                   # "long", "short", "flat", "api_error", "validation_failed"
    confidence: float = 0.0
    regime: str = ""
    allowed: bool = True
    gate_reason: str = ""
    notes: str = ""
    memory_update: str = ""
    strategy_weights: Dict[str, float] = field(default_factory=dict)
    mode: str = ""
    trigger_reason: str = ""
    trigger_context: str = ""
    usage: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)  # full original record


@dataclass
class TradeRecord:
    """One parsed row from trades.csv."""
    timestamp: str               # ISO datetime string
    ts: float = 0.0              # unix timestamp (computed)
    symbol: str = ""
    side: str = ""               # "long" / "short"
    entry: float = 0.0
    exit: float = 0.0
    pnl: float = 0.0
    fees: float = 0.0
    state_path: str = ""
    outcome: str = ""
    leverage: float = 1.0
    confidence: float = 0.0
    strategy: str = ""
    entry_type: str = ""
    primary_driver: str = ""
    regime: str = ""
    volatility_band: str = ""
    entry_reasons: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class JoinedRecord:
    """An LLM decision optionally matched to a trade."""
    decision: LLMDecisionRecord
    trade: Optional[TradeRecord] = None
    match_type: str = ""          # "pre_trade", "pre_close", "general", ""
    match_delta_s: float = 0.0    # seconds between decision and trade


# ── Loaders ──────────────────────────────────────────────────

def load_decisions(path: str) -> List[LLMDecisionRecord]:
    """Load LLM decisions from a JSONL file."""
    records = []
    if not os.path.exists(path):
        logger.warning(f"Decision log not found: {path}")
        return records

    with open(path, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError as e:
                logger.warning(f"[joiner] Bad JSON at line {line_num}: {e}")
                continue

            # Skip non-decision entries (api_error, validation_failed)
            action = d.get("action", "")
            if action in ("api_error", "validation_failed"):
                records.append(LLMDecisionRecord(
                    ts=d.get("ts", 0),
                    action=action,
                    raw=d,
                ))
                continue

            records.append(LLMDecisionRecord(
                ts=d.get("ts", 0),
                action=action,
                confidence=d.get("confidence", 0),
                regime=d.get("regime", ""),
                allowed=d.get("allowed", True),
                gate_reason=d.get("gate_reason", ""),
                notes=d.get("notes", ""),
                memory_update=d.get("memory_update", "") or "",
                strategy_weights=d.get("strategy_weights", {}),
                mode=d.get("mode", ""),
                trigger_reason=d.get("trigger_reason", ""),
                trigger_context=d.get("trigger_context", ""),
                usage=d.get("usage", {}),
                raw=d,
            ))

    return records


def load_trades(path: str) -> List[TradeRecord]:
    """Load trades from CSV file."""
    records = []
    if not os.path.exists(path):
        logger.warning(f"Trade log not found: {path}")
        return records

    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts_str = row.get("timestamp", "")
            ts_float = 0.0
            if ts_str:
                try:
                    dt = datetime.fromisoformat(ts_str)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    ts_float = dt.timestamp()
                except (ValueError, TypeError):
                    pass

            records.append(TradeRecord(
                timestamp=ts_str,
                ts=ts_float,
                symbol=row.get("symbol", ""),
                side=row.get("side", "").lower(),
                entry=_safe_float(row.get("entry", 0)),
                exit=_safe_float(row.get("exit", 0)),
                pnl=_safe_float(row.get("pnl", 0)),
                fees=_safe_float(row.get("fees", 0)),
                state_path=row.get("state_path", ""),
                outcome=row.get("outcome", ""),
                leverage=_safe_float(row.get("leverage", 1)),
                confidence=_safe_float(row.get("confidence", 0)),
                strategy=row.get("strategy", ""),
                entry_type=row.get("entry_type", ""),
                primary_driver=row.get("primary_driver", ""),
                regime=row.get("regime", ""),
                volatility_band=row.get("volatility_band", ""),
                entry_reasons=row.get("entry_reasons", ""),
                raw=dict(row),
            ))

    return records


def _safe_float(v, default=0.0) -> float:
    try:
        return float(v) if v else default
    except (ValueError, TypeError):
        return default


# ── Join logic ───────────────────────────────────────────────

def join_decisions_trades(
    decisions: List[LLMDecisionRecord],
    trades: List[TradeRecord],
) -> List[JoinedRecord]:
    """Join LLM decisions to trades by time proximity.

    For each decision:
      1. If trigger_reason contains "pre-trade" -> match to trade that opened
         within PRE_TRADE_MATCH_WINDOW_S after the decision.
      2. If trigger_reason contains "pre-close" -> match to trade that closed
         within PRE_CLOSE_MATCH_WINDOW_S after the decision.
      3. Otherwise -> match to nearest trade within GENERAL_MATCH_WINDOW_S.

    Trades may be matched to multiple decisions (many-to-many).
    """
    joined = []

    # Sort trades by timestamp for binary-search-like matching
    sorted_trades = sorted(trades, key=lambda t: t.ts)

    for dec in decisions:
        # Skip errors
        if dec.action in ("api_error", "validation_failed"):
            joined.append(JoinedRecord(decision=dec))
            continue

        trigger = dec.trigger_reason.lower() if dec.trigger_reason else ""

        # Determine match window
        if "pre-trade" in trigger or "pre_trade" in trigger:
            window = PRE_TRADE_MATCH_WINDOW_S
            match_type = "pre_trade"
        elif "pre-close" in trigger or "pre_close" in trigger:
            window = PRE_CLOSE_MATCH_WINDOW_S
            match_type = "pre_close"
        else:
            window = GENERAL_MATCH_WINDOW_S
            match_type = "general"

        # Find best matching trade
        best_trade = None
        best_delta = float("inf")

        for trade in sorted_trades:
            delta = trade.ts - dec.ts
            # For pre-trade: trade should open AFTER the decision
            if match_type == "pre_trade" and delta < 0:
                continue
            # For pre-close: trade should close AFTER the decision
            if match_type == "pre_close" and delta < 0:
                continue

            abs_delta = abs(delta)
            if abs_delta <= window and abs_delta < best_delta:
                best_delta = abs_delta
                best_trade = trade

        joined.append(JoinedRecord(
            decision=dec,
            trade=best_trade,
            match_type=match_type if best_trade else "",
            match_delta_s=best_delta if best_trade else 0,
        ))

    return joined


# ── Convenience loaders ──────────────────────────────────────

def load_session(
    decisions_path: str = "data/llm/decisions.jsonl",
    trades_path: str = "data/trades.csv",
) -> List[JoinedRecord]:
    """Load and join all data for a session."""
    decisions = load_decisions(decisions_path)
    trades = load_trades(trades_path)
    return join_decisions_trades(decisions, trades)


def load_today() -> List[JoinedRecord]:
    """Load today's session data using default paths."""
    return load_session()
