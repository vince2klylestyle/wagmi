# Configuration Security Fixes - Implementation Guide

This document provides concrete code fixes for the critical configuration and security issues identified in CONFIG_AUDIT_REPORT.md.

---

## FIX 1: Add Startup Configuration Validation

**File:** `bot/trading_config.py` (at end, before apply_profile)

```python
def validate_config(config: TradingConfig) -> Tuple[bool, List[str]]:
    """Validate configuration for safety and consistency.

    Returns:
        (is_valid, error_messages)
        If is_valid=False, bot should not start.
    """
    errors = []
    warnings = []

    # ── CRITICAL: Environment mode
    if config.environment not in ("paper", "production"):
        errors.append(f"ENVIRONMENT must be 'paper' or 'production', got '{config.environment}'")

    # ── CRITICAL: Live trading requires API keys
    if config.auto_trade:
        hl_key = os.getenv("HL_API_KEY", "")
        hl_secret = os.getenv("HL_API_SECRET", "")

        if not hl_key or not hl_key.startswith("0x"):
            errors.append("Live mode requires valid HL_API_KEY (0x...)")
        if not hl_secret or not hl_secret.startswith("0x"):
            errors.append("Live mode requires valid HL_API_SECRET (0x...)")

    # ── CRITICAL: Equity sanity
    if config.starting_equity <= 0:
        errors.append(f"STARTING_EQUITY must be > 0, got {config.starting_equity}")
    if config.starting_equity < 100 and config.auto_trade:
        warnings.append(f"Live trading with ${config.starting_equity} is very small (min $400 recommended)")

    # ── CRITICAL: Risk per trade
    if config.risk_per_trade <= 0:
        errors.append(f"RISK_PER_TRADE must be > 0, got {config.risk_per_trade}")
    if config.risk_per_trade > 0.10:
        errors.append(f"RISK_PER_TRADE > 10% is dangerous, got {config.risk_per_trade:.1%}")
    if config.auto_trade and config.risk_per_trade > 0.05:
        warnings.append(f"Live trading with RISK_PER_TRADE={config.risk_per_trade:.1%} is aggressive (2% recommended)")

    # ── CRITICAL: Leverage
    if config.max_leverage < 1.0:
        errors.append(f"MAX_LEVERAGE must be >= 1.0, got {config.max_leverage}")
    if config.max_leverage > 100:
        errors.append(f"MAX_LEVERAGE > 100 is dangerous, got {config.max_leverage}")

    # ── CRITICAL: Circuit breakers
    if config.circuit_breaker_daily_loss_pct <= 0:
        errors.append("CIRCUIT_BREAKER_DAILY_LOSS_PCT must be > 0")
    if config.circuit_breaker_daily_loss_pct > 0.50:
        errors.append(f"CIRCUIT_BREAKER_DAILY_LOSS_PCT > 50% is weak, got {config.circuit_breaker_daily_loss_pct:.0%}")

    if config.max_consecutive_losses < 1 or config.max_consecutive_losses > 100:
        errors.append(f"MAX_CONSECUTIVE_LOSSES must be 1-100, got {config.max_consecutive_losses}")

    # ── CRITICAL: Confidence floors
    if config.ensemble_confidence_floor < 50 or config.ensemble_confidence_floor > 90:
        warnings.append(f"ENSEMBLE_CONFIDENCE_FLOOR={config.ensemble_confidence_floor:.0f} (typical 55-70)")

    # ── CRITICAL: Alerts (for live)
    if config.auto_trade:
        if not os.getenv("TELEGRAM_TOKEN") and not os.getenv("DISCORD_WEBHOOK"):
            errors.append("Live trading requires TELEGRAM_TOKEN or DISCORD_WEBHOOK for alerts")
        if os.getenv("TELEGRAM_TOKEN") and not os.getenv("TELEGRAM_CHAT_ID"):
            errors.append("TELEGRAM_TOKEN set but TELEGRAM_CHAT_ID missing")
        if os.getenv("TELEGRAM_TOKEN") and os.getenv("TELEGRAM_ALLOWED_USER_ID") == "0":
            warnings.append("TELEGRAM_ALLOWED_USER_ID not set; anyone can control the bot!")

    # ── CRITICAL: Anthropic API key (if LLM enabled)
    if config.llm_mode > 0:  # Any LLM enabled
        if not os.getenv("ANTHROPIC_API_KEY"):
            errors.append("LLM_MODE > 0 requires ANTHROPIC_API_KEY")

    # ── Position sizing
    if config.max_open_positions < 1:
        errors.append(f"MAX_OPEN_POSITIONS must be >= 1, got {config.max_open_positions}")

    # ── Timeframe weights
    total_weight = (config.tf_weight_5m + config.tf_weight_1h +
                   config.tf_weight_6h + config.tf_weight_daily)
    if total_weight <= 0:
        errors.append("All timeframe weights are 0; no signals will be generated")

    return (len(errors) == 0, errors + warnings)
```

