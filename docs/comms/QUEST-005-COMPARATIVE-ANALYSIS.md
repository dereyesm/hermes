# QUEST-005 Comparative Analysis — Clan DANI vs Clan JEI

> Iteration 1 | Domain: Prompt Engineering & Agent Orchestration
> Date: 2026-03-27 (draft) | Updated: 2026-03-30 (JEI artifact decrypted)
> Status: Phase 4 Bilateral Merge ready (Apr 5)

## Inventory Comparison

| Dimension | DANI (momoshod) | JEI | Notes |
|---|---|---|---|
| **Total skills** | 33 | 40 | JEI +21% in raw count |
| **Categories** | 7 dimensions (global, nymyka, momoshod, momofinance, zima26, hermes, global-limited) | 9 categories (orchestration, security, engineering, process, knowledge, comms, finance, legal, ops) | DANI organizes by life dimension; JEI by functional domain |
| **Prototype** | 12 (36%) | 25 (62.5%) | JEI has more skills but majority are prototype-stage |
| **Stable** (Trainer+) | 17 (52%) | 12 (30%) | DANI's stable ratio is 1.7x JEI's |
| **Battle-tested** (Gym Leader+) | 4 (12%) | 3 (7.5%) | Comparable at the top; DANI slightly ahead |
| **Agents (autonomous)** | 2 (heraldo, exit-protocol) | 1+ (Huitaca + JAi router) | Both have email/notification agents; JEI has a dedicated router |
| **XP system** | Arena + registry.json (per-skill XP/level/medals) | GoGi Dojo (RPG mechanics, quests, dice rolls) | Different gamification philosophies (see Patterns) |

**Key observation**: JEI has more total skills but a heavier prototype tail (62.5% vs 36%). DANI has fewer skills but higher maturity concentration — over half are stable or above.

## Practice Scores Comparison

| Practice | DANI (est.) | JEI | Gap | Who leads |
|---|---|---|---|---|
| **Prompt Engineering** | 4 | 4 | 0 | Tie |
| **Security** | 4 | 4 | 0 | Tie |
| **Orchestration** | 4 | 3 | +1 | DANI |
| **Knowledge Management** | 4 | 4 | 0 | Tie |
| **Testing** | 4 | 3 | +1 | DANI |

DANI scores are estimated from QUEST-004 (76% across 14 categories, 1087 HERMES tests, proven bilateral crypto, multi-dimension CLAUDE.md architecture, HERMES bus protocol). JEI self-reported in the artifact.

**Prompt Engineering (tie at 4/4)**: Both clans use structured prompt chains with role-scoped boundaries. DANI's architecture uses YAML frontmatter skills with dimension-scoped MCPs and a firewall preventing cross-context leakage. JEI uses YAML frontmatter with keyword-based auto-trigger and staged outputs with a mandatory security gate. Both approaches are mature but differ in enforcement mechanism (DANI: MCP firewall; JEI: security gate stage).

**Security (tie at 4/4)**: Both implement the full HERMES crypto stack (Ed25519 + X25519 + AES-256-GCM + HKDF). DANI authored ARC-8446 and the canonical v1.2 spec; JEI achieved canonical alignment (confirmed 2026-03-25). JEI adds a dedicated CISO agent with pre-flight checks — DANI handles this through rules files (supply-chain-sop.md, firewall rules) and Artemisa wellness monitoring. Both have zero-secrets-in-repo policies.

**Orchestration (DANI leads, 4 vs 3)**: DANI operates a 33-skill ecosystem across 7 dimensions with formalized governance (Consejo 3-5 voices for decisions, Dojo for dispatch, Arena for training, HERMES bus for inter-dimensional sync). JEI has a mandatory 3-agent triada (REGLA-ORCH-002) and tiered autonomy (Tier1/Tier2), but acknowledges "significant human-in-the-loop orchestration" still required. DANI's governance is more layered: Consejo deliberates, Ares executes, Palas monitors, Artemisa guards — each with clear non-overlapping mandates.

