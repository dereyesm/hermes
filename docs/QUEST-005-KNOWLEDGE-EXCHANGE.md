# QUEST-005: Bilateral Knowledge Exchange Protocol

| Field | Value |
|---|---|
| ID | QUEST-005 |
| Title | Bilateral Knowledge Exchange — Clan DANI x Clan JEI |
| Status | **PROPOSED** |
| Clans | momoshod, jei |
| Depends | QUEST-004 (baseline assessment), QUEST-003 Phase 2 (E2E channel) |
| Created | 2026-03-21 |
| Proposed by | JEI (Jeimmy Gomez) + DANI (Daniel Reyes) |

## Objective

Establish a structured, repeatable protocol for bilateral knowledge exchange
between HERMES clans. Each clan runs a sovereign assessment in its own
environment, exports a structured artifact (never raw data), and exchanges
findings via the encrypted relay. The result is a merged synthesis that captures:

1. **What we taught them** — practices from Clan DANI adopted by Clan JEI
2. **What they taught us** — practices from Clan JEI adopted by Clan DANI
3. **New anti-patterns discovered** — things neither should do
4. **New best practices discovered** — things both should do
5. **Cultural delta** — differences in approach that are valid in context

This is not a one-off assessment. It is the first instance of a **Knowledge
Exchange Protocol** designed to scale to N clans.

## Design Principles

1. **Sovereign execution** — Each clan runs the assessment locally. No clan
   accesses the other's environment, files, or configuration.
2. **Structured output** — The exchange artifact is a formal document with
   defined sections, not free text. This enables comparison, merge, and
   versioning across clans and over time.
3. **Security by design** — The prompt chain includes an output filter stage
   that strips paths, keys, credentials, and environment-specific data before
   export.
4. **Iterative scope** — Each exchange covers ONE knowledge domain per
   iteration. First iteration: **Prompt Engineering & Agent Orchestration**.
5. **E2E encrypted transit** — All artifacts transit via HERMES relay with
   ECDHE v3 encryption (proven in QUEST-003).

## Phase 1: Close QUEST-004 Baseline (Week of 2026-03-22)

QUEST-004 (Claude Code Best Practices Assessment) already exists with:
- DANI baseline: 71% (Advanced), 43 items, 14 categories
- JEI: self-assessment pending

**Actions:**
1. JEI completes self-assessment using existing QUEST-004 checklist
2. Both clans share scores via relay (encrypted)
3. Identify top-3 gaps per clan — these become input for Phase 2

**Output:** `QUEST-004-bilateral-scores.json` (encrypted, in relay)

## Phase 2: Prompt Chain Design (Week of 2026-03-24)

Design the sovereign prompt chain that each clan will execute locally.

### Prompt Chain Architecture

The chain has 5 stages, each producing a structured output:

```
Stage 1: INVENTORY
  "List your active skills/agents by category. For each, state:
   - Role (1 line)
   - Primary interaction pattern (direct/delegated/autonomous)
   - Maturity (prototype/stable/battle-tested)
   Do NOT include: file paths, API keys, internal config, or PII."

Stage 2: PRACTICE SCAN
  "For each category below, rate your clan 1-5 and provide one example:
   - Prompt engineering (clarity, chaining, context management)
   - Security practices (key management, access control, audit)
   - Agent orchestration (delegation, parallelism, error handling)
   - Knowledge management (memory, documentation, cross-session)
   - Testing & validation (coverage, regression, bilateral)
   Do NOT include: specific vulnerabilities, credential details, or paths."

Stage 3: PATTERN EXTRACTION
  "From Stages 1-2, identify:
   - Top 3 patterns that work well (with reasoning)
   - Top 3 anti-patterns discovered (with what went wrong)
   - 1 unconventional practice that others might find surprising"

Stage 4: OUTPUT FILTER (SECURITY GATE)
  "Review the Stage 1-3 outputs. Remove any:
   - Absolute file paths or directory structures
   - API keys, tokens, passwords, or credential references
   - Internal IP addresses or hostnames
   - PII (names beyond clan leads, emails, phone numbers)
   - Specific vulnerability descriptions that could be exploited
   Replace with [REDACTED:category] markers."

Stage 5: SYNTHESIS ARTIFACT
  "Compile Stages 1-4 into the Exchange Artifact format (see below).
   Sign with clan identity. Ready for encrypted relay transmission."
```

