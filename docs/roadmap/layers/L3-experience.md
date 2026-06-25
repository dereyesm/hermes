---
title: L3 — Experience
type: layer
status: planned
percent: 5
depends_on: ["[[L2-network]]"]
---

# L3 — Experience

The layer that makes the metaverse **feel like a game**. Without this, the protocol is invisible.

## Vision

When a user opens `amaru shell`, they should see:

- Their identity, Welt form, current mood
- A map of online clans (like a WoW zone)
- A bus stream filtered to what they care about
- Available quests
- Slash commands to invoke any LLM, send messages, accept missions

This is what turns "a federated bus protocol" into "a place you go to".

## Components

| Component | Spec target | Status | Notes |
|---|---|---|---|
| [[../components/tui-shell]] (`amaru shell`) | AES-7531 *(draft)* | planned 🔵 | the headline feature |
| Welt UI binding | — | partial | data exists, no UI |
| Multi-LLM in-shell | — | partial | adapters exist, no UX |
| Real-time presence | — | live | `amaru hub roster` |
| Visual map of clans | — | planned 🔵 | rendered from Agora directory |
| Mood + dimension display | — | planned 🔵 | injects from hooks |

## Inspirations

| Source | What we take |
|---|---|
| **World of Warcraft** | Zone awareness, LFG status, party formation, raid coordination |
| **GTA Online** | Open-world economy, missions, reputation visible to others |
| **mosh / tmux** | Terminal-native, no browser required |
| **textual** (Python) / **bubbletea** (Go) | TUI frameworks |
| **vim / emacs** | Modal keybindings, leader keys |

## Why "feel" matters

A protocol that **works** is not the same as a protocol that **invites**. People do not adopt RFCs; they adopt experiences. The TUI shell is the bridge from "an open-source Python package" to "a place worth going to".

## Links

- [[00-VISION]]
- [[L2-network]]
- [[../components/tui-shell]]
- [[L4-governance]]
- [[../PROGRESS]]