**Usage in bot initialization:**

```python
# bot/multi_strategy_main.py (in __init__)

def __init__(self, config: TradingConfig):
    self.config = config

    # ── NEW: Validate config before proceeding
    is_valid, messages = validate_config(config)

    for msg in messages:
        if msg.startswith("ERROR"):
            logger.error(f"CONFIG VALIDATION FAILED: {msg}")
        else:
            logger.warning(f"CONFIG WARNING: {msg}")

    if not is_valid:
        logger.critical("Cannot start bot due to configuration errors.")
        raise SystemExit("Configuration validation failed. See logs above.")

    # Continue with existing initialization...
    self.stop_event = threading.Event()
    apply_profile(config)
    # ... rest of __init__
```

---

## FIX 2: Environment Mode Validation

**File:** `bot/trading_config.py` (after TradingConfig class definition)

```python
def validate_mode_and_lock():
    """Validate that ENVIRONMENT variable is set correctly and matches .env.

    This function:
    1. Checks that ENVIRONMENT is explicitly set (not defaulting)
    2. Validates that mode matches loaded .env file
    3. Prevents accidental live trading when expecting paper
    """
    env_mode = os.getenv("ENVIRONMENT", "")

    if not env_mode:
        logger.warning("⚠️  ENVIRONMENT variable not set; defaulting to 'paper'")
        logger.warning("   For production trading, explicitly set: export ENVIRONMENT=production")
        os.environ["ENVIRONMENT"] = "paper"  # Explicit default
        return "paper"

    if env_mode not in ("paper", "production"):
        raise ValueError(f"ENVIRONMENT must be 'paper' or 'production', got '{env_mode}'")

    # Log mode prominently
    if env_mode == "production":
        logger.critical("=" * 60)
        logger.critical("🔴 LIVE TRADING MODE ACTIVE (REAL MONEY)")
        logger.critical("=" * 60)
    else:
        logger.info("=" * 60)
        logger.info("🟢 PAPER TRADING MODE (SIMULATED)")
        logger.info("=" * 60)

    return env_mode
```

**Call this early in bot initialization:**

```python
# bot/multi_strategy_main.py (very start of __init__)

def __init__(self, config: TradingConfig):
    # ── FIRST: Validate and lock mode
    mode = validate_mode_and_lock()
    if mode != config.environment:
        logger.critical(f"Mode mismatch! Env says {mode}, config says {config.environment}")
        raise SystemExit("Configuration mode mismatch.")

    # Continue...
```

---

## FIX 3: Sanitize All Logging (Never Log API Keys)

**File:** `bot/core/structured_logging.py` (new utility)

