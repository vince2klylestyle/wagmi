"""Closed Trade Analyzer - Extract lessons from completed trades.

Analyzes closed trades by cross-referencing:
- Entry decision (from decisions.jsonl)
- Exit decision (if exists)
- Actual PnL outcome
- Thesis correctness
- Confidence calibration

Outputs TradeLesson objects that feed into memory enrichment.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TradeLesson:
    """Lesson extracted from a closed trade."""
    trade_id: str
    symbol: str
    entry_time: datetime
    exit_time: datetime
    entry_thesis: str
    outcome_thesis: str
    setup_type: str  # "trending_bear+3-agree+80conf"
    confidence_correct: bool
    pnl_usd: float
    pnl_pct: float
    r_multiple: float
    hold_duration_minutes: int
    lessons: List[str]
    risk_flags: List[str] = field(default_factory=list)
    regime: str = ""
    n_agree: int = 0
    confidence_predicted: float = 0.0
    confidence_actual_wr: float = 0.0


@dataclass
class SetupPattern:
    """Aggregated pattern from multiple similar trades."""
    setup_type: str
    win_count: int = 0
    loss_count: int = 0
    total_pnl_usd: float = 0.0
    avg_r_multiple: float = 0.0
    avg_hold_minutes: int = 0
    sample_size: int = 0
    confidence_bins: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    regime_dependent: bool = False
    related_patterns: List[str] = field(default_factory=list)
    discovered_date: Optional[datetime] = None
    last_verified_date: Optional[datetime] = None


class ClosedTradeAnalyzer:
    """Extract lessons from closed trades."""

    def __init__(self, decisions_log_path: str = "bot/data/llm/decisions.jsonl"):
        self.decisions_log_path = Path(decisions_log_path)
        self.patterns: Dict[str, SetupPattern] = {}

    def analyze(
        self,
        trade_id: str,
        symbol: str,
        entry_price: float,
        exit_price: float,
        entry_time: datetime,
        exit_time: datetime,
        position_size: float,
        entry_risk_pct: float,
        regime: str,
        side: str,  # "BUY" or "SELL"
    ) -> Optional[TradeLesson]:
        """Analyze a closed trade and extract lessons.

        Args:
            trade_id: Unique trade identifier
            symbol: Trading symbol (BTC, ETH, SOL, HYPE)
            entry_price: Entry price
            exit_price: Exit price
            entry_time: When trade opened
            exit_time: When trade closed
            position_size: Position quantity
            entry_risk_pct: Risk % from entry decision
            regime: Market regime at entry
            side: BUY or SELL

        Returns:
            TradeLesson object with extracted insights, or None if analysis fails
        """
        try:
            # Calculate PnL
            if side == "BUY":
                pnl_usd = (exit_price - entry_price) * position_size
                move_direction = "up" if exit_price > entry_price else "down"
            else:  # SELL
                pnl_usd = (entry_price - exit_price) * position_size
                move_direction = "down" if exit_price < entry_price else "up"

            pnl_pct = (pnl_usd / (entry_price * position_size)) if entry_price > 0 else 0.0

            # Estimate R-multiple (assuming risk_pct represents stop width)
            stop_distance = entry_risk_pct * entry_price if entry_risk_pct > 0 else 0.001
            move_distance = abs(exit_price - entry_price)
            r_multiple = move_distance / stop_distance if stop_distance > 0 else 0.0

            # Hold duration
            hold_duration_minutes = int((exit_time - entry_time).total_seconds() / 60)

            # Lookup entry decision from decisions.jsonl
            entry_decision = self._lookup_decision(symbol, entry_time, "go")
            if not entry_decision:
                logger.warning(f"[ANALYZER] No entry decision found for {trade_id}")
                entry_thesis = "unknown"
                confidence_predicted = 0.0
                n_agree = 0
            else:
                entry_thesis = entry_decision.get("thesis", "unknown")
                confidence_predicted = entry_decision.get("confidence", 0.0)
                n_agree = entry_decision.get("n_agree", 1)

            # Evaluate thesis correctness
            thesis_correct = self._evaluate_thesis_correctness(
                entry_thesis, move_direction, pnl_usd
            )

            # Outcome thesis
            outcome_thesis = f"Move was {move_direction} {abs(pnl_pct):.1%}, R={r_multiple:.2f}"

            # Build setup type
            confidence_bin = int(confidence_predicted / 10) * 10  # 80 → "80-90"
            setup_type = f"{regime}+{n_agree}-agree+{confidence_bin}conf"

            # Extract lessons
            lessons = self._extract_lessons(
                thesis_correct,
                confidence_predicted,
                pnl_usd,
                pnl_pct,
                regime,
                symbol,
            )

            # Risk flags
            risk_flags = []
            if pnl_usd < 0 and abs(pnl_pct) > 0.05:  # Significant loss (5%+)
                risk_flags.append("large_loss")
            if hold_duration_minutes < 1:  # Immediate stop
                risk_flags.append("instant_stop")
            if hold_duration_minutes > 1440:  # Over 1 day
                risk_flags.append("extended_hold")

            lesson = TradeLesson(
                trade_id=trade_id,
                symbol=symbol,
                entry_time=entry_time,
                exit_time=exit_time,
                entry_thesis=entry_thesis,
                outcome_thesis=outcome_thesis,
                setup_type=setup_type,
                confidence_correct=thesis_correct,
                pnl_usd=pnl_usd,
                pnl_pct=pnl_pct,
                r_multiple=r_multiple,
                hold_duration_minutes=hold_duration_minutes,
                lessons=lessons,
                risk_flags=risk_flags,
                regime=regime,
                n_agree=n_agree,
                confidence_predicted=confidence_predicted,
                confidence_actual_wr=1.0 if pnl_usd > 0 else 0.0,  # Binary win/loss
            )

            # Update pattern tracking
            self._update_pattern(lesson)

            logger.info(
                f"[ANALYZER] {trade_id} ({symbol}): {pnl_usd:+.2f} USD, "
                f"thesis={thesis_correct}, setup={setup_type}"
            )

            return lesson

        except Exception as e:
            logger.error(f"[ANALYZER] Failed to analyze {trade_id}: {e}", exc_info=True)
            return None

    def get_patterns(self) -> Dict[str, SetupPattern]:
        """Get all discovered patterns."""
        return self.patterns

    def get_pattern(self, setup_type: str) -> Optional[SetupPattern]:
        """Get stats for a specific setup type."""
        return self.patterns.get(setup_type)

    def _lookup_decision(
        self,
        symbol: str,
        event_time: datetime,
        action_filter: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Find decision in audit trail (±5s window)."""
        if not self.decisions_log_path.exists():
            return None

        try:
            with open(self.decisions_log_path) as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if entry.get("symbol") != symbol:
                            continue
                        if action_filter and entry.get("action") != action_filter:
                            continue

                        # Check timestamp (±5s window)
                        entry_time = datetime.fromisoformat(entry.get("timestamp", ""))
                        time_diff = abs((event_time - entry_time).total_seconds())
                        if time_diff <= 5:
                            return entry
                    except (json.JSONDecodeError, ValueError):
                        continue

            return None
        except Exception as e:
            logger.error(f"[ANALYZER] Failed to lookup decision: {e}")
            return None

    def _evaluate_thesis_correctness(
        self,
        thesis: str,
        actual_direction: str,
        pnl: float,
    ) -> bool:
        """Simple heuristic: thesis correct if trade was profitable."""
        return pnl > 0

    def _extract_lessons(
        self,
        thesis_correct: bool,
        confidence: float,
        pnl_usd: float,
        pnl_pct: float,
        regime: str,
        symbol: str,
    ) -> List[str]:
        """Extract actionable lessons from trade outcome."""
        lessons = []

        # Confidence calibration feedback
        if not thesis_correct and confidence >= 80:
            lessons.append(
                f"⚠️ OVERCONFIDENT: {confidence:.0f}% confidence but trade lost. "
                f"Deflate confidence in {regime} regime."
            )
        elif thesis_correct and confidence < 50:
            lessons.append(
                f"✓ UNDERCONFIDENT: {confidence:.0f}% but trade won. "
                f"Increase confidence in {regime} for {symbol}."
            )

        # Setup-specific feedback
        if abs(pnl_pct) > 0.05:  # Large loss
            lessons.append(
                f"Large loss ({pnl_pct:.1%}). Review stop placement "
                f"and position size for {symbol} in {regime}."
            )
        elif pnl_pct > 0.02:  # Good win
            lessons.append(
                f"Strong win ({pnl_pct:.1%}). Pattern working well. "
                f"Increase conviction in {regime} regime."
            )

        return lessons

    def _update_pattern(self, lesson: TradeLesson) -> None:
        """Update pattern statistics with new trade."""
        setup_type = lesson.setup_type

        if setup_type not in self.patterns:
            self.patterns[setup_type] = SetupPattern(
                setup_type=setup_type,
                discovered_date=datetime.utcnow(),
            )

        pattern = self.patterns[setup_type]
        pattern.sample_size += 1
        pattern.last_verified_date = datetime.utcnow()

        if lesson.pnl_usd > 0:
            pattern.win_count += 1
        else:
            pattern.loss_count += 1

        pattern.total_pnl_usd += lesson.pnl_usd
        pattern.avg_r_multiple = (
            pattern.avg_r_multiple * (pattern.sample_size - 1) + lesson.r_multiple
        ) / pattern.sample_size

        # Track confidence bin
        conf_bin = int(lesson.confidence_predicted / 10) * 10
        if conf_bin not in pattern.confidence_bins:
            pattern.confidence_bins[conf_bin] = {
                "wins": 0,
                "losses": 0,
                "total_r": 0.0,
            }

        bin_stats = pattern.confidence_bins[conf_bin]
        if lesson.pnl_usd > 0:
            bin_stats["wins"] += 1
        else:
            bin_stats["losses"] += 1
        bin_stats["total_r"] += lesson.r_multiple


def get_analyzer() -> ClosedTradeAnalyzer:
    """Get or create analyzer instance."""
    return ClosedTradeAnalyzer()
