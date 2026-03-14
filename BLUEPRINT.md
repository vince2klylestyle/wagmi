# WAGMI Quant Alpha Engine — Master Blueprint

> Post-backtest roadmap for evolving from AI-assisted tactical trading into a true quantitative alpha engine.
> Generated from 9-agent parallel audit covering: position sizing, signal diversification, execution quality, learning/adaptivity, trade frequency math, and 4-phase architecture design.

---

## Current State: Quant Audit Summary (Score: 4.5/10)

| Dimension | Score | Key Finding |
|-----------|-------|-------------|
| Position Sizing & Risk | 5.5/10 | Half-Kelly exists but no risk parity, no vol targeting |
| Signal Diversification | 3/10 | All strategies use overlapping indicators (80%+ momentum) |
| Execution Quality | 6/10 | Good fee modeling, but ALL orders are market orders |
| Learning & Adaptivity | 5/10 | Excellent logging, no walk-forward validation |
| Trade Frequency Math | 5/10 | ~50 trades/day projected, breakeven WR=46.4% |
| Multi-Asset Coverage | 1/10 | Only 5 correlated crypto symbols |
| Factor Exposure | 1/10 | Single factor (momentum). No value/carry/macro |

### The 5 Brutal Truths
1. **Fee drag is the silent killer** — Real costs ~25 bps vs modeled 14 bps. Breakeven WR is 46-50%, not 38%.
2. **Strategies are correlated, not diversified** — All 4 core strategies use MACD/ADX/RSI/BB variants. "4 opinions from 1 brain."
3. **No walk-forward validation** — Learning loop trains and tests on same data. #1 overfitting risk.
4. **LLM is discretionary, not statistical** — Claude forms theses. No p-values, no known false-positive rates.
5. **5 symbols is not a portfolio** — All crypto, all correlated >0.7.

### What We Do Well (Keep These)
- Circuit breakers + session drawdown cap = institutional-grade risk control
- Multi-agent LLM reasoning with Critic veto = intelligent quality gate
- Deep memory (Trade DNA) + learning feedback = strong self-improvement
- EV gating + fee-drag filters = cost-aware signal selection
- Regime-aware voting = adaptive to market conditions
- Half-Kelly engine with per-strategy calibration

---

## Phase 1: True Signal Diversification & Factor Architecture
**Timeline: Weeks 1-4 | Impact: HIGH | Effort: MEDIUM**

### Problem
All 4 core strategies use overlapping price-action indicators:
- `regime_trend`: WaveTrend + MACD + MFI + ADX
- `confidence_scorer`: ADX + MACD + BB + RSI + Keltner
- `bollinger_squeeze`: BB/Keltner + MACD histogram + RSI
- `monte_carlo_zones`: SMA20/50 + RSI + stdev zones

Result: 80%+ exposure to momentum factor. When momentum crashes, ALL strategies lose simultaneously.

### Solution: Orthogonal Signal Sources

#### Phase 1a — Activate Existing Dormant Strategies (Week 1)
These strategies ALREADY EXIST in the codebase but are disabled or underutilized:

| Strategy | File | Factor | Status | Action |
|----------|------|--------|--------|--------|
| `funding_rate` | `strategies/funding_rate.py` | Carry | Exists | Enable, tune thresholds |
| `oi_delta` | `strategies/oi_delta.py` | Flow | Exists | Enable, validate signals |
| `cvd_strategy` | `strategies/cvd_strategy.py` | Flow | Exists | Enable, tune |
| `liquidation_cascade` | `strategies/liquidation_cascade.py` | Microstructure | Exists | Enable for extreme events |
| `vmc_cipher` | `strategies/vmc_cipher.py` | Multi-oscillator | Exists | Re-evaluate edge |

**Goal**: Go from 4 active strategies to 7-8, with 3+ non-overlapping factor sources.

#### Phase 1b — New Orthogonal Signals (Weeks 2-3)

| Signal | Factor Category | Data Source | Expected Alpha | Effort |
|--------|----------------|-------------|----------------|--------|
| **Funding rate term structure** | Carry | Hyperliquid API (funding history) | Medium-High | 2 days |
| **Order book imbalance** | Microstructure | Hyperliquid WebSocket L2 | Medium | 3 days |
| **Exchange netflow** | On-chain | CryptoQuant / Glassnode API | High | 3 days |
| **Fear & Greed Index** | Sentiment | Alternative.me API (free) | Low-Medium | 1 day |
| **Cross-asset correlation** | Macro | DXY via CCXT (forex pair) | Medium | 2 days |
| **Whale wallet tracking** | On-chain | Arkham / Nansen API | High | 4 days |

**Funding Rate Term Structure** (highest ROI):
```
Signal: Compare current funding rate to 7-day average
If funding >> avg → market overleveraged long → short bias
If funding << avg → market overleveraged short → long bias
Backwardation (negative funding) = strong carry signal
```
Integration: New strategy inheriting `BaseStrategy`, returns `Signal` with `strategy="funding_curve"`. Ensemble treats as independent vote.

**Order Book Imbalance**:
```
Signal: bid_depth / ask_depth ratio at top 5 levels
If bid/ask > 1.5 → absorption buying → long bias
If bid/ask < 0.67 → selling pressure → short bias
```
Integration: Real-time WebSocket feed, computed every tick, exposed to strategies as a feature.

#### Phase 1c — Factor Model Architecture (Week 4)

Target allocation across factor categories:

```
Portfolio Factor Budget:
├── Momentum (25%): regime_trend, confidence_scorer, bollinger_squeeze
├── Carry (25%): funding_rate, funding_curve (new)
├── Flow/Microstructure (25%): oi_delta, cvd, order_book_imbalance (new)
└── Sentiment/Macro (25%): fear_greed, exchange_netflow (new), cross_asset_corr (new)
```

**Implementation: Factor-Weighted Ensemble**
```python
# In ensemble.py, add factor-aware weighting:
STRATEGY_FACTOR_MAP = {
    'regime_trend': 'momentum',
    'confidence_scorer': 'momentum',
    'bollinger_squeeze': 'momentum',
    'funding_rate': 'carry',
    'funding_curve': 'carry',
    'oi_delta': 'flow',
    'cvd_strategy': 'flow',
    'order_book_imbalance': 'flow',
    'fear_greed': 'sentiment',
    'exchange_netflow': 'sentiment',
}

# Cap per-factor contribution to prevent momentum dominance
MAX_FACTOR_WEIGHT = 0.35  # No single factor can be >35% of ensemble vote
```

### Symbol Expansion Strategy

**Tier 1 — Add immediately (high liquidity, low correlation to BTC):**
- ETH, AVAX, LINK, AAVE, ARB

**Tier 2 — Add after validation (medium liquidity):**
- SUI, SEI, TIA, JUP, WIF

**Tier 3 — Monitor only (low liquidity, high risk):**
- PEPE, BONK, WEN, ONDO

**Selection criteria:**
- Hyperliquid daily volume > $10M
- Correlation to BTC < 0.80 (24h rolling)
- Spread < 5 bps at $50k notional

---

## Phase 2: Execution Optimization & Statistical Validation
**Timeline: Weeks 3-8 | Impact: HIGH | Effort: HIGH**

