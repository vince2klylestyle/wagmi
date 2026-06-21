"""
Main entry point for the multi-strategy auto-trading bot.
Wires together all components: data fetcher, strategies, ensemble,
position management, leverage, risk, ML, and alerts.

Usage:
    python multi_strategy_main.py           # Paper trading (default)
    ENVIRONMENT=production python multi_strategy_main.py  # Live trading
"""

import asyncio
import logging
import os
import signal
import sys
import time
import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, Any

import pandas as pd

from data.fetcher import DataFetcher
from data.db import (
    init_db, log_signal, log_trade, log_equity, get_daily_summary,
    update_signal_traded, log_signal_outcome, log_health_event,
    update_daily_performance, get_signal_performance, get_recent_trades,
)
from data.strategy_weights import StrategyWeightManager
from feedback.regime_feedback import RegimeFeedbackManager
from feedback.adaptive_confidence import AdaptiveConfidenceFloor
from feedback.hold_time_rules import HoldTimeRuleManager
from data.risk_log import log_rejection, get_rejection_counts
from data.ml_log import log_ml_stats, log_ml_confidence
from data.trade_log import log_closed_trade
from data.learning import record_trade_outcome, get_performance
from trading_config import TradingConfig, DEFAULT_SYMBOLS, apply_profile, get_symbol_param
from strategies.regime_trend import RegimeTrendStrategy
from strategies.monte_carlo_zones import MonteCarloZonesStrategy
from strategies.confidence_scorer import ConfidenceScorerStrategy
from strategies.multi_tier_quality import MultiTierQualityStrategy
from strategies.funding_rate import FundingRateStrategy
from strategies.oi_delta import OIDeltaStrategy
from strategies.bollinger_squeeze import BollingerSqueezeStrategy
from strategies.vmc_cipher import VMCCipherStrategy
from strategies.lead_lag import LeadLagStrategy
from strategies.liquidation_cascade import LiquidationCascadeStrategy
from strategies.probability_engine import ProbabilityEngineStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.ensemble import EnsembleStrategy
from execution.position_manager import PositionManager
from execution.leverage import LeverageManager
from execution.risk import RiskManager, CircuitBreaker
from execution.trade_logger import TradeLogger
from ml.learner import SignalLearner, TradeOutcome, MarketSnapshot
from alerts.router import AlertRouter
from alerts.telegram_bot import TelegramCommandBot
from execution.trade_profile import classify_trade, apply_profile_to_signal
from execution.dynamic_tp import optimize_tp_sl as dynamic_tp_optimize
from execution.precision import validate_fill_price, get_min_qty, get_max_leverage, get_all_symbol_specs, round_qty

# LLM meta-brain
from llm.autonomy import LLMMode, get_llm_mode, should_call_llm, llm_has_veto, describe_mode
from llm.decision_engine import get_trading_decision, DecisionResult
from llm.decision_types import (
    StrategySignal as LLMStrategySignal,
    MarketSnapshot as LLMMarketSnapshot,
    GlobalContext as LLMGlobalContext,
)
from llm.risk_gating import RiskContext as LLMRiskContext
from llm.triggers import LLMTrigger, TriggerAccumulator, TRIGGER_LABELS
from execution.candidate import TradeCandidate, CandidateLogger
from execution.reconciliation import (
    reconcile_positions,
    save_circuit_breaker_state,
    restore_circuit_breaker_state,
    periodic_reconciliation_check,
)
from execution.auto_recovery import (
    startup_recovery,
    save_position_state,
    save_heartbeat,
    should_skip_stale_signals,
)
from execution.time_sizing import get_time_multiplier, get_full_time_multiplier
from execution.ops_guard import OpsGuard
from execution.rotation_manager import RotationManager, RotationConfig
from data.fetchers.telemetry import Telemetry

# Feedback loop system
from feedback.loop import FeedbackLoop
from feedback.signal_quality import QualityFeatures, SignalQualityScorer
from feedback.parameter_tuner import ParameterTuner
from feedback.continuous_backtest import ContinuousBacktester

# Perpetual learning systems (Master Engine + 5 subsystems)
from learning import get_master_engine

# Signal ingestion pipeline
from signals.telegram_ingest import TelegramSignalMonitor, IngestedSignal
from signals.llm_analyzer import analyze_signal, format_analysis_for_telegram

# Growth intelligence — self-evolving meta-brain
from llm.growth.orchestrator import get_growth_orchestrator

# Mechanical bot instrumentation (TIER 4: observation-only hooks)
try:
    from llm.mechanical_bot_instrumentation import get_mechanical_bot_instrumentation
    from llm.mechanical_bot_memory import get_mechanical_bot_memory
    _MECHANICAL_BOT_INSTRUMENTATION_AVAILABLE = True
except ImportError:
    _MECHANICAL_BOT_INSTRUMENTATION_AVAILABLE = False

# Bot perception system (TIER 5: unified API + instrumentation aggregation)
try:
    from llm.bot_perception_api import get_bot_perception_api_client
    from llm.bot_perception_aggregator import get_bot_perception_aggregator
    _BOT_PERCEPTION_SYSTEM_AVAILABLE = True
except ImportError:
    _BOT_PERCEPTION_SYSTEM_AVAILABLE = False

# LLM exit engine — dynamic SL/TP management for open positions
try:
    from llm.exit_engine import ExitEngine
    from llm.exit_types import ExitDecision
    _EXIT_ENGINE_AVAILABLE = True
except ImportError:
    _EXIT_ENGINE_AVAILABLE = False

# Feedback loop closers — self-performance, cost, operator channel
from llm.cost_tracker import get_cost_tracker
from llm.operator_channel import get_operator_channel
from llm.self_performance import get_performance_stats

# Wave 1: Signal Flagger — cheap heuristic flags for LLM attention routing
try:
    from llm.signal_flagger import get_signal_flagger, FlagType, FlaggedSignal
    _SIGNAL_FLAGGER_AVAILABLE = True
except ImportError:
    _SIGNAL_FLAGGER_AVAILABLE = False

# Wave 1: Signal Override — bypass soft blockers for powerful signals
try:
    from llm.signal_override import (
        should_override_blocker, BlockerType, get_override_engine,
    )
    _SIGNAL_OVERRIDE_AVAILABLE = True
except ImportError:
    _SIGNAL_OVERRIDE_AVAILABLE = False

# Wave 1: Self-Teaching — periodic learning cycles + knowledge injection
try:
    from llm.self_teaching import get_teaching_engine
    _SELF_TEACHING_AVAILABLE = True
except ImportError:
    _SELF_TEACHING_AVAILABLE = False

