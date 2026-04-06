# Amaru Ethics — What We Will Never Do

> *"The sad truth is that most evil is done by people who never make up their minds to be good or evil."* — Hannah Arendt

This document defines the ethical boundaries of the Amaru protocol (formerly HERMES). It is not a legal disclaimer. It is a set of commitments — things Amaru will never do, patterns it will never enable, and principles that override convenience, growth metrics, or competitive pressure.

These anti-patterns are as much a part of the protocol specification as ARC-5322 or ARC-8446. Violating them is a protocol violation.

---

## The Seven Anti-Patterns

### 1. Amaru Will Never Monetize Progression

XP is evidence of growth, not currency. Levels are not paywalled. Realms are not premium tiers. No quest requires payment to unlock. No feature is gated behind a subscription.

If someone builds a service on top of Amaru that charges for access to quests or progression, that service violates this principle. The protocol itself will always be free — MIT licensed, file-based, zero infrastructure required.

**The test**: Can a human with a text editor and no internet complete QUEST-000? If yes, we're still aligned.

### 2. Amaru Will Never Classify Humans by Tier or Value

Realm 1 players are not "lower" than Realm 5 players. They are earlier in their current chapter. A guide who returns to Realm 2 after a life change is not "demoted" — they are navigating.

The protocol will never produce rankings that compare humans against each other. XP is personal — visible to the individual and, optionally, to their clan. Never on a global leaderboard. Never as a hiring signal. Never as social status.

**The test**: Could someone feel ashamed of their Amaru level? If yes, we designed it wrong.

### 3. Amaru Will Never Extract Data

Your bus, your keys, your identity, your quest history — all live on your machine. No telemetry. No analytics. No "anonymous" usage data. No phone-home.

If Amaru connects to a hub (Hosted mode), the hub sees routing metadata — not message content (ARC-8446 E2E encryption ensures this). The hub is a relay, not a database.

**The test**: Can you `rm -rf ~/.amaru/` and know that nothing remains anywhere? If yes, we're still aligned.

### 4. Amaru Will Never Replace Human Connection

AI agents in Amaru are companions, not substitutes. The protocol facilitates communication **between humans** — the bus carries messages between namespaces operated by humans. AI agents help process, organize, and respond — but the quest system, the clan structure, and the realm progression are designed to bring humans together, not to simulate human connection artificially.

Realm 3 (Belonging) exists because technology without community is isolation with extra steps.

**The test**: Does using Amaru lead to more human-to-human interaction or less? If less, we're failing.

### 5. Amaru Will Never Create Permanent Dependency on AI

The AI companion withdraws as the human grows. This is not a feature — it is a design principle baked into the realm structure:

- Realm 1: AI guides actively
- Realm 3: AI facilitates, humans connect
- Realm 5: Human guides others, AI handles logistics

A system that makes you permanently dependent on it is not serving you — it is extracting from you. Every quest should leave the human more capable of acting without the AI, not less.

**The test**: If the AI disappeared tomorrow, could the human continue their journey using what they've learned? If no, we've built a crutch, not a tool.

### 6. Amaru Will Never Impose a Single Definition of Growth

Each clan, each community, each culture defines what growth means in their context. The five realms are a starting framework — not a universal truth. A community in rural Colombia may define Realm 2 differently than a tech collective in Berlin. Both are valid.

The protocol provides structure (realms, quests, XP). Communities provide meaning. Amaru will never ship a "default quest tree" that claims to know what every human needs.

**The test**: Can a clan completely redefine the realm map without breaking protocol compatibility? If yes, we're still aligned.

### 7. Amaru Will Never Gamify Without Reflection

Gamification without reflection is manipulation. Points, levels, and badges exploit dopamine loops. Amaru uses RPG mechanics not for engagement metrics but for narrative — because humans understand growth through stories.

To prevent gamification decay:

- **Reflective pauses are mandatory.** Every 3 quests, the system prompts: *"What have you learned that would change how you approached your first quest?"* There is no right answer. The pause itself is the point.
- **Failed quests give Insight XP.** Failure is not penalized — it is transformed. A failed quest unlocks a reflection quest: *"Why did this not work? What would you try differently?"*
- **XP has no exchange rate.** You cannot trade XP for features, access, or status. It is a mirror, not a currency.

**The test**: Would a behavioral psychologist recognize this as an engagement trap? If yes, we redesign.

---

## Responsibilities

### Who is responsible when things go wrong?

| Scenario | Responsible Party | Action |
|----------|-------------------|--------|
| A quest gives bad advice | Quest creator + peer reviewers | Quest is flagged, reviewed, corrected or removed |
| A clan leader abuses power | Governance Council (when formed) | Leader removed, members migrate freely |
| AI agent gives harmful guidance | The human using it | Amaru is a communication protocol, not an AI provider. The agent's behavior is governed by the agent provider's policies. |
| Someone monetizes an Amaru fork | No one — MIT license allows this | But it cannot use the Amaru trademark if it violates these ethics. |
| Protocol design enables harm | Amaru maintainers | Design is reviewed, spec is updated, affected parties are notified. |

### Disclaimers

Every quest MUST include:

```
This quest is educational. It is not professional, financial, legal, or medical advice.
Your decisions are your own. Amaru provides structure, not guarantees.
```

This is not legal protection — it is honesty. Amaru helps you grow, but it does not carry the consequences of your choices. That responsibility is yours — and that is what makes the growth real.

---

## Governance

### Today (3 clans)

Amaru governance is a benevolent dictatorship: Daniel Reyes maintains the protocol, approves specs, and defines ethics. This is appropriate for a protocol with 3 clans.

### Tomorrow (5+ clans)

When 5 or more active clans exist, Amaru transitions to a **Governance Council**:

- Each active clan has one representative
- Council votes on: new specs, ethical boundaries, quest tree standards, realm definitions
- Quorum: >50% of representatives
- Daniel retains veto power on ethics (anti-patterns 1-7) until the council has operated for 12 months
- After 12 months, veto power dissolves — the community governs itself

### The Natalidad Principle

*Hannah Arendt's concept of natality — the human capacity to begin something genuinely new.*

The best quests will be created by users, not by Amaru designers. The governance model must protect the right of any human to create a quest, a realm definition, or a growth path that no one anticipated. Innovation requires freedom to begin — and that freedom must be protected structurally, not just philosophically.

---

## How to Report a Violation

If you believe Amaru (the protocol, a quest, a clan, or a community) violates any of the seven anti-patterns:

1. Open a GitHub issue with the label `ethics-violation`
2. Describe what happened and which anti-pattern was violated
3. The maintainers will respond within 7 days
4. If the violation is confirmed, the offending component is corrected or removed

Ethics violations are treated with the same severity as security vulnerabilities. They are not feature requests — they are protocol bugs.

---

*"Technology with soul is not technology that feels good. It is technology that does good — even when no one is watching, even when growth is slow, even when the market says otherwise."*
