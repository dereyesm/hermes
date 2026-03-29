# Protocol Architect — Experiencia Codificada

> Patrones aprendidos en batalla. Este archivo es la memoria operativa del skill.
> Se actualiza al cierre de sesion cuando hay nuevos patrones confirmados (3+ ocurrencias).
> El SKILL.md define QUE hace Protocol Architect. Este archivo define COMO lo hace bien.

## Ultima actualizacion: 2026-03-28
## Fuente: 20 specs, 1146 tests, 5 QUESTs, 10 Arena sessions (643.5 XP)

---

## 1. Heuristicas (atajos decisionales probados)

### Spec design workflow (>95% first-draft approval)

| Decision | Heuristica | Confianza | Nota |
|----------|-----------|-----------|------|
| New spec scope | 1 ARC = 1 concern. Si cubre 2 concerns, split | 100% | ARC-9001 (integrity) separado de ARC-0369 (ASP) — confirmed correct split |
| Field addition to Message | Verbose JSON only, compact unchanged | 100% | seq field, w field — performance preserved for hot path |
| New module vs extend existing | <300 lines related code → same module. >300 or different concern → new module | 90% | integrity.py (F1-F2 ~270 lines) is at boundary |
| Backward compat | All new params default=None. Messages without new fields always valid | 100% | Zero callers break pattern, confirmed across 4 spec additions |
| Test count heuristic | ~10 tests per new class, ~5 per significant method | 90% | Confirmed: 163 tests for F1-F2+F4-F5 (5 new classes) |

### Crypto decisions (ARC-8446 lineage)

| Decision | Heuristica | Confianza | Nota |
|----------|-----------|-----------|------|
| Key type selection | Ed25519 (sign) + X25519 (DH) + AES-256-GCM (encrypt) | 100% | Battle-tested combo, matches Signal Protocol choices |
| ECDHE per-message | Single ephemeral DH, not double ratchet | 95% | Sufficient for async bus; double ratchet adds complexity without benefit for file-based |
| HKDF info string | Include protocol version in info | 100% | v3 divergence with JEI proved this matters — `ECDHE-v1` vs `v3-ECDHE` |
| AAD scope | Always include eph_pub in AAD | 100% | Prevents ephemeral key substitution attack. JEI v3 divergence: they omitted it |
| Signature scope | Sign `ciphertext || eph_pub` (TLS 1.3 order) | 100% | JEI used `eph_pub || ciphertext` — converging to TLS 1.3 convention |
| Compact sealed format | Array length determines type: 5=static, 6=ECDHE | 100% | Auto-detection without type field — elegant, proven in production |

### Module architecture

| Decision | Heuristica | Confianza | Nota |
|----------|-----------|-----------|------|
| Return values from write functions | Always return the written object (Message, ConflictRecord) | 100% | write_message() changed None→Message in 2026-03-20, no callers broke |
| Integration wiring in agent.py | Init in `_init_asp()`, use in `_bus_loop()`/`_evaluation_loop()` | 100% | Consistent pattern across seq_tracker, ownership_registry, asp |
| CLI subcommand placement | `hermes <noun> <verb>` (e.g., `hermes agent list`, `hermes config migrate`) | 100% | 5 subcommand groups follow this pattern |
| Adapter pattern | Read canonical source (~/.hermes/), generate target via symlinks | 100% | Claude Code adapter proven. Symlinks > copies (single source of truth) |

---

## 2. Anti-patrones (errores a NO repetir)

| Anti-patron | Que pasa | Solucion |
|-------------|----------|----------|
| Adding features to compact format prematurely | Compact is the hot path (872K msg/sec). Adding fields kills perf | New fields go to verbose JSON only. Compact stays frozen until benchmark proves it's needed |
| Mixing orthogonal concerns in one spec | ARC-0369 (ASP) almost included bus integrity — would have been 1200+ lines | Split early. 1 ARC = 1 concern. If in doubt, split |
| Double-daemon spawn on install | Two daemons writing to same bus = corruption | Atomic PID file check (installer.py fix 2026-03-18). Always check process table |
| Notification injection via peer messages | Untrusted content in desktop notifications | Sanitize all notification content. Never render raw peer message text |
| Assuming key file by name | `dani.key` ≠ production key. `momoshod.key` is real | Always verify by fingerprint comparison, never by filename |
| Over-engineering crypto for bilateral | JEI interop showed 3 divergences in v3 despite both implementing "the same thing" | Start with minimal shared test vector. Confirm byte-level match BEFORE building on top |

