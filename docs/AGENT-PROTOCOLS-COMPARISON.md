# HERMES in the Agent Protocol Landscape

> Where does HERMES fit among MCP, A2A, ACP, and ANP — and what unique value does it bring?

## The Landscape at a Glance

The AI agent ecosystem is converging on four major protocols, each solving a different problem:

| Protocol | Created by | Problem it solves | Layer |
|----------|-----------|-------------------|-------|
| **MCP** (Model Context Protocol) | Anthropic | Give LLMs structured access to tools, data, and memory | Context |
| **A2A** (Agent-to-Agent Protocol) | Google | Let agents from different frameworks collaborate | Collaboration |
| **ACP** (Agent Communication Protocol) | BeeAI / IBM | Structure the intent of inter-agent messages | Communication |
| **ANP** (Agent Network Protocol) | Community (China-origin) | Discover and connect agents across distributed systems | Networking |

Each solves a real problem. None solves all of them. And critically, **none of them addresses the reality of how most AI agents actually operate today**: as stateless, ephemeral sessions that start, do work, and disappear — often on local machines, with no persistent server, no always-on process, and no guaranteed network connectivity.

That's where HERMES enters.

---

## What HERMES Is

**HERMES** (Heterogeneous Event Routing for Multi-agent Ephemeral Sessions) is a file-based communication protocol for coordinating AI agents across isolated workspaces. It is modeled on TCP/IP — a layered stack from physical storage (L0) to social networking (L5) — using nothing but plain text files.

```
┌─────────────────────────────────────────────────────────────────┐
│  L5  SOCIAL (Agora)     Inter-clan discovery, reputation, trust │
├─────────────────────────────────────────────────────────────────┤
│  L4  APPLICATION        Agent orchestration                     │
├─────────────────────────────────────────────────────────────────┤
│  L3  TRANSPORT          Session lifecycle (SYN/FIN/ACK/TTL)     │
├─────────────────────────────────────────────────────────────────┤
│  L2  NETWORK            Routing tables, namespace addressing    │
├─────────────────────────────────────────────────────────────────┤
│  L1  FRAME              JSONL message format                    │
├─────────────────────────────────────────────────────────────────┤
│  L0  PHYSICAL           File system (bus.jsonl)                 │
└─────────────────────────────────────────────────────────────────┘
```

No servers. No databases. No Docker. No cloud. Just files that any agent can read and write.

---

## Side-by-Side Comparison

### Scope and Architecture

| Dimension | MCP | A2A | ACP | ANP | HERMES |
|-----------|-----|-----|-----|-----|--------|
| **Primary unit** | Single model + tools | Multiple agents | Agent pairs | Agent network | Namespaces in a clan |
| **Transport** | JSON-RPC over stdio/HTTP | HTTP/SSE, JSON-RPC | HTTP, events | HTTP, DID-based | File system (JSONL) |
| **Requires server** | Yes (MCP server) | Yes (agent server) | Yes (runtime) | Yes (network nodes) | **No** |
| **Requires network** | Usually | Yes | Yes | Yes | **No** |
| **State model** | Stateful connection | Stateful tasks | Stateful sessions | Stateful registry | **Stateless sessions, persistent bus** |
| **Isolation model** | Server-scoped | Agent cards | Agent boundaries | Network auth | **Namespace firewalls (default-deny)** |
| **Spec count** | 1 spec | 1 spec | 1 spec | 1 spec | **30+ specs** (RFC-like process) |
| **Protocol layers** | 1 (context) | 1 (collaboration) | 1 (communication) | 1 (networking) | **6 layers** (L0-L5) |
| **Human-in-the-loop** | Tool approval | Optional | Optional | Optional | **By design at every boundary** |

### What Each Protocol Does Best

| Protocol | Strength | Analogy |
|----------|----------|---------|
| **MCP** | Gives a model structured awareness of its environment | "The senses" — what the agent can see and touch |
| **A2A** | Lets agents delegate tasks to each other across frameworks | "The org chart" — who reports to whom |
| **ACP** | Structures conversations between agents with intent types | "The language" — request vs. proposal vs. update |
| **ANP** | Enables agents to find and connect across distributed systems | "The phone book" — who exists and how to reach them |
| **HERMES** | Coordinates ephemeral agents across isolated domains via files | "The postal system" — persistent, sovereign, works offline |

---

## Five Ways HERMES Adds Unique Value

### 1. Infrastructure-Free Coordination

Every other protocol requires running services: MCP needs servers, A2A needs HTTP endpoints, ACP needs a runtime, ANP needs network nodes. HERMES requires **nothing but a file system**.

```
MCP:    Model ←→ MCP Server ←→ Tools/Data
A2A:    Agent ←→ HTTP Server ←→ Agent
ACP:    Agent ←→ Runtime ←→ Agent
ANP:    Agent ←→ Network Node ←→ Registry ←→ Agent

HERMES: Agent → bus.jsonl ← Agent
```

