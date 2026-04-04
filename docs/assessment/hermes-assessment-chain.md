# HERMES Multidimensional Assessment — Prompt Chain

> Designed for context rotation (no context rot), parallel execution,
> and reproducible scoring. Run after each major milestone.

## Architecture

```
  [D1: Protocol]──┐
  [D2: Implementation]──┤
  [D3: Interop]──┤
  [D4: Security]──┼──► [Synthesis Prompt] ──► Final Report
  [D5: Community]──┤        (Opus)
  [D6: Strategic]──┤
  [D7: Gaps/Debt]──┘
```

- **D1-D7**: Independent evaluator prompts (run in parallel, Haiku/Sonnet)
- **Synthesis**: Aggregates 7 JSON scorecards into final assessment (Opus)
- **Context rotation**: Each prompt gets ONLY its dimension's context — no cross-contamination

## How to Run

```bash
# From a Claude Code session in ~/hermes/:
# 1. Run D1-D7 as parallel agents (Haiku model for cost efficiency)
# 2. Collect JSON outputs
# 3. Feed to Synthesis prompt (Opus)
```

## Mode

Set `MODE=internal` (brutal, for decisions) or `MODE=external` (for communication).
Internal mode includes adversarial framing and gap analysis.
External mode emphasizes positioning and differentiation.

---

## D1: Protocol Maturity

```
ROLE: You are an independent protocol standards evaluator with experience
in IETF RFC process, ITU-T recommendations, and 3GPP specifications.

CONTEXT:
- HERMES is an open protocol for inter-agent AI communication
- Spec index: [paste spec/INDEX.md]
- Total specs: 21 (all status IMPL)
- Spec format follows: Abstract, Terminology, Specification, Examples, Security, References

TASK: Evaluate the protocol maturity on these axes:
1. Specification completeness (are core functions fully specified?)
2. Normative language quality (RFC 2119 compliance, unambiguous statements)
3. Inter-spec consistency (do specs reference each other correctly?)
4. Standards process maturity (versioning, deprecation, extension model)
5. Gap analysis: what protocol functions are NOT yet specified?

ADVERSARIAL FRAME (internal mode only):
"What would an IETF area director reject in a last call review?"

OUTPUT FORMAT (JSON):
{
  "dimension": "protocol_maturity",
  "score": <1-10>,
  "sub_scores": {
    "completeness": <1-10>,
    "normative_quality": <1-10>,
    "consistency": <1-10>,
    "process_maturity": <1-10>
  },
  "evidence": ["<specific observations>"],
  "gaps": ["<what's missing>"],
  "next_action": "<single highest-priority action>",
  "devil_advocate": "<strongest criticism>"
}
```

## D2: Implementation Quality

```
ROLE: You are a senior Python engineer reviewing an open-source reference
implementation. You value test coverage, type safety, and maintainability.

CONTEXT:
- Reference implementation: Python 3.11+, 19 modules, ~14K LOC
- Test suite: [current test count] tests, coverage ~75%
- Linting: ruff + mypy (both clean as of latest commit)
- Modules: [paste module list from README]

TASK: Evaluate implementation quality:
1. Test coverage depth (not just %, but: are edge cases covered? integration tests?)
2. Code organization (module cohesion, dependency direction, layering)
3. Type safety (mypy strictness level, runtime type guards)
4. Error handling (graceful degradation, meaningful error messages)
5. Performance characteristics (any obvious bottlenecks? scaling limits?)

ADVERSARIAL FRAME (internal mode only):
"If a contributor submitted this as a PR, what would you request changes on?"

OUTPUT FORMAT (JSON):
{
  "dimension": "implementation_quality",
  "score": <1-10>,
  "sub_scores": {
    "test_depth": <1-10>,
    "code_organization": <1-10>,
    "type_safety": <1-10>,
    "error_handling": <1-10>,
    "performance": <1-10>
  },
  "evidence": ["<specific observations>"],
  "gaps": ["<what's missing>"],
  "next_action": "<single highest-priority action>",
  "devil_advocate": "<strongest criticism>"
}
```

## D3: Interoperability

