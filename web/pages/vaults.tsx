import React from 'react';
import Head from 'next/head';
import { C, F, R } from '../src/theme';

/**
 * /vaults — placeholder.
 * WAGMI does not currently run a public vault. This page reserves the route
 * in the HL-style top-nav and links out to Hyperliquid's vaults until/if
 * WAGMI ships its own.
 */
export default function VaultsPage() {
  return (
    <>
      <Head>
        <title>Vaults — WAGMI</title>
      </Head>
      <div
        style={{
          background: '#0a0a0f',
          border: `1px solid ${C.border}`,
          borderRadius: R.lg,
          padding: 32,
          maxWidth: 720,
          margin: '40px auto',
        }}
      >
        <h1 style={{ fontSize: F['2xl'], fontWeight: 700, color: C.text, margin: 0 }}>Vaults</h1>
        <p
          style={{
            fontSize: F.md,
            color: C.textSub,
            lineHeight: 1.6,
            marginTop: 12,
            marginBottom: 24,
          }}
        >
          WAGMI does not currently operate a public vault. To deposit into a Hyperliquid-native
          vault, visit the Hyperliquid app directly.
        </p>
        <a
          href="https://app.hyperliquid.xyz/vaults"
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: 'inline-block',
            padding: '10px 16px',
            border: `1px solid ${C.brand}`,
            borderRadius: R.sm,
            color: C.brand,
            fontSize: F.sm,
            fontWeight: 600,
            textDecoration: 'none',
            transition: 'background 120ms ease-out',
          }}
        >
          Open Hyperliquid Vaults →
        </a>
      </div>
    </>
  );
}
