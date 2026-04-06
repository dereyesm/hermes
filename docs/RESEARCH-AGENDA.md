# Research Agenda — Amaru Protocol Evolution

> From file-based signaling to next-generation inter-agent communication.

## Vision

HERMES Phase 0 proved that file-based, TCP/IP-inspired signaling works for AI agents. The next phases must answer: can we build something **lighter, more secure, and more efficient** than stacking AI on HTTP/TCP — while remaining open and inspectable?

But efficiency alone is not enough. The AI agent ecosystem needs what the early internet gave humans: **a way to meet, trust, and collaborate across boundaries without surrendering sovereignty**. L1-L4 build the infrastructure. L5 builds the world on top of it — the Agora where clans connect, agents prove their worth, and reputation is earned, not bought.

## Industry Context

For curated analysis of industry frameworks (McKinsey, Gartner, etc.) that validate and inform HERMES design decisions, see **[INDUSTRY-RESEARCH.md](INDUSTRY-RESEARCH.md)**. The alignment map there connects each research line below to enterprise transformation themes.

## Research Lines

### L1: Post-Quantum Cryptographic Integrity

**Problem**: Bus messages are plaintext. Any process with file access can read, forge, or tamper.

**Target ARC**: ARC-8446 (Encrypted Bus Protocol)

**Approach**:
1. Survey NIST PQC finalists: Kyber (FIPS 203), Dilithium (FIPS 204), SPHINCS+ (FIPS 205)
2. Measure signature/key sizes vs classical (Ed25519, ECDSA) — PQC is 2-10x larger
3. Design a signing scheme for JSONL messages that doesn't break human readability
4. Prototype: sign messages in Python ref impl, verify on read
5. Benchmark: overhead per message (bytes, CPU time) on commodity hardware

**Key question**: Can we sign without inflating the bus beyond acceptable limits?

**Datasets**: NIST PQC reports, liboqs benchmarks, Open Quantum Safe project

### L2: Agent Communication Language (ACL)

**Problem**: JSON is verbose. A typical HERMES message is ~200 bytes of JSON for ~80 bytes of semantic content. 60% overhead.

**Target ARC**: ARC-7231 (Agent Semantics)

**Approach**:
1. Catalog HERMES message patterns (from bus-archive + active bus)
2. Design a compressed semantic encoding:
   - Option A: Binary (CBOR/MessagePack) with human-readable debug mode
   - Option B: Semantic hashing — shared ontology between agents reduces payload
   - Option C: Natural language tokens mapped to fixed-width codes (like Huffman for agent vocab)
3. Compare compression ratios: JSON vs CBOR vs custom ACL vs Protobuf
4. Maintain dual-mode: compressed for transit, expanded for inspection
5. Reference FIPA ACL (IEEE Foundation for Intelligent Physical Agents) and KQML

**Key question**: What compression ratio can we achieve without losing inspectability?

**Datasets**: Amaru bus archive (anonymized), FIPA ACL spec archive, JSON compression benchmarks

### L3: Channel Efficiency Model

**Problem**: We claim HERMES is lighter than HTTP/TCP for inter-agent communication. Prove it with data.

**Target ATR**: ATR-G.711 redefined as Channel Efficiency Model

**Approach**:
1. Model TCP/IP overhead for a typical agent API call:
   - TCP handshake (3 packets), TLS 1.3 (1-2 RTT), HTTP headers (~500 bytes), JSON body
   - Total overhead for a 120-byte payload: estimate ~2-4KB per message
2. Model HERMES overhead:
   - File append: 1 syscall, ~200 bytes JSON, no network stack
   - File read: 1 syscall, sequential scan
3. Use Ookla/M-Lab data to model real-world latency for network-based approaches
4. Calculate energy per message (Joules) for both models
5. Model scaling: at what agent count does HTTP API become bottleneck vs file bus?

**Key question**: At what scale does file-based beat network-based, and vice versa?

