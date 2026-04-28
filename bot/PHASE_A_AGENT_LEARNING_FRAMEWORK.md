# Phase A Agent Learning Framework
**Status**: Backtest running with full 9-agent coaching (2-3 hour run)  
**Agents Active**: Regime, Trade, Risk, Critic, Learning, Exit, Scout, Overseer, Quant  
**Route**: Claude CLI (USE_CLI_LLM=true)  
**Signal Volume**: 3,500+ signals over 100 days  

---

## What Each Agent Will Learn

### Regime Agent (Haiku via CLI)
**Role**: Classify market regime for each signal  
**Input**: OHLCV + trend indicators (1h, 6h, daily)  
**Output**: Regime classification (trending_bull, trending_bear, ranging, consolidation, high_volatility, etc.)

**Learning Targets**:
- Which regimes generate the most profitable signals
- Regime transition patterns (when does ranging become trending?)
- Regime-specific confidence calibration (is 60% confidence in trending = same as 60% in ranging?)

**Expected Output**:
```
Regime breakdown from 100-day backtest:
- trending_bear: 100% WR in Phase A sample, expect agent to recognize this as optimal
- trending_bull: 100% WR, expect high confidence recommendations
- ranging: 0% WR, expect agent to recommend SKIP or reduced leverage
- consolidation: 0% WR, expect agent to flag as risky
```

### Trade Agent (Sonnet via CLI)
**Role**: Form directional thesis, decide go/skip/flip  
**Input**: Regime, symbol, price structure, confluence score  
**Output**: Thesis + confidence (go/skip/flip)

**Learning Targets**:
- Which symbol+regime combos are tradable (ETH in trending OK? SOL in ranging avoid?)
- Confluence vs solo signal tradeoff (1_agree outperformed 2_agree by $1,746 in Phase A sample)
- Time-of-day patterns (18:00 UTC +$475, 10:00 UTC -$435)

**Expected Output**:
```
Trade decision patterns the agent will extract:
- BTC: Better in trending (100% WR), skip in ranging
- SOL: 67% WR overall, solid performer across regimes
- HYPE: Volatile, 33% WR, agent should recommend caution/reduced leverage
- ETH: 0% executed in Phase A, agent will analyze missed opportunities
```

### Risk Agent (Haiku via CLI)
**Role**: Size positions, flag portfolio risks, manage leverage  
**Input**: Trade thesis + confidence, current portfolio exposure  
**Output**: Recommended position size, leverage tier, portfolio risk flag

**Learning Targets**:
- Optimal leverage by confidence level (high confidence = 8-12x? low confidence = 2-4x?)
- Kelly sizing vs fixed sizing (which works better in this edge distribution?)
- Leverage correlation with drawdowns (is 4.7x avg leverage killing us?)

**Expected Output**:
```
Sizing patterns agent will learn:
- Current avg leverage: 4.7x on 9 trades
- Current avg loser: -$410.83
- Current avg winner: +$681.97
- Payoff ratio: 1.66:1
- Agent recommendation: "Reduce leverage on confidence <70%, boost on trending 100% WR setups"
```

### Critic Agent (Sonnet via CLI)
**Role**: Stress-test thesis, provide counter-thesis, veto trades  
**Input**: Trade Agent's thesis + underlying data  
**Output**: Confidence adjustment, veto reasoning

**Learning Targets**:
- Which Trade Agent decisions were actually bad (measure post-trade)
- What counter-theses work best (regime mismatch? weak confluence? liquidity issues?)
- Veto accuracy: What % of vetoed trades would have lost money?

**Expected Output**:
```
Critic learning:
- Phase A sample showed 2_agree combos were 0% WR (all losses)
- Agent will learn: "When multi_tier_quality contradicts, trust solo signal"
- Or: "multi_tier_quality disabled = good choice, Critic confirms"
- Veto recommendations: "Veto if range regime with high leverage"
```

### Learning Agent (Haiku via CLI)
**Role**: Extract lessons from closed trades, measure thesis accuracy  
**Input**: Closed trade with entry/exit/thesis  
**Output**: Thesis accuracy, pattern extracted, rule proposed

**Learning Targets**:
- Thesis accuracy by setup type (trend_follow: 75% WR, mean_reversion: 0% WR)
- Thesis accuracy by regime (trending 100%, ranging 0%)
- Thesis accuracy by hour (18:00 UTC +$475, 10:00 UTC -$435)
- Thesis accuracy by confidence level (90-100% profitable, <60% losing)

**Expected Output**:
```
Learning Agent extractions:
1. "trend_follow setup in trending market = 75% WR, should always accept"
2. "mean_reversion setup = 0% WR, should disable or add strict filters"
3. "high confidence (90-100%) = profitable, low confidence (<60%) = losing"
4. "18:00 UTC has +$475 avg win, 10:00 UTC has -$435 avg loss — time-of-day edge"
5. "bollinger_squeeze alone = 57% WR, viable solo strategy"
```

### Exit Agent (Haiku via CLI)
**Role**: Monitor open positions, reassess thesis validity  
**Input**: Open position + current regime/price  
**Output**: Hold/adjust/close recommendation

