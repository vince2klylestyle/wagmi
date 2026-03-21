# Data Pipeline Audit Report — nunuIRL Trading Bot

## Executive Summary
The data pipeline is **well-architected** with multi-layer resilience: exchange fallback chains, circuit breakers, in-memory caching, disk caching (backtest reproducibility), OHLCV validation, and staleness detection. Potential issues identified are primarily around **concurrent access**, **race conditions**, and **data mutation**.

---

## 1. DATA SOURCES & EXCHANGE CHAIN

### Primary Exchanges
**CCXT Priority Chain (per symbol):**
- **BTC/ETH/SOL**: Hyperliquid (primary) → Kraken → Bybit → CoinGecko
- **HYPE**: Hyperliquid (primary) → CoinGecko
- **PEPE**: Hyperliquid (as KPEPE) → Kraken → Bybit → CoinGecko
- **ALTs** (XRP, AVAX, LINK, etc.): Hyperliquid (primary) → Bybit → CoinGecko

**Fallback Chain:**
```
CCXT (Hyperliquid/Kraken/Bybit)
    ↓ (if unavailable)
CoinGecko API (30/90-day history)
    ↓ (if offline)
Disk cache (backtest mode only)
    ↓ (if no current data)
FAILURE → signal generation SKIPPED
```

**File:** `/home/user/WAGMI/bot/data/fetcher.py` lines 147-167 (symbol_exchanges mapping)

---

## 2. DATA REFRESH CYCLE

### Timing
- **Scan interval:** Configurable (default 15-60s in paper trading)
- **Cache TTL:** 45 seconds (default), configurable
- **Staleness threshold:** 300 seconds (5 minutes) + timeframe period

### Refresh Points
1. **Entry point:** `MultiStrategyBot.run()` → main loop at `/home/user/WAGMI/bot/multi_strategy_main.py:873`
2. **Per-symbol fetch:** `_process_symbol()` calls `fetcher.fetch_multi_timeframe()` at line 1785
3. **Concurrent fetching:** 5 workers max, ThreadPoolExecutor for parallel timeframe requests
4. **Open position monitoring:** Exit Agent refreshes data on all open positions (async)

### Cache Strategy
```
In-Memory Cache (45s TTL)
    ↓ check `_cache` dict (thread-safe with Lock)
Disk Cache (backtest mode)
    ↓ check `{symbol}_{timeframe}_{days}d.csv`
Exchange API Call (CCXT or CoinGecko)
    ↓ rate-limited per exchange
```

**Files:**
- `/home/user/WAGMI/bot/data/fetcher.py:336-346` (in-memory cache)
- `/home/user/WAGMI/bot/data/fetcher.py:350-381` (disk cache)

---

## 3. RETRY LOGIC & CIRCUIT BREAKER

### Retry Strategy
**Exponential backoff with jitter:**
- Max retries: 3 (default)
- Initial delay: 5 seconds
- Backoff factor: ~1.5x + random jitter
- File: `/home/user/WAGMI/bot/data/fetcher.py:129-140` (constructor)

### Circuit Breaker (Per-Exchange)
**State machine:**
- **Closed:** Normal operation (accept requests)
- **Open:** Exchange down (skip requests for `reset_s` seconds)
- **Half-open:** Allow 1 probe request after `reset_s` has elapsed

**Thresholds:**
- Opens after 5 consecutive failures (configurable)
- Resets after 300 seconds (5 minutes)
- File: `/home/user/WAGMI/bot/data/fetcher.py:69-113` (ExchangeCircuitBreaker class)

**Graceful degradation:**
- If Hyperliquid down: Fallback to Kraken/Bybit
- If all CCXT exchanges down: Use CoinGecko
- If all data sources fail: Skip signal generation for that symbol
- File: `/home/user/WAGMI/bot/multi_strategy_main.py:1776-1790` (_process_symbol, graceful degradation)

---

## 4. OHLCV DATA VALIDATION

### Per-Candle Integrity Checks
**`_validate_ohlcv()` at `/home/user/WAGMI/bot/data/fetcher.py:199-250`:**

