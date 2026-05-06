#!/usr/bin/env python3
"""
Emergency script to clear stale position state from position manager.
The position manager thinks SOL has an open LONG from April 1,
but all trades are actually closed.
"""
import json
from pathlib import Path

# Load position manager state
state_file = Path("data/position_state.json")
if state_file.exists():
    with open(state_file) as f:
        state = json.load(f)

    positions = state.get("positions", {})
    print(f"Loaded {len(positions)} positions from {state_file}")

    # Remove SOL if it exists
    if "SOL" in positions:
        sol_pos = positions.pop("SOL")
        print(f"Removed stale SOL position: {sol_pos.get('side')} entry={sol_pos.get('entry')}")

        # Save cleaned state
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)
        print(f"Saved cleaned state to {state_file}")
    else:
        print("No SOL position found in state")
else:
    print(f"State file not found: {state_file}")

# Also check in-memory position objects (if bot is running)
print("\nNote: Stop the bot and restart to load the cleaned state.")
