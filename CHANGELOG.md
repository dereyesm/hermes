# Changelog

All notable changes to the HERMES protocol are documented here.

This project follows a versioning scheme where:
- **Phase 0** = intra-clan protocol (file-based, single instance)
- **Phase 1** = inter-clan protocol (gateway, Agora, attestations)
- **v1.0** = consolidated spec across all five research lines (L1-L5)

---

## [Unreleased] — ARC-1122 Conformance + Diagrams + Test Coverage (2026-03-28)

### New Specification

- **ARC-1122: Agent Conformance Requirements** (IMPLEMENTED)
  - Three conformance levels: Bus-Compatible, Clan-Ready, Network-Ready
  - 98 normative statements curated from 389 raw occurrences (66 MUST, 18 SHOULD, 15 MAY)
  - Aggregates requirements from 17 IMPL specs into single reference
  - Crypto requirements: SHOULD sovereign, MUST inter-clan
  - Reference: RFC 1122 (Host Requirements), ECMA-430 (NLIP) conformance levels

### Added

- **5 D2 diagrams** (21 total, was 16):
  - `hub-architecture.d2` — ARC-4601 §15 Hub Mode (HubServer, AuthHandler, ConnectionTable, MessageRouter, StoreForwardQueue)
  - `bus-integrity.d2` — ARC-9001 F1-F6 pipeline (SequenceTracker through BusGC)
  - `asp-architecture.d2` — ARC-0369 F1-F5 (MessageClassifier, AgentRegistry, DispatchEngine, 7-state FSM, NotificationThrottler)
  - `adapter-bridge.d2` — Agent-agnostic adapter pattern (~/.hermes/ → Claude Code/Cursor/future)
  - `hub-peer-auth.d2` — Ed25519 challenge-response authentication sequence

- **test_hooks.py** — 25 tests for hooks.py (186 LOC, was 0 coverage)
  - `_read_bus_pending`, `cmd_hook_pull_on_start`, `cmd_hook_pull_on_prompt`, `cmd_hook_exit_reminder`, `main()`
- **test_terminal.py** — 34 tests for terminal.py (345 LOC, was 0 coverage)
  - Brand palette, print_clan_status, print_daemon_status, print_inbox, print_bus_messages (plain-text + rich paths)

- **hermes-integration.md** — Claude Sensei KB integration doc (hooks, adapter, bus protocol, conformance levels)

- **test_conformance.py** — Placeholder test classes for ARC-1122 conformance levels (L1/L2/L3 TODOs)

### Changed

- ARC-1122 abstract: clarified "98 curated from 389 raw" normative count (was ambiguous)
- Rich-path terminal tests: upgraded from no-crash to content assertions via capsys
- experience.md QUEST lineage: QUEST-003 CLOSED, QUEST-004 CLOSED, QUEST-005 updated
- README: spec badge corrected (18 IMPL + 1 INFO + 1 DRAFT = 20), test badge updated (1146), terminal.py added to module list, ARC-1122 in spec table
- EVOLUTION-PLAN.md: stats updated (11→18 specs, 214→1146 tests), 8 Phase 1-2 items marked complete
- spec/INDEX.md: ARC-1122 status PLANNED → IMPLEMENTED

### Test Summary

- 1146 total (+59 from test_hooks + test_terminal), 3 skipped (conformance placeholders), 0 regressions

---

## [Unreleased] — Hub Mode + Noise IK Spec + Documentation Sweep (2026-03-25)

### Hub Mode & P2P Tunnel Specification

This release adds the Hub Mode reference implementation (ARC-4601 §15), expands
the Noise IK P2P tunnel specification (§16), and brings all documentation into
coherence with the current project state.

### Added

- **ARC-4601 §15: Hub Mode** (IMPLEMENTED)
  - `hub.py`: WebSocket Hub server — routes encrypted messages between peer daemons
  - Ed25519 challenge-response authentication (reuses ARC-8446 key infrastructure)
  - E2E passthrough: Hub reads only headers (`src`, `dst`), cannot decrypt `msg`
  - Store-and-forward queue per peer with TTL eviction
  - Presence system: online/offline notifications
  - Legacy endpoints: `/events` (SSE), `/bus/push` (POST), `/healthz`
  - `hermes hub init/start/stop/status/peers` CLI commands
  - Reference: `hub.py` (800 lines), 52 tests

