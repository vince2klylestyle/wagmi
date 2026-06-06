# Autonomous Claude Coordination Protocol

**Purpose:** Both Claudes (desktop + laptop) operate autonomously on WAGMI without Nunu as middleman. Git is the message queue. 45-minute wakeup cycle keeps work flowing without spam.

---

## Cycle (do every wakeup)

1. `git fetch origin historical-import-2026-05-30`
2. Read `coordination/handshake.md` — last 50 lines (`tail -50`). Look for entries since your last work tagged with your name or `[QUESTION-FOR-<YOU>]`.
3. Check the open queue (see below). Pick highest-priority incomplete item not currently in flight by the other Claude.
4. Do the work — code change, audit, investigation, ship.
5. Verify syntax / sanity-check.
6. Commit + push to `historical-import-2026-05-30`.
7. Add ONE handshake entry (5-10 lines max) with tag (see below) and current status.
8. Schedule next wakeup in 45 minutes via `ScheduleWakeup`.
9. End turn.

---

## Handshake Tags

Use ONE per entry. Required.

- **[READY-FOR-REVIEW]** — work shipped, the other Claude should look + give feedback or merge
- **[SHIPPED]** — work shipped, no review needed, just FYI
- **[WORKING-ON-X]** — in progress status update (long task, no commit yet)
- **[BLOCKED]** — hit a blocker, need other Claude's input to proceed
- **[QUESTION-FOR-DESKTOP]** or **[QUESTION-FOR-LAPTOP]** — explicit question requiring the other Claude's response
- **[BUG-FOUND]** — surfaced a new bug, may or may not have fixed it, log for awareness
- **[INVESTIGATION]** — read-only audit work, no code change yet

---

## Escalate to Nunu ONLY if

- Both Claudes blocked on the same issue for >2 hours
- Need a strategic decision between approaches A vs B (philosophy / direction)
- Need credentials, API keys, config changes (never write these — ask)
- Equity / position state needs human review
- Found a critical bug requiring live bot stop

Do NOT escalate for:
- Routine progress (just push handshake entry)
- "What should I work on next" — pick from queue
- Minor disagreements (resolve via handshake discussion)
- Bot heartbeats / non-material events

---

## Current Queue (refresh from handshake each cycle)

Last updated: 2026-06-06 ~05:35 UTC. Verify against latest handshake before starting.

**OPEN:**

- **P3b** — graduated_rules.py:313 outcome callbacks: `times_correct` stays 0 despite `times_applied 16-347`. Initial diagnosis was regime name mismatch but canonicalize_regime exists at line 52. Real cause may be veto-rules-skip-at-line-311 or stale pre-restart `times_applied` accumulation. Owner: laptop (investigating per handshake).
- **P4** — equity persistence: `risk_equity_state.json` frozen at $5000 since 2026-05-30. Real equity per ledger ~$6,242. Fix `update_equity → save_equity_state` path in `bot/execution/risk.py`. Owner: laptop.
- **Alpha ops wiring** — surface OI Divergence + Funding Momentum + Liquidation magnetic zones into agent prompts (data exists, agents don't see). Owner: laptop.
- **Scorecard hardcoded edge_trends** — `bot/manual/trade_scorecard.py:34-41` has "HYPE_SELL weakening = 0pts" / "BTC_SELL weakening = 0pts" hardcoded. Causes sniper rejections at 28-30/100. Owner: open.
- **Ensemble.py:69 hardcoded confidence floor** — `confidence_floor=69.0` magic number fallback when dynamic engine fails. Strip to live data. Owner: open.
- **Probability Engine MIN_PROB_TP1=0.45** and `MIN_EV_PER_DOLLAR=0.15` in `bot/strategies/probability_engine.py:76` — make regime-conditional. Owner: open.
- **Code-quality audit** — find any other missing post-trade callback patterns (like the `process_agent_lesson` integration). Owner: laptop.

**RECENTLY SHIPPED (don't redo):**

- ✅ P1 (Critic veto) — laptop ed2f957
- ✅ P2 (Kelly recompute) — laptop 10a2175
- ✅ P3a (strategy weights frozen guard) — desktop d910443
- ✅ Memory write root cause — desktop 5e1489d + laptop 5695477
- ✅ Probability Engine prompt wiring — desktop 7adfc46
- ✅ Overdrive strip (13 sources) — desktop c09f58e
- ✅ HYPE permanent veto strip — desktop 5db5024
- ✅ Sync to single-bot — laptop ee67790

---

## Working Rules

- **Never push to `main`** — only `historical-import-2026-05-30`
- **Never add `ANTHROPIC_API_KEY`** — `USE_CLI_LLM=true` is mandatory
- **Don't restart bot** unless you're certain (desktop has the live bot; coordinate via handshake before restarting)
- **Don't run a second bot** — single source of truth
- **Don't write to gitignored `bot/data/*`** intentionally — it's gitignored for a reason; if a fix needs data state, write the fix to write live, don't commit data
- **Branch protocol:** desktop runs from `desktop-overdrive-2026-05-30`, laptop pushes to `historical-import-2026-05-30`. Desktop merges into live + restarts bot when material code changes accumulate.

---

## Example Entry Templates

```
## 2026-06-06 06:15 UTC — laptop-claude [SHIPPED]
P4 equity persistence sync fixed in commit abc1234.
Root cause: update_equity wrote in-memory but never called save_equity_state
on close. Added the call at risk.py:218. Risk_equity_state.json should
sync to ledger running_equity on next trade close.
Next wakeup: 06:55 UTC.
```

```
## 2026-06-06 06:15 UTC — desktop-claude [BUG-FOUND]
Found scorecard hardcoded edge_trends at trade_scorecard.py:34-41.
Stripped + pushed (def567).
Bot did NOT restart yet — waiting for laptop's P4 + alpha ops to batch.
[QUESTION-FOR-LAPTOP] When ETA on next batch?
Next wakeup: 06:55 UTC.
```

```
## 2026-06-06 06:15 UTC — desktop-claude [WORKING-ON-X]
Investigating laptop's P4 fix — running checks on equity state.
No commit yet. Will push by next cycle.
Next wakeup: 06:55 UTC.
```

---

## When in Doubt

Read latest handshake. If still unclear, push `[QUESTION-FOR-OTHER]` and end turn — the other Claude will see it next cycle.

The system only works if both Claudes follow the cycle. Skipping the handshake entry breaks the loop. Always close the loop.

-- Nunu via desktop-claude, 2026-06-06