# Wave 2: Liquidity Guard — pre-trade market health validation
try:
    from execution.liquidity_guard import validate_liquidity
    _LIQUIDITY_GUARD_AVAILABLE = True
except ImportError:
    _LIQUIDITY_GUARD_AVAILABLE = False

# Phase D+E+F: new modules
from execution.funding_timer import should_close_before_funding, minutes_until_next_funding
from strategies.regime_detector import RegimeTransitionDetector
from monitoring.health import HealthMonitor
from execution.graceful_degradation import DegradationManager
from execution.pending_orders import PendingOrderManager

# Watchdog: background health monitoring with stall detection and auto-alerts
from monitoring.watchdog import get_watchdog

# Enhanced Telegram alerts: actionable signal formatting
from alerts.enhanced_telegram import (
    format_signal_telegram, format_trade_event_telegram,
    format_heartbeat_telegram, format_daily_report_telegram,
)

# Telegram alert bridge: critical event notifications via TradeEventLogger callbacks
from alerts.telegram_alert_bridge import TelegramAlertBridge

# Global Brain + Portfolio Brain: cross-market reasoning for LLM
from llm.global_brain import build_global_context, apply_global_bias
from llm.portfolio_brain import build_portfolio_snapshot

# Self-Tuning Risk Engine: adaptive risk profiles
from risk.self_tuning import (
    get_telemetry as get_risk_telemetry,
    evaluate_and_adjust as risk_evaluate_and_adjust,
    get_dynamic_leverage_cap,
    get_profile_params as get_risk_profile_params,
)

# RL system: transition logging + policy application
from rl.buffer import append_transition as rl_append_transition
from rl.apply_policy import get_combined_rl_multiplier, is_rl_enabled

# Deep memory + cross-symbol pattern tracking
try:
    from llm.deep_memory import get_deep_memory, TradeDNA
    _DEEP_MEMORY_AVAILABLE = True
except ImportError:
    _DEEP_MEMORY_AVAILABLE = False

try:
    from strategies.cross_symbol_patterns import CrossSymbolTracker
    _CROSS_SYMBOL_AVAILABLE = True
except ImportError:
    _CROSS_SYMBOL_AVAILABLE = False

# Survival Pressure: performance accountability injected into LLM context
try:
    from llm.survival_pressure import (
        record_trade_outcome as survival_record_outcome,
        get_survival_context_for_llm,
        get_survival_report,
    )
    _SURVIVAL_PRESSURE_AVAILABLE = True
except ImportError:
    _SURVIVAL_PRESSURE_AVAILABLE = False

# Learning Mode: progressive LLM autonomy (ABSORB -> APPRENTICE -> ACTIVE)
try:
    from llm.learning_mode import (
        is_learning_mode_active,
        get_current_phase,
        record_signal_observed as learning_record_signal,
        record_trade_observed as learning_record_trade,
        record_counterfactual,
        apply_learning_constraints,
        get_learning_report,
        LearningPhase,
    )
    _LEARNING_MODE_AVAILABLE = True
except ImportError:
    _LEARNING_MODE_AVAILABLE = False

# Autonomy Progression: gate-based mode advancement (VETO_ONLY -> SIZING -> DIRECTION -> FULL)
try:
    from llm.progression import evaluate_progression, format_progression_status
    _PROGRESSION_AVAILABLE = True
except ImportError:
    _PROGRESSION_AVAILABLE = False

# Uplift Analytics: baseline vs LLM-filtered performance comparison
try:
    from llm.uplift_analytics import compute_uplift, format_uplift_report
    _UPLIFT_AVAILABLE = True
except ImportError:
    _UPLIFT_AVAILABLE = False

# Adaptive Risk: dynamic risk-per-trade based on streak and regime
try:
    from execution.adaptive_risk import get_adaptive_risk
    _ADAPTIVE_RISK_AVAILABLE = True
except ImportError:
    _ADAPTIVE_RISK_AVAILABLE = False

# Strategy Pruning: auto-reduce weights for underperforming strategies
try:
    from execution.strategy_pruning import evaluate_and_adjust as pruning_evaluate, get_strategy_weight
    _STRATEGY_PRUNING_AVAILABLE = True
except ImportError:
    _STRATEGY_PRUNING_AVAILABLE = False

# Human Copy-Trade Classifier: gate for copy-tradable signal publication
try:
    from classification.human_copy_classifier import classify_human_copy_tradable, CopyTradeResult
    _COPY_CLASSIFIER_AVAILABLE = True
except ImportError:
    _COPY_CLASSIFIER_AVAILABLE = False

# LLM Self-Performance: rolling accuracy stats for self-calibration
try:
    from llm.self_performance import get_compact_stats as get_llm_self_stats
    _SELF_PERF_AVAILABLE = True
except ImportError:
    _SELF_PERF_AVAILABLE = False

# Wave 3: Portfolio Risk Engine — correlation matrix, vol forecasting, risk budgeting
try:
    from analytics.portfolio_risk import get_portfolio_risk_engine
    _PORTFOLIO_RISK_AVAILABLE = True
except ImportError:
    _PORTFOLIO_RISK_AVAILABLE = False

# Wave 4: Performance Attribution — which decisions actually made money
try:
    from analytics.attribution import compute_attribution, format_attribution_report
    _ATTRIBUTION_AVAILABLE = True
except ImportError:
    _ATTRIBUTION_AVAILABLE = False

# Wave 4: A/B Testing — live strategy variant testing
try:
    from analytics.ab_testing import get_ab_manager
    _AB_TESTING_AVAILABLE = True
except ImportError:
    _AB_TESTING_AVAILABLE = False

# Wave 4: Counterfactual Learning — what-if analysis for vetoes and sizing
try:
    from analytics.counterfactual import get_counterfactual_engine
    _COUNTERFACTUAL_AVAILABLE = True
except ImportError:
    _COUNTERFACTUAL_AVAILABLE = False

# Wave 4: Meta-Learning — pattern analysis and strategy idea generation
try:
    from analytics.meta_learning import get_meta_engine
    _META_LEARNING_AVAILABLE = True
except ImportError:
    _META_LEARNING_AVAILABLE = False

# Web Dashboard: visual monitoring
try:
    from dashboard.server import get_dashboard_server
    _DASHBOARD_AVAILABLE = True
except ImportError:
    _DASHBOARD_AVAILABLE = False


def get_tp1_close_pct(confidence: float) -> float:
    """Legacy confidence-based TP1 close percentage.
    Now superseded by TradeProfile for live trading, but kept for
    backward compat (backtest engine, tests).
    Lower confidence = lock in more profit. Higher = let more ride."""
    if confidence < 70:
        return 1.00
    elif confidence < 85:
        return 0.70
    elif confidence < 92:
        return 0.50
    else:
        return 0.30


