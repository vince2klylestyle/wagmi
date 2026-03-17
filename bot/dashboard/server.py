"""
Lightweight web dashboard for the NunuIRL trading bot.

Uses Python's built-in http.server (zero external dependencies).
Serves a single-page HTML dashboard with auto-refreshing data via
fetch() calls to JSON API endpoints backed by the SQLite data layer.

Features:
  v4.0 — Professional Trading Intelligence Terminal
  - 6-tab layout: Overview | Charts & Zones | Signals | Trades | Analytics | System
  - TradingView Lightweight Charts with Monte Carlo zone overlays
  - Educational tooltips on every concept (click ? icons)
  - Live positions with price range bars (10s refresh)
  - Market awareness heatmap (regime, bias, danger zones)
  - Signal pipeline funnel visualization
  - Rejected signals / "What If" section
  - Copy Trade Intelligence (LLM insights when active)
  - Equity curve, daily PnL bars, strategy breakdown
  - Circuit breaker status, go-live gates
  - Health monitoring

Usage:
    # As a background thread inside the bot:
    from dashboard import get_dashboard_server
    srv = get_dashboard_server()
    srv.start(bot_instance=bot)

    # Standalone:
    cd bot && python -m dashboard
"""

import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict, List, Optional
from pathlib import Path
from urllib.parse import urlparse, parse_qs

_BOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BOT_DIR not in sys.path:
    sys.path.insert(0, _BOT_DIR)

logger = logging.getLogger("bot.dashboard")
_START_TIME = time.time()


# ═══════════════════════════════════════════════════════════════════════════
# HTML Dashboard (inline single-page app) — v4.0
# ═══════════════════════════════════════════════════════════════════════════

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<title>NunuIRL Trading Intelligence</title>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js"></script>
<style>
:root {
  --bg: #060611;
  --bg2: #0a0a1a;
  --card: #0f0f1e;
  --card-hover: #13132a;
  --border: #1a1a35;
  --border-bright: #2a2a50;
  --text: #e0e0f0;
  --text-dim: #9090b0;
  --muted: #5e5e80;
  --green: #00e6a0;
  --green-dim: rgba(0,230,160,0.12);
  --red: #ff4466;
  --red-dim: rgba(255,68,102,0.12);
  --blue: #4488ff;
  --blue-dim: rgba(68,136,255,0.12);
  --yellow: #ffc444;
  --yellow-dim: rgba(255,196,68,0.12);
  --purple: #a366ff;
  --purple-dim: rgba(163,102,255,0.12);
  --cyan: #22d3ee;
  --cyan-dim: rgba(34,211,238,0.12);
  --orange: #ff9100;
  --radius: 10px;
  --radius-sm: 6px;
  --shadow-sm: 0 2px 8px rgba(0,0,0,0.3);
  --shadow-md: 0 4px 20px rgba(0,0,0,0.4);
  --shadow-glow-green: 0 0 20px rgba(0,230,160,0.08);
  --shadow-glow-red: 0 0 20px rgba(255,68,102,0.08);
  --transition: 0.2s ease;
}

*, *::before, *::after { margin:0; padding:0; box-sizing:border-box; }

body {
  font-family: 'SF Mono', 'Cascadia Code', 'Fira Code', 'JetBrains Mono', Consolas, monospace;
  background: var(--bg);
  color: var(--text);
  font-size: 13px;
  min-height: 100vh;
  line-height: 1.5;
  overflow-x: hidden;
}

a { color: var(--blue); text-decoration: none; }
a:hover { text-decoration: underline; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-bright); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--muted); }

/* ── Layout ── */
.app { display: flex; flex-direction: column; min-height: 100vh; }

.top-bar {
  position: sticky; top: 0; z-index: 100;
  background: rgba(6,6,17,0.92);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
  padding: 0 24px;
  display: flex; justify-content: space-between; align-items: center;
  height: 52px;
}

.top-bar .brand {
  font-size: 16px; font-weight: 800; letter-spacing: -0.5px;
  background: linear-gradient(135deg, var(--cyan), var(--blue), var(--purple));
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}

.top-bar .brand span { font-weight: 400; opacity: 0.7; }

.top-bar .status-strip {
  display: flex; gap: 20px; align-items: center; font-size: 11px; color: var(--muted);
}

.top-bar .equity-ticker {
  font-size: 15px; font-weight: 700; letter-spacing: -0.3px;
  padding: 4px 14px; border-radius: 6px;
  background: var(--card); border: 1px solid var(--border);
}

/* ── Status Dots ── */
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 5px; vertical-align: middle; }
.dot-green { background: var(--green); box-shadow: 0 0 8px var(--green); }
.dot-yellow { background: var(--yellow); box-shadow: 0 0 8px var(--yellow); }
.dot-red { background: var(--red); box-shadow: 0 0 8px var(--red); }

/* ── Tab Navigation ── */
.tab-nav {
  display: flex; gap: 0;
  background: var(--bg2);
  border-bottom: 1px solid var(--border);
  padding: 0 24px;
  overflow-x: auto;
}

.tab-btn {
  padding: 12px 22px;
  font-size: 12px; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase;
  color: var(--muted); cursor: pointer;
  border: none; background: none;
  border-bottom: 2px solid transparent;
  transition: color var(--transition), border-color var(--transition);
  font-family: inherit;
  white-space: nowrap;
}

.tab-btn:hover { color: var(--text-dim); }
.tab-btn.active {
  color: var(--cyan);
  border-bottom-color: var(--cyan);
}

.tab-btn .tab-icon { margin-right: 6px; font-size: 14px; }

.tab-content { display: none; padding: 20px 24px; animation: fadeIn 0.25s ease; }
.tab-content.active { display: block; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }

/* ── Cards ── */
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 18px 20px;
  position: relative;
  transition: border-color var(--transition), box-shadow var(--transition);
}

.card:hover { border-color: var(--border-bright); }

.card h3 {
  font-size: 10px; text-transform: uppercase; letter-spacing: 1.2px;
  color: var(--muted); margin-bottom: 12px; font-weight: 700;
  display: flex; align-items: center; gap: 8px;
}

.card-hero {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  box-shadow: var(--shadow-glow-green);
}

.card-hero h3 {
  font-size: 12px; text-transform: uppercase; letter-spacing: 0.8px;
  color: var(--cyan); margin-bottom: 14px; font-weight: 700;
  display: flex; align-items: center; gap: 8px;
}

/* ── Grids ── */
.grid-5 { display: grid; grid-template-columns: repeat(5,1fr); gap: 12px; margin-bottom: 20px; }
.grid-4 { display: grid; grid-template-columns: repeat(4,1fr); gap: 14px; margin-bottom: 20px; }
.grid-3 { display: grid; grid-template-columns: repeat(3,1fr); gap: 16px; margin-bottom: 20px; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }
.full-width { margin-bottom: 20px; }

/* ── Metrics ── */
.metric { font-size: 28px; font-weight: 800; letter-spacing: -0.5px; line-height: 1.1; }
.metric-sub { font-size: 11px; color: var(--muted); margin-top: 5px; }
.green { color: var(--green); } .red { color: var(--red); } .blue { color: var(--blue); }
.yellow { color: var(--yellow); } .purple { color: var(--purple); } .cyan { color: var(--cyan); }

/* ── Progress Bars ── */
.bar-track { width: 100%; height: 6px; background: var(--border); border-radius: 3px; overflow: hidden; margin-top: 10px; }
.bar-fill { height: 100%; border-radius: 3px; transition: width 0.6s ease; }

/* ── Tables ── */
table { width: 100%; border-collapse: collapse; }
th { text-align: left; padding: 10px 12px; font-size: 10px; text-transform: uppercase; letter-spacing: 0.8px; color: var(--muted); border-bottom: 1px solid var(--border); font-weight: 700; white-space: nowrap; }
td { padding: 9px 12px; border-bottom: 1px solid rgba(26,26,53,0.5); font-size: 12px; white-space: nowrap; }
tr:hover td { background: rgba(255,255,255,0.015); }
.scroll-y { max-height: 420px; overflow-y: auto; }

/* ── Pills / Badges ── */
.pill { display: inline-block; padding: 3px 10px; border-radius: 5px; font-size: 10px; font-weight: 700; letter-spacing: 0.3px; }
.pill-long { background: var(--green-dim); color: var(--green); }
.pill-short { background: var(--red-dim); color: var(--red); }
.pill-win { background: var(--green-dim); color: var(--green); }
.pill-loss { background: var(--red-dim); color: var(--red); }
.pill-action { background: var(--blue-dim); color: var(--blue); }
.pill-neutral { background: rgba(94,94,128,0.15); color: var(--muted); }

.gate-pill { display: inline-block; padding: 3px 10px; border-radius: 5px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.3px; }
.gate-hard { background: var(--red-dim); color: var(--red); border: 1px solid rgba(255,68,102,0.2); }
.gate-soft { background: var(--yellow-dim); color: var(--yellow); border: 1px solid rgba(255,196,68,0.2); }
.gate-info { background: var(--blue-dim); color: var(--blue); border: 1px solid rgba(68,136,255,0.2); }

/* ── Heatmap ── */
.heatmap-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
.heatmap-cell {
  background: var(--bg2); border: 1px solid var(--border); border-left: 4px solid var(--muted);
  border-radius: var(--radius-sm); padding: 14px;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
  cursor: pointer;
}
.heatmap-cell:hover { transform: translateY(-2px); box-shadow: var(--shadow-md); }
.heatmap-cell .sym-name { font-size: 15px; font-weight: 800; margin-bottom: 6px; }
.regime-pill { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.3px; }
.opportunity-glow { box-shadow: 0 0 16px rgba(0,230,160,0.12); border-color: rgba(0,230,160,0.25); }
.danger-glow { box-shadow: 0 0 16px rgba(255,68,102,0.12); border-color: rgba(255,68,102,0.25); }

/* ── Educational Tooltip System ── */
.info-btn {
  display: inline-flex; align-items: center; justify-content: center;
  width: 16px; height: 16px; border-radius: 50%;
  background: var(--border); color: var(--muted);
  font-size: 9px; font-weight: 800; cursor: pointer;
  transition: all var(--transition);
  border: none; font-family: inherit;
  line-height: 1;
}
.info-btn:hover { background: var(--blue-dim); color: var(--blue); transform: scale(1.1); }

.edu-modal-overlay {
  display: none; position: fixed; inset: 0; z-index: 1000;
  background: rgba(0,0,0,0.6); backdrop-filter: blur(4px);
  justify-content: center; align-items: center;
}
.edu-modal-overlay.visible { display: flex; animation: fadeIn 0.2s ease; }

.edu-modal {
  background: var(--card); border: 1px solid var(--border-bright);
  border-radius: 14px; padding: 28px 32px; max-width: 520px; width: 90%;
  max-height: 80vh; overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0,0,0,0.5);
}

.edu-modal .edu-icon { font-size: 32px; margin-bottom: 12px; }
.edu-modal .edu-title { font-size: 18px; font-weight: 800; margin-bottom: 8px; color: var(--text); }
.edu-modal .edu-short { font-size: 14px; color: var(--cyan); margin-bottom: 16px; font-weight: 600; }
.edu-modal .edu-detail { font-size: 13px; color: var(--text-dim); line-height: 1.7; }
.edu-modal .edu-detail p { margin-bottom: 12px; }
.edu-modal .edu-detail strong { color: var(--text); }
.edu-modal .edu-close {
  position: absolute; top: 16px; right: 16px;
  background: none; border: none; color: var(--muted); font-size: 18px; cursor: pointer;
  font-family: inherit;
}
.edu-modal .edu-close:hover { color: var(--text); }

/* ── Chart Container ── */
.chart-container { position: relative; width: 100%; border-radius: var(--radius-sm); overflow: hidden; }
.chart-container.large { height: 420px; }
.chart-container.medium { height: 280px; }
.chart-container.small { height: 200px; }
.chart-wrap { position: relative; height: 250px; }
.chart-wrap canvas { width: 100% !important; height: 100% !important; }

/* ── Symbol Selector ── */
.symbol-tabs {
  display: flex; gap: 6px; margin-bottom: 14px; flex-wrap: wrap;
}
.symbol-tab {
  padding: 6px 14px; border-radius: 6px; font-size: 12px; font-weight: 700;
  background: var(--bg2); border: 1px solid var(--border); color: var(--muted);
  cursor: pointer; transition: all var(--transition); font-family: inherit;
}
.symbol-tab:hover { border-color: var(--border-bright); color: var(--text-dim); }
.symbol-tab.active { background: var(--cyan-dim); border-color: var(--cyan); color: var(--cyan); }

/* ── Zone Legend ── */
.zone-legend {
  display: flex; gap: 16px; flex-wrap: wrap; padding: 10px 0; font-size: 11px;
}
.zone-legend-item { display: flex; align-items: center; gap: 6px; color: var(--text-dim); cursor: pointer; }
.zone-legend-dot { width: 10px; height: 10px; border-radius: 3px; }

/* ── Signal Cards ── */
.signal-card {
  background: var(--bg2); border: 1px solid var(--border); border-radius: var(--radius-sm);
  padding: 16px; margin-bottom: 10px;
  transition: border-color var(--transition);
}
.signal-card:hover { border-color: var(--border-bright); }
.signal-card .signal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.signal-card .signal-sym { font-size: 16px; font-weight: 800; }
.signal-card .signal-conf { font-size: 24px; font-weight: 800; }

/* ── Confluence Meter ── */
.confluence-meter {
  display: flex; gap: 3px; margin: 8px 0;
}
.confluence-bar {
  height: 6px; flex: 1; border-radius: 3px; background: var(--border);
  transition: background var(--transition);
}
.confluence-bar.filled { background: var(--green); }
.confluence-bar.partial { background: var(--yellow); }

/* ── Price Range Bar ── */
.price-range-bar {
  position: relative; height: 24px; background: var(--border); border-radius: 4px;
  margin: 8px 0; overflow: visible;
}
.price-range-sl { position: absolute; top: 0; height: 100%; background: var(--red-dim); border-radius: 4px 0 0 4px; }
.price-range-tp { position: absolute; top: 0; height: 100%; background: var(--green-dim); border-radius: 0 4px 4px 0; }
.price-range-current {
  position: absolute; top: -3px; width: 4px; height: 30px;
  background: var(--cyan); border-radius: 2px;
  box-shadow: 0 0 6px var(--cyan);
}
.price-range-label {
  position: absolute; top: -18px; font-size: 9px; font-weight: 700;
  transform: translateX(-50%); white-space: nowrap;
}