| Check | Rule | Action |
|-------|------|--------|
| NaN/Inf | Remove rows with NaN or ±Inf | Drop invalid candles |
| OHLC Relationship | High ≥ Open, High ≥ Close, Low ≤ Open | Drop |
| Low ≤ Close | High ≥ Low | Drop |
| Positivity | Close > 0, Open > 0 | Drop |
| Volume | Volume ≥ 0 | Drop |

**Threshold:** Drop if >10% of candles invalid (warn); <10% silently drop

### Data Continuity Check
**`_check_data_continuity()` at `/home/user/WAGMI/bot/data/fetcher.py:385-399`:**
- Gap detection: >2.5x timeframe interval
- Example: 5m candles with gap >12.5 minutes triggers warning
- **Does NOT modify data** — only logs; strategy must handle missing data

**File:** `/home/user/WAGMI/bot/data/fetcher.py:385-425`

---

## 5. DATABASE SCHEMA & PERSISTENCE

### SQLite Tables (/home/user/WAGMI/bot/data/db.py)
| Table | Purpose | Retention | Key Fields |
|-------|---------|-----------|-----------|
| `signals` | Every signal generated | Unlimited | timestamp, symbol, strategy, confidence, traded |
| `trades` | Position events (OPEN, TP1, SL, etc.) | Unlimited | timestamp, symbol, action, pnl, fee |
| `equity_snapshots` | Periodic equity curve | Unlimited | timestamp, equity, open_positions, daily_pnl |
| `signal_outcomes` | Closed trade analysis | Unlimited | signal_id, pnl, pnl_pct, win, score |
| `health_events` | Bot health (stalls, errors) | Unlimited | timestamp, event_type, severity |
| `signal_rejections` | Rejected signals + gate | Unlimited | timestamp, gate, reason |
| `performance_daily` | Daily aggregation | Unlimited | date, symbol, strategy, trades, wins, pnl |
| `sniper_queue` | LLM sniper proposals | Unlimited | id, symbol, status, created_at |

**Indexes:** 13 indices on timestamp, symbol, strategy, status, gate (db.py:133-162)

**Concurrency:**
- WAL mode enabled (`PRAGMA journal_mode=WAL`)
- Per-connection with 10s timeout
- Thread-local connections

**File:** `/home/user/WAGMI/bot/data/db.py:24-170`

### Migrations System
- Version-based migrations (applied once, tracked in `_migrations` table)
- Idempotent (duplicate-column errors silently ignored)
- Current migration: v2 (sniper_queue table)
- File: `/home/user/WAGMI/bot/data/migrations.py:37-64`

---

## 6. DATA FLOW DIAGRAM

```
┌─────────────────────────────────────────────────────────────────┐
│  SIGNAL GENERATION CYCLE (every 15-60s per symbol)              │
└─────────────────────────────────────────────────────────────────┘

1. MAIN LOOP (multi_strategy_main.py:873)
   ↓
2. _process_symbol(symbol)  [line 1774]
   ↓
3a. fetch_multi_timeframe()  [line 1785]
    ├─ Check in-memory cache (45s TTL)
    ├─ Check disk cache (backtest mode)
    ├─ Concurrent CCXT fetch (ThreadPoolExecutor, 5 workers)
    │  ├─ Hyperliquid → Kraken → Bybit
    │  └─ Circuit breaker check per exchange
    ├─ Fallback to CoinGecko (if CCXT unavailable)
    ├─ Validate OHLCV (drop invalid candles)
    ├─ Check continuity (warn on gaps >2.5x period)
    └─ Cache result (memory + disk)
   ↓
3b. Get latest price
    └─ latest_price() calls fetch_ohlcv("1m") or ticker
   ↓
3c. Check stale data [line 1815-1847]
    ├─ Last candle age > (period + 5min)?
    ├─ YES → Skip signal generation (still process open positions)
    └─ NO → Proceed to strategy evaluation
   ↓
4. Run ensemble.evaluate(symbol, data)  [line 1858]
   ├─ Call each strategy.evaluate(symbol, data)
   │  ├─ strategy returns Optional[Signal]
   │  └─ deepcopy(signal) before mutation ← CRITICAL
   ├─ Merge votes → weighted_veto mode
   └─ Return AnnotatedSignal with merger metadata
   ↓
5. Signal filtering (risk_filter_chain.evaluate) [signal_pipeline.py]
   ├─ Gate 1: Validity (R:R, stop width, side)
   ├─ Gate 2: Circuit breaker
   ├─ Gate 3: Position limits
   ├─ Gate 4: Leverage decision
   ├─ Gate 5: Liquidation safety
   ├─ Gate 6: Portfolio risk
   └─ Log rejections if enabled
   ↓
6a. IF APPROVED: Execute trade
    └─ Log to trades table
   ↓
6b. REJECTION: Log to signal_rejections table
    └─ Continue to next symbol
   ↓
7. UPDATE POSITIONS (exit management)
   ├─ Check SL/TP for all open positions
   └─ Log closes to trades table
   ↓
8. LOG EQUITY SNAPSHOT
   └─ equity_snapshots table
```