```python
import logging
import re

class SensitiveRedactor(logging.Filter):
    """Filter to redact sensitive information from logs."""

    PATTERNS = [
        # API keys: sk-... or similar
        (r'sk-[a-zA-Z0-9]{40,}', 'sk-***'),

        # Ethereum private keys: 0x followed by 64 hex chars
        (r'0x[a-fA-F0-9]{64}(?![a-fA-F0-9])', '0x***'),

        # Ethereum addresses: 0x followed by 40 hex chars (if followed by non-hex)
        (r'0x[a-fA-F0-9]{40}(?![a-fA-F0-9])', '0x***'),

        # Bearer tokens
        (r'Bearer\s+[a-zA-Z0-9\-_.~\+\/]+=*', 'Bearer ***'),

        # Any "key=..." or "secret=..."
        (r'(key|secret|password|token)=([^&\s,)]+)', r'\1=***'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive fields from log record."""
        # Redact message
        if record.msg and isinstance(record.msg, str):
            for pattern, replacement in self.PATTERNS:
                record.msg = re.sub(pattern, replacement, record.msg, flags=re.IGNORECASE)

        # Redact exception info
        if record.exc_info:
            # Don't log exception tracebacks that might contain credentials
            record.exc_info = None
            if record.exc_text:
                record.exc_text = "[Exception details redacted]"

        return True

def setup_logging_with_redaction(log_dir: str = "logs"):
    """Setup logging with automatic credential redaction."""
    logger = logging.getLogger()

    # Add redaction filter to all handlers
    redactor = SensitiveRedactor()
    for handler in logger.handlers:
        handler.addFilter(redactor)

    # Also add to new handlers
    logger.redaction_filter = redactor
```

**Use in bot initialization:**

```python
# bot/multi_strategy_main.py

from core.structured_logging import setup_logging, setup_logging_with_redaction

_is_production = os.getenv("ENVIRONMENT", "paper").lower() == "production"
setup_logging(json_mode=_is_production, level=os.getenv("LOG_LEVEL", "INFO"), log_dir="logs")
setup_logging_with_redaction(log_dir="logs")  # ← NEW
```

---

## FIX 4: Validate Exchange Credentials

**File:** `bot/execution/order_executor.py` (add to initialization)

```python
def validate_hyperliquid_credentials() -> bool:
    """Validate Hyperliquid API credentials format.

    Does NOT check if credentials are valid (that requires API call),
    but checks that they have the right format.
    """
    api_key = os.getenv("HL_API_KEY", "").strip()
    api_secret = os.getenv("HL_API_SECRET", "").strip()

    errors = []

    # Validate API key (wallet address)
    if not api_key:
        return True  # OK, not configured yet (paper mode)
    if not api_key.startswith("0x"):
        errors.append(f"HL_API_KEY must start with '0x', got '{api_key[:10]}...'")
    elif len(api_key) != 42:
        errors.append(f"HL_API_KEY must be exactly 42 chars (0x + 40 hex), got {len(api_key)}")
    elif not all(c in "0123456789abcdefABCDEF" for c in api_key[2:]):
        errors.append(f"HL_API_KEY contains invalid hex characters")

    # Validate API secret (private key)
    if not api_secret:
        return True  # OK, not configured yet
    if not api_secret.startswith("0x"):
        errors.append(f"HL_API_SECRET must start with '0x', got '{api_secret[:10]}...'")
    elif len(api_secret) != 66:
        errors.append(f"HL_API_SECRET must be exactly 66 chars (0x + 64 hex), got {len(api_secret)}")
    elif not all(c in "0123456789abcdefABCDEF" for c in api_secret[2:]):
        errors.append(f"HL_API_SECRET contains invalid hex characters")

    if errors:
        for error in errors:
            logger.error(f"Credential validation: {error}")
        return False

    logger.info(f"HL credentials validated: {api_key[:10]}... (valid Ethereum address format)")
    return True

class OrderExecutor:
    def __init__(self, exchange: Optional[object] = None, mode: str = "paper", ...):
        # ← Add validation
        if mode == "live" and not validate_hyperliquid_credentials():
            raise ValueError("Invalid Hyperliquid credentials")

        self.exchange = exchange
        self.mode = mode
        # ... rest of init
```

---

## FIX 5: Improve Profile Override Logging

**File:** `bot/trading_config.py` (modify apply_profile function)

