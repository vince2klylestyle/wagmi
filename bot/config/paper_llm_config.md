# LLM-Enabled Paper Trading Configuration

## Recommended .env Settings for First LLM Paper Run

```bash
# Enable LLM at VETO_ONLY level — can block bad trades, can't originate
LLM_MODE=2
LLM_MULTI_AGENT=true

# Start with CONSERVATIVE tier — cheapest model routing
LLM_USAGE_TIER=CONSERVATIVE

# Budget: ~$0.007/decision × ~1 trade/day × 30 days = ~$0.21/month + exits
LLM_DAILY_BUDGET_USD=2.0

# Agent configuration
AGENT_REGIME_MODEL=claude-haiku-4-5-20251001
AGENT_TRADE_MODEL=claude-sonnet-4-5-20250929
AGENT_RISK_MODEL=claude-haiku-4-5-20251001
AGENT_LEARNING_MODEL=claude-haiku-4-5-20251001
AGENT_CRITIC_MODEL=claude-sonnet-4-5-20250929
AGENT_EXIT_ENABLED=true
AGENT_SCOUT_ENABLED=false    # Start without Scout (save budget)
AGENT_RISK_ENABLED=true
AGENT_LEARNING_ENABLED=true
AGENT_CRITIC_ENABLED=true
```

## Cost Estimate

At current trade frequency (1 trade/day):
- Entry pipeline: 1 × $0.007 = $0.007/day
- Exit checks: ~3 positions × 5 checks × $0.0001 = $0.0015/day
- Learning: ~1 close × $0.0001 = $0.0001/day
- **Total: ~$0.27/month** (extremely cheap)

## Go-Live Checklist

1. [ ] Run `cd bot && pytest tests/ -x` — all 1310 tests pass
2. [ ] Run `cd bot && python run.py backtest --days 30 --symbols BTC` — PF > 1.5
3. [ ] Set LLM_MODE=2 in .env
4. [ ] Set LLM_MULTI_AGENT=true in .env
5. [ ] Verify ANTHROPIC_API_KEY is valid
6. [ ] Start paper trading: `cd bot && python run.py paper --symbols BTC`
7. [ ] Monitor via Telegram: `/llm` command shows call count
8. [ ] After 24h: check `/performance` for WR and PnL
9. [ ] After 7d: compare paper PnL to backtest expectation
10. [ ] If LLM veto accuracy > 55%: consider upgrading to LLM_MODE=3 (SIZING)

## Scaling Path

- **Week 1-2**: LLM_MODE=2 (VETO_ONLY) — validate LLM adds value
- **Week 3-4**: LLM_MODE=3 (SIZING) — LLM adjusts position size
- **Month 2**: LLM_MODE=4 (DIRECTION) — LLM picks direction
- **Month 3+**: LLM_MODE=5 (FULL) — full autonomy with risk guardrails
- **At $10K**: Tighten CB to 1.5% daily loss, use 1/4 Kelly, cap leverage 5x