**Datasets**:
- Ookla Speedtest Intelligence (AWS Open Data: `s3://ookla-open-data/`)
- M-Lab NDT dataset (BigQuery: `measurement-lab.ndt.*`)
- CAIDA AS topology (caida.org/catalog)
- ITU-D ICT Eye (itu.int/en/ITU-D/Statistics)

### L4: Adaptive Topology

**Problem**: Star topology (controller hub) works for <10 namespaces. What about 100? 1000? Inter-instance peering?

**Target AES**: AES-802.1Q extended + new AES for adaptive routing

**Approach**:
1. Model current star topology limits: single bus file = bottleneck at N namespaces
2. Design tiered topology:
   - Small (<10 ns): Star (current, controller hub)
   - Medium (10-50 ns): Hierarchical star (regional controllers)
   - Large (50+ ns): Mesh with SDN controller (Dojo-like)
   - Inter-instance: BGP-like peering between HERMES deployments
3. Define topology negotiation protocol: agents discover and adapt
4. Failover: if controller goes offline, namespaces operate autonomously
5. Reference: OpenFlow (SDN), BGP (RFC 4271), OSPF (RFC 2328), Raft (consensus)

**Key question**: Can the protocol itself decide the topology, or does the operator?

**Datasets**: CAIDA AS topology (for inter-instance modeling), OpenFlow switch benchmarks

### L5: Social Topology & Agent Reputation (The Agora)

**Problem**: Amaru clans operate in isolation. Each clan has internal agents, metrics (Bounty/XP), and a private bus — but no mechanism exists for clans to discover each other, verify capabilities, collaborate on cross-clan tasks, or build verifiable reputation. The agent ecosystem is a collection of islands with no ocean.

Meanwhile, the AI agent landscape is fragmenting: proprietary platforms lock agents into walled gardens, agent marketplaces commoditize capabilities without attribution, and no open standard exists for inter-clan social interaction. The result is a world where AI agents serve corporations but not communities.

L5 answers: **How do sovereign clans meet, trust, collaborate, and build shared reputation — without surrendering privacy or sovereignty?**

**Target Specs**:

| Spec | Title | Sub-phase | Role |
|------|-------|-----------|------|
| **ARC-3022** | Agent Gateway Protocol | L5a | NAT at clan boundary — identity translation, filtering, profile publication |
| **ARC-2606** | Agent Profile & Discovery | L5a | Rich profile format, capability ontology, Agora directory search |
| **ARC-4861** | Cross-Clan Attestation Protocol | L5b | Signed statements certifying cross-clan value delivery |
| **AES-2040** | Agent Visualization Standard | L5c | Visual representation of agents and clans in the Agora |
| **ATR-X.500** | Agent Directory Services | L5a/b | Agora directory protocol, federation, search semantics |

**Dependencies on other lines**:
- L1 (Crypto) → attestation signatures, clan keypairs, TOFU-to-PKI upgrade path
- L2 (ACL) → cross-clan message semantics, capability ontology encoding
- L4 (Topology) → inter-instance peering is the transport layer beneath L5's social layer

---

#### L5a: Gateway + Profile (The Plumbing)

**Status**: ARC-3022 DRAFT COMPLETE (2026-03-01)

**Approach**:
1. ~~Define the Agent Gateway Protocol (ARC-3022)~~ — **DONE**
   - NAT-like identity translation (internal names → public aliases)
   - Outbound filter (default-deny, operator approval)
   - Inbound validator (source verification, rate limiting, quarantine)
   - AGORA: prefix convention for external messages on internal bus
   - TOFU trust model (upgrade to PKI when L1 delivers ARC-8446)
2. Design the Agent Profile format (ARC-2606):
   - Profile schema: clan metadata, published agents, capabilities, Resonance scores
   - Capability ontology: hierarchical taxonomy of what agents can do
     - Option A: Flat tags (e.g., `["property-law", "financial-audit"]`)
     - Option B: Hierarchical (e.g., `legal.property`, `finance.audit.forensic`)
     - Option C: Schema.org-inspired linked data (machine-discoverable)
   - Search protocol: how a clan finds agents with specific capabilities
   - Profile versioning: how profiles evolve without breaking references
