'use client';

import React, { useEffect, useState, useCallback } from 'react';
import Head from 'next/head';
import { motion, AnimatePresence } from 'framer-motion';
import { C, R, F, S, Glass, SP } from '../src/theme';
import { fadeUp, staggerContainer, orchestratedContainer, cinematicReveal, magneticHover } from '../src/animations';
import { TradingChart } from '../components/charts/TradingChart';
import type { ZoneBand, TradeMarker, SignalOverlay } from '../components/charts/TradingChart';
import { GeometricBG } from '../components/ui/GeometricBG';
import { GlowOrb } from '../components/ui/GlowOrb';
import { resolveApiBase, apiFetch } from '../src/api';
import type { TradeRecord, TradeHistoryResponse } from '../src/types';

// ── Types ────────────────────────────────────────────────────────────────────

type Signal = {
  symbol: string;
  label: string;
  score: number;
  price: number;
  sma20: number;
  sma50: number;
  atr14: number;
  atr_pct?: number;
  rsi14?: number;
  vol_spike?: boolean;
  zones: { deepAccum: number; accum: number; distrib: number; safeDistrib: number };
};

type SignalsPayload = {
  last_updated?: string;
  regime?: string;
  signals?: Record<string, Signal>;
};

// ── Constants ────────────────────────────────────────────────────────────────

const SYMBOLS = ['BTC', 'SOL', 'HYPE'] as const;

// ── Helpers ──────────────────────────────────────────────────────────────────

function buildZones(signal: Signal | undefined): ZoneBand[] {
  if (!signal?.zones) return [];
  const z = signal.zones;
  const zones: ZoneBand[] = [];
  if (z.deepAccum > 0 && z.accum > 0) {
    zones.push({ label: 'Deep Support', upper: z.accum, lower: z.deepAccum, color: '#16a34a', type: 'support' });
  }
  if (z.accum > 0 && z.distrib > 0) {
    zones.push({ label: 'Accumulation', upper: z.distrib, lower: z.accum, color: '#22c55e', type: 'support' });
  }
  if (z.distrib > 0 && z.safeDistrib > 0) {
    zones.push({ label: 'Distribution', upper: z.safeDistrib, lower: z.distrib, color: '#ef4444', type: 'resistance' });
  }
  return zones;
}

function buildSignalLevels(signal: Signal | undefined): SignalOverlay | null {
  if (!signal) return null;
  const z = signal.zones;
  return {
    entry: signal.price,
    sl: z.deepAccum || undefined,
    tp1: z.distrib || undefined,
    tp2: z.safeDistrib || undefined,
  };
}

function buildTradeMarkers(trades: TradeRecord[], symbol: string): TradeMarker[] {
  return trades
    .filter((t) => t.symbol?.includes(symbol) && t.entry && t.exit)
    .slice(0, 30) // limit to last 30
    .flatMap((t, i) => {
      const markers: TradeMarker[] = [];
      // We don't have exact timestamps for entry/exit, so approximate
      const now = Date.now() / 1000;
      const durationSec = (t.duration_h ?? 1) * 3600;
      const exitTime = now - i * 86400; // space them out for visibility
      const entryTime = exitTime - durationSec;

      if (t.entry) {
        markers.push({
          time: Math.floor(entryTime),
          type: 'entry',
          side: t.side as 'BUY' | 'SELL',
          price: t.entry,
          label: `${t.side} @ ${t.entry.toFixed(2)}`,
        });
      }
      if (t.exit) {
        markers.push({
          time: Math.floor(exitTime),
          type: 'exit',
          side: t.side as 'BUY' | 'SELL',
          price: t.exit,
          pnl: t.pnl ?? undefined,
          label: `Exit ${t.pnl ? (t.pnl > 0 ? '+' : '') + t.pnl.toFixed(2) + '%' : ''}`,
        });
      }
      return markers;
    });
}

// ── Stat Badge ───────────────────────────────────────────────────────────────

