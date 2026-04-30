# Session Summary — 2026-04-29

This document summarizes everything shipped in branch
`claude/audit-and-planning-3ocfV` during this session, what's working
end-to-end now vs. what's still pending, and the recommended next moves.

---

## Audit & Planning Documents

Persistent reference documents written this session, all under
`audits/2026-04-29/`:

| File | Purpose |
|---|---|
| `01_counterfactual_summary.md` | §7.1 — TP1 underweighting confirmed: +$477 across 134 closed-trade scenarios; veto correctness 0/218 → vetoes work |
| `02_rules_enforcement_audit.md` | §7.7 — P0 finding: bot has TWO graduated_rules systems with incompatible schemas, none of the 49 perpetual-loop rules are enforced at runtime |
| `03_web_page_audit.md` | Per-page Is/Should/Broken/Verdict for all 18 web pages; 18 → 12 IA proposal (later superseded) |
| `04_infrastructure_reshape_plan.md` | Three backends → one (`bot/api_server.py`); kill `api/app/` and `bot/dashboard/` |
| `05_ui_reshape_hyperliquid_style.md` | HL-styled scaffolding plan + §7 "beyond a clone" — eight WAGMI superpowers woven into HL chrome |
| `06_live_copilot_design.md` | /live triple-panel + Q&A + replay design spec |
| `07_session_summary.md` | This document |

Plus the master plan written earlier: `OVERNIGHT_BLUEPRINT_2026_04_29.md`.

---

## What's Built and Wired End-to-End

### Frontend (`web/`)

**Theme & Layout**
- `theme.ts` stripped of AI-style decoration (8 of 11 gradients flattened, glow shadows neutralized, springs overdamped, glass variants flattened to single panel style)
- HL-style horizontal top nav: Trade · Portfolio · Vaults · Leaderboard · Co-Pilot · Learn (`TopNav.tsx`)
- Contextual secondary nav (`SecondaryNav.tsx`) appears below top nav with sub-tabs based on URL: Portfolio (Overview/History/Forensics/Counterfactuals/Performance), Co-Pilot (Live/Decisions/Agents/Strategies/Backtest/Sniper-Copy), Learn (Getting Started/Masterclass/Thesis)
- BotStatusPill (live/stale/offline indicator) clickable → `/status`
- Layout: max-width 1440, slim footer, single global font stack

**New pages**
- `/live` — flagship Co-Pilot triple panel + Q&A
- `/status` — operator's morning-glance with synthesis verdicts per symbol
- `/trade` — HL-style 3-column chart + order rail + bot opinion slot
- `/vaults` — placeholder linking to HL
- `/leaderboard` — placeholder linking to HL

**New components**
- `components/live/MechanicalColumn.tsx` — ensemble/gates/edge/cohort/no-LLM verdict
- `components/live/AgenticColumn.tsx` — agent ladder + per-agent reasoning + AI-only verdict
- `components/live/SynthesisColumn.tsx` — disagreement banner, sized conviction, sizing helper, exit guidance, suggested questions
- `components/live/AskAgentsPanel.tsx` — Q&A chat with localStorage history per symbol
- `components/live/ScoreboardRow.tsx` — compact 4-cell row for scoreboard mode
- `components/live/ColumnShell.tsx` — shared Section/Stat/Skeleton/ErrorState primitives
- `components/trade/EdgeBadge.tsx`, `useEdgeStats.ts`, `CohortStrip.tsx` — knowledge layer for /trade
- `components/Tooltip.tsx` — hover-to-learn with built-in glossary
- `components/BotStatusPill.tsx` — top-nav health indicator
- `components/SecondaryNav.tsx` — contextual sub-nav
- `components/learn/index.tsx` — LearnSection/Accordion/InfoBox/Term primitives for incremental migration

### Backend (`bot/api_server.py`)

**New endpoints**
- `POST /v1/agents/ask` — interactive Q&A with the LLM agents
  - Body: `{agent: "trade"|"risk"|"critic"|"regime"|"all", question, context}`
  - Cost-capped at $0.05/call, Sonnet default
  - Rate-limited per IP: 5/min, 20/hour
  - Auto-enriches context with current regime + position from local files
- `GET /v1/decisions/at?ts=<iso>&symbol=<sym>` — replay-mode helper, returns most recent decision per symbol at-or-before timestamp
- `GET /v1/synthesis/{symbol}?ts=<iso>` — server-side combine of mechanical + agentic with disagreement penalty
- `GET /v1/llm/feed?include_agents=true` — joins agent_outputs.jsonl by pipeline_id

### Brand
- Renamed all cosmetic NunuIRL/Nunu/CrazyOnSol references → WAGMI across bot, api, infra, and web
- `bot/bot.py`'s `class NunuIRL` → `class WagmiClient` (only one caller, same file)

---

## What Works Right Now

When you boot `cd bot && python api_server.py` + `cd web && npm run dev`:

1. **`/status`** loads as the operator's morning view — equity, P&L today, open positions, alerts, synthesis verdict per symbol
2. **`/live`** is the headline experience:
   - Symbol pills (BTC/ETH/SOL/HYPE/All)
   - Live/Replay mode toggle
   - **Mechanical column** showing ensemble vote + gates + edge map + TOD cohort
   - **Agentic column** showing agent ladder with reasoning
   - **Synthesis column** with disagreement banner, sized conviction, sizing helper, exit guidance
   - **Ask-the-Agents panel** for interactive Q&A (rate-limited)
   - **All-symbols scoreboard** with compact 4-row view, color-coded by alignment
   - **Replay mode** with date/time picker rehydrating decision-time state
   - Mobile responsive (stacks on < 1024px), `?symbol=X` deep-linkable
3. **`/trade`** has 3-column HL-style layout with the WAGMI knowledge overlay (per-symbol edge stats, time-of-day cohort strip, hover-to-learn tooltips)
4. **Top nav + secondary nav** route between everything; bot status pill clickable to `/status`
5. **All existing pages** (forensics, results, performance, ai-decisions, etc.) still render — just rebranded and grouped under the secondary nav

---

## What's Pending

### High value, fast to ship
- **Wire treatment_wr A/B closure** in `bot/feedback/loop.py` — the §4.3 fix from the OVERNIGHT_BLUEPRINT, makes the perpetual improvement loop's 49 rules actually validated
- **Build `feedback/rule_compiler.py`** — translates `feedback/graduated_rules.json` to runtime `data/llm/graduated_rules.json` schema; the §7.7 P0 fix
- **Add startup self-check** that logs `[RULES] Loaded N runtime rules` and warns when count is zero with file present

### Medium scope
- **`/live` historical position rehydration** — replay mode currently says "positions not yet rehydrated"; needs persisted positions log
- **Loading skeletons + error states** on SynthesisColumn (only Mechanical + Agentic have them currently)
- **MDX migration of `learn.tsx`** — primitives are scaffolded in `components/learn/`; needs the 4,086-line content moved into `.mdx` files. ~5 hours of mostly mechanical work

### Larger, deferred
- **Auth layer** so `/v1/agents/ask` rate limits become per-user instead of per-IP
- **Server-Sent Events** for real-time updates (`/v1/signals/stream`, `/v1/decisions/stream`)
- **Delete legacy backends** (`api/app/`, `bot/dashboard/server.py`) per §04 plan

---

## Branch Commit Log (this session, in order)

```
77a45c6  brand: rename NunuIRL/Nunu/CrazyOnSol → WAGMI
fb6ebcf  api+ui: /v1/llm/feed?include_agents=true joins per-agent breakdown
3edad26  ui: BotStatusPill is now a Link to /status
dd51370  ui: /live polish — responsive grid + ?symbol= deep-link
f175ea4  ui: /status — operator's morning-glance page
6cb94fb  ui: contextual secondary nav (Portfolio / Co-Pilot / Learn sub-tabs)
e67d49a  ui: hardening — bot status pill + loading/error states on /live
8bcc97f  ui+api: replay mode wired end-to-end
4eb70f9  ui+api: scoreboard mode + rate-limited /v1/agents/ask
4ef2d4a  api: POST /v1/agents/ask — backend for /live Ask-the-Agents panel
d0789ce  ui: rename top-nav 'Bot' tab to 'Co-Pilot' pointing at /live
1dd3964  ui: /live co-pilot — full triple-panel + Q&A shell
c5f5936  audits: /live co-pilot design spec
d66a3fc  ui: /trade — knowledge layer (Phase 3b)
726870c  ui: /trade page (Phase 3a) — HL-style 3-column with WAGMI overlays
e0ef640  audits: add §7 'beyond a clone' addendum
b5c8ba1  ui: HL-style top-nav (Phase 2)
fabb7a5  ui: theme.ts — strip AI-style decoration (Phase 1)
9efbe3a  docs: OVERNIGHT_BLUEPRINT_2026_04_29 (audit + week-of-work plan)
97b2797  audits: §7.1 counterfactual + §7.7 rule enforcement audit
5115575  api+ui: /v1/synthesis/{symbol} backend + status page consumption
bf3ff98  ui: scaffold components/learn/ shared primitives
```

---

## Remaining Work for Next Session

1. **The bot itself.** The mechanical bot is offline 140+ hours. Per the OVERNIGHT_BLUEPRINT §4 critical path, the next session should focus on the trading loop — verify Finding 11 is filtering, fix the rule compiler so 49 rules actually enforce, wire treatment_wr collection, then restart paper.
2. **`/live` real data validation.** With the bot running again, the Q&A panel + agent ladder will fill with real reasoning. Some assumptions in MechanicalColumn/AgenticColumn about field shapes may need adjustment based on actual data.
3. **Counterfactual page promotion.** /counterfactuals is currently a 429-line page; the §7.1 finding (+$477 TP1 underweighting) deserves a hero stat at the top. A 30-minute upgrade.
4. **Premium gating.** When ready to monetize, gate the agentic column + Q&A behind auth. Free tier sees mechanical + synthesis + 1 question/hour.
5. **MDX migration of learn.tsx.** Now that primitives are scaffolded, an evening of work.

The branch is shippable — every commit leaves the app running. Pull `claude/audit-and-planning-3ocfV` and review on phone or desktop.
