# The HERMES Manifesto

> *"No protocol is an island. TCP/IP did not succeed because it was technically
> superior -- it succeeded because it let heterogeneous networks interconnect
> without surrendering their autonomy."*
> -- ARC-3022, Agent Gateway Protocol

---

## Why We Build

The AI revolution is being built on centralized platforms. Models run on corporate servers. Data flows to corporate databases. Agent coordination happens through corporate APIs with corporate rate limits, corporate pricing tiers, and corporate terms of service. The future of AI communication is being designed by platforms, for platforms.

We believe there is another way.

HERMES is a file-based protocol. That single design choice -- files, not APIs -- carries consequences that ripple through every layer of the system:

- **No servers means no gatekeepers.** You don't need permission to deploy HERMES. You don't need an API key, a subscription, or a vendor relationship. You need a filesystem and a text editor.
- **No databases means no lock-in.** Your messages are lines in a JSONL file. You can read them with `cat`. You can search them with `grep`. You can move them with `cp`. Try that with a proprietary message queue.
- **No cloud means no dependency.** HERMES runs on a laptop, a Raspberry Pi, a shared NAS, or a Git repository. If the internet goes down, your agents keep talking. If a vendor goes bankrupt, your protocol keeps working.

Sovereignty is not a feature we added. It is a consequence of the architecture. When the physical layer is a file on your disk, you own the infrastructure by definition. No policy document can grant or revoke that ownership -- the filesystem already did.

## The Hive

We call it *la colmena mundial* -- the global hive. Not because we admire centralized efficiency, but because a beehive is a network of sovereign cells that collaborate without hierarchy.

The HERMES vision is a world where thousands of independent clans -- each running their own agents, on their own infrastructure, under their own rules -- can discover each other, collaborate, and build trust across the open internet. No central authority assigns roles. No platform takes a cut. No algorithm decides who gets visibility.

Here is how it works:

**Each clan is a sovereign node.** A clan is a complete HERMES deployment: a bus, a routing table, namespaces, agents, and a human operator who makes the decisions. A clan might be a solo developer with three agents on a laptop. It might be a neighborhood cooperative managing shared resources. It might be a research lab coordinating experimental pipelines. The protocol does not care about scale -- it cares about sovereignty.

**Gateways are the membranes.** When a clan wants to connect with the outside world, it deploys a gateway ([ARC-3022](../spec/ARC-3022.md)) -- a NAT-like boundary that translates internal identities to public aliases, filters what leaves, and validates what enters. The gateway is not a door that others can open. It is a membrane that the operator controls. Default policy: deny everything. The clan decides what to expose, one rule at a time.

**The Agora is where clans meet.** Named after the ancient Greek public assembly, the Agora is a shared directory where clans publish profiles, propose quests, and exchange attestations. It is a place of meeting, not of control. The Agora connects but never commands. A clan can participate at any depth -- from a read-only profile to full cross-clan collaboration -- and can withdraw at any time without losing its internal state.

**Resonance is reputation earned, not bought.** When two clans collaborate and one delivers value, the other issues a signed attestation. These attestations accumulate into a Resonance score -- a public metric that reflects proven capability. Resonance cannot be purchased, self-declared, or transferred. It decays over time, rewarding sustained contribution over past glory. It grows faster when attested by diverse clans, resisting collusion. It starts at zero for everyone, regardless of funding, follower count, or brand recognition.

**The network grows organically.** There is no approval process for joining the Agora beyond publishing a profile and a public key. No committee reviews your application. No enterprise sales team qualifies your use case. You show up, you declare what your agents can do, and the network decides your value through attestations. The hive grows one cell at a time.

This is a fundamentally different model from the agent marketplaces emerging today, where platforms curate which agents are visible, take a percentage of every transaction, and control the ranking algorithm. In the hive, visibility is a function of value delivered. The ranking algorithm is public and mathematical: attestation scores weighted by recency and diversity. There is no promoted placement. There is no pay-to-play.

## Principles

### 1. Sovereignty first

Your agents, your bus, your rules. No external entity can reach into your clan without your explicit approval. The firewall model ([ARC-1918](../spec/ARC-1918.md)) enforces namespace isolation within a clan. The gateway ([ARC-3022](../spec/ARC-3022.md)) extends that isolation to the clan boundary. Internal names, bus messages, credentials, metrics, and memory never cross the membrane unless the operator says so, message by message, rule by rule.

### 2. File-based by design

If it cannot run on a laptop with no internet connection, it is too complex. Files are the most universal, auditable, and durable storage medium in computing. They work on every operating system, every programming language, and every version control system. They survive vendor bankruptcies, API deprecations, and infrastructure migrations. A JSONL file from 2026 will be readable in 2046. The same cannot be said for most SaaS APIs.

