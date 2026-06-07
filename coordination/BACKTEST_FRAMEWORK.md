# Backtest Framework & Trade Walkthroughs
**For understanding and validating trading decisions**

---

## Trade Walkthrough Template

When a trade fires, document it like this:

```
TRADE WALKTHROUGH: [Symbol] [Side] [Date/Time]

MARKET CONDITIONS AT ENTRY:
- Price: $______
- Regime: ______
- Volatility (ATR): ______
- Funding rate: ______
- OI trend: ______
- Volume: ______

RAW SIGNAL (Mechanical):
- Strategy: ______ (which of 4 generated this)
- Confidence: ___%
- Reason: [what price action triggered it]
- Entry: $______ SL: $______ TP: $______

AGENT DECISION CHAIN:

[1] Regime Agent (Haiku)
    Input: Price action, 1h/6h/daily trends, ADX, funding
    Decision: Regime is "______"
    Reasoning: [why]
    
[2] Trade Agent (Sonnet)
    Input: Signal, regime, strategy votes, recent wins/losses
    Decision: GO / SKIP / FLIP
    Confidence: ___%
    Reasoning: [why approved/rejected]
    Counter-thesis if rejected: ______
    
[3] Risk Agent (Haiku)
    Input: Approved signal, volatility, portfolio, equity
    Decision: Leverage __x, Size ____BTC, SL $_____, TP $_____
    Reasoning: [why this size]
    
[4] Critic Agent (Sonnet)
    Input: Full trade proposal from Risk Agent
    Decision: APPROVE / VETO
    Reasoning: [stress test results]

EXECUTION:
- Order placed: ______
- Filled: $______
- Slippage: $______

RESULT:
- Status: OPEN / CLOSED
- Current: $______ 
- P&L: $______
- Status trigger: [TP1 / TP2 / SL / trailing stop / thesis invalidated]

VALIDATION (Post-Trade):
- Was agent decision correct? YES / NO
- What would we change? [nothing / adjust SL / different leverage / etc]
- Learning: [what did we learn from this]
```

---

## Backtest Workflow

### Step 1: Identify Setup Type
From recent trade, extract the pattern:
```
Setup: [Symbol] [Side] in [Regime]
Example: SOL SHORT in trending_bear
Win rate (historical): ___%
Sample size: __trades
Best PnL: $______
Worst PnL: $______
```

### Step 2: Run Backtest on Similar Setups
```bash
cd bot
python run.py backtest \
  --symbols SOL \
  --days 30 \
  --filter-regime trending_bear \
  --filter-setup short \
  --llm
```

### Step 3: Analyze Results
```
BACKTEST RESULTS: SOL SHORT in trending_bear (30 days)

Total trades: __
Win rate: ___%
Avg win: $______
Avg loss: $______
Largest win: $______
Largest loss: $______
Profit factor: ______

By confidence level:
- 80%+ conf: __trades, __% WR
- 60-80% conf: __trades, __% WR
- <60% conf: __trades, __% WR

By leverage:
- 1.0-1.5x: __trades, __% WR, avg $______
- 1.5-2.0x: __trades, __% WR, avg $______
- 2.0-2.5x: __trades, __% WR, avg $______

Which agent was wrong most? _____
Should we adjust? [rule / threshold / leverage cap]
```

### Step 4: Validate Against Live
Compare live trade to backtest average:
```
Live trade: SOL SHORT trending_bear, 85% conf, 2.0x leverage → +$157
Backtest avg (2.0x leverage, 80%+ conf): +$145
Difference: +$12 (within 1 std dev) ✓

Conclusion: Trade validated. Approach is sound.
```

---

## Using Results

### For Confidence
If live trades match backtest expectations → system is working

### For Optimization
If live trades outperform backtest → raise leverage / lower confidence floor  
If live trades underperform backtest → lower leverage / raise confidence floor

### For Monitoring
Run weekly backtest on recent setups:
```bash
# Weekly validation
cd bot
python run.py backtest --symbols BTC ETH SOL HYPE --days 7 --llm --budget 5
```

Compare results:
- Same win rate? System is consistent
- Better win rate? Market favorability increased
- Worse win rate? Market conditions changed

---

## Trade Walkthrough Examples

### Example 1: WINNING TRADE ✅
```
TRADE WALKTHROUGH: ETH SHORT 2026-06-03 21:13 UTC

MARKET CONDITIONS:
- Price: $2,800
- Regime: trending_bear (strong downtrend)
- ATR: 0.9% (moderate volatility)
- Funding: -0.025% (shorts paying = crowded longs = mean reversion)
- Volume: High (breakout volume)

RAW SIGNAL:
- Strategy: bollinger_squeeze + regime_trend
- Confidence: 90%
- Entry: $2,800 SL: $2,850 TP: $2,600

AGENT CHAIN:

[1] Regime Agent
    Decision: trending_bear (EMA slopes down 1h+6h, ADX=48)
    
[2] Trade Agent
    Decision: GO (90% confidence, 2 strategies agree, strong thesis)
    Reasoning: "Support broken, resistance rejected 3x, negative funding. Short confluence clear."
    
[3] Risk Agent
    Decision: 2.0x leverage, 1.0 ETH, SL at $2,850
    Reasoning: "High volatility trending regime = 2.0x justified by Kelly"
    
[4] Critic Agent
    Decision: APPROVE
    Reasoning: "Thesis is falsifiable. If price holds $2,750, we close. Risk/reward 1:4, sharp."

RESULT:
- Status: CLOSED (trailing stop)
- Entry: $2,800 
- Exit: $1,790 (trailed as market fell)
- P&L: +$1,010.37 ✓ (10.1% return on risk)

VALIDATION:
- Decision correct? YES
- Would change anything? No, this trade had everything right.
- Learning: Negative funding + broken support + trending regime = best edge. Replicate.
```

### Example 2: SKIPPED TRADE (CORRECT) ✅
```
TRADE WALKTHROUGH: HYPE BUY 2026-06-07 01:10 UTC (SKIPPED)

MARKET CONDITIONS:
- Price: $67.50
- Regime: consolidation (choppy, no direction)
- ATR: 0.3% (low volatility)
- Funding: +0.001% (neutral)
- Volume: Low (range-bound)

RAW SIGNAL:
- Strategy: confidence_scorer
- Confidence: 77%
- Entry: $67.50 SL: $67.20 TP: $68.00

AGENT CHAIN:

[1] Regime Agent
    Decision: consolidation (no clear trend, chop ratio high)
    
[2] Trade Agent
    Decision: SKIP (consolidation = no edge, 1 strategy only)
    Reasoning: "No regime directional bias. Single strategy. Consolidation has negative EV historically."
    
[3] Risk Agent
    (Not reached - Trade Agent skipped)
    
[4] Critic Agent
    (Not reached - Trade Agent skipped)

RESULT:
- Status: SKIPPED (correct decision) ✓
- Would have entered: $67.50
- Later moved to: $67.74 (-0.36%)
- Why skipped was right: No edge in consolidation, would have been loss

VALIDATION:
- Decision correct? YES (consolidation trades lose)
- Learning: Agent skips are as important as agent goes. This prevented a losing trade.
```

---

## Next Steps

**For you:**
1. Send trade details when a trade fires
2. I'll build a walkthrough showing the decision chain
3. We'll backtest similar setups to validate

**For backtesting:**
1. Weekly validation (7-day recent trades)
2. Monthly deep audit (all trades, all setups)
3. Real-time optimization (adjust if patterns drift)

This gives you full transparency on why trades happened and confidence they're repeatable.
