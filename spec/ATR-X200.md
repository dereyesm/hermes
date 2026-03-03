# ATR-X.200 — HERMES Reference Model

| Field       | Value                                                          |
|-------------|----------------------------------------------------------------|
| **Number**  | ATR-X.200                                                      |
| **Title**   | HERMES Reference Model                                         |
| **Lineage** | ITU-T Recommendation X.200 — Open Systems Interconnection (OSI)|
| **Status**  | IMPLEMENTED                                                    |
| **Date**    | 2026-02-28                                                     |

---

## 1. Abstract

This document defines the HERMES Reference Model: a five-layer
architecture for inter-agent communication in stateless AI environments.
The model is derived from the principles of the ISO/IEC 7498-1
(OSI Reference Model, standardized as ITU-T Recommendation X.200) and
adapted to the constraints of file-based, session-scoped agent systems.

Where OSI addresses networked computer systems communicating over
physical media, HERMES addresses AI agents communicating through a shared
file system across temporal boundaries (sessions that do not share
runtime state). The protocol preserves OSI's core contribution —
layered separation of concerns — while collapsing seven layers to five,
reflecting the simpler topology of file-mediated agent messaging.

---

## 2. Scope

This recommendation:

- Defines the HERMES layered architecture and the responsibilities of
  each layer.
- Specifies the data units exchanged at each layer boundary.
- Establishes the interfaces between adjacent layers.
- Describes the end-to-end path of a message through the stack.
- Provides a formal comparison with both OSI and TCP/IP models.

This recommendation does NOT:

- Define the encoding of specific message types (see future ATRs).
- Specify agent behavior beyond bus interaction.
- Mandate a particular programming language or runtime.

---

## 3. Definitions

- **Agent**: An autonomous software entity (AI model, script, or tool)
  that reads from and writes to the HERMES bus.
- **Bus**: The active message file (`bus.jsonl`) containing all
  non-expired packets.
- **Namespace**: A logical isolation boundary grouping agents, files,
  and configuration. Equivalent to a network segment in TCP/IP.
- **Packet**: A single JSONL record in the bus file, representing one
  atomic message.
- **Session**: A bounded period during which an agent is active. Sessions
  are stateless — no runtime state persists between them.
- **PDU (Protocol Data Unit)**: The unit of data processed at a given
  layer.
- **SDU (Service Data Unit)**: The data passed from an upper layer to a
  lower layer for processing.

---

## 4. The HERMES Five-Layer Model

### 4.1 Layer Summary

```
+-------+------------------+-----------------+----------------------------+
| Layer | Name             | TCP/IP Equiv.   | HERMES Function            |
+-------+------------------+-----------------+----------------------------+
|  L4   | Application      | Application     | Agents read/write the bus  |
|  L3   | Transport        | Transport (TCP) | Bus lifecycle, ACK, TTL    |
|  L2   | Network          | Network (IP)    | Routing table, namespaces  |
|  L1   | Frame            | Data Link       | JSONL packet format        |
|  L0   | Physical         | Physical        | File system paths          |
+-------+------------------+-----------------+----------------------------+
```

### 4.2 Layer 0 — Physical

#### 4.2.1 Responsibilities

L0 provides the raw storage substrate for all HERMES communication. It
is responsible for:

- Providing a file system accessible to all agents within a deployment.
- Defining the canonical paths for bus files, routing tables, archives,
  and namespace configuration.
- Ensuring atomicity of file writes at the OS level.

#### 4.2.2 Data Unit

**Bits/Bytes** — raw file content on the storage medium.

#### 4.2.3 Interface to L1

L0 exposes file read and file append operations to L1. L1 treats L0 as
a reliable, ordered byte store. L0 does not interpret the content of
the bytes it stores.

#### 4.2.4 Implementation Requirements