---

## 7. STALENESS DETECTION

### Detection Points

**1. Fetcher level (is_data_stale):**
```python
# /home/user/WAGMI/bot/data/fetcher.py:252-267
get_data_freshness(symbol, timeframe) → seconds since last fetch
is_data_stale(symbol, timeframe, max_age_s=300)
```

**2. Multi-strategy level (candle age check):**
```python
# /home/user/WAGMI/bot/multi_strategy_main.py:1815-1847
_stale_check_tf = "5m" or "1h"
last_candle_time from dataframe
candle_age_s = now - last_candle_time
if candle_age_s > period_s + 300:
    SKIP SIGNAL GENERATION
else:
    PROCEED
```

**Thresholds:**
- 5m candles: stale if >425s old (5m period + 5min tolerance)
- 1h candles: stale if >3900s old (1h period + 5min tolerance)

**File:** `/home/user/WAGMI/bot/multi_strategy_main.py:1815-1847`

---

## 8. CRASH RECOVERY & RECONCILIATION

### Startup Reconciliation
**On bot start (/home/user/WAGMI/bot/multi_strategy_main.py:850-871):**
1. Call `reconcile_positions()` from execution module
2. Query Hyperliquid for all open positions
3. Compare with in-memory position manager
4. Restore any missing positions
5. Reconcile funding rates and open interest

**File:** `/home/user/WAGMI/bot/multi_strategy_main.py:850-871` (_reconcile_exchange_positions)

### Circuit Breaker State Persistence
**Survives restarts during drawdowns:**
```python
# /home/user/WAGMI/bot/multi_strategy_main.py:897-899
restore_circuit_breaker_state(self.risk_mgr.circuit_breaker)
```
- Persists to disk when circuit breaker triggers
- Reloaded on next startup
- Prevents aggressive re-entry during consecutive losses

---

## 9. POTENTIAL DATA CORRUPTION SCENARIOS

### CRITICAL: In-Place Signal Mutation
**Bug location:** `/home/user/WAGMI/bot/strategies/ensemble.py` (partially mitigated)

**Scenario:**
```python
# BAD (pre-deepcopy):
signals = ensemble.evaluate(symbol, data)
for sig in signals:
    sig.metadata["custom_field"] = value  # MUTATES shared signal!

# GOOD (current code):
signals = [deepcopy(s) for s in signals]  # line 377
self._last_signals[symbol] = {s.strategy: deepcopy(s) for s in signals}  # line 380
```

**Mitigation:** Deepcopy signals before passing to downstream consumers
- File: `/home/user/WAGMI/bot/strategies/ensemble.py:346, 377, 380, 605-606, 716`

### Race Condition: Concurrent Cache Reads/Writes
**File:** `/home/user/WAGMI/bot/data/fetcher.py:336-346`

**Code:**
```python
def _get_cached(self, key):
    with self._lock:  # ← PROTECTED
        if key in self._cache:
            ts, df = self._cache[key]
            if time.time() - ts < self.cache_ttl:
                return df.copy()  # ← Returns COPY, not reference
    return None

def _set_cache(self, key, df):
    with self._lock:  # ← PROTECTED
        self._cache[key] = (time.time(), df.copy())
```

