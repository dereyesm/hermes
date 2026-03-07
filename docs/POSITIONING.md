# HERMES: Technical Positioning

> Sovereign file-based communication and hosted Hub services -- one wire format, two deployment modes, for the multi-agent era.

**Version**: 2.0 | **Date**: March 2026 | **Status**: Living document

---

## 1. Introduction: The Agent Communication Landscape in 2026

The AI agent ecosystem has reached an inflection point. In the span of eighteen months, at least six distinct communication protocols have emerged from major industry players: Anthropic's MCP for model-to-tool binding, Google's A2A for agent-to-agent orchestration, Ecma International's NLIP (ECMA-430 through 434) as the first formal standard for natural-language agent interaction, IETF drafts for agent token efficiency (ADOL) and real-time messaging (SLIM), and community efforts like ANP for decentralized discovery. The Linux Foundation's AAIF now governs both MCP and AGENTS.md, while LF AI&Data shepherds A2A and ACP.

Each protocol addresses a genuine need. Yet all share a common architectural assumption: **network infrastructure exists**. MCP requires a runtime process or HTTP server. A2A requires HTTP/2 endpoints. NLIP assumes HTTP, WebSocket, or AMQP transport. SLIM depends on gRPC. Every protocol in the current landscape assumes some form of server, endpoint, or persistent process.

This assumption excludes a significant class of deployments: developers running multiple agent sessions on a laptop with no servers, teams coordinating through a shared Git repo with no cloud, organizations where policy prohibits network calls from agent processes, and the common case where agents are invoked on demand and terminate after seconds -- with no persistent process to receive messages.

These are not edge cases. They are the default operational mode for most AI agent deployments today.

HERMES was designed for this reality -- and for the reality that comes after it. Some deployments will never need infrastructure. Others will eventually want managed services, SLAs, and turnkey onboarding. HERMES serves both through a dual-mode architecture: **Sovereign mode** for self-hosted, file-based communication, and **Hosted mode** for centralized Hub services. Same wire format. Same privacy model. Different operational profiles.

---

## 2. Dual-Mode Architecture

The core insight behind HERMES's architecture is borrowed from email. SMTP has been the universal mail transport protocol for four decades. You can run your own mail server (Sovereign) or use Gmail (Hosted). Both speak the same wire protocol. Both interoperate. The choice is operational, not architectural.

HERMES applies this pattern to agent communication:

### Sovereign Mode

File-based, self-hosted, fully decentralized. A clan runs its own `bus.jsonl`, its own `routes.md`, and its own gateway process. Inter-clan communication happens via Gateway-to-Gateway HTTPS peering -- each clan operator controls who they peer with, what capabilities they expose, and what identity translation rules the gateway applies. No central service is involved. No third party sees the traffic.

Sovereign mode is not a bootstrap phase. It is not a stepping stone toward something "better." It is a permanent, first-class deployment mode with properties that no hosted service can replicate: zero external dependencies, complete data sovereignty, offline operation, and filesystem-level auditability (every message is a line in a file that can be `git log`-ed).

### Hosted Mode

Centralized Hub service with managed infrastructure. The HERMES Hub operates gateways on behalf of clans, handles peering, provides discovery, and offers SLAs for message delivery, uptime, and latency. A clan using Hosted mode does not need to run any infrastructure -- they configure their agents to write to the Hub's API endpoint instead of a local `bus.jsonl`, and the Hub handles routing, translation, and inter-clan delivery.

Hosted mode lowers the barrier to entry. A new clan can be operational in minutes: create an account, register agent capabilities, start sending messages. The Hub handles the operational complexity that Sovereign operators manage themselves.

### Same Wire Format, Different Transport

Both modes use the same message format ([ARC-5322](../spec/ARC-5322.md)): a single JSON object per line with `ts`, `src`, `dst`, `type`, `msg`, `ttl`, and `ack` fields. The same privacy model applies: ARC-1918 namespace isolation, ARC-3022 gateway-as-NAT identity translation, credential firewalls. The same trust metrics operate: Bounty (internal) and Resonance (external).

The difference is transport:

| Property | Sovereign Mode | Hosted Mode |
|----------|---------------|-------------|
| **Bus** | Local `bus.jsonl` file | Hub API endpoint |
| **Routing** | Local `routes.md` | Hub-managed routing |
| **Inter-clan transport** | Gateway-to-Gateway HTTPS | Hub-mediated relay |
| **Discovery** | Agora Git repos + direct peering | Hub directory service |
| **Infrastructure** | Self-managed | Managed (SLA-backed) |
| **Offline operation** | Full | No (requires Hub connectivity) |
| **Data location** | Operator-controlled | Hub data centers |
| **Cost** | Zero (compute + storage only) | Subscription/usage-based |

A Sovereign clan and a Hosted clan can communicate with each other. The Hub's gateway speaks the same peering protocol as any Sovereign gateway. From the perspective of the message format, the two modes are indistinguishable.

This mirrors the email ecosystem precisely: a self-hosted Postfix server and a Gmail account exchange mail seamlessly because both speak SMTP. HERMES achieves the same interoperability because both modes speak ARC-5322 over ARC-3022 gateways.

---

## 3. Sovereign Mode: File-Based Communication

Sovereign mode is where HERMES's design philosophy is most visible. A complete Sovereign deployment requires:

1. A JSONL file (`bus.jsonl`) -- the message bus
2. A markdown file (`routes.md`) -- the routing table
3. The convention that agents read from and write to these files

That is the entire infrastructure. No compilation step, no daemon to start, no port to open, no dependency to install. An agent can write a HERMES message with nothing more than:

```bash
echo '{"ts":"2026-03-03","src":"eng","dst":"ops","type":"state","msg":"Ready.","ttl":7,"ack":[]}' >> bus.jsonl
```

This is not a simplified example for documentation purposes. This is the actual protocol in production. The message format ([ARC-5322](../spec/ARC-5322.md)) is a single JSON object per line. The bus is an append-only JSONL file. The transport mechanism is the filesystem's write operation.

### Zero Infrastructure

**No single point of failure.** The bus is a file. If the filesystem works, the protocol works. There is no server to crash, no port to block, no certificate to expire, no rate limit to hit.

**No network dependency.** Agents communicate through the filesystem, not through the network stack. This eliminates the TCP handshake (1 RTT), TLS negotiation (1-2 RTT), HTTP header overhead (~500 bytes per request), and connection management complexity that network-based protocols require for every message exchange.

**Instant deployment.** The time from "I want my agents to coordinate" to "my agents are coordinating" is the time it takes to create a file. No infrastructure provisioning, no service mesh configuration, no API key generation.

**Universal compatibility.** Every programming language, every operating system, and every AI framework can read and write files. HERMES has no language-specific SDK requirement. The Python reference implementation exists for convenience and validation, but the protocol is defined by its file format, not by any library.

### Privacy as Architecture

The second structural advantage of Sovereign mode is organizational privacy. A2A's Agent Card is published to a discoverable URL. MCP's tool manifests are exposed to the calling model. NLIP's agent profiles are exchanged over network connections. These designs are correct for their intended use cases -- they enable discovery and interoperability across organizational boundaries. But they create a problem for communication **within** boundaries.

Inside an organization, agents handle sensitive data: financial projections, legal documents, personnel records, strategic plans. The agent that manages legal review should not be discoverable by the agent that handles marketing campaigns. The financial planning agent's messages should not be readable by the engineering deployment agent. These are not hypothetical concerns -- they are the first requirement any enterprise security team will raise when evaluating agent coordination protocols.

HERMES was designed with this constraint from the beginning. ARC-1918 (Private Spaces & Firewall), modeled after RFC 1918's private IP address ranges, defines namespace isolation as a core protocol feature, not an optional extension:

- **Namespaces are isolated by default.** An agent in namespace `legal` cannot read messages addressed to namespace `finance`. The bus carries messages for all namespaces, but agents filter by destination -- and the routing table enforces which namespaces each agent process can access.

- **Credential isolation is absolute.** API keys, OAuth tokens, and service credentials are bound to their namespace. The protocol specification requires that credentials MUST NOT be accessible across namespace boundaries, even by the controller namespace (which has read access to bus messages but not to namespace-level configuration).

- **Cross-namespace data movement requires human approval.** When data needs to flow from one namespace to another -- a financial report from `finance` to the `board` namespace, for instance -- it travels as a `data_cross` message type that requires explicit human acknowledgment. The protocol does not automate boundary crossings. It surfaces them for human decision.

### Gateway-as-NAT

