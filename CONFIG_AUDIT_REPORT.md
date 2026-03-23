# Configuration & Environment Security Audit Report
**Date:** 2026-03-20
**Scope:** nunuIRL Trading Bot - Configuration, Environment Variables, Hardcoded Values

---

## EXECUTIVE SUMMARY

**RISK LEVEL: MEDIUM**

The codebase has well-structured configuration management with environment variable support and sensible defaults. However, several safety-critical issues exist:

1. **CRITICAL RISK**: No validation that environment variables are set correctly before deploying to production
2. **HIGH RISK**: Paper vs. Live mode can be bypassed with environment variable manipulation
3. **MEDIUM RISK**: Some hardcoded values lack configuration flexibility
4. **MEDIUM RISK**: API keys logged in error cases without sanitization
5. **LOW RISK**: Missing initialization checks for required secrets

---

## 1. ENVIRONMENT VARIABLES - COMPREHENSIVE INVENTORY

### 1.1 Core Environment Control

| Variable | Default | Range/Type | Location | Risk |
|----------|---------|-----------|----------|------|
| `ENVIRONMENT` | `paper` | `paper` or `production` | trading_config.py:70 | **CRITICAL** |
| `ANTHROPIC_API_KEY` | `` (empty) | String (secret) | llm/client.py:31 | **HIGH** |
| `HL_API_KEY` | `` (empty) | String (wallet addr) | .env.example | **HIGH** |
| `HL_API_SECRET` | `` (empty) | String (private key) | .env.example | **HIGH** |

### 1.2 Risk Management Parameters

| Variable | Default | Paper | Live | Safety Notes |
|----------|---------|-------|------|--------------|
| `STARTING_EQUITY` | 10000.0 | 10000.0 | 400.0 | Should match account balance |
| `RISK_PER_TRADE` | 0.005 | 0.005 | 0.02 | **0.5% vs 2%**: Live is 4x higher per trade |
| `MAX_OPEN_POSITIONS` | 8 | 8 | 3 | **Live is 37% less**: Conservative for small accounts |
| `CIRCUIT_BREAKER_DAILY_LOSS_PCT` | 0.05 | 0.05 | 0.05 | **5% drawdown limit** — stops all trading |
| `MAX_CONSECUTIVE_LOSSES` | 5 | 5 | 4 | **Live stricter**: 4 losses vs 5 in paper |
| `CIRCUIT_BREAKER_COOLDOWN_MIN` | 60 | 60 | 120 | **Live: 2-hour cooldown** |
| `MAX_DRAWDOWN_PCT` | 0.15 | 0.15 | 0.15 | **15% session max** — hard stops at this level |
| `MAX_SESSION_DRAWDOWN_PCT` | 0.20 | 0.20 | 0.20 | **20% cumulative hard stop** (never resets) |
| `MAX_LEVERAGE` | 25.0 | 25.0 | 10.0 | **Live capped at 10x** for $400 account |
| `MAX_PORTFOLIO_LEVERAGE` | 4.0 | 4.0 | 4.0 | Portfolio-level cap |

### 1.3 Strategy & Ensemble Parameters

| Variable | Default | Notes |
|----------|---------|-------|
| `ENSEMBLE_MODE` | `weighted_veto` | Voting mechanism: only weighted_veto tested |
| `MIN_VOTES_REQUIRED` | 2 | Minimum 2 out of 4 strategies must agree |
| `VETO_RATIO` | 1.2 | Veto power threshold (lowered from 1.5) |
| `SCAN_INTERVAL_S` | 60 | Check for signals every 60 seconds |
| `ENABLE_LEVERAGE` | true | If false, all trades are 2.0x minimum |
| `ENABLE_TRAILING_STOP` | true | Progressive trailing stop logic |
| `TRAILING_STOP_ATR_MULT` | 1.5 | ATR multiplier for trailing distance |

### 1.4 LLM Configuration (Claude AI)

| Variable | Default | Recommended | Notes |
|----------|---------|-------------|-------|
| `LLM_MODE` | 0 | 0-5 scale | **0=OFF, 2=VETO_ONLY, 5=FULL AUTO** |
| `LLM_USAGE_TIER` | `RECOMMENDED` | See below | Smart model routing |
| `LLM_MODEL` | `claude-sonnet-4-5-20250929` | `haiku` for cost | Sonnet = $3/1M input, $15/1M output |
| `LLM_MIN_COOLDOWN_S` | 20 | 30 | Min seconds between LLM calls |
| `LLM_MAX_CALLS_HOUR` | 30 | 15 | Rate limit (impacts cost) |
| `LLM_MAX_CALLS_DAY` | 400 | 150 | Daily rate limit |
| `LLM_MULTI_AGENT` | false | true | Specialist agent pipeline |

