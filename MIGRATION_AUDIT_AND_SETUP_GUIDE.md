# Migration Audit & Setup Guide
**Complete understanding of all your automations before moving to the old computer**

---

## Overview
You have 3 main active automations + 3 static web projects. The old computer will run the 3 automations 24/7.

---

## 1. WAGMI Trading Bot (github.com/Vince2kLyleStyle/WAGMI)
**Current Branch**: `claude/debug-neural-queue-Nye7v` (your active development branch)

### What It Does
- Autonomous crypto trading on **Hyperliquid** exchange
- Evaluates 4 independent trading strategies (regime-trend, monte-carlo, confidence-score, multi-tier-quality)
- **Ensemble voting**: all 4 must agree (veto mode) for a trade to execute
- Runs **multi-agent specialist system**: Regime Agent → Trade Agent → Risk Agent → Critic Agent → execute
- Monitors open positions with **Exit Agent** for early profit-taking or risk management
- Learns from closed trades with **Learning Agent** to build hypothesis library
- **LLM cost**: ~$0.007 per trade decision (Haiku agents are cheap)

### How It Runs
```powershell
cd C:\Projects\WAGMI\bot
python run.py paper      # Paper trading (simulated, no real money)
python run.py live       # Live trading (uses HL_API_KEY + HL_API_SECRET)
```

### What It Needs to Run (25 Dependencies)
```
Core: requests, pandas, numpy, python-dotenv
Exchange: ccxt (talks to Hyperliquid, Kraken, Bybit)
LLM: anthropic (Claude API)
Async: httpx
Social: tweepy (Twitter integration)
Testing: pytest
```

### Environment Variables (Secrets Required)
```
# REQUIRED
ANTHROPIC_API_KEY               # Claude API key (console.anthropic.com)
TELEGRAM_TOKEN                  # Telegram bot token (@BotFather)
TELEGRAM_CHAT_ID                # Your chat ID (@userinfobot)
TELEGRAM_ALLOWED_USER_ID        # Your Telegram user ID (e.g. 6218092459)

# REQUIRED FOR LIVE TRADING ONLY (paper mode doesn't need these)
HL_API_KEY                       # Hyperliquid wallet address (0x...)
HL_API_SECRET                    # Hyperliquid private key

# OPTIONAL
TELEGRAM_SIGNAL_TOKEN           # Monitor external Telegram signals
TELEGRAM_SIGNAL_CHANNELS        # Channels to monitor (-1001234567890 format)
DISCORD_WEBHOOK                 # Discord alerts
COINGECKO_API_KEY              # CoinGecko API (optional, free tier works)
NUNUIRL_API_KEY                # Custom API integration (optional)
```

### Configuration (Trading Parameters)
```
ENVIRONMENT=paper|production     # paper (simulated) or production (real money)
STARTING_EQUITY=400.0           # Amount bot manages (you set this)
RISK_PER_TRADE=0.02             # 2% of equity per trade
MAX_OPEN_POSITIONS=3            # Max simultaneous trades
MAX_LEVERAGE=10.0               # Leverage cap
LLM_MODE=2                       # 0=OFF, 1=ADVISORY, 2=VETO_ONLY, 3-5=full control
LLM_USAGE_TIER=RECOMMENDED      # Cost: CONSERVATIVE (~$18/mo), RECOMMENDED (~$130/mo), etc.
SCAN_INTERVAL_S=60              # Check for signals every 60 seconds
```

### What It Outputs (Where to Find Results)
- **Live trades**: `bot/data/trades.csv` — every entry/exit logged
- **Decisions**: `bot/data/llm/decisions.jsonl` — LLM reasoning on each decision
- **Memory**: `bot/data/llm/llm_memory.json` (short-term 7-day TTL)
- **Deep knowledge**: `bot/data/llm/deep_memory/` — learned trade DNA, patterns, hypotheses
- **Paper trades**: `paper_trades/signals_*.csv`, `trades_*.csv` — simulation results
- **Logs**: `bot/logs/`, `bot/paper_trades/*.log` — execution logs
- **Feedback**: `bot/data/feedback/` — signal quality tracking, strategy weights

### 24/7 Auto-Start (Windows Task Scheduler)
```powershell
# Task Name: WAGMI-Bot-24-7
# Trigger: On startup (with 2-minute delay for network)
# Action: 
#   Program: powershell.exe
#   Arguments: -File "C:\Projects\WAGMI\START_BOT_QUICK.ps1"
# Run with highest privileges
# Allow task to be run on demand: YES
```

### To Test It Works (Before Migration)
1. On old computer, after cloning:
   ```powershell
   cd C:\Projects\WAGMI\bot
   python run.py paper  # Start paper trading for 5 minutes
   ```
   - Should fetch current BTC/ETH prices
   - Should generate signals every 60 seconds
   - Should evaluate them through 4 strategies
   - Should print "NO ENSEMBLE AGREEMENT" or "SIGNAL: BUY/SELL ..."
   - Ctrl+C to stop

