# LLM Agent Specification — Derived from 2,172 Signals

## What the LLM needs to do on every signal evaluation

### INPUT: Raw signal + market context
The LLM receives: symbol, side, confidence, entry, sl, tp1, strategies_agree,
regime, chop_score, ev, win_prob, funding_rate, volume, BTC trend, time of day,
recent win/loss streak, open positions, portfolio exposure.

### DECISION TREE (from 18 findings)

```
1. Is bollinger_squeeze involved?
   YES → Go to step 2
   NO  → Are other strategies > 2-agree? 
         YES with strong setup → proceed at 0.4x size
         NO → SKIP (all non-BB strategies lose money)

2. Is this a golden setup?
   ETH_SELL_BB → GO, 1.3x size (70% WR)
   BTC_BUY_BB  → GO, 1.2x size (69% WR)  
   SOL_BUY_BB  → GO, 1.2x size (67% WR)
   BTC_SELL_BB → GO, 1.0x size (61% WR)
   ETH_BUY_BB  → GO, 0.8x size (59% WR)
   
3. Is this a dead setup?
   HYPE_SELL_BB → SKIP (35% WR)
   BB + MTQ agree → SKIP or 0.5x (35% WR — MTQ is contra-indicator)

4. Is BB solo (no other strategy)?
   YES → Size UP to 1.3x (67.6% WR — strongest pattern)
   NO (BB + CS) → 1.0x (57% WR)
   NO (BB + MTQ) → REDUCE to 0.5x (35% WR)

5. Regime check:
   high_volatility → +20% size (62% WR for BB)
   trend → neutral (52% WR)
   range → slight boost (58% WR for BB)
   
6. Momentum check:
   After 2 consecutive wins → +30% size (75% WR)
   After 1 win → +20% size (67% WR)
   After 1 loss → -50% size (34% WR)
   After 2 losses → SKIP or -70% size (29% WR)

7. Early exit rule (for Exit Agent):
   Check at 1h: if losing, 67% chance stays losing
   BUT: BB losers recover 56% — hold BB losers to 4h before cutting
   Non-BB losers: cut at 1h (only 45% recovery rate)
   Winners at 1h: HOLD — 73% continue winning (for BB)

8. Hold time (for Exit Agent):
   Peak MFE at 8-12h (34% of peak moves)
   Don't cut winners before 8h unless thesis invalidated
   ETH_SELL_BB: peaks at 4-8h, take profit by 12h
   BTC_BUY_BB: needs 4h+ to develop, hold to 8h
   SOL_BUY_BB: decays after 4h, take profit by 8h
```

### SIZE CALCULATION
```
base_size = risk_per_trade (8% of equity)

adjustments:
  × golden_setup_mult (0.8 - 1.3 per setup table)
  × solo_bb_mult (1.3 if solo BB, 1.0 if BB+CS, 0.5 if BB+MTQ)
  × regime_mult (1.2 for high_vol, 0.9 for trend)
  × momentum_mult (1.3 after 2 wins, 0.3 after 2 losses)
  × vol_target_mult (inversely proportional to ATR)

final_size = max(min_notional, min(base_size × all_mults, max_notional))
```

### WHAT THE LLM ADDS BEYOND RULES
1. **Novel pattern recognition** — the rules cover known setups, but markets create
   new patterns. The LLM can spot "this looks like X but with Y different"
2. **Context synthesis** — funding rate + volume surge + BTC movement combined.
   Rules can't weight 20 factors simultaneously. LLM can.
3. **Thesis formation** — "BTC is breaking out of consolidation with volume confirm,
   ETH will follow in 2-4h" — this kind of reasoning is pure LLM territory.
4. **Dynamic TP/SL** — "this setup usually moves 0.8% but conditions suggest 1.5%"
   Based on vol regime, time of day, recent moves.
5. **Memory** — "last time BTC did this at this funding rate, it reversed at $X"
   Accumulates market knowledge over time.

### COST: $0.03 per signal evaluation, ~$0.38/day for all 4 symbols