---

## 3. Calibracion (umbrales ajustados)

| Metrica | Valor calibrado | Fuente |
|---------|----------------|--------|
| Tests per feature (F1-level) | ~30-50 tests | F1-F2: 163 tests for 5 classes |
| Tests per feature (simple) | ~10-15 tests | Config.toml migration: 31 tests |
| Spec lines per ARC | 200-400 lines typical, 856 max (ARC-0369) | 20 specs measured |
| Implementation lines per ARC feature | 100-200 lines | integrity.py F1-F2: ~270 total |
| Time to first working prototype | 1 session (2-3 hours) per ARC feature pair | Consistent across 10 sessions |
| Compact wire efficiency | 76.9% payload ratio | overhead_model.py benchmark |
| Compact throughput | 872K msg/sec | ATR-G.711 benchmark |
| Arena score range | 4.3-4.88 | 8 sessions measured |
| Backward compat breaks | 0 across 14 spec additions | Zero regression policy holds |

---

## 4. Vocabulario de dominio

| Termino | Significado | Contexto |
|---------|------------|----------|
| ARC | Architecture standard (core protocol) | Numbered sequentially. 13 ARC specs exist |
| ATR | Application Technical Report (research/benchmarks) | 2 ATR specs. ATR-G.711 = channel efficiency |
| AES | Application Engineering Specification (visual/tooling) | AES-2040 = visualization stack |
| ECDHE | Ephemeral Elliptic Curve Diffie-Hellman Exchange | Per-message forward secrecy. ARC-8446 §11.2 |
| AAD | Additional Authenticated Data in AES-GCM | Prevents ciphertext relocation attacks |
| HKDF | HMAC-based Key Derivation Function | SHA-256 based. Info string must include version |
| ASP | Agent Service Platform | ARC-0369. Message classification + agent registry + dispatch |
| FSM | Finite State Machine | 7-state agent lifecycle in ARC-0369 F4 |
| MVCC | Multi-Version Concurrency Control | ARC-9001 F3. Write vectors for causal ordering |
| Compact format | ARC-5322 §14 msgpack-style binary | Verbose JSON is default; compact is opt-in |
| Sealed envelope | Encrypted+signed message wrapper | Static (5 elements) or ECDHE (6 elements) |
| Write vector | `w: {src: seq}` causal snapshot | ARC-9001 F3. Like vector clocks for bus |

---

## 5. Workflows probados

### A. New ARC spec (end-to-end)

```
1. Daniel requests or Protocol Architect identifies need
2. EnterPlanMode — research existing patterns + related specs
3. Write spec in English (spec/ARC-XXXX.md) following INDEX.md format
4. Implement in reference/python/hermes/ — extend existing module or create new if >300 lines
5. Write tests (target: 10 per class, 5 per method)
6. Wire into agent.py (_init_asp, _bus_loop, _evaluation_loop)
7. Update CLI if user-facing (cli.py)
8. Update INDEX.md status → IMPLEMENTED
9. Run full test suite (python -m pytest tests/ -v)
10. Commit with `feat(spec): ARC-XXXX description`
```

### B. Bilateral QUEST with JEI

```
1. Design quest doc (docs/QUEST-XXX.md)
2. Encrypt proposal with JEI pubkey (ECDHE or static)
3. Push to hermes-relay (dani_outbox.jsonl)
4. Wait for JEI response in jei_outbox.jsonl (git pull relay)
5. Decrypt response, document findings
6. If divergence found → document in quest doc, plan alignment phase
7. Iterate until bilateral confirmation
```

### C. Arena session (HERMES team)

