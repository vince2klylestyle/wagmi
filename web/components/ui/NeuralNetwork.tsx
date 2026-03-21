'use client';
import React, { useMemo, useState, useCallback } from 'react';
import { C, F, R, SP, Glass, alpha } from '../../src/theme';

interface AgentNode {
  id: string;
  label: string;
  color: string;
  x: number;
  y: number;
  role: string;
  model: string;
}

interface NeuralNetworkProps {
  width?: number | string;
  height?: number;
  agentData?: Record<string, { accuracy?: number | null; total_decisions?: number }>;
  /** Enable hover interactivity — highlights connections, shows tooltip */
  interactive?: boolean;
}

const AGENTS: AgentNode[] = [
  { id: 'regime',   label: 'Regime',   color: '#06b6d4', x: 50, y: 10,  role: 'Classifies market regime', model: 'Haiku' },
  { id: 'scout',    label: 'Scout',    color: '#64748b', x: 15, y: 25,  role: 'Idle-time watchlists & pre-theses', model: 'Haiku' },
  { id: 'trade',    label: 'Trade',    color: '#6366f1', x: 50, y: 30,  role: 'Forms directional thesis', model: 'Sonnet' },
  { id: 'risk',     label: 'Risk',     color: '#f59e0b', x: 25, y: 50,  role: 'Sizes positions & flags risks', model: 'Haiku' },
  { id: 'critic',   label: 'Critic',   color: '#ec4899', x: 75, y: 50,  role: 'Stress-tests thesis', model: 'Sonnet' },
  { id: 'overseer', label: 'Overseer', color: '#7c3aed', x: 85, y: 25,  role: 'Portfolio-level oversight', model: 'Haiku' },
  { id: 'learning', label: 'Learning', color: '#10b981', x: 25, y: 75,  role: 'Extracts lessons from trades', model: 'Haiku' },
  { id: 'exit',     label: 'Exit',     color: '#ef4444', x: 75, y: 75,  role: 'Monitors open positions', model: 'Haiku' },
  { id: 'quant',    label: 'Quant',    color: '#3b82f6', x: 50, y: 90,  role: 'Statistical edge validation', model: 'Haiku' },
];

const CONNECTIONS: [string, string][] = [
  ['regime', 'trade'],
  ['regime', 'scout'],
  ['regime', 'overseer'],
  ['trade', 'risk'],
  ['trade', 'critic'],
  ['risk', 'critic'],
  ['critic', 'learning'],
  ['critic', 'exit'],
  ['learning', 'quant'],
  ['exit', 'quant'],
  ['scout', 'trade'],
  ['overseer', 'critic'],
];

