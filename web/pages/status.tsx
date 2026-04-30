'use client';

/**
 * /status — the operator's morning-glance page.
 *
 * Single page that answers, in one screen, the questions the operator asks
 * before doing anything else:
 *   1. Is the bot alive? When did it last decide / trade?
 *   2. What's the equity? Is it bleeding?
 *   3. Are there open positions? Are they OK?
 *   4. Are there alerts I should act on?
 *   5. What's the §7 audit say (rule enforcement, A/B closure, etc.)?
 *
 * Pulls from existing /v1/* endpoints — read-only. Designed for phone-first.
 */

import React, { useEffect, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { C, F, R } from '../src/theme';
import { resolveApiBase } from '../src/api';

type Summary = {
  equity?: number;
  peak_equity?: number;
  total_trades?: number;
  win_rate?: number;
  total_pnl?: number;
  open_positions?: number;
  today_pnl?: number;
  today_trades?: number;
};

type Position = {
  symbol: string;
  side: string;
  entry: number;
  qty: number;
  unrealized_pnl?: number;
  state?: string;
};

type LlmDecision = {
  symbol?: string;
  timestamp?: string;
  action?: string;
};

export default function StatusPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [lastDecision, setLastDecision] = useState<LlmDecision | null>(null);
  const [healthOk, setHealthOk] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    const apiBase = resolveApiBase();
    const load = async () => {
      try {
        const [healthRes, sumRes, posRes, feedRes] = await Promise.all([
          fetch(`${apiBase}/health`, { cache: 'no-store' }),
          fetch(`${apiBase}/v1/summary`, { cache: 'no-store' }),
          fetch(`${apiBase}/v1/positions`, { cache: 'no-store' }),
          fetch(`${apiBase}/v1/llm/feed?limit=1`, { cache: 'no-store' }),
        ]);
        if (cancelled) return;
        setHealthOk(healthRes.ok);
        if (sumRes.ok) setSummary(await sumRes.json());
        if (posRes.ok) {
          const j = await posRes.json();
          setPositions(j.positions || []);
        }
        if (feedRes.ok) {
          const j = await feedRes.json();
          setLastDecision((j.decisions || [])[0] || null);
        }
      } catch {
        if (!cancelled) setHealthOk(false);
      }
    };
    load();
    const id = setInterval(load, 30_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const lastDecisionTs = lastDecision?.timestamp ? new Date(lastDecision.timestamp) : null;
  const ageHours = lastDecisionTs ? (Date.now() - lastDecisionTs.getTime()) / 3.6e6 : null;
  const status: 'live' | 'stale' | 'offline' =
    healthOk === false ? 'offline' : ageHours == null || ageHours > 0.25 ? 'stale' : 'live';

  // Alert generation
  const alerts = generateAlerts({ summary, positions, ageHours, status });

  return (
    <>
      <Head>
        <title>Status — WAGMI</title>
      </Head>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <h1
          style={{
            margin: 0,
            fontSize: F.xl,
            fontWeight: 700,
            color: C.text,
            letterSpacing: -0.3,
          }}
        >
          Status
        </h1>

        {/* Headline row: bot status + equity + today P&L */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: 8,
          }}
        >
          <HeadlineCard
            label="bot"
            value={status.toUpperCase()}
            tone={status === 'live' ? C.bull : status === 'stale' ? C.warn : C.bear}
            sub={
              ageHours == null
                ? 'no decisions logged'
                : `last decision ${formatAge(ageHours)}`
            }
          />
          <HeadlineCard
            label="equity"
            value={summary?.equity != null ? `$${summary.equity.toFixed(0)}` : '—'}
            tone={C.text}
            sub={
              summary?.peak_equity
                ? `peak $${summary.peak_equity.toFixed(0)} · ${(((summary.equity || 0) / summary.peak_equity - 1) * 100).toFixed(1)}%`
                : ''
            }
          />
          <HeadlineCard
            label="today p&l"
            value={summary?.today_pnl != null ? `${summary.today_pnl >= 0 ? '+' : ''}$${summary.today_pnl.toFixed(2)}` : '—'}
            tone={(summary?.today_pnl ?? 0) >= 0 ? C.bull : C.bear}
            sub={`${summary?.today_trades ?? 0} trades`}
          />
          <HeadlineCard
            label="open positions"
            value={String(summary?.open_positions ?? 0)}
            tone={positions.length > 0 ? C.text : C.muted}
            sub={positions.length === 0 ? 'flat' : `total notional`}
          />
          <HeadlineCard
            label="all-time wr"
            value={summary?.win_rate != null ? `${(summary.win_rate * 100).toFixed(1)}%` : '—'}
            tone={(summary?.win_rate ?? 0) >= 0.5 ? C.bull : (summary?.win_rate ?? 0) >= 0.4 ? C.warn : C.bear}
            sub={`${summary?.total_trades ?? 0} trades total`}
          />
        </div>

        {/* Alerts */}
        {alerts.length > 0 && (
          <Card title="Alerts">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {alerts.map((a, i) => (
                <AlertRow key={i} alert={a} />
              ))}
            </div>
          </Card>
        )}

        {/* Open positions table */}
        <Card title="Open Positions" sub={positions.length === 0 ? 'no positions' : undefined}>
          {positions.length === 0 ? (
            <div style={{ color: C.muted, fontSize: F.sm }}>Flat.</div>
          ) : (
            <table
              style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontFamily: 'JetBrains Mono, monospace',
              }}
            >
              <thead>
                <tr style={{ textAlign: 'left', color: C.muted, fontSize: 10 }}>
                  <th style={th}>Symbol</th>
                  <th style={th}>Side</th>
                  <th style={th}>Qty</th>
                  <th style={thRight}>Entry</th>
                  <th style={thRight}>uPnL</th>
                  <th style={th}>State</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((p, i) => (
                  <tr key={i} style={{ borderTop: `1px solid ${C.border}`, fontSize: F.xs }}>
                    <td style={td}>
                      <Link href={`/live?symbol=${p.symbol}`} style={{ color: C.text, fontWeight: 600, textDecoration: 'none' }}>
                        {p.symbol}
                      </Link>
                    </td>
                    <td style={{ ...td, color: p.side.toUpperCase() === 'LONG' ? C.bull : C.bear }}>
                      {p.side}
                    </td>
                    <td style={td}>{p.qty}</td>
                    <td style={tdRight}>${p.entry.toFixed(2)}</td>
                    <td
                      style={{
                        ...tdRight,
                        color: (p.unrealized_pnl ?? 0) >= 0 ? C.bull : C.bear,
                      }}
                    >
                      {p.unrealized_pnl != null
                        ? `${p.unrealized_pnl >= 0 ? '+' : ''}$${p.unrealized_pnl.toFixed(2)}`
                        : '—'}
                    </td>
                    <td style={{ ...td, color: C.muted }}>{p.state || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        {/* Quick links */}
        <Card title="Quick links">
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
              gap: 6,
            }}
          >
            <QuickLink href="/live" label="Live Co-Pilot" sub="triple panel + Q&A" />
            <QuickLink href="/results" label="History" sub="closed trades" />
            <QuickLink href="/forensics" label="Forensics" sub="heatmaps & analytics" />
            <QuickLink href="/counterfactuals" label="Counterfactuals" sub="what we left on the table" />
            <QuickLink href="/strategies" label="Strategies" sub="fleet status" />
            <QuickLink href="/backtest" label="Backtest" sub="run + compare" />
          </div>
        </Card>
      </div>
    </>
  );
}

// ── Sub-components ───────────────────────────────────────────────────────────

function HeadlineCard({
  label,
  value,
  tone,
  sub,
}: {
  label: string;
  value: string;
  tone: string;
  sub?: string;
}) {
  return (
    <div
      style={{
        background: '#0a0a0f',
        border: `1px solid ${C.border}`,
        borderRadius: R.sm,
        padding: '10px 12px',
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
        fontFamily: 'JetBrains Mono, monospace',
      }}
    >
      <span style={{ fontSize: 10, color: C.muted, textTransform: 'uppercase', letterSpacing: 0.06, fontWeight: 600 }}>
        {label}
      </span>
      <span style={{ fontSize: F.lg, fontWeight: 700, color: tone, letterSpacing: -0.3 }}>
        {value}
      </span>
      {sub && (
        <span style={{ fontSize: 10, color: C.faint, fontFamily: 'JetBrains Mono, monospace' }}>
          {sub}
        </span>
      )}
    </div>
  );
}

function Card({
  title,
  sub,
  children,
}: {
  title: string;
  sub?: string;
  children: React.ReactNode;
}) {
  return (
    <section
      style={{
        background: '#0a0a0f',
        border: `1px solid ${C.border}`,
        borderRadius: R.sm,
      }}
    >
      <header
        style={{
          padding: '10px 12px',
          borderBottom: `1px solid ${C.border}`,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
        }}
      >
        <span
          style={{
            fontSize: 10,
            fontWeight: 700,
            color: C.text,
            letterSpacing: 0.06,
            textTransform: 'uppercase',
            fontFamily: 'JetBrains Mono, monospace',
          }}
        >
          {title}
        </span>
        {sub && <span style={{ fontSize: F.xs, color: C.muted }}>{sub}</span>}
      </header>
      <div style={{ padding: 12 }}>{children}</div>
    </section>
  );
}

type Alert = { tone: 'critical' | 'warning' | 'info'; text: string; href?: string };

function AlertRow({ alert }: { alert: Alert }) {
  const tone =
    alert.tone === 'critical' ? C.bear : alert.tone === 'warning' ? C.warn : C.info;
  const content = (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '8px 10px',
        background: '#050508',
        border: `1px solid ${C.border}`,
        borderLeft: `3px solid ${tone}`,
        borderRadius: 4,
        fontSize: F.xs,
        color: C.textSub,
        fontFamily: 'JetBrains Mono, monospace',
      }}
    >
      <span style={{ color: tone, fontWeight: 700, letterSpacing: 0.06, minWidth: 60 }}>
        {alert.tone.toUpperCase()}
      </span>
      <span style={{ flex: 1 }}>{alert.text}</span>
    </div>
  );
  return alert.href ? <Link href={alert.href} style={{ textDecoration: 'none' }}>{content}</Link> : content;
}