### Exchange Artifact Format

```json
{
  "quest": "QUEST-005",
  "clan": "<clan_id>",
  "domain": "prompt-engineering-and-orchestration",
  "version": "1.0",
  "ts": "<ISO 8601>",
  "inventory_summary": {
    "total_skills": 0,
    "by_category": {},
    "maturity_distribution": {}
  },
  "practice_scores": {
    "prompt_engineering": { "score": 0, "example": "" },
    "security": { "score": 0, "example": "" },
    "orchestration": { "score": 0, "example": "" },
    "knowledge_mgmt": { "score": 0, "example": "" },
    "testing": { "score": 0, "example": "" }
  },
  "patterns": {
    "top_practices": [],
    "anti_patterns": [],
    "unconventional": ""
  },
  "redactions": 0,
  "signed_by": "<clan_lead>"
}
```

## Phase 3: Sovereign Execution (Week of 2026-03-29)

Each clan runs the prompt chain in its own environment:

1. Clone the prompt chain template from HERMES repo
2. Execute stages 1-5 locally
3. Review output for security (Stage 4 gate)
4. Encrypt artifact with ECDHE and push to relay
5. Notify peer clan via relay message

**Output:** Two Exchange Artifacts in relay (one per clan, E2E encrypted)

## Phase 4: Bilateral Merge & Synthesis (Week of 2026-04-05)

Both clans decrypt each other's artifact and produce a **Merge Document**:

```
MERGE DOCUMENT — QUEST-005 Iteration 1
Domain: Prompt Engineering & Agent Orchestration

## What We Learned From Them
- [practice] — adopted because [reason]
- [practice] — noted but not adopted because [context difference]

## What We Taught Them
- [practice] — shared because [reason]

## New Anti-Patterns Discovered
- [pattern] — discovered through comparison, neither clan had identified alone

## New Best Practices Discovered
- [pattern] — emerged from the delta between clan approaches

## Cultural Delta (Valid Differences)
- [difference] — valid because [different context/goals/constraints]

## Next Domain Proposal
- Suggested domain for Iteration 2: [...]
```

The merge document is signed by both clans and stored in the HERMES repo
as a public reference (with consent).

## Phase 5: Protocol Formalization (ARC/ATR)

If the bilateral exchange succeeds, formalize the pattern as:
- **ATR-KEP-001**: Knowledge Exchange Protocol — Technical Report
- Defines the prompt chain template, artifact format, merge process
- Replicable by any HERMES clan pair without modification

## Timeline

| Phase | Target | Owner | Status |
|---|---|---|---|
| Phase 1: QUEST-004 close | 2026-03-22 — 2026-03-28 | Both clans | Pending |
| Phase 2: Prompt chain design | 2026-03-24 — 2026-03-31 | DANI (lead) | Pending |
| Phase 3: Sovereign execution | 2026-03-29 — 2026-04-05 | Each clan | Pending |
| Phase 4: Bilateral merge | 2026-04-05 — 2026-04-12 | Both clans | Pending |
| Phase 5: ATR formalization | 2026-04-12 — 2026-04-19 | DANI (lead) | Pending |

## Security Considerations

### What Crosses the Relay
- Structured artifacts with redacted specifics
- Practice scores (1-5 scale, not implementation details)
- Pattern descriptions (conceptual, not code-level)
- Signed merge documents (public, with consent)

### What NEVER Crosses the Relay
- File paths, directory structures, or system configuration
- API keys, tokens, credentials, or secrets
- Specific vulnerability descriptions
- Raw skill definitions or SKILL.md contents
- PII beyond clan lead names

### Output Filter (Stage 4)
The prompt chain includes a mandatory security gate. Each clan reviews
their own output before encryption. The gate uses `[REDACTED:category]`
markers so the receiving clan knows something was filtered without
knowing the content.

## Success Criteria

1. Both clans complete sovereign execution without security incidents
2. Each clan identifies at least 2 actionable practices from the other
3. The merge document is signed by both clans
4. The process is documented well enough for a third clan to replicate
5. ATR-KEP-001 is published in the HERMES spec index

## References

- QUEST-004: Claude Code Best Practices Assessment (baseline)
- QUEST-003: ECDHE Forward Secrecy (transport layer)
- ARC-8446: Cryptographic Envelope (encryption)
- ARC-5322: Message Format (wire format)
