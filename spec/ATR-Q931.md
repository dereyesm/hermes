# ATR-Q.931 — Session Setup Signaling

| Field        | Value                                                                       |
|--------------|-----------------------------------------------------------------------------|
| **Number**   | ATR-Q.931                                                                   |
| **Title**    | Session Setup Signaling                                                     |
| **Lineage**  | ITU-T Recommendation Q.931 (ISDN Layer 3 Call Control) + IETF RFC 3261 (SIP)|
| **Status**   | PROPOSED                                                                    |
| **Date**     | 2026-04-06                                                                  |
| **Authors**  | Daniel Reyes, Protocol Architect                                            |
| **Requires** | ARC-2119 (Requirement Keywords), ARC-5322 (Message Format), ARC-4601 §15 (Hub Mode), ATR-Q.700 (Out-of-Band Signaling) |
| **Extends**  | ARC-2314 (Skill Gateway Plane Architecture) — refines control plane        |

> **Editorial Review Window — 2026-04-06 → 2026-04-12**
>
> Promoted from DRAFT to PROPOSED on 2026-04-06. First-clan feedback
> (JEI) is explicitly invited via the Amaru bus (ARC-5322 alert frame)
> and via mention on `dereyesm/amaru-protocol#5`. Editorial revisions
> submitted before 2026-04-12 will be incorporated without a status
> bump. Structural changes after that date will require a new revision
> tag.
>
> §8.1 (`SENT` receipt) is already implemented in the reference hub
> (commit 611b88a). §8.2–§8.4 are gated on the ARC-4601 §18 amendment.

---

## 1. Abstract

This specification defines the Amaru signaling plane: an out-of-band
control channel that establishes, maintains, and tears down data sessions
between agent peers. It is modelled on ITU-T Recommendation Q.931 (ISDN
Layer 3 call control) and IETF RFC 3261 (Session Initiation Protocol),
adapted to the constraints of file-backed and hub-relayed agent
communication.

Where ARC-5322 defines the wire format of a single message and ARC-4601
defines how an Agent Node relays messages through a hub, ATR-Q.931
defines how two peers negotiate the *existence of a session* before any
payload is exchanged. A session groups a bounded sequence of related
messages (a quest dispatch and its responses, a cross-namespace data
exchange, or a multicast fan-out) under a single correlation identifier
and a shared lifecycle.

The signaling plane is separated from the data plane. Signaling frames
are small, unencrypted, rate-limited, and always routable by the hub.
Data frames carry payloads, MAY be end-to-end encrypted (ARC-8446), and
are only permitted to flow while an active session exists.

This document also defines delivery receipts — a four-stage confirmation
model (SENT → DELIVERED → READ → PROCESSED) inspired by 3GPP TS 23.040
SMS status reports and by the WhatsApp double-check convention — and
addressing modes beyond unicast and broadcast (multicast groups and
anycast).

---

## 2. Scope

This recommendation:

- Defines the session lifecycle state machine.
- Specifies the signaling primitives (`REGISTER`, `INVITE`, `200 OK`,
  `4xx`, `5xx`, `ACK`, `BYE`, `OPTIONS`, `NOTIFY`, `PING`, `PONG`,
  `JOIN`, `LEAVE`).
- Defines the signaling wire format as an extension of ARC-5322 using
  a `channel` discriminator.
- Specifies the four-stage delivery receipt model and its opt-in
  envelope extension.
- Defines multicast and anycast addressing syntax on top of the
  existing unicast and broadcast destinations.
- Specifies hub behaviour with respect to channel-aware routing.
- Defines a backward-compatible migration path from the single-channel
  wire format used prior to this specification.

This recommendation does NOT:

- Define the encryption of the data channel (see ARC-8446).
- Define agent authentication or peer registration (see ARC-4601 §15.6
  and ATR-X.509 when published).
- Define the physical transport of signaling frames (WebSocket, file,
  or otherwise — see ARC-4601 §15.4).
- Normalise Phase 2 (separate WebSocket per channel) or Phase 3
  (per-session ECDHE keys). These are documented in Section 11 as
  informational future work.
- Define test vectors. Conformance is stated in prose (Section 13),
  consistent with existing ATR specifications.

---

## 3. Definitions

- **Signaling channel**: A logical control path carrying session setup,
  presence, capability negotiation, delivery receipts, and keepalives.
  Always-on, small frames, rate-limited, not encrypted at the
  application layer.
- **Data channel**: A logical path carrying payload messages (dispatch,
  response, `data_cross`, stream segments). Opened only inside an
  active session. MAY be end-to-end encrypted.
- **Session**: A bounded correlation context between two or more peers,
  identified by a `session_id`. A session begins with an accepted
  `INVITE` and ends with a `BYE`, a timeout, or an irrecoverable error.
