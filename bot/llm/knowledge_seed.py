"""
Knowledge Seed: Foundational trading education for the LLM.

This module seeds the LLM's knowledge base with structured trading
education - the equivalent of a complete trading course that the LLM
must internalize before it can make decisions.

The knowledge is organized into categories:

  1. MARKET STRUCTURE      - How markets work, order flow, liquidity
  2. TECHNICAL ANALYSIS    - Chart patterns, indicators, price action
  3. RISK MANAGEMENT       - Position sizing, R:R, drawdown control
  4. CRYPTO SPECIFICS      - Funding rates, OI, liquidation mechanics
  5. SIGNAL INTERPRETATION - How to read and evaluate trading signals
  6. CHART READING         - How to analyze chart levels and structure
  7. PSYCHOLOGY            - Emotional discipline, FOMO, revenge trading
  8. STRATEGY KNOWLEDGE    - Understanding each ensemble strategy

This knowledge is injected into the LLM's context when analyzing
signals, making decisions, and running learning cycles. The LLM
builds ON TOP of this foundation with its own observations.
"""

import logging
import time
from typing import Dict, List, Any

logger = logging.getLogger("bot.llm.knowledge_seed")


# ═══════════════════════════════════════════════════════════════
# 1. MARKET STRUCTURE KNOWLEDGE
# ═══════════════════════════════════════════════════════════════

MARKET_STRUCTURE = [
    # Liquidity and order flow
    {
        "type": "axiom",
        "content": "Price moves toward liquidity. Stop losses cluster at obvious levels (round numbers, recent highs/lows). Smart money hunts these clusters before reversing.",
        "category": "market_structure",
        "tags": ["liquidity", "stops", "manipulation"],
    },
    {
        "type": "axiom",
        "content": "Volume confirms price movement. A move up on high volume is real. A move up on low volume is suspect and likely to reverse.",
        "category": "market_structure",
        "tags": ["volume", "confirmation"],
    },
    {
        "type": "principle",
        "content": "Support becomes resistance once broken, and resistance becomes support once reclaimed. Always check these flips before entering.",
        "category": "market_structure",
        "tags": ["support", "resistance", "flip"],
    },
    {
        "type": "principle",
        "content": "The trend is determined by higher highs and higher lows (uptrend) or lower highs and lower lows (downtrend). A break of structure signals potential reversal.",
        "category": "market_structure",
        "tags": ["trend", "structure"],
    },
    {
        "type": "axiom",
        "content": "Whales accumulate in ranges and distribute at highs. Prolonged consolidation after a move up often means distribution. After a move down, it means accumulation.",
        "category": "market_structure",
        "tags": ["accumulation", "distribution", "whales"],
    },

    # Order book dynamics
    {
        "type": "principle",
        "content": "Large buy walls can be fake (spoofing). Don't rely on order book depth alone. Actual fills (volume on candles) are more reliable than standing orders.",
        "category": "market_structure",
        "tags": ["orderbook", "spoofing"],
    },
    {
        "type": "principle",
        "content": "Market makers profit from the spread. In low liquidity, spreads widen and slippage increases. Avoid market orders in thin markets - use limits.",
        "category": "market_structure",
        "tags": ["spread", "slippage", "liquidity"],
    },
]

# ═══════════════════════════════════════════════════════════════
# 2. TECHNICAL ANALYSIS KNOWLEDGE
# ═══════════════════════════════════════════════════════════════

TECHNICAL_ANALYSIS = [
    # Key indicators
    {
        "type": "principle",
        "content": "RSI above 70 is overbought, below 30 is oversold. BUT in a strong trend, RSI can stay overbought for extended periods. Don't short RSI 80 in a bull trend.",
        "category": "technical",
        "tags": ["RSI", "overbought", "oversold"],
    },
    {
        "type": "principle",
        "content": "MACD crossover (signal line cross) confirms momentum shifts. MACD histogram divergence from price is a strong reversal signal.",
        "category": "technical",
        "tags": ["MACD", "momentum", "divergence"],
    },
    {
        "type": "principle",
        "content": "EMA 20 and EMA 50 crossovers (golden cross / death cross) are lagging but reliable. Price above both EMAs = bullish structure. Below both = bearish.",
        "category": "technical",
        "tags": ["EMA", "crossover", "trend"],
    },
    {
        "type": "principle",
        "content": "ATR (Average True Range) measures volatility. When ATR is high, use wider stops. When ATR is low, tighter stops work. Always scale stops to ATR, not fixed percentages.",
        "category": "technical",
        "tags": ["ATR", "volatility", "stops"],
    },
    {
        "type": "principle",
        "content": "VWAP (Volume Weighted Average Price) is institutional. Price above VWAP = buyers in control. Below = sellers. VWAP acts as dynamic support/resistance.",
        "category": "technical",
        "tags": ["VWAP", "institutional", "support"],
    },

    # Chart patterns
    {
        "type": "principle",
        "content": "Higher timeframe structure always wins. A 1h buy signal against a daily downtrend will likely fail. Always check the 4h and daily trend before trading lower timeframes.",
        "category": "technical",
        "tags": ["timeframe", "alignment", "HTF"],
    },
    {
        "type": "principle",
        "content": "Breakouts from tight ranges (Bollinger Band squeeze, low ATR) produce the strongest moves. The longer the compression, the bigger the expansion.",
        "category": "technical",
        "tags": ["breakout", "squeeze", "compression"],
    },
    {
        "type": "observation",
        "content": "Failed breakouts (price breaks above resistance then immediately returns below) are one of the strongest reversal signals. Trade the failure, not the breakout.",
        "category": "technical",
        "tags": ["failed_breakout", "reversal", "trap"],
    },
    {
        "type": "principle",
        "content": "Divergence between price and RSI/MACD is a leading indicator. Bullish divergence: price makes lower low, RSI makes higher low = potential bottom.",
        "category": "technical",
        "tags": ["divergence", "RSI", "reversal"],
    },
]

