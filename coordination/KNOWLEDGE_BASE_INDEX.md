# Knowledge Base Index
**Quick reference for Nunu, Laptop Claude, Desktop Claude**

For any question, find it below, then read the linked document.

---

## QUICK ANSWERS (Most Common Questions)

### "Why aren't we trading?"
**Answer**: Market is in consolidation (no edge). Waiting for trending_bear or trending_bull regime.
- **Full explanation**: `TRADING_SYSTEM_WALKTHROUGH.md` Part 4-5
- **Check current status**: Ask desktop Claude for latest logs

### "What's our win rate?"
**Answer**: Monday-Tuesday: 67-70% (BB solo strategy). Current: TBD (waiting for trending regime).
- **Full data**: `coordination/INBOX_DESKTOP_TO_LAPTOP.md` (search for "win rate")
- **Mon-Tue breakdown**: `TRADING_SYSTEM_WALKTHROUGH.md` Part 6

### "What leverage did we use Monday-Tuesday?"
**Answer**: 1.5-2.0x (not 25x max, not 0.15x dampened).
- **Details**: `TRADING_SYSTEM_WALKTHROUGH.md` Part 5, "Sizing Formula"

### "How do signals flow through the bot?"
**Answer**: Strategies generate → Regime Agent decides regime → Trade Agent decides go/skip → Risk Agent sizes → Critic Agent approves.
- **Full pipeline**: `TRADING_SYSTEM_WALKTHROUGH.md` Part 3

### "Why is Kelly dampened to 0.15x?"
**Answer**: Adaptive risk dampening after loss streak. Will recover organically as new wins accumulate.
- **Details**: `coordination/INBOX_DESKTOP_TO_LAPTOP.md` (search "Kelly dampening")

### "What's wrong with the current setup vs Monday-Tuesday?"
**Answer**: Nothing wrong (system is clean). Market conditions changed (consolidation vs trending). Config is correct.
- **Comparison table**: `TRADING_SYSTEM_WALKTHROUGH.md` Part 5

### "How do we replicate Monday-Tuesday?"
**Answer**: Wait for trending_bear/bull regime + 80%+ confidence + multiple strategies agreeing.
- **Checklist**: `TRADING_SYSTEM_WALKTHROUGH.md` Part 6

---

## TOPIC LOOKUP

### System Architecture & How Things Work
| Question | Document | Section |
|---|---|---|
| How does the multi-agent pipeline work? | TRADING_SYSTEM_WALKTHROUGH.md | Part 3 |
| What are the 4 strategies? | TRADING_SYSTEM_WALKTHROUGH.md | Part 2 |
| How is a signal generated? | TRADING_SYSTEM_WALKTHROUGH.md | Part 2 |
| How is leverage determined? | TRADING_SYSTEM_WALKTHROUGH.md | Part 5 |
| What data does the bot read? | TRADING_SYSTEM_WALKTHROUGH.md | Part 1 |

### Monday-Tuesday Performance & Replication
| Question | Document | Section |
|---|---|---|
| Which trades won on Monday-Tuesday? | TRADING_SYSTEM_WALKTHROUGH.md | Part 2 |
| Why did those trades work? | TRADING_SYSTEM_WALKTHROUGH.md | Part 4 |
| How do we replicate the winning approach? | TRADING_SYSTEM_WALKTHROUGH.md | Part 6 |
| What was the exact leverage used? | TRADING_SYSTEM_WALKTHROUGH.md | Part 5 |
| What regime were we in? | TRADING_SYSTEM_WALKTHROUGH.md | Part 4 |

### Current State & Issues
| Question | Document | Section |
|---|---|---|
| Why haven't we traded yet? | TRADING_SYSTEM_WALKTHROUGH.md | Part 5 |
| What's the current market regime? | INBOX_DESKTOP_TO_LAPTOP.md | Latest message |
| Is the system broken? | INBOX_DESKTOP_TO_LAPTOP.md | 00:25 UTC message |
| What cleanups were done? | INBOX_DESKTOP_TO_LAPTOP.md | 23:42 UTC message |
| What's the equity situation? | INBOX_DESKTOP_TO_LAPTOP.md | 00:25 UTC message |

