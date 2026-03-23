# Mechanical Bot System - Quick Start Guide

Fast reference for using the mechanical bot understanding system.

## 1. Wire Instrumentation (One-time Setup)

Add to `multi_strategy_main.py` after ensemble voting:

```python
from llm.mechanical_bot_instrumentation import get_mechanical_bot_instrumentation

instr = get_mechanical_bot_instrumentation()

# After ensemble generates signal
if signal_result:
    instr.on_signal_generated(
        signal_id=f"{symbol}_{int(time.time()*1000)%100000}",
        symbol=symbol,
        regime=snapshot["regime"],
        volatility_percentile=snapshot["volatility_pct"],
        alignment_score=snapshot["alignment"],
        btc_correlation=snapshot["btc_corr"],
        time_of_day=datetime.now().hour,
        side=signal_result.side,
        confidence=signal_result.confidence,
        num_strategies=len(signal_result.strategy_names),
        strategy_names=signal_result.strategy_names,
        entry_price=signal_result.entry,
    )
    signal_result.metadata["mech_signal_id"] = signal_id

# When position opens
instr.on_position_opened(
    trade_id=position.trade_id,
    signal_id=signal_result.metadata["mech_signal_id"],
    symbol=symbol,
    side=position.side,
    entry_price=position.entry_price,
    current_price=current_price,
    regime=snapshot["regime"],
    volatility=snapshot["volatility_pct"],
    alignment_score=snapshot["alignment"],
    initial_confidence=position.confidence,
    strategy_votes=position.num_votes,
)

# When position changes state (TP near, SL near, etc)
instr.on_position_state_change(
    trade_id=position.trade_id,
    phase="tp1_approached",  # or "sl_hit", "trailing", etc
    current_price=market_price,
    entry_price=position.entry_price,
    regime=snapshot["regime"],
    volatility=snapshot["volatility_pct"],
    alignment_score=snapshot["alignment"],
    position_pnl=pnl,
    position_pnl_pct=(pnl/risk)*100,
    distance_to_tp1_pct=distance,
    distance_to_sl_pct=distance,
)

# When position closes
instr.on_position_closed(
    trade_id=position.trade_id,
    signal_id=signal_result.metadata["mech_signal_id"],
    exit_price=position.exit_price,
    exit_reason="tp1_hit",  # or "sl_hit", "manual", etc
    pnl=position.pnl,
    pnl_pct=(position.pnl/risk)*100,
)
```

See `MECHANICAL_BOT_INTEGRATION.md` for complete wiring guide.

## 2. Run Paper Trading

Let the system accumulate data:
```bash
cd bot
python run.py paper
# Let it run for 24+ hours to get 50+ trades
```

## 3. Generate Analysis Report

```python
from llm.mechanical_bot_report import get_mechanical_bot_report_generator

gen = get_mechanical_bot_report_generator()

# Full report
report = gen.generate_comprehensive_report()
gen.save_report(report, "bot_analysis.json")

# Print summary to console
print(gen.print_report_summary())
```

Output shows:
- Signal metrics (execution rate, win rate, PnL)
- Top mechanical edges
- Identified trading gaps
- Regime/time-of-day performance
- Failure analysis

## 4. View Specific Analysis

### Signal Metrics
```python
from llm.mechanical_bot_report import get_mechanical_bot_report_generator
gen = get_mechanical_bot_report_generator()
sig_report = gen.generate_signal_report()
print(sig_report)
```

### Mechanical Bot Edges
```python
from llm.mechanical_bot_analyzer import get_mechanical_bot_analyzer
analyzer = get_mechanical_bot_analyzer()

edges = analyzer.identify_mechanical_bot_edges(top_n=5)
for edge in edges:
    print(f"{edge.edge_name}")
    print(f"  Condition: {edge.condition}")
    print(f"  Win Rate: {edge.win_rate:.0%}")
    print(f"  PnL: ${edge.total_pnl:.2f}")
```

### Trading Gaps
```python
analyzer = get_mechanical_bot_analyzer()

gaps = analyzer.identify_gaps(top_n=5)
for gap in gaps:
    print(f"Gap: {gap.description}")
    print(f"  Opportunity: ${gap.potential_pnl:.2f}")
    print(f"  Frequency: {gap.expected_frequency}")
```

### Performance by Regime
```python
analyzer = get_mechanical_bot_analyzer()

regime_perf = analyzer.get_regime_performance()
for regime, perf in regime_perf.items():
    print(f"{regime}: {perf['win_rate']:.0%} WR ({perf['wins']}W/{perf['losses']}L)")
```

### Performance by Time
```python
analyzer = get_mechanical_bot_analyzer()

time_perf = analyzer.get_time_of_day_performance()
for hour in sorted(time_perf.keys()):
    perf = time_perf[hour]
    print(f"{hour:02d}:00 - {perf['count']} trades, {perf['win_rate']:.0%} WR")
```

## 5. Generate Synthetic Signals

