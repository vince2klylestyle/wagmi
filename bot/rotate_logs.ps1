# WAGMI log rotation
# Rotates python_stdout.log and supervisor.log when oversize, prunes old archives.
# Briefly stops the WAGMI-Bot task to release file handles. Total downtime: ~10-15s.
#
# Usage:
#   powershell -File C:\Users\vince\WAGMI\bot\rotate_logs.ps1            # interactive, confirm before stopping bot
#   powershell -File C:\Users\vince\WAGMI\bot\rotate_logs.ps1 -Force     # no prompts
#   powershell -File C:\Users\vince\WAGMI\bot\rotate_logs.ps1 -DryRun    # show what would happen, no changes

param(
    [switch]$Force,
    [switch]$DryRun,
    [int]$MaxSizeMB = 50,        # rotate files larger than this
    [int]$KeepArchives = 30      # keep last N archives per log
)

$ErrorActionPreference = "Stop"
$LogsDir = "C:\Users\vince\WAGMI\bot\logs"
$TaskName = "WAGMI-Bot"

$targets = @(
    "python_stdout.log",
    "supervisor.log"
)

function Get-SizeMB {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return 0 }
    return [Math]::Round((Get-Item $Path).Length / 1MB, 2)
}

Write-Host ""
Write-Host "=== WAGMI Log Rotation ===" -ForegroundColor Cyan

# Survey
$toRotate = @()
$skipped = @()
foreach ($name in $targets) {
    $path = Join-Path $LogsDir $name
    $size = Get-SizeMB $path
    if (-not (Test-Path $path)) {
        $skipped += "$name (does not exist)"
        continue
    }
    if ($size -ge $MaxSizeMB) {
        $toRotate += [PSCustomObject]@{ Name = $name; Path = $path; SizeMB = $size }
    } else {
        $skipped += "$name ($size MB < $MaxSizeMB MB threshold)"
    }
}

Write-Host ""
Write-Host "Targets to rotate:" -ForegroundColor Yellow
if ($toRotate.Count -eq 0) {
    Write-Host "  (none -- all log files are below $MaxSizeMB MB)" -ForegroundColor Green
} else {
    foreach ($t in $toRotate) {
        Write-Host ("  {0,-30} {1,8} MB" -f $t.Name, $t.SizeMB)
    }
}
Write-Host ""
Write-Host "Skipped:" -ForegroundColor DarkGray
foreach ($s in $skipped) { Write-Host "  $s" -ForegroundColor DarkGray }

# Archive pruning survey
$archives = Get-ChildItem -Path $LogsDir -Filter "*.archive_*.log" -ErrorAction SilentlyContinue
$toPrune = @()
if ($archives.Count -gt 0) {
    $grouped = $archives | Group-Object { ($_.Name -replace '\.archive_.*$', '') }
    foreach ($g in $grouped) {
        $sorted = $g.Group | Sort-Object LastWriteTime -Descending
        if ($sorted.Count -gt $KeepArchives) {
            $toPrune += ($sorted | Select-Object -Skip $KeepArchives)
        }
    }
}
Write-Host ""
Write-Host "Old archives to prune (keeping last $KeepArchives per log):" -ForegroundColor Yellow
if ($toPrune.Count -eq 0) {
    Write-Host "  (none)" -ForegroundColor Green
} else {
    foreach ($p in $toPrune) {
        Write-Host ("  {0,-60} {1}" -f $p.Name, $p.LastWriteTime)
    }
}

if ($toRotate.Count -eq 0 -and $toPrune.Count -eq 0) {
    Write-Host ""
    Write-Host "Nothing to do. Exiting." -ForegroundColor Green
    exit 0
}

if ($DryRun) {
    Write-Host ""
    Write-Host "DryRun mode -- no changes made." -ForegroundColor Cyan
    exit 0
}

# Confirm if not -Force
if (-not $Force) {
    Write-Host ""
    Write-Host "This will STOP the bot briefly (~10-15s) to release file handles." -ForegroundColor Yellow
    $resp = Read-Host "Proceed? (y/N)"
    if ($resp -notmatch '^y') {
        Write-Host "Cancelled." -ForegroundColor Red
        exit 0
    }
}

# 1. Stop bot
Write-Host ""
Write-Host "Stopping WAGMI-Bot task..." -ForegroundColor Cyan
try {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
    Write-Host "  Stopped." -ForegroundColor Green
} catch {
    Write-Host "  Warning: could not stop task cleanly: $($_.Exception.Message)" -ForegroundColor Yellow
}

# 2. Rotate
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
foreach ($t in $toRotate) {
    $archivePath = "{0}\{1}.archive_{2}.log" -f $LogsDir, [System.IO.Path]::GetFileNameWithoutExtension($t.Name), $stamp
    try {
        Move-Item $t.Path $archivePath -Force
        Write-Host ("  {0} -> {1}" -f $t.Name, (Split-Path $archivePath -Leaf)) -ForegroundColor Green
    } catch {
        Write-Host ("  FAILED to rotate {0}: {1}" -f $t.Name, $_.Exception.Message) -ForegroundColor Red
    }
}

# 3. Prune
foreach ($p in $toPrune) {
    try {
        Remove-Item $p.FullName -Force
        Write-Host "  Pruned $($p.Name)" -ForegroundColor DarkGray
    } catch {
        Write-Host "  FAILED to prune $($p.Name): $($_.Exception.Message)" -ForegroundColor Red
    }
}

# 4. Restart bot
Write-Host ""
Write-Host "Restarting WAGMI-Bot task..." -ForegroundColor Cyan
try {
    Start-ScheduledTask -TaskName $TaskName
    Start-Sleep -Seconds 5
    $py = Get-Process python -ErrorAction SilentlyContinue
    if ($py) {
        Write-Host "  Bot restarted (PID $($py.Id))." -ForegroundColor Green
    } else {
        Write-Host "  Task started but python not yet visible. It usually takes ~10s for full warmup." -ForegroundColor Yellow
    }
} catch {
    Write-Host "  FAILED to restart task: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "  Restart manually: Start-ScheduledTask -TaskName WAGMI-Bot" -ForegroundColor Red
}

Write-Host ""
Write-Host "Done." -ForegroundColor Cyan
Write-Host ""