- **Dialog**: A SIP-derived term. Synonym for session in this document;
  retained in references to RFC 3261.
- **Peer**: An Agent Node (ARC-4601) capable of emitting and accepting
  signaling frames. A peer is identified by its `clan_id`.
- **Session ID** (`session_id`): A string that MUST be unique among
  active sessions for a given pair of peers. RECOMMENDED format is a
  UUID (RFC 9562).
- **Message reference** (`ref`): A sender-assigned, human-readable
  identifier for a single message, used to correlate delivery receipts
  with the original message.
- **Receipt stage**: One of `SENT`, `DELIVERED`, `READ`, `PROCESSED`.
  Each stage represents a distinct checkpoint in the delivery path.
- **Capability** (`cap`): A named feature that a peer advertises as
  supported (e.g., `signaling_v1`, `receipts`, `multicast`,
  `tunnel_mode`).
- **Hub**: A central relay as defined in ARC-4601 §15. In this
  specification the hub routes signaling frames actively and forwards
  data frames opaquely.

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT",
"SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this
document are to be interpreted as described in ARC-2119 (RFC 2119).

---

## 4. Session Lifecycle

### 4.1 State Machine

Every session progresses through a finite state machine. At any time,
a session is in exactly one state:

```
                 ┌──────────┐
                 │   IDLE   │◄─────────────┐
                 └────┬─────┘              │
                      │ send INVITE         │
                      ▼                    │
                 ┌──────────┐               │
           ┌────►│ INVITING │               │
           │     └────┬─────┘               │
           │          │ recv 200 OK          │
 recv 4xx  │          ▼                    │
 recv 5xx  │     ┌──────────┐               │
 timeout   │     │ACCEPTING │               │
           │     └────┬─────┘               │
           │          │ send ACK             │
           │          ▼                    │
           │     ┌────────────┐             │
           │     │ESTABLISHED │             │
           │     └────┬───────┘             │
           │          │ send/recv BYE       │
           │          │ or TTL expiry       │
           │          ▼                    │
           │     ┌────────────┐             │
           │     │TERMINATING │─────────────┘
           │     └────────────┘
           │
           └─────────────────────────────────┘
```

**States**:

| State         | Description                                                     |
|---------------|-----------------------------------------------------------------|
| `IDLE`        | No session exists. The peer has no state for this `session_id`. |
| `INVITING`    | An `INVITE` has been sent; awaiting a response.                 |
| `ACCEPTING`   | A `200 OK` has been received; the caller MUST send `ACK`.       |
| `ESTABLISHED` | A session is active. Data frames MAY flow.                      |
| `TERMINATING` | A `BYE` has been sent or received; resources are being released.|

A peer MUST maintain this state per `session_id`. A peer MUST NOT accept
data frames for a `session_id` unless the local state is `ESTABLISHED`
or `TERMINATING`.

### 4.2 Timing Constraints

| Timer                  | Default | Normative Level | Applies When                            |
|------------------------|---------|-----------------|-----------------------------------------|
| `INVITE` timeout       | 10 s    | MUST            | No response to an `INVITE`              |
| `ACK` timeout          | 5 s     | MUST            | Caller failed to send `ACK` after 200 OK|
| Session TTL (default)  | 300 s   | SHOULD          | No data frame observed for a session    |
| Keepalive interval     | 30 s    | SHOULD          | Signaling channel inactivity            |
| `PING` response window | 10 s    | MUST            | Keepalive reply expected                |

A session whose TTL expires MUST be transitioned to `TERMINATING` and
a `BYE` frame SHOULD be emitted. The TTL MAY be refreshed by any data
frame exchange or by an explicit `NOTIFY`.

### 4.3 Error Cases

- **`INVITE` timeout**: The caller MUST retry with exponential backoff
  (initial 10 s, factor 2, maximum 3 attempts). After the final attempt
  the session MUST transition to `IDLE` and an application-level error
  SHOULD be surfaced.
- **4xx response (client error)**: The caller MUST NOT retry with the
  same `session_id`. The session transitions directly to `IDLE`.
- **5xx response (server error)**: The caller MAY retry with the same
  `session_id` once after a minimum delay of 30 s.
- **Data channel drop mid-session**: The peer that detects the drop
  SHOULD emit a `RE-INVITE` (an `INVITE` reusing the existing
  `session_id`). If the counterparty accepts, the session remains in
  `ESTABLISHED` without replaying data frames already delivered.
- **Signaling channel drop**: Active sessions MUST continue to count
  down their TTL. Data frames MAY continue to flow until TTL expires.
  Upon reconnection, the peer MUST emit `REGISTER` and MAY issue
  `NOTIFY` frames to resynchronise presence state.

### 4.4 Example Flow

