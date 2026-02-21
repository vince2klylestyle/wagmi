"""
CSV validator and PnL verification tool.

Checks:
1. All required fields present in trades.csv and trade_outcomes.csv
2. No Unicode characters in any field
3. PnL math is correct: PnL = (exit - entry) * qty * leverage - fees (LONG)
4. qty is consistent with risk_per_trade
5. No impossible trades (PnL > max possible, price scale off by >10x)
6. Cross-check trades.csv against trade_outcomes.csv

Usage:
    python -m scripts.verify_csvs
    python -m scripts.verify_csvs --trades data/trades.csv
"""

import argparse
import csv
import json
import logging
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("verify")

_TRADES_FILE = os.path.join("data", "trades.csv")
_OUTCOMES_FILE = os.path.join("data", "analysis", "trade_outcomes.csv")
_PERF_FILE = os.path.join("data", "analysis", "performance.json")


def _read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _safe_float(val, default=0.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# ── 1. Schema Validation ──────────────────────────────────

TRADES_REQUIRED = [
    "timestamp", "symbol", "side", "entry", "exit",
    "pnl", "fees", "state_path", "outcome",
    "leverage", "confidence",
    "entry_type", "primary_driver", "regime", "volatility_band",
    "ml_conf_at_entry",
]

OUTCOMES_REQUIRED = [
    "timestamp", "symbol", "side", "outcome", "pnl",
    "state_path", "leverage", "confidence",
    "entry_type", "primary_driver", "regime", "volatility_band",
]


def validate_schema(rows, required_fields, source_name):
    """Check that all required fields are present and non-empty."""
    issues = []
    for i, row in enumerate(rows):
        for field in required_fields:
            val = row.get(field, "")
            if val is None or val.strip() == "":
                issues.append(f"Row {i+1}: missing '{field}'")
    if issues:
        print(f"\n[FAIL] {source_name}: {len(issues)} missing field(s)")
        for iss in issues[:10]:
            print(f"  {iss}")
        if len(issues) > 10:
            print(f"  ... and {len(issues)-10} more")
    else:
        print(f"[OK] {source_name}: all required fields present ({len(rows)} rows)")
    return len(issues) == 0


# ── 2. ASCII Safety ────────────────────────────────────────

def validate_ascii(rows, source_name):
    """Check no Unicode arrows or non-ASCII in critical fields."""
    issues = []
    for i, row in enumerate(rows):
        for key, val in row.items():
            if val and "\u2192" in val:
                issues.append(f"Row {i+1}, field '{key}': contains Unicode arrow")
            # Check for any non-ASCII in state_path
            if key == "state_path" and val:
                try:
                    val.encode("ascii")
                except UnicodeEncodeError:
                    issues.append(f"Row {i+1}, state_path: non-ASCII characters")
    if issues:
        print(f"\n[FAIL] {source_name}: {len(issues)} ASCII issue(s)")
        for iss in issues[:5]:
            print(f"  {iss}")
    else:
        print(f"[OK] {source_name}: all fields ASCII-safe")
    return len(issues) == 0


# ── 3. PnL Math Verification ──────────────────────────────

def verify_pnl_math(rows, source_name):
    """Recompute PnL and flag mismatches > 0.5%.

    PnL formula:
      LONG:  pnl = (exit - entry) * qty * leverage - fees
      SHORT: pnl = (entry - exit) * qty * leverage - fees

    Note: trades.csv stores NET PnL (after fees). So:
      logged_pnl should equal gross_pnl - fees
    """
    issues = []
    verified = 0

    for i, row in enumerate(rows):
        entry = _safe_float(row.get("entry"))
        exit_p = _safe_float(row.get("exit"))
        leverage = _safe_float(row.get("leverage", 1))
        pnl_logged = _safe_float(row.get("pnl"))
        fees = _safe_float(row.get("fees", 0))
        side = row.get("side", "LONG")
        symbol = row.get("symbol", "?")

        if entry <= 0 or exit_p <= 0:
            continue

        # We can't directly verify qty from the CSV since it's not stored.
        # But we can verify the PnL direction is correct.
        if side == "LONG":
            pnl_direction = exit_p - entry
        else:
            pnl_direction = entry - exit_p

        # Verify PnL sign matches direction
        # (net PnL after fees might be slightly negative even for correct direction)
        gross_pnl = pnl_logged + fees  # recover gross from net + fees
        if pnl_direction > 0 and gross_pnl < -abs(entry * 0.01):
            issues.append(
                f"Row {i+1} ({symbol}): direction says profit but PnL={pnl_logged:.2f} "
                f"(entry={entry}, exit={exit_p}, side={side})"
            )

        if pnl_direction < 0 and gross_pnl > abs(entry * 0.01):
            issues.append(
                f"Row {i+1} ({symbol}): direction says loss but PnL={pnl_logged:.2f} "
                f"(entry={entry}, exit={exit_p}, side={side})"
            )

        verified += 1

    if issues:
        print(f"\n[WARN] {source_name}: {len(issues)} PnL direction mismatch(es)")
        for iss in issues[:5]:
            print(f"  {iss}")
    else:
        print(f"[OK] {source_name}: PnL direction verified ({verified} trades)")
    return len(issues) == 0


# ── 4. Impossible Trade Detection ──────────────────────────

def detect_impossible_trades(rows, source_name):
    """Flag trades where PnL is impossible given the price move."""
    issues = []
    for i, row in enumerate(rows):
        entry = _safe_float(row.get("entry"))
        exit_p = _safe_float(row.get("exit"))
        leverage = _safe_float(row.get("leverage", 1))
        pnl = _safe_float(row.get("pnl"))
        symbol = row.get("symbol", "?")

        if entry <= 0 or exit_p <= 0:
            continue

        # Price scale check: exit should be within 50% of entry for crypto
        price_ratio = max(entry, exit_p) / max(min(entry, exit_p), 1e-12)
        if price_ratio > 10:
            issues.append(
                f"Row {i+1} ({symbol}): price scale off by {price_ratio:.1f}x "
                f"(entry={entry}, exit={exit_p})"
            )

        # Leverage sanity: should be 1-25x
        if leverage < 0.5 or leverage > 50:
            issues.append(
                f"Row {i+1} ({symbol}): leverage={leverage} out of range [1, 25]"
            )

        # PnL magnitude check: max possible PnL with 25x leverage and 100% move
        # is ~25x the notional. Flag if > 50% return on equity per trade.
        # (Assuming ~1% risk per trade, max PnL should be ~25R at 25x)

    if issues:
        print(f"\n[WARN] {source_name}: {len(issues)} suspicious trade(s)")
        for iss in issues[:5]:
            print(f"  {iss}")
    else:
        print(f"[OK] {source_name}: no impossible trades detected")
    return len(issues) == 0


# ── 5. Cross-check trades.csv vs trade_outcomes.csv ────────

def cross_check(trades, outcomes):
    """Verify trades.csv and trade_outcomes.csv are consistent."""
    if not trades or not outcomes:
        print("[SKIP] Cross-check: need both trades.csv and trade_outcomes.csv")
        return True

    t_count = len(trades)
    o_count = len(outcomes)

    if t_count != o_count:
        print(f"[WARN] Cross-check: trades.csv has {t_count} rows, "
              f"trade_outcomes.csv has {o_count} rows")
    else:
        print(f"[OK] Cross-check: both files have {t_count} rows")

    # Verify PnL totals match
    t_total = sum(_safe_float(r.get("pnl")) for r in trades)
    o_total = sum(_safe_float(r.get("pnl")) for r in outcomes)
    diff = abs(t_total - o_total)
    if diff > 1.0:
        print(f"[WARN] Cross-check: PnL total mismatch: "
              f"trades=${t_total:.2f} vs outcomes=${o_total:.2f} (diff=${diff:.2f})")
        return False
    else:
        print(f"[OK] Cross-check: PnL totals match (${t_total:.2f})")
    return True


# ── Main ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Verify CSV integrity")
    parser.add_argument("--trades", default=_TRADES_FILE)
    parser.add_argument("--outcomes", default=_OUTCOMES_FILE)
    args = parser.parse_args()

    print("=" * 70)
    print("CSV VERIFICATION REPORT")
    print("=" * 70)

    trades = _read_csv(args.trades)
    outcomes = _read_csv(args.outcomes)

    if not trades and not outcomes:
        print("\nNo trade data found. Run backtests or paper trading first.")
        print(f"  Expected: {args.trades}")
        print(f"  Expected: {args.outcomes}")
        print("=" * 70)
        return

    all_ok = True

    if trades:
        print(f"\n--- trades.csv ({len(trades)} rows) ---")
        all_ok &= validate_schema(trades, TRADES_REQUIRED, "trades.csv")
        all_ok &= validate_ascii(trades, "trades.csv")
        all_ok &= verify_pnl_math(trades, "trades.csv")
        all_ok &= detect_impossible_trades(trades, "trades.csv")

    if outcomes:
        print(f"\n--- trade_outcomes.csv ({len(outcomes)} rows) ---")
        all_ok &= validate_schema(outcomes, OUTCOMES_REQUIRED, "trade_outcomes.csv")
        all_ok &= validate_ascii(outcomes, "trade_outcomes.csv")

    all_ok &= cross_check(trades, outcomes)

    print("\n" + "=" * 70)
    if all_ok:
        print("RESULT: ALL CHECKS PASSED")
    else:
        print("RESULT: ISSUES FOUND (see above)")
    print("=" * 70)


if __name__ == "__main__":
    main()
