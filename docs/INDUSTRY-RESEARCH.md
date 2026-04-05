# Industry Research — Agentic Organizations

> Curated research on industry frameworks that validate and inform Amaru protocol design.
> This document complements [RESEARCH-AGENDA.md](RESEARCH-AGENDA.md) (technical research lines)
> and [USE-CASES-PRESENTATION.md](USE-CASES-PRESENTATION.md) (market positioning).

---

## 1. McKinsey: "The Agentic Organization" (2026)

**Title**: The Agentic Organization: Contours of the Next Paradigm for the AI Era
**Publisher**: McKinsey & Company — People & Organizational Performance
**Date**: 2026
**URL**: https://www.mckinsey.com/capabilities/people-and-organizational-performance/our-insights/the-agentic-organization-contours-of-the-next-paradigm-for-the-ai-era

**Core thesis**: The true competitive advantage of AI comes not from deploying agents in isolation, but from redesigning the enterprise as an "agentic organization" where humans and AI agents work together — redefining roles, skills, governance, and core practices across every organizational pillar.

### 1.1 Framework: 5 Pillars x 3 Themes = 15 Transformations

| | Business Model | Operating Model | Governance | Workforce & Culture | Technology & Data |
|---|---|---|---|---|---|
| **Theme 1** | Channel Disruption — AI channels enable hyperpersonalization | From Org Chart to Work Chart — agentic-first workflows move humans "above the loop" | Real-Time Decision-Making — agents drive faster budgeting, planning, and performance | Hybrid Talent System — functional boundaries blur; "hire to retire" is redefined | Distributed Ownership — AI mesh allows controlled democratization of IT systems and data |
| **Theme 2** | Cost Curve Compression — AI-first workflows drive marginal costs toward cost of compute | Reduced Org Friction — outcome-aligned agentic teams become organizational building blocks | Agentic Governance — agents control other agents with embedded guardrails | New Profiles, New Skills — orchestrators, AI coaches, human-in-the-loop designers emerge | Simplified Integration — agent-to-agent protocols ease integrations among agents, systems, and devices |
| **Theme 3** | New Sources of Differentiation — proprietary data becomes a key differentiable factor | Flat and Fluid Networks — dynamic, highly empowered teams steer to value | Human Oversight Remains — the sweet spot between accountability and speed matters | Culture Matters Even More — leaders set context for scaling, build trust, and guide ethically | Dynamic Sourcing — flexibility in decisions to buy or build avoids lock-in and protects intellectual property |

### 1.2 Detailed Analysis by Pillar

#### Business Model

- **AI-native channels** replace traditional customer touchpoints. Agents act as personal concierges activating end-to-end business flows (example: real-estate agent + mortgage agent triggered by a single customer intent).
- **Cost curve compression**: AI-first process redesign drives marginal costs toward cost of compute, not cost of labor.
- **Proprietary data moat**: First-party data becomes the defensible competitive advantage that agents consume and refine.

#### Operating Model

- **AI-first workflows by domain**: Work reimagined domain-by-domain starting from desired outcomes. "Small, outcome-focused agentic teams" — 2-5 humans supervising "agent factories" of 50-100 specialized agents executing end-to-end processes.
- **Cross-functional autonomous teams**: Shift from functional silos to flat, fluid, outcome-aligned networks. The new unit of value = "human + agent team" blended.
- **Humans move "above the loop"**: From executing tasks to orchestrating outcomes, supervising flows, defining goals, managing trade-offs.

#### Governance

- **Real-time, data-driven, embedded governance**: Traditional periodic budgeting/planning cycles are too slow. "Agentic budgeting" — proposal agents, scenario agents, reporting agents operating in real-time.
- **Control agents embedded in workflows (DevSecOps for agents)**: Critic agents challenge outputs, guardrail agents enforce policy, compliance agents monitor regulation. Every action logged and explainable.
- **Agent autonomy levels and decision boundaries**: Formal governance frameworks establishing autonomy levels, decision boundaries, behavior monitoring, audit mechanisms. End-user accountability: person/team deploying agents owns outputs.

#### Workforce, People & Culture

- **New profiles**: Prompt engineers, agent orchestrators, human-in-the-loop designers, hybrid managers, AI coaches, AI ethics officers, AI QA leads. McKinsey estimates 75% of current jobs will require redesign by 2030.
- **Culture shift**: From expertise-culture (deep specialist) to learning-culture (continuous experimentation, adaptation). Cohesion + purpose = organizational glue.
- **Leadership capabilities**: Stronger tech capabilities, systems thinking, ethical decision-making. CEO strategies: end experimentation, redesign governance (strategic AI council), organizational restructuring.

