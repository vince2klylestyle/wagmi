# LLM Ramp-Up Schedule: Gradual Integration

**Context:** Paper trading is LIVE with non-LLM system. This week: Build LLMs. Next week: Deploy with gradual ramp.

**Philosophy:** Don't blast LLMs into production. Let them learn. Start conservative. Scale up over 2 weeks.

---

## **Timeline**

### **Week 1 (THIS WEEK): Build Phase 4 LLM Agents**

**What:** Finish Phase 4 agent infrastructure
- Micro-Trend Detector ✅
- Scalper Agent ✅
- Conviction Agent ✅

**Integration:** Wire agents into existing paper trading pipeline
- Read from: Existing signal pipeline, market data, position manager
- Write to: Trade decisions (but LLMs disabled by default)

**Testing:** Basic sanity checks only
- Agent boots without errors
- Can parse market data
- Output format is valid JSON

**Deployment:** LLM features DISABLED by default (env var `LLM_AGENTS_ENABLED=false`)

---

### **Week 2: Deploy LLMs (Gradual Ramp)**

#### **Monday: LLMs Enabled (Advisory Mode)**

```
LLM_AGENTS_ENABLED=true
LLM_AGENT_MODE=advisory  # LLMs suggest, humans decide

Behavior:
- Micro-Trend runs, outputs classification
- Scalper runs, outputs signals
- Conviction runs, outputs alignment
- BUT: Non-LLM system still makes final decision
- LLM output logged but not acted upon

Purpose: Verify agents work in live market, no risk
```

**Monitor:** All metrics logged, but LLMs not controlling trades yet

#### **Tuesday-Wednesday: Slowly Enable Scalper**

```
LLM_SCALPER_ENABLED=true
LLM_SCALPER_CONFIDENCE_THRESHOLD=0.80  # Only fire high-confidence

Behavior:
- Non-LLM still controls 95% of trades
- Scalper Agent controls 5% (highest confidence only)
- Soft cap: Max 1 LLM scalp per hour

Purpose: Test execution with tiny positions ($100)
```

**Monitor:** Scalper win rate on real trades, slippage

#### **Thursday: Micro-Trend Starts Feeding Into Scalper**

```
LLM_MICRO_TREND_ENABLED=true
LLM_SCALPER_USE_MICRO_TREND=true  # Scalper reads Micro-Trend context

Behavior:
- Micro-Trend classification feeds into Scalper
- Scalper confidence boosted by Micro-Trend signal
- Still conservative (0.75+ confidence required)

Purpose: Test data flow between agents
```

#### **Friday: Conviction Agent Enabled (Rare Fire)**

```
LLM_CONVICTION_ENABLED=true
LLM_CONVICTION_THRESHOLD=0.92  # Only on maximum alignment

Behavior:
- Conviction agent runs on every signal
- Only fires if alignment > 0.92 (rare)
- When fires: 2.0x leverage authorized (vs normal 1.5x)
- Expected frequency: 0-2 trades per day

Purpose: Test high-conviction trading on real market
```

---

### **Week 3: Scale Up Gradually**

#### **Monday: Lower Scalper Confidence Gate**

```
LLM_SCALPER_CONFIDENCE_THRESHOLD=0.70  # Was 0.80

Behavior:
- More scalp signals fire (higher frequency)
- Expected: 5-10 LLM scalps per day (vs 1-2 before)
- Position size still tiny ($100)

Gate: If win rate drops <40%, revert to 0.80
```

#### **Tuesday: Increase Conviction Threshold Slightly**

```
LLM_CONVICTION_THRESHOLD=0.88  # Was 0.92, more fires

Expected frequency: 3-5 trades per day
```

#### **Wednesday: Start Mixing LLM + Non-LLM**

```
LLM_BLEND_RATIO=0.5  # 50% LLM decisions, 50% non-LLM

Behavior:
- For each signal: Flip coin
- Heads (50%): Use LLM recommendation
- Tails (50%): Use non-LLM recommendation
- A/B test in real-time

Purpose: Compare performance directly
```

**Monitor Closely:**
- LLM win rate vs Non-LLM win rate
- If LLM > Non-LLM: Increase blend ratio
- If LLM < Non-LLM: Decrease blend ratio

#### **Thursday-Friday: Scale Based on Results**

```
If LLM WR > Non-LLM WR:
  └─ Increase LLM_BLEND_RATIO to 0.75 (75% LLM, 25% non-LLM)

If LLM WR < Non-LLM WR:
  └─ Decrease LLM_BLEND_RATIO to 0.25 (25% LLM, 75% non-LLM)

If roughly equal:
  └─ Keep at 0.50, gather more data
```

---

## **Conservative Ramp-Up Progression**

