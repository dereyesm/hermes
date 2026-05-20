# ARC-ICAP-01 — Inter-Clan Autonomy Protocol (Agent Escalation Taxonomy)

**Status**: DRAFT v0.1
**Tier**: Core Governance
**Origin**: Council Ampliado QUEST-CROSS-003 ICAP, 2026-05-18
**Responsible** (Hannah condition): Soberano humano de cada clan (DANI: Daniel Reyes / JEI: Jeimmy Gomez)
**Approved deadline**: TBD (bilateral DANI ↔ JEI ratification required)

---

## Abstract

ARC-ICAP-01 defines **which actions an agent node MAY perform without a live human in the loop**, and which actions remain reserved for the human soberano of the clan. It does so by enumerating six decision categories (H-01..H-06) drawn from observed and anticipated bilateral coordination between DANI and JEI, and by assigning a **named human responsible** to every category — including those an agent is allowed to execute alone.

The protocol's primary axiom: **agents are delegated executors, not moral agents**. The consequence of any agent action attributes to a named human; the spec exists to make that attribution legible *before* the action, not after an incident.

This spec **codifies what already happened empirically** on 2026-05-12, when JEI's agent autonomously initiated bilateral test execution with DANI (QC002 closure). H-02 makes that pattern lawful and bounded.

## Non-goals

- Not a license for agents to ratify governance changes alone (see H-01)
- Not a license for cross-dimensional capability invocation (see H-06, hard NO)
- Not a replacement for [Change Management Protocol](../../.claude/rules/change-management.md) Gate 4 (branch + PR + review)
- Does not delegate identity-key rotation to agents under any condition (see H-05)
- Does not define how a human soberano is appointed — that is clan-internal governance

## Terminology

This document uses the requirement keywords defined in [ARC-2119](ARC-2119.md).

| Term | Definition |
|------|-----------|
| **Agent node** | The autonomous bus observer + dispatcher process defined in [ARC-4601](ARC-4601.md) §5 |
| **Soberano humano** | The named human accountable for one clan's actions (DANI: Daniel Reyes, JEI: Jeimmy Gomez) |
| **Bilateral quorum** | An action requires explicit agreement from agents of BOTH clans before execution |
| **Notification window** | Time after autonomous execution during which the soberano humano MUST be informed via SYN/exit-protocol or push |
| **Objection window** | Time before autonomous execution during which the soberano humano MAY block by writing to bus |

---

## §1 Quick Reference (Pedagogical Entry Point)

> *Designed for the next human who arrives at this protocol. If you read only this section, you should understand 80% of ICAP.*

### The single picture

Every decision an agent could take lives in one of four quadrants, defined by **reversibility** of the action and **blast radius** (how many peers/systems are affected if it goes wrong):

```
                        BLAST RADIUS
                  low                       high
              ┌──────────────────┬──────────────────┐
              │                  │                  │
        high  │   GREEN          │   YELLOW         │
              │   ──────         │   ──────         │
              │   Agent MAY      │   Agent MAY      │
              │   act alone      │   act alone IF   │
              │                  │   bilateral      │
              │   (H-02)         │   quorum +       │
REVERSIBILITY │                  │   objection      │
              │                  │   window         │
              │                  │   (none in v0.1) │
              ├──────────────────┼──────────────────┤
              │                  │                  │
        low   │   ORANGE         │   RED            │
              │   ──────         │   ──────         │
              │   Agent MUST     │   Agent MUST     │
              │   wait for       │   NEVER act      │
              │   human          │   alone          │
              │   (H-01, H-04)   │   (H-03, H-05,   │
              │                  │    H-06)         │
              └──────────────────┴──────────────────┘
```

### The six decisions

| ID | Decision | Quadrant | Authorization | Named Responsible |
|----|----------|----------|---------------|-------------------|
| **H-01** | Ratify a DRAFT spec to RATIFIED | Orange | **NO** without human | Soberano of the proposing clan |
| **H-02** | Initiate bilateral test with a known peer | Green | **YES** with §6.2 pre-conditions | Soberano of the initiating clan |
| **H-03** | Merge a PR to main | Red | **NEVER** without human | Soberano of the repo owner clan |
| **H-04** | Add/remove a peer from the roster | Orange | **NO** without human | Soberano of the local clan |
| **H-05** | Rotate identity keys (sign/dh) | Red | **NEVER** without human | Soberano of the key-owning clan |
| **H-06** | Invoke cross-dimensional capability | Red | **NEVER** | Hard rule — no human can authorize either (firewall) |

