# Session Starter — Copy one of these into a new Claude Code session

## Quick Start (default — picks up where we left off)
```
Read CLAUDE.md (focus on "Session Startup Context" at the top), then ROADMAP.md ("Priority Order" section near the bottom). Pick up the highest-priority unfinished item and execute. Run tests after every change.
```

## Backtest Improvement Tab
```
Read CLAUDE.md and BLUEPRINT.md ("Quant Research Findings" section at the bottom).
Your job: improve backtest profitability.

1. Run: cd bot && python backtest/runner.py --symbols BTC SOL HYPE --days 70
2. Compare results against the 70-day baseline:
   - Total: 51 trades, 47.1% WR, -$10,196 net, 0.55x PF
   - BTC: 25 trades, 56% WR, -$384 net
   - SOL: 5 trades, 17% WR, -$6,242 net (BROKEN — fix this)
   - HYPE: 21 trades, 48% WR, -$3,571 net
3. Focus on SOL (actively destroying capital) and HYPE (should improve after Session 4 fixes).
4. Run tests after every code change: cd bot && pytest tests/ -x -q
```

## Walk-Forward Validation Tab
```
Read CLAUDE.md and BLUEPRINT.md ("Quant Research Findings" section).
Your job: improve walk-forward ratio from 0.00 to >0.30.

The root cause: 80+ tunable parameters on 51 trades = 0.6 trades/param (need 30+).

1. Run current WF: cd bot && python cli.py --mode walkforward --days 7
2. Systematically reduce parameters — target 4-6 total params
3. The 11-multiplier compound sizing system is the worst offender — consider replacing with simple vol-targeting (1 param)
4. Test each strategy independently to find which ones have real edge vs noise
5. Run tests after every change: cd bot && pytest tests/ -x -q
```

## Parameter Reduction Sprint
```
Read CLAUDE.md, then BLUEPRINT.md ("Quant Research Findings").
Your job: reduce tunable parameters from 80+ to under 10.

Strategy:
1. Audit bot/trading_config.py — count every parameter that affects trade decisions
2. Identify which params can be hardcoded (universal constants) vs truly need tuning
3. Replace 11-multiplier sizing (kelly × IC × regime × drawdown × vol × BTC × portfolio × decay × agreement × WF × cap) with simple vol-targeting
4. Test each simplification independently with backtest
5. After each reduction, run walk-forward to check if WF ratio improves
```

## Strategy Deep-Dive (test each independently)
```
Read CLAUDE.md and bot/strategies/ensemble.py.
Your job: test each strategy independently to find which have real edge.

For each of the 9 active strategies:
1. Run backtest with ONLY that strategy enabled (min_votes=1, disable others)
2. Record: trades, WR, PF, avg PnL, max drawdown
3. Check: does the strategy work on ALL symbols or only some?
4. Build a matrix: strategy × symbol × regime → edge exists (yes/no)

This tells us which strategies to keep and which are noise.
```

## General Research / Analysis
```
Read CLAUDE.md. Send agents to research [YOUR TOPIC HERE].
Present findings, then update BLUEPRINT.md or ROADMAP.md with actionable items.
```
