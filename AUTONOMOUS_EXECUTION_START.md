# Autonomous Execution — Ready to Start

**Generated**: 2026-04-27, 18:15 UTC  
**Status**: ✅ BLUEPRINT COMPLETE, READY TO BEGIN  
**Next Action**: Start Week 3-A implementation

---

## What You'll Find

### Reference Documents (CRITICAL — READ FIRST)

1. **WEEKS3-6_BLUEPRINT.md** (1,600 lines)
   - Complete specification for all work
   - Every component detailed with:
     - Purpose, input/output, integration points
     - Code samples (patterns to follow)
     - Test requirements (min 20 lines per module)
     - Success criteria
   - Two Week 6 paths (Ollama vs Deepen) — choose one or do both

2. **SESSION_HANDOFF.md** (340 lines)
   - Week 1-2 completion summary
   - Current bot status: canary mode, BTC-only, all systems healthy
   - All 30 smoke tests passing
   - Infrastructure ready for Week 3

3. **WEEK2_STATUS.md** (320 lines)
   - Technical details of backend abstraction (310 lines)
   - Audit logging integration (260 lines)
   - Test results (11/11 passing)
   - Deployment readiness assessment

### Architectural Reference

- `bot/llm/backend.py` — Backend abstraction layer (CliBackend, ApiBackend, OllamaBackend, BackendRouter)
- `bot/llm/audit_logger.py` — decisions.jsonl audit trail (260 lines)
- `bot/llm/agents/coordinator.py` — Multi-agent orchestration (integration points marked)
- `bot/trading_config.py` — All tunable parameters (use for new agent configs)
- `bot/tests/test_backend_integration.py` — Test patterns to emulate (320+ lines)

### Git State

- **Current branch**: `claude/memegine-telegram-pipeline-4otXQ`
- **Recent commits**: 
  - `f74255e` — Fix Phase 1 regime detection
  - `6b3049b` — MASTER BUILD: Omniscient integration
  - `eec955f` — Critical fixes for signal confidence
- **All changes committed** — working directory clean

---

## How to Begin Week 3

**Autonomous execution permission**: Granted ("will work autonomously on it")

### Step 1: Read the Blueprint (20 min)

```bash
# skim the structure
head -100 WEEKS3-6_BLUEPRINT.md

# understand Week 3 components
sed -n '/^## WEEK 3/,/^## WEEK 4/p' WEEKS3-6_BLUEPRINT.md | head -200
```

### Step 2: Verify Bot Health (5 min)

```bash
cd bot
python run.py signals  # Quick signal check
tail -50 logs/canary.log  # Review latest logs
```

Expected: Signals generating, no errors, regime detection working.

### Step 3: Create Week 3 Branch

```bash
git checkout -b week-3-learning-loop
```

### Step 4: Start W3-A (Closed Trade Analyzer)

See **WEEKS3-6_BLUEPRINT.md: W3-A** (page 20)

```bash
# Create the module
touch bot/llm/learning/closed_trade_analyzer.py

# Add to __init__.py
echo "from .closed_trade_analyzer import *" >> bot/llm/learning/__init__.py

# Copy the template from blueprint (lines 120-200)
# Implement:
#   - @dataclass TradeLesson
#   - @dataclass SetupPattern
#   - analyze(trade_id, start_time) → lessons
#   - Build setup_type pattern grouping
#   - Emit confidence calibration feedback

# Create tests
touch bot/tests/test_closed_trade_analyzer.py

# Tests should cover:
#   - Mock 20 closed trades
#   - Lesson extraction (thesis_correct)
#   - Setup pattern grouping
#   - Calibration detection
```

**Done when**:
- Module exists and imports cleanly
- Tests pass (`pytest bot/tests/test_closed_trade_analyzer.py -v`)
- 45 lines of test code, 20 test cases minimum

### Step 5: Proceed Through W3-B, W3-C, W3-D, etc.

