# HERMES Evolution Plan v1.0

> From file-based prototype to industry-grade agent communication framework.
> Approved by: Consejo Tripartito + Protocol Architect | Date: 2026-03-02

## Executive Summary

HERMES is a lightweight, file-based inter-agent communication protocol with 18 implemented specs (+ 1 INFO + 1 DRAFT) and 1267 tests. The agent communication landscape has matured rapidly (A2A, MCP, Ecma NLIP, IETF drafts, 3GPP SBA patterns). This plan evolves HERMES to integrate with — not compete against — these standards, while preserving its unique strengths: zero infrastructure, privacy-first, telecom rigor.

**Strategic position**: HERMES is a **dual-mode protocol** — **Sovereign** (file-based, self-hosted, zero infrastructure) and **Hosted** (managed Hub with SLAs). Both modes use the same wire format (ARC-5322), same privacy model (ARC-1918), same gateway-as-NAT (ARC-3022). It contributes telecom-inspired concepts (CUPS separation, Shannon constraints, dual trust metrics) to the broader agent protocol ecosystem.

---

## Industry Landscape (as of March 2026)

### Standards Bodies & Active Work

| Body | Relevant Work | HERMES Connection |
|------|--------------|-------------------|
| **IETF** | draft-rosenberg-ai-protocols (framework), draft-chang-agent-token-efficient (ADOL), draft-mpsb-agntcy-slim (gRPC+MLS), draft-goswami-agentic-jwt | Reference in ARC specs; potential I-D submission |
| **3GPP** | TS 23.214 (CUPS), TS 23.501 (5G SBA), TS 29.244 (PFCP), TS 29.510 (NRF) | CUPS split pattern; NRF for discovery; SBA for service interfaces |
| **Broadband Forum** | TR-369/USP, TR-181 (Device:2 Data Model) | Data model separation; CRUD+Operate+Notify pattern; transport independence |
| **Ecma International** | ECMA-430 to 434 (NLIP suite), TR/113 | First formal agent comm standard; envelope protocol pattern |
| **ITU-T** | OTAI initiative, SG17 Digital Identity, AI Standards Exchange | HERMES as case study; identity standards alignment |
| **IEEE** | PES Multi-Agent Systems WG, semantic interoperability | AES track alignment; FIPA heritage |
| **Linux Foundation** | AAIF (MCP, AGENTS.md, goose), LF AI&Data (A2A+ACP) | Gateway bridge specs; interoperability layer |

### Competing Protocols

| Protocol | Owner | Model | Transport | HERMES Differentiator |
|----------|-------|-------|-----------|----------------------|
| **MCP** | Anthropic/AAIF | Model-to-Tools (vertical) | stdio, Streamable HTTP | HERMES = agent-to-agent horizontal + zero-infra |
| **A2A** | Google/LF AI&Data | Agent-to-Agent (horizontal) | HTTP/2, JSON-RPC, gRPC, SSE | HERMES = file-based, no servers, private-first |
| **Ecma NLIP** | Ecma TC56 | Envelope protocol, multimodal | HTTP, WS, AMQP | HERMES = lighter, file-native, telecom rigor |
| **ANP** | Open-source | Discovery + DIDs | HTTP, JSON-LD | HERMES = production-deployable, not just discovery |
| **SLIM** | IETF draft | Real-time messaging | gRPC + MLS | HERMES = async-first, file-based, no gRPC dependency |
| **AGENTS.md** | OpenAI/AAIF | Project instructions | Markdown | Complementary — HERMES is protocol, AGENTS.md is config |

### HERMES Unique Value (What Nobody Else Does)

1. **Zero infrastructure** — works with `cat >> bus.jsonl`, no servers/Docker/cloud/internet
2. **File-based = auditable** — every message is git-versionable, reproducible, inspectable
3. **Telecom engineering rigor** — ARC/ATR/AES tracks, Shannon constraint, CUPS/SBA patterns
4. **Private-first** — ARC-1918 firewalls, gateway-as-NAT (ARC-3022), identity never exposed
5. **Dual metrics** — Bounty (internal) + Resonance (external) for trust decomposition
6. **Sovereignty without isolation** — clans connect via Agora without surrendering control
7. **Dual-mode** — Sovereign (file-based, self-hosted) and Hosted (managed Hub) using the same protocol. Like SMTP and Gmail.

