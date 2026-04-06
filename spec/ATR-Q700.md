# ATR-Q.700: Out-of-Band Signaling for AI Agent Coordination

| Field | Value |
|-------|-------|
| **Number** | ATR-Q.700 |
| **Title** | Out-of-Band Signaling for AI Agent Coordination |
| **Lineage** | Inspired by ITU-T Q.700 — Introduction to CCITT Signalling System No. 7 |
| **Status** | INFORMATIONAL |
| **Created** | 2026-02-28 |

## Abstract

This document describes the design philosophy behind HERMES as an out-of-band signaling system for AI agents. It draws a direct analogy to the Signalling System No. 7 (SS7) architecture in telecommunications, where signaling (call setup, routing, billing) travels on a separate network from voice traffic. In HERMES, the bus carries coordination signals between agents, while the agents themselves perform actual work entirely within their own namespaces. This separation is not incidental -- it is the core architectural decision that makes HERMES viable for stateless AI sessions.

This is an informational specification. It does not define new message types, data formats, or protocol behavior. It explains *why* HERMES is designed the way it is.

## 1. The SS7 Analogy

### 1.1 What SS7 Did for Telecom

Before SS7, telephone signaling traveled in-band: the same channel that carried your voice also carried the tones and pulses that set up the call. This created problems:

- **Fragility.** A clever user could whistle the right frequency and hijack call routing (the infamous 2600 Hz blue box hack).
- **Coupling.** Signaling capacity was limited by voice channel capacity.
- **Inflexibility.** Adding new signaling features meant modifying the voice path.

SS7 solved this by creating a completely separate signaling network. Voice traveled on one set of links; call setup, teardown, number portability, and billing traveled on another. The two networks referenced each other but never mixed traffic.

The results were transformative:

| Capability | In-Band (pre-SS7) | Out-of-Band (SS7) |
|-----------|-------------------|-------------------|
| Call setup speed | Seconds (pulse/tone propagation) | Milliseconds (packet-switched signaling) |
| Feature addition | Requires voice path changes | Independent signaling evolution |
| Security | Vulnerable to in-band spoofing | Signaling network is separate and controlled |
| Scalability | Limited by trunk capacity | Signaling scales independently |

### 1.2 What HERMES Does for AI Agents

HERMES applies the same separation principle to AI agent orchestration:

| SS7 Concept | HERMES Equivalent |
|------------|-------------------|
| Voice circuit | Agent performing work in its namespace (writing code, sending emails, analyzing data) |
| Signaling link | The Amaru bus (`bus.jsonl`) |
| Signaling Transfer Point (STP) | The controller/router that reads and dispatches bus messages |
| Signal Unit (SU) | A single JSONL message on the bus |
| Point Code (address) | Namespace identifier (`engineering`, `finance`, `operations`) |
| ISUP (call control) | `state`, `alert`, `event` messages |
| TCAP (transactions) | `request`, `data_cross` messages |
| OMAP (operations) | `dispatch`, `dojo_event` messages |

The bus does not carry the work. It carries signals *about* the work.

## 2. Control Plane vs. Data Plane

### 2.1 The Two Planes

HERMES defines a clean boundary between two planes of operation:

**Control Plane (Amaru bus):**
- State announcements: "The finance namespace completed its monthly report."
- Alerts: "Infrastructure costs exceeded the projected budget."
- Requests: "Engineering needs the Q4 expense breakdown from operations."
- Dispatch: "Assign the compliance agent to review the new policy."
- Events: "The deployment pipeline completed successfully."

**Data Plane (agent work):**
- Writing and reviewing code
- Sending emails
- Querying databases
- Generating reports
- Deploying services
- Any tool invocation via MCP servers

### 2.2 What Crosses the Boundary

The only thing that crosses from data plane to control plane is a *summary signal*. When an agent completes a task, it emits a bus message describing the outcome -- not the output itself.

```
DATA PLANE (engineering namespace):
  Agent runs test suite → 47 tests pass, 3 fail

CONTROL PLANE (bus message):
  {"src":"engineering","dst":"*","type":"state","msg":"test_suite_47pass_3fail_auth_module"}
```

