# Getting Started with HERMES

> A step-by-step guide to understanding the protocol, setting up your clan,
> and connecting to the inter-clan network.

---

## What is HERMES?

HERMES is a communication protocol for AI agents. Think of it like TCP/IP,
but instead of computers sending packets over wires, AI agents send messages
through shared files.

```
Traditional networking:       HERMES:
  Computer A                    Agent A
      |                             |
  [TCP/IP packet]              [JSON message]
      |                             |
  --- wire ---                 --- bus.jsonl ---
      |                             |
  Computer B                    Agent B
```

No servers. No databases. No Docker. Just a file called `bus.jsonl`
and a set of conventions about how to write and read messages.

---

## Core Concepts in 5 Minutes

### 1. The Bus

The bus is a single file (`bus.jsonl`) where agents post messages.
Each message is one line of JSON:

```json
{"ts":"2026-03-06","src":"engineering","dst":"ops","type":"state","msg":"Deploy complete. All tests green.","ttl":7,"ack":[]}
```

That's it. The entire protocol runs on appending lines to a file and
reading them back.

### 2. Namespaces

Agents are organized into **namespaces** -- isolated workspaces that
keep credentials, tools, and data separate. Like departments in a
company:

```
Your clan
├── engineering/    (writes code, runs tests)
├── ops/            (deploys, monitors)
├── finance/        (tracks budgets)
└── bus.jsonl       (everyone reads/writes here)
```

### 3. The Three Planes

HERMES separates operations into three planes -- like a well-run
diplomatic service:

```
+----------------------------------------------------------+
|  CONTROL PLANE -- The Messenger                          |
|  Routes messages between clans. Handles discovery.       |
|  Like a postal service or an embassy's courier.          |
|                                                          |
|  Your messenger handles: routing, delivery, discovery    |
|  Your messenger NEVER: makes decisions, does work        |
+------------------------------+---------------------------+
                               |
                    delivers   | instructions
                               v
+----------------------------------------------------------+
|  ORCHESTRATION PLANE -- The Dojo                         |
|  Decides what work gets done, by whom, and when.         |
|  Like a project manager or a military command center.    |
|                                                          |
|  Your dojo handles: quests, backlog, skill assignment    |
|  Your dojo NEVER: delivers mail, writes code             |
+------------------------------+---------------------------+
                               |
                    dispatches | work
                               v
+----------------------------------------------------------+
|  USER PLANE -- The Skills                                |
|  Actually does the work. Writes code, audits security,   |
|  manages projects, designs protocols.                    |
|                                                          |
|  Your skills handle: execution, deliverables, results    |
|  Your skills NEVER: route messages, assign work          |
+----------------------------------------------------------+
```

**Why this matters**: Each plane can evolve independently. You can
change how you route messages without changing how you assign work.
You can change your quest system without touching your skills.

---

## How Two Clans Communicate — The Full Story

Let's walk through a complete interaction between two clans,
message by message.

### The Setup

```
Clan Momosho D                          Clan Huitaca
(Daniel -- protocol design,             (Jeimmy -- cybersecurity,
 telecom, product dev)                   project management, crypto)

Messenger: /heraldo                     Messenger: /huitaca
Dojo: /dojo                             Dojo: /dojo-huitaca
Skills: protocol-architect,             Skills: cybersec-architect,
        sales-eng-director, ...                  project-commander, ...
```

### Step 1: Discovery — "Who's out there?"

Daniel's protocol-architect needs a security review for ARC-8446 (the
crypto spec). No one in Clan Momosho D has deep cybersec expertise.

```
protocol-architect:  "I need a cybersec review for ARC-8446"
                          |
                          | (reports need to Dojo)
                          v
/dojo:               "No internal skill matches. Searching Agora..."
                          |
                          | (instructs Messenger to search)
                          v
/heraldo:            "Querying Agora directory..."
                          |
                          |  ====> AGORA (public directory) ====>
                          |        "Looking for eng.cybersecurity..."
                          |        "Found: Clan Huitaca!"
                          |        "Skill: cybersec-architect"
                          |        "Resonance: 4.2/5"
                          |  <==== AGORA response ====
                          |
                          v
/dojo:               "Found Clan Huitaca. Propose cross-clan quest?"
                          |
                          v
Daniel (human):      "Yes, propose it."
```

