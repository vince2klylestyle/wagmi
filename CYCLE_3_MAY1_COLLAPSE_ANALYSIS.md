# CYCLE 3: MAY 1 COLLAPSE FORENSICS & CONFIG VALIDATION

## Part 1: May 1 Collapse Timeline

**Date**: May 1, 2026  
**Context**: Phase 3.2 deployment attempt (aggressive solo-signal allowance)  
**Outcome**: Configuration error caused trading degradation

### Known Facts (from memory):
- **Before May 1** (Phase 2): +$925.84 net P&L on 90-day backtest (55% WR)
- **After May 1** (Phase 3.2 error): System stopped trading effectively
- **Root cause**: Phase 3.2 misconfiguration allowed too many low-quality solo signals

### Questions to Answer:
1. What was the exact error in Phase 3.2 config?
2. How many trades failed and why?
3. What were the bad signal characteristics?
4. How did it break the Phase 2 baseline?
5. What corrected it?

---

## Part 2: Phase 2/3.2 Config Comparison

### Phase 2 (Validated, +$925.84 P&L):
```
min_votes = 2 (strict ensemble)
confidence_floor = 30-55% (symbol-specific)
gates = ENABLED (regime, setup, hour filters)
phase3_filters = DISABLED
strategy_weights = balanced (regime-specific)
```

### Phase 3.2 (Error Config):
```
min_votes = 1 (relaxed, allow solos)
confidence_floor = ??? (need to check)
gates = ENABLED or DISABLED? (unclear)
phase3_filters = ??? (need to check)
strategy_weights = ??? (need to check)
```

---

## Part 3: Configuration Audit

Need to examine:
- `bot/trading_config.py` — base config
- `bot/strategies/ensemble.py` — voting thresholds
- `bot/strategies/phase3_filters.py` — Phase 3 logic
- `bot/data/strategy_weights_per_symbol.json` — per-symbol overrides
- `bot/feedback/adaptive_confidence.py` — dynamic floor calculation
- Git history: What changed around May 1?

---

## Part 4: Trade Forensics Questions

### Signal Quality Issues:
- How many solos passed in Phase 3.2 that wouldn't have in Phase 2?
- What was their average confidence? (likely <30%)
- Which strategies generated low-quality solos?
  - Expected: bollinger_squeeze, monte_carlo_zones (noise)
  - Safe: regime_trend, trend_breakout (higher quality)

### Execution Issues:
- Were stops too tight? (noise whipsaws)
- Were R:R ratios degraded? (bad setup)
- Were signals in bad regimes? (ranging, panic)

### System Issues:
- Did Phase 3 filters even fire? Or get bypassed?
- Did gates malfunction?
- Did leverage get miscalculated?

---

## Part 5: Current State Assessment

### What's Proven:
✅ Phase 2 works (55% WR, +$925.84)  
✅ Phase 3 ADX mapping fixed (regime→min_votes)  
✅ Phase 3 filters code is sound (11 tests passing)

### What's Unknown:
❓ Why Phase 3.2 config broke the system  
❓ Current exact configuration state  
❓ Whether Phase 3 fix actually activates Phase 3 filters  
❓ Whether Phase 3 filters are too lenient or strict  

### What's Needed:
🔍 Deep dive into May 1 git history  
🔍 Review current ensemble.py for any lingering issues  
🔍 Analyze Phase 3 filter logic for over-relaxation  
🔍 Test Phase 2 baseline (without Phase 3) to confirm it still works  

---

## Next Steps

### Action 1: Git History Investigation
```bash
git log --oneline --all | grep -i "phase 3\|may 1\|collapse"
git show <commit> -- bot/trading_config.py
git show <commit> -- bot/strategies/ensemble.py
```

### Action 2: Config Review
Review current files to find any aggressive settings that broke things:
- min_votes_required setting
- confidence_floor values
- phase3_filters enabled state
- AGGRESSIVE_MODE flag

### Action 3: Phase 2 Baseline Test
Run backtest with Phase 3 DISABLED:
```bash
python run.py backtest --symbols BTC,SOL --days 7 --phase2-only
```

This confirms Phase 2 still delivers the +925 baseline.

### Action 4: Phase 3 Filter Audit
Review bot/strategies/phase3_filters.py:
- Are strategy-specific floors too low?
- Is clustering filter too lenient?
- Are regex rules correct?

---

**Status**: Investigation not yet started  
**Confidence**: Can solve with code review + testing  
**Time Estimate**: 30-45 minutes for complete forensics