/* ── Strategy Bars ── */
.strat-row { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.strat-label { width: 140px; font-size: 11px; color: var(--text); text-align: right; overflow: hidden; text-overflow: ellipsis; }
.strat-bar-track { flex: 1; height: 16px; background: var(--border); border-radius: 5px; overflow: hidden; }
.strat-bar-fill { height: 100%; border-radius: 5px; transition: width 0.4s ease; display: flex; align-items: center; padding-left: 8px; font-size: 10px; font-weight: 700; color: #fff; }
.strat-pnl { width: 90px; font-size: 12px; text-align: right; font-weight: 700; }

/* ── Health Events ── */
.health-item { padding: 10px 14px; border-left: 3px solid var(--border); margin-bottom: 6px; font-size: 11px; border-radius: 0 6px 6px 0; background: rgba(255,255,255,0.01); }
.health-item.sev-INFO { border-left-color: var(--blue); }
.health-item.sev-WARNING { border-left-color: var(--yellow); }
.health-item.sev-ALERT, .health-item.sev-ERROR { border-left-color: var(--red); }

/* ── Copy Trade ── */
.copytrade-card { background: var(--card); border: 1px solid var(--border); border-left: 4px solid var(--purple); border-radius: var(--radius); padding: 18px; }
.copytrade-card h3 { font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--purple); margin-bottom: 10px; font-weight: 700; }

/* ── Pipeline Funnel ── */
.funnel-step {
  display: flex; align-items: center; gap: 12px; margin-bottom: 6px;
}
.funnel-bar-track { flex: 1; height: 28px; background: var(--border); border-radius: 6px; overflow: hidden; position: relative; }
.funnel-bar-fill { height: 100%; border-radius: 6px; display: flex; align-items: center; padding: 0 12px; font-size: 11px; font-weight: 700; transition: width 0.6s ease; }
.funnel-label { width: 130px; font-size: 11px; font-weight: 600; text-align: right; color: var(--text-dim); }
.funnel-count { width: 50px; font-size: 13px; font-weight: 800; text-align: left; }

/* ── Circuit Breaker ── */
.cb-gauge { display: flex; flex-direction: column; gap: 12px; }
.cb-row { display: flex; align-items: center; gap: 12px; }
.cb-label { width: 140px; font-size: 11px; color: var(--text-dim); }
.cb-bar { flex: 1; height: 10px; background: var(--border); border-radius: 5px; overflow: hidden; }
.cb-fill { height: 100%; border-radius: 5px; transition: width 0.5s ease; }
.cb-value { width: 80px; font-size: 12px; font-weight: 700; text-align: right; }

/* ── Animations ── */
@keyframes pulse { 0%,100% { opacity: 0.3; transform: scale(0.8); } 50% { opacity: 1; transform: scale(1.2); } }
@keyframes danger-pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
@keyframes glow-pulse { 0%,100% { box-shadow: 0 0 10px rgba(34,211,238,0.1); } 50% { box-shadow: 0 0 20px rgba(34,211,238,0.2); } }
.refresh-pulse { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: var(--blue); margin-right: 6px; animation: pulse 1.5s ease infinite; }
.danger-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: var(--red); margin-left: 6px; animation: danger-pulse 1.2s ease-in-out infinite; }

/* ── Empty States ── */
.empty { color: var(--muted); padding: 24px; text-align: center; font-size: 12px; }
.empty-icon { font-size: 28px; margin-bottom: 8px; opacity: 0.5; }
.empty-msg { margin-top: 4px; font-size: 11px; }

/* ── Section Titles ── */
.section-title { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); margin: 24px 0 12px 0; display: flex; align-items: center; gap: 8px; }

/* ── Footer ── */
.footer { text-align: center; color: var(--muted); font-size: 10px; padding: 24px 0 12px 0; border-top: 1px solid var(--border); margin-top: 24px; }

/* ── Responsive ── */
@media(max-width:1400px) { .grid-5 { grid-template-columns: repeat(3,1fr); } .grid-4 { grid-template-columns: repeat(2,1fr); } }
@media(max-width:1000px) { .grid-5 { grid-template-columns: repeat(2,1fr); } .grid-3,.grid-2 { grid-template-columns: 1fr; } .heatmap-grid { grid-template-columns: repeat(auto-fill,minmax(180px,1fr)); } .tab-btn { padding: 10px 14px; font-size: 11px; } }
@media(max-width:600px) { .grid-5,.grid-4 { grid-template-columns: 1fr; } .heatmap-grid { grid-template-columns: 1fr; } .top-bar { padding: 0 12px; } .tab-content { padding: 14px 12px; } .top-bar .equity-ticker { display: none; } }
</style>
</head>
<body>
<div class="app">

<!-- ═══ Top Bar ═══ -->
<div class="top-bar">
  <div class="brand">NunuIRL <span>Trading Intelligence</span></div>
  <div class="status-strip">
    <span class="equity-ticker" id="top-equity">$--</span>
    <span><span class="dot dot-green" id="health-dot"></span><span id="health-label">Connecting...</span></span>
    <span id="uptime-display">--</span>
    <span><span class="refresh-pulse"></span><span id="last-refresh">--</span></span>
  </div>
</div>

<!-- ═══ Tab Navigation ═══ -->
<div class="tab-nav">
  <button class="tab-btn active" data-tab="overview"><span class="tab-icon">&#9670;</span>Overview</button>
  <button class="tab-btn" data-tab="charts"><span class="tab-icon">&#9636;</span>Charts &amp; Zones</button>
  <button class="tab-btn" data-tab="signals"><span class="tab-icon">&#9889;</span>Signals</button>
  <button class="tab-btn" data-tab="trades"><span class="tab-icon">&#9733;</span>Trades</button>
  <button class="tab-btn" data-tab="analytics"><span class="tab-icon">&#9776;</span>Analytics</button>
  <button class="tab-btn" data-tab="system"><span class="tab-icon">&#9881;</span>System</button>
</div>

<!-- ════════════════════════════════════════════════════════════════════ -->
<!-- TAB 1: OVERVIEW -->
<!-- ════════════════════════════════════════════════════════════════════ -->
<div class="tab-content active" id="tab-overview">

  <!-- KPI Cards -->
  <div class="grid-5">
    <div class="card">
      <h3>Equity <button class="info-btn" onclick="showEdu('equity')">?</button></h3>
      <div class="metric blue" id="kpi-equity">--</div>
      <div class="metric-sub" id="kpi-equity-change">--</div>
    </div>
    <div class="card">
      <h3>Daily PnL <button class="info-btn" onclick="showEdu('daily_pnl')">?</button></h3>
      <div class="metric" id="kpi-pnl">$0.00</div>
      <div class="metric-sub" id="kpi-pnl-detail">0 trades | $0.00 fees</div>
    </div>
    <div class="card">
      <h3>Win Rate <button class="info-btn" onclick="showEdu('win_rate')">?</button></h3>
      <div class="metric" id="kpi-winrate">0%</div>
      <div class="bar-track"><div class="bar-fill" id="wr-bar" style="width:0%;background:var(--green)"></div></div>
      <div class="metric-sub" id="kpi-wl">0W / 0L</div>
    </div>
    <div class="card">
      <h3>Open Positions <button class="info-btn" onclick="showEdu('open_positions')">?</button></h3>
      <div class="metric cyan" id="kpi-open-positions">0</div>
      <div class="metric-sub" id="kpi-open-positions-sub">--</div>
    </div>
    <div class="card">
      <h3>Unrealized PnL <button class="info-btn" onclick="showEdu('unrealized_pnl')">?</button></h3>
      <div class="metric" id="kpi-unrealized-pnl">$0.00</div>
      <div class="metric-sub" id="kpi-unrealized-pnl-sub">across all positions</div>
    </div>
  </div>

  <!-- Live Positions Hero -->
  <div class="full-width">
    <div class="card-hero" style="animation: glow-pulse 3s ease infinite;">
      <h3>Live Positions <button class="info-btn" onclick="showEdu('positions')">?</button></h3>
      <div class="scroll-y">
        <table>
          <thead><tr><th>Symbol</th><th>Side</th><th>Entry</th><th>Current</th><th>Range</th><th>Unrealized PnL</th><th>PnL%</th><th>Leverage</th><th>State</th><th>Hold Time</th><th>Profile</th></tr></thead>
          <tbody id="positions-body"><tr><td colspan="11" class="empty"><div class="empty-icon">&#128269;</div>No open positions<div class="empty-msg">The bot is scanning for opportunities...</div></td></tr></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- Market Heatmap -->
  <div class="full-width">
    <div class="card">
      <h3>Market Awareness <button class="info-btn" onclick="showEdu('market_regime')">?</button></h3>
      <div class="heatmap-grid" id="heatmap-grid"><div class="empty" style="grid-column:1/-1;"><div class="empty-icon">&#127758;</div>Loading market data...</div></div>
    </div>
  </div>

  <!-- Signal Feed + Rejection Summary (2-col) -->
  <div class="grid-2">
    <div class="card">
      <h3>Signal Pipeline <button class="info-btn" onclick="showEdu('signal_pipeline')">?</button></h3>
      <div id="pipeline-funnel"><div class="empty"><div class="empty-icon">&#9889;</div>Signal pipeline loading...</div></div>
    </div>
    <div class="card">
      <h3>Recent Rejections <button class="info-btn" onclick="showEdu('rejections')">?</button></h3>
      <div class="scroll-y" style="max-height:300px;">
        <table>
          <thead><tr><th>Symbol</th><th>Side</th><th>Blocked By</th><th>Reason</th></tr></thead>
          <tbody id="rejections-body-mini"><tr><td colspan="4" class="empty">No rejections</td></tr></tbody>
        </table>
      </div>
    </div>
  </div>

</div>

<!-- ════════════════════════════════════════════════════════════════════ -->
<!-- TAB 2: CHARTS & ZONES -->
<!-- ════════════════════════════════════════════════════════════════════ -->
<div class="tab-content" id="tab-charts">

  <!-- Symbol Selector -->
  <div class="symbol-tabs" id="chart-symbol-tabs"></div>

  <!-- Zone Legend -->
  <div class="zone-legend">
    <div class="zone-legend-item"><div class="zone-legend-dot" style="background:#00e6a066;"></div>Deep Buy Zone <button class="info-btn" onclick="showEdu('deep_buy_zone')">?</button></div>
    <div class="zone-legend-item"><div class="zone-legend-dot" style="background:#00e6a033;"></div>Regular Buy Zone <button class="info-btn" onclick="showEdu('regular_buy_zone')">?</button></div>
    <div class="zone-legend-item"><div class="zone-legend-dot" style="background:#ff446633;"></div>Regular Sell Zone <button class="info-btn" onclick="showEdu('regular_sell_zone')">?</button></div>
    <div class="zone-legend-item"><div class="zone-legend-dot" style="background:#ff446666;"></div>Safe Sell Zone <button class="info-btn" onclick="showEdu('safe_sell_zone')">?</button></div>
    <div class="zone-legend-item"><div class="zone-legend-dot" style="background:var(--cyan);"></div>SMA20 <button class="info-btn" onclick="showEdu('sma')">?</button></div>
    <div class="zone-legend-item"><div class="zone-legend-dot" style="background:var(--purple);"></div>Entry Levels</div>
  </div>

  <!-- Main Chart -->
  <div class="card" style="padding:14px;">
    <div class="chart-container large" id="main-chart-container"></div>
  </div>

  <!-- Zone Details + Signal Context (below chart) -->
  <div class="grid-2" style="margin-top:16px;">
    <div class="card">
      <h3>Zone Analysis <button class="info-btn" onclick="showEdu('monte_carlo')">?</button></h3>
      <div id="zone-details"><div class="empty">Select a symbol to view zone analysis</div></div>
    </div>
    <div class="card">
      <h3>Active Signals on Chart <button class="info-btn" onclick="showEdu('signal_confluence')">?</button></h3>
      <div id="chart-signals"><div class="empty">Signal data will appear here</div></div>
    </div>
  </div>

</div>

<!-- ════════════════════════════════════════════════════════════════════ -->
<!-- TAB 3: SIGNALS -->
<!-- ════════════════════════════════════════════════════════════════════ -->
<div class="tab-content" id="tab-signals">

  <!-- Active Signals -->
  <div class="section-title">Active Signals <button class="info-btn" onclick="showEdu('signals')">?</button></div>
  <div id="active-signals-list"><div class="empty"><div class="empty-icon">&#128225;</div>No active signals right now<div class="empty-msg">The bot evaluates signals each scan cycle</div></div></div>

  <!-- Signal Pipeline Funnel (Full) -->
  <div class="section-title" style="margin-top:28px;">Signal Pipeline Funnel <button class="info-btn" onclick="showEdu('signal_pipeline')">?</button></div>
  <div class="card">
    <div id="pipeline-funnel-full"><div class="empty">Loading pipeline data...</div></div>
  </div>

  <!-- Rejected Signals Full Table -->
  <div class="section-title" style="margin-top:28px;">Rejected Signals / What If <button class="info-btn" onclick="showEdu('rejections')">?</button></div>
  <div class="card">
    <div class="scroll-y">
      <table>
        <thead><tr><th>Time</th><th>Symbol</th><th>Side</th><th>Confidence</th><th>Strategy</th><th>Blocked By</th><th>Reason</th><th>What If PnL</th></tr></thead>
        <tbody id="rejections-body"><tr><td colspan="8" class="empty">No rejected signals</td></tr></tbody>
      </table>
    </div>
  </div>

  <!-- Copy Trade Intelligence -->
  <div class="section-title" style="margin-top:28px;">AI Intelligence <button class="info-btn" onclick="showEdu('llm_agents')">?</button></div>
  <div class="copytrade-card">
    <h3>Multi-Agent Insights</h3>
    <div id="copytrade-content"><div class="empty"><div class="empty-icon">&#129302;</div>LLM Intelligence Offline<div class="empty-msg">Enable multi-agent system (LLM_MULTI_AGENT=true) to activate AI-powered trade analysis</div></div></div>
  </div>

</div>

<!-- ════════════════════════════════════════════════════════════════════ -->
<!-- TAB 4: TRADES -->
<!-- ════════════════════════════════════════════════════════════════════ -->
<div class="tab-content" id="tab-trades">

  <!-- Trade Stats Summary -->
  <div class="grid-4" id="trade-stats-cards">
    <div class="card"><h3>Total Trades</h3><div class="metric" id="ts-total">0</div></div>
    <div class="card"><h3>Profit Factor</h3><div class="metric" id="ts-pf">--</div></div>
    <div class="card"><h3>Avg Win</h3><div class="metric green" id="ts-avg-win">--</div></div>
    <div class="card"><h3>Avg Loss</h3><div class="metric red" id="ts-avg-loss">--</div></div>
  </div>

  <!-- Recent Trades Table -->
  <div class="card">
    <h3>Recent Trades <button class="info-btn" onclick="showEdu('trades')">?</button></h3>
    <div class="scroll-y" style="max-height:500px;">
      <table>
        <thead><tr><th>Time</th><th>Symbol</th><th>Side</th><th>Action</th><th>Price</th><th>PnL</th><th>Strategy</th></tr></thead>
        <tbody id="trades-body"><tr><td colspan="7" class="empty"><div class="empty-icon">&#128203;</div>No trades yet<div class="empty-msg">Trades will appear here once the bot starts executing</div></td></tr></tbody>
      </table>
    </div>
  </div>

  <!-- Performance by Strategy + Symbol -->
  <div class="grid-2" style="margin-top:16px;">
    <div class="card">
      <h3>Performance by Strategy (7d) <button class="info-btn" onclick="showEdu('strategy_performance')">?</button></h3>
      <div class="scroll-y"><table><thead><tr><th>Strategy</th><th>Trades</th><th>Wins</th><th>Win Rate</th><th>PnL</th><th>Avg Score</th></tr></thead><tbody id="signal-strat-body"><tr><td colspan="6" class="empty">Loading...</td></tr></tbody></table></div>
    </div>
    <div class="card">
      <h3>Performance by Symbol (7d)</h3>
      <div class="scroll-y"><table><thead><tr><th>Symbol</th><th>Trades</th><th>Wins</th><th>Win Rate</th><th>PnL</th></tr></thead><tbody id="signal-sym-body"><tr><td colspan="5" class="empty">Loading...</td></tr></tbody></table></div>
    </div>
  </div>

</div>

