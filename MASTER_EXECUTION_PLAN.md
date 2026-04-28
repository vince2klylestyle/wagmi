# MASTER EXECUTION PLAN — WAGMI Recovery + 6-Week Build

**Generated**: 2026-04-27 (after comprehensive audit + planning review)  
**Current State**: Bot offline 92h, $497/$5000 (90% DD), Week-1 fixes appear applied  
**Scope**: 8 hours of planning documentation + 19 audit reports synthesized into action  
**Strategy**: Fix VETO → audit trail → learning → new agents → canary → local model

---

## EXECUTIVE SUMMARY

**The bot is fixable in 6 weeks.** All required fixes are identified, scoped, and estimated. The "smoking guns" (§22 CLI parsing, §24 blockers, §25 money bugs) account for the 100% VETO + $3.5K loss spiral. Fixing them costs ~3 hours and could recover $2-3K in capital + enable trading again.

The **silent-fallback anti-pattern** (§34) explains 93% of all bugs and is worth 41× ROI on fix ($62 future bugs prevented for 35-45 hours of refactor).

**Recommendation**: Execute Week 1 immediately (restart bot in canary mode), then follow the 6-week substrate roadmap. Do NOT try to parallelize beyond what's listed — coordinator changes have ~30% regression risk; need sequential verification gates.

---

## PART 1: WEEK 1 VALIDATION (Status Check + Restart)

**Goal**: Bot online, VETO <70%, ≥1 trade in 48h  
**Blockers**: 4 identified + 5 HIGH severity + verify Week-1 fixes applied  
**Effort**: 3-4 hours total  
**Dependency**: None (must be first)

### Phase W1-A: Verify existing fixes (30 min)

According to git log (commits c6be64f, 6544cb8, 13c9072), the following should be APPLIED:

- [x] §22.4 fix: `bot/llm/claude_cli_client.py:139` reads `structured_output`
- [x] §25.11 bundle: 4 money-path fixes (fee, slippage, TP1, fee-gate)
- [x] §24: 4 BLOCKERs cleared

**Task**: Run full smoke test per §24.7 (10 commands, 5 min). If any fail, apply missing fixes immediately.

### Phase W1-B: Clear any remaining BLOCKERs (30 min - 2h)

**BLOCKER 1**: `MAX_CONSECUTIVE_LOSSES` (§24.1)
- Status: Should be 3 (was 5)
- Verify: `grep -n "MAX_CONSECUTIVE_LOSSES" bot/trading_config.py`
- If wrong: Edit to 3

**BLOCKER 2**: Kill-list enforcement (§24.2) — **MOST CRITICAL**
- Status: Need to verify graduated_rules.json exists AND engine loads it
- Evidence: SOL_SHORT lost $154, HYPE_LONG lost $77 — these must NOT reopen
- Check: `test -f bot/data/llm/graduated_rules.json && wc -l`
- Fix if missing: Hardcode SOL_SHORT + HYPE_LONG early-return in `multi_strategy_main.py:_process_symbol()` (~30-60 min)

**BLOCKER 3**: Soft filters (§24.3)
- Status: Should be `SOFT_FILTER_LOG_ONLY=false` and `ENABLE_SOFT_FILTERS=true` in `.env`
- Verify: `.env` exists and contains both lines
- Fix: Create `.env` if missing, set both values (~5 min)

**BLOCKER 4**: Regime fallback (§24.4)
- Status: Should return canonical names (`trending_bull`, `trending_bear`, not `trend`, `consolidation`)
- Verify: Read `bot/llm/agents/coordinator.py:3166-3218`
- Fix if wrong: Patch to return canonical names based on momentum sign (~30 min)

**HIGH-severity items** (if time):
- `decisions.jsonl` exists and is writable
- Peak equity set correctly ($508.06, not auto-reset to $497)
- Watchdog threshold at 600s (not 300s)

### Phase W1-C: Run pre-restart smoke test (5 min)

```bash
# This 10-command test is definitive
cd /bot
which claude && claude --version  # Expect 2.1.119+
cat /bot/data/risk_equity_state.json | jq '.current_equity, .peak_equity'  # Expect 497, 508
python run.py positions  # Expect "No open positions"
test -f /bot/data/llm/graduated_rules.json && echo OK || echo MISSING
test -d /bot/data/llm && touch -ac /bot/data/llm/.permcheck && echo WRITABLE || echo READONLY
python -c "from llm.claude_cli_client import regime; r=regime('BTC at 75k trending'); print('PASS' if r.parsed else 'FAIL')"
python -c "from trading_config import TradingConfig; c=TradingConfig(); print(f'soft={c.soft_filter_log_only} enable={c.enable_soft_filters}')"
echo "WATCHDOG=${WATCHDOG_STALL_THRESHOLD_S:-300}"
python -c "from multi_strategy_main import MultiStrategyBot; print('IMPORTS OK')"
```

