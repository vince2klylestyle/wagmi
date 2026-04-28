"""
Bottleneck Ranker: Identify top rejection reasons + estimate opportunity value.
"""

import json
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class BottleneckRanker:
    """Rank all rejections by opportunity value."""

    def __init__(self):
        self.backtest_dir = Path("data/backtest_results")

    def analyze_all_cycles(self) -> dict:
        """Analyze rejections across all cycles."""
        logger.info("\n" + "="*70)
        logger.info("BOTTLENECK ANALYSIS: Where We're Losing Alpha")
        logger.info("="*70)

        bottlenecks = {
            'insufficient_votes': {'count': 0, 'details': []},
            'confidence_floor': {'count': 0, 'details': []},
            'ev_floor': {'count': 0, 'details': []},
            'fee_drag': {'count': 0, 'details': []},
            'risk_filter': {'count': 0, 'details': []},
        }

        cycle_files = sorted(self.backtest_dir.glob("cycle_*.json"))

        for cycle_file in cycle_files:
            with open(cycle_file) as f:
                data = json.load(f)

            raw = data['metrics']['raw_output']
            cycle_metrics = self._extract_cycle_metrics(raw)

            # Extract rejection breakdown
            rejections = self._extract_rejections_from_raw(raw)
            for reason, count in rejections.items():
                if reason in bottlenecks:
                    bottlenecks[reason]['count'] += count

        # Rank by opportunity
        ranked = self._rank_by_opportunity(bottlenecks)

        logger.info("\nRejection Breakdown (ranked by opportunity):")
        for i, (reason, data) in enumerate(ranked, 1):
            count = data['count']
            opportunity = data['opportunity']
            logger.info(f"  {i}. {reason}: {count} signals → {opportunity}")

        return bottlenecks

    def _extract_cycle_metrics(self, raw: str) -> dict:
        """Extract key metrics from cycle."""
        metrics = {
            'total_signals': 0,
            'executed': 0,
            'rejected': 0,
        }

        if 'Signal gen:' in raw:
            idx = raw.find('Signal gen:')
            num_str = ""
            for c in raw[idx+10:idx+20]:
                if c.isdigit() or c in ',.':
                    num_str += c
                elif num_str:
                    break
            try:
                metrics['total_signals'] = int(num_str.replace(',', ''))
            except:
                pass

        return metrics

    def _extract_rejections_from_raw(self, raw: str) -> dict:
        """Extract rejection reasons from backtest output."""
        rejections = {
            'insufficient_votes': 0,
            'confidence_floor': 0,
            'ev_floor': 0,
            'fee_drag': 0,
            'risk_filter': 0,
        }

        lines = raw.split('\n')

        # Find rejection section
        for line in lines:
            if 'insufficient_votes' in line:
                # Try to extract count
                parts = line.split()
                for part in parts:
                    if part.isdigit():
                        rejections['insufficient_votes'] += int(part)
                        break

            elif 'confidence_floor' in line:
                parts = line.split()
                for part in parts:
                    if part.isdigit():
                        rejections['confidence_floor'] += int(part)
                        break

            elif 'ev_floor' in line:
                parts = line.split()
                for part in parts:
                    if part.isdigit():
                        rejections['ev_floor'] += int(part)
                        break

            elif 'fee_drag' in line:
                parts = line.split()
                for part in parts:
                    if part.isdigit():
                        rejections['fee_drag'] += int(part)
                        break

        return rejections

    def _rank_by_opportunity(self, bottlenecks: dict) -> list:
        """Rank bottlenecks by opportunity value."""
        # Estimate WR for each rejection reason
        wr_estimates = {
            'insufficient_votes': 0.50,  # Ensemble disagreed - might be 50/50
            'confidence_floor': 0.35,    # Low confidence = probably bad
            'ev_floor': 0.30,            # Negative expected value = bad
            'fee_drag': 0.45,            # Fees kill trade but signal might be ok
            'risk_filter': 0.40,         # Risk filter cautious
        }

        ranked = []
        for reason, data in bottlenecks.items():
            count = data['count']
            est_wr = wr_estimates.get(reason, 0.45)
            # Opportunity = (signals) × (estimated profitability)
            opportunity = count * (est_wr - 0.5)  # Subtract 50% baseline
            ranked.append((reason, {
                'count': count,
                'est_wr': est_wr,
                'opportunity': f"{opportunity:.0f} signal-value"
            }))

        ranked.sort(key=lambda x: x[1]['opportunity'], reverse=True)
        return ranked

    def run(self) -> dict:
        """Run complete bottleneck analysis."""
        return self.analyze_all_cycles()


if __name__ == "__main__":
    ranker = BottleneckRanker()
    ranker.run()
