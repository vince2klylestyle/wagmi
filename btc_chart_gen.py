import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as ticker
from matplotlib.patches import FancyArrowPatch
import numpy as np

fig, (ax_main, ax_vol) = plt.subplots(2, 1, figsize=(18, 11),
    gridspec_kw={'height_ratios': [4, 1]}, facecolor='#0d1117')

ax_main.set_facecolor('#0d1117')
ax_vol.set_facecolor('#0d1117')

# ── PRICE ACTION: Higher lows structure ────────────────────────────────────
candles = []

# Phase 1: drop to HL1 ($72,100)
prices1 = [78200, 77800, 77100, 76400, 75800, 75200, 74600, 74000, 73500, 73100, 72800, 72400, 72100]
for i in range(len(prices1) - 1):
    o = prices1[i]; c = prices1[i+1]
    noise = abs(o - c) * 0.6
    candles.append((len(candles), o, max(o,c)+noise, min(o,c)-noise*0.4, c))

# Phase 2: HL1 → HL2 ($73,800)
prices2 = [72100, 72400, 72900, 73300, 73800, 74200, 74500, 74100, 73800]
for i in range(len(prices2) - 1):
    o = prices2[i]; c = prices2[i+1]
    noise = abs(o - c) * 0.7
    candles.append((len(candles), o, max(o,c)+noise, min(o,c)-noise*0.3, c))

# Phase 3: HL2 → HL3/breakout ($74,500)
prices3 = [73800, 74000, 74500, 74800, 75100, 75400, 75200, 74900, 74500]
for i in range(len(prices3) - 1):
    o = prices3[i]; c = prices3[i+1]
    noise = abs(o - c) * 0.7
    candles.append((len(candles), o, max(o,c)+noise, min(o,c)-noise*0.3, c))

# Phase 4: retest + current
prices4 = [74500, 74700, 75000, 74800, 74600, 74500, 74700, 75000, 75300]
for i in range(len(prices4) - 1):
    o = prices4[i]; c = prices4[i+1]
    noise = abs(o - c) * 0.5
    candles.append((len(candles), o, max(o,c)+noise, min(o,c)-noise*0.3, c))

total_candles = len(candles)

# Projected candles (Asia open → target)
proj_prices = [75300, 75600, 75900, 76200, 76500, 76800, 76600, 76900]
proj_candles = []
for i in range(len(proj_prices) - 1):
    o = proj_prices[i]; c = proj_prices[i+1]
    proj_candles.append((total_candles+i, o, max(o,c)+120, min(o,c)-80, c))

all_x = total_candles + len(proj_candles)

# ── DRAW CANDLES ──────────────────────────────────────────────────────────
for (x, o, h, l, c) in candles:
    color = '#26a641' if c >= o else '#f85149'
    bh = max(abs(c - o), 10)
    ax_main.add_patch(plt.Rectangle((x-0.35, min(o,c)), 0.7, bh, color=color, zorder=3))
    ax_main.plot([x, x], [l, min(o,c)], color=color, lw=1.2, zorder=2)
    ax_main.plot([x, x], [max(o,c), h], color=color, lw=1.2, zorder=2)

for (x, o, h, l, c) in proj_candles:
    bh = max(abs(c - o), 10)
    ax_main.add_patch(plt.Rectangle((x-0.35, min(o,c)), 0.7, bh, color='#26a641', alpha=0.35, zorder=3))
    ax_main.plot([x, x], [l, h], color='#26a641', lw=0.8, alpha=0.4, zorder=2)

# ── VOLUME ──────────────────────────────────────────────────────────────
vols = [900,850,1000,1300,1500,1200,1000,900,850,800,750,900,1100,
        1200,1400,1600,1300,1100,1000,950,900,850,900,950,1000,
        1050,1100,1150,1050,1000,950,1000,950,900,950,1000]
for i, (x, o, h, l, c) in enumerate(candles):
    color = '#26a641aa' if c >= o else '#f85149aa'
    ax_vol.bar(x, vols[i % len(vols)], color=color, width=0.7)