#### Technology & Data

- **Agentic AI Mesh**: Composable, distributed, vendor-agnostic architecture. Design principles: composability, distributed intelligence, reuse & discoverability, unified orchestration, secure multi-agent collaboration.
- **Agent-to-Agent Protocols**: Open standards preferred over proprietary. MCP (Anthropic) and A2A (Google) cited as redefining agent-system interactions. MCP Gateway as key requirement. Move "above underlying system complexity."
- **Data democratization**: Standardized data pipelines, access controls, quality standards for agent consumption. Privacy, compliance, audit trails embedded.

### 1.3 Key Quotes

> "AI is bringing the largest organizational paradigm shift since the industrial and digital revolutions, uniting humans and AI agents — both virtual and physical — to work side by side at scale at near-zero marginal cost."

> "Agent-to-agent protocols will make integration across systems, machines, and humans easier and cheaper. By moving to agent-to-agent dialogue above underlying system complexity, organizations can integrate legacy systems, cloud platforms, and machines like drones into cohesive workflows more quickly and at lower cost."

> "Just as DevSecOps embedded automated checks into digital delivery, agentic organizations will embed control agents into workflows, with critic agents challenging outputs, guardrail agents enforcing policy, and compliance agents monitoring regulation."

> "Governance cannot remain a periodic, paper-heavy exercise. As agents operate continuously, governance must become real time, data driven, and embedded — with humans holding final accountability."

### 1.4 Three Workflow Archetypes (Accountability by Design)

| Archetype | Human Role | Agent Autonomy | Accountability |
|-----------|-----------|----------------|----------------|
| **Human-Led** | Active execution + oversight | Assistive | End-user owns outputs + oversight governance |
| **Agent-Led** | Supervision by exception | High, within boundaries | Combined accountability, human approval gates |
| **Fully Agentic** | Minimal intervention | Maximum (if control agents validate) | Embedded control agents + audit trails |

---

## 2. HERMES Alignment Map

How Amaru protocol components map to McKinsey's 15 transformation themes:

| McKinsey Theme | HERMES Component | Spec | Status |
|---|---|---|---|
| **Simplified Integration** — agent-to-agent protocols | ARC-5322 wire format + ARC-7231 A2A/MCP bridge | ARC-5322, ARC-7231 | IMPLEMENTED |
| **Distributed Ownership** — AI mesh architecture | ARC-3022 gateway (NAT/filter) + multi-clan topology | ARC-3022 | IMPLEMENTED |
| **Agentic Governance** — control agents with guardrails | ARC-2314 CUPS triple-plane (Control/Ops/User) | ARC-2314 | IMPLEMENTED |
| **Real-Time Decision-Making** — embedded governance | bus.jsonl with TTL + ack tracking + HERMES SYN/FIN lifecycle | ARC-5322, ARC-0793 | IMPLEMENTED |
| **Human Oversight Remains** — accountability + speed | Approval gates, Consejo Tripartito pattern, human-in-the-loop | ARC-1918 (Firewall) | OPERATIONAL |
| **Dynamic Sourcing** — avoid lock-in | Sovereign mode (zero infrastructure) + Hosted mode (optional Hub) | ARC-0001 | IMPLEMENTED |
| **Agentic AI Mesh** — composable, distributed | Multi-clan architecture (ARC-3022 sections 15-16) + relay bilateral | ARC-3022 | IMPLEMENTED |
| **Secure Multi-Agent Collaboration** | ARC-8446 Ed25519 + X25519 + AES-256-GCM + HKDF | ARC-8446 | IMPLEMENTED |
| **New Profiles, New Skills** — orchestrators emerge | Dojo skill dispatch + quest system + Arena training | ARC-2314 (CUPS) | OPERATIONAL |
| **Flat and Fluid Networks** | Skills travel across dimensions at Gym Leader+ rank | ARC-2606 (Profile) | IMPLEMENTED |

### What McKinsey Validates

1. **File-based bus is governance by design**: Every message is a JSON line — auditable, grep-searchable, git-versionable. This IS the "every action logged and explained in real time" that McKinsey prescribes.
2. **CUPS architecture = control-plane separation**: McKinsey's "control agents embedded in workflows" maps directly to ARC-2314's triple-plane model where Messengers (CP), Dojos (OP), and Skills (UP) are separated.
3. **Gateway-as-NAT = organizational boundaries**: ARC-3022's NAT pattern enforces the "respect organizational boundaries" principle that McKinsey frames as essential for trust.
4. **Sovereign + Hosted dual-mode = dynamic sourcing**: The ability to run without infrastructure (Sovereign) or with managed services (Hosted) is exactly the "flexibility in build vs buy" that avoids lock-in.

