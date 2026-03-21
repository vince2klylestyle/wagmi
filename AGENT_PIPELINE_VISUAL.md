# Agent Pipeline Visual Diagrams

## 1. COMPLETE MULTI-AGENT DECISION FLOW

```
╔════════════════════════════════════════════════════════════════════════════╗
║                         ENSEMBLE SIGNAL RECEIVED                           ║
║              (4 strategies vote: regime_trend, monte_carlo, etc)           ║
╚════════════════════════════════════════════════════════════════════════════╝
                                       ↓
                         ┌─────────────────────────┐
                         │  LOAD MEMORY SUMMARY    │
                         │  - deep_memory (DNA)    │
                         │  - recent_lessons       │
                         │  - self_teach rules     │
                         │  - hypothesis_tracker   │
                         │  - calibration_ledger   │
                         └─────────────────────────┘
                                       ↓
                         ┌─────────────────────────┐
                         │   BUILD SNAPSHOT        │
                         │   - market data         │
                         │   - positions           │
                         │   - risk context        │
                         │   - trigger reason      │
                         └─────────────────────────┘
                                       ↓
                    ┌──────────────────────────────────┐
                    │   THROTTLE CHECK (3 min cache)   │
                    │   Too recent? → Use cached       │
                    │   Otherwise → Run new pipeline   │
                    └──────────────────────────────────┘
                           ↓              ↓
                      USE CACHE      NEW DECISION
                           ↓              ↓
                        [CACHE]    ┌──────────────────────────────────────────┐
                                   │     MULTI-AGENT PIPELINE STARTS          │
                                   └──────────────────────────────────────────┘
                                                 ↓
                         ╔═══════════════════════════════════════╗
                         ║    STEP 1: REGIME AGENT (REQUIRED)   ║
                         ║    Model: Haiku, 2048 tokens         ║
                         ║    Timeout: 15 seconds               ║
                         ╚═══════════════════════════════════════╝
                                 ↓
                         ┌──────────────────┐
                         │ Input: Market    │
                         │ - Price change % │
                         │ - Volume ratio   │
                         │ - OI change      │
                         │ - Funding rate   │
                         │ - BTC direction  │
                         └──────────────────┘
                                 ↓
                         ┌────────────────────────────┐
                         │ REGIME AGENT REASONING:    │
                         │ 1. OBSERVE (data)          │
                         │ 2. RECALL (history)        │
                         │ 3. CLASSIFY (one regime)   │
                         └────────────────────────────┘
                                 ↓
                    ┌────────────────────────────────┐
                    │ Output JSON:                   │
                    │ {                              │
                    │   "rg": "trend",               │
                    │   "conf": 0.85,                │
                    │   "bias": "bullish",           │
                    │   "transition": "stable",      │
                    │   "regime_momentum": "str",    │
                    │   "expected_duration_h":[6,18]│
                    │   "outlook": "...1-line pred"  │
                    │ }                              │
                    └────────────────────────────────┘
                                 ↓
                    ┌────────────────────────────────┐
                    │ WRITE TO SCRATCHPAD:           │
                    │ regime = "trend"               │
                    │ regime_conf = 0.85             │
                    │ bias = "bullish"               │
                    │ outlook = "price to 145+"      │
                    └────────────────────────────────┘
                                 ↓
         ┌───────────────────────────────────────────────────────┐
         │ [OPTIONAL] QUANT AGENT (Statistical analysis)         │
         │  - Probability estimates                              │
         │  - Expected value calculation                         │
         │  - Kelly fraction sizing                              │
         │  - Signal quality scoring                             │
         │  Feeds into Trade Agent as quant context              │
         └───────────────────────────────────────────────────────┘
                                 ↓
                         ╔═══════════════════════════════════════╗
                         ║    STEP 2: TRADE AGENT (REQUIRED)    ║
                         ║    Model: Sonnet, 3072 tokens         ║
                         ║    Timeout: 20 seconds                ║
                         ╚═══════════════════════════════════════╝
                                 ↓
                         ┌──────────────────┐
                         │ Input:           │
                         │ - Regime output  │
                         │ - Signal context │
                         │ - Quant analysis │
                         │ - Memory lessons │
                         │ - Deep memory    │
                         │ - Self-teach     │
                         │ - Recent trades  │
                         │ - Scratchpad     │
                         └──────────────────┘
                                 ↓
                         ┌────────────────────────────┐
                         │ TRADE AGENT REASONING:     │
                         │ 1. OBSERVE (signals)       │
                         │ 2. RECALL (similar trades) │
                         │ 3. REASON (thesis)         │
                         │ 4. DECIDE (go/skip/flip)   │
                         │ 5. JUSTIFY (why?)          │
                         └────────────────────────────┘
                                 ↓
                    ┌────────────────────────────────┐
                    │ Output JSON:                   │
                    │ {                              │
                    │   "a": "go",                   │
                    │   "c": 0.72,                   │
                    │   "thesis": "SOL trend cont... │
                    │   "ea": "market now",          │
                    │   "mu": "memory note...",      │
                    │   "n": "brief reasoning"       │
                    │ }                              │
                    └────────────────────────────────┘
                                 ↓
                    ┌────────────────────────────────┐
                    │ WRITE TO SCRATCHPAD:           │
                    │ action = "go"                  │
                    │ confidence = 0.72              │
                    │ thesis = "SOL trend cont..."   │
                    └────────────────────────────────┘
                                 ↓
         ┌───────────────────────────────────────────────────────┐
         │ [OPTIONAL] RISK AGENT (Position sizing)               │
         │  - Leverage calculation                               │
         │  - Position size in USD                               │
         │  - Correlation penalties                              │
         │  - Funding cost checks                                │
         │  - Strategy weight adjustments                        │
         └───────────────────────────────────────────────────────┘
                                 ↓
         ┌───────────────────────────────────────────────────────┐
         │ CONSISTENCY CHECK                                      │
         │  - Regime format valid?                               │
         │  - Trade action matches regime?                       │
         │  - Risk flags align with trade?                       │
         │  On CRITICAL failure: Trade → skip (50% conf)         │
         └───────────────────────────────────────────────────────┘
                                 ↓
         ┌───────────────────────────────────────────────────────┐
         │ QUANT ADJUSTMENT                                      │
         │  If Quant Agent flagged signal as noise:              │
         │  - Apply confidence adjustment (-0.15 to +0.15)       │
         │  - On very low quality: Consider degrading to skip    │
         └───────────────────────────────────────────────────────┘
                                 ↓
                         ╔═══════════════════════════════════════╗
                         ║   STEP 3: CRITIC AGENT (OPTIONAL)    ║
                         ║   Model: Sonnet, 3072 tokens          ║
                         ║   Timeout: 20 seconds                 ║
                         ║   Veto Power: YES (can override)      ║
                         ╚═══════════════════════════════════════╝
                                 ↓
                         ┌──────────────────┐
                         │ Input:           │
                         │ - Regime output  │
                         │ - Trade output   │
                         │ - Risk output    │
                         │ - Scratchpad     │
                         │ - Recent lessons │
                         │ - Self-perf data │
                         └──────────────────┘
                                 ↓
                         ┌────────────────────────────┐
                         │ CRITIC REASONING:          │
                         │ 1. OBSERVE (prior agents)  │
                         │ 2. CHALLENGE (contradicts?)│
                         │ 3. VERDICT (approve/chal)  │
                         └────────────────────────────┘
                                 ↓
                    ┌────────────────────────────────────┐
                    │ Output JSON (if challenging):      │
                    │ {                                  │
                    │   "verdict": "challenge",          │
                    │   "confidence_adjustment": -0.10,  │
                    │   "adjusted_action": "skip",       │
                    │   "counter_thesis": "...",         │
                    │   "reason": "..."                  │
                    │ }                                  │
                    └────────────────────────────────────┘
                                 ↓
         ┌───────────────────────────────────────────────────────┐
         │ OUTPUT MERGER                                          │
         │  - Combines regime + trade + risk + critic            │
         │  - Creates single LLMDecision object                  │
         │  - Records consistency score                          │
         │  - Returns merged decision or None if required fails  │
         └───────────────────────────────────────────────────────┘
                                 ↓
╔════════════════════════════════════════════════════════════════╗
║                     RISK GATING LAYER                          ║
║                                                                ║
║ Rules (checked in priority order):                             ║
║  1. Circuit breaker active? → REJECT                           ║
║  2. Confidence < 0.60? → REJECT (confidence floor)             ║
║  3. Daily loss > limit? → REJECT                               ║
║  4. Max positions reached? → REJECT                            ║
║  5. Volatility too high? → REJECT                              ║
║  6. Panic regime + conf < 0.70? → REJECT                       ║
║  7. Unknown regime + non-flat? → REJECT                        ║
║  8. Low liquidity + non-flat? → REJECT                         ║
║  9. 4+ consecutive losses + conf < 0.68? → REJECT              ║
║  10. Flip + conf < 0.65? → REJECT (flip gate)                  ║
║                                                                ║
║ Result: GatedResult(allowed=bool, decision=LLMDecision)        ║
╚════════════════════════════════════════════════════════════════╝
                                 ↓
╔════════════════════════════════════════════════════════════════╗
║                   AUTONOMY ROUTER (Mode-Specific)              ║
║                                                                ║
║ Mode 0 (OFF):        → LLM ignored, use baseline               ║
║ Mode 1 (ADVISORY):   → LLM logged, not used                    ║
║ Mode 2 (VETO_ONLY):  → LLM can reject, scales by confidence    ║
║ Mode 3 (SIZING):     → LLM scales size, direction from ensemble║
║ Mode 4 (DIRECTION):  → LLM picks go/skip/flip + size           ║
║ Mode 5 (FULL):       → LLM drives direction + sizing + regime  ║
╚════════════════════════════════════════════════════════════════╝
                                 ↓
                    ┌─────────────────────────┐
                    │   AUDIT LOGGING         │
                    │   - Append to decisions.jsonl
                    │   - Include all details │
                    │   - Searchable          │
                    └─────────────────────────┘
                                 ↓
                    ┌─────────────────────────┐
                    │   BOT EXECUTION LAYER   │
                    │   - Position manager    │
                    │   - Exchange API        │
                    │   - Circuit breaker     │
                    │   - Final risk gating   │
                    └─────────────────────────┘
                                 ↓
                    ┌─────────────────────────┐
                    │   POSITION OPENED       │
                    │   OR SKIPPED            │
                    └─────────────────────────┘
```