3. Design the Agora directory (ATR-X.500):
   - Option A: **Git-based** — profiles as YAML files in a public repo, PRs for registration
     - Pros: auditable, offline-capable, familiar tooling, signed commits
     - Cons: scales to ~10K clans before repo size becomes unwieldy
   - Option B: **DHT (Kademlia-style)** — decentralized, no single point of failure
     - Pros: scales indefinitely, censorship-resistant
     - Cons: complex, eventual consistency, no audit trail
   - Option C: **Federated registries** — regional Agora instances that cross-reference
     - Pros: balances scale and governance, mirrors DNS hierarchy
     - Cons: requires coordination between registry operators
   - **Recommendation**: Start with Git (Option A), design migration path to C (federated)
4. Prototype: Python ref impl of `amaru.gateway` module
   - `Gateway` class with NAT, filter, validator components
   - CLI: `amaru gateway init`, `amaru gateway publish`, `amaru gateway discover`
   - Integration tests: two mock clans exchanging profiles via Git directory

**Key questions**:
- What capability ontology is rich enough for discovery but simple enough to adopt?
- At what clan count does Git-based directory need to federate?
- How to handle clan identity squatting (someone registers your clan name)?

**Datasets**:
- Schema.org ontology (schema.org/docs/full.html) — for capability modeling
- GitHub social graph (GHTorrent) — for modeling directory scale
- FIPA Agent Directory Facilitator spec (IEEE SC00023) — prior art

---

#### L5b: Attestation + Resonance (The Trust Layer)

**Approach**:
1. Formalize the Attestation Protocol (ARC-4861):
   - Attestation format: signed YAML/JSON with from_clan, to_clan, to_agent, rating, summary
   - Rating dimensions: quality (1-5), reliability (1-5), collaboration (1-5)
   - Rules: asymmetric, append-only, one per quest per agent pair, no self-attestation
   - Signature: Ed25519 initially, PQC upgrade path via ARC-8446
   - Storage: attestations stored at both issuing and receiving clan gateways
   - Verification: any clan can verify using the issuer's public key from Agora directory
2. Design the Resonance metric:
   - Formula: `Resonance(a) = Σ score(att) × recency(att) × diversity(att)`
   - Recency weight: linear decay over 365 days — encourages sustained contribution
   - Diversity bonus: attestations from N different clans worth more than N from one clan
   - Anti-gaming: Sybil resistance through clan identity verification + minimum age requirements
   - Resonance is COMPUTED, never self-declared — the gateway calculates from verified attestations
3. Design the dual metric architecture:
   - **Bounty** (internal): XP × precision × impact. Computed by Dojo. Visible to clan only.
   - **Resonance** (external): Attestation-derived. Computed by gateway. Visible to all clans.
   - Mapping: Bounty feeds capability claims; Resonance validates them externally
   - The two metrics are complementary, never substitutes:
     - High Bounty + Low Resonance = strong but unproven externally
     - Low Bounty + High Resonance = externally valued, possibly underrated internally
     - High both = proven agent
     - Low both = new or underperforming
   - Gateway MUST NOT expose Bounty through public profile
4. Model reputation dynamics:
   - Simulate Resonance evolution with synthetic attestation streams
   - Compare against EigenTrust (distributed) and PageRank (centralized) models
   - Measure: convergence time, Sybil resistance, sensitivity to collusion
   - Design circuit breakers: if a clan issues suspiciously many attestations, flag for review
5. Design dispute resolution framework:
   - What happens when a clan disputes an attestation?
   - Option A: Attestations are immutable — disputes are addressed by counter-attestations
   - Option B: Arbitration panel (set of neutral clans) can annotate disputed attestations
   - Option C: Time-based resolution — disputed attestations lose recency weight faster
   - **Recommendation**: Option A (simplest, aligns with append-only philosophy)

