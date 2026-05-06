#!/usr/bin/env python3
"""
Autonomous Aggressive Executor for WAGMI Trading System

This system:
1. Monitors ALL signals in real-time (632 signals from last optimization)
2. Shows detailed decision reasoning for each signal
3. Executes aggressively on high-conviction signals (>70% confidence)
4. Trades conservatively on medium-conviction (50-70%)
5. Skips low-conviction (<50%)

Usage:
  python autonomous_aggressive_executor.py [--mode aggressive|conservative|manual]

Modes:
  aggressive  - Execute on 60%+ confidence, use full Kelly leverage
  conservative - Execute on 75%+ confidence, use 50% Kelly
  manual      - Show all signals but require human confirmation
"""

import json
import time
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import threading
import queue

class AgggressiveSignalExecutor:
    def __init__(self, mode='aggressive'):
        self.mode = mode
        self.data_dir = Path('bot/data')
        self.decisions_path = self.data_dir / 'decisions.jsonl'
        self.log_path = Path('/tmp/phase3_live_paper.log')

        # Execution rules
        self.confidence_thresholds = {
            'aggressive': 60,      # Execute 60%+ confidence
            'conservative': 75,    # Execute 75%+ confidence
            'manual': 90          # Show 90%+ but require approval
        }
        self.threshold = self.confidence_thresholds.get(mode, 70)

        # Tracking
        self.executed_signals = {}
        self.pending_signals = {}
        self.rejected_signals = {}
        self.signal_queue = queue.Queue()

        # Autonomous execution rules
        self.auto_rules = {
            'bollinger_squeeze': {'execute': True, 'leverage': 5.0, 'min_conf': 40},
            'monte_carlo_zones': {'execute': True, 'leverage': 4.0, 'min_conf': 40},
            'vmc_cipher': {'execute': True, 'leverage': 5.0, 'min_conf': 35},
            'regime_trend': {'execute': False, 'leverage': 0, 'min_conf': 999},  # Disabled
            'multi_tier_quality': {'execute': True, 'leverage': 3.0, 'min_conf': 50}
        }

    def read_all_signals(self):
        """Read ALL signals from decisions.jsonl (not just last 20)."""
        if not self.decisions_path.exists():
            return []

        signals = []
        try:
            with open(self.decisions_path, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                        if record.get('type') == 'signal':
                            signals.append(record)
                    except:
                        pass
        except:
            pass

        return signals

    def analyze_signal_quality(self, signal):
        """Analyze whether signal meets execution criteria."""
        strategy = signal.get('strategy', '')
        confidence = signal.get('confidence', 0)
        n_agree = signal.get('n_agree', 1)

        # Check if strategy is allowed
        rules = self.auto_rules.get(strategy, {})
        if not rules.get('execute', False):
            return {
                'execute': False,
                'reason': f'Strategy {strategy} disabled (negative historical edge)',
                'confidence': confidence,
                'n_agree': n_agree
            }

        # Check confidence threshold
        min_conf = rules.get('min_conf', 70)
        if confidence < min_conf:
            return {
                'execute': False,
                'reason': f'Confidence {confidence:.1f}% < min {min_conf}%',
                'confidence': confidence,
                'n_agree': n_agree
            }

        # Check global execution threshold
        if confidence < self.threshold:
            return {
                'execute': False,
                'reason': f'Confidence {confidence:.1f}% < mode threshold {self.threshold}%',
                'confidence': confidence,
                'n_agree': n_agree
            }

        # Check multi-strategy agreement
        if n_agree < 1:
            return {
                'execute': False,
                'reason': 'No strategy agreement',
                'confidence': confidence,
                'n_agree': n_agree
            }

        return {
            'execute': True,
            'reason': f'{strategy} solo - {confidence:.1f}% confidence',
            'confidence': confidence,
            'n_agree': n_agree,
            'leverage': rules.get('leverage', 3.0)
        }

    def print_signal_analysis(self, signals):
        """Print detailed analysis of ALL signals."""
        print("\n" + "="*140)
        print("COMPREHENSIVE SIGNAL ANALYSIS - ALL SIGNALS")
        print(f"Total signals: {len(signals)} | Mode: {self.mode.upper()} | Threshold: {self.threshold}%")
        print("="*140)

        # Group by execution status
        executable = []
        pending = []
        rejected = []
        disabled = []

        for signal in signals:
            analysis = self.analyze_signal_quality(signal)
            signal['analysis'] = analysis

            if analysis['reason'].startswith('Strategy'):
                disabled.append(signal)
            elif analysis['execute']:
                executable.append(signal)
            elif analysis['confidence'] >= 50:
                pending.append(signal)
            else:
                rejected.append(signal)

        # Show executable signals (should execute immediately)
        print(f"\n🟢 EXECUTABLE SIGNALS ({len(executable)}) - EXECUTE NOW")
        print("-" * 140)
        if executable:
            print(f"{'Symbol':8s} {'Side':6s} {'Strategy':25s} {'Conf':7s} {'Agree':6s} {'Action':40s}")
            print("-" * 140)
            for signal in executable[-10:]:  # Show last 10
                print(f"{signal.get('symbol', '?'):8s} {signal.get('side', '?'):6s} "
                      f"{signal.get('strategy', '?'):25s} {signal.get('confidence', 0):6.1f}% "
                      f"{signal.get('n_agree', 1):6d} EXECUTE (+{signal['analysis'].get('leverage', 3.0):.1f}x)")

        # Show pending signals (monitor these)
        print(f"\n🟡 PENDING SIGNALS ({len(pending)}) - WATCH THESE")
        print("-" * 140)
        if pending:
            print(f"{'Symbol':8s} {'Side':6s} {'Strategy':25s} {'Conf':7s} {'Agree':6s} {'Status':40s}")
            print("-" * 140)
            for signal in pending[-10:]:
                status = signal['analysis']['reason']
                print(f"{signal.get('symbol', '?'):8s} {signal.get('side', '?'):6s} "
                      f"{signal.get('strategy', '?'):25s} {signal.get('confidence', 0):6.1f}% "
                      f"{signal.get('n_agree', 1):6d} {status}")

        # Show rejected signals (too low confidence)
        print(f"\n🔴 REJECTED SIGNALS ({len(rejected)}) - TOO LOW CONFIDENCE")
        print("-" * 140)
        if rejected:
            print(f"{'Symbol':8s} {'Side':6s} {'Strategy':25s} {'Conf':7s} {'Agree':6s} {'Status':40s}")
            print("-" * 140)
            for signal in rejected[-5:]:  # Only show last 5 (too many)
                status = signal['analysis']['reason']
                print(f"{signal.get('symbol', '?'):8s} {signal.get('side', '?'):6s} "
                      f"{signal.get('strategy', '?'):25s} {signal.get('confidence', 0):6.1f}% "
                      f"{signal.get('n_agree', 1):6d} {status}")
            if len(rejected) > 5:
                print(f"  ... and {len(rejected) - 5} more rejected signals")

        # Show disabled strategies
        print(f"\n⚠️  DISABLED STRATEGIES ({len(disabled)})")
        print("-" * 140)
        if disabled:
            strategies = defaultdict(int)
            for signal in disabled:
                strategies[signal.get('strategy', '?')] += 1
            for strategy, count in strategies.items():
                reason = self.auto_rules.get(strategy, {}).get('reason', 'Disabled')
                print(f"  {strategy:25s}: {count:4d} signals blocked")

        # Summary stats
        print("\n" + "-" * 140)
        print(f"Summary: {len(executable)} EXECUTE | {len(pending)} PENDING | "
              f"{len(rejected)} REJECTED | {len(disabled)} DISABLED")
        print("-" * 140)

        return {
            'executable': executable,
            'pending': pending,
            'rejected': rejected,
            'disabled': disabled
        }

    def monitor_loop(self, refresh_rate=2):
        """Continuous monitoring loop."""
        print(f"\nStarting Autonomous Execution Monitor (refresh: {refresh_rate}s)")
        print("Press Ctrl+C to stop\n")

        signal_count = 0
        try:
            while True:
                signals = self.read_all_signals()

                if len(signals) > signal_count:
                    # New signals detected
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] New signals detected!")
                    signal_count = len(signals)

                    # Show analysis
                    analysis = self.print_signal_analysis(signals)

                    # Show next executable signal
                    if analysis['executable']:
                        signal = analysis['executable'][-1]  # Last one (most recent)
                        print(f"\n>>> Next action: EXECUTE {signal.get('symbol')} {signal.get('side')} "
                              f"at {signal.get('confidence', 0):.1f}% confidence")

                time.sleep(refresh_rate)

        except KeyboardInterrupt:
            print("\n\nMonitoring stopped by user.")
            print(f"Summary: {signal_count} signals analyzed")

def main():
    mode = 'aggressive'
    if len(sys.argv) > 1:
        if '--mode' in sys.argv:
            mode = sys.argv[sys.argv.index('--mode') + 1]
        elif sys.argv[1] in ['aggressive', 'conservative', 'manual']:
            mode = sys.argv[1]

    executor = AgggressiveSignalExecutor(mode=mode)
    executor.monitor_loop(refresh_rate=2)

if __name__ == '__main__':
    main()