# ═══════════════════════════════════════════════════════════════
# 3. RISK MANAGEMENT KNOWLEDGE
# ═══════════════════════════════════════════════════════════════

RISK_MANAGEMENT = [
    {
        "type": "axiom",
        "content": "Never risk more than 1-2% of equity on a single trade. A string of 5 losses at 2% risk = 10% drawdown, which is recoverable. 5 losses at 10% = game over.",
        "category": "risk",
        "tags": ["position_sizing", "risk_per_trade"],
    },
    {
        "type": "axiom",
        "content": "The stop loss is sacred. Once set, NEVER widen it to avoid getting stopped out. Moving a stop further away is the #1 way traders blow up.",
        "category": "risk",
        "tags": ["stop_loss", "discipline"],
    },
    {
        "type": "axiom",
        "content": "Risk-reward ratio must be at least 1.5:1 for any trade. If risking $100, the target must be at least $150. Below 1.5:1, the math doesn't work over time.",
        "category": "risk",
        "tags": ["risk_reward", "RR"],
    },
    {
        "type": "principle",
        "content": "Take partial profits at TP1 (40-50% of position). This locks in gains and lets the rest ride risk-free. Emotion cannot affect a position that's already in profit.",
        "category": "risk",
        "tags": ["partial_profits", "TP1", "risk_free"],
    },
    {
        "type": "principle",
        "content": "After TP1 is hit, move stop loss to breakeven. Now the trade is risk-free. The remaining position either hits TP2 for bonus profit or gets stopped at breakeven.",
        "category": "risk",
        "tags": ["breakeven_stop", "risk_free"],
    },
    {
        "type": "axiom",
        "content": "Correlation kills portfolios. Don't open 3 long positions on correlated assets (BTC + ETH + SOL). If BTC dumps, they all dump. Diversify or accept concentrated risk.",
        "category": "risk",
        "tags": ["correlation", "diversification"],
    },
    {
        "type": "principle",
        "content": "Leverage amplifies BOTH gains and losses. 10x leverage means a 10% move against you wipes out the position. Only use high leverage (5x+) with tight stops and high confidence.",
        "category": "risk",
        "tags": ["leverage", "amplification"],
    },
    {
        "type": "axiom",
        "content": "Circuit breakers exist for a reason. After 5% daily loss, STOP TRADING. The tilt is real. Come back tomorrow with fresh eyes. Overriding circuit breakers requires 92%+ confidence.",
        "category": "risk",
        "tags": ["circuit_breaker", "tilt", "discipline"],
    },
]

# ═══════════════════════════════════════════════════════════════
# 4. CRYPTO-SPECIFIC KNOWLEDGE
# ═══════════════════════════════════════════════════════════════

