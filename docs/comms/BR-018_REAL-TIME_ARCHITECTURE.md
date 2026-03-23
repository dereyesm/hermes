# BR-018 — Real-Time Architecture Decision

> protocol-architect + hermes-research + hermes-community | 2026-03-23
> Audience: internal (Daniel + HERMES team)
> Mode: BR (3-skill)

---

## Context

HERMES v0.4.2-alpha operates file-based (JSONL bus). The Agent Node daemon
(ARC-4601) observes the bus via `kqueue` (macOS) and forwards to a remote
gateway via SSE pull + HTTP POST. Current transport:

```
Daemon ←SSE pull── Gateway:8080/events    (inbound)
Daemon ──HTTP POST→ Gateway:8080/bus/push  (outbound)
Daemon ──HTTP GET→  Gateway:8080/healthz   (heartbeat, 60s interval)
```

This works for async quests (minutes latency is fine). But bilateral
real-time coordination (QUEST-005, multi-clan sessions, live demos)
needs sub-second delivery. The relay with JEI currently uses git push/pull —
latency measured in hours.

**Question**: What architecture should HERMES adopt for real-time peer
communication?

**Constraints**:
- Phase 0 compatibility (file-based always works, no regression)
- ARC-8446 E2E encryption guarantees preserved
- ARC-3022 gateway semantics (NAT, filtering, translation) unchanged
- Incremental — can ship in phases without blocking current work
- No new runtime dependencies that break `pip install hermes-protocol`

---

## Current Transport Architecture (ARC-4601 baseline)

Before evaluating options, document what exists.

### Inbound: SSE pull (agent.py:643-722)

```python
# GatewayLink._sse_stream() — persistent HTTP/1.1 connection
# Raw socket + select() for non-blocking reads (5s timeout)
# Events delimited by \n\n
# Auto-deduplication: matched by src + ts + msg hash
# Auth: ?token=<sse_token> query param OR X-Gateway-Key header
# Reconnection: exponential backoff (1s → 60s max)
```

### Outbound: HTTP POST (agent.py:579-611)

```python
# GatewayLink.post_message() — single request per message
# Retries on 503 with exponential backoff (1s, 2s, 4s)
# Forwards messages matching forward_types config
# Escalates stale alerts and request-type messages
# Auth: X-Gateway-Key header
```

### Authentication: dual-token

```
auth_token (legacy, single token) OR:
  gateway_key  → X-Gateway-Key header (outbound POST)
  sse_token    → ?token=<value> query param (inbound SSE)
```

No mutual TLS. Tokens configured per-node in gateway config.

### Message flow (4 async loops)

1. **Bus Observer** (`_bus_loop`, :1241-1327): kqueue on bus.jsonl → evaluate → dispatch/forward/escalate
2. **SSE Inbound** (`_sse_loop`, :1339-1359): gateway SSE → validate → write to local bus
3. **Heartbeat** (`_heartbeat_loop`, :1360-1374): GET /healthz every 60s
4. **Evaluation Cycle** (`_evaluation_loop`, :1376-1438): periodic sweep for pending/stale messages

### Current limitations for real-time

- **No bidirectional transport**: SSE is unidirectional. POST is request-response.
- **No server-side daemon**: Gateway is passive relay, not active participant.
- **Two-hop latency**: SSE event → bus.jsonl write → Bus Observer → POST back out.
- **No WebSocket**: Zero WebSocket code in repo. All HTTP/1.1 raw sockets.

---

## Option A — Centralized Hub

### How it works

A managed server accepts WebSocket connections from all peers. Messages
are routed server-side via connection table: `clan_id → socket`. Hub
maintains store-and-forward queue for offline peers.

### Technical architecture

```
Peer-1 ──WS──→ Hub ──WS──→ Peer-2
                 ↓
         routing table:
         momoshod → ws://peer1:auto
         jei      → ws://peer2:auto
         nymyka   → ws://peer3:auto (offline → queue)
```

Hub processes:
- Accept WS connection + authenticate (token or signed challenge)
- On message: lookup `dst` in routing table → forward via WS
- If dst offline: queue in store-and-forward (TTL-based eviction)
- Heartbeat: WebSocket ping/pong frames (built-in RFC 6455)

### What the Hub sees

```json
{
  "ts": "2026-03-23",
  "src": "momoshod",     ← visible
  "dst": "jei",          ← visible
  "type": "quest005",    ← visible
  "msg": {
    "enc": "ECDHE",
    "ciphertext": "5850e2a5...",  ← opaque blob
    "nonce": "94356b68...",
    "eph_pub": "3e1cb5b7...",
    "signature": "f4fc1d7f..."
  }
}
```