```
Peer A                                      Peer B
  │                                            │
  │── INVITE (session_id, caps) ───────────────►│   signaling
  │                                            │
  │◄── 200 OK (session_id, accepted_caps) ─────│   signaling
  │                                            │
  │── ACK (session_id) ────────────────────────►│   signaling
  │                                            │
  │════ Data Channel Open ══════════════════════│
  │                                            │
  │── dispatch (session_id, payload) ──────────►│   data
  │                                            │
  │◄── response (session_id, result) ──────────│   data
  │                                            │
  │── BYE (session_id) ────────────────────────►│   signaling
  │                                            │
  │════ Data Channel Closed ════════════════════│
```

The `session_id` MUST be copied verbatim into every subsequent frame of
the same session, on both channels.

---

## 5. Signaling Primitives

### 5.1 REGISTER

`REGISTER` announces a peer's presence and advertises its capabilities.
A peer MUST emit a `REGISTER` as the first signaling frame after
authenticating with the hub (see ARC-4601 §15.6).

```json
{"channel":"sig","type":"REGISTER","clan_id":"peer-a",
 "capabilities":["signaling_v1","receipts","multicast"],
 "protocol_version":"0.5.0",
 "ts":"2026-04-05T12:00:00Z"}
```

A `REGISTER` MUST be re-emitted on reconnection. A peer MAY emit
`REGISTER` at any time to update its capability set.

### 5.2 INVITE

`INVITE` requests a new session. The caller proposes the session
identifier, target peer, and the capabilities it intends to use.

```json
{"channel":"sig","type":"INVITE","session_id":"3f2b...91a7",
 "src":"peer-a","dst":"peer-b",
 "intent":"dispatch",
 "caps":["dispatch","response"],
 "ts":"2026-04-05T12:00:01Z"}
```

| Field        | Required | Description                                            |
|--------------|----------|--------------------------------------------------------|
| `session_id` | YES      | Caller-assigned identifier, unique per peer pair       |
| `src`, `dst` | YES      | Same semantics as ARC-5322                             |
| `intent`     | YES      | High-level purpose: `dispatch`, `data_cross`, `sync`   |
| `caps`       | YES      | Data channel capabilities the caller intends to use    |

A callee MUST respond with exactly one of `200 OK`, a `4xx`, or a `5xx`
frame within the `INVITE` timeout window.

### 5.3 200 OK / 4xx / 5xx

These are session setup responses. They reuse HTTP/SIP status semantics:

| Code  | Class         | Meaning                                          |
|-------|---------------|--------------------------------------------------|
| 200   | Success       | Session accepted                                 |
| 400   | Client error  | Malformed `INVITE` (missing field, bad cap)      |
| 403   | Client error  | Peer refuses (policy, firewall, capacity)        |
| 408   | Client error  | Invite timeout observed by callee                |
| 415   | Client error  | Unsupported capability                           |
| 480   | Client error  | Callee temporarily unavailable (busy)            |
| 500   | Server error  | Internal failure on the callee                   |
| 503   | Server error  | Callee overloaded                                |

Example acceptance:

```json
{"channel":"sig","type":"200","session_id":"3f2b...91a7",
 "src":"peer-b","dst":"peer-a",
 "accepted_caps":["dispatch","response"],
 "ts":"2026-04-05T12:00:02Z"}
```

Example rejection:

```json
{"channel":"sig","type":"403","session_id":"3f2b...91a7",
 "src":"peer-b","dst":"peer-a",
 "reason":"firewall_denied",
 "ts":"2026-04-05T12:00:02Z"}
```

A `4xx` or `5xx` response MUST include a `reason` field with a short
human-readable string. Implementations MUST NOT place sensitive
information in `reason`.

### 5.4 ACK

`ACK` confirms that the caller has received the `200 OK` and is ready
to exchange data. The session transitions to `ESTABLISHED` upon emission
of `ACK` by the caller and upon receipt of `ACK` by the callee.

```json
{"channel":"sig","type":"ACK","session_id":"3f2b...91a7",
 "src":"peer-a","dst":"peer-b",
 "ts":"2026-04-05T12:00:03Z"}
```

### 5.5 BYE

`BYE` terminates an established session. Either peer MAY emit `BYE`
at any time. The receiving peer MUST transition the session to
`TERMINATING` and release any resources bound to `session_id`.

```json
{"channel":"sig","type":"BYE","session_id":"3f2b...91a7",
 "src":"peer-a","dst":"peer-b",
 "reason":"quest_complete",
 "ts":"2026-04-05T12:00:35Z"}
```

### 5.6 OPTIONS

`OPTIONS` queries a peer's capabilities without establishing a session.
It is useful for service discovery and health checks.

```json
{"channel":"sig","type":"OPTIONS","src":"peer-a","dst":"peer-b",
 "ts":"2026-04-05T12:00:00Z"}
```

A peer receiving `OPTIONS` MUST respond with a `REGISTER`-style frame
scoped to the requester.

