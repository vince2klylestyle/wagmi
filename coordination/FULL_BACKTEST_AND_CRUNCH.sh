#!/bin/bash
# FULL FORENSIC BACKTEST + COMPREHENSIVE DATA CRUNCH
# Runs backtest to completion, then extracts maximum data insights

set -e

cd "$(dirname "$0")/.."

echo "======================================================================"
echo "FULL FORENSIC BACKTEST + COMPREHENSIVE DATA CRUNCH"
echo "======================================================================"
echo ""
echo "Phase 1: Run full forensic backtest (14 quarters, 2023-2026)"
echo ""

# Clean old results
rm -rf coordination/backtest_results/* || true

# Start backtest and monitor
echo "Launching backtest runner..."
python coordination/run_full_forensic_backtest.py &
BACKTEST_PID=$!

echo "Launching monitor..."
sleep 2
python coordination/monitor_backtest.py &
MONITOR_PID=$!

echo ""
echo "Backtest running (PID $BACKTEST_PID)..."
echo "Monitor running (PID $MONITOR_PID)..."
echo ""

# Wait for backtest to complete
echo "Waiting for backtest to complete..."
wait $BACKTEST_PID
BACKTEST_STATUS=$?

echo ""
if [ $BACKTEST_STATUS -eq 0 ]; then
    echo "✓ Backtest completed successfully"
else
    echo "✗ Backtest failed with exit code $BACKTEST_STATUS"
    exit 1
fi

# Kill monitor
kill $MONITOR_PID 2>/dev/null || true

# Phase 2: Data crunch
echo ""
echo "======================================================================"
echo "Phase 2: COMPREHENSIVE DATA CRUNCH"
echo "======================================================================"
echo ""

python coordination/comprehensive_data_crunch.py

# Show summary
echo ""
echo "======================================================================"
echo "FULL EXECUTION COMPLETE"
echo "======================================================================"
echo ""
echo "Results directory: coordination/backtest_results/"
ls -lah coordination/backtest_results/

echo ""
echo "Next: Review backtest reports and data crunch summary"