<!-- ════════════════════════════════════════════════════════════════════ -->
<!-- TAB 5: ANALYTICS -->
<!-- ════════════════════════════════════════════════════════════════════ -->
<div class="tab-content" id="tab-analytics">

  <!-- Equity Curve -->
  <div class="card">
    <h3>Equity Curve (30d) <button class="info-btn" onclick="showEdu('equity_curve')">?</button></h3>
    <div class="chart-wrap" style="height:300px;"><canvas id="equity-chart"></canvas></div>
  </div>

  <!-- Strategy Breakdown -->
  <div class="grid-2" style="margin-top:16px;">
    <div class="card">
      <h3>Strategy Breakdown (Today) <button class="info-btn" onclick="showEdu('ensemble')">?</button></h3>
      <div id="strategy-bars"><div class="empty">No strategy data yet</div></div>
    </div>
    <div class="card">
      <h3>Strategy Weights <button class="info-btn" onclick="showEdu('strategy_weights')">?</button></h3>
      <div id="strategy-weights"><div class="empty">Strategy weights loading...</div></div>
    </div>
  </div>

  <!-- Daily PnL History -->
  <div class="card" style="margin-top:16px;">
    <h3>Daily PnL History <button class="info-btn" onclick="showEdu('daily_pnl')">?</button></h3>
    <div class="chart-wrap" style="height:200px;"><canvas id="daily-pnl-chart"></canvas></div>
  </div>

</div>

<!-- ════════════════════════════════════════════════════════════════════ -->
<!-- TAB 6: SYSTEM -->
<!-- ════════════════════════════════════════════════════════════════════ -->
<div class="tab-content" id="tab-system">

  <!-- Health Status -->
  <div class="grid-3">
    <div class="card"><h3>Bot Uptime</h3><div class="metric cyan" id="health-uptime">--</div><div class="metric-sub" id="health-started">--</div></div>
    <div class="card"><h3>Last Heartbeat</h3><div class="metric" id="health-heartbeat" style="font-size:18px;">--</div><div class="metric-sub" id="health-heartbeat-ago">--</div></div>
    <div class="card"><h3>Errors (24h)</h3><div class="metric" id="health-errors">0</div><div class="metric-sub" id="health-warnings">0 warnings</div></div>
  </div>

  <!-- Circuit Breaker + Risk -->
  <div class="grid-2">
    <div class="card">
      <h3>Circuit Breakers <button class="info-btn" onclick="showEdu('circuit_breaker')">?</button></h3>
      <div id="cb-status"><div class="empty">Circuit breaker data loading...</div></div>
    </div>
    <div class="card">
      <h3>Go-Live Gates <button class="info-btn" onclick="showEdu('go_live_gates')">?</button></h3>
      <div id="gates-status"><div class="empty">Gate data loading...</div></div>
    </div>
  </div>

  <!-- Health Events -->
  <div class="card">
    <h3>Recent Health Events</h3>
    <div class="scroll-y" id="health-events-list"><div class="empty">No health events</div></div>
  </div>

</div>

<!-- ═══ Educational Modal ═══ -->
<div class="edu-modal-overlay" id="edu-overlay" onclick="if(event.target===this)closeEdu()">
  <div class="edu-modal" style="position:relative;">
    <button class="edu-close" onclick="closeEdu()">&times;</button>
    <div class="edu-icon" id="edu-icon"></div>
    <div class="edu-title" id="edu-title"></div>
    <div class="edu-short" id="edu-short"></div>
    <div class="edu-detail" id="edu-detail"></div>
  </div>
</div>

<!-- ═══ Footer ═══ -->
<div style="padding:0 24px;">
  <div class="footer">NunuIRL Trading Bot &mdash; Dashboard v4.0 &mdash; Positions 10s | Data 30s | Charts on demand</div>
</div>

</div>
<script>
/* ═══════════════════════════════════════════════════════════════════ */
/* EDUCATIONAL CONTENT                                                */
/* ═══════════════════════════════════════════════════════════════════ */
const EDUCATION = {
  equity: { title:"Equity", icon:"\ud83d\udcb0", short:"Your total account value including all open positions.",
    detail:"<p><strong>Equity</strong> is the total value of your trading account right now. It includes your cash balance plus any unrealized profit or loss from open positions.</p><p>Think of it like checking your bank balance, but it fluctuates in real-time as the market moves. If you have a $1,000 account and an open trade that's up $50, your equity is $1,050.</p><p>Watching equity over time tells you whether your overall trading approach is growing your account or shrinking it.</p>" },
  daily_pnl: { title:"Daily PnL", icon:"\ud83d\udcc8", short:"Profit and Loss for today \u2014 how much money you've made or lost.",
    detail:"<p><strong>PnL (Profit and Loss)</strong> is the net result of all trades closed today, minus any fees paid to the exchange.</p><p>A positive PnL means the bot made money today. A negative PnL means it lost money. This is the most direct measure of daily performance.</p><p><strong>Fees matter:</strong> Every trade costs a small fee (usually 0.02-0.06% per trade). These add up, especially with frequent trading. The fee amount is shown separately so you can see the true cost.</p>" },
  win_rate: { title:"Win Rate", icon:"\ud83c\udfaf", short:"Percentage of trades that made money.",
    detail:"<p><strong>Win Rate</strong> is simply: (winning trades \u00f7 total trades) \u00d7 100%. A 60% win rate means 6 out of every 10 trades were profitable.</p><p><strong>Important:</strong> Win rate alone doesn't tell the whole story. You can have a 40% win rate and still be very profitable if your average win is much larger than your average loss. This is why Risk:Reward ratio matters too.</p><p>Most successful trading systems have win rates between 40-65%. Anything above 70% is exceptional and should be examined carefully to make sure it's sustainable.</p>" },
  open_positions: { title:"Open Positions", icon:"\ud83d\udcca", short:"Number of trades currently active (not yet closed).",
    detail:"<p><strong>Open positions</strong> are trades the bot has entered but not yet exited. Each position has an entry price, stop loss, and take profit targets.</p><p>More open positions means more capital at risk but also more potential opportunity. The bot limits how many positions can be open simultaneously to manage risk.</p>" },
  unrealized_pnl: { title:"Unrealized PnL", icon:"\u23f3", short:"Potential profit/loss on open trades that haven't been closed yet.",
    detail:"<p><strong>Unrealized PnL</strong> is what your open trades are worth right now, but you haven't locked in yet. It's 'paper profit' or 'paper loss'.</p><p>If you have a trade that's up $20, that $20 is unrealized \u2014 it only becomes real (realized) when you close the trade. The market could reverse and turn that $20 gain into a loss.</p><p>This is why stop losses exist: they automatically close a trade to prevent unrealized losses from growing too large.</p>" },
  market_regime: { title:"Market Regime", icon:"\ud83c\udf0a", short:"The current 'personality' of the market \u2014 trending, ranging, or chaotic.",
    detail:"<p><strong>Market regime</strong> describes the current behavior pattern of the market. Different regimes require different trading strategies:</p><p><strong>\u2022 Trend:</strong> Price is moving consistently in one direction. Best for momentum strategies.<br><strong>\u2022 Range:</strong> Price is bouncing between support and resistance. Best for buy-low-sell-high strategies.<br><strong>\u2022 High Volatility:</strong> Large, unpredictable price swings. Higher risk, but also opportunity.<br><strong>\u2022 Panic:</strong> Sharp selloffs driven by fear. Very dangerous for longs.<br><strong>\u2022 Low Liquidity:</strong> Not many buyers/sellers. Prices can gap unexpectedly.</p><p>The bot detects the current regime and adjusts its strategy accordingly. Trading against the regime (e.g., buying in a panic) is the most common way to lose money.</p>" },
  signal_pipeline: { title:"Signal Pipeline", icon:"\ud83d\udd0d", short:"The step-by-step process signals go through before becoming trades.",
    detail:"<p>Every potential trade goes through a <strong>6-stage safety pipeline</strong> before the bot will execute it:</p><p><strong>1. Signal Generation:</strong> 4 independent strategies analyze the market and vote.<br><strong>2. Ensemble Vote:</strong> Multiple strategies must agree (confluence) for the signal to pass.<br><strong>3. Circuit Breaker:</strong> Checks if we've lost too much today or hit too many losses in a row.<br><strong>4. Position Limits:</strong> Ensures we're not over-exposed.<br><strong>5. Leverage &amp; Liquidation:</strong> Calculates safe leverage and checks liquidation risk.<br><strong>6. Size Check:</strong> Ensures the position size meets the exchange's minimum.</p><p>Each gate can reject a signal. This is intentional \u2014 the pipeline is conservative to protect your capital. Most signals get rejected, and that's a good thing.</p>" },
  rejections: { title:"Rejected Signals", icon:"\ud83d\udeab", short:"Signals that were blocked by safety gates before becoming trades.",
    detail:"<p>When a strategy generates a signal but it gets <strong>rejected</strong>, it means one of the safety gates blocked it. This is the bot protecting your money.</p><p><strong>Hard gates</strong> (red) are non-negotiable: circuit breakers, liquidation risk, max positions. These exist to prevent catastrophic losses.</p><p><strong>Soft gates</strong> (yellow) are quality filters: minimum R:R ratio, expected value floor, fee drag. These ensure trades are worth taking after costs.</p><p>The <strong>What If PnL</strong> column shows what would have happened if the trade had been taken. Sometimes rejected signals would have been winners \u2014 that's the cost of safety. But over time, the gates save more money than they cost.</p>" },
  monte_carlo: { title:"Monte Carlo Simulation", icon:"\ud83c\udfb2", short:"Running thousands of random price simulations to predict probable future zones.",
    detail:"<p><strong>Monte Carlo simulation</strong> is a statistical technique that runs thousands of random price path simulations to estimate where price is likely to go.</p><p>Based on recent volatility and price history, it calculates probability bands \u2014 zones where price is statistically likely to find support (buyers step in) or resistance (sellers take profit).</p><p>The zones are color-coded from green (strong buy zone \u2014 price rarely goes this low) to red (strong sell zone \u2014 price rarely goes this high). When price enters these zones, it's a statistical edge.</p><p><strong>Note:</strong> These are probabilities, not guarantees. Black swan events can blow through any zone.</p>" },
  deep_buy_zone: { title:"Deep Buy Zone", icon:"\ud83d\udfe2", short:"Strong support area \u2014 price rarely drops this far, historically a high-probability buying opportunity.",
    detail:"<p>The <strong>Deep Buy Zone</strong> is calculated as SMA20 minus 2.2 standard deviations. Statistically, price only reaches this level about 1-3% of the time.</p><p>When price enters this zone, it represents an oversold condition. The Monte Carlo simulation shows that from this level, there's a high probability of a bounce. However, if price breaks through this zone, it could signal a regime change to panic.</p><p><strong>For traders:</strong> This is the area where the bot identifies the highest-conviction buying opportunities. Positions entered here typically have the best risk:reward ratios.</p>" },
  regular_buy_zone: { title:"Regular Buy Zone", icon:"\ud83d\udfe9", short:"Moderate support area \u2014 good buying zone in normal conditions.",
    detail:"<p>The <strong>Regular Buy Zone</strong> sits between the SMA20 and the Deep Buy Zone (SMA20 minus 1.3 standard deviations). Price visits this zone more frequently than the Deep Buy Zone.</p><p>This is a good entry area during trending or range-bound markets. The risk:reward isn't as extreme as the Deep Buy Zone, but opportunities are more frequent.</p>" },
  regular_sell_zone: { title:"Regular Sell Zone", icon:"\ud83d\udfe5", short:"Moderate resistance area \u2014 good zone to take profits.",
    detail:"<p>The <strong>Regular Sell Zone</strong> is the mirror of Regular Buy (SMA20 plus 1.3 standard deviations). When price reaches this zone, it's statistically extended to the upside.</p><p>This is where take-profit orders are often placed. If you bought in the buy zone, selling here locks in a profit while price is still elevated.</p>" },
  safe_sell_zone: { title:"Safe Sell Zone", icon:"\ud83d\udd34", short:"Strong resistance area \u2014 price rarely goes this high, high-probability profit-taking zone.",
    detail:"<p>The <strong>Safe Sell Zone</strong> (SMA20 plus 2.2 standard deviations) is the strongest resistance area. Price reaches this level only 1-3% of the time statistically.</p><p>This is where aggressive profit-taking happens. The Monte Carlo simulation shows high probability of a pullback from this level. It's also where the bot identifies the best shorting opportunities.</p>" },
  sma: { title:"SMA (Simple Moving Average)", icon:"\u2796", short:"The average price over the last 20 periods \u2014 the center of the trading range.",
    detail:"<p>The <strong>SMA20 (Simple Moving Average)</strong> is just the average closing price over the last 20 candles. It acts as the center line for the Monte Carlo zones.</p><p>When price is above the SMA20, the short-term trend is bullish. When below, it's bearish. The SMA20 often acts as dynamic support in uptrends and resistance in downtrends.</p><p>All the zone calculations are based on how far price deviates from this average.</p>" },
  signal_confluence: { title:"Signal Confluence", icon:"\ud83e\udd1d", short:"When multiple independent strategies agree on the same trade direction.",
    detail:"<p><strong>Confluence</strong> is when multiple independent analysis methods point to the same conclusion. It's one of the strongest edges in trading.</p><p>The bot runs 4 different strategies simultaneously. When 3 or 4 of them agree on a direction (e.g., all saying BUY), that's high confluence. The more strategies that agree, the higher the confidence score.</p><p><strong>Why it matters:</strong> Each strategy can be wrong on its own. But when multiple independent methods agree, the probability of being right increases significantly. Think of it like getting a second (and third, and fourth) opinion.</p>" },
  circuit_breaker: { title:"Circuit Breaker", icon:"\u26a1", short:"Emergency safety system that stops trading after too many losses.",
    detail:"<p><strong>Circuit breakers</strong> are automatic safety switches that halt trading when risk thresholds are exceeded:</p><p><strong>\u2022 Daily Loss Limit:</strong> If losses exceed a percentage of current equity in one day, trading stops until tomorrow.<br><strong>\u2022 Consecutive Losses:</strong> If N trades in a row lose money, trading pauses to prevent tilt-driven losses.<br><strong>\u2022 Drawdown Cap:</strong> If the account drops too far from its peak, all trading stops.</p><p>These exist because the biggest risk in trading isn't individual losses \u2014 it's a cascade of losses that wipes out the account. Circuit breakers prevent that spiral.</p>" },
  go_live_gates: { title:"Go-Live Gates", icon:"\ud83d\udea6", short:"5 checkpoints the bot must pass before trading with real money.",
    detail:"<p>Before switching from paper trading to live trading, the bot must pass 5 validation gates:</p><p><strong>1. Walk Forward:</strong> Strategy works on unseen data.<br><strong>2. Net PnL:</strong> System is profitable over the test period.<br><strong>3. Max Drawdown:</strong> Worst peak-to-trough drop is within acceptable limits.<br><strong>4. Factor ICs:</strong> Individual prediction factors have statistical significance.<br><strong>5. Sharpe Ratio:</strong> Risk-adjusted returns meet the minimum threshold.</p><p>All 5 gates must be green before live trading is authorized. This prevents deploying an untested or unprofitable system with real money.</p>" },
  positions: { title:"Trading Positions", icon:"\ud83d\udcbc", short:"Active trades with entry, stop loss, and take profit levels.",
    detail:"<p>Each <strong>position</strong> represents an active trade. Key information:</p><p><strong>\u2022 Side:</strong> LONG (betting price goes up) or SHORT (betting price goes down).<br><strong>\u2022 Entry:</strong> The price where the trade was opened.<br><strong>\u2022 Stop Loss (SL):</strong> The price where the trade automatically closes to limit losses.<br><strong>\u2022 Take Profit (TP1/TP2):</strong> Target prices to lock in profits.<br><strong>\u2022 Leverage:</strong> How much borrowed money is used (2x = trading with twice your money).<br><strong>\u2022 State:</strong> OPEN \u2192 TP1_HIT \u2192 TRAILING \u2192 CLOSED.</p><p>The <strong>price range bar</strong> shows where current price sits between the stop loss and take profit targets.</p>" },
  ensemble: { title:"Ensemble Voting", icon:"\ud83d\uddf3\ufe0f", short:"4 independent strategies vote on each trade \u2014 majority rules.",
    detail:"<p>The bot uses an <strong>ensemble</strong> (team) of 4 independent trading strategies. Each strategy analyzes the market differently and casts a vote.</p><p><strong>The 4 strategies:</strong><br>\u2022 Regime Trend \u2014 Follows overall market direction using momentum indicators<br>\u2022 Monte Carlo Zones \u2014 Statistical support/resistance from price simulations<br>\u2022 Multi-Tier Quality \u2014 Multi-timeframe signal quality scoring<br>\u2022 Confidence Scorer \u2014 Multi-factor confidence aggregation</p><p>A trade only executes when enough strategies agree (minimum 2 same-direction votes). This <strong>weighted veto</strong> system prevents any single strategy from making a bad trade on its own.</p>" },
  strategy_weights: { title:"Strategy Weights", icon:"\u2696\ufe0f", short:"How much influence each strategy has in the ensemble vote.",
    detail:"<p>Not all strategies are weighted equally. <strong>Strategy weights</strong> are adaptive \u2014 strategies that have been performing well recently get more influence, while struggling strategies get less.</p><p>Weights are recalculated based on rolling performance with exponential decay (recent trades matter more). This means the system naturally adapts to changing market conditions.</p>" },
  strategy_performance: { title:"Strategy Performance", icon:"\ud83d\udcca", short:"How each individual strategy is performing over the last 7 days.",
    detail:"<p>This table breaks down the performance of each of the 4 trading strategies independently. Key metrics:</p><p><strong>\u2022 Trades:</strong> How many signals this strategy generated that became trades.<br><strong>\u2022 Win Rate:</strong> What percentage of those trades were profitable.<br><strong>\u2022 PnL:</strong> Total profit or loss from this strategy's trades.<br><strong>\u2022 Avg Score:</strong> Average confidence score of signals (higher = more confident).</p>" },
  equity_curve: { title:"Equity Curve", icon:"\ud83d\udcc8", short:"A chart showing how your account value has changed over time.",
    detail:"<p>The <strong>equity curve</strong> plots your account value day by day. An upward-sloping curve means you're making money; downward means you're losing.</p><p><strong>What to look for:</strong><br>\u2022 Steady upward slope = consistent profitability<br>\u2022 Sharp drops = drawdowns (normal but should recover)<br>\u2022 Flat periods = no edge in current market conditions<br>\u2022 Stair-step pattern = normal for low-frequency trading</p>" },
  trades: { title:"Trade Journal", icon:"\ud83d\udcd3", short:"A log of every trade the bot has made with full details.",
    detail:"<p>The <strong>trade journal</strong> records every trade with its timestamp, symbol, direction, entry/exit price, and PnL. This is essential for learning what's working and what isn't.</p><p>Review your trades regularly to spot patterns: Are losses clustered around certain times? Does one symbol consistently underperform? Are stop losses too tight?</p>" },
  llm_agents: { title:"AI Multi-Agent System", icon:"\ud83e\udd16", short:"6 specialized AI agents that analyze trades from different perspectives.",
    detail:"<p>When enabled, the bot uses <strong>6 specialized AI agents</strong> (powered by Claude) that each analyze trades from a different angle:</p><p><strong>\u2022 Regime Agent:</strong> Classifies the current market environment.<br><strong>\u2022 Trade Agent:</strong> Forms a directional thesis (buy/sell/skip).<br><strong>\u2022 Risk Agent:</strong> Sizes positions and flags portfolio risks.<br><strong>\u2022 Critic Agent:</strong> Stress-tests the thesis and can veto bad trades.<br><strong>\u2022 Learning Agent:</strong> Extracts lessons from closed trades.<br><strong>\u2022 Exit Agent:</strong> Monitors open positions and recommends exits.</p><p>This creates a checks-and-balances system where no single perspective dominates.</p>" },
  signals: { title:"Trading Signals", icon:"\u26a1", short:"Buy or sell recommendations generated by the bot's analysis strategies.",
    detail:"<p>A <strong>signal</strong> is a recommendation to buy or sell a specific asset. Each signal includes:</p><p><strong>\u2022 Direction:</strong> BUY (go long) or SELL (go short)<br><strong>\u2022 Confidence:</strong> How certain the bot is (0-100%)<br><strong>\u2022 Entry Price:</strong> The recommended entry level<br><strong>\u2022 Stop Loss:</strong> Where to cut losses if wrong<br><strong>\u2022 Take Profit:</strong> Target prices for locking in gains</p><p>Not every signal becomes a trade. Signals must pass through the safety pipeline first, and many get filtered out. This is intentional \u2014 quality over quantity.</p>" },
  leverage: { title:"Leverage", icon:"\ud83d\udd0d", short:"Borrowed money that amplifies both gains AND losses.",
    detail:"<p><strong>Leverage</strong> lets you trade with more money than you have. 3x leverage means you're controlling 3x your actual capital.</p><p><strong>\u26a0\ufe0f Warning:</strong> Leverage is a double-edged sword. If you use 3x leverage and price moves 10% in your favor, you make 30%. But if it moves 10% against you, you lose 30%.</p><p>The bot calculates leverage based on confidence level and stop loss distance. Higher confidence + wider stops = more leverage allowed. The system caps maximum leverage to prevent excessive risk.</p>" },
  candlestick: { title:"Candlestick Charts", icon:"\ud83d\udcca", short:"Each candle shows the open, high, low, and close price for a time period.",
    detail:"<p>A <strong>candlestick</strong> represents price action for one time period (e.g., 1 hour):</p><p><strong>\u2022 Body (thick part):</strong> Shows open-to-close range. Green = price went up, Red = price went down.<br><strong>\u2022 Wicks (thin lines):</strong> Show the high and low reached during that period.<br><strong>\u2022 Long wick down:</strong> Buyers stepped in and pushed price back up (bullish).<br><strong>\u2022 Long wick up:</strong> Sellers stepped in and pushed price back down (bearish).</p><p>Reading candlestick patterns is one of the most fundamental skills in trading. The bot's Monte Carlo zones are overlaid on these charts to show key price levels.</p>" },
  paper_trading: { title:"Paper Trading", icon:"\ud83d\udcdd", short:"Simulated trading with fake money to test strategies before risking real capital.",
    detail:"<p><strong>Paper trading</strong> means the bot executes all its logic \u2014 signal generation, risk management, position sizing \u2014 but with simulated money instead of real funds.</p><p>This is how you validate that a trading system works before putting real money at risk. The bot tracks all trades as if they were real, including fees and slippage.</p><p>The Go-Live Gates system monitors paper trading performance and only authorizes live trading once specific performance benchmarks are met.</p>" }
};

