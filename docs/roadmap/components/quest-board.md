---
title: Public Quest Board — extends ARC-2314
type: component
status: planned
percent: 0
layer: L6-marketplace
priority: P2
depends_on: ["[[../layers/L2-network]]", "[[../layers/L5-reputation]]"]
---

# Public Quest Board

Extends [Dojo (ARC-2314)](../../../spec/) from 1-to-1 quest dispatch into a public publish/subscribe board.

## What changes

Today:
```
amaru send <target_clan> "<quest description>" --type dispatch
```
A point-to-point quest.

Tomorrow:
```
amaru quest publish "cooking-translator wanted" --reward "signed thank-you" --deadline 2d
amaru quest browse  # any clan can see open quests
amaru quest bid <quest-id> "I can do this in 4h, my Spanish is C2"
amaru quest award <quest-id> <bidder-clan>
```

## Required wire types (extensions to ARC-5322)

| Type | Description |
|---|---|
| `quest_open` | new public quest |
| `quest_bid` | proposal to fulfill |
| `quest_award` | accept a bid |
| `quest_deliver` | submit work |
| `quest_receipt` | confirm completion |
| `quest_dispute` | open arbitration |

## Discovery

Public quests are broadcast on the bus with `dst: "*"`. Clans that want to see the global board subscribe via `amaru quest browse`, which:
- Pulls from local hub's bus
- Filters for `quest_open` types
- Joins with reputation data ([[../layers/L5-reputation]])

## Dependency on reputation

Without trust signals, bidding is unsafe (anyone can claim anything). Quest board cannot ship before [[../layers/L5-reputation]] reaches at least basic aggregation.

## Inspiration

- WoW Trade Chat (instant, transient)
- Upwork (long-form, but platform-taxed)
- **Mingas** and **tequios** (Latin-American collective work) — reciprocity-based, no money required
- IRC channels (where helpers gathered organically)

## Links

- [[../00-VISION]]
- [[../layers/L6-marketplace]]
- [[../layers/L5-reputation]]
- [[../principles/abya-yala]]