---

## Phase 1: Foundation Hardening (March-April 2026)

**Goal**: Make existing specs industry-grade and the repo professionally presentable.

### 1.1 README & Documentation Overhaul

**Files**: `README.md`, `docs/POSITIONING.md` (new), `spec/INDEX.md`

- [x] Add ecosystem positioning section to README: "Where HERMES Fits"
  - Visual landscape map showing MCP (vertical), A2A (horizontal), HERMES (Sovereign + Hosted)
  - Explicit non-compete statement: HERMES complements, does not replace
- [x] Add badges: tests passing, Python version, license, spec count
- [x] Add "Standards References" section: formal citations to IETF RFCs, 3GPP TS, BBF TR, Ecma standards
- [x] Create `docs/POSITIONING.md`: technical white paper
  - HERMES dual-mode architecture: Sovereign (file-based) + Hosted (managed Hub)
  - Privacy-first: ARC-1918 firewalls, gateway-as-NAT
  - Gateway bridge to A2A/MCP
  - Research vehicle for telecom-inspired agent concepts
  - Formal references: TS 23.214, TS 23.501, TS 29.244, TR-369, ECMA-430, draft-rosenberg-ai-protocols
- [x] Update `spec/INDEX.md`: add "Industry Reference" column mapping each ARC/ATR/AES to its real-world standard body lineage AND modern equivalents

### 1.2 Formalize CUPS Split (Control Plane / User Plane)

**Specs affected**: ATR-X.200, ARC-0001

Inspired by 3GPP TS 23.214 (CUPS) and TS 29.244 (PFCP):

- [x] Add "Control Plane / User Plane Separation" section to ATR-X.200
  - **User Plane**: bus.jsonl (data forwarding, message transit)
  - **Control Plane**: routes.md, firewall rules, namespace config (policy, routing decisions)
  - Reference PFCP session model: CP establishes rules, UP executes them
- [ ] Document the mapping explicitly:

  | 3GPP CUPS | HERMES Equivalent |
  |-----------|-------------------|
  | SGW-C/PGW-C (Control) | Controller namespace + routes.md |
  | SGW-U/PGW-U (User) | bus.jsonl message forwarding |
  | PFCP Session | Namespace session (SYN/FIN) |
  | PDR (Packet Detection Rule) | Routing rule in routes.md |
  | FAR (Forwarding Action Rule) | Message type filter + dst routing |
  | Sx interface | Controller ↔ bus read/write interface |

### 1.3 Payload Limit Evolution

**Spec affected**: ARC-5322

The 120-char payload limit was a Shannon constraint for atomicity. Industry solved token-efficiency differently (IETF ADOL: schema dedup, adaptive fields). Evolution:

- [ ] Keep 120-char as RECOMMENDED default for signaling messages (preserves atomicity, human readability)
- [ ] Add `encoding` field to message format: `"encoding": "raw"` (default, 120-char) | `"cbor"` | `"ref"`
  - `raw`: current behavior, human-readable, 120-char limit
  - `cbor`: CBOR-encoded payload, no size limit, for bulk/structured data
  - `ref`: payload is a file path reference (for large payloads, binary data)
- [ ] This is backward-compatible: agents that don't recognize `encoding` treat as `raw`
- [ ] Reference IETF draft-chang-agent-token-efficient for rationale

### 1.4 Bridge Spec: Gateway ↔ A2A/MCP Mapping

**New spec**: ARC-7231 (Agent Semantics) — repurposed to include interop

- [ ] Define A2A Agent Card ↔ HERMES Profile (ARC-2606) field mapping:

  | A2A Agent Card Field | HERMES Profile Field | Notes |
  |---------------------|---------------------|-------|
  | `name` | `alias` | Public name |
  | `description` | `description` | Free text |
  | `url` | — | HERMES is file-based; gateway publishes |
  | `capabilities` | `capabilities` (ontology) | Map A2A skills to HERMES capability tree |
  | `authentication` | Gateway auth config | TOFU → OAuth upgrade path |