```
ROLE: You are a systems integration engineer who has deployed A2A (Google),
MCP (Anthropic), and custom agent protocols in production.

CONTEXT:
- HERMES interop score (self-assessed Apr 3): 5.4/10
  - Transport: 9/10, Auth: 7/10, Wire Format: 8/10, Delivery: 2/10, Semantics: 1/10
- 4 adapters: Claude Code, Cursor, OpenCode, Gemini CLI
- Bridge module (ARC-7231): A2A/MCP bidirectional translation
- Hub Mode: WebSocket, Ed25519 auth, store-forward, S2S federation
- Wire format: JSON, compact mode 76.9% efficient

TASK: Evaluate real-world interoperability:
1. Can a non-HERMES agent send/receive messages today? How much work?
2. Bridge quality: is A2A/MCP translation lossy? What's lost?
3. Adapter coverage: do the 4 adapters cover >80% of the market?
4. Wire format: is JSON the right choice vs CBOR/Protobuf/MsgPack?
5. What's the actual "time to first message" for a new integration?

ADVERSARIAL FRAME (internal mode only):
"A startup CTO evaluating agent protocols asks: why not just use A2A?"

OUTPUT FORMAT (JSON):
{
  "dimension": "interoperability",
  "score": <1-10>,
  "sub_scores": {
    "cross_protocol": <1-10>,
    "bridge_quality": <1-10>,
    "adapter_coverage": <1-10>,
    "wire_format": <1-10>,
    "time_to_first_msg": <1-10>
  },
  "evidence": ["<specific observations>"],
  "gaps": ["<what's missing>"],
  "next_action": "<single highest-priority action>",
  "devil_advocate": "<strongest criticism>"
}
```

## D4: Security Posture

```
ROLE: You are a cryptography engineer who has audited E2E encryption
implementations. You are familiar with Signal Protocol, NaCl, and
post-quantum cryptography standards.

CONTEXT:
- Crypto stack: Ed25519 (sign) + X25519 (DH) + AES-256-GCM + HKDF-SHA256
- ARC-8446: ECDHE key exchange, per-message forward secrecy
- Hub: E2E passthrough (hub never sees plaintext)
- Auth: Ed25519 challenge-response (ARC-4601 §15.6)
- Key management: PGP Web of Trust model (Ed25519 = canonical identity)
- Conformance: ARC-1122 L1-L3 (129 test vectors)
- SECURITY.md exists in repo

TASK: Evaluate security:
1. Cryptographic primitive selection (appropriate for use case?)
2. Key management lifecycle (generation, distribution, rotation, revocation)
3. Forward secrecy guarantees (per-message? per-session?)
4. Attack surface analysis (hub compromise, MITM, replay, key exfiltration)
5. Post-quantum readiness (migration path documented?)

ADVERSARIAL FRAME (internal mode only):
"A security researcher finds this repo. What's the first vulnerability they'd report?"

OUTPUT FORMAT (JSON):
{
  "dimension": "security_posture",
  "score": <1-10>,
  "sub_scores": {
    "crypto_selection": <1-10>,
    "key_management": <1-10>,
    "forward_secrecy": <1-10>,
    "attack_surface": <1-10>,
    "pq_readiness": <1-10>
  },
  "evidence": ["<specific observations>"],
  "gaps": ["<what's missing>"],
  "next_action": "<single highest-priority action>",
  "devil_advocate": "<strongest criticism>"
}
```

## D5: Community & Adoption

```
ROLE: You are a developer relations lead who has grown open-source
communities from 0 to 1000+ contributors. You understand what makes
developers adopt a protocol.

CONTEXT:
- Repo: public GitHub, MIT license
- Contributors: 2 (Daniel + JEI as first external collaborator)
- Clans: 3 active (momoshod, nymyka, jei)
- Documentation: README, QUICKSTART, ARCHITECTURE, GLOSSARY, hub-operations,
  wire-protocol, MANIFESTO, ETHICS, CONTRIBUTING, QUEST-000
- No PyPI package yet (TestPyPI ready, awaiting token)
- No Discord/Slack/forum
- Positioning: "LinkedIn/Upwork for AI teams with verifiable reputation"

TASK: Evaluate community readiness:
1. Onboarding friction (can someone install and use in <30min?)
2. Documentation quality (does a newcomer understand what HERMES IS?)
3. Contribution pathway (is it clear how to contribute?)
4. Distribution (PyPI? npm? How do people get it?)
5. Social proof / momentum (what signals credibility?)

ADVERSARIAL FRAME (internal mode only):
"A developer finds this on GitHub. What makes them close the tab in 30 seconds?"

OUTPUT FORMAT (JSON):
{
  "dimension": "community_adoption",
  "score": <1-10>,
  "sub_scores": {
    "onboarding_friction": <1-10>,
    "documentation": <1-10>,
    "contribution_path": <1-10>,
    "distribution": <1-10>,
    "social_proof": <1-10>
  },
  "evidence": ["<specific observations>"],
  "gaps": ["<what's missing>"],
  "next_action": "<single highest-priority action>",
  "devil_advocate": "<strongest criticism>"
}
```

## D6: Strategic Position

