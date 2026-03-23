# Phase 4 Implementation Plan: Scalping + Conviction Trading

**Timeline:** 2-3 weeks aggressive build
**Expected Revenue:** $1,770-6,550/month
**Expected Cost:** +$0.56/month
**ROI:** 3,200x

**Key Insight:** Scalping is 80% of the work but 30-40% of profit. Conviction is 20% of work but another 15-20% of profit. Together = game changer.

---

## **Phase 4.1: Scalping Infrastructure** (Week 1-2)

### **Component 1: Scalper Agent (Haiku)**

**Purpose:** Detect micro-trading opportunities on 1m/5m candles
**Trigger:** Every 1m candle (when enabled)
**Model:** Haiku (speed critical, must respond <500ms)
**Cost:** $0.0005/call × 100-200 scalps/day = $0.05-0.10/month

**Input Context:**
```json
{
  "symbol": "SOL",
  "current_price": 125.43,
  "1m_candle": {
    "open": 125.30,
    "high": 125.50,
    "low": 125.20,
    "close": 125.40,
    "volume": 2340000,
    "typical_volume_1m": 2100000
  },
  "recent_5m": [
    {"close": 125.10, "rsi_14": 15, "macd": -0.05},
    {"close": 125.20, "rsi_14": 18, "macd": -0.04},
    {"close": 125.40, "rsi_14": 28, "macd": -0.02}
  ],
  "micro_trend": "bouncing_from_low",
  "micro_momentum": "rising",
  "bid_ask_spread": 0.02,
  "order_book_depth": "thin_sellers"
}
```

**Output JSON:**
```json
{
  "action": "scalp_now|wait|pass",
  "target_ticks": 3,
  "risk_ticks": 1,
  "rr_ratio": 3.0,
  "thesis": "RSI(14)=28, emerging from oversold, volume rising → expect micro-bounce to 125.50",
  "confidence": 0.68,
  "profile": "SCALP_TIGHT",
  "entry_adjustment": "market_now",
  "profit_target": 125.46,
  "stop_loss": 125.39,
  "hold_time_seconds": 120,
  "risk_reason": "Micro dip in trend, RSI not yet 50% recovery"
}
```

**Prompt Structure:**
```
You are a micro-scalper for Hyperliquid perpetual futures. Your job is to find
1-3 minute trading opportunities when:
- Price overshoots (RSI<20 or >80)
- Volume spikes (>1.2x average)
- Bid-ask spread widens (more volatility)
- Micro-trend reversal (after 3+ candles of same direction)

RULES:
- Only scalp when condition is CLEAR (confidence >0.65)
- Hold time ALWAYS < 5 minutes (1m-3m ideal)
- Risk per scalp: 0.1-0.3% of account
- Target: 1:2 to 1:3 R:R (1 risk tick for 2-3 profit)
- Pass if uncertain — scalping is edge-heavy, not blind

Your profit thesis: RSI<20 bounces 60-70% of the time. Volume>1.5x usually means
squeeze resolution. Bid-ask widening = volatility → 50/50 odds but execution matters.

Output JSON. No prose.
```

**Backtesting Success Criteria:**
- Win rate: 45-55% (edge is execution + timing, not signal clarity)
- Profit per win: 0.5-1.0%
- Average hold time: 1.5-3 minutes
- Expected PnL: +0.1-0.2% per day when enabled
- Sharpe ratio > 1.0

---

### **Component 2: Micro-Trend Detector (Haiku)**

**Purpose:** Feed context into Scalper ("bouncing from low" vs "mid-trend dip")
**Trigger:** Every 5m candle
**Model:** Haiku
**Cost:** $0.0005/call × 1/5m = $0.07/month

**Output:**
```json
{
  "micro_trend": "bouncing_from_low|mid_trend_dip|exhaustion_forming|trend_intact|sideways_chop",
  "trend_strength": 0.0-1.0,
  "expected_continuation": "likely|uncertain|reversal_likely",
  "key_level": 125.20,
  "reason": "Price just touched 5m support (125.20), bouncing on volume"
}
```

**How Scalper Uses It:**
- "bouncing_from_low" + RSI<20 = STRONG scalp setup (confidence +0.10)
- "exhaustion_forming" + RSI>80 = STRONG scalp setup (confidence +0.10)
- "mid_trend_dip" + RSI<50 = WEAK scalp setup (confidence -0.15, prefer skip)
- "sideways_chop" = best for scalping (no directional risk)

---

### **Component 3: Tick-Level Execution Optimizer**

**Purpose:** Improve entry price by 0.3-0.8% (not an LLM call — deterministic)
**Cost:** $0.00 (no LLM)

