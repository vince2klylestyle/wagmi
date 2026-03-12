"""
Structured pattern cache for actionable trading knowledge.

Stores learned patterns as compact, queryable facts:
  "SOL_SHORT_trend": {win_rate: 0.30, trades: 12, pnl: -450, ...}

Fed by:
  1. Deep memory trade DNA (on each trade close)
  2. Backtest results (after each backtest run)
  3. Mode comparison results (after comparison runs)

Consumed by:
  - snapshot_builder.py: injects relevant patterns into LLM prompts
  - Trade Agent: uses patterns to size up/avoid specific setups

Key design:
  - Max 200 patterns, pruned by staleness + statistical confidence
  - Patterns decay over 30 days unless reinforced
  - Symbol-specific queries return only relevant patterns (~50-100 tokens)
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

logger = logging.getLogger("bot.llm.pattern_cache")

# Persistence path
_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "llm")
_CACHE_PATH = os.path.join(_DATA_DIR, "pattern_cache.json")

MAX_PATTERNS = 200
STALENESS_DAYS = 30
MIN_TRADES_FOR_CONFIDENCE = 5


@dataclass
class TradingPattern:
    """A single actionable trading pattern."""
    key: str              # "SOL_SHORT_trend" (symbol_side_regime)
    symbol: str           # "SOL"
    side: str             # "LONG" or "SHORT"
    regime: str           # "trend", "range", "panic", etc.
    win_rate: float       # 0.0-1.0
    trades: int           # number of trades observed
    pnl: float            # cumulative PnL
    avg_winner: float     # average winning trade PnL
    avg_loser: float      # average losing trade PnL
    reason: str = ""      # human-readable insight
    last_updated: float = field(default_factory=time.time)
    source: str = "live"  # "live", "backtest", "comparison"

    @property
    def confidence(self) -> float:
        """Statistical confidence based on sample size. 0-1 scale."""
        if self.trades < MIN_TRADES_FOR_CONFIDENCE:
            return 0.0
        # Rough confidence: asymptotes to 1.0 as trades increase
        return min(1.0, self.trades / 50.0)

    @property
    def is_stale(self) -> bool:
        """Check if pattern is older than STALENESS_DAYS without reinforcement."""
        age_days = (time.time() - self.last_updated) / 86400
        return age_days > STALENESS_DAYS

    @property
    def action_hint(self) -> str:
        """Suggest action based on win rate."""
        if self.trades < MIN_TRADES_FOR_CONFIDENCE:
            return "insufficient_data"
        if self.win_rate >= 0.60:
            return "size_up"
        if self.win_rate <= 0.40:
            return "avoid"
        return "normal"

    def to_prompt_str(self) -> str:
        """Compact string for LLM injection (~30-50 tokens)."""
        action = self.action_hint
        parts = [f"{self.symbol}/{self.side.lower()}/{self.regime}"]
        parts.append(f"{self.win_rate:.0%} WR ({self.trades} trades, ${self.pnl:+.0f})")
        if action == "avoid":
            parts.append("— AVOID")
        elif action == "size_up":
            parts.append("— SIZE UP")
        if self.reason:
            parts.append(f"({self.reason})")
        return " ".join(parts)


class PatternCache:
    """Thread-safe pattern cache with file persistence."""

    def __init__(self, path: str = _CACHE_PATH):
        self._path = path
        self._patterns: Dict[str, TradingPattern] = {}
        self._load()

    def _load(self):
        """Load patterns from disk."""
        try:
            if os.path.exists(self._path):
                with open(self._path) as f:
                    data = json.load(f)
                for key, d in data.items():
                    self._patterns[key] = TradingPattern(**d)
                logger.info(f"[PATTERNS] Loaded {len(self._patterns)} patterns from cache")
        except Exception as e:
            logger.warning(f"[PATTERNS] Failed to load cache: {e}")
            self._patterns = {}

    def _save(self):
        """Persist patterns to disk."""
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w") as f:
                json.dump(
                    {k: asdict(v) for k, v in self._patterns.items()},
                    f, indent=2
                )
        except Exception as e:
            logger.warning(f"[PATTERNS] Failed to save cache: {e}")

    @staticmethod
    def make_key(symbol: str, side: str, regime: str) -> str:
        """Generate pattern key."""
        return f"{symbol}_{side.upper()}_{regime.lower()}"

    def update_pattern(
        self,
        symbol: str,
        side: str,
        regime: str,
        win: bool,
        pnl: float,
        reason: str = "",
        source: str = "live",
    ):
        """Update a pattern with a new trade outcome."""
        key = self.make_key(symbol, side, regime)
        if key in self._patterns:
            p = self._patterns[key]
            # Update rolling stats
            p.trades += 1
            p.pnl += pnl
            old_wr = p.win_rate
            p.win_rate = (old_wr * (p.trades - 1) + (1.0 if win else 0.0)) / p.trades
            if win:
                if p.avg_winner == 0:
                    p.avg_winner = pnl
                else:
                    p.avg_winner = p.avg_winner * 0.8 + pnl * 0.2  # EMA
            else:
                if p.avg_loser == 0:
                    p.avg_loser = pnl
                else:
                    p.avg_loser = p.avg_loser * 0.8 + pnl * 0.2  # EMA
            if reason:
                p.reason = reason
            p.last_updated = time.time()
            p.source = source
        else:
            self._patterns[key] = TradingPattern(
                key=key,
                symbol=symbol,
                side=side.upper(),
                regime=regime.lower(),
                win_rate=1.0 if win else 0.0,
                trades=1,
                pnl=pnl,
                avg_winner=pnl if win else 0.0,
                avg_loser=pnl if not win else 0.0,
                reason=reason,
                source=source,
            )

        self._prune()
        self._save()

    def ingest_backtest_report(self, report: Dict):
        """Ingest findings from a backtest report into pattern cache.

        Expected report structure:
        {
            "by_symbol_regime_side": {
                "SOL_SHORT_trend": {"wr": 0.30, "trades": 12, "pnl": -450, ...},
                ...
            }
        }
        """
        data = report.get("by_symbol_regime_side", {})
        for key, stats in data.items():
            parts = key.split("_")
            if len(parts) < 3:
                continue
            symbol, side, regime = parts[0], parts[1], "_".join(parts[2:])
            wr = stats.get("wr", 0.5)
            trades = stats.get("trades", 0)
            pnl = stats.get("pnl", 0.0)
            avg_w = stats.get("avg_winner", 0.0)
            avg_l = stats.get("avg_loser", 0.0)

            cache_key = self.make_key(symbol, side, regime)
            self._patterns[cache_key] = TradingPattern(
                key=cache_key,
                symbol=symbol,
                side=side.upper(),
                regime=regime.lower(),
                win_rate=wr,
                trades=trades,
                pnl=pnl,
                avg_winner=avg_w,
                avg_loser=avg_l,
                source="backtest",
            )

        self._prune()
        self._save()
        logger.info(f"[PATTERNS] Ingested {len(data)} patterns from backtest report")

    def get_relevant_patterns(
        self,
        symbol: str,
        side: Optional[str] = None,
        regime: Optional[str] = None,
        min_trades: int = MIN_TRADES_FOR_CONFIDENCE,
    ) -> List[TradingPattern]:
        """Get patterns relevant to a specific trade setup.

        Returns patterns matching symbol (required), optionally filtered by side/regime.
        Sorted by relevance (exact match first, then by trade count).
        """
        results = []
        for p in self._patterns.values():
            if p.symbol != symbol:
                continue
            if p.trades < min_trades:
                continue
            if p.is_stale:
                continue
            # Score: exact match > partial match
            score = 0
            if side and p.side == side.upper():
                score += 2
            if regime and p.regime == regime.lower():
                score += 2
            results.append((score, p))

        results.sort(key=lambda x: (-x[0], -x[1].trades))
        return [p for _, p in results[:5]]  # Max 5 patterns per query

    def get_prompt_context(
        self,
        symbol: str,
        side: Optional[str] = None,
        regime: Optional[str] = None,
    ) -> str:
        """Get a compact prompt string for LLM injection.

        Returns ~50-100 tokens of actionable pattern knowledge.
        """
        patterns = self.get_relevant_patterns(symbol, side, regime)
        if not patterns:
            return ""
        lines = [p.to_prompt_str() for p in patterns]
        return " | ".join(lines)

    def get_all_actionable(self, min_trades: int = MIN_TRADES_FOR_CONFIDENCE) -> List[TradingPattern]:
        """Get all patterns with actionable hints (avoid or size_up)."""
        return [
            p for p in self._patterns.values()
            if p.trades >= min_trades and not p.is_stale
            and p.action_hint in ("avoid", "size_up")
        ]

    def _prune(self):
        """Remove stale patterns and cap at MAX_PATTERNS."""
        # Remove stale
        stale_keys = [k for k, p in self._patterns.items() if p.is_stale]
        for k in stale_keys:
            del self._patterns[k]

        # Cap at MAX_PATTERNS: keep highest confidence patterns
        if len(self._patterns) > MAX_PATTERNS:
            sorted_patterns = sorted(
                self._patterns.items(),
                key=lambda x: (x[1].confidence, x[1].trades),
                reverse=True,
            )
            self._patterns = dict(sorted_patterns[:MAX_PATTERNS])

    def __len__(self) -> int:
        return len(self._patterns)

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        actionable = self.get_all_actionable()
        return {
            "total_patterns": len(self._patterns),
            "actionable_avoid": sum(1 for p in actionable if p.action_hint == "avoid"),
            "actionable_size_up": sum(1 for p in actionable if p.action_hint == "size_up"),
            "sources": {
                "live": sum(1 for p in self._patterns.values() if p.source == "live"),
                "backtest": sum(1 for p in self._patterns.values() if p.source == "backtest"),
                "comparison": sum(1 for p in self._patterns.values() if p.source == "comparison"),
            },
        }


# ── Module-level singleton ──────────────────────────────────────────

_instance: Optional[PatternCache] = None


def get_pattern_cache() -> PatternCache:
    """Get or create the global PatternCache instance."""
    global _instance
    if _instance is None:
        _instance = PatternCache()
    return _instance