### Problem
- ALL orders are market orders → leaving 10-15 bps on the table
- Hidden execution friction ~25 bps vs modeled 14 bps
- Fees exceed per-trade risk by 2.55x at current sizing
- No walk-forward validation → overfitting risk

### 2a — Limit Order Infrastructure (Week 3-4)

**TP/SL as Limit Orders:**
```python
# Current: market order on TP/SL hit
# New: place limit order at TP price, fallback to market after 30s
async def close_position_smart(position, target_price, urgency):
    if urgency == "low":  # TP1, TP2
        # Place limit order at target price
        order = await place_limit_order(target_price, side="close")
        await asyncio.sleep(30)
        if not order.filled:
            await cancel_and_market_close(order)
    elif urgency == "high":  # SL, circuit breaker
        await market_close(position)  # Immediate market order
```

**Expected savings:** 5-10 bps per close = $25-50 per trade on $50k account.

**Maker Fee Capture for Entries:**
```
Current: Taker entry (4 bps cost)
New: Post-only limit order at mid-price (−1.5 bps rebate)
Savings: 5.5 bps per entry = $27.50 per trade on $50k notional
Combined savings: 10-15 bps per round trip
```

### 2b — Walk-Forward Validation Framework (Weeks 5-6)

**Architecture:**
```
Data partition:
├── Training window:   [T-90 days : T-14 days]  (76 days)
├── Validation window: [T-14 days : T-7 days]   (7 days)
└── Test window:       [T-7 days : T]            (7 days, UNTOUCHED)

Schedule:
- Retrain weekly (Sunday night)
- Validate daily (compare predicted vs actual WR)
- Test monthly (evaluate out-of-sample Sharpe)
```

**What gets validated:**
- Strategy weights (rolling_weights)
- EV deflation ratios
- Regime-aware min_votes table
- Kelly fraction per strategy
- Confidence scorer historical WR

**Significance testing:**
```python
# After N trades, test if observed WR > breakeven WR at p<0.05
from scipy.stats import binom_test
p_value = binom_test(wins, n=total_trades, p=breakeven_wr, alternative='greater')
if p_value < 0.05:
    log("Edge confirmed at 95% confidence")
else:
    log(f"Edge NOT confirmed (p={p_value:.3f}), need more trades")
```

**Convergence requirements:**
- 300 trades → Sharpe estimate stabilizes (±0.2)
- 1,000 trades → Win rate converges (±3%)
- At 50 trades/day: **6 days to stabilize Sharpe, 20 days to confirm WR**

### 2c — Realistic Backtesting Engine (Weeks 7-8)

**Current gaps → fixes:**

| Gap | Fix |
|-----|-----|
| Instant fills | Add fill delay (1-3 candles based on liquidity) |
| Fixed slippage (3 bps) | Dynamic slippage = f(order_size / book_depth) |
| No market impact | Impact model: 0.1 × sqrt(notional / ADV) |
| Same data for train+test | Proper holdout with walk-forward |
| No regime stratification | Report results per regime separately |

**Monte Carlo parameter sensitivity:**
```python
# Vary each parameter ±20% and measure PnL impact
params_to_test = ['sl_atr_multiplier', 'min_signal_rr', 'min_signal_ev',
                  'ensemble_confidence_floor', 'risk_per_trade']
for param in params_to_test:
    for mult in [0.8, 0.9, 1.0, 1.1, 1.2]:
        run_backtest(param=default * mult)
        record(param, mult, sharpe, max_dd, trade_count)
```

---

## Phase 3: Portfolio Construction & Risk Intelligence
**Timeline: Weeks 5-10 | Impact: VERY HIGH | Effort: HIGH**

### Problem
- Flat 0.5% risk per trade (not volatility-adjusted)
- No risk parity (all positions sized equally in dollar terms)
- No portfolio-level Sharpe optimization
- Correlation gate is binary (reject/reduce), not continuous

### 3a — Volatility-Targeted Sizing (Weeks 5-6)

**Current:**
```python
qty = (equity * risk_per_trade * risk_mult) / (stop_width * leverage)
# Same 0.5% risk regardless of realized volatility
```

**New: Volatility-normalized sizing:**
```python
# Target: each position contributes equal VOLATILITY to portfolio
target_position_vol = 0.10 / sqrt(max_positions)  # 10% annual target / sqrt(8)
realized_vol = ewma_volatility(symbol, lookback=72h)
position_size = target_position_vol / realized_vol

# High vol symbol (DOGE, 80% annualized) → small position
# Low vol symbol (BTC, 40% annualized) → larger position
```

**Integration point:** `execution/risk.py:calculate_qty()` — multiply base size by vol-normalization factor.

### 3b — Real-Time Correlation Matrix (Weeks 5-6)

**Current:** Pearson correlation, 72h lookback, binary thresholds.

**New: Dynamic Correlation-Aware Portfolio:**
```python
class PortfolioRiskEngine:
    def compute_portfolio_var(self, positions):
        """Compute portfolio VaR using current correlation matrix."""
        cov_matrix = self.get_ewma_covariance(lookback=72)
        weights = [pos.notional / total_notional for pos in positions]
        portfolio_var = sqrt(weights.T @ cov_matrix @ weights)
        return portfolio_var

    def marginal_risk_contribution(self, new_position, existing_positions):
        """How much risk does adding this position contribute?"""
        var_before = self.compute_portfolio_var(existing_positions)
        var_after = self.compute_portfolio_var(existing_positions + [new_position])
        return var_after - var_before

    def should_add_position(self, new_pos, existing):
        """Only add if marginal risk < risk budget."""
        marginal = self.marginal_risk_contribution(new_pos, existing)
        budget_remaining = self.target_portfolio_var - self.compute_portfolio_var(existing)
        return marginal <= budget_remaining
```

**Integration point:** `core/signal_pipeline.py` Gate 4 — replace binary correlation check with marginal VaR check.

### 3c — Kelly Criterion Integration (Weeks 7-8)

**Current:** Half-Kelly per-strategy with 30-trade lookback. Not setup-specific.

**New: Setup-Specific Kelly:**
```python
# Track edge per (strategy, regime, symbol, signal_type) tuple
# Example: "bollinger_squeeze + squeeze_breakout + trending_bull + BTC"
#   → observed: 62% WR, 1.8 payoff ratio
#   → Kelly f* = (0.62 * 1.8 - 0.38) / 1.8 = 0.408
#   → Half-Kelly: 20.4% of bankroll
#   → Actual allocation: min(risk_per_trade, half_kelly * scaling)

class SetupKelly:
    def get_optimal_fraction(self, strategy, regime, symbol, signal_type):
        key = (strategy, regime, symbol, signal_type)
        stats = self.setup_stats.get(key)
        if not stats or stats.trials < 10:
            return self.default_fraction  # Bayesian prior
        wr = stats.wins / stats.trials
        pr = stats.avg_win / stats.avg_loss
        kelly = (wr * pr - (1 - wr)) / pr
        return max(0, kelly * 0.5)  # Half-Kelly, floor at 0
```

**Integration point:** `execution/risk.py:calculate_qty()` — replace flat `risk_per_trade` with Kelly-derived fraction when sufficient data exists.

