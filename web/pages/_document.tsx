import { Html, Head, Main, NextScript } from 'next/document';

export default function Document() {
  return (
    <Html lang="en">
      <Head>
        {/* Viewport is set via next/head in _app or per-page; charset is auto-injected by Next.js */}
        {/* Inter font from Google Fonts */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
        {/* Favicon */}
        <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='6' fill='%236366f1'/><text x='50%25' y='55%25' dominant-baseline='middle' text-anchor='middle' fill='white' font-size='18' font-family='system-ui' font-weight='bold'>W</text></svg>" />
        {/* Primary meta */}
        <meta name="description" content="WAGMI — AI-powered crypto trading bot with real-time signals, LLM decision analysis, copy-trade intelligence, and backtested proof." />
        {/* Open Graph */}
        <meta property="og:title" content="WAGMI — AI-Powered Crypto Trading Bot" />
        <meta property="og:description" content="Real-time signals, LLM brain analysis, copy-trade intelligence, and backtested proof." />
        <meta property="og:type" content="website" />
        <meta property="og:site_name" content="WAGMI" />
        <meta property="og:url" content="https://wagmi.trade" />
        <meta property="og:image" content="https://wagmi.trade/og-image.png" />
        {/* Twitter Card */}
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="WAGMI — AI-Powered Crypto Trading Bot" />
        <meta name="twitter:description" content="Real-time signals, LLM brain analysis, copy-trade intelligence, and backtested proof." />
        <meta name="twitter:image" content="https://wagmi.trade/og-image.png" />
        {/* Robots / indexing */}
        <meta name="robots" content="index, follow" />
        {/* Theme */}
        <meta name="theme-color" content="#0a0f1e" />
        {/* Global styles */}
        <style>{`
          *, *::before, *::after { box-sizing: border-box; }
          html {
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            scroll-behavior: smooth;
          }
          body { margin: 0; padding: 0; background: #0a0f1e; color: #f1f5f9; }
          a { color: inherit; text-decoration: none; }
          button { font-family: inherit; cursor: pointer; }
          code, pre { font-family: 'JetBrains Mono', 'Fira Code', monospace; }

          /* ── CSS custom properties (design system tokens) ─────────── */
          :root {
            /* Brand */
            --color-brand: #6366f1;
            --color-brand-dark: #4f46e5;
            --color-brand-glow: rgba(99,102,241,0.15);

            /* Semantic */
            --color-bull: #16a34a;
            --color-bear: #dc2626;
            --color-warn: #d97706;
            --color-info: #2563eb;

            /* Dark surfaces */
            --color-bg: #0a0f1e;
            --color-surface: #111827;
            --color-surface-hover: #1e293b;
            --color-card: #1a2236;
            --color-border: #2d3748;
            --color-border-bright: #4a5568;

            /* Text */
            --color-text: #f1f5f9;
            --color-text-sub: #cbd5e1;
            --color-muted: #64748b;

            /* Radii */
            --radius-sm: 6px;
            --radius-md: 10px;
            --radius-lg: 16px;
            --radius-pill: 9999px;
          }

          /* Skip-to-content link (hidden until focused) */
          .skip-to-content {
            position: absolute;
            top: -100%;
            left: 12px;
            z-index: 9999;
            padding: 8px 16px;
            background: #6366f1;
            color: #fff;
            font-size: 14px;
            font-weight: 600;
            border-radius: 0 0 6px 6px;
            text-decoration: none;
            transition: top 0.15s ease;
          }
          .skip-to-content:focus { top: 0; outline: none; }

          /* Focus-visible ring for keyboard navigation */
          :focus-visible {
            outline: 2px solid #6366f1;
            outline-offset: 2px;
          }
          /* Suppress focus ring for mouse/touch interactions */
          :focus:not(:focus-visible) { outline: none; }

          /* Skeleton pulse animation */
          @keyframes skeletonPulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
          }
          .skeleton {
            background: #1e293b;
            border-radius: 6px;
            animation: skeletonPulse 1.4s ease-in-out infinite;
          }

          /* Activity ticker scroll */
          @keyframes tickerScroll {
            0% { transform: translateX(0); }
            100% { transform: translateX(-50%); }
          }

          /* Fade in cards */
          @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(12px); }
            to   { opacity: 1; transform: translateY(0); }
          }
          .fade-in { animation: fadeInUp 0.3s ease both; }

          /* Scrollbar styling */
          ::-webkit-scrollbar { width: 6px; height: 6px; }
          ::-webkit-scrollbar-track { background: #111827; }
          ::-webkit-scrollbar-thumb { background: #374151; border-radius: 3px; }
          ::-webkit-scrollbar-thumb:hover { background: #4a5568; }

          /* Table base */
          table { border-collapse: collapse; width: 100%; }
          th { text-align: left; }
        `}</style>
      </Head>
      <body>
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