| Requirement | Description |
|-------------|-------------|
| Path convention | A base directory MUST contain: `bus.jsonl`, `bus-archive.jsonl`, `routes.md` |
| Atomicity | File appends MUST be atomic at the line level. Partial line writes MUST NOT be visible to readers |
| Encoding | All files MUST be UTF-8 encoded |
| Permissions | The bus file MUST be readable and writable by all agents in the deployment |
| Separation | Each namespace MAY have its own file tree. Cross-namespace access is governed by L2 |

#### 4.2.5 Canonical File Layout

```
<base>/
├── bus.jsonl              # Active message bus (L0 storage for L1 frames)
├── bus-archive.jsonl      # Expired messages (historical record)
├── routes.md              # Routing table consumed by L2
└── protocol.md            # Protocol specification (informational)
```

---

### 4.3 Layer 1 — Frame

#### 4.3.1 Responsibilities

L1 defines the wire format of a HERMES packet. It is responsible for:

- Serializing agent messages into a deterministic, parseable format.
- Deserializing raw lines from the bus file into structured packets.
- Enforcing field presence and type constraints.
- Providing framing boundaries (one JSON object per line).

#### 4.3.2 Data Unit

**Frame** — a single line of valid JSON in the bus file, conforming to
the packet schema.

#### 4.3.3 Packet Schema

```json
{
  "ts":   "YYYY-MM-DD",
  "src":  "<namespace>",
  "dst":  "<namespace> | *",
  "type": "<message-type>",
  "msg":  "<payload>",
  "ttl":  <integer>,
  "ack":  [<namespace>, ...]
}
```

| Field  | Type     | Constraints |
|--------|----------|-------------|
| `ts`   | string   | ISO 8601 date (YYYY-MM-DD). REQUIRED |
| `src`  | string   | Source namespace identifier. REQUIRED |
| `dst`  | string   | Destination namespace or `*` (broadcast). REQUIRED |
| `type` | string   | One of the defined message types. REQUIRED |
| `msg`  | string   | Payload. Max 200 characters. REQUIRED |
| `ttl`  | integer  | Time-to-live in days from `ts`. REQUIRED. MUST be > 0 |
| `ack`  | array    | List of namespace identifiers that have consumed the message. REQUIRED. MAY be empty |

#### 4.3.4 Message Types

| Type         | Semantics                                   | Default TTL |
|--------------|---------------------------------------------|-------------|
| `state`      | A namespace's state has changed              | 7           |
| `alert`      | Urgent information for another namespace     | 5           |
| `event`      | An occurrence has been recorded (informational)| 3         |
| `request`    | A namespace requires data or action from another| 7        |
| `data_cross` | Permitted data crossing between namespaces   | 7           |
| `dispatch`   | A controller assigns agent(s) to a task      | 3           |

#### 4.3.5 Interface to L0

L1 passes serialized JSON lines to L0 for storage (write path) and
receives raw lines from L0 for deserialization (read path).

#### 4.3.6 Interface to L2

L1 provides parsed packet objects to L2, which inspects the `dst` field
for routing decisions. On the write path, L2 provides a validated
packet to L1 for serialization.

#### 4.3.7 Implementation Requirements

| Requirement | Description |
|-------------|-------------|
| One frame per line | Each packet MUST occupy exactly one line. No multi-line JSON |
| Valid JSON | Each line MUST be independently parseable as a JSON object |
| Field validation | Implementations MUST reject frames missing required fields |
| Append-only | New frames are appended to the bus file. Existing frames MUST NOT be modified in place (except `ack` array updates by L3) |
| Ordering | Frames appear in the bus file in chronological append order |

---

### 4.4 Layer 2 — Network

#### 4.4.1 Responsibilities

L2 provides logical addressing and routing. It is responsible for:

- Maintaining a routing table that maps namespace identifiers to file
  system paths and associated agents.
- Resolving the `dst` field of a packet to determine which agents
  should receive it.
- Expanding broadcast (`*`) destinations to the full set of namespaces.
- Enforcing namespace isolation (firewall rules).

#### 4.4.2 Data Unit

