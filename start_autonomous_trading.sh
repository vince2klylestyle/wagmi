#!/bin/bash
# Unified Autonomous Trading System
# Runs 3 processes in parallel:
# 1. Paper trading bot (generates signals)
# 2. Signal generator (shows all signals)
# 3. Autonomous executor (trades aggressively on high-conviction signals)

set -e

echo "=============================================="
echo "WAGMI AUTONOMOUS TRADING SYSTEM"
echo "=============================================="
echo ""
echo "Starting 3 autonomous processes:"
echo "1. Paper trading bot (signal generation)"
echo "2. Signal monitor (real-time visibility)"
echo "3. Aggressive executor (autonomous trading)"
echo ""

# Kill any existing processes
pkill -f "run.py paper" || true
pkill -f "autonomous_signal_executor" || true
pkill -f "cli_monitor.py" || true

sleep 1

# Log files
BOT_LOG="/tmp/autonomous_bot_$(date +%s).log"
EXEC_LOG="/tmp/autonomous_executor_$(date +%s).log"
MON_LOG="/tmp/autonomous_monitor_$(date +%s).log"

echo "Logs:"
echo "  Bot: $BOT_LOG"
echo "  Executor: $EXEC_LOG"
echo "  Monitor: $MON_LOG"
echo ""

# Start bot in background
echo "[1/3] Starting paper trading bot..."
cd bot
python run.py paper > "$BOT_LOG" 2>&1 &
BOT_PID=$!
echo "  Bot PID: $BOT_PID"
cd ..

sleep 2

# Start autonomous executor in background
echo "[2/3] Starting aggressive signal executor..."
python autonomous_signal_executor.py --mode aggressive > "$EXEC_LOG" 2>&1 &
EXEC_PID=$!
echo "  Executor PID: $EXEC_PID"

# Start monitor in foreground
echo "[3/3] Starting signal monitor (foreground)..."
sleep 1

# Monitor will run in foreground and show output
python cli_monitor.py live

# Cleanup on exit
echo ""
echo "Cleaning up..."
kill $BOT_PID $EXEC_PID 2>/dev/null || true

echo ""
echo "System stopped."
