# Signal Flow Redesign: LLM-First Architecture

## Problem Statement

The current signal flow in `_process_symbol()` (multi_strategy_main.py, lines 2420-5600) runs **47 mechanical gates** before the LLM ever sees a signal at line 5242. The LLM at Level 5 "FULL" mode can only rubber-stamp what the mechanical system already approved, making ~7000 lines of LLM code functionally equivalent to Level 2 "VETO_ONLY."

**Current flow (simplified):**
```
Ensemble (line 3726)
  -> 18 quality gates in ensemble.py (confidence floor, chop, trend flip, quality scorer)
  -> Signal dedup (line 4086)
  -> Anti-round-trip filter (line 4185)
  -> Signal flagger (line 4197)
  -> ML confidence adjustment (line 4274)
  -> Feedback loop floor (line 4320)
  -> Circuit breaker (line 4392)
  -> HTF trend gate (line 4460)
  -> RiskFilterChain (line 4498) — 15+ gates inside
  -> Feedback leverage cap (line 4598)
  -> Funding rate entry filter (line 4704)
  -> Min profit threshold (line 4728)
  -> Vol-target sizing (line 4754)
  -> Correlation guard x2 (line 4800, 4812)
  -> Sector exposure (line 4834)
  -> Global brain sizing (line 4860)
  -> Portfolio risk (line 4872)
  -> Time-of-day sizing (line 4892)
  -> Liquidity guard (line 4910)
  -> Reflection engine (line 4919)
  -> Qty floor + min notional (line 4949)
  -> Trade classification (line 4975)
  -> Slippage check (line 5159)
  -> LLM VETO CHECK (line 5242) <-- TOO LATE
  -> Execution
```

**Result:** 91% of signals are killed before the LLM sees them. The LLM's intelligence is wasted.

---

## New Architecture

### Tier 1: SAFETY GATES (before LLM, never bypassed)

These protect against catastrophic loss and exchange rejection. They stay upstream.

| # | Gate | Location | Why it stays |
|---|------|----------|-------------|
| 1 | Signal.is_valid | signal_pipeline.py:262 | Structurally broken signal (SL on wrong side, zero stop width) |
| 2 | Circuit breaker | signal_pipeline.py:377 | Daily loss limit, consecutive losses — protect capital |
| 3 | Max open positions | signal_pipeline.py:390 | Hard portfolio limit — exchange margin requirement |
| 4 | Duplicate position guard | signal_pipeline.py:401 | Prevents 9-BTC-SHORT-in-one-day bug |
| 5 | Notional cap (15x equity) | multi_strategy_main.py:5520 | Hard leverage ceiling — exchange liquidation protection |
| 6 | Portfolio notional cap | multi_strategy_main.py:5536 | Aggregate over-leverage prevention |
| 7 | Liquidation safety | signal_pipeline.py:743 | SL beyond liquidation price |
| 8 | OpsGuard | multi_strategy_main.py:5546 | Rate limiting, exposure limits |
| 9 | Min qty / min notional | multi_strategy_main.py:4969, 5489 | Exchange minimum order requirements |
| 10 | Degradation halt | multi_strategy_main.py:2423 | Exchange is down |

### Tier 2: LLM AGENT PIPELINE (the brain)

After safety gates pass, the signal goes directly to the LLM multi-agent pipeline. The LLM replaces ALL quality/sizing gates.

**LLM receives:** Raw signal + full market data + open positions + equity
**LLM returns:** go/skip + leverage + position_qty + regime + thesis + risk_mult

### Tier 3: EXECUTION (post-LLM)

Only hard exchange mechanics:
- Live price refresh + slippage check
- Order placement
- Position manager opens
- Feedback systems record

### Gates REMOVED from pre-LLM path (LLM replaces these)

