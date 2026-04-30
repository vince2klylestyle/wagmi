import React from 'react';

/**
 * WAGMI Design System — shared tokens.
 * True black base, green accent (#00cc88), clean card surfaces.
 */

export const C: Record<string, string> = {
  // Brand — green accent
  brand: '#00cc88',
  brandDark: '#00a86b',
  brandGlow: 'rgba(0,204,136,0.15)',
  brandMid: '#00e699',

  // Semantic
  bull: '#00cc88',
  bullLight: 'rgba(0,204,136,0.12)',
  bullMid: '#00e699',
  bear: '#ff4466',
  bearLight: 'rgba(255,68,102,0.12)',
  bearMid: '#ff6680',
  warn: '#ffaa00',
  warnLight: 'rgba(255,170,0,0.12)',
  warnMid: '#ffc133',
  info: '#4488ff',
  infoLight: 'rgba(68,136,255,0.12)',
  infoMid: '#66aaff',
  purple: '#aa66ff',
  purpleLight: 'rgba(170,102,255,0.12)',

  // Dark surface scale — true black
  bg: '#050508',
  surface: '#0a0a0f',
  surfaceHover: '#0f0f18',
  card: '#0d0d14',
  cardHover: '#121220',
  border: 'rgba(255,255,255,0.06)',
  borderBright: 'rgba(255,255,255,0.12)',

  // Text on dark
  text: '#f0f0f5',
  textSub: '#a0a0b8',
  muted: '#6b6b7b',
  faint: '#333344',

  // Semantic muted tints
  bearMuted: 'rgba(255,68,102,0.10)',
  bullMuted: 'rgba(0,204,136,0.10)',
  brandMuted: 'rgba(0,204,136,0.10)',
  warnMuted: 'rgba(255,170,0,0.10)',
  infoMuted: 'rgba(68,136,255,0.10)',
  purpleMuted: 'rgba(170,102,255,0.10)',

  // Heatmap cells
  heatBull3: '#006644',
  heatBull2: '#008855',
  heatBull1: '#00cc88',
  heatNeutral: '#1a1a26',
  heatBear1: '#ff4466',
  heatBear2: '#cc2244',
  heatBear3: '#881133',

  // Legacy light surface scale — kept for backwards compat (not used in new design)
  bgLight: '#f8fafc',
  surfaceLight: '#ffffff',
  cardLight: '#f1f5f9',
  borderLight: '#e2e8f0',
  textLight: '#0f172a',
  textSubLight: '#374151',
  mutedLight: '#6b7280',

  // Extended palette
  cyan: '#00ddcc',
  cyanGlow: 'rgba(0,221,204,0.15)',
  rose: '#ff4488',
  roseGlow: 'rgba(255,68,136,0.15)',
  amber: '#ffaa00',
  emerald: '#00cc88',
};

export const R = {
  xs: 4,
  sm: 6,
  md: 10,
  lg: 12,
  xl: 16,
  pill: 999,
} as const;

// Shadows reduced to "none" for chrome; modal-only depth retained.
// Glow variants neutralized — trading tools use borders, not glows.
export const S = {
  sm: 'none',
  md: 'none',
  lg: '0 4px 16px rgba(0,0,0,0.4)', // reserved for modals/popovers
  card: 'none',
  glow: 'none',
  bullGlow: 'none',
  bearGlow: 'none',
  brandGlow: 'none',
  depth1: 'none',
  depth2: 'none',
  depth3: '0 8px 24px rgba(0,0,0,0.5)', // reserved for modals only
  ambient: 'none',
  innerLight: 'none',
} as const;

// Glass variants are flattened to a single panel style.
// All variants now reference the same simple panel — solid background, 1px border, no shadow.
// Field names preserved for backwards compat across pages; visual variety removed intentionally.
const _PANEL: React.CSSProperties = {
  background: '#0a0a0f',
  border: '1px solid rgba(255,255,255,0.06)',
};
export const Glass = {
  card: _PANEL,
  nav: _PANEL,
  elevated: _PANEL,
  crystal: _PANEL,
  liquid: _PANEL,
  frosted: _PANEL,
  diamond: _PANEL,
  void: _PANEL,
} as const;

