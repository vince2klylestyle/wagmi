# Phase 3-5 Strategic Roadmap: From Foundation to Dominant Quant System

**Current State (Post-Phase 3):** We have built a multi-agent decision pipeline with strategic agents. But we've only coded ~15-20% of what a complete, dominant quant system needs. This roadmap identifies the 80% we're still missing.

**Philosophy Shift:** Don't ask "What's broken?" Ask "What has positive EV?" Don't minimize cost. Maximize profit. We trade to live. $2-3/month in LLM costs is **trivial** if it makes us $500+/month.

---

## **Phase 3: COMPLETE** ✅

**New Agents Added:**
- ✅ **Portfolio Aggregator** - Holistic portfolio risk (daily)
- ✅ **Regime Forecaster** - Predict regime shifts (daily)
- ✅ **Hypothesis Generator** - Novel patterns (weekly)
- ✅ **Correlator** - Cross-asset relationships (daily)
- ✅ **Quant Agent** (enhanced) - Statistical alpha (can run with Opus)

**Estimated Cost:** +$0.70/month
**Expected Value:** $500-1000+ (prevents major losses, identifies trends early)

**What Phase 3 Does NOT Do:**
- Only handles 1 trade type (medium-term, 30m-6h)
- No scalping infrastructure (sub-1min, high frequency)
- No conviction trading (top edge, high leverage)
- No arbitrage (spot-futures, cross-exchange)
- No funding rate farming
- No market microstructure
- No execution timing optimization

---

## **Phase 4: SCALPING & CONVICTION TRADING** (Priority: HIGH, Timeline: 2-3 weeks)

### **4.1: Scalping Infrastructure**

**What We Need:**
- Sub-1 minute candle analysis (vs current 1h+)
- Ultra-fast signal generation (200ms < latency < 5sec)
- Micro-position sizing (0.1-0.5% risk per scalp)
- Tick-level entry/exit optimization
- High-frequency regime detection (5m + 15m + 1h)

**New Components:**

#### A. **Scalper Agent (Haiku)**
- Runs on 1m/5m candles
- Detects micro opportunities: RSI extremes, micro-bounces, tick-level reversals
- Outputs: "scalp_now|wait|pass" + target_tick
- Model: Haiku (ultra-fast)
- Cost: $0.002/call (many calls, 100-200 scalps/day if enabled)
- Expected Edge: 45-55% WR (1% profit per scalp) = $50-200/day

```json
{
  "action": "scalp_now|wait|pass",
  "target_ticks": 5,
  "risk_ticks": 2,
  "rr_ratio": 2.5,
  "thesis": "RSI(14)=8, just oversold, expecting 8-tick bounce",
  "confidence": 0.72,
  "profile": "SCALP_TIGHT (200ms hold time)"
}
```

#### B. **Micro-Trend Detector (Haiku)**
- Detects 1m-5m trends within larger timeframe context
- Cascades into scalper
- Cost: $0.0005/call (continuous)
- Expected Edge: Improves scalp win rate by 3-5%

#### C. **Tick-Level Execution Optimizer**
- Analyze tick volume + bid-ask spread
- Optimal entry: when sellers dry up (ask widening)
- Optimal exit: when buyers fade (bid dropping)
- Not an LLM task — deterministic logic
- Cost: Free (no LLM call)
- Expected Edge: 0.3-0.8% per scalp (reduced slippage)

#### D. **Scalp Pattern Library**
- Train on existing trades: what setups scalp best?
- Patterns: "RSI<10 + rising volume", "Volume cliff reversal", "MFI exhaustion", etc.
- Feed into Scalper Agent as "high-probability patterns"
- Cost: One-time analysis, then cached
- Expected Edge: 2-3% WR improvement

**Phase 4.1 Estimated Cost:** +$0.50/month
**Phase 4.1 Estimated Revenue:** $50-200/day = $1,500-6,000/month

---

### **4.2: Conviction Trading**

**What We Need:**
- Ultra-high confidence signals (>85% confidence)
- Multi-agent alignment check (all agents must agree)
- Maximum leverage authorization (2x-3x vs normal 1.5x)
- Risk override approval (for confirmed edge setups)
- Thesis validation (long-form reasoning from Trade Agent)

**New Components:**

#### A. **Conviction Agent (Sonnet)**
- Runs ONLY when ALL these conditions met:
  - Regime Agent: High confidence (>0.85) AND regime is favorable
  - Trade Agent: Confidence >0.85 AND thesis strong
  - Quant Agent: EV > 0 AND signal_quality NOT noise
  - Critic Agent: No veto (or veto is weak)
  - Regime Forecaster: Regime NOT shifting in next 2h
