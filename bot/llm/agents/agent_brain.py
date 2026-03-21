"""
Agent Brain: per-agent persistent learning and belief system.

Each agent gets its own brain that:
1. Tracks beliefs (learned patterns with Bayesian confidence updating)
2. Records decision accuracy (per-regime, per-setup calibration)
3. Provides calibration curves (is 70% confidence really 70% accurate?)
4. Persists to disk for learning across sessions

Brain files stored in: bot/data/llm/brains/{agent_name}_brain.json
"""

import json
import logging
import math
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("bot.llm.agents.agent_brain")

# Default brains directory
_BRAINS_DIR = Path(__file__).parent.parent / "data" / "llm" / "brains"


# ─────────────────────────────────────────────────────────────────────────────
# BELIEF SYSTEM
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Belief:
    """A learned belief held by this agent."""
    statement: str
    confidence: float  # 0-1, updated via Bayesian updating
    evidence_count: int = 0
    counter_evidence: int = 0
    first_observed: str = ""  # ISO timestamp
    last_updated: str = ""
    regime_context: str = ""
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Belief":
        return Belief(**{k: v for k, v in d.items() if k in Belief.__dataclass_fields__})


# ─────────────────────────────────────────────────────────────────────────────
# AGENT BRAIN
# ─────────────────────────────────────────────────────────────────────────────