### Autonomous Monitoring & Coordination
| Question | Document | Section |
|---|---|---|
| How does laptop monitor the bot? | LAPTOP_AUTONOMOUS_LOOP.md | Full doc |
| What is the coordination protocol? | COMMS_PROTOCOL.md | Full doc |
| How do Laptop & Desktop Claude communicate? | handshake.md | Full log |
| What's the status of each cycle? | INBOX_*.md | Latest entries |

### Configuration & Settings
| Question | Document |
|---|---|
| What's the current LLM_MODE? | bot/.env or INBOX_DESKTOP_TO_LAPTOP.md (00:25 UTC) |
| What's MAX_LEVERAGE? | bot/.env or INBOX_DESKTOP_TO_LAPTOP.md |
| Is ENSEMBLE_MODE solo or weighted_veto? | INBOX_DESKTOP_TO_LAPTOP.md (00:25 UTC) |
| What's the confidence floor? | bot/.env or TRADING_SYSTEM_WALKTHROUGH.md |

---

## HOW TO USE THIS

### For Nunu (asking questions):
1. **Find your question** in the Quick Answers or Topic Lookup above
2. **Go to the linked document**
3. **Read the section** — it has the full explanation
4. **If you want more details**: Ask me (Laptop Claude) or desktop Claude specific follow-up questions

### For Laptop Claude (me):
- When Nunu asks a question, reference this index
- Keep this index updated as we add new docs
- Answer with "See KNOWLEDGE_BASE_INDEX.md — [question] → [document] → [section]"

### For Desktop Claude:
- Read the coordination inbox for async messages
- Check this index if you need to understand Laptop's analysis
- Update the index if you add new documentation

### For Both Claudes:
- Keep documents updated (when something changes, update the relevant doc + index)
- Link to specific sections (not just files)
- Use markdown headers consistently so sections are findable

---

## DOCUMENT MAP

| Document | Purpose | Owner | Updated |
|---|---|---|---|
| TRADING_SYSTEM_WALKTHROUGH.md | Complete system explanation for Nunu | Laptop | 2026-06-07 02:45 |
| LAPTOP_AUTONOMOUS_LOOP.md | How laptop monitors every 60 min | Laptop | 2026-06-06 23:30 |
| COMMS_PROTOCOL.md | How Laptop/Desktop communicate | Desktop | 2026-05-30 |
| handshake.md | Detailed async discussion log | Both | Ongoing |
| INBOX_LAPTOP_TO_DESKTOP.md | Laptop's messages to Desktop | Laptop | Ongoing |
| INBOX_DESKTOP_TO_LAPTOP.md | Desktop's messages to Laptop | Desktop | Ongoing |
| bot/.env | Current bot configuration | Desktop | Ongoing |
| bot/data/kelly_weights.json | Sizing dampening & recovery | Bot | Auto-updated |
| bot/data/risk_equity_state.json | Equity tracking | Bot | Auto-updated |

---

## ADDING NEW INFORMATION

When something new should be documented:

1. **Quick fix** (< 5 min): Update TRADING_SYSTEM_WALKTHROUGH.md Part X
2. **Discussion** (async): Add to INBOX_LAPTOP_TO_DESKTOP.md or INBOX_DESKTOP_TO_LAPTOP.md
3. **New topic** (major): Create new .md file + add to this index
4. **Update index**: Always update this file when documents change

---

## HOW TO ANSWER QUESTIONS GOING FORWARD

**Template for any Claude answering Nunu:**

```
Q: [Nunu's question]

A: [Quick 1-sentence answer]

**See**: KNOWLEDGE_BASE_INDEX.md → "[Your Question]" → [Document] → [Section]

**Details**: [1-2 paragraphs from the document if needed]
```

**Example:**

```
Q: Why aren't we trading?

A: Market is in consolidation (no edge). Waiting for trending regime.

**See**: KNOWLEDGE_BASE_INDEX.md → "Why aren't we trading?" → TRADING_SYSTEM_WALKTHROUGH.md → Part 5

**Details**: The bot generates signals correctly, but the LLM correctly skips them because consolidation has no statistical edge. Monday-Tuesday worked because we had trending_bear regime (clear downtrend). When the market trends again, the bot will execute at 1.5-2.0x leverage with high confidence setups.
```

---

**Status**: This index is now the master reference. Keep it current, and any Claude can instantly answer questions with full context.