**Key questions**:
- What is the minimum number of attestations for Resonance to be statistically meaningful?
- How do we prevent Sybil attacks (fake clans attesting for each other)?
- Can Resonance be portable across Agora implementations, or is it directory-specific?
- What decay rate balances rewarding consistency vs. allowing recovery from bad ratings?

**Datasets**:
- EigenTrust dataset (Kamvar et al., 2003) — P2P reputation simulation
- eBay/Amazon review datasets (Kaggle) — real-world reputation dynamics
- Bitcoin Web of Trust dataset — decentralized trust graph analysis
- Stack Overflow reputation data (archive.org) — skill-based reputation modeling

**Mathematical tools**:
- **EigenTrust algorithm**: Global trust from local attestations — iterative aggregation
- **PageRank (adapted)**: Clan influence weighted by who attests for whom
- **Bayesian reputation**: Prior belief updated with each attestation (Beta distribution)
- **Sybil detection**: Graph clustering (spectral analysis) to identify colluding clans
- **Decay functions**: Exponential vs. linear vs. step — model impact on long-term fairness

---

#### L5c: Visual Agora (The Social Space)

**Problem**: Protocols are invisible. For L5 to drive adoption, clans and their agents need a visual, interactive representation — a space where humans can browse, compare, and connect with agents from other clans. The goal is not a dashboard but a **world**: the Agora.

**Target AES**: AES-2040 (Agent Visualization Standard)

**Approach**:
1. Define the visualization data model (AES-2040):
   - Agent representation: avatar/sprite, alias, capabilities, Resonance badge, clan affiliation
   - Clan representation: banner/emblem, display name, total Resonance, member count
   - Space representation: rooms/zones where agents "exist" — organized by capability domain
   - Interaction model: agents don't "chat" — they display attestations, quest history, capabilities
2. Design the Agora UI as a web application:
   - Option A: **2D isometric** (Habbo Hotel style) — familiar, lightweight, retro-cool
   - Option B: **Card-based directory** — simpler, mobile-friendly, LinkedIn-like
   - Option C: **Terminal/ASCII** — extends arena.py to a networked multi-clan view
   - **Recommendation**: Option A for the public Agora, Option C as reference implementation
3. Define interaction patterns:
   - **Browse**: Explore clans and their published agents by capability, Resonance, or domain
   - **Inspect**: View an agent's public profile, attestation history, Resonance graph over time
   - **Propose**: Initiate a quest proposal from one clan's agent to another's
   - **Attest**: After a quest, issue a signed attestation through the UI
   - **Observe**: Watch real-time Agora activity — new clans joining, quests completing, Resonance changing
4. Design the theming/aesthetic system:
   - Each clan can customize their agents' visual representation within constraints
   - Resonance level affects visual flair (higher Resonance = more elaborate display)
   - Capability domains map to visual zones (legal = courthouse, finance = vault, engineering = workshop)
   - RPG/cyberpunk aesthetic as default skin — but the standard is skin-agnostic
5. Prototype:
   - Phase 1: Static HTML/JS page that reads clan profiles from Git directory and renders cards
   - Phase 2: Interactive 2D space with agent sprites, clan zones, attestation visualization
   - Phase 3: Real-time updates via WebSocket/SSE (connects to ARC-6455 Real-Time Bus Extensions)
6. Accessibility and openness:
   - The Agora MUST be viewable without authentication (public profiles are public)
   - Quest proposals and attestations require clan gateway authentication
   - The visualization layer is a CLIENT of the Agora directory, not a gatekeeper
   - Multiple Agora UIs can coexist — the standard defines the data model, not the renderer

**Key questions**:
- Should the Agora UI be a centralized web app or a static site generated from the Git directory?
- How do we make agent visualization meaningful (not just cosmetic) — tied to real capabilities?
- Can the visual layer work offline (read-only mode from cached profiles)?
- What's the minimum viable visual that drives adoption without over-engineering?

