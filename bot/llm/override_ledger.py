"""
Override Ledger: Accountability for LLM-reasoned overrides.

Every time the LLM overrides a mechanical block, we log:
  - The block that was bypassed (EV, anti-roundtrip, etc.)
  - The full context the LLM saw
  - The LLM's reasoning and cited evidence
  - Which agents voted and their confidence
  - The eventual outcome (win/loss, PnL)

This enables:
  1. Post-hoc accuracy tracking: "LLM override accuracy: 67% over last 20"
  2. Auto-disable if accuracy degrades below threshold
  3. Learning: what kinds of overrides work, what kinds don't
  4. Audit trail: every override is justified and reviewable

The ledger is append-only (never mutated), stored as JSONL for easy analysis.
"""

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bot.llm.override_ledger")

LEDGER_PATH = Path("data/llm/override_ledger.jsonl")
LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class OverrideRecord:
    """One override decision, complete with context and outcome tracking."""
    override_id: str
    timestamp: float
    symbol: str
    side: str

    # What was blocked
    block_type: str  # "negative_ev", "anti_roundtrip", "circuit_breaker", etc.
    block_reason: str
    block_details: Dict[str, Any] = field(default_factory=dict)  # EV=-0.07, WP=0.34, etc.

    # Signal context
    confidence: float = 0.0
    num_strategies_agree: int = 0
    strategies_firing: List[str] = field(default_factory=list)
    regime_1h: str = ""
    regime_4h: str = ""
    regime_6h: str = ""
    volume_ratio: float = 0.0

    # Edge data the LLM saw
    edge_data: Dict[str, Any] = field(default_factory=dict)
    # e.g., {"setup_key": "HYPE_BUY", "wr": 58.3, "pf": 1.61, "n": 36, "verdict": "CONFIRMED_EDGE"}

    # LLM decision
    override_decision: str = ""  # "override" or "confirm_block"
    override_agent_confidence: float = 0.0
    override_agent_reasoning: str = ""
    evidence_cited: List[str] = field(default_factory=list)

    # Multi-agent consensus
    critic_vote: str = ""  # "agree", "challenge", "veto"
    critic_reasoning: str = ""
    risk_vote: str = ""  # "agree", "reduce_size", "veto"
    risk_reasoning: str = ""

    # Final decision
    override_approved: bool = False
    approval_reason: str = ""  # Why consensus agreed/disagreed

    # Trade outcome (filled in later when position closes)
    trade_opened: bool = False
    entry_price: float = 0.0
    exit_price: float = 0.0
    pnl: float = 0.0
    outcome: str = ""  # "pending", "win", "loss", "breakeven", "not_opened"
    resolved_at: float = 0.0


class OverrideLedger:
    """Append-only ledger of LLM-reasoned overrides with outcome tracking."""

    def __init__(self, path: Path = LEDGER_PATH):
        self.path = path
        self._records: Dict[str, OverrideRecord] = {}
        self._load()

    def _load(self):
        """Load existing ledger from disk."""
        if not self.path.exists():
            return
        try:
            with open(self.path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        rec = OverrideRecord(**data)
                        self._records[rec.override_id] = rec
                    except Exception as e:
                        logger.debug(f"Failed to parse ledger line: {e}")
            logger.info(f"[OVERRIDE-LEDGER] Loaded {len(self._records)} records")
        except Exception as e:
            logger.warning(f"[OVERRIDE-LEDGER] Load error: {e}")

    def record_override(self, record: OverrideRecord) -> str:
        """Append a new override decision to the ledger."""
        if not record.override_id:
            record.override_id = f"ov_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        if not record.timestamp:
            record.timestamp = time.time()

        self._records[record.override_id] = record
        self._append_to_disk(record)

        logger.info(
            f"[OVERRIDE-LEDGER] {record.override_id} recorded: "
            f"{record.symbol} {record.side} | block={record.block_type} | "
            f"decision={record.override_decision} | approved={record.override_approved}"
        )
        return record.override_id

    def _append_to_disk(self, record: OverrideRecord):
        """Append a single record (never rewrite the file)."""
        try:
            with open(self.path, "a") as f:
                f.write(json.dumps(asdict(record), default=str) + "\n")
        except Exception as e:
            logger.warning(f"[OVERRIDE-LEDGER] Write error: {e}")

    def resolve_outcome(
        self,
        override_id: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
    ):
        """Update a record with its trade outcome (for accuracy tracking)."""
        rec = self._records.get(override_id)
        if not rec:
            logger.warning(f"[OVERRIDE-LEDGER] Cannot resolve: {override_id} not found")
            return

        rec.entry_price = entry_price
        rec.exit_price = exit_price
        rec.pnl = pnl
        rec.resolved_at = time.time()
        if pnl > 0:
            rec.outcome = "win"
        elif pnl < 0:
            rec.outcome = "loss"
        else:
            rec.outcome = "breakeven"

        # Rewrite the file with updated record (append-only exception for resolutions)
        self._rewrite_disk()
        logger.info(
            f"[OVERRIDE-LEDGER] {override_id} resolved: "
            f"{rec.outcome} pnl=${pnl:.2f}"
        )

    def _rewrite_disk(self):
        """Rewrite the full ledger (called after outcome resolution)."""
        try:
            with open(self.path, "w") as f:
                for rec in self._records.values():
                    f.write(json.dumps(asdict(rec), default=str) + "\n")
        except Exception as e:
            logger.warning(f"[OVERRIDE-LEDGER] Rewrite error: {e}")

    def get_accuracy(self, lookback: int = 20) -> Optional[float]:
        """Return win rate over the last N resolved overrides. None if insufficient."""
        resolved = [r for r in self._records.values()
                    if r.override_approved and r.outcome in ("win", "loss")]
        if len(resolved) < 5:
            return None
        resolved.sort(key=lambda r: r.resolved_at, reverse=True)
        sample = resolved[:lookback]
        wins = sum(1 for r in sample if r.outcome == "win")
        return wins / len(sample)

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for reporting."""
        all_records = list(self._records.values())
        approved = [r for r in all_records if r.override_approved]
        resolved = [r for r in approved if r.outcome in ("win", "loss")]
        wins = [r for r in resolved if r.outcome == "win"]
        losses = [r for r in resolved if r.outcome == "loss"]

        return {
            "total_overrides_evaluated": len(all_records),
            "overrides_approved": len(approved),
            "overrides_resolved": len(resolved),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(resolved) if resolved else None,
            "total_pnl": sum(r.pnl for r in resolved),
            "avg_win": sum(r.pnl for r in wins) / len(wins) if wins else 0,
            "avg_loss": sum(r.pnl for r in losses) / len(losses) if losses else 0,
            "recent_accuracy_20": self.get_accuracy(20),
        }

    def should_auto_disable(self, min_samples: int = 10, threshold: float = 0.4) -> bool:
        """Auto-disable if accuracy drops below threshold over min_samples overrides."""
        acc = self.get_accuracy(min_samples)
        if acc is None:
            return False
        return acc < threshold

    def get_pending_records(self) -> List[OverrideRecord]:
        """Return records awaiting outcome resolution."""
        return [r for r in self._records.values()
                if r.override_approved and r.outcome in ("", "pending")]


# ── Singleton ────────────────────────────────────────────────────

_ledger: Optional[OverrideLedger] = None


def get_override_ledger() -> OverrideLedger:
    global _ledger
    if _ledger is None:
        _ledger = OverrideLedger()
    return _ledger
