#!/usr/bin/env python3
"""
Real-time CLI monitoring dashboard for WAGMI trading system.
Shows live market analysis, agent thinking, signal generation, and system health.

Usage:
  python cli_monitor.py [mode] [refresh_rate]

Modes:
  live      - Real-time trading signals and executions (2s refresh)
  analysis  - Detailed market regime analysis and agent decisions (5s refresh)
  signals   - Signal pipeline breakdown with gate rejections (2s refresh)
  thinking  - Agent thought protocol and reasoning (5s refresh)
  health    - System health, memory, performance metrics (10s refresh)
  full      - All modes combined (10s refresh)
"""

import json
import time
import os
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import sys

class CLIMonitor:
    def __init__(self, mode='full', refresh_rate=None):
        self.mode = mode
        self.data_dir = Path('bot/data')
        self.log_path = Path('/tmp/phase3_live_paper.log')

        if refresh_rate is None:
            refresh_rate = {'live': 2, 'analysis': 5, 'signals': 2, 'thinking': 5, 'health': 10, 'full': 10}
            self.refresh_rate = refresh_rate.get(mode, 5)
        else:
            self.refresh_rate = refresh_rate

        self.last_stats = {}
        self.signal_buffer = []
        self.trade_buffer = []

    def read_decisions_log(self):
        """Read recent decisions from JSONL log."""
        decisions_path = self.data_dir / 'decisions.jsonl'
        if not decisions_path.exists():
            return [], [], []

        signals, trades, thoughts = [], [], []
        try:
            with open(decisions_path, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                        record_type = record.get('type', '')

                        if record_type == 'signal':
                            signals.append(record)
                        elif record_type == 'trade':
                            trades.append(record)
                        elif record_type == 'thought':
                            thoughts.append(record)
                    except:
                        pass
        except:
            pass

        return signals[-20:], trades[-10:], thoughts[-10:]

    def read_paper_log(self, lines=50):
        """Read recent paper trading log."""
        if not self.log_path.exists():
            return []

        try:
            with open(self.log_path, 'r') as f:
                all_lines = f.readlines()
                return all_lines[-lines:]
        except:
            return []

    def extract_regime_info(self, log_lines):
        """Extract regime classification from logs."""
        regimes = {}
        for line in log_lines:
            if '[REGIME]' in line:
                # Parse: [REGIME] BTC: high_volatility | ADX=41.1 ATR%=0.576
                parts = line.split('[REGIME]')
                if len(parts) > 1:
                    content = parts[1]
                    if '|' in content:
                        symbol_regime = content.split('|')[0].strip()
                        metrics = content.split('|')[1:] if len(content.split('|')) > 1 else []
                        if ':' in symbol_regime:
                            symbol, regime = symbol_regime.split(':')
                            regimes[symbol.strip()] = {
                                'regime': regime.strip(),
                                'metrics': ' | '.join(metrics).strip()
                            }
        return regimes

    def print_header(self):
        """Print monitor header."""
        print("\n" + "="*120)
        print(f"WAGMI TRADING SYSTEM - LIVE MONITOR [{self.mode.upper()}]")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("="*120 + "\n")

    def display_live_mode(self):
        """Show real-time trading signals and executions."""
        self.print_header()

        signals, trades, _ = self.read_decisions_log()
        log_lines = self.read_paper_log(30)
        regimes = self.extract_regime_info(log_lines)

        print("📊 CURRENT MARKET REGIMES")
        print("-" * 120)
        for symbol, regime_info in regimes.items():
            regime = regime_info['regime']
            metrics = regime_info['metrics']
            regime_emoji = {'trending_bull': '🟢', 'trending_bear': '🔴', 'range': '⚪',
                          'high_volatility': '⚡', 'low_liquidity': '💧'}.get(regime, '❓')
            print(f"  {regime_emoji} {symbol:6s} → {regime:20s}  {metrics}")

        print("\n📈 RECENT SIGNALS (Last 5)")
        print("-" * 120)
        for signal in signals[-5:]:
            symbol = signal.get('symbol', '?')
            side = signal.get('side', '?')
            confidence = signal.get('confidence', 0)
            strategy = signal.get('strategy', '?')
            timestamp = signal.get('timestamp', '')
            executed = signal.get('executed', False)

            exec_mark = '✅' if executed else '⏳'
            side_emoji = '🟢 BUY' if side == 'BUY' else '🔴 SELL'
            conf_bar = '█' * int(confidence / 10) + '░' * (10 - int(confidence / 10))

            print(f"  {exec_mark} {symbol:6s} {side_emoji:8s} [{conf_bar}] {confidence:5.1f}% | {strategy:20s}")

        print("\n💰 EXECUTED TRADES (Last 5)")
        print("-" * 120)
        for trade in trades[-5:]:
            symbol = trade.get('symbol', '?')
            side = trade.get('side', '?')
            entry_price = trade.get('entry_price', 0)
            size = trade.get('size', 0)
            pnl = trade.get('pnl', None)
            timestamp = trade.get('timestamp', '')

            side_emoji = '🟢' if side == 'BUY' else '🔴'
            pnl_str = f"${pnl:+.2f}" if pnl is not None else 'OPEN'
            pnl_emoji = '✅' if pnl and pnl > 0 else '❌' if pnl and pnl < 0 else '🔄'

            print(f"  {pnl_emoji} {symbol:6s} {side_emoji} {side:4s} | Entry: {entry_price:10.2f} | Size: {size:8.4f} | {pnl_str}")

        # Extract recent activity from logs
        print("\n⚙️ SYSTEM ACTIVITY (Last 10)")
        print("-" * 120)
        activity_lines = [l for l in log_lines if any(x in l for x in ['SIGNAL', 'TRADE', 'GATE', 'REJECTED'])]
        for line in activity_lines[-10:]:
            # Clean up ANSI codes
            clean_line = line.replace('\x1b[0m', '').replace('\x1b[33m', '').replace('\x1b[32m', '')
            clean_line = clean_line.split('[I]')[-1].split('[W]')[-1].split('[E]')[-1]
            print(f"  {clean_line[:110]}")

    def display_analysis_mode(self):
        """Show detailed market analysis and agent decisions."""
        self.print_header()

        log_lines = self.read_paper_log(100)
        regimes = self.extract_regime_info(log_lines)

        print("🧠 MARKET ANALYSIS BY SYMBOL")
        print("-" * 120)
        for symbol in ['BTC', 'ETH', 'SOL', 'HYPE']:
            regime_info = regimes.get(symbol, {})
            regime = regime_info.get('regime', 'UNKNOWN')
            metrics = regime_info.get('metrics', '')

            # Extract strategy performance for this symbol
            relevant_lines = [l for l in log_lines if symbol in l and 'strategy' in l.lower()]

            print(f"\n  {symbol}")
            print(f"    Regime: {regime}")
            if metrics:
                print(f"    Metrics: {metrics[:90]}")

        print("\n\n🔄 ENSEMBLE VOTING SUMMARY")
        print("-" * 120)
        ensemble_lines = [l for l in log_lines if 'ensemble' in l.lower() or 'vote' in l.lower()]
        for line in ensemble_lines[-5:]:
            clean = line.replace('\x1b[0m', '').replace('\x1b[33m', '').replace('\x1b[32m', '')
            print(f"  {clean[:110]}")

        print("\n\n⚖️ GATE DECISIONS")
        print("-" * 120)
        gate_lines = [l for l in log_lines if 'gate' in l.lower() or 'rejected' in l.lower() or 'filter' in l.lower()]
        for line in gate_lines[-8:]:
            clean = line.replace('\x1b[0m', '').replace('\x1b[33m', '').replace('\x1b[32m', '')
            print(f"  {clean[:110]}")

    def display_signals_mode(self):
        """Show signal pipeline with gate breakdown."""
        self.print_header()

        signals, _, _ = self.read_decisions_log()
        log_lines = self.read_paper_log(100)

        # Count signals by status
        executed = sum(1 for s in signals if s.get('executed'))
        rejected = len(signals) - executed

        print("📊 SIGNAL PIPELINE SUMMARY")
        print("-" * 120)
        print(f"  Generated:    {len(signals):4d}")
        print(f"  Executed:     {executed:4d} ({executed*100//max(len(signals),1):3d}%)")
        print(f"  Rejected:     {rejected:4d} ({rejected*100//max(len(signals),1):3d}%)")

        print("\n🚫 REJECTION GATES (from logs)")
        print("-" * 120)
        rejection_reasons = defaultdict(int)
        for line in log_lines:
            if 'rejected' in line.lower() or 'gate' in line.lower():
                if 'confidence' in line:
                    rejection_reasons['confidence_floor'] += 1
                if 'fee' in line:
                    rejection_reasons['fee_drag'] += 1
                if 'leverage' in line or 'liquidation' in line:
                    rejection_reasons['leverage_gate'] += 1
                if 'position' in line and 'limit' in line:
                    rejection_reasons['position_limit'] += 1
                if 'insufficient' in line:
                    rejection_reasons['insufficient_votes'] += 1
                if 'circuit' in line:
                    rejection_reasons['circuit_breaker'] += 1

        for gate, count in sorted(rejection_reasons.items(), key=lambda x: -x[1])[:8]:
            bar = '█' * min(count // 2, 30) + ('...' if count > 60 else '')
            print(f"  {gate:20s}: {count:4d} rejections {bar}")

        print("\n✅ RECENT ACCEPTED SIGNALS")
        print("-" * 120)
        accepted = [s for s in signals if s.get('executed')]
        for signal in accepted[-5:]:
            symbol = signal.get('symbol', '?')
            strategy = signal.get('strategy', '?')
            confidence = signal.get('confidence', 0)
            side = signal.get('side', '?')
            print(f"  {symbol:6s} | {side:4s} | {confidence:5.1f}% confidence | {strategy}")

    def display_thinking_mode(self):
        """Show agent thought protocol and reasoning."""
        self.print_header()

        _, _, thoughts = self.read_decisions_log()

        print("💭 AGENT REASONING (Last 10 Thoughts)")
        print("-" * 120)

        for i, thought in enumerate(thoughts[-10:], 1):
            agent = thought.get('agent', '?')
            phase = thought.get('phase', '?')
            timestamp = thought.get('timestamp', '')

            print(f"\n  [{i}] Agent: {agent} | Phase: {phase}")

            if 'observation' in thought:
                print(f"      OBSERVE: {thought['observation'][:100]}")
            if 'recall' in thought:
                print(f"      RECALL:  {thought['recall'][:100]}")
            if 'reason' in thought:
                print(f"      REASON:  {thought['reason'][:100]}")
            if 'decision' in thought:
                print(f"      DECIDE:  {thought['decision'][:100]}")

    def display_health_mode(self):
        """Show system health and performance metrics."""
        self.print_header()

        log_lines = self.read_paper_log(50)

        print("❤️ SYSTEM HEALTH")
        print("-" * 120)

        # Extract heartbeat metrics
        for line in log_lines[-20:]:
            if '[HEARTBEAT]' in line:
                # Parse heartbeat: equity=$10,000 positions=0 daily_pnl=$-8.34 WR20=0%
                parts = {}
                for segment in line.split():
                    if '=' in segment:
                        key, val = segment.split('=', 1)
                        parts[key] = val

                print(f"  Equity:       {parts.get('equity', 'N/A')}")
                print(f"  Daily P&L:    {parts.get('daily_pnl', 'N/A')}")
                print(f"  Positions:    {parts.get('positions', '0')}")
                print(f"  Win Rate 20:  {parts.get('WR20', 'N/A')}")
                print(f"  API Calls:    {parts.get('api', 'N/A')}")
                break

        # Extract warnings and errors
        print("\n⚠️ WARNINGS & ERRORS (Last 5)")
        print("-" * 120)
        issues = [l for l in log_lines if '[W]' in l or '[E]' in l]
        for line in issues[-5:]:
            clean = line.replace('\x1b[0m', '').replace('\x1b[33m', '').replace('\x1b[32m', '')
            print(f"  {clean[:110]}")

        print("\n✅ OPERATIONAL STATUS")
        print("-" * 120)
        print(f"  Paper Trading: {'🟢 RUNNING' if self.log_path.exists() else '🔴 OFFLINE'}")
        print(f"  Log Path:      {self.log_path}")
        print(f"  Data Dir:      {self.data_dir}")
        print(f"  Last Update:   {datetime.now().strftime('%H:%M:%S')}")

    def run(self):
        """Run monitor loop."""
        try:
            while True:
                os.system('clear' if os.name == 'posix' else 'cls')

                if self.mode == 'live':
                    self.display_live_mode()
                elif self.mode == 'analysis':
                    self.display_analysis_mode()
                elif self.mode == 'signals':
                    self.display_signals_mode()
                elif self.mode == 'thinking':
                    self.display_thinking_mode()
                elif self.mode == 'health':
                    self.display_health_mode()
                elif self.mode == 'full':
                    self.display_live_mode()
                    print("\n")
                    self.display_analysis_mode()

                print("\n" + "="*120)
                print(f"Refreshing in {self.refresh_rate}s... (Press Ctrl+C to exit)")
                time.sleep(self.refresh_rate)
        except KeyboardInterrupt:
            print("\n\nMonitor stopped.")

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'live'
    rate = int(sys.argv[2]) if len(sys.argv) > 2 else None

    monitor = CLIMonitor(mode=mode, refresh_rate=rate)
    monitor.run()
