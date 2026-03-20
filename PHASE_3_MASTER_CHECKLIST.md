# Phase 3: Master Deployment Checklist

**Purpose:** Complete step-by-step checklist for Phase 3A, 3B-1, 3B-2, and 3C execution
**Format:** Checkbox list for tracking
**Status:** Ready for immediate execution

---

## Phase 3A: Staging Deployment (24 hours)

### Pre-Deployment (T-0h)

#### Environment Setup
- [ ] Staging server/environment prepared
- [ ] Python 3.10+ installed
- [ ] Virtual environment created: `python3.10 -m venv venv_staging`
- [ ] Virtual environment activated: `source venv_staging/bin/activate`
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] Verify key installs: `python -c "import pandas, ccxt, anthropic; print('OK')"`

#### Configuration
- [ ] `.env` created from `.env.example`
- [ ] ENVIRONMENT=paper verified in `.env`
- [ ] STARTING_EQUITY set to desired amount
- [ ] API keys left blank (paper trading mode)
- [ ] All required variables set

#### Code Verification
- [ ] Pre-flight validation run: `python PHASE_3_PREFLIGHT_VALIDATION.py`
- [ ] All critical files compile successfully
- [ ] All Phase 2 fixes present in code
- [ ] Git branch confirmed: `claude/analyze-paper-trading-UjWeZ`
- [ ] Working tree clean: `git status`

#### Database Setup
- [ ] Database directory exists: `bot/data/`
- [ ] Database created or will auto-create on first run
- [ ] Schema migrations ready

#### Monitoring Setup
- [ ] PHASE_3A_STAGING_MONITOR.py copied to deployment location
- [ ] Monitoring script tested locally: `python PHASE_3A_STAGING_MONITOR.py`
- [ ] Log directory exists: `bot/data/logs/`
- [ ] Alert system configured (if using)

### Deployment (T+0h)

#### Bot Startup
- [ ] Run bot in paper mode: `cd bot && python run.py paper &`
- [ ] Capture bot PID for monitoring
- [ ] Verify no startup errors in logs
- [ ] Verify market data connecting
- [ ] Verify exchange API responding

#### Initial Monitoring
- [ ] Take baseline snapshot: `python PHASE_3A_STAGING_MONITOR.py`
- [ ] Memory baseline: <50 MB
- [ ] Database baseline: 0 bytes (fresh)
- [ ] Confirm bot running: `ps aux | grep python | grep run.py`

### Hourly Checkpoints (T+1h through T+24h)

#### Every Hour: Automated Checks
- [ ] Memory usage snapshot (via monitor script)
- [ ] Database size check
- [ ] Trade count check
- [ ] Signal count check
- [ ] Error log scan

#### T+1:00 Checkpoint
- [ ] At least 1 signal evaluated? YES/NO
- [ ] Memory <75 MB? YES/NO
- [ ] No ERROR logs? YES/NO
- [ ] Status: GOOD/INVESTIGATE

#### T+2:00 Checkpoint
- [ ] Market data flowing? YES/NO
- [ ] Ensemble voting working? YES/NO
- [ ] LLM decision engine responding? YES/NO
- [ ] Status: GOOD/INVESTIGATE

#### T+4:00 Checkpoint (First Trade Target)
- [ ] At least 1 trade executed? YES/NO
- [ ] Trade properly recorded in DB? YES/NO
- [ ] Risk sizing applied correctly? YES/NO
- [ ] Status: GOOD/INVESTIGATE

#### T+8:00 Checkpoint
- [ ] Memory growth rate <1 MB/hour? YES/NO
- [ ] Database growth rate <2 MB/hour? YES/NO
- [ ] At least 3 trades attempted? YES/NO
- [ ] Circuit breaker not falsely triggered? YES/NO
- [ ] TTL pruning scheduled? YES/NO
- [ ] Status: GOOD/INVESTIGATE

#### T+12:00 Checkpoint
- [ ] Minimum 5 trades executed? YES/NO
- [ ] First trade closures occurring? YES/NO
- [ ] Deep memory recording trades? YES/NO
- [ ] Feedback loop updating weights? YES/NO
- [ ] No cascading errors? YES/NO
- [ ] Status: GOOD/INVESTIGATE

#### T+16:00 Checkpoint
- [ ] Memory <100 MB? YES/NO
- [ ] Database <20 MB? YES/NO
- [ ] All gates working (slippage, liquidation)? YES/NO
- [ ] Alert system verified? YES/NO
- [ ] No unhandled exceptions? YES/NO
- [ ] Status: GOOD/INVESTIGATE

### Final Assessment (T+24h)