### 5.7 NOTIFY

`NOTIFY` pushes state updates to a peer or to the broadcast address.
Unlike `REGISTER`, `NOTIFY` carries a typed payload describing the
nature of the update.

```json
{"channel":"sig","type":"NOTIFY","src":"peer-a","dst":"*",
 "event":"presence_changed",
 "state":"busy",
 "ts":"2026-04-05T12:00:00Z"}
```

Recognised `event` values include `presence_changed`, `roster_update`,
`capability_changed`. Implementations MAY define additional events,
but MUST prefix non-standard events with `x-` to avoid collision with
future normative events.

### 5.8 PING / PONG

`PING` and `PONG` are keepalives for the signaling channel. They MUST
NOT be interpreted as session setup frames. A peer SHOULD emit `PING`
after the keepalive interval (default 30 s) of signaling inactivity.
A `PING` MUST be answered with a `PONG` within the response window
(default 10 s).

```json
{"channel":"sig","type":"PING","src":"peer-a","dst":"peer-b",
 "ts":"2026-04-05T12:00:30Z"}

{"channel":"sig","type":"PONG","src":"peer-b","dst":"peer-a",
 "ts":"2026-04-05T12:00:30Z"}
```

### 5.9 JOIN / LEAVE

`JOIN` and `LEAVE` manage multicast group membership. See Section 9.2.

---

## 6. Wire Format

### 6.1 Channel Discrimination

Every frame governed by this specification MUST carry a `channel`
field with value `"sig"` or `"data"`. Frames lacking a `channel` field
are treated as legacy single-channel frames and routed according to
ARC-4601 §15 (backward compatibility, see Section 12).

```abnf
channel = "sig" / "data"
```

### 6.2 Signaling Frame Schema

A signaling frame is a JSON object with the following structure:

```json
{
  "channel": "sig",
  "type":    "<signaling primitive>",
  "src":     "<clan_id>",
  "dst":     "<clan_id> | *",
  "ts":      "<ISO-8601 instant>",
  "session_id": "<uuid>",          // when applicable
  "...":     "<primitive-specific fields>"
}
```

| Field        | Required | Description                                          |
|--------------|----------|------------------------------------------------------|
| `channel`    | MUST     | Literal string `"sig"`                               |
| `type`       | MUST     | One of the primitives in Section 5                   |
| `src`        | MUST     | Originating peer identifier (same semantics as ARC-5322 §4.2.2) |
| `dst`        | MUST     | Destination peer identifier or `*`                   |
| `ts`         | MUST     | ISO-8601 instant (date-time with timezone)           |
| `session_id` | Conditional | REQUIRED on `INVITE`, `200`, `4xx`, `5xx`, `ACK`, `BYE` |
| `ref`        | OPTIONAL | Message reference for receipt correlation (Section 8)|

The signaling frame timestamp `ts` MUST use a full instant
(`YYYY-MM-DDTHH:MM:SSZ`), distinct from the day-granularity `ts` field
of ARC-5322. This difference is normative: session control is latency
sensitive and requires sub-second precision.

### 6.3 Signaling Frame Constraints

- A signaling frame MUST NOT exceed 512 bytes including all JSON
  delimiters.
- A peer MUST NOT emit more than 60 signaling frames per minute to
  any single destination on the signaling channel. Implementations
  MUST enforce this rate limit at the hub (ARC-4601 §15.7 queue
  behaviour) and SHOULD enforce it locally before emission.
- Signaling frames MUST NOT contain application payload. Payload
  belongs on the data channel.
- Signaling frames MUST NOT be encrypted at the application layer.
  Transport security (TLS/WSS per ARC-4601 §15.4) still applies.

### 6.4 Data Frame Schema

A data frame wraps a full ARC-5322 message and tags it with a
`session_id`:

```json
{
  "channel":    "data",
  "session_id": "<uuid>",
  "payload":    <ARC-5322 message>
}
```

| Field        | Required | Description                                     |
|--------------|----------|-------------------------------------------------|
| `channel`    | MUST     | Literal string `"data"`                         |
| `session_id` | MUST     | Identifier of an `ESTABLISHED` session          |
| `payload`    | MUST     | A valid ARC-5322 message                        |

The `payload` MAY be encrypted in accordance with ARC-8446. Data frames
are opaque to the hub (see Section 7.1).

### 6.5 HELLO Extension

Upon connection to the hub, a peer MUST emit a `hello` frame advertising
its protocol version and supported channels. This extends ARC-4601
§15.5 without breaking it:

```json
{
  "type": "hello",
  "clan_id": "peer-a",
  "protocol_version": "0.5.0",
  "capabilities": ["e2e_crypto","signaling_v1"],
  "channels": ["sig","data"]
}
```

