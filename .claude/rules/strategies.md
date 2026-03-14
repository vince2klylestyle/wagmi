# Strategy Development Rules

## Architecture
The bot uses 11 trading strategies (9 active, 2 disabled) that vote through a weighted-veto ensemble:

**Active (9):**
1. `regime_trend.py` — Regime-based trend following (1h+6h MACD+MFI)
2. `confidence_scorer.py` — Multi-factor momentum scoring (ADX+MACD+BB+RSI)
3. `bollinger_squeeze.py` — BB/KC squeeze detection + breakout
4. `vmc_cipher.py` — 5-oscillator confluence (WaveTrend-based)
5. `probability_engine.py` — Regime-conditional Monte Carlo simulation
6. `monte_carlo_zones.py` — Daily TF mean-reversion zones
7. `funding_rate.py` — Counter-trades extreme funding (live/paper only, no backtest data)
8. `oi_delta.py` — Open interest expansion/contraction signals
9. `liquidation_cascade.py` — Post-cascade reversal signals (volume spikes + wicks)

**Disabled (2):**
10. `lead_lag_enabled.py` — 0% WR, -$1,100 net (disabled)
11. `multi_tier_quality.py` — PF 0.82, -$1,223 net (disabled)

Ensemble voting happens in `bot/strategies/ensemble.py` (weighted_veto mode, 1,599 lines).
Regime-based allowlists gate which strategies can vote in each market condition.

## Signal Contract
All strategies MUST return `Optional[Signal]` from their `evaluate()` method.

The `Signal` dataclass (`bot/strategies/base.py`) requires:
- `strategy`: str — strategy name
- `symbol`: str — trading pair
- `side`: str — "BUY" or "SELL"
- `confidence`: float — 0-100 scale
- `entry`: float — entry price
- `sl`: float — stop loss price
- `tp1`, `tp2`: float — take profit targets
- `atr`: float — current ATR value

Signal validation (`Signal.is_valid`):
- Stop width must be >= 0.3% of entry
- SL must be on correct side of entry
- TP1, TP2 must be on correct side of entry
- R:R ratio must be >= 1.0

## Rules for Strategy Changes
- NEVER modify the Signal dataclass without updating ALL strategies and the ensemble
- NEVER remove the `is_valid` checks — they prevent nonsensical trades
- Every strategy MUST handle missing data gracefully (return None, not crash)
- Ensemble MIN_VOTES and VETO_RATIO are in `trading_config.py` — don't hardcode
- Strategy weights are managed by `bot/data/strategy_weights.py` — don't override manually
- Timeframe weights: 5m=0.5, 1h=1.0, 6h=1.5, daily=2.0 (in `trading_config.py`)

## Testing
- Run `cd bot && pytest tests/ -k "ensemble or strategy"` after any strategy change
- Verify signal validity with: `assert signal.is_valid` in tests
