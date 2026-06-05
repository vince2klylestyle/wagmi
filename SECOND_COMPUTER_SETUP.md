# Second Computer Setup — Analytics & Dev Workhorse

**Role:** This machine = analytics, optimization, dev environment. **NOT** a second live paper bot — two paper bots writing to the same trades.csv / equity state would collide and corrupt your data. Live bot stays on Primary.

---

## What to install once

1. **Python 3.11+** (matches Primary)
2. **Node.js + npm** (for the `claude` CLI)
3. **Claude Code CLI**: `npm i -g @anthropic-ai/claude-code` and `claude /login` with your same account
4. **Git for Windows**
5. **VS Code** (optional, useful for editing) and **Windows Remote Desktop** or **Tailscale** if you want to dev on this machine but jump to Primary

## Get the code

```powershell
cd C:\Users\vince
git clone <primary repo URL>  WAGMI
# OR: copy C:\Users\vince\WAGMI\ from Primary via OneDrive / file share
cd WAGMI\bot
pip install -r requirements.txt
```

Then copy `bot/.env` from Primary so `USE_CLI_LLM=true` is set. Same `claude` subscription works on both machines (Anthropic counts usage per account, not per host).

## What to RUN on this machine

These are safe — read from data, write to separate output paths, no state collision:

### Backtest farm (uses CLI routing, no API cost)
```powershell
cd C:\Users\vince\WAGMI\bot
python run.py backtest --symbols BTC,ETH,SOL --days 30 --learn --csv data\backtest_results.csv
python run.py backtest --symbols BTC,ETH --days 90 --llm --budget 5
```

### Swarm optimizer (offline parameter search)
```powershell
python cli.py --mode optimize
```

### Strategy evolution analysis
```powershell
python cli.py --mode evolve
```

### Slash commands inside Claude Code
Spin up `claude` here and run the analytics skills:
- `/edge-finder full` — where bot makes and loses money
- `/loss-autopsy worst` — forensic on worst losses
- `/sniper-setup top10` — reverse-engineer best trades
- `/pnl-maximize deep` — end-to-end profitability optimization
- `/backtest BTC,ETH 60 compare` — A/B test parameter changes
- `/babysit` — long-running monitor that reads Primary's logs and flags issues

These are all listed in `WAGMI/CLAUDE.md` and `WAGMI/bot/.claude/skills/`.

## What NOT to run here

- `python run.py paper` — would start a second live bot competing with Primary for state. DO NOT.
- Anything that writes to `bot/data/trades.csv`, `bot/data/risk_equity_state.json`, `bot/data/llm/decisions.jsonl`, `bot/data/llm/llm_memory.json`, `bot/data/feedback/*`
- Any skill that modifies `bot/.claude/skills/` or `bot/llm/agents/prompts.py` while Primary is reading them — push those through Git and pull on Primary instead

## Reading Primary's live data from Secondary

Two options:

**A) Sync via OneDrive/Dropbox** — Put `C:\Users\vince\WAGMI\bot\data\` under sync. Primary writes, Secondary reads. Caveat: sync conflicts on hot files (decisions.jsonl appends every tick) can cause issues. Use only if you accept a 5-30s data lag.

**B) Tailscale SMB share** — Share `C:\Users\vince\WAGMI\bot\data\` from Primary, mount on Secondary as `\\primary-pc\WAGMI-data`. Real-time read access, no sync conflicts. Requires Tailscale (free for personal use) so it works off-LAN too.

For day-1, just copy data files over manually when you want to analyze. Upgrade to sync once you know you'll use Secondary heavily.

## Remote desktop options

- **Windows Remote Desktop** (built in, Home edition gets you outbound only — connect FROM Secondary TO Primary, not the other way unless Primary runs Pro)
- **Tailscale + RDP** — works off-LAN
- **Parsec** — free, very low latency, geared toward gaming but works for general remote
- **Chrome Remote Desktop** — simple, browser-based

If Primary is the always-on bot host, you'll mostly want to RDP **into** Primary to peek at logs or restart things — Secondary as the workstation, Primary as the server.

## When to bring Secondary online

You don't have to do this today. The bot is live on Primary and collecting data. Bring Secondary up when:
- You have time to run a deep `/edge-finder` or backtest comparison
- You want a dev env that won't risk crashing the live bot
- You start wanting two Claude Code sessions in parallel (one watching, one experimenting)

Until then, Primary alone is doing the work that matters: data collection.
