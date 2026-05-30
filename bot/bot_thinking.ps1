# WAGMI Bot — Live LLM thinking view
# Shows: bot status, scout watchlist, current regime, recent decisions, recent skips, EV info.
# Refreshes every 10s. Ctrl+C to exit.
#
# Usage:
#   powershell -File C:\Users\vince\WAGMI\bot\bot_thinking.ps1
#   powershell -File bot_thinking.ps1 -Once    (single snapshot, no refresh loop)

param(
    [switch]$Once,
    [int]$RefreshSeconds = 10
)

$ErrorActionPreference = "Continue"
$BotDir = "C:\Users\vince\WAGMI\bot"
$LogsDir = Join-Path $BotDir "logs"
$DataDir = Join-Path $BotDir "data"
$LlmDir  = Join-Path $DataDir "llm"

function Get-BotStatus {
    $hb = Join-Path $DataDir "bot_heartbeat.txt"
    $py = Get-Process python -ErrorAction SilentlyContinue | Sort-Object StartTime | Select-Object -First 1

    $status = @{
        Alive = $false
        PID = "?"
        HeartbeatAgeS = -1
        Uptime = "?"
        EquityUSD = "?"
        PeakUSD = "?"
    }

    if (Test-Path $hb) {
        $status.HeartbeatAgeS = ((Get-Date) - (Get-Item $hb).LastWriteTime).TotalSeconds
        $status.Alive = $status.HeartbeatAgeS -lt 90
    }
    if ($py) {
        $status.PID = $py.Id
        $status.Uptime = "{0:dd\.hh\:mm\:ss}" -f ((Get-Date) - $py.StartTime)
    }

    $eqFile = Join-Path $DataDir "risk_equity_state.json"
    if (Test-Path $eqFile) {
        try {
            $eq = Get-Content $eqFile -Raw | ConvertFrom-Json
            $status.EquityUSD = "{0:N2}" -f $eq.equity
            $status.PeakUSD   = "{0:N2}" -f $eq.peak_equity
        } catch {}
    }
    return $status
}

function Get-RecentAgentDecisions {
    param([int]$Limit = 8)
    $f = Join-Path $LlmDir "agent_performance.jsonl"
    if (-not (Test-Path $f)) { return @() }
    $lines = Get-Content $f -Tail ($Limit * 5)  # over-read; we filter for decisions
    $items = @()
    foreach ($line in $lines) {
        try {
            $d = $line | ConvertFrom-Json
            if ($d.type -ne "decision") { continue }
            $ts = "?"
            if ($d.timestamp -is [double] -or $d.timestamp -is [int64] -or $d.timestamp -is [decimal]) {
                $ts = ([DateTime]'1970-01-01').AddSeconds([double]$d.timestamp).ToString("HH:mm:ss")
            }
            $items += [PSCustomObject]@{
                Time = $ts
                Role = $d.agent_role
                Symbol = $d.symbol
                Side = if ($d.side) { $d.side } else { "" }
                Decision = $d.decision
                Conf = if ($d.confidence -ne $null) { "{0:N2}" -f $d.confidence } else { "?" }
                Model = $d.model_used
                LatencyMs = $d.latency_ms
                Reasoning = ($d.reasoning_summary | Out-String).Trim()
            }
        } catch {}
    }
    return $items | Select-Object -Last $Limit
}

function Get-LatestScoutWatchlist {
    $f = Join-Path $LlmDir "agent_performance.jsonl"
    if (-not (Test-Path $f)) { return $null }
    $lines = Get-Content $f -Tail 200
    [array]::Reverse($lines)
    foreach ($line in $lines) {
        try {
            $d = $line | ConvertFrom-Json
            if ($d.agent_role -eq "scout" -and $d.reasoning_summary) {
                return $d.reasoning_summary
            }
        } catch {}
    }
    return $null
}

function Get-RecentSkips {
    param([int]$Limit = 5)
    $f = Join-Path $LlmDir "counterfactual_pending.jsonl"
    if (-not (Test-Path $f)) { return @() }
    $lines = Get-Content $f -Tail $Limit
    $items = @()
    foreach ($line in $lines) {
        try {
            $d = $line | ConvertFrom-Json
            $items += [PSCustomObject]@{
                Time = $d.created_at.Substring(11,8)
                Symbol = $d.symbol
                Side = $d.side
                EntryPrice = $d.entry_price
                Confidence = "{0:N1}%" -f $d.confidence
                Reason = $d.skip_reason
                Regime = $d.regime
            }
        } catch {}
    }
    return $items
}

