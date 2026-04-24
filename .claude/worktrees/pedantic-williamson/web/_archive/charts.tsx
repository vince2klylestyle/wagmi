'use client';

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import Head from 'next/head';
import { motion, AnimatePresence } from 'framer-motion';
import { C, R, F, S, Glass, SP, G, alpha } from '../src/theme';
import { fadeUp, staggerContainer, orchestratedContainer, cinematicReveal, magneticHover, hoverGlow, viewportTrigger, scrollStagger } from '../src/animations';
import { TradingChart } from '../components/charts/TradingChart';
import type { ZoneBand, TradeMarker, SignalOverlay } from '../components/charts/TradingChart';
import { GeometricBG } from '../components/ui/GeometricBG';
import { GlowOrb } from '../components/ui/GlowOrb';
import { resolveApiBase, apiFetch } from '../src/api';
import type { TradeRecord, TradeHistoryResponse, LlmMarketView } from '../src/types';

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

// ── Section Header ──────────────────────────────────────────────────────────

function SectionTitle({ title, subtitle, icon }: { title: string; subtitle?: string; icon: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
      <span style={{ fontSize: 18 }}>{icon}</span>
      <div>
        <h2 style={{ fontSize: F.lg, fontWeight: 800, color: C.text, margin: 0, letterSpacing: -0.3 }}>{title}</h2>
        {subtitle && <p style={{ fontSize: F.xs, color: C.muted, margin: '2px 0 0' }}>{subtitle}</p>}
      </div>
    </div>
  );
}

// ── Gauge Component ─────────────────────────────────────────────────────────

function Gauge({ value, max, label, color, size = 80 }: { value: number; max: number; label: string; color: string; size?: number }) {
  const pct = Math.min(Math.max(value / max, 0), 1);
  const r = (size - 8) / 2;
  const circumference = Math.PI * r;
  const dashOffset = circumference * (1 - pct);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
      <svg width={size} height={size / 2 + 8} viewBox={`0 0 ${size} ${size / 2 + 8}`}>
        <path d={`M 4 ${size / 2 + 4} A ${r} ${r} 0 0 1 ${size - 4} ${size / 2 + 4}`}
          fill="none" stroke={C.faint} strokeWidth={6} strokeLinecap="round" />
        <path d={`M 4 ${size / 2 + 4} A ${r} ${r} 0 0 1 ${size - 4} ${size / 2 + 4}`}
          fill="none" stroke={color} strokeWidth={6} strokeLinecap="round"
          strokeDasharray={circumference} strokeDashoffset={dashOffset}
          style={{ transition: 'stroke-dashoffset 0.8s ease' }} />
        <text x={size / 2} y={size / 2} textAnchor="middle" fill={color}
          fontSize={size > 70 ? 16 : 13} fontWeight={800} fontFamily="'JetBrains Mono', monospace">
          {value.toFixed(0)}
        </text>
      </svg>
      <span style={{ fontSize: 9, fontWeight: 700, color: C.muted, textTransform: 'uppercase', letterSpacing: '0.08em' }}>{label}</span>
    </div>
  );
}

// ── Mini Sparkline Bar ──────────────────────────────────────────────────────

function MiniBar({ value, max, color, width = 60 }: { value: number; max: number; color: string; width?: number }) {
  const pct = Math.min(Math.max(value / max, 0), 1) * 100;
  return (
    <div style={{ width, height: 6, background: C.faint, borderRadius: 3, overflow: 'hidden' }}>
      <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 3, transition: 'width 0.6s ease' }} />
    </div>
  );
}

// ── Pill Tag ────────────────────────────────────────────────────────────────

function PillTag({ label, color }: { label: string; color: string }) {
  return (
    <span style={{
      padding: '3px 8px', borderRadius: R.pill, background: alpha(color, 0.12),
      border: `1px solid ${alpha(color, 0.25)}`, fontSize: 9, fontWeight: 700,
      color, textTransform: 'uppercase', letterSpacing: '0.06em',
    }}>{label}</span>
  );
}

// ── Glass Panel ─────────────────────────────────────────────────────────────