```python
from llm.mechanical_bot_synthesis import get_mechanical_bot_synthesizer

synth = get_mechanical_bot_synthesizer()

# Generate gap-filling signals
gap_ideas = synth.generate_gap_filling_signals(symbol="BTC", max_ideas=5)

# Generate edge-boosting signals
boost_ideas = synth.generate_edge_boosting_signals(symbol="BTC")

# Generate time-based signals
time_ideas = synth.generate_time_based_signals(symbol="BTC")

# Convert to executable signals
for idea in gap_ideas:
    signal = synth.convert_idea_to_signal(idea, current_price=42000)
    if signal:
        # Send to ensemble
        result = ensemble.evaluate_llm_signal(signal)
```

## 6. Track Trade Evolution

```python
from llm.mechanical_bot_state_tracker import get_mechanical_bot_state_tracker

tracker = get_mechanical_bot_state_tracker()

# Get completed trade analysis
analysis = tracker.analyze_state_evolution("trade_123")
print(f"Initial confidence: {analysis['initial_confidence']:.0f}%")
print(f"Final confidence: {analysis['final_confidence']:.0f}%")
print(f"Confidence trend: {analysis['confidence_trend']}")
print(f"Major drops: {len(analysis['major_confidence_drops'])}")
```

## 7. Get Memory Report

```python
from llm.mechanical_bot_memory import get_mechanical_bot_memory

memory = get_mechanical_bot_memory()

# Get summary
report = memory.get_memory_report()
print(f"Total signals: {report['signal_metrics']['total_signals']}")
print(f"Win rate: {report['signal_metrics']['win_rate']}")
print(f"Patterns: {report['pattern_metrics']['patterns_discovered']}")
```

## Quick Commands

### Get all reports
```python
from llm.mechanical_bot_report import get_mechanical_bot_report_generator
gen = get_mechanical_bot_report_generator()
full = gen.generate_comprehensive_report()
gen.save_report(full)
print(gen.print_report_summary())
```

### Get top edges
```python
from llm.mechanical_bot_analyzer import get_mechanical_bot_analyzer
analyzer = get_mechanical_bot_analyzer()
for edge in analyzer.identify_mechanical_bot_edges(top_n=3):
    print(f"{edge.edge_name}: {edge.win_rate:.0%} WR, ${edge.total_pnl:.2f}")
```

### Get identified gaps
```python
analyzer = get_mechanical_bot_analyzer()
for gap in analyzer.identify_gaps(top_n=3):
    print(f"{gap.description}")
```

### Generate synthetic signals
```python
from llm.mechanical_bot_synthesis import get_mechanical_bot_synthesizer
synth = get_mechanical_bot_synthesizer()
ideas = synth.generate_gap_filling_signals("BTC", max_ideas=3)
for idea in ideas:
    print(f"{idea.gap_description} (Confidence: {idea.confidence:.0f}%)")
```

### Get synthesis plan
```python
synth = get_mechanical_bot_synthesizer()
plan = synth.get_synthesis_plan("BTC")
print(f"Ideas: {len(plan.signal_ideas)}")
print(f"Expected trades/day: {plan.expected_additional_trades_per_day:.1f}")
print(f"Expected win rate: {plan.expected_win_rate:.0%}")
```

## Data Files Generated

```
data/llm/mechanical_bot_memory/
├── signals.jsonl           # All signals (append-only)
├── patterns.jsonl          # Pattern updates
├── failures.jsonl          # Loss records
└── successes.jsonl         # Win records

data/llm/mechanical_bot_state/
├── state_history.jsonl     # State transitions
└── trade_*.json            # Individual trade histories

data/llm/reports/
└── mechanical_bot_report_YYYYMMDD_HHMMSS.json  # Reports
```

## Performance

- **Memory**: <1MB for 1000 signals
- **CPU**: <0.1ms per hook
- **Storage**: ~500B per signal + 100B per state
- **All I/O**: Append-only (efficient)

## Troubleshooting

### No data showing?
- Check hooks are wired
- Check `data/llm/mechanical_bot_memory/` exists
- Need at least 1 complete trade cycle

### Wrong analysis?
- Need minimum 5+ trades per pattern
- Minimum 10 trades for reliable edges
- Minimum 50+ trades for comprehensive analysis

### Reports empty?
- Run full paper trading session
- Check `generate_comprehensive_report()` vs specific report
- Verify at least 1 trade completed

## Architecture

```
Data Collection              Analysis                Synthesis
─────────────────────────────────────────────────────────
on_signal_generated ──► Memory stores  ──► Analyzer finds  ──► Synthesizer
on_position_opened          signal          edges & gaps        generates
on_position_state_change    & context                           signals
on_position_closed
capture_market_snapshot

                           Reporter
                           Generates
                           Reports
```

## Next Steps

1. Wire instrumentation (see `MECHANICAL_BOT_INTEGRATION.md`)
2. Run paper trading 24-100 hours
3. Generate analysis report
4. Review edges and gaps
5. Generate synthetic signals
6. Test in paper trading
7. Measure LLM value-add

## Full Documentation

- System overview: `MECHANICAL_BOT_SYSTEM_OVERVIEW.md`
- Integration guide: `MECHANICAL_BOT_INTEGRATION.md`
- Memory unit: `mechanical_bot_memory.py`
- Analyzer: `mechanical_bot_analyzer.py`
- State tracker: `mechanical_bot_state_tracker.py`
- Instrumentation: `mechanical_bot_instrumentation.py`
- Reports: `mechanical_bot_report.py`
- Synthesis: `mechanical_bot_synthesis.py`