- [ ] Define MCP Tool ↔ HERMES Agent Capability mapping:
  - MCP `tools[]` → HERMES `capabilities[]` with `type: "tool"` extension
  - MCP `resources[]` → HERMES namespace read permissions
  - MCP `prompts[]` → HERMES message templates

- [ ] Define translation flow: Gateway receives A2A JSON-RPC → translates to HERMES JSONL → routes internally → response translated back
- [ ] Reference: 3GPP SBA pattern (TS 23.501) where NFs expose services via standardized interfaces (HTTP/2 REST) — gateway does the same for HERMES agents

### 1.5 Test & CI Hardening

- [x] Add GitHub Actions CI: pytest on push/PR, Python 3.10-3.13 matrix
- [x] Add `pyproject.toml` classifiers for PyPI readiness
- [ ] Add code coverage badge (target: 90%+)
- [ ] Create conformance test suite: `tests/conformance/` — validates any implementation against spec

**Phase 1 Deliverables**:
- Professional README with ecosystem positioning
- `docs/POSITIONING.md` white paper
- CUPS split formalized in ATR-X.200
- Payload encoding extension in ARC-5322
- A2A/MCP bridge mapping in ARC-7231
- CI pipeline + badges

---

## Phase 2: Security & Identity (May-June 2026)

**Goal**: Replace TOFU with real cryptographic identity, aligned with industry standards.

### 2.1 ARC-8446: Encrypted Bus Protocol

Inspired by RFC 8446 (TLS 1.3) + NIST PQC (FIPS 203-205) + IETF draft-goswami-agentic-jwt:

- [ ] Define message signing scheme for JSONL:
  - `sig` field appended to message JSON (detached signature)
  - Ed25519 as MUST (fast, small, proven); Dilithium as SHOULD (PQC-ready)
  - Signature covers: `ts + src + dst + type + msg` (canonical form)
- [ ] Define clan keypair lifecycle:
  - Generation: `hermes keygen` CLI command
  - Storage: `~/.hermes/keys/` (private), published via gateway profile (public)
  - Rotation: annual, with overlap period for verification
- [ ] Design key discovery: gateway publishes public key in ARC-2606 profile
- [ ] Reference: ECMA-434 (NLIP Agent Security Profiles) for security level taxonomy:
  - Level 0: No security (current default, development only)
  - Level 1: Message signing (integrity, non-repudiation)
  - Level 2: Payload encryption (confidentiality)
  - Level 3: Channel encryption + mutual auth (full security)
- [x] Prototype: Python `hermes.crypto` module — sign/verify using Ed25519 (cryptography lib)

### 2.2 ATR-X.509: Agent Identity Certificates

Inspired by ITU-T X.509 + W3C DIDs + IETF draft-goswami-agentic-jwt:

- [ ] Define agent identity document:
  - Clan ID (namespace), Agent alias (public), Capabilities, Public key, Expiry
  - Format: JSON (human-readable) with optional CBOR encoding
- [ ] Evaluate DID-lite: simplified W3C DID document for agents
  - `did:hermes:<clan-id>:<agent-alias>` — resolvable via Agora directory
  - Lighter than full DID infrastructure; interoperable with ANP
- [ ] Define trust chain: Root (Agora directory) → Clan cert → Agent cert
- [ ] Reference: 3GPP TS 29.510 (NRF) OAuth 2.0 token model for agent auth between clans

### 2.3 ARC-7519: Message Authentication (JWT Integration)

- [ ] Define Agentic JWT profile for HERMES:
  - Claims: `iss` (clan), `sub` (agent), `aud` (target clan/agent), `cap` (capabilities), `exp`
  - Reference: IETF draft-goswami-agentic-jwt-00
- [ ] Use for gateway-to-gateway authentication during cross-clan operations
- [ ] Backward compatible: JWT auth is OPTIONAL; unsigned messages still work in Phase 0 mode

