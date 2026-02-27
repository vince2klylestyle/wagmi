"""
Enhanced TradeCandidate with dual-entry system.

Extends the existing candidate.TradeCandidate with:
- snapshot_entry / live_entry / effective_entry()
- snapshot_ts / execution_ts / snapshot_age
- human_copy_tradable flag
- stale flag
- slippage tracking
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
import time


@dataclass
class EnhancedTradeCandidate:
    """Trade candidate with full dual-entry and safety metadata.

    This wraps/extends the base TradeCandidate for the execution pipeline.
    The base TradeCandidate (in execution/candidate.py) remains the primary
    dataclass. This adds execution-time fields.
    """
    # Core
    symbol: str
    side: str  # "LONG" or "SHORT"
    entry_type: str  # "SCALP", "MEDIUM", "TREND", "REGIME"
    primary_driver: str
    regime: str
    volatility_band: str = "medium"

    # DUAL ENTRY SYSTEM
    snapshot_entry: float = 0.0
    live_entry: Optional[float] = None
    snapshot_ts: float = field(default_factory=time.time)
    execution_ts: Optional[float] = None

    # Risk
    leverage: float = 1.0
    size_usd: float = 0.0
    rr1: float = 1.0
    rr2: float = 2.0

    # Classification
    confidence: float = 0.0
    strategies_agree: List[str] = field(default_factory=list)
    individual_confidences: Dict[str, float] = field(default_factory=dict)
    human_copy_tradable: bool = False
    stale: bool = False

    # Levels
    sl_price: Optional[float] = None
    tp1_price: Optional[float] = None
    tp2_price: Optional[float] = None
    atr: float = 0.0

    # Computed at execution time
    slippage_pct: float = 0.0
    spread_pct: float = 0.0
    liquidity_usd: float = 0.0
    snapshot_age_seconds: float = 0.0

    # Veto/downgrade tracking
    veto_reasons: List[str] = field(default_factory=list)
    downgrade_reasons: List[str] = field(default_factory=list)

    def effective_entry(self) -> float:
        """Prefer live_entry when available; fall back to snapshot_entry."""
        if self.live_entry is not None and self.live_entry > 0:
            return self.live_entry
        return self.snapshot_entry

    def compute_snapshot_age(self) -> float:
        """Compute age of snapshot in seconds."""
        now = self.execution_ts if self.execution_ts else time.time()
        age = now - self.snapshot_ts
        self.snapshot_age_seconds = age
        return age

    def compute_slippage(self) -> float:
        """Compute slippage between snapshot and live entry."""
        if not self.live_entry or self.snapshot_entry <= 0:
            self.slippage_pct = 0.0
            return 0.0
        slip = abs(self.live_entry - self.snapshot_entry) / self.snapshot_entry * 100
        self.slippage_pct = round(slip, 4)
        return self.slippage_pct

    def to_log_dict(self) -> Dict[str, Any]:
        """All fields needed for complete trade logging."""
        return {
            "symbol": self.symbol,
            "side": self.side,
            "entry_type": self.entry_type,
            "primary_driver": self.primary_driver,
            "regime": self.regime,
            "volatility_band": self.volatility_band,
            "snapshot_entry": self.snapshot_entry,
            "live_entry": self.live_entry,
            "effective_entry": self.effective_entry(),
            "snapshot_ts": self.snapshot_ts,
            "execution_ts": self.execution_ts,
            "snapshot_age_seconds": self.snapshot_age_seconds,
            "slippage_pct": self.slippage_pct,
            "spread_pct": self.spread_pct,
            "liquidity_usd": self.liquidity_usd,
            "confidence": self.confidence,
            "leverage": self.leverage,
            "size_usd": self.size_usd,
            "rr1": self.rr1,
            "rr2": self.rr2,
            "human_copy_tradable": self.human_copy_tradable,
            "stale": self.stale,
            "sl_price": self.sl_price,
            "tp1_price": self.tp1_price,
            "tp2_price": self.tp2_price,
            "veto_reasons": ";".join(self.veto_reasons),
            "downgrade_reasons": ";".join(self.downgrade_reasons),
        }