A hub that does not recognise `signaling_v1` MUST fall back to the
legacy single-channel wire format. A peer that does not receive a
matching capability in the hub's `auth_ok` response MUST revert to
legacy mode for the duration of that connection.

---

## 7. Hub Integration

### 7.1 Channel-Aware Routing

A hub compliant with this specification MUST inspect the `channel`
field of every incoming frame and apply the following routing rules:

| Channel | Routing Behaviour                                                     |
|---------|------------------------------------------------------------------------|
| `sig`   | Active routing. The hub parses `type`, validates `src`/`dst`, applies rate limiting, and MAY act on the frame (for example, maintaining group membership for `JOIN`/`LEAVE`). |
| `data`  | Opaque forwarding. The hub forwards the frame to `dst` without inspecting `payload`, consistent with ARC-4601 §15.8 (E2E Passthrough). |

A hub MUST NOT inspect or modify the `payload` field of a data frame.
A hub MUST NOT make routing decisions based on the contents of an
encrypted payload.

### 7.2 Session State Tracking

A hub MUST maintain a table of active sessions with the following
minimum schema:

| Column       | Type    | Purpose                                        |
|--------------|---------|------------------------------------------------|
| `session_id` | string  | Primary key                                    |
| `src`        | string  | Calling peer                                   |
| `dst`        | string  | Called peer                                    |
| `state`      | enum    | One of the states in Section 4.1               |
| `opened_at`  | instant | Timestamp of the original `INVITE`             |
| `last_seen`  | instant | Most recent signaling or data frame            |
| `receipt`    | array   | Receipt stages requested (Section 8.4) or null |

A hub MUST expire session rows whose `last_seen` exceeds the session
TTL. A hub MUST reject data frames referencing a `session_id` not
present in the session table with a `404` equivalent error on the
signaling channel.

### 7.3 Backward Compatibility

A hub MUST accept legacy frames (ARC-4601 §15.5 `{"type":"msg", ...}`)
from peers that do not advertise `signaling_v1`. Legacy traffic is
routed as a single logical channel without session tracking, consistent
with pre-ATR-Q.931 behaviour.

### 7.4 Relationship with ARC-4601 §18

The wire-level changes required by this specification (channel field
handling, session table, receipt frame emission) are introduced as a
forthcoming amendment to ARC-4601 (referred to here as §18 for
tracking purposes). That amendment is out of scope for this document;
ATR-Q.931 defines the protocol obligations, ARC-4601 §18 will define
the hub-side implementation requirements.

---

## 8. Delivery Receipts

### 8.1 Four-Stage Model

A receipt represents a checkpoint in the delivery path of a message.
Four stages are defined:

| Stage       | Meaning                                                           |
|-------------|-------------------------------------------------------------------|
| `SENT`      | The hub has accepted the message from the sender and queued it   |
|             | for routing.                                                      |
| `DELIVERED` | The recipient peer has received the message and written it to   |
|             | its inbox.                                                        |
| `READ`      | The recipient peer's Agent Node has bridged the message to the   |
|             | application layer (L4 per ATR-X.200).                             |
| `PROCESSED` | The recipient's application has produced a result or dispatched  |
|             | an action in response.                                            |

The stages form a strict total order: `SENT` < `DELIVERED` < `READ`
< `PROCESSED`. A receipt for a later stage implies that all earlier
stages have been satisfied, but implementations MUST NOT synthesise
earlier receipts from a later one.

```
Sender               Hub                   Receiver
  │                   │                      │
  │── msg ───────────►│                      │
  │◄── SENT ──────────│                      │   ✓
  │                   │── msg ──────────────►│
  │                   │◄── DELIVERED ────────│   ✓✓
  │◄── DELIVERED ─────│                      │
  │                   │                      │── bridge to L4
  │                   │◄── READ ─────────────│   ✓✓
  │◄── READ ──────────│                      │
  │                   │                      │── action dispatched
  │                   │◄── PROCESSED ────────│   ✓✓
  │◄── PROCESSED ─────│                      │
```

### 8.2 Receipt Frame Format

Receipts travel on the signaling channel. Each receipt is a distinct
frame:

```json
{"channel":"sig","type":"SENT","ref":"peer-a-067",
 "ts":"2026-04-05T12:00:01Z"}

{"channel":"sig","type":"DELIVERED","ref":"peer-a-067",
 "peer":"peer-b","ts":"2026-04-05T12:00:03Z"}

{"channel":"sig","type":"READ","ref":"peer-a-067",
 "peer":"peer-b","ts":"2026-04-05T12:00:05Z"}

{"channel":"sig","type":"PROCESSED","ref":"peer-a-067",
 "peer":"peer-b","result":"OK",
 "agent":"cross-clan-dispatcher",
 "ts":"2026-04-05T12:00:35Z"}
```