### 3d — Inverse-Variance Signal Combination (Weeks 9-10)

**Current:** Majority voting with confidence-weighted win probability deflation.

**New: IC-Weighted Combination:**
```python
# Information Coefficient = correlation between predicted and actual returns
# Weight each strategy by IC^2 / turnover (Sharpe-optimal)

class ICWeightedEnsemble:
    def compute_strategy_weight(self, strategy_name):
        ic = self.information_coefficients[strategy_name]  # Rolling 100-trade IC
        turnover = self.strategy_turnover[strategy_name]    # Avg trades/day
        if turnover == 0:
            return 0
        # Grinold-Kahn fundamental law: IR = IC * sqrt(breadth)
        # Weight proportional to IR^2
        ir_squared = (ic ** 2) * turnover
        return ir_squared

    def combine_signals(self, signals):
        weights = {s.strategy: self.compute_strategy_weight(s.strategy) for s in signals}
        total_weight = sum(weights.values())
        if total_weight == 0:
            return None  # No strategies have edge
        # Weighted average confidence
        combined_conf = sum(s.confidence * weights[s.strategy] for s in signals) / total_weight
        return combined_conf
```

**Integration point:** `strategies/ensemble.py` — add as alternative to `weighted_veto` mode. Configure via `ENSEMBLE_MODE=ic_weighted`.

---

## Phase 4: LLM-Quant Hybrid Architecture
**Timeline: Weeks 8-14 | Impact: MEDIUM-HIGH | Effort: HIGH**

### Problem
- LLM acts as decision-maker (discretionary), not feature-generator (quantitative)
- No statistical significance testing on LLM decisions
- Cost: $50-600/month with uncertain alpha attribution
- 1-5s latency is acceptable for swing trades but limits strategy universe

### 4a — LLM A/B Testing Framework (Weeks 8-9)

**Architecture:**
```python
class LLMAlphaTest:
    """Random 50/50 split: LLM-enhanced vs pure-quant decisions."""

    def should_use_llm(self, signal_id: str) -> bool:
        # Deterministic hash for reproducibility
        return hash(signal_id) % 2 == 0

    def record_outcome(self, signal_id, used_llm, pnl, holding_period):
        group = "llm" if used_llm else "quant_only"
        self.results[group].append({
            'pnl': pnl,
            'holding_period': holding_period,
            'timestamp': time.time()
        })

    def compute_alpha_attribution(self):
        llm_sharpe = sharpe(self.results['llm'])
        quant_sharpe = sharpe(self.results['quant_only'])
        p_value = ttest_ind(
            [r['pnl'] for r in self.results['llm']],
            [r['pnl'] for r in self.results['quant_only']]
        ).pvalue
        return {
            'llm_sharpe': llm_sharpe,
            'quant_sharpe': quant_sharpe,
            'alpha_delta': llm_sharpe - quant_sharpe,
            'p_value': p_value,
            'significant': p_value < 0.05
        }
```

**Decision rule:** After 200 trades per group (400 total, ~8 days):
- If LLM adds Sharpe at p<0.05 → keep LLM, expand usage
- If no significant difference → reduce LLM to veto-only (save costs)
- If LLM hurts Sharpe → disable LLM, pure quant mode

### 4b — LLM as Feature Generator, Not Decision Maker (Weeks 9-10)

**Current flow:**
```
Market data → LLM → "go/skip/flip" decision → execute
```

**New flow:**
```
Market data → LLM → features (regime_prob, sentiment_score, thesis_confidence)
                  ↓
         Statistical model (logistic regression / XGBoost)
                  ↓
         Calibrated probability → Kelly sizing → execute
```

**LLM outputs become features:**
```python
class LLMFeatureExtractor:
    def extract_features(self, market_snapshot) -> dict:
        """LLM produces structured features, not decisions."""
        prompt = """
        Analyze this market data. Output ONLY these fields as JSON:
        - regime_probability: {trend: 0.X, range: 0.X, panic: 0.X}
        - sentiment_score: -1.0 to 1.0
        - thesis_confidence: 0.0 to 1.0
        - key_risk_factors: [list of strings]
        - similar_historical_pattern: string description
        DO NOT make a trade decision.
        """
        response = self.llm_client.call(prompt, market_snapshot)
        return parse_features(response)
```

**Statistical model consumes LLM features + technical features:**
```python
# Features: [adx, rsi, bb_width, macd_hist, llm_sentiment, llm_regime_trend_prob, ...]
# Target: trade_profitable (0/1)
# Model: logistic regression with known calibration
model = LogisticRegression()
model.fit(X_train, y_train)
prob = model.predict_proba(X_new)[0, 1]
# Now we have a CALIBRATED probability with known false-positive rate
```

### 4c — HMM Regime Detection (Weeks 10-12)

**Current:** LLM classifies regime as single string ("trend", "range", etc.)

**New: Hidden Markov Model + LLM hybrid:**
```python
from hmmlearn import GaussianHMM

class HybridRegimeDetector:
    def __init__(self, n_regimes=4):
        self.hmm = GaussianHMM(n_components=n_regimes, covariance_type="full")
        # Regimes: 0=trending, 1=ranging, 2=volatile, 3=crisis

    def fit(self, returns, volumes, spreads):
        """Fit HMM on multi-feature time series."""
        features = np.column_stack([returns, volumes, spreads])
        self.hmm.fit(features)

    def predict_regime(self, current_features):
        """Returns probability distribution over regimes."""
        probs = self.hmm.predict_proba(current_features)
        return {
            'trending': probs[0, 0],
            'ranging': probs[0, 1],
            'volatile': probs[0, 2],
            'crisis': probs[0, 3],
            'transition_matrix': self.hmm.transmat_  # P(next regime | current)
        }

    def blend_with_llm(self, hmm_probs, llm_regime_probs):
        """Bayesian blend: HMM prior + LLM likelihood."""
        blended = {}
        for regime in hmm_probs:
            blended[regime] = hmm_probs[regime] * llm_regime_probs.get(regime, 0.5)
        total = sum(blended.values())
        return {k: v/total for k, v in blended.items()}
```

### 4d — Cost-Optimized LLM Routing (Weeks 12-14)

**Decision tree for when to invoke LLM:**
```
Signal arrives from ensemble
├── 3+ strategies agree, confidence > 75%
│   └── SKIP LLM (signal is obvious, save $0.003)
├── 2 strategies agree, confidence 60-75%
│   └── HAIKU only ($0.0001) — quick regime check
├── 1 strategy, high conviction (80%+)
│   └── SONNET ($0.003) — full thesis + counter-thesis
├── Regime shift detected
│   └── OPUS ($0.015) — deep analysis, rare event
└── No signal, idle
    └── SCOUT agent (Haiku, $0.0001) — watchlist prep
```

**Expected cost savings:** 40-60% reduction from current spend by skipping LLM on obvious signals.

---

## Phase 5: Profitability Validation Protocol
**Timeline: Continuous | The phase that actually matters**

### The Math That Matters

