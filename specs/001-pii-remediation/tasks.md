# Tasks: Remove personal PII from public repo docs

**Spec**: `spec.md` | **Plan**: `plan.md` | **Branch**: `chore/sdd-adoption-spec-kit`

## Phase 1 — Remediation (User Story 1, P1 + User Story 2, P2)

- [ ] **T001** [US1] `SECURITY.md` — remove the personal-email reporting line; make GitHub Security Advisories the reporting channel; fix stale `dereyesm/hermes` → `dereyesm/amaru-protocol`.
- [ ] **T002** [US1] `docs/comms/2026-03-15_QUEST-002_PING_JEI.md:20` — replace `From` with neutral clan/bilateral reference (also removes MomoshoD/MomoFinance — US2).
- [ ] **T003** [US1] `docs/comms/2026-03-16_QUEST-003_KICKOFF_JEI.md:5` — replace `From` table cell with neutral clan/bilateral reference (also removes MomoshoD — US2).
- [ ] **T004** [US1] `docs/ecosystem/dani_roster.md:101` — replace "Maintained by" line: drop personal email, keep clan + `@dereyesm`.

## Phase 2 — Verification

- [ ] **T005** SC-001: `git grep -nI "[redacted]" -- '*.md' ':!CLAUDE.md'` → 0 results.
- [ ] **T006** SC-002: `git grep -nI "MomoshoD\|MomoFinance"` in the 2 remediated comms → 0 results.
- [ ] **T007** SC-003: `reference/python/.venv/bin/python -m pytest` green (no code touched).

## Phase 3 — Delivery

- [ ] **T008** Commit (Conventional Commits + Directed-By footer): scaffolding/constitution + PII remediation.
- [ ] **T009** Open PR to `main`. **Push pending Daniel approval** (Constitution Principle VI).

## Dependencies

- T001–T004 independent (parallelizable).
- T005–T007 after T001–T004.
- T008 after T005–T007 green. T009 after T008.