#### Success Criteria Validation
- [ ] At least 5 trades executed? YES/NO
- [ ] Memory <100 MB throughout? YES/NO
- [ ] Database <20 MB throughout? YES/NO
- [ ] No circuit breaker false re-trips? YES/NO
- [ ] All safety gates working? YES/NO
- [ ] Zero ERROR logs? YES/NO
- [ ] System stable for 24 hours? YES/NO
- [ ] TTL pruning/archival on schedule? YES/NO
- [ ] No unhandled exceptions? YES/NO
- [ ] Position manager working correctly? YES/NO
- [ ] Trade outcomes recorded correctly? YES/NO
- [ ] Feedback loop updating strategy weights? YES/NO

#### Final Report Generation
- [ ] Generate final snapshot: `python PHASE_3A_STAGING_MONITOR.py`
- [ ] Create final report: `PHASE_3A_FINAL_REPORT.md`
- [ ] Backup all data: `tar czf phase3a_backup_$(date +%s).tar.gz bot/data/`
- [ ] Document any anomalies or issues
- [ ] Sign off on Phase 3A results

#### Decision Point
- [ ] All 12 success criteria PASSED?
  - **YES → Proceed to Phase 3B-1**
  - **NO → Investigate and retry Phase 3A**

---

## Phase 3B-1: Production Initial Deployment (24 hours)

### Pre-Deployment (T+24h to T+24.5h)

#### Production Environment Preparation
- [ ] Production server/cloud instance prepared
- [ ] Python 3.10+ installed
- [ ] Virtual environment created
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] Database initialized

#### Production Configuration
- [ ] `.env.production` created from `.env.example`
- [ ] ENVIRONMENT=production configured
- [ ] Real Hyperliquid API credentials added (SECURE!)
- [ ] Anthropic API key configured
- [ ] STARTING_EQUITY set to real balance
- [ ] RISK_PER_TRADE set conservatively (2%)
- [ ] MAX_LEVERAGE set conservatively (2.0x)
- [ ] MAX_OPEN_POSITIONS set conservatively (2)
- [ ] Symbols: BTC, SOL (conservative starter set)

#### Pre-Flight Checks
- [ ] Exchange connectivity verified
- [ ] Exchange balance confirmed
- [ ] API rate limits understood
- [ ] LLM connectivity verified
- [ ] Database ready
- [ ] Monitoring setup ready

### Deployment (T+24.5h)

#### Production Bot Startup
- [ ] Run bot in production: `cd bot && python run.py paper` (switch to production after validation)
- [ ] Capture bot PID
- [ ] Verify no startup errors
- [ ] Verify exchange connected
- [ ] Verify API responding

#### Initial Production Validation
- [ ] Real exchange balance confirmed
- [ ] Real slippage measured
- [ ] Real fees charged correctly
- [ ] API rate limits adequate
- [ ] Execution latency acceptable

### Monitoring (24 hours, T+24.5h to T+48.5h)

#### Real-Time Monitoring
- [ ] Continuous log monitoring
- [ ] Hourly health snapshots
- [ ] Trade execution tracking
- [ ] Real PnL tracking

#### Critical Metrics
- [ ] Memory <100 MB? Continuous
- [ ] Database <20 MB? Continuous
- [ ] Trades executing? Yes
- [ ] Slippage acceptable? Yes
- [ ] Fees correct? Yes
- [ ] Liquidation checks working? Yes
- [ ] Circuit breaker not re-tripping? Yes

### Phase 3B-1 Decision (T+48.5h)

#### Stability Check
- [ ] System ran stably for 24 hours? YES/NO
- [ ] All success criteria from Phase 3A still met? YES/NO
- [ ] Real trading working correctly? YES/NO
- [ ] No new issues discovered? YES/NO
- [ ] PnL reasonable (not necessarily positive, but realistic)? YES/NO

#### Decision Point
- [ ] All checks PASSED?
  - **YES → Proceed to Phase 3B-2 (Scale)**
  - **NO → Investigate and fix before scaling**

---

## Phase 3B-2: Scale to Full Symbol Set (24 hours)

### Pre-Deployment (T+48.5h to T+49h)

#### Scaling Plan
- [ ] List all configured symbols
- [ ] Plan gradual scale-up (not all at once)
- [ ] Phase 3B-2a: Add 5 more symbols (12 hours)
- [ ] Phase 3B-2b: Add remaining symbols (12 hours)
- [ ] Monitoring intensified for scale transition

### Phase 3B-2a: Initial Scale (T+49h to T+61h)

