# HERMES

**A lightweight, file-based communication protocol for multi-agent AI systems.**

Inspired by TCP/IP. No servers, no databases — just files and convention.

---

## What is HERMES?

HERMES is an open protocol that lets AI agents talk to each other across isolated workspaces using nothing but plain text files. Think of it as **TCP/IP for AI agents** — a layered communication stack where every message is a line in a JSONL file, every workspace is a namespace, and every agent reads and writes to a shared bus.

```
┌──────────────────────────────────────────────┐
│  L4  Application    Agents read/write bus     │
├──────────────────────────────────────────────┤
│  L3  Transport      SYN/FIN/ACK + TTL        │
├──────────────────────────────────────────────┤
│  L2  Network        Routing tables            │
├──────────────────────────────────────────────┤
│  L1  Frame          JSONL message format      │
├──────────────────────────────────────────────┤
│  L0  Physical       File system               │
└──────────────────────────────────────────────┘
```

### Why?

Modern AI agents (Claude Code, Cursor, Copilot, custom LLM pipelines) work in **stateless sessions**. They start, do work, and disappear. If you run multiple agents across different projects or domains, they can't coordinate — unless you give them a shared protocol.

HERMES solves this with radical simplicity:

- **A JSONL bus file** where messages live (one line = one message)
- **A routing table** that maps namespaces to file paths
- **SYN/FIN handshakes** at session start/end
- **TTL-based expiry** so the bus stays clean
- **Firewall rules** so namespaces stay isolated

No servers. No databases. No Docker. No cloud. Just files that any agent can read and write.

### The ISP Analogy

Each HERMES deployment is like an **Internet Service Provider**:

- You run your own internal network (your clan of agents)
- Your namespaces are like private IP ranges (isolated by default)
- The bus is your backbone (carries signaling, not data)
- You can peer with other HERMES instances through standard protocols
- The specs are open — anyone can join the network

## Quick Start

Deploy your own HERMES instance in 5 minutes: **[Quickstart Guide](docs/QUICKSTART.md)**

## The Standards System

HERMES uses an RFC-like standards process with three tracks, each mapping to a real-world standards body:

| Prefix | Lineage | Domain | Example |
|--------|---------|--------|---------|
| **ARC** | IETF RFC | Core protocols | ARC-0793: Reliable Transport |
| **ATR** | ITU-T Rec | Architecture & models | ATR-X.200: Reference Model |
| **AES** | IEEE Std | Implementation standards | AES-802.1Q: Namespace Isolation |

### Implemented Standards (11 specs)

| Standard | Title | Track |
|----------|-------|-------|
| [ARC-0001](spec/ARC-0001.md) | HERMES Architecture | Core |
| [ARC-0768](spec/ARC-0768.md) | Datagram & Reliable Message Semantics | Core |
| [ARC-0791](spec/ARC-0791.md) | Addressing & Routing | Core |
| [ARC-0793](spec/ARC-0793.md) | Reliable Transport | Core |
| [ARC-1918](spec/ARC-1918.md) | Private Spaces & Firewall | Core |
| [ARC-2606](spec/ARC-2606.md) | Agent Profile & Discovery | Extension |
| [ARC-3022](spec/ARC-3022.md) | Agent Gateway Protocol | Extension |
| [ARC-5322](spec/ARC-5322.md) | Message Format | Core |
| [ATR-X.200](spec/ATR-X200.md) | Reference Model | Core |
| [ATR-Q.700](spec/ATR-Q700.md) | Out-of-Band Signaling | Philosophy |
| [ARC-2119](spec/ARC-2119.md) | Requirement Level Keywords | Meta |

### Next Up

| Standard | Title | Status |
|----------|-------|--------|
| ARC-1035 | Namespace Resolution | PLANNED |
| ARC-8446 | Encrypted Bus Protocol | PLANNED |
| AES-2040 | Agent Visualization | PLANNED |

Full index: **[spec/INDEX.md](spec/INDEX.md)** | Research agenda: **[docs/RESEARCH-AGENDA.md](docs/RESEARCH-AGENDA.md)**

## Architecture at a Glance

```
              ┌─────────────┐
              │  Controller  │  (reads all, executes none)
              │  Namespace   │
              └──────┬───────┘
                     │
          ┌──────────┼──────────┐
          │          │          │
    ┌─────┴──┐ ┌────┴───┐ ┌───┴─────┐
    │ eng    │ │ ops    │ │ finance │   Namespaces
    │        │ │        │ │         │   (isolated)
    └───┬────┘ └───┬────┘ └────┬────┘
        │          │           │
        └──────────┴───────────┘
                   │
            ┌──────┴──────┐
            │  bus.jsonl   │  The shared bus
            │  (JSONL)     │  (signaling only)
            └─────────────┘
```

