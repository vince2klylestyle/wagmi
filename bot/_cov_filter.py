"""Temp: analyze coverage.json to find hot-path modules needing tests."""
import json

with open('coverage.json') as f:
    data = json.load(f)

files = data['files']
rows = []
for path, info in files.items():
    stmts = info['summary']['num_statements']
    pct = info['summary']['percent_covered']
    missing = info['summary']['missing_lines']
    rows.append((path, stmts, pct, missing))

# Exclusions: one-off scripts, backtest drivers, social/manual tools, CLI,
# top-level entrypoints, dead/deprecated per prior audits.
exclusion_subs = [
    'manual' + '\\',
    'social' + '\\',
    'backtest' + '\\',
    'analyze_backtest',
    'deep_analysis',
    'best_1_6_16',
    'run.py',
    'bot.py',
    'cli.py',
    'tests' + '\\',
    'llm\\plots',
    'llm\\metrics',   # reporting
    'llm\\analyze',
    'llm\\knowledge_roadmap',  # flagged dead
    'llm\\bot_perception_analyzer',  # research tool
    'llm\\learning_integrator',  # replaced by agents/learning_integration
    'agents\\active_learning',  # advisory only per notes
    'agents\\comprehensive_snapshot',  # unused prototype
    'agents\\quant_engine',
    'agents\\decision_ledger',
    'quant_brain',  # superseded
    'auto_optimizer',
    'watchdog.py',  # script
    'tools\\',  # script-ish
    'validation\\',  # already-known gaps
]

low = [r for r in rows if r[1] > 100 and r[2] < 50
       and not any(x in r[0] for x in exclusion_subs)]
low.sort(key=lambda r: (r[2], -r[1]))

print(f'Hot-path modules <50% and >100 LOC: {len(low)}')
print()
for path, stmts, pct, missing in low[:30]:
    print(f'{pct:5.1f}%  {stmts:5d} LOC  {missing:5d} missing  {path}')