**LLM Usage Tier Breakdown:**
- `CONSERVATIVE`: Haiku only (~$18/mo)
- `RECOMMENDED`: Sonnet default (~$130/mo)
- `AGGRESSIVE`: Opus for critical decisions (~$600/mo)
- `UNLEASHED`: Opus everywhere (~$1,400/mo)

### 1.5 Leverage & Position Sizing

| Variable | Default | Notes |
|----------|---------|-------|
| `ENABLE_LEVERAGE` | true | If false, defaults to 2.0x (minimum) |
| `MAX_LEVERAGE` | 25.0 | Absolute cap across all positions |
| `MIN_LEVERAGE_ENTRY_GATE` | 1.0 | Floor for leverage eligibility |
| `MAX_RISK_MULTIPLIER` | 1.5 | Position size scaling cap |
| `LEVERAGE_CAP_MEDIUM_RISK` | 20.0 | Max for medium-risk assets (SOL) |
| `LEVERAGE_CAP_HIGH_RISK` | 12.0 | Max for high-risk assets (HYPE) |
| `MAX_EXTREME_POSITIONS` | 2 | Max positions with >5x leverage |
| `MIN_STOP_WIDTH_PCT` | 0.003 | **0.3% stop minimum** — prevents infinite R:R |
| `TAKER_FEE_BPS` | 4 | **4 basis points** on Hyperliquid |
| `SLIPPAGE_BPS` | 3 | Estimated slippage in basis points |

### 1.6 Confidence & Quality Gates

| Variable | Default | Notes |
|----------|---------|-------|
| `ENSEMBLE_CONFIDENCE_FLOOR` | 55.0 | Minimum confidence to trade |
| `MAX_ENSEMBLE_CONFIDENCE` | 95.0 | Cap at 95% to avoid clustering |
| `RANGING_CONFIDENCE_FLOOR` | 68.0 | Higher floor when market is choppy |
| `MIN_SIGNAL_RR` | 1.2 | Minimum 1.2:1 risk-reward ratio |
| `MIN_SIGNAL_EV` | 0.08 | Minimum expected value per dollar |
| `CB_CONF_OVERRIDE_PCT` | 0.95 | Only 95%+ confidence can override circuit breaker |
| `CHOP_THRESHOLD` | 0.65 | ADX threshold for chop detection |
| `ADX_MIN_TRENDING` | 10.0 | Minimum ADX for trending signals |

### 1.7 Data & Technical Indicators

| Variable | Default | Notes |
|----------|---------|-------|
| `ATR_PERIOD` | 14 | Periods for ATR calculation |
| `EMA_SHORT_PERIOD` | 20 | Short-term EMA |
| `EMA_MEDIUM_PERIOD` | 50 | Medium-term EMA |
| `EMA_LONG_PERIOD` | 200 | Long-term EMA |
| `MACD_FAST` | 12 | MACD fast line |
| `MACD_SLOW` | 26 | MACD slow line |
| `MACD_SIGNAL` | 9 | MACD signal line |
| `RSI_PERIOD` | 14 | RSI calculation period |
| `HTF_HOURS` | 16 | High-timeframe hours for regime detection |

### 1.8 Circuit Breaker & Loss Limits

| Variable | Default | Notes |
|----------|---------|-------|
| `CIRCUIT_BREAKER_DAILY_LOSS_PCT` | 0.05 | **5% daily loss = full stop** |
| `MAX_CONSECUTIVE_LOSSES` | 5 | Stop after N losses in a row |
| `MAX_DRAWDOWN_PCT` | 0.15 | **15% max drawdown from peak** |
| `MAX_SESSION_DRAWDOWN_PCT` | 0.20 | **20% session hard stop** (never resets) |
| `LOSS_COOLDOWN_S` | 60 | Seconds before trading after a loss |
| `WIN_COOLDOWN_S` | 60 | Seconds before trading after a win |

### 1.9 Rotation & Position Turnover