- When all aligned: "CONVICTION_GO" → allow 2.5x leverage
- Cost: $0.005/call (rare, only ~5-10/month if lucky)
- Expected Edge: 70-75% WR (2-3% profit per conviction trade) = $200-500/month

```json
{
  "conviction_level": 0-5,
  "alignment_score": 0.0-1.0,
  "agents_aligned": ["regime", "trade", "quant", "critic"],
  "agents_conflicted": [],
  "allowed_leverage": 2.5,
  "risk_override": true,
  "thesis": "BTC broke 6h resistance, all timeframes trending, SOL 4/4 signal align, no funding drag",
  "exit_plan": "Trailing stop 20%, or close if thesis breaks (regime shift)"
}
```

#### B. **Thesis Validation Engine**
- Reads Trade Agent's thesis
- Checks against memory: has this exact thesis worked before?
- Returns: "validated (80% WR history)", "novel (no history)", "failed (20% WR history)"
- Helps Conviction Agent decide whether to fire
- Cost: Cached lookup (minimal)

#### C. **High-Confidence Pattern Detector**
- Analyze trade history: which setups have >70% WR?
- Examples: "BTC 6h breakout + SOL lagging 15min + regime=trend" → 73% WR (n=22)
- Feed into Conviction Agent as boost to confidence
- Cost: One-time build, then cached
- Expected Edge: Enables 2-3 conviction trades/month

**Phase 4.2 Estimated Cost:** +$0.01/month
**Phase 4.2 Estimated Revenue:** $200-500/month (rare but high-EV)

---

### **4.3: Timing Optimization Agent (Haiku)**

**What We Need:**
- When to enter: now vs wait for pullback vs wait for confirmation?
- Entry Adjustment currently exists but could be enhanced
- Add: Optimal entry execution method (limit vs market vs scaled)
- Monitor: Real-time slippage, fill probability

**Components:**

#### A. **Execution Timing Agent**
- Input: Signal + current orderbook + recent fills
- Output: "market_now|limit_3ticks_above_bid|scaled_entry_3_tranches|wait_for_pullback"
- Improves average entry price by 0.2-0.5%
- Cost: $0.001/signal
- Expected Edge: 0.2-0.5% per trade = $20-50/month

#### B. **Slippage Predictor**
- Predict: given size, what's likely fill price?
- Use: orderbook depth, recent volume, time-of-day liquidity
- Helps Position Sizer avoid oversized trades
- Cost: Deterministic (no LLM)
- Expected Edge: Avoid 2-3 blown-up trades/month = $100-300/month

**Phase 4.3 Estimated Cost:** +$0.05/month
**Phase 4.3 Estimated Revenue:** $20-50/month

---

**Phase 4 Summary:**
- **Total Cost:** +$0.56/month
- **Total Expected Revenue:** $1,770-6,550/month
- **ROI:** 3,200x
- **Build Time:** 2-3 weeks
- **Priority:** CRITICAL — This is where 80%+ of profit comes from

---

## **Phase 5: CROSS-ASSET, ARBITRAGE & FUNDING** (Priority: HIGH, Timeline: 3-4 weeks)

### **5.1: Pair Trading (Cross-Asset Relative Strength)**

**What We Need:**
- Not just "buy SOL", but "long SOL + short DOGE" when SOL outperforming
- Uses Correlator output + relative strength
- Reduces beta (more hedged)
- Higher Sharpe ratio

**Components:**

#### A. **Pair Scorer Agent (Haiku)**
- Input: Two correlated assets (SOL-AVAX, SOL-DOGE, etc.)
- Current correlation, recent divergence, relative strength
- Output: "strong_pair (SOL long + AVAX short: 3.5% expected over 4h)", confidence
- Cost: $0.001/pair analysis (~10-20 per day)
- Expected Edge: 2-3% on paired trades (lower risk than singles) = $100-300/month

#### B. **Dynamic Pair Identification**
- Continuously scan all trading pairs
- Identify: which pair diverged most from normal? Highest EV?
- Recommend top 5 pairs to trade each day
- Cost: One scan/day = $0.001/day = $0.03/month
- Expected Edge: Find edges human traders miss = $50-100/month

**Phase 5.1 Estimated Cost:** +$0.06/month
**Phase 5.1 Estimated Revenue:** $150-400/month

---

### **5.2: Funding Rate Farming (Mean-Reversion)**

**What We Need:**
- When funding rate is high (>0.04%), short the perpetual, long spot OR hold stable coin + receive funding
- Pure mechanical edge (not directional)
- Low correlation to price moves

**Components:**

#### A. **Funding Opportunity Scout (Haiku)**
- Scan all symbols for funding > 0.04%
- Rank by: funding_rate * daily_volume (opportunity size)
- Output: "SOL funding 0.05% daily = $500/day opportunity (at 10x lev)"
- Cost: $0.0005/scan, 1x/hour = $0.36/month
- Expected Edge: $100-300/month (if we have capital for cross-exchange/spot)