---

## 2. EXIT INTELLIGENCE PIPELINE

```
╔════════════════════════════════════════════════════════════════════════════╗
║                     EXIT PIPELINE (Periodic On Open Positions)             ║
║                     Runs every 2 minutes per symbol                        ║
╚════════════════════════════════════════════════════════════════════════════╝

OPEN POSITION STATE
  {
    symbol: "SOL",
    side: "LONG",
    entry: 145.50,
    current: 147.80,
    hold_time_min: 67,
    unrealized_pnl: 39.15,
    sl_original: 142.50,
    tp_original: 154.20,
    ...
  }
         ↓
    ┌────────────────────────┐
    │ PREPARE CONTEXT        │
    │ - Entry regime         │
    │ - Current regime       │
    │ - Recent lessons       │
    │ - Volume/funding       │
    │ - Original thesis      │
    └────────────────────────┘
         ↓
╔═══════════════════════════════════════════════════════════════╗
║  EXIT AGENT (Haiku, 1024 tokens, timeout 10s)               ║
║  Role: Reassess thesis validity, suggest adjustments        ║
╚═══════════════════════════════════════════════════════════════╝
         ↓
    ┌───────────────────────────────┐
    │ OUTPUT:                       │
    │ {                             │
    │   "action": "hold|tighten_sl" │
    │   "confidence": 0.78,         │
    │   "urgency": "low|medium|...  │
    │   "new_sl": 144.50 (optional) │
    │   "new_tp": null (optional)   │
    │   "reason": "thesis valid..." │
    │   "thesis_status": "valid"    │
    │ }                             │
    └───────────────────────────────┘
         ↓
╔═══════════════════════════════════════════════════════════════╗
║  SAFETY GATING (Non-Negotiable)                             ║
║  - SL can only TIGHTEN (move closer to price)               ║
║  - TP can only WIDEN (increase profit target)               ║
║  - Early close requires confidence >= 0.60                  ║
║  - Partial close requires remaining qty > min*2             ║
╚═══════════════════════════════════════════════════════════════╝
         ↓
    ┌─────────────────┐
    │ APPLY DECISION  │
    │ (if approved)   │
    │ - Modify SL/TP  │
    │ - Close portion │
    │ - Full close    │
    └─────────────────┘
         ↓
    ┌──────────────────────┐
    │ AUDIT LOG            │
    │ exit_decisions.jsonl │
    │ - Action taken       │
    │ - Old/new levels     │
    │ - P&L impact         │
    └──────────────────────┘
```