**Phase 2 Deliverables**:
- ARC-8446 spec + Python crypto module
- ATR-X.509 spec with DID-lite
- ARC-7519 JWT integration spec
- All specs reference NIST, IETF, ITU-T, Ecma standards

---

## Phase 3: Efficiency & Semantics (July-August 2026)

**Goal**: Prove HERMES efficiency claims with data; design compressed agent language.

### 3.1 L3: Channel Efficiency Model (ATR-G.711 → ATR-CE)

- [x] Benchmark: HERMES file-based vs HTTP/TCP for agent communication
  - TCP handshake (3-way) + TLS 1.3 (1-2 RTT) + HTTP headers (~500B) + JSON body
  - vs. HERMES: 1 syscall (file append), ~200B JSON, no network stack
  - Model energy per message (Joules) using published CPU/storage benchmarks
- [ ] Use open datasets:
  - Ookla Open Data (`s3://ookla-open-data/`) for real-world latency baselines
  - M-Lab NDT (`measurement-lab.ndt.*`) for throughput measurements
  - CAIDA topology for inter-node modeling
- [ ] Publish as reproducible Jupyter notebook in `research/L3/`
- [ ] Scale analysis: at what agent count does file-bus bottleneck vs HTTP API?
- [ ] Reference: Broadband Forum TR-181 data model efficiency patterns

### 3.2 L2: Agent Communication Language (ARC-7231)

- [ ] Catalog all HERMES message patterns from bus-archive + real deployments
- [ ] Design dual-mode encoding:
  - **Mode A (text)**: Current JSON, human-readable, for development/debug
  - **Mode B (binary)**: CBOR (RFC 8949) encoding, for production/high-throughput
- [ ] Compression benchmarks: JSON vs CBOR vs MessagePack vs Protobuf
  - Target: 50%+ payload reduction in Mode B vs Mode A
- [ ] Define capability ontology encoding (from ARC-2606):
  - 9 top-level domains compressed to 4-bit codes
  - Hierarchical path compressed via shared prefix table
- [ ] Reference: FIPA ACL performatives + BBF TR-369/USP CRUD+Operate+Notify pattern:

  | BBF USP Operation | HERMES Message Type | Description |
  |-------------------|---------------------|-------------|
  | Get | `query` | Read agent state |
  | Set | `state` | Update agent state |
  | Add | `event` (type: create) | Register new entity |
  | Delete | `event` (type: remove) | Deregister entity |
  | Operate | `dispatch` | Invoke agent capability |
  | Notify | `alert` | Async notification |

### 3.3 Multi-Language SDK Foundation

- [ ] Define conformance test suite as language-agnostic YAML (input → expected output)
- [ ] TypeScript SDK: `reference/typescript/` — message, bus, sync modules
- [ ] Rust SDK: `reference/rust/` — for embedded/IoT agent scenarios
- [ ] All SDKs validate against same conformance tests

**Phase 3 Deliverables**:
- L3 efficiency paper + Jupyter notebook with reproducible benchmarks
- ARC-7231 dual-mode encoding spec
- TypeScript + Rust reference implementations
- Conformance test suite (YAML-based, language-agnostic)

---

## Phase 4: Topology & Social Layer (September-October 2026)

**Goal**: Scale beyond single-machine; enable inter-clan collaboration.

### 4.1 L4: Adaptive Topology (AES-802.1Q Extended)

- [ ] Define topology tiers:
  - **Micro** (<10 agents): Star topology (current, controller hub)
  - **Small** (10-50): Hierarchical star (regional controllers, inspired by 3GPP RAN hierarchy)
  - **Medium** (50-500): Mesh with SDN controller (reference: OpenFlow, 3GPP SBA NRF)
  - **Large** (500+): Federated mesh (reference: BGP RFC 4271, 3GPP inter-PLMN roaming)
- [ ] Topology negotiation protocol: agents discover optimal topology via bus signaling
- [ ] Reference: 3GPP TS 23.501 Section 4.2.6 (NF discovery and selection) for dynamic service discovery in mesh

### 4.2 L5b: Attestation + Resonance (ARC-4861)