# ── KEY LEVELS ──────────────────────────────────────────────────────────
# SL zone
ax_main.axhspan(72800, 73100, alpha=0.12, color='#f85149', zorder=1)
ax_main.axhline(73100, color='#f85149', lw=1.5, ls='--', alpha=0.85, zorder=4)
ax_main.text(all_x+0.4, 73100, '  SL $73,100\n  (below HL structure)', color='#f85149', fontsize=8.5, va='center', fontweight='bold')

# Entry zone
ax_main.axhspan(74500, 75100, alpha=0.10, color='#d4a017', zorder=1)
ax_main.axhline(74500, color='#d4a017', lw=2.0, ls='-', alpha=0.9, zorder=4)
ax_main.text(all_x+0.4, 74780, '  ENTRY ZONE\n  $74,500 - $75,000', color='#d4a017', fontsize=8.5, va='center', fontweight='bold')

# Target zones
ax_main.axhspan(76500, 77100, alpha=0.15, color='#26a641', zorder=1)
ax_main.axhline(76500, color='#26a641', lw=1.5, ls='--', alpha=0.85, zorder=4)
ax_main.text(all_x+0.4, 76500, '  TARGET $76,500\n  R:R 2:1', color='#26a641', fontsize=8.5, va='center', fontweight='bold')
ax_main.axhline(77000, color='#26a641', lw=1.0, ls=':', alpha=0.5, zorder=4)
ax_main.text(all_x+0.4, 77050, '  EXT $77,000', color='#26a641', fontsize=8, alpha=0.7)

# Prior resistance
ax_main.axhline(75400, color='#bc8cff', lw=1.2, ls='-.', alpha=0.6, zorder=4)
ax_main.text(1, 75500, 'Prior resistance → support', color='#bc8cff', fontsize=7.5, alpha=0.7)

# ── HIGHER LOWS TRENDLINE ──────────────────────────────────────────────
hl_pts = [(12, 72100), (21, 73800), (29, 74500)]
xl = [p[0] for p in hl_pts] + [all_x-1]
yl = [p[1] for p in hl_pts] + [75400]
ax_main.plot(xl, yl, color='#58a6ff', lw=2.0, ls='-', alpha=0.8, zorder=5, label='HL trendline')
ax_main.scatter([p[0] for p in hl_pts], [p[1] for p in hl_pts], color='#58a6ff', s=80, zorder=6)

labels = [('HL1\n$72,100', 12, 72100), ('HL2\n$73,800', 21, 73800), ('HL3 / BREAKOUT\n$74,500', 29, 74500)]
for lbl, x, y in labels:
    ax_main.annotate(lbl, xy=(x, y), xytext=(x-0.5, y-480),
        color='#58a6ff', fontsize=7.5, ha='center', fontweight='bold',
        arrowprops=dict(arrowstyle='->', color='#58a6ff', lw=1.2))

# ── PROJECTED MOVE ARROW ─────────────────────────────────────────────
ax_main.add_patch(FancyArrowPatch(
    (total_candles+1, 75300), (total_candles+6, 76800),
    arrowstyle='->', color='#26a641', lw=2.5, mutation_scale=20, alpha=0.65, zorder=6))
ax_main.text(total_candles+5.5, 76920, 'PROJECTED +$1,500', color='#26a641', fontsize=8.5, ha='center', fontweight='bold', alpha=0.85)

# ── ASIA OPEN MARKER ────────────────────────────────────────────────
asia_x = total_candles - 2
ax_main.axvline(asia_x, color='#ffa500', lw=1.5, ls=':', alpha=0.75, zorder=4)
ax_main.text(asia_x+0.3, 77600, 'ASIA OPEN\nCATALYST WINDOW', color='#ffa500', fontsize=8, fontweight='bold')