| Field    | Required                      | Description                         |
|----------|-------------------------------|-------------------------------------|
| `type`   | MUST                          | One of `SENT`, `DELIVERED`, `READ`, `PROCESSED` |
| `ref`    | MUST                          | The `ref` copied from the original message     |
| `peer`   | MUST (except `SENT`)          | The peer confirming the stage                   |
| `ts`     | MUST                          | Instant at which the stage completed            |
| `result` | OPTIONAL (only on `PROCESSED`)| Short status: `OK`, `FAIL`, custom token        |
| `agent`  | OPTIONAL (only on `PROCESSED`)| The agent that executed the action              |

### 8.3 Message Reference

Each message that participates in the receipt model MUST carry a
`ref` field in its ARC-5322 envelope. The `ref` is sender-assigned
and SHOULD follow the form `<clan_id>-<sequence>` for human
readability. Implementations MAY additionally include an opaque
`msg_id` (UUID) for programmatic correlation; `msg_id` is OPTIONAL.

Examples of valid `ref` values:

- `peer-a-067`
- `clan-x-2026-04-05-15`
- `dispatch-90f2`

The `ref` MUST be unique within a 24-hour window per sender. A
collision with an earlier `ref` results in undefined receipt
correlation.

### 8.4 Opt-In Behaviour

Receipts are opt-in. A sender that requires receipts MUST include a
`receipt` array in the ARC-5322 envelope listing the stages it wishes
to observe:

```json
{"ts":"2026-04-05","src":"peer-a","dst":"peer-b",
 "type":"dispatch","msg":"QUEST-007 payload",
 "ttl":3,"ack":[],
 "ref":"peer-a-067",
 "receipt":["DELIVERED","READ","PROCESSED"]}
```

Rules:

- A hub MUST NOT emit receipt frames for a message whose envelope
  does not contain a `receipt` array.
- A hub MUST emit exactly one receipt frame per requested stage per
  message per peer.
- A hub MUST NOT emit receipts for stages not present in the
  `receipt` array.
- If a sender requests `PROCESSED` but the recipient is unable to
  emit it (e.g., the message does not map to an action), the hub
  SHOULD NOT synthesise a `PROCESSED` frame. The absence of a
  receipt is itself a signal.
- Absence of a `receipt` array means fire-and-forget semantics
  (current default, backward compatible).

### 8.5 Aggregated Delivery Reports

For multicast or broadcast messages, a sender MAY request an
aggregated delivery report. The flow is:

```json
// Sender requests the report
{"channel":"sig","type":"REPORT_REQUEST","ref":"quest-cross-002",
 "ts":"2026-04-05T12:01:00Z"}

// Hub responds
{"channel":"sig","type":"DELIVERY_REPORT","ref":"quest-cross-002",
 "report":[
   {"peer":"peer-a","sent":true,"delivered":true,"read":true,"processed":true},
   {"peer":"peer-b","sent":true,"delivered":true,"read":false,"processed":false}
 ],
 "ts":"2026-04-05T12:01:00Z"}
```

A hub MUST maintain aggregated receipt state for a message for at
least the TTL of the original envelope. After TTL expiry the hub MAY
garbage-collect the state, after which a `REPORT_REQUEST` for that
`ref` SHOULD return a `404` equivalent on the signaling channel.

### 8.6 Mapping to 3GPP TS 23.040 SMS Status Report

The receipt model is intentionally aligned with the SMS delivery
report defined in 3GPP TS 23.040 §9.2.3.15. The mapping is:

| ATR-Q.931 field | 3GPP TS 23.040 element                 |
|-----------------|----------------------------------------|
| `ref`           | TP-MR (Message Reference)              |
| `peer`          | TP-RA (Recipient Address)              |
| `ts` (SENT)     | TP-SCTS (Service Centre Time Stamp)    |
| `ts` (DELIVERED)| TP-DT (Discharge Time)                 |
| `type`          | TP-ST (Status: delivered/failed/pending)|

`READ` and `PROCESSED` have no direct SMS counterpart. `READ` is
modelled after XMPP XEP-0333 (Chat Markers) and the WhatsApp double
blue check. `PROCESSED` is Amaru-specific.

---

## 9. Addressing Modes

### 9.1 Unicast and Broadcast

Unicast (`dst = "<clan_id>"`) and broadcast (`dst = "*"`) are defined
by ARC-5322 and ARC-4601. ATR-Q.931 does not modify their semantics.

### 9.2 Multicast Groups

A multicast group is a named set of peers that jointly receive
messages addressed to the group. The group address takes the form
`group:<name>` where `<name>` follows the `clan_id` grammar from
ARC-5322 §4.2.2.

Group membership is managed by two signaling primitives:

