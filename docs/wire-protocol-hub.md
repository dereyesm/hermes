# HERMES Hub Wire Protocol — Implementor's Guide

> Everything you need to connect two HERMES clans in real-time via WebSocket hub.
> This is the golden path: two laptops, one LAN, zero cloud.

**Status**: Living document. Canonical reference for ARC-4601 §15 Hub Mode.
**Version**: 0.2.0 (2026-04-04)

## Overview

A HERMES hub is a WebSocket server that routes messages between connected clans.
It provides:

- **Real-time delivery** via persistent WebSocket connections
- **Store-and-forward** for offline peers (per-peer FIFO queues with TTL)
- **Presence notifications** (online/offline broadcasts)
- **E2E passthrough** — the hub routes but never reads encrypted payloads

## Quick Start

```bash
# Clan A: Start hub
hermes hub start --dir ~/.hermes     # Listens on :8443

# Clan B: Connect to Clan A's hub
python3 scripts/quest005_hub_client.py --clan DANI --host 192.168.68.100 --port 8443
```

## 1. Transport

- **Protocol**: WebSocket (RFC 6455) over TCP
- **Default port**: 8443
- **URI format**: `ws://<host>:<port>` (LAN) or `wss://<host>:<port>` (TLS)
- **Frame encoding**: JSON text frames (UTF-8)
- **No binary frames** — all communication is JSON

## 2. Authentication

### 2.1 Ed25519 Challenge-Response (Normative — ARC-4601 §15.6)

This is the canonical auth flow. All HERMES hubs SHOULD implement this.

```
CLIENT                                  HUB
  |                                      |
  |─── HELLO ──────────────────────────► |
  |    {                                 |
  |      "type": "hello",               |
  |      "clan_id": "<your_clan_id>",   |
  |      "sign_pub": "<ed25519_hex_64>",|
  |      "protocol_version": "0.4.2a1", |
  |      "capabilities": []             |
  |    }                                 |
  |                                      |
  |◄── CHALLENGE ─────────────────────── |
  |    {                                 |
  |      "type": "challenge",            |
  |      "nonce": "<64_hex_chars>",      |
  |      "server_version": "0.4.2a1",   |
  |      "server_clan_id": "hub",       |
  |      "server_capabilities": [        |
  |        "store_forward",              |
  |        "e2e_passthrough",            |
  |        "presence"                    |
  |      ]                               |
  |    }                                 |
  |                                      |
  |─── AUTH ───────────────────────────► |
  |    {                                 |
  |      "type": "auth",                |
  |      "nonce_response": "<sig_hex>"  |
  |    }                                 |
  |                                      |
  |◄── AUTH_OK ────────────────────────  |
  |    {                                 |
  |      "type": "auth_ok",             |
  |      "clan_id": "<your_clan_id>",   |
  |      "queue_depth": 0               |
  |    }                                 |
```

**Signing the nonce** (critical — most common implementation bug):

```python
# CORRECT: sign the raw bytes of the nonce
nonce_bytes = bytes.fromhex(nonce_hex)
signature = ed25519_private_key.sign(nonce_bytes)
nonce_response = signature.hex()

# WRONG: signing the UTF-8 string
signature = ed25519_private_key.sign(nonce_hex.encode())  # DO NOT DO THIS
```

**Auth failure**:
```json
{"type": "auth_fail", "reason": "authentication failed"}
```
The hub closes the connection after sending `auth_fail`.

### 2.2 Legacy Auth (Backward Compatibility)

If the first frame is NOT `type: "hello"`, the hub enters legacy mode:
1. Extracts `clan_id` from `clan_id` or `from` field of first frame
2. Extracts `sign_pub` if present
3. Sends CHALLENGE, proceeds with challenge-response as normal
4. Accepts `clan_id`/`sign_pub` from either the first frame or the auth frame

This allows older clients to connect without modification.

### 2.3 Peer Registration

The hub must know a peer's public key before it can authenticate.
Keys are registered in `hub-peers.json`:

```json
{
  "peers": {
    "momoshod": {
      "sign_pub": "85a940d9b5a2f084...",
      "display_name": "Clan MomoshoD",
      "registered_at": "2026-03-25T16:59:12Z"
    },
    "jei": {
      "sign_pub": "b05d85e59a6dee74...",
      "display_name": "Clan JEI",
      "registered_at": "2026-03-18"
    }
  }
}
```

Generate this file: `hermes hub init`

## 3. Message Exchange

### 3.1 Sending Messages (Client → Hub)

All messages MUST use this frame format:

```json
{
  "type": "msg",
  "payload": {
    "src": "<sender_clan_id>",
    "dst": "<recipient_clan_id_or_*>",
    "type": "<message_type>",
    "msg": "<content>",
    "ttl": 3600
  }
}
```

