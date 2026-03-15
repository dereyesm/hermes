# SEQ-2314: CUPS Triple-Plane Quest Dispatch

> How a quest flows through the three planes: Control (Messenger), Orchestration (Dojo), and User (Skills).

Inspired by 3GPP CUPS (Control and User Plane Separation). Each plane has a distinct responsibility and clear boundaries.

## Actors

| Actor | Role | Plane | Spec Reference |
|-------|------|-------|----------------|
| **Messenger** | Routes messages, handles discovery | Control Plane (CP) | ARC-2314 Section 4 |
| **Dojo** | Dispatches quests, manages skill roster | Orchestration Plane (OP) | ARC-2314 Section 5 |
| **Skill** | Executes actual work | User Plane (UP) | ARC-2314 Section 6 |
| **Bus** | Shared transport | Transport | ARC-5322 |
| **Remote Clan** | External clan (via Gateway) | External | ARC-3022 |

## Sequence Diagram

```mermaid
sequenceDiagram
    participant RC as Remote Clan<br/>(via Gateway)
    participant M as Messenger<br/>(Control Plane)
    participant BUS as Bus<br/>(bus.jsonl)
    participant D as Dojo<br/>(Orchestration Plane)
    participant S as Skill<br/>(User Plane)
    participant H as Human<br/>(approver)

    Note over RC,H: Phase 1: Inbound Request (CP)

    RC->>M: Cross-clan quest proposal<br/>via Gateway (ARC-3022)
    M->>M: Validate message (ARC-5322)
    M->>M: Apply inbound firewall (ARC-1918)
    M->>BUS: Write request to bus<br/>[CID:quest-42]

    Note over RC,H: Phase 2: Quest Dispatch (OP)

    D->>BUS: Read bus (SYN phase)
    BUS-->>D: Pending request [CID:quest-42]
    D->>D: Parse quest requirements:<br/>needed capabilities, urgency
    D->>D: Search skill roster:<br/>match capabilities, check XP,<br/>check availability

    alt No matching skill
        D->>BUS: Write alert: "No skill matches"
        D-->>H: Escalate to human
    else Skill matched
        D-->>H: "Matched: cybersec-architect.<br/>Approve dispatch?"
        H->>D: Approved

        D->>BUS: Write dispatch message<br/>dst=cybersec-architect<br/>[CID:quest-42-dispatch]
    end

    Note over RC,H: Phase 3: Execution (UP)

    S->>BUS: Read bus (SYN)
    BUS-->>S: Dispatch [CID:quest-42-dispatch]
    S->>S: Execute work with guardrails:<br/>max_turns, timeout, tool allowlist
    S->>S: Produce deliverable

    alt Success
        S->>BUS: Write result<br/>[RE:quest-42-dispatch]<br/>type=event
    else Failure
        S->>BUS: Write alert<br/>DISPATCH_FAILED
    end

    Note over RC,H: Phase 4: Result Flow (UP → OP → CP)

    D->>BUS: Read result [RE:quest-42-dispatch]
    D->>D: Evaluate: quality, XP award
    D->>D: Update skill XP + leaderboard
    D->>BUS: Write response<br/>[RE:quest-42]<br/>type=state

    M->>BUS: Read response [RE:quest-42]
    M->>M: Outbound filter check
    M->>M: NAT translate (internal → external)
    M->>RC: Forward response via Gateway

    Note over RC,H: Phase 5: Attestation (both clans)

    RC-->>M: Attestation: quality, reliability, collaboration
    M->>BUS: Write attestation event
    D->>D: Update Resonance score
```

## Three-Plane Architecture

```mermaid
flowchart TB
    subgraph CP ["Control Plane (Messenger)"]
        direction LR
        CP1[Route messages]
        CP2[Discovery / Agora]
        CP3[Firewall / NAT]
        CP4[Session mgmt]
    end

    subgraph OP ["Orchestration Plane (Dojo)"]
        direction LR
        OP1[Quest dispatch]
        OP2[Skill roster]
        OP3[Backlog / priority]
        OP4[XP / governance]
    end

    subgraph UP ["User Plane (Skills)"]
        direction LR
        UP1[Execute work]
        UP2[Produce deliverables]
        UP3[Report results]
    end

    CP -->|"delivers instructions"| OP
    OP -->|"dispatches work"| UP
    UP -->|"returns results"| OP
    OP -->|"sends responses"| CP

    style CP fill:#1a3a5c,color:#fff
    style OP fill:#3a1a5c,color:#fff
    style UP fill:#1a5c3a,color:#fff
```

## Key Design Points

- **Separation of concerns** — each plane can evolve independently
- **Messenger never does work** — it only routes and filters
- **Dojo never delivers mail** — it only assigns and evaluates
- **Skills never route messages** — they only execute and report
- **Human-in-the-loop** — quest dispatch requires human approval
- **Dual reputation** — Bounty (internal XP) + Resonance (external attestations)
- **CUPS boundary** — like 3GPP's PFCP interface between control and user planes

## Referenced By

- [ARC-2314: Skill Gateway Plane Architecture](../../spec/ARC-2314.md) -- Sections 4-6
- [ATR-X.200: Reference Model](../../spec/ATR-X200.md) -- Layer model
- [docs/GETTING-STARTED.md](../GETTING-STARTED.md) -- "The Three Planes"
