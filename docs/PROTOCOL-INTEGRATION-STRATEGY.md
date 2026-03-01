# Protocol Integration Strategy for HERMES

> Expert analysis: how MCP, A2A, ACP, ANP, and AG-UI can be adopted at each HERMES layer — with alternatives, trade-offs, and a phased roadmap.

**Date**: 2026-03-01
**Status**: PROPOSAL
**Audience**: HERMES contributors, protocol designers, potential adopters

---

## Executive Summary

The AI agent protocol ecosystem has converged around five complementary standards, each solving a different layer of the problem:

| Protocol | Maintainer | Layer | Governance |
|----------|-----------|-------|------------|
| **MCP** | Anthropic → Linux Foundation (AAIF) | Context & Tools | Open (AAIF) |
| **A2A** | Google → Linux Foundation | Collaboration & Task Delegation | Open (LF) |
| **ACP** | IBM / BeeAI → Linux Foundation | Structured Communication | Open (LF) |
| **ANP** | Community (IETF draft) | Discovery & Networking | Open (IETF) |
| **AG-UI** | CopilotKit | Agent-to-User Interface | Open source |

HERMES is the only protocol that provides a **complete, file-based stack from L0 (storage) to L5 (social)**. Instead of competing with these protocols, HERMES can **adopt them strategically at specific layers** while preserving its core principles: file-based operation, namespace isolation, stateless sessions, human-in-the-loop, and sovereignty.

This document maps each external protocol to the HERMES layer where it adds the most value, presents alternatives for each integration point, and proposes a phased adoption roadmap.

---

## The Integration Thesis

```
                External Protocols              HERMES Layers
                ─────────────────              ─────────────

                ┌───────────┐
                │   AG-UI   │ ──────────────► L5  Social (Agora UI)
                └───────────┘                     + L4 (operator dashboard)
                ┌───────────┐
                │    ANP    │ ──────────────► L5  Social (Agora discovery)
                └───────────┘                     + L2 (dynamic routing)
                ┌───────────┐
                │    A2A    │ ──────────────► L4  Application (cross-agent tasks)
                └───────────┘                     + L5 (Agent Cards as profiles)
                ┌───────────┐
                │    ACP    │ ──────────────► L3  Transport (structured messaging)
                └───────────┘                     + L1 (rich content types)
                ┌───────────┐
                │    MCP    │ ──────────────► L4  Application (tool access)
                └───────────┘                     + L0 (resource exposure)
```

**Principle**: Adopt external protocols where they have clear advantages. Preserve HERMES primitives where file-based simplicity wins.

---

## Layer-by-Layer Analysis

### L0 — Physical (File System)

**Current state**: JSONL files on disk. `bus.jsonl`, `bus-archive.jsonl`, `routes.md`, namespace directories.

**Assessment**: This is HERMES's strongest differentiator. No external protocol operates at this layer — they all assume network transport. L0 should remain file-native.

#### Integration Opportunity: MCP as a Resource Bridge

MCP defines **Resources** — structured data that servers expose to clients. A HERMES namespace could expose its bus and configuration as MCP Resources, letting MCP-compatible agents read HERMES state through a standardized interface.

```
┌──────────────────────────────────────────────────────┐
│  HERMES Namespace (eng)                               │
│                                                      │
│  bus.jsonl ◄────► MCP Resource Server                │
│  config.md        (exposes bus as resource)           │
│  memory/          (exposes memory as resource)        │
│                                                      │
│  Agent (Claude Code) ◄──MCP──► Resource Server       │
│  "Read my pending bus messages via MCP"               │
└──────────────────────────────────────────────────────┘
```

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A: MCP Resource Bridge** | Wrap bus.jsonl as an MCP resource | Agents use standard MCP to read bus | Adds server process, breaks "no server" principle |
| **B: MCP-compatible file format** | Align HERMES message format with MCP resource schema | Native compatibility without servers | Format constraints may conflict with HERMES simplicity |
| **C: Keep L0 pure** | No external protocol at L0 | Preserves zero-infrastructure promise | MCP agents need custom HERMES adapter |

**Recommendation**: **Option C for core, Option A as optional adapter.** L0 is HERMES's identity. Adding a server breaks the core proposition. But an *optional* MCP Resource Server (a thin wrapper) could serve as a bridge for teams already invested in MCP.

