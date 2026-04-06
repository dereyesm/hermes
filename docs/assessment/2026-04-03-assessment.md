# HERMES Assessment — 2026-04-03

> HEAD: 3a69981 | Mode: internal | Evaluators: 7 parallel (Haiku) + synthesis (Opus)

## Overall: 6.83/10 (delta +0.33 from 6.5 on Apr 1)

## Scorecards

| # | Dimension | Score | Weight | Weighted | Strongest Sub | Weakest Sub |
|---|-----------|-------|--------|----------|---------------|-------------|
| D1 | Protocol Maturity | 7.2 | 20% | 1.44 | Completeness 8.1 | Process maturity 6.2 |
| D2 | Implementation Quality | 7.6 | 20% | 1.52 | Test depth 8.2 | Performance 6.5 |
| D3 | Interoperability | 5.4 | 15% | 0.81 | Wire format 8.0 | Time-to-first-msg 4.0 |
| D4 | Security Posture | 7.2 | 15% | 1.08 | Crypto selection 8.5 | PQ readiness 5.0 |
| D5 | Community & Adoption | 6.2 | 10% | 0.62 | Documentation 8.0 | Social proof 4.0 |
| D6 | Strategic Position | 6.8 | 10% | 0.68 | Differentiation 8.2 | Monetization 4.8 |
| D7 | Gaps & Tech Debt | 6.8 | 10% | 0.68 | — | Hub/agent 52% cov |

## Sub-Scores Detail

### D1: Protocol Maturity (7.2)
- Completeness: 8.1 — 16/21 specs IMPL, core protocol fully specified
- Normative quality: 7.8 — RFC 2119 compliant, 968 normative statements
- Consistency: 6.9 — Cross-referencing sparse, some circular deps (ARC-0020)
- Process maturity: 6.2 — No formal Last-Call, no extension registry, no versioning scheme

### D2: Implementation Quality (7.6)
- Test depth: 8.2 — 1507 tests, good breadth, edge cases covered for core modules
- Code organization: 7.8 — Clean separation, 19 modules well-layered
- Type safety: 7.5 — mypy clean, proper dataclass usage
- Error handling: 7.0 — Graceful degradation but 11 broad `except Exception:` blocks
- Performance: 6.5 — Sequential broadcast, no idle timeout, scaling untested

### D3: Interoperability (5.4)
- Cross-protocol: 6.0 — Bridge exists (A2A/MCP) but lossy translation
- Bridge quality: 5.0 — Metadata lost in both directions
- Adapter coverage: 7.0 — 4 adapters (~40% market), missing LangChain/AutoGen
- Wire format: 8.0 — JSON 76.9% efficient, human-readable, backward compatible
- Time-to-first-msg: 4.0 — ~1-2h without adapters, pip install 404

### D4: Security Posture (7.2)
- Crypto selection: 8.5 — Ed25519+X25519+AES-256-GCM+HKDF, TLS 1.3 aligned
- Key management: 7.0 — TOFU model, 0o600 perms, but no at-rest encryption
- Forward secrecy: 8.5 — Per-message ECDHE, AAD binding, nonce tracking
- Attack surface: 6.5 — Hub E2E passthrough good, but Python can't securely zeroize
- PQ readiness: 5.0 — Migration path mentioned (FIPS 203-205), not implemented

### D5: Community & Adoption (6.2)
- Onboarding friction: 6.5 — `amaru install` works but pip 404, no video demo
- Documentation: 8.0 — 30+ docs, comprehensive specs, architecture guides
- Contribution path: 7.0 — CONTRIBUTING.md with ARC proposal template
- Distribution: 4.5 — No PyPI, no npm, GitHub clone only
- Social proof: 4.0 — 0 stars, 0 external mentions, 2 contributors

### D6: Strategic Position (6.8)
- Differentiation: 8.2 — Sovereign-first + E2E + file-based genuinely unique
- Market timing: 7.1 — Agentic orgs validated (McKinsey), but crowded market
- Competitive moat: 6.5 — Compound (sovereign+crypto+gateway) but each piece replicable
- Monetization: 4.8 — Sovereign = free by design, no revenue path defined
- Network effects: 6.5 — 3 clans, fragile, zero switching costs