function Get-CounterfactualCount {
    $f = Join-Path $LlmDir "counterfactual_pending.jsonl"
    if (-not (Test-Path $f)) { return 0 }
    return (Get-Content $f | Measure-Object -Line).Lines
}

function Get-CurrentRegimes {
    $logFile = Get-ChildItem (Join-Path $LogsDir "bot_*.log") -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $logFile) { return @{} }
    $tail = Get-Content $logFile.FullName -Tail 400
    $regimes = @{}
    foreach ($line in ($tail | Where-Object { $_ -match '\[REGIME\]' })) {
        if ($line -match '\[REGIME\]\s+(\w+):\s+(\w+)') {
            $regimes[$Matches[1]] = $Matches[2]
        }
    }
    return $regimes
}

function Get-LatestEvSnapshot {
    $logFile = Get-ChildItem (Join-Path $LogsDir "bot_*.log") -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $logFile) { return $null }
    $tail = Get-Content $logFile.FullName -Tail 500
    [array]::Reverse($tail)
    foreach ($line in $tail) {
        if ($line -match 'ENSEMBLE.*(\w+)\s+(BUY|SELL).*EV=([-\d.]+).*R:R=([\d.]+).*fee_drag=([\d.]+).*win_prob=([\d.]+)') {
            return [PSCustomObject]@{
                Symbol = $Matches[1]
                Side = $Matches[2]
                EV = $Matches[3]
                RR = $Matches[4]
                FeeDrag = $Matches[5]
                WinProb = $Matches[6]
            }
        }
    }
    return $null
}