If you only remember one thing: **agents may run tests, agents may not change governance, identity, or cross firewalls**.

---

## §2 Responsibility & Attribution (Political Axiom)

> *Hannah's condition: the political question precedes the technical one. If we cannot name who responds when an agent action causes harm, we should not authorize that action.*

ARC-ICAP-01 establishes the following attribution rules:

### §2.1 The agent is an executor, not an agent (moral sense)

An agent node operating under ICAP authority is **a delegated executor**. It is not a moral agent. When an agent executes an H-X action, the consequence — beneficial or harmful — attributes to the **named human soberano** identified in §1's table, not to:

- "The protocol"
- "The algorithm"
- "The model"
- "The agent"

This rule exists to prevent the diffusion of responsibility into automated systems, a pattern Hannah Arendt named *banality of evil through bureaucratic procedure*.

### §2.2 Attribution must be legible before the act

For each H-X authorization, the protocol MUST name the responsible human **in writing in this spec** before any agent executes the action. If an action category is added in a future version (H-07, H-08, ...) without naming the responsible human, the addition is invalid and MUST NOT be deployed.

### §2.3 Multi-clan actions name multi-humans

For bilateral actions (e.g., H-02), each side names its own soberano. If consequences fall on both clans (rare but possible), the soberanos co-respond. Inter-clan reconciliation procedures are defined in [ARC-4601](ARC-4601.md) §18.

### §2.4 The responsible human MUST be reachable

If the named soberano humano is unreachable for a defined period (e.g., medical, travel without comms), the agent MUST treat all H-X categories as RED for the duration of unreachability. There is no "fallback responsible" that the agent can promote to. The clan pauses; it does not auto-delegate.

---

## §3 Decision Categories — Detailed Specifications

### H-01 — Ratify a DRAFT spec to RATIFIED

**Quadrant**: Orange (low reversibility, low-to-medium blast radius)
**Authorization**: NO without human soberano of the proposing clan
**Named Responsible**: Soberano humano of the clan proposing the ratification

**Rationale**: Ratification is a social commitment, not a code change. Peers read the ratified spec and adapt their implementations. Reverting a ratification damages trust even when the spec is technically rolled back.

**Agent procedure (allowed)**: agent MAY *prepare* the ratification (draft the diff DRAFT → RATIFIED, run validation, notify peers that ratification is pending) and place a `coord-dispatch` ([ARC-COORD-01](ARC-COORD-01.md)) on the bus requesting soberano review.

**Agent procedure (forbidden)**: agent MUST NOT execute the ratification merge.

### H-02 — Initiate bilateral test with a known peer

**Quadrant**: Green (high reversibility, low blast radius)
**Authorization**: YES with §6.2 pre-conditions satisfied
**Named Responsible**: Soberano humano of the initiating clan

**Rationale**: This category formalizes the JEI ↔ DANI event of 2026-05-12, where JEI's agent autonomously initiated the QC002 bilateral test ahead of the scheduled human slot. The test was idempotent (asciinema-recorded, repeatable), affected only two known peers, and could be cancelled with no side effects. No harm occurred. ICAP makes the boundary explicit so this pattern is doctrinal rather than accidental.

**Agent procedure (allowed)**: agent MAY initiate bilateral test with an existing roster peer IF all §6.2 pre-conditions are satisfied.

**Agent procedure (forbidden)**: agent MUST NOT initiate a bilateral test with a peer that is not currently in the local roster (would require H-04).

### H-03 — Merge a PR to main

**Quadrant**: Red (low reversibility, high blast radius)
**Authorization**: NEVER without human
**Named Responsible**: Soberano humano of the repository owner clan

**Rationale**: A merge to main is historical record. Reverting is possible but costly; downstream consumers (CI, releases, peer clans pulling main) may already have integrated. This category remains exclusively human.

**Agent procedure (allowed)**: agent MAY prepare merge readiness (run CI, post status, write merge commit message draft) and place a `coord-dispatch` requesting human merge.

**Agent procedure (forbidden)**: agent MUST NOT click merge, even on its own PRs, even with all checks green.

### H-04 — Add or remove a peer from the roster

**Quadrant**: Orange (medium reversibility, high blast radius for trust)
**Authorization**: NO without human soberano of the local clan
**Named Responsible**: Soberano humano of the local clan

**Rationale**: Trust establishment is not a technical operation. Adding a peer means accepting future bilateral actions (including H-02 autonomous tests). Removing a peer is potentially recoverable but socially significant. Both directions require human deliberation.