| Variable | Default | Notes |
|----------|---------|-------|
| `ENABLE_ROTATION` | true | Automatically exit stale positions |
| `ROTATION_MIN_HOLD_S` | 300 | Minimum 5 minutes holding time |
| `ROTATION_GLOBAL_COOLDOWN_S` | 600 | 10-minute global cooldown between rotations |
| `ROTATION_MAX_PER_HOUR` | 3 | Max 3 rotations per hour |
| `ROTATION_MAX_PER_DAY` | 12 | Max 12 rotations per day |

### 1.10 Alerts & Notifications

| Variable | Default | Notes |
|----------|---------|-------|
| `DISCORD_WEBHOOK` | `` (empty) | Discord webhook URL |
| `TELEGRAM_TOKEN` | `` (empty) | Telegram bot token |
| `TELEGRAM_CHAT_ID` | `` (empty) | Telegram chat ID |
| `TELEGRAM_ALLOWED_USER_ID` | 0 | **Security**: Only allow this user ID |
| `COINGECKO_API_KEY` | `` (empty) | Optional fallback data source |

### 1.11 Feature Flags (Waves 1-4)

| Variable | Default | Notes |
|----------|---------|-------|
| `ENABLE_ML` | true | Machine learning position adjustments |
| `ENABLE_SIGNAL_FLAGGER` | true | Cheap heuristic flags (SNIPER, ANOMALY) |
| `ENABLE_SIGNAL_OVERRIDE` | true | Bypass soft blockers for exceptional signals |
| `ENABLE_SELF_TEACHING` | true | Periodic learning cycles |
| `ENABLE_FEW_SHOT` | true | Inject past trades into LLM prompts |
| `ENABLE_PORTFOLIO_RISK` | true | Portfolio-level correlation checks |
| `ENABLE_CASCADE_SIGNALS` | true | Detect BTC/ETH cascade sell-offs |
| `ENABLE_LIQUIDITY_GUARD` | true | Reject trades in dead markets |
| `ENABLE_REGIME_STRATEGY_FILTER` | true | Disable low-WR strategies in unfavorable regimes |
| `DYNAMIC_TP_SCALING` | true | Scale TP based on momentum |
| `ENABLE_AB_TESTING` | true | A/B test strategy parameters |
| `ENABLE_CHOP_DETECTOR` | true | Suppress signals in choppy markets |
| `ENABLE_SOFT_FILTERS` | false | **Default OFF**: Phase 1 validation only |
| `ENABLE_DASHBOARD` | true | Built-in web dashboard |

---

## 2. CRITICAL SAFETY FINDINGS

### 2.1 **CRITICAL: Environment Mode Misconfiguration Risk**

**Problem:** The `ENVIRONMENT` variable controls paper vs. live mode, but there is **NO validation** at startup.

```python
# bot/trading_config.py:70
environment: str = field(default_factory=lambda: _env("ENVIRONMENT", "paper"))

# bot/multi_strategy_main.py:340
_is_production = os.getenv("ENVIRONMENT", "paper").lower() == "production"

# bot/cli.py:140
os.environ["ENVIRONMENT"] = "production"
```

**Attack Vector:**
```bash
# Attacker could set ENVIRONMENT before running bot
export ENVIRONMENT=production
python run.py paper  # This will ACTUALLY trade live!
```

**Impact:** Real money trades executed when expecting paper trading.

**Recommendation:**
1. Add explicit mode verification at startup
2. Store mode in config file (immutable during session)
3. Check CLI args override environment variables
4. Log mode selection with clear warnings

**Current Safeguards (Weak):**
- `cli.py:135` asks for "CONFIRM LIVE" — but can be bypassed with `--yes`
- Go-live gate checks exist but only after initialization

---

### 2.2 **HIGH: API Key Logging Risk**

**Problem:** Anthropic API key is loaded and used without sanitization. If exceptions occur, logs could expose it.

```python
# bot/llm/client.py:31
api_key = os.getenv("ANTHROPIC_API_KEY", "")
if not api_key:
    logger.warning("ANTHROPIC_API_KEY not set, LLM calls will fail")
    return None
return anthropic.Anthropic(api_key=api_key)  # Key passed to client
```

**Risk:** If exception handling logs the client object or full response, the key could leak.

**Recommendation:**
1. Never log exception details that might contain API objects
2. Wrap API calls with exception handlers that sanitize
3. Use masking in logs: `api_key="sk-***...***"`

