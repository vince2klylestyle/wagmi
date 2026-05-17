# WAGMI Trading Bot — Quick Start Script (May 11, 2026)
# Copy-paste this script to activate fixes and validate

Write-Host "================================" -ForegroundColor Cyan
Write-Host "WAGMI BOT — QUICK START" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Verify environment
Write-Host "[1/5] Checking environment..." -ForegroundColor Yellow
$pythonVersion = & python --version 2>&1
Write-Host "  Python: $pythonVersion"

if (-not (Test-Path ".env")) {
    Write-Host "  .env: MISSING! Please check." -ForegroundColor Red
    exit 1
}
Write-Host "  .env: EXISTS ✓"

if (-not (Test-Path "bot/requirements.txt")) {
    Write-Host "  requirements.txt: MISSING!" -ForegroundColor Red
    exit 1
}
Write-Host "  requirements.txt: EXISTS ✓"
Write-Host ""

# Step 2: Verify TIME_STOP fix
Write-Host "[2/5] Checking TIME_STOP fix..." -ForegroundColor Yellow
$timeStopValue = Select-String -Path "bot/trading_config.py" -Pattern "TIME_STOP\s*=\s*(\d+)" | Select-Object -First 1
if ($timeStopValue -match "TIME_STOP\s*=\s*(\d+)") {
    $timeStop = $matches[1]
    if ($timeStop -eq "60") {
        Write-Host "  TIME_STOP: $timeStop (CORRECT ✓)" -ForegroundColor Green
    } else {
        Write-Host "  TIME_STOP: $timeStop (EXPECTED 60!) ⚠️" -ForegroundColor Yellow
    }
}
Write-Host ""

# Step 3: Optional dependency install
Write-Host "[3/5] Dependencies..." -ForegroundColor Yellow
$installDeps = Read-Host "  Install/upgrade dependencies? (y/n, default n)"
if ($installDeps -eq "y") {
    Write-Host "  Installing... this may take 1-2 minutes"
    & pip install -r bot/requirements.txt --upgrade --quiet
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Dependencies installed ✓" -ForegroundColor Green
    } else {
        Write-Host "  Dependency installation failed!" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  Skipping dependency install"
}
Write-Host ""

# Step 4: Start bot
Write-Host "[4/5] Starting bot with fixes..." -ForegroundColor Yellow
Write-Host ""
Write-Host "--- BOT OUTPUT BEGINS ---" -ForegroundColor Cyan
cd bot
& python run.py paper
# Bot will run until manually stopped (Ctrl+C)

# Step 5: Post-run
Write-Host ""
Write-Host "--- BOT OUTPUT ENDS ---" -ForegroundColor Cyan
Write-Host ""
Write-Host "[5/5] Bot stopped. Analyze results:" -ForegroundColor Yellow
Write-Host "  - Check bot/data/signal_outcomes.jsonl for signals"
Write-Host "  - Check bot/data/trades.csv for executed trades"
Write-Host "  - Check bot/data/bot.log for errors"
Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Cyan
Write-Host "1. Review metrics from PREP_BRIEFING_20260511.md"
Write-Host "2. If trade velocity improved → validation successful"
Write-Host "3. If stuck → debug soft-reject gate (CYCLE 8 blocker)"
Write-Host ""
Write-Host "See REMOTE_SETUP_CHECKLIST.md for detailed guidance" -ForegroundColor Cyan
