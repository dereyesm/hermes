# HERMES Standards Index

Master index of all HERMES standards across the three tracks: ARC, ATR, and AES.

## Status Legend

| Status | Meaning |
|--------|---------|
| **IMPLEMENTED** | Complete spec with working reference implementation |
| **DRAFT** | Spec in progress, subject to change |
| **PLANNED** | Outlined but not yet written |
| **INFORMATIONAL** | Context, philosophy, or guidance — not a protocol spec |

---

## ARC — Agent Request for Comments (IETF Lineage)

Core protocol standards governing message formats, transport, addressing, and security.

| Number | Title | IETF Lineage | Status | Tier |
|--------|-------|-------------|--------|------|
| [ARC-0001](ARC-0001.md) | HERMES Architecture | Original | IMPLEMENTED | Core |
| ARC-0020 | Agent Lifecycle Management | RFC 20 (ASCII) | PLANNED | Core |
| [ARC-0768](ARC-0768.md) | Datagram & Reliable Message Semantics | RFC 768 (UDP) | IMPLEMENTED | Core |
| [ARC-0791](ARC-0791.md) | Addressing & Routing | RFC 791 (IP) | IMPLEMENTED | Core |
| [ARC-0793](ARC-0793.md) | Reliable Transport | RFC 793 (TCP) | IMPLEMENTED | Core |
| ARC-1035 | Namespace Resolution | RFC 1035 (DNS) | PLANNED | Extension |
| ARC-1122 | Agent Conformance Requirements | RFC 1122 (Host Req.) | PLANNED | Core |
| [ARC-1918](ARC-1918.md) | Private Spaces & Firewall | RFC 1918 (Private Addr.) | IMPLEMENTED | Core |
| [ARC-2119](ARC-2119.md) | Requirement Level Keywords | RFC 2119 (MUST/SHOULD) | IMPLEMENTED | Meta |
| ARC-2818 | Secure Bus Transport | RFC 2818 (HTTPS) | PLANNED | Security |
| [ARC-5322](ARC-5322.md) | Message Format | RFC 5322 (IMF) | IMPLEMENTED | Core |
| ARC-6455 | Real-Time Bus Extensions | RFC 6455 (WebSocket) | PLANNED | Extension |
| [ARC-2606](ARC-2606.md) | Agent Profile & Discovery | RFC 2606 (Reserved Domains) | IMPLEMENTED | Extension |
| [ARC-3022](ARC-3022.md) | Agent Gateway Protocol | RFC 3022 (NAT) | IMPLEMENTED | Extension |
| ARC-7231 | Agent Semantics | RFC 7231 (HTTP Semantics) | PLANNED | Extension |
| ARC-7519 | Message Authentication | RFC 7519 (JWT) | PLANNED | Security |
| ARC-7540 | Multiplexed Bus Channels | RFC 7540 (HTTP/2) | PLANNED | Extension |
| ARC-8446 | Encrypted Bus Protocol | RFC 8446 (TLS 1.3) | PLANNED | Security |

## ATR — Agent Telecom Recommendations (ITU-T Lineage)

Architecture, reference models, and telecom-inspired patterns.

| Number | Title | ITU-T Lineage | Status | Tier |
|--------|-------|-------------- |--------|------|
| ARC-0001 | _(see above)_ | — | — | — |
| [ATR-X.200](ATR-X200.md) | Reference Model | X.200 (OSI) | IMPLEMENTED | Core |
| ATR-X.500 | Agent Directory Services | X.500 (Directory) | PLANNED | Extension |
| ATR-X.509 | Agent Identity Certificates | X.509 (PKI) | PLANNED | Security |
| ATR-X.680 | Message Schema Notation | X.680 (ASN.1) | PLANNED | Extension |
| ATR-E.164 | Global Agent Addressing | E.164 (Phone Numbers) | PLANNED | Extension |
| [ATR-Q.700](ATR-Q700.md) | Out-of-Band Signaling | Q.700 (SS7) | INFORMATIONAL | Philosophy |
| ATR-Q.931 | Session Setup Signaling | Q.931 (ISDN) | PLANNED | Extension |
| ATR-G.711 | Payload Encoding | G.711 (Audio Codec) | PLANNED | Extension |

## AES — Agent Engineering Standards (IEEE Lineage)

Implementation standards for interoperability, isolation, and quality of service.

| Number | Title | IEEE Lineage | Status | Tier |
|--------|-------|-------------|--------|------|
| AES-802.1Q | Namespace Isolation (VLANs) | 802.1Q (VLANs) | PLANNED | Core |
| AES-802.3 | Bus Access Control | 802.3 (Ethernet) | PLANNED | Extension |
| AES-802.11 | Wireless/Ephemeral Agents | 802.11 (WiFi) | PLANNED | Extension |
| AES-1588 | Bus Timestamp Precision | 1588 (PTP) | PLANNED | Extension |
| AES-2030 | Ethical Agent Communication | 2030 (Ethical AI) | PLANNED | Philosophy |
| AES-2040 | Agent Visualization Standard | — (Original) | PLANNED | Extension |

---

## Tier Definitions

| Tier | Description |
|------|-------------|
| **Core** | Required for any HERMES-conformant implementation |
| **Extension** | Optional capabilities that extend the base protocol |
| **Security** | Standards focused on authentication, encryption, and integrity |
| **Meta** | Standards about the standards process itself |
| **Philosophy** | Design rationale and architectural guidance |

## Proposing a New Standard

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the process, or open an issue using the [ARC Proposal template](../.github/ISSUE_TEMPLATE/arc-proposal.md).
