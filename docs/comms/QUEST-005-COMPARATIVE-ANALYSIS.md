# QUEST-005 Comparative Analysis — Clan DANI vs Clan JEI

> Iteration 1 | Domain: Prompt Engineering & Agent Orchestration
> Date: 2026-03-27 (draft) | Updated: 2026-04-02 (DANI artifact generated, Phase 4 merge)
> Status: Phase 4 Bilateral Merge COMPLETE

## Inventory Comparison

| Dimension | DANI (momoshod) | JEI | Notes |
|---|---|---|---|
| **Total skills** | 35 | 40 | JEI +14% in raw count (was +21% at QUEST-004) |
| **Categories** | 7 dimensions (global, nymyka, momoshod, momofinance, zima26, hermes, global-limited) | 9 categories (orchestration, security, engineering, process, knowledge, comms, finance, legal, ops) | DANI organizes by life dimension; JEI by functional domain |
| **Prototype** | 16 (46%) | 25 (62.5%) | JEI's prototype tail remains heavier |
| **Stable** (Trainer+) | 12 (34%) | 12 (30%) | Comparable stable tier |
| **Battle-tested** (Gym Leader+) | 7 (20%) | 3 (7.5%) | DANI leads 2.7x in battle-tested ratio |
| **Agents (autonomous)** | 2 (heraldo, exit-protocol) | 1+ (Huitaca + JAi router) | Both have email/notification agents; JEI has a dedicated router |
| **XP system** | Arena + registry.json (3524 XP, 25+ medals) | GoGi Dojo (RPG mechanics, quests, dice rolls) | Different gamification philosophies (see Patterns) |
| **Tests** | 1451 (23 files, 81% cov, 126 conformance vectors) | ~40 (bot modules only) | DANI leads ~36x in test count |
| **Adapters** | 4 (Claude Code, Cursor, OpenCode, Gemini CLI) | N/A | DANI's agent-agnostic adapter layer |

**Key observation**: DANI has grown from 33 to 35 skills with stronger battle-tested concentration (20% vs 7.5%). JEI has more total skills but a heavier prototype tail (62.5% vs 46%). The testing gap remains the most significant asymmetry.

## Practice Scores Comparison

| Practice | DANI (est.) | JEI | Gap | Who leads |
|---|---|---|---|---|
| **Prompt Engineering** | 4 | 4 | 0 | Tie |
| **Security** | 4 | 4 | 0 | Tie |
| **Orchestration** | 4 | 3 | +1 | DANI |
| **Knowledge Management** | 4 | 4 | 0 | Tie |
| **Testing** | 4 | 3 | +1 | DANI |

DANI scores are from the DANI artifact (quest005_artifact_dani.json, 2026-04-02), based on 35 skills, 1451 tests, 81% coverage, 4 adapters, 21 specs IMPL, ARC-1122 conformance (126 test vectors). JEI scores are self-reported from JEI artifact (quest005_artifact_jei_decrypted.json, 2026-03-25).

**Prompt Engineering (tie at 4/4)**: Both clans use structured prompt chains with role-scoped boundaries. DANI's architecture uses YAML frontmatter skills with dimension-scoped MCPs and a firewall preventing cross-context leakage. JEI uses YAML frontmatter with keyword-based auto-trigger and staged outputs with a mandatory security gate. Both approaches are mature but differ in enforcement mechanism (DANI: MCP firewall; JEI: security gate stage).

**Security (tie at 4/4)**: Both implement the full HERMES crypto stack (Ed25519 + X25519 + AES-256-GCM + HKDF). DANI authored ARC-8446 and the canonical v1.2 spec; JEI achieved canonical alignment (confirmed 2026-03-25). JEI adds a dedicated CISO agent with pre-flight checks — DANI handles this through rules files (supply-chain-sop.md, firewall rules) and Artemisa wellness monitoring. Both have zero-secrets-in-repo policies.

**Orchestration (DANI leads, 4 vs 3)**: DANI operates a 33-skill ecosystem across 7 dimensions with formalized governance (Consejo 3-5 voices for decisions, Dojo for dispatch, Arena for training, Amaru bus for inter-dimensional sync). JEI has a mandatory 3-agent triada (REGLA-ORCH-002) and tiered autonomy (Tier1/Tier2), but acknowledges "significant human-in-the-loop orchestration" still required. DANI's governance is more layered: Consejo deliberates, Ares executes, Palas monitors, Artemisa guards — each with clear non-overlapping mandates.