**Status:** SAFE — Lock protects all access, copies prevent external mutation

### Race Condition: Stale Data Between Fetch and Evaluation
**Scenario:**
```
Thread A: Fetch 1h data at T=0
Thread B: Fetch 1h data at T=30s (gets cached copy from T=0)
         Evaluates stale data at T=0 as if it's current

Protection:
- Staleness check at _process_symbol() before strategy eval
- Candle age check compares to current time
- If data older than period + 5min, SKIP signal generation
```

**File:** `/home/user/WAGMI/bot/multi_strategy_main.py:1815-1847`

### Data Continuity Gaps (Not Corruption)
**Scenario:** Exchange returns incomplete OHLCV (missing candles)

**Handling:**
- Logged as warning (gaps >2.5x period)
- Data returned unchanged (does not interpolate)
- Strategies must handle missing data gracefully

**File:** `/home/user/WAGMI/bot/data/fetcher.py:385-425` (_check_data_continuity)

### SQLite WAL Mode Crash
**Scenario:** Bot crashes while writing to SQLite

**Protection:**
- WAL mode enabled (write-ahead logging)
- Rollback on exception in all write operations
- Example: `/home/user/WAGMI/bot/data/db.py:196-203` (log_signal try/except/rollback)

**Files:** `/home/user/WAGMI/bot/data/db.py:27-32` (WAL pragma), `/home/user/WAGMI/bot/data/db.py:180-203` (try/except/rollback pattern)

---

## 10. MISSING TIMEFRAME HANDLING

### Strategy Requirements
**Each strategy declares `get_required_timeframes()`:**

| Strategy | Requires |
|----------|----------|
| RegimeTrend | 1h, 6h, 1d |
| MonteCarlo | 1d |
| ConfidenceScorer | 5m, 1h |
| MultiTierQuality | 5m, 1h |
| FundingRate | 1h |
| OIDelta | 1h |
| Bollinger | 1h |
| VmcCipher | 1h |
| LeadLag | 5m, 1h (BTC) |

**Ensemble aggregates:**
```python
# /home/user/WAGMI/bot/strategies/ensemble.py
needed_tfs = ensemble.get_all_required_timeframes()
# Returns: ["5m", "1h", "6h", "1d"]
```

**If timeframe missing:**
- Strategy returns `None` (no signal)
- Ensemble proceeds (strategy counts as no vote)
- If majority of strategies fail: ensemble votes = 0

**File:** `/home/user/WAGMI/bot/multi_strategy_main.py:540` (_needed_tfs aggregation)

### Fallback Behavior
**No automatic interpolation or upsampling:**
- If 5m data missing: ConfidenceScorer returns None
- If 1h missing: Most strategies return None
- System allows partial data → some strategies return signals, others don't

**Best practice:** Ensure all fetches complete before passing to ensemble

---

## 11. PRICING DATA

### Latest Price Fetch
**Two entry points:**

1. **Snapshot entry** (signal generation):
   ```python
   current_price = self.fetcher.latest_price(symbol, sym_cfg.coingecko_id)
   # At signal fire time
   ```

2. **Live entry** (execution):
   ```python
   live_price = self.price_store.get_price(symbol)
   # From PriceStore cache (updated async)
   ```

**Files:**
- `/home/user/WAGMI/bot/data/fetcher.py:871-920` (latest_price method)
- `/home/user/WAGMI/bot/data/price_store.py` (PriceStore class)

### Price Validation
- Check price > 0
- Check source (Hyperliquid, CoinGecko, etc.)
- Staleness detection: Default 5 seconds (configurable)

**File:** `/home/user/WAGMI/bot/data/price_store.py:32-50`

---

## 12. RATE LIMITING

### Per-Exchange Rate Limits
**Enforced with thread-safe wait:**

```python
# /home/user/WAGMI/bot/data/fetcher.py:323-332
_exchange_rate_limits = {
    "hyperliquid": 0.25s,  # 4 req/sec max
    "kraken": 0.5s,        # 2 req/sec max
    "bybit": 0.15s,        # ~6 req/sec max
}

def _ccxt_rate_limit(self, ex_name):
    with self._lock:
        wait = calculate_wait_time()
        self._last_exchange_request_ts[ex_name] = time.time() + max(0, wait)
    if wait > 0:
        time.sleep(wait)
```

