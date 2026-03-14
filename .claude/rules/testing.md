# Testing Rules

## Test Structure
Tests live in `bot/tests/` with **45 test files, 1,308 tests** covering:
- Phase-based tests (test_phase2.py, test_phase345.py, test_phase_c/d/ef/k/l.py)
- E2E pipeline tests (test_e2e_phases.py)
- Safety tests (test_execution_safety.py, test_ops_guard.py, test_ops_reliability.py)
- Feedback loop tests (test_feedback_loop.py, test_feedback_closers.py, test_sprint2_feedback_loops.py)
- Ensemble weight tests (test_ensemble_weights.py)
- Strategy tests (test_new_strategies.py, test_strategy_hardening.py)
- Quant system tests (test_quant_system.py, test_quant_backbone.py, test_quant_session2.py)
- Multi-agent tests (test_multi_agent.py)
- Wiring tests (test_wiring.py, test_wave1/2/3_wiring.py, test_session3_wiring.py)
- Profitability tests (test_profitability_fixes.py, test_profitability_shield.py)
- Self-teaching tests (test_self_teaching.py)
- Serialization tests (test_serializers.py)
- Stability tests (test_stability_fixes.py)
- Stress tests (test_stress.py)
- PnL math tests (test_pnl_math.py)
- Graduated risk tests (test_graduated_risk.py)
- Analytics tests (test_analytics.py, test_ev_and_schemas.py)
- Golden replay tests (test_golden_replay.py)

## Running Tests
```bash
cd bot && pytest tests/                    # All tests
cd bot && pytest tests/ -k "agent"         # Agent-related tests
cd bot && pytest tests/ -k "safety"        # Safety tests
cd bot && pytest tests/ -x                 # Stop on first failure
cd bot && pytest tests/ -v                 # Verbose output
```

## Rules
- NEVER skip tests to make a PR pass
- After modifying ANY execution/risk code, run the full suite
- After modifying agent prompts, run agent-specific tests
- New features MUST include tests (at minimum, smoke tests)
- Mock external dependencies (exchange APIs, LLM calls) in tests
- Use `bot/llm/test_harness.py` for deterministic LLM testing
- Test both happy path AND error paths (API failure, parse failure, circuit breaker)