function GlassPanel({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <motion.div variants={fadeUp} style={{ ...Glass.card, borderRadius: R.lg, padding: '20px 24px', ...style }}>
      {children}
    </motion.div>
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
  const [marketView, setMarketView] = useState<LlmMarketView | null>(null);
  // Position calculator state
  const [calcAccount, setCalcAccount] = useState(10000);
  const [calcRisk, setCalcRisk] = useState(2);

  const apiBase = resolveApiBase();

  // Fetch signals, trades, and market view
  useEffect(() => {
    let mounted = true;

    async function load() {
      setLoading(true);
      const [sigData, tradeData, mvData] = await Promise.all([
        apiFetch<SignalsPayload>('/v1/signals'),
        apiFetch<TradeHistoryResponse>('/v1/trades/history?limit=100'),
        apiFetch<LlmMarketView>('/v1/llm/market-view'),
      ]);

      if (!mounted) return;

      if (sigData?.signals) setSignals(sigData.signals);
      if (sigData?.regime) setRegime(sigData.regime);
      if (tradeData?.trades) setTrades(tradeData.trades);
      if (mvData) setMarketView(mvData);
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

  // ── Derived data for feature panels ──────────────────────────────────────
  const allSignals = Object.entries(signals).map(([sym, sig]) => ({ sym, ...sig }));

  // Compute trend status from SMA crossover
  const trendStatus = useMemo(() => {
    if (!activeSignal) return { label: 'Unknown', color: C.muted };
    if (activeSignal.sma20 > activeSignal.sma50) return { label: 'Bullish', color: C.bull };
    if (activeSignal.sma20 < activeSignal.sma50) return { label: 'Bearish', color: C.bear };
    return { label: 'Neutral', color: C.muted };
  }, [activeSignal]);

  // RSI interpretation
  const rsiData = useMemo(() => {
    const rsi = activeSignal?.rsi14 ?? 50;
    let label = 'Neutral';
    let color = C.muted;
    if (rsi >= 70) { label = 'Overbought'; color = C.bear; }
    else if (rsi >= 60) { label = 'Bullish'; color = C.bull; }
    else if (rsi <= 30) { label = 'Oversold'; color = C.bull; }
    else if (rsi <= 40) { label = 'Bearish'; color = C.bear; }
    return { value: rsi, label, color };
  }, [activeSignal]);

  // Volatility interpretation
  const volData = useMemo(() => {
    const atr = activeSignal?.atr_pct ?? 2;
    let label = 'Normal';
    let color = '#60a5fa';
    if (atr >= 5) { label = 'Extreme'; color = C.bear; }
    else if (atr >= 3) { label = 'High'; color = C.warn; }
    else if (atr <= 1) { label = 'Low'; color = C.bull; }
    return { value: atr, label, color };
  }, [activeSignal]);

  // Build key levels table
  const keyLevels = useMemo(() => {
    if (!activeSignal) return [];
    const price = activeSignal.price;
    const z = activeSignal.zones;
    const levels: { label: string; price: number; type: string; distance: number; color: string }[] = [];
    if (z.deepAccum > 0) levels.push({ label: 'Deep Support', price: z.deepAccum, type: 'support', distance: ((z.deepAccum - price) / price) * 100, color: '#16a34a' });
    if (z.accum > 0) levels.push({ label: 'Accumulation', price: z.accum, type: 'support', distance: ((z.accum - price) / price) * 100, color: '#22c55e' });
    if (activeSignal.sma50 > 0) levels.push({ label: 'SMA 50', price: activeSignal.sma50, type: activeSignal.sma50 > price ? 'resistance' : 'support', distance: ((activeSignal.sma50 - price) / price) * 100, color: '#60a5fa' });
    if (activeSignal.sma20 > 0) levels.push({ label: 'SMA 20', price: activeSignal.sma20, type: activeSignal.sma20 > price ? 'resistance' : 'support', distance: ((activeSignal.sma20 - price) / price) * 100, color: '#818cf8' });
    if (z.distrib > 0) levels.push({ label: 'Distribution', price: z.distrib, type: 'resistance', distance: ((z.distrib - price) / price) * 100, color: '#f87171' });
    if (z.safeDistrib > 0) levels.push({ label: 'Safe Distribution', price: z.safeDistrib, type: 'resistance', distance: ((z.safeDistrib - price) / price) * 100, color: '#ef4444' });
    return levels.sort((a, b) => b.price - a.price);
  }, [activeSignal]);

  // Position size calculation
  const posCalc = useMemo(() => {
    if (!activeSignal) return null;
    const riskAmount = calcAccount * (calcRisk / 100);
    const slDistance = activeSignal.zones.deepAccum > 0
      ? Math.abs(activeSignal.price - activeSignal.zones.deepAccum) / activeSignal.price
      : (activeSignal.atr_pct ?? 2) / 100;
    const positionSize = slDistance > 0 ? riskAmount / slDistance : 0;
    const leverage = positionSize > 0 ? positionSize / calcAccount : 1;
    const coins = activeSignal.price > 0 ? positionSize / activeSignal.price : 0;
    return { riskAmount, slDistance: slDistance * 100, positionSize, leverage, coins };
  }, [activeSignal, calcAccount, calcRisk]);

  // Recent signals with outcomes
  const recentSignals = useMemo(() => {
    return symbolTrades.slice(0, 8).map((t) => ({
      symbol: t.symbol,
      side: t.side,
      entry: t.entry,
      exit: t.exit,
      pnl: t.pnl,
      outcome: t.outcome,
      strategy: t.strategy,
      confidence: t.confidence,
      rr: t.rr_achieved,
      duration: t.duration_h,
      llmAction: t.llm_action,
      regime: t.llm_regime,
    }));
  }, [symbolTrades]);

  // Correlation matrix (computed from trade PnL patterns)
  const correlationMatrix = useMemo(() => {
    const syms = ['BTC', 'SOL', 'HYPE'] as const;
    const matrix: Record<string, Record<string, number>> = {};
    syms.forEach((a) => {
      matrix[a] = {};
      syms.forEach((b) => {
        if (a === b) { matrix[a][b] = 1; return; }
        const tradesA = trades.filter((t) => t.symbol?.includes(a)).map((t) => t.pnl ?? 0);
        const tradesB = trades.filter((t) => t.symbol?.includes(b)).map((t) => t.pnl ?? 0);
        const n = Math.min(tradesA.length, tradesB.length);
        if (n < 3) { matrix[a][b] = 0; return; }
        const meanA = tradesA.slice(0, n).reduce((s, v) => s + v, 0) / n;
        const meanB = tradesB.slice(0, n).reduce((s, v) => s + v, 0) / n;
        let num = 0, denA = 0, denB = 0;
        for (let i = 0; i < n; i++) {
          const da = tradesA[i] - meanA, db = tradesB[i] - meanB;
          num += da * db; denA += da * da; denB += db * db;
        }
        matrix[a][b] = denA > 0 && denB > 0 ? num / Math.sqrt(denA * denB) : 0;
      });
    });
    return matrix;
  }, [trades]);

  // Price alerts (levels within 2% of current price)
  const priceAlerts = useMemo(() => {
    return keyLevels
      .filter((l) => Math.abs(l.distance) < 2 && Math.abs(l.distance) > 0.1)
      .sort((a, b) => Math.abs(a.distance) - Math.abs(b.distance));
  }, [keyLevels]);

  // AI bias
  const aiBias = useMemo(() => {
    if (marketView?.overall_bias) return marketView.overall_bias;
    if (marketView?.per_symbol?.[activeSymbol]) {
      const dec = marketView.per_symbol[activeSymbol];
      if (dec.action === 'proceed') return 'bullish';
      if (dec.action === 'flip') return 'bearish';
    }
    return 'neutral';
  }, [marketView, activeSymbol]);

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

          {/* ════════════════════════════════════════════════════════════════
              FEATURE PANELS — The real value below the chart
              ════════════════════════════════════════════════════════════════ */}

          {/* ── 1. AI Analysis Panel ───────────────────────────────────── */}
          <GlassPanel>
            <SectionTitle icon={'\u{1F9E0}'} title="AI Analysis" subtitle="Real-time AI market intelligence and directional bias" />
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 20, marginTop: 16 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                  <PillTag label={regime} color={regimeColor} />
                  <PillTag label={aiBias} color={aiBias === 'bullish' ? C.bull : aiBias === 'bearish' ? C.bear : C.brand} />
                  {activeSignal?.vol_spike && <PillTag label="VOL SPIKE" color={C.warn} />}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
                  <Gauge value={activeSignal?.score ?? 0} max={100} label="Signal Score" color={C.brand} size={90} />
                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
                    <div style={{ fontSize: F.xs, color: C.muted }}>AI Confidence</div>
                    <div style={{ fontSize: F['2xl'], fontWeight: 800, color: C.text, fontFamily: "'JetBrains Mono', monospace" }}>
                      {activeSignal?.score ?? '\u2014'}<span style={{ fontSize: F.sm, color: C.muted }}>/100</span>
                    </div>
                    <div style={{ fontSize: F.xs, color: C.textSub, lineHeight: 1.4 }}>
                      {marketView?.summary || `${activeSymbol} is currently in a ${regime} regime. AI is analyzing market conditions.`}
                    </div>
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div style={{ fontSize: F.xs, fontWeight: 700, color: C.muted, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Recent AI Decisions</div>
                {[
                  { label: 'Proceed (Go)', value: marketView?.decision_counts?.proceed ?? 0, color: C.bull, max: Math.max(marketView?.decision_counts?.total_recent ?? 1, 1) },
                  { label: 'Skip (Flat)', value: marketView?.decision_counts?.flat ?? 0, color: C.warn, max: Math.max(marketView?.decision_counts?.total_recent ?? 1, 1) },
                  { label: 'Reverse (Flip)', value: marketView?.decision_counts?.flip ?? 0, color: C.bear, max: Math.max(marketView?.decision_counts?.total_recent ?? 1, 1) },
                ].map((d) => (
                  <div key={d.label} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontSize: F.xs, color: C.textSub, minWidth: 100 }}>{d.label}</span>
                    <MiniBar value={d.value} max={d.max} color={d.color} width={120} />
                    <span style={{ fontSize: F.xs, fontWeight: 700, color: d.color, fontFamily: "'JetBrains Mono', monospace", minWidth: 20, textAlign: 'right' }}>{d.value}</span>
                  </div>
                ))}
                <div style={{ fontSize: 10, color: C.faint, marginTop: 4 }}>Total decisions: {marketView?.decision_counts?.total_recent ?? 0}</div>
              </div>
            </div>
          </GlassPanel>

          {/* ── 2. Technical Dashboard ─────────────────────────────────── */}
          <div>
            <SectionTitle icon={'\u{1F4CA}'} title="Technical Indicators" subtitle="Key technical analysis metrics for the selected asset" />
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginTop: 12 }}>
              <motion.div variants={fadeUp} style={{ ...Glass.card, borderRadius: R.lg, padding: 16, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
                <Gauge value={rsiData.value} max={100} label="RSI (14)" color={rsiData.color} size={90} />
                <PillTag label={rsiData.label} color={rsiData.color} />
                <span style={{ fontSize: 9, color: C.muted, textAlign: 'center' }}>
                  {rsiData.value >= 70 ? 'Consider taking profits' : rsiData.value <= 30 ? 'Potential bounce zone' : 'Neutral momentum'}
                </span>
              </motion.div>
              <motion.div variants={fadeUp} style={{ ...Glass.card, borderRadius: R.lg, padding: 16, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
                <div style={{ fontSize: 28, lineHeight: 1 }}>{trendStatus.label === 'Bullish' ? '\u2191' : trendStatus.label === 'Bearish' ? '\u2193' : '\u2194'}</div>
                <span style={{ fontSize: 9, fontWeight: 700, color: C.muted, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Trend</span>
                <PillTag label={trendStatus.label} color={trendStatus.color} />
                <div style={{ fontSize: 9, color: C.muted, textAlign: 'center' }}>
                  SMA20: {activeSignal?.sma20?.toLocaleString(undefined, { maximumFractionDigits: 0 }) ?? '\u2014'}<br />
                  SMA50: {activeSignal?.sma50?.toLocaleString(undefined, { maximumFractionDigits: 0 }) ?? '\u2014'}
                </div>
              </motion.div>
              <motion.div variants={fadeUp} style={{ ...Glass.card, borderRadius: R.lg, padding: 16, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
                <Gauge value={volData.value} max={8} label="ATR %" color={volData.color} size={90} />
                <PillTag label={volData.label} color={volData.color} />
                <span style={{ fontSize: 9, color: C.muted, textAlign: 'center' }}>
                  {volData.value >= 3 ? 'Wide stops needed' : volData.value <= 1 ? 'Tight range, small moves' : 'Standard volatility'}
                </span>
              </motion.div>
              <motion.div variants={fadeUp} style={{ ...Glass.card, borderRadius: R.lg, padding: 16, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
                <div style={{ fontSize: 28, lineHeight: 1 }}>{activeSignal?.vol_spike ? '\u26A0' : '\u2713'}</div>
                <span style={{ fontSize: 9, fontWeight: 700, color: C.muted, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Volume</span>
                <PillTag label={activeSignal?.vol_spike ? 'SPIKE' : 'Normal'} color={activeSignal?.vol_spike ? C.warn : C.bull} />
                <span style={{ fontSize: 9, color: C.muted, textAlign: 'center' }}>
                  {activeSignal?.vol_spike ? 'Unusual volume detected' : 'Volume within normal range'}
                </span>
              </motion.div>
            </div>
          </div>

          {/* ── 3. Key Levels Table ────────────────────────────────────── */}
          <GlassPanel>
            <SectionTitle icon={'\u{1F4CD}'} title="Key Price Levels" subtitle="Support, resistance, and moving average levels with distance from current price" />
            {keyLevels.length > 0 ? (
              <div style={{ marginTop: 14, overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: F.xs }}>
                  <thead>
                    <tr>
                      {['Level', 'Price', 'Type', 'Distance', 'Proximity'].map((h) => (
                        <th key={h} style={{ padding: '8px 12px', textAlign: 'left', color: C.muted, fontWeight: 700, fontSize: 9, textTransform: 'uppercase', letterSpacing: '0.08em', borderBottom: `1px solid ${C.border}` }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    <tr style={{ background: alpha(C.brand, 0.08) }}>
                      <td style={{ padding: '8px 12px', fontWeight: 800, color: C.brand }}>Current Price</td>
                      <td style={{ padding: '8px 12px', fontWeight: 800, color: C.text, fontFamily: "'JetBrains Mono', monospace" }}>${activeSignal?.price?.toLocaleString(undefined, { minimumFractionDigits: 2 }) ?? '\u2014'}</td>
                      <td style={{ padding: '8px 12px' }}><PillTag label="ACTIVE" color={C.brand} /></td>
                      <td style={{ padding: '8px 12px', color: C.muted }}>{'\u2014'}</td>
                      <td style={{ padding: '8px 12px' }}>{'\u2014'}</td>
                    </tr>
                    {keyLevels.map((level, i) => (
                      <tr key={i} style={{ borderBottom: `1px solid ${C.faint}` }}>
                        <td style={{ padding: '8px 12px', fontWeight: 700, color: level.color }}>{level.label}</td>
                        <td style={{ padding: '8px 12px', fontFamily: "'JetBrains Mono', monospace", color: C.text }}>${level.price.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                        <td style={{ padding: '8px 12px' }}><PillTag label={level.type} color={level.type === 'support' ? C.bull : C.bear} /></td>
                        <td style={{ padding: '8px 12px', fontFamily: "'JetBrains Mono', monospace", color: level.distance > 0 ? C.bull : C.bear }}>{level.distance > 0 ? '+' : ''}{level.distance.toFixed(2)}%</td>
                        <td style={{ padding: '8px 12px' }}><MiniBar value={Math.max(0, 5 - Math.abs(level.distance))} max={5} color={Math.abs(level.distance) < 2 ? C.warn : level.color} width={80} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ marginTop: 14, padding: 24, textAlign: 'center', color: C.muted, fontSize: F.sm }}>No signal data available {'\u2014'} waiting for market analysis</div>
            )}
          </GlassPanel>

          {/* ── 4. Trade Setup Scanner ─────────────────────────────────── */}
          <div>
            <SectionTitle icon={'\u{1F3AF}'} title="Active Trade Setups" subtitle="Live trading opportunities detected by the signal engine" />
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 12, marginTop: 12 }}>
              {allSignals.length > 0 ? allSignals.map((sig) => {
                const entry = sig.price;
                const sl = sig.zones.deepAccum || sig.zones.accum;
                const tp1 = sig.zones.distrib;
                const tp2 = sig.zones.safeDistrib;
                const riskPct = sl > 0 ? Math.abs(entry - sl) / entry * 100 : 0;
                const rewardPct = tp1 > 0 ? Math.abs(tp1 - entry) / entry * 100 : 0;
                const rr = riskPct > 0 ? rewardPct / riskPct : 0;
                return (
                  <motion.div key={sig.sym} variants={fadeUp} {...hoverGlow} style={{ ...Glass.card, borderRadius: R.lg, padding: 16, cursor: 'pointer', border: `1px solid ${sig.sym === activeSymbol ? alpha(C.brand, 0.3) : 'rgba(255,255,255,0.04)'}` }} onClick={() => setActiveSymbol(sig.sym)}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontSize: F.md, fontWeight: 800, color: C.text }}>{sig.sym}/USDT</span>
                        <PillTag label={`Score ${sig.score}`} color={sig.score >= 60 ? C.bull : sig.score >= 40 ? C.warn : C.bear} />
                      </div>
                      <span style={{ fontSize: F.lg, fontWeight: 800, fontFamily: "'JetBrains Mono', monospace", color: C.text }}>${entry.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 8, marginBottom: 10 }}>
                      {[
                        { label: 'Entry', value: entry, color: '#f59e0b' },
                        { label: 'Stop Loss', value: sl, color: C.bear },
                        { label: 'TP1', value: tp1, color: C.bull },
                        { label: 'TP2', value: tp2, color: '#34d399' },
                      ].map((lv) => (
                        <div key={lv.label} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                          <span style={{ fontSize: 8, fontWeight: 700, color: C.muted, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{lv.label}</span>
                          <span style={{ fontSize: F.xs, fontWeight: 700, color: lv.color, fontFamily: "'JetBrains Mono', monospace" }}>{lv.value > 0 ? `$${lv.value.toLocaleString(undefined, { maximumFractionDigits: 2 })}` : '\u2014'}</span>
                        </div>
                      ))}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 9, color: C.muted, minWidth: 24 }}>R:R</span>
                      <div style={{ flex: 1, height: 8, borderRadius: 4, display: 'flex', overflow: 'hidden', background: C.faint }}>
                        <div style={{ width: `${riskPct > 0 ? (riskPct / (riskPct + rewardPct)) * 100 : 50}%`, background: alpha(C.bear, 0.6), height: '100%' }} />
                        <div style={{ flex: 1, background: alpha(C.bull, 0.6), height: '100%' }} />
                      </div>
                      <span style={{ fontSize: F.xs, fontWeight: 800, color: rr >= 2 ? C.bull : rr >= 1 ? C.warn : C.bear, fontFamily: "'JetBrains Mono', monospace", minWidth: 40, textAlign: 'right' }}>{rr > 0 ? `${rr.toFixed(1)}:1` : '\u2014'}</span>
                    </div>
                  </motion.div>
                );
              }) : (
                <div style={{ ...Glass.card, borderRadius: R.lg, padding: 32, textAlign: 'center', color: C.muted, gridColumn: '1 / -1' }}>No active trade setups {'\u2014'} waiting for signals</div>
              )}
            </div>
          </div>

          {/* ── 5. Position Size Calculator ────────────────────────────── */}
          <GlassPanel>
            <SectionTitle icon={'\u{1F522}'} title="Position Size Calculator" subtitle="Calculate optimal position size based on your risk tolerance" />
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 20, marginTop: 16 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                    <label style={{ fontSize: F.xs, fontWeight: 700, color: C.textSub }}>Account Size</label>
                    <span style={{ fontSize: F.xs, fontWeight: 800, color: C.text, fontFamily: "'JetBrains Mono', monospace" }}>${calcAccount.toLocaleString()}</span>
                  </div>
                  <input type="range" min={1000} max={100000} step={1000} value={calcAccount} onChange={(e) => setCalcAccount(Number(e.target.value))} style={{ width: '100%', accentColor: C.brand, cursor: 'pointer' }} />
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: C.faint }}><span>$1,000</span><span>$100,000</span></div>
                </div>
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                    <label style={{ fontSize: F.xs, fontWeight: 700, color: C.textSub }}>Risk Per Trade</label>
                    <span style={{ fontSize: F.xs, fontWeight: 800, color: C.text, fontFamily: "'JetBrains Mono', monospace" }}>{calcRisk.toFixed(1)}%</span>
                  </div>
                  <input type="range" min={0.5} max={5} step={0.5} value={calcRisk} onChange={(e) => setCalcRisk(Number(e.target.value))} style={{ width: '100%', accentColor: C.brand, cursor: 'pointer' }} />
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: C.faint }}><span>0.5%</span><span>5%</span></div>
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                {posCalc ? [
                  { label: 'Risk Amount', value: `$${posCalc.riskAmount.toFixed(0)}`, color: C.warn },
                  { label: 'SL Distance', value: `${posCalc.slDistance.toFixed(2)}%`, color: C.bear },
                  { label: 'Position Size', value: `$${posCalc.positionSize.toFixed(0)}`, color: C.brand },
                  { label: 'Leverage', value: `${posCalc.leverage.toFixed(1)}x`, color: posCalc.leverage > 5 ? C.bear : posCalc.leverage > 2 ? C.warn : C.bull },
                  { label: `${activeSymbol} Amount`, value: posCalc.coins.toFixed(activeSymbol === 'BTC' ? 4 : 2), color: C.text },
                  { label: 'Max Loss', value: `$${posCalc.riskAmount.toFixed(0)}`, color: C.bear },
                ].map((o) => (
                  <div key={o.label} style={{ ...Glass.card, borderRadius: R.md, padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <span style={{ fontSize: 8, fontWeight: 700, color: C.muted, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{o.label}</span>
                    <span style={{ fontSize: F.md, fontWeight: 800, color: o.color, fontFamily: "'JetBrains Mono', monospace" }}>{o.value}</span>
                  </div>
                )) : (
                  <div style={{ gridColumn: '1 / -1', padding: 20, textAlign: 'center', color: C.muted, fontSize: F.sm }}>Waiting for signal data...</div>
                )}
              </div>
            </div>
          </GlassPanel>

          {/* ── 6. Recent Signals Feed ─────────────────────────────────── */}
          <GlassPanel>
            <SectionTitle icon={'\u{1F4E1}'} title="Recent Signals" subtitle={`Last ${recentSignals.length} trade signals for ${activeSymbol}`} />
            {recentSignals.length > 0 ? (
              <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 2 }}>
                {recentSignals.map((sig, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 14px', background: i % 2 === 0 ? 'transparent' : alpha(C.brand, 0.03), borderRadius: R.sm }}>
                    <PillTag label={sig.side || '\u2014'} color={sig.side === 'BUY' ? C.bull : C.bear} />
                    <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 6, fontSize: F.xs, fontFamily: "'JetBrains Mono', monospace" }}>
                      <span style={{ color: C.textSub }}>{sig.entry?.toFixed(2) ?? '\u2014'}</span>
                      <span style={{ color: C.faint }}>{'\u2192'}</span>
                      <span style={{ color: C.textSub }}>{sig.exit?.toFixed(2) ?? '\u2014'}</span>
                    </div>
                    <span style={{ fontSize: F.xs, fontWeight: 800, fontFamily: "'JetBrains Mono', monospace", color: (sig.pnl ?? 0) >= 0 ? C.bull : C.bear, minWidth: 55, textAlign: 'right' }}>
                      {sig.pnl != null ? `${sig.pnl >= 0 ? '+' : ''}${sig.pnl.toFixed(2)}%` : '\u2014'}
                    </span>
                    <PillTag label={sig.outcome || '\u2014'} color={sig.outcome === 'WIN' ? C.bull : C.bear} />
                    <span style={{ fontSize: 10, color: C.muted, minWidth: 60 }}>{sig.strategy || '\u2014'}</span>
                    <span style={{ fontSize: 10, color: C.faint, minWidth: 40 }}>{sig.duration != null ? `${sig.duration.toFixed(1)}h` : '\u2014'}</span>
                    {sig.llmAction && <PillTag label={sig.llmAction} color={sig.llmAction === 'proceed' ? C.bull : sig.llmAction === 'flip' ? C.bear : C.muted} />}
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ marginTop: 14, padding: 24, textAlign: 'center', color: C.muted, fontSize: F.sm }}>No recent signals for {activeSymbol}</div>
            )}
          </GlassPanel>

          {/* ── 7. Correlation Matrix + 8. Price Alerts ────────────────── */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 16 }}>
            <GlassPanel>
              <SectionTitle icon={'\u{1F517}'} title="Market Correlations" subtitle="PnL correlation between traded assets" />
              <div style={{ marginTop: 14 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '40px repeat(3, 1fr)', gap: 4 }}>
                  <div />
                  {(['BTC', 'SOL', 'HYPE'] as const).map((s) => (
                    <div key={s} style={{ textAlign: 'center', fontSize: 9, fontWeight: 700, color: C.muted, padding: 6 }}>{s}</div>
                  ))}
                  {(['BTC', 'SOL', 'HYPE'] as const).map((row) => (
                    <React.Fragment key={row}>
                      <div style={{ fontSize: 9, fontWeight: 700, color: C.muted, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{row}</div>
                      {(['BTC', 'SOL', 'HYPE'] as const).map((col) => {
                        const corr = correlationMatrix[row]?.[col] ?? 0;
                        const bg = corr === 1 ? alpha(C.brand, 0.2) : corr > 0.3 ? alpha(C.bull, 0.15 + corr * 0.15) : corr < -0.3 ? alpha(C.bear, 0.15 + Math.abs(corr) * 0.15) : alpha(C.muted, 0.08);
                        return (
                          <div key={col} style={{ background: bg, borderRadius: R.sm, padding: 10, textAlign: 'center', fontSize: F.xs, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace", color: corr === 1 ? C.brand : corr > 0.3 ? C.bull : corr < -0.3 ? C.bear : C.muted, border: `1px solid ${alpha(C.border, 0.3)}` }}>
                            {corr === 1 ? '1.00' : corr.toFixed(2)}
                          </div>
                        );
                      })}
                    </React.Fragment>
                  ))}
                </div>
                <div style={{ fontSize: 9, color: C.faint, marginTop: 8, textAlign: 'center' }}>Based on historical trade PnL patterns. Values range from -1 (inverse) to +1 (correlated).</div>
              </div>
            </GlassPanel>

            <GlassPanel>
              <SectionTitle icon={'\u{1F514}'} title="Price Alerts" subtitle="Key levels approaching current price" />
              <div style={{ marginTop: 14 }}>
                {priceAlerts.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {priceAlerts.map((alert, i) => (
                      <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 14px', ...Glass.card, borderRadius: R.md, border: `1px solid ${alpha(alert.color, 0.2)}` }}>
                        <div style={{ width: 8, height: 8, borderRadius: '50%', background: alert.color, boxShadow: i === 0 ? `0 0 8px ${alert.color}` : 'none' }} />
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: F.xs, fontWeight: 700, color: alert.color }}>{alert.label}</div>
                          <div style={{ fontSize: 10, color: C.muted }}>${alert.price.toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
                        </div>
                        <div style={{ textAlign: 'right' }}>
                          <div style={{ fontSize: F.xs, fontWeight: 800, fontFamily: "'JetBrains Mono', monospace", color: alert.distance > 0 ? C.bull : C.bear }}>{alert.distance > 0 ? '+' : ''}{alert.distance.toFixed(2)}%</div>
                          <div style={{ fontSize: 9, color: C.muted }}>{alert.distance > 0 ? 'above' : 'below'} price</div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ padding: 32, textAlign: 'center' }}>
                    <div style={{ fontSize: 24, marginBottom: 8 }}>{'\u2705'}</div>
                    <div style={{ fontSize: F.sm, color: C.textSub, fontWeight: 600 }}>No nearby levels</div>
                    <div style={{ fontSize: F.xs, color: C.muted, marginTop: 4 }}>Price is clear of major support/resistance zones</div>
                  </div>
                )}
              </div>
            </GlassPanel>
          </div>

        </motion.div>
      </div>
    </>
  );
}