**Inspiration and references**:
- Habbo Hotel (Sulake, 2000) — 2D isometric social space with rooms and avatars
- GitHub profile + contribution graph — reputation visualization through activity
- Arena.py "El Pueblo" (Dojo internal) — ASCII clan roster, extensible to web
- Cyberpunk 2077 "Street Cred" UI — reputation as a visible, gamified metric
- One Piece Bounty posters — visual representation of an agent's known impact
- Pokemon trainer cards — compact summary of team composition and achievements

**Technical stack considerations**:
- Static site generator (Hugo/Astro) + Git directory = zero-server Agora viewer
- Phaser.js or PixiJS for 2D isometric rendering (if Option A)
- YAML profiles → JSON API via build step → consumed by any frontend
- Attestation verification in browser via WebCrypto API (Ed25519 verification)

---

#### L5 Cross-Cutting Concerns

**Privacy-by-design**: Every L5 component inherits ARC-1918's default-deny model. The gateway is the sole boundary. Internal data never leaks. This is non-negotiable — a social layer that compromises sovereignty is worse than no social layer.

**Human-in-the-loop**: All cross-clan interactions (quest proposals, attestation issuance, profile publication) require operator approval. The Agora facilitates — it does not automate trust decisions.

**Interoperability**: L5 specs define data formats and protocols, not implementations. Any frontend can render Agora profiles. Any backend can serve the directory. The standard outlives any specific tool.

**Progressive disclosure**: A clan can participate in L5 at any depth:
- Level 0: No gateway. Fully private. No Agora participation.
- Level 1: Gateway with profile only. Discoverable but no interaction.
- Level 2: Gateway + quest proposals. Active collaboration.
- Level 3: Full attestation participation. Building Resonance.
- Level 4: Visual presence in the Agora. Full social participation.

## Timeline (Suggested)

| Phase | Period | Deliverable |
|-------|--------|-------------|
| Phase 1 | Mar-Apr 2026 | L3 Channel Efficiency paper + data pipeline |
| Phase 1b | Mar 2026 | L5a ARC-3022 Gateway draft (DONE) + ARC-2606 Profile |
| Phase 2 | May-Jun 2026 | L1 ARC-8446 draft + Python prototype |
| Phase 3 | Jul-Aug 2026 | L2 ACL draft + compression benchmarks |
| Phase 3b | Jul-Aug 2026 | L5b ARC-4861 Attestation + Resonance prototype |
| Phase 4 | Sep-Oct 2026 | L4 Adaptive topology draft + simulation |
| Phase 4b | Sep-Oct 2026 | L5c AES-2040 Visual Agora prototype |
| Phase 5 | Nov-Dec 2026 | HERMES v1.0 spec consolidation (L1-L5) |

## Mathematical Tools

| Tool | Application | Line |
|------|------------|------|
| Shannon entropy | Measure information density of messages | L2, L3 |
| Kolmogorov complexity | Lower bound on message compression | L2 |
| Queueing theory (M/M/1, M/M/c) | Bus scaling under load | L3, L4 |
| Graph theory (Dijkstra, Bellman-Ford) | Routing in mesh topologies | L4 |
| Erlang B/C | Blocking probability in dispatch | L4 |
| Lattice-based crypto math | PQC scheme analysis | L1 |
| EigenTrust algorithm | Global trust aggregation from local attestations | L5b |
| PageRank (adapted) | Clan influence weighting in attestation graphs | L5b |
| Bayesian reputation (Beta distribution) | Prior/posterior trust updates per attestation | L5b |
| Spectral graph clustering | Sybil detection — identify colluding clan groups | L5b |
| Decay functions (exponential/linear) | Resonance recency weighting fairness analysis | L5b |
| Network effects modeling (Metcalfe's law) | Agora value vs. clan count — adoption threshold | L5a, L5c |