**Logic:**
```python
def optimize_entry_execution(signal, orderbook, recent_fills):
    """
    Given a scalp signal, decide: market now vs limit vs scaled?
    """

    # If bid-ask is wide (>0.05%), use limit order
    if orderbook['spread'] > 0.05:
        # Place limit 1 tick below signal entry
        # Wait up to 2 candles, then market if not filled
        return {"method": "limit_1tick_with_market_fallback"}

    # If recent fills show fast execution (<200ms), market order
    if recent_fills['avg_latency_ms'] < 200:
        return {"method": "market_now"}

    # If volume is spiking, use scaled entry
    # 1/3 market now, 1/3 at +1 tick, 1/3 at +2 ticks
    if recent_fills['volume_spike'] > 1.5:
        return {"method": "scaled_entry_3_tranches"}

    # Default: market order
    return {"method": "market_now"}
```

**Expected Benefit:** 0.2-0.5% better average entry price = +$20-50/month

---

### **Component 4: Scalp Pattern Library**

**Purpose:** Learn which scalp setups have highest win rate from history
**Trigger:** Weekly offline analysis
**Cost:** $0.00 (cached)

**Process:**
1. Analyze last 500 trades
2. Filter: which were scalps (hold time < 5min)?
3. Group by: RSI level, volume spike, bid-ask spread, micro-trend
4. Calculate: win rate per pattern
5. Feed into Scalper as "boost_confidence" guidance

**Example Output:**
```json
{
  "scalp_patterns": [
    {
      "name": "RSI<15 + volume>1.5x + bouncing_from_low",
      "wr": 0.62,
      "n": 42,
      "avg_profit": 0.8,
      "confidence_boost": +0.15
    },
    {
      "name": "RSI>85 + volume>1.3x + exhaustion_forming",
      "wr": 0.58,
      "n": 35,
      "avg_profit": 0.7,
      "confidence_boost": +0.10
    },
    {
      "name": "Sideways_chop + width>2% band",
      "wr": 0.48,
      "n": 28,
      "avg_profit": 0.5,
      "confidence_boost": 0.0
    }
  ],
  "avoid_patterns": [
    {
      "name": "Mid-trend dip (RSI 40-60) + volume<0.8x",
      "wr": 0.35,
      "reason": "Noise, no edge"
    }
  ]
}
```

---

## **Phase 4.2: Conviction Trading** (Week 1-2, parallel)

### **Component 1: Conviction Agent (Sonnet)**

**Purpose:** Fire ONLY when all agents align (Regime + Trade + Quant + Critic)
**Trigger:** When alignment score > 0.90
**Model:** Sonnet (sophisticated reasoning)
**Cost:** $0.003/call × 10/month = $0.03/month

**Input:**
```json
{
  "regime_analysis": {
    "rg": "trend",
    "conf": 0.92,
    "bias": "bullish",
    "regime_momentum": "strengthening"
  },
  "trade_decision": {
    "a": "go",
    "c": 0.88,
    "thesis": "BTC +2.5% 1h, SOL 4/4 signal align, MC 68% up, regime trend confirmed"
  },
  "quant_analysis": {
    "ev": 0.15,
    "signal_quality": {"is_noise": false},
    "kelly_fraction": 0.18,
    "probability": {"up": 0.68, "down": 0.22, "sideways": 0.10}
  },
  "critic_analysis": {
    "action": "proceed",
    "confidence": 0.85,
    "concern": "None material"
  },
  "forecaster_analysis": {
    "hours_until_transition": [8, 16],
    "transition_probability": 0.15
  }
}
```

**Output:**
```json
{
  "conviction_level": 4,
  "alignment_score": 0.92,
  "agents_aligned": ["regime", "trade", "quant", "critic"],
  "agents_conflicted": [],
  "allowed_leverage": 2.5,
  "risk_override": true,
  "thesis": "All 4 agents agree: strong trend, SOL signal aligned, no quant noise, critic clear. 92% alignment → conviction trade authorized.",
  "position_size_multiplier": 2.5,
  "exit_plan": "Trailing stop 20% or close if regime shifts before 8h",
  "expected_pnl": "$50-100 on 1% risk trade",
  "confidence_boost": 0.25
}
```

**Prompt:**
```
You are the Conviction Agent. Your job is to AUTHORIZE HIGH-LEVERAGE trades when
ALL specialist agents align (not just one or two).

ALIGNMENT CHECK:
- Regime Agent must have confidence > 0.80 AND be in favorable regime
- Trade Agent must have confidence > 0.80 AND thesis be concrete
- Quant Agent must show EV > 0 AND signal NOT be noise
- Critic Agent must NOT veto (or veto be weak: concern < "material")
- Forecaster Agent must NOT predict regime shift in next 2h

If all 4 aligned: CONVICTION_GO authorized. Leverage = 2.5x (vs normal 1.5x).

ALIGNMENT SCORE = average confidence across agents.

If alignment > 0.90: conviction_level = 4 (maximum)
If alignment > 0.80: conviction_level = 3 (high)
If alignment > 0.70: conviction_level = 2 (medium) ← conditional authorization
If alignment < 0.70: conviction_level = 0 (no conviction, skip)

Output JSON. This is rare (5-10/month if lucky). But when it fires, it's HIGH EDGE.
```