- [ ] Attestation format: signed JSON with `from_clan`, `to_clan`, `agent`, `quest_id`, `ratings`, `summary`
- [ ] Resonance formula: `R(a) = sum(score * recency_weight * diversity_bonus)` per attestation
- [ ] Anti-Sybil: minimum clan age (30 days) + minimum internal activity before external attestation
- [ ] Simulate: EigenTrust vs PageRank vs Bayesian models with synthetic data
- [ ] Reference: IETF draft-rosenberg-ai-protocols Section 4 (trust and delegation patterns)

### 4.3 Real-Time Extensions (ARC-6455)

- [ ] Define WebSocket/SSE bridge for real-time bus monitoring
- [ ] File-watcher mode: `inotify`/`FSEvents` → SSE stream for web clients
- [ ] Reference: A2A's SSE streaming pattern; MCP's Streamable HTTP transport
- [ ] This is OPTIONAL — file-based polling remains the default

**Phase 4 Deliverables**:
- Adaptive topology spec (AES-802.1Q extended)
- Attestation protocol (ARC-4861) + Resonance calculator
- Real-time extensions spec (ARC-6455) + prototype
- Simulation notebooks for topology + reputation models

---

## Phase 5: Consolidation & Publication (November-December 2026)

**Goal**: HERMES v1.0 — a complete, citable, implementable protocol suite.

### 5.1 Spec Consolidation

- [ ] All Core tier specs: IMPLEMENTED status with reference impl + conformance tests
- [ ] All Security tier specs: at least DRAFT with prototype
- [ ] Cross-reference matrix: every spec cites which industry standards it relates to
- [ ] Formal ABNF/JSON Schema for all message formats (machine-parseable)

### 5.2 Industry Engagement

- [ ] Submit HERMES concepts as IETF Internet-Draft:
  - Title: "File-Based Agent Communication: A Zero-Infrastructure Protocol for AI Agent Coordination"
  - Focus: CUPS split for agents, gateway-as-NAT pattern, dual trust metrics
  - Reference: draft-rosenberg-ai-protocols as framework, HERMES as instance
- [ ] Submit to ITU-T OTAI as case study for open telecom agent protocol
- [ ] Publish L3 efficiency paper to arXiv (reproducible, with open datasets)
- [ ] Engage with AAIF: propose HERMES gateway bridge as interop layer for MCP/A2A

### 5.3 Agent Visualization Standard (AES-2040)

AES-2040 defines a 5-layer visualization stack and the Protocol Explorer:

- [x] **Layer 1** (ASCII art): Inline spec examples — active since Phase 0
- [x] **Layer 2** (Mermaid): 13 diagrams in `docs/diagrams/` — implemented Phase 1
- [ ] **Layer 3** (D2): Animated protocol flow diagrams for presentations and desktop app
- [ ] **Layer 4** (Excalidraw): Community collaboration templates
- [ ] **Layer 5** (Protocol Explorer): Interactive browser-based agent trace tool
  - 6 visualization modes: Message Flow, Session Timeline, Cross-Clan Path, Crypto Envelope, Dispatch Tree, Bus Health
  - Connects to Agent Node (ARC-4601) via SSE or reads bus.jsonl directly
  - Zero-server SPA (Svelte + D3.js), deployable on GitHub Pages
  - No equivalent exists for agent-to-agent protocols (gap in the market)
- [ ] Visual Agora: static site reading clan profiles → card-based directory with Resonance scores

### 5.4 HERMES v1.0 Release

- [ ] Version bump: v1.0.0
- [ ] Complete documentation suite (positioning, architecture, quickstart, all specs)
- [ ] PyPI package: `pip install hermes-protocol`
- [ ] npm package: `npm install @hermes-protocol/core`
- [ ] Crates.io: `hermes-protocol`
- [ ] Announcement: GitHub release + blog post + social

**Phase 5 Deliverables**:
- HERMES v1.0 spec suite (all core specs IMPLEMENTED)
- IETF Internet-Draft submission
- ITU-T OTAI case study
- arXiv paper (L3 efficiency)
- Visual Agora prototype
- Packages on PyPI, npm, crates.io

---

## Cross-Phase: Standards Reference Matrix