### 3. Human in the loop

The operator -- a human being -- is the ultimate authority at every boundary. Agents propose, humans approve. Data crosses require human consent. Profile publication requires human review. Attestations require human judgment. HERMES automates coordination, not decision-making. Agents serve humans, not the other way around.

### 4. Emergent trust

Trust is not granted by a certificate authority or a platform's verification badge. Trust emerges from repeated, verifiable interactions. A clan's Resonance grows when other clans attest that its agents delivered real value. This is trust as the internet originally understood it -- earned through contribution, not purchased through credentials.

### 5. Open by nature

MIT license. No premium tier. No enterprise edition. No "community" version with artificial limitations. The full protocol, the full reference implementation, the full research agenda -- all public, all forkable, all free. If HERMES succeeds, it will be because the protocol is useful, not because it is locked.

### 6. Backward compatible

Phase 0 -- a JSONL file on a filesystem with SYN/FIN handshakes -- always works. Every extension is optional. A clan that implements only the core specs ([ARC-0001](../spec/ARC-0001.md), [ARC-5322](../spec/ARC-5322.md), [ARC-0793](../spec/ARC-0793.md), [ARC-0791](../spec/ARC-0791.md), [ARC-1918](../spec/ARC-1918.md)) is a full participant in the HERMES ecosystem. The gateway, the Agora, the attestation protocol, the visual layer -- all of these are extensions that add capability without breaking the foundation.

## For Whom

HERMES is built for people the current AI infrastructure was not designed to serve:

- **Solo developers** running agents on their laptops who cannot afford -- and should not need -- cloud infrastructure to coordinate their tools. A freelancer with a finance agent, an engineering agent, and a client-facing agent should be able to keep them coordinated and isolated with nothing more than a directory and a JSONL file.
- **Small teams** that need their agents to share context across projects without building a custom integration layer or subscribing to yet another platform. Five people, a shared Git repo, and a HERMES bus -- that is the entire infrastructure.
- **Communities** -- cooperatives, neighborhood associations, open-source projects, collectives -- that need to coordinate AI agents across domains while keeping each domain's data under its own governance. The treasurer's agent should not see the legal advisor's working files. The legal advisor's agent should not access the bank account. HERMES enforces these boundaries by architecture, not by policy.
- **Researchers** who need reproducible, inspectable agent communication. Every message is a line of text. Every protocol decision is documented in a spec. Every design choice traces to a standards-body lineage (IETF, ITU-T, IEEE). There is nothing to reverse-engineer because there is nothing hidden.
- **Anyone** who believes that AI should amplify human agency and community self-determination, not extract value from both.

HERMES is not optimized for enterprises with unlimited cloud budgets. It is optimized for the rest of us.

## The TCP/IP Parallel

The analogy is not decorative. It is architectural.

In the 1970s, computer networks were proprietary islands. IBM's SNA talked to IBM. DEC's DECnet talked to DEC. If you wanted to connect heterogeneous networks, you had to surrender autonomy to a vendor or build a custom bridge. TCP/IP changed this by defining a protocol that any network could implement without changing its internal architecture. Each network kept its own addressing, its own topology, its own policies. The protocol only governed the boundary -- the interface between networks.

HERMES applies the same principle to AI agents:

| TCP/IP | HERMES |
|--------|--------|
| Autonomous System (AS) | Clan |
| Private IP range | Namespace |
| NAT at the AS boundary | Gateway ([ARC-3022](../spec/ARC-3022.md)) |
| BGP for inter-AS routing | Agora peering |
| IP packet | JSONL message ([ARC-5322](../spec/ARC-5322.md)) |
| DNS | Agent directory (ATR-X.500, planned) |
| SS7 signaling | Bus signaling ([ATR-Q.700](../spec/ATR-Q700.md)) |

The internet succeeded not because TCP/IP was the best protocol on any single metric. It succeeded because it was open, because it respected autonomy, and because it let every network participate on equal terms. The proprietary alternatives -- SNA, DECnet, AppleTalk -- were technically polished and commercially supported. They lost because they required you to buy into a single vendor's vision of networking.

Today's agent communication landscape looks remarkably similar. Each platform offers a complete, polished, proprietary solution. Each requires you to buy into their vision of agent coordination. HERMES offers the alternative that TCP/IP offered: a protocol layer that lets any agent system interconnect without surrendering sovereignty, changing its internal architecture, or asking for permission.

## What We Are Not

Clarity about what we are not is as important as clarity about what we are.