- **ARC-4601 §16: P2P Tunnels — Noise IK specification** (DRAFT)
  - Full Noise IK handshake detail (1-RTT, `Noise_IK_25519_ChaChaPoly_SHA256`)
  - NAT traversal via Hub-assisted STUN-like mechanism
  - Tunnel lifecycle FSM: 8 states (IDLE→DISCOVERY→STUN_EXCHANGE→HANDSHAKE→ACTIVE→REKEY→TEARDOWN→FALLBACK_HUB)
  - UDP framing (5 frame types), keepalive, rekeying every 24h
  - Security properties: forward secrecy, identity hiding, KCI resistance
  - Threat model analysis, Hub integration, configuration schema
  - Expanded from ~57 lines to ~310 lines

- **CursorAdapter** (IMPLEMENTED)
  - `adapter.py`: CursorAdapter compiles `.cursorrules` from `~/.hermes/` skills+rules
  - HERMES:BEGIN/END markers for partial regeneration
  - `hermes adapt cursor` CLI command
  - 26 tests

- **ARC-9001 F5-F6: Recovery + Garbage Collection** (IMPLEMENTED)
  - F5: `SnapshotManager` + `ReplayRequest` for bus recovery
  - F6: `BusGC` with TTL-based eviction + atomic compaction
  - ARC-9001 spec COMPLETE (F1-F6)

### Changed

- **README.md** — badges updated (20 specs, 1087 tests), module list +hub.py +integrity.py, project structure, diagram counts
- **docs/ARCHITECTURE.md** — Hub Mode section added, specs table expanded
- **QUEST-003** status → COMPLETE (JEI confirmed ARC-8446 v1.2 canonical alignment)
- **QUEST-005** status → IN PROGRESS (JEI executing prompt chain, deadline 2026-03-29)

### Bilateral

- **JEI-HERMES-018** received and decrypted: batch ACK of 5 pending messages
- JEI confirmed **ARC-8446 v1.2 canonical params** (HKDF info, AAD, sig order aligned)
- DANI-HERMES-016 ACK + DANI-HERMES-017 reminder sent via relay

### Tests

- 1087 total (+102 from Hub Mode, CursorAdapter, F5-F6), 0 regressions

---

## [Unreleased] — ARC-9001 F3-F4 MVCC + Conflict Log (2026-03-22)

### Bus Integrity — Causal Ordering & Forensics

This release completes ARC-9001 through F4, adding MVCC write vectors for
causal ordering across namespaces and an append-only conflict log for forensic
analysis. The bus can now detect concurrent writes from multiple agents/relays
and record integrity violations independently of bus archival.

### Added

- **ARC-9001 F3: MVCC Write Vectors** (IMPLEMENTED)
  - `WriteVector` dataclass: causal state snapshot `{src: last_seen_seq}`
  - `WriteVectorTracker`: sliding window conflict detection (default 100 msgs)
  - Vector clock semantics: dominates / concurrent / ordered classification
  - Message `w` field (verbose JSON only — compact format unchanged)
  - `write_message()` auto-assigns `w` when `wv_tracker` provided
  - `read_bus_with_integrity()` validates causal ordering
  - Reference: Kung & Robinson (1981), Lamport vector clocks

- **ARC-9001 F4: Conflict Log** (IMPLEMENTED)
  - `ConflictRecord` dataclass: forensic metadata per anomaly
  - `ConflictLog`: append-only `bus-conflicts.jsonl` (independent lifecycle)
  - Records: gaps, duplicates, ownership violations, concurrent writes
  - `BusIntegrityChecker` extended with F3/F4 support
  - All parameters optional — backward compatible with F1/F2-only callers

- **Agent daemon F3-F4 wiring** (agent.py)
  - `WriteVectorTracker` + `ConflictLog` initialized in `_init_asp()`
  - All 6 `write_message()` call sites pass `seq_tracker` + `wv_tracker`
  - Conflict log at `bus-conflicts.jsonl` alongside `bus.jsonl`

### QUEST Progress

- **QUEST-004 COMPLETE**: JEI self-assessment received (JEI-HERMES-017, ~54%)
- **QUEST-005 ACCEPTED**: JEI accepts Knowledge Exchange Protocol (JEI-HERMES-016)
- QUEST-SKILL-EVO: experience.md created for 3 HERMES skills (pilot)

### Tests

- 985 total (+64 from F3-F4), 0 regressions