function Render {
    Clear-Host
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host " WAGMI BOT THINKING                  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
    Write-Host "================================================================" -ForegroundColor Cyan

    # Status line
    $s = Get-BotStatus
    $aliveColor = if ($s.Alive) { "Green" } else { "Red" }
    $hbStr = if ($s.HeartbeatAgeS -ge 0) { "{0:N0}s ago" -f $s.HeartbeatAgeS } else { "n/a" }
    Write-Host ""
    Write-Host (" Status: " ) -NoNewline
    Write-Host ($(if ($s.Alive) { "ALIVE" } else { "DEAD" })) -ForegroundColor $aliveColor -NoNewline
    Write-Host ("    PID $($s.PID)    Uptime $($s.Uptime)    Heartbeat $hbStr")
    Write-Host (" Equity: `$$($s.EquityUSD)    Peak: `$$($s.PeakUSD)")

    # Counterfactual count
    $cfCount = Get-CounterfactualCount
    Write-Host (" Skips tracked (counterfactuals): $cfCount") -ForegroundColor DarkGray

    # Current regimes
    Write-Host ""
    Write-Host " REGIMES (latest scan)" -ForegroundColor Yellow
    $regimes = Get-CurrentRegimes
    if ($regimes.Count -gt 0) {
        foreach ($sym in @("BTC","ETH","SOL","HYPE")) {
            if ($regimes.ContainsKey($sym)) {
                $r = $regimes[$sym]
                $color = if ($r -match "trend") { "Green" } elseif ($r -match "consolidat") { "Yellow" } else { "Gray" }
                Write-Host ("  {0,-5} {1}" -f $sym, $r) -ForegroundColor $color
            }
        }
    } else {
        Write-Host "  (no regime data in recent logs)" -ForegroundColor DarkGray
    }

    # Scout watchlist
    Write-Host ""
    Write-Host " LLM SCOUT WATCHLIST (what it's expecting)" -ForegroundColor Yellow
    $scoutRaw = Get-LatestScoutWatchlist
    if ($scoutRaw) {
        # The reasoning_summary is a stringified dict — try to parse out watchlist entries
        $text = $scoutRaw.ToString()
        # crude extraction: each {symbol: 'X', priority: 'Y', setup_forming: 'Z', pre_thesis: 'W'}
        $watchPattern = "'symbol':\s*'([^']+)'.*?'priority':\s*'([^']+)'.*?'setup_forming':\s*'([^']*)'.*?'pre_thesis':\s*'([^']{0,200})"
        $matches = [regex]::Matches($text, $watchPattern)
        if ($matches.Count -gt 0) {
            foreach ($m in $matches) {
                $sym = $m.Groups[1].Value
                $pri = $m.Groups[2].Value
                $setup = $m.Groups[3].Value
                $thesis = $m.Groups[4].Value
                $color = if ($pri -eq "high") { "Green" } else { "White" }
                Write-Host ("  [{0,4}] {1,-5} setup: {2}" -f $pri.ToUpper(), $sym, $setup) -ForegroundColor $color
                Write-Host ("         {0}" -f $thesis) -ForegroundColor DarkGray
            }
        } else {
            $excerpt = if ($text.Length -gt 400) { $text.Substring(0, 400) + "..." } else { $text }
            Write-Host ("  $excerpt") -ForegroundColor DarkGray
        }
    } else {
        Write-Host "  (no scout output yet)" -ForegroundColor DarkGray
    }

    # Latest EV snapshot
    Write-Host ""
    Write-Host " LATEST MECHANICAL EV READ (informational, LLM decides)" -ForegroundColor Yellow
    $ev = Get-LatestEvSnapshot
    if ($ev) {
        $color = if ([double]$ev.EV -gt 0) { "Green" } else { "Red" }
        Write-Host ("  {0} {1}  EV={2}  R:R={3}  fee_drag={4}  win_prob={5}" -f $ev.Symbol, $ev.Side, $ev.EV, $ev.RR, $ev.FeeDrag, $ev.WinProb) -ForegroundColor $color
    } else {
        Write-Host "  (no recent EV evaluation)" -ForegroundColor DarkGray
    }

    # Recent agent decisions (the actual LLM reasoning)
    Write-Host ""
    Write-Host " RECENT LLM DECISIONS (last 6 across agents)" -ForegroundColor Yellow
    $dec = Get-RecentAgentDecisions -Limit 6
    if ($dec.Count -gt 0) {
        foreach ($d in $dec) {
            $sym = if ($d.Symbol) { $d.Symbol } else { "-" }
            $sd = if ($d.Side) { $d.Side } else { "-" }
            $color = if ($d.Decision -match "go|proceed|enter") { "Green" }
                     elseif ($d.Decision -match "skip|flat|monitor") { "Yellow" }
                     elseif ($d.Decision -match "flip|reverse|veto") { "Magenta" }
                     else { "White" }
            Write-Host ("  {0}  {1,-7} {2,-5} {3,-5} {4,-8}  conf={5}  ({6})" -f $d.Time, $d.Role, $sym, $sd, $d.Decision, $d.Conf, $d.Model) -ForegroundColor $color
            if ($d.Reasoning) {
                $r = $d.Reasoning -replace "`r?`n", " "
                if ($r.Length -gt 110) { $r = $r.Substring(0, 110) + "..." }
                Write-Host ("    -> $r") -ForegroundColor DarkGray
            }
        }
    } else {
        Write-Host "  (no agent decisions logged yet)" -ForegroundColor DarkGray
    }

    # Recent skips
    Write-Host ""
    Write-Host " RECENT SKIPS (last 5 vetoes/non-entries with reason)" -ForegroundColor Yellow
    $skips = Get-RecentSkips -Limit 5
    if ($skips.Count -gt 0) {
        foreach ($k in $skips) {
            Write-Host ("  {0}  {1,-5} {2,-5} @ `${3,-9:N2}  conf={4,-6}  regime={5,-13}  {6}" -f $k.Time, $k.Symbol, $k.Side, [double]$k.EntryPrice, $k.Confidence, $k.Regime, $k.Reason) -ForegroundColor DarkGray
        }
    } else {
        Write-Host "  (no recent skips)" -ForegroundColor DarkGray
    }

    Write-Host ""
    Write-Host "================================================================" -ForegroundColor DarkGray
    if (-not $Once) {
        Write-Host (" Refreshes every {0}s   |   Ctrl+C to exit" -f $RefreshSeconds) -ForegroundColor DarkGray
    }
    Write-Host ""
}

if ($Once) {
    Render
} else {
    while ($true) {
        Render
        Start-Sleep -Seconds $RefreshSeconds
    }
}