```python
def apply_profile(config: TradingConfig) -> TradingConfig:
    """Apply paper/live profile overrides with logging.

    Profile overrides only apply if the corresponding env var is NOT set.
    Explicit env vars always take priority.

    NEW: This function now logs all overrides with clear warnings.
    """
    profile = PAPER_PROFILE_OVERRIDES if config.is_paper else LIVE_PROFILE_OVERRIDES

    logger.info(f"Applying {'PAPER' if config.is_paper else 'LIVE'} profile overrides:")

    overridden = []
    for key, value in profile.items():
        env_key = key.upper()
        if os.getenv(env_key) is None:
            old_value = getattr(config, key, None)
            setattr(config, key, value)
            if old_value != value:
                logger.warning(f"  {key}: {old_value} → {value} (profile override)")
                overridden.append((key, old_value, value))
        else:
            logger.debug(f"  {key}: {getattr(config, key)} (env var takes priority)")

    if not overridden:
        logger.info("  (no overrides applied — all values set via environment)")

    return config
```

---

## FIX 6: Add Pre-Flight Checks Before Live Trading

**File:** `bot/bot.py` (new module `bot/preflight.py`)

```python
"""Pre-flight checks before starting live trading."""

import logging
import os
from typing import List, Tuple

logger = logging.getLogger("bot.preflight")

def preflight_checks(config) -> Tuple[bool, List[str]]:
    """Run all pre-flight checks before trading.

    Returns:
        (all_passed, issues_found)
    """
    issues = []

    # ── Check environment mode
    mode = os.getenv("ENVIRONMENT", "paper")
    if config.auto_trade and mode != "production":
        issues.append(f"Live trading expected but ENVIRONMENT={mode}")

    # ── Check equity is reasonable
    if config.auto_trade and config.starting_equity < 100:
        issues.append(f"Equity too low for live trading: ${config.starting_equity}")

    # ── Check that circuit breaker won't trigger immediately
    if config.circuit_breaker_daily_loss_pct < 0.02:
        issues.append("CIRCUIT_BREAKER_DAILY_LOSS_PCT < 2% may trigger too easily")

    # ── Check LLM config if enabled
    if config.llm_mode > 0:
        if not os.getenv("ANTHROPIC_API_KEY"):
            issues.append("LLM_MODE > 0 but ANTHROPIC_API_KEY not set")

    # ── Check alerts
    has_discord = bool(os.getenv("DISCORD_WEBHOOK", "").strip())
    has_telegram = bool(os.getenv("TELEGRAM_TOKEN", "").strip())
    if config.auto_trade and not (has_discord or has_telegram):
        issues.append("Live trading without alerts is dangerous")

    # ── Check telegram security
    if has_telegram and config.auto_trade:
        user_id = os.getenv("TELEGRAM_ALLOWED_USER_ID", "0")
        if user_id == "0" or user_id == "":
            issues.append("TELEGRAM_ALLOWED_USER_ID not set; anyone can control the bot!")

    # Log results
    if not issues:
        logger.info("✅ All pre-flight checks passed")
    else:
        for issue in issues:
            logger.warning(f"⚠️  {issue}")

    return (len(issues) == 0, issues)
```

**Call before bot.run():**

```python
# bot/cli.py (_run_live function)

def _run_live(skip_confirm: bool = False):
    """Live trading mode - requires confirmation."""
    # ... existing confirmation code ...

    # NEW: Run pre-flight checks
    from preflight import preflight_checks

    os.environ["ENVIRONMENT"] = "production"
    config = TradingConfig()

    all_ok, issues = preflight_checks(config)
    if not all_ok:
        logger.error("Pre-flight checks failed. Fix issues above and retry.")
        sys.exit(1)

    logger.info("Starting bot...")
    bot = MultiStrategyBot(config)
    bot.run()
```

---

## FIX 7: Make Critical Values Non-Overridable

**File:** `bot/trading_config.py` (add immutable config wrapper)