| # | Gate | Current Location | Why LLM replaces it |
|---|------|-----------------|---------------------|
| 1 | Confidence floor (69%) | ensemble.py:558-636 | LLM Trade Agent decides if confidence is sufficient for thesis |
| 2 | Chop detector graduated floor | ensemble.py:563-584 | LLM Regime Agent classifies market conditions |
| 3 | R:R floor (min_signal_rr) | signal_pipeline.py:270 | LLM Risk Agent evaluates risk/reward in context |
| 4 | Fee-drag filter | signal_pipeline.py:281-313 | LLM Risk Agent factors costs into sizing |
| 5 | EV floor | signal_pipeline.py:316-331 | LLM Quant Agent computes EV with full context |
| 6 | Slippage impact filter | signal_pipeline.py:336-357 | LLM Risk Agent factors slippage into sizing |
| 7 | Win probability floor | signal_pipeline.py:360-374 | LLM Quant Agent uses win probability as input, not hard gate |
| 8 | Leverage gate (min 1.0x) | signal_pipeline.py:504-520 | LLM Risk Agent decides leverage |
| 9 | Graduated leverage scalar | signal_pipeline.py:522-534 | LLM Risk Agent handles sizing |
| 10 | Stop-width leverage cap | signal_pipeline.py:547-558 | LLM Risk Agent considers stop width |
| 11 | Correlation size reduction | signal_pipeline.py:560-564 | LLM Risk Agent sees portfolio context |
| 12 | Regime risk multiplier | signal_pipeline.py:566-592 | LLM Regime Agent classifies regime |
| 13 | Symbol risk multiplier | signal_pipeline.py:594-603 | LLM has per-symbol memory |
| 14 | Symbol+side risk multiplier | signal_pipeline.py:605-618 | LLM knows directional edge per symbol |
| 15 | Adaptive sizing (anti-martingale) | signal_pipeline.py:620-639 | LLM Risk Agent streak awareness |
| 16 | Solo strategy risk override | signal_pipeline.py:641-644 | LLM decides solo vs consensus weight |
| 17 | Confidence calibration | signal_pipeline.py:647-673 | LLM already calibrated via learning |
| 18 | Time-of-day sizing | signal_pipeline.py:675-690 | LLM sees time context, decides sizing |
| 19 | Confidence-based sizing bands | signal_pipeline.py:692-720 | LLM Risk Agent handles sizing |
| 20 | Quant conviction multiplier | signal_pipeline.py:722-726 | LLM Quant Agent handles this |
| 21 | Risk mult floor (0.50) | signal_pipeline.py:731 | LLM sets its own floor |
| 22 | Signal dedup | multi_strategy_main.py:4086 | LLM can decide re-entry |
| 23 | Anti-round-trip filter | multi_strategy_main.py:4185 | LLM has trade history context |
| 24 | ML confidence adjustment | multi_strategy_main.py:4274 | LLM replaces ML learner |
| 25 | Feedback loop floor | multi_strategy_main.py:4320 | LLM replaces feedback floor |
| 26 | HTF trend gate (0.4x) | multi_strategy_main.py:4460 | LLM sees HTF data directly |
| 27 | All RiskFilterChain quality gates | signal_pipeline.py (various) | LLM replaces quality + sizing |
| 28 | Feedback leverage cap | multi_strategy_main.py:4598 | LLM sets own leverage |
| 29 | Self-tuning leverage cap | multi_strategy_main.py:4618 | LLM is the tuner |
| 30 | R:R gate for high leverage | multi_strategy_main.py:4636 | LLM Risk Agent handles this |
| 31 | Signal decay | multi_strategy_main.py:4667 | LLM sees signal age |
| 32 | Liquidity guard | multi_strategy_main.py:4679 | LLM sees volume data |
| 33 | Funding rate entry filter | multi_strategy_main.py:4704 | LLM sees funding rates |
| 34 | Min profit threshold | multi_strategy_main.py:4728 | LLM computes profitability |
| 35 | Vol-target sizing | multi_strategy_main.py:4754 | LLM Risk Agent handles this |
| 36 | Correlation guard (compute) | multi_strategy_main.py:4800 | LLM sees portfolio |
| 37 | CorrelationGate (cluster) | multi_strategy_main.py:4812 | LLM sees correlations |
| 38 | Sector exposure | multi_strategy_main.py:4834 | LLM sees sector data |
| 39 | Global brain sizing | multi_strategy_main.py:4860 | LLM IS the global brain |
| 40 | Portfolio risk limit | multi_strategy_main.py:4872 | LLM Risk Agent handles this |
| 41 | Time-of-day sizing (main) | multi_strategy_main.py:4892 | LLM sees time context |
| 42 | Reflection engine | multi_strategy_main.py:4919 | LLM has memory of entries |
| 43 | Qty floor (50%) | multi_strategy_main.py:4949 | LLM sets final qty |
| 44 | Adaptive risk multiplier | multi_strategy_main.py:5424 | LLM Risk Agent handles this |
| 45 | RL policy multiplier | multi_strategy_main.py:5441 | LLM replaces RL |
| 46 | Profitable pattern boost | multi_strategy_main.py:5454 | LLM has deep memory |
| 47 | Regime-specific confidence floor | multi_strategy_main.py:3941 | LLM Regime Agent handles this |

