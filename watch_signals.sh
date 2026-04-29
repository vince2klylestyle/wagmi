#!/bin/bash
# Real-time signal watcher - streams market thinking in real-time

LOG_FILE="/tmp/phase3_live_paper.log"
REFRESH_RATE=${1:-2}

if [ ! -f "$LOG_FILE" ]; then
    echo "Log file not found: $LOG_FILE"
    echo "Start paper trading first: cd bot && python run.py paper"
    exit 1
fi

echo "=== WAGMI SIGNAL WATCHER - Real-time Market Thinking ==="
echo "Refresh rate: ${REFRESH_RATE}s | Press Ctrl+C to stop"
echo ""

# Keep track of last shown line number
LAST_LINE=0

while true; do
    clear

    echo "╔═══════════════════════════════════════════════════════════════════════════════╗"
    echo "║ SYMBOL REGIMES (Current Market States)                                        ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════════╝"

    # Show regime analysis
    grep "\[REGIME\]" "$LOG_FILE" | tail -4 | while read line; do
        # Clean ANSI codes and parse
        clean=$(echo "$line" | sed 's/\x1b\[[0-9;]*m//g')
        if [[ $clean =~ \[REGIME\] ]]; then
            content="${clean#*[REGIME] }"
            symbol=$(echo "$content" | cut -d: -f1)
            regime=$(echo "$content" | cut -d: -f2 | cut -d'|' -f1 | xargs)

            case "$regime" in
                "trending_bull") emoji="🟢" ;;
                "trending_bear") emoji="🔴" ;;
                "range") emoji="⚪" ;;
                "high_volatility") emoji="⚡" ;;
                "low_liquidity") emoji="💧" ;;
                *) emoji="❓" ;;
            esac

            printf "%s %-8s %s\n" "$emoji" "$symbol" "$regime"
        fi
    done

    echo ""
    echo "╔═══════════════════════════════════════════════════════════════════════════════╗"
    echo "║ LATEST SIGNALS (What We Want to Trade)                                       ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════════╝"

    # Show recent signals
    grep -E "SIGNAL|confidence" "$LOG_FILE" | tail -10 | grep -v "^\s*$" | while read line; do
        clean=$(echo "$line" | sed 's/\x1b\[[0-9;]*m//g')
        if [[ $clean =~ \[.*\] ]]; then
            # Extract symbol and confidence if present
            if [[ $clean =~ ([A-Z]{3,4}).*confidence ]] || [[ $clean =~ ([A-Z]{3,4}) ]]; then
                echo "  $clean" | cut -c1-85
            fi
        fi
    done

    echo ""
    echo "╔═══════════════════════════════════════════════════════════════════════════════╗"
    echo "║ GATE STATUS (What's Blocking Trades)                                         ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════════╝"

    # Count rejections by type
    echo "  Confidence floor: $(grep -c 'confidence.*floor\|confidence_floor' "$LOG_FILE" 2>/dev/null || echo '0')"
    echo "  Fee drag:         $(grep -c 'fee.*drag\|fee_drag' "$LOG_FILE" 2>/dev/null || echo '0')"
    echo "  Insufficient votes: $(grep -c 'insufficient.*vote' "$LOG_FILE" 2>/dev/null || echo '0')"
    echo "  Leverage gate:    $(grep -c 'leverage\|liquidation' "$LOG_FILE" 2>/dev/null || echo '0')"
    echo "  Position limit:   $(grep -c 'position.*limit' "$LOG_FILE" 2>/dev/null || echo '0')"

    echo ""
    echo "╔═══════════════════════════════════════════════════════════════════════════════╗"
    echo "║ P&L SUMMARY (Current Performance)                                            ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════════╝"

    # Extract latest heartbeat
    grep "HEARTBEAT" "$LOG_FILE" | tail -1 | while read line; do
        clean=$(echo "$line" | sed 's/\x1b\[[0-9;]*m//g')
        equity=$(echo "$clean" | grep -o "equity=\$[0-9,.]*" | head -1)
        pnl=$(echo "$clean" | grep -o "daily_pnl=\$[^[:space:]]*" | head -1)
        wr=$(echo "$clean" | grep -o "WR[0-9]*=[0-9%]*" | head -1)

        echo "  $equity | $pnl | $wr"
    done

    echo ""
    echo "Last updated: $(date '+%H:%M:%S') | Watching: $LOG_FILE"
    echo "Press Ctrl+C to stop (next refresh in ${REFRESH_RATE}s...)"

    sleep "$REFRESH_RATE"
done
