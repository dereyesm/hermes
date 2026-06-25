---
title: L5 — Reputation
type: layer
status: planned
percent: 10
depends_on: ["[[L1-identity]]", "[[L4-governance]]"]
---

# L5 — Reputation

Trust accumulated over time, visible across the network, **not** held by any central scorer.

## Components

| Component | Spec target | Status | Notes |
|---|---|---|---|
| [[../components/reputation]] | ATR-REP-01 *(to draft)* | planned 🔵 | core spec |
| Quest receipts as proof | ATR-Q.931 §8 | live (30%) | receipts exist; aggregation doesn't |
| Signed ratings | — | planned 🔵 | new wire type |
| Weighted history | — | planned 🔵 | client-side aggregation |
| Constitutional violations as negative | — | planned 🔵 | bound to [[L4-governance]] |
| Decay function | — | planned 🔵 | old quests count less |

## Design constraints

- **No blockchain**. Bus + signed receipts + local aggregation is sufficient and respects sovereignty.
- **Computed locally**. Each clan computes the reputation of others from the messages it has received. No global ranking.
- **Disputable**. Bad receipts can be appealed via Dojo.
- **Pseudonymous-friendly**. Reputation attaches to an Ed25519 key, which a human can choose to associate with their real name or not.

## What it enables

- The marketplace ([[L6-marketplace]]) can show "trust level" to bidders
- The constitution ([[L4-governance]]) can have proportional consequences
- New clans can bootstrap from invitations by trusted ones

## Risk

Reputation systems are **easily weaponized**. The constitution must include explicit protections:
- No mob-piling (single grievance ≠ reputation collapse)
- Appeals must be possible
- Reputation is visible, not score-driven (qualitative > quantitative)

## Links

- [[00-VISION]]
- [[L1-identity]]
- [[L4-governance]]
- [[L6-marketplace]]
- [[../PROGRESS]]