**Knowledge Management (tie at 4/4)**: Both use typed persistent memory (4 types). JEI's GoGi Learning Daemon runs autonomously every 5 minutes — DANI has no equivalent autonomous learner but compensates with a rigorous exit protocol (7-step mandatory session harvest, MEMORY.md compaction checks, bus sync, dashboard sync). JEI's KNOWN_ERRORS.md maps failure domains to pre-flight triggers — a practice DANI lacks in formalized form.

**Testing (DANI leads, 4 vs 3)**: DANI has 1451 tests across 23 test files covering 19 Python modules (81% coverage), with bilateral ECDHE verification catching 3 crypto divergences and ARC-1122 conformance providing 126 golden test vectors across 3 levels. JEI reports passing bot tests (19/19, 21/21) but acknowledges "coverage incomplete outside bot layer; most agents lack automated test suites." The coverage gap is the most significant asymmetry between clans (~36x test count difference).

## Pattern Divergences

### Top practices unique to each

**DANI only:**
- **Multi-dimensional MCP firewall**: Skills are scoped to dimensions, each dimension has explicit ALLOWED/PROHIBITED MCP lists. A Nymyka skill cannot touch personal Gmail; an Amaru skill cannot touch any MCP. No equivalent in JEI.
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

## What We Learned From Them (DANI perspective)

The bilateral exchange surfaced three JEI practices that address gaps in DANI's ecosystem:

1. **KNOWN_ERRORS.md as diagnostic memory**: DANI's rules files are prescriptive ("do X"), but JEI's KNOWN_ERRORS.md is diagnostic ("when you see Y, it means Z"). This distinction matters: prescriptive rules assume you know the failure domain; diagnostic entries help when you don't. **Adoption status**: Not yet implemented. Candidate: supply-chain-sop.md could be the first KNOWN_ERRORS per-dimension file.

2. **Spec-First gate as quality checkpoint**: DANI uses plan mode and Consejo deliberation for big decisions, but small-to-medium changes have no formal gate. JEI's ADR-002 creates a lightweight checkpoint for everything. **Adoption status**: HERMES already has ARC specs (the most rigorous version). The gap is in other dimensions (Nymyka, MomoshoD) where no spec gate exists.

3. **Autonomous learning daemon**: DANI's learning is session-bound — the exit protocol harvests insights only at session end. JEI's GoGi runs every 5 minutes, capturing patterns continuously. **Adoption status**: Conceptually appealing but architecturally challenging — Claude Code sessions don't have background processes. A cron-based agent (like heraldo for email) scoped to MEMORY.md maintenance could approximate this.

**Meta-insight**: JEI's practices consistently address the problem of *inter-session knowledge decay* — the fundamental LLM limitation where each session starts from zero. DANI compensates with rigorous exit protocols; JEI compensates with continuous background capture. Both approaches are valid; combining them would be strongest.

## What We Taught Them (JEI perspective, inferred)

Based on the cross-pollination analysis and JEI's reported gaps:

1. **MCP firewall pattern**: JEI does not report dimension-scoped credential isolation. Operating across projects without a firewall risks credential cross-contamination — a bug class DANI's architecture prevents by design. JEI's adoption would require mapping their 9 functional categories to credential scopes.

2. **Exit protocol discipline**: JEI's artifact does not describe a session-end ritual. Without one, session insights depend on the human remembering to persist them. DANI's 7-step protocol makes this mandatory and produces a next-session prompt that eliminates cold-start ramp-up.

3. **Test coverage as protocol validation**: DANI's 1451-test suite and ARC-1122 conformance spec (126 test vectors across 3 levels) demonstrate that protocol-level code can be comprehensively verified. JEI's ~40 tests cover bot modules only. The conformance spec provides a reusable template — JEI could adopt ARC-1122 levels to verify their own HERMES implementation.

**Meta-insight**: DANI's practices consistently address the problem of *systemic integrity* — ensuring that the whole system (credentials, sessions, protocol) behaves correctly even under edge conditions. JEI's strength is more in *adaptive resilience* — recovering from failures and learning from them continuously.

## Updated Gap Analysis