**File:** `/home/user/WAGMI/bot/data/fetcher.py:181-186` (rate limit config), `/home/user/WAGMI/bot/data/fetcher.py:323-332` (enforcement)

---

## 13. KNOWN ISSUES & RECOMMENDATIONS

### HIGH PRIORITY

1. **Missing Data Mutation Defense in Signal Handling**
   - Problem: Signals passed to multiple downstream handlers; if one mutates metadata, others see changes
   - Current: Ensemble uses deepcopy (good)
   - Gap: Signal pipeline and execution layer should also deepcopy
   - Fix: Add `signal = deepcopy(signal)` in `signal_pipeline.py` before evaluation

2. **No Explicit Data Freshness Validation Before Backtest**
   - Problem: Backtest can run on disk cache without verifying age
   - Fix: Add `max_cache_age_days` config; reject disk cache if older than threshold

3. **CoinGecko Fallback Limited to 90 Days**
   - Problem: If running 180-day backtest, only gets 90 days
   - Fix: Document limitation; use live CCXT for longer backtests

### MEDIUM PRIORITY

4. **Race Between Staleness Check and Strategy Eval**
   - Problem: Small window between staleness check (line 1815) and strategy.evaluate() (line 1858)
   - Fix: Low risk due to 5min tolerance, but could add thread-safe timestamp assertion

5. **No Disk Space Monitoring for Cache**
   - Problem: Backtest cache can grow unbounded
   - Fix: Add LRU eviction or age-based cleanup for `/home/user/WAGMI/bot/data/cache/`

6. **Open Interest & Funding Rate Cached Too Long**
   - Problem: Injected only every 60 ticks (line 1799), but could be stale
   - Fix: Make OI/FR refresh interval configurable

### LOW PRIORITY

7. **Verbose Logging on Every Fetch**
   - Problem: Thousands of log lines per day
   - Fix: Add `--quiet` mode to suppress non-error fetcher logs

8. **No Metrics for Data Freshness**
   - Problem: Can't easily see "what % of signals use fresh data"
   - Fix: Add telemetry for staleness checks passed/skipped

---

## 14. SUMMARY CHECKLIST

| Item | Status | File | Notes |
|------|--------|------|-------|
| Exchange fallback chain | ✓ | fetcher.py:147-167 | 3-4 tier fallback |
| Circuit breaker | ✓ | fetcher.py:69-113 | Per-exchange, 5 failures = open |
| Retry logic | ✓ | fetcher.py:129-140 | Exponential backoff, 3 retries |
| In-memory cache | ✓ | fetcher.py:336-346 | 45s TTL, thread-safe |
| Disk cache | ✓ | fetcher.py:350-381 | Backtest reproducibility |
| OHLCV validation | ✓ | fetcher.py:199-250 | Drops invalid candles, warns if >10% bad |
| Data continuity check | ✓ | fetcher.py:385-425 | Logs gaps >2.5x period |
| Staleness detection | ✓ | multi_strategy_main.py:1815-1847 | 5m tolerance + period |
| Crash recovery | ✓ | multi_strategy_main.py:850-871 | Reconciles positions on startup |
| Signal mutation safety | ~ | ensemble.py:377,380 | Uses deepcopy, but not everywhere |
| Rate limiting | ✓ | fetcher.py:181-186,323-332 | Thread-safe per-exchange |
| Database concurrency | ✓ | db.py:27-32 | WAL mode + per-connection |
| Missing timeframe handling | ✓ | strategies/base.py, ensemble.py | Strategies return None, ensemble proceeds |

---

## 15. DATA FLOW AUDIT COMPLETE

**Overall Assessment:** PRODUCTION-READY with minor hardening needed.

**Risk Level:** LOW (existing resilience is strong)

**Recommended Next Steps:**
1. Add signal deepcopy in signal_pipeline.py (defensive)
2. Document CoinGecko 90-day limit in README
3. Add telemetry for staleness checks
4. Monitor disk cache size during backtests