#### Gradual Addition
- [ ] Add 5 new symbols: ETH, AVAX, ARB, OP, DOGE (or configured subset)
- [ ] Monitor portfolio effects
- [ ] Check correlation distribution
- [ ] Verify leverage not excessive
- [ ] Monitor for new issues

#### Metrics During Scale
- [ ] Memory growth rate acceptable? YES/NO
- [ ] Database growth rate acceptable? YES/NO
- [ ] Portfolio correlation healthy? YES/NO
- [ ] Leverage distribution good? YES/NO
- [ ] No new API errors? YES/NO

### Phase 3B-2b: Full Scale (T+61h to T+72h)

#### Complete Symbol Set
- [ ] Add all remaining configured symbols
- [ ] Final portfolio monitoring
- [ ] Full-scale stability check (12 hours)

#### Final Metrics
- [ ] All symbols trading? YES/NO
- [ ] Portfolio metrics healthy? YES/NO
- [ ] No concentration risks? YES/NO
- [ ] System stable at full scale? YES/NO

### Go-Live Decision (T+72h)

#### Final Assessment
- [ ] Phase 3A PASSED? YES
- [ ] Phase 3B-1 PASSED? YES
- [ ] Phase 3B-2 PASSED? YES
- [ ] All success criteria maintained? YES
- [ ] System ready for continuous operation? YES

#### Decision
- **✅ GO-LIVE APPROVED** or **❌ REMEDIATE ISSUE**

---

## Phase 3C: Configuration Hardening (Optional, Parallel)

**Can be applied during Phase 3B-1 or Phase 3B-2 without stopping trading**

### Pre-Implementation
- [ ] Review all 5 fixes: PHASE_3C_CONFIGURATION_HARDENING.md
- [ ] Understand each fix thoroughly
- [ ] Test each fix in staging first (if time permits)

### Implementation (3-4 hours parallel work)

#### Fix 1: Circuit Breaker Exception Handling (30 min)
- [ ] Review code in `bot/execution/risk.py`
- [ ] Implement try/except wrapper
- [ ] Test exception handling
- [ ] Verify fail-safe behavior

#### Fix 2: Database Health Checks (45 min)
- [ ] Implement `check_database_health()` function
- [ ] Integrate into signal pipeline Gate 0
- [ ] Test DB failure detection
- [ ] Verify trading stops on DB error

#### Fix 3: LLM Unavailability Tracking (30 min)
- [ ] Implement LLMAvailability tracking
- [ ] Update decide() function
- [ ] Configure alert thresholds
- [ ] Test silent failure detection

#### Fix 4: Reconciliation Startup Gate (20 min)
- [ ] Update run() function
- [ ] Make reconciliation mandatory
- [ ] Add graceful exit if failed
- [ ] Test startup gate

#### Fix 5: Position SL/TP Persistence (45 min)
- [ ] Implement position backup to disk
- [ ] Implement recovery from backup
- [ ] Test crash recovery
- [ ] Verify original SL/TP restored

### Verification
- [ ] All 5 fixes applied without errors
- [ ] Code compiles without syntax errors
- [ ] Phase 2 tests still pass
- [ ] Trading continues normally
- [ ] New defensive features working

### Rollback (if needed)
- [ ] Comment out problematic fix
- [ ] Restart trading
- [ ] Investigate
- [ ] Retry fix after correction

---

## Post-Deployment (Ongoing)

### Daily Operations
- [ ] Daily health check (every 12 hours)
- [ ] Daily PnL review
- [ ] Error log review
- [ ] Memory/database trend analysis
- [ ] Generate daily report

### Weekly Review
- [ ] Week summary statistics
- [ ] Performance analysis
- [ ] System improvements planned
- [ ] Risk assessment

### Monthly Maintenance
- [ ] Full system review
- [ ] Performance benchmarking
- [ ] Configuration optimization
- [ ] Documentation updates

---

## Summary

**Total Checkpoints:**
- Phase 3A: 1 initial + 7 hourly + 1 final = 9 checkpoints
- Phase 3B-1: 1 initial + hourly + 1 final = continuous
- Phase 3B-2: 2 phases + 1 final = 3 checkpoints
- Phase 3C: 5 implementation tasks (parallel)

**Total Time:**
- Phase 3A: 24 hours
- Phase 3B-1: 24 hours
- Phase 3B-2: 24 hours
- Phase 3C: 3-4 hours (parallel)
- **Total: 72-96 hours to complete Phase 3**

---

**This checklist ensures nothing is missed during Phase 3 execution.**

Use it as your primary operational guide from T+0 (now) through T+72h (go-live).

---

**Created:** 2026-03-20 23:50 UTC
**Version:** 1.0 Final
**Status:** Ready for execution