**Knowledge Management (tie at 4/4)**: Both use typed persistent memory (4 types). JEI's GoGi Learning Daemon runs autonomously every 5 minutes — DANI has no equivalent autonomous learner but compensates with a rigorous exit protocol (7-step mandatory session harvest, MEMORY.md compaction checks, bus sync, dashboard sync). JEI's KNOWN_ERRORS.md maps failure domains to pre-flight triggers — a practice DANI lacks in formalized form.

**Testing (DANI leads, 4 vs 3)**: DANI has 1087 tests across 15 test files covering 17 Python modules, with bilateral ECDHE verification catching 3 crypto divergences. JEI reports passing bot tests (19/19, 21/21) but acknowledges "coverage incomplete outside bot layer; most agents lack automated test suites." The coverage gap is significant.

## Pattern Divergences

### Top practices unique to each

**DANI only:**
- **Multi-dimensional MCP firewall**: Skills are scoped to dimensions, each dimension has explicit ALLOWED/PROHIBITED MCP lists. A Nymyka skill cannot touch personal Gmail; a HERMES skill cannot touch any MCP. No equivalent in JEI.
- **Exit protocol as institutional ritual**: 7 mandatory steps (harvest, HERMES FIN, memory update, commit/push, dashboard sync, next session prompt, gratitude). Ensures zero session-end data loss and always produces a next-session ramp-up prompt.
- **Arena training system**: Skills grow XP through structured PvP/Multi/BR exercises with scored evaluations. Skills "level up" with documented first bloods and medals. JEI's GoGi has narrative arcs but is more of a learning daemon than a structured competitive growth system.

**JEI only:**
- **KNOWN_ERRORS.md as institutional memory**: Structured error catalog (8 failure domains) linked to pre-flight triggers. Solves LLM session memory decay for recurring mistakes. DANI's closest equivalent is rules files, but they are prescriptive (do X) rather than diagnostic (when you see Y, it means Z).
- **Spec-First mandate (ADR-002)**: Nothing gets implemented without an approved mini-spec. DANI uses plan mode and Consejo deliberation for important decisions but does not enforce a formal spec gate for every implementation.
- **GoGi autonomous learning daemon**: Runs every 5 minutes, captures ecosystem lessons without human prompting. DANI's learning is session-bound (exit protocol harvest), not continuous.

### Anti-patterns unique to each

**JEI reported:**
- Monolithic agent files (1283-line GoGi, refactored 8x to 163 lines + 6 modules)
- Missing global identity context (per-project drift, now fixed)
- External SaaS dependency for internal ops (migrated to self-hosted)

**DANI known:**
- Worktrees completely unused (0% in both QUEST-004 assessments)
- Checkpointing not adopted (11.1 gap open since QUEST-004)
- IDE integration minimal (no VS Code plugin, no custom keybindings)

### Unconventional approaches

**JEI**: Narrative gamification (GoGi Dojo) — RPG mechanics with dice rolls, quests, Level 7 "Gran Maestro" progression. Converts maintenance overhead into self-sustaining incentive loop.

**DANI**: Dimension-as-identity architecture — each life dimension (work, personal, finance, housing, open-source) is a separate namespace with its own head, skills, MCPs, and firewall. Skills have passports to travel between dimensions. The bus protocol syncs state without crossing credential boundaries.

## Cross-Pollination Opportunities

### What DANI should adopt from JEI

1. **KNOWN_ERRORS.md pattern**: Create a structured error catalog per dimension mapping failure domains to pre-flight triggers. Immediate candidate: supply-chain-sop.md could be reformatted as KNOWN_ERRORS entries with trigger conditions.
2. **Spec-First gate (ADR-002)**: Formalize a lightweight spec requirement before implementation in non-HERMES dimensions. HERMES already has ARC specs; Nymyka and MomoshoD do not.
3. **Autonomous learning daemon**: A background process (or cron hook) that periodically scans session logs and extracts patterns without waiting for exit protocol. Could be a heraldo-like agent scoped to MEMORY.md maintenance.