This isn't a limitation — it's a design choice. File-based means:
- **Works anywhere**: laptop, NAS, Git repo, USB drive, air-gapped systems
- **Zero ops**: no processes to keep running, no ports to open, no certificates to manage
- **Survives session death**: the bus persists even when every agent is offline
- **Git-native**: commit the bus alongside code, get full history for free

For solo developers, small teams, and offline-first workflows, this eliminates entire categories of infrastructure complexity.

### 2. Sovereignty and Isolation by Default

MCP, A2A, ACP, and ANP all assume agents **should** be able to reach each other. HERMES assumes the opposite: **namespaces are isolated by default** and crossing boundaries requires explicit rules + human approval.

```
┌─────────────────────────────────────────────────┐
│                   HERMES Instance                │
│                                                  │
│  ┌────────────┐          ┌────────────┐         │
│  │engineering │          │  finance   │         │
│  │ ✅ github  │  data    │  ✅ banking│         │
│  │ ❌ banking │ ─cross──►│  ❌ github │         │
│  └────────────┘  only    └────────────┘         │
│                                                  │
│  Default: DENY. Cross: explicit rule + approval. │
└─────────────────────────────────────────────────┘
```

This mirrors how real organizations work. An engineering agent shouldn't casually access the banking API. A personal finance agent shouldn't read your employer's Jira. HERMES enforces this structurally, not just by convention.

The other protocols offer authentication and authorization, but they don't provide **namespace-level isolation with a firewall model** as the default posture.

### 3. Designed for Ephemeral Agents

Modern AI agents — Claude Code, Cursor, Copilot, custom LLM pipelines — are **stateless sessions**. They start, they work, they vanish. Next time they run, they start from zero.

The other protocols assume agents are persistent processes with stable network addresses. HERMES assumes the opposite and designs for it:

```
Session Start (SYN)           Work Phase              Session End (FIN)
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ Read bus          │    │ Agent does work  │    │ Write state to   │
│ Filter by dst     │───►│ in its namespace │───►│ bus              │
│ Report pending    │    │                  │    │ ACK consumed msgs│
│ Flag stale (>3d)  │    │ Bus NOT used     │    │ Update SYNC HDR  │
└──────────────────┘    └──────────────────┘    └──────────────────┘
```

The bus is the persistent memory. Agents are transient. This is **TCP for ephemeral processes** — the handshake (SYN/FIN) ensures coordination survives agent lifetimes.

### 4. The Full Stack (L0–L5)

While MCP, A2A, ACP, and ANP each solve one layer, HERMES provides the **entire stack**:

```
                    MCP        A2A        ACP        ANP      HERMES
                   ─────      ─────      ─────      ─────    ────────
L5 Social                                                    ████████  Agora
   (discovery,                                               ████████  (Gateway,
    reputation,                          ┌───┐     ┌───┐     ████████   Resonance,
    trust)                               │   │     │███│     ████████   Attestations)
                                         └───┘     └───┘
L4 Application    ┌───┐     ┌───┐                            ████████  Agent
   (orchestration)│███│     │███│                             ████████  orchestration
                  └───┘     └───┘
L3 Transport                ┌───┐     ┌───┐                  ████████  SYN/FIN/ACK
   (delivery)               │███│     │███│                  ████████  TTL expiry
                            └───┘     └───┘
L2 Network                            ┌───┐     ┌───┐       ████████  Routing tables
   (addressing)                        │   │     │███│       ████████  Namespace addr.
                                       └───┘     └───┘
L1 Frame          ┌───┐     ┌───┐     ┌───┐                  ████████  JSONL format
   (format)       │███│     │███│     │███│                  ████████
                  └───┘     └───┘     └───┘
L0 Physical                                                  ████████  File system
   (storage)                                                 ████████
```

This isn't about replacing the other protocols — it's about having a **coherent, integrated stack** from storage to social layer, designed with the same principles (file-based, stateless, sovereign) at every level.

### 5. Inter-Clan Trust Without Surrendering Sovereignty

The Agora (L5) solves the same problem ANP tackles — agent discovery and networking — but with a fundamentally different trust model:

| Aspect | ANP / Other Protocols | HERMES Agora |
|--------|----------------------|--------------|
| Identity | Agents have network identities | Internal names hidden behind NAT-like gateway |
| Discovery | Central or distributed registry | Agora directory (Git-based, federated) |
| Trust | Authentication tokens, DID | TOFU + cryptographic attestations |
| Reputation | Platform-managed or none | **Dual**: private Bounty (internal) + public Resonance (external) |
| Data exposure | Capabilities + endpoints | **Only** what operator explicitly publishes |
| Default posture | Connect | **Isolate** (default-deny, gateway mediates) |

