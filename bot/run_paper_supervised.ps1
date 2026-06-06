# WAGMI Bot supervised launcher
# Self-loops on python exit so a python crash auto-restarts within seconds.
# Task Scheduler restarts THIS script if it dies. Two layers of resilience.

$ErrorActionPreference = "Continue"
$BotDir = "C:\Users\vince\WAGMI\bot"
$LogsDir = Join-Path $BotDir "logs"
$WrapperLog = Join-Path $LogsDir "supervisor.log"
$HeartbeatFile = Join-Path $BotDir "data\bot_heartbeat.txt"

if (-not (Test-Path $LogsDir)) { New-Item -ItemType Directory -Path $LogsDir | Out-Null }

function Write-WrapperLog {
    param([string]$msg)
    $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Add-Content -Path $WrapperLog -Value $line -Encoding utf8
}

# Background heartbeat: touch a file every 30s so user can verify bot is alive
# by checking the file's modification time. No external creds needed.
$HeartbeatJob = Start-Job -ScriptBlock {
    param($HbFile, $BotDir)
    while ($true) {
        $stamp = "{0}  alive  cwd={1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss UTC zzz"), $BotDir
        Set-Content -Path $HbFile -Value $stamp -Encoding utf8
        Start-Sleep -Seconds 30
    }
} -ArgumentList $HeartbeatFile, $BotDir

Write-WrapperLog "=== Supervisor started (PID $PID, heartbeat job $($HeartbeatJob.Id)) ==="

Set-Location $BotDir

$RestartCount = 0
while ($true) {
    $RestartCount++
    Write-WrapperLog "Launching python run.py paper (attempt #$RestartCount)"

    try {
        # python writes its own logs into logs/bot_*.log; we just capture stdout/stderr
        # for the supervisor's view in case python crashes before its logger is up.
        & python run.py paper 2>&1 | Tee-Object -FilePath (Join-Path $LogsDir "python_stdout.log") -Append
        $exitCode = $LASTEXITCODE
    } catch {
        $exitCode = -1
        Write-WrapperLog "EXCEPTION launching python: $($_.Exception.Message)"
    }

    Write-WrapperLog "Python exited with code $exitCode. Restarting in 30s..."

    # Backoff: 30s default, longer if we're restart-looping rapidly
    if ($RestartCount -gt 5) {
        $sleep = [Math]::Min(300, 30 * ($RestartCount - 4))
        Write-WrapperLog "Restart loop detected ($RestartCount attempts), backing off ${sleep}s"
        Start-Sleep -Seconds $sleep
    } else {
        Start-Sleep -Seconds 30
    }
}
