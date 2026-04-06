# QUEST-005: Knowledge Exchange — Prompt Chain Template v1.0

> Executable template for bilateral knowledge exchange between Amaru clans.
> Domain: Prompt Engineering & Agent Orchestration (Iteration 1).

## Instructions

1. Copy this file to your local workspace
2. Execute each stage sequentially in a Claude Code session
3. Review Stage 4 output (security gate) before proceeding to Stage 5
4. Encrypt the final artifact and push to relay

**Time estimate:** 30-45 minutes per clan

---

## Stage 1: INVENTORY

```
List your active skills/agents by category. For each, state:
- Name
- Role (1 line)
- Primary interaction pattern (direct/delegated/autonomous)
- Maturity (prototype/stable/battle-tested)

Output as a table. Do NOT include: file paths, API keys, internal config, or PII.
Summarize: total count, by-category breakdown, maturity distribution.
```

**Expected output:** Table of skills + summary stats.

---

## Stage 2: PRACTICE SCAN

```
For each category below, rate your clan 1-5 and provide ONE concrete example:

1. Prompt engineering (clarity, chaining, context management)
2. Security practices (key management, access control, audit)
3. Agent orchestration (delegation, parallelism, error handling)
4. Knowledge management (memory, documentation, cross-session persistence)
5. Testing & validation (coverage, regression detection, bilateral verification)

Scale: 1=not started, 2=basic, 3=functional, 4=mature, 5=exemplary

Do NOT include: specific vulnerabilities, credential details, or file paths.
```

**Expected output:** 5 categories with score + example each.

---

## Stage 3: PATTERN EXTRACTION

```
From Stages 1-2, identify:

1. Top 3 patterns that work well (with reasoning why they work)
2. Top 3 anti-patterns discovered (with what went wrong)
3. 1 unconventional practice that others might find surprising

For each, explain the context in which it applies. Patterns without
context are not transferable.
```

**Expected output:** 7 items with reasoning.

---

## Stage 4: OUTPUT FILTER (SECURITY GATE)

```
Review the Stage 1-3 outputs. Remove any:

- Absolute file paths or directory structures
- API keys, tokens, passwords, or credential references
- Internal IP addresses, hostnames, or URLs
- PII (names beyond clan leads, emails, phone numbers)
- Specific vulnerability descriptions that could be exploited
- Internal configuration values (ports, database names, etc.)

Replace each removal with [REDACTED:category] markers.
Report the total count of redactions by category.

This stage is MANDATORY. Do not skip it.
```

**Expected output:** Sanitized Stages 1-3 + redaction count.

---

## Stage 5: SYNTHESIS ARTIFACT

```
Compile Stages 1-4 into the following JSON structure.
Sign with your clan identity (clan_id + lead name).

{
  "quest": "QUEST-005",
  "iteration": 1,
  "domain": "prompt-engineering-and-orchestration",
  "clan": "<your_clan_id>",
  "version": "1.0",
  "ts": "<ISO 8601 timestamp>",
  "inventory_summary": {
    "total_skills": <int>,
    "by_category": { "<category>": <count>, ... },
    "maturity_distribution": { "prototype": <n>, "stable": <n>, "battle-tested": <n> }
  },
  "practice_scores": {
    "prompt_engineering": { "score": <1-5>, "example": "<sanitized>" },
    "security": { "score": <1-5>, "example": "<sanitized>" },
    "orchestration": { "score": <1-5>, "example": "<sanitized>" },
    "knowledge_mgmt": { "score": <1-5>, "example": "<sanitized>" },
    "testing": { "score": <1-5>, "example": "<sanitized>" }
  },
  "patterns": {
    "top_practices": ["<pattern 1>", "<pattern 2>", "<pattern 3>"],
    "anti_patterns": ["<anti-pattern 1>", "<anti-pattern 2>", "<anti-pattern 3>"],
    "unconventional": "<surprising practice>"
  },
  "redactions": <total_count>,
  "signed_by": "<clan_lead_name>"
}
```

**Expected output:** JSON artifact ready for encryption and relay.

---

## After Completion

1. Encrypt the JSON artifact with peer clan's public key (ECDHE)
2. Push to HERMES relay as `quest005_artifact` message type
3. Notify peer clan that artifact is ready
4. Wait for peer clan's artifact
5. Proceed to Phase 4 (Bilateral Merge) when both artifacts are available

## Security Checklist

Before encrypting, verify:
- [ ] No file paths in output
- [ ] No API keys or credentials
- [ ] No internal URLs or IPs
- [ ] No PII beyond clan lead name
- [ ] Redaction count matches actual removals
- [ ] JSON is valid and parseable

---

*Template version 1.0 — QUEST-005 Knowledge Exchange Protocol*
*Created by Clan DANI (momoshod) for bilateral use with Clan JEI*
