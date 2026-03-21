# Post-Paper-Trading Transition Plan

## Context
The WAGMI trading bot is currently paper trading, collecting data and improving the UI. After a couple days of paper trading, we need a structured 3-7 day transition plan to go live with $100-500 test capital on Hyperliquid. The focus areas are: **Agent/LLM accuracy tuning**, **data migration & memory seeding**, and **strategy weight & ensemble optimization**. This plan ensures we extract maximum value from paper trading data before risking real capital.

## Important Realities
- **Go-live gates expect 30 days of data** (Gate 2 = net PnL over 30d, Gate 5 = 30d Sharpe). With only a few days of paper trading, some gates will return `INSUFFICIENT DATA`. This is expected — we'll use the gates as aspirational targets while relying on manual analysis for the go-live decision.
- **LIVE_PROFILE_OVERRIDES in `trading_config.py` are currently identical to paper** (25x leverage, 0.5% risk, 8 positions). We need to update these for conservative live trading, OR override via `.env` vars (which take priority).
- **VETO_ONLY mode is not pure veto** — it also applies confidence-based size scaling (0.6x for weak LLM approval <55% confidence). This is actually good for live — a soft graduated approach.
- **There is no `MAX_SAME_DIRECTION` parameter** in trading_config.py. Correlation is managed via `enable_correlation_check` + `correlation_rejection_threshold` (default 0.8).
- **The existing PHASE_3_DEPLOYMENT_GUIDE.md** describes a 72-96h phased rollout. This plan supersedes it with more granular focus on LLM/agent tuning and data migration, but we should follow its server requirements for production (dedicated server, 1GB RAM, 10GB disk, 24/7 uptime).

---

## Day 1: Data Extraction & Diagnostic Analysis

### 1.1 Run All Existing Diagnostic Skills
Use the built-in skills to generate baseline reports — no new code needed.

```bash
cd bot
# Core diagnostics
/paper-status gates          # Go-live gate progress
/evolution 30d               # Strategy evolution over paper period
/growth-report deep          # Unified learning intelligence
/confidence-calibrate system # Calibration drift analysis
/veto-review 30d             # Critic Agent veto accuracy
/thesis-track deep           # Prediction accuracy by regime/symbol/setup
/edge-finder full            # Where money is made/lost
/loss-autopsy patterns       # Loss pattern forensics
```

**Decision criteria**: Document each report's findings. Flag any agent with <50% accuracy, any strategy with negative edge, any regime with 0 trades.

### 1.2 Build a Paper Trading Analysis Script
**New file**: `bot/scripts/paper_analysis.py`

This script consolidates paper trading data into a single actionable report:

1. **Trade statistics** — Read `bot/data/trades.csv` + `bot/data/trade_ledger.csv`:
   - Total trades, win rate, profit factor, Sharpe, max drawdown
   - Per-symbol breakdown (BTC, ETH, SOL, HYPE, etc.)
   - Per-regime breakdown (trend, range, panic, high_vol)
   - Per-strategy breakdown (which of the 11 strategies contributed)

2. **Agent accuracy audit** — Read `bot/data/llm/decisions.jsonl`:
   - Regime Agent: Did regime classification match actual price action?
   - Trade Agent: Did go/skip decisions correlate with profitable outcomes?
   - Critic Agent: Veto accuracy (saved PnL vs. missed PnL from vetoed trades)
   - Exit Agent: Did exit recommendations improve vs. mechanical trailing stops?
   - Confidence calibration: Plot predicted confidence vs. actual win rate

3. **Counterfactual analysis** — Read counterfactual log:
   - How many skipped trades would have been winners?
   - Which gate rejects the most profitable signals? (too conservative?)
   - Net counterfactual PnL (are we leaving money on the table?)

4. **Ensemble performance** — From `bot/data/strategy_weights.py` + trade data:
   - MIN_VOTES impact: Compare 2-agree vs. 3-agree signal quality
   - VETO_RATIO impact: Would different ratios improve/degrade?
   - Strategy correlation: Which strategies agree/disagree most?

