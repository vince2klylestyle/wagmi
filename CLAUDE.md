# CLAUDE.md — Master Onboarding Guide

> **Read this first.** This is the single source of truth for starting a new Claude Code session.
> For strategic context → `BLUEPRINT.md`. For execution tracking → `ROADMAP.md`.

## Session Startup Context

**Current State (March 2026):**
- 11 strategies built, **9 active**, 2 disabled (lead_lag: 0% WR; multi_tier_quality: PF 0.82)
- 9 LLM agents (7 core + Overseer + Quant), multi-agent pipeline ready but disabled by default
- 45 test files, **1,308 tests passing**
- 5 symbols: BTC, SOL, HYPE, DOGE, FARTCOIN (all Hyperliquid)
- 123 config parameters in `trading_config.py`

**Critical Problem:** Walk-forward ratio = 0.00 (zero generalization). Root cause: 80+ tunable params on 51 trades = 0.6 trades/param (need 30+). See BLUEPRINT.md "Quant Research Findings" section.

**Active Priorities (in order):**
1. Run 70-day backtest to validate Session 4 changes (9 strategies, HYPE fixes)
2. Fix SOL (17% WR, -$6,242 — actively destroying capital)
3. Improve walk-forward ratio from 0.00 (deployment blocker)
4. Radical parameter reduction (80+ → 4-6 params)
5. Paper trade validation before live

**Two-Tab Workflow:**
- **Tab 1 — Walk-Forward Validation**: `cd bot && python cli.py --mode walkforward --days 7`
- **Tab 2 — Backtest Improvement**: `cd bot && python backtest/runner.py --symbols BTC SOL HYPE --days 70`

---

## Project Overview
**nunuIRL Trading Bot** — Autonomous crypto trading bot for Hyperliquid with LLM-powered decision making (Claude API), multi-strategy ensemble, multi-agent specialist system, and Telegram/Discord monitoring.

## Architecture
```
bot/                    # Main bot code (run from here: cd bot && python run.py paper)
  ├── run.py            # Entry point (starts the bot loop)
  ├── cli.py            # CLI: --mode paper|live|replay|evolve|tiers|optimize|walkforward
  ├── core/             # Signal pipeline (6-stage filter), portfolio analytics, logging
  ├── strategies/       # 11 trading strategies + ensemble voting (weighted_veto mode)
  │   ├── ensemble.py         # Regime-aware weighted-veto voting (1,599 lines)
  │   ├── regime_trend.py     # ACTIVE: 6h/16h MACD+MFI regime alignment
  │   ├── confidence_scorer.py # ACTIVE: Multi-factor momentum scoring
  │   ├── bollinger_squeeze.py # ACTIVE: BB/KC squeeze detection
  │   ├── vmc_cipher.py       # ACTIVE: 5-oscillator confluence (WaveTrend)
  │   ├── probability_engine.py # ACTIVE: Regime-conditional Monte Carlo
  │   ├── monte_carlo_zones.py # ACTIVE: Daily TF mean-reversion zones
  │   ├── funding_rate.py     # ACTIVE: Counter-trades extreme funding (live/paper only)
  │   ├── oi_delta.py         # ACTIVE: Open interest expansion/contraction
  │   ├── liquidation_cascade.py # ACTIVE: Post-cascade reversal signals
  │   ├── lead_lag_enabled.py # DISABLED: 0% WR, -$1,100 net
  │   └── multi_tier_quality.py # DISABLED: PF 0.82, -$1,223 net
  ├── llm/              # Claude AI meta-brain (77 files)
  │   ├── decision_engine.py  # Monolithic LLM pipeline (fallback)
  │   ├── agents/             # Multi-agent specialist system (9 agents)
  │   │   ├── coordinator.py  # Pipeline orchestration
  │   │   ├── prompts.py      # 9 specialist prompts
  │   │   ├── base.py         # AgentRole enum, configs, defaults
  │   │   ├── shared_context.py    # Shared reasoning framework + strategy theory
  │   │   ├── thought_protocol.py  # OBSERVE→RECALL→REASON→DECIDE→JUSTIFY
  │   │   ├── consistency_checker.py  # Cross-agent coherence
  │   │   ├── learning_integration.py # Wires to deep memory/hypotheses
  │   │   └── calibration_ledger.py   # Per-agent accuracy tracking
  │   ├── client.py           # Anthropic API wrapper
  │   ├── usage_tiers.py      # Model routing (Opus/Sonnet/Haiku by trigger)
  │   ├── memory_store.py     # Short-term memory (100 notes, 7-day TTL)
  │   ├── deep_memory.py      # Long-term structured memory (trade DNA)
  │   ├── self_teaching.py    # Self-improvement curriculum (5 levels)
  │   └── growth/             # Hypothesis tracking, recommendations
  ├── execution/        # 28 modules: position manager, leverage, risk, reconciliation
  ├── feedback/         # 16 modules: signal quality, evolution, parameter tuner, Kelly
  ├── data/             # Runtime data (trades.csv, decisions.jsonl, memory)
  │   └── fetcher.py    # Multi-exchange OHLCV + OI + funding via CCXT
  ├── backtest/         # Backtest engine + runner + walk-forward validation
  └── tests/            # 45 test files, 1,308 tests
```