---

### **Component 2: Thesis Validator (Deterministic)**

**Purpose:** Check memory: have we seen this exact thesis before? Did it work?
**Trigger:** Before Conviction Agent
**Cost:** $0.00 (cached lookup)

**Logic:**
```python
def validate_thesis(thesis: str, deep_memory, pattern_library):
    """
    Example thesis: "BTC broke 6h resistance, SOL lagging, regime=trend"

    Search deep memory for similar theses.
    Return: validation_score, historical_wr, n_trades
    """

    # Fuzzy match thesis against pattern library
    similar_theses = deep_memory.search_similar(thesis, threshold=0.85)

    if similar_theses:
        validated_theses = [t for t in similar_theses if t['wr'] > 0.60]
        if validated_theses:
            return {
                "status": "validated",
                "historical_wr": mean([t['wr'] for t in validated_theses]),
                "n_trades": sum([t['n'] for t in validated_theses]),
                "boost_confidence": +0.10
            }
        else:
            return {
                "status": "failed_pattern",
                "historical_wr": mean([t['wr'] for t in similar_theses]),
                "boost_confidence": -0.20
            }
    else:
        return {
            "status": "novel",
            "historical_wr": None,
            "boost_confidence": 0.0
        }
```

---

### **Component 3: High-Confidence Pattern Detector**

**Purpose:** Find setups that have >70% WR from history
**Trigger:** Weekly offline + feed into Conviction Agent
**Cost:** $0.00 (cached)

**Example:**
```json
{
  "high_confidence_patterns": [
    {
      "name": "BTC 6h breakout + SOL lagging 15min + regime=trend",
      "wr": 0.73,
      "n": 22,
      "avg_profit": 2.1,
      "condition": "conviction_boost": +0.15,
      "last_occurrence": "2026-03-19 14:30"
    },
    {
      "name": "Volume>2x avg + RSI<25 + DEEP_BUY zone",
      "wr": 0.68,
      "n": 34,
      "avg_profit": 1.5,
      "conviction_boost": +0.10
    }
  ]
}
```

---

## **Phase 4.3: Timing Optimization** (Week 2)

### **Component 1: Execution Timing Agent (Haiku)**

**Purpose:** Choose best entry method: market now vs limit vs scaled vs wait
**Trigger:** Per signal
**Model:** Haiku
**Cost:** $0.001/signal = $0.06/month

**Input:**
```json
{
  "signal": {
    "entry": 125.40,
    "thesis": "BTC trending, SOL breakout confirmed",
    "confidence": 0.82,
    "hold_time_expected": "4h"
  },
  "current_market": {
    "price": 125.50,
    "bid_ask_spread": 0.03,
    "recent_fills": {
      "avg_latency_ms": 180,
      "fill_rate": 0.95
    },
    "volume_profile": "rising",
    "momentum": "strong"
  }
}
```

**Output:**
```json
{
  "entry_method": "market_now|limit_1tick|scaled_3_tranches|wait_for_pullback",
  "reasoning": "Spread is tight (0.03), fill rate is 95%, momentum is strong → market now captures thesis",
  "alternative": "If spread widens to >0.05, use limit_1tick_with_market_fallback",
  "expected_improvement": 0.15
}
```

**Prompt:**
```
You are the Execution Timing specialist. Your job is to choose the OPTIMAL entry method.

OPTIONS:
1. "market_now" — Enter immediately at market. Use when:
   - Spread is tight (<0.05)
   - Fill rate is high (>90%)
   - Momentum is strong (want to not miss move)

2. "limit_1tick" — Place limit order 1 tick above bid. Use when:
   - Spread is wide (>0.05)
   - You have time to wait (hold time >2h)
   - Momentum is uncertain

3. "scaled_entry" — 1/3 market + 1/3 at +1tick + 1/3 at +2ticks. Use when:
   - Position size is large (1-2% risk)
   - Momentum is strong but execution risk is high
   - Want to average entry price better

4. "wait_for_pullback" — Don't enter yet. Use when:
   - Price is already extended >2% from key level
   - Momentum is fading
   - Better entry likely within next 1-2 candles

Choose the method that maximizes fill quality + executes thesis intent.
```

---

## **Phase 4 Architecture in Coordinator**