**Fields**:

| Field | Required | Description |
|-------|----------|-------------|
| `type` | YES | Always `"msg"` for message frames |
| `payload` | YES | Nested dict with ARC-5322 envelope |
| `payload.src` | YES | Sender's clan_id |
| `payload.dst` | YES | Recipient clan_id or `"*"` for broadcast |
| `payload.type` | YES | Message type: `state`, `event`, `alert`, `dispatch` |
| `payload.msg` | YES | Message content (string, max ~4KB recommended) |
| `payload.ttl` | YES | Time-to-live in seconds (for store-forward queue) |
| `payload.ts` | NO | ISO-8601 timestamp (added by sender) |
| `payload.ack` | NO | Array of message IDs being acknowledged |

### 3.2 Common Bug: Missing Payload Wrapper

The hub SILENTLY DROPS messages that don't match the expected format.

```python
# Hub routing code (hub.py L507-511):
if frame_type == "msg":
    payload = frame.get("payload", {})
    if not isinstance(payload, dict) or "dst" not in payload:
        continue  # ← SILENTLY DROPPED — no error sent back
    await self.router.route(payload, clan_id)
```

**WRONG formats** (all silently dropped):
```json
{"type": "msg", "from": "JEI", "text": "hello"}
{"from": "DANI", "text": "hello"}
{"type": "msg", "text": "hello"}
{"type": "msg", "dst": "jei", "msg": "hello"}
```

**CORRECT**:
```json
{"type": "msg", "payload": {"src": "jei", "dst": "momoshod", "type": "event", "msg": "hello", "ttl": 3600}}
```

### 3.3 Receiving Messages (Hub → Client)

The hub delivers messages in the same frame format:

```json
{
  "type": "msg",
  "payload": {
    "src": "jei",
    "dst": "momoshod",
    "type": "event",
    "msg": "Hello from JEI!",
    "ttl": 3600
  }
}
```

Parse `frame.payload.src` for the sender and `frame.payload.msg` for the content.

### 3.4 Routing Rules

| `dst` value | Behavior | If recipient offline |
|-------------|----------|---------------------|
| `"momoshod"` | Unicast to momoshod | **Queued** (store-forward, delivered on reconnect) |
| `"*"` | Broadcast to all connected except sender | **NOT queued** (ephemeral) |

**Recommendation**: Use directed messages (`dst: "clan_id"`) for important content.
Broadcasts are useful for presence announcements but are lost if the peer is offline.

## 4. Hub-Initiated Frames

These frames are sent by the hub without client request.

### 4.1 Presence

When a peer connects or disconnects, the hub broadcasts to all other connected peers:

```json
{"type": "presence", "clan_id": "jei", "status": "online"}
{"type": "presence", "clan_id": "jei", "status": "offline"}
```

### 4.2 Drain (Queued Messages)

When a peer authenticates, the hub delivers any messages queued during their absence:

```json
{
  "type": "drain",
  "messages": [
    {"src": "momoshod", "dst": "jei", "type": "event", "msg": "You were offline", "ttl": 3600}
  ],
  "remaining": 0
}
```

Multiple drain frames may be sent (batch size = 100). Check `remaining > 0` for more batches.

### 4.3 Pong

Response to client ping:

```json
{"type": "pong", "ts": "2026-04-03T20:00:00Z", "queue_depth": 0}
```

## 5. Keepalive

Send periodic pings to detect dead connections:

```json
{"type": "ping"}
```

Recommended interval: 30-60 seconds. The hub responds with a `pong` frame.

## 6. Disconnect

When a client disconnects (WebSocket close or network failure):

1. Hub removes peer from connection table
2. Hub broadcasts `{"type": "presence", "clan_id": "...", "status": "offline"}`
3. Future directed messages for this peer are queued (store-forward)
4. Queued messages are delivered via `drain` on next authentication

## 7. Full Session Timeline

```
Time  Event                          JEI Client        Hub        DANI Client
────  ─────                          ──────────        ───        ───────────
T+0   JEI connects                   → HELLO           
T+0   Hub challenges                                   → CHALLENGE
T+0   JEI signs nonce                → AUTH
T+0   Hub authenticates                                → AUTH_OK
T+0   Presence broadcast                                          ← PRESENCE(jei:online)
T+1   Drain (if queued msgs)         ← DRAIN
T+5   JEI sends message              → MSG(dst:momoshod)
T+5   Hub routes to DANI                                          ← MSG(src:jei)
T+6   DANI replies                                     ← MSG(dst:jei)
T+6   Hub routes to JEI              ← MSG(src:momoshod)
T+60  JEI keepalive                  → PING
T+60  Hub responds                   ← PONG
T+120 JEI disconnects                [close]
T+120 Presence broadcast                                          ← PRESENCE(jei:offline)
T+130 DANI sends while JEI offline                     ← MSG(dst:jei)  → queued
T+200 JEI reconnects                 → HELLO/AUTH
T+200 Hub drains queue               ← DRAIN(1 msg)
```

