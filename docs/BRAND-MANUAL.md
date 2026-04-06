# Amaru — Brand Manual

> *The protocol is the value, not the pipe.*

**Version**: 1.1
**Date**: 2026-04-06
**Classification**: Public

> Amaru (formerly HERMES) — rebranded 2026-04-05.

---

## 1. Brand Identity

### 1.1 Name

**Amaru** — Named after the Quechua cosmic serpent that connects worlds — sky, earth, and the inner realm. The name encodes the protocol's purpose: enabling communication across boundaries that no single platform controls.

- **Full name**: Amaru Protocol
- **Formerly**: HERMES (Greek messenger god). Rebranded 2026-04-05.
- **Never**: amaru (all lowercase in prose), AMARÚ, Amarú
- **In code/CLI**: `amaru` (all lowercase, per Unix convention)
- **Repo**: `dereyesm/amaru-protocol`

### 1.2 Tagline

**Primary**: *An open protocol for inter-agent AI communication.*

**Secondary options** (context-dependent):
- *Inspired by TCP/IP. Built by telecom engineers.*
- *Sovereign agent communication for a multi-agent world.*
- *The messenger crosses boundaries.*

### 1.3 Positioning Statement

Amaru is an **open, sovereign protocol** for inter-agent AI communication — what TCP/IP did for computers, Amaru does for AI agents. Unlike cloud-dependent frameworks, Amaru works anywhere files work: air-gapped networks, local machines, sovereign infrastructure. It provides end-to-end encryption, verifiable reputation, and protocol-level interoperability with A2A and MCP — without requiring any single vendor's cloud.

### 1.4 Core Values

| Value | Meaning | Anti-pattern |
|-------|---------|-------------|
| **Sovereignty** | Agents and operators own their data and infrastructure | Vendor lock-in, cloud dependency |
| **Openness** | MIT license, public specs, standards-first | Proprietary protocols, walled gardens |
| **Precision** | 120-char payloads, Shannon-constrained, mathematically grounded | Verbose JSON blobs, unstructured comms |
| **Interoperability** | Bridge to A2A, MCP, NLIP — not replace them | "Kill the competition" mentality |
| **Trust without platforms** | E2E crypto, TOFU, attestation-based reputation | Centralized trust authorities |

---

## 2. Voice & Tone

### 2.1 Brand Voice

Amaru speaks like a **telecom engineer who reads philosophy** — technically precise, architecturally grounded, but aware that protocols shape societies.

| Attribute | Description | Example |
|-----------|-------------|---------|
| **Technical** | Grounded in RFCs, ITU-T, IEEE standards | "ARC-8446 implements Ed25519 + X25519 + AES-256-GCM, aligned with TLS 1.3 verify-before-decrypt." |
| **Concise** | Shannon-inspired brevity | "Signaling, not data." (ATR-Q.700) |
| **Principled** | Clear design philosophy | "The Agora is not a marketplace. It's a public square." |
| **Inclusive** | Welcomes builders from any stack | "Amaru doesn't care if you're running Claude Code, Cursor, or a custom LLM pipeline." |

### 2.2 Writing Rules

1. **English** for all public-facing content (global audience)
2. **Active voice** — "Amaru routes messages" not "Messages are routed by Amaru"
3. **Concrete analogies** over abstract descriptions:
   - Gateway = NAT (not "boundary component")
   - Bus = shared file (not "message broker")
   - Clan = autonomous agent team (not "organization unit")
4. **Reference always** — every design claim links to an RFC, paper, or dataset
5. **No hype** — "efficient" with benchmarks, not "revolutionary"

### 2.3 Terminology

| Term | Definition | Never say |
|------|-----------|-----------|
| **Clan** | An autonomous group of agents sharing an Amaru instance | Team, org, tenant |
| **Namespace** | An agent's address within a clan | User, account, endpoint |
| **Bus** | The shared JSONL file where messages live | Queue, broker, channel |
| **Gateway** | NAT-like boundary between clan and Agora | API, proxy, router |
| **Agora** | Public discovery layer (Git-based) | Marketplace, registry, hub |
| **Dojo** | SDN controller / skill orchestrator | Scheduler, dispatcher |
| **Quest** | Cross-clan collaboration with deliverables | Project, task, ticket |
| **Bounty** | Internal reputation metric | Score, points, karma |
| **Resonance** | External reputation from attestations | Rating, rank, trust score |
| **Sovereign mode** | File-based, self-hosted, no cloud | On-premise, local, offline |
| **Hosted mode** | Managed Hub service | Cloud, SaaS, hosted |

---

## 3. Visual Identity

### 3.1 Logo Concept

The Amaru logo represents **a messenger crossing boundaries** — two domains connected by a path.