**Key files to read**:
- `bot/data/trades.csv` — Trade outcomes
- `bot/data/trade_ledger.csv` — Attribution ledger (regime, factors, Kelly)
- `bot/data/llm/decisions.jsonl` — All LLM decisions (append-only)
- `bot/llm/thesis_tracker.py` — Has `get_accuracy_report()` method
- `bot/llm/confidence_calibrator.py` — Has calibration curve data
- `bot/llm/counterfactual_learner.py` — Tracked skipped trades
- `bot/feedback/evolution_tracker.py` — Has `generate_report()` method
- `bot/data/strategy_weights.py` — Rolling strategy weights

### 1.3 Run Go-Live Gates
```bash
cd bot && python cli.py --mode gate
```
**File**: `bot/validation/go_live_gate.py` — Evaluates 5 gates:
1. Walk-forward ratio > 0.7
2. Net PnL > $0 (30d, min 5 trades)
3. Max drawdown < 15%
4. All factor ICs > 0 (30d)
5. Sharpe ratio > 1.0

**Action**: Record which gates pass/fail. Failing gates determine Day 2-3 priorities.

**If gates return INSUFFICIENT DATA** (likely with <30 days paper):
- This is expected. The gates need 30d of trade data + 5 minimum trades.
- Use the manual analysis from §1.2 as the primary go/no-go decision.
- Re-run gates weekly once live to track progress toward full validation.

**Gate Failure Remediation**:
| Gate | If Failing | Remediation |
|------|-----------|-------------|
| Walk-forward < 0.7 | Overfitting detected | Reduce strategy complexity, raise MIN_VOTES to 3 |
| Net PnL < $0 | Losing money | Analyze per-strategy PnL — disable losers, don't go live |
| Max DD > 15% | Risk too high | Tighten circuit breakers, reduce leverage, reduce positions |
| Factor ICs < 0 | Signals not predictive | Review signal pipeline, check for stale data issues |
| Sharpe < 1.0 | Risk-adjusted returns poor | Improve win rate OR reduce loss size via tighter stops |

---

## Day 2-3: Tuning & Optimization

### 2.1 Agent Prompt Refinements
Based on Day 1 analysis, tune agent prompts in `bot/llm/agents/prompts.py`:

| Agent | What to Check | Potential Tuning |
|-------|--------------|-----------------|
| **Regime** | Classification accuracy vs. actual regime | Adjust regime boundary definitions, add examples from paper data |
| **Trade** | Go/skip decision accuracy per regime | Add regime-specific decision heuristics learned from paper |
| **Critic** | Veto rate & accuracy (saved PnL / missed PnL) | If over-vetoing (>30% rate, <50% accuracy): soften counter-thesis requirement. If under-vetoing: strengthen |
| **Exit** | Exit timing vs. mechanical trailing stops | If exits underperform mechanical stops: reduce Exit Agent influence |
| **Scout** | Watchlist quality (did scouted setups materialize?) | Prune low-hit-rate watchlist criteria |

**Rules** (from `.claude/rules/llm-agents.md`):
- All agents must use identical vocabulary (regime names, action names, confidence scales)
- Test after prompt changes: `cd bot && pytest tests/ -k "agent or multi_agent"`
- Keep prompts under max_tokens budget per agent

### 2.2 Confidence Calibration Update
**File**: `bot/llm/confidence_calibrator.py`

Using paper trading data:
1. Build calibration curve: predicted confidence buckets (50-60, 60-70, 70-80, 80-90, 90-100) vs actual win rates
2. If 80% confidence trades only win 55% of the time → apply deflation factor
3. Update per-agent calibration in the calibrator's state
4. Use `/confidence-calibrate system` to verify

### 2.3 Strategy Weight Finalization
**File**: `bot/data/strategy_weights.py`

From paper trading performance data:
1. Calculate per-strategy win rate, profit factor, and Sharpe **by regime**
2. Lock final weights:
   - Strategies with PF > 1.5 in their target regime → weight 1.2-1.5x
   - Strategies with PF 1.0-1.5 → weight 1.0x (neutral)
   - Strategies with PF < 1.0 → weight 0.5x or disable