```python
# In coordinator.py, add to get_trading_decision():

# Phase 4: Scalping + Conviction
if is_scalp_timeframe:  # Every 1m candle
    scalp_out = self._call_agent(AgentRole.SCALPER, scalp_input, model)
    if scalp_out.ok and scalp_out.data.get("a") == "scalp_now":
        # Execute scalp with ultra-tight risk management
        return self._merge_scalp_output(scalp_out)

# Conviction trade check
alignment_score = compute_agent_alignment(
    regime_out, trade_out, quant_out, critic_out, forecaster_out
)
if alignment_score > 0.85:
    conviction_out = self._call_agent(AgentRole.CONVICTION, conviction_input, model_sonnet)
    if conviction_out.ok and conviction_out.data.get("a") == "go":
        # Authorize 2.5x leverage
        trade_out.data["leverage_multiplier"] = 2.5
        trade_out.data["conviction_approved"] = True
```

---

## **Phase 4 Testing Strategy**

### **Unit Tests:**
```python
# test_scalper_agent.py
def test_scalper_rsi_oversold():
    """Scalper should trigger on RSI<20 + volume spike"""
    signal = run_scalper_agent(
        rsi=15,
        volume_ratio=1.6,
        micro_trend="bouncing_from_low",
        confidence=0.68
    )
    assert signal['action'] == 'scalp_now'
    assert signal['hold_time_seconds'] < 300

def test_conviction_requires_alignment():
    """Conviction should NOT fire unless all agents agree"""
    conviction = run_conviction_agent(
        regime_conf=0.85,  # Good
        trade_conf=0.82,   # Good
        quant_ev=0.12,     # Good
        critic_veto=True   # BAD
    )
    assert conviction['conviction_level'] == 0
    assert conviction['a'] != 'go'

# test_execution_timing.py
def test_execution_chooses_market_on_tight_spread():
    """Execution optimizer should use market order when spread tight"""
    method = get_execution_method(
        spread=0.02,
        fill_rate=0.96,
        momentum="strong"
    )
    assert method == "market_now"
```

### **Backtest Strategy:**
```bash
# Backtest with scalping enabled
cd bot && python run.py backtest --mode paper --enable_scalping --symbols SOL,ETH --days 30

# Expected results:
# - Base system (trend following): +0.8% PnL, Sharpe 0.9
# - With scalping: +1.3% PnL, Sharpe 1.2
# - With conviction: +1.5% PnL, Sharpe 1.3
# - Combined: +1.8-2.0% PnL, Sharpe 1.4+
```

---

## **Phase 4 Deployment Checklist**

- [ ] Scalper Agent prompt finalized
- [ ] Micro-Trend Detector integrated
- [ ] Conviction Agent prompt finalized
- [ ] Execution Timing Agent integrated
- [ ] Scalp Pattern Library built from trade history
- [ ] Thesis Validator implemented (deterministic)
- [ ] All 4 agents added to AgentRole enum
- [ ] All 4 agents added to AGENT_PROMPTS dict
- [ ] All 4 agents added to DEFAULT_AGENT_CONFIGS
- [ ] Coordinator.py wired with scalp/conviction logic
- [ ] Unit tests passing (50+ tests)
- [ ] Backtest passing (Sharpe > 1.0, PnL > 1.5%)
- [ ] Paper trading deployed with strict limits
- [ ] Monitoring: scalp win rate, conviction accuracy, execution slippage
- [ ] Real trading: enabled after 2 weeks of paper trading success

---

## **Success Criteria for Phase 4**

**Scalping:**
- Win rate: 45-55%
- Profit per win: 0.5-1.0%
- Daily PnL: +0.1-0.2%
- Sharpe: >1.0

**Conviction:**
- Win rate: 70-75%
- Profit per win: 2-3%
- Frequency: 5-10 trades/month
- Monthly PnL: $200-500

**Combined:**
- Daily PnL: +0.2-0.4% (vs +0.08-0.12% pre-Phase 4)
- Monthly expected: $1,770-6,550 (from $500-1,000)
- Sharpe: 1.3-1.5
- Max drawdown: <20%

---

## **Go/No-Go Decision Point**

After 2 weeks of paper trading Phase 4:

**GO (to live trading) if:**
- Scalp win rate ≥45%
- Conviction win rate ≥70%
- Combined Sharpe ≥1.2
- Max drawdown ≤15%
- No execution bugs/slippage issues

**NO-GO (iterate) if:**
- Scalp win rate <45%
- Conviction fires but has veto issues
- Execution timing causing slippage >0.2%
- Sharpe <1.0 or drawdown >20%

---

**Last Updated:** 2026-03-20
**Status:** Ready to implement
**Estimated Completion:** 2026-04-05
