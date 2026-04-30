'use client';

import React from 'react';
import { C, F, R } from '../../src/theme';

/**
 * ColumnShell — shared visual container for the three /live columns.
 * Header has a label, a tone color (for visual differentiation), and
 * optional verdict chip. Body is whatever the column renders.
 */

export type ColumnTone = 'mechanical' | 'agentic' | 'synthesis';

const TONE: Record<ColumnTone, { color: string; label: string }> = {
  mechanical: { color: C.info, label: 'MECHANICAL' },
  agentic: { color: C.purple, label: 'AGENTIC' },
  synthesis: { color: C.brand, label: 'SYNTHESIS' },
};

export default function ColumnShell({
  tone,
  verdict,
  children,
}: {
  tone: ColumnTone;
  verdict?: { label: string; color?: string } | null;
  children: React.ReactNode;
}) {
  const t = TONE[tone];
  return (
    <section
      style={{
        background: '#0a0a0f',
        border: `1px solid ${C.border}`,
        borderTop: `2px solid ${t.color}`,
        borderRadius: R.sm,
        display: 'flex',
        flexDirection: 'column',
        minHeight: 480,
      }}
    >
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 12px',
          borderBottom: `1px solid ${C.border}`,
        }}
      >
        <span
          style={{
            fontSize: 10,
            fontWeight: 700,
            color: t.color,
            letterSpacing: 0.08,
            fontFamily: 'JetBrains Mono, monospace',
          }}
        >
          {t.label}
        </span>
        {verdict && (
          <span
            style={{
              fontSize: F.xs,
              fontWeight: 700,
              color: verdict.color || C.text,
              padding: '2px 8px',
              border: `1px solid ${(verdict.color || C.borderBright) + '55'}`,
              borderRadius: 3,
              fontFamily: 'JetBrains Mono, monospace',
            }}
          >
            {verdict.label}
          </span>
        )}
      </header>
      <div style={{ flex: 1, padding: 12, display: 'flex', flexDirection: 'column', gap: 12 }}>
        {children}
      </div>
    </section>
  );
}

export function Section({
  title,
  children,
  hint,
}: {
  title: string;
  children: React.ReactNode;
  hint?: string;
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          fontSize: 10,
          color: C.muted,
          textTransform: 'uppercase',
          letterSpacing: 0.06,
          fontWeight: 600,
        }}
      >
        <span>{title}</span>
        {hint && <span style={{ color: C.faint, textTransform: 'none', letterSpacing: 0 }}>{hint}</span>}
      </div>
      <div>{children}</div>
    </div>
  );
}

export function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: React.ReactNode;
  tone?: string;
}) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        fontSize: F.xs,
        fontFamily: 'JetBrains Mono, monospace',
        padding: '3px 0',
      }}
    >
      <span style={{ color: C.muted }}>{label}</span>
      <span style={{ color: tone || C.text }}>{value}</span>
    </div>
  );
}

export function Empty({ note }: { note?: string }) {
  return (
    <div style={{ color: C.muted, fontSize: F.sm, fontStyle: 'italic' }}>
      {note || 'No data yet — wires in next commit.'}
    </div>
  );
}

/**
 * Skeleton — neutral pulsing rectangle for in-flight data. Use when waiting
 * on a fetch instead of leaving sections blank.
 */
export function Skeleton({
  width = '100%',
  height = 16,
  rows = 1,
}: {
  width?: number | string;
  height?: number;
  rows?: number;
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          style={{
            width,
            height,
            background: 'linear-gradient(90deg, rgba(255,255,255,0.03), rgba(255,255,255,0.06), rgba(255,255,255,0.03))',
            borderRadius: 3,
            animation: 'wagmi-skeleton-pulse 1.6s ease-in-out infinite',
          }}
        />
      ))}
      <style jsx global>{`
        @keyframes wagmi-skeleton-pulse {
          0%, 100% { opacity: 0.5; }
          50% { opacity: 0.95; }
        }
      `}</style>
    </div>
  );
}

/**
 * ErrorState — user-visible error w/ retry button. Compact, fits inside columns.
 */
export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div
      style={{
        padding: 10,
        background: '#050508',
        border: `1px solid ${C.bear}55`,
        borderLeft: `3px solid ${C.bear}`,
        borderRadius: 4,
        fontSize: F.xs,
        color: C.textSub,
        fontFamily: 'JetBrains Mono, monospace',
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
      }}
    >
      <span style={{ color: C.bear, fontWeight: 700 }}>error</span>
      <span style={{ color: C.textSub, lineHeight: 1.4 }}>{message}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            alignSelf: 'flex-start',
            padding: '3px 10px',
            background: 'transparent',
            border: `1px solid ${C.border}`,
            borderRadius: 3,
            color: C.text,
            fontSize: 10,
            fontFamily: 'inherit',
            cursor: 'pointer',
          }}
        >
          retry
        </button>
      )}
    </div>
  );
}