```json
{"channel":"sig","type":"JOIN","group":"quest-007-team",
 "src":"peer-a","ts":"2026-04-05T12:00:00Z"}

{"channel":"sig","type":"LEAVE","group":"quest-007-team",
 "src":"peer-a","ts":"2026-04-05T13:00:00Z"}
```

Rules:

- A hub MUST maintain a membership table mapping group names to the
  set of currently joined peers.
- A message with `dst = "group:<name>"` MUST be fanned out by the hub
  to every current member of the group, excluding the sender.
- Group membership is **ephemeral** in this revision: a peer that
  disconnects is implicitly removed from all groups it had joined.
  Persistent groups are out of scope and will be addressed in a
  future revision.
- A hub MUST reject a `JOIN` from a peer that is not authenticated
  (ARC-4601 §15.6).

### 9.3 Anycast

Anycast addresses a single member of a named service class. The
address takes the form `any:<service>` where `<service>` is a
service identifier (for example `any:cross-clan-dispatcher`).

- A hub MUST select exactly one peer that advertises the service via
  its `capabilities` list in `REGISTER`.
- Selection SHOULD be based on the peer's current queue depth
  (lowest first). Implementations MAY use round-robin as a fallback.
- Anycast messages MUST NOT be replicated; unlike multicast, only the
  selected peer receives the message.

---

## 10. Failure Isolation

The separation of signaling and data planes is designed to contain
failures rather than allow them to cascade.

| Failure                         | Signaling Impact               | Data Impact                                            |
|---------------------------------|--------------------------------|--------------------------------------------------------|
| Signaling channel drops         | Reconnect with backoff         | Data channels continue until session TTL               |
| Data channel drops              | `BYE` emitted via signaling    | Only the affected session is lost                      |
| Ping storm on signaling         | Rate-limited at 60 frames/min  | Zero impact (separate channel)                         |
| Large payload on data           | Zero impact                    | Backpressure via `NOTIFY state=paused`                 |
| Peer crash                      | Presence `NOTIFY` to offline   | All sessions for that peer transition to `TERMINATING` |
| Hub restart                     | All peers MUST re-`REGISTER`   | In-flight sessions MUST be resurrected via `RE-INVITE` |

A compliant implementation MUST NOT allow a failure in one channel to
invalidate state on the other beyond the rules described above.

---

## 11. Migration Path

ATR-Q.931 defines a staged migration. Only Phase 1 is normative in
this document; Phases 2 and 3 are informational and will be defined
in future specifications.

| Phase | Scope                                                          | Version Target | Normative Here |
|-------|----------------------------------------------------------------|----------------|----------------|
| 1     | Channel tagging, receipt envelope, session state machine       | v0.5.x         | YES            |
| 2     | Separate WebSocket connections for signaling and data         | v0.6.x         | NO             |
| 3     | Per-session ECDHE keys on the data channel                    | v1.0.0         | NO (see ARC-8446 future revision) |

Phase 1 is purely additive: a peer that ignores the `channel` field
remains interoperable with a compliant hub through the backward
compatibility rules in Section 12.

---

## 12. Backward Compatibility

### 12.1 Legacy Frame Handling

A peer MAY omit the `channel` field entirely. A hub receiving a
legacy frame MUST route it as if it were a data frame belonging to
an implicit legacy session. Legacy frames do not participate in the
state machine defined in Section 4.

### 12.2 Capability Negotiation

A peer signals support for ATR-Q.931 by including `signaling_v1` in
the `capabilities` array of its `hello` frame (Section 6.5). A hub
MUST confirm `signaling_v1` support in its `auth_ok` response for the
signaling plane to be considered active for that connection.

### 12.3 Receipt Absence

A sender that does not include a `receipt` array receives no receipts.
This matches pre-ATR-Q.931 behaviour (fire-and-forget) and is the
default mode.

### 12.4 Mixed Deployments

In a deployment where some peers support ATR-Q.931 and others do not,
the hub MUST track capabilities per connection and MUST NOT emit
signaling frames toward legacy peers. Delivery receipts MAY still be
emitted to the sender, with the `PROCESSED` stage omitted when the
recipient is legacy.

---

## 13. Conformance

An implementation conforms to ATR-Q.931 if it:

1. Implements the session state machine defined in Section 4.1 with
   all five states (`IDLE`, `INVITING`, `ACCEPTING`, `ESTABLISHED`,
   `TERMINATING`).
2. Enforces the timing constraints of Section 4.2, at least for the
   MUST-level timers (`INVITE` timeout, `ACK` timeout, `PING` response
   window).
3. Implements the signaling primitives of Section 5.1 through 5.8
   (`REGISTER`, `INVITE`, `200`, `4xx`, `5xx`, `ACK`, `BYE`, `OPTIONS`,
   `NOTIFY`, `PING`, `PONG`). `JOIN` / `LEAVE` are REQUIRED only if the
   implementation advertises the `multicast` capability.