| Metric | Breakeven | Target | Exceptional |
|--------|-----------|--------|-------------|
| Win Rate | 46.4% | 52%+ | 58%+ |
| Sharpe Ratio | 1.0 | 2.0 | 3.0+ |
| Monthly Return | 0% | +5-10% | +15%+ |
| Max Drawdown | <15% | <10% | <5% |
| Trades/Day | 30 | 50 | 100+ |
| Fee Drag (% of edge) | <50% | <25% | <15% |

### 3-Phase Validation Pipeline

**Stage 1: Backtest Validation (1 week)**
```bash
cd bot && python backtest/runner.py --symbols BTC SOL HYPE DOGE FARTCOIN --days 30
```
Must achieve:
- [ ] 100+ trades
- [ ] WR > 47%
- [ ] Sharpe > 1.5
- [ ] Max DD < 12%
- [ ] No single trade loss > 1% equity

**Stage 2: Paper Trading (3 weeks)**
```bash
cd bot && python run.py paper
```
Must achieve over 21 days:
- [ ] 500+ trades
- [ ] WR > 46% (lower bar — real conditions)
- [ ] Sharpe > 1.2
- [ ] Circuit breaker triggered < 3 times
- [ ] Positive cumulative PnL after week 2

**Stage 3: Live Deployment (gradual)**
- Week 1: 10% of capital, monitor only
- Week 2: 25% of capital if Stage 2 metrics hold
- Week 4: 50% of capital
- Week 8: Full capital if Sharpe > 1.5

### Kill Switches
- WR drops below 42% over 100 trades → pause, investigate
- Max DD exceeds 12% → circuit breaker + manual review
- Sharpe drops below 0.8 over 500 trades → reduce to 25% capital
- LLM costs exceed $20/day without proportional alpha → disable LLM

---

## Implementation Priority Matrix

| # | Item | Phase | Impact | Effort | ROI |
|---|------|-------|--------|--------|-----|
| 1 | Activate dormant strategies (funding, OI, CVD) | 1a | HIGH | LOW | **HIGHEST** |
| 2 | Limit TP/SL orders + maker fee capture | 2a | HIGH | MEDIUM | **VERY HIGH** |
| 3 | Volatility-targeted sizing | 3a | HIGH | MEDIUM | **HIGH** |
| 4 | Walk-forward validation framework | 2b | CRITICAL | MEDIUM | **HIGH** |
| 5 | LLM A/B testing framework | 4a | MEDIUM | LOW | **HIGH** |
| 6 | Correlation-aware portfolio construction | 3b | HIGH | HIGH | MEDIUM |
| 7 | New orthogonal signals (funding curve, OB imbalance) | 1b | MEDIUM | MEDIUM | MEDIUM |
| 8 | Factor-weighted ensemble | 1c | MEDIUM | MEDIUM | MEDIUM |
| 9 | Setup-specific Kelly sizing | 3c | MEDIUM | HIGH | MEDIUM |
| 10 | HMM regime detection | 4c | MEDIUM | HIGH | LOW-MEDIUM |
| 11 | IC-weighted signal combination | 3d | MEDIUM | HIGH | LOW-MEDIUM |
| 12 | Symbol expansion (ETH, AVAX, LINK...) | 1 | LOW-MEDIUM | LOW | MEDIUM |
| 13 | Realistic backtesting engine | 2c | MEDIUM | HIGH | LOW |
| 14 | LLM as feature generator | 4b | MEDIUM | HIGH | LOW |

---

## Comparison: Where We Are vs Where We're Going

| Aspect | Current (v1) | After Blueprint (v2) | True Quant Fund |
|--------|-------------|---------------------|-----------------|
| Instruments | 5 crypto | 15-20 crypto | 100+ multi-asset |
| Factors | 1 (momentum) | 4 (momentum, carry, flow, sentiment) | 10+ |
| Daily trades | 6-50 | 50-100 | 500-5000 |
| Signal combination | Majority vote | IC-weighted + factor-balanced | Bayesian optimal |
| Validation | None | Walk-forward weekly | Rolling holdout daily |
| Position sizing | Flat 0.5% | Vol-targeted + setup-Kelly | Portfolio Sharpe optimizer |
| Execution | Market orders | Limit TP/SL + maker capture | TWAP/VWAP + smart routing |
| Risk model | Circuit breakers | Portfolio VaR + marginal risk | Expected shortfall + PCA |
| LLM role | Decision maker | Feature generator + veto | N/A (pure statistical) |
| Projected Sharpe | 1.0-1.5 | 2.0-2.5 | 3.0-6.0 |
| Max Drawdown | 15-20% | 8-12% | 3-8% |

---

## Session 2 Progress: Quant Wiring & Feedback Loops (March 14, 2026)

### Completed Implementations

#### 1. IC Tracker Wired Into Ensemble Voting & Position Sizing
- **Files**: `bot/strategies/ensemble.py`, `bot/multi_strategy_main.py`
- **What**: IC tracker `get_ic_weight()` now multiplies into both ensemble strategy weights AND the compound sizing system
- **Effect**: Inverted factors (IC < 0) get weight 0.0 (killed), decaying factors get 0.0-1.0 linear scale
- **Integration points**:
  - `ensemble._get_strategy_weight()` applies IC weight before voting
  - `multi_strategy_main.py` line ~3230 applies IC weight as compound sizing multiplier
  - IC tracker injected into ensemble at init time via `ensemble.ic_tracker = self.ic_tracker`

#### 2. Kelly Sizing Already Wired (Confirmed)
- **File**: `bot/multi_strategy_main.py` line 3225
- **What**: `kelly_engine.compute_kelly_weight(strategy)` is the first multiplier in the 8-multiplier compound sizing system
- **Status**: Was already wired — no changes needed

#### 3. Missed Trade Tracker (NEW — Full Feedback Loop)
- **New file**: `bot/feedback/missed_trade_tracker.py` (400+ LOC)
- **What**: Comprehensive tracking of EVERY rejected signal with:
  - Full signal context (symbol, side, confidence, strategies, regime, EV)
  - Rejection classification into 18 categories (fee_drag, circuit_breaker, correlation_cluster, etc.)
  - **Counterfactual analysis**: What WOULD have happened (price after 1h/4h/8h, would TP1/SL hit)
  - **Missed alpha calculation**: How much profit each gate cost us
  - **Gate effectiveness**: % of rejections that were correct (saved us from losses)
  - **Top missed opportunities**: Biggest winners we blocked
- **Integration**: Wired into `backtest/engine.py` at 3 rejection points:
  - Risk filter chain rejections (line ~1387)
  - Regime-blocked signals (lines ~675, ~689)
  - Backtest report includes `missed_trades` and `gate_effectiveness` sections
- **Report output**: New sections in backtest report showing per-category breakdown, gate accuracy, and top missed opportunities

#### 4. Auto-Decay for Strategy Weights
- **File**: `bot/multi_strategy_main.py` line ~1272
- **What**: Daily decay (alpha=0.9) applied automatically during daily report generation
- **Effect**: Old trade outcomes gradually lose influence, preventing stale data from dominating

### Quant Infrastructure Audit Summary