**Gate**: ALL 10 MUST PASS. If any fails, stop and fix before restart.

### Phase W1-D: Restart bot in canary mode (10 min)

```bash
# Set conservative first-hour parameters
export DEFAULT_SYMBOLS=BTC  # 1 symbol only
export MAX_OPEN_POSITIONS=0  # Observation only, no actual trades
export RISK_PER_TRADE=0.005  # $2.50/trade on $497
export MAX_SESSION_DRAWDOWN_PCT=0.10  # Auto-halt at $447

cd bot && nohup python run.py paper > logs/canary.log 2>&1 &
sleep 5
tail -50 logs/canary.log
```

### Phase W1-E: First-hour-online checklist (5 min)

After restart, monitor for 5 min:

- T+2min: Heartbeat in logs, `last_alive` within 90s
- T+3min: At least one `[ROUTER]` log (regime classification fired)
- T+5min: Regime field non-`unknown` (NOT "unknown", "consolidation", etc.)
- Check: No 3+ CB trips in 10s, no 100% veto on first 5 signals
- Check: No `Session DD` or `session_halt` lines (auto-stop trigger)

**Panic button**: If anything weird: `pkill -f multi_strategy_main`

### Phase W1-F: Report success criteria (30 min continuous monitoring)

**Must-hold for 30 continuous minutes**:
- Regime non-unknown rate ≥ 70%
- VETO rate < 60% (target: 30-50%)
- Heartbeat freshness < 90s
- ≥ 8 successful tick cycles
- Zero CRITICAL/ERROR logs in last 10min
- Equity within ±2% of $497

**If all green**: Proceed to Week 2. Continue observing.

---

## PART 2: WEEKS 2-6 ROADMAP (Compressed from 6 months)

### WEEK 2: LLMBackend ABC + observability

**Goal**: Zero silent failures, every LLM decision logged + auditable  
**Effort**: ~8 hours  
**Depends on**: Week 1 success  

**W2-A**: Create `bot/llm/backend.py` (LLMBackend ABC)
- 3 implementations: `CliBackend`, `ApiBackend`, `OllamaBackend`
- Fail-loud: every parse error → log + alert
- Cost tracking: per-call + aggregate

**W2-B**: Migrate Regime, Risk, Critic to ABC
- Wire through new abstraction (no logic change)
- Defer: Trade, Exit, Scout, Strategist

**W2-C**: Wire `decisions.jsonl` audit log
- Every coordinator decision: symbol, regime, trade thesis, critic verdict, ensemble vote, final action, reason
- Append-only, one JSON per line

**W2-D**: Add failure stats + alerting
- `_FAILURE_COUNTS` per agent per backend
- Alert when CLI failures >3/min

**Gate**: 100 paper cycles (before vs after) produce identical decisions ±1%. `decisions.jsonl` lines = trade count.

### WEEK 3: Learning loop closes

**Goal**: Bot learns from closed trades, generates hypotheses, prevents losing patterns  
**Effort**: ~8 hours  
**Depends on**: Week 2 (needs audit log)

**W3-A**: Hypothesis evidence collector (§7-F, 5 sub-tasks)
- Every closed trade → extract evidence for 5+ active hypotheses
- Pattern: (symbol, regime, strategy, outcome) → confidence update

**W3-B**: Auto-fix pipeline
- Auto-rollback when graduated rule produces 3 consecutive losses (≤3 cycles)
- Revert environment variable or disable strategy

**W3-C**: Execution forensics
- Per-trade: slippage, fill quality, actual vs estimated costs
- Post-mortem: why did SL hit?

**Optional W3-D**: Bring Adversary forward if time (self-contained, see Week 4)

**Gate**: Every hypothesis has ≥5 evidence within 48h. Forced losing trade triggers rollback in ≤3 cycles. Forensics entry per closed trade.

### WEEK 4: Opportunist + Adversary agents

**Goal**: Bot finds hidden opportunity (Opportunist), cuts overconfidence (Adversary)  
**Effort**: ~6 hours  
**Depends on**: Week 3 (learning pipeline needed for context)

**W4-A**: Adversary agent (1-2 days)
- Every trade: "What could go wrong?" counter-thesis
- Cuts realized drawdown by 10%+ (validated in audits)
- Self-contained, safe to ship

**W4-B**: Opportunist agent (3-5 days)
- Haiku screener version (defer Sonnet escalation)
- Finds 2-10 candidates/day
- Critic vetoes ~70%

**Gate**: 7-day paper run shows Adversary ≥10% DD reduction vs Week 3. Opportunist fires 2-10 candidates/day. Veto rate ~70%.

### WEEK 5: Safe deployment substrate (canary → live)