Each component has the same structure:
1. Create file
2. Implement classes/functions from blueprint
3. Integrate at marked points
4. Write tests (min 20 lines)
5. Commit

---

## Key Principles

### Code Quality
✅ Type hints on ALL functions  
✅ 1-2 line docstrings (not multi-paragraph)  
✅ No silent failures (all errors logged/raised)  
✅ 80%+ test coverage per module  
✅ Backwards compatible (no breaking changes)

### Autonomy Checklist
- [x] Blueprint is comprehensive (1,600 lines)
- [x] Integration points are marked (search "Integration Points" in blueprint)
- [x] Test patterns are provided (look at test_backend_integration.py)
- [x] Success criteria defined (per week)
- [x] Dependencies documented (follow timeline in blueprint)
- [x] Permission granted ("go fully autonomously")

### Communication
- Commit frequently (per component, ~1 commit per 6-8 hours work)
- Keep commit messages clear (what + why, not just what)
- Log progress to `AUTONOMOUS_SESSION_LOG.md` (create daily)
- No user pings needed (autonomous = self-contained)

---

## Decision: Week 6 Path

**Two paths at Week 6 (see blueprint for details)**:

1. **Ollama Path** (40-50 hours):
   - Implement OllamaBackend (was stub)
   - Set up fallback chain (CLI → API → Ollama)
   - Benchmark local models vs Claude
   - Optimize routing by agent type
   - **Cost benefit**: Reduce LLM bill by ~30% (Haiku→Ollama for low-cost agents)

2. **Deepen Path** (60-80 hours):
   - Hypothesis-to-rule graduation pipeline
   - Knowledge distillation agent
   - Counterfactual analysis
   - Edge discovery system
   - Curriculum advancement
   - **Edge benefit**: Maximize trading alpha (better pattern detection, self-improvement)

**Recommendation**: Start Week 3-5, decide at Day 25 based on:
- Cost trajectory (LLM spending on track?)
- System maturity (do we need deeper learning, or cost savings?)
- Time remaining (can we do both?)

**User preference noted**: "don't really need ollama wedge, BUT WANT US TO CONTINUE AND WORK AS HARD AS POSSIBLE."
→ Suggests Deepen path is priority, but keep Ollama option open.

---

## Reference: File Locations

**Core System**:
- `bot/run.py` — Entry point
- `bot/multi_strategy_main.py` — Main loop (6,028 lines)
- `bot/trading_config.py` — All config (490+ lines)

**LLM Agents**:
- `bot/llm/agents/coordinator.py` — Multi-agent orchestration
- `bot/llm/agents/prompts.py` — All agent prompts
- `bot/llm/backend.py` — Backend abstraction
- `bot/llm/audit_logger.py` — Audit trail

**Execution**:
- `bot/execution/position_manager.py` — Position lifecycle
- `bot/execution/order_executor.py` — Order submission
- `bot/execution/risk.py` — Circuit breakers

**Data**:
- `bot/data/strategy_weights.py` — Rolling performance weights
- `bot/data/fetcher.py` — OHLCV data pipeline
- `bot/data/llm/decisions.jsonl` — Audit trail (append-only)
- `bot/data/llm/graduated_rules.json` — Learned rules

**Tests**:
- `bot/tests/test_*.py` — 41 test files, 3,500+ tests
- Look at `test_backend_integration.py` (320 lines) for patterns

---

## Commit Template

```
<type>: <subject>

<body (optional)>

[Week 3-A: Closed Trade Analyzer] or [Week 4-C: Coordinator Enhancement] etc.
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `perf`

Example:
```
feat: Add closed trade analyzer for lesson extraction

Implements TradeLesson and SetupPattern dataclasses for analyzing
completed trades and extracting statistical lessons about win rates
and confidence calibration.

Wired into Learning Agent post-close path. Reads decisions.jsonl,
outputs pattern statistics.

