# Testing Gaps & Action Checklist

## Critical Safety Test Cases (MUST IMPLEMENT)

### ✅ 1. Agent Consistency & Vocabulary
**Status**: NOT TESTED
**File to create**: `tests/test_agent_consistency.py`
**Risk**: Agents could misinterpret each other → wrong decisions

- [ ] Test regime vocabulary is consistent across all agents
  - `test_all_agents_use_same_regime_names()` - should include: trend, range, panic, high_volatility, low_liquidity, news_dislocation, unknown

- [ ] Test action vocabulary is normalized
  - `test_action_normalization()` - go→proceed, skip→flat, flip→reverse

- [ ] Test shared memory bus passes context correctly
  - `test_upstream_agent_context_to_downstream()` - regime output → trade input
  - `test_trade_output_format_for_risk_input()` - trade decision → risk agent

- [ ] Test cross-agent output validation
  - `test_regime_output_schema_valid()` - has required fields: rg, conf, bias, transition
  - `test_trade_output_schema_valid()` - has required fields: a, c, n, mu, ea
  - `test_risk_output_schema_valid()` - has required fields: sz, sw, risks, override

- [ ] Test cascade failure detection
  - `test_downstream_agent_rejects_invalid_upstream()` - malformed regime output

---

### ✅ 2. Kelly Criterion & EV Safety
**Status**: NOT TESTED
**File to create**: `tests/test_kelly_safety.py`
**Risk**: Kelly overleverage → account blowup

- [ ] Test Kelly fraction bounds
  - `test_kelly_fraction_min_zero()` - 0 allowed
  - `test_kelly_fraction_max_fifty_percent()` - 0.5 cap
  - `test_kelly_fraction_clamped_to_bounds()` - values >0.5 clamped

- [ ] Test Kelly with edge case win rates
  - `test_kelly_with_zero_winrate()` - expectancy=0, kelly=0
  - `test_kelly_with_fifty_percent_winrate()` - neutral setup
  - `test_kelly_with_negative_expectancy()` - losing setup (kelly should be negative/0)

- [ ] Test Kelly modulation of size
  - `test_risk_agent_applies_kelly_modulation()` - sz × kelly_mult
  - `test_kelly_mult_formula_correct()` - kelly_mult = 1 + 1.5 × (kelly - 0.15)
  - `test_size_multiplier_never_exceeds_2x()` - final clamping

- [ ] Test conditional edge detection
  - `test_conditional_edge_vs_base_wr()` - higher conditional edge detected
  - `test_conditional_edge_min_samples()` - requires N similar trades before trust

- [ ] Test fat-tail risk assessment
  - `test_fat_tail_risk_low_normal_markets()` - low when vol normal
  - `test_fat_tail_risk_high_on_spike()` - high when vol spiking
  - `test_max_adverse_move_percentage()` - 2-3% in trend regime

---

### ✅ 3. Concurrent Position Safety
**Status**: NOT TESTED
**File to create**: `tests/test_concurrent_positions.py`
**Risk**: Overlapping positions, liquidation cascades, state corruption

- [ ] Test multiple symbols are independent
  - `test_btc_long_independent_from_eth_long()` - separate margin, SL
  - `test_three_symbols_concurrent()` - BTC LONG, ETH SHORT, SOL LONG

- [ ] Test TP/SL overlaps are detected
  - `test_overlapping_tp_ranges_rejected()` - two longs with overlapping TP
  - `test_overlapping_sl_ranges_detected()` - warning or rejection

- [ ] Test position flips during trailing
  - `test_flip_rejected_during_trailing()` - can't LONG then SHORT same symbol
  - `test_flip_after_trailing_complete()` - OK if no position

- [ ] Test simultaneous open/close
  - `test_open_new_while_closing()` - queuing behavior
  - `test_close_during_entry()` - cancellation logic

- [ ] Test liquidation cascades
  - `test_single_symbol_liquidation()` - doesn't affect others
  - `test_multi_symbol_liquidation_cascade()` - correlated crashes
  - `test_remaining_positions_after_cascade()` - survivors still valid