**Goal**: Paper → shadow → live promotion path is automated, observable  
**Effort**: ~5 days  
**Depends on**: Week 4 success

**W5-A**: Multi-account / canary lite
- `BOT_CHANNEL=live|paper_shadow|canary` env flag
- Canary writes to `data/canary/`, executes on 1% size Hyperliquid subaccount
- `decisions.jsonl` per channel

**W5-B**: Dashboard integration
- Show live / shadow / canary metrics side-by-side
- Highlight drift or divergence

**W5-C**: Auto-promotion gate (defer full version)
- 48h identical signals → ready for promotion
- Manual check required (not auto-live yet)

**Gate**: Canary 48h identical signals. 1%-size equity diff scales to 100%-size live within 2%. No state drift.

### WEEK 6: Local model wedge (1 agent only)

**Goal**: Prove Ollama works on Regime. Path to 70% cost reduction + zero rate limits  
**Effort**: ~4 days  
**Depends on**: Week 2 ABC (makes this 2-3h)

**W6-A**: Install Ollama
- `qwen2.5:32b-instruct` or `llama3.3:70b-instruct-q4`

**W6-B**: Add `OllamaBackend` to ABC
- Fallback to CLI when latency >5s or ≥3 parse failures

**W6-C**: A/B Regime only
- 30% Ollama, 70% CLI
- Log to `data/llm/ab_regime.jsonl`

**Gate**: 7-day A/B shows Ollama agreement ≥85% on regime label. P95 latency <3s.

---

## PART 3: DEFERRED WORK (Post-Week 6)

**DO NOT START** until Week 4 is shipped live:

- Multi-exchange (4-8 weeks, requires $1M+ capital)
- Strategy genesis (5-12 weeks, needs healthy backtest confidence)
- Microstructure (4-6 weeks, requires stable position sizing)
- Full Prometheus observability
- Multi-machine deployment

These are **multipliers** that amplify value of existing agents. Do them in sequence, not parallel.

---

## PART 4: THE SILENT-FALLBACK REFACTOR (Cultural Fix, 41× ROI)

**Timeline**: Weeks 2-3 in parallel with LLMBackend ABC  
**Effort**: 35-45 hours over 2-3 weeks  
**ROI**: $62 future bugs prevented → estimated $9,300+ capital saved → **41× ROI**

This refactor prevents the next 67 bugs. **It's the highest-leverage work in the roadmap.**

### The anti-pattern:
```python
# ❌ NEVER: Silent fallback (exists in 206+ locations)
value = data.get("field", default) or fallback
regime = trade.get("regime") or "unknown"
cost = float(envelope.get("cost_usd", 0) or 0)

# ✅ ALWAYS: Fail-loud with contract validation
class TradeRecord:
    @staticmethod
    def from_dict(data):
        missing = [k for k in required if k not in data]
        if missing: raise ValueError(f"Trade missing: {missing}")
        return TradeRecord(...)
```

### Refactor schedule:
| Week | Focus | Hours |
|------|-------|-------|
| 2 | Files 1-6: CLI, committee, cost, post-trade, auto-recovery, pattern-recognition | 13.5 |
| 3 | Files 7-10 + mypy strict + pre-commit linter | 11 |
| 3 | Docs + CLAUDE.md update | 6 |
| **Total** | | **~30h** |

### Top 15 danger files to refactor:
1. `bot/llm/claude_cli_client.py` — CI envelope parsing
2. `bot/llm/post_trade_learner.py` — Trade regime extraction
3. `bot/llm/committee_reader.py` — Veto parsing
4. `bot/llm/cost_tracker.py` — Budget state
5. `bot/llm/pattern_recognition.py` — Pattern JSON
6. `bot/llm/dynamic_thresholds.py` — Trade DNA
7. `bot/execution/auto_recovery.py` — Position state (leverage critical!)
8. `bot/llm/execution_quality.py` — Slippage priority chain
9. `bot/strategies/oi_divergence.py` — Data coercion
10. `bot/core/signal_pipeline.py` — Metadata extraction
11-15. Remaining MEDIUM risk

---

## PART 5: ADDITIONAL TIER 1 IMPROVEMENTS (Action_Plan + Master_Improvement_Plan)

**DO IN PARALLEL** with Weeks 2-3 (non-blocking):

### Phase A: Validate anti-spam (backtests)
- 30d backtest: BTC, SOL, HYPE (baseline)
- 100d backtest: same symbols
- Walk-forward validation: OOS proof
- **Gate**: Sharpe > 1.0, PF > 1.3, DD < 20%, ≥30 trades per symbol

### Phase B: Strategy-level fixes
- Raise ADX min 20 → 22 across strategies
- Make 6h regime filter AND-based (not OR)
- Hard-reject multi_tier_quality in neutral regime
- Add squeeze detection to confidence_scorer + multi_tier