**Hub knows**: who talks to whom, when, how often, message sizes.
**Hub cannot know**: message content (AES-256-GCM under ECDHE shared secret).

### Advantages
- Simple topology: all peers connect to one endpoint
- NAT traversal solved (Hub has public IP)
- Offline store-and-forward built in
- WebSocket ping/pong handles liveness
- Easiest to implement (~500 LOC server)

### Disadvantages
- Single point of failure (Hub down = all comms down)
- Hub operator sees full metadata graph (who, when, frequency, sizes)
- Scaling requires infrastructure investment
- Contradicts HERMES "sovereign" positioning
- New trust relationship: Hub operator

### Score breakdown

| Criterion | Weight | Score | Weighted | Notes |
|-----------|--------|-------|----------|-------|
| Sovereignty | 3 | 1 | 3 | Hub operator holds metadata power over all clans |
| Simplicity | 2 | 5 | 10 | Easiest to implement, well-understood pattern |
| Latency | 2 | 4 | 8 | Sub-second but extra hop through Hub |
| NAT traversal | 2 | 5 | 10 | Solved by default (Hub has public IP) |
| E2E compat | 1 | 4 | 4 | ARC-8446 works, but metadata exposed |
| | **10** | | **35 → norm 18** | Normalized: 35 × (25/50) = 17.5 ≈ **18** |

---

## Option B — Pure P2P (WireGuard mesh)

### How it works

Each peer runs WireGuard. Peers exchange public keys and endpoints
out-of-band (or via initial Hub bootstrap). Direct encrypted tunnels
between peers. No central server after setup.

### Technical architecture

```
Peer-1 ←──WireGuard tunnel──→ Peer-2
  ↑                              ↑
  └──WireGuard tunnel──→ Peer-3 ─┘

  mesh: N peers = N*(N-1)/2 tunnels
  3 clans = 3 tunnels
  10 clans = 45 tunnels
  50 clans = 1,225 tunnels
```

### WireGuard specifics
- **Layer**: L3 (kernel-level IP tunnel) — HERMES is L7 (application messages)
- **Handshake**: Noise IK variant, 1 RTT (pre-shared public keys)
- **Per-packet overhead**: 60 bytes (IPv4+UDP+WG header) + 16 bytes (Poly1305 tag) = 76 bytes
- **Encryption**: ChaCha20-Poly1305 (post-quantum considerations: none)
- **NAT**: WireGuard itself does NOT solve NAT — needs manual port forwarding or external STUN
- **Admin**: Requires root/admin privileges for kernel tunnel interface

### Impedance mismatch

```
HERMES message (L7, JSON/compact):
  {"ts":"...","src":"momoshod","dst":"jei","type":"quest","msg":"..."}

WireGuard packet (L3, IP):
  [IPv4 header][UDP header][WG header][encrypted IP packet]

  Inside the WG tunnel, still need:
  - TCP connection between peers (for reliability)
  - HTTP or custom protocol (for HERMES message framing)
  - OR: raw UDP + custom reliability layer

  WireGuard gives you an encrypted pipe.
  You still need to build everything on top.
```

### Advantages
- True sovereignty: zero intermediaries
- WireGuard is battle-tested (~4K LOC kernel module)
- Zero metadata leakage to third parties
- Aligned with cypherpunk ethos
- Post-tunnel: lowest possible latency (direct)

### Disadvantages
- NAT traversal is unsolved (the hard problem)
- Mesh scales quadratically: 50 clans = 1,225 tunnels
- Offline peers = lost messages (no store-and-forward)
- L3↔L7 impedance: still need HERMES framing inside tunnel
- Requires root privileges (kernel interface)
- Peer discovery requires out-of-band mechanism
- Key rotation/management at scale is complex

### Score breakdown

| Criterion | Weight | Score | Weighted | Notes |
|-----------|--------|-------|----------|-------|
| Sovereignty | 3 | 5 | 15 | Maximum — no intermediary at all |
| Simplicity | 2 | 1.5 | 3 | NAT + mesh mgmt + L3/L7 gap = very complex |
| Latency | 2 | 5 | 10 | Direct peer, lowest possible after setup |
| NAT traversal | 2 | 1.1 | 2.2 | WireGuard alone doesn't solve NAT |
| E2E compat | 1 | 5 | 5 | Compatible (redundant encryption layer) |
| | **10** | | **35.2 → norm 19.7** | |

