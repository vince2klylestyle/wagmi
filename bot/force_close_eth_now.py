#!/usr/bin/env python3
"""
Emergency close stuck ETH SHORT position to unblock trade accumulation.
Position has been open 85+ minutes, TIME_STOP threshold approaching.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

# Load current position state
state_path = Path("data/position_state.json")
if not state_path.exists():
    print("❌ No position state file found")
    sys.exit(1)

with open(state_path) as f:
    state = json.load(f)

# Find ETH position
eth_pos = state["positions"].get("ETH")
if not eth_pos:
    print("❌ No ETH position found")
    sys.exit(1)

if eth_pos["state"] != "OPEN":
    print(f"❌ ETH position not OPEN (state={eth_pos['state']})")
    sys.exit(1)

# Close at current entry price (market close, realize current loss/gain)
entry = eth_pos["entry"]
current_price = 2323.45  # Current market price
qty = eth_pos["qty"]
leverage = eth_pos["leverage"]

# SHORT position PnL: (entry - exit) * qty * leverage
if eth_pos["side"] == "SHORT":
    pnl = (entry - current_price) * qty * leverage
else:
    pnl = (current_price - entry) * qty * leverage

print(f"\n[FORCE_CLOSE] Closing ETH {eth_pos['side']} Position")
print(f"   Entry: {entry}")
print(f"   Close: {current_price}")
print(f"   Qty: {qty} @ {leverage}x")
print(f"   Est. PnL: ${pnl:.2f}")

# Update position state
eth_pos["state"] = "CLOSED"
eth_pos["qty"] = 0
eth_pos["close_time"] = datetime.now(timezone.utc).isoformat()
eth_pos["realized_pnl"] = pnl
eth_pos["state_path"].append("CLOSED")
eth_pos["outcome"] = "MANUAL_CLOSE_EMERGENCY"

# Remove from active positions
del state["positions"]["ETH"]
state["position_count"] = len(state["positions"])
state["saved_at"] = datetime.now(timezone.utc).isoformat()

# Save
with open(state_path, "w") as f:
    json.dump(state, f, indent=2)

print(f"\n[SUCCESS] Position closed. Remaining positions: {state['position_count']}")
print(f"   Bot can now enter new trades")
