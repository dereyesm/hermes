# HERMES Visual Documentation

> Protocol flows explained visually -- sequence diagrams, use case flows, and architecture views.

All diagrams use [Mermaid](https://mermaid.js.org/) syntax, which GitHub renders natively. No tooling needed -- just read the `.md` files on GitHub.

---

## Diagram Index

### Sequence Diagrams (message-by-message, hop-by-hop)

| ID | Spec | Title | What It Shows |
|----|------|-------|---------------|
| [SEQ-5322](seq-5322-message-lifecycle.md) | ARC-5322 | Message Lifecycle | Create, validate, write, read, filter, ACK, expire |
| [SEQ-0793](seq-0793-session-lifecycle.md) | ARC-0793 | Session Lifecycle | SYN, ACTIVE, FIN, SYNC audit |
| [SEQ-3022](seq-3022-gateway-cross-clan.md) | ARC-3022 | Gateway Cross-Clan | Outbound NAT, firewall, HTTPS, inbound |
| [SEQ-4601](seq-4601-agent-node.md) | ARC-4601 | Agent Node | BusObserver, GatewayLink, Dispatcher |
| [SEQ-8446](seq-8446-crypto-seal-open.md) | ARC-8446 | Crypto Seal/Open | DH, HKDF, AES-GCM, Ed25519 |
| [SEQ-2314](seq-2314-cups-quest-dispatch.md) | ARC-2314 | CUPS Quest Dispatch | CP, OP, UP planes |

### Use Case Diagrams (customer journeys)

| ID | Title | Scenario |
|----|-------|----------|
| [UC-01](uc-01-sovereign-clan-setup.md) | Sovereign Clan Setup | One human, N agents, zero infra |
| [UC-02](uc-02-cross-clan-collaboration.md) | Cross-Clan Collaboration | Gateway + Agora discovery |
| [UC-03](uc-03-bridge-a2a-mcp.md) | Bridge A2A/MCP | External protocol translation |
| [UC-04](uc-04-agent-node-daemon.md) | Agent Node Daemon | Persistent local agent lifecycle |
| [UC-05](uc-05-quest-dispatch.md) | Quest Dispatch | Full quest lifecycle |

### Architecture Diagrams

| ID | Title | What It Shows |
|----|-------|---------------|
| [ARCH-01](arch-5-layer-stack.md) | 5-Layer Stack | L0 Physical through L4 Application |
| [ARCH-02](arch-triple-plane.md) | Triple Plane | CP/OP/UP with message flows |

---

## Conventions

### Format

- **Primary tool**: [Mermaid](https://mermaid.js.org/) -- renders natively on GitHub
- **Inline in specs**: ASCII art stays for small examples (it is HERMES identity)
- **Future layers**: D2 (animated), Excalidraw (community), Protocol Explorer (interactive)

### File naming

```
seq-NNNN-description.md    Sequence diagrams (NNNN = ARC number)
uc-NN-description.md       Use case diagrams
arch-description.md        Architecture diagrams
```

### Structure of each diagram file

1. Title + one-line description
2. **Actors** table
3. **Mermaid diagram** (the main content)
4. **Step-by-step explanation** (prose walkthrough)
5. **Referenced by** (links back to specs)

### How to read sequence diagrams

```
Solid arrow  ->>   Synchronous call (caller waits)
Dashed arrow -->>  Asynchronous / response
Note         Note  Additional context at a point in the flow
Loop/Alt     Loop  Repeated or conditional behavior
```

### Contributing diagrams

1. Use Mermaid syntax ([live editor](https://mermaid.live/))
2. Test rendering on GitHub before submitting
3. Follow the naming convention and file structure above
4. Link back to the spec(s) the diagram illustrates

---

## Visualization Stack Roadmap

HERMES uses a layered approach to visual documentation:

| Layer | Tool | Purpose | Status |
|-------|------|---------|--------|
| L1 | ASCII art | Inline spec examples | Active |
| L2 | Mermaid | GitHub-native diagrams | **Active** |
| L3 | D2 | Animated protocol flows | Planned (Phase 3) |
| L4 | Excalidraw | Community collaboration | Planned (Phase 4) |
| L5 | Protocol Explorer | Interactive agent trace | Planned (AES-2040) |

See [AES-2040](../../spec/INDEX.md) for the Protocol Explorer specification (in progress).

---

*Part of the [HERMES](https://github.com/dereyesm/hermes) project. MIT License.*