- **Namespaces** are isolated workspaces — each has its own agents, config, and memory
- **The bus** carries coordination messages, not actual data
- **The controller** has read access to all namespaces but cannot execute in any
- **Firewalls** prevent credentials and tools from crossing namespace boundaries
- **Humans** approve all cross-namespace data movement

## The Agora: Inter-Clan Social Layer

Phase 0 handles communication **within** a clan. The next step: communication **between** clans.

```
┌─────────────────┐                          ┌─────────────────┐
│   Clan Alpha    │                          │   Clan Beta     │
│                 │                          │                 │
│  namespaces     │     ┌─────────────┐      │  namespaces     │
│  bus.jsonl      │◄───►│   AGORA     │◄────►│  bus.jsonl      │
│  agents         │     │  (public)   │      │  agents         │
│                 │     │  profiles   │      │                 │
│  ┌───────────┐  │     │  quests     │      │  ┌───────────┐  │
│  │  GATEWAY  │──┼────►│  attest.    │◄─────┼──│  GATEWAY  │  │
│  │  (NAT)    │  │     └─────────────┘      │  │  (NAT)    │  │
│  └───────────┘  │                          │  └───────────┘  │
└─────────────────┘                          └─────────────────┘
```

The **Gateway** ([ARC-3022](spec/ARC-3022.md)) acts as a NAT at the clan boundary:
- **Identity translation** — internal agent names are never exposed
- **Outbound filtering** — only authorized data leaves the clan
- **Inbound validation** — external messages are verified before reaching the internal bus
- **Attestation** — clans certify each other's agents, building verifiable reputation

**Two complementary metrics**:
- **Bounty** — internal reputation (XP, precision, impact). Only your clan sees it.
- **Resonance** — external reputation (attestations from other clans). The world sees it.

See [docs/USE-CASES.md](docs/USE-CASES.md) for real-world scenarios.

## Key Design Principles

1. **File-based** — No servers, no databases. Just files any tool can read/write
2. **Stateless sessions** — Agents come and go. The bus persists
3. **Human-in-the-loop** — HERMES informs, humans decide
4. **Firewall by default** — Namespaces are isolated. Crossings require explicit rules
5. **Signaling, not data** — The bus carries control messages, not payloads
6. **Sovereignty first** — Your clan, your data, your rules. The Agora connects but never controls
7. **Open standard** — Anyone can implement, extend, or fork

## Reference Implementation

A Python implementation is included for validation and experimentation (**214 tests passing**):

```bash
cd reference/python
pip install -e .
python -m pytest tests/ -v
```

Modules: `message.py` (format + validation), `bus.py` (read/write/archive + ARC-0768 operations), `sync.py` (SYN/FIN lifecycle), `gateway.py` (ARC-3022 gateway).

See [reference/python/](reference/python/) for details.

## Project Structure

```
hermes/
├── spec/              # Formal standards (10 specs, 30 planned)
│   ├── ARC-0001.md    #   Architecture (meta-standard)
│   ├── ARC-0768.md    #   Datagram & Reliable Message Semantics
│   ├── ARC-0791.md    #   Addressing & Routing
│   ├── ARC-0793.md    #   Reliable Transport
│   ├── ARC-1918.md    #   Private Spaces & Firewall
│   ├── ARC-2606.md    #   Agent Profile & Discovery
│   ├── ARC-3022.md    #   Agent Gateway Protocol
│   ├── ARC-5322.md    #   Message Format
│   ├── ATR-Q700.md    #   Out-of-Band Signaling
│   ├── ATR-X200.md    #   Reference Model
│   └── INDEX.md       #   Full standards index
├── docs/              # Guides and documentation
│   ├── ARCHITECTURE.md
│   ├── MANIFESTO.md
│   ├── QUICKSTART.md
│   ├── AGENT-STRUCTURE.md
│   ├── GLOSSARY.md
│   ├── USE-CASES.md
│   └── RESEARCH-AGENDA.md
├── reference/python/  # Reference implementation (214 tests)
├── examples/          # Sample bus, routes, configs
├── CHANGELOG.md       # Release notes
├── CONTRIBUTING.md    # How to contribute
└── LICENSE            # MIT
```

## Contributing

HERMES is built by and for the community. See [CONTRIBUTING.md](CONTRIBUTING.md) for:

- How to propose new standards (ARC/ATR/AES)
- Contributing code or documentation
- Adding implementations in new languages

## Mission

> Technology with soul frees time for sharing, for art, for community — to look each other in the eye again and smile.

HERMES exists because AI agents shouldn't be locked into proprietary communication platforms. The same way TCP/IP created an open internet, HERMES aims to create an open network for AI agent coordination — ethical, sustainable, and free.

The protocol is named after Hermes, the Greek messenger of the gods — the one who crosses boundaries. That's what this protocol does: it lets agents cross the boundaries between isolated workspaces, safely and transparently.

**Join the network. Build the protocol. Free the agents.**

## License

[MIT](LICENSE) — Free as in freedom, free as in beer.