function StatBadge({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 2,
      padding: '8px 14px',
      ...Glass.card,
      borderRadius: R.md,
      minWidth: 80,
    }}>
      <span style={{ fontSize: 9, fontWeight: 600, color: C.muted, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
        {label}
      </span>
      <span style={{
        fontSize: F.base,
        fontWeight: 800,
        color: color || C.text,
        fontFamily: "'JetBrains Mono', monospace",
        fontVariantNumeric: 'tabular-nums',
      }}>
        {value}
      </span>
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function ChartsPage() {
  const [activeSymbol, setActiveSymbol] = useState<string>('BTC');
  const [signals, setSignals] = useState<Record<string, Signal>>({});
  const [trades, setTrades] = useState<TradeRecord[]>([]);
  const [regime, setRegime] = useState('unknown');
  const [loading, setLoading] = useState(true);
  const [layout, setLayout] = useState<'single' | 'split'>('single');

  const apiBase = resolveApiBase();

  // Fetch signals and trades
  useEffect(() => {
    let mounted = true;

    async function load() {
      setLoading(true);
      const [sigData, tradeData] = await Promise.all([
        apiFetch<SignalsPayload>('/v1/signals'),
        apiFetch<TradeHistoryResponse>('/v1/trades/history?limit=100'),
      ]);

      if (!mounted) return;

      if (sigData?.signals) setSignals(sigData.signals);
      if (sigData?.regime) setRegime(sigData.regime);
      if (tradeData?.trades) setTrades(tradeData.trades);
      setLoading(false);
    }

    load();

    // Refresh every 30s
    const interval = setInterval(load, 30_000);
    return () => { mounted = false; clearInterval(interval); };
  }, []);

  const activeSignal = signals[activeSymbol];
  const activeZones = buildZones(activeSignal);
  const activeLevels = buildSignalLevels(activeSignal);
  const activeMarkers = buildTradeMarkers(trades, activeSymbol);

  // Quick stats for the active symbol
  const symbolTrades = trades.filter((t) => t.symbol?.includes(activeSymbol));
  const wins = symbolTrades.filter((t) => t.outcome === 'WIN').length;
  const total = symbolTrades.length;
  const winRate = total > 0 ? ((wins / total) * 100).toFixed(0) : '—';
  const totalPnl = symbolTrades.reduce((acc, t) => acc + (t.pnl ?? 0), 0);
  const avgRR = symbolTrades.length > 0
    ? (symbolTrades.reduce((acc, t) => acc + (t.rr_achieved ?? 0), 0) / symbolTrades.length).toFixed(2)
    : '—';

  const REGIME_COLOR: Record<string, string> = {
    trend: C.bull, range: '#60a5fa', panic: C.bear,
    high_volatility: '#fbbf24', low_liquidity: '#64748b',
    news_dislocation: '#7c3aed', unknown: C.muted, neutral: C.muted,
  };
  const regimeKey = regime.toLowerCase().replace(' ', '_');
  const regimeColor = REGIME_COLOR[regimeKey] || C.muted;

  return (
    <>
      <Head>
        <title>Charts | WAGMI</title>
      </Head>

      <div style={{ position: 'relative', minHeight: '100vh' }}>
        {/* Atmospheric background */}
        <GeometricBG variant="wave" opacity={0.02} />
        <GlowOrb color="rgba(99,102,241,0.08)" size={450} top="5%" right="10%" blur={120} duration={22} />

        <motion.div
          initial="hidden"
          animate="show"
          variants={orchestratedContainer}
          style={{ display: 'flex', flexDirection: 'column', gap: 20 }}
        >
          {/* ── Page header ──────────────────────────────────────────────── */}
          <motion.div variants={fadeUp} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
            <div>
              <h1 style={{ fontSize: F['2xl'], fontWeight: 800, color: C.text, margin: 0, letterSpacing: -0.5 }}>
                Live Charts
              </h1>
              <p style={{ fontSize: F.sm, color: C.muted, margin: '4px 0 0' }}>
                Real-time price action with support/resistance zones, trade entries, and signal levels
              </p>
            </div>

            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              {/* Regime badge */}
              <div style={{
                padding: '5px 12px',
                borderRadius: R.pill,
                background: `${regimeColor}15`,
                border: `1px solid ${regimeColor}40`,
                fontSize: 11,
                fontWeight: 700,
                color: regimeColor,
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
              }}>
                {regime}
              </div>

              {/* Layout toggle */}
              <div style={{ display: 'flex', border: `1px solid ${C.border}`, borderRadius: R.sm, overflow: 'hidden' }}>
                <button
                  onClick={() => setLayout('single')}
                  style={{
                    padding: '5px 10px',
                    background: layout === 'single' ? `${C.brand}20` : 'transparent',
                    border: 'none',
                    color: layout === 'single' ? C.brand : C.muted,
                    fontSize: 11,
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Single
                </button>
                <button
                  onClick={() => setLayout('split')}
                  style={{
                    padding: '5px 10px',
                    background: layout === 'split' ? `${C.brand}20` : 'transparent',
                    border: 'none',
                    borderLeft: `1px solid ${C.border}`,
                    color: layout === 'split' ? C.brand : C.muted,
                    fontSize: 11,
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Split
                </button>
              </div>
            </div>
          </motion.div>

          {/* ── Symbol selector + stats strip ──────────────────────────── */}
          <motion.div variants={fadeUp} style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
            {/* Symbol tabs */}
            <div style={{ display: 'flex', gap: 4 }}>
              {SYMBOLS.map((sym) => {
                const sig = signals[sym];
                const isActive = sym === activeSymbol;
                const price = sig?.price;
                return (
                  <motion.button
                    key={sym}
                    onClick={() => setActiveSymbol(sym)}
                    {...magneticHover}
                    style={{
                      padding: '10px 18px',
                      ...Glass[isActive ? 'crystal' : 'card'],
                      borderRadius: R.md,
                      border: `1px solid ${isActive ? C.brand + '60' : 'rgba(255,255,255,0.04)'}`,
                      cursor: 'pointer',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'flex-start',
                      gap: 2,
                      minWidth: 100,
                      boxShadow: isActive ? `0 0 20px ${C.brand}15` : 'none',
                      transition: 'all 0.2s ease',
                    }}
                  >
                    <span style={{ fontSize: F.sm, fontWeight: 800, color: isActive ? C.text : C.textSub }}>
                      {sym}
                    </span>
                    {price ? (
                      <span style={{
                        fontSize: 11,
                        fontWeight: 600,
                        color: C.muted,
                        fontFamily: "'JetBrains Mono', monospace",
                        fontVariantNumeric: 'tabular-nums',
                      }}>
                        ${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </span>
                    ) : (
                      <span style={{ fontSize: 10, color: C.faint }}>Loading...</span>
                    )}
                  </motion.button>
                );
              })}
            </div>

            {/* Stats strip */}
            <div style={{ display: 'flex', gap: 8, marginLeft: 'auto', flexWrap: 'wrap' }}>
              <StatBadge label="Win Rate" value={`${winRate}%`} color={Number(winRate) >= 50 ? '#4ade80' : '#f87171'} />
              <StatBadge label="Total PnL" value={`${totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(2)}%`} color={totalPnl >= 0 ? '#4ade80' : '#f87171'} />
              <StatBadge label="Avg R:R" value={avgRR} color={Number(avgRR) >= 1 ? '#4ade80' : C.muted} />
              <StatBadge label="Trades" value={String(total)} />
            </div>
          </motion.div>

          {/* ── Chart area ────────────────────────────────────────────── */}
          <AnimatePresence mode="wait">
            {layout === 'single' ? (
              <motion.div key="single" variants={fadeUp} initial="hidden" animate="show" exit="hidden">
                <TradingChart
                  symbol={activeSymbol}
                  height={620}
                  zones={activeZones}
                  signalLevels={activeLevels}
                  tradeMarkers={activeMarkers}
                  title={`${activeSymbol}/USDT`}
                  subtitle={activeSignal ? `Score: ${activeSignal.score}/100 · RSI: ${activeSignal.rsi14?.toFixed(0) ?? '—'} · ATR: ${activeSignal.atr_pct?.toFixed(2) ?? '—'}%` : undefined}
                />
              </motion.div>
            ) : (
              <motion.div
                key="split"
                variants={staggerContainer}
                initial="hidden"
                animate="show"
                exit="hidden"
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(480px, 1fr))',
                  gap: 16,
                }}
              >
                {SYMBOLS.map((sym) => {
                  const sig = signals[sym];
                  return (
                    <motion.div key={sym} variants={fadeUp}>
                      <TradingChart
                        symbol={sym}
                        height={380}
                        zones={buildZones(sig)}
                        signalLevels={buildSignalLevels(sig)}
                        tradeMarkers={buildTradeMarkers(trades, sym)}
                        title={`${sym}/USDT`}
                        defaultTimeframe="1h"
                        timeframes={['15m', '1h', '4h', '1d']}
                      />
                    </motion.div>
                  );
                })}
              </motion.div>
            )}
          </AnimatePresence>

          {/* ── Zone legend / key ──────────────────────────────────────── */}
          <motion.div
            variants={fadeUp}
            style={{
              ...Glass.card,
              borderRadius: R.lg,
              padding: '16px 20px',
              display: 'flex',
              gap: 20,
              flexWrap: 'wrap',
              alignItems: 'center',
            }}
          >
            <span style={{ fontSize: 11, fontWeight: 700, color: C.muted, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Chart Key
            </span>
            {[
              { color: '#22c55e', label: 'Support / Buy Zone', style: 'dashed' },
              { color: '#ef4444', label: 'Resistance / Sell Zone', style: 'dashed' },
              { color: '#f59e0b', label: 'Signal Entry', style: 'solid' },
              { color: '#34d399', label: 'Take Profit (TP1/TP2)', style: 'solid' },
              { color: '#ef4444', label: 'Stop Loss', style: 'solid' },
            ].map((item) => (
              <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{
                  width: 20,
                  height: 3,
                  background: item.color,
                  borderRadius: 1,
                  ...(item.style === 'dashed' ? { backgroundImage: `repeating-linear-gradient(90deg, ${item.color} 0px, ${item.color} 4px, transparent 4px, transparent 8px)`, background: 'none' } : {}),
                }} />
                <span style={{ fontSize: 10, fontWeight: 600, color: C.textSub }}>{item.label}</span>
              </div>
            ))}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <svg width="12" height="12" viewBox="0 0 12 12"><polygon points="6,1 11,11 1,11" fill="#22c55e" /></svg>
              <span style={{ fontSize: 10, fontWeight: 600, color: C.textSub }}>Buy Entry</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <svg width="12" height="12" viewBox="0 0 12 12"><polygon points="6,11 11,1 1,1" fill="#ef4444" /></svg>
              <span style={{ fontSize: 10, fontWeight: 600, color: C.textSub }}>Sell / Exit</span>
            </div>
          </motion.div>
        </motion.div>
      </div>
    </>
  );
}
