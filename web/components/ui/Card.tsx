'use client';

import React, { useCallback, useRef, useState } from 'react';
import { motion, useMotionValue, useSpring } from 'framer-motion';
import { C, R, S, Glass } from '../../src/theme';
import { fadeUp, etherealFloat, magneticHover, luminousHover, hoverGlow } from '../../src/animations';

type GlassVariant = 'glass' | 'crystal' | 'liquid' | 'frosted' | 'diamond' | 'void';

export interface CardProps {
  accent?: string;
  /** Glass surface variant — controls blur, opacity, and inner reflections */
  variant?: GlassVariant;
  /** Legacy: if true uses Glass.card (same as variant='glass') */
  glass?: boolean;
  /** Hover effect style */
  hover?: boolean | 'magnetic' | 'luminous' | 'glow';
  /** Animated prismatic border (rainbow edge rotation) */
  prismatic?: boolean;
  /** Refraction edge effect (chromatic top edge highlight) */
  refraction?: boolean;
  /** Breathing glow animation */
  breathe?: boolean;
  /** Cursor-following radial glow on hover (default true for crystal/diamond) */
  glow?: boolean;
  /** Glow color override — default adapts to accent or brand indigo */
  glowColor?: string;
  /** 3D perspective tilt toward cursor (default true when glow is enabled) */
  tilt?: boolean;
  /** Animate on scroll into view instead of on mount */
  scrollReveal?: boolean;
  delay?: number;
  style?: React.CSSProperties;
  className?: string;
  children: React.ReactNode;
  onClick?: () => void;
}

const GLASS_MAP: Record<GlassVariant, React.CSSProperties> = {
  glass: Glass.card,
  crystal: Glass.crystal,
  liquid: Glass.liquid,
  frosted: Glass.frosted,
  diamond: Glass.diamond,
  void: Glass.void,
};

function getHoverProps(hover: CardProps['hover']) {
  if (!hover) return {};
  if (hover === 'magnetic') return magneticHover;
  if (hover === 'luminous') return luminousHover;
  return hoverGlow;
}

// Resolve glow color: accent-aware or default brand
function resolveGlowColor(accent?: string, glowColor?: string): string {
  if (glowColor) return glowColor;
  if (accent === C.bull || accent === '#16a34a') return 'rgba(22,163,74,0.10)';
  if (accent === C.bear || accent === '#dc2626') return 'rgba(220,38,38,0.10)';
  return 'rgba(99,102,241,0.08)';
}

export function Card({
  accent,
  variant,
  glass = true,
  hover = false,
  prismatic = false,
  refraction = false,
  breathe = false,
  glow: glowProp,
  glowColor,
  tilt: tiltProp,
  scrollReveal = false,
  delay = 0,
  style,
  className,
  children,
  onClick,
}: CardProps) {
  // Auto-enable glow on premium variants unless explicitly disabled
  const isPremium = variant === 'crystal' || variant === 'diamond';
  const enableGlow = glowProp !== undefined ? glowProp : isPremium;
  const enableTilt = tiltProp !== undefined ? tiltProp : enableGlow;

  // ── Cursor glow state ───────────────────────────────────────────────
  const containerRef = useRef<HTMLDivElement>(null);
  const [glowPos, setGlowPos] = useState({ x: 0, y: 0 });
  const [glowVisible, setGlowVisible] = useState(false);

  // ── Tilt spring values ──────────────────────────────────────────────
  const springCfg = { stiffness: 300, damping: 20, mass: 0.5 };
  const rxRaw = useMotionValue(0);
  const ryRaw = useMotionValue(0);
  const sRaw = useMotionValue(1);
  const rotateX = useSpring(rxRaw, springCfg);
  const rotateY = useSpring(ryRaw, springCfg);
  const scaleVal = useSpring(sRaw, springCfg);

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    const el = containerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();

    if (enableGlow) {
      setGlowPos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
    }

    if (enableTilt) {
      const nx = ((e.clientX - rect.left) / rect.width - 0.5) * 2;
      const ny = ((e.clientY - rect.top) / rect.height - 0.5) * 2;
      ryRaw.set(nx * 6);
      rxRaw.set(-ny * 6);
      sRaw.set(1.02);
    }
  }, [enableGlow, enableTilt, rxRaw, ryRaw, sRaw]);

  const onMouseEnter = useCallback(() => {
    if (enableGlow) setGlowVisible(true);
  }, [enableGlow]);

  const onMouseLeave = useCallback(() => {
    if (enableGlow) setGlowVisible(false);
    if (enableTilt) {
      rxRaw.set(0);
      ryRaw.set(0);
      sRaw.set(1);
    }
  }, [enableGlow, enableTilt, rxRaw, ryRaw, sRaw]);

  // ── Surface style ──────────────────────────────────────────────────
  const surfaceStyle = variant
    ? GLASS_MAP[variant]
    : glass
      ? Glass.card
      : { background: C.card, border: `1px solid ${C.border}` };

  const classes = [
    className,
    prismatic && 'prismatic-border',
    refraction && 'refraction-edge',
    breathe && 'breathe-slow',
  ].filter(Boolean).join(' ') || undefined;

  const baseStyle: React.CSSProperties = {
    position: 'relative',
    borderRadius: R.lg,
    overflow: 'hidden',
    ...surfaceStyle,
    boxShadow: isPremium
      ? (GLASS_MAP[variant!] as any).boxShadow
      : S.md,
    ...(enableTilt ? { perspective: 1000, transformStyle: 'preserve-3d' as const } : {}),
    ...style,
  };

  // Tilt motion styles (only applied when tilt is enabled)
  const tiltMotionStyle = enableTilt
    ? { rotateX, rotateY, scale: scaleVal }
    : {};

  // Animation trigger: scroll-into-view vs on-mount
  const animTrigger = scrollReveal
    ? { initial: 'hidden' as const, whileInView: 'show' as const, viewport: { once: true, margin: '-60px' } }
    : { initial: 'hidden' as const, animate: 'show' as const };

  const resolvedColor = resolveGlowColor(accent, glowColor);

  return (
    <motion.div
      ref={containerRef}
      className={classes}
      style={{ ...baseStyle, ...tiltMotionStyle }}
      variants={isPremium ? etherealFloat : fadeUp}
      transition={{ delay }}
      {...animTrigger}
      {...getHoverProps(hover)}
      onMouseMove={onMouseMove}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      onClick={onClick}
    >
      {/* Cursor-following glow overlay */}
      {enableGlow && (
        <div
          aria-hidden="true"
          style={{
            position: 'absolute',
            inset: 0,
            pointerEvents: 'none',
            zIndex: 1,
            opacity: glowVisible ? 1 : 0,
            transition: 'opacity 0.3s ease',
            background: `radial-gradient(circle 300px at ${glowPos.x}px ${glowPos.y}px, ${resolvedColor}, transparent 100%)`,
            borderRadius: 'inherit',
          }}
        />
      )}

      {/* Accent stripe */}
      {accent && (
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: 2,
            background: accent,
            zIndex: 2,
          }}
        />
      )}
      {children}
    </motion.div>
  );
}

export default Card;