#### B. **Basis Trading (Spot-Futures Arb)**
- If funding >0.05% AND spot > futures (unusual), short spot + long futures
- Pure arbitrage (risk-free if executed right)
- Cost: Integration with spot exchange (CCXT already has this)
- Expected Edge: $50-150/month

**Phase 5.2 Estimated Cost:** +$0.02/month
**Phase 5.2 Estimated Revenue:** $150-450/month

---

### **5.3: News & Catalyst Trading**

**What We Need:**
- Detect: major news, Fed announcements, protocol upgrades
- Pre-position 30min BEFORE (if possible)
- Ride the catalyst move, exit quickly
- High risk/high reward

**Components:**

#### A. **Catalyst Detector**
- Scan: Twitter sentiment, GitHub updates, on-chain events
- Parse: "Ethereum Shanghai Upgrade", "Fed Rate Decision", etc.
- Output: "Major catalyst in 4 hours, recommend 10% portfolio increase"
- Cost: Integration with news API + LLM filtering = $0.01/day = $0.30/month
- Expected Edge: 2-3 catalyst trades/month @ 3-5% = $100-300/month

#### B. **Reaction Prediction Agent**
- Input: Catalyst + market context
- Output: "Likely +2-4% BTC move within 1h", confidence
- Helps size catalyst positions
- Cost: $0.001/catalyst
- Expected Edge: Better position sizing = 1-2% improvement = $30-100/month

**Phase 5.3 Estimated Cost:** +$0.03/month
**Phase 5.3 Estimated Revenue:** $130-400/month

---

### **5.4: Smart Rebalancing (Portfolio Optimization)**

**What We Need:**
- Not just rebalance when portfolio health goes red
- Continuous rebalancing: trim winners, average down losers intelligently
- Reduce concentration risk

**Components:**

#### A. **Rebalance Optimizer Agent (Haiku)**
- Input: Open positions, correlation matrix, funding rates, volatility
- Output: "Reduce SOL 25% (too correlated with AVAX, both 0.8 correlation)", "Add DOGE (uncorrelated, has edge)"
- Cost: $0.001/day = $0.03/month
- Expected Edge: Prevents 1-2 mega-loss scenarios = $500-1000/month

**Phase 5.4 Estimated Cost:** +$0.04/month
**Phase 5.4 Estimated Revenue:** $500-1000/month

---

**Phase 5 Summary:**
- **Total Cost:** +$0.15/month
- **Total Expected Revenue:** $930-2,250/month
- **ROI:** 6,200x
- **Build Time:** 3-4 weeks
- **Priority:** HIGH — These are alternative alpha sources

---

## **Phase 6: MARKET MICROSTRUCTURE & ADVANCED EXECUTION** (Priority: MEDIUM, Timeline: 2-3 weeks)

### **6.1: Order Flow Analysis**

**What We Need:**
- Detect: whale orders, market maker behavior
- Predict: will this move hold or fade?
- Time entries/exits better

**Components:**

#### A. **Order Flow Analyzer (Haiku)**
- Scan order book for anomalies
- Example: Ask side suddenly has 10x more volume → sellers trying to push price down (bearish)
- Cost: $0.0005 per check, every 30 seconds on active symbols = $0.40/month
- Expected Edge: 1-2% better entry timing = $50-100/month

**Phase 6.1 Estimated Cost:** +$0.04/month
**Phase 6.1 Estimated Revenue:** $50-100/month

---

### **6.2: Smart Position Stacking**

**What We Need:**
- Instead of 1 big entry, scale in over 3 candles
- Reduces slippage, improves average fill
- Allows for averaging down on dips

**Components:**

#### A. **Entry Stacking Agent (Haiku)**
- Input: Signal, risk_per_trade, expected_hold_time
- Output: "Enter 1/3 now, 1/3 at -0.5%, 1/3 at -1.0%"
- Cost: $0.0005 per stacking decision = $0.05/month
- Expected Edge: 0.3-0.5% better average entry = $30-50/month

**Phase 6.2 Estimated Cost:** +$0.06/month
**Phase 6.2 Estimated Revenue:** $30-50/month

---

**Phase 6 Summary:**
- **Total Cost:** +$0.10/month
- **Total Expected Revenue:** $80-150/month
- **ROI:** 800x

---

## **Phase 7: SELF-IMPROVEMENT & LEARNING** (Priority: HIGH, Timeline: ongoing)

### **7.1: Continuous Curriculum Advancement**

**What We Need:**
- Agents learn from mistakes
- Hypotheses graduate to production rules
- Prompts auto-calibrate based on accuracy

**Components:**