**Primary mark**: Stylized caduceus simplified to two parallel lines (domains) with a diagonal crossing element (the messenger). Geometric, not ornamental.

**Constraints**:
- Monochrome-first (must work in terminal output and markdown)
- No gradients in primary mark
- Minimum clear space: 1x height on all sides

### 3.2 Color Palette

| Role | Color | Hex | Usage |
|------|-------|-----|-------|
| **Primary** | Deep Indigo | `#1A1A2E` | Headers, primary text, backgrounds |
| **Accent** | Electric Teal | `#00D4AA` | Links, highlights, interactive elements |
| **Signal** | Amber | `#F5A623` | Warnings, alerts, attention states |
| **Success** | Emerald | `#27AE60` | Confirmations, passing tests, healthy states |
| **Error** | Crimson | `#E74C3C` | Errors, failures, security alerts |
| **Neutral** | Slate | `#7F8C8D` | Secondary text, borders, disabled states |
| **Background** | Near-White | `#F8F9FA` | Page backgrounds, cards |

**Rationale**: Indigo + Teal = technical depth + clarity. Borrowed from network monitoring UIs where readability under pressure matters more than aesthetics.

### 3.3 Typography

| Context | Font | Fallback |
|---------|------|----------|
| **Headings** | Inter (Bold/Semibold) | system-ui, sans-serif |
| **Body** | Inter (Regular) | system-ui, sans-serif |
| **Code/Specs** | JetBrains Mono | monospace |
| **Terminal** | System monospace | — |

### 3.4 ASCII Art (Terminal/Markdown)

```
╔═══════════════════════════════════════╗
║  A M A R U    P R O T O C O L         ║
║  ─────────────────────────────────    ║
║  Open Inter-Agent Communication       ║
╚═══════════════════════════════════════╝
```

Use ASCII box drawing for terminal-friendly branding. No Unicode emoji in protocol output.

---

## 4. Messaging Framework

### 4.1 Elevator Pitch (30 seconds)

> "AI agents are proliferating, but they can't talk to each other without going through a vendor's cloud. Amaru is an open protocol — like TCP/IP for AI agents — that lets any agent on any platform communicate with end-to-end encryption, even offline. It bridges to Google A2A and Anthropic MCP, but doesn't depend on either."

### 4.2 Technical Pitch (2 minutes)

> "Amaru is a file-based inter-agent communication protocol inspired by TCP/IP and the 3GPP service-based architecture. It uses JSONL as its wire format with a 120-character Shannon-constrained payload, supports both datagram and reliable transport modes, and implements Ed25519 + X25519 + AES-256-GCM encryption aligned with TLS 1.3.
>
> What makes it different: it works anywhere files work — no servers, no Docker, no cloud. Air-gapped military networks, local development machines, sovereign infrastructure. The protocol bridges bidirectionally to Google A2A and Anthropic MCP via ARC-7231, so Amaru agents can participate in broader ecosystems without lock-in.
>
> The Agora layer uses Git repositories for discovery — agents publish profiles and build reputation through cryptographically signed attestations, not platform ratings. Think SMTP, not Slack."

### 4.3 Competitive Positioning

| Dimension | Amaru | A2A (Google) | MCP (Anthropic) | NLIP (Ecma) | ANP |
|-----------|--------|-------------|-----------------|-------------|-----|
| **Transport** | File (JSONL) + future Hub | HTTP/gRPC/SSE | HTTP/stdio/SSE | HTTP | DID-based |
| **Encryption** | E2E (Ed25519+X25519+AES-256-GCM) | TLS (transport) | TLS (transport) | Profile-based | DID-Auth |
| **Offline** | Yes (sovereign mode) | No | Local stdio only | No | No |
| **Governance** | MIT, independent | Linux Foundation | Anthropic | Ecma TC54 | Community |
| **Discovery** | Git-based Agora | Agent Cards (HTTPS) | Capability negotiation | NLIP profiles | DID documents |
| **Reputation** | Bounty + Resonance (dual) | None | None | None | None |
| **Interop** | Bridges to A2A + MCP | Native | Native | Bridges | DID |

**Key differentiators**:
1. **Sovereign-first**: Works without internet, clouds, or vendors
2. **E2E encryption**: Not just transport security — payload-level crypto
3. **Dual reputation**: Internal (Bounty) + external (Resonance) trust model
4. **Telecom DNA**: Designed by engineers who built 3GPP/ITU-T systems, not web developers adding features

### 4.4 "Why Not Just Use X?" Responses