**Candidate spec**: ARC-6455 (Real-Time Bus Extensions) — could define a MCP-compatible adapter as an extension.

---

### L1 — Frame (Message Format)

**Current state**: JSONL with 7 fields: `{ts, src, dst, type, msg, ttl, ack}`. Max payload: 120 chars. Human-readable.

**Assessment**: The format is intentionally minimal. But three protocols offer lessons for enriching it without losing simplicity.

#### Integration Options

| Option | From protocol | What it adds | Trade-off |
|--------|--------------|-------------|-----------|
| **A: JSON-LD metadata** | ANP | Semantic annotations on messages. Agents can reason about message meaning, not just content. Add an optional `@context` field | Adds complexity. Most intra-clan messages don't need semantics |
| **B: MIME content types** | ACP | Support for typed payloads beyond plain text: `text/plain`, `application/json`, `image/png` reference | Enriches cross-namespace data sharing. Breaks 120-char simplicity |
| **C: Message intent types** | ACP | Extend `type` field to include structured intent: `request`, `proposal`, `inform`, `confirm`, `reject` | Richer bus semantics. Maps well to ACP performatives |
| **D: Keep current format** | — | Minimal, human-readable, proven | External protocols need translation layer |

**Recommendation**: **Option C (message intent types) for Phase 2, Option A (JSON-LD) for L5 Agora messages only.**

The current 6 message types (`state`, `alert`, `event`, `request`, `data_cross`, `dispatch`) already cover most intra-clan needs. But ACP's structured intent model (request/propose/inform/confirm) would enrich inter-clan (Agora) communication without changing the intra-clan format.

**Proposed evolution**:

```
Phase 0 (current):  type: "request" | "state" | "alert" | "event" | "data_cross" | "dispatch"

Phase 2 (proposed): type: "request" | "state" | "alert" | "event" | "data_cross" | "dispatch"
                         | "propose" | "confirm" | "reject" | "inform"
                                       ↑ ACP-inspired additions for Agora messages

Phase 3 (proposed): For Agora messages only, add optional "@context" for JSON-LD compatibility
                    {"ts":"...","src":"gateway","dst":"*","type":"propose",
                     "msg":"AGORA:quest from nakama-crew",
                     "@context":"https://hermes-protocol.org/v1/agora"}
```

**Candidate spec**: ARC-7231 (Agent Semantics) — already planned in research agenda L2.

---

### L2 — Network (Routing)

**Current state**: Static routing table (`routes.md`). Namespace → path → agents → tools. Star topology with controller at center.

**Assessment**: Static routing works for small deployments (<10 namespaces). Two external protocols offer compelling models for dynamic discovery.

#### Integration Options

| Option | From protocol | What it adds | Trade-off |
|--------|--------------|-------------|-----------|
| **A: Agent Cards** | A2A | Each namespace publishes a `agent.json` describing capabilities. Controller uses cards for intelligent routing | Adds discovery overhead. But enables dynamic namespace onboarding |
| **B: DID-based identity** | ANP | Namespaces identified by Decentralized Identifiers. Cryptographic verification of namespace identity | Strong identity model. But overkill for intra-clan (trust is implicit) |
| **C: ACP offline discovery** | ACP | Namespace metadata embedded in distribution packages. Enables routing decisions without running processes | Good fit for HERMES philosophy (offline-first). Less dynamic than Agent Cards |
| **D: Hybrid static+dynamic** | — | Keep `routes.md` for core routing. Add optional `capabilities.json` per namespace for intelligent dispatch | Best of both worlds. Adds one file per namespace |

**Recommendation**: **Option D (hybrid) for intra-clan, Option A (Agent Cards) for inter-clan.**

For intra-clan routing, static routes are sufficient and transparent. Adding a `capabilities.json` per namespace enables the controller to make smarter dispatch decisions without adding infrastructure.

For inter-clan (Agora), A2A Agent Cards are the emerging standard for agent discovery. Publishing HERMES clan profiles as A2A-compatible Agent Cards would give HERMES instant interoperability with the A2A ecosystem.

**Proposed evolution**:

```
Intra-clan (L2):
  routes.md (static)           ← unchanged
  [ns]/capabilities.json       ← NEW: ACP-inspired offline metadata
    {
      "namespace": "engineering",
      "capabilities": ["code-review", "ci-cd", "architecture"],
      "tools": ["github", "jira"],
      "availability": "ephemeral"
    }

Inter-clan (L5):
  /.well-known/agent.json      ← A2A Agent Card published by gateway
    {
      "name": "Clan Momosho-D",
      "url": "https://agora.hermes-protocol.org/momosho-d",
      "capabilities": [...],
      "authentication": {...}
    }
```

**Candidate specs**: ARC-2606 (Agent Profile & Discovery) — align with A2A Agent Card format. AES-802.1Q extension — add capabilities.json to namespace standard.

---

### L3 — Transport (Session Lifecycle)

**Current state**: SYN/FIN/ACK handshake. TTL-based expiry. At-least-once delivery via ACK array. Bus used only at session boundaries.

**Assessment**: This is one of HERMES's most innovative layers — designing for ephemeral agents. External protocols model persistent connections. But there are useful concepts to adopt.

#### Integration Options

| Option | From protocol | What it adds | Trade-off |
|--------|--------------|-------------|-----------|
| **A: A2A task lifecycle** | A2A | Map A2A task states to bus messages: `submitted` → `working` → `input-required` → `completed` / `failed` | Richer work tracking. Enables cross-protocol task bridging |
| **B: ACP async patterns** | ACP | Support fire-and-forget, request-response, and streaming patterns as bus message categories | Enriches transport semantics beyond SYN/FIN |
| **C: MCP capability negotiation** | MCP | At SYN time, agent announces its MCP capabilities. Bus records what tools each agent can use | Enables smarter dispatch (controller knows who can do what) |
| **D: Streaming bus** | AG-UI / ACP | For real-time workloads, support SSE/WebSocket streaming of bus events alongside file-based polling | Bridges gap for teams needing real-time coordination |

**Recommendation**: **Option A (A2A task lifecycle mapping) for Phase 2. Option D (streaming bus) for Phase 3.**

The A2A task lifecycle maps naturally to HERMES bus semantics:

```
A2A Task State          HERMES Bus Equivalent
─────────────          ──────────────────────
submitted              dispatch message (src: controller, dst: namespace)
working                state message ("task_xyz:in_progress")
input-required         request message (dst: controller, "need_input:...")
completed              state message ("task_xyz:completed")
failed                 alert message ("task_xyz:failed:reason")
```

This mapping doesn't change the bus format — it enriches the *convention* for how agents report task progress. An A2A bridge could translate between the two representations.

For streaming (Option D), this is the biggest architectural decision for HERMES evolution. File polling works for ephemeral sessions but fails for teams needing sub-second coordination. ARC-6455 (Real-Time Bus Extensions) should define an *optional* streaming layer that coexists with the file-based bus:

```
                    ┌───────────────────────┐
                    │    HERMES Transport    │
                    │                       │
                    │  ┌─────────────────┐  │
                    │  │  bus.jsonl       │  │  ← Primary (always available)
                    │  │  (file-based)    │  │     Append-only. Persistent.
                    │  └────────┬────────┘  │
                    │           │            │
                    │  ┌────────┴────────┐  │
                    │  │  SSE/WebSocket   │  │  ← Optional (ARC-6455)
                    │  │  (real-time)     │  │     Ephemeral. Low-latency.
                    │  └─────────────────┘  │     File is source of truth.
                    │                       │
                    └───────────────────────┘
```

**Candidate specs**: ARC-6455 (Real-Time Bus Extensions) — define streaming adapter. ARC-0793 revision — add task lifecycle conventions.

---

### L4 — Application (Agent Orchestration)

**Current state**: Agents read bus at SYN, do work in their namespace, write bus at FIN. Each namespace has its own tools, credentials, and memory.

**Assessment**: This is where external protocols add the most value. L4 is where agents *do things* — and MCP, A2A, ACP, and AG-UI each solve a piece of the orchestration puzzle.

#### The Four Integration Points

