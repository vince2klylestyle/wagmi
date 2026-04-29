# Live Monitoring Guide - WAGMI Trading System

## Quick Start

### Option 1: Interactive CLI Dashboard (Recommended)
```bash
# Show real-time trading activity (refreshes every 2s)
python cli_monitor.py live

# Show detailed market analysis and agent decisions
python cli_monitor.py analysis

# Show signal pipeline and gate rejections
python cli_monitor.py signals

# Show agent thought protocol and reasoning
python cli_monitor.py thinking

# Show system health and performance
python cli_monitor.py health

# Show everything combined
python cli_monitor.py full
```

### Option 2: Direct Log Streaming
```bash
# Watch paper trading in real-time (follow mode)
tail -f /tmp/phase3_live_paper.log

# Get latest 100 lines with timestamps
tail -100 /tmp/phase3_live_paper.log

# Filter for specific activities
tail -100 /tmp/phase3_live_paper.log | grep "SIGNAL\|TRADE\|GATE"
```

### Option 3: Command-Line Quick Checks
```bash
# Count trades by symbol in the last run
grep "TRADE EXECUTED" /tmp/phase3_live_paper.log | cut -d' ' -f3 | sort | uniq -c

# Show current equity and P&L
tail -1 /tmp/phase3_live_paper.log | grep "HEARTBEAT"

# List all rejections by gate type
grep "REJECTED\|gate=" /tmp/phase3_live_paper.log | grep -o "gate=[^ ]*" | sort | uniq -c

# Show signal generation rate (signals per hour)
echo "Signals in last hour: $(grep -c 'SIGNAL GENERATED' /tmp/phase3_live_paper.log)"
```

---

## Understanding the Monitoring Modes

### LIVE MODE
Real-time view of what's actually trading:
- Current market regimes (trending, ranging, volatile, etc.)
- Latest 5 signals generated (with confidence bars)
- Latest 5 executed trades (with P&L)
- System activity log (last 10 events)

**Use this to**: Watch trades execute, confirm signal quality, catch rejections immediately

### ANALYSIS MODE
Deep dive into market understanding:
- Symbol-by-symbol regime breakdown with metrics (ADX, ATR, slope)
- Ensemble voting summary (how strategies agree/disagree)
- Gate decision audit (what passed, what failed and why)

**Use this to**: Understand why certain symbols aren't getting signals, verify regime classification, check gate accuracy

