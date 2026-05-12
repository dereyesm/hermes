---
title: Fractal Principle
type: principle
status: live
---

# Each member is a piece of Amaru AND Amaru itself

> *Un metaverso donde cada miembro de la comunidad sea un pedacito de Amaru y Amaru a la vez.*
> — Daniel Reyes, 2026-05-12

## What it means

Amaru is **holographic, not hierarchical**:

- Every clan running the protocol **is** Amaru in its full form
- No central node has more "Amaru-ness" than another
- A single user with `amaru` installed locally is already a sovereign node
- Two users together are already a federation
- The "metaverse" is **the sum of all sovereign instances**, not a platform they log into

This is the opposite of Facebook, Discord, Roblox. There is no "Amaru Inc." that hosts the world. There are only **clans that adopt the protocol** and federate by choice.

## Why it matters

The fractal architecture protects against:

- **Platform capture** — no company can sell or shut down Amaru
- **Single point of failure** — if one hub dies, the rest keep working
- **Centralized censorship** — each clan governs its own membership
- **Surveillance** — no global feed, no telemetry pipeline, no behavioral profile

It enables:

- **Local sovereignty** — see [[sovereignty]]
- **Community-scoped governance** — see [[constitution]]
- **Organic growth** — the network grows by *invitations*, not by viral acquisition

## Implementation evidence

| Feature | Where the fractal shows up |
|---|---|
| Hub Mode | Each user runs their own hub. No DNS, no signup. |
| S2S federation | ARC-4601 §17 — hubs talk peer-to-peer, no master |
| Bus.jsonl | Each clan has its **own** bus. Sync via consent. |
| Identity | Ed25519 keys generated locally. No issuer. |
| Adapters | Each agent (Claude Code, Cursor, Continue.dev) is also a node. |

## Tensions

- **Discoverability**: fractal networks are hard to find. Solved by [[../layers/L2-network]] (Agora directory) and *word-of-mouth invitation*.
- **Newcomer cost**: requires installation, not signup. Solved by `amaru install` one-command setup (already exists).
- **Coordination**: distributed coordination is harder than centralized. Solved by Dojo quests + bus eventual consistency.

## Links

- [[00-VISION]]
- [[sovereignty]]
- [[constitution]]
- [[abya-yala]]
- [[../layers/L0-foundation]]