| Component | LOC | Status | Wired? | Gap |
|-----------|-----|--------|--------|-----|
| IC Tracker | 286 | Full | **YES** (now) | Was dead code — now wired into voting + sizing |
| Kelly Engine | 276 | Full | YES | Already wired into compound sizing |
| Strategy Weights | 220 | Full | YES | Auto-decay now added |
| Correlation Gate | 341 | Full | YES | Active in signal pipeline |
| Walk-Forward (BT) | 343 | Full | YES | Backtest-only |
| Walk-Forward (Live) | 205 | Full | Partial | Not continuously monitored |
| Portfolio Risk | 1134 | Full | **YES** | Budget utilization → compound sizing multiplier |
| Quant Analytics | 576 | Full | Partial | Backtest-only |
| Deployment Gate | 204 | Full | YES | One-time check |
| Missed Trade Tracker | 400+ | **NEW** | **YES** | Comprehensive feedback loop |

### Backtest Accuracy Gaps Identified

1. **TP fill optimism**: TP exits assume no slippage (limit fill), SL exits add slippage (market) — asymmetric
2. **No liquidation enforcement**: Positions can go past liquidation in backtest without being force-closed
3. **Funding rate fixed**: Uses 0.01%/8h fixed vs live variable 0.005-0.05%
4. **No gap handling**: No detection of overnight/weekend price gaps
5. **Stale MTM prices**: Multi-symbol equity calc uses up to 1h stale prices for inactive symbols
6. **No market impact**: Slippage is fixed 3 bps regardless of position size

### Session 3 Progress (Swarm Findings + Deep Wiring)

**Swarm Audit Results** — 6 agents analyzed the codebase. Key findings:
- Kelly engine IS wired (confirmed, not dead code as initially reported)
- Compound sizing IS active via `_compound_mult` (8-multiplier system)
- Time stops ARE enforced in position_manager.py (8h default)
- Trade ledger WAS recording empty compound_size_multiplier (fixed)
- Portfolio risk budget WAS computed but NOT a sizing multiplier (fixed)
- Missed trade tracker WAS only in backtest engine (fixed: now in ensemble too)

**Changes Implemented:**
1. **Portfolio risk budget → compound sizing** (`multi_strategy_main.py:3263-3283`)
   - `compute_risk_budget()` now feeds into `_compound_mult`
   - Linear scale: 1.0× at 50% budget utilization → 0.2× at 100%
   - Prevents overleveraging as portfolio fills up
2. **Trade ledger attribution fix** (`multi_strategy_main.py:1944`)
   - `compound_size_multiplier` now records actual `_compound_mult` value (was `""`)
   - `_compound_mult_cache` dict stores per-symbol at entry, pops at close
3. **Missed trade tracker → ensemble wiring** (`ensemble.py:728-736, 401, 428, 1118, 1141, 1163`)
   - All 6 ensemble rejection paths now record to MissedTradeTracker:
     - Low volume/chop filter
     - 4h regime conflict
     - Insufficient votes
     - Losing combo blocked
     - Opposition veto (weighted)
     - Confidence floor / graduated rules / trend alignment (via `_record_counterfactual`)
4. **MissedTradeTracker bug fix** (`missed_trade_tracker.py:376`)
   - Fixed unhashable dataclass in set comprehension
5. **11 new tests** (`tests/test_quant_session2.py`)
   - MissedTradeTracker: record, ensemble rejection, counterfactual, report, gate effectiveness
   - Ensemble wiring: tracker injection, counterfactual delegation
   - Portfolio risk budget: math verification at 50%/80%/100% utilization
   - Compound mult cache: store/retrieve/pop lifecycle

### Session 3b: Profitability Improvements (Swarm Agent Findings)

**Source**: Profitability swarm agent identified 10 issues with +15-30% total uplift potential.

**Changes Implemented:**
1. **Fee-drag gate tightened: 30% → 20%/25%** (`signal_pipeline.py:102, 370`)
   - 2-agree signals: max 20% fee drag (was 30%)
   - 3+ agree signals: max 25% fee drag (higher WR compensates)
   - Eliminates negative-EV trades that were slipping through

2. **Consensus multiplier: regime-aware exponential** (`ensemble.py:1288-1305`)
   - Old: flat 1.03x per additional strategy (linear)
   - New: regime-dependent lookup table:
     - Consolidation 3-agree: 1.18x (was 1.06x) — 86% empirical WR justifies
     - Trending 3-agree: 1.14x — strong edge confirmed
     - High-vol 3-agree: 1.04x — low confidence in regime
     - Range/panic: minimal bonus (1.03-1.06x)

3. **Win probability deflation: regime-calibrated** (`ensemble.py:1389-1410`)
   - Old: flat per agreement level (0.65 for 2-agree, 0.82 for 3-agree)
   - New: 4×6 regime lookup table:
     - Trending bull 2-agree: 0.75 (was 0.72) — empirical 58% WR supports
     - High-vol 2-agree: 0.60 (was 0.65) — tighter deflation in unreliable regime
     - Panic 1-agree: 0.35 (was 0.50) — extreme deflation prevents FOMO

4. **Early exit: regime-adaptive** (`position_manager.py:364-423`)
   - Old: fixed 65% SL progress + all 3 conditions required
   - New: regime-dependent thresholds:
     - Panic/high-vol: 35-40% progress, 1 condition (cut fast)
     - Range/consolidation: 45-50% progress, 2 conditions
     - Trending: 70% progress, 3 conditions (let trends breathe)
   - Added 3rd condition: extreme SL progress (>80%) counts as condition

### Session 3c: Strategy Edge Calibration (Swarm Agent Findings)

**Source**: Strategy edge decay swarm agent analyzed all 10 strategies.

**Changes Implemented:**
1. **RSI thresholds crypto-calibrated** across 4 active strategies:
   - `confidence_scorer.py`: 30/70 → 25/75 (extreme zones for scoring)
   - `monte_carlo_zones.py`: 30/70 → 25/75 (deep buy/safe sell zones)
   - `liquidation_cascade.py`: 30/70 → 25/75 (post-cascade reversal)
   - Crypto RSI runs hotter than equities; 30/70 catches noise, 25/75 catches real extremes

2. **Bollinger squeeze bandwalk RSI contradiction fixed** (`bollinger_squeeze.py:273-283`)
   - Old: RSI > 80 during upper bandwalk → REJECT (contradicts bandwalk definition)
   - New: RSI > 85 during bandwalk → +3 confidence (confirms strong trend)
   - Bandwalk = riding the band = RSI naturally extreme. Rejecting defeats the purpose.

3. **Confidence scorer 6h penalty softened** (`confidence_scorer.py:370-380`)
   - Old: -15/-20 penalty when 6h diverges
   - New: -8/-12 penalty (less harsh, keeps more 1h-confirmed signals through)
   - Old penalty killed signals where 1h had genuine edge but 6h was neutral

### Session 3d: Walk-Forward Live Monitoring (Wiring Holes Swarm)

**Source**: Wiring holes swarm agent confirmed IC/Kelly/portfolio risk all wired. Major remaining gap: walk-forward.

**Changes Implemented:**
1. **Walk-forward degradation → compound sizing** (`multi_strategy_main.py`)
   - `_wf_ratio` tracked and recomputed daily from 60-day trade history
   - `_get_wf_multiplier()`: WF >= 0.7 → 1.0×, linear scale to 0.0× at WF = 0
   - Negative WF (overfitting detected) → 0.0× (halt new entries)
   - Wired as 10th compound sizing multiplier (after portfolio risk budget)
   - Warning logged when WF ratio < 0.4 (critical degradation)