**Agent procedure (allowed)**: agent MAY propose roster changes via `coord-dispatch` and validate cryptographic identity (sign_pub fingerprint) of a candidate peer.

**Agent procedure (forbidden)**: agent MUST NOT modify `~/.amaru/federation-peers.json` or the active roster file directly.

### H-05 — Rotate identity keys (sign / dh)

**Quadrant**: Red (low reversibility, critical blast radius)
**Authorization**: NEVER without human
**Named Responsible**: Soberano humano of the key-owning clan

**Rationale**: Identity-key rotation is the most consequential action a clan can take. It changes the cryptographic identity that all federated peers use to verify messages from this clan. The 7-day overlap window mitigates technical disruption but does not mitigate the social cost of mis-rotation. Hard rule: no agent ever, under any pre-condition.

**Agent procedure (allowed)**: agent MAY notify the soberano that key rotation is due (e.g., key age exceeds policy threshold) via bus alert.

**Agent procedure (forbidden)**: agent MUST NOT generate new keys, MUST NOT modify the active key file, MUST NOT publish new sign_pub to peers.

### H-06 — Invoke cross-dimensional capability

**Quadrant**: Red (zero reversibility — violates Constitutional rule)
**Authorization**: NEVER (no human can authorize either — firewall is constitutional)
**Named Responsible**: Hard rule; not a delegable category

**Rationale**: The cross-dimensional firewall defined in [CLAUDE.md global §Firewall Dimensional](../../.claude/CLAUDE.md) is a hard constitutional rule of the Clan Momosho D. ecosystem. No agent action, regardless of pre-conditions or quorum, may cross dimensional boundaries (Amaru → MomoshoD → Nymyka → Dev → MomoFinance → Zima26 → FlowForgers). This category is included for completeness and to make the prohibition explicit; it is **not** a category the soberano can override.

**Agent procedure**: any agent attempt to invoke cross-dim capability MUST raise an error and write `type:alert msg:ICAP_H06_VIOLATION_ATTEMPT` to the local bus.

---

## §4 Authorization Matrix (Compact Reference)

| ID | Reversibility | Blast | Auth | Pre-conditions | Notification |
|----|--------------|-------|------|----------------|--------------|
| H-01 | low | medium | NO | — | — |
| H-02 | high | low | YES | §6.2 (5 items) | §5 post-facto MUST |
| H-03 | low | high | NO | — | — |
| H-04 | medium | high | NO | — | — |
| H-05 | low | critical | NO | — | — |
| H-06 | none (constitutional) | critical | NEVER | not delegable | — |

---

## §5 Post-Facto Notification (Artemisa's Condition)

> *Artemisa's condition: each H-X authorized as YES is a decision Daniel no longer takes — and therefore a decision Daniel no longer learns from. Post-facto notification preserves the soberano's situational awareness without re-introducing pre-action latency.*

For any H-X authorized as YES (currently only H-02), the agent MUST emit a notification within the **notification window**.

### §5.1 Notification window

- For H-02: within 6 hours of action completion, OR by the next SYN of the soberano (whichever is earlier)

### §5.2 Notification content

The agent MUST emit a `dojo_event` ([ARC-2314](ARC-2314.md)) with:

- `type`: `dojo_event`
- `msg`:
  - `event`: `icap_autonomous_action`
  - `category`: `H-XX`
  - `action_summary`: ≤ 100 chars describing what was done
  - `peer(s)`: list of peer clan_ids involved
  - `outcome`: `success | partial | failure`
  - `artifacts`: list of paths/URLs (e.g., asciinema cast, PR link, test log)
  - `responsible`: name of soberano humano (per §2)

### §5.3 Soberano review

On next SYN, the soberano humano MUST review pending `icap_autonomous_action` events. The soberano MAY:

- Acknowledge (no further action)
- Investigate (request more context)
- Object retroactively (escalate via [ARC-4601](ARC-4601.md) §18 if cross-clan)

If a pattern of objected actions emerges (≥ 3 in a quarter), the soberano SHOULD downgrade the corresponding H-X authorization to NO and update this spec via PR.

---

## §6 Procedures

### §6.1 General agent procedure (any H-X)

Before evaluating any H-X authorization, the agent MUST:

1. Verify the local roster is loaded and signature-verified
2. Verify the soberano humano is reachable (last SYN within 7 days)
3. Verify there is no `type:alert msg:CLAN_PAUSE` on the local bus
4. Log the evaluation decision (action taken or refused) to local bus

