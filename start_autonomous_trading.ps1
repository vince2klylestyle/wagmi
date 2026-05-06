# Unified Autonomous Trading System (Windows PowerShell)
# Runs 3 processes in parallel:
# 1. Paper trading bot (generates signals)
# 2. Autonomous executor (trades aggressively)
# 3. CLI monitor (shows everything)

Write-Host "=============================================="
Write-Host "WAGMI AUTONOMOUS TRADING SYSTEM" -ForegroundColor Cyan
Write-Host "=============================================="
Write-Host ""
Write-Host "Starting 3 autonomous processes:" -ForegroundColor Green
Write-Host "1. Paper trading bot (signal generation)"
Write-Host "2. Aggressive executor (autonomous trading)"
Write-Host "3. CLI monitor (real-time visibility)"
Write-Host ""

# Kill any existing processes
Get-Process | Where-Object { $_.ProcessName -like "*python*" } | Stop-Process -Force -ErrorAction SilentlyContinue

Start-Sleep -Seconds 1

# Log files
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BOT_LOG = "C:\tmp\autonomous_bot_$timestamp.log"
$EXEC_LOG = "C:\tmp\autonomous_executor_$timestamp.log"
$MON_LOG = "C:\tmp\autonomous_monitor_$timestamp.log"

# Ensure tmp directory exists
$null = New-Item -ItemType Directory -Path "C:\tmp" -Force -ErrorAction SilentlyContinue

Write-Host "Logs:"
Write-Host "  Bot: $BOT_LOG" -ForegroundColor Gray
Write-Host "  Executor: $EXEC_LOG" -ForegroundColor Gray
Write-Host "  Monitor: $MON_LOG" -ForegroundColor Gray
Write-Host ""

# Start bot in background
Write-Host "[1/3] Starting paper trading bot..." -ForegroundColor Green
$botProcess = Start-Process -FilePath "python" -ArgumentList "bot\run.py paper" -WorkingDirectory "$PSScriptRoot" `
    -RedirectStandardOutput $BOT_LOG -PassThru -WindowStyle Hidden
Write-Host "  Bot PID: $($botProcess.Id)"

Start-Sleep -Seconds 2

# Start autonomous executor in background
Write-Host "[2/3] Starting aggressive signal executor..." -ForegroundColor Green
$execProcess = Start-Process -FilePath "python" -ArgumentList "autonomous_signal_executor.py --mode aggressive" `
    -WorkingDirectory "$PSScriptRoot" -RedirectStandardOutput $EXEC_LOG -PassThru -WindowStyle Hidden
Write-Host "  Executor PID: $($execProcess.Id)"

Start-Sleep -Seconds 1

# Start monitor in current console (foreground)
Write-Host "[3/3] Starting signal monitor..." -ForegroundColor Green
Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "LIVE MARKET MONITOR" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

python cli_monitor.py live

# Cleanup on exit
Write-Host ""
Write-Host "Cleaning up..."
$botProcess | Stop-Process -Force -ErrorAction SilentlyContinue
$execProcess | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "System stopped." -ForegroundColor Yellow
Write-Host ""
Write-Host "Check logs:" -ForegroundColor Gray
Write-Host "  tail -f $BOT_LOG"
Write-Host "  tail -f $EXEC_LOG"
Write-Host ""