---

## 2. Instagram Automation (github.com/Vince2kLyleStyle/wagmi-project)
**Current Branch**: `claude/tiktok-scraper-tool-hXD41`

### What It Does
- Uses **BlueStacks emulator** to automate Instagram reels posting
- Scrapes Instagram for high-engagement content
- Automatically captions, filters, and reposts to your Instagram
- Posts to "memegine" niche (memes + Solana/crypto content)
- Runs **parallel processes**: scraper + poster + monitor
- Continuous 24/7 content feed automation

### How It Runs
```powershell
cd C:\Projects\wagmi-project
python watchdog.py             # Main orchestrator (scraper + poster + monitor)
python bluestacks_poster.py    # Manual poster (posts from queue)
python bluestacks_scraper.py   # Manual scraper (finds content)
```

### What It Needs to Run (7 Dependencies)
```
instagrapi          # Instagram API wrapper
Pillow              # Image processing
python-dotenv       # Secrets management
requests            # HTTP calls
telethon            # Telegram integration
pygetwindow         # Windows automation (finds BlueStacks window)
```

### Also Requires (System Software)
- **BlueStacks** Android emulator (installed on the old computer)
- **Android Debug Bridge (ADB)** — comes with BlueStacks
- **Instagram account** — your actual Instagram credentials

### Environment Variables (Secrets Required)
```
# REQUIRED
IG_USERNAME=dumbmoneyonsolana           # Your Instagram username
IG_PASSWORD=your_actual_password        # Your Instagram password

# OPTIONAL
TELEGRAM_API_ID=12345678               # Telegram app API ID
TELEGRAM_API_HASH=your_api_hash_here   # Telegram app API hash
TELEGRAM_PHONE=+1234567890             # Your Telegram phone number
IG_PROXY=http://user:pass@host:port    # Optional proxy for IG
```

### Configuration (In code)
- Scraper targets: high-engagement Solana/meme accounts
- Caption strategy: auto-generated from content theme
- Queue system: posts 1-3 reels per hour (configurable)
- Restart strategy: auto-restarts if stuck or crashes

### What It Outputs
- **Posted content**: your Instagram feed (the goal)
- **Logs**: `bluestacks_poster_output.log`, `bluestacks_scraper.log` — execution trace
- **Queue**: `success.txt` — list of successfully posted URLs
- **Debug**: hundreds of PNG screenshots (can delete after debugging)

### 24/7 Auto-Start (Windows Task Scheduler)
```powershell
# Task Name: Instagram-Watchdog
# Trigger: On startup (with 5-minute delay, after WAGMI)
# Action:
#   Program: powershell.exe
#   Arguments: -Command "cd C:\Projects\wagmi-project; python watchdog.py"
# Run with highest privileges: YES
# Allow manual trigger: YES
```

### To Test It Works (Before Migration)
1. On old computer:
   - Install BlueStacks
   - Log into Instagram via BlueStacks (one-time setup)
   ```powershell
   cd C:\Projects\wagmi-project
   python bluestacks_scraper.py  # Find 3-5 posts, should save URLs
   python bluestacks_poster.py   # Post 1 to your account (test)
   ```
   - Check your Instagram — should see test post
   - If stuck: check `bluestacks_poster_output.log` for errors

---

## 3. Other Projects (Static/Lower Priority)

### textile-sales (Next.js app)
- **Status**: No remote yet, 3 local commits
- **Purpose**: E-commerce website (textile company)
- **Runs**: `npm install && npm run dev` (dev server on localhost:3000)
- **Migration**: Create GitHub remote + clone to old computer
- **Auto-start**: Not required for 24/7 (dev-only)

### CrazyonSol + crypto-site
- **Status**: Already on GitHub, clean
- **Purpose**: Landing pages / marketing sites
- **Migration**: Clone to old computer if needed, not critical for 24/7 automation

---

## Claude Code Configuration

### What Transfers
- `.claude/` directory: settings, auth, project history
- **Auth credentials** (`.credentials.json`) — must re-login on new machine

### What Doesn't Transfer
- All 27 project worktrees (April sessions, likely stale) — safe to ignore
- Local history.jsonl — won't hurt to transfer but not critical

### Re-Login on New Machine
```powershell
claude auth login  # One-time, browser opens, click to authorize
claude --version   # Verify it worked
```

---

## Summary: What Goes Where

| Project | Runs on Old Computer? | 24/7? | Required Secrets | Required Software |
|---------|----------------------|-------|------------------|-------------------|
| **WAGMI Bot** | YES | YES | Anthropic API, Telegram token, HL keys (live only) | Python 3.11+, Node.js (for web dash) |
| **Instagram Bot** | YES | YES | IG username/password, Telegram API | BlueStacks, ADB |
| **textile-sales** | Optional | NO | None | Node.js, npm |
| **CrazyonSol** | Optional | NO | None | None |
| **Claude Code** | YES (for monitoring) | NO | Claude auth | Claude Code CLI (npm install -g @anthropic-ai/claude-code) |

