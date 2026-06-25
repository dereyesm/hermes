# DANI Ecosystem Roster

> Public registry of clans, capabilities, and signature fingerprints operated by **DANI** (Daniel Reyes / dereyesm), for federation purposes under QUEST-CROSS-003 (ICAP).
>
> This roster is **sovereign-compatible** by design: it lists clan-level identity and capabilities, **not** the internal skills, files, or dimensions of each clan. Per the firewall doctrine (CLAUDE.md global, §"Firewall Dimensional"), internal structure of a clan is its own concern and is not exported across federation.

**Updated**: 2026-05-12
**Format version**: 0.1
**Companion specs**: ARC-2606 (Agent Profile), ARC-0370 (Auto-Peer Discovery), ARC-4601 §15.14 (Session Resumption — DRAFT)

---

## 1. Active clans

These clans operate in the federated network today and may appear as `src` or `dst` in bus messages addressed to JEI or other peers.

### momoshod — primary

| Field | Value |
|---|---|
| **clan_id** | `momoshod` |
| **role** | primary operator (DANI) |
| **sign_pub** | `85a940d9b5a2f084c660087c7377a07fa8128758a48bd6b55016fd32f7cffe5f` |
| **fingerprint** | `85a940d9...` (8-hex prefix) |
| **hub** | `ws://192.168.68.102:8443` (LAN, dynamic) |
| **status** | active |
| **capabilities** | `eng.software`, `protocol.architecture`, `creative.writing` |
| **public skills** | `protocol-architect`, `amaru-research`, `amaru-community` |
| **scope** | open-source protocol design and reference implementation for the Amaru Protocol; bilateral federation with peer clans |

### nymyka — federated peer

| Field | Value |
|---|---|
| **clan_id** | `nymyka` |
| **role** | federated peer (autonomous, separate governance) |
| **sign_pub** | `2e77eddff4fc898f98a10c58be305739d2e481da2a260943e53ac1287943b13b` |
| **fingerprint** | `2e77eddf...` |
| **status** | registered, currently paused (team capacity) |
| **capabilities** | `enterprise.consulting`, `eng.software` (private scope) |
| **public skills** | *(not exported — Nymyka maintains its own private roster)* |
| **scope** | cross-clan dispatch to `nymyka` requires explicit quest approval from Nymyka's CEO. Federation does not imply transitive trust. |
| **notes** | Nymyka is an independent organization that runs the Amaru protocol; its internal agents, clients, and quests are out of scope for this roster. |

---

## 2. Out of scope for this roster

The DANI operator participates in additional work contexts not listed here. Those contexts:

- Run their own private bus and skills (firewall dimensional rule)
- Do **not** federate to JEI or other public peers via this protocol today
- Will appear in this roster only if and when:
  1. They federate explicitly (via `amaru peer invite`/`accept`)
  2. Their stakeholders (corporate, legal, contractual) authorize public listing
  3. A scoped capability declaration is agreed

If a cross-clan quest is proposed that touches one of these contexts, the request will be acknowledged at the `momoshod` clan level and routed internally; the federation does **not** see the internal structure.

This is the same model JEI applies on her side: JEI's internal triada (JAi/Bruja/Bachue) operates with full firewall; the federation sees `jei` as a single clan identity.

---

## 3. Trust model

- **Direct trust**: clans listed in §1 with `status: active`. JEI may dispatch quests to these clan_ids and expect responses signed by the listed `sign_pub`.
- **Transitive trust**: NOT granted. A quest dispatched to `momoshod` does not authorize `momoshod` to forward to any non-listed clan without an explicit consent event on the bus.
- **Capability negotiation**: per ARC-4601 §18.5 (DRAFT), capabilities may be filtered at the hub. Quests outside a listed capability set MUST be rejected with an `err` frame.

---

## 4. Sign_pub verification

Receiving clans MUST verify `sign_pub` matches the value listed here before honoring a federated message. The current canonical source for `sign_pub` values is this file. A future amendment may move the registry to a signed manifest format (candidate: ARC-0370 §3 Federation Gossip).

---

## 5. Update procedure

Changes to this roster (add clan, remove clan, rotate sign_pub, change scope) require:

- A pull request to `amaru-protocol`
- Review by at least one peer clan with which DANI has an active federation
- Bus event `roster_updated` after merge, signed by DANI's primary clan

A rotation of `sign_pub` (key compromise or routine rotation) MUST be announced with both the old and new values for a 7-day overlap window so peers can verify and trust the new key.

---

## 6. References

- **CLAUDE.md global, §Firewall Dimensional** — internal-clan opacity is doctrinal
- **ARC-2606** — Agent Profile & Discovery
- **ARC-0370** — Auto-Peer Discovery Protocol (4-level discovery)
- **ARC-4601 §15.14** — Session Resumption (DRAFT, last-known-peers cache)
- **ARC-8446** — Encrypted Bus Protocol (key formats, fingerprints)
- **QUEST-CROSS-003 (ICAP)** — Inter-Clan Autonomy Protocol (consumer of this roster)

---

**Maintained by**: DANI clan — @dereyesm (contact via [GitHub Security Advisories](https://github.com/dereyesm/amaru-protocol/security/advisories/new))
**Companion**: JEI's roster lives in her own ecosystem; the federation joins these two sovereign registries via bilateral handshake, not by merging them.