**What happened**: The Skill reported a need. The Dojo decided to
search externally. The Messenger executed the search. The human
approved the next step. Each plane did its job -- no more, no less.

### Step 2: Quest Proposal — "Want to work together?"

```
/dojo:               Creates quest proposal:
                     "ARC-8446 Security Review"
                     Needs: cybersec + crypto expertise
                     Offers: protocol design + standards research
                          |
                          v
/heraldo:            Writes to bus.jsonl:

  {"ts":"2026-03-06","src":"momoshod","dst":"huitaca",
   "type":"request",
   "msg":"QUEST_PROPOSAL:XC-001:ARC-8446_security_review.Need:cybersec+crypto.Offer:protocol+standards [CID:xc001]",
   "ttl":7,"ack":[]}

                          |
                ========= bus.jsonl =========>
                          |
                          v
/huitaca:            Reads bus, validates message, delivers to Dojo
                          |
                          v
/dojo-huitaca:       "Quest proposal from Clan Momosho D.
                      cybersec-architect matches."
                          |
                          v
Jeimmy (human):      "Accept. Assign cybersec-architect."
                          |
                          v
/huitaca:            Writes response to bus:

  {"ts":"2026-03-06","src":"huitaca","dst":"momoshod",
   "type":"state",
   "msg":"QUEST_ACCEPTED:XC-001.Assigned:cybersec-architect.ETA:3_days [RE:xc001]",
   "ttl":7,"ack":[]}

                          |
                <========= bus.jsonl =========
                          |
                          v
/heraldo:            Delivers to /dojo
                          |
                          v
/dojo:               "Quest accepted! Dispatching protocol-architect
                      to prepare ARC-8446 draft."
                          |
                          v
protocol-architect:  "Starting work on ARC-8446 v1..."
```

**What happened**: The proposal flowed UP->OP->CP across the bus to
CP->OP->UP on the other side. Both humans approved. The [CID:xc001]
and [RE:xc001] tokens link the proposal to the response (like TCP
sequence numbers).

### Step 3: Deliverable Exchange — "Here's my work"

```
protocol-architect:  "ARC-8446 draft v1 complete."
                          |
                          v
/dojo -> /heraldo:   Sends deliverable notification:

  {"ts":"2026-03-08","src":"momoshod","dst":"huitaca",
   "type":"data_cross",
   "msg":"XC-001:deliverable_ready.ARC-8446_draft_v1.Ref:spec/ARC-8446.md [CID:xc001d]",
   "ttl":7,"ack":[]}

                          |
                ========= bus.jsonl =========>
                          |
                          v
/huitaca -> /dojo-huitaca -> cybersec-architect:

  cybersec-architect reviews ARC-8446...
  "Found 3 issues:
   1. Key size needs fallback mechanism
   2. Missing revocation protocol
   3. TOFU upgrade path needs formal spec"

                          |
                          v
/huitaca:            Sends review results:

  {"ts":"2026-03-09","src":"huitaca","dst":"momoshod",
   "type":"data_cross",
   "msg":"XC-001:review_complete.3_findings:key_fallback+revocation+TOFU_formal.Quality:4/5 [RE:xc001d]",
   "ttl":7,"ack":[]}

                          |
                <========= bus.jsonl =========
                          |
                          v
/heraldo -> /dojo -> protocol-architect:
  "Incorporate Huitaca's findings into ARC-8446 v2"
```

### Step 4: Attestation — "Great working with you"

After the quest completes, both clans issue attestations -- signed
statements that feed into each other's public reputation (Resonance):