```
1. Identify parallel workstreams for BR/Multi
2. Protocol-architect takes spec/implementation
3. hermes-research takes benchmarks/data
4. hermes-community takes docs/visual/narrative
5. Each skill works independently, merge at end
6. Scorecard: CQ, DD, GO, IP, IN — target 4.3+ overall
```

---

## 6. Arena Track Record

| Session | Date | Mode | Score | XP | Output |
|---------|------|------|-------|----|--------|
| PVP-005 | 2026-03-08 | PvP w/cybersec | 4.88 | 49 | ARC-8446 mitigations, QUEST-001 security review |
| MULTI-009 | 2026-03-13 | Multi 6-skill | 4.5 | 90 | Hackathon operativa, QUEST system explained |
| MULTI-010 | 2026-03-14 | Multi 6-skill | 4.4 | — | Zima26 emergency, 64-item checklist |
| MULTI-011 | 2026-03-15 | Multi 6-skill | 3.3 | 49.5 | Zima26 dashboard MVP |
| BR-008 | 2026-03-16 | BR 3-skill | 4.3 | 86 | QUEST-003 ECDHE + overhead_model.py |
| MULTI-012 | 2026-03-16 | Multi 5-skill | 4.3 | 64.5 | Zima26 pre-session #82 |
| BR-010 | 2026-03-18 | BR 5-skill | 4.3 | 86 | installer.py + hooks.py + 605 tests |
| PVP-015 | 2026-03-18 | PvP w/research | 4.7 | 47 | ARC-0369 spec (856 lines, TR-369 mapping) |
| BR-018 | 2026-03-23 | BR 3-skill | 3.9 | 78 | Real-time architecture decision (Hub vs P2P vs Hybrid) |
| MULTI-021 | 2026-03-28 | Multi 3-skill | 4.1 | 61.5 | Sprint quality eval: ARC-1122 + 5 D2 + 59 tests |

**Medals**: TE (1), PU (3), AR (1), FA (1) — 6 total
**Total XP**: 661.5 | **Avg score**: 4.28 | **Sessions**: 10

### Patterns from Arena

| Pattern | Observation | Actionable |
|---------|------------|------------|
| Best scores come from focused PvP | PVP-005 (4.88) and PVP-015 (4.7) > any Multi | Prefer PvP for spec design; Multi for ops |
| Cross-dimension Multis score lower | MULTI-011 (3.3) was Zima26 context — domain mismatch | Protocol Architect adds less value outside HERMES domain |
| Triple Strike (BR-008) is the sweet spot | 3 HERMES skills in parallel = complementary outputs | Default Arena format for HERMES team work |
| Score floor is 4.3 in-domain | No in-domain session below 4.3 since debut | 4.3 is the baseline, not the ceiling |

---

## 7. QUEST Lineage

| QUEST | Status | Key learning |
|-------|--------|-------------|
| QUEST-001 | COMPLETE (2026-03-08) | Security review with cybersec — first inter-clan Arena |
| QUEST-002 | COMPLETE (2026-03-16) | ECDHE implementation — bilateral keys established |
| QUEST-003 | CLOSED (2026-03-25) | ARC-8446 v1.2 canonical confirmed. 3 v3 divergences resolved. Fallback sunset ~24 Apr |
| QUEST-004 | CLOSED (2026-03-22) | Claude Code assessment — JEI ~54% vs DANI 71%. Gap 17pp |
| QUEST-005 | IN PROGRESS (artifact received 2026-03-25) | Knowledge Exchange — JEI artifact received, bilateral merge Abr 5 |
| QUEST-CROSS-001 | ACK received | CTO review of ARC-4601 — first cross-clan dispatch |

---

## Estadisticas acumuladas

| Metrica | Valor |
|---------|-------|
| Specs designed | 20 (18 IMPL + 1 INFO + 1 DRAFT) |
| Tests maintained | 1146 |
| Python modules | 17 |
| Arena sessions | 10 (661.5 XP) |
| QUESTs completed | 3 (QUEST-001, 002, CROSS-001) |
| QUESTs in progress | 3 (003, 004, 005) |
| Bilateral clans | 2 (JEI, Nymyka) |
| Commits authored | ~40 (since 2026-02-28) |
| Zero regression streak | 14 spec additions |