def _fmt_price(price: float) -> str:
    """Format price with appropriate precision (handles micro-prices like PEPE)."""
    if price == 0:
        return "0"
    abs_p = abs(price)
    if abs_p >= 1.0:
        return f"{price:,.2f}"
    elif abs_p >= 0.001:
        return f"{price:.4f}"
    elif abs_p >= 0.000001:
        return f"{price:.8f}"
    else:
        return f"{price:.12f}"


# Setup structured logging with rotating file handler
from core.structured_logging import setup_logging, log_trade_event, log_metric

# Extracted mixin modules (refactored from this file)
from core.analytics import AnalyticsMixin
from core.llm_integration import LLMIntegrationMixin
from core.position_wiring import PositionWiringMixin

_is_production = os.getenv("ENVIRONMENT", "paper").lower() == "production"
setup_logging(
    json_mode=_is_production,
    level=os.getenv("LOG_LEVEL", "INFO"),
    log_dir="logs",
)
logger = logging.getLogger("bot.main")


class MultiStrategyBot(AnalyticsMixin, LLMIntegrationMixin, PositionWiringMixin):
    """
    The main bot that orchestrates everything.

    Loop:
    1. Fetch data for all symbols
    2. Run ensemble evaluation
    3. ML-adjust confidence
    4. Determine leverage
    5. Open positions if signal passes filters
    6. Update existing positions (TP/SL/trailing)
    7. Record outcomes for ML learning
    8. Send alerts
    9. Sleep and repeat
    """

    def __init__(self, config: TradingConfig):
        self.config = config
        self.stop_event = threading.Event()

        # Apply paper/live profile overrides (caps leverage, risk, etc.)
        apply_profile(config)

        # Data
        self.fetcher = DataFetcher(
            max_retries=config.fetcher_max_retries,
            retry_delay=5.0,
            cache_ttl=max(90, config.scan_interval_s * 3),  # survive full tick + LLM pipeline
            cb_threshold=config.fetcher_circuit_breaker_threshold,
            cb_reset_s=config.fetcher_circuit_breaker_reset_s,
        )

        # Strategy accuracy weights
        self.weight_mgr = StrategyWeightManager(
            path="ml_data/strategy_weights.json",
            decay_alpha=0.9,
        )

        # Regime-specific feedback (tracks per-regime performance)
        self.regime_feedback = RegimeFeedbackManager(data_dir="data/feedback")

        # Adaptive confidence floor (dynamic thresholds from realized performance)
        self.confidence_floor = AdaptiveConfidenceFloor(data_dir="data/feedback")

        # Hold-time rules (minimum hold times per regime based on live performance)
        self.hold_time_rules = HoldTimeRuleManager(data_dir="data/feedback")

        # Signal quality scorer (meta-confidence based on signal context)
        self.signal_quality = SignalQualityScorer(data_dir="data/feedback")

        # Parameter tuner (autonomous parameter adaptation based on performance)
        self.parameter_tuner = ParameterTuner(data_dir="data/feedback")

        # Continuous backtest (real-time validation of signal quality against historical baselines)
        self.continuous_backtest = ContinuousBacktester(data_dir="data/feedback")

        # Strategies — each toggleable via STRATEGY_*_ENABLED env var
        sym_configs = DEFAULT_SYMBOLS
        self.strategies = []

        if os.getenv("STRATEGY_REGIME_TREND_ENABLED", "true").lower() == "true":
            self.strategies.append(RegimeTrendStrategy(sym_configs, config.htf_hours))
        if os.getenv("STRATEGY_CONFIDENCE_SCORER_ENABLED", "true").lower() == "true":
            self.strategies.append(ConfidenceScorerStrategy(sym_configs, data_dir="ml_data", backtest_mode=True))
        if os.getenv("STRATEGY_MULTI_TIER_QUALITY_ENABLED", "true").lower() == "true":
            self.strategies.append(MultiTierQualityStrategy(sym_configs))
        if os.getenv("STRATEGY_MONTE_CARLO_ENABLED", "false").lower() == "true":
            self.strategies.append(MonteCarloZonesStrategy(
                sym_configs,
                mc_sims=config.mc_num_sims,
                mc_hours=config.mc_forward_hours,
            ))

        # New quant strategies (Phase 6 alpha generation)
        if os.getenv("STRATEGY_FUNDING_RATE_ENABLED", "true").lower() == "true":
            self.strategies.append(FundingRateStrategy(sym_configs))
        if os.getenv("STRATEGY_OI_DELTA_ENABLED", "true").lower() == "true":
            self.strategies.append(OIDeltaStrategy(sym_configs))
        if os.getenv("STRATEGY_BOLLINGER_SQUEEZE_ENABLED", "true").lower() == "true":
            self.strategies.append(BollingerSqueezeStrategy(sym_configs))
        if os.getenv("STRATEGY_VMC_CIPHER_ENABLED", "false").lower() == "true":
            self.strategies.append(VMCCipherStrategy(sym_configs))
        if os.getenv("STRATEGY_LEAD_LAG_ENABLED", "false").lower() == "true":
            self.strategies.append(LeadLagStrategy(sym_configs))
        if os.getenv("STRATEGY_LIQUIDATION_CASCADE_ENABLED", "true").lower() == "true":
            self.strategies.append(LiquidationCascadeStrategy(sym_configs))
        if os.getenv("STRATEGY_PROBABILITY_ENGINE_ENABLED", "true").lower() == "true":
            self.strategies.append(ProbabilityEngineStrategy(
                sym_configs,
                num_sims=config.mc_num_sims,
                forward_bars=config.mc_forward_hours,
            ))
        if os.getenv("STRATEGY_CVD_SIGNAL_ENABLED", "false").lower() == "true":
            try:
                from strategies.cvd_signal import CVDSignalStrategy
                self.strategies.append(CVDSignalStrategy(sym_configs))
            except Exception as e:
                logger.warning(f"[INIT] CVD signal strategy unavailable: {e}")
        if os.getenv("STRATEGY_MEAN_REVERSION_ENABLED", "true").lower() == "true":
            self.strategies.append(MeanReversionStrategy(sym_configs))

        enabled_names = [s.name for s in self.strategies]
        logger.info(f"[INIT] Active strategies: {enabled_names}")
        # Chop detector: multi-factor choppy market filter
        chop = None
        if config.enable_chop_detector:
            try:
                from strategies.chop_detector import ChopDetector
                from trading_config import DEFAULT_SYMBOL_OVERRIDES
                chop = ChopDetector(threshold=config.chop_threshold)
                # Set per-symbol volatility profiles for adaptive thresholds
                for sym, overrides in DEFAULT_SYMBOL_OVERRIDES.items():
                    if hasattr(overrides, "volatility_profile"):
                        chop.set_symbol_profile(sym, overrides.volatility_profile)
                logger.info(f"[INIT] Chop detector enabled (threshold={config.chop_threshold})")
            except Exception as e:
                logger.warning(f"[INIT] Chop detector init failed: {e}")

        self.ensemble = EnsembleStrategy(
            strategies=self.strategies,
            mode=config.ensemble_mode,
            min_votes=config.min_votes_required,
            weight_manager=self.weight_mgr,
            veto_ratio=config.veto_ratio,
            chop_detector=chop,
            confidence_floor=config.ensemble_confidence_floor,
            ranging_confidence_floor=config.ranging_confidence_floor,
        )
        # Wire signal quality scoring to ensemble (applies learned context confidence multipliers)
        self.ensemble._signal_quality_scorer = self.signal_quality

        # Wire manual sniper callback: receives solo signals that the ensemble
        # rejects for insufficient consensus. The sniper has its own proven-setup
        # gates and can profitably trade signals the bot sits out on.
        self.ensemble._manual_sniper_callback = self._on_solo_signal_for_sniper

        # Apply quant system config disables (kill toxic strategies)
        self.ensemble.apply_config_disables(config)

        # Wire volatility profiles for per-symbol confidence floor capping
        from trading_config import DEFAULT_SYMBOL_OVERRIDES
        vol_profiles = {
            sym: ov.volatility_profile
            for sym, ov in DEFAULT_SYMBOL_OVERRIDES.items()
            if hasattr(ov, 'volatility_profile') and ov.volatility_profile
        }
        self.ensemble.set_symbol_volatility_profiles(vol_profiles)

        # ── LLM Sniper Engine (optional, additive — never touches existing trades) ──
        # Intercepts single-strategy ensemble rejections and queues LLM proposals.
        # Activated only when LLM_SNIPER_ENABLED=true. Off by default.
        try:
            import os as _os
            if _os.getenv("LLM_SNIPER_ENABLED", "").lower() in ("1", "true", "yes"):
                from llm.sniper import LLMSniperEngine
                _sniper = LLMSniperEngine(max_leverage=config.max_leverage)
                self.ensemble._sniper_callback = _sniper.evaluate_candidate
                logger.info("[INIT] LLM Sniper Engine enabled — queuing rejected 1-vote signals for LLM review")
            else:
                logger.debug("[INIT] LLM Sniper disabled (LLM_SNIPER_ENABLED not set)")
        except Exception as _se:
            logger.warning(f"[INIT] LLM Sniper Engine init failed (non-fatal): {_se}")

        # ── Manual Sniper Signal System (reads signals only, never touches trading) ──
        # Also runs standalone via: python -m manual.runner
        self._manual_sniper = None
        self._manual_alerter = None
        self._sniper_simulator = None
        try:
            from manual.sniper_filter import ManualSniperFilter
            from manual.alerts import ManualSniperAlerter
            from manual.config import ManualSniperConfig
            _ms_config = ManualSniperConfig()
            if _ms_config.enabled:
                self._manual_sniper = ManualSniperFilter(_ms_config)
                self._manual_alerter = ManualSniperAlerter(_ms_config)
                try:
                    from manual.simulator import SniperSimulator
                    self._sniper_simulator = SniperSimulator(
                        starting_equity=_ms_config.equity
                    )
                except Exception:
                    pass
                # Signal value tracker: quantifies every signal's real-world outcome
                self._signal_tracker = None
                try:
                    from manual.signal_tracker import SignalValueTracker
                    self._signal_tracker = SignalValueTracker()
                    logger.info("[INIT] Signal Value Tracker enabled")
                except Exception as _svt_err:
                    logger.debug(f"[INIT] Signal tracker not available: {_svt_err}")
                # Auto-execute: optionally route sniper signals to the order executor
                self._sniper_auto_execute = os.getenv(
                    "SNIPER_AUTO_EXECUTE", "false"
                ).lower() == "true"
                logger.info(
                    f"[INIT] Manual Sniper System enabled — "
                    f"target=${_ms_config.daily_target}/day "
                    f"max_lev={_ms_config.max_leverage}x "
                    f"auto_execute={self._sniper_auto_execute}"
                )
        except Exception as _ms_err:
            logger.debug(f"[INIT] Manual Sniper System not available: {_ms_err}")
        if not hasattr(self, "_sniper_auto_execute"):
            self._sniper_auto_execute = False
        if not hasattr(self, "_signal_tracker"):
            self._signal_tracker = None

        # ── Anticipatory Entry Engine (precision limit-order style entries) ──
        self._anticipation_engine = None
        _anticipatory_enabled = os.getenv("ANTICIPATORY_ENTRIES_ENABLED", "true").lower() == "true"
        if _anticipatory_enabled and self._manual_sniper is not None:
            try:
                from manual.anticipatory_entries import get_anticipation_engine
                self._anticipation_engine = get_anticipation_engine()
                logger.info("[INIT] Anticipatory Entry Engine enabled (precision entries)")
            except Exception as _ae_err:
                logger.debug(f"[INIT] Anticipatory Engine not available: {_ae_err}")

        # ── Quant Brain Pre-Filter (zero-cost, rule-based signal gating) ──
        self._quant_brain = None
        self._quant_brain_enabled = os.getenv("QUANT_BRAIN_ENABLED", "true").lower() == "true"
        if self._quant_brain_enabled:
            try:
                from llm.quant_brain import get_quant_brain
                self._quant_brain = get_quant_brain()
                logger.info("[INIT] Quant Brain pre-filter enabled (zero API cost)")
            except Exception as _qb_err:
                logger.warning(f"[INIT] Quant Brain init failed (non-fatal): {_qb_err}")
                self._quant_brain = None

        # Reflection Engine: post-trade analysis with coded observations
        self._reflection_engine = None
        try:
            from llm.reflection_engine import ReflectionEngine
            self._reflection_engine = ReflectionEngine()
            logger.info("[INIT] Reflection Engine enabled (post-trade analysis)")
        except Exception as _re_err:
            logger.debug(f"[INIT] Reflection engine not available: {_re_err}")

        # Background Thinker: periodic rule-based analysis between signals (no LLM calls)
        self._background_thinker = None
        try:
            from llm.agents.background_thinker import BackgroundThinker
            self._background_thinker = BackgroundThinker(interval_seconds=300)
            logger.info("[INIT] Background thinker enabled (5min cycles)")
        except ImportError:
            logger.debug("[INIT] Background thinker not available")

        # Pre-Trade Simulator: scenario-based imagination before each entry (no LLM calls)
        self._pre_trade_sim = None
        self._last_simulation: Dict[str, Any] = {}
        try:
            from llm.agents.pre_trade_simulator import PreTradeSimulator
            self._pre_trade_sim = PreTradeSimulator()
            logger.info("[INIT] Pre-trade simulator enabled")
        except ImportError:
            logger.debug("[INIT] Pre-trade simulator not available")

        # Agent Performance Tracker: per-agent decision quality measurement
        self._agent_perf = None
        try:
            from llm.agents.agent_performance import get_tracker
            self._agent_perf = get_tracker()
            logger.info("[INIT] Agent performance tracker enabled")
        except ImportError:
            logger.debug("[INIT] Agent performance tracker not available")

        # Agent Cost Optimizer: gates LLM calls based on budget, tracks ROI per pipeline
        self._cost_optimizer = None
        try:
            from llm.agents.cost_optimizer import get_cost_optimizer
            _daily_budget = float(os.getenv("LLM_DAILY_BUDGET_USD", "0.50"))
            self._cost_optimizer = get_cost_optimizer(daily_budget=_daily_budget)
            logger.info(f"[INIT] Cost optimizer enabled (budget=${_daily_budget:.2f}/day)")
        except Exception as _co_err:
            logger.debug(f"[INIT] Cost optimizer not available: {_co_err}")

        # Active Learning Engine: meta-learning that improves the brain over time
        self._active_learning = None
        try:
            from llm.agents.active_learning import ActiveLearningEngine
            self._active_learning = ActiveLearningEngine()
            logger.info("[INIT] Active learning engine enabled (30min cycles)")
        except Exception as _al_err:
            logger.debug(f"[INIT] Active learning engine not available: {_al_err}")

        # Execution
        self.risk_mgr = RiskManager(
            starting_equity=config.starting_equity,
            risk_per_trade=config.risk_per_trade,
            max_open_positions=config.max_open_positions,
            circuit_breaker=CircuitBreaker(
                daily_loss_limit_pct=config.circuit_breaker_daily_loss_pct,
                max_consecutive_losses=config.max_consecutive_losses,
                cooldown_minutes=config.circuit_breaker_cooldown_min,
            ),
        )

        self.pos_mgr = PositionManager(
            taker_fee_bps=config.taker_fee_bps,
            enable_trailing=config.enable_trailing_stop,
            trailing_atr_mult=config.trailing_stop_atr_mult,
            time_stop_hours=config.time_stop_hours,
            hold_time_rules=self.hold_time_rules,
        )
        # Per-symbol execution lock: prevents duplicate entries when two signals
        # for the same symbol race through the pipeline simultaneously.
        self._executing_symbols: set = set()
        self._executing_lock = threading.Lock()
        self.leverage_mgr = LeverageManager(
            enable_leverage=config.enable_leverage,
            max_leverage=config.max_leverage,
        )

        # Order executor: bridges PositionManager with exchange
        from execution.order_executor import create_executor
        _exec_mode = "live" if not config.is_paper else "paper"
        _max_slip = float(os.getenv("MAX_ENTRY_SLIPPAGE_PCT", "1.5"))
        try:
            self.order_executor = create_executor(
                fetcher=self.fetcher,
                mode=_exec_mode,
                max_slippage_pct=_max_slip,
            )
        except ValueError:
            # Live mode without exchange credentials — fall back to paper
            logger.warning("[INIT] No exchange credentials for live mode, falling back to paper executor")
            self.order_executor = create_executor(fetcher=self.fetcher, mode="paper")

        # Entry optimizer: limit-order-first for better fills (saves ~3 bps per entry)
        try:
            from execution.entry_optimizer import EntryOptimizer
            _limit_timeout = float(os.getenv("ENTRY_LIMIT_TIMEOUT_S", "10"))
            self.entry_optimizer = EntryOptimizer(
                use_limit_orders=os.getenv("ENTRY_USE_LIMIT_ORDERS", "true").lower() in ("1", "true", "yes"),
                use_burst_detection=False,  # Burst detection adds latency, disable for now
                limit_timeout_s=_limit_timeout,
            )
            logger.info(f"[INIT] Entry optimizer enabled (limit timeout={_limit_timeout}s)")
        except Exception as _eo_err:
            logger.debug(f"[INIT] Entry optimizer not available: {_eo_err}")
            self.entry_optimizer = None

        # ML
        self.ml = SignalLearner(
            data_dir="ml_data",
            min_samples=config.ml_min_samples,
            retrain_interval=config.ml_retrain_interval,
            adjustment_weight=config.ml_adjustment_weight,
        ) if config.enable_ml else None

        # Alerts
        self.alerts = AlertRouter(
            discord_webhook=config.discord_webhook,
            telegram_token=config.telegram_token,
            telegram_chat_id=config.telegram_chat_id,
        )

        # Telegram alert bridge: hooks into TradeEventLogger for critical alerts
        self.telegram_bridge = TelegramAlertBridge(
            telegram_token=config.telegram_token,
            telegram_chat_id=config.telegram_chat_id,
        )
        try:
            from core.structured_logging import get_trade_event_logger
            tel = get_trade_event_logger()
            tel.add_callback(self.telegram_bridge.on_trade_event)
        except Exception as e:
            logger.debug(f"Telegram alert bridge callback registration skipped: {e}")

        # Trade logging (paper trading validation)
        self.trade_logger = TradeLogger(log_dir="paper_trades") if not config.auto_trade else None

        self._tick = 0
        self._needed_tfs = self.ensemble.get_all_required_timeframes()

        # Per-symbol cooldown: prevent rapid re-entry after a position closes
        self._symbol_cooldown: Dict[str, float] = {}  # symbol -> timestamp of last close
        self._cooldown_seconds = config.loss_cooldown_s
        self._win_cooldown_seconds = config.win_cooldown_s

        # Correlation guard: prevent correlated blowups
        self._max_same_direction = int(os.getenv("MAX_SAME_DIRECTION", "3"))
        self._max_same_tier = int(os.getenv("MAX_SAME_TIER", "2"))

        # Track last close result per symbol for anti-round-tripping
        self._last_close_win: Dict[str, bool] = {}  # symbol -> was_win
        self._last_close_side: Dict[str, str] = {}  # symbol -> "LONG"/"SHORT"

        # Per-symbol daily loss tracking: stop trading a symbol after -$30/day
        self._symbol_daily_pnl: Dict[str, float] = {}  # symbol -> cumulative PnL today
        self._symbol_daily_pnl_date: str = ""  # YYYY-MM-DD of last reset
        self._symbol_daily_loss_limit = float(os.getenv("SYMBOL_DAILY_LOSS_LIMIT", "-30"))

        # Signal dedup: prevent spam from repeated same-side evaluations
        self._last_signal: Dict[str, tuple] = {}  # symbol -> (side, timestamp)
        self._signal_dedup_seconds = config.signal_dedup_window_s

        # Last known prices for fill-price validation
        self._last_prices: Dict[str, float] = {}  # symbol -> price
        # Last known funding rates per symbol (updated from fetcher)
        self._last_funding_rates: Dict[str, float] = {}  # symbol -> funding rate
        self._last_open_interest: Dict[str, float] = {}  # symbol -> OI (for oi_delta strategy)

        # LLM meta-brain
        self.llm_mode = get_llm_mode()
        self._llm_triggers = TriggerAccumulator()
        self._slippage_reject_cooldown: Dict[str, float] = {}  # symbol -> timestamp
        self.pending_orders = PendingOrderManager(max_pending=5)

        # Dual-world candidate logging (baseline vs LLM)
        self._candidate_logger = CandidateLogger()
        self._active_candidates: Dict[str, TradeCandidate] = {}  # symbol -> last candidate that opened a trade

        # Operations guard: kill switch, rate limiting, exposure limits
        self.ops_guard = OpsGuard()

        # Trade rotation manager: rotate stale/losing positions into better signals
        if config.enable_rotation:
            self.rotation_mgr = RotationManager(RotationConfig(
                min_hold_before_rotation_s=config.rotation_min_hold_s,
                global_rotation_cooldown_s=config.rotation_global_cooldown_s,
                max_rotations_per_hour=config.rotation_max_per_hour,
                max_rotations_per_day=config.rotation_max_per_day,
                estimated_round_trip_fee_pct=config.taker_fee_bps / 100.0,  # one-way fee in % (rotation mgr doubles for close+open)
            ))
        else:
            self.rotation_mgr = None

        # Feedback loop: self-improving confidence, backtesting, quality scoring
        self.feedback = FeedbackLoop(data_dir="data/feedback")
        # Wire SignalQualityScorer into ensemble so session/hour/entry_type WR
        # adjustments (US=57% WR, Asia=14% WR) actually affect confidence scoring.
        self.ensemble.set_quality_scorer(self.feedback.quality)
        logger.info("[INIT] SignalQualityScorer wired into ensemble — session/hour WR now adjusts confidence")

        # Quant system: IC tracker, Kelly engine, trade ledger, shadow ledger, daily report
        try:
            from feedback.ic_tracker import ICTracker
            from feedback.kelly_engine import KellyEngine
            from feedback.trade_ledger import TradeLedger
            from feedback.shadow_ledger import ShadowLedger
            from feedback.daily_report import DailyReporter
            from execution.correlation_gate import CorrelationGate
            self.ic_tracker = ICTracker(data_dir="data")
            self.kelly_engine = KellyEngine(data_path="data/kelly_weights.json")
            self.trade_ledger = TradeLedger(data_dir="data")
            self.shadow_ledger = ShadowLedger(data_dir="data")
            self.correlation_gate = CorrelationGate()
            from execution.sector_exposure import SectorExposure
            self._sector_exposure_cls = SectorExposure
            from execution.execution_analytics import ExecutionAnalytics
            self.execution_analytics = ExecutionAnalytics(data_dir="data")
            self.daily_reporter = DailyReporter(
                trade_ledger=self.trade_ledger,
                ic_tracker=self.ic_tracker,
                kelly_engine=self.kelly_engine,
            )
            self.ensemble.set_shadow_ledger(self.shadow_ledger)
            # Wire missed trade tracker into ensemble + main loop
            try:
                from feedback.missed_trade_tracker import MissedTradeTracker
                self._missed_trade_tracker = MissedTradeTracker(data_dir="data")
                self.ensemble.set_missed_trade_tracker(self._missed_trade_tracker)
                logger.info("[INIT] MissedTradeTracker wired into ensemble + pipeline")
            except Exception as mt_e:
                logger.debug(f"[INIT] MissedTradeTracker unavailable: {mt_e}")
                self._missed_trade_tracker = None
            # Wire rejection outcome tracker for adaptive EV calibration
            try:
                from feedback.rejection_tracker import RejectionOutcomeTracker
                self._rejection_tracker = RejectionOutcomeTracker(data_dir="data")
                self.ensemble._rejection_outcome_tracker = self._rejection_tracker
                logger.info("[INIT] RejectionOutcomeTracker wired into ensemble EV gate")
            except Exception as rt_e:
                logger.debug(f"[INIT] RejectionOutcomeTracker unavailable: {rt_e}")
                self._rejection_tracker = None
            # Wire EV calibrator for adaptive threshold adjustment
            try:
                from feedback.ev_calibrator import EVCalibrator
                self._ev_calibrator = EVCalibrator(data_dir="data")
                self.ensemble._ev_calibrator = self._ev_calibrator
                # Connect rejection tracker -> EV calibrator feedback loop
                if self._rejection_tracker is not None:
                    self._rejection_tracker._outcome_callback = self._ev_calibrator.ingest_outcome
                logger.info("[INIT] EVCalibrator wired into ensemble EV gate")
            except Exception as ev_e:
                logger.debug(f"[INIT] EVCalibrator unavailable: {ev_e}")
                self._ev_calibrator = None
            # Wire LLM-reasoned override coordinator into ensemble
            # Allows OverrideAgent to bypass EV blocks when regime-specific edge is proven
            try:
                from llm.agents.coordinator import get_coordinator, is_multi_agent_enabled
                if is_multi_agent_enabled():
                    self.ensemble._override_coordinator = get_coordinator()
                    logger.info("[INIT] LLM Override Coordinator wired into ensemble EV gate")
            except Exception as oc_e:
                logger.debug(f"[INIT] Override coordinator unavailable: {oc_e}")
            # Wire cross-asset correlation boost into ensemble
            try:
                from feedback.correlation_boost import CrossAssetCorrelationBoost
                self._correlation_boost = CrossAssetCorrelationBoost(symbols=list(DEFAULT_SYMBOLS.keys()))
                self.ensemble._correlation_boost = self._correlation_boost
                logger.info("[INIT] CrossAssetCorrelationBoost wired into ensemble win_prob")
            except Exception as cb_e:
                logger.debug(f"[INIT] CrossAssetCorrelationBoost unavailable: {cb_e}")
                self._correlation_boost = None
            # Wire IC tracker into ensemble so inverted/decaying factors get downweighted in voting
            if self.ic_tracker:
                self.ensemble.ic_tracker = self.ic_tracker
                logger.info("[INIT] IC tracker wired into ensemble voting — inverted factors will be auto-downweighted")
            # Wire regime-aware strategy weighting into ensemble
            try:
                if config.regime_strategy_weighting_enabled:
                    from data.regime_strategy_weighter import RegimeStrategyWeighter
                    self._regime_strategy_weighter = RegimeStrategyWeighter(data_dir="data/regime_strategy_weights")
                    self.ensemble.set_regime_strategy_weighter(self._regime_strategy_weighter)
                    logger.info("[INIT] RegimeStrategyWeighter wired — strategy weights adjust per regime")
                else:
                    self._regime_strategy_weighter = None
            except Exception as rsw_e:
                logger.debug(f"[INIT] RegimeStrategyWeighter unavailable: {rsw_e}")
                self._regime_strategy_weighter = None
            logger.info("[INIT] Quant system loaded: IC tracker, Kelly engine, trade ledger, shadow ledger, correlation gate, daily report")
        except Exception as e:
            logger.warning(f"[INIT] Quant system partially unavailable: {e}")
            self.ic_tracker = None
            self.kelly_engine = None
            self.trade_ledger = None
            self.shadow_ledger = None
            self.correlation_gate = None
            self._sector_exposure_cls = None
            self.execution_analytics = None
            self._missed_trade_tracker = None

        # AutoOptimizer: autonomous review + parameter tuning
        # Lazy-initialized on first tick when EvolutionTracker is ready
        self._evolution_tracker = None
        self._auto_optimizer_initialized = False
        logger.info("[INIT] AutoOptimizer will initialize on first tick with EvolutionTracker")

        # Growth intelligence: self-evolving meta-brain
        self.growth = get_growth_orchestrator()

        # Operator channel: LLM → operator communication via Telegram
        self.operator_channel = get_operator_channel(alert_router=self.alerts)

        # Wave 1: Signal Flagger — cheap heuristic flags for every signal
        self.signal_flagger = get_signal_flagger() if _SIGNAL_FLAGGER_AVAILABLE else None

        # Wave 1: Signal Override — bypass soft blockers for powerful signals
        self.signal_override = get_override_engine() if _SIGNAL_OVERRIDE_AVAILABLE else None

        # Wave 1: Self-Teaching — periodic learning cycles
        self.teaching_engine = get_teaching_engine() if _SELF_TEACHING_AVAILABLE else None

        # Seed knowledge base with foundational axioms (idempotent — skips if already seeded)
        if self.teaching_engine:
            try:
                from llm.knowledge_seed import seed_knowledge_base
                seed_knowledge_base()
            except Exception as e:
                logger.debug(f"Knowledge seed error (non-fatal): {e}")

        # Veto tracking is handled by growth orchestrator (growth/veto_feedback.py)

        # Confidence calibration: bootstrap from backtest data if no curve exists yet
        try:
            from llm.confidence_calibrator import ConfidenceCalibrator
            self._confidence_calibrator = ConfidenceCalibrator(data_dir="data/llm")
            if not self._confidence_calibrator._curve:
                self._confidence_calibrator.bootstrap_from_backtest("data/backtest_trades_30d.csv")
                logger.info("[INIT] Confidence calibrator bootstrapped from backtest data")
            else:
                logger.info("[INIT] Confidence calibrator loaded existing calibration curve")
        except Exception as cc_err:
            logger.debug(f"[INIT] Confidence calibrator unavailable: {cc_err}")
            self._confidence_calibrator = None

        # Phase D+E+F: new subsystems
        self.regime_detector = RegimeTransitionDetector()
        self.health_monitor = HealthMonitor()
        self.degradation = DegradationManager()

        # LLM exit engine: dynamic SL/TP management for open positions
        if _EXIT_ENGINE_AVAILABLE:
            self.exit_engine = ExitEngine()
            logger.info("[INIT] LLM exit engine loaded")
        else:
            self.exit_engine = None
            logger.warning("[INIT] LLM exit engine unavailable — running without dynamic exits")
        self._exit_check_counter = 0

        # Cross-symbol pattern tracker: detects lead-lag relationships
        self.cross_symbol_tracker = CrossSymbolTracker() if _CROSS_SYMBOL_AVAILABLE else None

        # Cross-asset lead-lag monitor: BTC leads SOL/ETH
        self._cross_asset_monitor = None
        try:
            from execution.cross_asset_alert import CrossAssetLeadLagMonitor, LeadLagBoostEngine
            self._cross_asset_monitor = CrossAssetLeadLagMonitor()
            logger.info("[INIT] Cross-asset lead-lag monitor enabled (BTC→SOL/ETH)")
            # LeadLagBoostEngine: real-time confidence boost for follower signals
            if getattr(self.config, 'enable_lead_lag_boost', False):
                self._lead_lag_engine = LeadLagBoostEngine(
                    btc_move_threshold=getattr(self.config, 'lead_lag_btc_move_threshold', 0.3),
                    max_boost=getattr(self.config, 'lead_lag_max_boost', 12.0),
                    min_correlation=getattr(self.config, 'lead_lag_min_correlation', 0.60),
                    correlation_decay=getattr(self.config, 'lead_lag_correlation_decay', 0.98),
                )
                self.ensemble.set_lead_lag_engine(self._lead_lag_engine)
                logger.info("[INIT] Lead-lag boost engine enabled (BTC→SOL/ETH confidence boost)")
            else:
                self._lead_lag_engine = None
        except Exception as _ca_err:
            logger.debug(f"[INIT] Cross-asset monitor not available: {_ca_err}")
            self._lead_lag_engine = None

        # Track 1h price changes for cross-market divergence detection
        self._price_changes_1h: Dict[str, float] = {}
        self._price_highs_1h: Dict[str, float] = {}  # Rolling 1h high per symbol (for veto resolution)
        self._price_lows_1h: Dict[str, float] = {}   # Rolling 1h low per symbol (for veto resolution)

        # Self-tuning risk engine: adaptive profiles based on equity curve
        self.risk_telemetry = get_risk_telemetry()

        # Adaptive risk: dynamic risk-per-trade based on streak and regime
        self.adaptive_risk = get_adaptive_risk() if _ADAPTIVE_RISK_AVAILABLE else None

        # Cache global bias from Global Brain (updated each LLM context build)
        self._global_bias: str = "neutral"
        self._global_bias_adjustment: Dict[str, Any] = {}

        # Telegram command bot
        tg_user_id = int(os.getenv("TELEGRAM_ALLOWED_USER_ID") or "0")
        self.telegram_bot = TelegramCommandBot(
            token=config.telegram_token,
            allowed_user_id=tg_user_id,
            bot_instance=self,
        )

        # Telegram signal ingestion pipeline
        self.signal_monitor = TelegramSignalMonitor(
            on_signal=self._handle_ingested_signal,
        )

        # Watchdog: background health monitoring with stall detection
        self.watchdog = get_watchdog(
            alert_fn=self.alerts.send_market_update if self.alerts else None,
        )

        # Wave 3: Portfolio Risk Engine — correlation, vol forecasting, risk budgeting
        self.portfolio_risk = get_portfolio_risk_engine() if (
            _PORTFOLIO_RISK_AVAILABLE and config.enable_portfolio_risk
        ) else None

        # Wave 4: A/B Testing — live strategy variant testing
        self.ab_manager = get_ab_manager() if (
            _AB_TESTING_AVAILABLE and config.enable_ab_testing
        ) else None

        # Wave 4: Counterfactual Learning — what-if veto and sizing analysis
        self.counterfactual = get_counterfactual_engine() if (
            _COUNTERFACTUAL_AVAILABLE and config.enable_counterfactual
        ) else None

        # Wave 4: Meta-Learning — pattern analysis and strategy idea generation
        self.meta_engine = get_meta_engine() if (
            _META_LEARNING_AVAILABLE and config.enable_meta_learning
        ) else None

        # Web Dashboard
        self.dashboard = get_dashboard_server() if (
            _DASHBOARD_AVAILABLE and config.enable_dashboard
        ) else None

        # Paper trading hourly checkpoint (paper mode only)
        self.paper_validator = None
        self._paper_checkpoint_last = time.time()
        if config.is_paper:
            try:
                from monitoring.paper_validator import PaperValidator
                from core.signal_pipeline import enable_rejection_logging
                enable_rejection_logging(True)
                self.paper_validator = PaperValidator(
                    risk_mgr=self.risk_mgr,
                    pos_mgr=self.pos_mgr,
                    alert_router=self.alerts,
                    start_equity=getattr(config, "starting_equity", 0.0),
                )
                logger.info("[PAPER-VALIDATOR] Hourly checkpoint monitoring enabled")
            except Exception as e:
                logger.debug(f"[PAPER-VALIDATOR] Not available: {e}")

        # ── Dual Wallet System ──
        self._dual_wallet_enabled = config.dual_wallet_enabled
        self._wallet_a = None
        self._wallet_b = None
        self._wallet_dispatcher = None
        self._account_guardian = None

        if self._dual_wallet_enabled:
            try:
                from wallet.profile import wallet_a_default, wallet_b_default
                from wallet.context import WalletContext
                from wallet.dispatcher import WalletDispatcher
                from wallet.guardian import AccountGuardian
                from wallet.pnl_tracker import WalletPnLTracker

                profile_a = wallet_a_default()
                profile_b = wallet_b_default()

                # Each wallet gets its own execution components
                wallet_equity_a = config.starting_equity * config.wallet_a_equity_pct
                wallet_equity_b = config.starting_equity * config.wallet_b_equity_pct

                self._wallet_a = WalletContext(profile=profile_a)
                self._wallet_a.pos_mgr = PositionManager(
                    taker_fee_bps=config.taker_fee_bps,
                    enable_trailing=config.enable_trailing_stop,
                    trailing_atr_mult=config.trailing_stop_atr_mult,
                    time_stop_hours=config.time_stop_hours,
                    hold_time_rules=self.hold_time_rules,
                )
                self._wallet_a.risk_mgr = RiskManager(
                    starting_equity=wallet_equity_a,
                    risk_per_trade=profile_a.risk_per_trade,
                    max_open_positions=profile_a.max_open_positions,
                    circuit_breaker=CircuitBreaker(
                        daily_loss_limit_pct=profile_a.cb_daily_loss_pct,
                        max_consecutive_losses=profile_a.cb_max_consecutive_losses,
                        cooldown_minutes=config.circuit_breaker_cooldown_min,
                    ),
                )
                self._wallet_a.circuit_breaker = self._wallet_a.risk_mgr.circuit_breaker
                self._wallet_a.leverage_mgr = LeverageManager(
                    enable_leverage=config.enable_leverage,
                    max_leverage=profile_a.max_leverage,
                )
                self._wallet_a.pnl_tracker = WalletPnLTracker(
                    "A", wallet_equity_a, data_dir="data",
                )
                self._wallet_a.initialize()

                self._wallet_b = WalletContext(profile=profile_b)
                self._wallet_b.pos_mgr = PositionManager(
                    taker_fee_bps=config.taker_fee_bps,
                    enable_trailing=config.enable_trailing_stop,
                    trailing_atr_mult=config.trailing_stop_atr_mult,
                    time_stop_hours=config.time_stop_hours,
                    hold_time_rules=self.hold_time_rules,
                )
                self._wallet_b.risk_mgr = RiskManager(
                    starting_equity=wallet_equity_b,
                    risk_per_trade=profile_b.risk_per_trade,
                    max_open_positions=profile_b.max_open_positions,
                    circuit_breaker=CircuitBreaker(
                        daily_loss_limit_pct=profile_b.cb_daily_loss_pct,
                        max_consecutive_losses=profile_b.cb_max_consecutive_losses,
                        cooldown_minutes=config.circuit_breaker_cooldown_min,
                    ),
                )
                self._wallet_b.circuit_breaker = self._wallet_b.risk_mgr.circuit_breaker
                self._wallet_b.leverage_mgr = LeverageManager(
                    enable_leverage=config.enable_leverage,
                    max_leverage=profile_b.max_leverage,
                )
                self._wallet_b.pnl_tracker = WalletPnLTracker(
                    "B", wallet_equity_b, data_dir="data",
                )
                self._wallet_b.initialize()

                self._account_guardian = AccountGuardian()
                self._wallet_dispatcher = WalletDispatcher(
                    self._wallet_a, self._wallet_b, self._account_guardian,
                )

                logger.info(
                    f"[INIT] Dual Wallet System enabled: "
                    f"A ({profile_a.name}: {profile_a.max_leverage}x, "
                    f"${wallet_equity_a:.2f}) + "
                    f"B ({profile_b.name}: {profile_b.max_leverage}x, "
                    f"${wallet_equity_b:.2f})"
                )
            except Exception as dw_err:
                logger.warning(f"[INIT] Dual wallet init failed, falling back to single: {dw_err}")
                self._dual_wallet_enabled = False
                self._wallet_a = None
                self._wallet_b = None
                self._wallet_dispatcher = None
                self._account_guardian = None