### SIGNALS MODE
Pipeline visibility and rejection breakdown:
- Signal generation count
- Execution rate (what % of signals become trades)
- Rejection rate breakdown by gate:
  - confidence_floor (too low confidence)
  - fee_drag (fees > profit)
  - leverage_gate (liquidation risk)
  - position_limit (max position size)
  - insufficient_votes (ensemble didn't agree)
  - circuit_breaker (daily loss limit hit)

**Use this to**: Identify the bottleneck in your pipeline (where signals die)

### THINKING MODE
Agent internal reasoning:
- What each agent observed (market data, patterns)
- What each agent recalled (memory, historical context)
- How each agent reasoned through the decision
- What decision each agent made
- Why they chose that decision

**Use this to**: Verify agent quality, debug decision chains, confirm LLM isn't hallucinating

### HEALTH MODE
System operational status:
- Current equity and daily P&L
- Open positions count
- Win rate (last 20 trades)
- API call count and cache hits
- Warnings and errors (last 5)
- Operational status (is trading running?)

**Use this to**: Quick health check, catch crashes before they cost money, monitor API rate limits

---

## Common Analysis Workflows

### "Why aren't we trading SOL?"
```bash
# 1. Check ANALYSIS mode to see SOL regime
python cli_monitor.py analysis
# Look for SOL in the regime output

# 2. Check SIGNALS mode for rejection breakdown
python cli_monitor.py signals
# Look for SOL-specific rejections in logs

# 3. Search logs for SOL signals
grep "SOL.*SIGNAL\|SOL.*REJECT" /tmp/phase3_live_paper.log
```

### "Are the gates too strict?"
```bash
# Show rejection breakdown
python cli_monitor.py signals
# If most rejections are from confidence_floor or insufficient_votes,
# gates might be too strict. If most are fee_drag or liquidation,
# data quality might be the issue.
```

### "Is the system actually using Phase 3 changes?"
```bash
# Check Phase 3 config (confidence_floor at 20%)
grep "confidence_floor.*20" bot/strategies/ensemble.py

# Check for monte_carlo_zones solos in log
grep "monte_carlo_zones.*solo" /tmp/phase3_live_paper.log

# Check symbol-specific micro-filters active
grep "SOL.*65\|BTC.*70" /tmp/phase3_live_paper.log
```

### "What's the real signal generation rate?"
```bash
# Count SIGNAL entries (all generated signals)
echo "Total signals: $(grep -c 'SIGNAL' /tmp/phase3_live_paper.log)"

# Count TRADE EXECUTED (signals that became trades)
echo "Executed trades: $(grep -c 'TRADE EXECUTED' /tmp/phase3_live_paper.log)"

# Calculate conversion rate
signals=$(grep -c 'SIGNAL' /tmp/phase3_live_paper.log || echo 1)
trades=$(grep -c 'TRADE EXECUTED' /tmp/phase3_live_paper.log || echo 0)
rate=$((trades * 100 / signals))
echo "Signal conversion rate: ${rate}%"
```

---

## Key Metrics to Watch

| Metric | Target | Warning | Critical |
|--------|--------|---------|----------|
| Daily P&L | Positive | Flat | < -$500 |
| Win Rate | > 55% | 40-55% | < 40% |
| Signal Throughput | 100+ per day | 50-100 | < 50 |
| Execution Rate | > 2% | 1-2% | < 1% |
| Avg Trade Time | 1-6h | Variable | Holding losses |
| Confidence Floor Active | 20% | 30%+ | > 50% |

---

## Phase 3 Implementation Checklist

Verify these are active:

- ✅ confidence_floor: 20.0 (was 69%)
- ✅ ranging_confidence_floor: 20.0 (was 69%)
- ✅ _PROVEN_SOLO_STRATEGIES includes monte_carlo_zones
- ✅ monte_carlo_zones min_confidence: 60%
- ✅ SOL SHORT micro-filter: 65% (was 75%)
- ✅ BTC LONG micro-filter: 70% (was 80%)

Check with:
```bash
grep "confidence_floor.*20\|monte_carlo_zones\|_PROVEN_SOLO" bot/strategies/ensemble.py | head -5
```

---

## Autonomous Loop Status

Three loops are constantly improving the system:

1. **Real Hyperliquid KB Loop** (KB v642+)
   - Analyzes real market data
   - Tests decision thresholds
   - Current finding: GO trades at 50% WR, SKIP at 22%

2. **Fresh Validated KB Loop** (KB v1293+)
   - Tests new KB versions on recent candles
   - Validates no data leakage
   - Currently: Limited fresh data (waiting for live trades)

3. **Large Analysis Loop** (KB v1169+)
   - Backtests full history
   - Identifies edge patterns
   - Current: 25.4% win rate baseline, identifies 50% accurate agent

---

## Troubleshooting

### Paper trading exited unexpectedly
```bash
# Check last error in log
tail -50 /tmp/phase3_live_paper.log | grep -E "ERROR|Exception|Traceback"

# Restart trading
cd bot && python run.py paper
```

### No signals being generated
```bash
# Check regime classification is working
grep "[REGIME]" /tmp/phase3_live_paper.log | tail -5

# Check symbol filters aren't blocking everything
grep "disabled.*regime_trend\|Symbol.*REJECT" /tmp/phase3_live_paper.log | wc -l

# Check confidence floor isn't set too high
grep "confidence_floor" /tmp/phase3_live_paper.log | tail -1
```

### All signals are being rejected
```bash
# See which gate is rejecting
python cli_monitor.py signals
# Check the rejection breakdown

# If insufficient_votes: ensemble might not have enough agreement
# If confidence_floor: lower the threshold further
# If fee_drag: tight stop losses are eating profits
```

### LLM API errors
```bash
# Check for auth issues
grep "API call FAILED\|Unauthorized" /tmp/phase3_live_paper.log

# Check rate limiting
grep "rate limited\|429\|quota" /tmp/phase3_live_paper.log

# Check fallback to monolithic LLM
grep "falling back to monolithic" /tmp/phase3_live_paper.log
```

---

## Manual Monitoring During Trading

### Every 15 minutes
```bash
python cli_monitor.py live    # Check signals are flowing
python cli_monitor.py health   # Quick system check
```

### Every Hour
```bash
python cli_monitor.py analysis   # Regime accuracy check
python cli_monitor.py signals    # Gate efficiency review
```

### Every 4 Hours
```bash
# Full status review
python cli_monitor.py full
# Then review bot/data/decisions.jsonl for P&L patterns
```

---

## Expected Behavior (Phase 3)

### Signal Generation
- **Before Phase 3**: 4 trades in 60 days (0.2% candle→trade conversion)
- **After Phase 3**: Target 150-300 trades in 60 days (3-5x improvement)
- **Reason**: Confidence floor 69%→20% unlocks low-confidence signals for risk/EV gates

### Gate Breakdown
- **Confidence floor**: Drops from rejecting 99%+ to ~50-60%
- **Risk/EV gates**: Now handling more signals, filtering by actual edge
- **Execution rate**: Should see monte_carlo_zones and symbol solos executing

### P&L Impact
- **Short-term**: Higher volume = more data, but may dilute accuracy
- **Medium-term** (50-100 trades): Validate that 20% confidence floor + micro-filters stays profitable
- **Long-term**: Use data to refine micro-filter thresholds (Phase 4)

---

## Next Steps

1. **Monitor for 24-48 hours** → Collect 20-50 live trades
2. **Analyze signal quality** → Which symbols/setups are profitable?
3. **Refine thresholds** → Adjust confidence floors based on patterns
4. **Phase 4 planning** → Profit factor gating, regime-specific rules

Keep using `/health-check quick` and `python cli_monitor.py live` during this period.
