# Protocol Explorer — Wireframes

> Text-based wireframes for each visualization mode of the HERMES Protocol Explorer (AES-2040).

These wireframes define the layout and information hierarchy. The actual implementation will use D3.js/Svelte with interactive elements.

---

## Mode 1: Message Flow (default view)

```
┌─────────────────────────────────────────────────────────────────────┐
│  HERMES Protocol Explorer           [Connected ●]  [Dark Mode ◐]  │
├──────┬──────────────────────────────────────────────────────────────┤
│      │                                                              │
│ FILTER│   engineering    ops       finance    controller    *       │
│      │       │           │           │           │                  │
│ ☑ state │    │           │           │           │                  │
│ ☑ alert │    ●──state──→●           │           │    10:01:23      │
│ ☑ event │    │           │           │           │                  │
│ ☑ request│   │           │    ●←─data_cross──●  │    10:01:45      │
│ ☑ dispatch   │           │           │           │                  │
│ ☑ dojo  │    │           │           │    ●←─dispatch──●   10:02:01│
│      │       │           │           │           │                  │
│ SRC: │       ●──event──→─┼───────────┼───────────● (broadcast)     │
│ [all ▼]│     │           │           │           │    10:02:15      │
│      │       │           │ ✓         │ ✓         │                  │
│ DST: │       │           │ (ACKed)   │ (ACKed)   │                  │
│ [all ▼]│     │           │           │           │                  │
│      │       │     ⚠─────●           │           │    10:03:00      │
│ TTL: │       │  (stale, 4d)          │           │                  │
│ [1-7] │      │           │           │           │                  │
│      │       ▼           ▼           ▼           ▼                  │
├──────┴──────────────────────────────────────────────────────────────┤
│ Selected: {"ts":"2026-03-14","src":"engineering","dst":"ops",...}   │
│ Type: state | TTL: 7d (5d remaining) | ACK: [ops] | Encoding: raw │
└─────────────────────────────────────────────────────────────────────┘
```

**Interactions**:
- Click any arrow → inspect full message in bottom panel
- Hover → tooltip with `msg` preview
- Filter sidebar → show/hide by type, src, dst
- Scroll → navigate time axis

---

## Mode 2: Session Timeline

```
┌─────────────────────────────────────────────────────────────────────┐
│  Session Timeline                                 Mar 12-14, 2026  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Namespace      Mar 12         Mar 13         Mar 14                │
│                 ├──────────────┼──────────────┼─────────            │
│                                                                     │
│  engineering    ██SYN██████ACTIVE████████FIN██  ░░░░  ██SYN██ACT██  │
│                 v12                      v13          v14            │
│                                                                     │
│  ops            ░░░░░░░░░  ██SYN██ACTIVE████FIN██  ░░░░░░░░░░░░░  │
│                            v8                v9                     │
│                                                                     │
│  finance        ██SYN██ACT██FIN██  ░░░░░░░░░░░░░  ⚠ STALE (8d)   │
│                 v3          v4                                      │
│                                                                     │
│  controller     ████████████████████████████████████████████████████ │
│                 (always active — Agent Node daemon)                  │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│  Legend: ██ Active session  ░░ Idle  ⚠ Stale (>7d since last sync) │
│  vN = SYNC HEADER version number at FIN                             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Mode 3: Cross-Clan Path

```
┌─────────────────────────────────────────────────────────────────────┐
│  Cross-Clan Path Trace                    Message: [CID:quest-42]  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────┐    ┌──────────────┐    ┌──────────┐    ┌──────────┐  │
│  │Agent A   │───►│Gateway Alpha │───►│Gateway   │───►│Agent B   │  │
│  │(engineering)  │(NAT outbound)│    │Beta      │    │(cybersec)│  │
│  └──────────┘    └──────────────┘    │(NAT in)  │    └──────────┘  │
│                                      └──────────┘                   │
│  Hop 1           Hop 2               Hop 3           Hop 4         │
│  src: engineering internal→external  validate         delivered     │
│  dst: cybersec   "engineering"→      rate limit: OK   to bus       │
│  type: request   "alpha-eng"         ARC-5322: OK     ACK pending  │
│  0ms             +12ms               +89ms            +2ms          │
│                  ✓ Filter pass       ✓ Validation     ✓ Written    │
│                  ✓ NAT translate     ✓ Peer known                  │
│                                                                     │
│  Total latency: 103ms                                               │
├─────────────────────────────────────────────────────────────────────┤
│  [◄ Previous hop]  [Next hop ►]  [Show raw message]                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Mode 4: Crypto Envelope

