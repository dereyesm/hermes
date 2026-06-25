---
title: Constitution spec — ATR-CONST-01
type: component
status: planned
percent: 0
layer: L4-governance
priority: P1
depends_on: ["[[../principles/constitution]]"]
---

# ATR-CONST-01 — Amaru Constitution

The spec that translates [[../principles/constitution]] into an enforceable + auditable protocol.

## Scope

Defines:
- Format of a clan's adhesion signature file
- Format of a constitutional violation event in the bus
- Format of an appeal request
- Format of an arbitration ruling
- Required fields for each rule (R1–R8 minimum)
- Versioning of the constitution itself

Does NOT define:
- Which behaviors count as violations (that's the constitution text, separate)
- Punishment severity (lives in [[../layers/L5-reputation]])

## Status

**Pre-draft**. Awaiting Consejo Ampliado initial framing.

## Path to v0.1 ratified

- [ ] Daniel writes first text of R1–R8
- [ ] Consejo Ampliado (Palas + Ares + Artemisa + MariaM + Hannah) review
- [ ] Spec draft on branch
- [ ] Bilateral consultation with JEI clan (first external partner)
- [ ] Open issue inviting public comments (Tinkuy quest)
- [ ] Mark as v0.1 *experimental*

## Open governance question

If the constitution is meant to bind the network, who can amend it?

**Proposal (to deliberate)**: amendments require **3 clans** to sign a `constitution_amendment` event. Daniel cannot amend it alone after v0.1.

This protects against single-actor capture.

## Links

- [[../00-VISION]]
- [[../principles/constitution]]
- [[../principles/abya-yala]]
- [[../layers/L4-governance]]
- [[../layers/L5-reputation]]
