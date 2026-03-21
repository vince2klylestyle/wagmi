'use client';

import React, { useEffect, useRef, useState, useCallback, useId } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { C, R, F, S, Glass, SP } from '../../src/theme';
import { fadeUp, magneticHover, cinematicReveal } from '../../src/animations';
import { resolveApiBase } from '../../src/api';
import type { IChartApi, ISeriesApi, IPriceLine, UTCTimestamp } from 'lightweight-charts';

// ── Types ────────────────────────────────────────────────────────────────────

export type TradeMarker = {
  time: number; // UTCTimestamp
  type: 'entry' | 'exit';
  side: 'BUY' | 'SELL';
  price: number;
  label?: string;
  pnl?: number;
};

export type ZoneBand = {
  label: string;
  upper: number;
  lower: number;
  color: string;
  type: 'support' | 'resistance' | 'entry' | 'target' | 'stop';
};

export type SignalOverlay = {
  entry?: number;
  sl?: number;
  tp1?: number;
  tp2?: number;
  side?: string;
};

export type TradingChartProps = {
  symbol: string;
  height?: number;
  timeframes?: string[];
  defaultTimeframe?: string;
  zones?: ZoneBand[];
  signalLevels?: SignalOverlay | null;
  tradeMarkers?: TradeMarker[];
  showVolume?: boolean;
  showLegend?: boolean;
  title?: string;
  subtitle?: string;
};

// ── Constants ────────────────────────────────────────────────────────────────

const TF_OPTIONS = ['5m', '15m', '1h', '4h', '1d'] as const;

const TV_SYMBOLS: Record<string, string> = {
  BTC: 'BINANCE:BTCUSDT',
  SOL: 'BINANCE:SOLUSDT',
  HYPE: 'BYBIT:HYPEUSDT',
  ETH: 'BINANCE:ETHUSDT',
};

const ZONE_COLORS: Record<string, { bg: string; border: string; label: string }> = {
  support:    { bg: 'rgba(22,163,74,0.08)',  border: 'rgba(22,163,74,0.5)',  label: '#4ade80' },
  resistance: { bg: 'rgba(220,38,38,0.08)',  border: 'rgba(220,38,38,0.5)',  label: '#f87171' },
  entry:      { bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.5)', label: '#fbbf24' },
  target:     { bg: 'rgba(34,211,153,0.08)', border: 'rgba(34,211,153,0.5)', label: '#34d399' },
  stop:       { bg: 'rgba(239,68,68,0.08)',  border: 'rgba(239,68,68,0.5)',  label: '#f87171' },
};

// ── Component ────────────────────────────────────────────────────────────────

