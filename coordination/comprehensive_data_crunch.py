#!/usr/bin/env python3
"""
COMPREHENSIVE DATA CRUNCH - Extract MAXIMUM insights from all backtest data
Runs after backtest completes to analyze every aspect of the 14-quarter forensic audit
"""

import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from collections import defaultdict

RESULTS_DIR = Path("coordination/backtest_results")

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

def crunch_all_data():
    """Extract maximum data from all backtest results"""

    log("=" * 80)
    log("COMPREHENSIVE DATA CRUNCH: All 14 Quarters (2023-2026)")
    log("=" * 80)

    # Find all progress checkpoints
    progress_file = RESULTS_DIR / "progress.jsonl"
    checkpoints = []

    if progress_file.exists():
        log(f"\nReading {progress_file.name}...")
        with open(progress_file, "r") as f:
            for i, line in enumerate(f, 1):
                try:
                    cp = json.loads(line)
                    checkpoints.append(cp)
                except:
                    pass
        log(f"  Loaded {len(checkpoints)} checkpoints")

    # Analyze progress by quarter
    log("\nPROGRESS SUMMARY BY QUARTER:")
    by_quarter = defaultdict(list)
    for cp in checkpoints:
        q = cp.get("quarter", "unknown")
        stage = cp.get("stage", "unknown")
        by_quarter[q].append(stage)

    for q in sorted(by_quarter.keys()):
        stages = " -> ".join(by_quarter[q])
        log(f"  {q}: {stages}")

    # Count completion status
    log("\nCOMPLETION STATUS:")
    total_quarters = 14
    backtest_complete = sum(1 for cp in checkpoints if cp.get("stage") == "backtest_complete")
    forensic_complete = sum(1 for cp in checkpoints if cp.get("stage") == "forensic_generated")

    log(f"  Backtest runs completed: {backtest_complete}/{total_quarters}")
    log(f"  Forensic reports generated: {forensic_complete}/{total_quarters}")

    # Check for final report
    final_report = RESULTS_DIR / "FULL_FORENSIC_REPORT_2023_2026.md"
    if final_report.exists():
        log(f"  Final synthesis report: COMPLETE")
    else:
        log(f"  Final synthesis report: PENDING")

    # Analyze backtest.log for statistics
    log("\nBACKTEST LOG ANALYSIS:")
    log_file = RESULTS_DIR / "backtest.log"
    if log_file.exists():
        with open(log_file, "r", errors="ignore") as f:
            lines = f.readlines()

        log(f"  Log lines: {len(lines)}")

        # Count key metrics
        data_coverage_lines = [l for l in lines if "Data Coverage" in l]
        circuit_breaker_lines = [l for l in lines if "Circuit breaker" in l]
        pnl_lines = [l for l in lines if "PnL" in l or "equity" in l]

        log(f"  Data coverage mentions: {len(data_coverage_lines)}")
        log(f"  Circuit breaker mentions: {len(circuit_breaker_lines)}")
        log(f"  PnL-related lines: {len(pnl_lines)}")

        # Show last few lines
        log("\n  Last 5 log entries:")
        for line in lines[-5:]:
            log(f"    {line.strip()}")

    # List all output files
    log("\nOUTPUT FILES:")
    output_files = sorted(RESULTS_DIR.glob("*"))
    for f in output_files:
        size = f.stat().st_size if f.is_file() else 0
        log(f"  {f.name} ({size:,} bytes)")

    # Analyze forensic reports
    log("\nFORENSIC REPORTS ANALYSIS:")
    forensic_files = sorted(RESULTS_DIR.glob("forensic_*.md"))
    log(f"  Total forensic reports: {len(forensic_files)}")

    if forensic_files:
        log("  Forensic reports generated:")
        for f in forensic_files:
            size = f.stat().st_size
            log(f"    {f.name} ({size} bytes)")

    # Summary statistics
    log("\nOVERALL SUMMARY:")
    log(f"  Period: 2023-01-01 to 2026-06-07")
    log(f"  Quarters analyzed: {len(by_quarter)}")
    log(f"  Checkpoints saved: {len(checkpoints)}")
    log(f"  Backtest completion rate: {backtest_complete}/{total_quarters}")
    log(f"  Report generation rate: {forensic_complete}/{total_quarters}")

    log("\n" + "=" * 80)
    log("DATA CRUNCH COMPLETE")
    log("=" * 80)

    return {
        "checkpoints": len(checkpoints),
        "by_quarter": dict(by_quarter),
        "backtest_complete": backtest_complete,
        "forensic_complete": forensic_complete,
        "total_quarters": total_quarters
    }

if __name__ == "__main__":
    results = crunch_all_data()

    # Save summary
    summary_file = RESULTS_DIR / "data_crunch_summary.json"
    with open(summary_file, "w") as f:
        json.dump(results, f, indent=2, default=str)

    log(f"\nSummary saved to: {summary_file}")