### What Suggests New Specs/Features

| McKinsey Gap | Potential HERMES Response | Priority |
|---|---|---|
| **Agentic budgeting** (scenario agents, proposal agents) | ARC extension: economic message types for resource allocation | Low (post-v1.0) |
| **Agent autonomy levels** (formal classification) | ARC extension: autonomy_level field in ARC-2606 profiles | Medium |
| **Compliance agent pattern** | AES standard: compliance checker as gateway plugin | Medium |
| **Cross-functional team composition** | ARC-2606: team formation protocol using capability ontology | Low (L5b) |

---

## 3. Related McKinsey Research (2025-2026)

| # | Title | Focus | URL |
|---|---|---|---|
| 1 | "Accountability by Design in the Agentic Organization" | Governance structures, workflow archetypes, accountability lines | mckinsey.com/.../accountability-by-design-in-the-agentic-organization |
| 2 | "Six Shifts to Build the Agentic Organization of the Future" | 6 foundational shifts: reimagine work, rethink leadership, redesign roles | mckinsey.com/.../six-shifts-to-build-the-agentic-organization-of-the-future |
| 3 | "The Change Agent: CEO Strategies for the Agentic Age" | CEO playbook: end experimentation, redesign governance, restructure org | mckinsey.com/.../the-change-agent-goals-decisions-and-implications-for-ceos-in-the-agentic-age |
| 4 | "Seizing the Agentic AI Advantage" | Business impact metrics, scalable delivery patterns, ROI framework | mckinsey.com/.../seizing-the-agentic-ai-advantage |
| 5 | "Agentic AI Mesh — Enabling Agents at Scale" | Mesh architecture design, integration patterns, operational deployment | medium.com/quantumblack/how-we-enabled-agents-at-scale-in-the-enterprise-with-the-agentic-ai-mesh |
| 6 | "Rethink Management and Talent for Agentic AI" | New roles, upskilling, talent management frameworks | mckinsey.com/.../rethink-management-and-talent-for-agentic-ai |
| 7 | "The Big Rethink: An Agenda for Thriving in the Agentic Age" | Strategic agenda, competitive positioning, paradigm shift framing | mckinsey.com/.../the-big-rethink-an-agenda-for-thriving-in-the-agentic-age |
| 8 | "Building and Managing an Agentic AI Workforce" | Workforce transformation, skill redefinition, organizational culture | mckinsey.com/.../the-future-of-work-is-agentic |
| 9 | "Trust in the Age of Agents" | Risk governance, trust mechanisms, autonomous system oversight | mckinsey.com/.../trust-in-the-age-of-agents |
| 10 | "Unlocking AI and Agentic for Your Organization" | Implementation roadmap, service offerings | mckinsey.com/.../agentic-organization |

---

## 4. Research Agenda Connections

| Research Line | McKinsey Theme Connection |
|---|---|
| **L1**: Post-Quantum Cryptographic Integrity | Secure Multi-Agent Collaboration — crypto as trust foundation |
| **L2**: Agent Communication Language | Simplified Integration — semantic interoperability between agents |
| **L3**: Channel Efficiency | Cost Curve Compression — optimize transport for marginal cost reduction |
| **L4**: Topology & Adaptive Networks | Distributed Ownership + Flat and Fluid Networks |
| **L5**: Ecosystem & Governance (Agora) | Agentic Governance + Human Oversight + New Profiles |

---

## Bibliography

McKinsey & Company. "The Agentic Organization: Contours of the Next Paradigm for the AI Era." People & Organizational Performance, 2026.

McKinsey & Company. "Accountability by Design in the Agentic Organization." The Organization Blog, 2026.

McKinsey & Company. "Six Shifts to Build the Agentic Organization of the Future." The Organization Blog, 2026.

McKinsey & Company. "The Change Agent: Goals, Decisions, and Implications for CEOs in the Agentic Age." QuantumBlack, 2026.

McKinsey & Company. "Seizing the Agentic AI Advantage." QuantumBlack, 2025.

McKinsey & Company. "How We Enabled Agents at Scale in the Enterprise with the Agentic AI Mesh." QuantumBlack (Medium), 2025.

McKinsey & Company. "Rethink Management and Talent for Agentic AI." The Organization Blog, 2025.

McKinsey & Company. "The Big Rethink: An Agenda for Thriving in the Agentic Age." QuantumBlack, 2025.

McKinsey & Company. "Trust in the Age of Agents." Risk & Resilience, 2025.

---

*Last updated: 2026-03-11 | Maintained by Protocol Architect*
