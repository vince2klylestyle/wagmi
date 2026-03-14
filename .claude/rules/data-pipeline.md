# Data Pipeline Rules

## Architecture
- `bot/data/fetcher.py` — Multi-exchange OHLCV data fetching via CCXT
- `bot/data/fetchers/` — Per-exchange fetcher implementations
- `bot/data/db.py` — SQLite persistence layer
- `bot/data/migrations.py` — Schema migrations
- `bot/data/strategy_weights.py` — Rolling strategy performance weights

## Data Requirements by Strategy
| Strategy | Timeframes Needed | Data Source | Notes |
|---|---|---|---|
| regime_trend | 1h, 6h | CCXT (Hyperliquid) | |
| confidence_scorer | varies | CCXT | ADX+MACD+BB+RSI |
| bollinger_squeeze | 1h | CCXT | BB/KC squeeze |
| vmc_cipher | 1h | CCXT | WaveTrend oscillators |
| probability_engine | 1h | CCXT | Monte Carlo sim |
| monte_carlo_zones | daily | CCXT | Mean-reversion zones |
| funding_rate | N/A | REST API (live) | No historical data in backtest |
| oi_delta | N/A | REST API (live) | fetch_open_interest() via CCXT |
| liquidation_cascade | 1h | CCXT | Volume spikes + wick detection |
| lead_lag (disabled) | 5m, 1h | CCXT | |
| multi_tier_quality (disabled) | 5m, 1h | CCXT | |

## Rules
- NEVER assume all timeframes are available — strategies must handle missing data
- Data freshness: if last candle is >5 minutes old, flag as stale
- Exchange API calls MUST have retry logic (exponential backoff)
- NEVER store API keys in code or data files
- SQLite migrations must be backwards-compatible
- Strategy weights should decay exponentially (recent trades weighted more)
- `decisions.jsonl` is append-only — never truncate in production
- Memory files (`llm_memory.json`, `deep_memory/`) are critical — handle write errors gracefully
