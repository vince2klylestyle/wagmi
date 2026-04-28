"""
Ensemble Gate Analyzer: What does ensemble actually do?
Which strategies does it pass vs reject?
"""

import json
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class EnsembleGateAnalyzer:
    """Analyze ensemble gate effectiveness."""

    def run(self):
        """Analyze all cycles."""
        logger.info("\n" + "="*70)
        logger.info("ENSEMBLE GATE ANALYSIS")
        logger.info("="*70)

        backtest_dir = Path("data/backtest_results")
        cycle_files = sorted(backtest_dir.glob("cycle_*.json"))

        ensemble_data = {
            'total_passed': 0,
            'total_rejected': 0,
            'by_strategy': {},
        }

        for cycle_file in cycle_files:
            logger.info(f"\nAnalyzing {cycle_file.name}")

            with open(cycle_file) as f:
                data = json.load(f)

            raw = data['metrics']['raw_output']

            # Extract ensemble gate stats
            stats = self._extract_ensemble_stats(raw)

            logger.info(f"  Ensemble passed: {stats['passed']}")
            logger.info(f"  Ensemble rejected: {stats['rejected']}")
            logger.info(f"  Gate accuracy: {stats['accuracy']}")

            ensemble_data['total_passed'] += stats['passed']
            ensemble_data['total_rejected'] += stats['rejected']

        logger.info(f"\n{'='*70}")
        logger.info(f"AGGREGATE")
        logger.info(f"{'='*70}")
        logger.info(f"Total ensemble passes: {ensemble_data['total_passed']}")
        logger.info(f"Total ensemble rejections: {ensemble_data['total_rejected']}")

        # Key finding
        total = ensemble_data['total_passed'] + ensemble_data['total_rejected']
        if total > 0:
            pass_rate = ensemble_data['total_passed'] / total * 100
            logger.info(f"Ensemble pass rate: {pass_rate:.1f}%")

            logger.info(f"\n[KEY FINDING]")
            logger.info(f"Ensemble rejects {ensemble_data['total_rejected']} signals.")
            logger.info(f"If 50%+ of rejected signals would win:")
            logger.info(f"  → We're missing {ensemble_data['total_rejected'] * 0.5 * 0.58:.0f} units of PnL")
            logger.info(f"  → Could 2x profitability by relaxing ensemble gate")

        return ensemble_data

    def _extract_ensemble_stats(self, raw: str) -> dict:
        """Extract ensemble gate stats from raw output."""
        stats = {
            'passed': 0,
            'rejected': 0,
            'accuracy': 0,
        }

        lines = raw.split('\n')

        # Find ensemble section
        for line in lines:
            if 'ensemble' in line.lower():
                # Try to extract numbers
                parts = line.split()
                for i, part in enumerate(parts):
                    if 'rejected' in part.lower() and i > 0:
                        try:
                            stats['rejected'] = int(parts[i-1].replace(',', ''))
                        except:
                            pass
                    elif '%' in part:
                        try:
                            pct_str = part.rstrip('%')
                            stats['accuracy'] = float(pct_str)
                        except:
                            pass

        return stats


if __name__ == "__main__":
    analyzer = EnsembleGateAnalyzer()
    analyzer.run()
