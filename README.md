# HeyAnon Platform

Multi-strategy crypto auto-trading system with self-improving ML.

## Architecture

```
bot/                        # Trading bot (Python)
  multi_strategy_main.py    # Main entry point
  trading_config.py         # All config via env vars
  strategies/               # 4 strategies + ensemble voting
  execution/                # Position manager, leverage, risk
  ml/                       # Self-improving ML learner
  backtest/                 # Backtesting engine
  alerts/                   # Discord + Telegram routing
  data/                     # CoinGecko data fetcher

api/                        # FastAPI backend (dashboard, trade logging)
web/                        # Next.js frontend (future app UI)
executor/                   # Copy trading executor
infra/                      # Docker Compose orchestration
```

## Quick Start

```bash
cd bot
cp .env.example .env        # Edit with your Discord/Telegram tokens
pip install -r requirements.txt

# Paper trading (default):
python multi_strategy_main.py

# Backtest:
python -m backtest.engine --symbols BTC,ETH,SOL --days 30
```

## Strategies

| Strategy | Edge | Timeframes |
|----------|------|------------|
| Regime Trend | WaveTrend + MACD/MFI multi-TF regime | 1h, 6h, 16h |
| Monte Carlo Zones | SMA zones + 1000-sim price prediction | Daily |
| Confidence Scorer | Zone signals with historical win-rate tracking | Daily |
| Multi-Tier Quality | EMA crossover + VWAP + tiered confidence | 5m, 30m, 1h |

Ensemble voting requires 2+ strategies to agree. Consensus boosts confidence,
which determines leverage (spot at low confidence, up to 25x when all 4 agree).

## Key Features

- **Trailing stop loss** - Activates after TP1 (40% partial close), trails by 1.5x ATR
- **Dynamic leverage** - 1x to 25x based on confidence + strategy agreement
- **ML self-improvement** - Learns from every trade, adjusts confidence over time
- **Circuit breakers** - Halts on 5% daily loss, 5 consecutive losses, or 10% drawdown
- **CoinGecko data** - Supports all coins including HYPE
