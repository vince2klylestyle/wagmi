#!/usr/bin/env bash
# Nightly Replay Audit
# Runs the replay engine against today's trade log and posts summary to Telegram.
# Schedule via cron: 0 0 * * * /path/to/nightly_replay.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BOT_DIR="$SCRIPT_DIR/../bot"
LOG_DIR="$SCRIPT_DIR/../data/logs"
REPLAY_LOG="$LOG_DIR/nightly_replay_$(date +%Y%m%d).txt"

cd "$BOT_DIR"

echo "=== Nightly Replay Audit $(date -u) ===" | tee "$REPLAY_LOG"

# Find today's trade log
TRADE_LOG="$LOG_DIR/trades_enhanced.csv"
if [ ! -f "$TRADE_LOG" ]; then
    TRADE_LOG="$SCRIPT_DIR/../data/analysis/trade_candidates.csv"
fi

if [ ! -f "$TRADE_LOG" ]; then
    echo "No trade log found. Skipping replay." | tee -a "$REPLAY_LOG"
    exit 0
fi

# Run replay
python cli.py --mode replay --replay-file "$TRADE_LOG" 2>&1 | tee -a "$REPLAY_LOG"
REPLAY_EXIT=$?

# Save telemetry snapshot
python -c "
import sys; sys.path.insert(0, '.')
from data.fetchers.telemetry import Telemetry
Telemetry.save_snapshot()
print('Telemetry snapshot saved.')
" 2>&1 | tee -a "$REPLAY_LOG"

# Post to Telegram if configured
if [ -n "${TELEGRAM_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
    # Truncate message to 4000 chars (Telegram limit)
    SUMMARY=$(head -c 3900 "$REPLAY_LOG")
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
        -d chat_id="$TELEGRAM_CHAT_ID" \
        -d text="$SUMMARY" \
        -d parse_mode="Markdown" > /dev/null 2>&1 || true
    echo "Posted to Telegram." | tee -a "$REPLAY_LOG"
fi

echo "=== Replay complete (exit=$REPLAY_EXIT) ===" | tee -a "$REPLAY_LOG"
exit $REPLAY_EXIT