2. **5 new tests** for WF multiplier math (strong/degraded/critical/negative/zero)

### Compound Sizing: Complete 10-Multiplier System

| # | Multiplier | Source | Effect |
|---|-----------|--------|--------|
| 1 | Kelly weight | `kelly_engine` | Size up proven strategies, down unproven |
| 2 | IC weight | `ic_tracker` | Kill inverted factors, half-size decaying |
| 3 | Regime scalar | `risk_mgr` | Reduce in bear/chop, maintain in trend |
| 4 | Drawdown dial | `risk_mgr` | Progressive reduction during drawdowns |
| 5 | Vol regime | ATR current/baseline | Inverse volatility sizing |
| 6 | BTC momentum | 1h price change | Alignment with BTC direction |
| 7 | Portfolio budget | `portfolio_risk` | Scale down as budget fills (>50%) |
| 8 | Walk-forward | `_wf_ratio` | Auto-reduce on OOS degradation |
| 9 | Cap/Floor | 0.1×-2.0× | Prevent extreme sizes |
| 10 | Circuit breaker | CB constraints | Override during consecutive losses |

### Session 3e: Regime-Conditional SL/TP + Rolling Sharpe

**Source**: Missing quant mechanics swarm (12 findings). Implemented top priorities.

**Changes Implemented:**
1. **Regime-conditional SL/TP widths** (`trading_config.py`)
   - `REGIME_SL_TP_SCALARS` lookup table: per-regime multipliers on base SL/TP
   - `trending_bull`: 1.2× SL (wider), 0.9×/0.85× TP (let winners run)
   - `high_volatility`: 1.4× SL, 0.7×/0.7× TP (avoid noise stops, quick exits)
   - `panic`: 1.5× SL, 0.6×/0.6× TP (max stop width, fast exits)
   - `consolidation`: 0.85× SL (tighter), 1.2×/1.3× TP (larger targets for breakout)
   - `get_regime_sl_tp()` helper multiplies base × regime scalar
2. **Wired into confidence_scorer** (`confidence_scorer.py`)
   - Replaces hardcoded `K * A` with `get_regime_sl_tp()` output
3. **Wired into regime_trend** (`regime_trend.py`)
   - Replaces hardcoded `2.0 * R` / `4.0 * R` TP targets
   - SL also regime-adjusted via `_sl_mult`
4. **Rolling Sharpe tracker** (`multi_strategy_main.py`)
   - Daily computation from trade ledger (30-day window)
   - Warnings on negative Sharpe, info log on low Sharpe (<0.5)
   - Foundation for auto-reducing position sizes on Sharpe degradation
5. **4 new tests**: default/trending/panic regime SL/TP, unknown regime passthrough

### Session 3f: Regime Slippage, Signal Decay Sizing, Agreement Sizing

**Source**: Background swarm agents (signal pipeline, position manager, data fetcher audits).

**Changes Implemented:**
1. **Regime-specific slippage in EV calculation** (`ensemble.py`)
   - `_REGIME_SLIPPAGE_BPS` table: trending=1bps, panic=6bps, high_vol=4bps
   - Slippage added to fee_drag in EV formula: `total_cost = fees × 2 + slippage`
   - Prevents entries where execution costs eat the edge in volatile conditions
2. **Regime-specific slippage in signal pipeline** (`signal_pipeline.py`)
   - Same slippage table applied to both `evaluate()` and `evaluate_annotated()` fee-drag gates
   - Ensures consistent cost modeling between ensemble and pipeline
3. **Half-size for 1-agree trades** (`multi_strategy_main.py`)
   - Compound sizing multiplier applies 0.5× when `num_agree == 1`
   - Was documented/commented but never actually wired in
4. **Signal decay → compound sizing** (`multi_strategy_main.py`)
   - Stale signals get reduced position size (not just lower confidence)
   - Uses `compute_signal_decay()` with 5× decay window for gradual reduction
   - This is the 11th compound sizing multiplier

### Compound Sizing: Complete 11-Multiplier System (Updated)

| # | Multiplier | Source | Effect |
|---|-----------|--------|--------|
| 1 | Kelly weight | `kelly_engine` | Size up proven strategies, down unproven |
| 2 | IC weight | `ic_tracker` | Kill inverted factors, half-size decaying |
| 3 | Regime scalar | `risk_mgr` | Reduce in bear/chop, maintain in trend |
| 4 | Drawdown dial | `risk_mgr` | Progressive reduction during drawdowns |
| 5 | Vol regime | ATR current/baseline | Inverse volatility sizing |
| 6 | BTC momentum | 1h price change | Alignment with BTC direction |
| 7 | Portfolio budget | `portfolio_risk` | Scale down as budget fills (>50%) |
| 8 | Signal decay | `compute_signal_decay` | Reduce size for stale signals |
| 9 | Agreement level | `num_agree` | Half-size for 1-agree cherry-picks |
| 10 | Walk-forward | `_wf_ratio` | Auto-reduce on OOS degradation |
| 11 | Cap/Floor | 0.1×-2.0× | Prevent extreme sizes |

### Session 3g: EV Formula Fix + Calibration Tracking

**Source**: Deep EV audit agent (10 critical findings). Implemented top 3.

**Changes Implemented:**
1. **Partial-close-aware EV formula** (`ensemble.py`)
   - Old formula assumed 100% closes at TP1 (systematically underestimated true edge)
   - New formula: 60% closes at TP1, 45% of remainder reaches TP2, rest at ~breakeven
   - `EV = p_win × [0.6 × (rr1 - fee) + 0.4 × 0.45 × (rr2 - fee) + 0.4 × 0.55 × (-fee/2)] - p_loss × (1 + fee)`
   - This corrects the single biggest source of false EV rejections
2. **EV vs realized outcome tracking** (`multi_strategy_main.py`)
   - Trade ledger now records: `predicted_ev`, `realized_rr`, `win` flag
   - Enables post-hoc calibration: predicted vs actual WR by agreement/regime
   - Foundation for adaptive deflation factor recalibration
3. **Entry reasons now store EV data** (`multi_strategy_main.py`)
   - `ev_per_dollar`, `win_prob_deflated`, `fee_drag_pct` in entry_reasons
   - Available at close time for calibration tracking
4. **Ensemble metadata expanded** (`ensemble.py`)
   - Now includes `win_prob`, `rr_tp2` for downstream analysis

### Session 3h: Pipeline Rejection Tracking

**Source**: Missed trade design agent (16 rejection gates identified).

**Changes Implemented:**
1. **MissedTradeTracker wired into main loop** (`multi_strategy_main.py`)
   - Initialized at startup alongside IC tracker, Kelly engine, trade ledger
   - Wired into ensemble via `set_missed_trade_tracker()`
2. **Pipeline rejections now tracked** (`multi_strategy_main.py`)
   - All `RiskFilterChain.evaluate()` rejections recorded with `gate="pipeline"`
   - Covers: fee drag, EV floor, circuit breaker, leverage, correlation, liquidation
3. **RiskFilterChain gains tracker API** (`signal_pipeline.py`)
   - `set_missed_trade_tracker()` and `_track_pipeline_rejection()` methods
