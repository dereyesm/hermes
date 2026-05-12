---
title: L4 — Governance
type: layer
status: planned
percent: 0
depends_on: ["[[L1-identity]]"]
---

# L4 — Governance

The constitution made into protocol. Rights, duties, sanctions, appeal — all encoded.

## Components

| Component | Spec target | Status | Owner |
|---|---|---|---|
| [[../components/constitution]] | ATR-CONST-01 *(to draft)* | planned 🔵 | Consejo Ampliado |
| Constitutional validator | — | planned 🔵 | Daniel + Hannah |
| Adhesion signature file | — | planned 🔵 | each clan |
| Bus event vocabulary for violations | — | planned 🔵 | extends ARC-5322 |
| Appeal protocol | — | planned 🔵 | extends ARC-2314 (Dojo) |
| Sanction mechanism | — | planned 🔵 | bound to [[L5-reputation]] |

## The path

Per [[../principles/constitution]], the recommended path is **hybrid**:
- Voluntary adhesion (each clan signs)
- Visible violations (logged to bus)
- Reputation consequence (not block)
- Right to appeal preserved

## Open questions

- Who can amend the constitution after v1?
- What is the quorum of clans needed to ratify a change?
- Can a clan be "expelled" from the network, or only marked as non-conforming?
- How are conflicts between two clans' internal rules resolved when they federate?

These need [[../principles/abya-yala]] framing and Consejo Ampliado deliberation.

## Links

- [[00-VISION]]
- [[../principles/constitution]]
- [[../principles/abya-yala]]
- [[L1-identity]]
- [[L5-reputation]]
- [[../PROGRESS]]
