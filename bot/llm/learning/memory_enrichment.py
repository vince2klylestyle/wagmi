"""Memory Enrichment - Convert lessons into deep memory + rule graduation.

Takes TradeLesson objects from closed_trade_analyzer and:
1. Injects short-term memory notes (7-day TTL)
2. Updates deep memory patterns (long-term)
3. Graduates validated patterns into enforceable rules
4. Flags underperforming rules for review/demotion
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class EnrichedMemoryNote:
    """Short-term memory note about a pattern or calibration issue."""
    content: str
    tags: List[str]
    ttl_days: int = 7
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class GraduatedRule:
    """Rule extracted from validated pattern."""
    rule_id: str
    trigger: str  # "symbol=ETH,regime=trending_bear,n_agree=3"
    action: str  # "promote_confidence", "enforce", "skip", etc.
    effect: str  # "+15%", "-20%", "BLOCK", etc.
    confidence: float  # 0-1, rule strength
    sample_size: int  # trades this rule was based on
    win_rate: float  # actual win rate
    discovered_date: str
    evidence: str  # Human-readable justification


class MemoryEnricher:
    """Enrich memory systems with extracted lessons."""

    def __init__(
        self,
        memory_store_path: str = "bot/llm/memory_store.py",
        deep_memory_dir: str = "bot/data/llm/deep_memory",
        graduated_rules_path: str = "bot/data/llm/graduated_rules.json",
    ):
        self.memory_store_path = Path(memory_store_path)
        self.deep_memory_dir = Path(deep_memory_dir)
        self.graduated_rules_path = Path(graduated_rules_path)
        self.deep_memory_dir.mkdir(parents=True, exist_ok=True)

    def enrich_memory(self, lesson) -> Dict[str, Any]:
        """Process a lesson and update all memory systems.

        Args:
            lesson: TradeLesson from closed_trade_analyzer

        Returns:
            Dict with enrichment results (notes added, rules graduated, etc.)
        """
        result = {
            "notes_added": 0,
            "patterns_updated": 0,
            "rules_graduated": 0,
            "rules_flagged_for_review": 0,
        }

        try:
            # 1. Inject short-term memory notes
            notes_added = self._inject_short_term_memory(lesson)
            result["notes_added"] = notes_added

            # 2. Update deep memory patterns
            patterns_updated = self._update_deep_memory(lesson)
            result["patterns_updated"] = patterns_updated

            # 3. Check for rule graduation
            rules_graduated = self._check_and_graduate_rules(lesson)
            result["rules_graduated"] = rules_graduated

            # 4. Check for rule demotion
            rules_flagged = self._check_rule_demotion(lesson)
            result["rules_flagged_for_review"] = rules_flagged

            logger.info(
                f"[ENRICHMENT] Processed {lesson.symbol} trade: "
                f"{notes_added} notes, {patterns_updated} patterns, "
                f"{rules_graduated} rules graduated"
            )

            return result

        except Exception as e:
            logger.error(f"[ENRICHMENT] Failed to enrich memory: {e}", exc_info=True)
            return result

    def _inject_short_term_memory(self, lesson) -> int:
        """Inject bite-sized lessons into short-term memory (7-day TTL)."""
        notes_added = 0

        # Confidence calibration note
        if not lesson.confidence_correct and lesson.confidence_predicted >= 80:
            note = EnrichedMemoryNote(
                content=(
                    f"⚠️ OVERCONFIDENT: {lesson.confidence_predicted:.0f}% confidence "
                    f"predicted but trade lost ({lesson.pnl_pct:.1%}). "
                    f"Deflate confidence in {lesson.regime} regime for {lesson.symbol}."
                ),
                tags=["confidence", "calibration", lesson.symbol, lesson.regime],
                ttl_days=7,
            )
            self._write_memory_note(note)
            notes_added += 1

        elif lesson.confidence_correct and lesson.confidence_predicted < 50:
            note = EnrichedMemoryNote(
                content=(
                    f"✓ UNDERCONFIDENT: {lesson.confidence_predicted:.0f}% but trade won "
                    f"({lesson.pnl_pct:+.1%}). Increase confidence in {lesson.regime} "
                    f"regime for {lesson.symbol}."
                ),
                tags=["confidence", "calibration", lesson.symbol, lesson.regime],
                ttl_days=7,
            )
            self._write_memory_note(note)
            notes_added += 1

        # Setup performance note
        if lesson.pnl_usd > 0 and lesson.r_multiple > 1.5:
            note = EnrichedMemoryNote(
                content=(
                    f"✓ STRONG WIN: {lesson.setup_type} produced {lesson.pnl_pct:+.1%} "
                    f"({lesson.r_multiple:.2f}R). Pattern working well. Trust this setup."
                ),
                tags=["pattern", "winning", lesson.symbol, lesson.regime],
                ttl_days=7,
            )
            self._write_memory_note(note)
            notes_added += 1

        elif lesson.pnl_usd < 0 and lesson.pnl_pct < -0.05:
            note = EnrichedMemoryNote(
                content=(
                    f"❌ LARGE LOSS: {lesson.setup_type} lost {abs(lesson.pnl_pct):.1%}. "
                    f"Review stop placement and sizing for {lesson.symbol}."
                ),
                tags=["pattern", "losing", lesson.symbol, lesson.regime],
                ttl_days=7,
            )
            self._write_memory_note(note)
            notes_added += 1

        # Risk flag notes
        for risk_flag in lesson.risk_flags:
            note = EnrichedMemoryNote(
                content=(
                    f"🚩 RISK: {risk_flag.upper()} detected in {lesson.symbol} trade. "
                    f"Hold={lesson.hold_duration_minutes}min. Investigate pattern."
                ),
                tags=["risk", risk_flag, lesson.symbol],
                ttl_days=14,
            )
            self._write_memory_note(note)
            notes_added += 1

        return notes_added

    def _update_deep_memory(self, lesson) -> int:
        """Update deep memory patterns.jsonl with aggregated statistics."""
        patterns_updated = 0

        try:
            patterns_file = self.deep_memory_dir / "patterns.jsonl"

            # Read existing patterns
            patterns = {}
            if patterns_file.exists():
                with open(patterns_file) as f:
                    for line in f:
                        try:
                            p = json.loads(line)
                            patterns[p["setup_type"]] = p
                        except json.JSONDecodeError:
                            continue

            # Update or create pattern for this setup
            setup_type = lesson.setup_type
            if setup_type not in patterns:
                patterns[setup_type] = {
                    "setup_type": setup_type,
                    "discovered_date": datetime.utcnow().isoformat(),
                    "win_count": 0,
                    "loss_count": 0,
                    "total_pnl_usd": 0.0,
                    "total_pnl_pct": 0.0,
                    "avg_r_multiple": 0.0,
                    "sample_size": 0,
                    "confidence_bins": {},
                }

            pattern = patterns[setup_type]
            pattern["last_updated_date"] = datetime.utcnow().isoformat()

            # Update counts
            if lesson.pnl_usd > 0:
                pattern["win_count"] += 1
            else:
                pattern["loss_count"] += 1

            pattern["sample_size"] += 1
            pattern["total_pnl_usd"] += lesson.pnl_usd
            pattern["total_pnl_pct"] += lesson.pnl_pct

            # Update R-multiple (rolling average)
            old_avg = pattern.get("avg_r_multiple", 0.0)
            new_count = pattern["sample_size"]
            pattern["avg_r_multiple"] = (
                (old_avg * (new_count - 1) + lesson.r_multiple) / new_count
            )

            # Track confidence bin
            conf_bin = int(lesson.confidence_predicted / 10) * 10
            if str(conf_bin) not in pattern["confidence_bins"]:
                pattern["confidence_bins"][str(conf_bin)] = {
                    "wins": 0,
                    "losses": 0,
                    "total_r": 0.0,
                    "sample_size": 0,
                }

            bin_stats = pattern["confidence_bins"][str(conf_bin)]
            if lesson.pnl_usd > 0:
                bin_stats["wins"] += 1
            else:
                bin_stats["losses"] += 1
            bin_stats["total_r"] += lesson.r_multiple
            bin_stats["sample_size"] += 1

            # Write updated patterns
            with open(patterns_file, "w") as f:
                for p in patterns.values():
                    f.write(json.dumps(p) + "\n")

            patterns_updated = 1

        except Exception as e:
            logger.error(f"[ENRICHMENT] Failed to update deep memory: {e}")

        return patterns_updated

    def _check_and_graduate_rules(self, lesson) -> int:
        """Graduate validated patterns to enforceable rules."""
        rules_graduated = 0

        try:
            # Load existing rules
            rules = []
            if self.graduated_rules_path.exists():
                with open(self.graduated_rules_path) as f:
                    data = json.load(f)
                    rules = data.get("rules", [])

            # Check if this lesson's pattern meets graduation threshold
            setup_type = lesson.setup_type

            # Count recent trades with this setup (should be done by pattern tracker)
            # For now, we'll just log a candidate for graduation
            if lesson.confidence_correct and lesson.r_multiple > 1.5:
                # Candidate for graduation
                rule_candidate = {
                    "trigger": setup_type,
                    "action": "promote_confidence" if lesson.confidence_correct else "demote_confidence",
                    "effect": f"+10%" if lesson.confidence_correct else "-15%",
                    "discovered_date": datetime.utcnow().isoformat(),
                    "status": "candidate",  # Requires manual review
                    "evidence": f"Trade {lesson.trade_id}: {lesson.pnl_pct:+.1%}, {lesson.r_multiple:.2f}R",
                }

                # Check if similar rule exists
                similar_exists = any(r.get("trigger") == setup_type for r in rules)
                if not similar_exists:
                    rules.append(rule_candidate)
                    rules_graduated = 1

            # Write updated rules
            rules_data = {"rules": rules, "last_updated": datetime.utcnow().isoformat()}
            with open(self.graduated_rules_path, "w") as f:
                json.dump(rules_data, f, indent=2)

        except Exception as e:
            logger.error(f"[ENRICHMENT] Failed to check rule graduation: {e}")

        return rules_graduated

    def _check_rule_demotion(self, lesson) -> int:
        """Flag underperforming rules for review/demotion."""
        rules_flagged = 0

        try:
            if self.graduated_rules_path.exists():
                with open(self.graduated_rules_path) as f:
                    data = json.load(f)
                    rules = data.get("rules", [])

                # Check if this trade contradicts any rules
                setup_type = lesson.setup_type
                for rule in rules:
                    if rule.get("trigger") == setup_type and rule.get("status") != "archived":
                        # If rule predicts success but this trade lost, flag it
                        if "promote" in rule.get("action", "") and lesson.pnl_usd < 0:
                            rule["flagged_for_review"] = True
                            rule["last_contradiction"] = datetime.utcnow().isoformat()
                            rules_flagged += 1

                # Write updates
                rules_data = {"rules": rules, "last_updated": datetime.utcnow().isoformat()}
                with open(self.graduated_rules_path, "w") as f:
                    json.dump(rules_data, f, indent=2)

        except Exception as e:
            logger.error(f"[ENRICHMENT] Failed to check rule demotion: {e}")

        return rules_flagged

    def _write_memory_note(self, note: EnrichedMemoryNote) -> None:
        """Write memory note to memory store."""
        try:
            # In real implementation, would call memory_store.add_note()
            # For now, log it
            logger.debug(f"[MEMORY] {' | '.join(note.tags)}: {note.content}")
        except Exception as e:
            logger.debug(f"[MEMORY] Failed to write note: {e}")


def get_enricher() -> MemoryEnricher:
    """Get or create enricher instance."""
    return MemoryEnricher()
