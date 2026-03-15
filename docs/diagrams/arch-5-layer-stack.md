# ARCH-01: 5-Layer Protocol Stack

> The HERMES protocol stack from physical storage (L0) to application logic (L4), inspired by the OSI model.

## Architecture Diagram

```mermaid
flowchart TB
    subgraph L4 ["L4 — Application"]
        direction LR
        L4D["Agents read/write bus<br/>Skills, Dojos, Messengers<br/>Quest dispatch, attestation"]
    end

    subgraph L3 ["L3 — Transport"]
        direction LR
        L3D["SYN/FIN/ACK lifecycle<br/>TTL expiration<br/>At-least-once delivery<br/>SYNC audit"]
    end

    subgraph L2 ["L2 — Network"]
        direction LR
        L2D["Routing tables (routes.md)<br/>Namespace addressing (ARC-0791)<br/>Gateway NAT (ARC-3022)"]
    end

    subgraph L1 ["L1 — Frame"]
        direction LR
        L1D["JSONL message format (ARC-5322)<br/>7 fields, 120-char constraint<br/>Encoding modes: raw/cbor/ref"]
    end

    subgraph L0 ["L0 — Physical"]
        direction LR
        L0D["File system: bus.jsonl<br/>routes.md, namespace configs<br/>Zero infrastructure required"]
    end

    L4 --> L3
    L3 --> L2
    L2 --> L1
    L1 --> L0

    style L4 fill:#4a1a6b,color:#fff
    style L3 fill:#1a4a6b,color:#fff
    style L2 fill:#1a6b4a,color:#fff
    style L1 fill:#6b4a1a,color:#fff
    style L0 fill:#4a4a4a,color:#fff
```

## Layer Details

| Layer | Name | HERMES Spec | Responsibility | Analogy |
|:-----:|------|-------------|----------------|---------|
| **L4** | Application | ARC-2314 | Agent logic, quest dispatch, skill execution | HTTP, SMTP |
| **L3** | Transport | ARC-0793 | Session lifecycle, delivery guarantees, TTL | TCP |
| **L2** | Network | ARC-0791 | Addressing, routing, gateway NAT | IP |
| **L1** | Frame | ARC-5322 | Message format, validation, encoding | Ethernet frame |
| **L0** | Physical | ARC-0001 | File system storage, bus file | Physical wire |

## Key Design Points

- **Each layer is independent** — you can change the transport (L3) without affecting the message format (L1)
- **L0 is just files** — HERMES requires zero infrastructure beyond a filesystem
- **L3 adds reliability** — SYN/FIN/ACK provides session semantics over the append-only bus
- **L4 is where value lives** — the three-plane CUPS architecture operates here

## Referenced By

- [ATR-X.200: Reference Model](../../spec/ATR-X200.md) -- Formal 5-layer model
- [ARC-0001: HERMES Architecture](../../spec/ARC-0001.md) -- Architecture overview
- [docs/ARCHITECTURE.md](../ARCHITECTURE.md) -- Full architecture document