---

## 3. LEARNING PIPELINE (Post-Close)

```
╔════════════════════════════════════════════════════════════════════════════╗
║                    LEARNING PIPELINE (Post-Close, Async)                   ║
║                    Extracts lessons from closed trades                     ║
╚════════════════════════════════════════════════════════════════════════════╝

TRADE CLOSED
  {
    symbol: "SOL",
    side: "long",
    pnl: +48.91,
    entry_regime: "trend",
    setup_type: "trend_at_zone",
    hold_time: 150 (minutes),
    funding_paid: 2.45,
    thesis: "SOL trend continuation at zone",
    ...
  }
         ↓
┌─────────────────────────────────┐
│ DETERMINISTIC POST-TRADE LEARNER│
│ (Always runs, non-LLM)          │
│ - Pattern matching              │
│ - Win rate calculation          │
│ - Setup profitability tracking  │
└─────────────────────────────────┘
         ↓
╔═══════════════════════════════════════════════════════════════╗
║  LEARNING AGENT (Haiku, 2048 tokens, async timeout 15s)     ║
║  Role: Extract deeper insights, propose hypotheses          ║
╚═══════════════════════════════════════════════════════════════╝
         ↓
    ┌────────────────────────────┐
    │ LEARNING AGENT REASONING:  │
    │ 1. OBSERVE (trade outcome) │
    │ 2. DIAGNOSE (why won/lost?)│
    │ 3. PRESCRIBE (next time?)  │
    │ 4. GENERATE hypothesis?    │
    └────────────────────────────┘
         ↓
    ┌──────────────────────────────────────┐
    │ OUTPUT:                              │
    │ {                                    │
    │   "lesson": "trend_at_zone setup..." │
    │   "category": "setup_discovery",     │
    │   "strength": "medium",              │
    │   "applies_to": {                    │
    │     "symbol": "SOL,BTC,ETH",         │
    │     "regime": "trend",               │
    │     "side": "long"                   │
    │   },                                 │
    │   "hypothesis": "trend_at_zone + MC" │
    │   "thesis_correct": true             │
    │ }                                    │
    └──────────────────────────────────────┘
         ↓
    ┌──────────────────────────────────────┐
    │ PROCESS_AGENT_LESSON                 │
    │ Inject into multiple systems:        │
    └──────────────────────────────────────┘
         ↓
    ┌────────────────────────────────────────────────────────┐
    │ 1. POST-TRADE LEARNER (ring buffer, 100 most recent)  │
    │    - Recent lessons available to Trade Agent          │
    │    - 7-day TTL                                        │
    │    - Used for contextual memory in future decisions   │
    └────────────────────────────────────────────────────────┘
    ┌────────────────────────────────────────────────────────┐
    │ 2. DEEP MEMORY (persistent knowledge)                 │
    │    - Trade DNA: entry setup + thesis + outcome        │
    │    - Pattern library: recurring edge types            │
    │    - Insight journal: high-level observations         │
    │    - Searchable by symbol, regime, setup_type         │
    └────────────────────────────────────────────────────────┘
    ┌────────────────────────────────────────────────────────┐
    │ 3. HYPOTHESIS TRACKER (testable predictions)          │
    │    - New hypothesis: "trend_at_zone + MC is an edge"  │
    │    - Test on next 20 similar trades                   │
    │    - If 70%+ win rate → promote to rule               │
    │    - If <50% → mark as debunked                       │
    └────────────────────────────────────────────────────────┘
    ┌────────────────────────────────────────────────────────┐
    │ 4. KNOWLEDGE BASE (self-teaching curriculum)          │
    │    - Strong lessons → promote to axioms/rules         │
    │    - Available to Trade Agent as "self_teach" context │
    │    - Categories: regime_insight, setup_discovery,etc. │
    └────────────────────────────────────────────────────────┘
    ┌────────────────────────────────────────────────────────┐
    │ 5. CALIBRATION LEDGER (per-agent accuracy)            │
    │    - Record: setup_type, regime, outcome per agent    │
    │    - Helps Trade Agent calibrate confidence           │
    │    - Example: "In TREND regime, trend_at_zone = 72%"  │
    └────────────────────────────────────────────────────────┘
         ↓
    ┌──────────────────────────────────────┐
    │ FEEDBACK LOOP                        │
    │ On next similar trade:               │
    │ Trade Agent receives:                │
    │ - "Recent lesson: SOL trend_at_zone │
    │   +48 profit, same setup now"       │
    │ - "Hypothesis: trend_at_zone valid" │
    │ - "Self-teach: favor trend_at_zone" │
    │ - "Calibration: 72% accuracy"       │
    │                                      │
    │ → Confidence boost: 0.65 → 0.78     │
    └──────────────────────────────────────┘
```

