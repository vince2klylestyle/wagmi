# WAGMI Frontend Blueprint — JUICE-Level Dashboard Build

**Date**: 2026-04-17
**Inspiration**: juiceeverything.com (automated token management, clean web dashboard, institutional polish)
**Goal**: Transform WAGMI's existing frontend into a JUICE-quality web dashboard

---

## CURRENT STATE (what already exists)

### 1. Next.js Frontend (`/web/`)
- **Status**: Builds clean, 18 pages, all compile
- **Tech**: Next.js 14.2, React 18, TypeScript, Framer Motion, Lightweight Charts, SWR
- **Pages**: index, dashboard, signals, backtest, results, performance, masterclass, learn, agent-intelligence, ai-decisions, forensics, copy-trade, llm-audit, portfolio, strategies
- **Components**: 20+ (charts, UI, layout, sidebar)
- **Design**: Dark theme (#050508 bg), green accent (#00cc88), JetBrains Mono for numbers, Inter for text
- **Brand**: Currently "CrazyOnSol" — needs rename to WAGMI
- **Start**: `cd web && npm run dev` (port 3000)

### 2. Lightweight Data API (`/bot/api_server.py`) [JUST BUILT]
- **Status**: Working, tested, serving live data
- **Tech**: FastAPI + uvicorn, reads directly from bot data files
- **No Postgres needed** — reads trades.csv, position_state.json, signal_outcomes.jsonl, etc.
- **Endpoints implemented**:
  - `GET /health` — health check
  - `GET /v1/summary` — dashboard summary (equity, WR, PnL, positions)
  - `GET /v1/trades/history?limit=N` — trade history
  - `GET /v1/trades/equity-curve` — equity curve from trades
  - `GET /v1/strategies` — strategy list
  - `GET /v1/positions` — open positions
  - `GET /v1/account` — equity/peak equity
  - `GET /v1/llm/market-view` — latest LLM memory
  - `GET /v1/llm/feed?limit=N` — LLM decisions
  - `GET /v1/agents/overview` — 9-agent system overview
  - `GET /v1/agents/team/calibration` — agent calibration
  - `GET /v1/agents/debate/history` — agent debates
  - `GET /v1/signals/funnel?hours=N` — signal pipeline funnel
  - `GET /v1/sniper/recent?limit=N` — recent sniper signals
- **Start**: `cd bot && python api_server.py` (port 8000)

### 3. Python Dashboard (`/bot/dashboard/`)
- **Status**: Fully implemented, 9.7k LOC, 40+ API endpoints
- **Note**: Runs inside the bot process (needs bot running)
- **Good for**: in-process monitoring, but NOT for the standalone web dashboard
- **Start**: Automatic when bot runs (`python run.py paper`)

---

## HOW TO RUN RIGHT NOW

```bash
# Terminal 1: API server (serves bot data)
cd bot && python api_server.py

# Terminal 2: Frontend (connects to API)
cd web && npm run dev

# Open: http://localhost:3000
```

---

## WHAT TO BUILD NEXT (priority order)

### Phase 1: Connect & Polish (4-6 hours)
1. **Wire dashboard.tsx to real data** — it currently calls `/v1/trades/history` and `/v1/trades/equity-curve` which the API now serves. Verify data flows and renders.
2. **Add /v1/positions panel** to dashboard — live open positions with unrealized PnL (the API endpoint exists).
3. **Rebrand "CrazyOnSol" → "WAGMI"** across all pages, components, meta tags.
4. **Fix any broken data flows** — some pages may expect fields the API doesn't serve yet.
5. **Add auto-refresh** — SWR already installed; add 10s polling for positions, 30s for trades.

### Phase 2: JUICE-Quality Features (6-10 hours)
1. **Real-time equity ticker** — header bar showing live equity, daily PnL, open positions count (like JUICE's wallet overview).
2. **Signal funnel visualization** — visual pipeline: signals generated → passed → traded → outcome. Use `/v1/signals/funnel`.
3. **Sniper alerts panel** — recent sniper/premium signals with tier badges, from `/v1/sniper/recent`.
4. **Position cards with live price** — for each open position: entry, current, SL, TP1/TP2, unrealized PnL bar, time held.
5. **Performance charts** — equity curve (Lightweight Charts), win rate gauge, PnL by symbol heatmap.
6. **Mobile responsive** — JUICE looks great on mobile. Our Layout.tsx already handles mobile but pages need checking.

### Phase 3: Advanced (10+ hours)
1. **WebSocket for real-time** — replace polling with WebSocket push from bot process.
2. **Trade execution from dashboard** — POST endpoints to close positions, adjust SL, etc. (needs bot integration).
3. **Strategy control panel** — enable/disable strategies, adjust risk params from web UI.
4. **Multi-wallet view** — if dual-wallet A/B is active, show both wallets side by side.
5. **Vercel deployment** — `vercel.json` already exists. Connect to Vercel for public hosting.
6. **Auth layer** — simple JWT/password to protect the dashboard.

---

## DESIGN LANGUAGE (match JUICE's polish)

Already have:
- Dark bg (#050508), card surfaces (#0d0d14)
- Green accent (#00cc88) for profit/bull
- Red (#ff4466) for loss/bear
- Monospace numbers (JetBrains Mono)
- Clean body text (Inter)
- Framer Motion page transitions
- Collapsible sidebar with icon nav

Need to add:
- **Glass morphism cards** — `backdrop-filter: blur(12px)` on overlays
- **Subtle glow effects** — brand-colored box shadows on active elements
- **Gradient accents** — linear-gradient headers for section dividers
- **Loading skeletons** — Skeleton.tsx component exists, wire it into data-loading states
- **Status indicators** — pulsing green dot for "live", amber for "stale", red for "error"

---

## KEY FILES TO EDIT

| File | What to do |
|------|-----------|
| `web/src/api.ts` | Already points to localhost:8000 ✅ |
| `web/pages/dashboard.tsx` | Wire to `/v1/summary`, `/v1/positions`, add auto-refresh |
| `web/pages/index.tsx` | Rebrand, add hero stats from `/v1/summary` |
| `web/components/Layout.tsx` | Add live equity ticker in header |
| `web/components/Sidebar.tsx` | Rebrand CrazyOnSol → WAGMI |
| `web/pages/_document.tsx` | Update meta tags, favicon, fonts |
| `web/src/theme.ts` | Possibly adjust colors (current palette is solid) |
| `bot/api_server.py` | Add new endpoints as frontend needs them |

---

## API ENDPOINT GAPS TO FILL

When pages need data the API doesn't serve yet:
1. `/v1/backtest/results` — for backtest.tsx page
2. `/v1/forensics/analysis` — for forensics.tsx page
3. `/v1/copy/status` — for copy-trade.tsx page
4. `/v1/portfolio/allocation` — for portfolio.tsx page
5. `/v1/performance/metrics` — for performance.tsx page

Each of these can read from existing bot data files. Pattern: read CSV/JSON → transform → serve JSON.

---

## SESSION CONTEXT FOR NEXT CLAUDE

- User's equity: ~$589 ($568 start + $89.54 total PnL - recent losses)
- Bot is running paper mode on Hyperliquid via CCXT
- LLM agents are DORMANT (LLM_MODE=0, no API credits)
- The bot is ensemble-only right now (no sniper auto-exec)
- User trades manually at 7-20x using sniper alerts on Telegram
- User admires JUICE's institutional look — clean, professional, not flashy
- All 3,184 tests pass
- Pending bot restart to load new trail/alert/leverage fixes

---

## QUICK WINS (do these first in next session)

1. `cd bot && python api_server.py` — start API
2. `cd web && npm run dev` — start frontend
3. Open `http://localhost:3000/dashboard` — see what renders
4. Fix any broken data flows (missing fields, wrong types)
5. Add equity ticker to Layout header
6. Rebrand to WAGMI
7. Screenshot for user to see progress
