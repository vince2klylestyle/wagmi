"""
CLI Trade Executor — Execute cached signals without API calls.

Execution modes:
  - log: Record trade decision to CSV (no simulation)
  - simulate: Estimate P&L using signal SL/TP targets
  - paper: Log to trades.csv as if filled

Usage:
    python cli.py trade execute --signal-id 0 --size 1.0 --mode simulate
"""

import csv
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger("bot.cli.executor")


class TradeExecutor:
    """Execute trades from cached signals."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.execution_log = self.data_dir / "cli_executions.csv"
        self._ensure_log_exists()

    def _ensure_log_exists(self):
        """Create execution log CSV if it doesn't exist."""
        if self.execution_log.exists():
            return
        with open(self.execution_log, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp",
                "symbol",
                "side",
                "entry",
                "size",
                "sl",
                "tp1",
                "tp2",
                "confidence",
                "signal_source",
                "execution_mode",
                "expected_rr",
                "status",
            ])

    def execute_signal(
        self,
        signal: Dict[str, Any],
        size: float = 1.0,
        mode: str = "log",
        signal_id: int = 0,
    ) -> Dict[str, Any]:
        """Execute a signal (log, simulate, or paper trade).

        Args:
            signal: Signal dict from cache
            size: Position size multiplier (1.0 = standard)
            mode: 'log' (record only), 'simulate' (estimate P&L), 'paper' (add to trades.csv)
            signal_id: Index of signal (for tracking)

        Returns:
            Execution result dict with status, P&L, etc.
        """
        symbol = signal.get("symbol", "?")
        side = signal.get("side", "?")
        entry = signal.get("entry", 0)
        sl = signal.get("sl", 0)
        tp1 = signal.get("tp1", 0)
        tp2 = signal.get("tp2", 0)
        confidence = signal.get("confidence", 0)

        # Calculate R:R ratio
        rr1 = self._calculate_rr(entry, tp1, sl, side)
        rr2 = self._calculate_rr(entry, tp2, sl, side)

        # Log execution
        timestamp = datetime.now(timezone.utc).isoformat()
        self._log_execution(
            timestamp=timestamp,
            symbol=symbol,
            side=side,
            entry=entry,
            size=size,
            sl=sl,
            tp1=tp1,
            tp2=tp2,
            confidence=confidence,
            signal_source=f"cli_signal_{signal_id}",
            execution_mode=mode,
            expected_rr=rr1,
            status="PENDING",
        )

        result = {
            "timestamp": timestamp,
            "symbol": symbol,
            "side": side,
            "entry": entry,
            "size": size,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "confidence": confidence,
            "rr1": rr1,
            "rr2": rr2,
            "signal_id": signal_id,
            "mode": mode,
            "status": "EXECUTED" if mode in ("paper", "simulate") else "LOGGED",
        }

        # Simulate P&L if requested
        if mode == "simulate":
            result["simulated_pnl_tp1"] = self._simulate_pnl(entry, tp1, size, side)
            result["simulated_pnl_tp2"] = self._simulate_pnl(entry, tp2, size, side)
            result["worst_case_pnl"] = self._simulate_pnl(entry, sl, size, side)

        return result

    def _calculate_rr(self, entry: float, target: float, stop: float, side: str) -> float:
        """Calculate risk-reward ratio."""
        if side.upper() == "LONG":
            risk = entry - stop
            reward = target - entry
        else:
            risk = stop - entry
            reward = entry - target

        if risk <= 0:
            return 0
        return round(reward / risk, 2)

    def _simulate_pnl(self, entry: float, exit_price: float, size: float, side: str) -> float:
        """Estimate P&L from entry and exit (in USD notional)."""
        if side.upper() == "LONG":
            pct_move = (exit_price - entry) / entry
        else:
            pct_move = (entry - exit_price) / entry
        # Assume $1 per unit (simplified)
        return round(pct_move * size * 100, 2)

    def _log_execution(self, **kwargs):
        """Log execution to CSV."""
        with open(self.execution_log, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=kwargs.keys())
            writer.writerow(kwargs)

    def get_execution_count(self) -> int:
        """Get number of executions logged."""
        if not self.execution_log.exists():
            return 0
        with open(self.execution_log) as f:
            return sum(1 for _ in f) - 1  # Exclude header

    def get_execution_stats(self) -> Dict[str, Any]:
        """Get summary statistics of all executions."""
        if not self.execution_log.exists():
            return {"total": 0}

        executions = []
        with open(self.execution_log) as f:
            reader = csv.DictReader(f)
            executions = list(reader)

        symbols = set(e.get("symbol") for e in executions)
        sides = {}
        total_pnl = 0.0

        for e in executions:
            side = e.get("side", "?")
            sides[side] = sides.get(side, 0) + 1

        return {
            "total_executions": len(executions),
            "unique_symbols": len(symbols),
            "symbols": sorted(list(symbols)),
            "sides": sides,
            "execution_log": str(self.execution_log),
        }


def run_executor_cli(signal_id: int, size: float = 1.0, mode: str = "log", source: str = "extracted"):
    """Main entry point for trade executor CLI."""
    from cli.cached_signals import CachedSignalLoader

    # Load the signal
    loader = CachedSignalLoader()
    signal = loader.find_signal(signal_id, source)

    if not signal:
        print(f"Signal {signal_id} not found in {source}")
        return

    # Execute the trade
    executor = TradeExecutor()
    result = executor.execute_signal(signal, size, mode, signal_id)

    # Display result
    print("=" * 70)
    print(f"TRADE EXECUTION RESULT")
    print("=" * 70)
    print()
    print(f"  Symbol:        {result['symbol']}")
    print(f"  Side:          {result['side']}")
    print(f"  Entry:         {result['entry']}")
    print(f"  Size:          {result['size']}")
    print(f"  Stop Loss:     {result['sl']}")
    print(f"  Take Profit 1: {result['tp1']}")
    print(f"  Take Profit 2: {result['tp2']}")
    print(f"  Confidence:    {result['confidence']}%")
    print(f"  Risk:Reward:   1:{result['rr1']:.2f}")
    print()
    print(f"  Mode:          {result['mode']}")
    print(f"  Status:        {result['status']}")
    print()

    if mode == "simulate":
        print("  Simulated P&L:")
        print(f"    @ TP1: ${result.get('simulated_pnl_tp1', 0):.2f}")
        print(f"    @ TP2: ${result.get('simulated_pnl_tp2', 0):.2f}")
        print(f"    @ SL:  ${result.get('worst_case_pnl', 0):.2f}")
        print()

    # Show execution log
    stats = executor.get_execution_stats()
    print(f"Total executions: {stats['total_executions']}")
    print(f"Log file: {stats['execution_log']}")
    print()
    print("=" * 70)