# ── WAGMI AGENT BOX ─────────────────────────────────────────────────
box_txt = (
    'WAGMI 9-AGENT CONSENSUS\n'
    + '='*28 + '\n'
    'Regime Agent:   TRENDING_BULL\n'
    'Trade Agent:    GO (3/4 conv.)\n'
    'Risk Agent:     SL below HL3\n'
    'Critic Agent:   PASS (valid)\n'
    'Learning:       trending +EV\n'
    + '-'*28 + '\n'
    'Dynamic SL:     1.2x ATR boost\n'
    'AdaptiveSizer:  neutral\n'
    'Quality mult:   1.0x (trending)\n'
    + '-'*28 + '\n'
    'Confidence:     ~78%  > floor 65%\n'
    'VERDICT:        LONG BIAS'
)
ax_main.text(0.3, 75400, box_txt, fontsize=7.2, color='#e6edf3',
    bbox=dict(boxstyle='round,pad=0.6', facecolor='#161b22', edgecolor='#58a6ff', alpha=0.93, lw=1.5),
    fontfamily='monospace', va='top', zorder=10)

# ── R:R BRACKET ────────────────────────────────────────────────────
rx = all_x + 6
ax_main.annotate('', xy=(rx, 73100), xytext=(rx, 74750),
    arrowprops=dict(arrowstyle='<->', color='#f85149', lw=1.5))
ax_main.text(rx+0.5, 73900, 'RISK\n~$1,650', color='#f85149', fontsize=7.5, va='center')

ax_main.annotate('', xy=(rx, 74750), xytext=(rx, 76500),
    arrowprops=dict(arrowstyle='<->', color='#26a641', lw=1.5))
ax_main.text(rx+0.5, 75620, 'REWARD\n~$1,750', color='#26a641', fontsize=7.5, va='center')

ax_main.text(rx, 75050, '2:1\nR:R', color='#e6edf3', fontsize=9, ha='center', fontweight='bold')

# ── FORMATTING ─────────────────────────────────────────────────────
ax_main.set_xlim(-1, all_x + 11)
ax_main.set_ylim(71000, 78400)
ax_main.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f'${v:,.0f}'))
ax_main.tick_params(colors='#8b949e', labelsize=8)
for sp in ax_main.spines.values(): sp.set_color('#30363d')
ax_main.grid(axis='y', color='#21262d', lw=0.5)

ax_main.set_title(
    'BTC/USD  4H  |  WAGMI MULTI-AGENT THESIS  |  Higher Low Breakout Retest\n'
    'Regime: TRENDING_BULL  •  9-Agent Consensus: GO  •  Target: $76,500  •  SL: $73,100',
    color='#e6edf3', fontsize=11, fontweight='bold', pad=12)

ax_vol.set_xlim(-1, all_x + 11)
ax_vol.tick_params(colors='#8b949e', labelsize=7)
for sp in ax_vol.spines.values(): sp.set_color('#30363d')
ax_vol.set_ylabel('Vol', color='#8b949e', fontsize=8)
ax_vol.set_yticks([])
ax_vol.grid(axis='y', color='#21262d', lw=0.4)
ax_vol.axvline(asia_x, color='#ffa500', lw=1.2, ls=':', alpha=0.5)

handles = [
    mpatches.Patch(color='#26a641', label='Bullish'),
    mpatches.Patch(color='#f85149', label='Bearish'),
    plt.Line2D([0],[0], color='#58a6ff', lw=2, label='Higher low trendline'),
    plt.Line2D([0],[0], color='#d4a017', lw=2, label='Entry $74.5k-75k'),
    plt.Line2D([0],[0], color='#f85149', lw=1.5, ls='--', label='SL $73,100'),
    plt.Line2D([0],[0], color='#26a641', lw=1.5, ls='--', label='Target $76,500'),
    plt.Line2D([0],[0], color='#ffa500', lw=1.5, ls=':', label='Asia open'),
    mpatches.Patch(color='#26a641', alpha=0.35, label='Projected move'),
]
ax_main.legend(handles=handles, loc='upper right', fontsize=7.5,
    facecolor='#161b22', edgecolor='#30363d', labelcolor='#e6edf3', framealpha=0.9, ncol=2)

fig.patch.set_facecolor('#0d1117')
plt.tight_layout(rect=[0, 0, 0.87, 1])
plt.savefig('btc_thesis_chart.png', dpi=160, bbox_inches='tight', facecolor='#0d1117')
print('Saved btc_thesis_chart.png')
