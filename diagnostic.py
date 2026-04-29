"""Quick diagnostic to find where the bot hangs."""
import sys
import time
import logging

# Set up logging to see where we stop
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(name)s: %(message)s'
)
logger = logging.getLogger("diagnostic")

sys.path.insert(0, 'bot')

logger.info("=" * 60)
logger.info("DIAGNOSTIC: Finding where bot hangs")
logger.info("=" * 60)

try:
    logger.info("1. Importing TradingConfig...")
    from bot.trading_config import TradingConfig, DEFAULT_SYMBOLS
    logger.info("   ✓ TradingConfig imported")
    
    logger.info("2. Initializing config...")
    config = TradingConfig()
    logger.info("   ✓ Config initialized")
    
    logger.info("3. Importing MultiStrategyBot...")
    from bot.multi_strategy_main import MultiStrategyBot
    logger.info("   ✓ MultiStrategyBot imported")
    
    logger.info("4. Creating bot instance...")
    bot = MultiStrategyBot(config)
    logger.info("   ✓ Bot created (this may take a while)")
    
    logger.info("5. [WOULD CALL bot.run() here — STOPPING BEFORE IT]")
    logger.info("   Bot is ready to run, but would hang in run()")
    logger.info("   The issue is in one of these startup steps:")
    logger.info("   - _run_health_check()")
    logger.info("   - _reconcile_exchange_positions()")
    logger.info("   - telegram_bot.start()")
    logger.info("   - signal_monitor.start()")
    logger.info("   - watchdog.start()")

except Exception as e:
    logger.error(f"ERROR at import/init stage: {e}", exc_info=True)
    sys.exit(1)

logger.info("Diagnostic complete. Bot initialization doesn't hang — hang is in run()")
