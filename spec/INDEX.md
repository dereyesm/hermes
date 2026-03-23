# HERMES Standards Index

Master index of all HERMES standards across the three tracks: ARC, ATR, and AES.

## Status Legend

| Status | Meaning |
|--------|---------|
| **IMPLEMENTED** | Complete spec with working reference implementation |
| **DRAFT** | Spec in progress, subject to change |
| **PLANNED** | Outlined but not yet written |
| **INFORMATIONAL** | Context, philosophy, or guidance -- not a protocol spec |

---

## ARC -- Agent Request for Comments (IETF Lineage)

Core protocol standards governing message formats, transport, addressing, and security.

| Number | Title | IETF Lineage | Industry Reference | Status | Tier |
|--------|-------|-------------|-------------------|--------|------|
| [ARC-0001](ARC-0001.md) | HERMES Architecture | Original | IETF draft-rosenberg-ai-protocols (framework); 3GPP TS 23.501 (SBA pattern) | IMPLEMENTED | Core |
| ARC-0020 | Agent Lifecycle Management | RFC 20 (ASCII) | AGENTS.md (AAIF) agent lifecycle; 3GPP TS 23.501 NF lifecycle | PLANNED | Core |
| [ARC-0369](ARC-0369.md) | Agent Service Platform | BBF TR-369 (USP) | BBF TR-369 Controller/Agent model; 3GPP TS 23.501 NF lifecycle; USP MTP | IMPLEMENTED | Core |
| [ARC-0768](ARC-0768.md) | Datagram & Reliable Message Semantics | RFC 768 (UDP) | A2A stateless interactions; ECMA-431 (NLIP) interaction modes | IMPLEMENTED | Core |
| [ARC-0791](ARC-0791.md) | Addressing & Routing | RFC 791 (IP) | ANP DID-based discovery; 3GPP TS 29.510 (NRF) NF discovery | IMPLEMENTED | Core |
| [ARC-0793](ARC-0793.md) | Reliable Transport | RFC 793 (TCP) | MCP Streamable HTTP; A2A task lifecycle; ECMA-431 session management | IMPLEMENTED | Core |
| ARC-1035 | Namespace Resolution | RFC 1035 (DNS) | 3GPP TS 29.510 (NRF) service discovery; ANP DID resolution | PLANNED | Extension |
| ARC-1122 | Agent Conformance Requirements | RFC 1122 (Host Req.) | ECMA-430 (NLIP) conformance levels | PLANNED | Core |
| [ARC-1918](ARC-1918.md) | Private Spaces & Firewall | RFC 1918 (Private Addr.) | 3GPP TS 23.501 network slicing (Section 5.15); IEEE 802.1Q VLANs | IMPLEMENTED | Core |
| [ARC-2119](ARC-2119.md) | Requirement Level Keywords | RFC 2119 (MUST/SHOULD) | Universal across IETF, 3GPP, Ecma specifications | IMPLEMENTED | Meta |
| ARC-2818 | Secure Bus Transport | RFC 2818 (HTTPS) | ECMA-434 (NLIP) security profiles; IETF draft-mpsb-agntcy-slim (MLS) | PLANNED | Security |
| [ARC-5322](ARC-5322.md) | Message Format | RFC 5322 (IMF) | ECMA-430 (NLIP) envelope format; IETF draft-chang-agent-token-efficient (ADOL) | IMPLEMENTED | Core |
| ARC-6455 | Real-Time Bus Extensions | RFC 6455 (WebSocket) | A2A SSE streaming; MCP Streamable HTTP | PLANNED | Extension |
| [ARC-2606](ARC-2606.md) | Agent Profile & Discovery | RFC 2606 (Reserved Domains) | A2A Agent Cards; ANP capability files; ECMA-432 (NLIP) agent discovery | IMPLEMENTED | Extension |
| [ARC-2314](ARC-2314.md) | Skill Gateway Plane Architecture | -- (3GPP TS 23.214 CUPS) | 3GPP TS 23.501 (SBA); TS 23.502 (SMF); TS 29.244 (PFCP); TS 29.510 (NRF) | IMPLEMENTED | Core |
| [ARC-3022](ARC-3022.md) | Agent Gateway Protocol | RFC 3022 (NAT) | 3GPP TS 23.214 (CUPS); BBF TR-369 gateway; 3GPP inter-PLMN roaming | IMPLEMENTED | Extension |
| [ARC-4601](ARC-4601.md) | Agent Node Protocol | RFC 4601 (PIM-SM) | 3GPP TS 23.501 NF lifecycle; PIM-SM rendezvous point; persistent forwarding state | IMPLEMENTED | Extension |
| [ARC-7231](ARC-7231.md) | Agent Semantics — Bridge Protocol Mapping | RFC 7231 (HTTP Semantics) | BBF TR-369 CRUD+Operate+Notify; FIPA ACL performatives; A2A v0.3/MCP bridge mapping | IMPLEMENTED | Extension |
| ARC-7519 | Message Authentication | RFC 7519 (JWT) | IETF draft-goswami-agentic-jwt; 3GPP TS 29.510 (NRF) OAuth 2.0 model | PLANNED | Security |
| ARC-7540 | Multiplexed Bus Channels | RFC 7540 (HTTP/2) | A2A multiplexed task streams; 3GPP TS 23.501 PDU sessions | PLANNED | Extension |
| [ARC-8446](ARC-8446.md) | Encrypted Bus Protocol | RFC 8446 (TLS 1.3) | ECMA-434 (NLIP) security levels; IETF SLIM (MLS); NIST FIPS 203-205 (PQC) | IMPLEMENTED | Security |
| [ARC-9001](ARC-9001.md) | Bus Integrity Protocol | — (MVCC/OCC) | SS7 sequence numbering (ITU-T Q.703); Database OCC; 3GPP TS 23.501 NF state | IMPLEMENTED | Core |