4. **1 new test** for pipeline rejection tracking

### Still Pending

- [ ] Wire rebalance suggestions into exit intelligence (currently computed but ignored)
- [ ] Seed signal quality from backtest before paper trading
- [ ] Auto-reduce sizing when rolling Sharpe < 0 for 3+ consecutive days
- [ ] ATR multiplier sweep for BTC-specific optimization
- [ ] Graduated correlation size reduction (continuous vs binary 0.85 threshold)
- [ ] Empirically validate win_prob deflation factors from trade data
- [ ] Add funding cost model to EV calculation (estimated hold time × rate)

---

## Session 4: HYPE Alpha Unlock — 5→9 Strategies + HYPE Tuning (March 14, 2026)

### Context & Problem
70-day backtest baseline: 51 trades, 47.1% WR, -$10,196 net, 0.55x PF.
- **BTC**: 18 trades, 67% WR, +$440 — solid
- **SOL**: 12 trades, 17% WR, -$6,242 — terrible
- **HYPE**: 21 trades, 48% WR, -$3,571 — edge suppressed
- **Consolidation**: 34 trades, 35% WR, -$12,178 — the 30-day "78% WR" was noise
- Only 5 of 11 strategies were active. 2-agree dominated (40/51) at 0.45x PF.

### Root Cause Analysis (3 audit agents deployed)

**Strategy Arsenal Problem**: Only 5 strategies active (regime_trend, confidence_scorer, bollinger_squeeze, vmc_cipher, probability_engine). 6 were disabled:
- liquidation_cascade: works with OHLCV proxy, no API needed — **should be enabled**
- monte_carlo_zones: fully implemented — **should be enabled**
- funding_rate: fetcher exists but data not injected into strategy dict — **wiring gap**
- oi_delta: needs OI fetch method — **needs implementation**
- multi_tier_quality: PF 0.82, -$1,223 — rightfully disabled
- lead_lag: 0% WR — rightfully disabled

**HYPE-Specific Suppression**:
1. HYPE risk_tier was "medium" but volatility_profile was "high" — **mismatch bug**
2. high_volatility regime only allowed 2 strategies — too few for min_votes=2
3. Confidence floor climbed to 93% for HYPE — unreachable for a naturally choppy asset
4. high_volatility R:R scalars were INVERTED: tp1=0.7, tp2=0.7 on sl=1.4 — **same bug as trending**

### Changes Implemented (13 files, 227 insertions, 67 deletions)

#### Phase 1: Enable Strategies (5 → 9)
1. **liquidation_cascade** — enabled by default in backtest (was `false`)
2. **monte_carlo_zones** — enabled by default (was `false`)
3. **funding_rate** — enabled + data wired:
   - Cached funding rate now injected into `data["_funding_rate"]` and `data["_meta"]["funding_rate"]`
   - Was fetched but never passed to strategies (`multi_strategy_main.py:1661`)
4. **oi_delta** — enabled + data wired:
   - New `fetch_open_interest()` method in `data/fetcher.py` (CCXT)
   - OI current + previous cached and injected into `data["_meta"]`
   - OI threshold raised 3%→5% (audit: 3% catches noise on large markets)
5. **multi_tier_quality** — flipped to `false` in backtest (was `true`, PF 0.82)

**Regime allowlists expanded** (`ensemble.py:163-174`):
- `trending_bear`: +oi_delta, +liquidation_cascade
- `trending_bull`: +oi_delta
- `trend`: +oi_delta
- `consolidation`: +monte_carlo_zones, +funding_rate
- `range`: +monte_carlo_zones, +funding_rate
- `high_volatility`: +bollinger_squeeze, +liquidation_cascade, +oi_delta (2→5 strategies)
- `panic`: +liquidation_cascade
- `unknown`: +monte_carlo_zones

#### Phase 2: Ensemble Voting Adjustment
**min_votes raised from 2 → 3** for most regimes (with 9 strategies, 2/9=22% agreement was too weak):
- trending_bull/bear/trend/consolidation/range/panic/unknown: all 3
- **high_volatility stays at 2** (only 5 strategies allowed, 2/5=40% is adequate)

#### Phase 3: HYPE Bug Fixes
1. **risk_tier "medium"→"high"** in DEFAULT_SYMBOLS (was inconsistent with overrides)
2. **high_vol R:R inversion fixed**: `{sl:1.4, tp1:0.7, tp2:0.7}` → `{sl:1.4, tp1:1.2, tp2:2.0}`
3. **Confidence floor capping** — new `set_symbol_volatility_profiles()` method:
   - BTC (low vol): max floor 93% (unchanged)
   - SOL (medium vol): max floor 90%
   - HYPE (high vol): max floor 85%
4. **Regime risk multipliers adjusted**:
   - high_volatility: 0.5→0.7 (less punitive for HYPE)
   - consolidation: 1.3→1.0 (70-day showed 35% WR, not 78%)

#### Phase 4: HYPE-Tuned Strategy Parameters
1. **VMC Cipher** — WT zones relaxed ±60→±55 for high-vol symbols only
2. **Probability Engine** — tighter thresholds for high-vol: MIN_PROB 0.45→0.48, MIN_EV 0.15→0.18
3. **Bollinger Squeeze** — 5-bar squeeze minimum (vs 3) for high-vol; TP2 5→6 ATR for breakouts

#### Phase 5: LLM Layer Fixes
1. **normalizers.py** — updated hardcoded strategy list (added 4 new, removed dead entries)
2. **shared_context.py** — STRATEGY_THEORY entries for all 9 active strategies
3. **shared_context.py** — STRATEGY_CONFLUENCE pairs for new strategy combinations

#### Phase 6: Reporting & Cosmetic
1. **"llm_vetoed" → "other_rejections"** in backtest funnel output (no LLM in standard backtest)
2. **runner.py** — updated signal funnel key for new name

### Audit Corrections Applied
Three audit agents validated the plan and caught errors:
- **Slippage kept at 4 bps** (audit: spreads widen in high vol, 2 bps would be wrong)
- **VMC zones conservative** (±55 not ±50 — audit found ±50 increases false signals 15-20%)
- **BB Squeeze: structural fix** (longer squeeze bars, not wider multipliers)
- **high_vol R:R properly calibrated** (audit: `{1.4, 1.2, 2.0}` not `{1.5, 1.0, 1.2}`)
- **min_votes=3 critical** (audit: 2-agree at 9 strategies → signal spam + quality drop)

### Tests
All 1308 tests pass after changes.

### What to Validate
Run 70-day backtest and compare against baseline:
```bash
cd bot && python backtest/runner.py --symbols BTC SOL HYPE --days 70
```
Expected improvements:
- More strategy diversity in BY AGREEMENT (3-agree, 4-agree should appear)
- HYPE PnL improves from -$3,571 (wider TPs, more signals, lower confidence floor)
- high_volatility R:R no longer inverted
- "other_rejections" replaces "llm_vetoed" in output

Note: funding_rate and oi_delta return None in backtest (no historical API data) — their impact shows in paper/live only.

---

## Two-Tab Workflow: Walk-Forward + Backtest Improvement