---

## 4. AUTONOMY MODES: DECISION TREE

```
┌──────────────────────────────────────────────────────┐
│  LLM MODE (controls LLM influence on trading)       │
└──────────────────────────────────────────────────────┘
                      ↓
        ┌─────────────┬─────────────┬──────────────┐
        ↓             ↓             ↓              ↓
    MODE 0       MODE 1       MODE 2+        Roadmap Phase
    (OFF)      (ADVISORY)    (VETO_ONLY      Enforcement
                                +)           (clamping)
        ↓             ↓             ↓              ↓
    ┌───────┐   ┌──────────┐   ┌────────┐    ┌────────┐
    │ Skip  │   │ Call LLM │   │Call LLM│    │Enforce │
    │ LLM   │   │ Log it   │   │ USE it │    │max     │
    │ call  │   │ Ignore   │   │        │    │mode    │
    └───────┘   │ (quality │   └────────┘    └────────┘
       ↓        │ validation)       ↓
       │            ↓           ┌─────────────┬────────────┬──────────┐
       │        Track LLM       ↓             ↓            ↓          ↓
       │        divergence   Mode 2       Mode 3        Mode 4      Mode 5
       │        rate        VETO_ONLY     SIZING       DIRECTION     FULL
       │            ↓        (can         (scales       (direction   (drives
       │        Use to       reject)      size)         + size)      all)
       │        promote to               ↓             ↓             ↓
       │        VETO_ONLY   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
       │            ↓       │Direction:│ │Direction:│ │Direction:│ │Direction:│
       │        When LLM    │Ensemble  │ │Ensemble  │ │LLM       │ │LLM       │
       │        agrees 70%+ │Size: LLM │ │Size: LLM │ │Size: LLM │ │Size: LLM │
       │        for 20      │Flip: NO  │ │Flip: NO  │ │Flip: YES │ │Flip: YES │
       │        trades →    │Veto: YES │ │Veto: YES │ │Veto: YES │ │Veto: YES │
       │        promote     └──────────┘ └──────────┘ └──────────┘ └──────────┘
       │                           ↓             ↓            ↓          ↓
       │        ┌─────────────────────────────────────────────────────┐
       │        │        ALL MODES:                                   │
       │        │  Risk gating applies confidence floor (0.60)        │
       │        │  Risk gating applies flip gate (0.65)               │
       │        │  Bot's circuit breaker still active                 │
       │        │  Daily loss limit enforced                          │
       │        │  Leverage caps enforced                             │
       │        │  Max positions enforced                             │
       │        └─────────────────────────────────────────────────────┘
       │                            ↓
       │        ┌─────────────────────────────────────────────────────┐
       │        │  Decision sent to execution layer                   │
       │        │  - Position manager                                 │
       │        │  - Exchange API                                     │
       │        │  - Final circuit breaker check                      │
       │        │  - Trade executed or rejected                       │
       │        └─────────────────────────────────────────────────────┘
       │                            ↓
       └──────────────────────────────────────────────
                                  ↓
                    ┌─────────────────────────┐
                    │  AUDIT LOG              │
                    │ decisions.jsonl         │
                    │ - All LLM decisions     │
                    │ - All outcomes          │
                    │ - Veto analysis         │
                    │ - Mode used             │
                    └─────────────────────────┘
```

