# SEQ-3022: Gateway Cross-Clan Communication

> How a message travels from one clan to another through the Gateway NAT boundary, hop by hop.

The Gateway is the membrane between sovereign clans. It translates identity, filters traffic, and never exposes internal structure.

## Actors

| Actor | Role | Spec Reference |
|-------|------|----------------|
| **Agent A** | Source namespace inside Clan Alpha | ARC-5322 |
| **Gateway Alpha** | Clan Alpha's boundary — outbound filter + NAT | ARC-3022 Sections 7-8 |
| **Agora** | Public directory for clan discovery | ARC-2606 |
| **Gateway Beta** | Clan Beta's boundary — inbound validation | ARC-3022 Sections 8 |
| **Agent B** | Destination namespace inside Clan Beta | ARC-5322 |

## Sequence Diagram

```mermaid
sequenceDiagram
    participant A as Agent A<br/>(Clan Alpha)
    participant BA as Bus Alpha<br/>(bus.jsonl)
    participant GA as Gateway Alpha<br/>(NAT outbound)
    participant AG as Agora<br/>(public directory)
    participant GB as Gateway Beta<br/>(NAT inbound)
    participant BB as Bus Beta<br/>(bus.jsonl)
    participant B as Agent B<br/>(Clan Beta)

    Note over A,B: Phase 1: Discovery (one-time)

    GA->>AG: Publish clan profile<br/>(capabilities, public alias)
    GB->>AG: Publish clan profile
    GA->>AG: Search: "eng.cybersecurity"
    AG-->>GA: Found: Clan Beta<br/>(alias, capabilities, endpoint)

    Note over A,B: Phase 2: Outbound (Alpha → Beta)

    A->>BA: Write message to bus<br/>(src="engineering", dst="ops-beta")
    GA->>BA: Monitor bus for outbound messages
    GA->>GA: Outbound filter check:<br/>1. Is src allowed to send externally?<br/>2. Is dst a known peer?<br/>3. Is type in forward_types?

    alt Filter blocks
        GA-->>BA: Write alert: "Outbound blocked"
    else Filter passes
        GA->>GA: NAT translate:<br/>internal "engineering" →<br/>external alias "alpha-eng"
        GA->>GA: Strip internal metadata<br/>(namespace IDs, paths, credentials)
        GA->>GA: Validate per ARC-5322
        GA->>GB: HTTPS POST /bus/push<br/>(translated message)
    end

    Note over A,B: Phase 3: Inbound (at Beta's boundary)

    GB->>GB: Inbound validation:<br/>1. Source in peer list?<br/>2. Rate limit OK?<br/>3. Payload valid (ARC-5322)?

    alt Validation fails
        GB-->>GA: HTTP 4xx/5xx error
    else Validation passes
        GB->>GB: NAT translate:<br/>external "alpha-eng" →<br/>internal alias for Alpha
        GB->>BB: Append to local bus
    end

    Note over A,B: Phase 4: Consumption & ACK

    B->>BB: SYN: read bus, filter pending
    BB-->>B: New message from Clan Alpha
    B->>B: Process message
    B->>BB: ACK message

    Note over A,B: Phase 5: Response (reverse path)

    B->>BB: Write response with [RE:token]
    GB->>BB: Monitor bus for outbound
    GB->>GA: HTTPS POST /bus/push (response)
    GA->>BA: Append to local bus
    A->>BA: SYN: reads response
```

## Key Design Points

- **Gateway-as-NAT** — internal namespace names are NEVER exposed externally
- **Default-deny outbound** — only whitelisted types/destinations pass the filter
- **Sovereignty preserved** — each clan controls its own firewall rules independently
- **Bidirectional** — responses flow back through the same boundary in reverse
- **CID/RE correlation** — `[CID:token]` and `[RE:token]` link request to response across clans
- **HTTPS required** — inter-gateway transport is always encrypted in transit

## Referenced By

- [ARC-3022: Agent Gateway Protocol](../../spec/ARC-3022.md) -- Sections 4-8
- [ARC-2606: Agent Profile & Discovery](../../spec/ARC-2606.md) -- Agora directory
- [docs/GETTING-STARTED.md](../GETTING-STARTED.md) -- "How Two Clans Communicate"