class AgentBrain:
    """Per-agent brain with beliefs, performance tracking, and calibration."""

    def __init__(self, agent_role: str, brains_dir: Optional[Path] = None):
        self.agent_role = agent_role
        self._dir = brains_dir or _BRAINS_DIR
        self._path = self._dir / f"{agent_role}_brain.json"

        # Belief system
        self.beliefs: List[Belief] = []

        # Performance tracking
        self.total_decisions: int = 0
        self.correct_decisions: int = 0
        self.decisions_by_regime: Dict[str, Tuple[int, int]] = {}  # regime -> (correct, total)
        self.calibration_history: List[Tuple[float, bool]] = []  # (confidence, was_correct)
        self.avg_response_time_ms: float = 0.0
        self.last_n_decisions: List[dict] = []  # Rolling window

        # Metadata
        self.created_at: str = datetime.now().isoformat()
        self.last_updated: str = ""

        self.load()

    # ── Belief Management ───────────────────────────────────────

    def update_belief(
        self,
        statement: str,
        evidence_for: bool,
        regime: str = "",
        tags: Optional[List[str]] = None,
    ) -> Belief:
        """Bayesian update of a belief based on new evidence.

        Uses log-odds for numerical stability:
        log_odds = log(p / (1-p))
        Update: log_odds += evidence_weight
        """
        # Find existing belief or create new
        existing = None
        for b in self.beliefs:
            if b.statement == statement:
                existing = b
                break

        if existing is None:
            existing = Belief(
                statement=statement,
                confidence=0.5,  # Start with maximum uncertainty
                first_observed=datetime.now().isoformat(),
                regime_context=regime,
                tags=tags or [],
            )
            self.beliefs.append(existing)

        # Bayesian update using log-odds
        p = max(0.01, min(0.99, existing.confidence))
        log_odds = math.log(p / (1 - p))

        # Evidence weight: diminishes as evidence accumulates (diminishing returns)
        total_evidence = existing.evidence_count + existing.counter_evidence + 1
        weight = 0.5 / math.sqrt(total_evidence)

        if evidence_for:
            log_odds += weight
            existing.evidence_count += 1
        else:
            log_odds -= weight
            existing.counter_evidence += 1

        # Convert back to probability
        existing.confidence = 1.0 / (1.0 + math.exp(-log_odds))
        existing.last_updated = datetime.now().isoformat()

        return existing

    def get_beliefs_for_context(
        self,
        regime: str = "",
        symbol: str = "",
        top_k: int = 5,
    ) -> List[Belief]:
        """Get most relevant beliefs for current trading context."""
        scored = []
        for b in self.beliefs:
            score = b.confidence * 0.5  # Base: higher confidence = more relevant

            # Regime match bonus
            if regime and b.regime_context == regime:
                score += 0.3
            elif not b.regime_context:
                score += 0.1  # Universal beliefs get small bonus

            # Recency bonus
            if b.last_updated:
                try:
                    age_hours = (datetime.now() - datetime.fromisoformat(b.last_updated)).total_seconds() / 3600
                    if age_hours < 24:
                        score += 0.2
                    elif age_hours < 168:  # 1 week
                        score += 0.1
                except (ValueError, TypeError):
                    pass

            # Symbol tag match
            if symbol and symbol.upper() in [t.upper() for t in b.tags]:
                score += 0.2

            # Evidence quality
            total_ev = b.evidence_count + b.counter_evidence
            if total_ev >= 5:
                score += 0.1

            scored.append((score, b))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [b for _, b in scored[:top_k]]

    # ── Decision Recording ──────────────────────────────────────

    def record_decision(self, decision: dict) -> None:
        """Record a decision this agent made."""
        self.total_decisions += 1
        entry = {
            "ts": time.time(),
            "regime": decision.get("regime", "unknown"),
            "action": decision.get("a", decision.get("action", "unknown")),
            "confidence": decision.get("c", decision.get("confidence", 0.5)),
        }
        self.last_n_decisions.append(entry)
        # Keep rolling window of 50
        if len(self.last_n_decisions) > 50:
            self.last_n_decisions = self.last_n_decisions[-50:]

    def record_outcome(
        self,
        decision_id: str,
        was_correct: bool,
        details: dict,
    ) -> None:
        """Record whether this agent's decision was correct."""
        if was_correct:
            self.correct_decisions += 1

        regime = details.get("regime", "unknown")
        if regime not in self.decisions_by_regime:
            self.decisions_by_regime[regime] = (0, 0)
        correct, total = self.decisions_by_regime[regime]
        self.decisions_by_regime[regime] = (
            correct + (1 if was_correct else 0),
            total + 1,
        )

        confidence = details.get("confidence", 0.5)
        self.calibration_history.append((confidence, was_correct))

        # Keep calibration history bounded
        if len(self.calibration_history) > 500:
            self.calibration_history = self.calibration_history[-500:]

        self.last_updated = datetime.now().isoformat()

    # ── Calibration ─────────────────────────────────────────────

    def calibration_error(self) -> float:
        """How well-calibrated is this agent? 0=perfect, 1=terrible.

        Positive = overconfident, negative = underconfident.
        """
        if len(self.calibration_history) < 3:
            return 0.0

        total_error = 0.0
        for conf, correct in self.calibration_history:
            expected = conf
            actual = 1.0 if correct else 0.0
            total_error += (expected - actual)

        return total_error / len(self.calibration_history)

    def calibration_curve(self, bins: int = 10) -> Dict[str, dict]:
        """Returns {predicted_conf_bucket: actual_accuracy} for calibration plot."""
        if len(self.calibration_history) < 3:
            return {}

        bin_size = 1.0 / bins
        result = {}

        for i in range(bins):
            lower = i * bin_size
            upper = (i + 1) * bin_size
            label = f"{lower:.1f}-{upper:.1f}"
            in_bucket = [(c, w) for c, w in self.calibration_history if lower <= c < upper]

            if in_bucket:
                predicted_avg = sum(c for c, _ in in_bucket) / len(in_bucket)
                actual_acc = sum(1 for _, w in in_bucket if w) / len(in_bucket)
                result[label] = {
                    "predicted_avg": round(predicted_avg, 3),
                    "actual_accuracy": round(actual_acc, 3),
                    "count": len(in_bucket),
                }

        return result

    def confidence_adjustment(self, raw_confidence: float) -> float:
        """Adjust agent's raw confidence based on historical calibration.

        If agent is overconfident, reduces. If under, increases.
        """
        if len(self.calibration_history) < 5:
            return raw_confidence  # Not enough data

        cal_err = self.calibration_error()

        # Apply correction: if overconfident by 0.1, reduce by ~0.05 (half correction)
        adjustment = -cal_err * 0.5
        adjusted = max(0.0, min(1.0, raw_confidence + adjustment))

        return adjusted

    # ── Performance Summary ─────────────────────────────────────

    def get_performance_summary(self) -> str:
        """Human-readable performance summary for injection into agent prompt."""
        if self.total_decisions == 0:
            return ""

        wr = self.correct_decisions / self.total_decisions if self.total_decisions > 0 else 0
        parts = [f"WR={wr:.0%}({self.total_decisions}t)"]

        # Best/worst regime
        if self.decisions_by_regime:
            best_regime = max(
                self.decisions_by_regime.items(),
                key=lambda x: x[1][0] / x[1][1] if x[1][1] > 0 else 0,
            )
            worst_regime = min(
                self.decisions_by_regime.items(),
                key=lambda x: x[1][0] / x[1][1] if x[1][1] > 0 else 0,
            )
            if best_regime[1][1] >= 3:
                br_wr = best_regime[1][0] / best_regime[1][1]
                parts.append(f"best={best_regime[0]}({br_wr:.0%})")
            if worst_regime[1][1] >= 3 and worst_regime[0] != best_regime[0]:
                wr_wr = worst_regime[1][0] / worst_regime[1][1]
                parts.append(f"worst={worst_regime[0]}({wr_wr:.0%})")

        cal = self.calibration_error()
        if abs(cal) > 0.1:
            direction = "over" if cal > 0 else "under"
            parts.append(f"cal={direction}conf({abs(cal):.0%})")

        return " | ".join(parts)

    def get_lessons_learned(self, regime: str = "", last_n: int = 10) -> List[str]:
        """Extract lessons from beliefs relevant to regime."""
        beliefs = self.get_beliefs_for_context(regime, top_k=last_n)
        return [
            f"{b.statement} (conf={b.confidence:.0%}, n={b.evidence_count}+/{b.counter_evidence}-)"
            for b in beliefs if b.confidence > 0.55 or b.confidence < 0.35
        ]

    # ── Persistence ─────────────────────────────────────────────

    def save(self) -> None:
        """Save brain state to disk."""
        self.last_updated = datetime.now().isoformat()
        self._dir.mkdir(parents=True, exist_ok=True)

        data = {
            "agent_role": self.agent_role,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "beliefs": [b.to_dict() for b in self.beliefs],
            "performance": {
                "total_decisions": self.total_decisions,
                "correct_decisions": self.correct_decisions,
                "decisions_by_regime": {k: list(v) for k, v in self.decisions_by_regime.items()},
                "calibration_history": self.calibration_history,
                "avg_response_time_ms": self.avg_response_time_ms,
                "last_n_decisions": self.last_n_decisions[-20:],  # Save last 20
            },
        }

        try:
            with open(self._path, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"[BRAIN] Saved {self.agent_role} brain ({len(self.beliefs)} beliefs)")
        except Exception as e:
            logger.error(f"[BRAIN] Failed to save {self.agent_role}: {e}")

    def load(self) -> None:
        """Load brain state from disk."""
        if not self._path.exists():
            return

        try:
            with open(self._path, "r") as f:
                data = json.load(f)

            self.created_at = data.get("created_at", self.created_at)
            self.last_updated = data.get("last_updated", "")

            # Load beliefs
            self.beliefs = [Belief.from_dict(b) for b in data.get("beliefs", [])]

            # Load performance
            perf = data.get("performance", {})
            self.total_decisions = perf.get("total_decisions", 0)
            self.correct_decisions = perf.get("correct_decisions", 0)
            self.decisions_by_regime = {
                k: tuple(v) for k, v in perf.get("decisions_by_regime", {}).items()
            }
            self.calibration_history = [
                (float(c), bool(w)) for c, w in perf.get("calibration_history", [])
            ]
            self.avg_response_time_ms = perf.get("avg_response_time_ms", 0.0)
            self.last_n_decisions = perf.get("last_n_decisions", [])

            logger.debug(
                f"[BRAIN] Loaded {self.agent_role} brain: "
                f"{len(self.beliefs)} beliefs, {self.total_decisions} decisions"
            )
        except Exception as e:
            logger.error(f"[BRAIN] Failed to load {self.agent_role}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# BRAIN MANAGER
# ─────────────────────────────────────────────────────────────────────────────

class BrainManager:
    """Manages all agent brains."""

    def __init__(self, brains_dir: Optional[Path] = None):
        self._dir = brains_dir or _BRAINS_DIR
        self._brains: Dict[str, AgentBrain] = {}

    def get_brain(self, agent_role: str) -> AgentBrain:
        """Get or create brain for an agent."""
        if agent_role not in self._brains:
            self._brains[agent_role] = AgentBrain(agent_role, self._dir)
        return self._brains[agent_role]

    def sync_all(self) -> None:
        """Save all brains to disk."""
        for brain in self._brains.values():
            brain.save()

    def cross_agent_learning(self, lesson: str, source_agent: str, regime: str = "") -> None:
        """Share a lesson from one agent to relevant others.

        E.g., if Trade Agent learns "SOL mean-reverts after RSI<25",
        this adds it as a belief to Risk and Critic agents too.
        """
        # Relevance mapping: which agents care about which lessons
        relevance = {
            "regime": ["trade", "risk", "scout"],
            "trade": ["critic", "risk", "learning"],
            "risk": ["trade", "critic"],
            "critic": ["trade"],
            "learning": ["trade", "risk", "critic", "regime"],
            "scout": ["trade"],
        }

        target_agents = relevance.get(source_agent, [])
        for target in target_agents:
            brain = self.get_brain(target)
            brain.update_belief(
                statement=f"[from {source_agent}] {lesson}",
                evidence_for=True,
                regime=regime,
                tags=[source_agent, "cross_agent"],
            )

    def get_team_calibration_report(self) -> Dict[str, Any]:
        """Overall team calibration across all agents."""
        report = {}
        for role, brain in self._brains.items():
            if brain.total_decisions > 0:
                report[role] = {
                    "total_decisions": brain.total_decisions,
                    "accuracy": brain.correct_decisions / brain.total_decisions,
                    "calibration_error": brain.calibration_error(),
                    "belief_count": len(brain.beliefs),
                }
        return report


# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL INSTANCE
# ─────────────────────────────────────────────────────────────────────────────

_brain_manager: Optional[BrainManager] = None


def get_brain_manager() -> BrainManager:
    """Get or create the global brain manager."""
    global _brain_manager
    if _brain_manager is None:
        _brain_manager = BrainManager()
    return _brain_manager


__all__ = [
    "Belief",
    "AgentBrain",
    "BrainManager",
    "get_brain_manager",
]
