---
title: Reputation spec — ATR-REP-01
type: component
status: planned
percent: 10
layer: L5-reputation
priority: P1
depends_on: ["[[../layers/L1-identity]]"]
---

# ATR-REP-01 — Reputation Protocol

How trust gets attached to an Ed25519 identity over time, **computed locally**, **not stored centrally**.

## Inputs to local reputation calculation

| Source | Weight | Decay |
|---|---|---|
| Quest receipts received | + | 6 months |
| Quest disputes filed (won) | ++ | 12 months |
| Quest disputes filed (lost) | − | 12 months |
| Constitutional violations | −− | 24 months |
| Endorsements signed by trusted peers | + | 12 months |
| Time present in the network | + | none |

## Output

Not a single score. A **reputation card**:

```
clan: jei
identity: b05d85e5...
member since: 2026-03-18
quests completed: 47
quests disputed: 0
constitutional violations: 0
endorsed by: 3 trusted clans (momoshod, tinkuy-collective, ...)
last seen: 2 hours ago
```

## Trust transitivity

Each clan defines a **trust function**: how the reputation of clan X seen through clan Y propagates. Default: simple weighted average among clans you already trust, capped at 1 hop.

This is *not* PageRank. PageRank centralizes; Amaru reputation is local.

## Privacy

A clan can opt to **publish** part of its reputation card (member-since, quest-count) and **withhold** the rest (specific quests). Default = withhold everything; explicit publish to make visible.

## Why not blockchain

- No global state needed (each clan computes its own view)
- Bus signatures already provide auditability
- Avoids energy and complexity
- Stays sovereign

## Status

**Pre-draft**. Sketch exists in this file. Awaiting first real conflict in the network to validate priorities.

## Links

- [[../00-VISION]]
- [[../layers/L5-reputation]]
- [[../layers/L4-governance]]
- [[../layers/L1-identity]]
