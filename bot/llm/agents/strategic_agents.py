"""
Strategic Agent Methods for Coordinator

These methods implement the 4 new Phase 3 strategic agents:
1. Portfolio Aggregator - holistic portfolio risk analysis (daily)
2. Regime Forecaster - predict regime shifts (daily)
3. Hypothesis Generator - novel pattern discovery (weekly)
4. Correlator - cross-asset correlation analysis (daily)

Each method follows the pattern of existing strategic agents (Scout, Overseer, Exit).
They are called independently, cache their outputs, and feed results into the decision pipeline.
"""

import json
import logging
import os
from typing import Any, Dict, Optional

from llm.agents.base import AgentConfig, AgentOutput, AgentRole
from llm.agents.shared_context import get_pipeline_scratchpad

logger = logging.getLogger("bot.llm.agents.strategic_agents")


def build_portfolio_aggregator(
    coordinator: Any,
    model_for_trigger: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Run Portfolio Aggregator agent to analyze holistic portfolio health.

    Returns:
        Parsed portfolio analysis dict or None on failure.
    """
    cfg = coordinator.configs.get(
        AgentRole.PORTFOLIO,
        AgentConfig(role=AgentRole.PORTFOLIO),
    )
    if not cfg.enabled:
        return None

    portfolio_input = _build_portfolio_input(coordinator)
    out = coordinator._call_agent(AgentRole.PORTFOLIO, portfolio_input, model_for_trigger)

    if not out.ok:
        logger.warning("[PORTFOLIO] Agent call failed")
        return None

    data = out.data
    scratchpad = get_pipeline_scratchpad()

    # Write portfolio health to scratchpad
    scratchpad.write("portfolio", "health", data.get("portfolio_health", "unknown"))
    scratchpad.write("portfolio", "beta", data.get("beta", 1.0))
    scratchpad.write("portfolio", "var_95pct", data.get("var_95pct", "unknown"))
    scratchpad.write("portfolio", "rebalance_action", data.get("rebalance_action", "none"))

    # Log summary
    logger.info(
        f"[PORTFOLIO] {data.get('summary', '')} "
        f"(health={data.get('portfolio_health')}, "
        f"urgency={data.get('urgency', 'none')})"
    )
    return data


def build_regime_forecaster(
    coordinator: Any,
    model_for_trigger: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Run Regime Forecaster agent to predict regime transitions.

    Returns:
        Parsed regime forecast dict or None on failure.
    """
    cfg = coordinator.configs.get(
        AgentRole.FORECASTER,
        AgentConfig(role=AgentRole.FORECASTER),
    )
    if not cfg.enabled:
        return None

    forecaster_input = _build_forecaster_input(coordinator)
    out = coordinator._call_agent(AgentRole.FORECASTER, forecaster_input, model_for_trigger)

    if not out.ok:
        logger.warning("[FORECASTER] Agent call failed")
        return None

    data = out.data
    scratchpad = get_pipeline_scratchpad()

    # Write forecast to scratchpad for Trade Agent to see
    scratchpad.write("forecaster", "current_regime", data.get("current_regime"))
    scratchpad.write("forecaster", "hours_until_transition", data.get("hours_until_transition", [999, 999]))
    scratchpad.write("forecaster", "predicted_next_regime", data.get("predicted_next_regime"))
    scratchpad.write("forecaster", "transition_probability", data.get("transition_probability", 0.0))
    scratchpad.write("forecaster", "impact_on_current_trades", data.get("impact_on_current_trades"))

    # Log forecast
    logger.info(
        f"[FORECASTER] Transition in {data.get('hours_until_transition', [999, 999])[0]}-"
        f"{data.get('hours_until_transition', [999, 999])[1]}h → "
        f"{data.get('predicted_next_regime')} "
        f"({data.get('transition_probability', 0.0):.0%} confidence)"
    )
    return data


def build_hypothesis_generator(
    coordinator: Any,
    model_for_trigger: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Run Hypothesis Generator agent to discover novel trading patterns.
    Runs WEEKLY (not every trade).

    Returns:
        Parsed hypotheses dict or None on failure.
    """
    cfg = coordinator.configs.get(
        AgentRole.HYPOTHESIS,
        AgentConfig(role=AgentRole.HYPOTHESIS),
    )
    if not cfg.enabled:
        return None

    hypothesis_input = _build_hypothesis_input(coordinator)
    out = coordinator._call_agent(AgentRole.HYPOTHESIS, hypothesis_input, model_for_trigger)

    if not out.ok:
        logger.warning("[HYPOTHESIS] Agent call failed")
        return None

    data = out.data
    scratchpad = get_pipeline_scratchpad()

    # Write hypotheses to scratchpad for learning agent
    scratchpad.write("hypothesis", "novel_hypotheses", data.get("novel_hypotheses", []))
    scratchpad.write("hypothesis", "pattern_gaps", data.get("pattern_gaps", []))
    scratchpad.write("hypothesis", "next_week_focus", data.get("next_week_focus", ""))

    # Log summary
    num_hyps = len(data.get("novel_hypotheses", []))
    logger.info(
        f"[HYPOTHESIS] Generated {num_hyps} novel hypotheses. "
        f"Focus: {data.get('next_week_focus', '')}"
    )
    return data


def build_correlator(
    coordinator: Any,
    model_for_trigger: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Run Correlator agent to analyze cross-asset relationships.

    Returns:
        Parsed correlation analysis dict or None on failure.
    """
    cfg = coordinator.configs.get(
        AgentRole.CORRELATOR,
        AgentConfig(role=AgentRole.CORRELATOR),
    )
    if not cfg.enabled:
        return None

    correlator_input = _build_correlator_input(coordinator)
    out = coordinator._call_agent(AgentRole.CORRELATOR, correlator_input, model_for_trigger)

    if not out.ok:
        logger.warning("[CORRELATOR] Agent call failed")
        return None

    data = out.data
    scratchpad = get_pipeline_scratchpad()

    # Write correlator output to scratchpad
    scratchpad.write("correlator", "correlation_regime", data.get("correlation_regime"))
    scratchpad.write("correlator", "btc_lead_lag", data.get("btc_lead_lag", {}))
    scratchpad.write("correlator", "pair_trade_opportunities", data.get("pair_trade_opportunities", []))
    scratchpad.write("correlator", "alerts", data.get("alerts", []))

    # Log summary
    logger.info(
        f"[CORRELATOR] {data.get('correlation_regime')} regime. "
        f"BTC→SOL lag {data.get('btc_lead_lag', {}).get('SOL', {}).get('lag_minutes', '?')}min. "
        f"Pair trades: {len(data.get('pair_trade_opportunities', []))}"
    )
    return data


# ─── Input Builders ─────────────────────────────────────────────────

def _build_portfolio_input(coordinator: Any) -> str:
    """Build input context for Portfolio Aggregator agent."""
    # This would include:
    # - All open positions (symbols, sides, sizes, entry prices)
    # - Portfolio metrics (beta, correlation, VaR, max drawdown)
    # - Regime classification per position
    # - Funding rates and their impact

    # For now, return a minimal implementation
    # In production, this would fetch from execution.position_manager and core.portfolio_analytics

    context = {
        "note": "Portfolio analysis request",
        "timestamp": "NOW",
        "positions": "TODO: inject from position_manager",
        "portfolio_stats": "TODO: inject from portfolio_analytics",
    }
    return json.dumps(context, indent=2)


def _build_forecaster_input(coordinator: Any) -> str:
    """Build input context for Regime Forecaster agent."""
    # This would include:
    # - Current regime classification
    # - Historical regime durations
    # - Volume, volatility, ADX trends
    # - BTC regime and correlation
    # - Open interest changes

    context = {
        "note": "Regime transition forecast request",
        "timestamp": "NOW",
        "current_regime": "TODO: inject from last regime agent output",
        "volume_trend": "TODO: inject from OHLCV data",
        "volatility_trend": "TODO: inject from ATR data",
        "history": "TODO: inject from regime change history",
    }
    return json.dumps(context, indent=2)


def _build_hypothesis_input(coordinator: Any) -> str:
    """Build input context for Hypothesis Generator agent."""
    # This would include:
    # - Trade history (outcomes, setups, symbols)
    # - Pattern library (what exists, edges)
    # - Pattern gaps (what's missing)
    # - Regime-specific inefficiencies

    context = {
        "note": "Novel hypothesis generation request",
        "timestamp": "NOW",
        "trade_history": "TODO: inject from decisions.jsonl",
        "pattern_library": "TODO: inject from deep_memory",
        "gaps": "TODO: compute from existing patterns",
    }
    return json.dumps(context, indent=2)


def _build_correlator_input(coordinator: Any) -> str:
    """Build input context for Correlator agent."""
    # This would include:
    # - BTC price, regime, volume, funding
    # - Altcoin prices (SOL, ETH, AVAX, DOGE, etc)
    # - Correlation matrices (7d, 30d, 90d)
    # - Lead-lag relationships
    # - Funding rate spreads

    context = {
        "note": "Cross-asset correlation analysis request",
        "timestamp": "NOW",
        "btc_data": "TODO: inject BTC OHLCV + funding",
        "alts": ["SOL", "ETH", "AVAX", "DOGE"],
        "correlations": "TODO: inject from data pipeline",
        "lead_lag_history": "TODO: inject from historical analysis",
    }
    return json.dumps(context, indent=2)