---

## 5. FAILURE RECOVERY AND FALLBACK

```
┌──────────────────────────────────────────────────────────┐
│  LLM CALL FAILS (timeout, API error, invalid JSON, etc) │
└──────────────────────────────────────────────────────────┘
                      ↓
        ┌─────────────────────────────────────────┐
        │ ERROR RECOVERY PIPELINE                 │
        │ (bot/llm/recovery.py)                   │
        └─────────────────────────────────────────┘
                      ↓
        ┌─────────────────────────────────────────┐
        │ 1. LOG ERROR                            │
        │    - Timestamp, error_type, stack_trace │
        │    - Update error_stats                 │
        │    - Track consecutive_errors           │
        └─────────────────────────────────────────┘
                      ↓
        ┌─────────────────────────────────────────┐
        │ 2. IS AGENT REQUIRED?                   │
        └─────────────────────────────────────────┘
                   ↙ YES          NO ↘
        ┌──────────────────┐  ┌──────────────────┐
        │ ABORT PIPELINE   │  │ DEGRADE          │
        │ Return None      │  │ GRACEFULLY       │
        │ → Fallback to    │  │ Continue         │
        │   ensemble       │  │ without it       │
        └──────────────────┘  └──────────────────┘
                  ↓               ↓
        ┌──────────────────────────────────────────┐
        │ 3. CHECK CONSECUTIVE ERRORS              │
        └──────────────────────────────────────────┘
                      ↓
              ┌───────────────────┐
              │ >= 3 consecutive? │
              └───────────────────┘
               YES ↓         NO ↓
        ┌────────────────┐  ┌──────────────────┐
        │ CIRCUIT BREAKER│  │ Continue trading │
        │ Disable LLM    │  │ normally         │
        │ for 30 min     │  └──────────────────┘
        │ Fallback to    │
        │ pure ensemble  │
        └────────────────┘
                ↓
        ┌──────────────────────────────────────────┐
        │ AUTONOMY ROUTER (mode-aware fallback)    │
        │ - Mode 0/1: Always use baseline          │
        │ - Mode 2+: Use baseline (skip LLM veto)  │
        └──────────────────────────────────────────┘
                      ↓
        ┌──────────────────────────────────────────┐
        │ BOT TRADES ON ENSEMBLE ONLY              │
        │ (no LLM influence for this cycle)        │
        │ LLM ERROR = ZERO IMPACT                  │
        └──────────────────────────────────────────┘
```

