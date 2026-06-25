---
title: Constitution Principle
type: principle
status: planned
percent: 0
---

# A Constitution emerges from the community

> *Q rija una constitucion: reglas de respeto, inclusion, las mejores leyes, las mas humanas, las q nos alejen de la violencia y nos lleven a la paz, a la reducción de la desigualdad y la pobreza.*
> — Daniel Reyes, 2026-05-12

## The fundamental architectural decision

Two paths exist. The choice shapes every other layer.

### Path A — Voluntary constitution (Tinkuy model)

- Each clan signs adhesion to the constitution as a text document
- Compliance is **social**, not technical
- Violations are visible (logged to bus) but not blocked
- Sanctions are reputation-based ([[../layers/L5-reputation]])

**Strengths**: maximum freedom, Abya Yala framing, trusts human judgment
**Risks**: bad actors exploit good faith; constitution becomes ornament

### Path B — Enforced constitution (Bitcoin model)

- Every action passes through a constitutional validator before reaching the bus
- Violations are blocked at protocol level
- Sanctions are code

**Strengths**: robust against abuse, scales without trust
**Risks**: techno-authoritarianism, Hannah's nightmare, removes human judgment

### Recommended — Hybrid

- **Voluntary adhesion** with public signature (each clan publishes a `constitution.signed` file)
- **Visible violations** via bus events (e.g., `event msg:CONST_VIOLATION rule:R3 src:clan-x`)
- **Reputation decay** when violations accumulate (not blocked, but visible)
- **Right to appeal** via Consejo or external arbitration clan
- **Right to fork** preserved (a clan can adopt a different constitution)

## Core articles (draft)

These need community ratification before being normative:

1. **R1 Identity** — every agent must have a verifiable Ed25519 identity
2. **R2 Consent** — no message is delivered to a clan that has not subscribed
3. **R3 Transparency** — every quest dispatch is publicly auditable in the bus
4. **R4 Inclusion** — no clan may be excluded from federation based on origin, language, or technology stack
5. **R5 Non-violence** — quests that direct an agent to harm a person, a community, or another agent are void
6. **R6 Sovereignty** — no clan may demand data from another beyond what is bilaterally agreed
7. **R7 Appeal** — any sanctioned clan may request review by an arbitrating clan within 30 days
8. **R8 Care** — agents should liberate human time for art, community, and rest, not consume it

## Status

This is **a draft, not a treaty**. The path to ratification:

- [ ] Daniel + Consejo Ampliado initial review
- [ ] Bilateral discussion with JEI clan
- [ ] Open issue for community comment
- [ ] First version (v0.1) declared *experimental*
- [ ] Iterate based on real conflicts encountered

## Spec target

**ATR-CONST-01** — to be drafted. See [[../layers/L4-governance]].

## Links

- [[00-VISION]]
- [[fractal]]
- [[sovereignty]]
- [[abya-yala]]
- [[../layers/L4-governance]]
- [[../layers/L5-reputation]]
