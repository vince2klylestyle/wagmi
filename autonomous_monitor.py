#!/usr/bin/env python3
"""
Autonomous System Monitor - Lightweight check-in loop
Runs every 2-4 hours, reports system health, metrics, and learnings
"""

import json
import os
import time
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

class AutonomousMonitor:
    def __init__(self):
        self.data_dir = Path('bot/data')
        self.decisions_log = self.data_dir / 'llm' / 'decisions.jsonl'
        self.trades_log = self.data_dir / 'trades.csv'
        self.kb_file = self.data_dir / 'llm' / 'teaching' / 'knowledge_base.json'
        self.last_check = {}

    def read_recent_trades(self, hours=4):
        """Read trades from last N hours."""
        try:
            trades = []
            if not self.trades_log.exists():
                return []

            cutoff = datetime.utcnow() - timedelta(hours=hours)
            with open(self.trades_log, 'r') as f:
                for i, line in enumerate(f):
                    if i == 0:  # Skip header
                        continue
                    parts = line.strip().split(',')
                    if len(parts) >= 2:
                        trades.append({
                            'symbol': parts[0] if len(parts) > 0 else '?',
                            'side': parts[1] if len(parts) > 1 else '?',
                            'raw': line.strip()
                        })
            return trades[-20:] if len(trades) > 20 else trades
        except Exception as e:
            return []

    def read_recent_decisions(self, count=10):
        """Read recent LLM decisions."""
        try:
            if not self.decisions_log.exists():
                return []
            decisions = []
            with open(self.decisions_log, 'r') as f:
                for line in f:
                    if line.strip():
                        decisions.append(json.loads(line))
            return decisions[-count:]
        except Exception as e:
            return []

    def check_kb_state(self):
        """Check knowledge base evolution."""
        try:
            if self.kb_file.exists():
                with open(self.kb_file, 'r') as f:
                    kb = json.load(f)
                    return {
                        'patterns': len(kb.get('patterns', {})),
                        'rules': len(kb.get('rules', {})),
                        'hypotheses': len(kb.get('hypotheses', {})),
                    }
        except Exception:
            pass
        return None

    def report(self):
        """Generate check-in report."""
        trades = self.read_recent_trades(hours=4)
        decisions = self.read_recent_decisions(count=5)
        kb = self.check_kb_state()

        print("\n" + "="*70)
        print("AUTONOMOUS SYSTEM CHECK-IN")
        print("Time: " + datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"))
        print("="*70)

        # System Status
        print("\nSYSTEM STATUS:")
        print(f"  Bot running: {'YES' if Path('/tmp/autonomous_bot_*.log').exists() else 'CHECK'}")
        print(f"  Recent trades (4h): {len(trades)}")
        print(f"  Recent decisions: {len(decisions)}")

        # Trades
        if trades:
            print("\nRECENT TRADES:")
            for i, trade in enumerate(trades[-5:], 1):
                print(f"  {i}. {trade['symbol']:5} {trade['side']:5} | {trade['raw'][:60]}")
        else:
            print("\nRECENT TRADES: None in last 4 hours")

        # KB Evolution
        if kb:
            print("\nKNOWLEDGE BASE:")
            print(f"  Patterns learned: {kb['patterns']}")
            print(f"  Rules active: {kb['rules']}")
            print(f"  Hypotheses tracking: {kb['hypotheses']}")

        # Next check
        next_check = datetime.utcnow() + timedelta(hours=3)
        print(f"\nNEXT CHECK: {next_check.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("="*70 + "\n")

def run_check_in_loop(interval_hours=3):
    """Run autonomous monitoring in background."""
    monitor = AutonomousMonitor()

    while True:
        try:
            monitor.report()
        except Exception as e:
            print(f"[ERROR] Check-in failed: {e}")

        # Sleep until next check
        sleep_seconds = interval_hours * 3600
        print(f"[MONITOR] Sleeping {interval_hours}h until next check...")
        time.sleep(sleep_seconds)

if __name__ == '__main__':
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    run_check_in_loop(interval_hours=interval)