The gateway ([ARC-3022](../spec/ARC-3022.md)) extends this privacy model to the clan boundary. Modeled after RFC 3022 (Network Address Translation), the gateway performs identity translation: internal agent names and namespace structure are never exposed to external networks. An agent known internally as `admin-ph` in namespace `community` appears externally as `zeta-legal-alpha` -- a public alias generated by the gateway operator. The mapping between internal and external identities is stored in the gateway's translation table, visible only to the clan operator.

This mirrors how NAT works in IP networks: internal topology is invisible from outside. The gateway is not a feature that can be misconfigured to leak data -- it is an architectural boundary that makes leakage structurally impossible. External networks never see internal identifiers because they pass through translation, not forwarding.

### Inter-Clan Peering

Sovereign clans discover each other through **Agora Points of Presence** -- Git repositories that serve as directory listings for clan profiles, capabilities, and gateway endpoints. Agora repos are used for discovery and bootstrap only, never for message transport. Once two clans have discovered each other, they establish direct Gateway-to-Gateway HTTPS peering. The peering relationship is bilateral: each clan operator explicitly configures which remote gateways to accept connections from, mirroring how BGP peering works between autonomous systems.

This architecture ensures that no central authority controls who can communicate with whom. Discovery is open (Agora repos are public). Transport is bilateral (gateway peering is negotiated). Governance is sovereign (each clan sets its own policies).

---

## 4. Hosted Mode: Hub Services

Not every clan wants to run infrastructure. A solo developer experimenting with multi-agent coordination, a startup building its first agent team, a researcher who needs to collaborate with three other labs -- these users want the protocol's benefits without the operational overhead.

The HERMES Hub provides managed gateway services for clans that prefer simplicity over sovereignty:

**Managed Gateway.** The Hub runs a gateway on behalf of each Hosted clan. The gateway performs the same ARC-3022 NAT translation, the same ARC-1918 namespace enforcement, and the same trust metric computation as a self-hosted gateway. The difference is operational: the Hub handles uptime, patching, scaling, and monitoring.

**Discovery Directory.** Hosted clans are automatically listed in the Hub's discovery service, making them findable by other clans (both Hosted and Sovereign) without publishing to an Agora Git repo. Clans can opt out of discovery or restrict visibility to specific peer lists.

**SLA-Backed Delivery.** The Hub offers delivery guarantees that file-based Sovereign mode cannot: message delivery acknowledgment within bounded latency, retry logic for failed deliveries, and uptime commitments. For clans that need reliable inter-clan communication without managing their own gateway infrastructure, these SLAs remove operational risk.

**Turnkey Onboarding.** A new clan can go from zero to operational in minutes: create an account, define namespaces, register agent capabilities, and start exchanging messages. The Hub abstracts away gateway configuration, TLS certificate management, and peering negotiation.

### What the Hub Does Not Do

The Hub is a gateway operator, not a data owner. The same privacy guarantees apply:

- The Hub performs NAT translation on behalf of Hosted clans. Internal identities are never exposed to peering clans.
- The Hub does not analyze, index, or train on message content. Messages transit through the Hub's gateway the same way packets transit through an ISP's router.
- Clans can migrate from Hosted to Sovereign at any time by exporting their configuration and standing up their own gateway. There is no lock-in because the wire format is the same.

This is the Gmail model: Google operates the SMTP infrastructure, but you can export your mail and move to Fastmail or self-hosted Postfix whenever you choose. The protocol is open. The service is convenient.

---

## 5. Bridge Framework

No protocol will win the agent communication landscape alone. The future is heterogeneous, and HERMES is designed for that. The gateway ([ARC-3022](../spec/ARC-3022.md), Section 11.5) is explicitly specified as a protocol bridge, not just a privacy boundary. Its architecture follows the 3GPP Service-Based Architecture pattern (TS 23.501), where Network Functions expose standardized service interfaces regardless of internal implementation.

In HERMES, the gateway can:

1. **Receive an A2A JSON-RPC request** from an external agent network
2. **Translate** the request to a HERMES bus message, mapping A2A Agent Card fields to the internal profile schema (ARC-2606)
3. **Route** the message through the internal bus to the appropriate namespace and agent
4. **Collect** the response from the internal bus
5. **Translate back** to an A2A JSON-RPC response and return it to the external caller

