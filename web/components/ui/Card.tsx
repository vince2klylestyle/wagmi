'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { C, R, S, Glass } from '../../src/theme';
import { fadeUp, hoverGlow } from '../../src/animations';

export interface CardProps {
  accent?: string;
  glass?: boolean;
  hover?: boolean;
  delay?: number;
  style?: React.CSSProperties;
  className?: string;
  children: React.ReactNode;
}

export function Card({
  accent,
  glass = true,
  hover = false,
  delay = 0,
  style,
  className,
  children,
}: CardProps) {
  const baseStyle: React.CSSProperties = {
    position: 'relative',
    borderRadius: R.lg,
    overflow: 'hidden',
    ...(glass
      ? Glass.card
      : {
          background: C.card,
          border: `1px solid ${C.border}`,
        }),
    boxShadow: S.md,
    ...style,
  };

  return (
    <motion.div
      className={className}
      style={baseStyle}
      variants={fadeUp}
      initial="hidden"
      animate="show"
      transition={{ delay }}
      {...(hover ? hoverGlow : {})}
    >
      {accent && (
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: 2,
            background: accent,
          }}
        />
      )}
      {children}
    </motion.div>
  );
}

export default Card;
