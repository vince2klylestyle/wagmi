# Test script to run bot and monitor for trades

$BotPath = "C:\Users\vince\WAGMI PROJECT\WAGMI\bot"
$LogPath = "C:\Users\vince\WAGMI PROJECT\WAGMI\bot_exec_test.log"

# Clear old log
if (Test-Path $LogPath) { Remove-Item $LogPath -Force }

# Start bot process
cd $BotPath
$Process = Start-Process python -ArgumentList "run.py paper" -NoNewWindow -PassThru -RedirectStandardOutput $LogPath

Write-Host "Bot started (PID: $($Process.Id)). Running for 90 seconds..."
Start-Sleep -Seconds 90

# Kill bot
Write-Host "Stopping bot..."
Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue

# Check results
Write-Host "`n=== BOT EXECUTION TEST RESULTS ==="
Write-Host "Trade ledger modification time:"
(Get-Item "data/trade_ledger.csv").LastWriteTime

Write-Host "`nRecent signals from signal_outcomes.jsonl:"
$SignalFile = "data/logs/signal_outcomes.jsonl"
if (Test-Path $SignalFile) {
    Get-Content $SignalFile -Tail 3 | ForEach-Object {
        $json = $_ | ConvertFrom-Json -ErrorAction SilentlyContinue
        if ($json) {
            "{0} {1} {2} conf={3}% passed={4}" -f $json.ts, $json.sym, $json.side, $json.conf, $json.passed
        }
    }
} else {
    Write-Host "Signal file not found"
}

Write-Host "`nBot log tail (last 20 lines):"
Get-Content $LogPath -Tail 20 -ErrorAction SilentlyContinue
