# UC-02: Cross-Clan Collaboration

> Two independent clans discover each other through the Agora, propose a quest, exchange deliverables, and build reputation.

This is the core value proposition of HERMES: sovereign clans collaborating without surrendering control.

## Actors

| Actor | Role |
|-------|------|
| **Clan Alpha** | Needs a service (e.g., security audit) |
| **Clan Beta** | Provides the service (e.g., cybersec expertise) |
| **Agora** | Public directory where clans find each other |
| **Human A** | Clan Alpha's operator — approves all decisions |
| **Human B** | Clan Beta's operator — approves all decisions |

## Use Case Flow

```mermaid
flowchart TD
    START([Clan Alpha needs expertise<br/>not available internally]) --> SEARCH

    subgraph discovery ["1. Discovery"]
        SEARCH["Dojo detects capability gap"]
        SEARCH --> AGORA["Messenger queries Agora:<br/>'eng.cybersecurity'"]
        AGORA --> FOUND["Found: Clan Beta<br/>Resonance: 4.2/5<br/>Skill: cybersec-architect"]
    end

    subgraph proposal ["2. Quest Proposal"]
        FOUND --> PROPOSE["Dojo creates quest proposal"]
        PROPOSE --> HUMAN_A{"Human A:<br/>Approve proposal?"}
        HUMAN_A -->|No| CANCEL([Quest cancelled])
        HUMAN_A -->|Yes| SEND["Messenger sends via Gateway<br/>[CID:quest-42]"]
        SEND --> RECEIVE["Beta's Messenger receives"]
        RECEIVE --> HUMAN_B{"Human B:<br/>Accept quest?"}
        HUMAN_B -->|No| DECLINE["Send decline [RE:quest-42]"]
        HUMAN_B -->|Yes| ACCEPT["Send accept [RE:quest-42]<br/>Assign: cybersec-architect"]
    end

    subgraph work ["3. Deliverable Exchange"]
        ACCEPT --> WORK_A["Alpha's skill produces deliverable"]
        WORK_A --> DELIVER["Send via Gateway<br/>[CID:quest-42-d1]"]
        DELIVER --> REVIEW["Beta's skill reviews"]
        REVIEW --> RESULTS["Send findings back<br/>[RE:quest-42-d1]"]
        RESULTS --> ITERATE{"More iterations<br/>needed?"}
        ITERATE -->|Yes| WORK_A
        ITERATE -->|No| COMPLETE["Quest complete"]
    end

    subgraph attestation ["4. Attestation"]
        COMPLETE --> ATTEST_A["Alpha attests Beta:<br/>Quality: 4/5<br/>Reliability: 5/5"]
        COMPLETE --> ATTEST_B["Beta attests Alpha:<br/>Quality: 5/5<br/>Collaboration: 5/5"]
        ATTEST_A --> RESONANCE["Both Resonance scores updated<br/>(verified, not self-declared)"]
        ATTEST_B --> RESONANCE
    end

    RESONANCE --> DONE([Both clans enriched.<br/>Reputation earned through work.])
    DECLINE --> DONE2([Alpha searches for other clans])

    style START fill:#1a1a2e,color:#fff
    style DONE fill:#16213e,color:#fff
    style CANCEL fill:#3e1616,color:#fff
```

## Key Design Points

- **Both humans approve** — no autonomous cross-clan action
- **Sovereignty preserved** — internal data, skills, and processes stay private
- **Reputation earned** — Resonance comes from verified cross-clan attestations, not self-declaration
- **CID/RE correlation** — every message in the sequence is traceable via tokens
- **Gateway-as-NAT** — internal namespace names never cross the boundary

## Referenced By

- [docs/GETTING-STARTED.md](../GETTING-STARTED.md) -- "How Two Clans Communicate"
- [docs/USE-CASES.md](../USE-CASES.md) -- Use Case #3
- [ARC-3022: Agent Gateway Protocol](../../spec/ARC-3022.md)
