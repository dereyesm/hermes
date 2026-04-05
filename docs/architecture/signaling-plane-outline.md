# ARC Signaling/Data Plane Separation — Design Outline

> Pre-spec outline for the bilateral signaling protocol.
> Extends ATR-Q.700 (philosophy) and ARC-2314 (triple-plane) into concrete hub protocol.
> Addresses P0 from bilateral-issues-plan.md.

## Problem Statement

The current hub (ARC-4601) multiplexes control messages (presence, routing, auth, keepalive) and data messages (quest dispatch, responses, bus sync) on a single WebSocket connection. This creates cascading failures:

1. **Ping storm** (P2): 241K broadcast events overwhelmed the data path, causing inbox corruption and cursor invalidation
2. **Routing table loss**: reconnection to regain presence clears routing state, disrupting active data flows
3. **No session concept**: data messages are fire-and-forget, no correlation between request and response
4. **No backpressure**: a slow consumer gets flooded with both signaling and data

## Telecom Lineage

| Telecom Standard | HERMES Analog | Role |
|-----------------|---------------|------|
| SIP (RFC 3261) | Signaling channel | Session setup, presence, capabilities negotiation |
| RTP/SRTP (RFC 3550) | Data channel | Encrypted quest dispatch, responses |
| SDP (RFC 4566) | Capabilities exchange | Agent catalog, supported message types |
| SS7 (Q.700) | Bus philosophy | Out-of-band coordination (ATR-Q.700, already spec'd) |
| 3GPP CUPS (TS 23.214) | Plane separation | Control/User plane split (ARC-2314, already spec'd) |

## Proposed Architecture

```
Peer A (DANI)                                          Peer B (JEI)
┌─────────────────┐                                   ┌─────────────────┐
│                  │     Signaling Channel (WS #1)     │                  │
│  Agent Node      │◄─────────────────────────────────►│  Agent Node      │
│                  │     always-on, lightweight         │                  │
│  ┌────────────┐  │                                   │  ┌────────────┐  │
│  │ Signaling  │  │     Data Channel (WS #2, N)       │  │ Signaling  │  │
│  │ Controller │  │◄─────────────────────────────────►│  │ Controller │  │
│  └────────────┘  │     on-demand, encrypted, per-    │  └────────────┘  │
│                  │     session (AES-256-GCM)          │                  │
└─────────────────┘                                   └─────────────────┘
```

## 1. Signaling Channel

**Purpose**: Always-on lightweight connection for coordination.

**Message types** (signaling-only):
- `REGISTER` — Announce presence and capabilities to peer
- `INVITE` — Request a data session (quest, sync, data_cross)
- `200 OK` / `4xx` / `5xx` — Session setup response (SIP response model)
- `ACK` — Confirm session established
- `BYE` — Tear down data session
- `OPTIONS` — Query peer capabilities without session setup
- `NOTIFY` — Push state updates (presence changes, peer roster)
- `PING/PONG` — Keepalive (already exists)

**Properties**:
- Max message size: 512 bytes (signals only, never payloads)
- Rate limit: 60 msgs/min per peer (generous for signaling)
- Reconnection: independent from data channel
- No encryption required (no sensitive data — session tokens are opaque)

## 2. Data Channel

**Purpose**: On-demand encrypted tunnels for actual payload exchange.

**Message types** (data-only):
- `dispatch` — Quest/task dispatch to peer
- `response` — Result of dispatched work
- `data_cross` — Cross-namespace data exchange
- `bus_sync` — Selective bus state replication
- `stream` — Chunked transfer for large payloads (future)

**Properties**:
- Established via signaling INVITE/OK/ACK
- Each session has a `session_id` (UUID, referenced in both channels)
- E2E encrypted (ARC-8446: AES-256-GCM, ECDHE key per session)
- Rate limit: configurable per peer, per session type
- Backpressure: peer can send PAUSE/RESUME via signaling
- TTL: sessions expire after configurable timeout (default 300s)

## 3. Session Lifecycle

```
DANI                              JEI
  │                                │
  │──── INVITE (quest, caps) ─────►│  signaling
  │                                │
  │◄─── 200 OK (session_id) ──────│  signaling
  │                                │
  │──── ACK ──────────────────────►│  signaling
  │                                │
  │════ Data Channel Open ═════════│  data (new WS or muxed)
  │                                │
  │──── dispatch (QUEST-007) ─────►│  data (encrypted)
  │                                │
  │◄─── response (OK, result) ────│  data (encrypted)
  │                                │
  │──── BYE ──────────────────────►│  signaling
  │                                │
  │════ Data Channel Closed ═══════│
```

**Error cases**:
- INVITE timeout (no response in 10s) → retry with backoff
- Data channel drops → signaling sends RE-INVITE to reestablish
- Signaling drops → data channels continue until TTL expires, then graceful shutdown

## 4. Failure Isolation

| Failure | Signaling Impact | Data Impact |
|---------|-----------------|-------------|
| Signaling WS drops | Reconnect with backoff | Data channels continue (TTL-bounded) |
| Data WS drops | BYE sent via signaling | Only affected session lost |
| Ping storm on signaling | Rate-limited at 60/min | Zero impact (separate channel) |
| Large payload on data | Zero impact | Backpressure via PAUSE signal |
| Peer crash | Presence update → offline | All sessions terminated (BYE) |

## 5. Wire Protocol Changes

### Current (v0.4.2)
```json
{"type": "msg", "payload": {"src": "dani", "dst": "jei", "type": "dispatch", "msg": "..."}}
```

### Proposed (v0.5)
```json
// Signaling frame
{"channel": "sig", "type": "INVITE", "session_id": "uuid", "caps": ["dispatch", "data_cross"]}

// Data frame
{"channel": "data", "session_id": "uuid", "payload": {"src": "dani", "dst": "jei", ...}}
```

**Backward compatibility**: Hub accepts both formats. Old clients (v0.4.x) treated as single-channel (legacy mode). New clients negotiate channel separation during HELLO.

### HELLO extension
```json
{
  "type": "hello",
  "clan_id": "momoshod",
  "protocol_version": "0.5.0",
  "capabilities": ["e2e_crypto", "signaling_v1"],
  "channels": ["signaling", "data"]
}
```

If peer doesn't advertise `signaling_v1`, fallback to current single-channel mode.

## 6. Migration Path

| Phase | What | When |
|-------|------|------|
| **Phase 1** | Tag existing messages with `channel` field (backward compatible) | v0.5.0 |
| **Phase 2** | Separate WebSocket connections for signaling vs data | v0.6.0 |
| **Phase 3** | Per-session ECDHE keys on data channel (Noise IK, ARC-4601 §16) | v1.0.0 |

Phase 1 is purely additive — no breaking changes. Old clients ignore the `channel` field.

## 7. Spec Placement

This outline maps to two planned specs in INDEX.md:

| Spec | Title | Status |
|------|-------|--------|
| ATR-Q.931 | Session Setup Signaling | PLANNED → this outline |
| ARC-4601 §18 | Signaling/Data Channel Separation | Extension to existing Agent Node spec |

**Recommendation**: ATR-Q.931 as standalone spec (session lifecycle, message types, failure isolation). ARC-4601 amendment for wire protocol changes (channel field, HELLO extension).

## 8. Addressing Modes (IP Analogy)

Current HERMES only supports unicast (`dst: "jei"`) and broadcast (`dst: "*"`).
Multi-clan quests require multicast — a message to a defined group.

| Mode | IP Analogy | HERMES Wire Format | Use Case |
|------|-----------|-------------------|----------|
| **Unicast** | dst = single IP | `"dst": "jei"` | Direct peer message |
| **Broadcast** | dst = 255.255.255.255 | `"dst": "*"` | State announcements, alerts |
| **Multicast** | dst = 224.x.x.x (group) | `"dst": "group:quest-007-team"` | Multi-clan quest dispatch |
| **Anycast** | dst = nearest replica | `"dst": "any:cross-clan-dispatcher"` | Load-balanced agent dispatch |

### Multicast groups

```json
// Signaling: JOIN group (SIP SUBSCRIBE analog)
{"channel": "sig", "type": "JOIN", "group": "quest-007-team", "clan_id": "jei"}

// Signaling: LEAVE group
{"channel": "sig", "type": "LEAVE", "group": "quest-007-team", "clan_id": "jei"}

// Data: message to group (all members receive)
{"channel": "data", "dst": "group:quest-007-team", "payload": {...}}
```

Hub maintains group membership table. Fan-out is hub responsibility (like IGMP snooping in switches).

### Anycast

For dispatching to "whoever has capacity" — useful when multiple clans have the same agent type:
```json
{"dst": "any:cross-clan-dispatcher", "payload": {...}}
```
Hub routes to the peer with lowest queue depth (or round-robin). Modeled after DNS anycast / SRV records.

## 9. Header Privacy (IPsec Tunnel Mode Analogy)

Current wire format exposes `src`, `dst`, `type` in plaintext. The hub needs `dst` to route,
but peer-to-peer messages don't need the hub to see `src` or `type`.

### Transport Mode (current — ARC-8446)

```
┌──────────────────────────────────────────────┐
│ PLAINTEXT HEADER          │ ENCRYPTED PAYLOAD │
│ src: "dani"               │ AES-256-GCM(msg)  │
│ dst: "jei"                │                   │
│ type: "dispatch"          │                   │
└──────────────────────────────────────────────┘
Hub sees: who talks to whom, message type, frequency
```

### Tunnel Mode (proposed — ARC-8446 extension)

```
┌────────────────────────────────────────────────────────────┐
│ OUTER HEADER (hub sees)   │ ENCRYPTED INNER (peer decrypts)          │
│ dst: "jei"                │ AES-256-GCM(src + type + msg + metadata) │
│ session_id: "uuid"        │                                          │
└────────────────────────────────────────────────────────────┘
Hub sees: only destination + session. Cannot see source, type, or content.
```

**Trade-off**: Tunnel mode prevents hub from doing type-based routing or rate limiting by message type.
Solution: signaling channel stays in transport mode (hub needs to route), data channel uses tunnel mode
(hub is just a relay — consistent with E2E passthrough design).

**Reference**: IPsec (RFC 4301) Transport vs Tunnel mode. WireGuard uses only tunnel mode.

## 10. Delivery Reports & Read Receipts (SMS/WhatsApp Analogy)

Messages today are fire-and-forget. The sender has no confirmation that the message
was delivered, read, or processed. This section adds protocol-level delivery reports
modeled after SMS delivery reports (3GPP TS 23.040) and WhatsApp's check marks.

### Three-stage confirmation

```
Sender              Hub                 Receiver
  │                  │                    │
  │── msg ──────────►│                    │
  │◄── SENT ─────────│                    │   ✓  (hub accepted)
  │                  │── msg ────────────►│
  │                  │◄── DELIVERED ──────│   ✓✓ (arrived at inbox)
  │◄── DELIVERED ────│                    │
  │                  │                    │── agent processes
  │                  │◄── READ ──────────│   ✓✓ (bridged to bus)
  │◄── READ ─────────│                    │
  │                  │                    │── agent dispatches
  │                  │◄── PROCESSED ─────│   ✓✓ (action taken)
  │◄── PROCESSED ────│                    │
```

### Wire format (signaling channel)

```json
// Stage 1: SENT — hub confirms acceptance (immediate, same connection)
{"channel": "sig", "type": "SENT", "ref": "DANI-067", "ts": "2026-04-05T12:00:01Z"}

// Stage 2: DELIVERED — peer's hub listener received and wrote to inbox
{"channel": "sig", "type": "DELIVERED", "ref": "DANI-067", "peer": "jei", "ts": "2026-04-05T12:00:03Z"}

// Stage 3: READ — peer's AgentNode bridged to bus (hub_inbox_loop processed it)
{"channel": "sig", "type": "READ", "ref": "DANI-067", "peer": "jei", "ts": "2026-04-05T12:00:05Z"}

// Stage 4: PROCESSED — peer's agent executed the dispatch (optional, dispatch-only)
{"channel": "sig", "type": "PROCESSED", "ref": "DANI-067", "peer": "jei",
 "result": "OK", "agent": "cross-clan-dispatcher", "ts": "2026-04-05T12:00:35Z"}
```

### Telecom lineage

| HERMES Stage | SMS (3GPP TS 23.040) | WhatsApp | SIP (RFC 3261) | XMPP (XEP-0184) |
|-------------|---------------------|----------|----------------|------------------|
| SENT | RP-ACK (relay accepted) | Single gray check | 100 Trying | — |
| DELIVERED | Status-Report (delivered) | Double gray check | 200 OK | `<received/>` stanza |
| READ | — (no SMS equivalent) | Double blue check | — | `<displayed/>` (XEP-0333) |
| PROCESSED | — | — | — | — (HERMES-specific) |

### Message reference (`ref` field)

Each message needs a unique ID for receipt correlation. Options:

| Approach | Format | Pros | Cons |
|----------|--------|------|------|
| Sender-assigned | `DANI-067` | Human-readable, already in use | Not globally unique |
| UUID | `550e8400-e29b-41d4-a716-446655440000` | Globally unique | Not human-readable |
| Hash-based | SHA-256(src+ts+msg)[:12] | Deterministic, dedup-friendly | Collision risk at scale |

**Recommendation**: Sender-assigned ID (current CLAN-HERMES-SEQ pattern) as `ref`. Add optional
`msg_id` (UUID) to wire format for programmatic correlation. Both travel in the message envelope.

### Implementation in current architecture

| Stage | Where it happens | Code location | Effort |
|-------|-----------------|---------------|--------|
| SENT | Hub sends ack frame after routing | hub.py `_handle_connection` after `router.route()` | Low |
| DELIVERED | Hub listener writes to inbox, sends receipt | hub.py listener + new receipt frame | Medium |
| READ | `_hub_inbox_loop` sends receipt after bridge | agent.py L1840 after `write_message` | Medium |
| PROCESSED | `_execute_decision` sends receipt after dispatch | agent.py L1235 after `_forward_to_hub` | Low |

### Opt-in behavior

Not all messages need receipts. Add `receipt` field to message envelope:

```json
// Request all receipts
{"type": "msg", "payload": {...}, "receipt": ["DELIVERED", "READ", "PROCESSED"]}

// Request only delivery confirmation
{"type": "msg", "payload": {...}, "receipt": ["DELIVERED"]}

// No receipts (fire-and-forget, current default)
{"type": "msg", "payload": {...}}
```

Hub only generates receipts when `receipt` array is present. Backward compatible:
old clients don't send `receipt` field → no receipts generated.

### Delivery report (aggregated)

For broadcast/multicast messages, sender can request a delivery report — a summary
of all receipts for a given message:

```json
// Sender requests report
{"channel": "sig", "type": "REPORT_REQUEST", "ref": "QUEST-CROSS-002"}

// Hub responds with aggregated status
{"channel": "sig", "type": "DELIVERY_REPORT", "ref": "QUEST-CROSS-002",
 "report": [
   {"peer": "momoshod", "sent": true, "delivered": true, "read": true, "processed": true},
   {"peer": "jei", "sent": true, "delivered": true, "read": false, "processed": false}
 ],
 "ts": "2026-04-05T12:01:00Z"
}
```

Hub maintains receipt state per message (TTL-bounded, same as message TTL).
After TTL expires, receipt state is garbage-collected.

### Reference: 3GPP SMS Status Report (TS 23.040 §9.2.3.15)

The SMS delivery report contains:
- TP-MR (Message Reference): correlates with original message
- TP-RA (Recipient Address): who received it
- TP-SCTS (Service Centre Time Stamp): when SC received it
- TP-DT (Discharge Time): when delivered to recipient
- TP-ST (Status): delivered / failed / pending / temporary error

HERMES maps these directly:
- `ref` = TP-MR
- `peer` = TP-RA
- `ts` (SENT) = TP-SCTS
- `ts` (DELIVERED) = TP-DT
- `type` (DELIVERED/READ/PROCESSED) = TP-ST

## Open Questions

1. **Muxing vs separate WebSockets?** Muxing is simpler (one connection, `channel` field) but doesn't give true failure isolation. Separate WSs give real isolation but double connection overhead. Telecom precedent: separate bearers (SS7 link sets vs voice trunks). **Recommendation**: Start with muxing (Phase 1), migrate to separate (Phase 2).

2. **Session correlation for fire-and-forget?** Current dispatches are fire-and-forget. Adding session_id creates request-response correlation. Do we make sessions optional (backward compat) or mandatory (cleaner but breaking)? **Recommendation**: Optional in Phase 1, mandatory in Phase 2.

3. **Rate limiting scope?** Per-peer? Per-session? Per-channel? **Recommendation**: Per-channel per-peer. Signaling: 60/min. Data: configurable (default 600/min).

4. **Hub routing in multi-channel mode?** Hub currently routes all messages the same way. With channels, does the hub inspect `channel` to route differently? **Recommendation**: Hub routes signaling messages, forwards data messages opaquely (E2E passthrough, consistent with current design).

5. **Multicast group persistence?** Groups could be ephemeral (exist only while members are connected) or persistent (survive reconnections). **Recommendation**: Ephemeral for v0.5, persistent for v0.6 (requires group state in hub).

6. **Tunnel mode for signaling?** Signaling needs hub routing (transport mode). But should signaling metadata (which quests are active, who subscribes to what) be visible to hub? **Recommendation**: Signaling stays transport mode. Privacy-sensitive signaling (capability negotiation) can use per-message encryption within transport mode.