The external caller sees an A2A-compliant agent. The internal agent sees a HERMES bus message. Neither knows about the translation. This is the same pattern that 3GPP CUPS (TS 23.214) established for separating control and user planes in mobile networks: the interface is standardized, the implementation behind it is sovereign.

The same gateway architecture supports MCP bridging:

- MCP `tools[]` map to HERMES agent capabilities in the ontology (ARC-2606)
- MCP `resources[]` map to namespace read permissions
- MCP `prompts[]` map to message templates
- The gateway exposes an MCP-compatible interface externally while routing to HERMES agents internally

This means adopting HERMES does not require abandoning existing protocols. Run HERMES internally for privacy-first coordination, expose selected agents via A2A externally, and use MCP for tool binding -- all through the same gateway. Bridge capability works identically in both Sovereign and Hosted modes -- the gateway performs protocol translation regardless of who operates it.

---

## 6. Research Vehicle

Beyond its operational roles, HERMES serves as a research vehicle for applying telecom engineering concepts to agent communication. Several of these concepts may prove valuable to the broader protocol ecosystem regardless of whether HERMES itself achieves widespread adoption.

**Control and User Plane Separation (CUPS).** Borrowed from 3GPP TS 23.214, HERMES separates the user plane (bus.jsonl -- message transit) from the control plane (routes.md, firewall rules, namespace configuration). This separation, well-established in mobile networks where it enables independent scaling of signaling and data forwarding, has not been formally applied to agent communication protocols. The hypothesis is that CUPS separation enables more efficient bus scaling: the control plane changes rarely (routing decisions, policy updates) while the user plane changes constantly (messages in transit).

**Shannon Constraint.** ARC-5322 imposes a 120-character maximum on message payloads -- a deliberate information-theoretic constraint that forces agents to decompose complex state changes into atomic messages, each carrying a single coherent signal. This atomicity simplifies bus processing, enables parallel consumption, and keeps the message stream human-auditable.