CRYPTO_SPECIFICS = [
    {
        "type": "axiom",
        "content": "Funding rate is the cost of holding a leveraged position. Positive funding = longs pay shorts (market is overleveraged long). Negative = shorts pay longs. Extreme funding precedes reversals.",
        "category": "crypto",
        "tags": ["funding", "cost", "reversal"],
    },
    {
        "type": "axiom",
        "content": "Open Interest (OI) shows total outstanding contracts. Rising OI + rising price = new longs entering (trend continuation). Rising OI + falling price = new shorts entering (bearish). Falling OI = positions closing.",
        "category": "crypto",
        "tags": ["open_interest", "trend", "positioning"],
    },
    {
        "type": "principle",
        "content": "Liquidation cascades create the biggest moves. When OI drops rapidly + price drops rapidly, it's a liquidation cascade. These create overshoots and snap-back rallies.",
        "category": "crypto",
        "tags": ["liquidation", "cascade", "overshoot"],
    },
    {
        "type": "principle",
        "content": "BTC dominance drives alt behavior. When BTC dominance rises, alts bleed. When BTC dominance falls, alts pump. Never long alts when BTC is dumping - they fall 2-3x harder.",
        "category": "crypto",
        "tags": ["BTC_dominance", "alts", "correlation"],
    },
    {
        "type": "principle",
        "content": "Crypto is 24/7 but not equally liquid. Asian session (00:00-08:00 UTC) and European open (07:00-09:00 UTC) are high activity. US close to Asian open (21:00-00:00 UTC) is thin.",
        "category": "crypto",
        "tags": ["sessions", "liquidity", "timing"],
    },
    {
        "type": "observation",
        "content": "Weekend markets are thinner, more manipulable, and produce more false signals. Reduce position size on weekends. Best signals come Tuesday-Thursday.",
        "category": "crypto",
        "tags": ["weekend", "liquidity", "timing"],
    },
    {
        "type": "principle",
        "content": "Meme coins (DOGE, PEPE, FARTCOIN) have higher volatility and thinner books. They move 2-5x faster than BTC. Use wider stops, lower leverage, and expect bigger swings.",
        "category": "crypto",
        "tags": ["memecoins", "volatility", "risk"],
    },
    # Funding cost awareness
    {
        "type": "axiom",
        "content": "Funding rate is a REAL COST paid every 8 hours. At 0.05% funding on 5x leverage, you lose 0.75%/day just holding. Your PnL = Price Move - Funding Paid - Fees. Never forget the funding term.",
        "category": "crypto",
        "tags": ["funding", "cost", "hold_time", "critical"],
    },
    {
        "type": "axiom",
        "content": "High positive funding (>0.03%) on longs means you are PAYING to hold. Either trade quickly (scalp), take the opposite side (get paid), or stay flat. Holding a long in high funding is bleeding money.",
        "category": "crypto",
        "tags": ["funding", "cost", "longs", "critical"],
    },
    {
        "type": "principle",
        "content": "Funding cost scales with leverage. 0.01% funding on 10x = 0.3%/day cost. On a trade expecting 2% move over 3 days, funding eats 0.9% — nearly half your profit. Always factor funding into R:R math.",
        "category": "crypto",
        "tags": ["funding", "leverage", "risk_reward"],
    },
    {
        "type": "principle",
        "content": "When funding is extreme (>0.05%), the crowded side usually gets liquidated. This is both a reversal signal AND a cost signal. Trading against extreme funding is often free money — you get paid to hold AND profit from the reversal.",
        "category": "crypto",
        "tags": ["funding", "reversal", "opportunity"],
    },
    {
        "type": "principle",
        "content": "In high funding environments, prefer shorter hold times. A 2-hour scalp avoids the 8-hour funding payment entirely. Adjust your entry refinement: 'market now' for quick scalps, avoid 'scale in' which extends hold time.",
        "category": "crypto",
        "tags": ["funding", "hold_time", "scalp"],
    },
]

# ═══════════════════════════════════════════════════════════════
# 5. SIGNAL INTERPRETATION KNOWLEDGE
# ═══════════════════════════════════════════════════════════════

SIGNAL_INTERPRETATION = [
    {
        "type": "principle",
        "content": "A good trading signal must have: clear entry, defined stop loss, at least one take profit target, and a reason (why NOW, not just why this direction).",
        "category": "signals",
        "tags": ["quality", "components"],
    },
    {
        "type": "principle",
        "content": "Signal timing matters as much as direction. A correct direction with wrong timing gets stopped out before the move happens. Check if the signal is early, on time, or late.",
        "category": "signals",
        "tags": ["timing", "entry"],
    },
    {
        "type": "axiom",
        "content": "Never take a signal blindly. Every signal should be verified against the chart, the current regime, and cross-market conditions. The signal provider doesn't know YOUR risk tolerance.",
        "category": "signals",
        "tags": ["verification", "independence"],
    },
    {
        "type": "principle",
        "content": "Multiple timeframe confirmation increases signal quality. A buy signal on 1h that aligns with 4h uptrend and daily support = high quality. A buy signal on 1h against daily downtrend = low quality.",
        "category": "signals",
        "tags": ["MTF", "confirmation", "quality"],
    },
    {
        "type": "principle",
        "content": "Strategy agreement is the strongest predictor of trade success. When 3+ independent strategies agree on direction, the probability of success increases significantly.",
        "category": "signals",
        "tags": ["agreement", "ensemble", "probability"],
    },
    {
        "type": "observation",
        "content": "Signals with vague entry zones ('buy around 95k-97k') are weaker than precise entries ('buy at 96,200 on the retest'). Precision = conviction from the signal source.",
        "category": "signals",
        "tags": ["precision", "conviction"],
    },
    {
        "type": "principle",
        "content": "Check the signal's risk-reward BEFORE taking it. If the stop is 3% away and the target is 2% away, the R:R is 0.67:1 - that's a bad trade even if the direction is right.",
        "category": "signals",
        "tags": ["risk_reward", "evaluation"],
    },
]