## Key Commands
```bash
cd bot && python run.py paper                          # Paper trading (safe)
cd bot && python run.py backtest                       # Run backtest
cd bot && python run.py signals                        # One-shot signal check
cd bot && python cli.py --mode walkforward --days 7    # Walk-forward validation
cd bot && python cli.py --mode tiers                   # LLM tier comparison
cd bot && python cli.py --mode evolve                  # Strategy evolution report
cd bot && python cli.py --mode optimize                # Parameter optimization
cd bot && python backtest/runner.py --symbols BTC SOL HYPE --days 70  # Multi-symbol backtest
cd bot && pytest tests/                                # Run all 1,308 tests
cd bot && pytest tests/ -k "agent"                     # Agent-specific tests
cd bot && pytest tests/ -x -q                          # Stop on first failure, quiet
```

## Environment Setup
- Copy `.env.example` → `.env`, fill in `ANTHROPIC_API_KEY` and Telegram/Discord creds
- Key env vars:
  - `LLM_USAGE_TIER` (CONSERVATIVE/RECOMMENDED/AGGRESSIVE/UNLEASHED)
  - `LLM_MODE` (0-5 autonomy: OFF/ADVISORY/VETO_ONLY/SIZING/DIRECTION/FULL)
  - `LLM_MULTI_AGENT` (true/false — enables specialist agent pipeline)
  - `ENVIRONMENT` (paper/production)

## Multi-Agent System (9 Agents)
Enable with `LLM_MULTI_AGENT=true`.

**Core Pipeline** (sequential): Regime → Trade → Risk → Critic → (Learning post-close)

| Agent | Model | Role | Required |
|-------|-------|------|----------|
| Regime | Haiku | Classifies market regime + directional outlook | Yes |
| Trade | Sonnet | Forms thesis, decides go/skip/flip | Yes |
| Risk | Haiku | Sizes positions, flags portfolio risks | Optional |
| Critic | Sonnet | Stress-tests thesis, veto power | Optional |
| Learning | Haiku | Extracts lessons from closed trades | Post-trade |
| Exit | Haiku | Monitors open positions, recommends hold/adjust/close | Optional |
| Scout | Haiku | Idle-time prep: watchlists, pre-formed theses | Optional |
| Overseer | Haiku | System health monitoring | Periodic |
| Quant | Haiku | Quantitative analysis | Optional |

Per-agent overrides: `AGENT_<ROLE>_MODEL`, `AGENT_<ROLE>_ENABLED=true/false`

## Trading System Architecture

**Signal Flow:** Strategy signals → Ensemble voting (min_votes=3) → 6-stage pipeline filter → LLM veto gate → Execution

**Ensemble Rules:**
- 9 active strategies vote per-regime (STRATEGY_REGIME_ALLOWLIST gates which strategies vote)
- min_votes=3 for most regimes, 2 for high_volatility (only 4-5 strategies allowed)
- Confidence floor capping: 93% for BTC (low vol), 90% for SOL (medium), 85% for HYPE (high)
- Chop detection filters ranging markets

**Risk Layers:**
- Circuit breakers: daily loss limit, consecutive loss streak, max drawdown
- 6-stage signal filter: validity → CB → position limits → leverage → liquidation → sizing
- Half-Kelly position sizing with per-strategy calibration
- Graduated leverage tiers by confidence + agreement

**Symbols & Volatility Profiles:**
| Symbol | Risk Tier | Vol Profile | Max Leverage |
|--------|-----------|-------------|-------------|
| BTC | low | low | 10x |
| SOL | medium | medium | 20x |
| HYPE | high | high | 20x |
| DOGE | medium | high | 12x |
| FARTCOIN | medium | high | 10x |

## Development Notes
- Python 3.10+, dependencies in `requirements.txt`
- CCXT for exchange connectivity (Hyperliquid primary)
- All trade decisions logged to `bot/data/llm/decisions.jsonl`
- LLM memory: short-term in `bot/data/llm/llm_memory.json`, deep in `bot/data/llm/deep_memory/`
- See `ROADMAP.md` for full development roadmap and priority order
- See `BLUEPRINT.md` for strategic context, quant audit, and system design rationale

## Custom Skills (Slash Commands)
Invoke with `/skill-name` in Claude Code sessions:

**Daily Operations:** `/signal-check`, `/health-check`, `/evolution`, `/trade-postmortem`
**Development:** `/backtest`, `/optimize`, `/stress-test`, `/deploy-paper`
**Code Quality:** `/refactor`, `/safety-audit`, `/cost-audit`
**Agent Dev:** `/add-agent`, `/agent-debug`
**LLM Tuning:** `/prompt-calibrate`, `/agent-consistency`, `/confidence-calibrate`, `/memory-optimize`, `/knowledge-distill`, `/veto-review`, `/agent-replay`, `/growth-report`, `/curriculum-advance`, `/model-route-tune`
**Prediction:** `/thesis-track`, `/exit-review`, `/setup-edge`
**Profitability:** `/pnl-maximize`, `/edge-finder`, `/loss-autopsy`, `/sniper-setup`, `/strategy-discover`, `/bug-triage`, `/config-audit`
**System:** `/system-map`, `/roadmap-status`, `/telegram-signals`, `/alert-config`, `/web-dashboard`

## Auto-Loaded Rules
Domain-specific rules in `.claude/rules/` auto-load when editing matching files:
- `bot/llm/**` → `.claude/rules/llm-agents.md` (agent dev rules)
- `bot/strategies/**` → `.claude/rules/strategies.md` (signal contract)
- `bot/execution/**` → `.claude/rules/execution-safety.md` (safety rules)
- `bot/tests/**` → `.claude/rules/testing.md` (test requirements)
- `bot/data/**` → `.claude/rules/data-pipeline.md` (data pipeline rules)

## Branch Strategy
- `main` — stable
- `claude/*` — active development branches
