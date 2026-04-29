#!/usr/bin/env python3
"""
UNIFIED MONITORING: Everything in one view
Shows both mechanical process (gates, regimes, signals) AND agent thinking (OBSERVE→REASON→DECIDE)
"""

import json
import time
import os
from pathlib import Path
from datetime import datetime
from collections import defaultdict

class UnifiedMonitor:
    def __init__(self, refresh_rate=3):
        self.refresh_rate = refresh_rate
        self.log_path = Path('/tmp/phase3_live_paper.log')
        self.data_dir = Path('bot/data')

    def read_recent_logs(self, lines=100):
        """Read last N lines from paper trading log."""
        if not self.log_path.exists():
            return []
        try:
            with open(self.log_path, 'r') as f:
                return f.readlines()[-lines:]
        except:
            return []

    def read_decisions(self):
        """Read signals, trades, thoughts from decisions.jsonl."""
        signals, trades, thoughts = [], [], []
        decisions_path = self.data_dir / 'decisions.jsonl'
        if not decisions_path.exists():
            return signals, trades, thoughts

        try:
            with open(decisions_path, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                        if record.get('type') == 'signal':
                            signals.append(record)
                        elif record.get('type') == 'trade':
                            trades.append(record)
                        elif record.get('type') == 'thought':
                            thoughts.append(record)
                    except:
                        pass
        except:
            pass

        return signals[-15:], trades[-10:], thoughts[-10:]

    def extract_regime(self, logs):
        """Extract current regime for each symbol."""
        regimes = {}
        for line in logs[-50:]:
            if '[REGIME]' in line:
                clean = line.replace('\x1b[0m', '').replace('\x1b[33m', '').replace('\x1b[32m', '')
                if '|' in clean:
                    parts = clean.split('[REGIME]')[1].split('|')
                    symbol_regime = parts[0].strip()
                    if ':' in symbol_regime:
                        symbol, regime = symbol_regime.split(':')
                        metrics = '|'.join(parts[1:]).strip() if len(parts) > 1 else ''
                        regimes[symbol.strip()] = (regime.strip(), metrics[:60])
        return regimes

    def extract_signals_in_flight(self, logs):
        """Extract signals currently being evaluated."""
        signals = []
        for line in logs[-30:]:
            if 'confidence' in line.lower() and ('[BUY]' in line or '[SELL]' in line or 'SIGNAL' in line):
                clean = line.replace('\x1b[0m', '').replace('\x1b[33m', '').replace('\x1b[32m', '')
                signals.append(clean.strip()[-100:])
        return signals[-5:]

    def extract_gate_decisions(self, logs):
        """Extract recent gate decisions."""
        decisions = []
        for line in logs[-40:]:
            if 'rejected' in line.lower() or ('gate' in line.lower() and 'decision' in line.lower()):
                clean = line.replace('\x1b[0m', '').replace('\x1b[33m', '').replace('\x1b[32m', '')
                decisions.append(clean.strip()[-100:])
        return decisions[-4:]

    def print_screen(self):
        """Print unified view."""
        os.system('clear' if os.name == 'posix' else 'cls')

        logs = self.read_recent_logs(100)
        signals, trades, thoughts = self.read_decisions()
        regimes = self.extract_regime(logs)
        signals_in_flight = self.extract_signals_in_flight(logs)
        gate_decisions = self.extract_gate_decisions(logs)

        print("\n" + "="*140)
        print(" UNIFIED MONITOR — MECHANICAL PROCESS + AGENT THINKING")
        print("="*140)

        # ─────────────────────────────────────────────────────────────────
        # MECHANICAL PROCESS (Left side)
        # ─────────────────────────────────────────────────────────────────
        print("\n┌─── MECHANICAL PROCESS ─────────────────────────────────┐" + "─"*67 + "┐")

        print("│ CURRENT REGIMES                                         │" + " "*67 + "│")
        for symbol in ['BTC', 'ETH', 'SOL', 'HYPE']:
            if symbol in regimes:
                regime, metrics = regimes[symbol]
                emoji = {'trending_bull': '🟢', 'trending_bear': '🔴', 'range': '⚪',
                        'high_volatility': '⚡', 'low_liquidity': '💧'}.get(regime, '❓')
                print(f"│  {emoji} {symbol:6s} → {regime:18s}  {metrics:30s} │" + " "*67 + "│")

        print("│                                                         │" + " "*67 + "│")
        print("│ SIGNALS BEING EVALUATED                                 │" + " "*67 + "│")
        for sig in signals_in_flight[-3:]:
            print(f"│  {sig[:55]:55s} │" + " "*67 + "│")

        print("│                                                         │" + " "*67 + "│")
        print("│ GATE DECISIONS (PASS/REJECT)                           │" + " "*67 + "│")
        for gate in gate_decisions[-3:]:
            print(f"│  {gate[:55]:55s} │" + " "*67 + "│")

        # ─────────────────────────────────────────────────────────────────
        # AGENT THINKING (Right side)
        # ─────────────────────────────────────────────────────────────────
        print("│                                                         │ AGENT REASONING  │")
        print("│ RECENT TRADES EXECUTED                                 │" + "─"*37 + "│")
        for i, trade in enumerate(trades[-3:]):
            symbol = trade.get('symbol', '?')
            side = trade.get('side', '?')[0]
            pnl = trade.get('pnl', 0)
            pnl_str = f"${pnl:+.2f}" if pnl else "OPEN"
            emoji = '✅' if pnl and pnl > 0 else '❌' if pnl and pnl < 0 else '🔄'
            print(f"│  {emoji} {symbol} {side} @ {pnl_str:8s}                          │ ", end="")

            # Show corresponding agent thought
            if i < len(thoughts):
                thought = thoughts[-(i+1)]
                agent = thought.get('agent', '?')[:12]
                decision = thought.get('decision', '')[:30]
                print(f"Agent: {agent:12s}                │")
            else:
                print(" "*37 + "│")

        print("│                                                         │" + " "*37 + "│")

        # ─────────────────────────────────────────────────────────────────
        # COMBINED: SIGNAL QUALITY + AGENT ASSESSMENT
        # ─────────────────────────────────────────────────────────────────
        print("└─────────────────────────────────────────────────────────┴─────────────────────────────────────────────┘")
        print()

        # Show sample agent thought in detail
        if thoughts:
            latest_thought = thoughts[-1]
            print("╔" + "═"*138 + "╗")
            print("║ LATEST AGENT REASONING CHAIN (OBSERVE → RECALL → REASON → DECIDE → JUSTIFY)")
            print("╠" + "═"*138 + "╣")

            agent = latest_thought.get('agent', 'Unknown')
            phase = latest_thought.get('phase', 'Unknown')
            symbol = latest_thought.get('symbol', '?')
            timestamp = latest_thought.get('timestamp', '')

            print(f"║ Agent: {agent:15s} | Symbol: {symbol:6s} | Phase: {phase:15s} | Time: {timestamp:20s}" + " "*48 + "║")
            print("║" + " "*138 + "║")

            if 'observation' in latest_thought:
                obs = latest_thought['observation'][:130]
                print(f"║ [OBSERVE] {obs:<128s} ║")

            if 'recall' in latest_thought:
                rec = latest_thought['recall'][:130]
                print(f"║ [RECALL]  {rec:<128s} ║")

            if 'reason' in latest_thought:
                rea = latest_thought['reason'][:130]
                print(f"║ [REASON]  {rea:<128s} ║")

            if 'decision' in latest_thought:
                dec = latest_thought['decision'][:130]
                print(f"║ [DECIDE]  {dec:<128s} ║")

            if 'justify' in latest_thought:
                jus = latest_thought['justify'][:130]
                print(f"║ [JUSTIFY] {jus:<128s} ║")

            print("╚" + "═"*138 + "╝")

        # ─────────────────────────────────────────────────────────────────
        # SUMMARY METRICS
        # ─────────────────────────────────────────────────────────────────
        print()
        print("📊 SUMMARY METRICS")
        print("─" * 140)

        executed = sum(1 for s in signals if s.get('executed'))
        rejected = len(signals) - executed

        wins = sum(1 for t in trades if t.get('pnl', 0) > 0)
        losses = sum(1 for t in trades if t.get('pnl', 0) < 0)
        total_pnl = sum(t.get('pnl', 0) for t in trades)

        print(f"  Signals Generated: {len(signals):3d} | Executed: {executed:2d} ({executed*100//max(len(signals),1):2d}%) | Rejected: {rejected:2d}")
        print(f"  Trades: {len(trades):2d} | Wins: {wins:2d} | Losses: {losses:2d} | Win Rate: {wins*100//max(len(trades),1)}% | Total P&L: ${total_pnl:+.2f}")
        print(f"  Regimes Active: {len(regimes)} | Gate Decisions: {len(gate_decisions)} | Agent Thoughts: {len(thoughts)}")

        print()
        print(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')} | Refreshing every {self.refresh_rate}s (Ctrl+C to exit)")
        print("─" * 140)

    def run(self):
        """Run monitor loop."""
        try:
            while True:
                self.print_screen()
                time.sleep(self.refresh_rate)
        except KeyboardInterrupt:
            print("\nMonitor stopped.")

if __name__ == '__main__':
    import sys
    rate = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    monitor = UnifiedMonitor(refresh_rate=rate)
    monitor.run()