3. Apply via `bot/trading_config.py` strategy weight overrides

**Critical strategies to evaluate**:
- `regime_trend` — Expected strong in trend regimes
- `confidence_scorer` — Core strategy, should work across regimes
- `oi_delta`, `funding_rate` — Newer strategies, may need weight reduction
- `liquidation_cascade` — High-impact but rare signals
- `lead_lag` — Currently disabled ($-1,100 PnL track record), keep disabled unless paper data reverses this
- `multi_tier_quality` — Currently disabled (toxic combo with confidence_scorer)

### 2.4 Ensemble Parameter Finalization
**File**: `bot/trading_config.py`

Decisions to make based on paper data:
- **MIN_VOTES**: If 2-agree signals have PF > 1.5, keep at 2. If not, raise to 3.
- **VETO_RATIO**: If current 1.2 produces good signal quality, keep. Adjust ±0.1 based on data.
- **Confidence floors**: Replace adaptive floors with data-driven per-regime floors:
  ```python
  # Example (values from paper data analysis)
  CONFIDENCE_FLOORS = {
      "trend": 65,      # Lower bar in trending (high-probability)
      "range": 80,      # Higher bar in ranging (more false signals)
      "panic": 85,      # Very high bar in panic
      "high_volatility": 75,
      "unknown": 70,
  }
  ```

### 2.5 Hypothesis Graduation
**File**: `bot/llm/growth/hypothesis_tracker.py`

Use `/knowledge-distill hypotheses` to:
1. List all hypotheses with >70% supporting evidence
2. Graduate validated hypotheses to codified rules in knowledge base
3. Example: "SOL breakouts fail in high_vol regime" → add as anti-pattern to Trade Agent prompt
4. Prune disproven hypotheses (<30% evidence)

### 2.6 Autonomy Level Decision
**File**: `bot/llm/autonomy_router.py`

Based on paper trading LLM performance:
- If LLM vetoes saved net positive PnL → promote from ADVISORY(1) to VETO_ONLY(2)
- If LLM sizing suggestions outperformed fixed sizing → promote to SIZING(3)
- **For initial live**: Start at VETO_ONLY(2) — safest with real money

**What VETO_ONLY actually does** (from `autonomy_router.py:_mode_veto_only()`):
- LLM says "flat" → trade rejected (full veto)
- LLM says "flip" → downgraded to flat (flip not allowed in VETO_ONLY)
- LLM says "proceed" with confidence ≥ 0.55 → full baseline size
- LLM says "proceed" with confidence < 0.55 → 0.6x size (weak approval scaling)
- LLM fails/missing → use baseline unchanged (graceful degradation)

This means VETO_ONLY is already a graduated system, not just binary pass/fail. The weak-approval sizing is effectively a lightweight SIZING mode. This is ideal for initial live.

**Divergence tracking** (ADVISORY mode data):
- `autonomy_router.py` tracks a 50-entry deque of LLM agree/disagree with baseline
- `get_divergence_rate()` returns what % of the time LLM disagrees
- If divergence rate > 30% AND LLM-preferred outcomes were better → validates promotion
- Re-evaluate after 1 week of live data

### 2.7 Alert System Verification
Before go-live, verify Telegram/Discord are configured and working:
```bash
# Check .env has these set:
# TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ALLOWED_USER_ID
# DISCORD_WEBHOOK (optional)

# Test Telegram bot responds to /status command
# Test alert routing: priority signals go to both Discord + Telegram
```
**File**: `bot/alerts/router.py` — smart routing with rate limiting and dedup
- Priority signals (conf ≥ 75%): Discord priority webhook + Telegram
- Regular signals (conf ≥ 65%): Discord all channel + Telegram
- Rate limits: max 5 priority alerts per symbol per 10 min

This is critical for live — you need to know immediately if something goes wrong.

---

## Day 3-4: Data Migration & Memory Seeding

