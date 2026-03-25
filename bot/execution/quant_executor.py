"""
Quant Executor — Unified execution engine that orchestrates all optimizers.

This is the master integration layer that connects:
- SizingOptimizer (Kelly criterion, compound curves)
- PositionLayerManager (scalp/swing/regime)
- PortfolioRiskBudget (correlation-aware budgeting)
- EntryOptimizer (limit orders, burst detection)
- ExitOptimizer (partial profits, time-decay, trailing)
- SignalValueTracker (outcome quantification)

Flow:
  Signal → Classify Layer → Kelly Size → Budget Check → Entry Optimize → Execute

Usage:
    executor = QuantExecutor(equity=100.0)
    decision = executor.evaluate_signal(sniper_signal, current_price)
    if decision.execute:
        executor.execute_trade(decision)
"""

import logging
import os
from dataclasses import dataclass
from typing import Optional, Dict, Any

logger = logging.getLogger("bot.execution.quant_executor")


@dataclass
class TradeDecision:
    """Complete trade decision from the quant executor."""
    execute: bool
    symbol: str
    side: str
    layer: str              # "scalp", "swing", "regime"
    entry_method: str       # "MARKET", "LIMIT", "WAIT"
    entry_price: float
    limit_price: Optional[float]
    sl: float
    tp: float
    leverage: float
    risk_pct: float
    risk_amount: float
    position_size_usd: float
    kelly_rationale: str
    layer_rationale: str
    entry_rationale: str
    budget_rationale: str
    reject_reason: Optional[str] = None


class QuantExecutor:
    """Unified execution engine combining all optimization modules."""

    def __init__(self, equity: float = 100.0):
        self.equity = equity

        # Import and initialize all components
        from execution.sizing_optimizer import SizingOptimizer
        from execution.position_layers import PositionLayerManager
        from execution.portfolio_risk_budget import PortfolioRiskBudget
        from execution.entry_optimizer import EntryOptimizer
        from execution.exit_optimizer import ExitOptimizer

        self.sizer = SizingOptimizer()
        self.layers = PositionLayerManager()
        self.budget = PortfolioRiskBudget()
        self.entry_opt = EntryOptimizer()
        self.exit_opt = ExitOptimizer()

        logger.info(
            f"[QUANT-EXEC] Initialized: equity=${equity:.2f}, "
            f"modules=[sizer, layers, budget, entry, exit]"
        )

    def update_equity(self, equity: float) -> None:
        """Update equity for all components."""
        self.equity = equity

    def evaluate_signal(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        confidence: float,
        num_agree: int,
        regime: str,
        stop_width_pct: float,
        is_dip_buy: bool = False,
        tier: str = "PREMIUM",
        setup_key: Optional[str] = None,
    ) -> TradeDecision:
        """Evaluate a signal through the full optimization pipeline.

        Returns a TradeDecision with execute=True if the trade should be taken.
        """
        if setup_key is None:
            setup_key = f"{symbol}_{side.replace('LONG', 'BUY').replace('SHORT', 'SELL')}"

        position_side = "LONG" if side in ("BUY", "LONG") else "SHORT"

        # ── Step 1: Layer Classification ──
        layer_result = self.layers.classify_signal(
            symbol=symbol,
            side=side,
            confidence=confidence,
            num_agree=num_agree,
            regime=regime,
            stop_width_pct=stop_width_pct,
            entry_price=entry_price,
            is_dip_buy=is_dip_buy,
        )

        if layer_result is None:
            return TradeDecision(
                execute=False,
                symbol=symbol, side=position_side, layer="none",
                entry_method="NONE", entry_price=entry_price,
                limit_price=None, sl=0, tp=0,
                leverage=0, risk_pct=0, risk_amount=0,
                position_size_usd=0,
                kelly_rationale="", layer_rationale="No layer available",
                entry_rationale="", budget_rationale="",
                reject_reason="No layer capacity (all full or signal too weak)",
            )

        # ── Step 2: Kelly Sizing ──
        open_count = len(self.layers.get_all_positions())
        sizing = self.sizer.get_optimal_size(
            setup=setup_key,
            equity=self.equity,
            confidence=confidence,
            num_agree=num_agree,
            regime=regime,
            is_dip_buy=is_dip_buy,
            stop_width_pct=layer_result.stop_width_pct,
            open_positions=open_count,
        )

        # Apply layer's Kelly fraction multiplier
        adjusted_risk = sizing.risk_amount * layer_result.config.kelly_fraction_mult
        adjusted_size = sizing.position_size_usd * layer_result.config.kelly_fraction_mult

        # ── Step 3: Portfolio Budget Check ──
        can_budget, budget_reason = self.budget.can_allocate(
            symbol, position_side, adjusted_risk, self.equity
        )

        if not can_budget:
            return TradeDecision(
                execute=False,
                symbol=symbol, side=position_side,
                layer=layer_result.layer.value,
                entry_method="NONE", entry_price=entry_price,
                limit_price=None, sl=layer_result.sl_price, tp=layer_result.tp_price,
                leverage=layer_result.leverage, risk_pct=sizing.risk_pct,
                risk_amount=adjusted_risk, position_size_usd=adjusted_size,
                kelly_rationale=sizing.rationale,
                layer_rationale=layer_result.rationale,
                entry_rationale="", budget_rationale=budget_reason,
                reject_reason=f"Budget denied: {budget_reason}",
            )

        # ── Step 4: Entry Optimization ──
        entry_decision = self.entry_opt.evaluate_entry(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            confidence=confidence,
            num_agree=num_agree,
            tier=tier,
            is_dip_buy=is_dip_buy,
        )

        # Use layer's SL/TP (computed from layer config)
        use_leverage = min(layer_result.leverage, sizing.leverage)

        return TradeDecision(
            execute=entry_decision.action != "WAIT",
            symbol=symbol,
            side=position_side,
            layer=layer_result.layer.value,
            entry_method=entry_decision.action,
            entry_price=entry_price,
            limit_price=entry_decision.limit_price,
            sl=layer_result.sl_price,
            tp=layer_result.tp_price,
            leverage=use_leverage,
            risk_pct=sizing.risk_pct,
            risk_amount=round(adjusted_risk, 2),
            position_size_usd=round(adjusted_size, 2),
            kelly_rationale=sizing.rationale,
            layer_rationale=layer_result.rationale,
            entry_rationale=entry_decision.rationale,
            budget_rationale="Budget approved",
        )

    def record_outcome(self, setup: str, won: bool, pnl_pct: float, trade_id: str = "") -> None:
        """Record a trade outcome for Kelly learning and budget adjustment."""
        self.sizer.record_outcome(setup, won, pnl_pct)
        if trade_id:
            self.budget.release(trade_id, won)