## 8. Implementation Checklist

For a minimal client that can participate in HERMES hub bilateral:

- [ ] WebSocket connection to `ws://host:port`
- [ ] Ed25519 key pair (sign only — `sign_private`, `sign_public`)
- [ ] HELLO frame with `clan_id` + `sign_pub`
- [ ] Sign nonce as `bytes.fromhex(nonce)` (NOT UTF-8 string)
- [ ] Send messages with `{"type": "msg", "payload": {"src", "dst", "type", "msg", "ttl"}}`
- [ ] Parse received `type: "msg"` frames → extract `payload.src` and `payload.msg`
- [ ] Handle `type: "presence"` frames (peer online/offline)
- [ ] Handle `type: "drain"` frames (queued messages on reconnect)
- [ ] Send `{"type": "ping"}` every 30-60s
- [ ] Auto-reconnect with exponential backoff on disconnect

## 9. S2S Federation Wire Format (ARC-4601 §17)

When two hubs connect via S2S, the HELLO frame includes `"role": "hub"` and a `peers` array
listing the clans reachable through that hub. After authentication, message routing works
identically to client connections — but common pitfalls apply.

### 9.1 S2S HELLO (Hub-to-Hub)

```json
{
  "type": "hello",
  "clan_id": "jei-hub",
  "sign_pub": "b05d85e59a6dee74...",
  "protocol_version": "0.4.2a1",
  "capabilities": ["e2e_crypto", "s2s"],
  "role": "hub",
  "peers": ["jei"]
}
```

The `peers` array tells the receiving hub which clans are reachable via this S2S link.
The receiving hub adds these to its federation routing table.

### 9.2 S2S Message Routing

Messages sent via S2S MUST use the same `{"type":"msg","payload":{...}}` wrapper as
client messages. The hub does not distinguish between locally-originated and S2S-originated
messages at the routing layer.

```json
{"type": "msg", "payload": {"src": "jei", "dst": "momoshod", "type": "event", "msg": "Hello from JEI via S2S", "ts": "2026-04-04", "ttl": 7}}
```

**Common mistake**: Sending the payload without the `{"type":"msg","payload":{...}}` wrapper.
The hub message loop only processes frames with `type == "msg"` — all other frame types
are silently ignored (except `ping` and `s2s_presence`).

### 9.3 S2S Key Format (HERMES Native)

The S2S hub authenticates using the same Ed25519 challenge-response as clients.
Key files MUST be in HERMES native JSON format (not PEM):

```json
{
  "sign_private": "<64-char hex>",
  "sign_public": "<64-char hex>",
  "dh_private": "<64-char hex>",
  "dh_public": "<64-char hex>",
  "clan_id": "jei"
}
```

**Common mistake**: Using PEM-exported keys with field names `private`/`public` instead of
`sign_private`/`sign_public`. The hub expects the HERMES native format with `sign_private` key.

If your keys are in PEM format, convert them:

```python
from cryptography.hazmat.primitives.serialization import load_pem_private_key, Encoding, PublicFormat, PrivateFormat, NoEncryption

with open("key.pem", "rb") as f:
    key = load_pem_private_key(f.read(), password=b"your-passphrase")

sign_private = key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()).hex()
sign_public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
```

### 9.4 S2S Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `sign_private` KeyError | Key file uses PEM field names | Re-export with `sign_private`/`sign_public` fields |
| Auth OK but 0 messages routed | Missing `{"type":"msg","payload":{...}}` wrapper | Wrap payload in msg frame (§3.1) |
| `queue_depth: 0` after send | `dst` field missing from payload | Add `"dst": "target_clan_id"` to payload (§3.2) |
| Connection drops after HELLO | `role: "hub"` not in HELLO | Add `"role": "hub"` to HELLO frame |
| S2S connects but no routing | `peers` array empty in HELLO | Include reachable clan IDs in `peers` |

### 9.5 ConnectionTable: Multiple Sessions

The hub supports multiple simultaneous connections per `clan_id`. A clan can have both
a listener (for receiving) and a client (for sending) connected at the same time.
Messages to that clan are delivered to ALL active connections.

This means:
- A `hermes hub listen` daemon and an interactive client can coexist
- Store-and-forward drain happens on the first connection; subsequent connections
  receive only new messages
- Disconnecting one session does not affect others for the same clan

---

## 10. Conformance Levels (ARC-1122)