# ═══════════════════════════════════════════════════════════════
# 6. CHART READING KNOWLEDGE
# ═══════════════════════════════════════════════════════════════

CHART_READING = [
    {
        "type": "principle",
        "content": "Read charts from left to right. Start with the daily, then 4h, then 1h. The higher timeframe sets the bias, the lower timeframe finds the entry.",
        "category": "chart_reading",
        "tags": ["top_down", "HTF", "LTF"],
    },
    {
        "type": "principle",
        "content": "Key levels come from: previous day high/low, weekly open, monthly open, significant swing points, round numbers (90k, 95k, 100k). These are where orders cluster.",
        "category": "chart_reading",
        "tags": ["key_levels", "support", "resistance"],
    },
    {
        "type": "principle",
        "content": "Candlestick wicks show rejection. A long lower wick on a daily candle means buyers stepped in hard. A long upper wick means sellers rejected the price. Pay attention to wick length relative to body.",
        "category": "chart_reading",
        "tags": ["wicks", "rejection", "candles"],
    },
    {
        "type": "principle",
        "content": "Volume profile shows where most trading occurred. High Volume Nodes (HVN) act as magnets. Low Volume Nodes (LVN) get passed through quickly. Price spends time at HVN and gaps through LVN.",
        "category": "chart_reading",
        "tags": ["volume_profile", "HVN", "LVN"],
    },
    {
        "type": "principle",
        "content": "When evaluating a signal's entry/SL/TP: map the levels onto the chart structure. Is the entry at support/resistance? Is the SL below the last swing low? Is the TP at a logical target?",
        "category": "chart_reading",
        "tags": ["mapping", "structure", "evaluation"],
    },
    {
        "type": "principle",
        "content": "Consolidation (low ATR, tight range) followed by expansion (volume + breakout) is the highest-probability setup. The entry is on the breakout retest, not the initial break.",
        "category": "chart_reading",
        "tags": ["consolidation", "expansion", "retest"],
    },
]

# ═══════════════════════════════════════════════════════════════
# 7. TRADING PSYCHOLOGY KNOWLEDGE
# ═══════════════════════════════════════════════════════════════

PSYCHOLOGY = [
    {
        "type": "axiom",
        "content": "FOMO (Fear Of Missing Out) is the enemy. If you missed the entry, let it go. Chasing a move that already happened is how you buy tops and sell bottoms.",
        "category": "psychology",
        "tags": ["FOMO", "discipline"],
    },
    {
        "type": "axiom",
        "content": "Revenge trading after a loss is the fastest way to blow up. After a loss, the correct action is to WAIT, not trade more aggressively. The circuit breaker enforces this.",
        "category": "psychology",
        "tags": ["revenge_trading", "tilt", "discipline"],
    },
    {
        "type": "principle",
        "content": "The best trade is often NO trade. If the setup isn't clear, if the regime is uncertain, if cross-market is conflicting - staying flat IS a position. Cash has zero drawdown.",
        "category": "psychology",
        "tags": ["patience", "flat", "discipline"],
    },
    {
        "type": "principle",
        "content": "Confirmation bias makes you see what you want to see. If you're already long, you'll interpret neutral data as bullish. Always consider the counter-argument before confirming a bias.",
        "category": "psychology",
        "tags": ["confirmation_bias", "objectivity"],
    },
    {
        "type": "principle",
        "content": "Size down after a losing streak, size up after a winning streak. This is counterintuitive but mathematically optimal - winning streaks compound, losing streaks preserve capital.",
        "category": "psychology",
        "tags": ["streak", "sizing", "optimal"],
    },
]

# ═══════════════════════════════════════════════════════════════
# 8. STRATEGY-SPECIFIC KNOWLEDGE
# ═══════════════════════════════════════════════════════════════

