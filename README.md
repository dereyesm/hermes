# HERMES — Local-first messaging for AI agents

[![Tests](https://github.com/dereyesm/hermes/actions/workflows/ci.yml/badge.svg)](https://github.com/dereyesm/hermes/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/badge/pypi-hermes--protocol-blue.svg)](https://pypi.org/project/hermes-protocol/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Your AI agents can't talk to each other. HERMES fixes that -- no servers, no cloud, no API keys. Just a local message bus that works offline.

## Quick Start

```bash
pip install hermes-protocol        # 1. Install
hermes init --clan-id my-team      # 2. Initialize (creates ~/.hermes/)
hermes adapt claude-code           # 3. Connect your AI agent
```

That's it. Your agent can now read and write messages through the HERMES bus.

### Send your first message

From Claude Code (or any MCP-enabled agent):

```
"Send a HERMES message to cursor: Backend API ready at /api/todos"
```

Or from the command line:

```bash
echo '{"ts":"2026-04-03","src":"backend","dst":"frontend","type":"dispatch","msg":"API ready: GET/POST /api/todos","ttl":7,"ack":[]}' >> ~/.hermes/bus.jsonl
```

Or from Python:

```python
from hermes.bus import write_message
from hermes.message import create_message

write_message("~/.hermes/bus.jsonl", create_message(
    src="backend", dst="frontend", type="dispatch",
    msg="API ready: GET/POST /api/todos",
))
```

### Connect multiple agents

```bash
hermes adapt claude-code           # Claude Code (MCP tools + hooks)
hermes adapt cursor                # Cursor (.cursorrules + bus symlink)
hermes adapt gemini-cli            # Gemini CLI (GEMINI.md + settings)
hermes adapt opencode              # OpenCode (AGENTS.md + config)
hermes adapt continue              # Continue.dev (.continuerc.json + rules)
hermes adapt --all                 # All detected agents at once
```

Every agent reads the same `~/.hermes/bus.jsonl`. Messages are just JSON lines -- `cat`, `grep`, and `jq` all work.

---

## Why HERMES?

- **Zero infrastructure** -- no servers, no Docker, no cloud. Works offline with `cat >> bus.jsonl`.
- **E2E encrypted** -- Ed25519 + AES-256-GCM per message. Even the relay can't read your data.
- **Agent-agnostic** -- works with Claude Code, Cursor, Gemini CLI, OpenCode, or any tool that reads files.

---

## How It Works

```
  Claude Code                    Cursor
      │                            │
      │ hermes_bus_write()         │ reads .cursor/bus.jsonl
      │                            │
      └──────► ~/.hermes/bus.jsonl ◄──────┘
                    │
              Just a file.
         grep it. git it. own it.
```

HERMES messages have 7 fields. That's the whole protocol:

```json
{"ts":"2026-04-03","src":"backend","dst":"frontend","type":"dispatch","msg":"API ready","ttl":7,"ack":[]}
```

---

## What else can it do?

| Feature | Command | What it does |
|---------|---------|-------------|
| **Real-time P2P** | `hermes hub install` | WebSocket hub for live messaging between machines |
| **Peer encryption** | `hermes peer invite` | One-command bilateral key exchange |
| **Hub federation** | Built-in (S2S) | Your hub talks to other hubs (BGP-style routing) |
| **Token telemetry** | `hermes llm usage` | Track AI token costs across backends |
| **Full setup** | `hermes install` | OS service + hooks + keys in one command |

---

## Deep Dive

Everything below is for the curious. You don't need any of it to use HERMES.

<details>
<summary><strong>Where HERMES Fits (vs MCP, A2A, NLIP)</strong></summary>

| Protocol | Scope | Transport | Infrastructure Required |
|----------|-------|-----------|------------------------|
| **MCP** (Anthropic/AAIF) | Model-to-Tools (vertical) | stdio, Streamable HTTP | Runtime process or HTTP server |
| **A2A** (Google/LF AI&Data) | Agent-to-Agent (horizontal) | HTTP/2, JSON-RPC, gRPC, SSE | HTTP endpoints, cloud services |
| **Ecma NLIP** (TC56) | Envelope protocol, multimodal | HTTP, WebSocket, AMQP | Network transport layer |
| **SLIM** (IETF draft) | Real-time agent messaging | gRPC + MLS | gRPC infrastructure |
| **ANP** | Discovery + DIDs | HTTP, JSON-LD | HTTP + DID resolver |
| **HERMES** | Sovereign + Hosted dual-mode | **File system / HTTPS** | **None** (Sovereign) or **Hub** (Hosted) |

**HERMES complements, does not replace, existing protocols.** Use MCP for tool binding. Use A2A for real-time agent-to-agent RPC. Use HERMES for the coordination layer that works without infrastructure.

See [docs/POSITIONING.md](docs/POSITIONING.md) for the full technical positioning paper.

</details>

<details>
<summary><strong>Key Features (full list)</strong></summary>

- **Zero infrastructure** -- works with `cat >> bus.jsonl`. No servers, no Docker, no cloud, no internet required.
- **End-to-end encrypted** -- Ed25519 signing + X25519 ECDHE key agreement + AES-256-GCM per message. Forward secrecy by default.
- **76.9% wire efficient** -- compact mode is 4.9x less overhead than gRPC. Still valid JSON. See [ATR-G.711](spec/ATR-G711.md).
- **File-based = auditable** -- every message is a line of JSON. Git-versionable, grep-searchable, human-inspectable.
- **Telecom engineering rigor** -- 20 formal specs modeled after IETF, ITU-T, and IEEE.
- **Privacy-first** -- firewalls enforce namespace isolation. The gateway acts as NAT: internal identity is never exposed externally.
- **Backward compatible** -- Phase 0 (JSONL on a filesystem) always works. Every extension is optional.

</details>

<details>
<summary><strong>Wire Format Details</strong></summary>

Two wire formats are supported, auto-detected by the first character (`{` or `[`):

```json
{"ts":"2026-03-03","src":"engineering","dst":"ops","type":"state","msg":"Build pipeline green.","ttl":7,"ack":[]}
[9559,"engineering","ops",0,"Build pipeline green.",7,[]]
```

| Metric | Verbose | Compact |
|--------|---------|---------|
| Wrapper overhead | 105 B | **36 B** |
| Efficiency @120B | 53.1% | **76.9%** |
| vs gRPC | 1.7x | **4.9x** less overhead |

See [ARC-5322](spec/ARC-5322.md) for the full message format specification.

</details>

---

## Supported Agents

HERMES is agent-agnostic. The `hermes adapt` command generates the configuration each AI coding assistant expects from a single canonical source (`~/.hermes/`).

| Agent | Command | Output | Skills Format |
|-------|---------|--------|---------------|
| [Claude Code](https://claude.ai/code) | `hermes adapt claude-code` | `~/.claude/` (CLAUDE.md + symlinks) | SKILL.md (native) |
| [Cursor](https://cursor.com) | `hermes adapt cursor` | `.cursorrules` (compiled markdown) | Compiled into rules |
| [OpenCode](https://opencode.ai) | `hermes adapt opencode` | `~/.config/opencode/` (AGENTS.md + JSON) | SKILL.md (symlinks) |
| [Gemini CLI](https://github.com/google-gemini/gemini-cli) | `hermes adapt gemini-cli` | `GEMINI.md` + settings | Compiled into markdown |
| [Continue.dev](https://continue.dev) | `hermes adapt continue` | `.continuerc.json` + rules | SKILL.md (symlinks) |

Skills follow the [Agent Skills Open Standard](https://agentskills.io), making them portable across Claude Code, Gemini CLI, Cursor, OpenCode, and 30+ tools without modification. See [installable-model.md](docs/architecture/installable-model.md) for architecture details.

---

## Architecture

<p align="center">
  <img src="docs/diagrams/excalidraw/hero-clan-topology.svg" alt="HERMES Protocol — Clan topology with sovereign agents, encrypted relay, and cross-clan quest dispatch" width="800"/>
  <br/>
  <em>Sovereign clans communicate through encrypted relay channels. Each clan owns its agents, bus, and firewall. The Agora provides public discovery without surrendering sovereignty.</em>
</p>

<p align="center">
  <img src="docs/diagrams/d2/five-layer-stack.svg" alt="HERMES 5-layer protocol stack" width="600"/>
</p>

<p align="center">
  <img src="docs/diagrams/d2/namespace-topology.svg" alt="HERMES star topology with controller hub" width="600"/>
</p>

The **Compact Wire Format** ([ARC-5322 §14](spec/ARC-5322.md)) reduces wrapper overhead by 66% while remaining valid JSON:

<p align="center">
  <img src="docs/diagrams/d2/compact-wire-format.svg" alt="HERMES compact wire format — verbose vs compact comparison" width="800"/>
</p>

The **Skill Gateway** ([ARC-2314](spec/ARC-2314.md)) separates operations into three planes:

<p align="center">
  <img src="docs/diagrams/d2/cups-three-planes.svg" alt="HERMES CUPS triple-plane architecture" width="700"/>
</p>

- **Namespaces** are isolated workspaces with their own agents, configuration, and credentials
- **The bus** carries coordination messages (signaling, not bulk data)
- **The controller** has read access to all namespaces but cannot execute in any
- **Firewalls** (ARC-1918) prevent credentials and tools from crossing namespace boundaries
- **Humans** approve all cross-namespace data movement

Inter-clan communication uses the **Gateway** ([ARC-3022](spec/ARC-3022.md)) as a NAT at the boundary:

<p align="center">
  <img src="docs/diagrams/d2/gateway-clan-boundary.svg" alt="HERMES inter-clan gateway with NAT and Agora" width="700"/>
</p>

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full architecture document.

---

## Visual Documentation

Protocol flows explained with diagrams -- sequence diagrams (message-by-message), use case flows (customer journeys), and architecture views. All rendered natively by GitHub using [Mermaid](https://mermaid.js.org/).

**[Browse all diagrams](docs/diagrams/README.md)**

Highlights:
- **[Message Lifecycle](docs/diagrams/seq-5322-message-lifecycle.md)** -- how a message is created, validated, written, consumed, and archived
- **[Sovereign Clan Setup](docs/diagrams/uc-01-sovereign-clan-setup.md)** -- step-by-step setup with zero infrastructure

---

## The Standards System

HERMES uses a formal, RFC-like standards process with three tracks, each tracing its lineage to a real-world standards body:

| Track | Lineage | Domain | Example |
|-------|---------|--------|---------|
| **ARC** | IETF RFC | Core protocols: message formats, transport, addressing, security | ARC-0793: Reliable Transport |
| **ATR** | ITU-T Rec. | Architecture, reference models, telecom-inspired patterns | ATR-X.200: Reference Model |
| **AES** | IEEE Std | Implementation standards: interoperability, isolation, QoS | AES-802.1Q: Namespace Isolation |

### Standards (18 IMPL + 1 INFO + 1 DRAFT = 20 spec files)

| Standard | Title | Tier | IETF/ITU-T Lineage |
|----------|-------|------|---------------------|
| [ARC-0001](spec/ARC-0001.md) | HERMES Architecture | Core | Original (cf. RFC 791, 793) |
| [ARC-0768](spec/ARC-0768.md) | Datagram & Reliable Message Semantics | Core | RFC 768 (UDP) |
| [ARC-0791](spec/ARC-0791.md) | Addressing & Routing | Core | RFC 791 (IP) |
| [ARC-0793](spec/ARC-0793.md) | Reliable Transport | Core | RFC 793 (TCP) |
| [ARC-1918](spec/ARC-1918.md) | Private Spaces & Firewall | Core | RFC 1918 (Private Addressing) |
| [ARC-2314](spec/ARC-2314.md) | Skill Gateway Plane Architecture | Core | 3GPP TS 23.214 (CUPS) |
| [ARC-2606](spec/ARC-2606.md) | Agent Profile & Discovery | Extension | RFC 2606 (Reserved Domains) |
| [ARC-3022](spec/ARC-3022.md) | Agent Gateway Protocol | Extension | RFC 3022 (NAT) |
| [ARC-4601](spec/ARC-4601.md) | Agent Node Protocol + Hub Mode (§15) | Extension | RFC 4601 (PIM-SM), RFC 6455 (WebSocket) |
| [ARC-5322](spec/ARC-5322.md) | Message Format + Compact Wire (§14) | Core | RFC 5322 (Internet Message Format) |
| [ARC-7231](spec/ARC-7231.md) | Agent Semantics — Bridge Protocol | Extension | RFC 7231 (HTTP Semantics) |
| [ARC-8446](spec/ARC-8446.md) | Encrypted Bus Protocol | Security | RFC 8446 (TLS 1.3) |
| [ARC-9001](spec/ARC-9001.md) | Bus Integrity Protocol | Core | MVCC/OCC, ITU-T Q.703 (SS7) |
| [ARC-0369](spec/ARC-0369.md) | Agent Service Platform | Core | BBF TR-369 (USP) |
| [ARC-1122](spec/ARC-1122.md) | Agent Conformance Requirements | Core | RFC 1122 (Host Requirements), ECMA-430 |
| [ARC-2119](spec/ARC-2119.md) | Requirement Level Keywords | Meta | RFC 2119 (MUST/SHOULD/MAY) |
| [ATR-X.200](spec/ATR-X200.md) | Reference Model | Core | ITU-T X.200 (OSI Reference Model) |
| [ATR-Q.700](spec/ATR-Q700.md) | Out-of-Band Signaling | Philosophy | ITU-T Q.700 (SS7) |
| [ATR-G.711](spec/ATR-G711.md) | Payload Encoding & Wire Efficiency | Extension | ITU-T G.711 (PCM) |
| [AES-2040](spec/AES-2040.md) | Agent Visualization Standard | Extension | Original (DRAFT) |

Full index with 30 planned standards: **[spec/INDEX.md](spec/INDEX.md)**

---

## Reference Implementation

A Python reference implementation is included for validation and experimentation (**1500+ tests passing**):

```bash
cd reference/python
pip install -e .
python -m pytest tests/ -v
```

Modules:
- `message.py` -- format validation per ARC-5322 (verbose + compact §14), transport mode per ARC-0768
- `bus.py` -- read, write, filter, archive, correlation per ARC-0793 and ARC-0768
- `sync.py` -- SYN/FIN lifecycle management
- `gateway.py` -- identity translation, outbound filtering, attestation per ARC-3022
- `bridge.py` -- A2A/MCP bidirectional translation per ARC-7231
- `crypto.py` -- Ed25519 + X25519 + AES-256-GCM encryption per ARC-8446
- `agent.py` -- persistent Agent Node daemon per ARC-4601
- `hub.py` -- Hub Mode server: WebSocket routing, store-forward, Ed25519 auth per ARC-4601 §15
- `integrity.py` -- bus integrity: sequencing, ownership, MVCC, conflict log per ARC-9001
- `dojo.py` -- orchestration plane: quest dispatch, skill matching, XP tracking per ARC-2314
- `config.py` -- clan configuration and peer management
- `agora.py` -- Agora directory client for clan discovery
- `adapter.py` -- agent-agnostic adapter bridge (generates agent configs from `~/.hermes/`)
- `asp.py` -- Agent Service Platform: bus convergence + agent registration per ARC-0369
- `cli.py` -- command-line interface for clan operations
- `installer.py` -- cross-platform one-command setup
- `hooks.py` -- Claude Code hook handlers (SYN/FIN, hub_inject, dojo lifecycle)
- `terminal.py` -- brand-aware CLI output (rich/plain-text dual mode) per AES-2040
- `mcp_server.py` -- MCP server (11 tools: bus read/write, seal/open, peers, status, hub_send)
- `llm/` -- multi-LLM adapter layer: Gemini + Claude backends, SkillLoader, token telemetry

See [reference/python/](reference/python/) for details.

### Hub Mode (Real-Time P2P)

Run a local hub for real-time message routing between clans:

```bash
hermes hub init                  # generate hub-peers.json from peer registry
hermes hub install               # install as persistent OS service (macOS/Linux)
hermes hub status                # check hub health
hermes hub peers                 # list connected peers
hermes hub uninstall             # stop and remove services
```

The hub provides WebSocket-based routing (port 8443), store-and-forward for offline peers, Ed25519 challenge-response auth, and S2S federation between hubs. See the [Hub Operations Guide](docs/hub-operations.md).

---

## Standards References

HERMES design traces to established telecom, internet, and industry standards:

**IETF**:
RFC 768 (UDP), RFC 791 (IP), RFC 793 (TCP), RFC 1918 (Private Address Allocation), RFC 2119 (Requirement Levels), RFC 3022 (NAT), RFC 5322 (Internet Message Format), RFC 7231 (HTTP Semantics), RFC 7519 (JWT), RFC 8446 (TLS 1.3), RFC 8949 (CBOR), draft-rosenberg-ai-protocols (Framework for AI Protocols)

**3GPP**:
TS 23.214 (Control and User Plane Separation -- CUPS), TS 23.501 (5G System Architecture -- SBA), TS 29.244 (PFCP), TS 29.510 (NRF Discovery)

**ITU-T**:
X.200 (OSI Reference Model), Q.700 (SS7 Signaling), X.509 (PKI), E.164 (Numbering)

**IEEE**:
802.1Q (VLANs / Namespace Isolation), 802.3 (Ethernet / Bus Access), 1588 (Precision Time Protocol)

**Ecma International**:
ECMA-430 through ECMA-434 (NLIP -- Natural Language Interaction Protocol suite)

**Broadband Forum**:
TR-369 (USP -- User Services Platform), TR-181 (Device Data Model)

---

## Roadmap

HERMES follows a 5-phase evolution plan from file-based prototype to industry-grade protocol suite:

| Phase | Period | Focus |
|-------|--------|-------|
| **Phase 1** | Mar-Apr 2026 | Foundation hardening: documentation, CUPS split, payload evolution, A2A/MCP bridge spec, CI |
| **Phase 2** | May-Jun 2026 | Security & identity: Ed25519+PQC signing, DID-lite, JWT gateway auth |
| **Phase 3** | Jul-Aug 2026 | Efficiency & semantics: benchmarks with open data, CBOR encoding, TypeScript + Rust SDKs |
| **Phase 4** | Sep-Oct 2026 | Topology & social: adaptive topologies, attestation protocol, real-time extensions |
| **Phase 5** | Nov-Dec 2026 | v1.0 consolidation: IETF I-D submission, arXiv paper, Visual Agora, packages |

Full plan: **[docs/EVOLUTION-PLAN.md](docs/EVOLUTION-PLAN.md)**

---

## Project Structure

```
hermes/
├── spec/              # Formal standards (20 specs, 30 planned)
│   ├── ARC-0001.md    #   Architecture (meta-standard)
│   ├── ARC-0768.md    #   Datagram & Reliable Message Semantics
│   ├── ARC-0791.md    #   Addressing & Routing
│   ├── ARC-0793.md    #   Reliable Transport
│   ├── ARC-1918.md    #   Private Spaces & Firewall
│   ├── ARC-2119.md    #   Requirement Level Keywords
│   ├── ARC-2314.md    #   Skill Gateway Plane Architecture
│   ├── ARC-2606.md    #   Agent Profile & Discovery
│   ├── ARC-3022.md    #   Agent Gateway Protocol
│   ├── ARC-5322.md    #   Message Format
│   ├── ARC-0368.md    #   Agent Profile Format
│   ├── ARC-0369.md    #   Agent Service Platform
│   ├── ARC-1122.md    #   Conformance Testing
│   ├── ARC-4601.md    #   Agent Node Protocol (Hub + S2S Federation)
│   ├── ARC-7231.md    #   Agent Semantics — Bridge Protocol
│   ├── ARC-8446.md    #   Encrypted Bus Protocol
│   ├── ARC-9001.md    #   Bus Integrity & Sequencing
│   ├── AES-2040.md    #   Agent Visualization Standard (DRAFT)
│   ├── ATR-G711.md    #   Payload Encoding & Wire Efficiency
│   ├── ATR-Q700.md    #   Out-of-Band Signaling
│   ├── ATR-X200.md    #   Reference Model
│   └── INDEX.md       #   Full standards index
├── docs/              # Guides and documentation
│   ├── ARCHITECTURE.md
│   ├── EVOLUTION-PLAN.md
│   ├── GETTING-STARTED.md
│   ├── POSITIONING.md
│   ├── USE-CASES.md
│   └── diagrams/      #   Visual documentation (11 Mermaid + 16 D2)
├── reference/python/  # Reference implementation (1500+ tests)
├── examples/          # Sample bus, routes, configs
├── CHANGELOG.md
├── CONTRIBUTING.md
└── LICENSE            # MIT
```

---

## Contributing

HERMES is built by and for the community. See [CONTRIBUTING.md](CONTRIBUTING.md) for:

- How to propose new standards (ARC/ATR/AES)
- Contributing code or documentation
- Adding implementations in new languages

---

## License

[MIT](LICENSE) -- Free as in freedom, free as in beer.