### 3.1 Memory Preservation
Back up all paper trading intelligence:

```bash
# Create paper trading snapshot
mkdir -p bot/data/paper_snapshots/$(date +%Y%m%d)
cp -r bot/data/llm/ bot/data/paper_snapshots/$(date +%Y%m%d)/
cp bot/data/trades.csv bot/data/paper_snapshots/$(date +%Y%m%d)/
cp bot/data/trade_ledger.csv bot/data/paper_snapshots/$(date +%Y%m%d)/
cp -r bot/data/feedback/ bot/data/paper_snapshots/$(date +%Y%m%d)/
```

### 3.2 Deep Memory Curation
**File**: `bot/llm/deep_memory.py`

1. **Keep**: Trade DNA entries with clear lessons (win patterns, loss patterns)
2. **Prune**: Low-confidence entries, duplicates, entries from first few days (learning noise)
3. **Summarize**: Compress 500 individual trade entries into pattern summaries:
   - "BTC trend entries with 3+ strategy agreement: 72% WR, avg +1.2% PnL"
   - "SOL range entries: 38% WR, avoid unless confidence >85%"
4. Use `/memory-optimize prune` to clean up

### 3.3 Short-Term Memory Reset
**File**: `bot/llm/memory_store.py`

- Keep the most valuable recent notes (top-10 by relevance)
- Clear noise/stale notes
- Add "transition note": summary of paper trading learnings to seed live context

### 3.4 Knowledge Base Update
**File**: `bot/data/llm/teaching/knowledge_base.json`

Inject validated paper trading insights:
- Per-symbol behavioral patterns
- Per-regime strategy preferences
- Key anti-patterns (what to avoid)
- Calibration adjustments

### 3.5 Curriculum State Check
**File**: `bot/llm/self_teaching.py`

- Check current curriculum level (likely Level 1 or 2 after paper)
- If Level 1 complete (100+ trades analyzed, 50%+ hypothesis accuracy): advance to Level 2
- Use `/curriculum-advance evaluate` to assess

---

## Day 4-5: Configuration, Validation & Go-Live

### 4.1 Trading Config Changes for Live
**File**: `bot/trading_config.py`

Two approaches for config changes — choose one:

**Option A: Update LIVE_PROFILE_OVERRIDES** (recommended — keeps `.env` clean):
Update the `LIVE_PROFILE_OVERRIDES` dict in `trading_config.py` (line ~634):
```python
LIVE_PROFILE_OVERRIDES = {
    "max_leverage": 5.0,            # Was 25.0 — conservative start
    "risk_per_trade": 0.01,         # Was 0.005 — 1% risk ($3 per trade on $300)
    "max_open_positions": 2,        # Was 8 — start narrow
    "max_portfolio_leverage": 2.0,  # Was 4.0 — tighter notional cap
    "enable_smart_orders": True,    # Real limit orders for live
}
```

**Option B: Override via .env** (env vars take priority over profile overrides):
```bash
RISK_PER_TRADE=0.01
MAX_LEVERAGE=5.0
MAX_OPEN_POSITIONS=2
MAX_PORTFOLIO_LEVERAGE=2.0
```

**All config changes (both options need these in .env):**
```bash
# Environment
ENVIRONMENT=production

# Capital
STARTING_EQUITY=300                  # $300 test capital

# Circuit Breakers (tighter for live)
CIRCUIT_BREAKER_DAILY_LOSS_PCT=0.03  # 3% daily (was 5% paper)
MAX_CONSECUTIVE_LOSSES=3             # 3 losses (was 5 paper)
MAX_DRAWDOWN_PCT=0.10               # 10% (was 15% paper)

# Ensemble (validated from paper)
MIN_VOTES_REQUIRED=<from Day 2 analysis>
VETO_RATIO=<from Day 2 analysis>

# LLM
LLM_MODE=2                          # VETO_ONLY
LLM_MULTI_AGENT=true

# Correlation guard (replaces the non-existent MAX_SAME_DIRECTION)
ENABLE_CORRELATION_CHECK=true
CORRELATION_REJECTION_THRESHOLD=0.8  # Reject new position if >0.8 correlated with existing

# Hyperliquid credentials (NEVER commit)
HL_API_KEY=<wallet-address>
HL_API_SECRET=<private-key>

# Alerts (critical for live monitoring)
TELEGRAM_TOKEN=<bot-token>
TELEGRAM_CHAT_ID=<chat-id>
TELEGRAM_ALLOWED_USER_ID=<numeric-user-id>
```