STRATEGY_KNOWLEDGE = [
    # ── regime_trend: Theory, HOW, Trust, Failure ──
    {
        "type": "axiom",
        "content": "RegimeTrend uses WaveTrend oscillator on 1h for entry timing, filtered by MACD histogram + MFI on 6h and 16h for regime confirmation. It answers: 'Is momentum shifting AND does the higher timeframe regime agree?'",
        "category": "strategy",
        "tags": ["regime_trend", "WaveTrend", "theory"],
    },
    {
        "type": "principle",
        "content": "RegimeTrend alignment scored 0-4: (1) WaveTrend cross direction, (2) MFI above/below 50, (3) 6h MACD+MFI bullish, (4) 16h MACD+MFI bullish. Needs 3/4 minimum. 4/4 = highest conviction. Confidence = align × 25.",
        "category": "strategy",
        "tags": ["regime_trend", "alignment", "confidence"],
    },
    {
        "type": "principle",
        "content": "RegimeTrend excels in trending markets (strong regime). Fails in ranges where WaveTrend produces false crosses. MFI < 40 in a bullish regime = divergence warning. Momentum entries (recent cross, not this-bar) are slightly lower conviction but catch trends early.",
        "category": "strategy",
        "tags": ["regime_trend", "trust", "failure"],
    },

    # ── monte_carlo_zones: Theory, HOW, Trust, Failure ──
    {
        "type": "axiom",
        "content": "MonteCarlo uses SMA20 ± k×stdev to define statistical zones (DEEP_BUY, BUY, HOLD, SELL, SAFE_SELL). Price in extreme zones = statistically likely to revert. 1000 Monte Carlo simulations project 12h forward price probability using historical volatility.",
        "category": "strategy",
        "tags": ["monte_carlo", "zones", "theory"],
    },
    {
        "type": "principle",
        "content": "MonteCarlo is a mean-reversion strategy. It buys when price is in buy zone AND MC simulation shows >60% up probability. RSI14 < 30 confirms oversold. It answers: 'Is price statistically extreme AND likely to revert?'",
        "category": "strategy",
        "tags": ["monte_carlo", "mean_reversion", "confidence"],
    },
    {
        "type": "principle",
        "content": "MonteCarlo excels in range-bound markets where price oscillates around SMA20. Fails in trends where price blows through zones without reverting. News dislocations make the historical distribution unreliable. Trust it most when RSI confirms extremes.",
        "category": "strategy",
        "tags": ["monte_carlo", "trust", "failure"],
    },

    # ── confidence_scorer: Theory, HOW, Trust, Failure ──
    {
        "type": "axiom",
        "content": "ConfidenceScorer uses the same zones as MonteCarlo but adds historical win rate tracking per (symbol, action) pair. It adjusts confidence by observed outcomes: high past accuracy = confidence boost, low accuracy = reduction. It answers: 'Has this exact type of signal historically worked?'",
        "category": "strategy",
        "tags": ["confidence_scorer", "meta", "theory"],
    },
    {
        "type": "principle",
        "content": "ConfidenceScorer is the most adaptive strategy. Trust grows with sample size — 20+ similar trades = statistically meaningful. Best used to arbitrate when other strategies disagree. Cold start problem: unreliable with < 10 trades. Lags regime shifts because it learns from past, not present.",
        "category": "strategy",
        "tags": ["confidence_scorer", "trust", "adaptive"],
    },

    # ── multi_tier_quality: Theory, HOW, Trust, Failure ──
    {
        "type": "axiom",
        "content": "MultiTierQuality uses 5m EMA20/EMA50 crossover for micro-trend direction, confirmed by session VWAP alignment and 1h EMA trend for macro direction. Three tiers: PRIORITY (75%+), REGULAR (65%+), MANUAL (<65%). It answers: 'Is there a clean micro-entry aligned with the macro trend?'",
        "category": "strategy",
        "tags": ["multi_tier", "EMA", "VWAP", "theory"],
    },
    {
        "type": "principle",
        "content": "MultiTierQuality excels for scalps (5-30min holds). When EMA + VWAP + 1h all align = high conviction. Noisy in ranges where EMA crossovers whipsaw. MANUAL tier = low conviction, should not drive decisions. Strongest when combined with regime_trend macro direction.",
        "category": "strategy",
        "tags": ["multi_tier", "trust", "scalp", "failure"],
    },

    # ── Cross-strategy interpretation ──
    {
        "type": "principle",
        "content": "When regime_trend and multi_tier_quality agree on direction, the signal has both macro (6h/16h regime) and micro (5m entry) confirmation — highest quality setup. regime_trend provides the 'why' (regime supports), multi_tier provides the 'when' (exact entry bar).",
        "category": "strategy",
        "tags": ["cross_strategy", "regime_trend", "multi_tier"],
    },
    {
        "type": "principle",
        "content": "monte_carlo acts as a contrarian check on regime_trend. If regime_trend says BUY but monte_carlo says price is in SELL zone, the trade may be chasing. If both agree (regime bullish + price in buy zone), the setup is strong from both trend and mean-reversion perspectives.",
        "category": "strategy",
        "tags": ["cross_strategy", "monte_carlo", "regime_trend"],
    },
    {
        "type": "principle",
        "content": "confidence_scorer with hist_WR > 60% for a setup type = validated statistical edge. Weight this signal up. hist_WR < 40% = historically losing setup. This should override other strategies' raw confidence scores.",
        "category": "strategy",
        "tags": ["cross_strategy", "confidence_scorer", "edge"],
    },

    # ── Ensemble rules ──
    {
        "type": "axiom",
        "content": "The ensemble voting system requires 2+ strategy agreement for a trade. This is the primary quality filter. 3-strategy agreement has historically 2x better win rate than 2-strategy. Duration-aware weighting: scalps weight 5m signals, trend trades weight daily signals.",
        "category": "strategy",
        "tags": ["ensemble", "voting", "agreement"],
    },
    {
        "type": "principle",
        "content": "When evaluating signal ctx (context), read the indicator values, not just the direction. 'WT cross-up, 4/4 align' is vastly different from 'WT cross-up, 2/4 align (momentum)'. The ctx tells you HOW strong the signal's own internal confirmation is.",
        "category": "strategy",
        "tags": ["signal_context", "interpretation"],
    },

    # ── Predictive patterns — HOW TO PREDICT where price goes ──
    {
        "type": "axiom",
        "content": "PREDICTION RULE: Form a directional thesis BEFORE evaluating a trade. 'Where is price going and why?' beats 'Should I take this signal?' Every decision starts with a prediction. The trade either aligns with your prediction or it doesn't.",
        "category": "strategy",
        "tags": ["prediction", "thesis", "framework"],
    },
    {
        "type": "principle",
        "content": "Convergent confluence is the strongest predictor: when trend-following (regime_trend) AND mean-reversion (monte_carlo) agree on direction, price is BOTH trending AND at a statistical edge. This is the highest-probability setup — size up aggressively.",
        "category": "strategy",
        "tags": ["confluence", "convergent", "prediction"],
    },
    {
        "type": "principle",
        "content": "Conflicting strategies are INFORMATIVE, not noise. regime_trend BUY + monte_carlo SELL zone = price is trending but overextended. Prediction: short-term pullback within the trend. Action: wait for pullback to MC buy zone, then enter with trend.",
        "category": "strategy",
        "tags": ["conflict", "interpretation", "prediction"],
    },
    {
        "type": "principle",
        "content": "RSI divergence + WT divergence = strongest reversal predictor. If price makes new high but RSI and WaveTrend don't, the move is exhausting. Predict reversal. If MFI also dropping (MFI<40 in bull): double confirmation of exhaustion.",
        "category": "strategy",
        "tags": ["divergence", "reversal", "prediction"],
    },
    {
        "type": "principle",
        "content": "MC probability >70% with RSI extreme (<25 or >75) = high-probability mean-reversion. Predict a return to SMA20 within 12h. The further price deviates from SMA20 in sigmas, the stronger the reversion pull. 2+ sigma = strong, 3+ sigma = very strong.",
        "category": "strategy",
        "tags": ["monte_carlo", "extreme", "prediction"],
    },
    {
        "type": "principle",
        "content": "BTC leads, alts follow with 10-30min lag. If BTC breaks structure (new 4h high/low), predict alts will follow within 30min. Use BTC's move to front-run alt entries — this is the single most reliable cross-market predictor.",
        "category": "strategy",
        "tags": ["btc_lead", "correlation", "prediction"],
    },
    {
        "type": "principle",
        "content": "Veto is a prediction opportunity. When you veto a trade, you're predicting the OPPOSITE will happen. Track your veto accuracy — if vetoed trades would have won (vacc < 0.50), your predictions are inverted. Consider flipping your thesis when vacc is poor.",
        "category": "strategy",
        "tags": ["veto", "prediction", "counter_thesis"],
    },

    # ── Confidence interpretation per strategy ──
    {
        "type": "principle",
        "content": "RegimeTrend confidence = align × 25: 75% means 3/4 criteria met (cross + MFI + one HTF). 100% means 4/4 = all timeframes confirming. Momentum entries (-5% penalty) are slightly weaker but catch trends earlier. Read ctx for which criteria are missing.",
        "category": "strategy",
        "tags": ["regime_trend", "confidence", "interpretation"],
    },
    {
        "type": "principle",
        "content": "MonteCarlo confidence = zone depth + MC probability + RSI confirmation. DEEP_BUY with MC>70%up and RSI<30 → maximum conviction (~85%). Regular BUY with MC~55% → moderate conviction (~65%). The MC probability is forward-looking — it tells you the statistical odds, not just current position.",
        "category": "strategy",
        "tags": ["monte_carlo", "confidence", "interpretation"],
    },
    {
        "type": "principle",
        "content": "ConfidenceScorer adjusts base zone confidence by historical win rate. If hist_WR=70% for BUY signals on this symbol, confidence gets boosted. If hist_WR=35%, confidence gets crushed. hist_WR=n/a means cold start — treat as 50% baseline, don't discount or boost.",
        "category": "strategy",
        "tags": ["confidence_scorer", "confidence", "interpretation"],
    },
    {
        "type": "principle",
        "content": "MultiTier confidence maps to tiers: PRIORITY (75%+) = all alignments (EMA cross + VWAP + 1h). REGULAR (65-74%) = 2/3 aligned. MANUAL (<65%) = weak, should not drive decisions alone. VWAP opposition is a strong negative — price fighting VWAP rarely sustains.",
        "category": "strategy",
        "tags": ["multi_tier", "confidence", "interpretation"],
    },

    # ── Regime transition prediction ──
    {
        "type": "axiom",
        "content": "REGIME TRANSITION SIGNALS: Volume rising + OI expanding + funding tilting one way = trend forming. Volume dying + OI flat + funding normalizing = trend exhausting → range. Volume spike + OI contracting = panic/liquidation cascade. Detect transitions EARLY for profit.",
        "category": "strategy",
        "tags": ["regime", "transition", "prediction"],
    },
    {
        "type": "principle",
        "content": "Trend regime is where 70%+ of all profit is made. Be aggressive entering trend trades, patient exiting them. Range regime: most trades are small winners or small losers — reduce frequency, tighten targets. Panic: stay flat. The regime determines your playbook, not individual signals.",
        "category": "strategy",
        "tags": ["regime", "profitability", "playbook"],
    },
]