/* ═══════════════════════════════════════════════════════════════════ */
/* UTILITY FUNCTIONS                                                  */
/* ═══════════════════════════════════════════════════════════════════ */
function fmt$(v) { if(v==null||isNaN(v)) return '--'; return (v>=0?'+':'')+'\u0024'+Math.abs(v).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2}); }
function fmtAbs$(v) { if(v==null||isNaN(v)) return '--'; return '\u0024'+Math.abs(v).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2}); }
function fmtPct(v) { if(v==null||isNaN(v)) return '--'; return (v>=0?'+':'')+v.toFixed(2)+'%'; }
function fmtTime(iso) { if(!iso) return '--'; try { return new Date(iso).toLocaleTimeString(); } catch { return iso; } }
function fmtDateTime(iso) { if(!iso) return '--'; try { const d=new Date(iso); return d.toLocaleDateString(undefined,{month:'short',day:'numeric'})+' '+d.toLocaleTimeString(); } catch { return iso; } }
function fmtDuration(s) { if(!s||s<0) return '--'; const d=Math.floor(s/86400),h=Math.floor((s%86400)/3600),m=Math.floor((s%3600)/60),sec=Math.floor(s%60); if(d>0) return d+'d '+h+'h '+m+'m'; if(h>0) return h+'h '+m+'m '+sec+'s'; if(m>0) return m+'m '+sec+'s'; return sec+'s'; }
function fmtPrice(v) { if(v==null||isNaN(v)) return '--'; if(v>1000) return '\u0024'+v.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2}); return '\u0024'+v.toFixed(v<1?6:4); }
function pnlColor(v) { return v>=0 ? 'var(--green)' : 'var(--red)'; }
function pnlClass(v) { return v>=0 ? 'green' : 'red'; }
function sidePill(side) { const s=(side||'').toUpperCase(); const isLong=s==='BUY'||s==='LONG'; return '<span class="pill '+(isLong?'pill-long':'pill-short')+'">'+(isLong?'LONG':'SHORT')+'</span>'; }

/* ═══════════════════════════════════════════════════════════════════ */
/* EDUCATIONAL MODAL                                                  */
/* ═══════════════════════════════════════════════════════════════════ */
function showEdu(key) {
  const info = EDUCATION[key];
  if(!info) return;
  document.getElementById('edu-icon').textContent = info.icon || '\u2753';
  document.getElementById('edu-title').textContent = info.title || key;
  document.getElementById('edu-short').textContent = info.short || '';
  document.getElementById('edu-detail').innerHTML = info.detail || '';
  document.getElementById('edu-overlay').classList.add('visible');
}
function closeEdu() { document.getElementById('edu-overlay').classList.remove('visible'); }
document.addEventListener('keydown', e => { if(e.key==='Escape') closeEdu(); });

/* ═══════════════════════════════════════════════════════════════════ */
/* TAB NAVIGATION                                                     */
/* ═══════════════════════════════════════════════════════════════════ */
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    const tab = document.getElementById('tab-' + btn.dataset.tab);
    if(tab) tab.classList.add('active');
    if(btn.dataset.tab === 'charts' && !chartInitialized) initChartTab();
    if(btn.dataset.tab === 'analytics' && !analyticsInitialized) loadAnalytics();
  });
});

/* ═══════════════════════════════════════════════════════════════════ */
/* CHART TAB — TradingView Lightweight Charts                         */
/* ═══════════════════════════════════════════════════════════════════ */
let chartInitialized = false;
let tvChart = null;
let tvCandleSeries = null;
let currentChartSymbol = null;
let zonePriceLines = [];

function initChartTab() {
  chartInitialized = true;
  loadChartSymbols();
}

async function loadChartSymbols() {
  try {
    const res = await fetch('/api/market');
    let symbols = [];
    if(res.ok) {
      const market = await res.json();
      symbols = market.map(m => m.symbol).filter(Boolean);
    }
    if(symbols.length === 0) symbols = ['BTC','SOL','HYPE','DOGE','FARTCOIN'];
    const container = document.getElementById('chart-symbol-tabs');
    container.innerHTML = symbols.map((s,i) =>
      '<button class="symbol-tab'+(i===0?' active':'')+'" data-symbol="'+s+'" onclick="selectChartSymbol(\''+s+'\')">'+s+'</button>'
    ).join('');
    selectChartSymbol(symbols[0]);
  } catch { selectChartSymbol('BTC'); }
}

async function selectChartSymbol(symbol) {
  currentChartSymbol = symbol;
  document.querySelectorAll('.symbol-tab').forEach(b => {
    b.classList.toggle('active', b.dataset.symbol === symbol);
  });
  await loadChartData(symbol);
}

async function loadChartData(symbol) {
  const container = document.getElementById('main-chart-container');
  if(!container) return;

  // Create or recreate chart
  if(tvChart) { tvChart.remove(); tvChart = null; }
  container.innerHTML = '';

  tvChart = LightweightCharts.createChart(container, {
    width: container.clientWidth,
    height: 420,
    layout: { background: { type: 'solid', color: '#0f0f1e' }, textColor: '#9090b0', fontFamily: "'SF Mono','Fira Code',monospace", fontSize: 11 },
    grid: { vertLines: { color: 'rgba(26,26,53,0.5)' }, horzLines: { color: 'rgba(26,26,53,0.5)' } },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal, vertLine: { color: 'rgba(34,211,238,0.3)', labelBackgroundColor: '#1a1a35' }, horzLine: { color: 'rgba(34,211,238,0.3)', labelBackgroundColor: '#1a1a35' } },
    rightPriceScale: { borderColor: '#1a1a35' },
    timeScale: { borderColor: '#1a1a35', timeVisible: true, secondsVisible: false },
    handleScroll: true, handleScale: true,
  });

  tvCandleSeries = tvChart.addSeries(LightweightCharts.CandlestickSeries, {
    upColor: '#00e6a0', downColor: '#ff4466',
    borderUpColor: '#00e6a0', borderDownColor: '#ff4466',
    wickUpColor: '#00e6a088', wickDownColor: '#ff446688',
  });

  // Fetch OHLCV + zones in parallel
  const [ohlcvRes, zonesRes] = await Promise.allSettled([
    fetch('/api/ohlcv?symbol='+symbol+'&timeframe=1h'),
    fetch('/api/zones?symbol='+symbol)
  ]);

  // Set candle data
  if(ohlcvRes.status==='fulfilled' && ohlcvRes.value.ok) {
    try {
      const candles = await ohlcvRes.value.json();
      if(Array.isArray(candles) && candles.length > 0) {
        const chartData = candles.map(c => ({
          time: typeof c.time === 'string' ? Math.floor(new Date(c.time).getTime()/1000) : c.time,
          open: c.open, high: c.high, low: c.low, close: c.close
        })).filter(c => c.time && !isNaN(c.open));
        if(chartData.length > 0) {
          tvCandleSeries.setData(chartData);
          tvChart.timeScale().fitContent();
        }
      }
    } catch(e) { console.error('OHLCV parse error:', e); }
  }

  // Overlay zones
  zonePriceLines.forEach(pl => { try { tvCandleSeries.removePriceLine(pl); } catch {} });
  zonePriceLines = [];

  let zoneData = null;
  if(zonesRes.status==='fulfilled' && zonesRes.value.ok) {
    try { zoneData = await zonesRes.value.json(); } catch {}
  }

  if(zoneData && zoneData.zones) {
    const z = zoneData.zones;
    const zoneConfigs = [
      { price: z.safe_sell, title: 'Safe Sell Zone', color: '#ff4466', style: 2 },
      { price: z.regular_sell, title: 'Regular Sell', color: '#ff446688', style: 1 },
      { price: z.sma20, title: 'SMA20', color: '#22d3ee', style: 2 },
      { price: z.regular_buy, title: 'Regular Buy', color: '#00e6a088', style: 1 },
      { price: z.deep_buy, title: 'Deep Buy Zone', color: '#00e6a0', style: 2 },
    ];

    zoneConfigs.forEach(zc => {
      if(zc.price && !isNaN(zc.price)) {
        const pl = tvCandleSeries.createPriceLine({
          price: zc.price, color: zc.color, lineWidth: 1,
          lineStyle: zc.style, axisLabelVisible: true, title: zc.title,
        });
        zonePriceLines.push(pl);
      }
    });

    // Zone details panel
    renderZoneDetails(z, zoneData.regime);
  }

  // Signal markers
  if(zoneData && zoneData.signals && zoneData.signals.length > 0) {
    renderChartSignals(zoneData.signals);
    try {
      const markers = zoneData.signals.map(s => ({
        time: typeof s.timestamp === 'string' ? Math.floor(new Date(s.timestamp).getTime()/1000) : s.timestamp,
        position: (s.side||'').toUpperCase()==='BUY' ? 'belowBar' : 'aboveBar',
        color: (s.side||'').toUpperCase()==='BUY' ? '#00e6a0' : '#ff4466',
        shape: (s.side||'').toUpperCase()==='BUY' ? 'arrowUp' : 'arrowDown',
        text: (s.strategy||'Signal') + ' ' + (s.confidence||0).toFixed(0) + '%',
      })).filter(m => m.time && !isNaN(m.time)).sort((a,b) => a.time - b.time);
      if(markers.length > 0 && typeof LightweightCharts.createSeriesMarkers === 'function') {
        LightweightCharts.createSeriesMarkers(tvCandleSeries, markers);
      }
    } catch(e) { console.error('Marker error:', e); }
  }

  // Resize handler
  const resizeObserver = new ResizeObserver(entries => {
    if(tvChart) tvChart.applyOptions({ width: container.clientWidth });
  });
  resizeObserver.observe(container);
}