export function TradingChart({
  symbol,
  height = 560,
  timeframes,
  defaultTimeframe = '1h',
  zones = [],
  signalLevels,
  tradeMarkers = [],
  showVolume = true,
  showLegend = true,
  title,
  subtitle,
}: TradingChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);
  const priceLinesRef = useRef<IPriceLine[]>([]);
  const roRef = useRef<ResizeObserver | null>(null);

  const [tf, setTf] = useState(defaultTimeframe);
  const [status, setStatus] = useState<'loading' | 'ok' | 'error'>('loading');
  const [chartReady, setChartReady] = useState(false);
  const [lastPrice, setLastPrice] = useState<number | null>(null);
  const [priceChange, setPriceChange] = useState<number | null>(null);
  const [hoveredZone, setHoveredZone] = useState<string | null>(null);

  const apiBase = resolveApiBase();
  const activeTfs = timeframes || [...TF_OPTIONS];
  const uid = useId();

  // ── Initialize chart ───────────────────────────────────────────────────────
  useEffect(() => {
    if (typeof window === 'undefined' || !containerRef.current) return;

    let destroyed = false;

    (async () => {
      const lc = await import('lightweight-charts');
      if (destroyed || !containerRef.current) return;

      containerRef.current.innerHTML = '';
      const chart = lc.createChart(containerRef.current, {
        autoSize: true,
        layout: {
          background: { color: 'transparent' },
          textColor: C.textSub,
          fontFamily: "'Inter', system-ui, sans-serif",
          fontSize: 11,
        },
        grid: {
          vertLines: { color: 'rgba(45,55,72,0.4)' },
          horzLines: { color: 'rgba(45,55,72,0.4)' },
        },
        crosshair: {
          mode: lc.CrosshairMode.Normal,
          vertLine: { color: 'rgba(99,102,241,0.3)', labelBackgroundColor: C.brand },
          horzLine: { color: 'rgba(99,102,241,0.3)', labelBackgroundColor: C.brand },
        },
        rightPriceScale: {
          borderColor: 'rgba(45,55,72,0.5)',
          scaleMargins: { top: 0.05, bottom: showVolume ? 0.2 : 0.05 },
        },
        timeScale: {
          borderColor: 'rgba(45,55,72,0.5)',
          timeVisible: true,
          secondsVisible: false,
        },
        handleScroll: true,
        handleScale: true,
      });
      chartRef.current = chart;

      // Volume histogram
      if (showVolume) {
        const volSeries = chart.addSeries(lc.HistogramSeries, {
          color: C.brand + '44',
          priceFormat: { type: 'volume' },
          priceScaleId: 'vol',
        });
        chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });
        volumeSeriesRef.current = volSeries;
      }

      // Candlestick series
      const candleSeries = chart.addSeries(lc.CandlestickSeries, {
        upColor: '#22c55e',
        downColor: '#ef4444',
        borderUpColor: '#22c55e',
        borderDownColor: '#ef4444',
        wickUpColor: '#22c55e88',
        wickDownColor: '#ef444488',
      });
      candleSeriesRef.current = candleSeries;
      setChartReady(true);

      // Resize observer
      const ro = new ResizeObserver(() => {
        if (containerRef.current && !destroyed) {
          chart.applyOptions({ width: containerRef.current.clientWidth });
        }
      });
      ro.observe(containerRef.current);
      roRef.current = ro;
    })();

    return () => {
      destroyed = true;
      roRef.current?.disconnect();
      chartRef.current?.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
      priceLinesRef.current = [];
      setChartReady(false);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Fetch candle data ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!chartReady || !candleSeriesRef.current) return;
    setStatus('loading');

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 8000);

    fetch(`${apiBase}/v1/ohlcv?symbol=${symbol}&timeframe=${tf}&limit=300`, {
      signal: controller.signal,
    })
      .then((r) => r.json())
      .then((raw: any[]) => {
        clearTimeout(timeoutId);
        if (!Array.isArray(raw) || raw.length === 0) {
          setStatus('error');
          return;
        }
        const sorted = [...raw]
          .map((c) => ({ ...c, time: c.time as UTCTimestamp }))
          .sort((a, b) => a.time - b.time);

        if (candleSeriesRef.current) {
          candleSeriesRef.current.setData(sorted);
          volumeSeriesRef.current?.setData(
            sorted.map((c) => ({
              time: c.time,
              value: c.volume,
              color: c.close >= c.open ? '#22c55e44' : '#ef444444',
            })),
          );
          chartRef.current?.timeScale().fitContent();

          // Track last price
          const last = sorted[sorted.length - 1];
          const prev = sorted.length > 1 ? sorted[sorted.length - 2] : last;
          setLastPrice(last.close);
          setPriceChange(prev.close ? ((last.close - prev.close) / prev.close) * 100 : 0);
        }

        // Apply trade markers via series markers (v5 compatible)
        if (tradeMarkers.length > 0 && candleSeriesRef.current) {
          try {
            const markers = tradeMarkers
              .map((m) => ({
                time: m.time as UTCTimestamp,
                position: m.type === 'entry' ? ('belowBar' as const) : ('aboveBar' as const),
                color: m.type === 'entry'
                  ? (m.side === 'BUY' ? '#22c55e' : '#ef4444')
                  : (m.pnl && m.pnl > 0 ? '#22c55e' : '#ef4444'),
                shape: m.type === 'entry' ? ('arrowUp' as const) : ('arrowDown' as const),
                text: m.label || (m.type === 'entry'
                  ? `${m.side} @ ${m.price.toFixed(2)}`
                  : `Exit ${m.pnl ? (m.pnl > 0 ? '+' : '') + m.pnl.toFixed(2) + '%' : ''}`),
              }))
              .sort((a, b) => (a.time as number) - (b.time as number));
            // v5: markers are set on series via type assertion
            (candleSeriesRef.current as any).setMarkers(markers);
          } catch {
            // Markers not supported in this version — silently skip
          }
        }

        setStatus('ok');
      })
      .catch(() => {
        clearTimeout(timeoutId);
        setStatus('error');
      });

    return () => {
      clearTimeout(timeoutId);
      controller.abort();
    };
  }, [symbol, tf, apiBase, chartReady, tradeMarkers]);

  // ── Apply zone bands + signal lines ────────────────────────────────────────
  useEffect(() => {
    const series = candleSeriesRef.current;
    if (!series) return;

    // Clear previous
    priceLinesRef.current.forEach((pl) => {
      try { series.removePriceLine(pl); } catch {}
    });
    priceLinesRef.current = [];

    (async () => {
      const { LineStyle } = await import('lightweight-charts');
      const lines: IPriceLine[] = [];

      // Zone bands — upper and lower lines with fill implied
      for (const zone of zones) {
        const zc = ZONE_COLORS[zone.type] || ZONE_COLORS.support;
        if (zone.upper > 0) {
          lines.push(
            series.createPriceLine({
              price: zone.upper,
              color: zc.border,
              lineWidth: 1,
              lineStyle: LineStyle.Dashed,
              axisLabelVisible: true,
              title: `${zone.label} ↑`,
            }),
          );
        }
        if (zone.lower > 0) {
          lines.push(
            series.createPriceLine({
              price: zone.lower,
              color: zc.border,
              lineWidth: 1,
              lineStyle: LineStyle.Dashed,
              axisLabelVisible: true,
              title: `${zone.label} ↓`,
            }),
          );
        }
      }

      // Signal entry / SL / TP lines
      if (signalLevels) {
        const sigLines = [
          { price: signalLevels.sl,    color: '#ef4444', title: '■ SL',    width: 2, style: LineStyle.Solid },
          { price: signalLevels.entry, color: '#f59e0b', title: '◆ Entry', width: 2, style: LineStyle.Solid },
          { price: signalLevels.tp1,   color: '#34d399', title: '▲ TP1',   width: 2, style: LineStyle.Solid },
          { price: signalLevels.tp2,   color: '#16a34a', title: '▲ TP2',   width: 1, style: LineStyle.Dashed },
        ];
        for (const l of sigLines) {
          if (!l.price || l.price === 0) continue;
          lines.push(
            series.createPriceLine({
              price: l.price,
              color: l.color,
              lineWidth: l.width as any,
              lineStyle: l.style,
              axisLabelVisible: true,
              title: l.title,
            }),
          );
        }
      }

      priceLinesRef.current = lines;
    })();
  }, [zones, signalLevels, chartReady]);

  // ── TradingView fallback ───────────────────────────────────────────────────
  const renderFallbackChart = useCallback(() => {
    const TV_TF: Record<string, string> = { '5m': '5', '15m': '15', '1h': '60', '4h': '240', '1d': 'D' };
    const tvSymbol = TV_SYMBOLS[symbol] ?? `BINANCE:${symbol}USDT`;
    const tvSrc = `https://s.tradingview.com/widgetembed/?frameElementId=tv_${uid}&symbol=${tvSymbol}&interval=${TV_TF[tf] ?? '60'}&theme=dark&style=1&locale=en&hide_top_toolbar=0&hide_side_toolbar=0&allow_symbol_change=0&save_image=0&withdateranges=1`;
    return (
      <iframe
        src={tvSrc}
        style={{ width: '100%', height: '100%', border: 'none', display: 'block' }}
        allow="fullscreen"
        title={`${symbol} Chart`}
      />
    );
  }, [symbol, tf, uid]);

  const isPositive = (priceChange ?? 0) >= 0;

  return (
    <motion.div
      variants={cinematicReveal}
      initial="hidden"
      animate="show"
      className="refraction-edge"
      style={{
        ...Glass.crystal,
        borderRadius: R.lg,
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {/* ── Header bar ───────────────────────────────────────────────────── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '16px 20px 12px',
          borderBottom: `1px solid rgba(255,255,255,0.04)`,
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        {/* Left: Symbol + price */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: F.lg, fontWeight: 800, color: C.text, letterSpacing: -0.5 }}>
                {title || `${symbol}/USDT`}
              </span>
              {lastPrice != null && (
                <span style={{
                  fontSize: F.lg,
                  fontWeight: 700,
                  color: isPositive ? C.bull : C.bear,
                  fontFamily: "'JetBrains Mono', monospace",
                  fontVariantNumeric: 'tabular-nums',
                }}>
                  ${lastPrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              )}
              {priceChange != null && (
                <span
                  style={{
                    fontSize: F.xs,
                    fontWeight: 700,
                    color: isPositive ? '#4ade80' : '#f87171',
                    background: isPositive ? 'rgba(22,163,74,0.15)' : 'rgba(220,38,38,0.15)',
                    padding: '2px 8px',
                    borderRadius: R.pill,
                  }}
                >
                  {isPositive ? '+' : ''}{priceChange.toFixed(2)}%
                </span>
              )}
            </div>
            {subtitle && (
              <div style={{ fontSize: F.xs, color: C.muted, marginTop: 2 }}>{subtitle}</div>
            )}
          </div>
        </div>

        {/* Right: Timeframe selector */}
        <div style={{ display: 'flex', gap: 4 }}>
          {activeTfs.map((t) => (
            <button
              key={t}
              onClick={() => setTf(t)}
              style={{
                padding: '5px 12px',
                borderRadius: R.sm,
                border: `1px solid ${tf === t ? C.brand : 'rgba(255,255,255,0.06)'}`,
                background: tf === t ? `${C.brand}20` : 'transparent',
                color: tf === t ? C.brand : C.muted,
                fontSize: 11,
                fontWeight: 700,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                letterSpacing: '0.02em',
              }}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* ── Zone legend ──────────────────────────────────────────────────── */}
      {showLegend && (zones.length > 0 || signalLevels) && (
        <div
          style={{
            display: 'flex',
            gap: 12,
            padding: '8px 20px',
            borderBottom: '1px solid rgba(255,255,255,0.03)',
            flexWrap: 'wrap',
            alignItems: 'center',
          }}
        >
          {zones.map((z) => {
            const zc = ZONE_COLORS[z.type] || ZONE_COLORS.support;
            return (
              <div
                key={z.label}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  fontSize: 10,
                  fontWeight: 600,
                  color: hoveredZone === z.label ? zc.label : C.muted,
                  cursor: 'default',
                  transition: 'color 0.15s',
                }}
                onMouseEnter={() => setHoveredZone(z.label)}
                onMouseLeave={() => setHoveredZone(null)}
              >
                <div
                  style={{
                    width: 12,
                    height: 4,
                    borderRadius: 2,
                    background: zc.border,
                    boxShadow: hoveredZone === z.label ? `0 0 8px ${zc.border}` : 'none',
                  }}
                />
                {z.label}
                <span style={{ color: C.faint, fontFamily: "'JetBrains Mono', monospace", fontSize: 9 }}>
                  {z.lower.toLocaleString()}–{z.upper.toLocaleString()}
                </span>
              </div>
            );
          })}
          {signalLevels && (
            <>
              {signalLevels.entry && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, fontWeight: 600, color: '#fbbf24' }}>
                  <div style={{ width: 12, height: 3, background: '#f59e0b', borderRadius: 1 }} />
                  Entry {signalLevels.entry.toLocaleString()}
                </div>
              )}
              {signalLevels.sl && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, fontWeight: 600, color: '#f87171' }}>
                  <div style={{ width: 12, height: 3, background: '#ef4444', borderRadius: 1 }} />
                  SL {signalLevels.sl.toLocaleString()}
                </div>
              )}
              {signalLevels.tp1 && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, fontWeight: 600, color: '#34d399' }}>
                  <div style={{ width: 12, height: 3, background: '#34d399', borderRadius: 1 }} />
                  TP1 {signalLevels.tp1.toLocaleString()}
                </div>
              )}
              {signalLevels.tp2 && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, fontWeight: 600, color: '#16a34a' }}>
                  <div style={{ width: 12, height: 3, background: '#16a34a', borderRadius: 1, opacity: 0.7 }} />
                  TP2 {signalLevels.tp2.toLocaleString()}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ── Chart canvas ─────────────────────────────────────────────────── */}
      <div style={{ position: 'relative' }}>
        {status === 'error' ? (
          <div style={{ width: '100%', height, borderRadius: 0, overflow: 'hidden', background: '#131722' }}>
            {renderFallbackChart()}
          </div>
        ) : (
          <div
            ref={containerRef}
            style={{ width: '100%', height, background: 'transparent' }}
          />
        )}

        {/* Loading overlay */}
        <AnimatePresence>
          {status === 'loading' && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              style={{
                position: 'absolute',
                inset: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: 'rgba(10,15,30,0.7)',
                backdropFilter: 'blur(4px)',
                fontSize: F.sm,
                color: C.muted,
                zIndex: 5,
              }}
            >
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
                <div className="breathe-glow" style={{
                  width: 32,
                  height: 32,
                  borderRadius: '50%',
                  border: `2px solid ${C.brand}`,
                  borderTopColor: 'transparent',
                  animation: 'spin 0.8s linear infinite, breatheGlow 2s ease-in-out infinite',
                }} />
                Loading {symbol} candles...
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Trade markers badge count */}
        {tradeMarkers.length > 0 && (
          <div style={{
            position: 'absolute',
            top: 8,
            left: 12,
            display: 'flex',
            gap: 6,
            zIndex: 4,
          }}>
            <span style={{
              fontSize: 10,
              fontWeight: 700,
              padding: '3px 8px',
              borderRadius: R.pill,
              background: 'rgba(22,163,74,0.15)',
              color: '#4ade80',
              border: '1px solid rgba(22,163,74,0.2)',
            }}>
              {tradeMarkers.filter((m) => m.type === 'entry').length} entries
            </span>
            <span style={{
              fontSize: 10,
              fontWeight: 700,
              padding: '3px 8px',
              borderRadius: R.pill,
              background: 'rgba(99,102,241,0.15)',
              color: '#a5b4fc',
              border: '1px solid rgba(99,102,241,0.2)',
            }}>
              {tradeMarkers.filter((m) => m.type === 'exit').length} exits
            </span>
          </div>
        )}
      </div>

      {/* Spinner keyframe */}
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </motion.div>
  );
}

export default TradingChart;