```
Week 2, Monday:   LLM_AGENTS_ENABLED=true (advisory only)
Week 2, Tuesday:  LLM_SCALPER_ENABLED=true (0.80 confidence)
Week 2, Thursday: LLM_MICRO_TREND_ENABLED=true
Week 2, Friday:   LLM_CONVICTION_ENABLED=true

Week 3, Monday:   Lower scalper gate to 0.70
Week 3, Tuesday:  Conviction threshold to 0.88
Week 3, Wednesday-Friday: A/B test (50/50 blend)

Week 3 End: Scale to final position sizing (0.5x-1.0x of non-LLM)
```

---

## **Safety Rails at Each Stage**

### **Advisory Mode (Week 2, Monday)**
```
Kill switch: None (LLMs not trading, just logging)
Monitor: Agent outputs (valid JSON? Reasonable confidence?)
Gate to next stage: Agents produce clean output for 24 hours
```

### **Scalper Enabled (Week 2, Tuesday)**
```
Kill switch: If any single trade > 0.5% loss, disable Scalper
Monitor: Win rate, slippage, execution quality
Gate: 10+ scalp trades at ≥40% WR → proceed to Micro-Trend
```

### **Micro-Trend + Conviction (Week 2, Thursday-Friday)**
```
Kill switch: If conviction win rate <60%, disable Conviction
Monitor: Both agents separately
Gate: 5+ conviction trades at ≥70% WR → proceed to blend
```

### **A/B Testing (Week 3, Wednesday)**
```
Kill switch: If either LLM or non-LLM shows <35% WR, revert
Monitor: Side-by-side performance comparison
Gate: Run for 5+ days of A/B tests before scaling blend
```

---

## **Position Sizing During Ramp-Up**

### **Week 2 (Advisory → Scalar)**

```
Non-LLM system: 1.0x normal position size
Scalper (LLM): 0.1x normal (tiny, $100 test positions)
Conviction (LLM): 0.5x normal (small, $500 test positions)

Total portfolio: ~1.0x-1.5x (slightly larger than before)
```

### **Week 3 (Scale Phase)**

```
Non-LLM system: 1.0x normal
Scalper (LLM): 0.5x normal (scale up from 0.1x)
Conviction (LLM): 1.0x normal (scale up from 0.5x)

Total portfolio: ~2.0x-2.5x (larger, but still controlled)
```

### **Week 4+ (Full Integration)**

```
If both LLM + Non-LLM showing >45% WR:
  └─ Both get 1.0x normal position sizing
  └─ Total portfolio: 2.0x (full deployment)

If LLM < Non-LLM in performance:
  └─ Reduce LLM to 0.5x, keep non-LLM at 1.0x
  └─ Total: 1.5x (LLM supporting, not leading)
```

---

## **Real-Time Monitoring: Per Stage**

### **Week 2, Monday (Advisory)**

```
Metric              Target        Action If Miss
─────────────────────────────────────────────────
Agent boot time     <2s           Debug startup
JSON valid          100%          Debug parsing
Output reasonable   Yes           Check logic
```

### **Week 2, Tuesday (Scalper)**

```
Metric              Target        Action If Miss
─────────────────────────────────────────────────
Scalp WR            ≥40%          Lower confidence gate
Execution fills     95%+          Check order size
Slippage actual     ≤0.12%        Reduce position size
Errors/crashes      0             Debug immediately
```

### **Week 2, Thursday-Friday (Conviction)**

```
Metric              Target        Action If Miss
─────────────────────────────────────────────────
Conviction WR       ≥70%          Raise alignment threshold
Fire frequency      1-5/day       Check threshold
Avg conviction PnL  >0%           Adjust leverage multiplier
```

### **Week 3, Wed-Fri (A/B Test)**

```
Metric              Target        Action If Miss
─────────────────────────────────────────────────
LLM WR              ≥40%          Lower confidence gates
Non-LLM WR         ≥40%          Check non-LLM logic
LLM vs Non-LLM     Comparable    Analyze differences
```

---

## **Decision Points: Go/No-Go**

### **After Week 2**

**Question:** Can LLMs execute without crashing?
- ✅ YES: Proceed to scaling (Week 3)
- ❌ NO: Debug, stay in advisory mode

**Metrics Gate:**
- Scalper 10+ trades at ≥40% WR? ✅ Go
- Conviction 5+ trades at ≥70% WR? ✅ Go
- Zero crashes in 7 days? ✅ Go

### **After Week 3 (Mid-Week)**

**Question:** Are LLMs competitive with non-LLM system?
- ✅ YES: Scale to 50/50 blend
- ❌ NO: Keep at 20/80, debug

**Metrics Gate:**
- LLM WR ≥ Non-LLM WR? ✅ Continue
- Blend test stable? ✅ Continue