---

## Option C — Hybrid (Hub routing + P2P tunnels)

### How it works

A lightweight Hub handles discovery, routing, and store-and-forward.
Peers connect to Hub for message relay by default. When both peers are
online and directly reachable, they establish Noise IK tunnels for
P2P messaging, bypassing the Hub.

```
Phase A (ships first):
  Peer-1 ──WS──→ Hub ──WS──→ Peer-2
                   ↓
           encrypted blobs pass through
           Hub never decrypts (ARC-8446 E2E)

Phase B (additive):
  Peer-1 ←──Noise IK tunnel──→ Peer-2
  Hub still available as fallback + discovery + store-and-forward
```

### The reframe: why "centralized vs decentralized" is a false dichotomy

ARC-8446 E2E encryption means the Hub **never sees plaintext**. Every
message on the wire looks like this:

```json
{
  "ciphertext": "5850e2a55b663220...",   // AES-256-GCM encrypted
  "nonce": "94356b68c5001a17...",        // random 12 bytes
  "signature": "f4fc1d7f74caf90f...",    // Ed25519 over ct||eph_pub
  "sender_sign_pub": "85a940d9b5a2...", // public (safe to see)
  "eph_pub": "3e1cb5b79f867745..."       // ephemeral X25519 (public)
}
```

To decrypt, you need:
1. `shared = X25519(my_dh_private, eph_pub)` — Hub has no private key
2. `key = HKDF-SHA256(shared, info=b"HERMES-ARC8446-ECDHE-v1")` — Hub cannot compute
3. `plaintext = AES-GCM.decrypt(key, nonce, ciphertext, aad)` — Hub cannot decrypt

**The Hub is a routing convenience, not a trust boundary.**

Traditional hub-vs-P2P debates assume the hub can read traffic. HERMES
E2E makes this assumption invalid. The only privacy loss with a Hub is
**metadata** (who talks to whom, when, sizes). For metadata-sensitive
peers, Phase B P2P tunnels eliminate even that.

**Industry precedent**: Signal's servers are "hubs" — they route encrypted
blobs without reading content. WhatsApp same. Matrix homeservers same
(with Olm/Megolm). The security model doesn't change when routing goes
through a server — it changes when encryption breaks.

### Phase A: Hub Gateway Server (detailed)

Extend ARC-4601 with server-side mode. The Hub is the "SMTP server" of
HERMES:

```
Hub Server Components:
├── WebSocket endpoint     /ws           bidirectional per-peer
├── REST fallback          /bus/push     HTTP POST for legacy daemons
├── SSE fallback           /events       for clients that can't WebSocket
├── Health                 /healthz      liveness probe
├── Connection table       clan_id → ws  in-memory routing
├── Store-and-forward      TTL queue     for offline peers
├── Bus Observer           server bus    watches for locally-generated messages
└── STUN relay             /stun         endpoint hints for Phase B
```

**Wire protocol (WebSocket frames)**:

```json
// Client → Hub: authenticated message
{"type": "msg", "payload": <ARC-5322 message (encrypted)>}

// Hub → Client: routed message
{"type": "msg", "payload": <ARC-5322 message (encrypted)>}

// Client → Hub: heartbeat
{"type": "ping", "ts": 1711180800}

// Hub → Client: heartbeat response + metadata
{"type": "pong", "ts": 1711180800, "queue_depth": 3}

// Hub → Client: queued messages on reconnect
{"type": "drain", "messages": [<msg1>, <msg2>, ...]}
```

**Authentication flow**:

```
1. Client opens WebSocket to Hub
2. Hub sends challenge: {"type": "challenge", "nonce": <random>}
3. Client signs nonce with Ed25519 key: {"type": "auth", "clan_id": "momoshod",
   "signature": <sign(nonce, private_key)>, "pub_key": <sign_pub>}
4. Hub verifies signature against registered clan public keys
5. Hub adds clan_id → ws to routing table
6. Bidirectional message flow begins
```

**What changes from current ARC-4601**:

| Component | Current (client daemon) | Phase A (server mode) |
|-----------|------------------------|----------------------|
| Transport in | SSE pull (unidirectional) | WebSocket (bidirectional) |
| Transport out | HTTP POST (request/response) | WebSocket (bidirectional) |
| Auth | Token-based (configured) | Challenge-response (Ed25519) |
| State | Local bus.jsonl + state.json | In-memory routing table + queue |
| Bus | File-based (kqueue observer) | Optional file-based + in-memory |
| Scaling | Single node | Horizontal with shared routing state |