The dual reputation model is particularly unique:

```
INTERNAL (Clan only)              EXTERNAL (Agora)
┌─────────────────┐              ┌─────────────────┐
│     BOUNTY      │              │   RESONANCE     │
│                 │              │                 │
│  XP × precision │   Gateway   │  Σ attestations │
│  × impact       │─────────────│  × recency      │
│                 │  translates  │  × diversity    │
│  Computed by    │  but never   │                 │
│  operator       │  exposes     │  Computed from  │
│                 │  Bounty      │  external sigs  │
└─────────────────┘              └─────────────────┘
```

A clan can be highly capable internally (high Bounty) without revealing operational details. External clans judge based on Resonance — earned through cryptographically verified attestations from real collaborations, not self-reported claims.

---

## HERMES as Complement, Not Competitor

HERMES doesn't replace MCP, A2A, ACP, or ANP. It occupies a different niche and can work alongside them:

| Scenario | Protocol combination |
|----------|---------------------|
| **Agent needs tool access** | MCP provides the tool interface; HERMES coordinates which namespace the agent operates in and what tools it's allowed to use |
| **Agents collaborate across frameworks** | A2A handles the cross-framework delegation; HERMES provides the isolation model ensuring agents can't access unauthorized namespaces |
| **Agents negotiate a plan** | ACP structures the conversation; HERMES persists the outcome on the bus so the next ephemeral session knows what was decided |
| **Agents discover each other at scale** | ANP handles network-level discovery; HERMES Agora adds sovereignty (gateway filtering) and reputation (Resonance from attestations) |
| **Agents coordinate offline** | Only HERMES works here — file-based, no network required |

### Potential Integration Points

```
┌────────────────────────────────────────────────────────────┐
│                    HERMES Clan                              │
│                                                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                │
│  │ eng (ns) │  │ ops (ns) │  │ fin (ns) │                │
│  │          │  │          │  │          │                │
│  │ Uses MCP │  │ Uses MCP │  │ Uses MCP │  ← MCP for    │
│  │ for tools│  │ for tools│  │ for tools│    tool access │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                │
│       └──────────────┼──────────────┘                     │
│                      │                                     │
│               ┌──────┴──────┐                              │
│               │  bus.jsonl   │  ← HERMES for coordination  │
│               └──────┬──────┘                              │
│                      │                                     │
│            ┌─────────┴─────────┐                           │
│            │     GATEWAY       │  ← HERMES for sovereignty │
│            └────────┬──────────┘                           │
└─────────────────────┼──────────────────────────────────────┘
                      │
         ═════════════╪════════════════
                      │
               ┌──────┴──────┐
               │    AGORA    │  ← Could use A2A/ANP as
               │             │    transport for inter-clan
               └─────────────┘    communication
```

---

## When to Use What

| You need... | Use |
|-------------|-----|
| An LLM to call tools and access data | **MCP** |
| Persistent agents to delegate tasks across frameworks | **A2A** |
| Structured intent in agent conversations | **ACP** |
| Large-scale agent discovery on the open internet | **ANP** |
| Ephemeral agents to coordinate across isolated domains, offline-capable, with sovereignty | **HERMES** |
| All of the above, integrated into one stack | **HERMES** as the coordination spine + the others for their specialties |

---

## The Deeper Argument

The other protocols are designed for a world where agents are **services** — always running, network-connected, API-addressable. That world exists in enterprise deployments and cloud platforms.

But most AI agents today are **sessions** — a developer opens Claude Code, gets something done, closes it. A team member runs Cursor for an hour. Someone spins up a custom LLM pipeline, runs it, and kills it. These agents are ephemeral. They don't have stable addresses. They don't run servers. They work on local files.

HERMES is designed for this reality:
- **Ephemeral agents** → persistent bus
- **Local files** → no infrastructure
- **Isolated domains** → firewall by default
- **Human operators** → human-in-the-loop at every boundary
- **Independent teams** → sovereign clans with gateway protection

The protocols are **building blocks** that work together:

```
ANP     → How agents find each other across the internet
ACP     → How agents structure their conversations
A2A     → How agents delegate work to each other
MCP     → How agents access tools and context
HERMES  → How ephemeral agents coordinate across isolated
           domains with persistent state, sovereignty,
           and no infrastructure requirements
```

HERMES is TCP/IP for AI agents. The others are the applications that run on top.

---

## Related Documents

- [HERMES Architecture](ARCHITECTURE.md) — the 5-layer stack in detail
- [Use Cases](USE-CASES.md) — real-world deployment scenarios
- [Research Agenda](RESEARCH-AGENDA.md) — L1–L5 evolution roadmap
- [ARC-3022: Agent Gateway Protocol](../spec/ARC-3022.md) — inter-clan sovereignty
- [Quickstart Guide](QUICKSTART.md) — deploy HERMES in 5 minutes
