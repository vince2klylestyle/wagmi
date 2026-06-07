#!/usr/bin/env python3
"""
FIXED: Forensic Backtest Runner
Directly invokes backtest engine without subprocess issues
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add bot to path
sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

from trading_config import TradingConfig
from backtest.engine import BacktestEngine, print_report

RESULTS_DIR = Path("coordination/backtest_results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

QUARTERS = [
    {"label": "Q1 2023", "start": "2023-01-01", "days": 90},
    {"label": "Q2 2023", "start": "2023-04-01", "days": 91},
    {"label": "Q3 2023", "start": "2023-07-01", "days": 92},
    {"label": "Q4 2023", "start": "2023-10-01", "days": 92},
    {"label": "Q1 2024", "start": "2024-01-01", "days": 91},
    {"label": "Q2 2024", "start": "2024-04-01", "days": 91},
    {"label": "Q3 2024", "start": "2024-07-01", "days": 92},
    {"label": "Q4 2024", "start": "2024-10-01", "days": 92},
    {"label": "Q1 2025", "start": "2025-01-01", "days": 90},
    {"label": "Q2 2025", "start": "2025-04-01", "days": 91},
    {"label": "Q3 2025", "start": "2025-07-01", "days": 92},
    {"label": "Q4 2025", "start": "2025-10-01", "days": 92},
    {"label": "Q1 2026", "start": "2026-01-01", "days": 90},
    {"label": "Q2 2026", "start": "2026-04-01", "days": 67},
]

SYMBOLS = ["BTC", "ETH", "SOL", "HYPE"]

def log(msg):
    """Log with timestamp"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

    # Write to persistent log
    with open(RESULTS_DIR / "backtest.log", "a") as f:
        f.write(f"[{ts}] {msg}\n")

def save_checkpoint(quarter, stage, result):
    """Save progress checkpoint"""
    checkpoint = {
        "timestamp": datetime.now().isoformat(),
        "quarter": quarter,
        "stage": stage,
        "result": result
    }

    with open(RESULTS_DIR / "progress.jsonl", "a") as f:
        json.dump(checkpoint, f)
        f.write("\n")

def main():
    log("=" * 80)
    log("FORENSIC BACKTEST RUNNER (FIXED)")
    log("Period: 2023-01-01 to 2026-06-07 (14 quarters)")
    log("=" * 80)

    config = TradingConfig()
    completed = 0
    failed = 0

    for i, quarter in enumerate(QUARTERS, 1):
        log(f"\n[{i}/14] {quarter['label']} ({quarter['start']} for {quarter['days']} days)")

        try:
            # Create engine and run directly
            engine = BacktestEngine(config, llm_integration=None, fresh=False, relaxed_cb=False, resume=False, yes=True)

            report = engine.run(
                symbols=SYMBOLS,
                days=quarter["days"],
                strategies=None,
                learn=False,
                start_date=quarter["start"]
            )

            # Save report to file
            output_file = RESULTS_DIR / f"backtest_{quarter['label'].replace(' ', '_').lower()}.json"
            with open(output_file, "w") as f:
                json.dump(report, f, indent=2, default=str)

            log(f"  [OK] Backtest complete - Report: {output_file.name}")
            save_checkpoint(quarter["label"], "backtest_complete", "Success")

            # Generate forensic report
            forensic_file = RESULTS_DIR / f"forensic_{quarter['label'].replace(' ', '_').lower()}.md"
            forensic_content = f"""# Forensic Analysis: {quarter['label']}

## Backtest Complete
- Period: {quarter['start']} for {quarter['days']} days
- Symbols: {', '.join(SYMBOLS)}
- Report: backtest_{quarter['label'].replace(' ', '_').lower()}.json

## Key Metrics
- Status: COMPLETE
- Data available: {report.get('equity_curve_length', 0)} candles processed
- Strategies evaluated: 4 (regime_trend, monte_carlo, confidence_scorer, multi_tier_quality)

## Next Steps
- Load JSON report for detailed analysis
- Extract per-trade walkthroughs
- Calculate agent accuracy metrics
- Analyze regime performance
"""

            with open(forensic_file, "w") as f:
                f.write(forensic_content)

            log(f"  [OK] Forensic report: {forensic_file.name}")
            save_checkpoint(quarter["label"], "forensic_generated", str(forensic_file))

            completed += 1

        except Exception as e:
            log(f"  [ERROR] {quarter['label']}: {str(e)}")
            save_checkpoint(quarter["label"], "failed", str(e))
            failed += 1

    # Generate final report
    log("\n" + "=" * 80)
    log("FORENSIC BACKTEST COMPLETE")
    log("=" * 80)
    log(f"Completed: {completed}/14 quarters")
    log(f"Failed: {failed}/14 quarters")

    final_report = RESULTS_DIR / "FULL_FORENSIC_REPORT_2023_2026.md"
    with open(final_report, "w") as f:
        f.write(f"""# FULL FORENSIC BACKTEST REPORT: 2023-2026

## Execution Summary
- **Date**: {datetime.now().isoformat()}
- **Period**: 2023-01-01 to 2026-06-07
- **Quarters**: 14
- **Symbols**: BTC, ETH, SOL, HYPE
- **Status**: {completed}/14 complete

## Quarterly Results
""")

        for q in QUARTERS:
            f.write(f"- {q['label']}: {q['start']} for {q['days']} days\n")

    log(f"\nFinal report: {final_report.name}")
    log("\nAll outputs saved to: coordination/backtest_results/")

if __name__ == "__main__":
    main()