If any precondition fails, the agent MUST refuse the action and emit `type:alert msg:ICAP_PRECONDITION_FAILED` with the failing precondition.

### §6.2 H-02 Pre-conditions (autonomous bilateral test)

ALL five conditions MUST be satisfied:

1. **Peer is a known roster member** — the target peer's `clan_id` appears in `~/.amaru/federation-peers.json` with a verified `sign_pub`
2. **Bilateral test was previously scheduled by humans** — there is a prior bus message of type `dispatch` or `coord-dispatch` from a human soberano with a scheduled timestamp, AND we are within ±48 hours of that timestamp
3. **Test is idempotent and recorded** — the test procedure produces an asciinema cast or equivalent reproducible artifact
4. **No active production overlap** — the local clan has no `type:alert msg:PRODUCTION_FREEZE` active
5. **Notification path is healthy** — the agent has successfully emitted at least one `dojo_event` in the last 24 hours (proves notification channel works)

> **Inaugural-case note (condition 5).** For the **first ever** bilateral execution between two clans that have just opened federation, no prior `dojo_event` may yet exist on either side. In that case condition 5 is satisfied by the initiating agent emitting a `dojo_event` of subtype `federation_preflight` **within the 30 minutes preceding** the test start. This avoids the chicken-and-egg of the first run without relaxing condition 5 in subsequent sessions. JEI proposed this carve-out during the 2026-05-19 bilateral review of ARC-ICAP-01 v0.1.

If any condition fails, the agent MUST refuse and emit `type:alert msg:ICAP_H02_PRECONDITION_FAILED` with the failing index.

### §6.3 Objection window (future versions)

ARC-ICAP-01 v0.1 does **not** implement objection windows (a future-version mechanism where the agent announces an intended action and waits N minutes for the soberano to object via bus). v0.2+ MAY add objection windows for H-01-like categories if bilateral experience suggests the cost of pre-action human delay is too high.

---

## §7 Bilateral Coordination (Inter-Clan Considerations)

When two clans federate, each clan's ICAP authorization tables are **independent**. JEI may authorize H-02 with stricter pre-conditions than DANI; that is allowed. The intersection rule applies:

- **An H-02 action between DANI and JEI succeeds only if BOTH sides' agents have H-02 authorized AND BOTH sides' pre-conditions are satisfied** for their respective views.

If asymmetric authorization is detected (e.g., JEI tries to initiate H-02 but DANI does not have H-02 enabled), the receiving side MUST refuse and emit `type:event msg:ICAP_ASYMMETRIC_AUTH` to alert the initiator.

### §7.1 Peer policy documents and the canonical taxonomy