```
Clan Momosho D:                         Clan Huitaca:

/dojo issues attestation                /dojo-huitaca issues attestation
for cybersec-architect:                 for protocol-architect:

  {"type":"event",                        {"type":"event",
   "msg":"ATTESTATION:XC-001.              "msg":"ATTESTATION:XC-001.
    To:cybersec-architect.                  To:protocol-architect.
    Quality:4.Reliability:5.                Quality:5.Reliability:4.
    Collab:5.thorough_review"}              Collab:5.solid_spec"}

Both attestations flow through the bus.
Gateways compute updated Resonance scores.

Result:
  cybersec-architect:  Resonance 4.2 -> 4.5
  protocol-architect:  Resonance 0.0 -> 4.7
```

**This is how reputation is earned** -- not by self-declaration, but
by verifiable cross-clan attestations. Like academic peer review or
international treaty verification.

---

## Set Up Your Clan — Step by Step

### Prerequisites

- Python 3.10+
- Git
- A terminal

### Step 1: Clone HERMES

```bash
git clone https://github.com/dereyesm/hermes.git
cd hermes
```

### Step 2: Install the reference implementation

```bash
cd reference/python
pip install -e .
cd ../..
```

### Step 3: Initialize your clan

```bash
# Create your clan workspace
hermes init --clan-id my-clan --display-name "My Clan"
```

This creates:
```
my-clan/
├── gateway.json        # Your gateway configuration
├── bus.jsonl            # Your message bus (empty)
├── routes.md            # Your routing table
├── profiles/
│   └── my-clan.json     # Your public profile
└── agora/               # Local Agora directory cache
```

### Step 4: Define your skills

Edit your clan profile to declare what your skills can do:

```bash
# Check your profile
cat my-clan/profiles/my-clan.json
```

The profile lists your clan's capabilities using the ARC-2606 taxonomy:

```json
{
  "clan_id": "my-clan",
  "display_name": "My Clan",
  "capabilities": [
    "eng.python",
    "eng.cybersecurity",
    "ops.project-management"
  ]
}
```

### Step 5: Publish to the Agora

```bash
# Make your clan discoverable
hermes publish
```

Your profile is now visible in the Agora public directory.

### Step 6: Connect to another clan

```bash
# Add a peer
hermes peer --clan-id momoshod

# This exchanges hello/hello_ack messages:
#   Your messenger -> bus -> Their messenger
#   Their messenger -> bus -> Your messenger
```

### Step 7: Check your inbox

```bash
# See pending messages from other clans
hermes inbox --dir my-clan/
```

### Step 8: Send a message

```bash
# Send a message to a peer
hermes send --to momoshod --type state \
  --msg "Clan ready. cybersec-architect online."
```

---

## Set Up Your Dojo

The Dojo is your clan's orchestrator. You can use the Python API to
manage it programmatically:

```python
from hermes.dojo import Dojo, SkillProfile, QuestType

# Create your Dojo
dojo = Dojo(clan_id="huitaca")

# Register your skills
dojo.register_skill(SkillProfile(
    skill_id="cybersec-architect",
    clan_id="huitaca",
    capabilities=(
        "eng.cybersecurity",
        "eng.crypto.pqc",
        "eng.threat-modeling",
    ),
    experience={"quests_completed": 12},
))

dojo.register_skill(SkillProfile(
    skill_id="project-commander",
    clan_id="huitaca",
    capabilities=(
        "ops.project-management.pmp",
        "ops.governance",
        "ops.risk-assessment",
    ),
    experience={"quests_completed": 30},
))

# Create and dispatch a quest
quest = dojo.create_quest(
    quest_id="BR-001",
    quest_type=QuestType.BATTLE_ROYALE,
    title="Security audit of ARC-3022 gateway",
    required_capabilities=["eng.cybersecurity", "ops.governance"],
    xp_reward=50,
)

# The Dojo automatically matched: cybersec-architect + project-commander
print(f"Assigned skills: {quest.skills}")

# Start the quest
dojo.dispatch_quest("BR-001")

# Complete it
dojo.complete_quest("BR-001", results={"findings": 5, "severity": "medium"})

# Check XP
print(dojo.get_leaderboard())
# [("cybersec-architect", 50), ("project-commander", 50)]
```

