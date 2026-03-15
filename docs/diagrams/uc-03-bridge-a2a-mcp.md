# UC-03: Bridge from A2A/MCP to HERMES

> How an external A2A agent or MCP client interacts with a HERMES clan through the Gateway Bridge.

HERMES doesn't replace A2A or MCP — it bridges to them. The Gateway translates protocol semantics bidirectionally.

## Actors

| Actor | Role |
|-------|------|
| **A2A Client** | External agent using Google A2A protocol |
| **MCP Client** | External tool using Anthropic MCP protocol |
| **Gateway Bridge** | Translates between external protocol and HERMES JSONL |
| **HERMES Agent** | Internal skill behind the gateway |

## Bridge Flow — A2A

```mermaid
sequenceDiagram
    participant C as A2A Client
    participant BR as Gateway Bridge<br/>(A2A endpoint)
    participant GW as Gateway Core<br/>(filter + NAT)
    participant BUS as Bus<br/>(bus.jsonl)
    participant AG as HERMES Agent<br/>(internal skill)

    Note over C,AG: 1. Discovery

    C->>BR: GET /.well-known/agent.json
    BR-->>C: Agent Card (from ARC-2606 profile)<br/>{name, skills, capabilities}

    Note over C,AG: 2. Invoke (A2A → HERMES)

    C->>BR: POST /a2a<br/>tasks/send (JSON-RPC)<br/>"Analyze debt scenario..."
    BR->>BR: Parse JSON-RPC envelope<br/>Extract semantic intent: INVOKE
    BR->>BR: Generate CID:<br/>brg-a2a-20260314-001
    BR->>GW: HERMES message:<br/>type=dispatch<br/>[CID:brg-a2a-20260314-001]
    GW->>GW: Inbound validation<br/>Rate limit check
    GW->>BUS: Append to bus

    Note over C,AG: 3. Internal Processing

    AG->>BUS: SYN: read dispatch
    AG->>AG: Execute work
    AG->>BUS: Write result<br/>[RE:brg-a2a-20260314-001]

    Note over C,AG: 4. Response (HERMES → A2A)

    GW->>BUS: Read response
    GW->>BR: Outbound filter pass
    BR->>BR: Translate to A2A format:<br/>task state = completed<br/>artifacts = [{text: result}]
    BR-->>C: JSON-RPC response<br/>tasks/send result
```

## Bridge Flow — MCP

```mermaid
sequenceDiagram
    participant C as MCP Client
    participant BR as Gateway Bridge<br/>(MCP endpoint)
    participant BUS as Bus<br/>(bus.jsonl)
    participant AG as HERMES Agent

    Note over C,AG: 1. Tool Discovery

    C->>BR: tools/list (JSON-RPC)
    BR-->>C: Tool list (from ARC-2606 capabilities)<br/>[{name: "aureus_debt_strategy",<br/> inputSchema: {...}}]

    Note over C,AG: 2. Tool Call (MCP → HERMES)

    C->>BR: tools/call (JSON-RPC)<br/>tool: "aureus_debt_strategy"<br/>args: {scenario: "..."}
    BR->>BR: Map tool name → namespace + capability
    BR->>BR: Generate CID: brg-mcp-20260314-001
    BR->>BUS: Write dispatch<br/>[CID:brg-mcp-20260314-001]

    Note over C,AG: 3. Processing & Response

    AG->>BUS: Read dispatch, execute work
    AG->>BUS: Write result [RE:brg-mcp-20260314-001]
    BR->>BUS: Read response
    BR->>BR: Translate to MCP format:<br/>{content: [{type: "text", text: result}]}
    BR-->>C: tools/call result (JSON-RPC)
```

## Unified Operation Semantics

```mermaid
flowchart LR
    subgraph external ["External Protocol"]
        A2A["A2A: tasks/send"]
        MCP["MCP: tools/call"]
    end

    subgraph bridge ["Gateway Bridge"]
        SEM["Semantic extraction:<br/>Query | Update | Create<br/>Invoke | Notify"]
    end

    subgraph hermes ["HERMES"]
        REQ["request"]
        STATE["state"]
        EVT["event"]
        DISP["dispatch"]
        ALERT["alert"]
    end

    A2A --> SEM
    MCP --> SEM
    SEM -->|Query| REQ
    SEM -->|Update| STATE
    SEM -->|Create| EVT
    SEM -->|Invoke| DISP
    SEM -->|Notify| ALERT

    style external fill:#1a3a5c,color:#fff
    style bridge fill:#5c3a1a,color:#fff
    style hermes fill:#1a5c3a,color:#fff
```

## Key Design Points

- **Bidirectional** — external protocols can call HERMES agents AND HERMES agents can call external ones
- **Semantic preservation** — operation intent (Query, Invoke, Notify, etc.) is maintained across translation
- **Identity isolation** — internal namespace names are NEVER exposed through bridge endpoints
- **CID correlation** — bridge-generated CIDs track the full request/response lifecycle
- **Rate limiting** — bridge has independent rate limits on top of gateway limits
- **Optional** — a HERMES deployment without a bridge is fully functional

## Referenced By

- [ARC-7231: Agent Semantics](../../spec/ARC-7231.md) -- Sections 3-6
- [ARC-3022: Agent Gateway Protocol](../../spec/ARC-3022.md) -- Gateway architecture