function renderZoneDetails(zones, regime) {
  const el = document.getElementById('zone-details');
  if(!el) return;
  const items = [
    { label: 'Safe Sell', price: zones.safe_sell, color: 'var(--red)', desc: 'Strong resistance \u2014 statistically unlikely to go higher' },
    { label: 'Regular Sell', price: zones.regular_sell, color: 'var(--red)', desc: 'Moderate resistance \u2014 good profit-taking zone' },
    { label: 'SMA20 (Center)', price: zones.sma20, color: 'var(--cyan)', desc: 'Moving average \u2014 fair value center' },
    { label: 'Regular Buy', price: zones.regular_buy, color: 'var(--green)', desc: 'Moderate support \u2014 good entry zone' },
    { label: 'Deep Buy', price: zones.deep_buy, color: 'var(--green)', desc: 'Strong support \u2014 high-probability bounce area' },
  ];
  let html = '<div style="margin-bottom:12px;">Regime: <span class="regime-pill" style="background:var(--blue-dim);color:var(--blue);">'+(regime||'unknown').toUpperCase()+'</span></div>';
  items.forEach(item => {
    if(item.price) {
      html += '<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;padding:8px;background:var(--bg2);border-radius:6px;border-left:3px solid '+item.color+';">' +
        '<div style="flex:1;"><div style="font-weight:700;font-size:12px;color:'+item.color+';">'+item.label+'</div><div style="font-size:10px;color:var(--muted);">'+item.desc+'</div></div>' +
        '<div style="font-size:14px;font-weight:800;">'+fmtPrice(item.price)+'</div></div>';
    }
  });
  el.innerHTML = html;
}

function renderChartSignals(signals) {
  const el = document.getElementById('chart-signals');
  if(!el) return;
  if(!signals || signals.length === 0) { el.innerHTML = '<div class="empty">No signals for this symbol</div>'; return; }
  el.innerHTML = signals.slice(0,8).map(s => {
    const isLong = (s.side||'').toUpperCase() === 'BUY';
    return '<div class="signal-card" style="border-left:3px solid '+(isLong?'var(--green)':'var(--red)')+';padding:10px 14px;margin-bottom:6px;">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;">' +
      '<div>'+sidePill(s.side)+' <span style="font-weight:700;font-size:13px;margin-left:6px;">'+(s.confidence||0).toFixed(0)+'%</span></div>' +
      '<span style="font-size:10px;color:var(--muted);">'+(s.strategy||'--')+'</span></div>' +
      '<div style="display:flex;gap:12px;margin-top:6px;font-size:10px;color:var(--text-dim);">' +
      '<span>Entry: '+fmtPrice(s.entry)+'</span><span>SL: '+fmtPrice(s.sl)+'</span><span>TP1: '+fmtPrice(s.tp1)+'</span></div></div>';
  }).join('');
}

/* ═══════════════════════════════════════════════════════════════════ */
/* EQUITY CHART (Chart.js)                                            */
/* ═══════════════════════════════════════════════════════════════════ */
let equityChart = null;
let dailyPnlChart = null;
let analyticsInitialized = false;

function buildEquityChart(eqData) {
  const canvas = document.getElementById('equity-chart');
  if(!canvas || !eqData || eqData.length < 2) return;
  const ctx = canvas.getContext('2d');
  const labels = eqData.map(d => { try { return new Date(d.timestamp).toLocaleDateString(undefined,{month:'short',day:'numeric'}); } catch { return ''; } });
  const values = eqData.map(d => d.equity);
  const isUp = values[values.length-1] >= values[0];
  const lineColor = isUp ? '#00e6a0' : '#ff4466';
  const fillColor = isUp ? 'rgba(0,230,160,0.08)' : 'rgba(255,68,102,0.08)';
  if(equityChart) { equityChart.data.labels=labels; equityChart.data.datasets[0].data=values; equityChart.data.datasets[0].borderColor=lineColor; equityChart.data.datasets[0].backgroundColor=fillColor; equityChart.update('none'); return; }
  equityChart = new Chart(ctx, {
    type:'line', data:{ labels, datasets:[{ label:'Equity', data:values, borderColor:lineColor, backgroundColor:fillColor, borderWidth:2, fill:true, tension:0.3, pointRadius:0, pointHitRadius:10, pointHoverRadius:4, pointHoverBackgroundColor:lineColor }] },
    options:{ responsive:true, maintainAspectRatio:false, interaction:{mode:'index',intersect:false}, plugins:{ legend:{display:false}, tooltip:{ backgroundColor:'#1a1a2e', borderColor:'#2a2a50', borderWidth:1, titleFont:{family:'monospace',size:11}, bodyFont:{family:'monospace',size:11}, callbacks:{ label:function(c){ return 'Equity: \u0024'+c.parsed.y.toLocaleString(undefined,{minimumFractionDigits:2}); } } } }, scales:{ x:{ grid:{color:'rgba(26,26,53,0.5)',drawBorder:false}, ticks:{color:'#5e5e80',font:{size:10,family:'monospace'},maxTicksLimit:10} }, y:{ grid:{color:'rgba(26,26,53,0.5)',drawBorder:false}, ticks:{color:'#5e5e80',font:{size:10,family:'monospace'},callback:v=>'\u0024'+v.toLocaleString()} } } }
  });
}

/* ═══════════════════════════════════════════════════════════════════ */
/* RENDER FUNCTIONS                                                   */
/* ═══════════════════════════════════════════════════════════════════ */

function renderPositions(positions) {
  const tbody = document.getElementById('positions-body');
  if(!tbody) return;
  if(!positions || positions.length === 0) {
    tbody.innerHTML = '<tr><td colspan="11" class="empty"><div class="empty-icon">\ud83d\udd0d</div>No open positions<div class="empty-msg">The bot is scanning for opportunities...</div></td></tr>';
    document.getElementById('kpi-open-positions').textContent = '0';
    const uEl = document.getElementById('kpi-unrealized-pnl'); uEl.textContent = '\u00240.00'; uEl.className = 'metric';
    return;
  }
  let totalPnl = 0;
  const stateColors = { OPEN:'var(--blue)', TP1_HIT:'var(--green)', TRAILING:'var(--yellow)', CLOSING:'var(--orange)' };
  let html = positions.map(p => {
    const uPnl = p.unrealized_pnl || 0; totalPnl += uPnl;
    const pnlPct = p.pnl_pct || 0;
    const state = (p.state || 'OPEN').toUpperCase();
    const stColor = stateColors[state] || 'var(--muted)';
    const entry = p.entry_price || p.entry || 0;
    const sl = p.sl || 0; const tp1 = p.tp1 || 0;
    const current = p.current_price || 0;
    // Price range bar
    let rangeHtml = '--';
    if(sl && tp1 && entry && current) {
      const lo = Math.min(sl, entry); const hi = Math.max(tp1, entry);
      const range = hi - lo || 1;
      const curPct = Math.max(0, Math.min(100, ((current - lo) / range) * 100));
      const entryPct = ((entry - lo) / range) * 100;
      rangeHtml = '<div class="price-range-bar" style="width:120px;height:16px;">' +
        '<div style="position:absolute;top:0;left:0;width:'+entryPct+'%;height:100%;background:var(--red-dim);border-radius:4px 0 0 4px;"></div>' +
        '<div style="position:absolute;top:0;left:'+entryPct+'%;width:'+(100-entryPct)+'%;height:100%;background:var(--green-dim);border-radius:0 4px 4px 0;"></div>' +
        '<div style="position:absolute;top:-1px;left:'+curPct+'%;width:3px;height:18px;background:var(--cyan);border-radius:2px;box-shadow:0 0 4px var(--cyan);"></div></div>';
    }
    return '<tr><td><strong>'+(p.symbol||'--')+'</strong></td><td>'+sidePill(p.side)+'</td><td>'+fmtPrice(entry)+'</td><td>'+fmtPrice(current)+'</td>' +
      '<td>'+rangeHtml+'</td>' +
      '<td class="'+(uPnl>=0?'pnl-pos':'pnl-neg')+'">'+fmt$(uPnl)+'</td><td style="color:'+pnlColor(pnlPct)+'">'+fmtPct(pnlPct)+'</td>' +
      '<td>'+(p.leverage||1)+'x</td><td><span style="color:'+stColor+';font-size:11px;font-weight:600;">'+state+'</span></td>' +
      '<td>'+fmtDuration(p.hold_time_s)+'</td><td style="color:var(--muted);font-size:11px;">'+(p.trade_profile||'--')+'</td></tr>';
  }).join('');
  html += '<tr style="border-top:2px solid var(--border);"><td colspan="5" style="text-align:right;font-weight:700;color:var(--muted);">Total Unrealized</td><td class="'+(totalPnl>=0?'pnl-pos':'pnl-neg')+'" style="font-size:14px;">'+fmt$(totalPnl)+'</td><td colspan="5"></td></tr>';
  tbody.innerHTML = html;
  document.getElementById('kpi-open-positions').textContent = positions.length;
  const uEl = document.getElementById('kpi-unrealized-pnl'); uEl.textContent = fmt$(totalPnl); uEl.className = 'metric ' + pnlClass(totalPnl);
}

function renderHeatmap(marketData) {
  const grid = document.getElementById('heatmap-grid');
  if(!grid) return;
  if(!marketData || marketData.length === 0) { grid.innerHTML = '<div class="empty" style="grid-column:1/-1;"><div class="empty-icon">\ud83c\udf0d</div>No market data available<div class="empty-msg">Market data will populate once the bot starts scanning</div></div>'; return; }
  const regimeColors = { trend:'var(--green)', range:'var(--yellow)', panic:'var(--red)', high_volatility:'var(--orange)', low_liquidity:'var(--purple)', consolidation:'var(--blue)', news_dislocation:'var(--cyan)', unknown:'var(--muted)' };
  grid.innerHTML = marketData.map(m => {
    const regime = (m.regime||'unknown').toLowerCase();
    const borderColor = regimeColors[regime] || regimeColors.unknown;
    const bias = (m.signal_bias||'neutral').toLowerCase();
    const conf = Math.max(0,Math.min(100,m.confidence||0));
    const danger = m.danger_level || 0;
    const isOpp = bias==='bullish' && conf>60;
    const isDanger = danger > 60;
    let biasArrow, biasColor;
    if(bias==='bullish') { biasArrow='\u2191 Bullish'; biasColor='var(--green)'; }
    else if(bias==='bearish') { biasArrow='\u2193 Bearish'; biasColor='var(--red)'; }
    else { biasArrow='\u2014 Neutral'; biasColor='var(--muted)'; }
    const confColor = conf>70?'var(--green)':conf>40?'var(--yellow)':'var(--red)';
    let extra = '';
    if(isDanger) extra += '<div style="color:var(--red);font-size:10px;margin-top:4px;">\u26a0 Danger: '+danger+'%<span class="danger-dot"></span></div>';
    if(m.recent_pnl != null && !isNaN(m.recent_pnl)) extra += '<div style="color:'+pnlColor(m.recent_pnl)+';font-size:10px;margin-top:2px;">PnL: '+fmt$(m.recent_pnl)+'</div>';
    if(m.signal_count) extra += '<div style="color:var(--muted);font-size:10px;margin-top:2px;">'+m.signal_count+' signals today</div>';
    return '<div class="heatmap-cell'+(isOpp?' opportunity-glow':'')+(isDanger?' danger-glow':'')+'" style="border-left-color:'+borderColor+';" onclick="switchToChart(\''+m.symbol+'\')">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;"><span class="sym-name">'+(m.symbol||'--')+'</span></div>' +
      '<div style="margin-bottom:6px;"><span class="regime-pill" style="background:'+borderColor+'22;color:'+borderColor+';">'+regime.toUpperCase()+'</span></div>' +
      '<div style="color:'+biasColor+';font-size:12px;font-weight:600;margin-bottom:4px;">'+biasArrow+'</div>' +
      '<div style="font-size:10px;color:var(--muted);margin-bottom:2px;">Confidence: '+conf+'%</div>' +
      '<div style="background:var(--border);border-radius:3px;height:5px;overflow:hidden;"><div style="width:'+conf+'%;height:100%;background:'+confColor+';border-radius:3px;transition:width 0.4s;"></div></div>' +
      extra + '<div style="font-size:9px;color:var(--muted);margin-top:6px;opacity:0.6;">Click for chart \u2192</div></div>';
  }).join('');
}

function switchToChart(symbol) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  document.querySelector('[data-tab="charts"]').classList.add('active');
  document.getElementById('tab-charts').classList.add('active');
  if(!chartInitialized) initChartTab();
  selectChartSymbol(symbol);
}