---

## Full Setup Checklist (Old Computer)

### Phase 1: Install Software (1-2 hours)
- [ ] Windows Update (get current)
- [ ] Git (git-scm.com, check "Add to PATH")
- [ ] Python 3.11+ (python.org, check "Add to PATH")
- [ ] Node.js 18+ (nodejs.org, includes npm)
- [ ] BlueStacks (for Instagram bot)
- [ ] Claude Code CLI: `npm install -g @anthropic-ai/claude-code`
- [ ] VS Code (optional, useful for monitoring)

### Phase 2: Clone Repos (5 mins)
```powershell
mkdir C:\Projects
cd C:\Projects
git clone https://github.com/Vince2kLyleStyle/WAGMI
git clone https://github.com/Vince2kLyleStyle/wagmi-project
```

### Phase 3: Set Up Secrets (20 mins)
For WAGMI bot:
1. `cp WAGMI\.env.example WAGMI\.env`
2. Fill in: ANTHROPIC_API_KEY, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ALLOWED_USER_ID
3. For live trading later: add HL_API_KEY, HL_API_SECRET

For Instagram bot:
1. `cp wagmi-project\.env.example wagmi-project\.env`
2. Fill in: IG_USERNAME, IG_PASSWORD

### Phase 4: Install Dependencies (10 mins)
```powershell
cd C:\Projects\WAGMI\bot
pip install -r requirements.txt

cd C:\Projects\wagmi-project
pip install -r requirements.txt

cd C:\Projects\WAGMI\web
npm install
```

### Phase 5: Test Before Auto-Start (10 mins)
```powershell
# Test WAGMI bot
cd C:\Projects\WAGMI\bot
python run.py paper
# Wait 2 cycles, should see signals → Ctrl+C

# Test Instagram bot
cd C:\Projects\wagmi-project
python bluestacks_scraper.py
# Should scrape 3-5 URLs → Ctrl+C
```

### Phase 6: Set Up Auto-Start (30 mins)
Create 2 Windows Task Scheduler tasks:
1. **WAGMI-Bot-24-7** — runs on startup, triggers `START_BOT_QUICK.ps1`
2. **Instagram-Watchdog** — runs on startup (5-min delay), triggers `python watchdog.py`

### Phase 7: Enable Remote Desktop (5 mins)
```powershell
# Run as admin on old computer:
Set-ItemProperty -Path "HKLM:\System\CurrentControlSet\Control\Terminal Server" -Name "fDenyTSConnections" -Value 0
Enable-NetFirewallRule -DisplayGroup "Remote Desktop"
```

Then from laptop: `Win + R` → `mstsc` → old computer's IP → enter

### Phase 8: Verify It All Works (15 mins)
- [ ] Boot old computer
- [ ] Both tasks start automatically
- [ ] Check WAGMI logs: `Get-Content C:\Projects\WAGMI\bot\logs\latest.log -Tail 20`
- [ ] Check Instagram logs: `Get-Content C:\Projects\wagmi-project\bluestacks_poster_output.log -Tail 20`
- [ ] RDP into old computer from laptop — works smoothly
- [ ] Claude Code login on old computer — `claude --version` works

---

## Risk Mitigations

**Before Moving to Old Computer:**
- ✅ All code pushed to GitHub (WAGMI, wagmi-project)
- ✅ All secrets documented separately (NOT in git)
- ✅ 23 stashes dropped (clean slate)
- ✅ Session docs committed (useful context preserved)
- ✅ No uncommitted code left on laptop

**During Setup:**
- Start with **paper trading** (no real money risk)
- Run **manual tests** before enabling auto-start
- Monitor **logs closely** first 24 hours
- Use **RDP** to check status remotely

**After Setup:**
- Keep **original laptop** as backup (don't delete projects)
- Do **daily health checks** first week (logs, positions, errors)
- Set up **Telegram alerts** so you know if something breaks
- Test **circuit breakers** (intentionally trip one to verify)

---

## Questions to Answer Before We Start

1. **WAGMI Trading**: paper mode only, or ready to add live HL_API_KEY + HL_API_SECRET?
2. **Instagram Bot**: Instagram account already set up? Can login via BlueStacks?
3. **Telegram Alerts**: Already have bot token + chat ID? Or need help setting up?
4. **Old Computer Hardware**: How much RAM/storage? (minimum: 4GB RAM, 50GB free space)
5. **Network**: Will old computer be connected to WiFi or Ethernet? (Ethernet more reliable for 24/7)

---

## Next Steps (After You Approve This Understanding)

1. Gather all your secrets (API keys, credentials) — doesn't go to GitHub
2. Set a specific date/time to set up the old computer
3. I'll walk you through Phase 1-5 step-by-step (install + clone + test)
4. You verify everything works (paper trades, Instagram posts)
5. We set up auto-start + RDP + monitoring
6. You're running 24/7 with full remote access from laptop

This is very doable, and we'll be methodical so nothing breaks. You're going to have a solid infrastructure. ✅
