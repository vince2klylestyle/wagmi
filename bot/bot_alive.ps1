# Quick "is the bot alive?" check. Run this whenever you want a fast read.
# Usage: powershell -File bot_alive.ps1   (or just double-click)

$BotDir = "C:\Users\vince\WAGMI\bot"
$HeartbeatFile = Join-Path $BotDir "data\bot_heartbeat.txt"
$SupervisorLog = Join-Path $BotDir "logs\supervisor.log"

Write-Host ""
Write-Host "=== WAGMI Bot Health ===" -ForegroundColor Cyan

# Heartbeat freshness
if (Test-Path $HeartbeatFile) {
    $hb = Get-Item $HeartbeatFile
    $ageSec = ((Get-Date) - $hb.LastWriteTime).TotalSeconds
    $ageStr = if ($ageSec -lt 60) { "{0:N0}s ago" -f $ageSec }
              elseif ($ageSec -lt 3600) { "{0:N1}m ago" -f ($ageSec / 60) }
              else { "{0:N1}h ago" -f ($ageSec / 3600) }
    $status = if ($ageSec -lt 90) { "ALIVE" } elseif ($ageSec -lt 600) { "STALE" } else { "DEAD" }
    $color = if ($status -eq "ALIVE") { "Green" } elseif ($status -eq "STALE") { "Yellow" } else { "Red" }
    Write-Host ("  Heartbeat: {0} ({1})" -f $status, $ageStr) -ForegroundColor $color
    Write-Host ("  Last beat: {0}" -f $hb.LastWriteTime)
} else {
    Write-Host "  Heartbeat: MISSING (supervisor not running)" -ForegroundColor Red
}

# Python process
$py = Get-Process python -ErrorAction SilentlyContinue
if ($py) {
    foreach ($p in $py) {
        $cpuMin = if ($p.CPU) { "{0:N1}min CPU" -f ($p.CPU / 60) } else { "?" }
        Write-Host ("  Python PID {0}: started {1}, {2}" -f $p.Id, $p.StartTime, $cpuMin) -ForegroundColor Green
    }
} else {
    Write-Host "  Python: NO PROCESS" -ForegroundColor Red
}

# Most-recent supervisor log lines
if (Test-Path $SupervisorLog) {
    Write-Host ""
    Write-Host "Recent supervisor activity:" -ForegroundColor Cyan
    Get-Content $SupervisorLog -Tail 5 | ForEach-Object { Write-Host "  $_" }
}

# Most-recent bot log line
$latestBotLog = Get-ChildItem (Join-Path $BotDir "logs") -Filter "bot_*.log" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($latestBotLog) {
    Write-Host ""
    Write-Host ("Latest bot log: {0} ({1:N1} KB)" -f $latestBotLog.Name, ($latestBotLog.Length / 1KB)) -ForegroundColor Cyan
    Get-Content $latestBotLog.FullName -Tail 5 | ForEach-Object { Write-Host "  $_" }
}

# Equity snapshot
$equityFile = Join-Path $BotDir "data\risk_equity_state.json"
if (Test-Path $equityFile) {
    try {
        $eq = Get-Content $equityFile -Raw | ConvertFrom-Json
        Write-Host ""
        Write-Host ("Equity: `${0:N2}  |  Peak: `${1:N2}  |  Saved: {2}" -f $eq.equity, $eq.peak_equity, $eq.saved_at) -ForegroundColor Cyan
    } catch {}
}

Write-Host ""
