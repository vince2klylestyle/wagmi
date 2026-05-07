#!/usr/bin/env python3
"""
Persistent bot runner with auto-restart capability.
Keeps the trading bot running continuously by restarting on exit.
Used for audit trade accumulation (CP19/CP20).
"""

import subprocess
import time
import os
import sys
import json
from datetime import datetime, timezone

LOG_FILE = "bot_persistent_run.log"
TRADE_FILE = "data/closed_trades.csv"
STATE_FILE = "bot_persistent_state.json"

def log_msg(msg):
    """Log message to both file and stdout."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{ts}] {msg}"
    try:
        print(full_msg)
    except UnicodeEncodeError:
        # Fallback for Windows console
        print(full_msg.encode('ascii', 'replace').decode('ascii'))
    with open(LOG_FILE, "a", encoding='utf-8') as f:
        f.write(full_msg + "\n")

def count_trades():
    """Count closed trades from CSV."""
    try:
        with open(TRADE_FILE, "r") as f:
            lines = f.readlines()
        return len(lines) - 1  # Exclude header
    except FileNotFoundError:
        return 0

def get_state():
    """Load persistent state."""
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"starts": 0, "restarts": 0, "last_trade_count": 0, "start_time": None}

def save_state(state):
    """Save persistent state."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def main():
    """Run bot persistently with auto-restart."""
    log_msg("=" * 60)
    log_msg("PERSISTENT BOT RUNNER STARTED")
    log_msg("=" * 60)

    state = get_state()
    if state["start_time"] is None:
        state["start_time"] = datetime.now(timezone.utc).isoformat()

    target_trades = 50  # CP20 target
    max_runtime_hours = 48
    max_runtime_seconds = max_runtime_hours * 3600

    start_time = time.time()
    restart_count = 0

    while True:
        elapsed_hours = (time.time() - start_time) / 3600
        current_trades = count_trades()

        # Check completion gates
        if current_trades >= target_trades:
            log_msg(f"[SUCCESS] TARGET REACHED: {current_trades} trades (target={target_trades})")
            log_msg("AUDIT CHECKPOINT 20 READY FOR STATISTICAL VALIDATION")
            state["final_trade_count"] = current_trades
            state["completion_time"] = datetime.now(timezone.utc).isoformat()
            save_state(state)
            break

        if elapsed_hours > max_runtime_hours:
            log_msg(f"[TIMEOUT] {elapsed_hours:.1f} hours elapsed (max={max_runtime_hours}h)")
            log_msg(f"[TRADES] Accumulated: {current_trades}/{target_trades}")
            state["final_trade_count"] = current_trades
            state["timeout"] = True
            save_state(state)
            break

        # Log status
        progress_pct = (current_trades / target_trades) * 100
        log_msg(f"[CYCLE {restart_count + 1}] Starting bot | Trades: {current_trades}/{target_trades} ({progress_pct:.1f}%) | Elapsed: {elapsed_hours:.1f}h")

        # Start bot process
        try:
            process = subprocess.Popen(
                ["python", "run.py", "paper"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            restart_count += 1
            state["starts"] = restart_count

            # Monitor process for a time window
            monitor_timeout = 300  # 5 minutes per cycle
            start_monitor = time.time()
            line_count = 0

            while (time.time() - start_monitor) < monitor_timeout:
                try:
                    line = process.stdout.readline()
                    if line:
                        line_count += 1
                        # Log key events
                        if "HEARTBEAT" in line or "ERROR" in line or "Exception" in line:
                            log_msg(f"  [BOT] {line.strip()}")
                    else:
                        # EOF reached
                        break
                except:
                    break

                # Check if trades accumulating
                new_trades = count_trades()
                if new_trades > current_trades:
                    log_msg(f"  [NEW_TRADE] Total={new_trades}")
                    current_trades = new_trades
                    monitor_timeout = 300  # Reset timeout on new trade
                    start_monitor = time.time()

            # Terminate if still running
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except:
                    process.kill()

            log_msg(f"  [BOT] Process exited (read {line_count} log lines)")

        except Exception as e:
            log_msg(f"[ERROR] {e}")

        # Check for trades after this cycle
        new_trades = count_trades()
        if new_trades > current_trades:
            log_msg(f"  [CYCLE_RESULT] {new_trades - current_trades} new trade(s)")

        # Brief pause before restart
        log_msg(f"  [WAITING] 10s before restart...")
        time.sleep(10)

if __name__ == "__main__":
    main()
