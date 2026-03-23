'use client';

import React, { useEffect, useRef, useState } from 'react';
import { motion, useSpring, useTransform, useInView } from 'framer-motion';

export interface AnimatedNumberProps {
  value: number;
  format?: (n: number) => string;
  duration?: number;
  /** Trigger countup only when scrolled into view (default false) */
  triggerOnView?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

const defaultFormat = (n: number) =>
  n.toLocaleString('en-US', { maximumFractionDigits: 2 });

export function AnimatedNumber({
  value,
  format = defaultFormat,
  duration = 0.6,
  triggerOnView = false,
  className,
  style,
}: AnimatedNumberProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const isInView = useInView(ref, { once: true, margin: '-40px' });
  const [hasTriggered, setHasTriggered] = useState(!triggerOnView);

  const spring = useSpring(0, { duration: duration * 1000 });
  const display = useTransform(spring, (v) => format(v));

  // Trigger on view if enabled
  useEffect(() => {
    if (triggerOnView && isInView && !hasTriggered) {
      setHasTriggered(true);
    }
  }, [triggerOnView, isInView, hasTriggered]);

  // Animate to value
  useEffect(() => {
    if (hasTriggered) {
      spring.set(value);
    }
  }, [spring, value, hasTriggered]);

  return <motion.span ref={ref} className={className} style={style}>{display}</motion.span>;
}

export default AnimatedNumber;
