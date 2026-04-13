"""30-second status dashboard. Run: python tools/quick_status.py"""
import csv, json, os, sys
from datetime import datetime, timezone
from pathlib import Path

os.chdir(Path(__file__).parent.parent)

# Equity + CB state
try:
    cb = json.load(open("data/circuit_breaker_state.json"))
    print(f"Equity:      ${cb.get('peak_equity', 0) + cb.get('daily_pnl', 0):.2f}")
    print(f"Daily PnL:   ${cb.get('daily_pnl', 0):+.2f}")
    print(f"CB tripped:  {'YES' if cb.get('tripped') else 'no'}")
    print(f"Consec loss: {cb.get('consecutive_losses', 0)}")
    print(f"Last saved:  {cb.get('saved_at', '?')[:19]}")
except: print("CB state unavailable")

print()

# Trade count
try:
    trades = list(csv.DictReader(open("data/trade_ledger.csv")))
    print(f"Total trades: {len(trades)}")
    wins = sum(1 for t in trades if float(t.get('net_pnl', 0)) > 0)
    print(f"Lifetime WR:  {wins/len(trades)*100:.1f}%")
    total_pnl = sum(float(t.get('net_pnl', 0)) for t in trades)
    print(f"Lifetime PnL: ${total_pnl:+.2f}")
    
    # Last 5 trades
    print(f"\nLast 5 trades:")
    for t in trades[-5:]:
        sym = t['symbol']
        pnl = float(t.get('net_pnl', 0))
        w = 'W' if pnl > 0 else 'L'
        print(f"  {w} {sym:5s} ${pnl:+.2f}")
except: print("Trade ledger unavailable")

print()

# LLM status
try:
    cost = json.load(open("data/llm/cost_tracker.json"))
    print(f"LLM calls today: {cost.get('calls', 0)}")
    print(f"LLM spend today: ${cost.get('spend', 0):.2f}")
except: print("LLM: offline (no credits)")

print()
print("Bot: check if python.exe is running in task manager")