[Week 3-A: Closed Trade Analyzer]
```

---

## Testing Fast Path

**During development**:
```bash
# Just your module
pytest bot/tests/test_closed_trade_analyzer.py -v

# Your module + dependencies
pytest bot/tests/test_closed_trade_analyzer.py bot/tests/test_memory_enrichment.py -v

# Full suite (slow, run before final commit)
cd bot && pytest tests/ -x
```

**Before final commit**:
```bash
cd bot && pytest tests/ -x --tb=short
```

Should show: `X passed, Y skipped, 0 failed`

---

## Debugging Patterns

**Silent failures** (the enemy):
```python
# BAD
value = data.get('field', default)  # Hides errors!

# GOOD
if 'field' not in data:
    logger.error(f"Missing field in {data.keys()}")
    raise KeyError('field')
value = data['field']
```

**Integration issues**:
- Check integration points from blueprint
- Verify function signature matches (input/output types)
- Verify calls use correct arg order
- Verify return values are used correctly

**Test failures**:
- Look at actual vs expected in error message
- Use `-vv` flag for verbose output
- Add print() statements in test (pytest captures them with `-s`)

---

## Monitoring Progress

**Week 3 target**: 65-90 hours
- W3-A: 14h (closed trade analyzer)
- W3-B: 14h (memory enrichment)
- W3-C: 8h (learning agent integration)
- W3-D: 12h (deep memory query)
- W3-E: 8h (thesis tracker enhancement)
- W3-F: 6h (learning agent prompt)
- W3-G: 6h (decisions.jsonl tools)
- Polish: 8h

**Week 4 target**: 60-80 hours
- Similar breakdown (2-3 components per day)

**Week 5 target**: 60-90 hours
- Deployment infrastructure (shadow mode, canary gate, monitoring)

**Week 6 target**: 40-80 hours
- Path A (Ollama): 40-50h
- Path B (Deepen): 60-80h

**Parallel tracks**:
- Silent-fallback refactor: ~18 hours/week (can be interleaved)
- Tier 1 improvements: ~10 hours/week (low-priority, fill gaps)

---

## Quick Reference: Integration Points

**When adding new components, wire into**:

1. **Coordinator** (`bot/llm/agents/coordinator.py`):
   - Line 1537-1558: Entry decision audit logging (model)
   - Search for "Integration point" comments

2. **Config** (`bot/trading_config.py`):
   - Add any new toggles/thresholds
   - Example: `AGENT_OPPORTUNIST_ENABLED: bool = True`

3. **Tests** (`bot/tests/test_*.py`):
   - Min 20 lines per new module
   - Cover happy path + error cases

4. **CLI** (if user-facing):
   - `bot/cli.py` or new commands in `bot/run.py`

5. **Logging**:
   - Always log at INFO level on key events
   - Use structured format: `[COMPONENT] action: details`

---

## Final Checklist Before Starting

- [ ] Read SESSION_HANDOFF.md (bot health confirmed)
- [ ] Read WEEKS3-6_BLUEPRINT.md (understand scope)
- [ ] Check git branch (`git branch` should show new branch)
- [ ] Verify bot runs (`python run.py signals` completes)
- [ ] Understand Week 3 first 2 components (W3-A, W3-B)
- [ ] Know where tests go (`bot/tests/test_*.py`)
- [ ] Know commit format (see above)
- [ ] Permission confirmed (autonomous = self-contained, no pings)

✅ **All set. Begin Week 3-A.**

---

## Emergency Fallback

If stuck:
1. **Check blueprint** (search for your component name)
2. **Look at test patterns** (test_backend_integration.py)
3. **Check git log** (see how similar changes were done)
4. **Run tests** (pytest with -vv for detailed output)

If truly blocked (missing dependency, unclear spec):
- Create a note in bot/data/BLOCKER_NOTES.md
- Continue with next component (come back later)
- Don't break the build (always ensure tests pass)

---

**You have everything you need. Ship it.**