**Datagram** — a parsed packet (from L1) annotated with routing
metadata: resolved destination namespace(s) and the agents within each.

#### 4.4.3 Routing Table Structure

The routing table is a human-readable document (Markdown) with the
following logical structure:

```
Namespace → [File Paths] → [Agent Identifiers]
```

Example entry:

```markdown
| Namespace | Config Path         | Agents                    |
|-----------|---------------------|---------------------------|
| alpha     | /ns/alpha/          | agent-a, agent-b          |
| beta      | /ns/beta/           | agent-c                   |
```

#### 4.4.4 Routing Algorithm

```
INPUT:  packet with dst field
OUTPUT: set of (namespace, agent-list) tuples

1. IF dst == "*":
     RETURN all namespaces in routing table (broadcast)
2. ELSE IF dst exists in routing table:
     RETURN [(dst, agents(dst))]
3. ELSE:
     DISCARD packet (destination unknown)
     LOG routing error
```

#### 4.4.5 Firewall Model

L2 MAY enforce isolation rules that restrict which namespaces can
exchange messages. The firewall operates on two axes:

- **Source restriction**: A namespace MAY be prohibited from sending to
  certain destinations.
- **Type restriction**: Certain message types (e.g., `data_cross`) MAY
  require explicit allowlisting between namespace pairs.

Firewall rules are defined outside the bus file itself, typically in
the routing table or a companion configuration.

#### 4.4.6 Interface to L1

L2 receives parsed packets from L1 and returns validated, routable
packets. Packets that fail routing are discarded at this layer.

#### 4.4.7 Interface to L3

L2 passes routed datagrams (packets with resolved destinations) to L3
for lifecycle management. On the read path, L3 requests packets
filtered by namespace, and L2 performs the filtering.

#### 4.4.8 Implementation Requirements

| Requirement | Description |
|-------------|-------------|
| Routing table | Implementations MUST maintain a routing table mapping namespaces to paths and agents |
| Broadcast expansion | `*` destinations MUST be expanded to all known namespaces |
| Unknown destination | Packets addressed to unknown namespaces MUST be discarded, not silently dropped |
| Firewall enforcement | If firewall rules are defined, L2 MUST enforce them before passing packets to L3 |

---

### 4.5 Layer 3 — Transport

#### 4.5.1 Responsibilities

L3 manages the lifecycle of messages on the bus. It is responsible for:

- Tracking acknowledgment state (`ack` array).
- Enforcing TTL expiration policies.
- Archiving expired messages (moving from bus to archive).
- Providing reliable delivery semantics (at-least-once per namespace).
- Implementing the SYN/FIN session protocol.

#### 4.5.2 Data Unit

**Segment** — a datagram (from L2) enriched with transport metadata:
delivery state (pending, acknowledged, expired) and age in days.

#### 4.5.3 Acknowledgment Protocol

```
A message is PENDING for namespace N if:
  (dst == N  OR  dst == "*")  AND  N NOT IN ack

A message is ACKNOWLEDGED for namespace N if:
  N IN ack

A message is FULLY ACKNOWLEDGED if:
  (dst != "*" AND dst IN ack)
  OR
  (dst == "*" AND all known namespaces IN ack)
```

When an agent in namespace N consumes a message, N MUST be appended to
the `ack` array.

#### 4.5.4 TTL Lifecycle

```
age = current_date - ts

IF age > ttl:
  message is EXPIRED
  MOVE from bus.jsonl to bus-archive.jsonl
  (preserving the full packet including final ack state)
```

#### 4.5.5 Session Protocol

HERMES defines two session-boundary operations:

**SYN (Session Start)**:

```
1. Agent starts in namespace N
2. Read bus.jsonl
3. Filter: (dst == N OR dst == "*") AND N NOT IN ack
4. Present pending messages to the agent
5. Flag messages where age > 3 days and still unacknowledged
```

**FIN (Session End)**:

```
1. If session produced state changes:
     Append new packet(s) to bus.jsonl via L1
2. Acknowledge all messages consumed during this session:
     Append N to ack array for each consumed message
3. Run TTL expiration check:
     Archive any messages where age > ttl
```

#### 4.5.6 Interface to L2

L3 receives routed datagrams from L2 and returns filtered, lifecycle-
annotated segments. L3 invokes L2 for namespace resolution when
processing acknowledgments.

#### 4.5.7 Interface to L4

L3 provides the agent-facing bus interface to L4: read (with namespace
filtering and delivery state), write (with validation), and acknowledge.

#### 4.5.8 Implementation Requirements

| Requirement | Description |
|-------------|-------------|
| ACK atomicity | Acknowledgment writes MUST be atomic. A crash between read and ACK MUST NOT lose the ACK |
| TTL enforcement | Implementations MUST check TTL on every SYN and FIN operation |
| Archive preservation | Expired messages MUST be moved to archive, not deleted |
| At-least-once delivery | A message MUST remain visible to a namespace until that namespace appears in `ack` |
| Stale message detection | Messages pending for >3 days SHOULD be flagged during SYN |

---

### 4.6 Layer 4 — Application

#### 4.6.1 Responsibilities

L4 is the agent-facing layer. It is responsible for:

- Providing a high-level API for agents to send and receive messages.
- Interpreting message payloads according to application-level semantics.
- Implementing agent-specific logic for message handling (filtering,
  prioritization, response generation).
- Enforcing payload conventions (atomicity, prefixes, source annotations).

#### 4.6.2 Data Unit

**Message** — the application-level object consumed and produced by
agents. Contains the full semantic content: source, destination, type,
payload, and delivery metadata.

#### 4.6.3 Payload Conventions

L4 defines the following conventions for the `msg` field:

| Convention | Rule |
|------------|------|
| Atomicity | One message = one topic. Multiple topics require multiple packets |
| Projection prefix | `data_cross` messages containing projections (not verified data) MUST prefix `msg` with `PROJ:` |
| Source annotation | `data_cross` messages containing monetary values SHOULD include `@source` suffix |

#### 4.6.4 Agent Roles

L4 recognizes three operational roles that an agent may assume:

| Role       | Description |
|------------|-------------|
| **Producer** | Writes new messages to the bus |
| **Consumer** | Reads and acknowledges messages from the bus |
| **Router**   | Reads all messages across all namespaces; detects desynchronization; proposes corrections |

An agent MAY assume multiple roles simultaneously.

#### 4.6.5 Interface to L3

L4 invokes L3 operations:

- `read(namespace)` — retrieve pending messages for a namespace.
- `write(packet)` — submit a new message to the bus.
- `ack(namespace, message)` — acknowledge consumption of a message.
- `archive()` — trigger TTL expiration and archival.

#### 4.6.6 Implementation Requirements

| Requirement | Description |
|-------------|-------------|
| Payload validation | Agents SHOULD validate payload conventions before writing |
| Idempotent reads | Reading the bus MUST NOT alter its state. Only explicit ACK modifies state |
| Human authority | Agents MUST NOT execute irreversible actions based solely on bus messages without human approval |
| Namespace fidelity | An agent MUST only write messages with `src` matching its own namespace |

---

## 5. Full Stack Diagram