---

## 6. AGENT PIPELINE STATE MACHINE

```
   INPUT: Ensemble Signal
     ↓
  [REGIME]
     ↓
  regime_output (required)
     ├─ SUCCESS → Write scratchpad, continue
     ├─ FAIL → Fallback: unknown regime
     │         Continue if fallback ok
     │         Abort if fallback invalid
     └─ ABORT → Return None, use baseline
     ↓
  [QUANT] (optional)
     ↓
  quant_output (optional)
     ├─ SUCCESS → Write scratchpad
     └─ FAIL → Skip, continue
     ↓
  [TRADE]
     ↓
  trade_output (required)
     ├─ SUCCESS → Write scratchpad, continue
     ├─ FAIL → Fallback: skip (a=flat, c=0.0)
     │         Continue if fallback ok
     │         Abort if fallback invalid
     └─ ABORT → Return None, use baseline
     ↓
  [RISK] (optional)
     ↓
  risk_output (optional)
     ├─ SUCCESS → Consume
     └─ FAIL → Skip, continue
     ↓
  [CONSISTENCY CHECK]
     ↓
  consistency_report
     ├─ CONSISTENT → Continue
     └─ CRITICAL ISSUE → Override trade to skip
     ↓
  [QUANT ADJUSTMENT]
     ↓
  adjusted_trade_output (if quant failed)
     ├─ ADJUSTED → Apply confidence adjustment
     └─ UNCHANGED → Continue
     ↓
  [CRITIC] (optional)
     ↓
  critic_output (optional)
     ├─ APPROVED → Continue
     ├─ CHALLENGED → Apply critic adjustments
     └─ FAIL → Skip, continue
     ↓
  [OUTPUT MERGER]
     ↓
  LLMDecision
     ├─ VALID → Return merged
     └─ INVALID → Return None
     ↓
  [RISK GATING]
     ↓
  GatedResult
     ├─ ALLOWED → Return decision
     └─ REJECTED → Return reason
     ↓
  [AUTONOMY ROUTER]
     ↓
  Final decision (mode-aware)
     ├─ Mode 0: Baseline
     ├─ Mode 1: Baseline (logged)
     ├─ Mode 2: Veto applied
     ├─ Mode 3: Size scaled
     ├─ Mode 4: Direction from LLM
     └─ Mode 5: Full LLM control
     ↓
  [AUDIT LOG]
  [BOT EXECUTION]
```