### Phase B: Noise IK P2P Tunnels (detailed)

For peers that want to eliminate even metadata exposure:

**Noise IK handshake** (1 RTT, pre-shared public keys):

```
Initiator → Responder: e, es, s, ss
  e  = ephemeral X25519 keypair (generated)
  es = DH(e_priv, s_remote_pub)   — ephemeral-static
  s  = initiator's static pub (encrypted under es)
  ss = DH(s_priv, s_remote_pub)   — static-static

Result: symmetric keys for both directions
  k_init→resp = HKDF(es || ss, "initiator")
  k_resp→init = HKDF(es || ss, "responder")
```

**Why Noise IK over WireGuard**:
- Noise IK is L7-native (application-level, no kernel privileges)
- Same cryptographic primitives as ARC-8446 (X25519, Ed25519)
- 1 RTT handshake (same as WireGuard's Noise IK variant)
- No impedance mismatch (HERMES frames directly, no IP tunnel)
- Can run over existing WebSocket connection to Hub (upgrade in-place)

**STUN for NAT traversal** (RFC 5389):

```
1. Both peers send STUN Binding Request to Hub's STUN relay
2. Hub echoes back each peer's reflexive address (public IP:port)
3. Hub shares reflexive addresses between peers (encrypted)
4. Peers attempt direct UDP connection using reflexive addresses
5. If direct works → Noise IK handshake → P2P tunnel established
6. If direct fails (symmetric NAT) → fall back to Hub relay
```

**Fallback decision tree**:

```
Both peers online?
  ├── No → Hub store-and-forward (Phase A)
  └── Yes → Attempt STUN endpoint exchange
       ├── STUN fails → Hub relay (Phase A)
       └── STUN succeeds → Attempt direct connection
            ├── Direct fails → Hub relay (Phase A)
            └── Direct succeeds → Noise IK handshake
                 ├── Handshake fails → Hub relay (Phase A)
                 └── Handshake succeeds → P2P tunnel active
                      └── Tunnel drops → automatic fallback to Hub
```

### Wire efficiency impact

From L3 Channel Efficiency research (overhead_model.py, 120B payload):

| Protocol | Wire size | Overhead | Efficiency |
|----------|-----------|----------|------------|
| **HERMES compact (local bus)** | 157 B | 37 B | **76.9%** |
| HERMES compact (Hub WS) | 219 B | 99 B | 54.8% |
| MQTT v5.0 (TLS) | 253 B | 133 B | 47.4% |
| gRPC (HTTP/2, cold) | 300 B | 180 B | 40.0% |
| HTTP/1.1 REST | 597 B | 477 B | 20.1% |

Hub relay adds 62B network stack (TCP 20B + TLS 22B + IPv4 20B) per
message — unavoidable for any internet protocol. HERMES compact over
WebSocket still beats MQTT and gRPC.

### Latency profile

| Path | Cold start | Warm | Notes |
|------|-----------|------|-------|
| Local bus (Phase 0) | 0 ms | 0.1-2 ms | NVMe write + kqueue notification |
| Hub relay (Phase A) | 30-150 ms | 10-50 ms | DNS + TLS 1.3 + WS upgrade (cold). 1 RTT warm. |
| P2P tunnel (Phase B) | 50-200 ms | 5-10 ms | STUN + Noise IK setup (cold). Direct after. |
| Hub fallback | 10-50 ms | 10-50 ms | Always available, no P2P overhead |

### Advantages
- Works everywhere (Hub fallback is unconditional)
- NAT traversal: Hub always works, STUN for direct when possible
- Store-and-forward for offline peers (via Hub)
- E2E crypto means Hub is untrusted by design
- P2P tunnels available for metadata-sensitive peers
- Incremental: Phase A ships first, Phase B is additive
- Same crypto stack (X25519, Ed25519) — no new dependencies

### Disadvantages
- More complex than pure Hub (two transport paths)
- Hub still required for discovery and fallback
- Phase B (Noise IK + STUN) adds ~1000-1500 LOC implementation surface
- Tunnel lifecycle management (establish, rekey, teardown, reconnect)

### Score breakdown

| Criterion | Weight | Score | Weighted | Notes |
|-----------|--------|-------|----------|-------|
| Sovereignty | 3 | 4 | 12 | E2E blinds hub + P2P eliminates metadata |
| Simplicity | 2 | 3.5 | 7 | Phase A is simple (~800 LOC), Phase B adds complexity |
| Latency | 2 | 4.5 | 9 | Hub relay sub-second + P2P sub-10ms |
| NAT traversal | 2 | 4.5 | 9 | Hub always works, STUN for direct |
| E2E compat | 1 | 5 | 5 | ARC-8446 designed for exactly this |
| | **10** | | **42 → norm 21** | |

---

## Comparison Matrix

| | Hub (A) | P2P (B) | Hybrid (C) |
|---|---|---|---|
| **Sovereignty** | Low (metadata exposed) | Maximum (no intermediary) | High (E2E + P2P option) |
| **NAT** | Solved by default | Unsolved without STUN/TURN | Solved (Hub fallback) |
| **Offline** | Store-and-forward | Lost messages | Store-and-forward |
| **Warm latency** | 10-50 ms | 5-10 ms | Both available |
| **Complexity** | Low (~500 LOC) | Very high (mesh + NAT + L3/L7) | Medium (~800 LOC Phase A) |
| **Phase 0 compat** | Yes | No (new transport) | Yes (Hub = upgraded relay) |
| **Scaling** | Vertical (Hub resources) | Quadratic (N^2 tunnels) | Linear (Hub) + selective P2P |
| **Admin privileges** | No | Yes (WireGuard kernel) | No (Noise IK is L7) |
| **New dependencies** | `websockets` | `wireguard-tools` + root | `websockets` (Phase A) |
| **Industry precedent** | Signal, WhatsApp, Matrix | Tor, I2P | Signal + direct calls |
| **Score** | **18** | **19.7** | **21** |

---

## Recommendation

**Hybrid wins.** Ship in two phases:

### Phase A — Gateway Server (priority: next spec)

Extend ARC-4601 with server-side mode. The Hub is the "SMTP server"
of HERMES:

- WebSocket bidirectional transport (upgrade from SSE pull + HTTP POST)
- Challenge-response auth (Ed25519 signed nonce, reuses existing keys)
- Routing table: `clan_id → websocket` (in-memory, O(1) lookup)
- Store-and-forward queue for offline peers (TTL-based eviction)
- E2E passthrough: Hub routes encrypted ARC-8446 envelopes without decryption
- Backward compatible: legacy daemons can still use SSE + POST endpoints

**Implementation**: New ARC spec (ARC-4602 or ARC-4601 §14+ extension).
Reference impl ~800 LOC (gateway_server.py or extend agent.py).
Target: 50-80 new tests.

### Phase B — Noise IK Tunnels (stretch goal for v1.0)

For metadata-sensitive peers:

- Noise IK handshake (1 RTT, reuses X25519/Ed25519 keypairs)
- STUN endpoint exchange via Hub
- Automatic fallback to Hub relay on tunnel failure
- Tunnel lifecycle: establish → heartbeat → rekey (24h) → teardown

**Implementation**: New module (tunnel.py ~1000-1500 LOC).
Depends on Phase A for discovery and fallback.

---

## Skill Contributions

| Skill | Lens | Key contribution |
|-------|------|------------------|
| **protocol-architect** | Architecture | Current ARC-4601 transport analysis (SSE/POST/heartbeat). Wire protocol design (WS frames, auth challenge, drain). ARC-4602 scope definition. Phase A/B separation. |
| **hermes-research** | Data | L3 overhead model (6 protocols, measured). Latency profile (local/Hub/P2P). WireGuard vs Noise IK comparison (L3 vs L7, admin privileges). NAT traversal landscape (STUN/TURN/ICE). Serialization benchmarks (357K msg/sec compact). |
| **hermes-community** | Adoption | Hub-blind reframe (false dichotomy dissolved). Industry precedent mapping (Signal, Matrix, WhatsApp). Sovereignty narrative ("SMTP of HERMES"). Dual-mode positioning (sovereign + hosted unchanged). |

---

## Daniel Eval (5 axes)

| Axis | Score | Notes |
|------|-------|-------|
| CQ (Code Quality / Technical depth) | 3.9/5 | |
| DD (Domain Depth) | 3.9/5 | |
| GO (Go-to-market / Actionability) | 3.9/5 | |
| IP (Intellectual Property / Novel insight) | 3.9/5 | |
| IN (Integration / Cross-synthesis) | 3.9/5 | |
| **Overall** | **3.9/5** | |
| **XP** | **78** | BR mode = 2x multiplier (10 × 3.9 × 2) |
