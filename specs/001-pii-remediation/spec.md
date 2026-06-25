# Feature Specification: Remove personal PII from public repo docs

**Feature Branch**: `chore/sdd-adoption-spec-kit` (bootstrap exception — first SDD feature shares the SDD-adoption branch; future features use per-feature branches)

**Created**: 2026-05-26

**Status**: Draft

**Input**: First SDD feature for Amaru. Trigger: bilateral security audit (JEI/Bruja, 2026-05-19/25) flagged personal PII in the PUBLIC repo `dereyesm/amaru-protocol`, and an independent verification confirmed a personal email exposed in 4 tracked files. Enforces Constitution Principle I (No PII).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Personal email removed from all public docs (Priority: P1)

A visitor browsing the public repository (or a scraper) must not be able to harvest the maintainer's
personal email from any tracked file. The contact path for security or coordination uses neutral
channels instead.

**Why this priority**: The repo is PUBLIC. An exposed personal email is a live attack surface
(spam/phishing) and a Ley 1581 violation. This is the core of the audit finding.

**Independent Test**: `git grep -nI "[redacted]" -- '*.md' ':!CLAUDE.md'` returns **0**
results on the branch HEAD.

**Acceptance Scenarios**:

1. **Given** `SECURITY.md` listing a personal email as a reporting channel, **When** remediated, **Then** the reporting path is GitHub Security Advisories pointing at `dereyesm/amaru-protocol` (no personal email).
2. **Given** the two QUEST comms drafts with `From: <personal email>`, **When** remediated, **Then** the sender is a neutral clan reference with no email.
3. **Given** `docs/ecosystem/dani_roster.md` "Maintained by" line with a personal email, **When** remediated, **Then** the maintainer is identified by clan + public handle only.

---

### User Story 2 - Internal work-dimension references removed from public comms (Priority: P2)

Public comms must not leak internal dimension names (MomoshoD, MomoFinance, etc.), per the firewall
doctrine and Constitution Principle I.

**Why this priority**: Lower blast radius than an email (not directly harvestable for abuse) but still
an internal-structure leak the audit and firewall doctrine both flag.

**Independent Test**: `git grep -nI "MomoshoD\|MomoFinance" -- 'docs/comms/2026-03-15_QUEST-002_PING_JEI.md' 'docs/comms/2026-03-16_QUEST-003_KICKOFF_JEI.md'` returns 0.

**Acceptance Scenarios**:

1. **Given** comms text "send from MomoshoD or MomoFinance dimension", **When** remediated, **Then** the dimension reference is gone, replaced by a neutral bilateral-channel phrasing.

---

### Edge Cases

- `CLAUDE.md` contains the email but is **gitignored** (not tracked) — out of scope; verification excludes it.
- The maintainer's **name** ("Daniel Reyes") and **public GitHub handle** (`dereyesm`) are intentional OSS authorship/namespace and are **retained** (not PII to remediate).
- Git **history** still contains the email in past commits — see plan.md; history rewrite is a separate, human-approved decision, NOT part of this feature.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST contain zero occurrences of `[redacted]` in tracked files (excluding the gitignored `CLAUDE.md`).
- **FR-002**: `SECURITY.md` MUST provide a working vulnerability-reporting path via GitHub Security Advisories targeting `dereyesm/amaru-protocol` (fixing the stale `dereyesm/hermes` URL).
- **FR-003**: The two QUEST comms drafts MUST identify the sender without a personal email and without internal dimension names.
- **FR-004**: `docs/ecosystem/dani_roster.md` MUST identify the maintainer by clan + public handle, without a personal email.
- **FR-005**: No protocol behavior, spec content, or reference code is changed (docs-only remediation; Phase 0 untouched — Constitution Principle III).

### Key Entities

- **Personal email**: `[redacted]` — the primary PII to eliminate.
- **Internal dimensions**: MomoshoD, MomoFinance — internal-structure references to scrub from public comms.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `git grep -nI "[redacted]" -- '*.md' ':!CLAUDE.md'` → 0 results.
- **SC-002**: `git grep -nI "MomoshoD\|MomoFinance"` in the two remediated comms → 0 results.
- **SC-003**: Test suite stays green (no code touched): `reference/python/.venv/bin/python -m pytest`.
- **SC-004**: PR opened against `main`; CI green.

## Assumptions

- Name + public handle are acceptable in a public OSS repo and are retained (confirmed with Daniel this session).
- HEAD-only remediation is sufficient for this PR; git history rewrite is deferred to a separate human-approved decision coordinated with the JEI clan (collaborator on the repo).
- The bilateral security report's "repo is private" statement is inaccurate — the repo is PUBLIC, which raises (not lowers) urgency.