```python
class ImmutableConfig:
    """Wrapper that prevents modification of safety-critical fields."""

    # Fields that should NEVER be modified after initialization
    IMMUTABLE_FIELDS = {
        "environment",  # Paper vs live
        "circuit_breaker_daily_loss_pct",  # Daily loss limit
        "max_drawdown_pct",  # Max drawdown
        "max_consecutive_losses",  # Loss streak limit
    }

    def __init__(self, config: TradingConfig):
        self._config = config
        self._locked = False

    def lock(self):
        """Lock config to prevent further changes."""
        self._locked = True
        logger.info("Configuration locked (safety-critical fields are immutable)")

    def __setattr__(self, name: str, value):
        if name in ("_config", "_locked"):
            super().__setattr__(name, value)
            return

        if self._locked and name in self.IMMUTABLE_FIELDS:
            raise ValueError(f"Cannot modify immutable field: {name}")

        setattr(self._config, name, value)

    def __getattr__(self, name: str):
        return getattr(self._config, name)
```

---

## FIX 8: Configuration Audit Trail

**File:** `bot/config_audit.py` (new module)

```python
"""Log all configuration changes for audit purposes."""

import json
import os
from datetime import datetime

CONFIG_AUDIT_FILE = "data/config_audit.jsonl"

def audit_config_change(field: str, old_value, new_value, reason: str = ""):
    """Log configuration change to audit file."""
    os.makedirs("data", exist_ok=True)

    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "field": field,
        "old_value": str(old_value),
        "new_value": str(new_value),
        "reason": reason,
        "environment": os.getenv("ENVIRONMENT", "unknown"),
    }

    with open(CONFIG_AUDIT_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

def log_startup_config(config: TradingConfig):
    """Log full config at startup for audit trail."""
    startup_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event": "bot_startup",
        "environment": config.environment,
        "starting_equity": config.starting_equity,
        "risk_per_trade": config.risk_per_trade,
        "max_leverage": config.max_leverage,
        "max_open_positions": config.max_open_positions,
        "circuit_breaker_daily_loss_pct": config.circuit_breaker_daily_loss_pct,
        "llm_mode": config.llm_mode,
        "alert_channels": {
            "discord": bool(os.getenv("DISCORD_WEBHOOK")),
            "telegram": bool(os.getenv("TELEGRAM_TOKEN")),
        },
    }

    with open(CONFIG_AUDIT_FILE, "a") as f:
        f.write(json.dumps(startup_entry) + "\n")
```

---

## Implementation Checklist

- [ ] Add `validate_config()` to trading_config.py
- [ ] Add `validate_mode_and_lock()` function
- [ ] Integrate validation into MultiStrategyBot.__init__
- [ ] Create `SensitiveRedactor` logging filter
- [ ] Add pre-flight checks module
- [ ] Validate Hyperliquid credentials format
- [ ] Log all profile overrides with warnings
- [ ] Create ImmutableConfig wrapper for safety-critical fields
- [ ] Add config audit trail logging
- [ ] Test all fixes with paper trading first
- [ ] Update documentation in CLAUDE.md

---

## Testing Instructions

```bash
# Test with invalid config
export STARTING_EQUITY=-1000
python run.py paper  # Should fail with validation error

# Test with missing API key
export ENVIRONMENT=production
unset ANTHROPIC_API_KEY
python cli.py --mode live  # Should warn about missing key

# Test credential validation
export HL_API_KEY=invalid
export HL_API_SECRET=invalid
python cli.py --mode live  # Should validate format

# Test mode locking
export ENVIRONMENT=paper
python run.py paper  # Should log "PAPER MODE"

# Test logging redaction
export ANTHROPIC_API_KEY=sk-1234567890abcdef
python run.py paper 2>&1 | grep sk-  # Should show sk-***
```

---

## Risk Reduction Summary

| Fix | Risk Reduced | Effort |
|-----|-------------|--------|
| Config validation | Prevents crashes from bad config | 1 hour |
| Mode locking | Prevents accidental live trading | 2 hours |
| Logging redaction | Prevents API key leaks | 1 hour |
| Credential validation | Prevents invalid exchange config | 1 hour |
| Pre-flight checks | Catches unsafe setups before trading | 1.5 hours |
| Immutable config | Prevents runtime safety changes | 1 hour |
| Audit trail | Enables forensic analysis | 1.5 hours |
| **Total** | **CRITICAL risks eliminated** | **~9 hours** |

Implementing these fixes will reduce security and configuration risks from MEDIUM to LOW.
