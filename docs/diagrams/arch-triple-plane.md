# ARCH-02: Triple-Plane Architecture (CUPS)

> Control Plane, Orchestration Plane, and User Plane — three separated concerns inspired by 3GPP CUPS.

## Architecture Diagram

```mermaid
flowchart TB
    subgraph CP ["Control Plane — Messengers"]
        direction LR
        CP1["Route messages<br/>between clans"]
        CP2["Discovery via<br/>Agora directory"]
        CP3["Firewall & NAT<br/>(ARC-1918, ARC-3022)"]
        CP4["Session management<br/>(SYN/FIN)"]
    end

    subgraph OP ["Orchestration Plane — Dojos"]
        direction LR
        OP1["Quest dispatch<br/>& backlog"]
        OP2["Skill roster<br/>& matching"]
        OP3["XP tracking<br/>& governance"]
        OP4["Priority<br/>scheduling"]
    end

    subgraph UP ["User Plane — Skills"]
        direction LR
        UP1["Execute work<br/>(code, audit, design)"]
        UP2["Read/write bus<br/>(within guardrails)"]
        UP3["Produce<br/>deliverables"]
        UP4["Report results<br/>back to Dojo"]
    end

    BUS["bus.jsonl<br/>(shared transport)"]

    CP <-->|"signaling"| BUS
    OP <-->|"dispatch + results"| BUS
    UP <-->|"work data"| BUS

    CP -->|"delivers<br/>instructions"| OP
    OP -->|"dispatches<br/>work"| UP
    UP -.->|"returns<br/>results"| OP
    OP -.->|"sends<br/>responses"| CP

    EXT["External Clans<br/>(via Gateway)"]
    CP <-->|"inter-clan<br/>messages"| EXT

    style CP fill:#1a3a5c,color:#fff
    style OP fill:#3a1a5c,color:#fff
    style UP fill:#1a5c3a,color:#fff
    style BUS fill:#333,color:#fff
    style EXT fill:#5c3a1a,color:#fff
```

## Plane Responsibilities

| Plane | Role | What It Does | What It NEVER Does |
|-------|------|-------------|-------------------|
| **Control (CP)** | Messenger | Routes messages, handles discovery, enforces firewall | Makes decisions, does work |
| **Orchestration (OP)** | Dojo | Assigns quests, tracks skills, manages XP | Delivers mail, writes code |
| **User (UP)** | Skills | Executes actual work, produces deliverables | Routes messages, assigns work |

## Why Three Planes?

In telecom (3GPP TS 23.214), CUPS separates the "brain" (control) from the "muscle" (user plane). HERMES adds a third plane — orchestration — because agent ecosystems need a conductor who decides **what work gets done, by whom, and when**.

```
Telecom CUPS:        HERMES CUPS:
  Control Plane        Control Plane (Messenger)
  User Plane           Orchestration Plane (Dojo)  ← NEW
                       User Plane (Skills)
```

## Referenced By

- [ARC-2314: Skill Gateway Plane Architecture](../../spec/ARC-2314.md)
- [ATR-X.200: Reference Model](../../spec/ATR-X200.md)
- [SEQ-2314: CUPS Quest Dispatch](seq-2314-cups-quest-dispatch.md)
