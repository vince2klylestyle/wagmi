"""
CLI signal reader and manual approval interface.

Displays pending signals from the ensemble for manual review/approval.
Allows CLI-based execution without API calls.

Usage:
    python cli.py signals               # Show all pending signals
    python cli.py signals --symbol BTC  # Show BTC signals only
    python cli.py signals --limit 10    # Show last 10 signals
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger("bot.cli.signals")


class SignalViewer:
    """Read and display pending signals from ensemble."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.signals_file = self.data_dir / "pending_signals.jsonl"
        self.decisions_file = self.data_dir / "llm" / "decisions.jsonl"

    def get_pending_signals(self, symbol: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get pending signals from ensemble.

        Falls back to reading raw signals and filtering based on current state.
        """
        signals = []

        # Try to read from cached pending signals first
        if self.signals_file.exists():
            try:
                with open(self.signals_file) as f:
                    for line in f:
                        if line.strip():
                            sig = json.loads(line)
                            if symbol is None or sig.get("symbol") == symbol:
                                signals.append(sig)
                                if len(signals) >= limit:
                                    break
                return signals
            except Exception as e:
                logger.warning(f"Failed to read pending signals: {e}")

        # Fallback: read from decisions log (what the LLM saw)
        return self._read_recent_decisions(symbol, limit)

    def _read_recent_decisions(self, symbol: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Read recent decisions from LLM decisions log."""
        decisions = []

        if self.decisions_file.exists():
            try:
                with open(self.decisions_file) as f:
                    # Read last N lines (recent decisions)
                    lines = f.readlines()[-limit:]
                    for line in lines:
                        if line.strip():
                            dec = json.loads(line)
                            if symbol is None or dec.get("symbol") == symbol:
                                decisions.append(dec)
            except Exception as e:
                logger.warning(f"Failed to read decisions: {e}")

        return decisions

    def format_signal(self, sig: Dict[str, Any], index: int = 0) -> str:
        """Format a signal for display."""
        # Handle both signal and decision formats
        symbol = sig.get("symbol", "?")
        side = sig.get("side", sig.get("action", "?"))
        confidence = sig.get("confidence", 0)
        entry = sig.get("entry", sig.get("entry_price", "?"))
        sl = sig.get("sl", "?")
        tp1 = sig.get("tp1", "?")
        tp2 = sig.get("tp2", "?")
        strategy = sig.get("strategy", sig.get("source", "?"))
        timestamp = sig.get("timestamp", sig.get("time", "?"))

        # Format confidence as percentage
        conf_pct = f"{confidence:.0f}%" if isinstance(confidence, (int, float)) else "?"

        # Format prices
        def fmt_price(p):
            if isinstance(p, (int, float)):
                return f"{p:.2f}"
            return str(p)

        lines = [
            f"[{index+1}] {symbol:6s} {side:6s} @ {fmt_price(entry):>10s} | Conf: {conf_pct:>4s}",
            f"    Strategy: {strategy}",
            f"    SL: {fmt_price(sl):>10s}  TP1: {fmt_price(tp1):>10s}  TP2: {fmt_price(tp2):>10s}",
        ]

        # Add metadata if available
        if "num_agree" in sig:
            lines.append(f"    Agreement: {sig['num_agree']} strategies")

        if isinstance(timestamp, str):
            lines.append(f"    Time: {timestamp}")

        return "\n".join(lines)

    def display_signals(self, symbol: Optional[str] = None, limit: int = 50):
        """Display pending signals in a readable format."""
        signals = self.get_pending_signals(symbol, limit)

        if not signals:
            print("No pending signals.")
            return

        print("=" * 70)
        print(f"PENDING SIGNALS ({len(signals)} recent)")
        print("=" * 70)
        print()

        for i, sig in enumerate(signals):
            print(self.format_signal(sig, i))
            print()

        print("=" * 70)
        print(f"Total: {len(signals)} signals")
        print()
        print("To execute a signal (Phase 4):")
        print("  python cli.py trade execute --signal-id <index>")
        print()


def run_signals_cli(symbol: Optional[str] = None, limit: int = 50):
    """Main entry point for signals mode."""
    viewer = SignalViewer()
    viewer.display_signals(symbol, limit)
