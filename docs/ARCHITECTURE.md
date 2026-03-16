# HERMES Architecture Guide

A visual guide to the HERMES protocol stack.

## The 5-Layer Stack

<p align="center">
  <img src="diagrams/d2/five-layer-stack.svg" alt="HERMES 5-layer protocol stack" width="800"/>
</p>

## Message Lifecycle

<p align="center">
  <img src="diagrams/d2/message-lifecycle.svg" alt="HERMES message lifecycle" width="600"/>
</p>

## Namespace Topology

HERMES uses a **star topology** with the controller at the center:

<p align="center">
  <img src="diagrams/d2/namespace-topology.svg" alt="HERMES star topology with controller hub" width="600"/>
</p>

**Key rules**:
- Namespaces NEVER communicate directly — all traffic goes through the bus
- The controller can read all namespaces but cannot execute in any
- Each namespace has its own isolated set of tools and credentials
- Data crosses require explicit firewall rules + human approval

## Firewall Model

<p align="center">
  <img src="diagrams/d2/firewall-model.svg" alt="HERMES firewall model with namespace isolation" width="700"/>
</p>

## Session Lifecycle (SYN/FIN)

<p align="center">
  <img src="diagrams/d2/session-lifecycle.svg" alt="HERMES session lifecycle (SYN/FIN)" width="700"/>
</p>

## Control Plane vs Data Plane

<p align="center">
  <img src="diagrams/d2/control-vs-data-plane.svg" alt="HERMES control plane vs data plane separation" width="700"/>
</p>

HERMES is a **signaling protocol**, not a data protocol. Like SS7 in telecom networks, it carries the coordination messages that tell agents where to work and what changed — but the actual work happens outside the bus.

## File System Layout

A typical HERMES deployment:

```
~/.hermes/                          # or any root directory
├── bus.jsonl                       # active messages
├── bus-archive.jsonl               # expired messages
├── routes.md                       # routing table
│
├── engineering/                    # namespace: engineering
│   ├── config.md                   # namespace config + SYNC HEADER
│   ├── memory/                     # persistent state
│   │   └── MEMORY.md
│   └── agents/                     # agent definitions
│       ├── lead.md
│       └── reviewer.md
│
├── finance/                        # namespace: finance
│   ├── config.md
│   ├── memory/
│   │   └── MEMORY.md
│   └── agents/
│       └── accountant.md
│
└── controller/                     # namespace: controller
    ├── config.md
    └── agents/
        └── router.md
```

## Gateway: The Clan Boundary

When a clan wants to connect with other clans on the Agora (public inter-clan network), it deploys a **Gateway** — a NAT-like component at the boundary.

<p align="center">
  <img src="diagrams/d2/gateway-clan-boundary.svg" alt="HERMES gateway at clan boundary with NAT and Agora" width="800"/>
</p>

**What the gateway exposes**: Public profiles (alias, capabilities, Resonance score).

**What the gateway protects**: Internal names, bus messages, Bounty/XP, credentials, namespace topology, memory, session logs.

See [ARC-3022](../spec/ARC-3022.md) for the full specification.

## Dual Reputation Model

<p align="center">
  <img src="diagrams/d2/dual-reputation.svg" alt="HERMES dual reputation model — Bounty vs Resonance" width="600"/>
</p>

## Related Specifications

| Spec | Title | What it covers |
|------|-------|---------------|
| [ARC-0001](../spec/ARC-0001.md) | HERMES Architecture | The meta-standard |
| [ATR-X.200](../spec/ATR-X200.md) | Reference Model | Formal 5-layer model |
| [ARC-5322](../spec/ARC-5322.md) | Message Format | JSONL packet spec |
| [ARC-0793](../spec/ARC-0793.md) | Reliable Transport | SYN/FIN/ACK |
| [ARC-0791](../spec/ARC-0791.md) | Addressing & Routing | Namespaces and routes |
| [ARC-1918](../spec/ARC-1918.md) | Private Spaces | Firewall model |
| [ARC-3022](../spec/ARC-3022.md) | Agent Gateway | NAT, filtering, Agora connection |
| [ATR-Q.700](../spec/ATR-Q700.md) | OOB Signaling | Design philosophy |
