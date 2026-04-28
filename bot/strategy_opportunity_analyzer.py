"""
Strategy Opportunity Analyzer: For each disabled strategy, estimate edge if enabled.
"""

import json
from pathlib import Path
import logging
import re

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class StrategyOpportunityAnalyzer:
    """Analyze hidden alpha in disabled strategies."""

    def run(self):
        """Analyze all cycles."""
        logger.info("\n" + "="*70)
        logger.info("STRATEGY OPPORTUNITY ANALYSIS")
        logger.info("Hidden Alpha in Disabled Strategies")
        logger.info("="*70)

        backtest_dir = Path("data/backtest_results")
        cycle_files = sorted(backtest_dir.glob("cycle_*.json"))

        strategies = {
            'monte_carlo_zones': [],
            'regime_trend': [],
            'bollinger_squeeze': [],
            'confidence_scorer': [],
            'multi_tier_quality': [],
        }

        for cycle_file in cycle_files:
            with open(cycle_file) as f:
                data = json.load(f)

            raw = data['metrics']['raw_output']

            # Extract solo strategy performance
            for strat in strategies.keys():
                result = self._extract_strategy_performance(raw, strat)
                if result:
                    strategies[strat].append(result)

        logger.info("\n" + "="*70)
        logger.info("SUMMARY: Alpha Available by Strategy")
        logger.info("="*70)

        for strat, results in strategies.items():
            if results:
                avg_wr = sum(r['wr'] for r in results) / len(results)
                avg_alpha = sum(r['alpha'] for r in results) / len(results)
                total_signals = sum(r['signals'] for r in results)

                logger.info(f"\n{strat.upper()}")
                logger.info(f"  Signals (disabled): {total_signals}")
                logger.info(f"  Win Rate: {avg_wr:.0f}%")
                logger.info(f"  Alpha: {avg_alpha:.0f}%")
                logger.info(f"  Value: {'HIGH' if avg_wr > 55 else 'MEDIUM' if avg_wr > 45 else 'LOW'}")

                if avg_wr > 55:
                    logger.info(f"  → ENABLE THIS (high confidence edge)")
                elif avg_wr > 50:
                    logger.info(f"  → TEST this (marginal edge)")
                else:
                    logger.info(f"  → KEEP DISABLED (no edge)")

        return strategies

    def _extract_strategy_performance(self, raw: str, strat_name: str) -> dict | None:
        """Extract solo strategy performance."""
        lines = raw.split('\n')

        for line in lines:
            if strat_name in line and '%' in line:
                # Format: strategy_name Missed Won Lost WR% Alpha%
                parts = line.split()

                try:
                    # Find the percentages
                    for i, part in enumerate(parts):
                        if '%' in part:
                            wr_str = part.rstrip('%')
                            wr = float(wr_str)

                            # Look for more percentages (alpha)
                            for j in range(i+1, min(i+3, len(parts))):
                                if '%' in parts[j]:
                                    alpha_str = parts[j].rstrip('%').lstrip('+')
                                    alpha = float(alpha_str)

                                    # Extract signal count
                                    for k in range(len(parts)):
                                        if parts[k].isdigit():
                                            signals = int(parts[k])
                                            return {
                                                'strategy': strat_name,
                                                'signals': signals,
                                                'wr': wr,
                                                'alpha': alpha,
                                            }

                                    return {
                                        'strategy': strat_name,
                                        'signals': 0,
                                        'wr': wr,
                                        'alpha': alpha,
                                    }
                except:
                    pass

        return None


if __name__ == "__main__":
    analyzer = StrategyOpportunityAnalyzer()
    analyzer.run()