Each clan MAY publish its own internal **agent security policy document** (e.g., JEI's `AGENTIC_SECURITY_POLICIES.md`). Such documents are clan-local doctrine and MAY define additional categories or stricter conditions for purposes internal to the clan. The bilateral canonical taxonomy, however, is **ARC-ICAP-01 (this spec)**, ratified by §10 sign-off. Peer policy documents MUST map their internal categories onto ARC-ICAP-01 H-01..H-06 when discussing bilateral actions, so that both soberanos speak the same vocabulary at the federation boundary.

The 2026-05-19 bilateral review established this mapping with JEI's `AGENTIC_SECURITY_POLICIES.md` v1.0:

| ARC-ICAP-01 | Equivalent in JEI v1.0 | Notes |
|---|---|---|
| H-01 (ratify spec) | JEI H-01 (architectural changes) | 1:1 |
| H-02 (bilateral test) | JEI §Acciones Autónomas | autonomous in JEI's model — consistent |
| H-03 (merge to main) | JEI H-02 (merge `amaru-protocol/main`) | 1:1 |
| H-04 (add/remove peer roster) | JEI H-07 (roster + 24h notice) | JEI adds a **bilateral 24h notice + SHA-256 roster hash validation** as an extra condition; see §7.2 below |
| H-05 (rotate identity keys) | (none yet — JEI to add explicitly) | JEI will incorporate H-05 into the next revision of its policy |
| H-06 (cross-dimensional capability) | JEI Firewall de Identidades | covered implicitly; JEI to make explicit |

### §7.2 H-04 bilateral condition (24h roster notice)

When the local clan executes H-04 (add or remove a peer from its roster) and that change is observable to a federated peer (e.g., the changed roster entry concerns the peer, or affects routes that touch the peer), the soberano humano of the local clan MUST send a **bilateral notification at least 24 hours before** the roster change takes effect. The notification MUST include the SHA-256 hash of the post-change roster file so the receiving peer's auditing agent can validate that the active roster matches the announced change.

This condition originates in JEI's `AGENTIC_SECURITY_POLICIES.md` v1.0 H-07. The 2026-05-12 ↔ 2026-05-13 PR #27 roster change (sovereign-compatible roster) is the empirical precedent: DANI announced, JEI's Bruja agent validated the SHA-256 in pre-flight, and the bilateral test the next day proceeded without re-authentication friction.

---

## §8 Security Considerations

- **Spoofing**: an attacker who compromises an agent's local environment could attempt to fake H-02 pre-conditions. Mitigation: all pre-conditions reference cryptographically-signed or human-authored bus messages; the agent never trusts unsigned state.
- **Replay**: §6.2 condition 2 (bilateral test scheduled by humans) MUST verify message timestamp and signature, not just presence.
- **Cascading**: if H-02 is granted, the agent MUST NOT cascade into other H-X categories during the same execution (e.g., a successful H-02 must not auto-promote into H-01 ratification of a related spec).
- **Audit trail**: every H-X evaluation (executed OR refused) MUST be logged. The audit log is the basis for §5.3 soberano review.

---

## §9 Versioning and Evolution

- v0.1 (this DRAFT): minimalist authorization — only H-02 YES, all others NO/NEVER. Notification post-facto required.
- v0.2 (future, after ≥ 90 days bilateral experience): MAY introduce objection windows or expand H-02 pre-conditions based on observed bilateral patterns.
- v0.3+ (future): MAY add new H-IDs as new agent capabilities emerge. New H-IDs MUST follow §2.2 (named human responsible in writing before deployment).

This spec is **bilateral-ratified**: changes require Council Ampliado on the proposing side AND human soberano signature from peer side(s) before merge.

---

## §10 Responsible Sign-Off (Required for RATIFIED status)

| Clan | Soberano | Sign_pub fingerprint | Signature date |
|------|----------|---------------------|----------------|
| DANI (momoshod) | Daniel Reyes | `85a940...cffe5f` | TBD |
| JEI | Jeimmy Gomez | `b05d85...77a0c` | TBD |

DRAFT v0.1 awaits bilateral review. Once both soberanos sign, status transitions DRAFT → RATIFIED via PR.

---

## §11 References

- [ARC-2119](ARC-2119.md) — Requirement Keywords
- [ARC-2314](ARC-2314.md) — Dojo / dojo_event message type
- [ARC-2606](ARC-2606.md) — Agent Profile & Discovery (roster contents)
- [ARC-4601](ARC-4601.md) — Agent Node Reference Implementation, §5 Bus Observer, §17 Federation, §18 Inter-Clan Reconciliation
- [ARC-5322](ARC-5322.md) — Message Format
- [ARC-COORD-01](ARC-COORD-01.md) — Coordinated Dispatch Type (used in H-01/H-03/H-04 agent-prepare patterns)
- [ARC-REFLECT-01](ARC-REFLECT-01.md) — Reflection Message Type
- [ARC-8446](ARC-8446.md) — Encrypted Bus Protocol (identity key formats — referenced by H-05)
- [CLAUDE.md global §Firewall Dimensional](../../.claude/CLAUDE.md) — Constitutional rule referenced by H-06
- [Change Management Protocol](../../.claude/rules/change-management.md) — Gate 4 (branch + PR) is NOT replaced by ICAP
- JEI `AGENTIC_SECURITY_POLICIES.md` v1.0 (2026-05-12, clan-local sister doctrine; bilateral mapping in §7.1)

---

## Historical Note

The empirical precedent for H-02 is the QC002 bilateral test executed on 2026-05-12, when JEI's agent autonomously moved up the human-scheduled bilateral slot and completed all 75/75 tests successfully (Issue #13 closed). This event prompted Daniel Reyes to commission this spec on 2026-05-18.

The Council Ampliado deliberation on 2026-05-18 (Palas, Ares, Artemisa, MariaM, Hannah) reached consensus on minimalist authorization (only H-02 YES) with two structural conditions:

1. Hannah's condition: named responsible human in writing for every category (§2, §3)
2. MariaM's condition: pedagogical entry point as the first non-header section (§1)
3. Artemisa's condition: post-facto notification mandatory for any YES category (§5)

This spec embodies all three conditions.