- [ ] Test correlation risk detection
  - `test_high_correlation_symbols_detected()` - BTC/ETH (0.85+)
  - `test_correlation_reduce_size_recommendation()` - smaller sizes
  - `test_correlation_max_aggregate_leverage()` - portfolio-level cap

---

### ✅ 4. Extreme Market Scenarios
**Status**: PARTIALLY TESTED (expand test_stress.py)
**File to enhance**: `tests/test_stress.py`
**Risk**: Gap events, funding spikes, flash crashes

Add to existing `TestFlashCrash` and create new classes:

- [ ] Test gap up liquidation
  - `test_gap_up_overnight()` - price skips stop loss
  - `test_long_gap_up_liquidation()` - liq hit without passing SL
  - `test_short_gap_down_liquidation()` - liq hit in opposite direction

- [ ] Test overnight circuit limits (Hyperliquid)
  - `test_overnight_circuit_limit_enforcement()` - price move cap
  - `test_position_survived_circuit_limit()` - doesn't liquidate

- [ ] Test funding rate spikes
  - `test_funding_spike_0_75_percent_per_day()` - normal long funding
  - `test_funding_spike_2_percent_per_day()` - extreme spike
  - `test_position_profitability_after_funding()` - P&L calculation includes funding

- [ ] Test cascading liquidations
  - `test_one_liquidation_affects_others()` - margin freed by closing one
  - `test_liquidation_order_sequence()` - which positions close first

- [ ] Test exchange reconnect
  - `test_exchange_outage_reconnect()` - state reconciliation
  - `test_position_reconciliation_after_outage()` - compare onchain vs bot
  - `test_trade_execution_retry_after_recover()` - pending orders

---

### ✅ 5. Data Quality & Staleness
**Status**: NOT TESTED
**File to create**: `tests/test_data_quality.py`
**Risk**: Bad data → bad decisions

- [ ] Test stale candle detection
  - `test_stale_candle_over_5min_rejected()` - flag as stale
  - `test_recent_candle_accepted()` - within 5 min is OK
  - `test_stale_candle_blocks_entry()` - gated by data age

- [ ] Test missing candles
  - `test_missing_1h_candle_handled()` - strategy returns None
  - `test_missing_6h_candle_handled()` - falls back to 1h
  - `test_all_timeframes_missing_aborts()` - no signal generated

- [ ] Test zero volume detection
  - `test_zero_volume_candle_rejected()` - likely data error
  - `test_near_zero_volume_warning()` - log but allow

- [ ] Test extreme spread rejection
  - `test_spread_over_5_percent_rejected()` - too wide
  - `test_spread_normal_allowed()` - <1% is OK

- [ ] Test corrupted OHLCV recovery
  - `test_close_price_outside_ohl_rejected()` - sanity check
  - `test_high_lower_than_low_rejected()` - logic check
  - `test_volume_negative_rejected()` - impossible value

---

### ✅ 6. LLM Mocking Completeness
**Status**: PARTIAL (enhance existing mocks)
**File to enhance**: `tests/test_multi_agent.py`
**Risk**: LLM failures not simulated

- [ ] Test timeout scenarios
  - `test_llm_timeout_aborts_pipeline()` - agent fails, decision is None
  - `test_llm_rate_limit_retry()` - exponential backoff

- [ ] Test malformed response handling
  - `test_malformed_json_fails_gracefully()` - parse error → None
  - `test_missing_required_field_detected()` - schema validation

- [ ] Test NaN/Inf edge cases
  - `test_confidence_nan_replaced()` - NaN → 0 or default
  - `test_confidence_inf_clamped()` - inf → 1.0
  - `test_size_multiplier_nan_replaced()` - → 1.0

- [ ] Test hallucinated confidence
  - `test_llm_confidence_outside_0_1_clamped()` - clamp to [0, 1]
  - `test_confidence_100_rejected_as_unrealistic()` - cap at 0.95?

---