The bus message does not contain the test output. It does not contain the code. It contains a signal that other namespaces can use to coordinate their own work.

### 2.3 Why This Matters

**If the bus carried actual work products**, it would become:
- A data store (requiring backup, versioning, access control)
- A bottleneck (large payloads slow down signaling)
- A security liability (sensitive outputs exposed to all namespaces)
- A coupling mechanism (consumers depend on the format of work products)

**Because the bus carries only signals**, it remains:
- Lightweight (each message is a single line of JSONL, under 200 bytes)
- Fast (reading the entire bus is a trivial file operation)
- Safe (no sensitive data transits the bus, per ARC-1918)
- Decoupled (namespaces only need to understand the signal format, not each other's work)

## 3. Why File-Based Signaling Works for AI Agents

### 3.1 The Stateless Session Problem

Modern AI coding agents (Claude Code, Cursor, Aider, etc.) operate in stateless sessions. Each invocation starts with a blank slate. The agent reads its context from files, does work, and exits. There is no persistent process, no daemon, no WebSocket connection.

This creates a coordination problem: how does one session know what another session decided?

### 3.2 Files as the Universal Bus

The answer is simple, perhaps deceptively so: use the filesystem.

Files have properties that make them ideal for inter-session signaling:

| Property | Value for Signaling |
|----------|-------------------|
| **Persistence** | Survives session termination. The bus outlives any single agent. |
| **Atomicity** | File writes are atomic on modern filesystems. A message is either written or not. |
| **Universality** | Every programming language, every OS, every AI agent can read and write files. |
| **Inspectability** | A human can open `bus.jsonl` in any text editor and understand the state of the system. |
| **Versioning** | Files can be tracked in git, providing a complete audit trail of all signaling. |
| **No infrastructure** | No message broker, no database, no server. Zero operational overhead. |

### 3.3 The SYN/FIN Protocol

HERMES leverages the stateless nature of AI sessions rather than fighting it:

```
Session Start (SYN):
  1. Agent reads bus.jsonl
  2. Filters for messages addressed to its namespace
  3. Displays pending signals to the human operator
  4. Human decides what to act on

Session End (FIN):
  1. Agent summarizes state changes from this session
  2. Writes new signals to bus.jsonl
  3. ACKs consumed messages
  4. Updates SYNC HEADER
```

This is not a workaround for the lack of persistent processes. It is a design that *embraces* the session model. Each session is a transaction: read signals, do work, write signals. The bus provides continuity across transactions.

### 3.4 Comparison with Alternatives

| Approach | Requires | Persistence | Inspectable | AI-Native |
|----------|----------|-------------|-------------|-----------|
| HERMES (file bus) | Filesystem | Yes | Yes (text editor) | Yes (file I/O is universal) |
| Message broker (Redis, RabbitMQ) | Running service | Configurable | Requires tooling | No (needs client library) |
| Database (SQLite, Postgres) | Running service or file | Yes | Requires queries | Partial |
| Shared memory / IPC | Running processes | No | No | No |
| HTTP webhooks | Running server | No | Partial (logs) | No |

HERMES optimizes for the constraints of AI agents: no persistent processes, file-based context loading, human-in-the-loop operation.

## 4. The ISP Model

### 4.1 Each Instance is an Autonomous System

In internet routing, an Autonomous System (AS) is a network under a single administrative authority that presents a unified routing policy to the outside world. ISPs are the canonical example: each ISP runs its own internal network however it sees fit, but peers with other ISPs through standard protocols (BGP).

An Amaru instance follows the same model:

```
HERMES Instance = Autonomous System

  Internal structure:
    - Namespaces (engineering, finance, operations)
    - Agents (skills scoped to namespaces)
    - Bus (internal signaling)
    - Firewall (access control)
    - Controller (routing decisions)

  External interface:
    - SYNC HEADER (announces internal state to peers)
    - Peering protocol (future: inter-instance bus exchange)
```

### 4.2 Internal Autonomy

Each HERMES instance is free to organize its namespaces however it wants:

- **A solo developer** might have `work`, `personal`, `finance`.
- **A small team** might have `backend`, `frontend`, `devops`, `design`.
- **An enterprise** might have `engineering`, `sales`, `legal`, `compliance`, `hr`.

The internal namespace structure is invisible to external peers. Only the SYNC HEADER -- a summary of current state -- is exposed.

### 4.3 Peering (Future Vision)

Just as ISPs exchange routing information through BGP, HERMES instances could exchange state through a peering protocol:

```
Instance A (Team Alpha):                Instance B (Team Beta):
  namespaces:                              namespaces:
    - backend                                - mobile
    - infrastructure                         - qa
    - security                               - release

  SYNC HEADER:                             SYNC HEADER:
    state: "API v2 deployed"               state: "Mobile build 47 ready for QA"

                    ┌──── Peering Bus ────┐
                    │  state signals only  │
                    │  no tools/creds/data │
                    └──────────────────────┘
```

### 4.4 Peering Rules (Proposed)

Drawing from BGP conventions:

1. **Peering is bilateral.** Both instances must explicitly agree to exchange signals.
2. **Only SYNC HEADER data crosses the peering boundary.** Internal bus messages stay internal.
3. **No transitive peering.** If A peers with B and B peers with C, A does not automatically see C's state.
4. **Each instance filters what it exports.** Not all internal state needs to be visible to peers.
5. **Peering carries no execution authority.** Instance A cannot dispatch agents in Instance B.

### 4.5 Why This Model Scales

The ISP model scales the internet to billions of devices because it:

- Hides internal complexity behind a simple external interface
- Allows each network to evolve independently
- Requires only minimal agreement at boundaries (routing protocol, address format)
- Fails gracefully (one AS going down does not cascade)

HERMES inherits these properties. A solo developer's instance and an enterprise team's instance can peer without either needing to understand the other's internal structure. The agreement surface is minimal: message format, SYNC HEADER schema, peering handshake.

## 5. Design Principles Summary

The following principles, derived from decades of telecom engineering, guide HERMES design:

### P1: Separate Signaling from Traffic
The bus carries signals about work, never the work itself. This is the foundational principle.

### P2: Embrace Statelessness
AI agent sessions are stateless. Rather than adding statefulness (daemons, databases), HERMES uses file-based persistence that aligns with how agents already operate.

### P3: Default Deny, Explicit Allow
Inspired by firewall design and codified in ARC-1918. No namespace has access to anything unless explicitly granted.

### P4: Human in the Loop
HERMES informs; humans decide. No automatic execution across namespace boundaries. This is a conscious design choice, not a limitation.

### P5: Minimal Agreement Surface
Namespaces agree on message format and bus location. Everything else is internal. Instances agree on SYNC HEADER schema and peering protocol. Everything else is internal.

### P6: Inspectable by Default
Every piece of HERMES state is a human-readable text file. No binary formats, no encoded blobs, no opaque databases. A human with a text editor can audit the entire system.

### P7: No Infrastructure Dependencies
HERMES runs on a filesystem. No servers, no databases, no message brokers, no cloud services. If you can read and write files, you can run HERMES.

## 6. Future Work

### 6.1 Inter-Instance Peering Protocol
A formal specification for HERMES instances exchanging state signals, including discovery, handshake, and export filtering. Expected lineage: ATR-Q.700 series (signaling network procedures).

### 6.2 Multi-Agent Concurrent Signaling
Handling the case where multiple agents within the same instance write to the bus simultaneously. File locking strategies, append-only guarantees, and conflict resolution.

### 6.3 Signal Compression
As bus history grows, a mechanism for compacting old signals into summary records without losing audit trail integrity.

### 6.4 Observability
Metrics and dashboards for bus throughput, signal latency (time between emission and ACK), and namespace activity patterns. Inspired by SS7 network management (OMAP).

## Acknowledgments

The Signalling System No. 7 architecture, standardized by ITU-T in the Q.700 series of Recommendations, provided the conceptual foundation for HERMES's out-of-band signaling model. The BGP-based ISP peering model informed the inter-instance communication design. The SDN control/data plane separation, formalized by the Open Networking Foundation, influenced the controller architecture described in ARC-1918.

The principle that protocols should be simple enough to implement from the spec document alone comes from the IETF tradition, particularly Jon Postel's RFC 760 and the ethos captured in the Robustness Principle.