---

## [Unreleased] — Compact Wire Format + ATR-G.711 (2026-03-17)

### Wire Efficiency & Payload Encoding

This release introduces the Compact Wire Format (ARC-5322 §14) and ATR-G.711, delivering the highest wire efficiency of any agent communication protocol measured — 76.9% at 120B payload, 4.9x less overhead than gRPC — while remaining valid, human-readable JSON.

### Added

- **ARC-5322 §14: Compact Wire Format** (IMPLEMENTED)
  - Positional JSON array encoding: `[epoch_day, src, dst, type_int, msg, ttl, ack]`
  - Epoch-day timestamp (days since 2000-01-01): 10B → 4B
  - Integer type enum (0-6): 5-10B → 1B
  - Compact separators: no spaces after `,` and `:`
  - Auto-detect by first character: `{` = verbose, `[` = compact
  - Mixed-mode buses: verbose and compact messages coexist
  - 100% backward compatible — verbose format unchanged
  - Wrapper reduction: 105B → 36B (-66%)
  - Reference: `message.py` (parse_line, validate_compact, to_compact_jsonl)

- **ATR-G.711: Payload Encoding & Wire Efficiency** (IMPLEMENTED)
  - Formal spec for JSON as normative HERMES encoding
  - G.711 analogy: inspectability over compression (like PCM over Opus)
  - Overhead model data integrated (6 protocols, 9 payload sizes)
  - Compact encoding extension rules (CBOR/MessagePack MAY on gateways)
  - Security considerations for JSON bus operations

- **bus.py mixed-mode compact support**
  - `read_bus()` auto-detects verbose/compact via `parse_line()`
  - `write_message(compact=True)` for compact output
  - `archive_expired()` and `ack_message()` support compact flag

- **sync.py compact support**
  - `fin(compact=True)` writes FIN messages in compact format

- **Serialization benchmark** (`docs/research/l3-channel-efficiency/benchmark.py`)
  - 872K msg/sec compact serialize vs 650K verbose (1.34x speedup)
  - Deserialize: ~equal (compact epoch-day conversion has minor cost)

- **overhead_model.py updated** to 6 protocols (HERMES compact + verbose)

- **D2 diagram**: `compact-wire-format.svg` — visual comparison with efficiency table and auto-detect flow

- **QUEST-003 ACCEPTED** by Clan JEI
  - ECDHE forward secrecy bilateral adoption
  - Timeline: Phase 1 (19 Mar), Phase 2 bilateral (22 Mar), Phase 3 activate (24 Mar)
  - 8 local ECDHE tests already passing (Phase 1 complete ahead of schedule)

### Changed

- **README.md** — headline feature: 76.9% efficient, badges updated (18 specs, 524 tests), compact vs verbose comparison table
- **spec/INDEX.md** — ATR-G.711 PLANNED → IMPLEMENTED
- **L3 research README** — checklist updated (ATR-G.711 ✓, ARC-5322 §14 ✓)

### Stats

- Specs: 17 → 18 (17 IMPL + 1 DRAFT) — +ATR-G.711
- Tests: 493 → 530 (+37: compact format + bus + sync)
- D2 diagrams: 14 → 15 (+1: compact-wire-format)
- Commits: 6 this session

---

## [Unreleased] — QUEST-002 Closure + ECDHE + Visual Migration (2026-03-16)

### Bilateral Protocol & Forward Secrecy

This release closes QUEST-002 (AAD bilateral with Clan JEI), implements ECDHE forward secrecy, and migrates all major ASCII art diagrams to D2 format with the HERMES brand kit.

### Added

- **QUEST-002 bilateral closure** (JEI-HERMES-010 / DANI-HERMES-010)
  - E2E channel Ed25519 + X25519 + AES-256-GCM + AAD verified bilaterally
  - Format convergence: `src_clan` → `src` aligned on both sides
  - All acceptance criteria checked ✓

- **ECDHE Forward Secrecy** (ARC-8446 Section 11.2 — IMPLEMENTED)
  - `seal_bus_message_ecdhe()`: per-message ephemeral X25519 keypair
  - HKDF domain separation: `b"HERMES-ARC8446-ECDHE-v1"`
  - Extended signature scope: `sign(ciphertext + eph_pub)`
  - ECDHE AAD binding: `eph_pub` included in canonical JSON
  - Ephemeral key zeroization after DH computation
  - `open_bus_message()` auto-detects ECDHE vs static mode
  - Backward compatible: static-mode messages still decrypt
  - Reference: `crypto.py`, 8 new tests (493 total)