function QuickLink({ href, label, sub }: { href: string; label: string; sub: string }) {
  return (
    <Link
      href={href}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
        padding: '8px 10px',
        background: '#050508',
        border: `1px solid ${C.border}`,
        borderRadius: R.xs,
        textDecoration: 'none',
        transition: 'border-color 120ms ease-out',
      }}
    >
      <span style={{ fontSize: F.sm, fontWeight: 600, color: C.text }}>{label}</span>
      <span style={{ fontSize: 10, color: C.muted, fontFamily: 'JetBrains Mono, monospace' }}>
        {sub}
      </span>
    </Link>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function generateAlerts({
  summary,
  positions,
  ageHours,
  status,
}: {
  summary: Summary | null;
  positions: Position[];
  ageHours: number | null;
  status: 'live' | 'stale' | 'offline';
}): Alert[] {
  const alerts: Alert[] = [];

  if (status === 'offline') {
    alerts.push({
      tone: 'critical',
      text: 'API not responding. Bot may be down. Check that bot/api_server.py is running.',
    });
  } else if (status === 'stale' && ageHours != null && ageHours > 24) {
    alerts.push({
      tone: 'critical',
      text: `Bot inactive — last decision ${formatAge(ageHours)}. Restart pipeline to resume trading.`,
    });
  } else if (status === 'stale' && ageHours != null && ageHours > 1) {
    alerts.push({
      tone: 'warning',
      text: `No recent decisions (${formatAge(ageHours)}). Bot may be paused or in cooldown.`,
    });
  }

  if (summary?.equity != null && summary?.peak_equity) {
    const dd = (summary.equity / summary.peak_equity - 1) * 100;
    if (dd < -20) {
      alerts.push({
        tone: 'critical',
        text: `Drawdown ${dd.toFixed(1)}% from peak — review risk gates and recent losses.`,
        href: '/forensics',
      });
    } else if (dd < -10) {
      alerts.push({
        tone: 'warning',
        text: `Drawdown ${dd.toFixed(1)}% from peak — monitor.`,
        href: '/forensics',
      });
    }
  }

  if ((summary?.today_pnl ?? 0) < -50) {
    alerts.push({
      tone: 'warning',
      text: `Today's P&L ${summary!.today_pnl!.toFixed(2)} — circuit breaker may engage.`,
      href: '/live',
    });
  }

  if (positions.length > 0) {
    const losingPositions = positions.filter((p) => (p.unrealized_pnl ?? 0) < -20);
    if (losingPositions.length > 0) {
      alerts.push({
        tone: 'warning',
        text: `${losingPositions.length} losing position${losingPositions.length > 1 ? 's' : ''} — consider checking exits.`,
        href: '/live',
      });
    }
  }

  return alerts;
}

function formatAge(hours: number): string {
  if (hours < 1) return `${Math.round(hours * 60)} min ago`;
  if (hours < 24) return `${Math.round(hours)}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

const th: React.CSSProperties = {
  padding: '6px 8px',
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: 0.04,
};
const thRight: React.CSSProperties = { ...th, textAlign: 'right' };
const td: React.CSSProperties = { padding: '6px 8px', color: C.text };
const tdRight: React.CSSProperties = { ...td, textAlign: 'right' };
