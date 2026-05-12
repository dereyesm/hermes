---
title: L2 — Network
type: layer
status: live
percent: 100
depends_on: ["[[L0-foundation]]", "[[L1-identity]]"]
---

# L2 — Network

How nodes find each other and stay connected.

## Components

| Component | Spec | Status | Code |
|---|---|---|---|
| S2S federation | ARC-4601 §17 | live ✅ | `amaru/hub.py` (FederationLink) |
| Peer discovery (Agora) | — | live ✅ | `amaru/agora.py` |
| Auto-peer TOFU | ARC-0370 | live ✅ | `amaru/hub.py` |
| A2A/MCP bridge | ARC-7231 | live ✅ | `amaru/bridge.py` |
| Quest dispatch (Dojo) | ARC-2314 | live ✅ | `amaru/dojo.py` |
| Hub roster (LFG) | — | live ✅ | `amaru hub roster/ready/busy` |
| Peer invite/accept | — | live ✅ | `amaru peer invite/accept` |

## What it enables

- **Find your friends**: `amaru hub roster` shows who is online (like WoW)
- **Open or close to traffic**: `amaru hub ready/busy` (like LFG status)
- **Bring your own agents**: Claude Code, Cursor, Continue.dev, Gemini CLI all federate via adapters
- **Federate without DNS**: peer-to-peer via S2S, no name authority

## Operational evidence

- Bilateral with JEI clan: 22 tests Phase 5 GREEN
- QC002 Phase 1 bilateral cut: 12-may-2026 — `delivered via local hub` confirmed across LAN

## Links

- [[00-VISION]]
- [[L0-foundation]]
- [[L1-identity]]
- [[L3-experience]]
- [[L6-marketplace]]
- [[../PROGRESS]]