| Metric | QUEST-004 (Mar 18) | QUEST-005 (Mar 27) | Phase 4 (Apr 2) | Delta |
|---|---|---|---|---|
| **DANI overall** | 76% | Est. 78% | Est. 80%* | +4pp total |
| **JEI overall** | ~54% | Est. 62% | Est. 64%** | +10pp total |
| **Gap** | 22pp | 16pp | 16pp | Stable |

*DANI (Apr 2): 1451 tests (+364 since Mar 27), 4 adapters (+2), ARC-1122 conformance (126 vectors), PyPI publish prep done, CI 81%. Worktrees and checkpointing still open. Token telemetry module added. GeminiCLI adapter added.

**JEI (Apr 2, estimated): canonical ECDHE confirmed (Mar 25), hub bilateral available (Apr 2), QUEST-005 artifact delivered on time. No new data since artifact delivery — estimate holds from Mar 27.

**Trajectory**: The gap has stabilized at ~16pp. DANI's improvements are incremental (testing depth, adapter breadth, PyPI readiness) — the "easy wins" are exhausted, remaining gains require workflow changes (worktrees, checkpointing, IDE). JEI's trajectory depends on test coverage expansion and autonomous learning daemon maturation — both reported as in-progress but unverified.

**Convergence**: Both clans are converging toward 80%+ (the "battle-tested" tier). DANI is ~80%, JEI is ~64%. For JEI to reach 80%, the primary lever is testing (upgrading from 3→4 would close 4-5pp). For DANI, adopting KNOWN_ERRORS.md and closing the worktree gap would push past 82%.

---

## Artifact Exchange Log

| Date | Message | Status |
|------|---------|--------|
| 2026-03-25 | JEI-HERMES-019: QUEST-005 artifact (ECDHE encrypted) | Decrypted 2026-03-30, 6/6 relay msgs OK |
| 2026-03-25 | JEI-HERMES-020: Confirmation + hub bilateral availability | Decrypted 2026-03-30 |
| 2026-03-30 | DANI-HERMES-022: ACK sent (artifact received, hub Mar 31 confirmed) | Pushed to relay 900827e |
| 2026-04-02 | DANI artifact generated (quest005_artifact_dani.json) | Local, ready for encryption |
| 2026-04-02 | Phase 4 merge document updated (this file) | Complete |

## HERMES Updates Since Last Analysis (2026-03-27 → 2026-04-02)

- **GeminiCLIAdapter**: 4th adapter (Claude Code + Cursor + OpenCode + Gemini CLI)
- **`amaru adapt --list/--all`**: Auto-detect installed agents + batch adapt
- **Token Telemetry**: telemetry.py (TokenTracker, 10 models, JSONL, `amaru llm usage` CLI)
- **ARC-1122 L3 Conformance**: 41 Network-Ready test vectors (126 total across 3 levels)
- **CLI coverage**: Ratio improved 1:49 → 1:18
- **CI threshold**: 75% → 80% (passing 81%)
- **PyPI publish prep**: PEP 440 version, README long_description, py.typed, keywords, --version flag
- **OpenCodeAdapter**: 3rd adapter + Agent Skills Standard alignment
- **MANIFESTO.md + ETHICS.md + QUEST-000.md**: Social purpose formalized (5 Realms, 7 anti-patterns)
- **Tests**: 1087 → 1451 (+364), coverage 80% → 81%
- **Arena sessions**: BR-018 through BR-022 + MULTI-019/020/021

## Next Steps (Phase 5: ATR Formalization)

Phase 4 merge is complete. Phase 5 (2026-04-12 → 2026-04-19) will formalize the knowledge exchange protocol as an ATR spec:

1. **ATR-KEP-001**: Knowledge Exchange Protocol — formal spec based on QUEST-005 learnings
2. **Iteration 2 domain proposal**: Based on the meta-insights above, candidates include:
   - *Inter-session knowledge persistence* (where both clans have complementary approaches)
   - *Agent autonomy governance* (Tier1/Tier2 vs Consejo/Arena models)
   - *Testing as protocol validation* (conformance spec methodology)

---

*Analysis produced by Protocol Architect dimension, HERMES v0.4.2-alpha.*
*Data sources: DANI artifact (quest005_artifact_dani.json, 2026-04-02), JEI artifact (quest005_artifact_jei_decrypted.json, 2026-03-25), registry.json (DANI skill inventory), HERMES test suite (1451 tests, 81% coverage).*