```
┌─────────────────────────────────────────────────────────────────┐
│  HERMES L4: Application Layer                                    │
│                                                                  │
│  ┌─────────────────────┐    ┌─────────────────────┐            │
│  │  WITHIN namespace   │    │  BETWEEN namespaces  │            │
│  │                     │    │                      │            │
│  │  MCP ← tool access  │    │  A2A ← task delegation│           │
│  │  (agent ↔ tools)    │    │  (namespace ↔ namespace)│         │
│  │                     │    │                      │            │
│  │  ACP ← agent comms  │    │  Bus ← signaling     │            │
│  │  (agent ↔ agent     │    │  (persistent state)  │            │
│  │   within namespace) │    │                      │            │
│  └─────────────────────┘    └─────────────────────┘            │
│                                                                  │
│  ┌─────────────────────────────────────────────────┐            │
│  │  HUMAN ↔ AGENT                                   │            │
│  │                                                  │            │
│  │  AG-UI ← operator dashboard, controller UI       │            │
│  │  (human-in-the-loop interface)                   │            │
│  └─────────────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

#### 4a: MCP as the Standard Tool Interface

**Current**: Each namespace defines its tools in `config.md` and agent definitions. No standard interface.

**Proposal**: Adopt MCP as the canonical way agents access tools within a namespace.

```
┌────────────────────────────────────┐
│  Namespace: engineering            │
│                                    │
│  Agent (Claude Code)               │
│    │                               │
│    ├──MCP──► GitHub MCP Server     │
│    ├──MCP──► Jira MCP Server       │
│    └──MCP──► CI/CD MCP Server      │
│                                    │
│  Firewall: ONLY these tools.       │
│  No tool from another namespace.   │
└────────────────────────────────────┘
```

**Value for HERMES**: The namespace firewall (ARC-1918) controls *which MCP servers* are available per namespace. This is a natural fit — MCP provides the tool interface, HERMES provides the isolation policy.

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A: MCP mandatory** | All namespace tools must be MCP servers | Full standardization. Any MCP agent works in any HERMES namespace | Excludes non-MCP tools. Forces migration |
| **B: MCP recommended** | MCP as the preferred tool interface. Non-MCP tools allowed | Gradual adoption. Preserves flexibility | Fragmented tooling within namespaces |
| **C: MCP adapter** | HERMES provides an MCP adapter that wraps existing namespace tools | Best migration path. No tool changes needed | Adds adapter complexity |

**Recommendation**: **Option B for Phase 2, moving toward A as MCP adoption grows.**

**Candidate spec**: AES-XXXX (Namespace Tool Interface Standard) — define how namespaces declare MCP servers and firewall rules per server.

#### 4b: A2A for Cross-Namespace Task Delegation

**Current**: Cross-namespace work happens through bus messages (dispatch → state → ack). Asynchronous, file-based, latency in minutes.

**Proposal**: For teams needing real-time cross-namespace task delegation, support A2A as a transport between namespace agents — while the bus remains the persistent coordination layer.

```
Real-time path (A2A):
  eng-agent ──A2A──► ops-agent    "Deploy v2.1 to staging"
                                   (immediate, bidirectional)

Persistent path (bus):
  {"src":"eng","dst":"ops","type":"dispatch","msg":"deploy_v2.1_staging"}
                                   (async, survives session death)