### **After Week 3 (End)**

**Question:** Ready for full integration?
- ✅ YES: Both systems at 1.0x sizing (Week 4+)
- ❌ NO: Keep LLM at reduced sizing (0.5x), non-LLM at 1.0x

**Final Decision:** LLM-led or LLM-supporting?
- If LLM WR > Non-LLM: LLMs take lead
- If LLM WR < Non-LLM: LLMs support (reduced sizing)
- If equal: 50/50 blend forever

---

## **What Success Looks Like**

### **Week 2 Success**
- LLMs boot cleanly, output valid JSON
- Scalper: 10+ trades, 40-55% WR
- Conviction: 5+ trades, 70%+ WR
- Zero crashes/bugs

### **Week 3 Success**
- LLM win rate ≥ Non-LLM win rate
- A/B test stable (can compare fairly)
- Ready to scale both to full sizing

### **Week 4+ Success**
- LLMs integrated as co-pilots (or leaders)
- Combined system: 50-60% win rate
- Expected daily PnL: 0.3-0.5%

---

## **What Failure Looks Like**

### **Week 2 Failure**
- Agents crash frequently
- Win rates <35%
- Execution issues (fills, slippage)
→ **Action:** Debug Phase 4, stay in paper longer

### **Week 3 Failure**
- LLM WR < Non-LLM WR significantly
- A/B test shows divergence
→ **Action:** Reduce LLM sizing, keep as supporting only

### **Critical Failure**
- System loses >2% in single day
- Any crashes or logic errors
- Confidence scores obviously wrong
→ **Action:** Kill all LLM features, revert to non-LLM only, debug

---

## **Environment Variables: Control Ramp**

```bash
# Master switch
LLM_AGENTS_ENABLED=true/false

# Per-agent switches
LLM_MICRO_TREND_ENABLED=true/false
LLM_SCALPER_ENABLED=true/false
LLM_CONVICTION_ENABLED=true/false

# Confidence gates (increase = more conservative)
LLM_SCALPER_CONFIDENCE_THRESHOLD=0.55-0.80
LLM_CONVICTION_ALIGNMENT_THRESHOLD=0.85-0.95

# Position sizing multiplier (scale LLM positions independently)
LLM_SCALPER_POSITION_MULTIPLIER=0.1-1.0
LLM_CONVICTION_POSITION_MULTIPLIER=0.1-1.0

# A/B testing
LLM_BLEND_RATIO=0.0-1.0 (0=all non-LLM, 1.0=all LLM, 0.5=50/50)

# Logging/debugging
LLM_LOG_ALL_SIGNALS=true/false
LLM_LOG_AGENT_OUTPUT=true/false
```

**Example Week 2 Configuration:**
```bash
LLM_AGENTS_ENABLED=true
LLM_SCALPER_ENABLED=true
LLM_CONVICTION_ENABLED=true
LLM_MICRO_TREND_ENABLED=false
LLM_SCALPER_CONFIDENCE_THRESHOLD=0.80
LLM_CONVICTION_ALIGNMENT_THRESHOLD=0.92
LLM_SCALPER_POSITION_MULTIPLIER=0.1
LLM_CONVICTION_POSITION_MULTIPLIER=0.5
LLM_BLEND_RATIO=0.0  # Advisory mode (no actual trading)
```

**Example Week 3 Configuration:**
```bash
LLM_AGENTS_ENABLED=true
LLM_SCALPER_ENABLED=true
LLM_CONVICTION_ENABLED=true
LLM_MICRO_TREND_ENABLED=true
LLM_SCALPER_CONFIDENCE_THRESHOLD=0.70
LLM_CONVICTION_ALIGNMENT_THRESHOLD=0.88
LLM_SCALPER_POSITION_MULTIPLIER=0.5
LLM_CONVICTION_POSITION_MULTIPLIER=1.0
LLM_BLEND_RATIO=0.50  # A/B test
```

---

## **The Philosophy**

**Don't explode LLMs into production. Let them learn.**

- Week 2: Advisory mode (observe, no risk)
- Week 2: Gradual activation (smallest positions)
- Week 3: A/B test (compare fairly)
- Week 3 end: Scale based on data
- Week 4+: Fully integrated (or supporting role)

**This takes patience. But prevents catastrophic failures.**

---

**Timeline:**
- **This week:** Build Phase 4 agents (finish infrastructure)
- **Next week:** Deploy with advisory mode (no risk)
- **Week after:** Scale gradually, A/B test, decide

Ready to execute this?

---

**Last Updated:** 2026-03-20
**Status:** Ready for Phase 4 build
**Deployment:** Next week (advisory), Week 3 (gradual scale)