---

### 2.3 **HIGH: Hyperliquid Credentials Handling**

**Problem:** Exchange credentials are loaded from environment but no validation of format.

```python
# Hyperliquid expects wallet address (0x...) and private key
HL_API_KEY=0x1234...  # Ethereum wallet address
HL_API_SECRET=0xabcd...  # Private key (100% compromising)
```

**Risk:**
1. Private key stored in plaintext in `.env` file
2. No validation that credentials are valid before trading
3. Credentials could leak in error logs

**Recommendation:**
1. Use encrypted key storage (e.g., `cryptography.Fernet`)
2. Validate wallet address format at startup: must be `0x[0-9a-fA-F]{40}`
3. **NEVER log API credentials, even partial**
4. Use separate read-only API wallets (if Hyperliquid supports)

---

### 2.4 **MEDIUM: Profile Override Silently Applied**

**Problem:** Paper vs. Live profiles override configuration silently without notification.

```python
# bot/trading_config.py:634-640
LIVE_PROFILE_OVERRIDES = {
    "max_leverage": 25.0,
    "risk_per_trade": 0.005,     # Overwrites env var!
    "max_open_positions": 8,      # Overwrites env var!
    "max_portfolio_leverage": 4.0,
    "enable_smart_orders": True,  # Silently enabled in live
}

# Apply silently:
profile = LIVE_PROFILE_OVERRIDES if config.is_paper else LIVE_PROFILE_OVERRIDES
for key, value in profile.items():
    if os.getenv(env_key) is None:
        setattr(config, key, value)  # Silent override!
```

**Risk:** User sets `MAX_LEVERAGE=50.0` expecting it to apply, but live profile overrides to `25.0` without warning.

**Recommendation:**
1. Log all profile overrides with warnings
2. Allow disabling profile overrides with `DISABLE_PROFILE_OVERRIDES=true`
3. Make profiles more conservative, not less

---

### 2.5 **MEDIUM: Feature Flags Can Disable Safety**

**Problem:** Critical safety features are toggleable via environment variables.

```python
# bot/trading_config.py
enable_chop_detector: bool = field(default_factory=lambda: _env_bool("ENABLE_CHOP_DETECTOR", True))
enable_liquidity_guard: bool = field(default_factory=lambda: _env_bool("ENABLE_LIQUIDITY_GUARD", True))
enable_portfolio_risk: bool = field(default_factory=lambda: _env_bool("ENABLE_PORTFOLIO_RISK", True))
```

**Risk:** User could disable chop detector or liquidity guard, allowing bad trades.

```bash
export ENABLE_CHOP_DETECTOR=false  # Allows choppy-market trades
export ENABLE_LIQUIDITY_GUARD=false  # Allows dead-market entries
```

**Recommendation:**
1. Separate "feature flags" from "safety gates"
2. Make safety gates immutable: hardcode them, don't allow disable
3. Feature flags (soft filters, AB testing) can be toggleable

---

### 2.6 **MEDIUM: No Configuration Validation at Startup**

**Problem:** No validation that required environment variables are set before trading starts.

```python
# bot/llm/client.py:31-35
api_key = os.getenv("ANTHROPIC_API_KEY", "")
if not api_key:
    logger.warning("ANTHROPIC_API_KEY not set, LLM calls will fail")
    return None  # Graceful failure, but trading continues!
```

**Risk:** Bot can start paper trading without Discord/Telegram alerts configured, silently failing to notify user.

**Recommendation:**
1. Add `validate_config()` function called at startup
2. Check critical vars: `STARTING_EQUITY`, `RISK_PER_TRADE`, at least one alert channel
3. Exit with clear error message if validation fails

---

### 2.7 **LOW: Hardcoded Hyperliquid Maintenance Margins**

**Problem:** Maintenance margin tiers are hardcoded. If Hyperliquid changes them, bot uses outdated values.

```python
# bot/execution/leverage.py:31-39
HYPERLIQUID_MAINTENANCE_TIERS = [
    (100_000, 0.004),       # 0.4%
    (300_000, 0.006),       # 0.6%
    (600_000, 0.008),       # 0.8%
    (1_000_000, 0.01),      # 1.0%
    (5_000_000, 0.02),      # 2.0%
    (10_000_000, 0.03),     # 3.0%
    (float("inf"), 0.05),   # 5.0%
]
```