function renderRejections(rejections) {
  const tbody = document.getElementById('rejections-body');
  const tbodyMini = document.getElementById('rejections-body-mini');
  if(!rejections || rejections.length === 0) {
    if(tbody) tbody.innerHTML = '<tr><td colspan="8" class="empty">No rejected signals</td></tr>';
    if(tbodyMini) tbodyMini.innerHTML = '<tr><td colspan="4" class="empty">No rejections</td></tr>';
    return;
  }
  const hardGates = ['circuit_breaker','liquidation','max_positions'];
  const softGates = ['fee_drag','ev_floor','rr_floor','lev_ev_floor'];
  // Full table
  if(tbody) {
    tbody.innerHTML = rejections.slice(0,50).map(r => {
      const gate = (r.gate||'unknown').toLowerCase();
      let gateClass = 'gate-info';
      if(hardGates.includes(gate)) gateClass = 'gate-hard';
      else if(softGates.includes(gate)) gateClass = 'gate-soft';
      const cfPnl = r.counterfactual_pnl;
      const cfDisplay = (cfPnl!=null&&!isNaN(cfPnl)) ? '<span style="color:'+pnlColor(cfPnl)+';font-weight:600;">'+fmt$(cfPnl)+'</span>' : '<span style="color:var(--muted);">--</span>';
      return '<tr><td>'+fmtDateTime(r.timestamp)+'</td><td><strong>'+(r.symbol||'--')+'</strong></td><td>'+sidePill(r.side)+'</td><td>'+(r.confidence!=null?r.confidence.toFixed(0)+'%':'--')+'</td><td style="color:var(--muted)">'+(r.strategy||'--')+'</td><td><span class="gate-pill '+gateClass+'">'+gate.toUpperCase()+'</span></td><td style="color:var(--muted);font-size:11px;max-width:160px;overflow:hidden;text-overflow:ellipsis;" title="'+((r.reason||'').replace(/"/g,'&quot;'))+'">'+(r.reason||'--')+'</td><td>'+cfDisplay+'</td></tr>';
    }).join('');
  }
  // Mini table on overview
  if(tbodyMini) {
    tbodyMini.innerHTML = rejections.slice(0,10).map(r => {
      const gate = (r.gate||'unknown').toLowerCase();
      let gateClass = 'gate-info';
      if(hardGates.includes(gate)) gateClass = 'gate-hard';
      else if(softGates.includes(gate)) gateClass = 'gate-soft';
      return '<tr><td><strong>'+(r.symbol||'--')+'</strong></td><td>'+sidePill(r.side)+'</td><td><span class="gate-pill '+gateClass+'">'+gate.toUpperCase()+'</span></td><td style="color:var(--muted);font-size:11px;max-width:140px;overflow:hidden;text-overflow:ellipsis;">'+(r.reason||'--')+'</td></tr>';
    }).join('');
  }
}

function renderPipeline(pipelineData, targetId) {
  const el = document.getElementById(targetId);
  if(!el) return;
  if(!pipelineData || !pipelineData.total_signals) {
    el.innerHTML = '<div class="empty"><div class="empty-icon">\u26a1</div>No pipeline data yet<div class="empty-msg">Signal pipeline stats will appear once the bot generates signals</div></div>';
    return;
  }
  const total = pipelineData.total_signals || 0;
  const passed = pipelineData.passed || 0;
  const byGate = pipelineData.by_gate || {};
  const steps = [
    { label: 'Signals Generated', count: total, color: 'var(--blue)' },
  ];
  Object.entries(byGate).sort((a,b) => b[1]-a[1]).forEach(([gate, count]) => {
    steps.push({ label: gate.replace(/_/g,' '), count: count, color: 'var(--yellow)' });
  });
  steps.push({ label: 'Executed', count: passed, color: 'var(--green)' });

  const maxCount = Math.max(...steps.map(s => s.count), 1);
  el.innerHTML = steps.map(s => {
    const pct = Math.max(5, (s.count / maxCount) * 100);
    return '<div class="funnel-step"><div class="funnel-label">'+s.label+'</div><div class="funnel-bar-track"><div class="funnel-bar-fill" style="width:'+pct+'%;background:'+s.color+';color:#fff;">'+s.count+'</div></div></div>';
  }).join('');
}

function renderCopyTrade(data) {
  const container = document.getElementById('copytrade-content');
  if(!container) return;
  if(!data || !data.active) {
    container.innerHTML = '<div class="empty"><div class="empty-icon">\ud83e\udd16</div>LLM Intelligence Offline<div class="empty-msg">Enable multi-agent system (LLM_MULTI_AGENT=true) to activate AI analysis</div></div>';
    return;
  }
  let html = '';
  if(data.recommendation) {
    html += '<div style="background:var(--bg2);border-radius:8px;padding:14px;margin-bottom:12px;border-left:4px solid var(--purple);"><div style="color:var(--purple);font-size:10px;font-weight:700;margin-bottom:6px;">AI RECOMMENDATION</div><div style="color:var(--text);font-size:12px;">'+data.recommendation+'</div></div>';
  }
  if(data.insights && data.insights.length > 0) {
    const agentColors = { regime:'var(--blue)', trade:'var(--green)', risk:'var(--orange)', critic:'var(--red)', learning:'var(--purple)', exit:'var(--yellow)', scout:'var(--cyan)' };
    data.insights.forEach(ins => {
      const agent = (ins.agent||'unknown').toLowerCase();
      const color = agentColors[agent] || 'var(--muted)';
      html += '<div style="background:var(--bg2);border-radius:8px;padding:12px;margin-bottom:6px;border-left:3px solid '+color+';"><div style="display:flex;justify-content:space-between;"><span style="color:'+color+';font-size:10px;font-weight:700;text-transform:uppercase;">'+(ins.agent||'Agent')+'</span><span style="color:var(--muted);font-size:10px;">'+fmtTime(ins.timestamp)+'</span></div><div style="color:var(--text-dim);font-size:11px;margin-top:4px;">'+ins.summary+'</div></div>';
    });
  }
  container.innerHTML = html || '<div style="color:var(--muted);text-align:center;padding:15px;">Awaiting agent insights...</div>';
}

function renderStrategyBars(byStrategy) {
  const container = document.getElementById('strategy-bars');
  if(!byStrategy || Object.keys(byStrategy).length === 0) { container.innerHTML = '<div class="empty">No strategy data yet</div>'; return; }
  const entries = Object.entries(byStrategy).sort((a,b) => b[1].pnl - a[1].pnl);
  const maxAbs = Math.max(...entries.map(([_,s]) => Math.abs(s.pnl)), 1);
  container.innerHTML = entries.map(([name,s]) => {
    const wr = s.trades > 0 ? (s.wins/s.trades) : 0;
    const barPct = Math.min((Math.abs(s.pnl)/maxAbs)*100, 100);
    const barColor = s.pnl >= 0 ? 'var(--green)' : 'var(--red)';
    return '<div class="strat-row"><div class="strat-label">'+name+'</div><div class="strat-bar-track"><div class="strat-bar-fill" style="width:'+barPct+'%;background:'+barColor+';">'+(barPct>25?(wr*100).toFixed(0)+'% WR':'')+'</div></div><div class="strat-pnl" style="color:'+pnlColor(s.pnl)+'">'+fmt$(s.pnl)+'</div></div>';
  }).join('');
}

function renderWeights(weightsData) {
  const el = document.getElementById('strategy-weights');
  if(!el) return;
  if(!weightsData || Object.keys(weightsData).length === 0) { el.innerHTML = '<div class="empty">No weight data available</div>'; return; }
  const maxW = Math.max(...Object.values(weightsData), 1);
  el.innerHTML = Object.entries(weightsData).sort((a,b) => b[1]-a[1]).map(([name, w]) => {
    const pct = (w / maxW) * 100;
    return '<div class="strat-row"><div class="strat-label">'+name+'</div><div class="strat-bar-track"><div class="strat-bar-fill" style="width:'+pct+'%;background:var(--cyan);">'+w.toFixed(2)+'</div></div></div>';
  }).join('');
}

function renderCircuitBreakers(riskData) {
  const el = document.getElementById('cb-status');
  if(!el) return;
  if(!riskData) { el.innerHTML = '<div class="empty">Risk data unavailable</div>'; return; }
  const tripped = riskData.cb_tripped;
  let html = '';
  if(tripped) {
    html += '<div style="background:var(--red-dim);border:1px solid rgba(255,68,102,0.3);border-radius:8px;padding:12px;margin-bottom:12px;text-align:center;"><span style="color:var(--red);font-weight:800;font-size:14px;">\u26a0 CIRCUIT BREAKER TRIPPED</span></div>';
  }
  const gauges = [
    { label: 'Daily PnL', current: Math.abs(riskData.daily_pnl||0), max: Math.abs(riskData.daily_limit||100), unit: '\u0024', color: (riskData.daily_pnl||0) < 0 ? 'var(--red)' : 'var(--green)' },
    { label: 'Consecutive Losses', current: riskData.consecutive_losses||0, max: riskData.max_consecutive||5, unit: '', color: (riskData.consecutive_losses||0) >= (riskData.max_consecutive||5)*0.7 ? 'var(--yellow)' : 'var(--green)' },
    { label: 'Drawdown', current: Math.abs(riskData.drawdown_pct||0), max: 10, unit: '%', color: Math.abs(riskData.drawdown_pct||0) > 5 ? 'var(--red)' : 'var(--green)' },
  ];
  gauges.forEach(g => {
    const pct = Math.min((g.current / g.max) * 100, 100);
    html += '<div class="cb-row"><div class="cb-label">'+g.label+'</div><div class="cb-bar"><div class="cb-fill" style="width:'+pct+'%;background:'+g.color+';"></div></div><div class="cb-value" style="color:'+g.color+';">'+g.current.toFixed(g.unit==='\u0024'?2:0)+g.unit+' / '+g.max+g.unit+'</div></div>';
  });
  el.innerHTML = html;
}

function renderActiveSignals(signalData) {
  const el = document.getElementById('active-signals-list');
  if(!el) return;
  if(!signalData || signalData.length === 0) {
    el.innerHTML = '<div class="empty"><div class="empty-icon">\ud83d\udce1</div>No active signals right now<div class="empty-msg">The bot evaluates signals each scan cycle (~30s)</div></div>';
    return;
  }
  el.innerHTML = signalData.map(s => {
    const isLong = (s.side||'').toUpperCase() === 'BUY';
    const conf = s.confidence || 0;
    const confColor = conf>70?'var(--green)':conf>40?'var(--yellow)':'var(--red)';
    const strategies = s.strategies_agreeing || 0;
    const totalStrats = 4;
    let confluenceBars = '';
    for(let i=0; i<totalStrats; i++) {
      confluenceBars += '<div class="confluence-bar '+(i<strategies?'filled':'')+'"></div>';
    }
    return '<div class="signal-card">' +
      '<div class="signal-header"><div style="display:flex;align-items:center;gap:10px;"><span class="signal-sym">'+(s.symbol||'--')+'</span>'+sidePill(s.side)+'</div>' +
      '<div class="signal-conf" style="color:'+confColor+';">'+conf.toFixed(0)+'%</div></div>' +
      '<div style="font-size:11px;color:var(--text-dim);margin-bottom:8px;">'+(s.signal_context||s.reason||'Signal generated by ensemble')+'</div>' +
      '<div style="display:flex;gap:16px;font-size:11px;margin-bottom:8px;">' +
      '<span>Entry: <strong>'+fmtPrice(s.entry)+'</strong></span>' +
      '<span>SL: <strong style="color:var(--red);">'+fmtPrice(s.sl)+'</strong></span>' +
      '<span>TP1: <strong style="color:var(--green);">'+fmtPrice(s.tp1)+'</strong></span>' +
      '<span>TP2: <strong style="color:var(--green);">'+fmtPrice(s.tp2)+'</strong></span></div>' +
      '<div style="display:flex;align-items:center;gap:8px;font-size:10px;color:var(--muted);">' +
      '<span>Confluence: '+strategies+'/'+totalStrats+'</span><div class="confluence-meter">'+confluenceBars+'</div>' +
      '<span style="margin-left:auto;">'+((s.strategy||''))+'</span></div></div>';
  }).join('');
}

/* ═══════════════════════════════════════════════════════════════════ */
/* DATA LOADING                                                       */
/* ═══════════════════════════════════════════════════════════════════ */

async function loadAll() {
  try {
    const [dataRes, healthRes, marketRes, rejectionsRes, pipelineRes] = await Promise.allSettled([
      fetch('/api/data'), fetch('/api/health'), fetch('/api/market'), fetch('/api/rejections'), fetch('/api/pipeline')
    ]);
    let data=null, healthInfo=null, market=null, rejections=null, pipeline=null;
    if(dataRes.status==='fulfilled' && dataRes.value.ok) try { data = await dataRes.value.json(); } catch {}
    if(healthRes.status==='fulfilled' && healthRes.value.ok) try { healthInfo = await healthRes.value.json(); } catch {}
    if(marketRes.status==='fulfilled' && marketRes.value.ok) try { market = await marketRes.value.json(); } catch {}
    if(rejectionsRes.status==='fulfilled' && rejectionsRes.value.ok) try { rejections = await rejectionsRes.value.json(); } catch {}
    if(pipelineRes.status==='fulfilled' && pipelineRes.value.ok) try { pipeline = await pipelineRes.value.json(); } catch {}

    if(data) {
      const ds = data.daily_summary || {};
      const rt = data.recent_trades || [];
      const eq = data.equity_curve || [];
      const sp = data.signal_performance || {};
      const positions = data.positions || [];

      // Top bar equity ticker
      const lastEq = eq.length > 0 ? eq[eq.length-1] : {};
      const equity = lastEq.equity || 0;
      document.getElementById('kpi-equity').textContent = '\u0024'+equity.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
      document.getElementById('top-equity').textContent = '\u0024'+equity.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
      document.getElementById('top-equity').style.color = pnlColor(equity > 0 ? 1 : 0);
      if(eq.length>=2) { const prevEq=eq[0].equity||equity; const change=equity-prevEq; const changePct=prevEq>0?((change/prevEq)*100).toFixed(2):'0.00'; const el=document.getElementById('kpi-equity-change'); el.textContent=fmt$(change)+' ('+changePct+'% 30d)'; el.style.color=pnlColor(change); }

      const pnl = ds.net_pnl || 0;
      const pnlEl = document.getElementById('kpi-pnl'); pnlEl.textContent = fmt$(pnl); pnlEl.className = 'metric ' + pnlClass(pnl);
      document.getElementById('kpi-pnl-detail').textContent = (ds.total_trades||0)+' trades | \u0024'+(ds.total_fees||0).toFixed(2)+' fees';
      const wr = (ds.win_rate||0)*100; const wrEl = document.getElementById('kpi-winrate'); wrEl.textContent = wr.toFixed(1)+'%'; wrEl.className = 'metric '+(wr>=50?'green':(wr>0?'red':''));
      document.getElementById('wr-bar').style.width = wr+'%'; document.getElementById('wr-bar').style.background = wr>=50?'var(--green)':'var(--red)';
      document.getElementById('kpi-wl').textContent = (ds.wins||0)+'W / '+(ds.losses||0)+'L';

      renderPositions(positions);

      // Signal Performance
      const byStrat = sp.by_strategy || {}; const ssBody = document.getElementById('signal-strat-body');
      if(Object.keys(byStrat).length > 0) { ssBody.innerHTML = Object.entries(byStrat).sort((a,b) => b[1].pnl-a[1].pnl).map(([name,s]) => '<tr><td><strong>'+name+'</strong></td><td>'+s.trades+'</td><td>'+(s.wins||0)+'</td><td><span class="pill '+(s.win_rate>=0.5?'pill-win':'pill-loss')+'">'+(s.win_rate*100).toFixed(1)+'%</span></td><td style="color:'+pnlColor(s.pnl)+';font-weight:600">'+fmt$(s.pnl)+'</td><td>'+(s.avg_score||0).toFixed(1)+'</td></tr>').join(''); }
      const bySym = sp.by_symbol || {}; const symBody = document.getElementById('signal-sym-body');
      if(Object.keys(bySym).length > 0) { symBody.innerHTML = Object.entries(bySym).sort((a,b) => b[1].pnl-a[1].pnl).map(([sym,s]) => '<tr><td><strong>'+sym+'</strong></td><td>'+s.trades+'</td><td>'+(s.wins||0)+'</td><td><span class="pill '+(s.win_rate>=0.5?'pill-win':'pill-loss')+'">'+(s.win_rate*100).toFixed(1)+'%</span></td><td style="color:'+pnlColor(s.pnl)+';font-weight:600">'+fmt$(s.pnl)+'</td></tr>').join(''); }

      // Recent Trades
      const tBody = document.getElementById('trades-body');
      if(rt.length > 0) {
        tBody.innerHTML = rt.map(t => '<tr><td>'+fmtDateTime(t.timestamp)+'</td><td><strong>'+(t.symbol||'--')+'</strong></td><td>'+sidePill(t.side)+'</td><td><span class="pill pill-action">'+(t.action||'--')+'</span></td><td>'+fmtPrice(t.price)+'</td><td style="color:'+pnlColor(t.pnl||0)+';font-weight:600">'+fmt$(t.pnl||0)+'</td><td style="color:var(--muted)">'+(t.strategy||'')+'</td></tr>').join('');
        // Trade stats
        const wins = rt.filter(t => (t.pnl||0) > 0);
        const losses = rt.filter(t => (t.pnl||0) < 0);
        document.getElementById('ts-total').textContent = rt.length;
        const avgWin = wins.length > 0 ? wins.reduce((a,t) => a+(t.pnl||0), 0)/wins.length : 0;
        const avgLoss = losses.length > 0 ? losses.reduce((a,t) => a+(t.pnl||0), 0)/losses.length : 0;
        document.getElementById('ts-avg-win').textContent = fmt$(avgWin);
        document.getElementById('ts-avg-loss').textContent = fmt$(avgLoss);
        const grossWin = wins.reduce((a,t) => a+(t.pnl||0), 0);
        const grossLoss = Math.abs(losses.reduce((a,t) => a+(t.pnl||0), 0));
        document.getElementById('ts-pf').textContent = grossLoss > 0 ? (grossWin/grossLoss).toFixed(2) : '--';
      }

      renderStrategyBars(ds.by_strategy || {});
      if(data.copytrade) renderCopyTrade(data.copytrade);
    }

    if(healthInfo) {
      const uptime = healthInfo.uptime_seconds || 0;
      document.getElementById('health-uptime').textContent = fmtDuration(uptime);
      document.getElementById('health-started').textContent = 'Started: '+(healthInfo.started_at||'--');
      document.getElementById('health-heartbeat').textContent = healthInfo.last_heartbeat || '--';
      if(healthInfo.heartbeat_age_s != null) { const age=healthInfo.heartbeat_age_s; const ageEl=document.getElementById('health-heartbeat-ago'); ageEl.textContent=fmtDuration(age)+' ago'; ageEl.style.color=age>300?'var(--red)':(age>120?'var(--yellow)':'var(--muted)'); }
      const errCount = healthInfo.error_count||0; const warnCount = healthInfo.warning_count||0;
      const errEl = document.getElementById('health-errors'); errEl.textContent = errCount; errEl.className = 'metric '+(errCount>0?'red':'green');
      document.getElementById('health-warnings').textContent = warnCount + ' warnings';
      document.getElementById('uptime-display').textContent = 'Up: '+fmtDuration(uptime);
      const dot = document.getElementById('health-dot'); const label = document.getElementById('health-label');
      if(errCount>0) { dot.className='dot dot-red'; label.textContent=errCount+' error(s)'; }
      else if(warnCount>0) { dot.className='dot dot-yellow'; label.textContent='Warnings'; }
      else { dot.className='dot dot-green'; label.textContent='Healthy'; }
    }

    renderHeatmap(market);
    renderRejections(rejections);
    renderPipeline(pipeline, 'pipeline-funnel');
    renderPipeline(pipeline, 'pipeline-funnel-full');
    document.getElementById('last-refresh').textContent = new Date().toLocaleTimeString();
  } catch(err) {
    console.error('Dashboard load error:', err);
    document.getElementById('health-dot').className = 'dot dot-red';
    document.getElementById('health-label').textContent = 'Connection error';
  }
}

async function refreshPositionsOnly() {
  try { const res = await fetch('/api/positions'); if(res.ok) { const positions = await res.json(); renderPositions(positions); } } catch {}
}

async function loadAnalytics() {
  analyticsInitialized = true;
  // Load weights and risk data
  const [weightsRes, riskRes, perfRes] = await Promise.allSettled([
    fetch('/api/weights'), fetch('/api/risk'), fetch('/api/performance')
  ]);
  if(weightsRes.status==='fulfilled' && weightsRes.value.ok) { try { renderWeights(await weightsRes.value.json()); } catch {} }
  if(riskRes.status==='fulfilled' && riskRes.value.ok) { try { renderCircuitBreakers(await riskRes.value.json()); } catch {} }
  // Equity chart
  try { const eqRes = await fetch('/api/equity'); if(eqRes.ok) { const eq = await eqRes.json(); if(eq.length >= 2) buildEquityChart(eq); } } catch {}
  // Daily PnL chart
  if(perfRes.status==='fulfilled' && perfRes.value.ok) {
    try {
      const perf = await perfRes.value.json();
      if(Array.isArray(perf) && perf.length > 0) {
        const canvas = document.getElementById('daily-pnl-chart');
        if(canvas) {
          const ctx = canvas.getContext('2d');
          const labels = perf.map(d => d.date || '');
          const pnls = perf.map(d => d.pnl || 0);
          const colors = pnls.map(v => v >= 0 ? 'rgba(0,230,160,0.8)' : 'rgba(255,68,102,0.8)');
          dailyPnlChart = new Chart(ctx, {
            type:'bar', data:{ labels, datasets:[{ data:pnls, backgroundColor:colors, borderRadius:4 }] },
            options:{ responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}}, scales:{x:{grid:{display:false},ticks:{color:'#5e5e80',font:{size:10,family:'monospace'}}},y:{grid:{color:'rgba(26,26,53,0.5)'},ticks:{color:'#5e5e80',callback:v=>'\u0024'+v}}} }
          });
        }
      }
    } catch {}
  }
}

