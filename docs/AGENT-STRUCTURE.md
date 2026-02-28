# How I Structure AI Agents — A Practical Guide

> A real-world example of organizing AI agents using namespaces, firewalls, and HERMES for coordination.

## The Problem

When you have multiple AI agents working across different areas (engineering, sales, ops, finance), they need:
1. **Isolation** — agents in one area shouldn't access another area's tools or data
2. **Communication** — but they DO need to share state and coordinate
3. **Clarity** — each agent should have a clear role and boundaries

## The Solution: Namespaces + Skills + Protocol

### Layer 1: Namespaces (the walls)

Each business area is a **namespace** — an isolated workspace with its own tools, data, and agents.

```
company/
├── engineering/     # Code, PRs, CI/CD
│   ├── config.md    # What tools this namespace can use
│   ├── agents/      # Agent definitions
│   └── memory/      # Persistent context
├── operations/      # Project management, scheduling
├── sales/           # Proposals, clients, pricing
├── finance/         # Budgets, invoicing, reporting
└── controller/      # Read-only oversight (optional)
```

**Key rule:** Each namespace declares which tools (MCPs, APIs, services) it can access. An agent in `engineering` can use GitHub and Jira but NEVER the banking API. An agent in `finance` can use Sheets and invoicing but NEVER GitHub.

### Layer 2: Skills (the agents)

Each namespace has **skills** — specialized agents with a clear role:

```
engineering/
├── head: lead-dev          # Makes decisions for this namespace
├── skills/
│   ├── sprint-commander    # Sprint planning, ticket management
│   ├── code-reviewer       # PR reviews, quality checks
│   ├── devops              # CI/CD, deployments, infra
│   └── security-advisor    # Vulnerability scanning, audits
```

A skill definition (SKILL.md) contains:
- **Identity**: What it does, its expertise
- **Tools**: What it can access (inherited from namespace)
- **Rules**: Boundaries and behaviors
- **Triggers**: When to activate it

Example structure for a company with 4 areas:

| Namespace | Head Agent | Skills | Tools |
|-----------|-----------|--------|-------|
| engineering | lead-dev | sprint-commander, devops, reviewer, security | GitHub, Jira, CI |
| sales | sales-director | proposal-writer, pricing-analyst | CRM, Docs, Email |
| operations | pm | coordinator, process-optimizer | Calendar, Jira, Docs |
| finance | accountant | auditor, tax-advisor | Sheets, Banking, Invoicing |

### Layer 3: HERMES (the nervous system)

Skills in different namespaces communicate through **HERMES** — a message bus protocol.

```
engineering ──state──────► *           "sprint3_complete. 15_tickets_closed"
sales       ──request────► engineering "client_needs_api_estimate_by_friday"
engineering ──data_cross──► finance    "infra_costs_q4:hosting_2400usd"
controller  ──dispatch───► engineering "incident:api_p1_down. assign:devops"
```

**How it works:**
1. Each agent reads the bus at session start (**SYN**)
2. Filters for messages addressed to its namespace
3. Does its work
4. Writes state changes to the bus at session end (**FIN**)
5. ACKs messages it consumed

The bus is a single JSONL file — no servers, no databases, no infrastructure. Just a file that agents append to.

### Layer 4: Firewall (the rules)

A routing table defines what's allowed:

```markdown
## Permitted Data Crosses

| Source | Destination | Type | Example |
|--------|-------------|------|---------|
| engineering | finance | data_cross | Project costs |
| sales | finance | data_cross | Client invoices |
| finance | * | state | Monthly summaries |
```

Anything not in this table is **blocked by default**. An agent in `sales` can't send data to `engineering` unless explicitly permitted.

## Getting Started

### For your own company/team:

1. **Clone HERMES**: `git clone https://github.com/dereyesm/hermes`
2. **Run init**: `bash scripts/init_hermes.sh sales engineering ops finance`
3. **Configure namespaces**: Edit each `config.md` with your agents and tools
4. **Define routing**: Edit `routes.md` with permitted data flows
5. **Try the example**: `python examples/simple_agent.py engineering`
6. **Read the specs**: `spec/INDEX.md` for the full protocol

### For Claude Code specifically:

Each namespace maps to a directory with its own `.claude/skills/`:

```
~/company/
├── .claude/skills/        # Global skills (cross-namespace advisors)
│   ├── strategist/SKILL.md
│   └── coordinator/SKILL.md
├── engineering/.claude/skills/
│   ├── sprint-commander/SKILL.md
│   └── devops/SKILL.md
├── sales/.claude/skills/
│   └── proposal-writer/SKILL.md
└── .claude/sync/          # HERMES bus lives here
    ├── bus.jsonl
    └── routes.md
```

Skills are invoked with `/skill-name` from within their namespace directory.

## Key Principles

1. **Namespace = trust boundary** — tools and data don't cross without explicit permission
2. **Skills = single responsibility** — one agent, one job, clear boundaries
3. **HERMES = async coordination** — fire-and-forget messages, not synchronous calls
4. **File-based = zero infra** — no servers, no databases, works anywhere files work
5. **Human approves** — agents recommend, humans decide

## Architecture Diagram

```
                    ┌─────────────┐
                    │   Human     │
                    │  (approves) │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼────┐ ┌────▼─────┐ ┌────▼─────┐
        │  sales   │ │engineering│ │ finance  │
        │ ──────── │ │ ──────── │ │ ──────── │
        │ proposal │ │ sprint   │ │ auditor  │
        │ pricing  │ │ devops   │ │ tax      │
        │ [CRM]    │ │ [GitHub] │ │ [Sheets] │
        └────┬─────┘ └────┬─────┘ └────┬─────┘
             │            │            │
             └────────────┼────────────┘
                          │
                   ┌──────▼──────┐
                   │  HERMES Bus │
                   │ (bus.jsonl) │
                   └─────────────┘
```

## Further Reading

- [HERMES Quickstart](QUICKSTART.md) — 5-minute setup
- [Architecture Guide](ARCHITECTURE.md) — Full protocol stack
- [Specs Index](../spec/INDEX.md) — Formal standards (ARC/ATR/AES)
- [Example Agent](../examples/simple_agent.py) — Working Python template