4. Encodes frames according to Section 6 and rejects frames exceeding
   the 512-byte signaling limit.
5. Enforces the 60 frame/minute rate limit of Section 6.3.
6. Accepts the `channel` discriminator and treats frames lacking it
   as legacy per Section 12.1.
7. If acting as a hub, implements channel-aware routing per Section
   7.1 and maintains the session table per Section 7.2.
8. Implements the receipt stages it advertises via capabilities. A
   peer advertising `receipts` MUST support at minimum the `SENT` and
   `DELIVERED` stages; `READ` and `PROCESSED` are OPTIONAL.
9. Never synthesises a receipt stage it did not observe (Section 8.1).
10. Honours opt-in receipt semantics per Section 8.4 — no receipt is
    emitted for a message whose envelope lacks a `receipt` array.
11. Maintains ephemeral group membership per Section 9.2 and rejects
    group `JOIN` from unauthenticated peers.
12. Surfaces backward compatibility per Section 12, including refusal
    to emit signaling frames toward legacy peers.

Partial implementations MUST declare which primitives, receipt stages,
and addressing modes they support by listing the corresponding
capabilities in `REGISTER` and `hello` frames.

---

## 14. Security Considerations

### 14.1 Signaling Channel Exposure

The signaling channel is unencrypted at the application layer. The
hub inspects `type`, `src`, `dst`, `session_id`, and `ref` fields to
route and rate-limit. An adversary with access to the hub can observe
which peers are communicating, which sessions exist, and at what
frequency, but cannot observe payload contents.

Transport-level confidentiality (TLS/WSS per ARC-4601 §15.4) protects
signaling frames on the wire between peer and hub. Implementations
MUST use WSS or equivalent for any production deployment.

### 14.2 Receipt Metadata Leakage

Delivery receipts reveal timing information (`ts`) and, for the
`PROCESSED` stage, the identity of the executing agent. Implementations
MUST NOT place user-identifying strings in the `agent` field of a
`PROCESSED` receipt. Deployments sensitive to timing analysis SHOULD
disable the `PROCESSED` stage.

### 14.3 Rate Limiting as DoS Protection

The 60 frame/minute signaling limit (Section 6.3) is explicitly a DoS
containment mechanism. The P2 incident documented in the Amaru
bilateral testing record (241,000 broadcast events) is the motivating
example. A hub MUST enforce this limit independently of any peer's
self-reported state.

### 14.4 Session Hijacking

A hub MUST bind every `session_id` to the authenticated `src` that
opened it. A signaling frame referencing a `session_id` with a `src`
that does not match the binding MUST be rejected with a `403`
response.

### 14.5 Replay Protection

The `ts` field of each signaling frame MUST be checked against a
freshness window (RECOMMENDED: 60 seconds). Frames outside the window
MUST be discarded. This prevents simple replay of captured signaling
frames.

### 14.6 Group Membership Enumeration

The `DELIVERY_REPORT` frame exposes the set of peers in a group at
the time of reporting. Hubs MAY redact peers from a delivery report
if policy requires it; in that case the `report` array MUST omit
those entries entirely rather than misrepresent their status.

---

## 15. References

### 15.1 Normative

| Reference | Title                                                            |
|-----------|------------------------------------------------------------------|
| ARC-2119  | Requirement Level Keywords                                        |
| ARC-5322  | Message Format                                                   |
| ARC-4601  | Agent Node Protocol (especially §15 Hub Mode)                    |
| ARC-8446  | Encrypted Bus Protocol                                           |
| ATR-Q.700 | Out-of-Band Signaling                                            |
| ATR-X.200 | Reference Model                                                  |
| ARC-2314  | Skill Gateway Plane Architecture                                 |

### 15.2 External Normative

| Reference | Title                                                            |
|-----------|------------------------------------------------------------------|
| RFC 2119  | Key words for use in RFCs to Indicate Requirement Levels         |
| RFC 3261  | SIP: Session Initiation Protocol                                 |
| RFC 9562  | Universally Unique IDentifiers (UUIDs)                           |

### 15.3 Informative

| Reference       | Title                                                       |
|-----------------|-------------------------------------------------------------|
| ITU-T Q.931     | ISDN user-network interface layer 3 specification for basic call control |
| ITU-T Q.700     | Introduction to CCITT Signalling System No. 7               |
| 3GPP TS 23.040  | Technical realization of the Short Message Service — §9.2.3.15 Status Report |
| 3GPP TS 23.214  | Architecture enhancements for control and user plane separation |
| RFC 4566        | SDP: Session Description Protocol                            |
| XEP-0333        | Chat Markers (XMPP Extension)                                |
| Amaru Design    | `docs/architecture/signaling-plane-outline.md` (design outline, pre-spec) |

---

*ATR-Q.931 is part of the Amaru open standard. Licensed under MIT.*
