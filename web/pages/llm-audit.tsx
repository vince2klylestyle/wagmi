'use client';

import React, { useEffect, useState, useMemo } from 'react';
import Link from 'next/link';
import { C, R, F, S, fmtPct } from '../src/theme';
import type { LlmDecision, LlmFeedResponse } from '../src/types';

function resolveApiBase(): string {
  const envVal =
    (process.env.NEXT_PUBLIC_API_URL as string | undefined) ||
    (process.env.NEXT_PUBLIC_API_BASE_URL as string | undefined);
  if (envVal && envVal.trim().length > 0) return envVal;
  if (typeof window !== 'undefined') {
    const host = window.location.hostname;
    if (host && host !== 'localhost' && host !== '127.0.0.1') return 'https://nunuirl-platform.onrender.com';
  }
  return 'http://localhost:8000';
}

function Skeleton({ h = 16, w = '100%' }: { h?: number; w?: string | number }) {
  return <div className="skeleton" style={{ height: h, width: w, borderRadius: R.sm }} />;
}

function timeAgo(isoOrTs: string | number | null | undefined): string {
  if (!isoOrTs) return '';
  try {
    const ts = typeof isoOrTs === 'number' ? isoOrTs * 1000 : new Date(isoOrTs).getTime();
    const diff = Math.floor((Date.now() - ts) / 1000);
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  } catch { return ''; }
}

// ─── Model Routing Chart ──────────────────────────────────────────────────────