async function loadSystemTab() {
  const [riskRes, gatesRes] = await Promise.allSettled([
    fetch('/api/risk'), fetch('/api/gates')
  ]);
  if(riskRes.status==='fulfilled' && riskRes.value.ok) { try { renderCircuitBreakers(await riskRes.value.json()); } catch {} }
  if(gatesRes.status==='fulfilled' && gatesRes.value.ok) {
    try {
      const gates = await gatesRes.value.json();
      const el = document.getElementById('gates-status');
      if(el && gates) {
        el.innerHTML = Object.entries(gates).map(([name, g]) => {
          const passed = g.passed || g.status === 'pass';
          const val = g.current != null ? g.current : '--';
          const thresh = g.threshold != null ? g.threshold : '--';
          return '<div style="display:flex;align-items:center;gap:10px;padding:8px;background:var(--bg2);border-radius:6px;margin-bottom:6px;border-left:3px solid '+(passed?'var(--green)':'var(--red)')+';"><div style="flex:1;"><div style="font-weight:600;font-size:12px;">'+name.replace(/_/g,' ')+'</div><div style="font-size:10px;color:var(--muted);">Current: '+val+' / Threshold: '+thresh+'</div></div><span class="pill '+(passed?'pill-win':'pill-loss')+'">'+(passed?'PASS':'FAIL')+'</span></div>';
        }).join('');
      }
    } catch {}
  }
}

/* ═══════════════════════════════════════════════════════════════════ */
/* INITIALIZATION                                                     */
/* ═══════════════════════════════════════════════════════════════════ */
loadAll();
setInterval(loadAll, 30000);
setInterval(refreshPositionsOnly, 10000);

