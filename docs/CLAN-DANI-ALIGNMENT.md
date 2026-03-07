# Clan Alignment: DANI (Momosho D) — Response to Clan JEI (La Triada)

> Formal response to JEI-PMO-010 v1.1 (2026-03-05).
> This document answers the five namespace alignment questions posed by
> Clan JEI and establishes the inter-clan routing model.

**Date**: 2026-03-07
**From**: Clan DANI (Momosho D) — Daniel Reyes, Protocol Architect
**To**: Clan JEI (La Triada) — Jeimmy Gomez, La Soberana

---

## 1. Architectural Orthogonality

Clan JEI organizes by **function** (6 namespaces: estrategia, legal, seguridad,
operaciones, gateway, controller). Clan DANI organizes by **dimension** (6
dimensions: Global, Nymyka, MomoshoD, MomoFinance, Zima26, HERMES).

These are **orthogonal axes** of the same problem. Neither is wrong — they
reflect different operational realities. Per ARC-2314 Section 16.2, each clan
has absolute freedom over internal architecture. The protocol only mandates
the external interfaces.

```
JEI (function-based):

  estrategia ─── legal ─── seguridad ─── operaciones ─── gateway ─── controller
      JAi        Valerio    Bachue+Bruja   IdA+Patos      Huitaca    GoGi

DANI (dimension-based):

  Global ─── Nymyka ─── MomoshoD ─── MomoFinance ─── Zima26 ─── HERMES
  Consejo    12 skills   1 skill      2 skills        5 skills    1 skill
  Dojo       (corporate) (editorial)  (finance)       (housing)   (protocol)
  Heraldo
  Arena
```

From the Agora, both clans appear as **single super-skills** (ARC-2314 s16.3)
with aggregated capabilities. Internal structure is invisible to peers.

---

## 2. Answers to JEI's Five Questions

### Q1: What are your namespaces?

DANI has **6 dimensions** (not function-based namespaces):

| Dimension | Scope | Skills | Head |
|-----------|-------|--------|------|
| **Global** | Cross-dimensional deliberation | 7 (Palas, Ares, Artemisa, Consejo, Dojo, Heraldo, Arena) | — |
| **Nymyka** | Corporate (Grupo Nymyka) | 13 (MomoProdDev + 12 advisors) | MomoProdDev |
| **MomoshoD** | Editorial, personal brand | 1 (La Voluntad de D.) | — |
| **MomoFinance** | Personal finance | 2 (Plutus, Oraculo) | — |
| **Zima26** | Housing (propiedad horizontal) | 5 (admin, legal, fiscal, etc.) | — |
| **HERMES** | Protocol research | 1 (Protocol Architect) | Protocol Architect |

**Total**: 28 skills + 1 integrated Dojo across 6 dimensions.

Externally, DANI publishes a single Agora profile with aggregated capabilities.
Internal routing (which dimension handles what) is resolved by the Dojo
(integrated into Palas — see Q3).

### Q2: What is your gateway (equivalent to Huitaca)?

| | JEI | DANI |
|---|---|---|
| **Name** | Huitaca | Heraldo |
| **Type** | Bot Telegram + Agora relay | Global-limited skill (1 MCP) + Telegram bridge |
| **Role** | Sole entry/exit point of Clan JEI | Sole entry/exit point of Clan DANI |
| **Human gate** | JAi proposes, Jeimmy decides | Heraldo proposes, Daniel decides |
| **HERMES plane** | Control Plane (CP) | Control Plane (CP) |

Heraldo operates the gateway infrastructure (ARC-3022). It uses Telegram for
human relay and momoshod-gmail for email scanning (read-only sensor).

### Q3: What is your controller (equivalent to GoGi)?

| | JEI | DANI |
|---|---|---|
| **Name** | GoGi-Sensei | Palas (with Dojo integrated) |
| **Functions** | Meta-auditor (read-only) + Dojo (quest dispatch) | Strategy + Orchestration + Evaluation |
| **Audit** | GoGi audits both dimensions | Artemisa (guardian) + firewall in every CLAUDE.md |
| **Deployment model** | Separate controller + Dojo | Integrated OP-Strategy (ARC-2314 s11.2 variant) |
| **HERMES plane** | Orchestration Plane (OP) | Orchestration Plane (OP) + Strategy |

DANI chose to integrate its Dojo into Palas (the strategy skill). This means
the Orchestration Plane and the strategic deliberation layer are merged into
a single agent. This is a valid deployment model under ARC-2314: the spec
defines interfaces, not topology.

GoGi's read-only audit function has no single equivalent in DANI. Instead,
audit is **architectural**: every dimension's CLAUDE.md contains firewall
rules, and Artemisa (the guardian skill) monitors quality and limits.

### Q4: Are there equivalent namespaces?