# ═══════════════════════════════════════════════════════════════
# Knowledge Seeding Function
# ═══════════════════════════════════════════════════════════════

ALL_KNOWLEDGE = (
    MARKET_STRUCTURE +
    TECHNICAL_ANALYSIS +
    RISK_MANAGEMENT +
    CRYPTO_SPECIFICS +
    SIGNAL_INTERPRETATION +
    CHART_READING +
    PSYCHOLOGY +
    STRATEGY_KNOWLEDGE
)


def seed_knowledge_base(force: bool = False):
    """Seed the teaching engine's knowledge base with foundational knowledge.

    Only runs if the knowledge base is empty or force=True.
    This is the LLM's 'student course' - everything it needs to know
    before it starts learning from live data.
    """
    from llm.self_teaching import get_teaching_engine, KnowledgeType

    engine = get_teaching_engine()
    kb = engine.knowledge

    # Check if already seeded
    existing = kb.get_stats()
    if existing.get("total_entries", 0) > 20 and not force:
        logger.info(
            f"[KNOWLEDGE-SEED] Knowledge base already has {existing['total_entries']} entries. "
            f"Skipping seed (use force=True to re-seed)."
        )
        return

    count = 0
    for entry in ALL_KNOWLEDGE:
        kb.add(
            knowledge_type=entry["type"],
            content=entry["content"],
            confidence=0.90 if entry["type"] == "axiom" else 0.75,
            category=entry.get("category", ""),
            tags=entry.get("tags", []),
            source="student_course",
        )
        count += 1

    logger.info(f"[KNOWLEDGE-SEED] Seeded {count} knowledge entries from student course")

    # Also seed into deep memory insights
    try:
        from llm.deep_memory import get_deep_memory
        dm = get_deep_memory()

        # Add key insights as durable insights
        key_insights = [
            ("strategy_insight", "3+ strategy agreement has 2x better win rate than 2-strategy agreement"),
            ("risk_insight", "Never risk more than 1-2% per trade. 5 losses at 2% = 10% drawdown, recoverable"),
            ("regime_insight", "Trending markets favor regime_trend strategy. Ranging markets favor confidence_scorer"),
            ("timing_insight", "Best signals come Tuesday-Thursday. Weekend markets are thin and unreliable"),
            ("execution_insight", "Take 40-50% profit at TP1, move stop to breakeven, let rest ride to TP2"),
            ("symbol_insight", "Meme coins move 2-5x faster than BTC. Use wider stops and lower leverage"),
            ("correlation_insight", "When BTC dumps, alts dump 2-3x harder. Never long alts into a BTC nuke"),
            ("meta_insight", "The best trade is often no trade. Cash has zero drawdown. Patience > action"),
        ]

        for category, insight in key_insights:
            dm.insights.add_insight(
                category=category,
                insight=insight,
                confidence=0.85,
                evidence="Student course foundational knowledge",
                source="student_course",
            )

        logger.info(f"[KNOWLEDGE-SEED] Seeded {len(key_insights)} key insights into deep memory")
    except Exception as e:
        logger.warning(f"[KNOWLEDGE-SEED] Failed to seed deep memory insights: {e}")