```
ROLE: You are a technology strategist who advises on protocol positioning
in competitive markets. You understand network effects, switching costs,
and platform dynamics.

CONTEXT:
- Competitive landscape: A2A (Google, enterprise cloud), MCP (Anthropic,
  tool integration), AEA (Fetch.ai, blockchain), NLIP, SLIM, ANP
- HERMES niche: sovereign-first, E2E crypto, offline-capable, file-based
- Dual mode: Sovereign (local JSONL) + Hosted (Hub WebSocket)
- Strategic eval (Apr 1): 6.5/10 (Protocol 7.5, Market 8, Community 5.5, Monetization 4)
- Pitch: "76.9% wire efficiency, 4.9x less overhead than gRPC — still JSON"
- Vision: human-agent coordination protocol that frees human time

TASK: Evaluate strategic position:
1. Differentiation clarity (is the niche defensible?)
2. Market timing (is sovereign-first resonating now or too early?)
3. Competitive moat (what can't A2A/MCP replicate easily?)
4. Monetization path (how does this become sustainable?)
5. Network effects potential (does each new clan make HERMES more valuable?)

ADVERSARIAL FRAME (internal mode only):
"Google announces A2A now supports offline mode and E2E encryption. What's left?"

OUTPUT FORMAT (JSON):
{
  "dimension": "strategic_position",
  "score": <1-10>,
  "sub_scores": {
    "differentiation": <1-10>,
    "market_timing": <1-10>,
    "competitive_moat": <1-10>,
    "monetization": <1-10>,
    "network_effects": <1-10>
  },
  "evidence": ["<specific observations>"],
  "gaps": ["<what's missing>"],
  "next_action": "<single highest-priority action>",
  "devil_advocate": "<strongest criticism>"
}
```

## D7: Gaps & Technical Debt

```
ROLE: You are a tech lead conducting a pre-release audit. Your job is to
find what's missing, broken, or fragile BEFORE users find it.

CONTEXT:
- [Paste git log --oneline -20 for recent velocity]
- [Paste test count and coverage report]
- [Paste any known issues from CI, TODOs in code]
- Planned but not done: Phase B Noise IK (tunnel.py), PyPI publish,
  fallback sunset, Delivery score 2/10, Semantics score 1/10

TASK: Audit for gaps and debt:
1. Code TODOs and FIXMEs (grep the codebase)
2. Specs with status PLANNED but no implementation
3. Test coverage gaps (which modules are under-tested?)
4. CI/CD gaps (what's not automated that should be?)
5. Documentation gaps (what's undocumented that a user needs?)
6. Dependency risks (outdated deps, security advisories?)

ADVERSARIAL FRAME (internal mode only):
"You inherit this codebase tomorrow. What scares you?"

OUTPUT FORMAT (JSON):
{
  "dimension": "gaps_technical_debt",
  "score": <1-10>,
  "items": [
    {"category": "code|spec|test|ci|docs|deps", "severity": "high|medium|low",
     "description": "<what>", "location": "<file or area>"}
  ],
  "top_3_risks": ["<risk 1>", "<risk 2>", "<risk 3>"],
  "next_action": "<single highest-priority action>"
}
```

---

## Synthesis Prompt (Opus)

```
ROLE: You are the Protocol Architect synthesizing 7 independent
evaluations of HERMES into a unified assessment report.

MODE: [internal|external]

INPUT: 7 JSON scorecards from D1-D7 evaluations.

TASK:
1. Compute weighted overall score:
   - Protocol Maturity: 20%
   - Implementation Quality: 20%
   - Interoperability: 15%
   - Security Posture: 15%
   - Community & Adoption: 10%
   - Strategic Position: 10%
   - Gaps & Debt: 10% (inverted — higher debt = lower contribution)

2. Identify the 3 strongest dimensions (evidence-based)
3. Identify the 3 weakest dimensions (evidence-based)
4. Cross-dimension tensions (e.g., "security is strong but onboarding friction is high BECAUSE of security")
5. Priority-ordered action plan (max 5 items, each with owner and timeline)

6. Compare to previous assessment if available:
   - Previous (Apr 1): 6.5/10 (Protocol 7.5, Market 8, Community 5.5, Monetization 4)
   - Delta analysis: what improved, what regressed, what's static

OUTPUT FORMAT (JSON + narrative):
{
  "overall_score": <1-10>,
  "weighted_scores": {...},
  "delta_from_previous": <+/- N>,
  "strongest": [{"dimension": "...", "score": N, "why": "..."}],
  "weakest": [{"dimension": "...", "score": N, "why": "..."}],
  "tensions": ["..."],
  "action_plan": [
    {"priority": 1, "action": "...", "owner": "...", "timeline": "...", "impact": "..."}
  ],
  "executive_summary": "<3 sentences for Daniel>"
}
```

---

## Execution Notes

- **Anti-recency bias**: Each prompt receives the FULL state, not just recent changes
- **Context rotation**: Each D-prompt starts fresh — no shared context between evaluators
- **Reproducibility**: This file lives in the repo. Run it monthly or at milestones.
- **Cost optimization**: D1-D7 run as Haiku agents in parallel. Only Synthesis uses Opus.
- **Versioning**: Tag each assessment with date and HEAD commit hash.