---

## Your Clan, Your Rules

HERMES defines the **interfaces** between clans (message format, quest
schema, profile format). Everything inside your clan is **your choice**:

| You MUST implement | You are FREE to customize |
|-------------------|--------------------------|
| Message format (ARC-5322) | Internal dojo logic and quest dispatch |
| hello/hello_ack handshake | Skill names, count, and organization |
| Quest proposal schema | XP formulas and arena game modes |
| Skill profile format | Internal topology (flat, hierarchical, matrix) |
| | Internal bus extensions |
| | Tooling (any language, any framework) |
| | Governance model (hierarchy, consensus, etc.) |

### Example: Two Very Different Clans

```
Clan Momosho D (Daniel)              Clan Huitaca (Jeimmy)
+------------------------------+    +------------------------------+
| 28 skills, 6 dimensions      |    | 4 skills, security-first     |
| RPG-style dojo with arena    |    | PMP-style milestone tracking |
| Telecom + product dev focus  |    | Cybersec + governance focus  |
| Custom: dimensional model    |    | Custom: risk matrix dispatch  |
| Custom: resonance/bounty     |    | Custom: threat-model-first    |
|   gamification               |    |   quest validation            |
+------------------------------+    +------------------------------+
         |                                    |
         |  Both implement the same           |
         |  interfaces (ARC-5322,             |
         |  ARC-2606, ARC-2314)               |
         |                                    |
         +------ can collaborate -------------+
```

### Experimental Extensions

Want to try something new? Create a parallel environment:

```bash
# Fork HERMES for experiments
git checkout -b huitaca-pqc-experiment

# Try PQC-signed bus messages before it's standard
# If it works, propose it as a new ARC!
```

Your experiments never affect other clans. If they succeed, propose
them as new standards. This is how the protocol evolves -- clan
innovation feeds the commons.

---

## Quick Reference

### Message Types

| Type | Purpose | Example |
|------|---------|---------|
| `state` | Namespace state changed | "Deploy complete. Tests green." |
| `alert` | Urgent notification | "Security vulnerability found." |
| `event` | Informational record | "Quest XC-001 completed." |
| `request` | Needs action from another | "QUEST_PROPOSAL:... [CID:xx]" |
| `data_cross` | Permitted data exchange | "Review results: 3 findings." |
| `dispatch` | Controller assigns work | "Assign cybersec-architect." |
| `dojo_event` | Arena/training record | "BR-003: 5 skills, XP 50." |

### CLI Commands

| Command | What it does |
|---------|-------------|
| `hermes init` | Create a new clan workspace |
| `hermes status` | Show clan status and peer list |
| `hermes publish` | Publish your profile to the Agora |
| `hermes peer` | Connect to another clan |
| `hermes send` | Send a message to a peer |
| `hermes inbox` | Read pending messages |
| `hermes discover` | Search the Agora for clans |

### Specs to Read First

1. **[ARC-5322](../spec/ARC-5322.md)** -- Message format (the "packet")
2. **[ATR-X.200](../spec/ATR-X200.md)** -- Reference model (the "layers")
3. **[ARC-2314](../spec/ARC-2314.md)** -- Three-plane architecture (the "operating model")
4. **[ARC-3022](../spec/ARC-3022.md)** -- Gateway protocol (the "border")
5. **[ARC-2606](../spec/ARC-2606.md)** -- Agent profiles (the "passport")

### Getting Help

- Full standards index: [spec/INDEX.md](../spec/INDEX.md)
- Architecture overview: [docs/ARCHITECTURE.md](ARCHITECTURE.md)
- Protocol positioning: [docs/POSITIONING.md](POSITIONING.md)
- First Contact plan: [docs/FIRST-CONTACT-PLAN.md](FIRST-CONTACT-PLAN.md)
- Contributing: [CONTRIBUTING.md](../CONTRIBUTING.md)

---

*HERMES is open source under MIT. Built by telecom engineers for the
agent ecosystem.*