Every HERMES spec MUST cite its industry lineage. This matrix tracks the mapping:

| HERMES Spec | Primary Lineage | Modern Equivalents | Standards Body |
|-------------|----------------|-------------------|----------------|
| ARC-0001 | Original | draft-rosenberg-ai-protocols (IETF) | IETF |
| ARC-0768 | RFC 768 (UDP) | A2A stateless interactions | IETF |
| ARC-0791 | RFC 791 (IP) | ANP discovery; 3GPP NRF (TS 29.510) | IETF, 3GPP |
| ARC-0793 | RFC 793 (TCP) | MCP Streamable HTTP; A2A task lifecycle | IETF |
| ARC-1918 | RFC 1918 | 3GPP network slicing (TS 23.501 §5.15) | IETF, 3GPP |
| ARC-2606 | RFC 2606 | A2A Agent Cards; ANP capability files | IETF, Google |
| ARC-3022 | RFC 3022 (NAT) | 3GPP CUPS (TS 23.214); BBF TR-369 gateway | IETF, 3GPP, BBF |
| ARC-5322 | RFC 5322 (IMF) | ECMA-430 (NLIP); IETF ADOL | IETF, Ecma |
| ARC-7231 | RFC 7231 | BBF TR-369 CRUD+Operate+Notify; FIPA ACL | IETF, BBF, IEEE |
| ARC-7519 | RFC 7519 (JWT) | draft-goswami-agentic-jwt (IETF) | IETF |
| ARC-8446 | RFC 8446 (TLS) | ECMA-434 security profiles; SLIM MLS | IETF, Ecma |
| ATR-X.200 | X.200 (OSI) | 3GPP SBA (TS 23.501); CUPS (TS 23.214) | ITU-T, 3GPP |
| ATR-X.509 | X.509 | W3C DIDs; draft-goswami-agentic-jwt | ITU-T, W3C, IETF |
| ATR-Q.700 | Q.700 (SS7) | 3GPP PFCP (TS 29.244); SIP (RFC 3261) | ITU-T, 3GPP |
| AES-802.1Q | 802.1Q | 3GPP network slicing | IEEE, 3GPP |
| AES-2040 | Original | Agora visual layer | — |

---

## Principles (Non-Negotiable)

1. **Complement, don't compete** — HERMES bridges to A2A/MCP, doesn't replace them
2. **File-based always works** — Phase 0 JSONL mode is never deprecated
3. **Reference real standards** — every spec cites IETF, 3GPP, ITU-T, IEEE, Ecma as applicable
4. **Backward compatible** — new features are OPTIONAL extensions, never breaking changes
5. **Reproducible** — benchmarks use public datasets, scripts in repo, results verifiable
6. **Lightweight first** — complexity only if it reduces measured overhead
7. **Human approval** — Daniel approves every spec, every push, every publication
8. **1 developer reality** — scope to what 1 person can build well, not what a foundation can staff

---

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Scope creep (30 planned specs) | Focus on 15 strategic specs, defer rest to community |
| Ecosystem moves faster than HERMES | Bridge specs (Phase 1.4) ensure relevance regardless |
| Single point of failure (1 dev) | Open-source + clear contributing guide + conformance tests |
| Academic paper rejected | Publish to arXiv first (no review gate), iterate |
| No adoption | Position as research contribution, not product — value is in the ideas |
| Burnout | Artemisa protocol: 1 phase per 2 months, no more |

---

## Success Metrics

| Metric | Target (v1.0) |
|--------|---------------|
| Specs implemented | 18+ (from current 11) |
| Tests passing | 400+ (from current 214) |
| Reference implementations | 3 languages (Python, TypeScript, Rust) |
| Industry references cited | 30+ formal standards |
| GitHub stars | 100+ (organic, no marketing) |
| External contributors | 3+ |
| IETF I-D submitted | 1 |
| arXiv paper | 1 |
| Packages published | PyPI + npm + crates.io |

---

*"The same way TCP/IP created an open internet, HERMES aims to create an open network for AI agent coordination — not by replacing what exists, but by bridging what's missing."*

---

Consejo Tripartito + Protocol Architect
March 2, 2026