export const F = {
  xs: 11,
  sm: 12,
  base: 13,
  md: 14,
  lg: 16,
  xl: 18,
  '2xl': 22,
  '3xl': 28,
  '4xl': 36,
} as const;

/** Transition shorthand */
export const T = 'transition: all 0.15s ease;';

/** Spacing scale (4px base) */
export const SP = { 0: 0, 1: 4, 2: 8, 3: 12, 4: 16, 5: 20, 6: 24, 8: 32, 10: 40, 12: 48, 16: 64, 20: 80 } as const;

/** Z-index layers */
export const Z = { base: 1, dropdown: 300, sidebar: 350, modal: 400, toast: 500, tooltip: 600 } as const;

/** Responsive breakpoints (px) */
export const BP = { sm: 640, md: 768, lg: 1024, xl: 1280, '2xl': 1536 } as const;

/** Motion tokens — all variants use the same fast linear-ease.
 *  Springs/bouncy reduced to plain easing (still typed as such for backwards compat).
 *  Trading tools should feel predictable, not playful. */
export const M = {
  fast: { duration: 0.12, ease: [0.25, 0.1, 0.25, 1] as number[] },
  normal: { duration: 0.12, ease: [0.25, 0.1, 0.25, 1] as number[] },
  slow: { duration: 0.18, ease: [0.25, 0.1, 0.25, 1] as number[] },
  spring: { type: 'spring' as const, stiffness: 600, damping: 60 }, // overdamped → no bounce
  bouncy: { type: 'spring' as const, stiffness: 600, damping: 60 }, // overdamped → no bounce
} as const;

/** Gradient tokens — almost all flattened to solid surface colors.
 *  Decorative gradients (mesh/prismatic/iridescent/aurora/celestial) are now solid #050508.
 *  Trading tools don't use atmospheric gradients on chrome. */
export const G = {
  brand: 'linear-gradient(135deg, #00cc88 0%, #00e699 100%)', // kept for charts/CTAs only
  brandSubtle: 'rgba(0,204,136,0.10)',
  bull: '#00cc88',
  bear: '#ff4466',
  surface: '#0a0a0f',
  hero: '#050508',
  card: '#0a0a0f',
  mesh: '#050508',
  prismatic: '#0a0a0f',
  iridescent: '#0a0a0f',
  aurora: '#0a0a0f',
  celestial: '#050508',
} as const;

/** Format a number as USD */
export function fmtUsd(n: number | null | undefined, decimals = 2): string {
  if (n == null || isNaN(n)) return '—';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: decimals,
    minimumFractionDigits: decimals,
  }).format(n);
}

/** Format a percentage */
export function fmtPct(n: number | null | undefined, decimals = 1): string {
  if (n == null || isNaN(n)) return '—';
  const sign = n > 0 ? '+' : '';
  return `${sign}${n.toFixed(decimals)}%`;
}

/** Return a CSS rgba string for any hex color at the given opacity (0-1) */
export function alpha(hex: string, opacity: number): string {
  const h = hex.replace('#', '');
  const r = parseInt(h.substring(0, 2), 16);
  const g = parseInt(h.substring(2, 4), 16);
  const b = parseInt(h.substring(4, 6), 16);
  return `rgba(${r},${g},${b},${opacity})`;
}

/** Format a relative timestamp */
export function timeAgo(isoOrTs: string | number | null | undefined): string {
  if (!isoOrTs) return '';
  try {
    const ts = typeof isoOrTs === 'number' ? isoOrTs * 1000 : new Date(isoOrTs).getTime();
    const diff = Math.floor((Date.now() - ts) / 1000);
    if (diff < 5) return 'just now';
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  } catch {
    return '';
  }
}