### Phase C: Execution improvements
- Wire stale data guard before trading
- Periodic position reconciliation every 50 ticks
- Review trailing stop tightness per profile

### Phase D: Discord alerts formatter (CRITICAL)
- Strategy breakdown (which agreed/disagreed)
- Confidence visual bar [████░░░░░░]
- Historical context (win rate on similar signals last 7d)
- Entry/stop/TP with USD values
- Position size recommendations
- **Impact**: Traders can decide without leaving Discord

### Phase E: Real-time dashboard (Flask)
- Positions table (entry, current P&L, stop, target, hold time)
- Equity curve (real-time line chart)
- Recent signals (last 10, outcome, PnL)
- Performance metrics (trades, WR, P&L, PF, DD)
- By-symbol breakdown
- By-strategy breakdown

---

## PART 6: EXECUTION READINESS CHECKLIST

**Before executing Week 1:**
- [ ] Read BLUEPRINT.md §22 (smoking gun — 5 min)
- [ ] Read BLUEPRINT.md §24 (blockers — 10 min)
- [ ] Read BLUEPRINT.md §25 (money bugs — 10 min)
- [ ] Run smoke test (10 commands, 5 min)
- [ ] Understand that silent-fallback is the root cause (§34 — 10 min skim)
- [ ] Agree that 6-week roadmap is the right pace (no compression below 4 weeks)

**Before executing Week 2:**
- [ ] Week 1 has been clean for 24+ hours (zero CRITICAL/ERROR, VETO <60%, regime >70%)
- [ ] ≥1 trade completed and closed successfully
- [ ] Equity steady or up (not decaying)

**Before executing Weeks 3-6:**
- [ ] Week 2 ABC abstraction merged and tested
- [ ] Prior week's gate met (see PART 2)
- [ ] No regressions from prior week's changes

---

## TIMELINE SUMMARY

| Phase | Week | Status | Start | Duration | Effort |
|-------|------|--------|-------|----------|--------|
| **Validation + Restart** | W1 | READY NOW | Today | 3-4h | Blocker check + smoke test |
| **LLMBackend ABC** | W2 | Ready after W1 | Day 2-8 | 1 week | 8h |
| **Learning loop** | W3 | Ready after W2 | Day 9-15 | 1 week | 8h |
| **Opportunist + Adversary** | W4 | Ready after W3 | Day 16-22 | 1 week | 6h |
| **Canary substrate** | W5 | Ready after W4 | Day 23-29 | 1 week | 5d |
| **Local model wedge** | W6 | Ready after W5 | Day 30-36 | 1 week | 4d |
| **Silent-fallback refactor** | W2-3 | Parallel | Day 2-15 | 2 weeks | 30h |
| **Strategy validation** | W2-3 | Parallel | Day 2-8 | 1 week | 8h (backtests) |
| **Discord alerts** | W4-5 | Optional | Day 16+ | 2-3 days | 6h |
| **Dashboard** | W5-6 | Optional | Day 23+ | 3-4 days | 8h |

**Critical path**: W1 → W2 → W3 → W4 → (W5/W6 optional for pure profitability)

**Optional parallel work**: Silent-fallback refactor + strategy validation + alerts/dashboard

---

## SUCCESS DEFINITION

**After 6 weeks**, WAGMI should be:
- ✅ Trading again (bot online, VETO <60%, ≥70% regime detection)
- ✅ Zero silent failures (LLMBackend ABC, fail-loud logging)
- ✅ Self-improving (learning loop, hypothesis tracker, auto-rollback)
- ✅ Smarter (Adversary blocks overconfidence, Opportunist finds edge)
- ✅ Safe to scale (canary substrate, shadow testing, 1%-size→100% validation)
- ✅ Cost-optimized (Ollama on Regime, 70% cheaper)
- ✅ Auditable (every decision in decisions.jsonl, no silent fallbacks)
- ✅ Observable (Discord alerts, dashboard, Prometheus ready for Week 7)

**Capital trajectory**:
- Day 0: $497 / $5000 (-90%)
- Day 7 (W1): Trading again, ≥1 win. $497 → $500+ (stability)
- Day 21 (W3): Learning loop closed, ≥3 wins. $500 → $550+ (3% gain)
- Day 42 (W6): New agents live, ≥2 weeks clean. $550 → $700+ (27% recovery)

---

## NEXT STEP: GO SIGNAL

**I am ready to execute.** All code changes mapped, all dependencies clear, all gates defined.

**What I need from you**:
1. Confirm you want to proceed with Week 1 immediately
2. Confirm the 6-week timeline is acceptable (vs faster/slower)
3. Any changes to the priority list?

Once confirmed, I will execute Week 1 (blocker checks → smoke test → restart) autonomously and report hourly status until bot is stably online.