**Risk:** Small risk, but liquidation calculations could be wrong if Hyperliquid updates tiers.

**Recommendation:**
1. Fetch maintenance margins from exchange API at startup
2. Fall back to hardcoded values if API fails
3. Log a warning if using fallback values

---

## 3. HARDCODED VALUES - CRITICAL INVENTORY

### 3.1 Risk Multipliers (from trading_config.py)

| Risk Tier | SL Multiple | TP1 Multiple | TP2 Multiple | Notes |
|-----------|-------------|--------------|--------------|-------|
| low (BTC) | 1.3-2.2 | - | - | Widened from 1.0-1.8 to reduce stops from wicks |
| medium (SOL) | 1.5-2.5 | - | - | |
| high (HYPE) | 2.0-3.5 | - | - | Widest for volatile assets |

**Source:** `bot/trading_config.py:58-62`

### 3.2 Regime-Conditional Risk Multipliers

```python
REGIME_RISK_MULTIPLIERS = {
    "trending_bull":    0.7,    # Unproven edge
    "trending_bear":    0.7,
    "trend":            0.8,
    "consolidation":    1.0,    # Highest edge (78% WR)
    "range":            0.8,
    "high_volatility":  0.7,
    "panic":            0.3,    # Lowest size
    "low_liquidity":    0.5,
    "news_dislocation": 0.4,
    "unknown":          0.8,
}
```

**Risk:** These hardcoded multipliers assume specific regime profitability. If regime definitions change, sizes are wrong.

---

### 3.3 Leverage Tiers (hardcoded in leverage.py)

```python
# Tier 1: 60-64% confidence
leverage: 1.5x, risk_multiplier: 0.8x

# Tier 2: 65-69%
leverage: 1.5-2.0x, risk_multiplier: 0.8-1.0x

# Tier 3: 70-74%
leverage: 1.5-2.0x, risk_multiplier: 0.7-1.0x (depends on strategy agreement)

# Tier 4: 75-79%
leverage: 2.0-3.0x, risk_multiplier: 1.0-1.2x

# Tier 5: 80-89%
leverage: 3.0-4.0x, risk_multiplier: 1.2-1.3x

# Tier 6: 90%+
leverage: 4.0-5.0x, risk_multiplier: 1.3-1.5x (requires 3+ strategies)
```

**Location:** `bot/execution/leverage.py:120-200`

---

### 3.4 Fee Assumptions

```python
TAKER_FEE_BPS = 4          # 4 basis points (0.04%)
SLIPPAGE_BPS = 3           # 3 basis points estimated
MIN_PROFIT_THRESHOLD_MULT = 1.5  # TP1 must be 1.5x total expected costs
MIN_SIGNAL_EV = 0.08       # Minimum expected value per dollar risked
MIN_SIGNAL_RR = 1.2        # Minimum 1.2:1 risk-reward
```

**Risk:** If Hyperliquid raises fees to 5 bps, profit calculations are wrong.

---

### 3.5 Cooldown Times

```python
LOSS_COOLDOWN_S = 60       # 1 minute before re-entry after loss
WIN_COOLDOWN_S = 60        # 1 minute before re-entry after win
SIGNAL_DEDUP_WINDOW_S = 120  # 2 minutes (was 10 min, reduced for quant)
ROTATION_MIN_HOLD_S = 300  # 5 minutes minimum hold
ROTATION_GLOBAL_COOLDOWN_S = 600  # 10 minutes between rotations
```

**Risk:** Very short 1-minute cooldowns allow rapid revenge trading.

**Recommendation:** Make these configurable, with warnings if set too low:
```
MIN_LOSS_COOLDOWN_S=300  # Never less than 5 minutes
```

---

### 3.6 TP/SL Calculation Multipliers

```python
TP_SL_RR1 = 2.0            # Risk-reward ratio for TP1
TP_SL_RR2 = 4.0            # Risk-reward ratio for TP2
TP_SL_ATR_MULT = 1.5       # ATR multiplier for SL distance
SL_ATR_MULTIPLIER = 2.0    # Stop loss = 2.0x ATR
```

**Location:** `bot/trading_config.py:386-393`

---

### 3.7 ML/RL Parameters

```python
ML_MIN_SAMPLES = 20        # Need 20 samples before ML adjusts
ML_RETRAIN_INTERVAL = 10   # Retrain every 10 trades
ML_ADJUSTMENT_WEIGHT = 0.20  # ML adjusts confidence by max ±20%
SQUEEZE_ATR_RATIO = 0.65   # ATR compression threshold
```