export function NeuralNetwork({ width = '100%', height = 400, agentData, interactive = true }: NeuralNetworkProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const agentMap = useMemo(() => {
    const m: Record<string, AgentNode> = {};
    AGENTS.forEach(a => { m[a.id] = a; });
    return m;
  }, []);

  // Which agents are "active" (connected to hovered/selected)
  const activeId = hoveredId || selectedId;
  const connectedIds = useMemo(() => {
    if (!activeId) return new Set<string>();
    const ids = new Set<string>([activeId]);
    CONNECTIONS.forEach(([from, to]) => {
      if (from === activeId) ids.add(to);
      if (to === activeId) ids.add(from);
    });
    return ids;
  }, [activeId]);

  const isConnectionActive = useCallback((from: string, to: string) => {
    if (!activeId) return false;
    return (from === activeId || to === activeId);
  }, [activeId]);

  const handleNodeEnter = useCallback((id: string) => {
    if (interactive) setHoveredId(id);
  }, [interactive]);

  const handleNodeLeave = useCallback(() => {
    if (interactive) setHoveredId(null);
  }, [interactive]);

  const handleNodeClick = useCallback((id: string) => {
    if (interactive) setSelectedId(prev => prev === id ? null : id);
  }, [interactive]);

  // Tooltip data
  const tooltipAgent = activeId ? agentMap[activeId] : null;
  const tooltipData = activeId ? agentData?.[activeId] : null;

  return (
    <div style={{ width, height, position: 'relative' }}>
      <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet" style={{ width: '100%', height: '100%' }}>
        <defs>
          {AGENTS.map(a => (
            <radialGradient key={`grad-${a.id}`} id={`node-grad-${a.id}`}>
              <stop offset="0%" stopColor={a.color} stopOpacity="0.6" />
              <stop offset="70%" stopColor={a.color} stopOpacity="0.2" />
              <stop offset="100%" stopColor={a.color} stopOpacity="0" />
            </radialGradient>
          ))}
          <filter id="nn-glow">
            <feGaussianBlur stdDeviation="0.8" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="nn-glow-strong">
            <feGaussianBlur stdDeviation="1.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Connection lines */}
        {CONNECTIONS.map(([from, to], i) => {
          const a = agentMap[from];
          const b = agentMap[to];
          if (!a || !b) return null;
          const active = isConnectionActive(from, to);
          const dimmed = activeId && !active;
          return (
            <g key={`conn-${i}`}>
              <line
                x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                stroke={active ? a.color : C.border}
                strokeWidth={active ? '0.6' : '0.3'}
                opacity={dimmed ? 0.1 : active ? 0.7 : 0.4}
                style={{ transition: 'all 0.3s ease' }}
              />
              {/* Animated pulse dot along path */}
              <circle
                r={active ? '0.9' : '0.6'}
                fill={a.color}
                opacity={dimmed ? 0.1 : 0.8}
                filter={active ? 'url(#nn-glow-strong)' : 'url(#nn-glow)'}
                style={{ transition: 'opacity 0.3s ease' }}
              >
                <animateMotion
                  dur={active ? `${1.5 + i * 0.15}s` : `${2.5 + i * 0.3}s`}
                  repeatCount="indefinite"
                  path={`M${a.x},${a.y} L${b.x},${b.y}`}
                />
                <animate
                  attributeName="opacity"
                  values={dimmed ? '0;0.1;0.1;0' : '0;0.8;0.8;0'}
                  dur={active ? `${1.5 + i * 0.15}s` : `${2.5 + i * 0.3}s`}
                  repeatCount="indefinite"
                />
              </circle>
            </g>
          );
        })}

        {/* Agent nodes */}
        {AGENTS.map((a) => {
          const data = agentData?.[a.id];
          const accuracy = data?.accuracy;
          const isActive = activeId === a.id;
          const isConnected = connectedIds.has(a.id);
          const dimmed = activeId && !isConnected;
          const nodeScale = isActive ? 1.3 : 1;

          return (
            <g
              key={a.id}
              style={{
                cursor: interactive ? 'pointer' : 'default',
                transition: 'opacity 0.3s ease',
                opacity: dimmed ? 0.2 : 1,
              }}
              onMouseEnter={() => handleNodeEnter(a.id)}
              onMouseLeave={handleNodeLeave}
              onClick={() => handleNodeClick(a.id)}
            >
              {/* Outer glow halo */}
              <circle
                cx={a.x} cy={a.y}
                r={isActive ? 8 : 6}
                fill={`url(#node-grad-${a.id})`}
                style={{ transition: 'r 0.3s ease' }}
              >
                <animate
                  attributeName="r"
                  values={isActive ? '7;9;7' : '5.5;6.5;5.5'}
                  dur={isActive ? '1.5s' : '3s'}
                  repeatCount="indefinite"
                />
              </circle>
              {/* Inner orb */}
              <circle
                cx={a.x} cy={a.y}
                r={isActive ? 3.8 : 3}
                fill={alpha(a.color, isActive ? 0.25 : 0.15)}
                stroke={a.color}
                strokeWidth={isActive ? '0.7' : '0.4'}
                filter={isActive ? 'url(#nn-glow-strong)' : 'url(#nn-glow)'}
                style={{ transition: 'all 0.3s ease' }}
              />
              {/* Core dot */}
              <circle
                cx={a.x} cy={a.y}
                r={isActive ? 1.6 : 1.2}
                fill={a.color}
                opacity={0.9}
                style={{ transition: 'r 0.3s ease' }}
              />
              {/* Label */}
              <text
                x={a.x}
                y={a.y + (isActive ? 10 : 8.5)}
                textAnchor="middle"
                fill={isActive ? a.color : C.textSub}
                fontSize={isActive ? '3.2' : '3'}
                fontFamily="Inter, system-ui, sans-serif"
                fontWeight={isActive ? '700' : '600'}
                style={{ transition: 'fill 0.3s ease' }}
              >
                {a.label}
              </text>
              {/* Accuracy % if available */}
              {accuracy != null && (
                <text
                  x={a.x}
                  y={a.y + (isActive ? 12.8 : 11)}
                  textAnchor="middle"
                  fill={isActive ? a.color : C.muted}
                  fontSize="2.2"
                  fontFamily="'JetBrains Mono', monospace"
                  style={{ transition: 'fill 0.3s ease' }}
                >
                  {(accuracy * 100).toFixed(0)}%
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Floating tooltip (HTML overlay) */}
      {interactive && tooltipAgent && (
        <div
          style={{
            position: 'absolute',
            left: `${tooltipAgent.x}%`,
            top: `${Math.max(tooltipAgent.y - 18, 2)}%`,
            transform: 'translateX(-50%)',
            ...Glass.crystal,
            borderRadius: R.md,
            padding: `${SP[2]}px ${SP[3]}px`,
            pointerEvents: 'none',
            zIndex: 10,
            minWidth: 160,
            opacity: hoveredId ? 1 : 0,
            transition: 'opacity 0.2s ease',
            border: `1px solid ${alpha(tooltipAgent.color, 0.3)}`,
            boxShadow: `0 8px 32px rgba(0,0,0,0.4), 0 0 20px ${alpha(tooltipAgent.color, 0.15)}`,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: tooltipAgent.color, boxShadow: `0 0 8px ${tooltipAgent.color}` }} />
            <span style={{ fontSize: F.sm, fontWeight: 700, color: tooltipAgent.color }}>{tooltipAgent.label} Agent</span>
            <span style={{
              marginLeft: 'auto',
              fontSize: 10,
              padding: '1px 6px',
              borderRadius: R.pill,
              background: alpha(tooltipAgent.color, 0.15),
              color: tooltipAgent.color,
              fontWeight: 600,
            }}>
              {tooltipAgent.model}
            </span>
          </div>
          <div style={{ fontSize: F.xs, color: C.textSub, lineHeight: 1.4, marginBottom: 4 }}>
            {tooltipAgent.role}
          </div>
          {tooltipData && (
            <div style={{ display: 'flex', gap: 12, fontSize: 10, color: C.muted }}>
              {tooltipData.accuracy != null && (
                <span>Accuracy: <span style={{ color: tooltipData.accuracy > 0.6 ? '#16a34a' : '#f59e0b', fontWeight: 600 }}>{(tooltipData.accuracy * 100).toFixed(1)}%</span></span>
              )}
              {tooltipData.total_decisions != null && (
                <span>Decisions: <span style={{ color: C.textSub, fontWeight: 600 }}>{tooltipData.total_decisions}</span></span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default NeuralNetwork;
