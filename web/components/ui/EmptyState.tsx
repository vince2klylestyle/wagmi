'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { C, R, F, SP, G, Glass, alpha } from '../../src/theme';
import { cinematicReveal } from '../../src/animations';

export interface EmptyStateProps {
  icon?: string;
  title: string;
  subtitle?: string;
  action?: { label: string; onClick: () => void };
  /** Ambient background variant — adds a decorative visual behind the text */
  ambient?: 'waveform' | 'pulse' | 'constellation' | 'none';
}

// Tiny animated SVG waveform decoration
function AmbientWaveform() {
  const w = 280, h = 60;
  const pts = 8;
  const d = Array.from({ length: pts }, (_, i) => {
    const x = (i / (pts - 1)) * w;
    const y = h / 2 + Math.sin(i * 0.9) * 15;
    return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
  }).join(' ');

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', opacity: 0.12 }}>
      <defs>
        <linearGradient id="empty-wave-grad" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#6366f1" />
          <stop offset="50%" stopColor="#06b6d4" />
          <stop offset="100%" stopColor="#a855f7" />
        </linearGradient>
      </defs>
      <path d={d} fill="none" stroke="url(#empty-wave-grad)" strokeWidth={2.5} strokeLinecap="round">
        <animate attributeName="d"
          values={`${d};${Array.from({ length: pts }, (_, i) => {
            const x = (i / (pts - 1)) * w;
            const y = h / 2 + Math.cos(i * 0.9 + 1) * 18;
            return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
          }).join(' ')};${d}`}
          dur="6s" repeatCount="indefinite" />
      </path>
    </svg>
  );
}

// Pulsing concentric rings — "system alive" indicator
function AmbientPulse() {
  return (
    <svg width={120} height={120} viewBox="0 0 120 120" style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', opacity: 0.1 }}>
      {[40, 30, 20].map((r, i) => (
        <circle key={i} cx={60} cy={60} r={r} fill="none" stroke="#6366f1" strokeWidth={1}>
          <animate attributeName="r" values={`${r};${r + 12};${r}`} dur={`${3 + i * 0.5}s`} repeatCount="indefinite" />
          <animate attributeName="opacity" values="0.6;0.1;0.6" dur={`${3 + i * 0.5}s`} repeatCount="indefinite" />
        </circle>
      ))}
      <circle cx={60} cy={60} r={4} fill="#6366f1" opacity={0.5}>
        <animate attributeName="r" values="4;6;4" dur="2s" repeatCount="indefinite" />
      </circle>
    </svg>
  );
}

// Constellation dots — subtle connecting points
function AmbientConstellation() {
  const points = [
    { x: 30, y: 25 }, { x: 80, y: 15 }, { x: 140, y: 35 },
    { x: 60, y: 55 }, { x: 120, y: 50 }, { x: 200, y: 30 },
    { x: 170, y: 60 }, { x: 240, y: 45 }, { x: 100, y: 70 },
  ];
  return (
    <svg width={280} height={80} viewBox="0 0 280 80" style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', opacity: 0.08 }}>
      {/* Connection lines */}
      {points.map((p, i) =>
        points.slice(i + 1).filter(q => Math.hypot(q.x - p.x, q.y - p.y) < 90).map((q, j) => (
          <line key={`l-${i}-${j}`} x1={p.x} y1={p.y} x2={q.x} y2={q.y} stroke="#6366f1" strokeWidth={0.8} opacity={0.5} />
        ))
      )}
      {/* Points */}
      {points.map((p, i) => (
        <circle key={`p-${i}`} cx={p.x} cy={p.y} r={2} fill="#6366f1" opacity={0.7}>
          <animate attributeName="cy" values={`${p.y};${p.y - 4};${p.y}`} dur={`${4 + i * 0.3}s`} repeatCount="indefinite" />
        </circle>
      ))}
    </svg>
  );
}

const AMBIENT_MAP = {
  waveform: AmbientWaveform,
  pulse: AmbientPulse,
  constellation: AmbientConstellation,
  none: null,
};

export function EmptyState({ icon, title, subtitle, action, ambient = 'pulse' }: EmptyStateProps) {
  const AmbientBg = AMBIENT_MAP[ambient];

  return (
    <motion.div
      variants={cinematicReveal}
      initial="hidden"
      animate="show"
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: `${SP[12]}px ${SP[6]}px`,
        borderRadius: R.lg,
        ...Glass.crystal,
        textAlign: 'center',
        position: 'relative',
        overflow: 'hidden',
        minHeight: 180,
      }}
      className="refraction-edge"
    >
      {/* Ambient background decoration */}
      {AmbientBg && <AmbientBg />}

      {/* Content — always above ambient */}
      <div style={{ position: 'relative', zIndex: 1 }}>
        {icon && (
          <div style={{ fontSize: 40, opacity: 0.25, marginBottom: SP[3] }}>
            {icon}
          </div>
        )}
        <div
          style={{
            fontSize: F.lg,
            fontWeight: 600,
            color: C.textSub,
            marginBottom: subtitle ? SP[2] : action ? SP[4] : 0,
            background: G.brand,
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
          }}
        >
          {title}
        </div>
        {subtitle && (
          <div
            style={{
              fontSize: F.sm,
              color: C.muted,
              marginBottom: action ? SP[4] : 0,
              maxWidth: 340,
              lineHeight: 1.6,
            }}
          >
            {subtitle}
          </div>
        )}
        {action && (
          <motion.button
            onClick={action.onClick}
            whileHover={{ scale: 1.04, boxShadow: '0 0 24px rgba(99,102,241,0.3)' }}
            whileTap={{ scale: 0.97 }}
            style={{
              padding: `${SP[2]}px ${SP[6]}px`,
              borderRadius: R.md,
              border: '1px solid rgba(255,255,255,0.1)',
              background: G.brand,
              color: '#fff',
              fontSize: F.sm,
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'box-shadow 0.2s ease',
            }}
          >
            {action.label}
          </motion.button>
        )}
      </div>
    </motion.div>
  );
}

export default EmptyState;
