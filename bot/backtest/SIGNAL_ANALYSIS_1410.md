# Full Signal Analysis — 1,410 Raw Signals, 60 Days

## Data: Every strategy signal with 1h/2h/4h/8h/12h price outcome

### Strategy Ranking (4h horizon)
| Strategy | Signals | WR | Avg Move | Total | Verdict |
|----------|---------|-----|----------|-------|---------|
| **bollinger_squeeze** | 385 | **57%** | +0.15% | +58.9% | **ONLY WINNER** |
| probability_engine | 32 | 53% | -0.04% | -1.4% | Breakeven |
| mean_reversion | 51 | 43% | -0.18% | -9.0% | Loser |
| regime_trend | 79 | 43% | -0.31% | -24.6% | Loser |
| confidence_scorer | 845 | 47% | -0.07% | -59.5% | Loser (huge vol) |

### Golden Setups (>55% WR, n>20)
| Setup | WR | n | Avg Move | Action |
|-------|-----|---|----------|--------|
| ETH_SELL_BB | **70%** | 50 | +0.81% | MAX SIZE |
| BTC_BUY_BB | **69%** | 32 | +0.06% | TAKE |
| SOL_BUY_BB | **67%** | 24 | +0.36% | TAKE |
| BTC_SELL_BB | **61%** | 54 | +0.24% | TAKE |
| ETH_BUY_BB | **59%** | 59 | +0.14% | TAKE |

### Dead Setups (never take)
| Setup | WR | n | Avg Move | Action |
|-------|-----|---|----------|--------|
| HYPE_SELL_BB | 35% | 51 | -0.54% | NEVER |
| HYPE_BUY_CS | 38% | 125 | -0.19% | NEVER |
| All mean_reversion | 43% | 51 | -0.18% | AVOID |
| All regime_trend | 43% | 79 | -0.31% | AVOID |

### Confidence is NOT predictive
| Bucket | WR | Avg Move |
|--------|-----|----------|
| <60% | 52% | +0.01% |
| 70-79% | 52% | +0.01% |
| 80%+ | 50% | -0.09% |
| 60-69% | 47% | -0.06% |

### Regime Edge
| Regime | WR | n | Avg Move |
|--------|-----|---|----------|
| trending | 78% | 9 | +0.35% |
| high_volatility | **55%** | **258** | +0.11% |
| range | 47% | 98 | +0.05% |
| trend | 47% | 841 | -0.07% |

### BB-Only Simulation
- All BB signals: 385 trades, 57% WR, +59% cumulative
- Excluding HYPE_SELL_BB: 334 trades, **60% WR, +86% cumulative**
- At 8% risk, 7x leverage: ~48% account return in 60 days
