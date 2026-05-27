<!--
Sync Impact Report
- Version change: (template) → 1.0.0
- Ratification: initial adoption (2026-05-26)
- Modified principles: n/a (first ratified version)
- Added principles: I. No PII / No Personal Data; II. English for Public Specs;
  III. Backward Compatible; IV. Reproducible Data; V. Lightweight First (YAGNI);
  VI. Human Approval
- Added sections: "Spec Methodology (ARC ↔ SDD)"; "Governance"
- Removed sections: none
- Templates requiring updates:
  - .specify/templates/plan-template.md ⚠ pending (Constitution Check gate references generic rules; align on next /speckit-plan)
  - .specify/templates/spec-template.md ✅ compatible (no mandatory section conflicts)
  - .specify/templates/tasks-template.md ✅ compatible
- Follow-up TODOs: none
-->

# Amaru Protocol Constitution

Open protocol for inter-agent AI communication (MIT). Public repo: `dereyesm/amaru-protocol`.
This constitution governs how features are designed, built, and shipped. It supersedes ad-hoc
practice. Every contributor and every automated agent operating on this repo MUST comply.

## Core Principles

### I. No PII / No Personal Data (NON-NEGOTIABLE)

No personal email, personal identifier, or internal work-dimension reference may appear in any
tracked file. The repository is PUBLIC: a leaked personal email is an attack surface (spam,
phishing, social engineering) and a violation of Colombian data-protection law (Ley 1581,
Arts. 5/6/17). Use neutral channels instead — GitHub Security Advisories for vulnerability
reports, and bilateral clan channels (e.g. "DANI clan — bilateral channel") for coordination.
Rationale: open-source reach means any exposed personal datum is permanently mirrored beyond
the maintainer's control.

### II. English for Public Specs

All public-facing specs and documentation MUST be written in English. Rationale: the audience is
global; the protocol aims for interoperability across clans and ecosystems.

### III. Backward Compatible (NON-NEGOTIABLE)

Phase 0 (JSONL file-based, sovereign/offline mode) MUST always work. No change may break
file-based operation or require a hosted hub to function. Rationale: sovereignty and offline
capability are core to the protocol's purpose; hosted mode is additive, never mandatory.

### IV. Reproducible Data

Benchmarks and empirical claims MUST use public datasets plus scripts committed to the repo.
No result is citable unless a reader can reproduce it from the repository. Rationale: protocol
credibility rests on independently verifiable measurements, not asserted numbers.

### V. Lightweight First (YAGNI)

Add complexity only when it reduces measurable overhead or removes a demonstrated failure mode.
Prefer the simplest mechanism that satisfies the spec. Rationale: a coordination protocol that
is heavier than the work it coordinates defeats its own purpose.

### VI. Human Approval (NON-NEGOTIABLE)

Daniel approves every spec and every push. No autonomous publishing, merging to `main`, or
release. Agents may prepare, draft, and stage; a human authorizes the irreversible step.
Rationale: outward-facing and irreversible actions require accountable human judgment.

## Spec Methodology (ARC ↔ SDD)

Two complementary spec tracks coexist; neither replaces the other.

- **ARC / ATR / AES standards** (`spec/`, RFC-style) define the formal protocol. Each new
  standard is designed via plan mode before drafting. This is the protocol's normative layer.
- **Spec-Driven Development** (spec-kit, `specs/`) governs CODE feature development under
  `reference/python/`. Use the `specify → plan → tasks → implement` workflow for implementation
  work that is not itself a protocol standard.

Rule of thumb: if the artifact defines wire behavior, semantics, or cryptography for other
clans to interoperate with → it is an ARC/ATR/AES. If it implements or changes the reference
code → it is an SDD feature.

## Governance

This constitution supersedes ad-hoc practice. All changes go through **branch + PR** per the
Clan Change Management protocol; no change reaches `main` without a PR (repo-owner exceptions
do not apply to PII or high-risk changes). Amendments require Daniel's approval and a version
bump:

- **MAJOR** — backward-incompatible removal or redefinition of a principle.
- **MINOR** — a new principle or materially expanded guidance.
- **PATCH** — clarifications, wording, non-semantic refinements.

Compliance review: every PR MUST verify it does not introduce PII (Principle I) and does not
break Phase 0 (Principle III). Complexity must be justified against Principle V.

**Version**: 1.0.0 | **Ratified**: 2026-05-26 | **Last Amended**: 2026-05-26