```
┌─────────────────────────────────────────────────────────────────────┐
│  Crypto Envelope Inspector          ARC-8446 | Mode: Static DH     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  SEAL (Sender: Clan Alpha)                                          │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ Step 1: DH Key Agreement                              [▼]  │    │
│  │   X25519(my_dh_priv, peer_dh_pub) → raw_shared            │    │
│  ├─────────────────────────────────────────────────────────────┤    │
│  │ Step 2: HKDF Derivation                               [▼]  │    │
│  │   HKDF-SHA256(raw, info="HERMES-ARC8446-v1") → key        │    │
│  ├─────────────────────────────────────────────────────────────┤    │
│  │ Step 3: Nonce Generation                              [▼]  │    │
│  │   12 random bytes → a4b2c8e1...                            │    │
│  ├─────────────────────────────────────────────────────────────┤    │
│  │ Step 4: AAD Construction                              [▼]  │    │
│  │   canonical_json({dst,src,ts,type}) → 7b22647374...        │    │
│  ├─────────────────────────────────────────────────────────────┤    │
│  │ Step 5: AES-256-GCM Encrypt                           [▼]  │    │
│  │   Plaintext: "Quest accepted. Assigned cybersec-arch..."   │    │
│  │   Ciphertext: 8f3a7b2c... (+ GCM tag)                     │    │
│  ├─────────────────────────────────────────────────────────────┤    │
│  │ Step 6: Ed25519 Sign                                  [▼]  │    │
│  │   sign(my_sign_priv, ciphertext_bytes) → sig               │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  OPEN (Receiver: Clan Beta)                                         │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ Step 1: Verify Signature  ← CRITICAL: before decrypt  [✓]  │    │
│  │   Ed25519.verify(peer_sign_pub, ciphertext, sig)            │    │
│  ├─────────────────────────────────────────────────────────────┤    │
│  │ Step 2-4: DH + HKDF + AAD (symmetric)                [✓]  │    │
│  ├─────────────────────────────────────────────────────────────┤    │
│  │ Step 5: AES-256-GCM Decrypt                           [✓]  │    │
│  │   Plaintext recovered: "Quest accepted. Assigned..."       │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  [Show ECDHE variant]  [Show raw envelope JSON]  [Compare modes]   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Mode 5: Dispatch Tree

```
┌─────────────────────────────────────────────────────────────────────┐
│  Dispatch Tree                       Quest: [CID:quest-42]         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Incoming: type=dispatch, dst=dojo                                  │
│  Required: eng.cybersecurity + eng.crypto                           │
│                                                                     │
│  ┌─ Capability Match ──────────────────────────────────────────┐    │
│  │                                                              │    │
│  │  cybersec-architect    ✓ eng.cybersecurity  ✓ eng.crypto    │    │
│  │  XP: 450 (threshold: 100) ✓                                │    │
│  │  Slots: 1/2 available ✓                                     │    │
│  │  ──────────────────────────────────────── SELECTED ★        │    │
│  │                                                              │    │
│  │  project-commander     ✓ ops.governance    ✗ eng.crypto     │    │
│  │  ──────────────────────────────────────── REJECTED (caps)   │    │
│  │                                                              │    │
│  │  sales-director        ✗ eng.cybersecurity                  │    │
│  │  ──────────────────────────────────────── REJECTED (caps)   │    │
│  │                                                              │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  Result: cybersec-architect dispatched                               │
│  Guardrails: max_turns=10, timeout=300s, tools=[]                   │
│  Status: ✓ Completed (exit 0, 47s)                                  │
│  XP awarded: +50                                                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Mode 6: Bus Health

```
┌─────────────────────────────────────────────────────────────────────┐
│  Bus Health Dashboard                              Period: 7 days  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Queue Depth (L)          Throughput (λ)         ACK Rate           │
│  ┌──────────────┐         ┌──────────────┐      ┌──────────┐      │
│  │    ╱\        │         │  ▅ ▆ ▇ ▅ ▃   │      │          │      │
│  │   ╱  \  ╱\   │         │  █ █ █ █ █   │      │  94.2%   │      │
│  │  ╱    \/  \  │         │  █ █ █ █ █   │      │  ████████░│      │
│  │ ╱         \  │         │  M T W T F   │      │          │      │
│  └──────────────┘         └──────────────┘      └──────────┘      │
│  Current: 12 msgs         Avg: 8.4/day           Target: >90%     │
│                                                                     │
│  Stability: λ < μ ✓ (STABLE)    Little's Law: L=12, λ=8.4, W=1.4d│
│                                                                     │
│  TTL Countdown                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ msg-001 (state)    ████████████████░░░░  5d remaining       │   │
│  │ msg-002 (alert)    ████████░░░░░░░░░░░░  2d remaining  ⚠   │   │
│  │ msg-003 (event)    ██████████████████░░  1d remaining  ⚠⚠  │   │
│  │ msg-004 (dispatch) ████████████████████  3d remaining       │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Namespace Activity (last 7d)                                       │
│  engineering: ████████████ 12 msgs    ops: ████████ 8 msgs         │
│  finance:     ████ 4 msgs             controller: ██████████ 10    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Navigation

```
┌─────────────────────────────────────────────────────────────────────┐
│  [Message Flow]  [Timeline]  [Cross-Clan]  [Crypto]  [Dispatch]    │
│  [Bus Health]                                                       │
│                                                                     │
│  Status: Connected to Agent Node (port 8472)                        │
│  Bus: ~/.hermes/bus.jsonl (42 messages, 12 active)                  │
│  Last update: 2s ago                                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

*These wireframes define information hierarchy and layout. Visual design will be
refined during implementation. See [AES-2040](../../spec/AES-2040.md) for the
full specification.*
