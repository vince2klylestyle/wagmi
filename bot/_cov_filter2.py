"""Temp: hot-path low coverage."""
import json

with open('coverage.json') as f:
    data = json.load(f)

files = data['files']
candidates = []
for path, info in files.items():
    stmts = info['summary']['num_statements']
    pct = info['summary']['percent_covered']
    missing = info['summary']['missing_lines']
    if stmts < 100 or pct >= 50:
        continue
    p = path.replace('\\', '/')
    if not any(p.startswith(d) for d in ('llm/', 'feedback/', 'alerts/',
                                         'core/', 'wallet/', 'execution/')):
        continue
    dead = ['quant_brain', 'metrics', 'plots', 'knowledge_roadmap',
            'bot_perception', 'learning_integrator', 'active_learning',
            'comprehensive_snapshot', 'quant_engine', 'decision_ledger',
            'auto_optimizer', 'measurement_sprint', 'mechanical_',
            'llm/analyze', 'signal_validator', 'async_agent_teams']
    if any(d in p for d in dead):
        continue
    candidates.append((path, stmts, pct, missing))

candidates.sort(key=lambda r: -r[1])
for path, stmts, pct, missing in candidates[:25]:
    print(f'{pct:5.1f}%  {stmts:5d} LOC  {path}')
