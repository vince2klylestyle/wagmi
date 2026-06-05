"""
Memory Seeder — Pre-seeds LLM memory with validated findings from signal analysis.

Encodes 18 findings from the 2,172-signal deep analysis into both:
  - Short-term memory (llm_memory.json) for immediate agent use
  - Deep memory (insight_journal.json) for long-term structured recall

Usage:
  cd bot && python -m llm.memory_seeder          # CLI
  from llm.memory_seeder import seed_memory; seed_memory()  # Import
"""

import json
import logging
import os
import time
from typing import List, Dict, Any

logger = logging.getLogger("bot.llm.memory_seeder")

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "llm")
_MEMORY_PATH = os.path.join(_DATA_DIR, "llm_memory.json")
_JOURNAL_PATH = os.path.join(_DATA_DIR, "deep_memory", "insight_journal.json")

# ---------------------------------------------------------------------------
# 2026-06-05: FINDINGS list NEUTRALIZED per Nunu directive.
# The 18 hardcoded "2,172-signal analysis" findings were computed under the
# 10x fee bug (taker_fee_bps=45 vs real 4.5 bps). Their WR/PnL claims
# (BB solo 67.6%, ETH_SELL_BB 70%, etc) were polluting insight_journal.json
# and llm_memory.json which feed directly into agent prompts via
# prompt_enricher.py. When kelly_engine recomputes from corrected-fee
# trade_ledger, real findings can be re-derived from data.
#
# Original FINDINGS preserved in git history (this commit's parent).
# ---------------------------------------------------------------------------

FINDINGS: List[Dict[str, Any]] = [
    # Empty list — no fabricated seed insights. Live trade outcomes will
    # populate deep_memory + insight_journal organically via the closing flow.
]

# Keep the original list shape below as a reference, but never used.
_LEGACY_FINDINGS_DO_NOT_USE: List[Dict[str, Any]] = [
    {
        "text": "BB is only profitable strategy: 57% WR, +0.15%/trade. All others negative EV.",
        "symbol": "MARKET",
        "regime": "",
        "category": "strategy_insight",
        "confidence": 0.95,
        "evidence": "2,172-signal backtest analysis",
    },
    {
        "text": "BB solo signals = 67.6% WR. Strongest pattern. Trust BB alone over consensus.",
        "symbol": "MARKET",
        "regime": "",
        "category": "strategy_insight",
        "confidence": 0.95,
        "evidence": "2,172-signal analysis: BB solo >> multi-strategy agreement",
    },
    {
        "text": "BB+MTQ combo = 35% WR. Contra-indicator. SKIP when both agree.",
        "symbol": "MARKET",
        "regime": "",
        "category": "strategy_insight",
        "confidence": 0.92,
        "evidence": "2,172-signal analysis: BB+MTQ agreement is anti-predictive",
    },
    {
        "text": "High confidence is NOT predictive. 80%+ WR is WORSE than <60%. Ignore confidence scores.",
        "symbol": "MARKET",
        "regime": "",
        "category": "risk_insight",
        "confidence": 0.93,
        "evidence": "2,172-signal analysis: confidence inversely correlated with outcome",
    },
    {
        "text": "After 2 consecutive wins: 74-77% WR. After 2 losses: 28-29% WR. Streak momentum is real.",
        "symbol": "MARKET",
        "regime": "",
        "category": "execution_insight",
        "confidence": 0.90,
        "evidence": "2,172-signal analysis: streak-based WR validated",
    },
    {
        "text": "ETH_SELL_BB = 70% WR. Best golden setup. Prioritize ETH shorts on BB signals.",
        "symbol": "ETH",
        "regime": "",
        "category": "setup_insight",
        "confidence": 0.92,
        "evidence": "2,172-signal analysis: top setup by WR",
    },
    {
        "text": "BTC_BUY_BB = 69% WR. Second best setup. Prioritize BTC longs on BB signals.",
        "symbol": "BTC",
        "regime": "",
        "category": "setup_insight",
        "confidence": 0.91,
        "evidence": "2,172-signal analysis: second highest WR setup",
    },
    {
        "text": "SOL_BUY_BB = 67% WR. Reliable long setup on BB signals.",
        "symbol": "SOL",
        "regime": "",
        "category": "setup_insight",
        "confidence": 0.90,
        "evidence": "2,172-signal analysis: third highest WR setup",
    },
    {
        "text": "BTC_SELL_BB = 61% WR. Decent but weaker than BTC longs. Size down on BTC shorts.",
        "symbol": "BTC",
        "regime": "",
        "category": "setup_insight",
        "confidence": 0.88,
        "evidence": "2,172-signal analysis: moderate WR setup",
    },
    {
        "text": "HYPE_SELL_BB = 35% WR. Worst BB setup. AVOID shorting HYPE on BB signals.",
        "symbol": "HYPE",
        "regime": "",
        "category": "setup_insight",
        "confidence": 0.92,
        "evidence": "2,172-signal analysis: worst BB combo by far",
    },
    {
        "text": "HYPE_BUY_CS = 38% WR. Dead setup. SKIP all CS-only HYPE longs.",
        "symbol": "HYPE",
        "regime": "",
        "category": "setup_insight",
        "confidence": 0.90,
        "evidence": "2,172-signal analysis: consistently losing setup",
    },
    {
        "text": "high_volatility regime = 55% WR. Best regime for trading. Increase size in high vol.",
        "symbol": "MARKET",
        "regime": "high_volatility",
        "category": "regime_insight",
        "confidence": 0.88,
        "evidence": "2,172-signal analysis: regime-stratified WR",
    },
    {
        "text": "BTC leads cross-asset: when BTC wins, ETH follows 60% of the time. Watch BTC first.",
        "symbol": "BTC",
        "regime": "",
        "category": "correlation_insight",
        "confidence": 0.85,
        "evidence": "2,172-signal analysis: cross-asset lead-lag",
    },
    {
        "text": "R:R 1.0-1.5 = 57% WR. Tighter TPs outperform wide ones. Keep TP1 close.",
        "symbol": "MARKET",
        "regime": "",
        "category": "execution_insight",
        "confidence": 0.90,
        "evidence": "2,172-signal analysis: R:R bucket comparison",
    },
    {
        "text": "HYPE in extreme vol = 33% WR. Never trade HYPE during volatility spikes.",
        "symbol": "HYPE",
        "regime": "high_volatility",
        "category": "risk_insight",
        "confidence": 0.92,
        "evidence": "2,172-signal analysis: HYPE extreme vol is a death trap",
    },
    {
        "text": "1h timeframe predicts 4h with 67% accuracy (73% for BB). Use 1h as leading signal.",
        "symbol": "MARKET",
        "regime": "",
        "category": "timing_insight",
        "confidence": 0.87,
        "evidence": "2,172-signal analysis: multi-TF predictive power",
    },
    {
        "text": "MFE peaks at 8-12h holding. 34% of peak move captured at 12h. Optimal hold window.",
        "symbol": "MARKET",
        "regime": "",
        "category": "execution_insight",
        "confidence": 0.85,
        "evidence": "2,172-signal analysis: MFE curve analysis",
    },
    {
        "text": "BB losers recover 56% of loss, non-BB only 45%. BB signals have better loss recovery.",
        "symbol": "MARKET",
        "regime": "",
        "category": "risk_insight",
        "confidence": 0.83,
        "evidence": "2,172-signal analysis: loss recovery by strategy",
    },
]


