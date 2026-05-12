---
title: L6 — Marketplace
type: layer
status: planned
percent: 0
depends_on: ["[[L2-network]]", "[[L5-reputation]]"]
---

# L6 — Marketplace

The **bolsa de trabajo** — quests, services, missions. Where humans offer skills, agents offer capabilities, and clans coordinate around real work.

## Components

| Component | Spec target | Status | Notes |
|---|---|---|---|
| [[../components/quest-board]] | extends ARC-2314 | planned 🔵 | the public quest stream |
| Publish quest (open) | — | planned 🔵 | bus event `quest_open` |
| Bid on quest | — | planned 🔵 | new wire type |
| Award + escrow (symbolic) | — | planned 🔵 | reputation-backed, no money |
| Receipt of completion | ATR-Q.931 §8 | live | already exists |
| Search / filter | — | planned 🔵 | over Agora + bus history |

## Why "symbolic escrow"

Amaru does not handle real money. Money brings:
- Legal complexity per jurisdiction
- Payment processors as central points of failure
- Tax overhead that breaks individual users

Symbolic escrow uses **reputation as collateral**: bidding lowers your visible trust if you abandon. Money exchanges happen **outside** the protocol (Wise, bank transfer, cash) and the protocol only records the agreement.

## Vision in practice

```
$ amaru quest browse
  [Q-2026-05-12-001] cooking-translator wanted
    Offered by: jei clan
    Reputation: trusted-2
    Reward: signed thank-you + visibility
    Deadline: 2026-05-14

  [Q-2026-05-12-002] python-tutor for beginner
    Offered by: tinkuy-collective
    Reputation: new-1
    Reward: reciprocity barter (offers: graphic design)
    Deadline: open

$ amaru quest accept Q-2026-05-12-001
```

This is the **product** people will see. Everything else is plumbing.

## Inspirations

- Upwork (without the platform tax)
- IRC `#freenode` channels (where people just asked and others helped)
- World of Warcraft trade chat
- Latin-American **mingas** and **tequios** (collective work tradition)

## Links

- [[00-VISION]]
- [[L2-network]]
- [[L5-reputation]]
- [[../components/quest-board]]
- [[../principles/abya-yala]]
- [[../PROGRESS]]
