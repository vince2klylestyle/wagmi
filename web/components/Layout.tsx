'use client';

import React from 'react';
import { C, R } from '../src/theme';
import TopNav from './TopNav';

/**
 * Layout — HL-style horizontal nav at top, content below.
 * Sidebar removed at top level; if any pages need a left rail
 * (e.g. /trade market list), it lives inside the page itself.
 *
 * Phase 2 of the HL reshape — see audits/2026-04-29/05_ui_reshape_hyperliquid_style.md.
 */

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        minHeight: '100vh',
        background: C.bg,
        fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Skip-to-content for accessibility */}
      <a href="#main-content" className="skip-to-content">
        Skip to content
      </a>

      <TopNav />

      <main
        id="main-content"
        role="main"
        className="wagmi-main"
        style={{
          flex: 1,
          width: '100%',
          maxWidth: 1440,
          margin: '0 auto',
          padding: '20px 16px 40px',
        }}
      >
        {children}
      </main>

      <footer
        style={{
          borderTop: `1px solid ${C.border}`,
          background: '#050508',
          padding: '16px 16px 24px',
        }}
      >
        <div
          style={{
            maxWidth: 1440,
            margin: '0 auto',
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
            alignItems: 'center',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                width: 18,
                height: 18,
                borderRadius: R.xs,
                border: `1px solid ${C.brand}`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 10,
                fontWeight: 800,
                color: C.brand,
                fontFamily: 'JetBrains Mono, monospace',
              }}
            >
              W
            </span>
            <span style={{ fontSize: 12, fontWeight: 700, color: C.textSub, letterSpacing: -0.2 }}>
              WAGMI
            </span>
          </div>
          <p
            style={{
              margin: 0,
              fontSize: 11,
              color: C.muted,
              textAlign: 'center',
              lineHeight: 1.6,
              maxWidth: 560,
            }}
          >
            AI-driven market analysis for informational purposes only. Not financial advice. Crypto
            carries significant risk. Historical results don&apos;t predict future performance.
          </p>
          <p style={{ margin: 0, fontSize: 10, color: C.faint }}>&copy; 2026 WAGMI</p>
        </div>
      </footer>
    </div>
  );
}
