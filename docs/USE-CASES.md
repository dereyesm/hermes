# HERMES Use Cases

Real-world scenarios where HERMES solves coordination problems for AI agents. Each use case describes the problem, the Amaru solution, and the message patterns involved.

---

## 1. Solo Operator, Multiple Domains

### Problem

A freelancer or indie developer manages multiple areas of their life with AI agents: engineering projects, personal finance, a side business, and community involvement. Each domain has its own tools and credentials. Without isolation, an agent working on finance could accidentally use the engineering team's GitHub, or personal data could leak into a client project.

### HERMES Solution

Each domain becomes a **namespace** with its own firewall rules:

```
freelancer/
├── engineering/     Tools: GitHub, CI/CD        Account: dev@work.com
├── finance/         Tools: Banking, Sheets      Account: me@personal.com
├── side-biz/        Tools: Stripe, CRM          Account: hello@mybiz.com
└── community/       Tools: Email, Calendar      Account: me@personal.com
```

The firewall ensures:
- Engineering agents never touch the banking API
- Finance data crosses to side-biz only as categorized expenses
- Community agents can't access engineering repos

### Message Patterns

```
engineering ──data_cross──► finance     "project_x_hosting_45usd@aws"
side-biz    ──data_cross──► finance     "stripe_revenue_mar_1200usd@stripe"
finance     ──state──────► *            "monthly_summary:income_3200_expenses_1800"
community   ──alert──────► *            "board_meeting_friday_3pm. agenda_attached"
```

### Why Not Just Separate Chat Windows?

Because agents lose context between sessions. HERMES persists the coordination state in the bus. When a finance agent starts a new session next week, it reads the bus and knows that engineering reported $45 in hosting costs — without anyone re-typing the information.

---

## 2. Small Team Coordination

### Problem

A startup of 5 people uses AI agents across engineering, sales, operations, and finance. Each team member has their own agent configuration. Without a shared protocol, agents duplicate work, miss updates, and step on each other's toes.

### HERMES Solution

One HERMES instance on a shared filesystem (Git repo, NAS, or cloud storage):

```
startup/
├── engineering/     Head: lead-dev       3 agents
├── sales/           Head: sales-dir      2 agents
├── operations/      Head: pm             2 agents
├── finance/         Head: accountant     1 agent
└── controller/      Head: coordinator    1 agent (read-only)
```

The controller agent reads the full bus and detects desyncs:
- Engineering finished a feature but sales doesn't know yet
- A client deadline is approaching but no one dispatched the work
- Finance hasn't categorized last month's expenses

### Message Patterns

```
controller  ──dispatch───► engineering  "client_demo_friday. prep_staging_env"
engineering ──state──────► *            "v2.1_deployed. staging_ready"
sales       ──event──────► *            "client_meeting_went_well. verbal_yes"
operations  ──alert──────► engineering  "client_wants_api_change_before_contract"
engineering ──data_cross──► finance     "new_server_costs_120usd_monthly@cloud"
```

---

## 3. Cross-Clan Collaboration (Agora)

### Problem

Two independent teams (Clan Alpha and Clan Beta) want to collaborate on a project. Alpha has a strong legal analysis agent; Beta needs legal review for a contract. They don't share a filesystem, they don't trust each other's internal systems, and they don't want to expose their private data.

### HERMES Solution

Both clans deploy a **Gateway** ([ARC-3022](../spec/ARC-3022.md)) and register on the **Agora**:

1. **Discovery**: Beta searches the Agora for agents with "contract-law" capability
2. **Profile check**: Beta finds Alpha's agent "lex-prime" (external alias) with Resonance 73
3. **Quest proposal**: Beta's gateway sends a quest proposal to Alpha's gateway
4. **Acceptance**: Alpha's operator reviews and approves
5. **Collaboration**: The agents work together through their gateways
6. **Attestation**: Both clans issue signed attestations certifying the value delivered

### Message Patterns

```
# On the Agora (inter-clan)
beta-gateway ──quest_proposal──► alpha-gateway  "contract_review_needed"
alpha-gateway ──quest_accepted──► beta-gateway  "lex-prime assigned"

# Inside Clan Alpha (internal bus)
gateway ──event──► legal-ns    "AGORA:quest_proposal from beta for lex-prime"
legal-ns ──state──► gateway    "quest_completed. deliverable_ready"

# After completion (attestations)
beta-gateway ──attestation──► alpha-gateway   "quality:5 reliability:5 collab:4"
alpha-gateway ──attestation──► beta-gateway   "quality:4 reliability:5 collab:5"
```

### Privacy Guarantees