### ✅ 7. Evolution & Learning Safety
**Status**: NOT TESTED
**File to create**: `tests/test_evolution_tracker.py`
**Risk**: Bad strategies get higher weights → losses compound

- [ ] Test strategy degradation detection
  - `test_win_rate_below_50_detected()` - losing strategy flagged
  - `test_drawdown_above_threshold_detected()` - 5%+ daily drawdown
  - `test_consecutive_loss_streak_detected()` - 5+ losses in a row

- [ ] Test rolling performance windows
  - `test_recent_trades_weighted_more()` - exponential decay
  - `test_old_trades_decay_to_zero()` - 30-day cutoff

- [ ] Test regime-specific accuracy
  - `test_regime_trend_accuracy_tracked()` - per-regime WR
  - `test_regime_range_accuracy_tracked()` - separate from trend
  - `test_regime_switch_detected()` - accuracy changes at transition

- [ ] Test weight updates don't cause pump-and-dump
  - `test_weight_increase_max_2x_per_day()` - gradual increase
  - `test_weight_decrease_immediate()` - immediate on loss
  - `test_weight_never_negative()` - floor at prior

---

### ✅ 8. Auto-Optimizer Safety
**Status**: NOT TESTED
**File to create**: `tests/test_auto_optimizer.py`
**Risk**: Bad parameters → cascading losses

- [ ] Test parameter bounds enforcement
  - `test_leverage_max_20x_enforced()` - never exceeds limit
  - `test_stop_width_min_0_3_percent()` - no hair-trigger stops
  - `test_daily_loss_limit_positive()` - 0-10% range

- [ ] Test optimization stability
  - `test_parameter_changes_gradual()` - no jumps >20%
  - `test_rollback_on_degradation()` - revert if worse
  - `test_new_params_require_approval()` - human gate

- [ ] Test sensitivity analysis
  - `test_parameter_sensitivity_ranked()` - which matters most
  - `test_interactions_detected()` - leverage × confidence

- [ ] Test safety constraints
  - `test_liq_distance_min_5_percent()` - always safe
  - `test_funding_cost_factored_in()` - cost included in sizer

---

### ✅ 9. Memory & Persistence
**Status**: NOT TESTED (but critical for learning)
**File to create**: `tests/test_memory_store.py`
**Risk**: Memory loss → learning failures

- [ ] Test deep memory persistence
  - `test_deep_memory_survives_restart()` - pickle/json
  - `test_deep_memory_corruption_detected()` - CRC check

- [ ] Test TTL expiration
  - `test_note_expires_after_7_days()` - auto-prune
  - `test_recent_notes_kept()` - don't delete fresh data

- [ ] Test memory bus synchronization
  - `test_upstream_agent_writes_to_bus()` - regime → scratchpad
  - `test_downstream_agent_reads_bus()` - trade reads regime
  - `test_bus_cleared_between_decisions()` - fresh state

- [ ] Test corruption recovery
  - `test_corrupted_trade_dna_skipped()` - validate format
  - `test_invalid_hypothesis_quarantined()` - don't use bad lessons

- [ ] Test memory audit
  - `test_memory_size_bounded()` - <100MB
  - `test_memory_leak_detection()` - size doesn't grow unbounded

---

## Coverage Measurement Checklist

- [ ] Install `pytest-cov`
  ```bash
  pip install pytest-cov
  ```

- [ ] Generate baseline coverage
  ```bash
  cd bot && pytest tests/ --cov=. --cov-report=html
  ```

- [ ] Set coverage targets by module
  - Strategies: 100%
  - Execution: 95%+
  - LLM agents: 90%
  - Feedback: 85%
  - Data: 95%

- [ ] Add CI gate
  ```bash
  pytest tests/ --cov=. --cov-fail-under=80
  ```

- [ ] Document coverage in README

---

## Parameterization Refactoring Checklist

### Convert to @pytest.mark.parametrize

- [ ] Confidence ranges
  ```python
  @pytest.mark.parametrize("confidence", [0.50, 0.75, 0.95])
  def test_size_by_confidence(confidence):
      ...
  ```

