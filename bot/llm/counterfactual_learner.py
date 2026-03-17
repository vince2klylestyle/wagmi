"""
Counter-Factual Learning — Track What Would Have Happened

For every trade the system SKIPS (filtered by ensemble, vetoed by Critic,
rejected by risk gates), track what would have happened if the trade was taken.

This prevents the system from becoming too conservative after anti-spam tightening.
If we're consistently skipping trades that would have been profitable, that's a sign
our filters are too tight.

Tracks:
- Skipped trade entry price, TP1, TP2, SL
- Forward price action after skip (did it hit TP1? TP2? SL?)
- Reason for skip (which filter rejected it)
- Running PnL of "would-have-been" trades

This data feeds back to:
1. Learning Agent: "You skipped 5 winning trades this week"
2. Parameter tuner: loosening gates that block too many winners
3. Confidence calibration: adjusting filters that are miscalibrated

Storage: bot/data/llm/counterfactual_log.jsonl
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bot.llm.counterfactual")


class CounterfactualRecord:
    """A single skipped trade tracked for counterfactual analysis."""

    def __init__(self, symbol: str, side: str, entry_price: float,
                 sl: float, tp1: float, tp2: float, confidence: float,
                 skip_reason: str, strategy: str = "",
                 regime: str = "", metadata: Optional[Dict] = None):
        self.record_id = f"cf_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{id(self) % 10000}"
        self.symbol = symbol
        self.side = side
        self.entry_price = entry_price
        self.sl = sl
        self.tp1 = tp1
        self.tp2 = tp2
        self.confidence = confidence
        self.skip_reason = skip_reason
        self.strategy = strategy
        self.regime = regime
        self.metadata = metadata or {}
        self.created_at = datetime.now(timezone.utc).isoformat()

        # Outcome fields (filled when resolved)
        self.resolved = False
        self.would_hit_tp1 = False
        self.would_hit_tp2 = False
        self.would_hit_sl = False
        self.max_favorable_price: Optional[float] = None
        self.max_adverse_price: Optional[float] = None
        self.hypothetical_pnl_pct: Optional[float] = None
        self.resolved_at: Optional[str] = None
        self.bars_to_resolve: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "symbol": self.symbol,
            "side": self.side,
            "entry_price": self.entry_price,
            "sl": self.sl,
            "tp1": self.tp1,
            "tp2": self.tp2,
            "confidence": self.confidence,
            "skip_reason": self.skip_reason,
            "strategy": self.strategy,
            "regime": self.regime,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "resolved": self.resolved,
            "would_hit_tp1": self.would_hit_tp1,
            "would_hit_tp2": self.would_hit_tp2,
            "would_hit_sl": self.would_hit_sl,
            "max_favorable_price": self.max_favorable_price,
            "max_adverse_price": self.max_adverse_price,
            "hypothetical_pnl_pct": self.hypothetical_pnl_pct,
            "resolved_at": self.resolved_at,
            "bars_to_resolve": self.bars_to_resolve,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CounterfactualRecord":
        rec = cls(
            symbol=d["symbol"],
            side=d["side"],
            entry_price=d["entry_price"],
            sl=d["sl"],
            tp1=d["tp1"],
            tp2=d["tp2"],
            confidence=d["confidence"],
            skip_reason=d["skip_reason"],
            strategy=d.get("strategy", ""),
            regime=d.get("regime", ""),
            metadata=d.get("metadata", {}),
        )
        rec.record_id = d.get("record_id", rec.record_id)
        rec.created_at = d.get("created_at", rec.created_at)
        rec.resolved = d.get("resolved", False)
        rec.would_hit_tp1 = d.get("would_hit_tp1", False)
        rec.would_hit_tp2 = d.get("would_hit_tp2", False)
        rec.would_hit_sl = d.get("would_hit_sl", False)
        rec.max_favorable_price = d.get("max_favorable_price")
        rec.max_adverse_price = d.get("max_adverse_price")
        rec.hypothetical_pnl_pct = d.get("hypothetical_pnl_pct")
        rec.resolved_at = d.get("resolved_at")
        rec.bars_to_resolve = d.get("bars_to_resolve", 0)
        return rec


class CounterfactualLearner:
    """
    Tracks skipped trades and computes what would have happened.

    Provides aggregate stats:
    - How many skipped trades would have been winners?
    - Which skip reasons produce the most missed winners?
    - What's the total hypothetical PnL we left on the table?
    - Which filters need loosening vs tightening?
    """

    # Max bars to track a counterfactual before giving up
    MAX_TRACKING_BARS = 48  # 48h max for 1h candles

    # Max pending counterfactuals to track simultaneously
    MAX_PENDING = 200

    def __init__(self, data_dir: str = "data/llm"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.data_dir / "counterfactual_log.jsonl"

        self._pending: Dict[str, CounterfactualRecord] = {}
        self._resolved: List[CounterfactualRecord] = []
        self._load()

    def _load(self):
        """Load counterfactual history."""
        if not self.log_file.exists():
            return
        try:
            with open(self.log_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                        rec = CounterfactualRecord.from_dict(d)
                        if rec.resolved:
                            self._resolved.append(rec)
                        else:
                            self._pending[rec.record_id] = rec
                    except (json.JSONDecodeError, KeyError):
                        continue
            logger.info(f"Loaded {len(self._resolved)} resolved + "
                        f"{len(self._pending)} pending counterfactuals")
        except Exception as e:
            logger.warning(f"Failed to load counterfactual log: {e}")

    def _save_record(self, record: CounterfactualRecord):
        """Append a record to the log file."""
        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(record.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"Failed to save counterfactual record: {e}")

    def record_skip(self, symbol: str, side: str, entry_price: float,
                     sl: float, tp1: float, tp2: float, confidence: float,
                     skip_reason: str, strategy: str = "",
                     regime: str = "", metadata: Optional[Dict] = None) -> str:
        """Record a skipped trade for counterfactual tracking."""
        # Evict oldest pending if at capacity
        if len(self._pending) >= self.MAX_PENDING:
            oldest_key = min(self._pending, key=lambda k: self._pending[k].created_at)
            old = self._pending.pop(oldest_key)
            old.resolved = True
            old.resolved_at = datetime.now(timezone.utc).isoformat()
            old.hypothetical_pnl_pct = 0.0
            self._resolved.append(old)

        rec = CounterfactualRecord(
            symbol=symbol, side=side, entry_price=entry_price,
            sl=sl, tp1=tp1, tp2=tp2, confidence=confidence,
            skip_reason=skip_reason, strategy=strategy,
            regime=regime, metadata=metadata,
        )
        self._pending[rec.record_id] = rec
        self._save_record(rec)
        return rec.record_id

    def update_with_price(self, symbol: str, high: float, low: float, close: float):
        """
        Update all pending counterfactuals for a symbol with new price data.
        Call this on each new candle.
        """
        to_resolve = []

        for record_id, rec in self._pending.items():
            if rec.symbol != symbol:
                continue

            rec.bars_to_resolve += 1

            # Track max favorable/adverse excursion
            if rec.side == "BUY":
                if rec.max_favorable_price is None or high > rec.max_favorable_price:
                    rec.max_favorable_price = high
                if rec.max_adverse_price is None or low < rec.max_adverse_price:
                    rec.max_adverse_price = low

                # Check if TP1/TP2/SL would have been hit
                if high >= rec.tp1:
                    rec.would_hit_tp1 = True
                if high >= rec.tp2:
                    rec.would_hit_tp2 = True
                if low <= rec.sl:
                    rec.would_hit_sl = True
            else:  # SELL
                if rec.max_favorable_price is None or low < rec.max_favorable_price:
                    rec.max_favorable_price = low
                if rec.max_adverse_price is None or high > rec.max_adverse_price:
                    rec.max_adverse_price = high

                if low <= rec.tp1:
                    rec.would_hit_tp1 = True
                if low <= rec.tp2:
                    rec.would_hit_tp2 = True
                if high >= rec.sl:
                    rec.would_hit_sl = True

            # Resolve conditions: SL hit, TP2 hit, or max tracking bars
            if rec.would_hit_sl or rec.would_hit_tp2 or rec.bars_to_resolve >= self.MAX_TRACKING_BARS:
                # Calculate hypothetical PnL
                if rec.would_hit_sl and not rec.would_hit_tp1:
                    # SL hit first (loss)
                    loss_pct = abs(rec.entry_price - rec.sl) / rec.entry_price * 100
                    rec.hypothetical_pnl_pct = -loss_pct
                elif rec.would_hit_tp2:
                    # Full TP2 (big win)
                    gain_pct = abs(rec.tp2 - rec.entry_price) / rec.entry_price * 100
                    rec.hypothetical_pnl_pct = gain_pct
                elif rec.would_hit_tp1:
                    # TP1 but not TP2 (partial win)
                    gain_pct = abs(rec.tp1 - rec.entry_price) / rec.entry_price * 100
                    rec.hypothetical_pnl_pct = gain_pct * 0.65  # ~65% partial close
                else:
                    # Timed out, use close price
                    if rec.side == "BUY":
                        rec.hypothetical_pnl_pct = (close - rec.entry_price) / rec.entry_price * 100
                    else:
                        rec.hypothetical_pnl_pct = (rec.entry_price - close) / rec.entry_price * 100

                rec.resolved = True
                rec.resolved_at = datetime.now(timezone.utc).isoformat()
                to_resolve.append(record_id)

        # Move resolved records
        for rid in to_resolve:
            rec = self._pending.pop(rid)
            self._resolved.append(rec)
            self._save_record(rec)  # Save updated record

    def get_missed_opportunity_stats(self, lookback_days: int = 14) -> Dict[str, Any]:
        """Compute statistics on missed trading opportunities."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
        recent = [r for r in self._resolved if r.created_at >= cutoff]

        if not recent:
            return {"total_skips": 0, "sufficient_data": False}

        winners = [r for r in recent if (r.hypothetical_pnl_pct or 0) > 0]
        losers = [r for r in recent if (r.hypothetical_pnl_pct or 0) <= 0]

        total_hypo_pnl = sum(r.hypothetical_pnl_pct or 0 for r in recent)
        avg_hypo_pnl = total_hypo_pnl / len(recent) if recent else 0

        # By skip reason
        by_reason: Dict[str, Dict] = {}
        for r in recent:
            reason = r.skip_reason
            if reason not in by_reason:
                by_reason[reason] = {"total": 0, "would_win": 0, "would_lose": 0,
                                      "total_pnl": 0.0}
            by_reason[reason]["total"] += 1
            if (r.hypothetical_pnl_pct or 0) > 0:
                by_reason[reason]["would_win"] += 1
            else:
                by_reason[reason]["would_lose"] += 1
            by_reason[reason]["total_pnl"] += (r.hypothetical_pnl_pct or 0)

        for k, v in by_reason.items():
            v["skip_accuracy"] = v["would_lose"] / v["total"] if v["total"] > 0 else 0
            v["avg_pnl"] = v["total_pnl"] / v["total"] if v["total"] > 0 else 0

        # Identify filters that are too aggressive (blocking winners)
        problem_filters = {k: v for k, v in by_reason.items()
                           if v["total"] >= 5 and v["skip_accuracy"] < 0.5}

        return {
            "total_skips": len(recent),
            "sufficient_data": True,
            "would_win": len(winners),
            "would_lose": len(losers),
            "win_rate_of_skips": len(winners) / len(recent) if recent else 0,
            "total_hypothetical_pnl": total_hypo_pnl,
            "avg_hypothetical_pnl": avg_hypo_pnl,
            "by_skip_reason": by_reason,
            "problem_filters": problem_filters,
            "pending_count": len(self._pending),
        }

    def get_prompt_context(self, lookback_days: int = 7) -> str:
        """Generate context for agent prompts about missed opportunities."""
        stats = self.get_missed_opportunity_stats(lookback_days)
        if not stats.get("sufficient_data") or stats["total_skips"] < 10:
            return ""

        lines = [f"COUNTERFACTUAL ANALYSIS ({stats['total_skips']} skipped trades, {lookback_days}d):"]
        lines.append(f"  Of trades we skipped: {stats['would_win']} would have won, "
                     f"{stats['would_lose']} would have lost")
        lines.append(f"  Skip accuracy: {(1-stats['win_rate_of_skips'])*100:.0f}% correctly skipped")
        lines.append(f"  Hypothetical PnL left on table: {stats['total_hypothetical_pnl']:+.2f}%")

        if stats.get("problem_filters"):
            lines.append("  FILTERS BLOCKING TOO MANY WINNERS:")
            for filt, data in stats["problem_filters"].items():
                lines.append(f"    - {filt}: blocked {data['total']} trades, "
                             f"{data['would_win']} would have won "
                             f"(avg PnL={data['avg_pnl']:+.2f}%)")

        return "\n".join(lines)
