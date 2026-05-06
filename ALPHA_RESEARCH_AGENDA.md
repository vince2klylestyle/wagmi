# Alpha Research Agenda - Autonomous Deep Dive

## Mission
Discover new sources of alpha beyond solo strategy gates. Expand system capabilities systematically.

## Key Finding
- Gate optimization alone WON'T solve profitability (fee drag eating 230%+ of edge)
- Need higher-quality signals OR different trading approach
- Alpha exists but is being destroyed by fixed costs

## Research Tracks (Priority Order)

### TRACK 1: Fee Drag Root Cause
**Problem**: 233-242% of gross PnL consumed by fees (impossible under normal circumstances)

**Hypothesis**: 
- Signals have extremely wide stops (fee drag = fees / stop%)
- Position sizing too small (fixed fees = huge %)
- Too many small losing trades (fees > individual P&L)

**Investigation**:
- Extract avg stop width from signals
- Calculate position size in backtest
- Measure % of trades that lose < average fee
- Compare to known good setups

**Potential Fixes**:
1. Wider stops (if still profitable) - less fee drag%
2. Larger positions - fixed fees absorbed better
3. Tighter entry/exit - fewer high-fee trades
4. Different market (less competition, better fills)

### TRACK 2: Multi-Symbol Strategy
**Current**: 4 symbols (BTC, ETH, SOL, HYPE)
**Question**: Are all equally tradeable?

**Data from backtests**:
- SOL: 80% WR, +$556
- BTC: 0% WR, -$436
- ETH: 0% WR, -$77
- HYPE: Mixed (previous data showed -$6K)

**Research**:
- Single-symbol backtest for each (SOL-only, BTC-only, etc)
- Identify which symbols have positive edge
- Focus ensemble on high-edge symbols
- Consider market cap / volatility effects

### TRACK 3: Time-of-Day Alpha
**Hypothesis**: Certain market hours have better signal quality

**Investigation**:
- Extract hour from each executed trade
- Correlate with WR by hour
- Find hours with >55% WR
- Gate out bad hours entirely

### TRACK 4: Regime-Conditional Trading
**Hypothesis**: Some strategies only work in specific regimes

**Data hints**:
- "trending_bull: 85.7% WR" (from early backtest)
- "consolidation: 2-agree 80-89% WR"
- "ranging: 0% WR"

**Investigation**:
- Build regime-specific signal weights
- Disable strategies in unfavorable regimes
- Test regime + strategy combos
- Find killer regime-strategy pairs

### TRACK 5: Order Flow / Microstructure
**Question**: Is there alpha in how we enter/exit?

**Ideas**:
- Limit orders vs market orders impact fees
- Slippage varies by time of day
- Funding rates create alpha opportunities
- Cross-exchange spreads

### TRACK 6: Risk/Reward Calibration
**Problem**: BB solos 80% WR but still losing money overall

**Question**: Are we taking outsized risks to win?

**Investigation**:
- Compare avg winner vs avg loser for each strategy
- Measure profit factor (wins/losses)
- Check if 80% WR is on small wins, 20% on huge losses
- Recalibrate position sizing by strategy

### TRACK 7: Leverage Optimization
**Current**: Using 4-7x leverage

**Questions**:
- Is leverage helping or hurting?
- Some symbols better with 2x, others 5x?
- Are losses cascading from overleveraged positions?
- Could 2x leverage + more capital work better?

### TRACK 8: Strategy Combination Effects
**Finding**: RT solos lost $999, BB solos won $1,113

**Question**: Why mix losing + winning solos?

**Investigation**:
- Test each solo strategy completely isolated
- Find "pure" high-edge combinations
- Build ensemble from winners only
- Consider signal independence (are they correlated?)

## Measurements

For each research track, track:
- **Edge**: Win rate, profit factor, Sharpe ratio
- **Robustness**: Works across symbols? Times? Regimes?
- **Scalability**: What happens with 2x volume? 10x leverage?
- **Cost**: How sensitive to fees? Slippage?

## Success Criteria

- Find ONE isolated high-edge setup (70%+ WR, 2x+ profit factor)
- Document exactly why it works
- Scale it to full system
- Target: +$1000-5000 on 60-day backtest

## Tools & Data Sources

```bash
# Extract signal characteristics
grep "confidence\|stop\|entry" /tmp/backtest_wave_*.log

# Regime analysis
grep "\[REGIME\]" /tmp/phase3_live_paper.log | tail -20

# Hour-of-day correlation
grep "TRADE EXECUTED" /tmp/phase3_live_paper.log | grep -o "[0-9][0-9]:[0-9][0-9]" | sort | uniq -c

# Symbol-specific performance
grep "BTC\|ETH\|SOL\|HYPE" /tmp/phase3_live_paper.log | grep "TRADE"
```

## Next Steps (Immediate)

1. **REVERT fee drag change** (233% WR was worse than 242%)
2. **Run SOL-only backtest** (80% WR suggests isolated edge)
3. **Analyze stop width distribution** (understand fee drag issue)
4. **Find the true killer combo** (not just quantity, QUALITY)

---

**Mindset**: System has alpha, but we're not capturing it properly. Fix the capture mechanism, not just the gates.