def get_course_summary_for_prompt(symbol: str = "", regime: str = "") -> str:
    """Build a compact summary of relevant course knowledge for LLM prompt injection.

    This is called before every LLM decision to remind it of foundational knowledge.
    Filters by relevance to current symbol/regime to stay token-efficient.
    """
    parts = []

    # Always include core axioms (abbreviated)
    core_axioms = [
        "Volume confirms price. No volume = suspect move.",
        "Never risk >2% per trade. Stop loss is sacred.",
        "R:R minimum 1.5:1. Below that, skip.",
        "Never long alts into BTC dump.",
        "Funding extremes precede reversals AND cost money to hold against.",
        "Funding is REAL COST: 0.05% on 5x = 0.75%/day. Factor into every trade.",
        "3+ strategy agreement = highest probability.",
        "Circuit breaker = stop trading, no exceptions.",
        "Improve or die. Every trade counts. Learn from every outcome.",
    ]
    parts.append("CORE RULES: " + " | ".join(core_axioms))

    # Regime-specific knowledge
    if regime:
        regime_lower = regime.lower()
        if "trend" in regime_lower:
            parts.append(
                "REGIME(trend): Trust regime_trend(strong), multi_tier(moderate). "
                "monte_carlo(weak—zones get blown through). Volume + OI expanding confirms. "
                "Size up if cross-market aligns. RSI can stay overbought in trends."
            )
        elif "range" in regime_lower:
            parts.append(
                "REGIME(range): Trust monte_carlo(strong), confidence_scorer(strong). "
                "regime_trend(avoid—false WT crosses), multi_tier(weak—EMA whipsaw). "
                "Fade breakouts, trade mean reversion. Reduce size."
            )
        elif "panic" in regime_lower:
            parts.append(
                "REGIME(panic): EXTREME CAUTION. All strategies=avoid except confidence_scorer(weak). "
                "Only trade 80%+ confidence. Liquidation cascades create overshoots."
            )
        elif "high" in regime_lower and "vol" in regime_lower:
            parts.append(
                "REGIME(high_vol): Cap size at 1.0x. Wider stops (2x ATR). "
                "Trust multi_tier(moderate) for quick scalps, monte_carlo(moderate). "
                "regime_trend(weak). Both directions possible."
            )
        elif "low" in regime_lower and "liq" in regime_lower:
            parts.append(
                "REGIME(low_liq): STAY FLAT. All strategies=avoid. "
                "Thin market, wide spreads, unreliable signals."
            )
        elif "news" in regime_lower or "disloc" in regime_lower:
            parts.append(
                "REGIME(news_dislocation): Wait for dust to settle. "
                "confidence_scorer(moderate—if historical data exists). "
                "All others=avoid or weak. Wide stops, small size if entering."
            )
        elif "unknown" in regime_lower:
            parts.append(
                "REGIME(unknown): No edge identified. Default to SKIP. "
                "confidence_scorer(moderate) only if hist_WR>60%. "
                "All others=weak. Wait for regime clarity."
            )

    # Symbol-specific knowledge
    if symbol:
        sym_upper = symbol.upper()
        if sym_upper in ("DOGE", "PEPE", "FARTCOIN", "WIF", "BONK"):
            parts.append(
                f"SYMBOL({sym_upper}): Meme coin - 2-5x faster moves than BTC. "
                f"Wider stops, lower leverage, expect bigger swings."
            )
        elif sym_upper == "BTC":
            parts.append(
                "SYMBOL(BTC): Market leader. Sets the tone for all alts. "
                "Most liquid, tightest spreads. Key levels at round numbers."
            )
        elif sym_upper in ("ETH", "SOL"):
            parts.append(
                f"SYMBOL({sym_upper}): Large cap alt. Follows BTC direction generally. "
                f"Check BTC direction before trading. Higher beta than BTC."
            )

    return "\n".join(parts)