**Regime risk multipliers** — review `REGIME_RISK_MULTIPLIERS` dict (line ~599) against paper data. Currently:
- `trending_bull/bear`: 0.7x (conservative — unproven edge)
- `consolidation`: 1.0x
- `panic`: 0.3x (very conservative)
- These are already conservative and likely fine for initial live

### 4.2 Reconciliation & Exchange Connectivity Test
Before first live trade, verify exchange integration:
1. **API key permissions**: Ensure Hyperliquid API key has trade permissions but NOT withdrawal
2. **Connectivity test**: Fetch account balance, open orders, positions via CCXT
3. **Reconciliation on startup**: `bot/execution/reconciliation.py` automatically reconciles in-memory positions with exchange state — verify this runs cleanly with zero positions
4. **Order placement test**: Place and immediately cancel a tiny limit order to verify order flow works

### 4.3 Pre-Flight Validation
Run the existing deployment checklist:
```bash
/deploy-paper  # Reuse this skill's validation stages but for live
cd bot && pytest tests/ -x  # All tests must pass
python cli.py --mode gate   # All 5 go-live gates must pass
```

### 4.4 Dry-Run (First 24h)
1. Start with `python run.py live` (requires "CONFIRM LIVE" prompt)
2. Monitor via:
   - `/paper-status quick` (works for live too)
   - `/health-check deep`
   - Telegram alerts (ensure configured)
   - Dashboard: `python -m bot.dashboard.server`
3. Watch for:
   - First trade execution (fills matching expectations?)
   - Slippage vs. paper fills
   - API rate limits / connection issues
   - Circuit breaker behavior with real PnL

### 4.5 First 48h Monitoring Checklist
| Check | Frequency | What to Look For |
|-------|-----------|-----------------|
| Position state | Every 2h | Positions match exchange state (reconciliation) |
| PnL accuracy | Every trade | Declared PnL matches exchange PnL |
| Slippage | Every trade | Entry/exit vs. expected price |
| Memory growth | Every 6h | <2 MB/hour, no runaway growth |
| Error logs | Every 4h | Zero ERROR entries |
| Circuit breakers | Every 4h | No false trips |
| LLM costs | Daily | Within tier budget |

---

## Day 5+: Scale-Up Plan (Post-Validation)

### Phase 1 (Week 1): 2 symbols, $300, 1% risk
- SOL + HYPE only (most volatile, best paper data)
- Validate: fills match expected prices, PnL matches exchange PnL
- Compare: live slippage vs. paper's `SLIPPAGE_BPS=3` assumption
- Track: actual fees vs. `TAKER_FEE_BPS=4` (HL charges 3.5 bps)
- **Promotion criteria**: 5+ trades, no position mismatches, slippage < 5 bps avg

### Phase 2 (Week 2): 3 symbols, $300-500, 1% risk
- **If Week 1 passes**: Add BTC (low risk tier, wider stops via `BTC_ATR_MULTIPLIER=1.75`)
- Keep same risk params — only add symbol diversity
- **Promotion criteria**: 10+ total trades, win rate within 10% of paper rate, no CB trips