```
+------------------------------------------------------------------+
|                                                                  |
|   AGENT A (namespace: alpha)      AGENT B (namespace: beta)      |
|   +--------------------------+    +--------------------------+   |
|   |  L4  Application         |    |  L4  Application         |   |
|   |  [Message]               |    |  [Message]               |   |
|   +--------+-----------------+    +----------------+---------+   |
|            |                                       ^             |
|            | write(packet)                          | read(ns)   |
|            v                                       |             |
|   +--------+-----------------+    +----------------+---------+   |
|   |  L3  Transport           |    |  L3  Transport           |   |
|   |  [Segment]               |    |  [Segment]               |   |
|   |  ACK + TTL lifecycle     |    |  SYN + ACK + FIN         |   |
|   +--------+-----------------+    +----------------+---------+   |
|            |                                       ^             |
|            | route(packet)                          | filter(ns) |
|            v                                       |             |
|   +--------+---------------------------------------+---------+   |
|   |                    L2  Network                           |   |
|   |                    [Datagram]                             |   |
|   |           Routing table + Firewall rules                 |   |
|   +--------+---------------------------------------+---------+   |
|            |                                       ^             |
|            | serialize(json)                        | parse(line)|
|            v                                       |             |
|   +--------+---------------------------------------+---------+   |
|   |                    L1  Frame                             |   |
|   |                    [Frame]                               |   |
|   |              JSONL packet format                         |   |
|   +--------+---------------------------------------+---------+   |
|            |                                       ^             |
|            | append(bytes)                          | read(bytes)|
|            v                                       |             |
|   +--------+---------------------------------------+---------+   |
|   |                    L0  Physical                          |   |
|   |                    [Bits/Bytes]                           |   |
|   |               bus.jsonl on file system                   |   |
|   +----------------------------------------------------------+   |
|                                                                  |
+------------------------------------------------------------------+
```

---

## 6. Layer Interaction Model

This section traces the full lifecycle of a message from creation by a
sending agent to consumption by a receiving agent.

### 6.1 Write Path (Agent A sends a message)

```
Step  Layer  Operation
----  -----  ---------
 1    L4     Agent A constructs a Message: {src:"alpha", dst:"beta",
             type:"state", msg:"cache_invalidated", ttl:7, ack:[]}

 2    L4→L3  Agent invokes write(packet). L3 validates transport fields:
             ttl > 0, ts is current date, ack is empty array.

 3    L3→L2  L3 passes packet to L2 for routing validation.
             L2 confirms "beta" exists in routing table.
             L2 checks firewall: alpha → beta is permitted.

 4    L2→L1  L2 passes validated packet to L1 for framing.
             L1 serializes the packet as a single JSON line.
             L1 validates all required fields are present.

 5    L1→L0  L1 passes the serialized line to L0.
             L0 atomically appends the line to bus.jsonl.

Result: The message is now persisted in the bus file.
```

### 6.2 Read Path (Agent B consumes the message)

```
Step  Layer  Operation
----  -----  ---------
 1    L0     Agent B's session starts. L0 reads bus.jsonl from disk.

 2    L0→L1  Raw file content is passed to L1.
             L1 parses each line as a JSON object.
             L1 rejects malformed lines (logged, not fatal).

 3    L1→L2  Parsed packets are passed to L2.
             L2 filters by destination: retains packets where
             dst == "beta" OR dst == "*".

 4    L2→L3  Filtered datagrams are passed to L3.
             L3 applies transport filters:
               - Exclude packets where "beta" IN ack
               - Exclude packets where age > ttl (expired)
               - Flag packets where age > 3 and unacknowledged

 5    L3→L4  Pending segments are delivered to Agent B.
             Agent B processes each message according to its logic.

 6    L4→L3  Agent B acknowledges consumption.
             L3 appends "beta" to the ack array of each consumed
             message in bus.jsonl.

Result: The message is marked as delivered to namespace "beta".
```

### 6.3 Expiration Path

```
Step  Layer  Operation
----  -----  ---------
 1    L3     During SYN or FIN, L3 scans all packets in bus.jsonl.
             For each packet: compute age = current_date - ts.

 2    L3     If age > ttl:
               - Read the full packet (final state including ack).
               - Append the packet to bus-archive.jsonl via L1→L0.
               - Remove the packet from bus.jsonl.

Result: The bus file contains only active, non-expired messages.
        The archive preserves the complete history.
```

---

## 7. Comparison: OSI vs TCP/IP vs HERMES