---

## Files That Change

### 1. `bot/core/signal_pipeline.py` — MAJOR REFACTOR

**Create new class: `SafetyFilterChain`** (extract from `RiskFilterChain`)

Contains ONLY safety gates:
- Gate 1: `signal.is_valid` (structural validity)
- Gate 2: Circuit breaker
- Gate 3: Max open positions
- Gate 4: Duplicate position guard
- Gate 6: Liquidation safety (keep — it's about exchange liquidation)
- Gate 6b: Position sizing > 0 (keep — exchange rejection prevention)

**Keep `RiskFilterChain`** as a legacy wrapper for backtest mode (no LLM available).

```python
class SafetyFilterChain:
    """Safety-only gates that run BEFORE the LLM pipeline.

    These protect against catastrophic loss and exchange rejection.
    Quality/sizing decisions are delegated to the LLM.
    """

    def evaluate(self, signal, equity, current_open_count, open_positions) -> FilterResult:
        # Gate 1: Signal structural validity (is_valid)
        if not signal.is_valid:
            return FilterResult(approved=False, ...)

        # Gate 2: Circuit breaker (daily loss, consecutive losses)
        if not self.risk_mgr.is_trading_allowed(confidence=signal.confidence):
            return FilterResult(approved=False, ...)

        # Gate 3: Max open positions
        if current_open_count >= self.config.max_open_positions:
            return FilterResult(approved=False, ...)

        # Gate 4: Duplicate position guard
        if open_positions and signal.symbol in open_positions:
            return FilterResult(approved=False, ...)

        # Gate 5: Liquidation safety (needs leverage estimate — use max_leverage as ceiling)
        liq_check = self.leverage_mgr.validate_stop_vs_liquidation(
            entry=signal.entry, stop_loss=signal.sl, side=signal.side,
            leverage=self.config.max_leverage,  # worst-case check
            notional_usd=equity * self.config.max_leverage * 0.5,
        )
        if not liq_check["safe"]:
            return FilterResult(approved=False, ...)

        # PASS: signal is structurally safe, LLM decides quality + sizing
        return FilterResult(approved=True, signal=signal, metadata={...})
```

### 2. `bot/multi_strategy_main.py` — MAJOR REFACTOR of `_process_symbol()`

**New flow (pseudocode):**

```python
def _process_symbol(self, symbol, sym_cfg, trace_id):
    # ── Phase 1: Data fetch (unchanged) ──
    data = self.fetcher.fetch_multi_timeframe(symbol, ...)

    # ── Phase 2: Ensemble signal generation (unchanged) ──
    signal_result = self.ensemble.evaluate(symbol, data)
    if signal_result is None:
        return

    # ── Phase 3: SAFETY GATES ONLY ──
    from core.signal_pipeline import SafetyFilterChain
    safety = SafetyFilterChain(self.risk_mgr, self.leverage_mgr, self.config)
    safety_result = safety.evaluate(
        signal=signal_result,
        equity=self.risk_mgr.equity,
        current_open_count=len(open_pos),
        open_positions=open_pos,
    )
    if not safety_result.approved:
        log_rejection(symbol, f"safety: {safety_result.rejection_reason}")
        return

    # ── Phase 4: LLM AGENT PIPELINE (the brain) ──
    # Build context with ALL data the removed gates used to check:
    llm_context = self._build_llm_signal_context(
        signal=signal_result,
        data=data,
        equity=self.risk_mgr.equity,
        open_positions=open_pos,
        market_data={
            "funding_rate": self._last_funding_rates.get(symbol),
            "volume_ratio": signal_result.metadata.get("volume_ratio", 1.0),
            "time_utc_hour": datetime.now(timezone.utc).hour,
            "correlation_matrix": self._compute_portfolio_correlation(),
            "recent_trades": self.feedback.quality.by_symbol.get(symbol),
            "btc_trend": self._price_changes_1h.get("BTC", 0.0),
            "signal_age": time.time() - signal_result.metadata.get("generated_at", time.time()),
        },
    )

    llm_decision = self._run_llm_pipeline(llm_context, trace_id)
    # Returns: {action: go/skip, leverage, qty, regime, thesis, risk_notes}

    if llm_decision.action == "skip":
        log_rejection(symbol, f"LLM: {llm_decision.reason}")
        return

    # ── Phase 5: POST-LLM SAFETY (hard caps) ──
    leverage = llm_decision.leverage
    qty = llm_decision.qty

    # Hard notional cap (15x equity)
    notional = qty * signal_result.entry * leverage
    if notional > 15 * self.risk_mgr.equity:
        qty = (15 * self.risk_mgr.equity) / (signal_result.entry * leverage)

    # Portfolio notional cap
    if not self.pos_mgr.check_portfolio_notional_cap(...):
        return

    # OpsGuard rate limiting
    if not self.ops_guard.can_execute(...)["allowed"]:
        return

    # Min qty / min notional (exchange minimum)
    qty = max(qty, get_min_qty(symbol))

    # ── Phase 6: EXECUTION ──
    # Live price refresh, slippage check, order placement
    ...
```

### 3. `bot/strategies/ensemble.py` — MODERATE CHANGE

**Current behavior:** `evaluate()` applies confidence floor, chop floor, trend flip, quality scorer, and returns None if filtered.

**New behavior:** New method `evaluate_raw()` that returns the signal WITHOUT quality filters. The existing `evaluate()` stays for backtest compatibility.

```python
def evaluate_raw(self, symbol, data) -> Optional[Signal]:
    """Generate signal from strategy voting WITHOUT quality filters.

    Returns the raw ensemble signal with metadata (chop_score, trend
    alignment, etc.) attached but NOT used as gates. The LLM pipeline
    reads this metadata to make informed decisions.
    """
    # Run all strategies, collect votes, compute weighted confidence
    # ... (same as evaluate() through vote aggregation)

    # Attach metadata but DON'T filter:
    result.metadata["chop_score"] = chop_score
    result.metadata["trend_alignment"] = trend_adjustment
    result.metadata["quality_score"] = quality_score
    result.metadata["regime_floor_suggested"] = effective_floor
    result.metadata["win_prob"] = win_prob
    result.metadata["ev_per_dollar"] = ev

    return result  # Never returns None for quality reasons
```

### 4. `bot/llm/agents/coordinator.py` — MODERATE CHANGE

The coordinator currently receives a generic snapshot. It needs to receive the raw signal and all the context that used to live in mechanical gates.

**New method or extended pipeline:**

```python
def get_entry_decision(self, signal, market_context, portfolio_context):
    """Full entry pipeline: Regime -> Quant -> Trade -> Risk -> Critic.

    Unlike get_trading_decision() which operates on a compressed snapshot,
    this receives the raw signal and full context to make quality + sizing
    decisions that replace 47 mechanical gates.
    """
    # 1. Regime Agent: classify market (unchanged)
    # 2. NEW — Quant Agent: compute EV, Kelly, win probability
    # 3. Trade Agent: form thesis, go/skip/flip (receives quant output)
    # 4. Risk Agent: size position (FINAL authority on leverage + qty)
    # 5. Critic Agent: stress-test (structured debate for large trades)

    return EntryDecision(
        action="go" | "skip",
        leverage=float,
        qty=float,
        regime=str,
        thesis=str,
        risk_notes=str,
        sizing_rationale=str,
    )
```

### 5. `bot/llm/agents/prompts.py` — MODERATE CHANGE

Agent prompts need to be enriched with the data that mechanical gates used to check:

- **Regime Agent**: No change (already receives market data)
- **Trade Agent**: Add EV, win probability, fee drag, chop score to input data
- **Risk Agent**: Add full sizing authority. Prompt must produce: leverage, qty, risk_mult. Add portfolio correlation, sector exposure, time-of-day patterns as context.
- **Critic Agent**: Add structured debate format for trades above threshold
- **NEW Quant Agent** (or fold into Trade Agent): Computes EV, Kelly, win probability from raw signal data

### 6. `bot/core/llm_integration.py` — MODERATE CHANGE

The `_llm_veto_check` method becomes `_llm_entry_decision`. It moves from line 5242 to right after safety gates.

```python
def _llm_entry_decision(self, signal, data, open_pos, trace_id):
    """Full LLM pipeline for entry decisions.

    Replaces _llm_veto_check. Runs BEFORE sizing/quality gates,
    not after. The LLM IS the quality gate.
    """
    markets, global_ctx, risk_ctx, positions = self._build_llm_context()

    # Build signal-specific context with all data the removed gates used
    signal_ctx = {
        "signal": signal,
        "ev_per_dollar": signal.metadata.get("ev_per_dollar"),
        "win_prob": signal.metadata.get("win_prob"),
        "chop_score": signal.metadata.get("chop_score"),
        "fee_drag_pct": ...,
        "funding_rate": ...,
        "volume_ratio": ...,
        "portfolio_correlation": ...,
        "time_utc_hour": ...,
        "recent_performance": ...,
    }

    decision = self.coordinator.get_entry_decision(signal_ctx, ...)
    return decision
```

### 7. `bot/trading_config.py` — MINOR CHANGE

Add `LLM_FIRST_MODE` flag (default False for rollback safety):
```python
llm_first_mode: bool = os.getenv("LLM_FIRST_MODE", "false").lower() == "true"
```

### 8. `bot/llm/autonomy.py` — MINOR CHANGE

When `LLM_FIRST_MODE=true` AND `LLM_MODE >= SIZING`, the signal flow uses the new path. Otherwise, legacy path is used (backward compatible).

---

## Data Flow Differences

### What the LLM currently receives (line 5242):
- A `TradeCandidate` with pre-computed leverage, qty, entry_type
- All quality decisions already made
- Can only say "proceed" or "flat" (veto)

### What the LLM SHOULD receive (right after safety gates):
- Raw ensemble signal with attached metadata (chop_score, trend_alignment, win_prob, ev, etc.)
- Full OHLCV data for all timeframes
- Current portfolio state (open positions, correlation matrix)
- Market context (funding rates, volume ratios, BTC trend)
- Recent performance data (symbol win rate, strategy win rate, regime profitability)
- Time context (hour, day of week, session classification)
- Account state (equity, daily PnL, circuit breaker proximity)

### What the LLM SHOULD return:
```json
{
  "action": "go",
  "thesis": "BTC breaking out of 4h consolidation with volume confirm, HTF trend aligned",
  "leverage": 5.0,
  "risk_pct": 0.08,
  "regime": "trending_bull",
  "stop_adjustment": null,
  "tp1_adjustment": null,
  "confidence_override": 82,
  "sizing_rationale": "Full Kelly at 8% risk. Correlation risk low (0.3). Morning session edge (+20%). No fee drag issue (stop width 1.2%).",
  "risk_flags": ["approaching_daily_loss_limit"],
  "debate_summary": "Bull: volume + HTF + regime. Bear: overbought RSI. Resolution: volume overrides RSI in trend regime (75% WR historically)"
}
```

---

## Risks and Mitigations

### Risk 1: LLM API failure kills all trading
**Mitigation:** Fail-open with mechanical fallback. If LLM fails, run through legacy `RiskFilterChain` with all quality gates. The `LLM_FIRST_MODE` flag toggles between paths.

### Risk 2: LLM approves catastrophic trade
**Mitigation:** Post-LLM safety gates (notional cap, OpsGuard, exchange limits) are NEVER removed. The LLM can approve a bad trade but it cannot approve more than 15x equity in notional.

### Risk 3: LLM is too slow (adds latency)
**Mitigation:** The LLM already runs at line 5242. Moving it earlier doesn't add a new API call, it moves the existing one. Net latency is actually LOWER because we skip computing 40+ gates that the LLM replaces.

### Risk 4: Regression in backtest mode
**Mitigation:** Backtest mode (no LLM) continues using `RiskFilterChain` with all quality gates. The new path only activates when `LLM_FIRST_MODE=true` AND `LLM_MODE >= SIZING`.

### Risk 5: LLM returns garbage sizing
**Mitigation:** Post-LLM hard caps: max 15x equity notional, max per-symbol leverage from exchange, min qty from exchange, OpsGuard rate limiting. The LLM picks sizing within safe bounds.

---

## Incremental Implementation Plan

### Step 1: SafetyFilterChain extraction (LOW RISK)
- Extract safety gates from `RiskFilterChain` into `SafetyFilterChain`
- `RiskFilterChain` still exists, unchanged
- No behavior change — pure refactor
- **Files:** `bot/core/signal_pipeline.py`
- **Test:** All existing tests pass

### Step 2: `evaluate_raw()` in ensemble (LOW RISK)
- Add `evaluate_raw()` method to `EnsembleStrategy`
- Existing `evaluate()` unchanged
- Returns signal with metadata but no quality filtering
- **Files:** `bot/strategies/ensemble.py`
- **Test:** New tests that raw signals are returned with metadata

### Step 3: LLM context enrichment (LOW RISK)
- Modify `_build_llm_context()` to include all data that mechanical gates used to check
- Enrich agent prompts with this data
- No flow change — just richer context for existing LLM veto check
- **Files:** `bot/core/llm_integration.py`, `bot/llm/agents/prompts.py`, `bot/llm/agents/coordinator.py`
- **Test:** LLM receives richer context (log inspection)

### Step 4: LLM sizing authority (MEDIUM RISK)
- Extend Risk Agent prompt to return leverage + qty
- Add `get_entry_decision()` to coordinator
- Parse and validate LLM sizing output
- **Files:** `bot/llm/agents/coordinator.py`, `bot/llm/agents/prompts.py`
- **Test:** Mock LLM returns valid sizing, test bounds enforcement

### Step 5: Rewire `_process_symbol()` — THE BIG CHANGE (HIGH RISK)
- Add `LLM_FIRST_MODE` flag
- When enabled:
  1. Run `SafetyFilterChain` (not `RiskFilterChain`)
  2. Run `_llm_entry_decision()` (not `_llm_veto_check()`)
  3. Use LLM-returned leverage/qty (not mechanical)
  4. Apply post-LLM hard caps
  5. Execute
- When disabled: legacy path unchanged
- **Files:** `bot/multi_strategy_main.py`, `bot/trading_config.py`, `bot/llm/autonomy.py`
- **Test:** Run both paths in parallel, compare decisions (dual-track logging)

### Step 6: Dual-track validation (ZERO RISK)
- Run BOTH paths and log decisions side by side
- Compare: what would LLM-first approve that mechanical killed?
- Compare: what would LLM-first skip that mechanical approved?
- Tune for 1 week before switching live
- **Files:** `bot/multi_strategy_main.py` (dual-path logging)

### Step 7: Go live
- Set `LLM_FIRST_MODE=true` in production
- Monitor via existing candidate logger + growth intelligence
- Keep mechanical path as instant rollback (`LLM_FIRST_MODE=false`)

---

## Line-by-Line Reference: Current _process_symbol Flow

| Lines | What happens | Tier in new design |
|-------|-------------|-------------------|
| 2420-2500 | Data fetch, stale guard | UNCHANGED |
| 2500-3720 | Tick processing, position management | UNCHANGED |
| 3726 | `ensemble.evaluate()` | CHANGE to `evaluate_raw()` |
| 3728-3900 | Sniper evaluation | UNCHANGED (parallel path) |
| 3903-3963 | Mechanical bot instrumentation, regime floor | REMOVE (LLM handles) |
| 3965-4010 | Soft filter annotation | REMOVE (LLM handles) |
| 4010-4076 | Quant brain pre-filter | REMOVE (folded into LLM) |
| 4081-4092 | Signal dedup | REMOVE (LLM decides re-entry) |
| 4096-4183 | LLM trigger accumulation | KEEP (feeds into LLM pipeline) |
| 4185-4195 | Anti-round-trip filter | REMOVE (LLM has history) |
| 4197-4242 | Signal flagger | KEEP (cheap metadata for LLM) |
| 4244-4272 | Log signal to DB | KEEP |
| 4274-4318 | ML confidence adjustment | REMOVE (LLM replaces ML) |
| 4320-4388 | Feedback loop floor | REMOVE (LLM handles quality) |
| 4392-4458 | Circuit breaker check | MOVE to SafetyFilterChain |
| 4460-4487 | HTF trend gate | REMOVE (LLM sees HTF data) |
| 4489-4576 | RiskFilterChain.evaluate() | REPLACE with SafetyFilterChain |
| 4578-4644 | Leverage decisions + caps | REMOVE (LLM Risk Agent) |
| 4646-4665 | Rotation candidate | KEEP |
| 4667-4778 | Signal decay, liquidity, funding, min profit, vol-target | REMOVE (LLM context) |
| 4780-4967 | Position sizing + 12 multipliers | REMOVE (LLM Risk Agent) |
| 4975-5064 | Trade classification, dynamic TP | KEEP (post-LLM, before execution) |
| 5066-5127 | Entry reasons, correlation guard, slippage cooldown | PARTIALLY REMOVE |
| 5129-5198 | LLM trigger, price refresh, pending orders | KEEP |
| 5200-5219 | Price shift | KEEP |
| 5220-5357 | **LLM VETO CHECK** | REPLACE with _llm_entry_decision at line ~4100 |
| 5390-5487 | LLM size mult, adaptive risk, RL, pattern boost | REMOVE (LLM handles) |
| 5489-5561 | Notional floors/caps, OpsGuard | KEEP (post-LLM safety) |
| 5563-5600+ | Live price, execution | KEEP |

---

## Rollback Plan

1. Set `LLM_FIRST_MODE=false` in `.env`
2. Bot immediately uses legacy path with all 47 gates
3. No code change needed — flag-based routing
4. Dual-track logging shows divergence before any switch

This is a zero-downtime, instant-rollback design.
