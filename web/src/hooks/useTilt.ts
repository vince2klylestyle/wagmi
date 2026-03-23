import { useCallback, useRef } from 'react';
import { useMotionValue, useSpring, MotionValue } from 'framer-motion';

/**
 * 3D perspective tilt that follows the cursor.
 * Cards tilt toward the mouse position, creating a holographic glass effect.
 *
 * Usage:
 *   const { tiltRef, tiltStyle, handlers } = useTilt();
 *   <motion.div ref={tiltRef} {...handlers} style={{ ...tiltStyle }}>
 */

export interface UseTiltOptions {
  /** Max tilt angle in degrees — default 6 */
  maxTilt?: number;
  /** CSS perspective value — default 1000 */
  perspective?: number;
  /** Scale on hover — default 1.02 */
  scale?: number;
  /** Spring stiffness — default 300 */
  stiffness?: number;
  /** Spring damping — default 20 */
  damping?: number;
}

export interface TiltResult {
  tiltRef: React.RefObject<HTMLDivElement | null>;
  tiltStyle: {
    perspective: number;
    transformStyle: 'preserve-3d';
    rotateX: MotionValue<number>;
    rotateY: MotionValue<number>;
    scale: MotionValue<number>;
  };
  handlers: {
    onMouseMove: (e: React.MouseEvent) => void;
    onMouseLeave: () => void;
  };
}

export function useTilt({
  maxTilt = 6,
  perspective = 1000,
  scale = 1.02,
  stiffness = 300,
  damping = 20,
}: UseTiltOptions = {}): TiltResult {
  const tiltRef = useRef<HTMLDivElement>(null);

  const springConfig = { stiffness, damping, mass: 0.5 };
  const rx = useMotionValue(0);
  const ry = useMotionValue(0);
  const s = useMotionValue(1);

  const rotateX = useSpring(rx, springConfig);
  const rotateY = useSpring(ry, springConfig);
  const scaleVal = useSpring(s, springConfig);

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    const el = tiltRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    // Normalize cursor position to -1..1
    const nx = ((e.clientX - rect.left) / rect.width - 0.5) * 2;
    const ny = ((e.clientY - rect.top) / rect.height - 0.5) * 2;
    // rotateY = horizontal movement, rotateX = negative vertical
    ry.set(nx * maxTilt);
    rx.set(-ny * maxTilt);
    s.set(scale);
  }, [maxTilt, scale, rx, ry, s]);

  const onMouseLeave = useCallback(() => {
    rx.set(0);
    ry.set(0);
    s.set(1);
  }, [rx, ry, s]);

  return {
    tiltRef,
    tiltStyle: {
      perspective,
      transformStyle: 'preserve-3d' as const,
      rotateX,
      rotateY,
      scale: scaleVal,
    },
    handlers: { onMouseMove, onMouseLeave },
  };
}
