/**
 * /login — WAGMI Dashboard Entry
 *
 * Sophisticated, handcrafted authentication page.
 * Premium glassmorphism, intentional animations, no vibeslop.
 */

import React, { useState, useRef, useEffect } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';
import { C, R, F, S, A, DARK } from '../src/theme';
import { useAuth } from '../src/useAuth';

export default function LoginPage() {
  const router = useRouter();
  const { login, error } = useAuth();
  const [passcode, setPasscode] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [focusedInput, setFocusedInput] = useState(false);
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Track mouse position for gradient effect
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setMousePosition({
          x: e.clientX - rect.left,
          y: e.clientY - rect.top,
        });
      }
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    const success = await login(passcode);
    if (success) {
      router.push('/');
    }
    setIsSubmitting(false);
    setPasscode('');
    inputRef.current?.focus();
  };

  return (
    <>
      <Head>
        <title>WAGMI Dashboard — Access</title>
        <meta name="description" content="Enter the WAGMI trading intelligence dashboard" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <div
        ref={containerRef}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          background: `linear-gradient(135deg, ${C.bg} 0%, ${DARK.bg} 50%, #0d1529 100%)`,
          padding: '20px',
          fontFamily: 'system-ui, -apple-system, sans-serif',
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        {/* Animated background orbs */}
        <div
          style={{
            position: 'fixed',
            top: '10%',
            left: '5%',
            width: '300px',
            height: '300px',
            borderRadius: '50%',
            background: `radial-gradient(circle, rgba(99,102,241,0.1) 0%, rgba(99,102,241,0) 70%)`,
            filter: 'blur(60px)',
            animation: 'float 8s ease-in-out infinite',
            pointerEvents: 'none',
            zIndex: 0,
          }}
        />
        <div
          style={{
            position: 'fixed',
            bottom: '10%',
            right: '5%',
            width: '250px',
            height: '250px',
            borderRadius: '50%',
            background: `radial-gradient(circle, rgba(168,85,247,0.08) 0%, rgba(168,85,247,0) 70%)`,
            filter: 'blur(60px)',
            animation: 'float 10s ease-in-out infinite 1s',
            pointerEvents: 'none',
            zIndex: 0,
          }}
        />

        {/* Main container */}
        <div
          style={{
            position: 'relative',
            zIndex: 10,
            width: '100%',
            maxWidth: '420px',
            animation: `slideInUp 0.8s cubic-bezier(0.34, 1.56, 0.64, 1)`,
          }}
        >
          {/* Card with glassmorphism */}
          <div
            style={{
              background: `rgba(26, 34, 54, 0.7)`,
              backdropFilter: 'blur(20px)',
              border: `1px solid rgba(255, 255, 255, 0.1)`,
              borderRadius: `${R.lg}px`,
              padding: '48px 32px',
              boxShadow: `0 8px 32px rgba(0, 0, 0, 0.3), 0 0 1px rgba(255, 255, 255, 0.1)`,
              textAlign: 'center',
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            {/* Subtle gradient overlay based on mouse */}
            <div
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                background: `radial-gradient(circle 400px at ${mousePosition.x}px ${mousePosition.y}px, rgba(99, 102, 241, 0.05), transparent 80%)`,
                pointerEvents: 'none',
                transition: 'background 0.3s ease',
              }}
            />

            {/* Content */}
            <div style={{ position: 'relative', zIndex: 1 }}>
              {/* Icon */}
              <div
                style={{
                  fontSize: '56px',
                  marginBottom: '20px',
                  animation: `bounce 3s ease-in-out infinite`,
                  display: 'inline-block',
                }}
              >
                🤖
              </div>

              {/* Title */}
              <h1
                style={{
                  fontSize: F['3xl'],
                  fontWeight: 800,
                  color: C.text,
                  margin: '0 0 12px 0',
                  letterSpacing: '-0.5px',
                  background: `linear-gradient(135deg, ${C.text} 0%, ${C.textSub} 100%)`,
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  backgroundClip: 'text',
                }}
              >
                WAGMI
              </h1>

              {/* Subtitle */}
              <p
                style={{
                  fontSize: F.sm,
                  color: C.muted,
                  margin: '0 0 32px 0',
                  fontWeight: 500,
                  letterSpacing: '0.5px',
                  textTransform: 'uppercase',
                }}
              >
                Trading Intelligence
              </p>

              {/* Form */}
              <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                {/* Input container */}
                <div style={{ position: 'relative' }}>
                  <label
                    style={{
                      display: 'block',
                      fontSize: F.xs,
                      fontWeight: 700,
                      color: C.muted,
                      marginBottom: '10px',
                      textTransform: 'uppercase',
                      letterSpacing: '1.5px',
                    }}
                  >
                    Access Code
                  </label>

                  <div
                    style={{
                      position: 'relative',
                      transition: 'all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)',
                    }}
                  >
                    <input
                      ref={inputRef}
                      type="password"
                      value={passcode}
                      onChange={(e) => setPasscode(e.target.value)}
                      onFocus={() => setFocusedInput(true)}
                      onBlur={() => setFocusedInput(false)}
                      placeholder="Enter code"
                      style={{
                        width: '100%',
                        padding: '14px 16px',
                        fontSize: F.md,
                        background: focusedInput ? `rgba(255, 255, 255, 0.08)` : `rgba(255, 255, 255, 0.04)`,
                        color: C.text,
                        border: `1.5px solid ${
                          error ? C.bear : focusedInput ? C.brand : `rgba(255, 255, 255, 0.1)`
                        }`,
                        borderRadius: `${R.md}px`,
                        transition: 'all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)',
                        outline: 'none',
                        fontFamily: 'monospace',
                        letterSpacing: '3px',
                        boxSizing: 'border-box',
                        boxShadow: focusedInput
                          ? `0 0 20px rgba(99, 102, 241, 0.3), inset 0 1px 2px rgba(255, 255, 255, 0.1)`
                          : 'none',
                      }}
                      disabled={isSubmitting}
                      autoFocus
                    />

                    {/* Input underline effect */}
                    {focusedInput && (
                      <div
                        style={{
                          position: 'absolute',
                          bottom: 0,
                          left: 0,
                          right: 0,
                          height: '1px',
                          background: `linear-gradient(90deg, transparent, ${C.brand}, transparent)`,
                          animation: `expand 0.4s ease-out`,
                        }}
                      />
                    )}
                  </div>
                </div>

                {/* Error message */}
                {error && (
                  <div
                    style={{
                      fontSize: F.xs,
                      color: C.bear,
                      background: `rgba(220, 38, 38, 0.1)`,
                      border: `1px solid rgba(220, 38, 38, 0.3)`,
                      borderRadius: `${R.sm}px`,
                      padding: '10px 12px',
                      animation: `slideInDown 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)`,
                      fontWeight: 500,
                    }}
                  >
                    ✗ {error}
                  </div>
                )}

                {/* Submit button */}
                <button
                  type="submit"
                  disabled={!passcode || isSubmitting}
                  style={{
                    padding: '12px 24px',
                    fontSize: F.md,
                    fontWeight: 700,
                    background: !passcode || isSubmitting ? `rgba(99, 102, 241, 0.3)` : C.brand,
                    color: '#fff',
                    border: 'none',
                    borderRadius: `${R.md}px`,
                    cursor: passcode && !isSubmitting ? 'pointer' : 'default',
                    opacity: !passcode || isSubmitting ? 0.5 : 1,
                    transition: 'all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)',
                    textTransform: 'uppercase',
                    letterSpacing: '1.5px',
                    boxShadow: passcode && !isSubmitting ? `0 0 20px rgba(99, 102, 241, 0.4)` : 'none',
                    position: 'relative',
                    overflow: 'hidden',
                  }}
                  onMouseEnter={(e) => {
                    if (passcode && !isSubmitting) {
                      (e.currentTarget as any).style.transform = 'translateY(-2px)';
                      (e.currentTarget as any).style.boxShadow = `0 0 30px rgba(99, 102, 241, 0.6), 0 8px 16px rgba(0, 0, 0, 0.3)`;
                    }
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as any).style.transform = 'translateY(0)';
                    (e.currentTarget as any).style.boxShadow = passcode
                      ? `0 0 20px rgba(99, 102, 241, 0.4)`
                      : 'none';
                  }}
                >
                  {isSubmitting ? '⏳ Verifying...' : '→ Enter Dashboard'}
                </button>
              </form>

              {/* Divider */}
              <div style={{ margin: '28px 0', height: '1px', background: `rgba(255, 255, 255, 0.1)` }} />

              {/* Footer info */}
              <div style={{ fontSize: F.xs, color: C.muted, lineHeight: 1.6 }}>
                <p style={{ margin: '0 0 6px 0', fontWeight: 500 }}>🚀 9-Agent LLM Ensemble</p>
                <p style={{ margin: 0, opacity: 0.8 }}>Real-time decision transparency & learning</p>
              </div>
            </div>
          </div>

          {/* Bottom accent */}
          <div
            style={{
              marginTop: '32px',
              height: '1px',
              background: `linear-gradient(90deg, transparent, rgba(99, 102, 241, 0.3), transparent)`,
              animation: `pulse-subtle 3s ease-in-out infinite`,
            }}
          />
        </div>

        {/* Global styles for animations */}
        <style>{`
          @keyframes float {
            0%, 100% {
              transform: translateY(0px) translateX(0px);
            }
            33% {
              transform: translateY(30px) translateX(10px);
            }
            66% {
              transform: translateY(-20px) translateX(-10px);
            }
          }

          @keyframes bounce {
            0%, 100% {
              transform: translateY(0);
            }
            50% {
              transform: translateY(-12px);
            }
          }

          @keyframes slideInUp {
            from {
              opacity: 0;
              transform: translateY(40px);
            }
            to {
              opacity: 1;
              transform: translateY(0);
            }
          }

          @keyframes slideInDown {
            from {
              opacity: 0;
              transform: translateY(-10px);
            }
            to {
              opacity: 1;
              transform: translateY(0);
            }
          }

          @keyframes expand {
            from {
              width: 0;
            }
            to {
              width: 100%;
            }
          }

          @keyframes pulse-subtle {
            0%, 100% {
              opacity: 0.3;
            }
            50% {
              opacity: 0.7;
            }
          }

          input:disabled {
            opacity: 0.6;
          }

          button:active:not(:disabled) {
            transform: scale(0.98);
          }
        `}</style>
      </div>
    </>
  );
}