// Load system tab data when switching to it
document.querySelector('[data-tab="system"]').addEventListener('click', () => setTimeout(loadSystemTab, 100));
</script>
</body>
</html>
"""


# ═══════════════════════════════════════════════════════════════════════════
# HTTP Handler
# ═══════════════════════════════════════════════════════════════════════════

class DashboardHandler(BaseHTTPRequestHandler):
    """Serves the dashboard HTML and JSON API endpoints."""

    bot_instance = None

    def log_message(self, format, *args):  # noqa: A002
        logger.debug("HTTP %s", format % args)

    def do_GET(self):  # noqa: N802
        path = self.path.split("?")[0]
        routes = {
            "/":                 self._serve_dashboard,
            "/dashboard":        self._serve_dashboard,
            "/api/data":         self._serve_api_data,
            "/api/equity":       self._serve_equity_data,
            "/api/positions":    self._serve_positions,
            "/api/health":       self._serve_health,
            "/api/market":       self._serve_market,
            "/api/rejections":   self._serve_rejections,
            "/api/copytrade":    self._serve_copytrade,
            "/api/ohlcv":        self._serve_ohlcv,
            "/api/zones":        self._serve_zones,
            "/api/pipeline":     self._serve_pipeline,
            "/api/risk":         self._serve_risk,
            "/api/weights":      self._serve_weights,
            "/api/performance":  self._serve_performance,
            "/api/signals/active": self._serve_active_signals,
            "/api/gates":        self._serve_gates,
        }
        handler = routes.get(path)
        if handler:
            handler()
        else:
            self.send_error(404, "Not Found")

    def _serve_dashboard(self):
        body = DASHBOARD_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, obj: Any, status: int = 200):
        body = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _parse_query_params(self) -> Dict[str, str]:
        """Parse URL query parameters from self.path into a flat dict."""
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        return {k: v[-1] for k, v in qs.items()}

    # ── /api/data ──────────────────────────────────────────────────────
    def _serve_api_data(self):
        try:
            from data.db import get_dashboard_data
            data = get_dashboard_data()
            data["positions"] = self._get_positions_list()
            data["copytrade"] = self._get_copytrade_data()
            self._send_json(data)
        except Exception as exc:
            logger.exception("Error serving /api/data")
            self._send_json({"error": str(exc)}, status=500)

    # ── /api/equity ────────────────────────────────────────────────────
    def _serve_equity_data(self):
        try:
            from data.db import get_equity_curve
            self._send_json(get_equity_curve(30))
        except Exception as exc:
            logger.exception("Error serving /api/equity")
            self._send_json({"error": str(exc)}, status=500)

    # ── /api/positions ─────────────────────────────────────────────────
    def _serve_positions(self):
        try:
            self._send_json(self._get_positions_list())
        except Exception as exc:
            logger.exception("Error serving /api/positions")
            self._send_json({"error": str(exc)}, status=500)

    # ── /api/health ────────────────────────────────────────────────────
    def _serve_health(self):
        try:
            from data.db import get_health_events
            events = get_health_events(24)
            error_count = sum(1 for e in events if e.get("severity") in ("ALERT", "ERROR"))
            warning_count = sum(1 for e in events if e.get("severity") == "WARNING")

            heartbeats = [
                e for e in events
                if e.get("event_type", "").upper() in ("HEARTBEAT", "LOOP_TICK", "CYCLE")
            ]
            last_hb = heartbeats[0]["timestamp"] if heartbeats else None
            hb_age = None
            if last_hb:
                try:
                    hb_dt = datetime.fromisoformat(last_hb.replace("Z", "+00:00"))
                    hb_age = (datetime.now(timezone.utc) - hb_dt).total_seconds()
                except Exception:
                    pass

            started_at = datetime.fromtimestamp(_START_TIME, tz=timezone.utc).isoformat()
            uptime = time.time() - _START_TIME

            self._send_json({
                "uptime_seconds": uptime,
                "started_at": started_at,
                "last_heartbeat": last_hb or "--",
                "heartbeat_age_s": hb_age,
                "error_count": error_count,
                "warning_count": warning_count,
                "total_events_24h": len(events),
            })
        except Exception as exc:
            logger.exception("Error serving /api/health")
            self._send_json({"error": str(exc)}, status=500)

    # ── /api/market (heatmap data) ─────────────────────────────────────
    def _serve_market(self):
        try:
            self._send_json(self._get_market_data())
        except Exception as exc:
            logger.exception("Error serving /api/market")
            self._send_json({"error": str(exc)}, status=500)

    # ── /api/rejections (missed signals) ───────────────────────────────
    def _serve_rejections(self):
        try:
            self._send_json(self._get_rejections_data())
        except Exception as exc:
            logger.exception("Error serving /api/rejections")
            self._send_json({"error": str(exc)}, status=500)

    # ── /api/copytrade (LLM intelligence) ──────────────────────────────
    def _serve_copytrade(self):
        try:
            self._send_json(self._get_copytrade_data())
        except Exception as exc:
            logger.exception("Error serving /api/copytrade")
            self._send_json({"error": str(exc)}, status=500)

    # ── /api/ohlcv — OHLCV candle data for charts ─────────────────────
    def _serve_ohlcv(self):
        try:
            params = self._parse_query_params()
            symbol = params.get("symbol", "BTC").upper()
            timeframe = params.get("timeframe", "1h")

            from trading_config import DEFAULT_SYMBOLS
            sym_cfg = DEFAULT_SYMBOLS.get(symbol)
            if sym_cfg is None:
                self._send_json(
                    {"error": f"Unknown symbol: {symbol}",
                     "available": list(DEFAULT_SYMBOLS.keys())},
                    status=400,
                )
                return

            from data.fetcher import DataFetcher
            fetcher = DataFetcher(cache_ttl=30)
            df = fetcher.fetch_ohlcv(symbol, sym_cfg.coingecko_id, timeframe)

            if df is None or df.empty:
                self._send_json([])
                return

            candles = []
            for _, row in df.iterrows():
                ts = row.get("time")
                if hasattr(ts, "isoformat"):
                    ts = ts.isoformat()
                candles.append({
                    "time": ts,
                    "open": round(float(row["open"]), 6),
                    "high": round(float(row["high"]), 6),
                    "low": round(float(row["low"]), 6),
                    "close": round(float(row["close"]), 6),
                    "volume": round(float(row.get("volume", 0)), 2),
                })

            self._send_json(candles)
        except Exception as exc:
            logger.exception("Error serving /api/ohlcv")
            self._send_json({"error": str(exc)}, status=500)

    # ── /api/zones — Monte Carlo S/R zones + signal levels ─────────────
    def _serve_zones(self):
        try:
            params = self._parse_query_params()
            symbol = params.get("symbol", "BTC").upper()

            from data.db import get_signals_today

            signals_raw = get_signals_today()
            sym_signals = [
                s for s in (signals_raw or [])
                if s.get("symbol", "").upper() == symbol
            ]

            zones = {}
            regime = "unknown"
            for sig in reversed(sym_signals):
                meta = sig.get("metadata")
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except Exception:
                        meta = {}
                if not isinstance(meta, dict):
                    continue
                zone_data = meta.get("zones", meta)
                if zone_data.get("deep_buy") is not None:
                    zones = {
                        "deep_buy": zone_data.get("deep_buy"),
                        "regular_buy": zone_data.get("regular_buy"),
                        "regular_sell": zone_data.get("regular_sell"),
                        "safe_sell": zone_data.get("safe_sell"),
                        "sma20": zone_data.get("sma20"),
                    }
                    break
                r = meta.get("regime") or meta.get("market_regime")
                if r:
                    regime = r

            if regime == "unknown":
                for sig in reversed(sym_signals):
                    meta = sig.get("metadata")
                    if isinstance(meta, str):
                        try:
                            meta = json.loads(meta)
                        except Exception:
                            meta = {}
                    if isinstance(meta, dict):
                        r = meta.get("regime") or meta.get("market_regime")
                        if r:
                            regime = r
                            break

            signal_overlays = []
            for sig in sym_signals[-20:]:
                signal_overlays.append({
                    "side": sig.get("side"),
                    "entry": sig.get("entry"),
                    "sl": sig.get("sl"),
                    "tp1": sig.get("tp1"),
                    "tp2": sig.get("tp2"),
                    "confidence": sig.get("confidence"),
                    "strategy": sig.get("strategy"),
                    "timestamp": sig.get("timestamp"),
                })

            self._send_json({
                "symbol": symbol,
                "zones": zones,
                "signals": signal_overlays,
                "regime": regime,
            })
        except Exception as exc:
            logger.exception("Error serving /api/zones")
            self._send_json({"error": str(exc)}, status=500)

    # ── /api/pipeline — Signal pipeline funnel stats ───────────────────
    def _serve_pipeline(self):
        try:
            from data.db import get_signals_today, get_rejection_summary

            signals = get_signals_today() or []
            total_signals = len(signals)
            traded_count = sum(1 for s in signals if s.get("traded"))

            try:
                rejection_summary = get_rejection_summary(hours=24)
            except Exception:
                rejection_summary = {}
            by_gate = {}
            total_rejected = 0
            for gate, info in (rejection_summary or {}).items():
                count = info.get("count", 0) if isinstance(info, dict) else int(info)
                by_gate[gate] = count
                total_rejected += count

            self._send_json({
                "total_signals": total_signals,
                "total_rejected": total_rejected,
                "by_gate": by_gate,
                "passed": traded_count,
                "executed": traded_count,
            })
        except Exception as exc:
            logger.exception("Error serving /api/pipeline")
            self._send_json({"error": str(exc)}, status=500)

    # ── /api/risk — Circuit breaker & risk state ───────────────────────
    def _serve_risk(self):
        try:
            bot = DashboardHandler.bot_instance
            risk_state = None

            if bot is not None:
                rm = getattr(bot, "risk_manager", None)
                if rm is None:
                    engine = getattr(bot, "engine", None) or getattr(bot, "trading_engine", None)
                    if engine:
                        rm = getattr(engine, "risk_manager", None)
                if rm is not None:
                    cb = getattr(rm, "circuit_breaker", None)
                    try:
                        cb_status = cb.get_status() if cb and hasattr(cb, "get_status") else {}
                    except Exception:
                        cb_status = {}
                    equity = getattr(rm, "equity", 0)
                    peak = cb_status.get("peak_equity", 0)
                    risk_state = {
                        "daily_pnl": cb_status.get("daily_pnl", 0),
                        "daily_limit": abs(equity * getattr(cb, "daily_loss_limit_pct", 0.05)) if cb else 50,
                        "consecutive_losses": cb_status.get("consecutive_losses", 0),
                        "max_consecutive": getattr(cb, "max_consecutive_losses", 5) if cb else 5,
                        "cb_tripped": cb_status.get("tripped", False),
                        "drawdown_pct": round(((peak - equity) / peak) * 100, 2) if peak > 0 else 0,
                        "source": "live",
                    }

            if risk_state is None:
                risk_state = {
                    "daily_pnl": 0, "daily_limit": 50,
                    "consecutive_losses": 0, "max_consecutive": 5,
                    "cb_tripped": False, "drawdown_pct": 0,
                    "source": "unavailable",
                }

            self._send_json(risk_state)
        except Exception as exc:
            logger.exception("Error serving /api/risk")
            self._send_json({"error": str(exc)}, status=500)

    # ── /api/weights — Current strategy weights ────────────────────────
    def _serve_weights(self):
        try:
            from data.strategy_weights import StrategyWeightManager
            mgr = StrategyWeightManager()
            weights = mgr.get_all_weights()
            self._send_json(weights)
        except Exception as exc:
            logger.exception("Error serving /api/weights")
            self._send_json({"error": str(exc)}, status=500)

    # ── /api/performance — Daily performance history ───────────────────
    def _serve_performance(self):
        try:
            from data.db import get_performance_history
            params = self._parse_query_params()
            days = int(params.get("days", "30"))
            days = max(1, min(days, 365))
            history = get_performance_history(days)
            result = []
            for row in (history or []):
                result.append({
                    "date": row.get("date"),
                    "trades": row.get("trades", 0),
                    "wins": row.get("wins", 0),
                    "pnl": row.get("net_pnl", row.get("pnl", 0)),
                    "fees": row.get("total_fees", 0),
                })
            self._send_json(result)
        except Exception as exc:
            logger.exception("Error serving /api/performance")
            self._send_json({"error": str(exc)}, status=500)

    # ── /api/signals/active — Current active signals ───────────────────
    def _serve_active_signals(self):
        try:
            from data.db import get_signals_today
            signals = get_signals_today() or []
            by_symbol: Dict[str, list] = {}
            for sig in signals:
                sym = sig.get("symbol", "???")
                by_symbol.setdefault(sym, []).append(sig)

            result = []
            for sig in signals:
                sym = sig.get("symbol", "???")
                sym_signals = by_symbol.get(sym, [])
                side = (sig.get("side") or "").upper()
                agree_count = sum(
                    1 for s in sym_signals
                    if (s.get("side") or "").upper() == side
                    and s.get("strategy") != sig.get("strategy")
                )
                meta = sig.get("metadata")
                if isinstance(meta, str):
                    try: meta = json.loads(meta)
                    except Exception: meta = {}
                regime = meta.get("regime", "unknown") if isinstance(meta, dict) else "unknown"

                result.append({
                    "timestamp": sig.get("timestamp"),
                    "symbol": sym, "strategy": sig.get("strategy"),
                    "side": sig.get("side"), "confidence": sig.get("confidence"),
                    "entry": sig.get("entry"), "sl": sig.get("sl"),
                    "tp1": sig.get("tp1"), "tp2": sig.get("tp2"),
                    "regime": regime,
                    "strategies_agreeing": agree_count + 1,
                    "signal_context": meta.get("signal_context", "") if isinstance(meta, dict) else "",
                })
            self._send_json(result)
        except Exception as exc:
            logger.exception("Error serving /api/signals/active")
            self._send_json({"error": str(exc)}, status=500)

    # ── /api/gates — Go-live gate status ───────────────────────────────
    def _serve_gates(self):
        try:
            # Try to get gate status from bot instance
            bot = DashboardHandler.bot_instance
            gates = {}
            if bot is not None:
                gate_eval = getattr(bot, "gate_evaluator", None) or getattr(bot, "go_live_gates", None)
                if gate_eval and hasattr(gate_eval, "evaluate"):
                    try:
                        gates = gate_eval.evaluate()
                    except Exception:
                        pass
            if not gates:
                gates = {
                    "walk_forward": {"passed": False, "current": "N/A", "threshold": "N/A"},
                    "net_pnl": {"passed": False, "current": "N/A", "threshold": "> $0"},
                    "max_drawdown": {"passed": False, "current": "N/A", "threshold": "< 15%"},
                    "factor_ics": {"passed": False, "current": "N/A", "threshold": "> 0.02"},
                    "sharpe_ratio": {"passed": False, "current": "N/A", "threshold": "> 0.5"},
                }
            self._send_json(gates)
        except Exception as exc:
            logger.exception("Error serving /api/gates")
            self._send_json({"error": str(exc)}, status=500)

    # ═══════════════════════════════════════════════════════════════════
    # Data extraction helpers (all READ-ONLY)
    # ═══════════════════════════════════════════════════════════════════

    def _get_positions_list(self) -> list:
        """Pull open positions from the bot instance with enhanced fields."""
        bot = DashboardHandler.bot_instance
        if bot is None:
            return []

        positions_raw = None

        for attr in ("open_positions", "positions", "active_positions"):
            obj = getattr(bot, attr, None)
            if obj is not None:
                if callable(obj):
                    try:
                        positions_raw = obj()
                    except Exception:
                        pass
                else:
                    positions_raw = obj
                if positions_raw:
                    break

        if not positions_raw:
            engine = getattr(bot, "engine", None) or getattr(bot, "trading_engine", None)
            if engine:
                pm = getattr(engine, "position_manager", None) or engine
                for attr in ("open_positions", "positions", "get_positions"):
                    obj = getattr(pm, attr, None)
                    if obj is not None:
                        if callable(obj):
                            try:
                                positions_raw = obj()
                            except Exception:
                                pass
                        else:
                            positions_raw = obj
                        if positions_raw:
                            break

        if not positions_raw:
            return []

        result = []
        now = time.time()

        if isinstance(positions_raw, dict):
            items = list(positions_raw.values()) if positions_raw else []
        elif isinstance(positions_raw, (list, tuple)):
            items = positions_raw
        else:
            return []

        for pos in items:
            try:
                result.append(self._extract_position(pos, now))
            except Exception:
                pass

        return result

    def _extract_position(self, pos, now: float) -> dict:
        """Extract position fields from a dict or object."""
        if isinstance(pos, dict):
            g = pos.get
        else:
            g = lambda k, d=None: getattr(pos, k, d)

        entry_ts = g("open_time") or g("entry_time") or g("timestamp")
        hold_time = 0
        if entry_ts:
            try:
                if isinstance(entry_ts, (int, float)):
                    hold_time = now - entry_ts
                else:
                    dt = datetime.fromisoformat(str(entry_ts).replace("Z", "+00:00"))
                    hold_time = now - dt.timestamp()
            except Exception:
                pass

        entry_price = g("entry_price") or g("entry") or 0
        current_price = g("current_price") or g("mark_price") or 0
        unrealized_pnl = g("unrealized_pnl") or g("pnl") or 0

        pnl_pct = 0
        if entry_price and entry_price > 0 and unrealized_pnl:
            qty = g("qty") or g("quantity") or g("size") or 1
            if qty:
                pnl_pct = (unrealized_pnl / (entry_price * abs(qty))) * 100

        tp = g("trade_profile")
        if tp and hasattr(tp, "name"):
            tp = tp.name
        elif tp and hasattr(tp, "value"):
            tp = tp.value

        return {
            "symbol":          g("symbol", "???"),
            "side":            g("side", "LONG"),
            "entry_price":     entry_price,
            "current_price":   current_price,
            "sl":              g("sl") or g("stop_loss") or 0,
            "tp1":             g("tp1") or g("take_profit_1") or 0,
            "tp2":             g("tp2") or g("take_profit_2") or 0,
            "unrealized_pnl":  unrealized_pnl,
            "pnl_pct":         pnl_pct,
            "leverage":        g("leverage", 1),
            "state":           g("state", "OPEN"),
            "hold_time_s":     hold_time,
            "trade_profile":   str(tp) if tp else None,
            "notes":           g("notes"),
            "confidence":      g("confidence"),
        }

    def _get_market_data(self) -> list:
        """Build market heatmap data from signals and regime detection."""
        result = []
        danger_by_regime = {
            "panic": 90, "high_volatility": 70, "news_dislocation": 60,
            "low_liquidity": 50, "range": 30, "consolidation": 20,
            "trend": 10, "unknown": 0,
        }

        try:
            from data.db import get_signals_today, get_signal_performance
        except ImportError:
            return result

        try:
            signals = get_signals_today()
        except Exception:
            signals = []

        if not signals:
            return result

        by_symbol: Dict[str, list] = {}
        for sig in signals:
            sym = sig.get("symbol", "???")
            by_symbol.setdefault(sym, []).append(sig)

        perf_by_sym = {}
        try:
            sp = get_signal_performance(days=7)
            perf_by_sym = sp.get("by_symbol", {}) if isinstance(sp, dict) else {}
        except Exception:
            pass

        for sym, sigs in by_symbol.items():
            regime = "unknown"
            for sig in reversed(sigs):
                meta = sig.get("metadata")
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except Exception:
                        meta = {}
                if isinstance(meta, dict):
                    r = meta.get("regime") or meta.get("market_regime")
                    if r:
                        regime = r
                        break

            buys = sum(1 for s in sigs if (s.get("side") or "").upper() in ("BUY", "LONG"))
            sells = sum(1 for s in sigs if (s.get("side") or "").upper() in ("SELL", "SHORT"))
            bias = "bullish" if buys > sells else ("bearish" if sells > buys else "neutral")

            confs = [s.get("confidence", 0) for s in sigs if s.get("confidence")]
            avg_conf = sum(confs) / len(confs) if confs else 0

            danger = danger_by_regime.get(regime.lower(), 0)
            sym_perf = perf_by_sym.get(sym, {})
            recent_pnl = sym_perf.get("pnl")
            last_time = sigs[-1].get("timestamp") if sigs else None

            result.append({
                "symbol": sym, "regime": regime, "signal_bias": bias,
                "confidence": round(avg_conf, 1), "danger_level": danger,
                "recent_pnl": recent_pnl, "signal_count": len(sigs),
                "last_signal_time": last_time,
            })

        result.sort(key=lambda x: (-x["danger_level"], -x["signal_count"]))
        return result

    def _get_rejections_data(self) -> list:
        """Get recent rejected signals for the What If section."""
        try:
            from data.db import get_signal_rejections
        except ImportError:
            return []

        try:
            rejections = get_signal_rejections(hours=24)
        except Exception:
            return []

        result = []
        for r in (rejections or [])[:50]:
            meta = r.get("metadata")
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            if not isinstance(meta, dict):
                meta = {}

            result.append({
                "timestamp":          r.get("timestamp"),
                "symbol":             r.get("symbol"),
                "side":               r.get("side"),
                "confidence":         r.get("confidence"),
                "strategy":           r.get("strategy"),
                "gate":               r.get("gate"),
                "reason":             r.get("reason"),
                "counterfactual_pnl": meta.get("counterfactual_pnl") or meta.get("cf_pnl"),
            })

        return result

    def _get_copytrade_data(self) -> dict:
        """Get LLM copy-trade intelligence (placeholder when inactive)."""
        bot = DashboardHandler.bot_instance

        llm_active = False
        if bot is not None:
            for attr in ("llm_engine", "decision_engine", "agent_coordinator"):
                if getattr(bot, attr, None) is not None:
                    llm_active = True
                    break
            if not llm_active:
                llm_active = os.getenv("LLM_MULTI_AGENT", "").lower() in ("true", "1", "yes")

        if not llm_active:
            return {"active": False, "insights": [], "recommendation": "LLM system offline"}

        insights = []
        recommendation = ""
        decisions_path = os.path.join(_BOT_DIR, "data", "llm", "decisions.jsonl")
        try:
            if os.path.exists(decisions_path):
                with open(decisions_path, "r") as f:
                    lines = f.readlines()
                for line in lines[-10:]:
                    try:
                        dec = json.loads(line.strip())
                        agent = dec.get("agent") or dec.get("source") or "system"
                        summary = dec.get("summary") or dec.get("reasoning") or dec.get("decision", "")
                        if summary:
                            insights.append({
                                "agent": agent,
                                "summary": str(summary)[:300],
                                "timestamp": dec.get("timestamp"),
                            })
                    except Exception:
                        pass
                if insights:
                    recommendation = insights[-1].get("summary", "")
        except Exception:
            pass

        return {"active": llm_active, "insights": insights[-5:], "recommendation": recommendation}


# ═══════════════════════════════════════════════════════════════════════════
# Dashboard Server (threaded)
# ═══════════════════════════════════════════════════════════════════════════

class DashboardServer:
    """Manages the HTTP server lifecycle in a daemon thread."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = int(os.getenv("DASHBOARD_PORT", str(port)))
        self.server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self, bot_instance=None):
        DashboardHandler.bot_instance = bot_instance
        self.server = HTTPServer((self.host, self.port), DashboardHandler)
        self._thread = threading.Thread(
            target=self.server.serve_forever, name="dashboard-http", daemon=True,
        )
        self._thread.start()
        logger.info("Dashboard running at http://%s:%s",
                     self.host if self.host != "0.0.0.0" else "localhost", self.port)

    def stop(self):
        if self.server:
            self.server.shutdown()
            logger.info("Dashboard server stopped.")

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()


_singleton: Optional[DashboardServer] = None
_singleton_lock = threading.Lock()


def get_dashboard_server(host: str = "0.0.0.0", port: int = 8080) -> DashboardServer:
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = DashboardServer(host=host, port=port)
        return _singleton


if __name__ == "__main__":
    try:
        from dotenv import load_dotenv
        env_path = Path(_BOT_DIR).parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
        else:
            load_dotenv()
    except ImportError:
        pass

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s  %(message)s")

    try:
        from data.db import init_db
        init_db()
    except Exception as exc:
        logger.warning("Could not initialise DB: %s", exc)

    port = int(os.getenv("DASHBOARD_PORT", "8080"))
    srv = DashboardServer(port=port)
    srv.start()

    print(f"NunuIRL Dashboard running at http://localhost:{port}")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        srv.stop()
