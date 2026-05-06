# Extended Paper Trading Session — May 6, 2026

**Status**: ACTIVE  
**Start Time**: 17:30:49 UTC  
**Goal**: Collect 200+ trades to validate Phase 2 baseline across larger sample  
**Target Duration**: 6+ hours  
**Monitoring**: Real-time event capture via tail -f + regex filter

## Configuration Verified ✅
- MIN_VOTES_REQUIRED: 1 (allow solo signals)
- ENSEMBLE_CONFIDENCE_FLOOR: 55.0 (restored from broken 10.0)
- TAKER_FEE_BPS: 2 (realistic Hyperliquid fees)
- USE_CLI_LLM: true (CLI-only routing)
- LLM_MODE: 1 (ADVISORY - mechanical decisions, LLM logging)
- Strategy weights loaded: sniper_premium 0.658, ensemble 0.291, regime_trend 0.542
- All major systems initialized: signal pipeline, risk gates, learning loops, portfolio risk

## Bot Status
- Environment: paper (safe)
- Symbols: BTC, ETH, SOL, HYPE
- Strategies: regime_trend, monte_carlo_zones, bollinger_squeeze, trend_breakout
- Leverage: enabled (max 15.0x, with adaptive caps)
- Trailing stop: enabled (1.5x ATR)
- ML models: loaded
- Circuit breakers: armed

## Monitoring Active
- Process ID: 1872
- Log file: bot/logs/extended_session_20260506.log
- Monitor task: bsmzete1n (persistent, 6-hour timeout)
- Event capture: TRADE|REGIME|SIGNAL|ERROR|HEARTBEAT|WR:|P&L:|CIRCUIT

## Success Criteria
- Trade count: 200+ (vs 147 in initial Cycle 5)
- Win rate: 50%+ (matching initial phase)
- P&L: Positive overall
- Risk gates: 0 breaches (expect 0 circuit breaks)
- No regressions in individual strategy performance

## Next Checkpoint
- 30-minute autonomous checkpoints via ScheduleWakeup
- Real-time event notifications from Monitor task