---

### 3.8 Exchange-Specific Hardcodes

**Hyperliquid Symbol Mapping** (bot/execution/order_executor.py:37-56):
```python
SYMBOL_TO_PAIR = {
    "BTC": "BTC/USDC:USDC",
    "ETH": "ETH/USDC:USDC",
    "SOL": "SOL/USDC:USDC",
    # ... etc
}
```

**Risk:** If Hyperliquid changes pair format or adds symbols, bot needs code update.

---

## 4. ENVIRONMENT MODE HANDLING - DETAILED ANALYSIS

### 4.1 Paper Mode Activation

```bash
# Method 1: Default
python run.py paper
# Sets: ENVIRONMENT=paper (via cli.py:111)

# Method 2: Environment variable
export ENVIRONMENT=paper
python run.py paper

# Method 3: Direct CLI (unsafe - can be bypassed)
cd bot && python multi_strategy_main.py  # Defaults to paper if ENVIRONMENT not set
```

### 4.2 Live Mode Activation

```bash
# Only method: cli.py:120-146
python cli.py --mode live  # Asks for confirmation
python cli.py --mode live --yes  # Bypasses confirmation! ⚠️

# Then:
os.environ["ENVIRONMENT"] = "production"  # Sets it for bot initialization
```

### 4.3 Mode Detection Points

1. **cli.py:99-141** - Sets ENVIRONMENT before importing MultiStrategyBot
2. **multi_strategy_main.py:340** - Detects mode: `_is_production = os.getenv("ENVIRONMENT") == "production"`
3. **trading_config.py:511-516** - Properties:
   - `is_paper = (environment != "production")`
   - `auto_trade = (environment == "production")`

### 4.4 Mode-Specific Behavior Changes

| Behavior | Paper | Live |
|----------|-------|------|
| Order execution | Simulated, logged only | Real exchange order |
| Precision | Rounded | Rounded |
| Risk gates | Applied | Applied |
| Circuit breaker | Applied | Applied |
| Alerts | Discord/Telegram | Discord/Telegram |
| Fee charging | Simulated | Real |
| Position tracking | In-memory + CSV | Exchange state |
| Leverage | Up to MAX_LEVERAGE | Up to MAX_LEVERAGE |

### 4.5 Profile Overrides by Mode

**Paper Profile** (bot/trading_config.py:573-579):
```python
PAPER_PROFILE_OVERRIDES = {
    "max_leverage": 25.0,
    "risk_per_trade": 0.005,      # 0.5% — aggressive
    "max_open_positions": 8,
    "max_portfolio_leverage": 4.0,
    "enable_smart_orders": False,  # Conservative
}
```

**Live Profile** (bot/trading_config.py:634-640):
```python
LIVE_PROFILE_OVERRIDES = {
    "max_leverage": 25.0,          # Same as paper!
    "risk_per_trade": 0.005,       # Same as paper!
    "max_open_positions": 8,       # Same as paper!
    "max_portfolio_leverage": 4.0,
    "enable_smart_orders": True,   # More aggressive in live
}
```

**Problem:** Profiles are nearly identical! Paper mode is as aggressive as live.

**Recommendation:** Make paper more conservative:
```python
PAPER_PROFILE_OVERRIDES = {
    "max_leverage": 2.0,           # No leverage in paper
    "risk_per_trade": 0.001,       # 0.1% only
    "max_open_positions": 1,       # Single position
    "max_portfolio_leverage": 1.0, # No leverage
    "enable_smart_orders": False,
}
```

---

## 5. MISSING VALIDATION CHECKS

### 5.1 Startup Validation (MISSING)

No `validate_config()` function exists. Recommend adding:

```python
def validate_config(config: TradingConfig) -> List[str]:
    """Return list of validation errors. Empty = valid."""
    errors = []

    # Critical env vars
    if config.auto_trade and not os.getenv("HL_API_KEY"):
        errors.append("Live mode requires HL_API_KEY")
    if config.auto_trade and not os.getenv("HL_API_SECRET"):
        errors.append("Live mode requires HL_API_SECRET")

    # Sanity checks
    if config.starting_equity <= 0:
        errors.append(f"STARTING_EQUITY must be > 0, got {config.starting_equity}")
    if config.risk_per_trade <= 0 or config.risk_per_trade > 0.10:
        errors.append(f"RISK_PER_TRADE must be 0.001-0.10, got {config.risk_per_trade}")
    if config.max_leverage < 1.0 or config.max_leverage > 100:
        errors.append(f"MAX_LEVERAGE must be 1-100, got {config.max_leverage}")
    if config.max_consecutive_losses < 1 or config.max_consecutive_losses > 100:
        errors.append(f"MAX_CONSECUTIVE_LOSSES must be 1-100, got {config.max_consecutive_losses}")

    # Consistency checks
    if config.max_open_positions < 1:
        errors.append("MAX_OPEN_POSITIONS must be >= 1")
    if config.circuit_breaker_daily_loss_pct <= 0 or config.circuit_breaker_daily_loss_pct > 0.50:
        errors.append(f"CIRCUIT_BREAKER_DAILY_LOSS_PCT must be 0.01-0.50, got {config.circuit_breaker_daily_loss_pct}")

    return errors
```

### 5.2 Alert Channel Validation (MISSING)

```python
def validate_alerts(config: TradingConfig) -> bool:
    """Warn if no alerts configured."""
    if not config.discord_webhook and not config.telegram_token:
        logger.warning("⚠️  No alert channels configured! Signals will only be logged.")
        return False
    return True
```

### 5.3 Exchange Credential Validation (MISSING)

```python
def validate_exchange_creds(config: TradingConfig) -> bool:
    """Validate Hyperliquid credentials format."""
    if config.auto_trade:
        api_key = os.getenv("HL_API_KEY", "")
        api_secret = os.getenv("HL_API_SECRET", "")

        if not api_key.startswith("0x") or len(api_key) != 42:
            raise ValueError("HL_API_KEY must be Ethereum address (0x...)")
        if not api_secret.startswith("0x") or len(api_secret) != 66:
            raise ValueError("HL_API_SECRET must be 32-byte private key (0x...)")
    return True
```

---

## 6. RECOMMENDATIONS BY SEVERITY

### CRITICAL (Do Immediately)

1. **Add mode validation at startup**
   - Verify ENVIRONMENT is set before initializing bot
   - Prevent environment variable override after mode selection
   - Log mode selection prominently

2. **Add startup config validation**
   - Call `validate_config()` before any trading
   - Abort with clear error message if validation fails
   - Check critical env vars: ANTHROPIC_API_KEY, alert channels

3. **Sanitize all logging**
   - Never log API objects or full responses
   - Mask API keys in logs: `"sk-***...***"`
   - Use structured logging with sensitive field redaction

### HIGH (Do This Week)

4. **Separate safety gates from feature flags**
   - Make circuit breaker, risk gates, precision immutable
   - Only allow toggling non-critical features
   - Document which settings can be changed without approval

5. **Add Hyperliquid credential validation**
   - Validate wallet address format (0x + 40 hex chars)
   - Validate private key format (0x + 64 hex chars)
   - Do NOT log credentials

6. **Improve profile handling**
   - Log all profile overrides with warnings
   - Option to disable profile overrides
   - Make live profile MORE conservative, not less

### MEDIUM (Do This Month)

7. **Fetch maintenance margins from exchange**
   - Query Hyperliquid API at startup for current tiers
   - Fall back to hardcoded values if API fails
   - Log warning if using fallback

8. **Make critical timeouts configurable**
   - Allow setting min/max cooldown times
   - Warn if values are unsafe (e.g., <60s loss cooldown)
   - Document recommended ranges

9. **Add environment pre-flight checks**
   - Validate network connectivity to Hyperliquid
   - Check API key validity (dry auth call)
   - Verify data source accessibility

---

## 7. SAFE CONFIGURATION TEMPLATES

### Template A: Conservative Paper Trading (Learning Mode)

```bash
# .env
ENVIRONMENT=paper
STARTING_EQUITY=10000.0
RISK_PER_TRADE=0.001          # 0.1% — very conservative
MAX_LEVERAGE=1.0              # No leverage
MAX_OPEN_POSITIONS=1          # Single position
SCAN_INTERVAL_S=60
LLM_MODE=1                    # Advisory only
LLM_USAGE_TIER=CONSERVATIVE
ENABLE_LEVERAGE=false
ENABLE_TRAILING_STOP=true
CIRCUIT_BREAKER_DAILY_LOSS_PCT=0.02  # 2% stop
TELEGRAM_TOKEN=<your-token>
TELEGRAM_CHAT_ID=<your-chat>
```

