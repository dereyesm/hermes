---
title: L0 — Foundation
type: layer
status: live
percent: 100
depends_on: []
---

# L0 — Foundation

The wire. Bus + hub + message format. Without this, nothing else exists.

## Components

| Component | Spec | Status | Code |
|---|---|---|---|
| Wire format | ARC-5322 | live ✅ | `amaru/message.py` |
| Hub server | ARC-4601 §15 | live ✅ | `amaru/hub.py` |
| Bus storage | implied by ARC-5322 | live ✅ | `amaru/bus.py` |
| Wire protocol guide | `docs/wire-protocol-hub.md` | live ✅ | — |

## What it enables

- **Persistent message intent**: every send writes to bus first (ATR-Q.931 §8)
- **Asynchronous delivery**: store-and-forward if recipient is offline
- **Pluggable transport**: WebSocket today, anything tomorrow

## Why it is mature

- 1624/1624 tests pass
- Wire format is 76.9% efficient vs JSON-RPC, 4.9× less overhead than gRPC
- Bilateral execution proven with JEI clan (Issue #13 evidence)

## Links

- [[00-VISION]]
- [[L1-identity]]
- [[L2-network]]
- [[../PROGRESS]]