- [ ] Regimes
  ```python
  @pytest.mark.parametrize("regime", ["trend", "range", "panic", "unknown"])
  def test_agent_handles_regime(regime):
      ...
  ```

- [ ] Symbols
  ```python
  @pytest.mark.parametrize("symbol", ["BTC", "ETH", "SOL"])
  def test_signal_validity_all_symbols(symbol):
      ...
  ```

- [ ] Side (LONG/SHORT)
  ```python
  @pytest.mark.parametrize("side", ["LONG", "SHORT"])
  def test_liquidation_both_sides(side):
      ...
  ```

- [ ] Market conditions (5 × 4 matrix)
  ```python
  @pytest.mark.parametrize("symbol,regime", [
      ("BTC", "trend"), ("BTC", "range"),
      ("ETH", "trend"), ("ETH", "range"),
      ("SOL", "panic"), ("SOL", "high_volatility"),
      # ... 20 combinations
  ])
  def test_strategy_accuracy_matrix(symbol, regime):
      ...
  ```

---

## Test Infrastructure Improvements

- [ ] Create `tests/conftest.py` with shared fixtures
  ```python
  @pytest.fixture
  def mock_position_manager():
      return MagicMock(spec=PositionManager)

  @pytest.fixture
  def sample_snapshot():
      return {
          "m": [{"s": "BTC", "p": 95000}],
          "g": {"btc": 95000, "eq": 10000},
      }
  ```

- [ ] Create `tests/fixtures/` directory with test data
  - `snapshots.json` - sample market snapshots
  - `trades.csv` - historical trades for replay
  - `agents_responses.json` - sample LLM responses

- [ ] Add `tests/strategies.py` with test helpers
  - DummyStrategy base class
  - Signal factory functions
  - Position factory functions

- [ ] Add `pytest.ini` configuration
  ```ini
  [pytest]
  testpaths = tests
  python_files = test_*.py
  python_classes = Test*
  python_functions = test_*
  addopts = -v --strict-markers --tb=short
  ```

---

## Process Improvements

- [ ] Add pre-commit hook to run tests
  ```bash
  #!/bin/bash
  cd bot && python -m pytest tests/ -x --tb=short
  ```

- [ ] Add GitHub Actions (if applicable)
  ```yaml
  on: [push, pull_request]
  jobs:
    test:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v2
        - run: cd bot && pytest tests/ --cov=. --cov-fail-under=80
  ```

- [ ] Create TESTING.md with guidelines
  - Test naming conventions
  - Mock patterns
  - Coverage expectations
  - Failure modes to test

- [ ] Add test categorization markers
  ```python
  @pytest.mark.safety
  @pytest.mark.llm
  @pytest.mark.slow
  ```

---

## Implementation Priority

### Week 1 (Critical)
1. Agent consistency tests (20 tests)
2. Kelly safety tests (15 tests)
3. Expand stress scenarios (10 tests)
4. Install pytest-cov, generate baseline

### Week 2 (High)
5. Concurrent position tests (10 tests)
6. Data quality tests (12 tests)
7. Evolution tracker tests (15 tests)

### Week 3 (Medium)
8. Auto-optimizer tests (12 tests)
9. Memory store tests (12 tests)
10. LLM timeout/error tests (10 tests)

### Week 4+ (Nice-to-have)
11. Parameterized test conversion
12. Test data fixtures
13. Performance benchmarks
14. CI/CD integration

---

## Validation Checklist (Before Production)

- [ ] All circuit breaker tests passing
- [ ] All liquidation tests passing
- [ ] Agent consistency tests 100% pass
- [ ] Kelly safety tests 100% pass
- [ ] Concurrent position tests 100% pass
- [ ] Stress tests covering flash crash, gap, funding spike
- [ ] Data quality tests for staleness, corruption
- [ ] Evolution & optimizer tests passing
- [ ] Coverage ≥80% overall, 90%+ on safety-critical
- [ ] No skipped tests (xfail only for known issues)
- [ ] All mocked systems have deterministic responses
- [ ] No `print()` or `import pdb` left in tests