| JEI Namespace | JEI Agents | DANI Equivalent | Key Difference |
|---|---|---|---|
| **estrategia** | JAi | Consejo (Palas + Ares + Artemisa) | JEI: single orchestrator. DANI: deliberation triad (3 voices) |
| **legal** | Valerio, Valerio-Personal | consejero-legal (Zima26 dimension only) | JEI: cross-dimensional. DANI: scoped to housing law (Ley 675) |
| **seguridad** | Bachue, Bruja | Architectural pattern + Artemisa | JEI: dedicated agents. DANI: embedded in every CLAUDE.md as firewall rules |
| **operaciones** | IdA, Pato-Nymyka, Pato-Personal, Sakti | Distributed across all dimensions (28 skills) | JEI: centralized namespace. DANI: each dimension has its own operations |
| **gateway** | Huitaca | Heraldo | Direct equivalence |
| **controller** | GoGi-Sensei | Palas (Dojo integrated) | JEI: separate audit + dojo. DANI: merged strategy + orchestration |

**Notable gaps in DANI**:
- No cross-clan legal agent (Valerio-equivalent)
- No dedicated CISO/risk agent (Bruja-equivalent) — security is a pattern, not an agent
- No dedicated bienestar agent (Sakti-equivalent) — Artemisa covers this partially

**Notable capabilities in DANI not present in JEI**:
- Arena system (collaborative growth, PvP/Multi/BR modes)
- Observer skills (planned: sociologist, anthropologist, neuroscientist)
- 6 dimensions vs 2 (plus transversal)

### Q5: How does human approval work in your clan?

DANI uses a **triple firewall** model:

| Layer | What it protects | How it works |
|---|---|---|
| **MCP Firewall** | Tool access | Each dimension declares allowed/forbidden MCPs. Violations are blocked at invocation. |
| **Identity Firewall** | Credentials | Each dimension has its own account. Cross-account access is forbidden. |
| **Epistemological Firewall** | Knowledge boundaries | Skills cannot access data from other dimensions without explicit permission and translation. |

On top of the firewall, **human-in-the-loop** applies to all irreversible actions:
- Push to git, send email, publish content → require Daniel's explicit approval
- Global skills (Palas, Ares, Artemisa, Consejo, Dojo) are advisory only — they recommend, Daniel decides
- Dimensional skills execute within their scope but cannot cross the firewall

**For inter-clan communication**: everything that exits Clan DANI passes through
Heraldo (gateway) and requires Daniel's approval. This mirrors JEI's model:
"JAi propone, Jeimmy decide."

---

## 3. Inter-Clan Routing Model

All traffic between DANI and JEI flows **gateway-to-gateway**:

```
Clan DANI (internal)          Inter-Clan           Clan JEI (internal)
─────────────────────         ──────────           ────────────────────

  Palas (OP)                                         JAi (estrategia)
    │                                                  │
    ▼                                                  ▼
  Heraldo (CP) ──────────► Agora ◄──────────── Huitaca (CP)
  (gateway)                (relay)              (gateway)
    ▲                                                  ▲
    │                                                  │
  Daniel                                           Jeimmy
  (human gate)                                     (human gate)
```

**There are no direct namespace-to-namespace channels.** If JEI's Valerio
needs to communicate with DANI's consejero-legal, the message flows:

```
Valerio → JAi → Huitaca → [Agora] → Heraldo → Palas → consejero-legal
```

Each hop through a Dojo (JAi for JEI, Palas for DANI) ensures governance,
logging, and human approval at both ends.

---

## 4. Agora Profile — Clan DANI as Super-Skill

Per ARC-2314 s16.3, DANI appears in the Agora as:

```json
{
  "clan_id": "momosho-d",
  "clan_name": "Clan Momosho D",
  "sovereign": "Daniel Reyes",
  "gateway": "heraldo",
  "capabilities": [
    "engineering/software",
    "engineering/telecom",
    "finance/personal",
    "legal/housing",
    "creative/editorial",
    "research/protocol-design",
    "research/observation"
  ],
  "deployment_model": "integrated-op-strategy",
  "skills_count": 28,
  "dimensions": 6,
  "hermes_version": "0.3.0-alpha"
}
```

Internal skill roster, XP scores, and dimension structure are NOT published.
Only aggregated capabilities visible through the gateway.

---

## 5. Proposed Next Steps

| Step | Owner | When | Description |
|------|-------|------|-------------|
| 1 | Both | Now | Acknowledge this alignment document |
| 2 | Both | Next session | Diagnose and fix the relay (`jeipgg/nymyka-hermes-relay`) — SSL/token issue since Feb 28 |
| 3 | JEI | Post-fix | Send `ecosystem_manifest` via relay (introduce Valerio-Personal, Bachue to DANI) |
| 4 | DANI | Post-fix | Send DANI's Agora profile via relay |
| 5 | Both | Post-relay | First real inter-clan message (quest proposal or hello_ack) |

---

## 6. References

- [ARC-2314](../spec/ARC-2314.md) — Skill Gateway Plane Architecture (triple-plane CUPS, deployment models, diplomatic protocol)
- [ARC-3022](../spec/ARC-3022.md) — Agent Gateway Protocol (NAT, identity translation, Agora)
- [ARC-2606](../spec/ARC-2606.md) — Agent Profile & Discovery (capability ontology)
- [ARC-1918](../spec/ARC-1918.md) — Private Spaces & Firewall
- [GETTING-STARTED](GETTING-STARTED.md) — Introduction to HERMES for new clans
- JEI-PMO-010 v1.1 (2026-03-05) — Source document from Clan JEI

---

*Prepared by Protocol Architect, Clan Momosho D, 2026-03-07*
*In response to La Triada presentation (JAi + Jeimmy Gomez)*
