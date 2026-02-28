# WAGMI Trading Bot - Runbook

## Quick Start

### Paper Trading (Safe Default)
```bash
cd bot
python cli.py --mode paper
```

### Replay Audit
```bash
cd bot
python cli.py --mode replay --replay-file ../data/logs/trades_enhanced.csv
```

### Live Trading
```bash
cd bot
python cli.py --mode live
# Requires typing "CONFIRM LIVE" at the prompt
```

## Environment Variables

### Required for Live
- `ANTHROPIC_API_KEY` - LLM meta-brain
- `TELEGRAM_TOKEN` - Telegram bot token
- `TELEGRAM_CHAT_ID` - Alert channel
- `TELEGRAM_ALLOWED_USER_ID` - Authorized user for commands

### Hyperliquid
- `HYPERLIQUID_API_KEY` - Exchange API key
- `HYPERLIQUID_API_SECRET` - Exchange API secret
- `HYPERLIQUID_TESTNET` - Use testnet (default: false)

### Risk Configuration
- `RISK_PER_TRADE` - Risk per trade as fraction (default: 0.01 = 1%)
- `MAX_OPEN_POSITIONS` - Max simultaneous positions (default: 5)
- `MAX_LEVERAGE` - Max leverage (default: 25)
- `CIRCUIT_BREAKER_DAILY_LOSS_PCT` - Daily loss halt (default: 0.05 = 5%)
- `MAX_TRADES_PER_HOUR` - Hourly rate limit (default: 10)
- `MAX_TRADES_PER_DAY` - Daily rate limit (default: 50)

### LLM Configuration
- `LLM_MODE` - 0=OFF, 1=ADVISORY, 2=VETO_ONLY, 3=SIZING, 4=DIRECTION, 5=FULL
- `LLM_PERSONAS` - Comma-separated personas (risk_off,risk_on,scalper,swing)

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/status` | Equity, positions, PnL |
| `/positions` | Open position details |
| `/health` | System health check |
| `/telemetry` | Execution quality metrics with OK/WARN/CRITICAL |
| `/llm` | LLM meta-brain status |
| `/mode <0-5>` | View/change LLM autonomy mode |
| `/copytrades` | Human copy-tradable signals |
| `/replay` | Run trade log replay analysis |
| `/proposals` | Strategy discovery proposals |
| `/approve <id>` | Approve a strategy proposal |
| `/reject <id>` | Reject a strategy proposal |
| `/close <SYM>` | Force close a position |
| `/closeall` | Close all positions |
| `/pause` | Pause trading |
| `/resume` | Resume trading |
| `/kill` | Emergency kill switch |

## Emergency Procedures

### Immediate Stop
1. Telegram: `/kill` or `/closeall`
2. Or: `touch data/.kill_switch` on the server
3. Or: Kill the process

### Kill Switch Reset
1. Telegram: `/unkill`
2. Or: `rm data/.kill_switch` on the server

### Circuit Breaker Recovery
- Automatic: waits cooldown period (default: 60 min)
- Manual: restart the bot after investigation

## Monitoring

### Telemetry Thresholds
| Metric | OK | WARN | CRITICAL |
|--------|-----|------|----------|
| Avg snapshot age | <8s | 8-15s | >15s |
| Avg slippage | <0.3% | 0.3-0.8% | >0.8% |
| Avg spread | <0.2% | 0.2-0.5% | >0.5% |
| Avg liquidity | >$75K | $30K-75K | <$30K |
| Stale signals | <5 | 5-20 | >20 |
| LLM errors | <5 | 5-15 | >15 |

### Daily Checklist
1. Check `/telemetry` - all metrics OK
2. Check `/health` - system healthy
3. Check `/performance` - win rate stable
4. Run nightly replay: `scripts/nightly_replay.sh`

## Rollout Stages

### Stage 0: Manual Approval
- Every trade requires human confirmation
- Tiny position sizes (0.5% risk)
- Review every trade within 1 hour

### Stage 1: Automated with Caps
- Automated execution with strict limits
- 1% risk per trade, max 3 positions
- Daily PnL review, `/telemetry` check

### Stage 2: Full Automated
- After N successful days (configurable)
- Normal risk parameters
- Nightly replay audit
- Weekly performance review

## File Locations
- Trade logs: `data/logs/trades_enhanced.csv`
- Telemetry snapshots: `data/telemetry/latest.json`
- Replay reports: `data/logs/nightly_replay_YYYYMMDD.txt`
- Kill switch: `data/.kill_switch`
- Strategy proposals: `data/strategy_proposals/`