```
+------+----------------+----------------+------------------+
| OSI  | TCP/IP         | HERMES         | Data Unit        |
+------+----------------+----------------+------------------+
|  7   | Application    |                |                  |
|  6   | (merged into   |  L4            | Message          |
|  5   |  Application)  |  Application   |                  |
+------+----------------+----------------+------------------+
|  4   | Transport      |  L3 Transport  | Segment          |
+------+----------------+----------------+------------------+
|  3   | Network (IP)   |  L2 Network    | Datagram         |
+------+----------------+----------------+------------------+
|  2   | Data Link      |  L1 Frame      | Frame            |
+------+----------------+----------------+------------------+
|  1   | Physical       |  L0 Physical   | Bits/Bytes       |
+------+----------------+----------------+------------------+
```

### 7.1 Detailed Comparison

| Aspect | OSI / TCP/IP | HERMES |
|--------|-------------|--------|
| **Medium** | Electrical/optical signals over cables, radio | Bytes in files on a shared file system |
| **Addressing** | IP addresses, MAC addresses, ports | Namespace identifiers (strings) |
| **Routing** | Dynamic routing protocols (BGP, OSPF) | Static routing table (Markdown document) |
| **Framing** | Ethernet frames, IP packets | JSONL lines in a text file |
| **Transport** | TCP segments with seq/ack numbers | JSONL records with `ack` array and `ttl` |
| **Reliability** | TCP retransmission, checksums | At-least-once via persistent ack array |
| **Session** | TCP handshake (SYN/SYN-ACK/ACK) | SYN at session start, FIN at session end |
| **Multiplexing** | Ports | Message `type` field |
| **Broadcast** | Broadcast/multicast IP | `dst: "*"` wildcard |
| **Time model** | Real-time, continuous | Discrete sessions, day-granularity timestamps |
| **Presentation** | ASN.1, TLS | UTF-8 JSON (no encryption layer) |
| **Layers** | 7 (OSI) / 4 (TCP/IP) | 5 |

### 7.2 Why Five Layers

OSI's seven layers include Presentation (L6) and Session (L5), which
address concerns that do not arise in HERMES:

- **Presentation (L6)**: HERMES uses a single encoding (UTF-8 JSON)
  with no negotiation. There is no need for format translation.
- **Session (L5)**: HERMES sessions are implicit — bounded by agent
  start and stop. There is no multiplexed session management.

OSI's Physical and Data Link layers map naturally to HERMES L0 and L1.
The Network, Transport, and Application layers map one-to-one. The
result is a five-layer model that preserves the conceptual clarity of
OSI while reflecting the actual complexity of the system.

---

## 8. Conformance

An implementation conforms to ATR-X.200 if it:

1. Implements all five layers with the responsibilities described in
   Section 4.
2. Uses the packet schema defined in Section 4.3.3.
3. Implements the SYN and FIN session protocol defined in Section 4.5.5.
4. Implements the ACK protocol defined in Section 4.5.3.
5. Implements TTL expiration and archival as defined in Section 4.5.4.
6. Maintains a routing table consumable by L2 as described in
   Section 4.4.3.
7. Stores bus data in the file layout described in Section 4.2.5.

Partial implementations MUST declare which layers they implement and
which they delegate to external components.

---

## 9. Control Plane / User Plane Separation (CUPS)

### 9.1 Background

3GPP TS 23.214 introduced Control and User Plane Separation (CUPS) for
the Evolved Packet Core, enabling independent scaling of control
functions (policy, routing decisions) and user plane functions (data
forwarding). The same principle applies to HERMES: the path that
carries agent messages is architecturally distinct from the path that
governs how those messages are routed, filtered, and managed.

### 9.2 HERMES CUPS Mapping

HERMES naturally separates into two planes:

- **User Plane (UP)**: The `bus.jsonl` file and its archive. This is
  where messages transit between agents — analogous to the SGW-U/PGW-U
  in 3GPP. The UP handles message forwarding only; it does not make
  routing decisions.