function ModelRoutingChart({ decisions }: { decisions: LlmDecision[] }) {
  const counts: Record<string, number> = {};
  decisions.forEach((d) => {
    const model = d.model || 'unknown';
    const key = model.includes('haiku') ? 'Haiku' : model.includes('sonnet') ? 'Sonnet' : model.includes('opus') ? 'Opus' : 'Other';
    counts[key] = (counts[key] || 0) + 1;
  });
  const total = decisions.length || 1;

  const modelColors: Record<string, string> = {
    Haiku: C.warn,
    Sonnet: C.info,
    Opus: C.purple,
    Other: C.muted,
  };

  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);

  // Trigger × Model matrix
  const triggerModel: Record<string, Record<string, number>> = {};
  decisions.forEach((d) => {
    const trigger = d.trigger || 'unknown';
    const model = d.model?.includes('haiku') ? 'Haiku' : d.model?.includes('sonnet') ? 'Sonnet' : d.model?.includes('opus') ? 'Opus' : 'Other';
    if (!triggerModel[trigger]) triggerModel[trigger] = {};
    triggerModel[trigger][model] = (triggerModel[trigger][model] || 0) + 1;
  });
  const triggers = Object.keys(triggerModel).filter((t) => t !== 'unknown');
  const models = ['Haiku', 'Sonnet', 'Opus', 'Other'];

  return (
    <div>
      {/* Stacked bar */}
      <div style={{ marginBottom: 12 }}>
        <div style={{ height: 20, borderRadius: R.pill, overflow: 'hidden', display: 'flex', marginBottom: 8 }}>
          {entries.map(([model, count]) => (
            <div
              key={model}
              title={`${model}: ${count} (${((count / total) * 100).toFixed(0)}%)`}
              style={{ flex: count, background: modelColors[model] || C.muted, transition: 'flex 0.4s' }}
            />
          ))}
        </div>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          {entries.map(([model, count]) => (
            <div key={model} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: modelColors[model] || C.muted, display: 'inline-block' }} />
              <span style={{ fontSize: F.xs, fontWeight: 600, color: modelColors[model] || C.muted }}>{model}</span>
              <span style={{ fontSize: F.xs, color: C.muted }}>{count} ({((count / total) * 100).toFixed(0)}%)</span>
            </div>
          ))}
        </div>
      </div>

      {/* Trigger × Model matrix */}
      {triggers.length > 0 && (
        <div style={{ overflowX: 'auto', marginTop: 16 }}>
          <div style={{ fontSize: F.xs, color: C.muted, marginBottom: 8, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5 }}>
            Trigger → Model Routing Matrix
          </div>
          <table style={{ borderCollapse: 'collapse', fontSize: F.xs, minWidth: 400 }}>
            <thead>
              <tr>
                <th style={{ padding: '6px 10px', textAlign: 'left', color: C.muted, fontWeight: 600, borderBottom: `1px solid ${C.border}` }}>Trigger</th>
                {models.map((m) => (
                  <th key={m} style={{ padding: '6px 10px', textAlign: 'right', color: modelColors[m] || C.muted, fontWeight: 700, borderBottom: `1px solid ${C.border}` }}>{m}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {triggers.map((trigger) => (
                <tr key={trigger} style={{ borderBottom: `1px solid ${C.border}` }}>
                  <td style={{ padding: '6px 10px', color: C.textSub, fontWeight: 600 }}>{trigger}</td>
                  {models.map((m) => {
                    const count = triggerModel[trigger]?.[m] || 0;
                    return (
                      <td key={m} style={{ padding: '6px 10px', textAlign: 'right', color: count > 0 ? modelColors[m] : C.faint, fontWeight: count > 0 ? 700 : 400, fontVariantNumeric: 'tabular-nums' }}>
                        {count || '—'}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Veto Analysis ────────────────────────────────────────────────────────────

function VetoAnalysis({ decisions }: { decisions: LlmDecision[] }) {
  const vetoes = decisions.filter((d) => d.is_veto);
  if (!vetoes.length) {
    return <div style={{ color: C.muted, fontSize: F.sm, padding: '16px 0' }}>No veto decisions recorded yet.</div>;
  }

  const bySymbol: Record<string, number> = {};
  const byRegime: Record<string, number> = {};
  const byReason: Record<string, number> = {};

  vetoes.forEach((v) => {
    if (v.symbol) bySymbol[v.symbol] = (bySymbol[v.symbol] || 0) + 1;
    if (v.regime) byRegime[v.regime] = (byRegime[v.regime] || 0) + 1;
    if (v.gate_reason) {
      const key = v.gate_reason.length > 40 ? v.gate_reason.substring(0, 40) + '…' : v.gate_reason;
      byReason[key] = (byReason[key] || 0) + 1;
    }
  });

  const sortedEntries = (obj: Record<string, number>) => Object.entries(obj).sort((a, b) => b[1] - a[1]);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16 }}>
      {[
        { title: 'By Symbol', entries: sortedEntries(bySymbol), color: C.info },
        { title: 'By Regime', entries: sortedEntries(byRegime), color: C.bear },
        { title: 'By Reason (truncated)', entries: sortedEntries(byReason).slice(0, 5), color: C.warn },
      ].map(({ title, entries, color }) => (
        <div key={title}>
          <div style={{ fontSize: F.xs, color: C.muted, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>{title}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {entries.slice(0, 6).map(([key, count]) => (
              <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: F.xs, color: C.textSub, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{key}</span>
                <span style={{ fontSize: F.xs, fontWeight: 700, color, flexShrink: 0, minWidth: 28, textAlign: 'right' }}>{count}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Decision Row ─────────────────────────────────────────────────────────────

function DecisionRow({ d }: { d: LlmDecision }) {
  const [expanded, setExpanded] = useState(false);

  const actionColors: Record<string, { bg: string; text: string }> = {
    proceed: { bg: C.bull + '18', text: C.bullMid },
    go: { bg: C.bull + '18', text: C.bullMid },
    skip: { bg: C.surfaceHover, text: C.muted },
    flat: { bg: C.surfaceHover, text: C.muted },
    flip: { bg: C.purple + '18', text: '#c4b5fd' },
    veto: { bg: C.bear + '18', text: C.bearMid },
    unknown: { bg: C.surfaceHover, text: C.faint },
  };

  const actionStyle = actionColors[(d.action || '').toLowerCase()] || actionColors.unknown;
  const modelTag = d.model?.includes('haiku') ? 'Haiku' : d.model?.includes('sonnet') ? 'Sonnet' : d.model?.includes('opus') ? 'Opus' : d.model || '';
  const modelColor = modelTag === 'Haiku' ? C.warn : modelTag === 'Sonnet' ? C.info : C.purple;
  const confPct = Math.round((d.confidence ?? 0) * 100);
  const confColor = confPct >= 65 ? C.bull : confPct >= 42 ? C.warn : C.bear;

  return (
    <div style={{ borderBottom: `1px solid ${C.border}` }}>
      <button
        onClick={() => setExpanded((v) => !v)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 8, padding: '10px 16px',
          background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left', flexWrap: 'wrap',
        }}
      >
        {/* Timestamp */}
        <span style={{ fontSize: F.xs, color: C.faint, minWidth: 60, flexShrink: 0 }}>
          {timeAgo(d.ts_iso || d.ts)}
        </span>

        {/* Symbol */}
        {d.symbol && (
          <span style={{ fontSize: F.sm, fontWeight: 800, color: C.text, minWidth: 36 }}>{d.symbol}</span>
        )}

        {/* Action badge */}
        <span style={{
          fontSize: F.xs, fontWeight: 700, padding: '2px 8px', borderRadius: R.pill,
          background: actionStyle.bg, color: actionStyle.text,
        }}>
          {(d.action || 'UNKNOWN').toUpperCase()}
          {d.is_veto && ' — VETOED'}
        </span>

        {/* Confidence */}
        <span style={{ fontSize: F.xs, fontWeight: 700, color: confColor, minWidth: 36 }}>{confPct}%</span>

        {/* Regime */}
        {d.regime && (
          <span style={{ fontSize: F.xs, padding: '2px 6px', borderRadius: R.pill, background: C.surfaceHover, color: C.muted, textTransform: 'capitalize' }}>
            {d.regime}
          </span>
        )}

        {/* Model */}
        {modelTag && (
          <span style={{ fontSize: F.xs, fontWeight: 600, color: modelColor }}>{modelTag}</span>
        )}

        {/* Trigger */}
        {d.trigger && (
          <span style={{ fontSize: F.xs, color: C.faint }}>{d.trigger}</span>
        )}

        {/* Gate blocked badge */}
        {!d.allowed && d.gate_reason && (
          <span style={{ fontSize: F.xs, padding: '2px 6px', borderRadius: R.pill, background: C.warn + '18', color: C.warn, fontWeight: 600 }}>
            BLOCKED
          </span>
        )}

        <span style={{ marginLeft: 'auto', color: C.faint, fontSize: 11, transform: expanded ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}>▼</span>
      </button>

      {expanded && d.notes && (
        <div style={{ padding: '0 16px 12px', borderTop: `1px solid ${C.border}` }}>
          <div style={{ fontSize: F.xs, color: C.muted, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6, marginTop: 10 }}>
            LLM Reasoning
          </div>
          <div style={{ fontSize: F.xs, color: C.textSub, lineHeight: 1.7, fontStyle: 'italic' }}>
            {d.notes}
          </div>
          {d.gate_reason && (
            <div style={{ marginTop: 8, fontSize: F.xs, color: C.warn }}>
              <strong>Gate reason:</strong> {d.gate_reason}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main Page ─────────────────────────────────────────────────────────────────

export default function LlmAudit() {
  const [decisions, setDecisions] = useState<LlmDecision[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterAction, setFilterAction] = useState('All');
  const [filterTrigger, setFilterTrigger] = useState('All');
  const [filterSymbol, setFilterSymbol] = useState('All');
  const apiBase = resolveApiBase();

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`${apiBase}/v1/llm/feed?limit=200`);
        if (res.ok) {
          const d: LlmFeedResponse = await res.json();
          setDecisions(d?.items || []);
        }
      } catch {/* silent */}
      setLoading(false);
    };
    load();
    const iv = setInterval(load, 30000);
    return () => clearInterval(iv);
  }, [apiBase]);

  const triggers = useMemo(() => ['All', ...Array.from(new Set(decisions.map((d) => d.trigger).filter(Boolean)))], [decisions]);
  const symbols = useMemo(() => ['All', ...Array.from(new Set(decisions.map((d) => d.symbol).filter(Boolean) as string[]))], [decisions]);

  const filtered = useMemo(() => {
    return decisions.filter((d) => {
      if (filterAction !== 'All') {
        if (filterAction === 'VETO' && !d.is_veto) return false;
        if (filterAction === 'PROCEED' && !['proceed', 'go'].includes((d.action || '').toLowerCase())) return false;
        if (filterAction === 'SKIP' && !['skip', 'flat'].includes((d.action || '').toLowerCase())) return false;
        if (filterAction === 'FLIP' && (d.action || '').toLowerCase() !== 'flip') return false;
        if (filterAction === 'BLOCKED' && d.allowed) return false;
      }
      if (filterTrigger !== 'All' && d.trigger !== filterTrigger) return false;
      if (filterSymbol !== 'All' && d.symbol !== filterSymbol) return false;
      return true;
    });
  }, [decisions, filterAction, filterTrigger, filterSymbol]);

  // Stats
  const stats = useMemo(() => {
    const total = decisions.length;
    if (!total) return null;
    const proceed = decisions.filter((d) => ['proceed', 'go'].includes((d.action || '').toLowerCase())).length;
    const vetoes = decisions.filter((d) => d.is_veto).length;
    const blocked = decisions.filter((d) => !d.allowed).length;
    const avgConf = decisions.reduce((s, d) => s + (d.confidence ?? 0), 0) / total;
    const models: Record<string, number> = {};
    decisions.forEach((d) => {
      const m = d.model?.includes('haiku') ? 'Haiku' : d.model?.includes('sonnet') ? 'Sonnet' : d.model?.includes('opus') ? 'Opus' : 'Other';
      models[m] = (models[m] || 0) + 1;
    });
    return { total, proceed, vetoes, blocked, avgConf, models };
  }, [decisions]);

  const PillBtn = ({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) => (
    <button
      onClick={onClick}
      style={{
        fontSize: F.xs, padding: '3px 10px', borderRadius: R.pill, cursor: 'pointer', fontWeight: 600,
        border: `1px solid ${active ? C.brand : C.border}`,
        background: active ? C.brand + '22' : 'transparent',
        color: active ? C.brand : C.muted,
        transition: 'all 0.12s',
      }}
    >
      {label}
    </button>
  );

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ fontSize: F.xs, color: C.brand, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>
          AI Transparency
        </div>
        <h1 style={{ margin: 0, fontSize: 28, fontWeight: 800, color: C.text, letterSpacing: -0.5 }}>
          LLM Decision Audit
        </h1>
        <p style={{ margin: '6px 0 0', fontSize: F.sm, color: C.muted, maxWidth: 680 }}>
          Every AI decision, in full. What model was used, what trigger fired, the full reasoning, and whether the trade was blocked. Radical transparency.
        </p>
      </div>

      {/* Stat Row */}
      {loading ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 12, marginBottom: 28 }}>
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} h={64} />)}
        </div>
      ) : !stats ? (
        <div style={{ padding: '24px 20px', background: C.card, borderRadius: R.lg, border: `1px solid ${C.border}`, textAlign: 'center', color: C.muted, fontSize: F.sm, marginBottom: 28 }}>
          No LLM decisions recorded yet. Start the bot with <code style={{ background: C.surfaceHover, padding: '1px 4px', borderRadius: R.xs, color: C.brand }}>LLM_MODE=1</code> to see AI decisions here.
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 12, marginBottom: 28 }}>
          {[
            { label: 'Total Decisions', value: `${stats.total}`, color: C.text },
            { label: 'Proceed Rate', value: `${stats.total > 0 ? ((stats.proceed / stats.total) * 100).toFixed(0) : 0}%`, color: C.bull },
            { label: 'Veto Rate', value: `${stats.total > 0 ? ((stats.vetoes / stats.total) * 100).toFixed(0) : 0}%`, color: C.bear },
            { label: 'Gate Block Rate', value: `${stats.total > 0 ? ((stats.blocked / stats.total) * 100).toFixed(0) : 0}%`, color: C.warn },
            { label: 'Avg Confidence', value: `${(stats.avgConf * 100).toFixed(0)}%`, color: stats.avgConf >= 0.55 ? C.bull : C.warn },
            {
              label: 'Models Used',
              value: Object.entries(stats.models).map(([m, c]) => `${m[0]}:${c}`).join(' '),
              color: C.text,
            },
          ].map(({ label, value, color }) => (
            <div key={label} style={{ padding: '12px 14px', background: C.card, border: `1px solid ${C.border}`, borderRadius: R.lg }}>
              <div style={{ fontSize: F.xs, color: C.muted, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.6, marginBottom: 4 }}>{label}</div>
              <div style={{ fontSize: 18, fontWeight: 800, color, fontVariantNumeric: 'tabular-nums' }}>{value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Model Routing */}
      {decisions.length > 0 && (
        <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: R.lg, padding: '20px 24px', marginBottom: 24 }}>
          <h2 style={{ margin: '0 0 16px', fontSize: 16, fontWeight: 700, color: C.text }}>Model Routing</h2>
          <ModelRoutingChart decisions={decisions} />
        </div>
      )}

      {/* Veto Analysis */}
      {decisions.some((d) => d.is_veto) && (
        <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: R.lg, padding: '20px 24px', marginBottom: 24 }}>
          <h2 style={{ margin: '0 0 4px', fontSize: 16, fontWeight: 700, color: C.text }}>Veto Analysis</h2>
          <div style={{ fontSize: F.xs, color: C.muted, marginBottom: 16 }}>
            {decisions.filter((d) => d.is_veto).length} vetoes out of {decisions.length} decisions
          </div>
          <VetoAnalysis decisions={decisions} />
        </div>
      )}

      {/* Filters */}
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: R.lg, padding: '14px 20px', marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: F.xs, color: C.muted, fontWeight: 600 }}>Filter:</span>
          {['All', 'PROCEED', 'SKIP', 'VETO', 'FLIP', 'BLOCKED'].map((a) => (
            <PillBtn key={a} label={a} active={filterAction === a} onClick={() => setFilterAction(a)} />
          ))}
          <span style={{ color: C.faint }}>|</span>
          {symbols.slice(0, 8).map((s) => (
            <PillBtn key={s} label={s} active={filterSymbol === s} onClick={() => setFilterSymbol(s)} />
          ))}
          {triggers.length > 2 && (
            <>
              <span style={{ color: C.faint }}>|</span>
              <select
                value={filterTrigger}
                onChange={(e) => setFilterTrigger(e.target.value)}
                style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: R.sm, color: C.text, padding: '3px 8px', fontSize: F.xs, cursor: 'pointer' }}
              >
                {triggers.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </>
          )}
        </div>
      </div>

      {/* Decision Timeline */}
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: R.lg, overflow: 'hidden' }}>
        <div style={{ padding: '14px 20px', background: C.surfaceHover, borderBottom: `1px solid ${C.border}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: F.sm, fontWeight: 700, color: C.text }}>Decision Timeline</span>
          <span style={{ fontSize: F.xs, color: C.muted }}>{filtered.length} decisions · click to expand reasoning</span>
        </div>
        {loading ? (
          <div style={{ padding: '16px 20px' }}>
            {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} h={40} style={{ marginBottom: 8 }} />)}
          </div>
        ) : filtered.length === 0 ? (
          <div style={{ padding: '32px 24px', textAlign: 'center', color: C.muted, fontSize: F.sm }}>
            No decisions match the current filters.
          </div>
        ) : (
          filtered.map((d, i) => <DecisionRow key={i} d={d} />)
        )}
      </div>

      {/* Links */}
      <div style={{ display: 'flex', gap: 12, marginTop: 28, paddingTop: 20, borderTop: `1px solid ${C.border}` }}>
        <Link href="/signals" style={{ fontSize: F.sm, padding: '8px 16px', borderRadius: R.md, background: C.brand, color: '#fff', fontWeight: 700, textDecoration: 'none' }}>
          ← Live Signals
        </Link>
        <Link href="/forensics" style={{ fontSize: F.sm, padding: '8px 16px', borderRadius: R.md, border: `1px solid ${C.border}`, color: C.muted, fontWeight: 600, textDecoration: 'none' }}>
          Trade Forensics →
        </Link>
      </div>
    </div>
  );
}
