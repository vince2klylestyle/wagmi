import { useCallback, useRef, useState } from 'react';

/**
 * Cursor-following radial spotlight for glass surfaces.
 * Tracks mouse position relative to the element and exposes CSS-ready values.
 *
 * Usage:
 *   const { glowRef, glowStyle, handlers } = useMouseGlow({ color, radius });
 *   <div ref={glowRef} {...handlers} style={{ position: 'relative' }}>
 *     <div style={glowStyle} />
 *     {children}
 *   </div>
 */

export interface UseMouseGlowOptions {
  /** Glow color — default brand indigo */
  color?: string;
  /** Glow radius in px — default 300 */
  radius?: number;
  /** Peak opacity — default 0.08 */
  opacity?: number;
  /** Fade-out duration in ms — default 300 */
  fadeDuration?: number;
}

export interface MouseGlowResult {
  glowRef: React.RefObject<HTMLDivElement | null>;
  /** Inline style for the glow overlay div (position: absolute, pointer-events: none) */
  glowStyle: React.CSSProperties;
  /** Spread onto the container element */
  handlers: {
    onMouseMove: (e: React.MouseEvent) => void;
    onMouseEnter: () => void;
    onMouseLeave: () => void;
  };
}

export function useMouseGlow({
  color = 'rgba(99,102,241,0.08)',
  radius = 300,
  opacity = 1,
  fadeDuration = 300,
}: UseMouseGlowOptions = {}): MouseGlowResult {
  const glowRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const [visible, setVisible] = useState(false);

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    const el = glowRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    setPos({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    });
  }, []);

  const onMouseEnter = useCallback(() => setVisible(true), []);
  const onMouseLeave = useCallback(() => setVisible(false), []);

  const glowStyle: React.CSSProperties = {
    position: 'absolute',
    inset: 0,
    pointerEvents: 'none',
    zIndex: 1,
    opacity: visible ? opacity : 0,
    transition: `opacity ${fadeDuration}ms ease`,
    background: `radial-gradient(circle ${radius}px at ${pos.x}px ${pos.y}px, ${color}, transparent 100%)`,
    borderRadius: 'inherit',
  };

  return {
    glowRef,
    glowStyle,
    handlers: { onMouseMove, onMouseEnter, onMouseLeave },
  };
}