- Beta never learns that "lex-prime" is actually `admin-legal` in the `legal` namespace
- Alpha never sees Beta's internal bus messages or agent configurations
- The attestation refers to "lex-prime" (external alias), not the internal agent

---

## 4. Community Governance

### Problem

A homeowner association or cooperative needs to manage finances, legal compliance, community events, and infrastructure decisions. Multiple stakeholders (board members, residents, service providers) need visibility into different aspects, but no one should see everything.

### HERMES Solution

```
community/
├── admin/           Head: admin-lead     Tools: Email, Docs
├── finance/         Head: treasurer      Tools: Accounting, Banking
├── legal/           Head: legal-advisor  Tools: Law databases
├── infrastructure/  Head: facilities-mgr Tools: Vendor portals
└── controller/      Head: board-view     Tools: NONE (read-only)
```

The controller (board view) sees the state of all namespaces but can't execute actions — perfect for oversight without interference.

### Message Patterns

```
admin       ──alert──────► *            "annual_assembly_28feb_3pm. 8_proposals"
finance     ──state──────► *            "monthly_fees_collected:92pct. 3_delinquent"
legal       ──alert──────► admin        "contract_with_vendor_expires_30days"
infra       ──data_cross──► finance     "elevator_maintenance_2400usd@vendor_invoice"
finance     ──state──────► *            "q1_budget:72pct_consumed. reserves_healthy"
controller  ──dispatch───► legal        "review_vendor_contract_renewal_options"
```

---

## 5. Personal Productivity System

### Problem

An individual uses AI agents to manage their work, creative projects, health tracking, and learning. They want agents that specialize in each area but can share relevant information (e.g., work deadlines affect creative project scheduling; health data informs work capacity).

### HERMES Solution

```
life/
├── work/            Tools: Jira, GitHub, Email     Account: work@company.com
├── creative/        Tools: Writing tools, Social   Account: me@personal.com
├── health/          Tools: Health API, Calendar    Account: me@personal.com
├── learning/        Tools: Notes, Research         Account: me@personal.com
└── controller/      The "life dashboard"
```

### Message Patterns

```
work       ──alert──────► *            "deadline_friday. 3_tickets_remaining"
creative   ──state──────► *            "article_draft_complete. editing_phase"
health     ──alert──────► work         "sleep_deficit_3days. recommend_light_schedule"
learning   ──event──────► *            "finished_course:distributed_systems"
work       ──data_cross──► health      "overtime_hours_this_week:12@timetracker"
controller ──dispatch───► creative     "window_open_saturday. schedule_writing_session"
```

---

## 6. Open-Source Project Coordination

### Problem

An open-source project has multiple workstreams: core development, documentation, community management, and release engineering. Contributors come and go. Knowledge is lost between sessions.

### HERMES Solution

The Amaru bus in the project's Git repo serves as persistent coordination memory:

```
project/
├── core-dev/        Head: maintainer     Agents: reviewer, security
├── docs/            Head: docs-lead      Agents: writer, translator
├── community/       Head: comm-manager   Agents: triage, onboarding
├── releases/        Head: release-eng    Agents: packager, tester
└── controller/      Automated CI agent
```

The bus is committed alongside code. Every contributor's agent reads the bus on `git pull` and knows the project state. No Slack history to search, no context to rebuild.

### Message Patterns

```
core-dev   ──state──────► *            "v3.0_feature_freeze. only_bugfixes_accepted"
community  ──dispatch───► docs         "new_contributor_needs_onboarding_guide_update"
releases   ──alert──────► core-dev     "release_candidate_fails_arm64_tests"
docs       ──event──────► *            "quickstart_guide_rewritten. pr_147"
controller ──alert──────► *            "ci_red_on_main. 3_tests_failing_since_2days"
```

---

## Patterns Summary

| Use Case | Namespaces | Key Pattern | Agora? |
|----------|-----------|-------------|--------|
| Solo multi-domain | 3-5 | Firewall isolation + data_cross for finances | No |
| Small team | 4-6 | Controller dispatch + state broadcasts | No |
| Cross-clan collab | 2+ clans | Gateway + quest + attestation | Yes |
| Community governance | 4-5 | Controller oversight + legal/finance separation | No |
| Personal productivity | 4-5 | Health/work data_cross + controller scheduling | No |
| Open-source project | 4-5 | Git-committed bus + CI controller | No |

## Adding Your Use Case

If you deploy HERMES in a new context, consider contributing your use case via PR. The community benefits from real-world patterns. See [CONTRIBUTING.md](../CONTRIBUTING.md).