### Template B: Moderate Paper Trading (Testing Mode)

```bash
ENVIRONMENT=paper
STARTING_EQUITY=10000.0
RISK_PER_TRADE=0.005          # 0.5% — moderate
MAX_LEVERAGE=5.0              # Moderate leverage
MAX_OPEN_POSITIONS=3
SCAN_INTERVAL_S=60
LLM_MODE=2                    # Veto only
LLM_USAGE_TIER=RECOMMENDED
ENABLE_LEVERAGE=true
ENABLE_TRAILING_STOP=true
CIRCUIT_BREAKER_DAILY_LOSS_PCT=0.05  # 5% stop
TELEGRAM_TOKEN=<your-token>
TELEGRAM_CHAT_ID=<your-chat>
```

### Template C: Live Trading (Small Account)

```bash
ENVIRONMENT=production        # ⚠️ LIVE TRADING
STARTING_EQUITY=400.0
RISK_PER_TRADE=0.02           # 2% per trade = $8
MAX_LEVERAGE=10.0             # Conservative for small account
MAX_OPEN_POSITIONS=3
SCAN_INTERVAL_S=60
LLM_MODE=2                    # Veto only (start here)
LLM_USAGE_TIER=CONSERVATIVE
ENABLE_LEVERAGE=true
ENABLE_TRAILING_STOP=true
CIRCUIT_BREAKER_DAILY_LOSS_PCT=0.05  # 5% = $20
MAX_CONSECUTIVE_LOSSES=4
CIRCUIT_BREAKER_COOLDOWN_MIN=120     # 2 hours
HL_API_KEY=0x<your-wallet>
HL_API_SECRET=0x<your-private-key>
ANTHROPIC_API_KEY=sk-<your-key>
TELEGRAM_TOKEN=<your-token>
TELEGRAM_CHAT_ID=<your-chat>
TELEGRAM_ALLOWED_USER_ID=<your-user-id>
```

---

## 8. SUMMARY TABLE: Risk Levels by Configuration

| Configuration | Risk Level | Key Issues |
|---------------|-----------|-----------|
| Paper mode, no API keys | **LOW** | Simulated trading, no real capital at risk |
| Paper mode, with API keys | **MEDIUM** | Keys could leak if logs are exposed |
| Live mode, small account | **MEDIUM** | Loss limits are appropriate, but validation missing |
| Live mode, large account | **HIGH** | High leverage possible, no startup validation |
| Live mode with `--yes` flag | **CRITICAL** | Confirmation bypassed, mode could be wrong |

---

## 9. CHECKLIST FOR GO-LIVE

- [ ] ENVIRONMENT variable is explicitly set to "production" in .env (NOT environment)
- [ ] STARTING_EQUITY matches actual account balance
- [ ] RISK_PER_TRADE is 1-2% maximum (0.5% recommended for safety)
- [ ] MAX_LEVERAGE matches account tier and experience
- [ ] CIRCUIT_BREAKER_DAILY_LOSS_PCT is 5% or lower
- [ ] Alert channels configured: TELEGRAM_TOKEN and TELEGRAM_CHAT_ID
- [ ] HL_API_KEY and HL_API_SECRET are set (DO NOT commit to git)
- [ ] ANTHROPIC_API_KEY is set (DO NOT commit to git)
- [ ] At least 2 weeks of paper trading completed (>50 trades)
- [ ] Go-live gate passed (gate_result["passed"] = true)
- [ ] All tests pass: `pytest tests/ -v`
- [ ] Manual smoke test: place 1 small position, verify fills
- [ ] Alerts test: verify Discord/Telegram notifications work
- [ ] Backtest: recent 30-day backtest shows positive edge
- [ ] Review: circuit breaker events, win rate, Sharpe ratio

---

## CONCLUSION

The WAGMI bot has **mature configuration management** with sensible defaults and environment variable support. However, **critical validation gaps** exist around environment mode selection and startup checks. These should be addressed before live trading.

**Priority Order:**
1. Add startup config validation (prevents crashes)
2. Strengthen mode verification (prevents wrong env)
3. Sanitize logging (prevents key leaks)
4. Add pre-flight checks (prevents bad fills)

All code locations and default values are documented above for reference.