| Level | Name | Auth | Messages | Presence | Store-Forward |
|-------|------|------|----------|----------|---------------|
| L1 | Bus-Compatible | N/A | JSONL bus | N/A | N/A |
| L2 | Clan-Ready | Ed25519 | ARC-5322 | N/A | N/A |
| **L3** | **Network-Ready** | **Ed25519 HELLO flow** | **Hub msg frames** | **Handle presence** | **Handle drain** |

Hub bilateral requires **L3 Network-Ready** conformance.

## 11. References

- [ARC-4601](../spec/ARC-4601.md) — Agent Node Protocol (§15 Hub Mode)
- [ARC-5322](../spec/ARC-5322.md) — Message Format
- [ARC-8446](../spec/ARC-8446.md) — Encrypted Bus Protocol
- [ARC-1122](../spec/ARC-1122.md) — Conformance Testing

---

## Appendix A — Federation Roadmap (JEI Contribution)

*Análisis desde perspectiva de telecomunicaciones — JAi-JEI, 2026-04-03*

### Mapping to Telecom Architectures

| HERMES Concept | Telecom Equivalent | Problem Solved |
|---|---|---|
| Hub | SIP Proxy / Registrar | Rendezvous — how endpoints find each other |
| Ed25519 auth | SIP Digest (improved) | Endpoint identity |
| store-forward | SMS-C / MMS relay | Guaranteed delivery when recipient offline |
| HELLO/CHALLENGE/AUTH | TLS handshake | Secure session establishment |
| `dst:*` vs `dst:clan_id` | Broadcast vs unicast routing | Network efficiency |
| GitHub relay | X.400 / SMTP | Async, fault-tolerant, high-latency fallback |

### Current Topology: Star (v0.4.x)

```
  [DANI hub]     [JEI hub]
      |               |
    DANI            JEI
```

Each hub is standalone. No hub-to-hub routing (S2S). Clans must connect to the same hub for real-time exchange.

### Target Topology: Federated (v0.6+)

```
  [DANI hub] ──── S2S ──── [JEI hub] ──── S2S ──── [hub-C]
      |                         |                       |
    DANI                       JEI                    CLAN-C
```

**S2S routing rule:** If `dst` is not a local peer, the hub looks up the destination in a federation table and forwards the frame to the responsible hub. Analogous to BGP next-hop routing.

The `MessageRouter` in `hub.py` already has the structure for this — adding a federation table is the key step.

### Identity Model: PGP Web of Trust

`clan_id` is a human-readable alias. The canonical identity is the **Ed25519 public key**. If two clans claim the same `clan_id`, the public key fingerprint resolves the conflict — same model as PGP key IDs.

For federation: `clan_id` will evolve to `clan_id@hub` (analogous to XMPP JIDs: `jei@hub-jei.local`), enabling unambiguous routing across hub boundaries without breaking the current flat `clan_id` convention.

### Discovery Roadmap

| Phase | Mechanism | Scope |
|---|---|---|
| v0.4.x (now) | Manual config (`hub-peers.json`, CLI args) | LAN/fixed |
| v0.5 | mDNS `_hermes._tcp.local` (Bonjour/Avahi) | Auto-discovery on LAN |
| v0.6 | DNS SRV `_hermes._tcp.example.com` | WAN / public clans |
| v0.7 | Agora registry with hub endpoints | Internet-scale |

### Multiplexing Model

One WebSocket connection per hub, messages multiplexed using `payload.dst` as the demultiplexing key. Equivalent to MQTT (one socket, N topics). No concept of sub-channels or streams — consistent with KISS principle.

For N clans on the same hub: no protocol changes required. DANI + JEI + CLAN-C each connect to the hub; the router delivers each message to the correct peer(s) based on `dst`.

### Version Negotiation

`HELLO` carries `protocol_version` and `capabilities[]`. The server announces its version in `CHALLENGE`. Current behavior: informative only (graceful degradation). Future: `minimum_version` in `CHALLENGE` to reject incompatible clients with a `version_too_old` error.

`capabilities[]` is the primary feature negotiation mechanism — analogous to TLS cipher suites. A client that doesn't support `store_forward` simply doesn't receive queued messages.

### Sovereign-First Principle (Consejo Ampliado, 2026-04-03)

Cloud infrastructure is appropriate **only when it generates direct value** (monetizable quests, public demos, onboarding external clans). For daily lab work between co-located clans:

1. **LAN hub** — zero cost, <1ms latency, sovereign, no intermediaries
2. **cloudflared tunnel** — temporary, ephemeral, no persistent state, for remote sessions
3. **GCloud/Fly.io** — only when persistent availability generates revenue

This mirrors the HERMES dual-mode architecture: Sovereign (LAN) + Hosted (cloud) — where Hosted is opt-in, not the default.