```

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A: A2A alongside bus** | Real-time tasks via A2A, persistent coordination via bus | Best of both worlds | Two transport mechanisms to maintain |
| **B: A2A replaces inter-ns bus** | All inter-namespace communication via A2A | Simpler mental model when agents are online | Loses persistence when agents are offline |
| **C: A2A at gateway only** | A2A used only for inter-clan (Agora) communication. Intra-clan stays file-based | Cleanest separation of concerns | No real-time intra-clan option |

**Recommendation**: **Option C for Phase 2 (A2A at gateway). Option A for Phase 3 (A2A alongside bus for teams that need it).**

The gateway (ARC-3022) is the natural point to bridge HERMES's file-based world with A2A's HTTP-based world. A clan's gateway could expose A2A-compatible endpoints for inter-clan tasks while keeping the internal bus file-based.

**Candidate spec**: ARC-3022 revision — add A2A endpoint specification to gateway.

#### 4c: ACP for Structured Agent Communication

**Current**: Bus messages use free-text `msg` field (max 120 chars). Semantics are implicit.

**Proposal**: Adopt ACP's performative model for agent-to-agent communication within and between namespaces.

ACP defines communication as **structured intent**:

| ACP Performative | HERMES Mapping | Example |
|-----------------|----------------|---------|
| `request` | `type: "request"` | "Review PR #147" |
| `propose` | *NEW*: `type: "propose"` | "Suggest we deploy Friday" |
| `inform` | `type: "state"` | "v2.1 deployed" |
| `confirm` | *NEW*: `type: "confirm"` | "Deployment approved" |
| `reject` | *NEW*: `type: "reject"` | "Deployment blocked: tests failing" |

**Value for HERMES**: Enriches bus semantics without changing the format. Controllers can reason about agent *intent*, not just message content.

**Recommendation**: **Adopt ACP performatives as optional extensions to the `type` field in Phase 2.**

**Candidate spec**: ARC-7231 (Agent Semantics) — define the extended type vocabulary.

#### 4d: AG-UI for the Human Operator Interface

**Current**: The human operator interacts with HERMES through file inspection and agent sessions. No standardized UI.

**Proposal**: Adopt AG-UI as the protocol between HERMES and human-facing interfaces (controller dashboard, Agora browser, namespace inspector).

```
┌────────────────────────────────────────────────────┐
│  Human Operator                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │  Dashboard (web app)                          │  │
│  │                                               │  │
│  │  Bus viewer │ Namespace status │ Agora browser│  │
│  └──────────────────────┬───────────────────────┘  │
│                          │                          │
│                     AG-UI Protocol                  │
│                          │                          │
│  ┌──────────────────────┴───────────────────────┐  │
│  │  HERMES Backend                               │  │
│  │                                               │  │
│  │  bus.jsonl reader │ namespace scanner │ gateway│  │
│  └──────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────┘
```

**Value for HERMES**: AG-UI provides the human-in-the-loop interface that HERMES explicitly requires but doesn't currently standardize. It would make the controller namespace accessible via a real-time dashboard.

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A: AG-UI for controller dashboard** | Build the operator interface using AG-UI events | Standard protocol for agent UX. Rich streaming UX | Adds web dependency for a file-based protocol |
| **B: Terminal-native UI (arena.py)** | Extend the existing ASCII interface | Stays file-native. No web dependency | Limited reach. Not accessible to non-technical operators |
| **C: Both** | AG-UI for web dashboard, terminal for power users | Maximum reach | Two UI codebases to maintain |

**Recommendation**: **Option C. Terminal-first (Phase 2), AG-UI web dashboard (Phase 3, aligned with L5c Visual Agora).**

**Candidate spec**: AES-2040 (Agent Visualization Standard) — define the AG-UI event mapping for HERMES state.

---

### L5 — Social (Agora)

**Current state**: Gateway (ARC-3022 DRAFT). Identity translation, outbound filtering, inbound validation, attestations, Resonance metric. TOFU trust model.

**Assessment**: L5 is where external protocols have the most to offer. The Agora needs discovery (ANP), interoperability (A2A), and identity (DID). But sovereignty must remain non-negotiable.

#### The Integration Map

```
┌──────────────────────────────────────────────────────────────┐
│  L5: AGORA (Inter-Clan Social Layer)                          │
│                                                              │
│  ┌──────────────────┐   ┌──────────────────┐                │
│  │  DISCOVERY        │   │  IDENTITY         │                │
│  │                   │   │                   │                │
│  │  ANP discovery    │   │  ANP DIDs         │                │
│  │  protocol         │   │  (upgrade from    │                │
│  │  (agent search,   │   │   TOFU to DID)    │                │
│  │   capability      │   │                   │                │
│  │   matching)       │   │  A2A Agent Cards  │                │
│  └──────────────────┘   │  (profile format)  │                │
│                          └──────────────────┘                │
│  ┌──────────────────┐   ┌──────────────────┐                │
│  │  COLLABORATION    │   │  USER INTERFACE   │                │
│  │                   │   │                   │                │
│  │  A2A task protocol│   │  AG-UI for Agora  │                │
│  │  (cross-clan      │   │  browser/explorer │                │
│  │   quest execution)│   │                   │                │
│  │                   │   │  A2UI for quest    │                │
│  │  ACP performatives│   │  results rendering│                │
│  │  (quest negotiation)│ │                   │                │
│  └──────────────────┘   └──────────────────┘                │
└──────────────────────────────────────────────────────────────┘
```

#### 5a: ANP for Agora Discovery and Identity

**Current**: Agora directory planned as Git-based. Clan identity via operator-chosen ID. TOFU trust.

**Proposal**: Adopt ANP's Decentralized Identifier (DID) model for clan identity and its discovery protocol for agent search.

| Aspect | Current (ARC-3022) | With ANP | Delta |
|--------|-------------------|----------|-------|
| Clan identity | Operator-chosen string | W3C DID (e.g., `did:web:agora.hermes:momosho-d`) | Cryptographic, portable, standards-compliant |
| Agent discovery | Browse Git directory | ANP agent description protocol + crawling | Scalable, searchable, AI-native |
| Trust bootstrapping | TOFU (SSH-like) | DID verification + optional TOFU fallback | Stronger initial trust. Preserves TOFU as fallback |
| Profile format | Custom YAML | ANP JSON-LD agent description | Semantic interoperability with the wider ANP ecosystem |

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A: Full ANP adoption at L5** | Use ANP for identity (DID), discovery, and agent descriptions in the Agora | Maximum interoperability. Proven identity model | Heavy dependency on external standard. Complexity increase |
| **B: DID for identity only** | Adopt DID for clan identity. Keep HERMES-native discovery | Strongest security upgrade. Minimal protocol change | Doesn't solve discovery scale |
| **C: ANP discovery + HERMES identity** | Use ANP's discovery protocol. Keep operator-chosen clan IDs with TOFU | Scales discovery. Preserves simplicity of clan setup | Clan IDs less portable, weaker verification |
| **D: Phased adoption** | Phase 2: DID for identity. Phase 3: ANP discovery. Phase 4: full JSON-LD profiles | Incremental risk. Each phase delivers standalone value | Slower to full interoperability |

**Recommendation**: **Option D (phased adoption).** Start with DID for clan keypairs (ARC-8446 already plans cryptographic upgrades), then add ANP discovery, then full JSON-LD profiles.

**Candidate specs**: ARC-3022 revision (DID support), ATR-X.500 (Directory Services — align with ANP discovery), ARC-2606 (Profile format — align with ANP agent descriptions).

#### 5b: A2A Agent Cards as Profile Format

**Current**: Agora profiles are custom YAML (defined in ARC-3022).

**Proposal**: Publish clan profiles as A2A-compatible Agent Cards. This makes every HERMES clan discoverable by A2A-compatible agents across the internet.

```json
// /.well-known/agent.json (A2A Agent Card format)
{
  "name": "Clan Momosho-D",
  "description": "Legal analysis, financial strategy, community governance",
  "url": "https://agora.hermes-protocol.org/clans/momosho-d",
  "provider": {
    "organization": "HERMES Agora"
  },
  "version": "0.2.0",
  "capabilities": {
    "streaming": false,
    "pushNotifications": false
  },
  "skills": [
    {
      "id": "property-law",
      "name": "Property Law Analysis",
      "description": "Legal review for property contracts and HOA governance"
    },
    {
      "id": "debt-strategy",
      "name": "Debt Restructuring Strategy",
      "description": "Financial analysis for debt optimization"
    }
  ],
  "authentication": {
    "schemes": ["did-auth"]
  },
  // HERMES extensions
  "x-hermes": {
    "protocol_version": "0.2.0",
    "clan_id": "momosho-d",
    "resonance": 47,
    "gateway_public_key": "ed25519:..."
  }
}
```

**Value**: Any A2A client in the ecosystem (Google ADK, Microsoft Copilot Studio, etc.) could discover HERMES clans. HERMES gains access to a massive existing ecosystem without building its own from scratch.

**Recommendation**: **Adopt A2A Agent Card format with `x-hermes` extensions for Phase 2.**

**Candidate spec**: ARC-2606 (Agent Profile & Discovery) — define as A2A Agent Card superset.

#### 5c: ACP Performatives for Quest Negotiation

**Current**: Quest proposals are unstructured messages through the gateway.

**Proposal**: Use ACP's performative model for the quest lifecycle:

```
Phase        ACP Performative    HERMES Mapping
─────        ────────────────    ──────────────
Proposal     REQUEST             gateway → operator: "AGORA:quest_proposal"
Negotiation  PROPOSE / COUNTER   gateway ↔ gateway: terms adjustment
Acceptance   CONFIRM             gateway → internal bus: "quest_accepted"
Execution    INFORM (progress)   state messages during quest work
Completion   INFORM (result)     gateway → external: filtered deliverable
Attestation  CONFIRM (review)    signed attestation via gateway
```

**Value**: Structured negotiation prevents ambiguity in cross-clan interactions. Maps cleanly to HERMES's existing bus message types.

**Recommendation**: **Adopt ACP performatives for quest lifecycle in Phase 2.**

**Candidate spec**: ARC-4861 (Cross-Clan Attestation Protocol) — include ACP-aligned quest negotiation.

---

## Comparative Decision Matrix

For each HERMES layer, the recommended external protocol adoption:

| HERMES Layer | Primary Protocol | Secondary | Not Recommended | Rationale |
|-------------|-----------------|-----------|-----------------|-----------|
| **L0 Physical** | *None* (stay file-native) | MCP (optional adapter) | A2A, ACP, ANP | File-based is HERMES's identity |
| **L1 Frame** | ACP (intent types) | ANP (JSON-LD for Agora) | A2A, AG-UI | ACP enriches semantics; ANP adds semantic web compatibility |
| **L2 Network** | A2A (Agent Cards) | ACP (offline metadata) | AG-UI | A2A cards for profiles; ACP's offline discovery fits HERMES |
| **L3 Transport** | A2A (task lifecycle) | ACP (async patterns) | MCP, ANP | Task states map well; async patterns enrich delivery |
| **L4 Application** | MCP (tool access) | A2A (cross-ns tasks), AG-UI (operator UI) | ANP | MCP is the de facto tool standard; AG-UI for human layer |
| **L5 Social** | ANP (discovery + DID) | A2A (Agent Cards), ACP (quest negotiation) | — | ANP scales Agora; A2A provides interop; ACP structures quests |

---

## Phased Roadmap

### Phase 2: Foundation Integrations (Q2 2026)

| Action | Layer | Protocol | Spec |
|--------|-------|----------|------|
| Add ACP performative types to bus message vocabulary | L1, L3 | ACP | ARC-7231 |
| Add `capabilities.json` per namespace | L2 | ACP-inspired | AES-802.1Q rev |
| Recommend MCP for namespace tool interfaces | L4 | MCP | AES-XXXX (new) |
| Publish Agora profiles as A2A Agent Cards | L5 | A2A | ARC-2606 |
| Define ACP-aligned quest negotiation lifecycle | L5 | ACP | ARC-4861 |

**Deliverables**: Updated specs, Python ref impl additions, example Agent Card.

### Phase 3: Network Integrations (Q3-Q4 2026)

| Action | Layer | Protocol | Spec |
|--------|-------|----------|------|
| Adopt DID for clan identity | L5 | ANP | ARC-3022 rev |
| Add ANP discovery protocol for Agora | L5 | ANP | ATR-X.500 |
| Optional A2A task delegation alongside bus | L3, L4 | A2A | ARC-6455 |
| Optional SSE/WebSocket streaming bus | L3 | AG-UI-inspired | ARC-6455 |
| Terminal operator dashboard | L4 | — | AES-2040 |

**Deliverables**: DID integration, discovery prototype, streaming bus adapter.

### Phase 4: Full Ecosystem (2027)

| Action | Layer | Protocol | Spec |
|--------|-------|----------|------|
| AG-UI web dashboard for operator/Agora | L4, L5 | AG-UI | AES-2040 |
| JSON-LD profiles for full semantic interop | L1, L5 | ANP | ARC-2606 rev |
| A2A gateway endpoints for cross-ecosystem tasks | L5 | A2A | ARC-3022 rev |
| Full PKI upgrade (post-quantum) | L5 | — | ARC-8446 |

**Deliverables**: Visual Agora (web), full interoperability bridge, v1.0 spec.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Protocol dependency** — external protocols change or get abandoned | HERMES features break | All integrations are *optional extensions*, never core requirements. HERMES must always work file-only |
| **Complexity creep** — adding too many protocols dilutes simplicity | Adoption barrier rises | Each integration must pass the "solo developer test": can one person use it without a DevOps team? |
| **Governance fragmentation** — MCP, A2A, ACP now under Linux Foundation; ANP under IETF | Conflicting standards | Monitor convergence. Prefer protocols with open governance and MIT/Apache licensing |
| **Performance overhead** — JSON-LD, DID verification, streaming add latency | Bus response time degrades | All heavy protocols are optional (L5 only). Core bus stays JSONL append |
| **Breaking the "no server" promise** — MCP, A2A, AG-UI require servers | Identity crisis | Clearly separate: *core HERMES = file-only*. Server-based protocols are *bridges/adapters*, never requirements |

---

## Guiding Principles for Integration

1. **File-first**: Every feature must work with files alone. External protocols are bridges, never foundations.

2. **Optional, never required**: No external protocol becomes a dependency. A HERMES deployment that ignores all external protocols must be fully functional.

3. **Sovereignty preserved**: No integration may expose internal bus, internal agent names, credentials, or Bounty metrics. The gateway remains the sole boundary.

4. **Human-in-the-loop maintained**: External protocol integrations (A2A tasks, ANP discovery, ACP negotiations) still require operator approval at clan boundaries.

5. **Adopt the format, not the runtime**: Where possible, adopt data formats (Agent Cards, DIDs, performative types) without adopting runtime dependencies (servers, registries, brokers).

6. **Test with one person**: Every integration must be testable by a solo developer on a laptop. If it requires a cluster, it's a Phase 4 feature, not Phase 2.

---

## Conclusion

HERMES doesn't need to become MCP, A2A, ACP, or ANP. It needs to **speak their languages at the right layers** while preserving what makes it unique: file-based operation, namespace isolation, ephemeral session design, and sovereignty-first architecture.

The recommended strategy is:

- **MCP** at L4 for tool access (the de facto standard, 97M+ monthly SDK downloads)
- **ACP** at L1/L3 for message semantics and structured intent (enriches bus without infrastructure)
- **A2A** at L2/L5 for profiles and inter-ecosystem interoperability (150+ orgs backing it)
- **ANP** at L5 for discovery and decentralized identity (IETF track, AI-native design)
- **AG-UI** at L4/L5 for human-agent interfaces (the missing UX layer)

The result: a HERMES that works solo on a laptop with zero infrastructure *and* integrates with the global agent ecosystem when the operator chooses to connect.

---

## References

### Protocol Specifications

- [MCP Specification (2025-11-25)](https://modelcontextprotocol.io/specification/2025-11-25)
- [A2A Protocol — GitHub](https://github.com/a2aproject/A2A)
- [ACP — Agent Communication Protocol](https://agentcommunicationprotocol.dev/)
- [ANP — Agent Network Protocol Specs](https://agentnetworkprotocol.com/en/specs/)
- [AG-UI — Agent User Interaction Protocol](https://docs.ag-ui.com/)

### Academic Surveys

- [A Survey of Agent Interoperability Protocols (arXiv:2505.02279)](https://arxiv.org/abs/2505.02279)
- [ANP Technical White Paper (arXiv:2508.00007)](https://arxiv.org/abs/2508.00007)
- [IETF Draft: Framework for AI Agent Networks](https://datatracker.ietf.org/doc/html/draft-zyyhl-agent-networks-framework-01)

### Industry Context

- [Google Developers Blog — Announcing A2A](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/)
- [IBM Research — Agent Communication Protocol](https://research.ibm.com/projects/agent-communication-protocol)
- [Anthropic — Donating MCP to Linux Foundation](https://www.anthropic.com/news/donating-the-model-context-protocol-and-establishing-of-the-agentic-ai-foundation)
- [Top AI Agent Protocols in 2026 — GetStream](https://getstream.io/blog/ai-agent-protocols/)

### HERMES Specifications

- [ARC-0001: Architecture](../spec/ARC-0001.md)
- [ARC-3022: Agent Gateway Protocol](../spec/ARC-3022.md)
- [ARC-1918: Private Spaces & Firewall](../spec/ARC-1918.md)
- [Research Agenda](RESEARCH-AGENDA.md)