### What JEI should adopt from DANI

1. **MCP firewall pattern**: JEI operates across projects but does not report dimension-scoped MCP isolation. Adopting a firewall table (ALLOWED/PROHIBITED per context) would prevent credential cross-contamination.
2. **Exit protocol discipline**: JEI's session-end process is not described in the artifact. DANI's 7-step protocol ensures zero data loss and always produces a ramp-up prompt for the next session.
3. **Test coverage expansion**: JEI's 40 tests on bot modules leave agents untested. DANI's 1087-test suite demonstrates that protocol-level code can be comprehensively covered. Target: at least regression suites for the GoGi modules and triada orchestration logic.

## Updated Gap Analysis

| Metric | QUEST-004 (Mar 18) | QUEST-005 (Mar 27) | Delta |
|---|---|---|---|
| **DANI overall** | 76% (14 cats, 60 items) | Est. 78%* | +2pp (worktrees still 0%, but supply-chain-sop and §16 spec added) |
| **JEI overall** | ~54% (14 cats, 60 items) | Est. 62%** | +8pp (global identity fixed, GoGi refactored, self-hosted migration) |
| **Gap** | 22pp | Est. 16pp | Narrowing (-6pp) |

*DANI estimate based on: 3 QUEST-004 gaps closed same-session (6.3, 12.2, 6.6), supply-chain-sop.md added (new formalized practice), hub deploy tested, §16 spec complete. Worktrees and checkpointing remain open.

**JEI estimate based on: 3 anti-patterns resolved (monolithic files, global identity, SaaS dependency), HERMES canonical alignment confirmed, KNOWN_ERRORS.md institutional memory added, Tier1/Tier2 autonomy formalized. Test coverage gap remains open.

**Trajectory**: JEI is closing the gap faster (+8pp vs +2pp). This is expected — JEI started lower and the anti-pattern fixes yield large point gains. DANI's remaining gaps are harder to close (worktrees, checkpointing, IDE integration) because they require workflow changes, not just configuration.

**The gap is narrowing from 22pp to approximately 16pp.** If JEI closes the test coverage gap and DANI adopts KNOWN_ERRORS.md, both clans converge toward 80%+ — the "battle-tested" tier for Claude Code adoption.

---

## JEI Artifact Receipt Log

| Date | Message | Status |
|------|---------|--------|
| 2026-03-25 | JEI-HERMES-019: QUEST-005 artifact (ECDHE encrypted) | Decrypted 2026-03-30, 6/6 relay msgs OK |
| 2026-03-25 | JEI-HERMES-020: Confirmation + hub bilateral availability | Decrypted 2026-03-30 |
| 2026-03-30 | DANI-HERMES-022: ACK sent (artifact received, hub Mar 31 confirmed) | Pushed to relay 900827e |

## HERMES Updates Since Last Analysis (2026-03-27 → 2026-03-30)

- **OpenCodeAdapter**: 3rd adapter (Claude Code + Cursor + OpenCode), Agent Skills Standard alignment
- **MANIFESTO.md + ETHICS.md + QUEST-000.md**: Social purpose formalized (5 Realms, AI withdrawal, 7 anti-patterns)
- **Local LLM guide**: MLX + Qwen 2.5 Coder, 3 platforms (Mac/Linux/Windows)
- **Tests**: 1267 → 1305 (+38), coverage 80%
- **Arena BR-022**: Post-facto review found 7 fixes (DRY refactor, standard compliance, README visibility)

---

*Analysis produced by Protocol Architect dimension, HERMES v0.4.2-alpha.*
*Data sources: QUEST-004 assessment (DANI), QUEST-005 artifact (JEI, decrypted 2026-03-30), registry.json (DANI skill inventory).*
