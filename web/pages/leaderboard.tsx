import React from 'react';
import Head from 'next/head';
import { C, F, R } from '../src/theme';

/**
 * /leaderboard — placeholder.
 * Reserves the route slot in the HL-style nav. Links out to Hyperliquid's
 * public leaderboard for now. WAGMI's bot can be benchmarked against it later.
 */
export default function LeaderboardPage() {
  return (
    <>
      <Head>
        <title>Leaderboard — WAGMI</title>
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
        <h1 style={{ fontSize: F['2xl'], fontWeight: 700, color: C.text, margin: 0 }}>
          Leaderboard
        </h1>
        <p
          style={{
            fontSize: F.md,
            color: C.textSub,
            lineHeight: 1.6,
            marginTop: 12,
            marginBottom: 24,
          }}
        >
          The trader leaderboard lives on Hyperliquid. WAGMI&apos;s bot will be tracked alongside
          public traders in a future iteration of this page.
        </p>
        <a
          href="https://app.hyperliquid.xyz/leaderboard"
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
          }}
        >
          Open Hyperliquid Leaderboard →
        </a>
      </div>
    </>
  );
}