### D7: Gaps & Technical Debt (6.8)
- Critical: hub.py 52%, agent.py 52%, cli.py 55% coverage
- Critical: 11 broad `except Exception:` swallowing errors silently
- High: Tier 1 deps unpinned (anthropic, google-genai, mcp)
- Medium: 8 planned specs unwritten (lifecycle, discovery, JWT auth)
- Medium: No pip-audit in CI pipeline

## Top 3 Strengths
1. **Differentiation (8.2)** — Sovereign-first + E2E crypto + file-based bus. No competitor has SMTP-like dual-mode.
2. **Crypto Selection (8.5)** — Per-message forward secrecy, verify-before-decrypt, AAD binding. Production-grade primitives.
3. **Documentation (8.0)** — 30+ docs with IETF-grade spec rigor. Wire protocol guide eliminates 1-2h coordination per new clan.

## Top 3 Weaknesses
1. **Social Proof (4.0)** — 0 stars, 0 PyPI, 0 community channels. Invisible to the world.
2. **Time-to-first-msg (4.0)** — pip install 404. No quick demo. ~1-2h bootstrap.
3. **Monetization (4.8)** — No revenue path. Sovereign mode free by design.

## Cross-Dimension Tensions
- Security (7.2) vs Onboarding (6.5): E2E crypto adds key exchange friction
- Protocol Rigor (7.2) vs Accessibility (6.2): 620 MUST statements intimidate newcomers
- Sovereignty vs Network Effects: Zero lock-in = zero switching costs = fragile adoption

## Priority Action Plan
| # | Action | Owner | Timeline | Impact |
|---|--------|-------|----------|--------|
| 1 | PyPI publish (0.4.2a1) | Daniel (token needed) | Apr 5 | Unblocks 80% adoption friction |
| 2 | Pin Tier 1 deps (==) + pip-audit CI | Protocol Architect | Apr 5 | Supply chain hygiene |
| 3 | JEI pub key + hub.py migration | JEI (external) | Apr 12 | Completes S2S bilateral |
| 4 | Hub/agent test hardening (+80 tests) | Protocol Architect | Apr 12 | Production confidence |
| 5 | Asciinema demo + visibility push | Daniel + Community | Apr 19 | Social proof 0→1 |

## Devil's Advocate (strongest criticism per dimension)
- **D1**: IETF would reject: no versioning scheme, no extension registry, MUST inflation (620 > TCP's 40)
- **D2**: Hub/agent at 52% coverage = untested crash/recovery paths in production code
- **D3**: "Why not just use A2A?" — A2A has structured tasks, streaming, Google backing
- **D4**: Plaintext private keys on disk + Python can't securely zeroize ephemeral keys
- **D5**: Developer finds repo, tries `pip install amaru-protocol`, gets 404, closes tab
- **D6**: Google adds offline+E2E to A2A at I/O 2026 → HERMES loses differentiators
- **D7**: Inherit codebase tomorrow: 11 silent exception swallowers + 52% hub coverage = scary

## Comparison to Previous Assessment

| Dimension | Apr 1 | Apr 3 | Delta | Reason |
|-----------|-------|-------|-------|--------|
| Protocol | 7.5 | 7.2 | -0.3 | More rigorous evaluation exposed gaps (versioning, extension registry) |
| Implementation | — | 7.6 | new | First detailed code quality assessment |
| Interop | — | 5.4 | — | Confirmed self-assessment from Apr 3 |
| Security | — | 7.2 | new | First crypto audit |
| Community | 5.5 | 6.2 | +0.7 | Hub docs, wire protocol guide, QUICKSTART update |
| Strategic | 8.0→6.5 | 6.8 | +0.3 | S2S federation + bilateral proof strengthened position |
| Gaps | — | 6.8 | new | First formal debt audit |
| **Overall** | **6.5** | **6.83** | **+0.33** | Real progress on infra, identified clear action items |