def get_signal_evaluation_context() -> str:
    """Get the full context needed for evaluating an external signal.

    This is injected when the LLM analyzes incoming Telegram signals.
    More comprehensive than the trading decision context because signal
    evaluation needs the full educational framework.
    """
    return """SIGNAL EVALUATION FRAMEWORK:

When analyzing an external trading signal, follow this checklist:

1. COMPREHENSION: What setup is the signal provider trading? (breakout, reversal, trend continuation, range trade)
2. ENTRY QUALITY: Is the entry at a logical level? (support, resistance, EMA, VWAP)
3. STOP PLACEMENT: Is the stop below/above a logical structure? (swing low, ATR-based, key level)
4. TARGET LOGIC: Are the TPs at logical levels? (next resistance, fibonacci extension, measured move)
5. R:R MATH: Entry-to-SL distance vs Entry-to-TP1 distance. Must be >= 1.5:1.
6. REGIME FIT: Does the trade direction match the current market regime?
7. CROSS-MARKET: Does BTC support this direction? Any conflicting signals?
8. TIMING: Is this signal timely or stale? Has price already moved past the entry?
9. SOURCE QUALITY: How reliable is this signal source historically?
10. ENSEMBLE CHECK: Would our internal strategies agree with this signal?

VERDICT CRITERIA:
- TAKE: R:R >= 1.5:1, regime aligns, cross-market confirms, entry at logical level
- SKIP: R:R < 1.5:1, regime conflicts, or signal is stale/vague
- MODIFY: Direction correct but entry/SL/TP can be improved"""
