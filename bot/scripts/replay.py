"""
Replay mode: feed historical candles into the live engine loop.

Reuses the same code paths as live trading (ensemble, ML, position manager)
but replays from stored OHLCV data instead of live feeds.

Usage:
    python -m scripts.replay --symbol BTC --days 7

Output:
    data/replay/log.csv     (signals, state transitions, trades)
    data/replay/equity.csv  (equity curve)
"""

import argparse
import csv
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.fetcher import DataFetcher
from trading_config import TradingConfig, DEFAULT_SYMBOLS
from strategies.regime_trend import RegimeTrendStrategy
from strategies.monte_carlo_zones import MonteCarloZonesStrategy
from strategies.confidence_scorer import ConfidenceScorerStrategy
from strategies.multi_tier_quality import MultiTierQualityStrategy
from strategies.ensemble import EnsembleStrategy
from execution.position_manager import PositionManager
from execution.leverage import LeverageManager
from execution.risk import RiskManager, CircuitBreaker
from data.strategy_weights import StrategyWeightManager
from multi_strategy_main import get_tp1_close_pct

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("bot.replay")


def replay(symbol: str, days: int = 7):
    """Replay historical candles through the live trading logic."""
    config = TradingConfig()
    fetcher = DataFetcher(cache_ttl=3600)
    sym_cfg = DEFAULT_SYMBOLS.get(symbol)
    if not sym_cfg:
        logger.error(f"Unknown symbol: {symbol}")
        return

    weight_mgr = StrategyWeightManager(path="ml_data/strategy_weights.json")
    strategies = [
        RegimeTrendStrategy(DEFAULT_SYMBOLS, config.htf_hours),
        MonteCarloZonesStrategy(DEFAULT_SYMBOLS),
        ConfidenceScorerStrategy(DEFAULT_SYMBOLS, data_dir="ml_data"),
        MultiTierQualityStrategy(DEFAULT_SYMBOLS),
    ]
    ensemble = EnsembleStrategy(
        strategies=strategies, mode=config.ensemble_mode,
        min_votes=config.min_votes_required,
        weight_manager=weight_mgr, veto_ratio=config.veto_ratio,
    )
    pos_mgr = PositionManager(
        taker_fee_bps=config.taker_fee_bps,
        enable_trailing=config.enable_trailing_stop,
        trailing_atr_mult=config.trailing_stop_atr_mult,
    )
    risk_mgr = RiskManager(
        starting_equity=config.starting_equity,
        risk_per_trade=config.risk_per_trade,
        max_open_positions=config.max_open_positions,
        circuit_breaker=CircuitBreaker(),
    )
    lev_mgr = LeverageManager(
        enable_leverage=config.enable_leverage,
        max_leverage=config.max_leverage,
    )

    # Fetch all timeframes
    needed_tfs = ensemble.get_all_required_timeframes()
    all_data = fetcher.fetch_multi_timeframe(symbol, sym_cfg.coingecko_id, needed_tfs)

    df_1h = all_data.get("1h")
    if df_1h is None or df_1h.empty:
        logger.error(f"No 1h data for {symbol}")
        return

    # Walk forward through 1h candles
    out_dir = os.path.join("data", "replay")
    os.makedirs(out_dir, exist_ok=True)

    log_rows = []
    equity_rows = []
    min_bars = 50  # need 50 bars of history before evaluating

    for i in range(min_bars, len(df_1h)):
        # Build windowed data for each timeframe
        data_window = {}
        for tf, df in all_data.items():
            if df is not None and not df.empty:
                if tf == "1h":
                    data_window[tf] = df.iloc[:i+1].copy()
                else:
                    data_window[tf] = df.copy()

        price = float(df_1h["close"].iloc[i])
        ts = df_1h["time"].iloc[i] if "time" in df_1h.columns else datetime.now(timezone.utc)

        # Update positions
        df_5m = data_window.get("5m")
        events = pos_mgr.update_price(symbol, price, df_5m=df_5m)
        for event in events:
            risk_mgr.update_equity(event.pnl - event.fee)
            log_rows.append({
                "timestamp": str(ts), "type": "TRADE", "symbol": symbol,
                "action": event.action, "price": price, "pnl": event.pnl,
                "state_path": event.metadata.get("state_path", ""),
            })

        # Generate signal
        open_pos = pos_mgr.get_open_positions()
        if symbol not in open_pos and risk_mgr.can_open_position(pos_mgr.get_open_count()):
            sig = ensemble.evaluate(symbol, data_window)
            if sig and sig.confidence >= 65:
                rr1 = sig.risk_reward_tp1
                if rr1 >= 0.5:
                    lev = lev_mgr.decide(
                        sig.confidence,
                        sig.metadata.get("num_agree", 1),
                        sig.metadata.get("total_strategies", 4),
                        sym_cfg.risk_tier,
                        sum(1 for p in open_pos.values() if p.leverage > 5),
                    )
                    if lev.leverage > 0:
                        qty = risk_mgr.calculate_qty(
                            sig.entry, sig.sl,
                            leverage=lev.leverage,
                            risk_multiplier=lev.risk_multiplier,
                        )
                        if qty > 0:
                            tp1_pct = get_tp1_close_pct(sig.confidence)
                            side = "LONG" if sig.side == "BUY" else "SHORT"
                            pos_mgr.open_position(
                                symbol=symbol, side=side,
                                entry=sig.entry, qty=qty,
                                sl=sig.sl, tp1=sig.tp1, tp2=sig.tp2,
                                atr=sig.atr, leverage=lev.leverage,
                                strategy=sig.strategy,
                                confidence=sig.confidence,
                                tp1_close_pct=tp1_pct,
                            )
                            log_rows.append({
                                "timestamp": str(ts), "type": "SIGNAL", "symbol": symbol,
                                "action": f"OPEN {side}", "price": price,
                                "pnl": 0, "state_path": "",
                            })

        equity_rows.append({
            "timestamp": str(ts),
            "equity": risk_mgr.equity,
        })

    # Write output
    if log_rows:
        with open(os.path.join(out_dir, "log.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=log_rows[0].keys())
            w.writeheader()
            w.writerows(log_rows)

    if equity_rows:
        with open(os.path.join(out_dir, "equity.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=equity_rows[0].keys())
            w.writeheader()
            w.writerows(equity_rows)

    # Summary
    summary = pos_mgr.get_trade_summary()
    logger.info(f"Replay complete: {len(equity_rows)} bars, {summary.get('total_trades', 0)} trades")
    logger.info(f"  Final equity: ${risk_mgr.equity:,.2f}")
    logger.info(f"  Win rate: {summary.get('win_rate', 0):.0%}")
    logger.info(f"  Net PnL: ${summary.get('net_pnl', 0):+,.2f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replay historical data through live logic")
    parser.add_argument("--symbol", default="BTC")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()
    replay(args.symbol, args.days)