## ATR -- Agent Telecom Recommendations (ITU-T Lineage)

Architecture, reference models, and telecom-inspired patterns.

| Number | Title | ITU-T Lineage | Industry Reference | Status | Tier |
|--------|-------|-------------- |-------------------|--------|------|
| ARC-0001 | _(see above)_ | -- | -- | -- | -- |
| [ATR-X.200](ATR-X200.md) | Reference Model | X.200 (OSI) | 3GPP TS 23.501 (SBA); 3GPP TS 23.214 (CUPS); ECMA-430 (NLIP) layered model | IMPLEMENTED | Core |
| ATR-X.500 | Agent Directory Services | X.500 (Directory) | 3GPP TS 29.510 (NRF); ANP decentralized directory; ECMA-432 (NLIP) discovery | PLANNED | Extension |
| ATR-X.509 | Agent Identity Certificates | X.509 (PKI) | W3C DIDs v1.0; IETF draft-goswami-agentic-jwt; ECMA-434 (NLIP) security | PLANNED | Security |
| ATR-X.680 | Message Schema Notation | X.680 (ASN.1) | RFC 8949 (CBOR); ECMA-433 (NLIP) data packaging; JSON Schema | PLANNED | Extension |
| ATR-E.164 | Global Agent Addressing | E.164 (Phone Numbers) | ANP DID identifiers; A2A Agent Card URLs; 3GPP SUPI/GPSI (TS 23.003) | PLANNED | Extension |
| [ATR-Q.700](ATR-Q700.md) | Out-of-Band Signaling | Q.700 (SS7) | 3GPP TS 29.244 (PFCP) signaling; SIP (RFC 3261); ECMA-431 (NLIP) signaling | INFORMATIONAL | Philosophy |
| ATR-Q.931 | Session Setup Signaling | Q.931 (ISDN) | A2A task initiation; MCP session negotiation; SIP INVITE (RFC 3261) | PLANNED | Extension |
| [ATR-G.711](ATR-G711.md) | Payload Encoding & Wire Efficiency | G.711 (Audio Codec) | RFC 8949 (CBOR); BBF TR-181 data model encoding; MessagePack | IMPLEMENTED | Extension |

## AES -- Agent Engineering Standards (IEEE Lineage)

Implementation standards for interoperability, isolation, and quality of service.

| Number | Title | IEEE Lineage | Industry Reference | Status | Tier |
|--------|-------|-------------|-------------------|--------|------|
| AES-802.1Q | Namespace Isolation (VLANs) | 802.1Q (VLANs) | 3GPP TS 23.501 network slicing; RFC 1918 private addressing | PLANNED | Core |
| AES-802.3 | Bus Access Control | 802.3 (Ethernet) | 3GPP TS 23.501 NF service access; BBF TR-369 access control | PLANNED | Extension |
| AES-802.11 | Wireless/Ephemeral Agents | 802.11 (WiFi) | A2A ephemeral agent tasks; serverless function patterns | PLANNED | Extension |
| AES-1588 | Bus Timestamp Precision | 1588 (PTP) | 3GPP TS 23.501 time sync; NTP (RFC 5905) | PLANNED | Extension |
| AES-2030 | Ethical Agent Communication | 2030 (Ethical AI) | IEEE 7000 series (ethical AI); EU AI Act compliance | PLANNED | Philosophy |
| [AES-2040](AES-2040.md) | Agent Visualization Standard | -- (Original) | 5-layer viz stack; Protocol Explorer; Agora visual directory | DRAFT | Extension |
| AES-2045 | Agent Cognitive Profile | -- (Original) | FIPA ACL cognitive models; computational psychology | PLANNED | Extension |

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