### Tab 1: Walk-Forward Validation (separate session)

**Purpose**: Continuous walk-forward testing to measure out-of-sample generalization.

**Commands**:
```bash
# Quick 7-day walk-forward (fast iteration)
cd bot && python cli.py --mode walkforward --days 7 --symbols BTC SOL HYPE

# Full 70-day walk-forward (comprehensive validation)
cd bot && python cli.py --mode walkforward --days 70 --symbols BTC SOL HYPE

# Gate check (deployment readiness)
cd bot && python cli.py --mode gate --days 30 --symbols BTC SOL HYPE
```

**What to look for**:
- **Overfit Ratio** > 0.5 = strategy generalizes (currently 0.00 = failing)
- **Test Profitable** = YES required for deployment
- **Train WR vs Test WR** — gap > 15% = overfitting
- Walk-forward uses 60d train / 20d test windows by default

**Walk-forward is the most important metric.** A strategy can have great backtest PnL but WF=0 means it won't work in production. Every backtest improvement must be validated here.

**Session startup prompt**:
> I'm running walk-forward validation for the WAGMI trading bot. Run `cd bot && python cli.py --mode walkforward --days 70 --symbols BTC SOL HYPE` and analyze the results. Focus on:
> 1. Overfit ratio (target > 0.5)
> 2. Per-window train vs test WR gap
> 3. Which regimes generalize and which don't
> 4. Whether the 5→9 strategy expansion improved OOS performance
> If WF ratio is still 0, diagnose why and propose fixes.

### Tab 2: Backtest Improvement Pipeline (separate session)

**Purpose**: Iterate on strategy parameters, regime classification, and signal quality to improve profitability.

**Commands**:
```bash
# 70-day backtest (primary benchmark)
cd bot && python backtest/runner.py --symbols BTC SOL HYPE --days 70

# 30-day backtest (faster iteration)
cd bot && python backtest/runner.py --symbols BTC SOL HYPE --days 30

# With learning (pre-seeds signal quality from results)
cd bot && python backtest/runner.py --symbols BTC SOL HYPE --days 70 --learn

# HYPE-only analysis
cd bot && python backtest/runner.py --symbols HYPE --days 70
```

**70-day baseline to beat** (pre-Session 4):
```
Total: 51 | WR: 47.1% | PnL: -$10,196 | PF: 0.55x | DD: 21.7%
BTC: 18 trades, 67% WR, +$440
SOL: 12 trades, 17% WR, -$6,242
HYPE: 21 trades, 48% WR, -$3,571
Consolidation: 34 trades, 35% WR, -$12,178
2-agree: 40 trades, 45% WR, 0.45x PF
3-agree: 11 trades, 55% WR, 0.95x PF
Walk-Forward: ratio=0.00 (FAIL)
```

**Improvement priority order**:
1. **Get 3-agree PF > 1.0** — this is where real edge exists (0.95x is close)
2. **Fix SOL** — 17% WR is active alpha destruction. Consider disabling or special tuning.
3. **Validate HYPE improvements** — wider TPs + more strategies should help
4. **Improve WF ratio** — the critical metric for deployment readiness
5. **Reduce consolidation losses** — 35% WR at 34 trades is the biggest PnL drag

**Session startup prompt**:
> I'm running backtest improvement for the WAGMI trading bot. Current 70-day baseline: 51 trades, 47.1% WR, -$10,196 net. Key problems: consolidation 35% WR (-$12k), SOL 17% WR (-$6.2k), walk-forward ratio 0.00. Run `cd bot && python backtest/runner.py --symbols BTC SOL HYPE --days 70` with the latest code and compare results against the baseline. Analyze per-symbol, per-regime, and per-agreement level. Identify the biggest opportunities for improvement.

---

## Master Improvement Pipeline

```
┌─────────────────┐     ┌──────────────────┐     ┌───────────────────┐
│ Tab 2: Backtest │────▶│ Commit & Push    │────▶│ Tab 1: Walk-Fwd   │
│ Improvement     │     │ Changes          │     │ Validation        │
│                 │     │                  │     │                   │
│ • Run 70d BT    │     │ • git commit     │     │ • Run WF test     │
│ • Analyze gaps  │     │ • git push       │     │ • Check OOS ratio │
│ • Fix params    │     │                  │     │ • Diagnose overfit │
│ • Re-run BT     │     │                  │     │                   │
└─────────────────┘     └──────────────────┘     └───────────────────┘
         ▲                                                │
         │              If WF ratio improves              │
         └────────────────────────────────────────────────┘
         │              If WF ratio fails                 │
         └─── Revert changes, try different approach ─────┘
```

**Decision criteria for each iteration**:
- Backtest PnL improves AND WF ratio improves → **keep changes**
- Backtest PnL improves but WF ratio drops → **overfitting, revert**
- Backtest PnL same but WF ratio improves → **keep, strategy generalizes better**
- Both worse → **revert immediately**

---

## Current System State (Post-Session 4)

### Active Strategies: 9
| # | Strategy | Factor | Regime Allowlists |
|---|----------|--------|-------------------|
| 1 | regime_trend | Momentum | trending_bull/bear, trend |
| 2 | confidence_scorer | Momentum | ALL regimes |
| 3 | bollinger_squeeze | Volatility | trending, consolidation, range, high_vol |
| 4 | vmc_cipher | Multi-oscillator | trending, consolidation, range |
| 5 | probability_engine | Statistical | trending, high_vol, unknown |
| 6 | liquidation_cascade | Microstructure | high_vol, panic, trending_bear |
| 7 | monte_carlo_zones | Mean-reversion | consolidation, range, unknown |
| 8 | funding_rate | Carry | consolidation, range, high_vol |
| 9 | oi_delta | Flow | trending_bull/bear, trend, high_vol |

### Disabled Strategies: 2
- multi_tier_quality (PF 0.82, -$1,223)
- lead_lag (0% WR, -$137/trade)

### Compound Sizing: 11-Multiplier System
| # | Multiplier | Source | Effect |
|---|-----------|--------|--------|
| 1 | Kelly weight | `kelly_engine` | Size up proven strategies, down unproven |
| 2 | IC weight | `ic_tracker` | Kill inverted factors, half-size decaying |
| 3 | Regime scalar | `risk_mgr` | Reduce in bear/chop, maintain in trend |
| 4 | Drawdown dial | `risk_mgr` | Progressive reduction during drawdowns |
| 5 | Vol regime | ATR current/baseline | Inverse volatility sizing |
| 6 | BTC momentum | 1h price change | Alignment with BTC direction |
| 7 | Portfolio budget | `portfolio_risk` | Scale down as budget fills (>50%) |
| 8 | Signal decay | `compute_signal_decay` | Reduce size for stale signals |
| 9 | Agreement level | `num_agree` | Half-size for 1-agree cherry-picks |
| 10 | Walk-forward | `_wf_ratio` | Auto-reduce on OOS degradation |
| 11 | Cap/Floor | 0.1×-2.0× | Prevent extreme sizes |

### Tests: 1308 passing

The blueprint transforms the bot from **"few big conviction bets"** to **"many small diversified edges"** — the core philosophy of quantitative investing. Each phase independently improves the system; together they compound into institutional-grade architecture.