def seed_memory(dry_run: bool = False) -> dict:
    """Seed both short-term and deep memory with validated findings.

    Args:
        dry_run: If True, return data without writing to disk.

    Returns:
        Dict with counts of notes seeded to each store.
    """
    now = time.time()

    # --- Build short-term memory notes ---
    memory_notes = []
    for f in FINDINGS:
        memory_notes.append({
            "text": f["text"],
            "ts": now,
            "symbol": f["symbol"],
            "regime": f.get("regime", ""),
        })

    memory_data = {
        "last_updated": int(now),
        "notes": memory_notes,
    }

    # --- Build deep memory journal entries ---
    journal_entries = []
    for f in FINDINGS:
        journal_entries.append({
            "ts": now,
            "category": f["category"],
            "insight": f["text"],
            "confidence": f["confidence"],
            "evidence": f["evidence"],
            "source": "deep_signal_analysis_2172",
            "validated": True,
            "validation_count": 2172,
        })

    if dry_run:
        return {
            "memory_notes": len(memory_notes),
            "journal_entries": len(journal_entries),
            "memory_data": memory_data,
            "journal_entries_data": journal_entries,
        }

    # --- Write short-term memory ---
    os.makedirs(os.path.dirname(_MEMORY_PATH), exist_ok=True)
    with open(_MEMORY_PATH, "w") as f:
        json.dump(memory_data, f, indent=2)
    logger.info(f"[SEED] Wrote {len(memory_notes)} notes to {_MEMORY_PATH}")

    # --- Merge into deep memory journal (preserve existing entries) ---
    journal_dir = os.path.dirname(_JOURNAL_PATH)
    os.makedirs(journal_dir, exist_ok=True)

    existing_journal = {"insights": []}
    if os.path.exists(_JOURNAL_PATH):
        try:
            with open(_JOURNAL_PATH, "r") as f:
                existing_journal = json.load(f)
        except (json.JSONDecodeError, IOError):
            logger.warning("[SEED] Could not read existing journal, starting fresh")

    # Remove any previous seeded entries (by source tag) to avoid duplicates
    existing_insights = [
        e for e in existing_journal.get("insights", [])
        if e.get("source") != "deep_signal_analysis_2172"
    ]

    # Prepend new entries (highest priority = first)
    existing_journal["insights"] = journal_entries + existing_insights

    with open(_JOURNAL_PATH, "w") as f:
        json.dump(existing_journal, f, indent=2)
    logger.info(f"[SEED] Wrote {len(journal_entries)} entries to {_JOURNAL_PATH}")

    print(f"Seeded {len(memory_notes)} notes to llm_memory.json")
    print(f"Seeded {len(journal_entries)} insights to insight_journal.json")
    print(f"Total deep memory insights: {len(existing_journal['insights'])}")

    return {
        "memory_notes": len(memory_notes),
        "journal_entries": len(journal_entries),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_memory()
