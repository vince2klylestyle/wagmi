"""
Signal Forensics: Extract complete ledger of every signal + outcome.
Fast iteration - get all data now.
"""

import json
from pathlib import Path
from typing import Dict, List, Any
import re
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class SignalForensicsAuditor:
    """Extract complete signal ledger from backtest cycles."""

    def __init__(self):
        self.backtest_dir = Path("data/backtest_results")
        self.signals = []

    def extract_from_raw_output(self, raw: str, cycle_num: int) -> List[Dict]:
        """Extract all signal data from raw backtest output."""
        signals = []

        # Extract executed trades (known winners)
        lines = raw.split('\n')

        # Find trade execution section
        in_trades = False
        for i, line in enumerate(lines):
            if 'Trade execution' in line or 'Positions' in line:
                in_trades = True
                continue

            if in_trades and ('════' in line or 'Solo Strategy' in line):
                break

            # Look for trade entries: symbol, direction, entry, sl, tp
            if in_trades and any(s in line for s in ['BTC', 'ETH', 'SOL', 'HYPE']):
                # Try to extract trade data
                signal = self._parse_trade_line(line, cycle_num)
                if signal:
                    signals.append(signal)

        # Extract rejected signals (gated out)
        rejected = self._extract_rejected_signals(raw, cycle_num)
        signals.extend(rejected)

        return signals

    def _extract_rejected_signals(self, raw: str, cycle_num: int) -> List[Dict]:
        """Extract signals that were rejected at gates."""
        rejected = []

        lines = raw.split('\n')
        in_rejected = False

        for line in lines:
            if 'insufficient_votes' in line or 'confidence_floor' in line or 'ev_floor' in line:
                # Extract rejected signal info
                parts = line.split()
                if len(parts) > 2:
                    signal = {
                        'cycle': cycle_num,
                        'strategy': self._extract_strategy(line),
                        'symbol': self._extract_symbol(line),
                        'executed': False,
                        'rejected_reason': self._extract_rejection_reason(line),
                        'confidence': self._extract_confidence(line),
                    }
                    if signal['strategy']:
                        rejected.append(signal)

        return rejected

    def _parse_trade_line(self, line: str, cycle_num: int) -> Dict | None:
        """Parse executed trade line."""
        symbols = ['BTC', 'ETH', 'SOL', 'HYPE']

        for symbol in symbols:
            if symbol in line:
                return {
                    'cycle': cycle_num,
                    'symbol': symbol,
                    'strategy': self._extract_strategy(line),
                    'setup': self._extract_setup(line),
                    'regime': self._extract_regime(line),
                    'executed': True,
                    'outcome': 'WIN' if self._is_profitable(line) else 'LOSS',
                    'confidence': self._extract_confidence(line),
                }

        return None

    def _extract_strategy(self, line: str) -> str:
        for strat in ['monte_carlo', 'regime_trend', 'bollinger', 'confidence_scorer', 'multi_tier']:
            if strat in line.lower():
                return strat
        return 'unknown'

    def _extract_symbol(self, line: str) -> str:
        for sym in ['BTC', 'ETH', 'SOL', 'HYPE']:
            if sym in line:
                return sym
        return 'unknown'

    def _extract_setup(self, line: str) -> str:
        for setup in ['trend_follow', 'mean_reversion', 'breakout', 'support_resist']:
            if setup in line.lower():
                return setup
        return 'unknown'

    def _extract_regime(self, line: str) -> str:
        for regime in ['trending_bull', 'trending_bear', 'ranging', 'consolidation', 'volatile']:
            if regime in line.lower():
                return regime
        return 'unknown'

    def _extract_confidence(self, line: str) -> float:
        match = re.search(r'(\d+)%', line)
        return float(match.group(1)) if match else 0.0

    def _extract_rejection_reason(self, line: str) -> str:
        if 'insufficient_votes' in line:
            return 'insufficient_votes'
        elif 'confidence_floor' in line:
            return 'confidence_floor'
        elif 'ev_floor' in line:
            return 'ev_floor'
        elif 'fee_drag' in line:
            return 'fee_drag'
        return 'unknown'

    def _is_profitable(self, line: str) -> bool:
        return '+' in line or 'WIN' in line.upper()

    def run(self) -> Dict[str, Any]:
        """Run complete forensics on all cycles."""
        logger.info("\n" + "="*70)
        logger.info("SIGNAL FORENSICS AUDIT")
        logger.info("="*70)

        cycle_files = sorted(self.backtest_dir.glob("cycle_*.json"))

        for cycle_file in cycle_files:
            logger.info(f"\nProcessing {cycle_file.name}")

            with open(cycle_file) as f:
                data = json.load(f)

            cycle_num = int(cycle_file.name.split('_')[1])
            raw_output = data['metrics']['raw_output']

            signals = self.extract_from_raw_output(raw_output, cycle_num)
            self.signals.extend(signals)

        # Aggregate results
        results = {
            'total_signals': len(self.signals),
            'executed': len([s for s in self.signals if s['executed']]),
            'rejected': len([s for s in self.signals if not s['executed']]),
            'signals': self.signals,
            'by_strategy': self._aggregate_by_strategy(),
            'by_symbol': self._aggregate_by_symbol(),
            'by_regime': self._aggregate_by_regime(),
            'by_setup': self._aggregate_by_setup(),
            'rejection_analysis': self._analyze_rejections(),
        }

        logger.info(f"\nTotal Signals: {results['total_signals']}")
        logger.info(f"Executed: {results['executed']}")
        logger.info(f"Rejected: {results['rejected']}")
        logger.info(f"Execution Rate: {results['executed']/max(1, results['total_signals'])*100:.1f}%")

        # Save
        with open('data/signal_forensics.json', 'w') as f:
            json.dump(results, f, indent=2)

        logger.info("\n[SAVED] Signal forensics to data/signal_forensics.json")

        return results

    def _aggregate_by_strategy(self) -> Dict:
        agg = {}
        for signal in self.signals:
            strat = signal.get('strategy', 'unknown')
            if strat not in agg:
                agg[strat] = {'total': 0, 'executed': 0, 'rejected': 0}
            agg[strat]['total'] += 1
            if signal['executed']:
                agg[strat]['executed'] += 1
            else:
                agg[strat]['rejected'] += 1
        return agg

    def _aggregate_by_symbol(self) -> Dict:
        agg = {}
        for signal in self.signals:
            sym = signal.get('symbol', 'unknown')
            if sym not in agg:
                agg[sym] = {'total': 0, 'executed': 0, 'rejected': 0}
            agg[sym]['total'] += 1
            if signal['executed']:
                agg[sym]['executed'] += 1
            else:
                agg[sym]['rejected'] += 1
        return agg

    def _aggregate_by_regime(self) -> Dict:
        agg = {}
        for signal in self.signals:
            regime = signal.get('regime', 'unknown')
            if regime not in agg:
                agg[regime] = {'total': 0, 'executed': 0, 'rejected': 0}
            agg[regime]['total'] += 1
            if signal['executed']:
                agg[regime]['executed'] += 1
            else:
                agg[regime]['rejected'] += 1
        return agg

    def _aggregate_by_setup(self) -> Dict:
        agg = {}
        for signal in self.signals:
            setup = signal.get('setup', 'unknown')
            if setup not in agg:
                agg[setup] = {'total': 0, 'executed': 0, 'rejected': 0}
            agg[setup]['total'] += 1
            if signal['executed']:
                agg[setup]['executed'] += 1
            else:
                agg[setup]['rejected'] += 1
        return agg

    def _analyze_rejections(self) -> Dict:
        reasons = {}
        for signal in self.signals:
            if not signal['executed']:
                reason = signal['rejected_reason']
                if reason not in reasons:
                    reasons[reason] = 0
                reasons[reason] += 1

        # Sort by count
        return dict(sorted(reasons.items(), key=lambda x: x[1], reverse=True))


if __name__ == "__main__":
    auditor = SignalForensicsAuditor()
    auditor.run()
