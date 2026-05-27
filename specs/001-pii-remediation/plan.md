# Implementation Plan: Remove personal PII from public repo docs

**Spec**: `specs/001-pii-remediation/spec.md` | **Branch**: `chore/sdd-adoption-spec-kit`

## Constitution Check

- **I. No PII** — this feature directly enforces it. ✅ (drives the work)
- **II. English** — all edits in English. ✅
- **III. Backward Compatible** — docs-only; no code, no spec, no wire change; Phase 0 untouched. ✅
- **V. Lightweight** — minimal edits (4 files), no new mechanism. ✅
- **VI. Human Approval** — push to public `main` gated on Daniel's explicit approval. ✅

No violations. No complexity to justify.

## Approach

Docs-only string remediation, one edit per occurrence, preserving surrounding meaning. Replacement
conventions:

| File | Current | Replacement |
|------|---------|-------------|
| `SECURITY.md:31-32` | `1. Email: [redacted] ...` + `2. ... dereyesm/hermes/.../advisories/new` | Single channel: **GitHub Security Advisories** at `dereyesm/amaru-protocol/security/advisories/new` (drop personal-email line; fix stale repo slug) |
| `docs/comms/2026-03-15_QUEST-002_PING_JEI.md:20` | `**From**: [redacted] (send from MomoshoD or MomoFinance dimension)` | `**From**: DANI clan (bilateral channel)` |
| `docs/comms/2026-03-16_QUEST-003_KICKOFF_JEI.md:5` | `\| From \| [redacted] (via MomoshoD) \|` | `\| From \| DANI clan (bilateral channel) \|` |
| `docs/ecosystem/dani_roster.md:101` | `**Maintained by**: Daniel Reyes (DANI) — [redacted] / @dereyesm` | `**Maintained by**: DANI clan — @dereyesm (contact via GitHub Security Advisories)` |

Retained intentionally: name "Daniel Reyes" elsewhere, handle `@dereyesm` (public namespace).

## Out of scope (separate, human-approved)

- **Git history rewrite** (`git filter-repo`) to purge the email from past commits. Destructive,
  breaks clones, requires coordination with JEI (repo collaborator). Decision deferred to Daniel.
- Broader audit of all 46 files matching name/handle — name+handle are acceptable; only email +
  internal dimensions are in scope here.

## Phasing

1. Edit the 4 files per the table.
2. Verify SC-001..SC-004.
3. Commit (Conventional Commits, Directed-By footer).
4. Open PR to `main` (push pending Daniel approval).
