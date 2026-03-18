import { Html, Head, Main, NextScript } from 'next/document';

export default function Document() {
  return (
    <Html lang="en">
      <Head>
        {/* Inter font from Google Fonts */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
        {/* Favicon */}
        <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='6' fill='%236366f1'/><text x='50%25' y='55%25' dominant-baseline='middle' text-anchor='middle' fill='white' font-size='18' font-family='system-ui' font-weight='bold'>W</text></svg>" />
        {/* Open Graph */}
        <meta property="og:title" content="WAGMI — AI-Powered Crypto Trading Bot" />
        <meta property="og:description" content="Real-time signals, LLM brain analysis, copy-trade intelligence, and backtested proof." />
        <meta property="og:type" content="website" />
        <meta name="theme-color" content="#0a0f1e" />
        {/* Global styles */}
        <style>{`
          *, *::before, *::after { box-sizing: border-box; }
          html { font-family: 'Inter', system-ui, -apple-system, sans-serif; }
          body { margin: 0; padding: 0; background: #0a0f1e; color: #f1f5f9; }
          a { color: inherit; text-decoration: none; }
          button { font-family: inherit; cursor: pointer; }
          code, pre { font-family: 'JetBrains Mono', 'Fira Code', monospace; }

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