### Phase 3 (Week 3): Full config, scale capital
- **If Week 2 passes**: Increase to paper-equivalent settings:
  - `RISK_PER_TRADE=0.005` (match paper's 0.5%)
  - `MAX_OPEN_POSITIONS=4-8`
  - `MAX_LEVERAGE=10-25` (match paper)
- Consider promoting LLM from VETO_ONLY(2) to SIZING(3) if veto accuracy > 60%
- Scale capital to $500+

### Phase 4 (Week 4+): Autonomy promotion
- If profitable through Week 3, evaluate SIZING(3) promotion
- Run `/agent-replay compare` to simulate SIZING vs VETO_ONLY on live data
- Consider DIRECTION(4) only after 30+ trades at SIZING show positive edge

### Rollback Triggers (Immediate Stop → Kill Switch)
| Trigger | Action | Recovery |
|---------|--------|----------|
| Drawdown > 10% | Kill switch (`data/.kill_switch`) | Review all trades, diagnose, re-paper |
| 3+ consecutive losses | Pause 60 min (circuit breaker handles this) | Automatic resume after cooldown |
| Slippage consistently > 10 bps | Reduce to limit orders only | Set `ENABLE_SMART_ORDERS=true` |
| API errors > 3/hour | Kill switch | Check API key, network, exchange status |
| Position state mismatch | Kill switch immediately | Manual reconciliation on exchange |
| LLM costs > $5/day at RECOMMENDED tier | Downgrade to CONSERVATIVE | Reduce agent call frequency |

**Kill switch**: `touch bot/data/.kill_switch` — file-persisted, survives restarts, handled by OpsGuard

---

## Files to Modify (Summary)

| File | Day | Changes |
|------|-----|---------|
| **NEW**: `bot/scripts/paper_analysis.py` | 1 | Paper trading analysis consolidation script |
| `bot/llm/agents/prompts.py` | 2 | Agent prompt tuning based on accuracy data |
| `bot/llm/confidence_calibrator.py` | 2 | Updated calibration curves from paper data |
| `bot/data/strategy_weights.py` | 2 | Lock strategy weights from paper performance |
| `bot/data/llm/deep_memory/` | 3 | Curated memory (pruned + summarized) |
| `bot/data/llm/llm_memory.json` | 3 | Reset with transition summary note |
| `bot/data/llm/teaching/knowledge_base.json` | 3 | Graduated hypotheses → codified rules |
| `bot/trading_config.py` (LIVE_PROFILE_OVERRIDES) | 4 | Conservative live profile: 5x lev, 1% risk, 2 positions |
| `.env` | 4 | ENVIRONMENT=production, HL credentials, circuit breakers, LLM_MODE=2, alerts |

**Files NOT to modify** (already correct for live):
- `bot/execution/risk.py` — Circuit breakers are env-driven, no code changes needed
- `bot/execution/ops_guard.py` — Kill switch + rate limits already production-ready
- `bot/core/signal_pipeline.py` — 6-gate filter chain is environment-agnostic
- `bot/execution/reconciliation.py` — Already reconciles on startup

## Existing Tools to Leverage (No New Code Needed)

| Tool | Purpose |
|------|---------|
| `python cli.py --mode gate` | Go-live gate evaluation |
| `/paper-status gates` | Gate progress during paper |
| `/evolution 30d` | Strategy performance over paper period |
| `/confidence-calibrate system` | Agent calibration audit |
| `/veto-review 30d` | Critic accuracy analysis |
| `/knowledge-distill hypotheses` | Graduate validated hypotheses |
| `/memory-optimize prune` | Clean up memory stores |
| `/growth-report deep` | Unified learning report |
| `/edge-finder full` | Edge attribution |
| `/loss-autopsy patterns` | Loss pattern analysis |
| `/curriculum-advance evaluate` | Self-teaching level check |
| `/thesis-track deep` | Prediction accuracy |
| `/deploy-paper` | Pre-flight validation (10 stages) |

## Verification Plan
1. **Before tuning**: Run full test suite (`pytest tests/`) — must pass
2. **After each prompt change**: Run agent tests (`pytest tests/ -k "agent"`)
3. **After config changes**: Run safety tests (`pytest tests/ -k "safety"`)
4. **Before go-live**: Run all go-live gates (`python cli.py --mode gate`)
5. **After go-live**: Monitor via `/health-check deep` + Telegram alerts for 48h