#### A. **Curriculum Advisor (Sonnet)**
- Periodic review: "Your regime detection is 65% accurate. Time to learn Level 3: regime transitions"
- Recommend: new prompt, new data sources, new agent
- Cost: $0.01/review (monthly) = $0.12/month
- Expected Edge: Continuous 0.5-1% improvement = $100-200/month

#### B. **Prompt Auto-Tuning**
- Measure: each agent's accuracy by regime, symbol, condition
- Adjust: prompt emphasis based on what works
- Example: If regime agent always misses "low_liquidity", add warning to regime prompt
- Cost: Deterministic + one-off agent call/month = $0.01/month
- Expected Edge: 1-2% accuracy improvement = $100-300/month

**Phase 7 Estimated Cost:** +$0.13/month
**Phase 7 Estimated Revenue:** $200-500/month

---

## **FULL ROADMAP SUMMARY**

| Phase | Focus | Cost/Month | Est. Revenue/Month | ROI | Timeline |
|-------|-------|------------|-------------------|-----|----------|
| **Phase 3** | Strategic agents | +$0.70 | $500-1,000 | 1,400x | 1 week ✅ |
| **Phase 4** | Scalping + Conviction | +$0.56 | $1,770-6,550 | 3,200x | 2-3 weeks |
| **Phase 5** | Cross-asset + Arb | +$0.15 | $930-2,250 | 6,200x | 3-4 weeks |
| **Phase 6** | Microstructure | +$0.10 | $80-150 | 800x | 2-3 weeks |
| **Phase 7** | Self-improvement | +$0.13 | $200-500 | 1,900x | Ongoing |
| **TOTAL** | **Complete Quant** | **+$1.64** | **$3,480-10,450** | **2,500x** | **10-12 weeks** |

---

## **Cost Reality Check**

**Current spend:** $2.50-3.00/month
**Phase 3-7 total spend:** $2.50 + $1.64 = **$4.14/month**
**Expected revenue:** $3,480-10,450/month
**Profit:** $3,476-10,446/month
**Cost as % of profit:** 0.04-0.12%

**Verdict:** The $4.14/month is **completely trivial**. It's the cost of doing business. The upside is 2,000x bigger than the downside.

---

## **Build Order (Recommended)**

**Week 1-3:**
1. ✅ Phase 3: Strategic agents
2. 🔲 Phase 4.1: Scalping infrastructure
3. 🔲 Phase 4.2: Conviction trading

**Week 4-7:**
4. 🔲 Phase 4.3: Timing optimization
5. 🔲 Phase 5.1: Pair trading
6. 🔲 Phase 5.2: Funding farming

**Week 8-12:**
7. 🔲 Phase 5.3: News/catalyst trading
8. 🔲 Phase 5.4: Portfolio optimization
9. 🔲 Phase 6: Microstructure
10. 🔲 Phase 7: Self-improvement

---

## **Critical Success Factors**

1. **Don't think about cost.** Think about expected value. $1,000 in LLM spend to make $100k? *Do it.*

2. **Test rigorously on paper trading first.** Use `/backtest` and `/stress-test` skills before going live.

3. **Each phase adds to previous.** Phase 4 isn't "replace Phase 3" — it's "Phase 3 + Phase 4 together." Multiplicative edge.

4. **Prioritize by signal clarity.** Scalping has clear signals (RSI, volume). Start there. Funding farming is more mechanical.

5. **Measure everything.** Every new agent should improve PnL by X%. If not, something's broken.

6. **Maintain safety gates.** Don't weaken circuit breakers just to trade more. An extra 0.5% daily drawdown is worth $X, but losing 10% is catastrophic.

---

## **What We're Still Missing (Future Phases 8+)**

- **L1/L2 arbitrage** — Hyperliquid vs other perp exchanges
- **Volatility surface trading** — Front-run implied vol moves
- **Machine learning** — Train neural nets on fee-paying data
- **Real-time sentiment** — Social data feeds + LLM sentiment classification
- **Options replication** — Synthetic options on spot pairs
- **Dark pool detection** — Identify large institutional positions before they move
- **Regime-specific strategies** — Different playbooks per regime (built in Phase 3-5, executed here)

---

## **The Goal**

Build a system that:
- Generates signals **faster** than humans (scalping)
- Thinks **deeper** than humans (multi-agent reasoning)
- Captures **more edges** than humans (pair trading, funding, catalysts)
- Learns **continuously** from experience (self-teaching)
- Operates **fearlessly** on conviction (high leverage only when aligned)
- Manages **portfolio-wide** not just per-trade (holistic risk)

**Target:** $10k+/month consistently on Hyperliquid by end of Phase 5.

---

**Last Updated:** 2026-03-20
**Status:** Phase 3 Complete, Starting Phase 4