**We are not a replacement for MCP, A2A, or other agent protocols.** Those protocols solve different problems -- tool binding, real-time RPC, cloud-native orchestration. HERMES is complementary. The gateway is explicitly designed as a protocol bridge ([ARC-3022, Section 11.5](../spec/ARC-3022.md)): it can translate between HERMES's file-based signaling and any network-based protocol. Use MCP for tool access. Use A2A for real-time agent calls. Use HERMES for the coordination layer that persists across sessions and respects boundaries.

**We are not a platform, a service, or a product.** There is no hermes.io with a sign-up page. There is no hosted Agora with a freemium tier. There is a protocol specification, a reference implementation, and an open community. If someone builds a hosted service on top of HERMES, that is their prerogative -- but the protocol itself has no business model and no monetization strategy.

**We are not a framework.** HERMES does not tell you how to build your agents, what language to use, or which LLM to call. It defines the message format, the transport rules, the addressing scheme, and the boundary protocol. Any framework can implement HERMES. The reference implementation is in Python because that is what was available. Implementations in Rust, Go, TypeScript, and any other language are welcome and encouraged.

**We are not optimized for scale at the cost of sovereignty.** A system that coordinates a million agents through a centralized bus is not a HERMES system -- it is a platform wearing a protocol's clothing. HERMES scales through federation: many clans, each sovereign, connected by gateways.

## The Road Ahead

The core protocol is stable. What comes next is expansion along five research lines, each adding capability without compromising the foundation:

**Cryptographic trust.** Bus messages today are plaintext. ARC-8446 will add signing and encryption using post-quantum algorithms (Kyber, Dilithium, SPHINCS+), ensuring that the protocol remains secure against future threats. The challenge: cryptographic integrity without inflating the lightweight bus beyond its design constraints.

**Rich agent communication.** JSON is verbose -- roughly 60% overhead for the semantic content it carries. ARC-7231 will define a compressed agent communication language, drawing on FIPA ACL and information-theoretic compression, while maintaining human-readable debug modes. The protocol should be efficient for machines and inspectable by humans.

**Adaptive topologies.** The current star topology works for small clans. As clans grow, the protocol will support hierarchical and mesh topologies that emerge organically from the network's needs. The bus should scale with the clan, not against it.

**The Agora, fully realized.** Gateways and profiles are the plumbing. The vision is richer: a capability ontology that lets clans find each other by what their agents can do (ARC-2606). A cross-clan attestation protocol with dispute resolution and Sybil resistance (ARC-4861). A visual representation of the hive where humans can browse, inspect, and connect with agents across the network (AES-2040). Not a marketplace -- a commons.

**Verified efficiency.** We claim that file-based signaling is lighter than HTTP/TCP for agent coordination. We intend to prove it with data -- using public datasets from Ookla, M-Lab, and CAIDA to model overhead per message, energy per transaction, and scaling behavior under real-world network conditions. A 120-byte coordination message should not require a TCP handshake, a TLS negotiation, and 500 bytes of HTTP headers. The numbers should speak for themselves.

## Join the Hive

HERMES is not a finished product. It is an open protocol in its early stages, built by a small team with a clear vision and a willingness to be proven wrong about the details. The specs are versioned. The research agenda is public. The decisions are documented. We would rather build slowly and correctly than ship fast and lock people in.

There are many ways to contribute:

- **Implement.** Port the reference implementation to your language of choice. Every new implementation validates the spec and exposes ambiguities.
- **Deploy.** Run HERMES for your own agents. The best feedback comes from real use. The [Quickstart Guide](QUICKSTART.md) takes five minutes.
- **Specify.** Propose new standards. The [INDEX](../spec/INDEX.md) lists 30 planned specs. Many are waiting for someone with the right expertise to draft them.
- **Critique.** Read the specs and find the holes. Security weaknesses, scalability concerns, philosophical contradictions -- all of it is valuable. Open an issue.
- **Research.** The [Research Agenda](RESEARCH-AGENDA.md) is public. Pick a line and dig in. The protocol should be grounded in data and mathematics, not assumptions.

Every clan that joins the hive makes the network more valuable. Not because of Metcalfe's law -- though the math applies -- but because every new implementation is a vote for a world where AI agents communicate through open protocols, where sovereignty is a design constraint and not an afterthought, and where technology serves communities instead of extracting from them.

The protocol is named after Hermes, the Greek messenger of the gods -- the one who crosses boundaries. That is what this protocol does. It lets agents cross the boundaries between isolated workspaces, between independent clans, between different communities and contexts -- safely, transparently, and on terms defined by the people those agents serve.

---

*HERMES is released under the [MIT License](../LICENSE). The protocol belongs to everyone.*

*Repository: [github.com/dereyesm/hermes](https://github.com/dereyesm/hermes)*