**Learning Targets**:
- Which setups need early exit (mean_reversion blow up, need tighter trailing?)
- Which setups benefit from patience (trend_follow need longer holds?)
- Exit profile accuracy (SL vs TP1 vs TP2 vs TRAILING — which exits most?)

**Expected Output**:
```
Exit learning:
- Current: 71.4% exit via SL (5 out of 7 losing positions)
- Trailing stops helping: 2 positions trailed for +$661.31
- Agent recommendation: "Use trailing stops more on trending setups, tighter SL on mean_reversion"
```

### Scout Agent (Haiku via CLI, idle-time)
**Role**: Prepare watchlists, pre-form theses during idle times  
**Input**: Market data, regime history, known edges  
**Output**: Pre-analyzed setups waiting for entry

**Learning Targets**:
- What symbols + regimes should we monitor constantly?
- Pre-position theses before entry signals (reduces decision latency)
- Watchlist quality (which watched setups actually trade vs false alarms?)

**Expected Output**:
```
Scout recommendations:
- "Watch SOL in trending: 67% WR, solid performer"
- "Flag HYPE for regime transitions: volatile, needs precise entry"
- "BTC only in trending: 100% WR trend_follow, skip ranging"
```

### Overseer Agent (Haiku via CLI, monitoring)
**Role**: Cross-agent consistency, health monitoring  
**Input**: All agent outputs  
**Output**: Contradiction flags, health metrics

**Learning Targets**:
- Do agents agree on regime classification?
- Are Trade and Critic agents' disagreements learning signals?
- Portfolio health: leverage, drawdown, stress signals

**Expected Output**:
```
Overseer alerts:
- "Regime Agent and Trade Agent aligned 94% of time"
- "Critic veto rate: 33% (3 vetoes out of 9 trades executed)"
- "Portfolio leverage trending up: 4.7x avg, peak 12x"
```

### Quant Agent (Haiku via CLI)
**Role**: Statistical analysis, metric extraction  
**Input**: Trade data, performance metrics  
**Output**: Quant insights, parameter recommendations

**Learning Targets**:
- Information coefficient by strategy (regime_trend = 0.45 IC? bollinger_squeeze = 0.65?)
- Sharpe ratio by setup type and regime
- Optimal parameters for gate thresholds (confidence_floor, min_votes, etc.)

**Expected Output**:
```
Quant findings:
- "bollinger_squeeze has positive IC: should increase weight"
- "multi_tier_quality has negative IC: confirmed disable"
- "Optimal confidence_floor: 75% in trending, 85% in ranging"
- "Optimal min_votes: 1 in trending, 3 in ranging"
```

---

## Phase A.5: Extract + Optimize

After backtest completes, agents will have learned:

1. **Strategy-specific value**: Which strategies work, which don't, under what conditions
2. **Regime-specific rules**: Different gates/leverage per regime
3. **Setup-specific profiles**: Different exit profiles for trend_follow vs mean_reversion
4. **Time-of-day patterns**: Profitable hours vs losing hours
5. **Symbol-specific edges**: BTC vs SOL vs ETH vs HYPE performance differences

### Config Optimizations to Apply
Based on what agents learn, update .env:

```bash
# Example: If agents find regime-specific value
ENSEMBLE_CONFIDENCE_FLOOR_TRENDING=55     # Lower in profitable regime
ENSEMBLE_CONFIDENCE_FLOOR_RANGING=85      # Higher in dangerous regime
MIN_VOTES_REQUIRED_TRENDING=1             # Accept solo in trending
MIN_VOTES_REQUIRED_RANGING=3              # Require consensus in ranging

# Example: If agents find setup-specific value
ENABLE_MEAN_REVERSION_GATE=true           # Since 0% WR, gate it
ENABLE_TREND_FOLLOW_BOOST=true            # 75% WR, boost confidence

# Example: If agents find symbol-specific value
BTC_ENABLED=true                          # 100% WR in trending
SOL_ENABLED=true                          # 67% WR, good performer
HYPE_ENABLED=true_with_caution            # 33% WR, needs filters
ETH_ENABLED=maybe_restricted              # 0% executed, analyze why
```

### Next Run: Phase A.5 Backtests
After config updates:
```bash
# 30d + 100d backtests with agent-optimized config
python run.py backtest --symbols BTC,ETH,SOL,HYPE --days 30
python run.py backtest --symbols BTC,ETH,SOL,HYPE --days 100
```

Expected improvement: +30-50% PnL as agents' learned rules take effect.

---

## Timeline

```
Now (04:00 UTC):     Start Phase A 100-day backtest with agents
~06:00-07:00 UTC:    Backtest completes, agents have learned
~07:00-08:00 UTC:    Extract lessons, document patterns
~08:00-09:00 UTC:    Apply optimizations, update config
~09:00-11:00 UTC:    Run Phase A.5 backtests with optimized config
~11:00 UTC+:         Measure improvement, decide next phase
```

**Cost**: ~$10-15 in Claude API calls (via CLI) for 3,500+ signal evaluations × 9 agents

---

**Philosophy**: This is not parameter optimization — it's **learning what the system is actually capable of**. Agents discover the real edges through empirical testing with full market context.