- **Control Plane (CP)**: The `routes.md` routing table, firewall
  rules (ARC-1918), namespace configuration, and session management
  (SYN/FIN). This is analogous to the SGW-C/PGW-C in 3GPP. The CP
  defines the rules that the UP executes.

| 3GPP CUPS Concept | HERMES Equivalent | Description |
|-------------------|-------------------|-------------|
| SGW-C / PGW-C (Control) | Controller namespace + `routes.md` | Routing policy, namespace management |
| SGW-U / PGW-U (User) | `bus.jsonl` message forwarding | Message transit between agents |
| PFCP Session | Namespace session (SYN/FIN) | Session lifecycle management |
| PDR (Packet Detection Rule) | Routing rule in `routes.md` | Pattern matching for message routing |
| FAR (Forwarding Action Rule) | Message type filter + `dst` routing | Action to take on matched messages |
| Sx interface | Controller ↔ bus read/write interface | CP-UP communication channel |

### 9.3 Separation Rules

1. **Independent evolution.** The UP format (JSONL messages per
   ARC-5322) and the CP format (routing tables, firewall rules) MUST
   be independently versionable. Changes to routing logic MUST NOT
   require changes to the message format.

2. **CP does not transit data.** The routing table and firewall
   configuration MUST NOT carry agent payload data. They define rules;
   the bus executes them.

3. **UP does not make policy.** The bus file is a transport medium.
   Routing decisions, namespace isolation, and access control MUST be
   resolved by the CP before a message is written to or read from the
   bus.

4. **Stateless UP operations.** An agent appending to `bus.jsonl` or
   reading from it SHOULD NOT need to maintain state beyond the current
   message. The CP maintains session state (SYN/FIN) and routing state
   (`routes.md`).

### 9.4 Benefits

- **Independent scaling.** In multi-machine deployments, the bus file
  (UP) can be replicated or sharded without changing routing logic.
- **Clear responsibility.** Debugging message flow issues reduces to:
  "Is it a routing problem (CP)?" vs "Is it a message format problem
  (UP)?"
- **Evolution path.** Future transport modes (network sockets,
  real-time streams per ARC-6455) can replace the UP without
  affecting the CP, and vice versa.

### 9.5 References

- 3GPP TS 23.214 — Architecture enhancements for control and user
  plane separation of EPC nodes
- 3GPP TS 29.244 — Interface between the control plane and the user
  plane nodes (PFCP)
- BBF TR-369 — User Services Platform (transport-independent
  management protocol with CP/UP separation)

---

## 10. Security Considerations

HERMES ATR-X.200 does not define an encryption or authentication layer.
The security model relies on:

- **File system permissions** (L0): The operating system controls which
  agents can read/write the bus.
- **Namespace isolation** (L2): Firewall rules restrict message flow
  between namespaces.
- **Human authority** (L4): Agents must not take irreversible actions
  based solely on bus messages.

Future ATRs MAY define signing or encryption extensions at L1 (frame
signatures) or L3 (encrypted payloads).

---

## 11. References

| Reference | Title |
|-----------|-------|
| ISO/IEC 7498-1:1994 | Information technology — Open Systems Interconnection — Basic Reference Model |
| ITU-T X.200 (1994) | Information technology — Open Systems Interconnection — Basic Reference Model: The basic model |
| ITU-T X.210 (1993) | Information technology — Open Systems Interconnection — Basic Reference Model: Conventions for the definition of OSI services |
| RFC 1122 (1989) | Requirements for Internet Hosts — Communication Layers |
| RFC 793 (1981) | Transmission Control Protocol |
| HERMES PROTOCOL.md | HERMES Protocol Specification (internal, v1) |
| 3GPP TS 23.214 | Architecture enhancements for control and user plane separation of EPC nodes |
| 3GPP TS 29.244 | Interface between the control plane and the user plane nodes (PFCP) |
| BBF TR-369 | User Services Platform (USP) |

---

*ATR-X.200 is part of the HERMES open standard. Licensed under MIT.*