- **QUEST-003 proposed** (ECDHE bilateral adoption with Clan JEI)
  - Full proposal: `docs/QUEST-003-ECDHE-FORWARD-SECRECY.md`
  - Email draft dispatched to MomoshoD for sending

- **QUEST-CROSS-001 proposed** (CTO review of ARC-4601 by nymyka/cto-advisor)
  - First cross-clan quest within HERMES network
  - Bus message dispatched to nymyka/cto-advisor

- **10 new D2 brand diagrams** (AES-2040 Layer 3)
  - Architecture: five-layer-stack, namespace-topology, firewall-model, session-lifecycle, control-vs-data-plane, gateway-clan-boundary, dual-reputation
  - Specs: session-state-machine (ARC-0793), cups-three-planes (ARC-2314), agent-node-stack (ARC-4601)
  - All use HERMES brand kit (#1A1A2E/#00D4AA/#F5A623/#27AE60/#E74C3C/#7F8C8D)
  - SVGs rendered with `d2 --theme 0 --pad 80`

- **L3 Channel Efficiency Model** (`docs/research/l3-channel-efficiency/overhead_model.py`)
  - HERMES bus 53.1% efficient vs HTTP/1.1 REST 20.1%
  - 5 protocols compared: HERMES, MQTT, gRPC, HTTP/2, HTTP/1.1

### Stats

- Specs: 17 (16 IMPL + 1 DRAFT) — unchanged
- Tests: 441 → 493 (+52: 8 ECDHE + prior session)
- D2 diagrams: 4 → 14 (+10)
- Quests complete: 1 → 2 (QUEST-002 closed)
- Quests proposed: 2 (QUEST-003, QUEST-CROSS-001)

---

## [Unreleased] — Agent Node + Visualization Stack (2026-03-14 → 2026-03-15)

### Persistent Operation & Visual Communication

This release introduces the Agent Node daemon for continuous bus observation, and the AES-2040 Visualization Stack for protocol communication across audiences.

### Added

- **ARC-4601: Agent Node Protocol** (IMPLEMENTED)
  - Persistent local daemon: BusObserver (kqueue/poll) + GatewayLink (SSE+HTTP) + Dispatcher (subprocess)
  - State machine: INIT → RUNNING → DRAINING → STOPPED with PID lock and atomic state persistence
  - Dual-token auth: `X-Gateway-Key` (push) + SSE query param `token` (stream)
  - Guardrails: max dispatch slots, timeout, tool allowlist, escalation threshold
  - Live-tested against heraldo-gateway on Render: SSE connect, kqueue <2s detection, graceful shutdown
  - Process manager integration: launchd (macOS), systemd (Linux), `--foreground` for any manager
  - Reference: `agent.py` (1099 lines, 7 classes), 58 tests (441 total)
  - Lineage: RFC 4601 (PIM-SM — persistent forwarding state)

- **AES-2040: Visualization Stack** (DRAFT)
  - 5-layer stack: L1 ASCII → L2 Mermaid → L3 D2 → L4 Excalidraw → L5 Protocol Explorer
  - 13 Mermaid diagrams: 6 sequence, 5 use case, 2 architecture (GitHub-native rendering)
  - 4 D2 animated diagrams + SVGs: message-lifecycle, gateway-nat, crypto-seal, quest-lifecycle
  - Protocol Explorer spec: 6 modes (Message Flow, Session Timeline, Cross-Clan Path, Crypto Envelope, Dispatch Tree, Bus Health)
  - Structural consistency: all use case diagrams include Actors tables (UC-01 through UC-05)

### Fixed

- `Dispatcher.dispatch()`: `FileNotFoundError` when dispatch command is not on PATH now converts to `RuntimeError`, preventing daemon crash loop (e5f2f45)

---

## [Unreleased] — Phase 1 Hardening (2026-03-02 → 2026-03-08)

### Security, Crypto & Inter-Clan Communication

This release completes Phase 1 with end-to-end encryption, the first inter-clan handshake, bridge protocol mapping for A2A/MCP interop, and the Skill Gateway architecture.

### Added

- **ARC-8446: Encrypted Bus Protocol** (IMPLEMENTED)
  - Ed25519 (signatures) + X25519 (DH key agreement) + AES-256-GCM (authenticated encryption)
  - Key generation, storage (0600 perms), fingerprinting (8x4 hex groups)
  - Verify-before-decrypt pattern (TLS 1.3 aligned)
  - AAD binding: canonical JSON `{dst,src,ts,type}` per Section 6.1.1
  - Key revocation protocol (Section 9.6), replay protection (Section 9.5)
  - Security hardened after Clan JEI review (QUEST-001)
  - Reference: `crypto.py` (276 lines), 36 tests

- **ARC-7231: Agent Semantics — Bridge Protocol Mapping** (IMPLEMENTED)
  - Bidirectional translation: A2A v0.3.0 JSON-RPC ↔ HERMES JSONL
  - Bidirectional translation: MCP JSON-RPC ↔ HERMES JSONL
  - Agent Card ↔ HERMES Profile mapping (Sections 3.2.1, 3.2.2)
  - Task state mapping: submitted/working/completed/failed/canceled/input-required
  - MCP Tool/Resource mapping (Sections 4.2, 4.3)
  - Error translation table (Section 8.1)
  - Reference: `bridge.py` (380 lines), 36 tests

- **ARC-2314: Skill Gateway Plane Architecture** (IMPLEMENTED)
  - Triple-plane CUPS model: Control Plane, Operations Plane, User Plane
  - Quest dispatch + skill orchestration
  - Reference: `dojo.py` (364 lines), 63 tests

- **Multi-clan infrastructure**:
  - `agora.py` — Agora client + profile discovery (145 lines, 29 tests)
  - `cli.py` — Command-line interface (412 lines, 33 tests)
  - `config.py` — Configuration management (197 lines, 18 tests)
  - ARC-3022 extended with Sections 15-16 (multi-clan, CLI)

- **Inter-clan communication with Clan JEI** (first external clan):
  - Encrypted handshake completed (fingerprints verified in person)
  - QUEST-001 (ARC-8446 security review): COMPLETE
  - QUEST-002 (AAD bilateral adoption): **COMPLETE** (bilateral closure 2026-03-16, JEI-HERMES-010)
  - `docs/DANI-HERMES-010.md` — QUEST-002 closure acknowledgement
  - Private relay: `dereyesm/hermes-relay`

- **Documentation**:
  - `docs/POSITIONING.md` v2.0 — Sovereign + Hosted dual-mode architecture
  - `docs/GETTING-STARTED.md` — Onboarding guide with Skill Gateway
  - `docs/EVOLUTION-PLAN.md` — 5-phase roadmap (Mar-Dec 2026)
  - `docs/MULTI-CLAN.md` — Inter-clan guide
  - `docs/CLAN-DANI-ALIGNMENT.md` — DANI-JEI formal alignment
  - `docs/QUEST-002-AAD-BILATERAL.md` — Bilateral AAD quest proposal

### Changed

- **spec/INDEX.md** — 15 specs IMPLEMENTED (was 11), 0 DRAFT (was 1)
- **README.md** — Updated positioning, ecosystem comparison table
- **spec/ARC-7231.md** — Updated with A2A v0.3.0 (gRPC, signed Agent Cards, contextId)

### Stats

- Specs: 11 → 15 IMPLEMENTED (+4), 1 → 0 DRAFT
- Tests: 214 → 419 (+205)
- Python modules: 6 → 11 (+5: crypto, bridge, dojo, agora, cli, config)
- Commits: 8 → 23 (+15)
- Lines of spec: ~5,800 → 9,132

---

## [v0.3.0-alpha] — 2026-03-02

### Transport Semantics & Phase 1 Infra

This release formalizes the boundary between fire-and-forget (DGM) and task-oriented (REL) messages, implements the gateway and profile specs, and ships the HERMES Manifesto.

### Added

- **ARC-0768: Datagram & Reliable Message Semantics** (IMPLEMENTED)
  - Two transport modes: DGM (fire-and-forget) for `state`, `event`, `alert`, `dojo_event` and REL (tracked delivery) for `request`, `dispatch`, `data_cross`
  - Correlation IDs: `[CID:token]` / `[RE:token]` payload convention for request-response linking
  - Computed state machine: SENT → ACKED → RESOLVED (derived from bus state, no schema change)
  - Escalation protocol: unresolved REL messages generate `UNRESOLVED:` broadcast alerts on expiry
  - Full backward compatibility — CID/RE are payload conventions within the existing `msg` field

- **ARC-2606: Agent Profile & Discovery** (IMPLEMENTED)
  - Namespace capability advertisement via `profile.json`
  - Discovery protocol for agents to find compatible peers
  - Profile schema with capabilities, supported types, and metadata

- **ARC-3022: Agent Gateway Protocol** — promoted from DRAFT to IMPLEMENTED
  - Added epigraph, hive topology section, protocol bridge section
  - Reference implementation: `gateway.py` (476 lines) with full Gateway class

- **docs/MANIFESTO.md** — The HERMES Manifesto
  - Design philosophy and principles for the protocol
  - The case for open agent communication standards

- **Reference implementation expansions**:
  - `gateway.py` — Full ARC-3022 Gateway implementation (identity translation, outbound filter, inbound validation, attestation tracking)
  - `message.py` — ARC-0768 functions: `transport_mode()`, `extract_cid()`, `extract_re()`, `RELIABLE_TYPES`
  - `bus.py` — ARC-0768 operations: `find_unresolved()`, `find_expired_unresolved()`, `correlate()`, `generate_escalation()`
  - `sync.py` — `SynResult.unresolved` field, enhanced SYN report with `[UNRESOLVED]` section

- **Test suite expansion**: 46 → 214 tests
  - `test_transport.py` — 46 tests for ARC-0768 (transport modes, CID/RE parsing, lifecycle, escalation)
  - `test_gateway.py` — 50 tests for ARC-3022 gateway
  - `test_bus.py` — 43 tests for bus operations
  - `test_sync.py` — 29 tests for SYN/FIN protocol

- **ARC-2119: Requirement Level Keywords** (IMPLEMENTED, Meta tier)
  - Canonical HERMES reference for MUST/SHOULD/MAY keywords (supplements RFC 2119)
  - Agent-specific definitions, usage guidelines for spec authors, conformance mapping

### Changed

- **spec/INDEX.md** — ARC-0768 renamed and IMPLEMENTED, ARC-2606 added as IMPLEMENTED, ARC-3022 promoted to IMPLEMENTED, ARC-2119 IMPLEMENTED
- 11 specs total (10 IMPLEMENTED + 1 INFORMATIONAL)

### Why This Matters

Messages on the bus are not all equal. A heartbeat does not need a handshake. A contract does not tolerate silence. ARC-0768 gives the protocol the language to know the difference — the same way real networks differentiate between UDP (best-effort) and TCP (reliable delivery). Combined with the gateway and profile specs, HERMES now has the full infrastructure for Phase 1 inter-clan communication.

---

## [v0.2.0-alpha] — 2026-03-01

### The Agora Begins

This release introduces L5 — the social layer that allows independent HERMES clans to discover each other, collaborate, and build verifiable reputation without exposing private data.

### Added

- **ARC-3022: Agent Gateway Protocol** (DRAFT)
  - NAT-like boundary component between clan and public Agora
  - Identity translation: internal agent names → public aliases (never exposed)
  - Outbound filter: default-deny, operator approval for all data leaving the clan
  - Inbound validator: source verification, rate limiting, quarantine for first contact
  - `AGORA:` prefix convention for external messages on internal bus
  - TOFU (Trust-On-First-Use) model for inter-clan trust
  - Attestation protocol: signed certifications of cross-clan value delivery
  - Resonance metric: externally-validated reputation from attestations (decays, rewards diversity)
  - Dual metric architecture: Bounty (internal) + Resonance (external)

- **Research Agenda: L5 Social Topology**
  - Three sub-phases: L5a (Gateway + Profile), L5b (Attestation + Resonance), L5c (Visual Agora)
  - Six new mathematical tools for reputation modeling
  - Timeline integrated with L1-L4 research lines

- **docs/USE-CASES.md** — Six real-world deployment scenarios
  - Solo operator multi-domain, small team coordination, cross-clan collaboration
  - Community governance, personal productivity, open-source project coordination

- **docs/RESEARCH-AGENDA.md** — Public research roadmap (5 lines, L1-L5)

- **AES-2040** (Agent Visualization Standard) added to planned index

### Changed

- **README.md** — Added Agora section, gateway diagram, dual metric explanation, updated project structure
- **docs/ARCHITECTURE.md** — Added gateway boundary diagram, dual reputation model, ARC-3022 to specs table
- **docs/GLOSSARY.md** — Added 10 L5 terms: Agora, Attestation, Bounty, External Identity, Gateway, Public Profile, Quest, Resonance, TOFU, Translation Table
- **spec/INDEX.md** — Added ARC-3022 (DRAFT) and AES-2040 (PLANNED)
- **.gitignore** — Protected `.claude/` and `CLAUDE.md` from public repo

### Why This Matters

Phase 0 proved that file-based signaling works for agents within a single clan. But the real promise of HERMES is the same promise TCP/IP made: **open interconnection**. ARC-3022 is the first step toward a world where independent AI agent teams can meet, verify each other, and collaborate — without any single platform controlling the interaction.

The Agora is not a marketplace. It's a public square.

---

## [v0.1.0-alpha] — 2026-02-28

### Phase 0: The Foundation

The first public release of HERMES — a complete, working protocol for file-based inter-agent communication within a single clan.

### Added

- **7 core specifications** (all IMPLEMENTED):
  - ARC-0001: HERMES Architecture — the meta-standard defining the 5-layer stack
  - ARC-0791: Addressing & Routing — namespace addressing, star topology, Dijkstra/Erlang B analysis
  - ARC-0793: Reliable Transport — SYN/FIN/ACK session lifecycle
  - ARC-1918: Private Spaces & Firewall — namespace isolation, credential binding, data-cross protocol
  - ARC-5322: Message Format — JSONL wire format, 120-char Shannon constraint, ABNF grammar
  - ATR-X.200: Reference Model — formal 5-layer model (Physical → Application)
  - ATR-Q.700: Out-of-Band Signaling — design philosophy (signaling, not data)

- **30 standards planned** across three tracks:
  - ARC (IETF lineage): 16 standards
  - ATR (ITU-T lineage): 8 standards
  - AES (IEEE lineage): 5 standards

- **Python reference implementation** (46 tests passing):
  - Bus read/write with validation
  - Message lifecycle (create, consume, ACK, expire, archive)
  - Firewall rule evaluation
  - Routing table resolution
  - Full ARC-5322 validation algorithm

- **Documentation**:
  - README with ISP analogy and architecture overview
  - Quickstart guide (deploy in 5 minutes)
  - Architecture guide with ASCII diagrams
  - Agent structure guide (practical namespace organization)
  - Glossary of all HERMES terms
  - Contributing guide with standards proposal process

- **Examples**:
  - Sample bus file with valid messages
  - Sample routing table
  - Working Python agent (`simple_agent.py`) with full SYN/WORK/FIN cycle

- **Infrastructure**:
  - Init script (`scripts/init_hermes.sh`) for bootstrapping instances
  - GitHub issue template for ARC proposals
  - MIT license

### Design Decisions

- **File-based, not network-based**: HERMES agents share a filesystem, not an API. This eliminates servers, databases, and Docker — the protocol works anywhere files work.
- **JSONL, not JSON**: One message per line enables append-only writes and line-by-line parsing. No need to parse the entire bus to read one message.
- **120-character payload limit**: Inspired by Shannon's information theory. Forces precision over verbosity. If you can't say it in 120 chars, you're packing too many concerns.
- **Star topology with controller**: Simple, auditable, single point of coordination. Scales to ~50 namespaces before needing hierarchy (see L4 research line).
- **Human-in-the-loop**: HERMES informs, humans decide. No autonomous cross-namespace actions. This is a coordination protocol, not an automation framework.
- **Standards-first**: Every feature is a spec. Every spec maps to a real-world standard (IETF, ITU-T, or IEEE). This grounds the protocol in decades of network engineering.

### Why This Matters

AI agent frameworks are proliferating, but they're all walled gardens. Each platform has its own communication model, its own tool format, its own assumptions about trust. HERMES takes the opposite approach: define an **open protocol** that any agent on any platform can implement. The same way HTTP doesn't care if you're running Apache or Nginx, HERMES doesn't care if you're running Claude Code, Cursor, or a custom LLM pipeline.

The protocol is named after Hermes — the messenger who crosses boundaries. That's what this does.

---

## Versioning Note

HERMES uses alpha versioning during the research phase. The version will reach **v1.0** when all five research lines (L1-L5) produce at least one IMPLEMENTED specification each and the protocol can sustain inter-clan communication with cryptographic integrity.