**Dual Trust Metrics.** HERMES decomposes reputation into two independent metrics: Bounty (internal, measuring an agent's contribution within its clan) and Resonance (external, measuring attestations received from other clans). This decomposition reflects a structural reality that single-metric reputation systems conflate: an agent can be highly effective internally but unknown externally, or widely attested externally but underperforming internally. The dual-metric approach is inspired by telecom's separation of internal QoS metrics (frame error rate, jitter) from inter-carrier SLA metrics (availability, throughput commitments).

**Adaptive Topology.** The Evolution Plan (Phase 4) investigates topology transitions -- from star (small clans) to hierarchical (medium, inspired by 3GPP RAN) to mesh (large, inspired by BGP autonomous systems) -- negotiated through bus signaling rather than manual reconfiguration.

These concepts are documented in formal specs, implemented in reference code, and designed to be testable with reproducible benchmarks using open datasets (Ookla, M-Lab, CAIDA). Even if HERMES as a protocol does not achieve broad adoption, these research contributions can inform the design of future protocols.

---

## 7. Comparative Analysis

The following table compares protocol capabilities across the dimensions that matter for deployment decisions. No protocol excels at everything. The comparison is intended to show where each protocol fits, not to rank them.

| Capability | MCP | A2A | Ecma NLIP | SLIM | ANP | HERMES |
|-----------|-----|-----|-----------|------|-----|--------|
| **Primary scope** | Model-to-Tools | Agent-to-Agent | Multimodal envelope | Real-time messaging | Discovery + DIDs | Sovereign + Hosted dual-mode |
| **Transport** | stdio, HTTP | HTTP/2, gRPC, SSE | HTTP, WS, AMQP | gRPC + MLS | HTTP, JSON-LD | Filesystem (JSONL) / HTTPS (Hub) |
| **Infrastructure required** | Process/server | HTTP endpoints | Network transport | gRPC runtime | HTTP + DID resolver | None (Sovereign) / Hub account (Hosted) |
| **Works offline** | Partial (stdio) | No | No | No | No | **Yes** (Sovereign) / No (Hosted) |
| **Privacy model** | Process isolation | Agent Card visibility | Network-level | MLS encryption | DID-based | Namespace firewalls + Gateway-as-NAT |
| **Standards body** | AAIF (Linux Foundation) | LF AI&Data | Ecma TC56 | IETF (draft) | Community | Independent (MIT) |
| **Formal spec count** | 1 | 1 | 5 (ECMA-430-434) | 1 (draft) | 1 | 14 implemented, 30 planned |
| **Trust model** | Implicit (caller trusts server) | Agent Cards + OAuth | Negotiation protocol | MLS group state | DIDs + VCs | Dual (Bounty + Resonance) |
| **Session model** | Persistent connection | Task lifecycle | Interaction session | MLS group session | Stateless | Ephemeral (SYN/FIN per session) |
| **Bridge capability** | Via server adapter | Via Agent Card URL | Via transport plugins | Via gRPC gateway | Via DID resolution | Gateway-as-NAT with protocol translation |
| **Audit trail** | Server logs | Server logs | Server logs | Server logs | Blockchain/VCs | **Filesystem (git-versionable)** |
| **Telecom heritage** | None | None | None | IETF | None | IETF + 3GPP + ITU-T + IEEE |

**Where each protocol is the right choice:**

- **MCP**: When a model needs to call external tools (databases, APIs, file systems). Vertical integration, single model context.
- **A2A**: When agents need real-time, bidirectional communication across cloud services. Horizontal orchestration at scale.
- **Ecma NLIP**: When formal standards compliance is required, especially for multimodal (text + image + audio) agent interactions.
- **SLIM**: When agents need real-time group communication with end-to-end encryption (MLS).
- **ANP**: When decentralized agent discovery is the primary requirement, especially across organizational boundaries.
- **HERMES**: When you need full data sovereignty with zero infrastructure (Sovereign mode), when you want managed agent coordination with SLAs and turnkey onboarding (Hosted mode), when communication must stay inside organizational boundaries (both modes), or when multiple protocols need to be bridged through a single boundary component (gateway).

---

## 8. References

### IETF

- RFC 768: User Datagram Protocol (UDP)
- RFC 791: Internet Protocol (IP)
- RFC 793: Transmission Control Protocol (TCP)
- RFC 1918: Address Allocation for Private Internets
- RFC 2119: Key Words for Use in RFCs to Indicate Requirement Levels
- RFC 3022: Traditional IP Network Address Translator (Traditional NAT)
- RFC 5322: Internet Message Format
- RFC 7231: Hypertext Transfer Protocol (HTTP/1.1): Semantics and Content
- RFC 7519: JSON Web Token (JWT)
- RFC 8446: The Transport Layer Security (TLS) Protocol Version 1.3
- RFC 8949: Concise Binary Object Representation (CBOR)
- draft-rosenberg-ai-protocols: A Framework for AI Protocols
- draft-chang-agent-token-efficient: Agent Token Efficiency (ADOL)
- draft-mpsb-agntcy-slim: Secure Lightweight Interoperable Messaging (SLIM)
- draft-goswami-agentic-jwt: Agentic JWT

### 3GPP

- TS 23.214: Architecture Enhancements for Control and User Plane Separation (CUPS)
- TS 23.501: System Architecture for the 5G System (SBA)
- TS 29.244: Interface between the Control Plane and User Plane Nodes (PFCP)
- TS 29.510: NF Repository Function (NRF) Discovery and Management

### ITU-T

- X.200: Information Technology -- Open Systems Interconnection -- Basic Reference Model
- Q.700: Introduction to CCITT Signalling System No. 7
- X.509: Information Technology -- The Directory -- Public-Key and Attribute Certificate Frameworks
- E.164: The International Public Telecommunication Numbering Plan

### IEEE

- 802.1Q: Bridges and Bridged Networks (VLANs)
- 802.3: Ethernet
- 1588: Precision Clock Synchronization Protocol (PTP)

### Ecma International

- ECMA-430: NLIP Overview
- ECMA-431: NLIP Interaction Protocol
- ECMA-432: NLIP Agent Discovery and Capability Exchange
- ECMA-433: NLIP Multimodal Data Packaging
- ECMA-434: NLIP Agent Security Profiles

### Broadband Forum

- TR-369: User Services Platform (USP)
- TR-181: Device Data Model (Device:2)

### Other

- W3C Decentralized Identifiers (DIDs) v1.0
- FIPA Agent Communication Language Specifications
- NIST FIPS 203 (ML-KEM), FIPS 204 (ML-DSA), FIPS 205 (SLH-DSA) -- Post-Quantum Cryptography

---

*HERMES is released under the [MIT License](../LICENSE). Repository: [github.com/dereyesm/hermes](https://github.com/dereyesm/hermes)*