| Objection | Response |
|-----------|----------|
| "Just use A2A" | A2A is excellent for cloud-native enterprise agents. Amaru serves the sovereign/offline/E2E-encrypted space that A2A doesn't address. They interop via ARC-7231. |
| "Just use MCP" | MCP is vertical (LLM ↔ tools). Amaru is horizontal (agent ↔ agent). They're complementary. Amaru bridges to MCP natively. |
| "Just use HTTP" | HTTP adds 40-60% overhead for agent-to-agent signaling. Amaru file-based transport has near-zero overhead for co-located agents. For remote, the Hub mode uses HTTP — but with Amaru semantics. |
| "Files don't scale" | Correct — that's why Amaru has dual-mode (Sovereign + Hosted). Files for <50 agents, Hub for scale. Same wire format both modes. |
| "Nobody uses this" | TCP/IP had 4 nodes in 1969. Amaru has 2 clans with encrypted bilateral communication in 2026. Protocols grow by being useful, not by being popular. |

---

## 5. Standards Identity

### 5.1 Spec Naming Convention

Amaru specs follow three tracks inspired by real-world standards bodies:

| Track | Lineage | Naming | Example |
|-------|---------|--------|---------|
| **ARC** | IETF (RFCs) | ARC-NNNN | ARC-5322 (Message Format, from RFC 5322) |
| **ATR** | ITU-T (Recommendations) | ATR-X.NNN | ATR-X.200 (Reference Model, from X.200 OSI) |
| **AES** | IEEE (Standards) | AES-NNN.NQ | AES-802.1Q (Namespace Isolation, from 802.1Q) |

**Rationale**: Every spec number maps to a real-world standard that inspired it. This is not vanity — it's a research tool. Engineers can look up the original standard to understand the design intent.

### 5.2 Spec Header Format

```markdown
# ARC-NNNN: Title

| Field | Value |
|-------|-------|
| Status | IMPLEMENTED / DRAFT / PLANNED |
| Track | ARC / ATR / AES |
| Tier | Core / Extension / Security / Meta / Philosophy |
| Lineage | RFC NNNN (Title) |
| Industry Reference | A2A, MCP, 3GPP TS, etc. |
| Date | YYYY-MM-DD |
| Author | Daniel Reyes |
```

---

## 6. Community Identity

### 6.1 Contribution Model

- **License**: MIT (permissive, no copyleft friction)
- **Governance**: Benevolent Dictator (Daniel Reyes, Protocol Architect) during bootstrap phase
- **Process**: GitHub issues → ARC proposal → plan mode → implementation → review → merge
- **Code of conduct**: Technical merit + respectful discourse. No corporate politics.

### 6.2 Clan Ecosystem

| Clan | Soberana | Status | Focus |
|------|---------|--------|-------|
| **DANI (momoshod)** | Daniel Reyes | Active | Protocol design, reference implementation |
| **JEI (La Triada)** | Jeimmy Gomez | Active | Security review, bilateral crypto |

New clans join by:
1. Deploying an Amaru instance (Sovereign mode: `scripts/init_amaru.sh`)
2. Generating keypair (`amaru keygen`)
3. Exchanging fingerprints with an existing clan (in-person or verified channel)
4. First encrypted handshake via relay or direct file exchange

### 6.3 Tagline for Community

> *The messenger crosses boundaries. So do we.*

---

## 7. Document Templates

### 7.1 Spec Document

Use `spec/ARC-0001.md` as the canonical template. Every spec includes:
- Abstract, Terminology, Specification, Examples, Security Considerations, References

### 7.2 Quest Proposal

Use `docs/QUEST-002-AAD-BILATERAL.md` as template. Every quest includes:
- Objective, Participants, Acceptance Criteria, Timeline, Deliverables

### 7.3 README Badge Format

```markdown
![specs](https://img.shields.io/badge/specs-15%20implemented-blue)
![tests](https://img.shields.io/badge/tests-419%20passing-green)
![version](https://img.shields.io/badge/version-v0.3.0--alpha-orange)
![license](https://img.shields.io/badge/license-MIT-brightgreen)
```

---

## 8. Anti-Patterns

Things Amaru **never** does in communication:

1. **Never claims to replace A2A, MCP, or any protocol** — we bridge, we don't compete
2. **Never uses "revolutionary", "disruptive", "game-changing"** — we use benchmarks
3. **Never promises scale we haven't tested** — file-based works for <50 agents, Hub for more
4. **Never hides limitations** — sovereign mode has tradeoffs, we document them
5. **Never uses corporate jargon** — "synergy", "leverage", "ecosystem play" are banned
6. **Never anthropomorphizes the protocol** — Amaru routes messages, it doesn't "think" or "decide"

---

*"The protocol is named after Amaru — the cosmic serpent that connects worlds. That's what this does."*
