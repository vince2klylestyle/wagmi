#!/usr/bin/env python3
"""
Diagnose where backtest hangs by adding detailed logging at each step
"""

import sys
import time
from datetime import datetime
from pathlib import Path

# Add bot to path
sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

def log_step(msg):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] {msg}", flush=True)

log_step("START: Diagnosing backtest hang")

try:
    log_step("Importing trading_config...")
    from trading_config import TradingConfig
    log_step("  [OK] trading_config imported")

    log_step("Creating TradingConfig instance...")
    config = TradingConfig()
    log_step(f"  [OK] config created (equity={config.starting_equity})")

    log_step("Importing BacktestEngine...")
    from backtest.engine import BacktestEngine
    log_step("  [OK] BacktestEngine imported")

    log_step("Creating BacktestEngine instance...")
    engine = BacktestEngine(config, llm_integration=None, fresh=False, relaxed_cb=False, resume=False, yes=True)
    log_step("  [OK] BacktestEngine created")

    log_step("Calling engine.run(symbols=['BTC'], days=5, strategies=None, learn=False, start_date='2023-01-01')...")
    start_time = time.time()

    report = engine.run(
        symbols=['BTC'],
        days=5,
        strategies=None,
        learn=False,
        start_date='2023-01-01'
    )

    elapsed = time.time() - start_time
    log_step(f"  [OK] engine.run completed in {elapsed:.1f}s")
    log_step(f"  Report keys: {list(report.keys())}")

except Exception as e:
    log_step(f"ERROR: {type(e).__name__}: {str(e)}")
    import traceback
    log_step(traceback.format_exc())

log_step("DONE")
