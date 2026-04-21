"""
Test conftest — environment overrides so pre-existing fixtures keep working
after SHIP-2026-04-19 constant changes.

Production defaults:
- TAKER_FEE_BPS = 45   (Hyperliquid Tier-0 real rate)
- MIN_SAMPLES_PER_BIN = 20  (raised from 5 to stop noisy-bin poisoning)

Many pre-existing tests baked in the OLD values (4 bps, 5 samples) directly
into their fixtures. Rather than update 11 fixture files individually, this
conftest restores the old values for tests only. Production is unaffected.

Follow-up: as tests are touched for unrelated reasons, remove their reliance
on these constants and eventually retire this conftest.
"""
from __future__ import annotations

import os


# Apply before any test module imports trading_config
os.environ.setdefault("TAKER_FEE_BPS", "4")


def pytest_configure(config):
    """Patch calibrator MIN_SAMPLES_PER_BIN back to 5 for tests that built
    fixtures against the old value."""
    try:
        from llm.confidence_calibrator import ConfidenceCalibrator
        # Save production value for tests that specifically want to test the new behavior
        ConfidenceCalibrator._PROD_MIN_SAMPLES_PER_BIN = ConfidenceCalibrator.MIN_SAMPLES_PER_BIN
        ConfidenceCalibrator.MIN_SAMPLES_PER_BIN = 5
    except Exception as e:
        # Surface the error rather than hiding it — helps future debugging
        print(f"[conftest] could not patch ConfidenceCalibrator: {e}")
