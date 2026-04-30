'use client';

import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { C, F } from '../src/theme';

/**
 * SecondaryNav — contextual sub-navigation rendered just below the top nav.
 *
 * Mirrors Hyperliquid's pattern: top nav has primary sections, then each
 * section has its own tab row. WAGMI's Portfolio and Co-Pilot sections are
 * actually multi-page experiences; this component flattens them into a tab
 * strip without touching the underlying pages.
 *
 * Decision logic lives here: pick which sub-nav to render based on URL.
 * If no match, returns null (no secondary nav).
 */

type SubItem = {
  href: string;
  label: string;
  match: (path: string) => boolean;
};

type SubGroup = {
  /** Identifier used by Layout for caching/animations (not user-visible) */
  key: string;
  /** Top-nav section this group belongs to (drives the wrapper tone) */
  parentLabel: string;
  /** Predicate: does the current route match this group? */
  matchesRoute: (path: string) => boolean;
  /** Tab items shown when this group is active */
  items: SubItem[];
};

const PORTFOLIO_GROUP: SubGroup = {
  key: 'portfolio',
  parentLabel: 'Portfolio',
  matchesRoute: (p) =>
    p.startsWith('/portfolio') ||
    p.startsWith('/dashboard') ||
    p.startsWith('/results') ||
    p.startsWith('/performance') ||
    p.startsWith('/forensics') ||
    p.startsWith('/counterfactuals'),
  items: [
    { href: '/dashboard', label: 'Overview', match: (p) => p === '/dashboard' || p === '/portfolio' || p.startsWith('/portfolio') },
    { href: '/results', label: 'History', match: (p) => p.startsWith('/results') },
    { href: '/forensics', label: 'Forensics', match: (p) => p.startsWith('/forensics') },
    { href: '/counterfactuals', label: 'Counterfactuals', match: (p) => p.startsWith('/counterfactuals') },
    { href: '/performance', label: 'Performance', match: (p) => p.startsWith('/performance') },
  ],
};

const COPILOT_GROUP: SubGroup = {
  key: 'copilot',
  parentLabel: 'Co-Pilot',
  matchesRoute: (p) =>
    p.startsWith('/live') ||
    p.startsWith('/ai-decisions') ||
    p.startsWith('/agent-intelligence') ||
    p.startsWith('/llm-audit') ||
    p.startsWith('/reasoning') ||
    p.startsWith('/strategies') ||
    p.startsWith('/backtest') ||
    p.startsWith('/copy-trade'),
  items: [
    { href: '/live', label: 'Live', match: (p) => p === '/live' || p.startsWith('/live') },
    { href: '/ai-decisions', label: 'Decisions', match: (p) => p.startsWith('/ai-decisions') || p.startsWith('/reasoning') },
    { href: '/agent-intelligence', label: 'Agents', match: (p) => p.startsWith('/agent-intelligence') || p.startsWith('/llm-audit') },
    { href: '/strategies', label: 'Strategies', match: (p) => p.startsWith('/strategies') },
    { href: '/backtest', label: 'Backtest', match: (p) => p.startsWith('/backtest') },
    { href: '/copy-trade', label: 'Sniper / Copy', match: (p) => p.startsWith('/copy-trade') },
  ],
};

const LEARN_GROUP: SubGroup = {
  key: 'learn',
  parentLabel: 'Learn',
  matchesRoute: (p) =>
    p.startsWith('/learn') || p.startsWith('/masterclass') || p.startsWith('/thesis'),
  items: [
    { href: '/learn', label: 'Getting Started', match: (p) => p === '/learn' || p.startsWith('/learn') },
    { href: '/masterclass', label: 'Masterclass', match: (p) => p.startsWith('/masterclass') },
    { href: '/thesis', label: 'Thesis', match: (p) => p.startsWith('/thesis') },
  ],
};

const GROUPS = [PORTFOLIO_GROUP, COPILOT_GROUP, LEARN_GROUP];

export default function SecondaryNav() {
  const router = useRouter();
  const path = router.asPath || '/';
  const group = GROUPS.find((g) => g.matchesRoute(path));
  if (!group) return null;

  return (
    <nav
      role="navigation"
      aria-label={`${group.parentLabel} sub-navigation`}
      style={{
        background: '#070710',
        borderBottom: `1px solid ${C.border}`,
        padding: '0 16px',
      }}
    >
      <div
        style={{
          maxWidth: 1440,
          margin: '0 auto',
          display: 'flex',
          alignItems: 'center',
          gap: 0,
          minHeight: 36,
          overflowX: 'auto',
        }}
      >
        {group.items.map((it) => {
          const active = it.match(path);
          return (
            <Link
              key={it.href}
              href={it.href}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                height: 36,
                padding: '0 12px',
                fontSize: F.xs,
                fontWeight: 500,
                color: active ? C.text : C.textSub,
                textDecoration: 'none',
                borderBottom: `2px solid ${active ? C.brand : 'transparent'}`,
                marginBottom: -1,
                transition: 'color 120ms ease-out, border-color 120ms ease-out',
                whiteSpace: 'nowrap',
                fontFamily: 'JetBrains Mono, monospace',
                letterSpacing: 0.02,
              }}
              onMouseEnter={(e) => {
                if (!active) (e.currentTarget as HTMLAnchorElement).style.color = C.text;
              }}
              onMouseLeave={(e) => {
                if (!active) (e.currentTarget as HTMLAnchorElement).style.color = C.textSub;
              }}
            >
              {it.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
