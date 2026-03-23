# HERMES Community — Experiencia Codificada

> Patrones aprendidos en batalla. Este archivo es la memoria operativa del skill.
> Se actualiza al cierre de sesion cuando hay nuevos patrones confirmados (3+ ocurrencias).
> El SKILL.md define QUE hace HERMES Community. Este archivo define COMO lo hace bien.

## Ultima actualizacion: 2026-03-22
## Fuente: 2 clanes onboarded, 5 QUESTs, visual stack AES-2040, 4 Arena sessions (172 XP)

---

## 1. Heuristicas (atajos decisionales probados)

### Clan onboarding

| Decision | Heuristica | Confianza | Nota |
|----------|-----------|-----------|------|
| First quest complexity | QUEST-001 debe ser autocontenido, completable en 1 sesion | 100% | JEI QUEST-001 (security review) = 1 session, success. QUEST-002 (bilateral crypto) = multi-session, harder |
| Communication channel | Relay repo (encrypted JSONL) for bilateral, bus.jsonl for broadcast | 100% | JEI relay = hermes-relay (private). Nymyka = bus.jsonl (same machine) |
| Key exchange | Generate + share pubkeys BEFORE first encrypted quest | 100% | JEI onboarding: keys first, then quests. Skipping this step = blocked |
| Quest naming | QUEST-NNN sequential, QUEST-CROSS for inter-clan | 95% | QUEST-CROSS-001 (Nymyka→HERMES) confirmed useful naming |
| Ping frequency | 1 ping per 5 days for unresponsive clan | 90% | JEI: 2 pings for QUEST-002 (5 days apart) before response. More = pushy |

### Visual strategy (AES-2040)

| Decision | Heuristica | Confianza | Nota |
|----------|-----------|-----------|------|
| Diagram tool selection | D2 for technical docs (brand colors), Mermaid for GitHub (native render) | 100% | 16 D2 + 13 Mermaid coexist. D2 for quality, Mermaid for zero-dep |
| ASCII→SVG migration | Replace ASCII art in README/ARCHITECTURE with D2 SVGs | 100% | PVP-014 output: 12 diagrams migrated. README readability improved |
| D2 render command | `d2 --theme 0 --pad 80 file.d2 file.svg` | 100% | Theme 0 = default (clean). Pad 80 = comfortable margins |
| Brand colors in D2 | Indigo #1A1A2E (primary), Teal #00D4AA (accent), Amber #F5A623 (highlight) | 100% | Documented in docs/brand/ since 2026-03-21 |
| Diagram per spec | 1 overview diagram per ARC minimum | 90% | Not all specs have one yet, but should |

### Narrative and positioning

| Decision | Heuristica | Confianza | Nota |
|----------|-----------|-----------|------|
| Headline format | Number + comparison + qualifier: "76.9% efficient, 4.9x less than gRPC — still JSON" | 100% | This format tested in multiple contexts, always lands |
| Audience-first messaging | Lead with their pain point, not HERMES features | 95% | 4 audience segments defined in SKILL.md — each has different entry |
| A2A positioning | Complementary, not competitor: "A2A=enterprise cloud, HERMES=sovereign+offline+E2E" | 100% | Avoids flame wars, positions HERMES in its actual niche |
| Pitch length | 30-second max. If it takes longer, it's not clear enough | 95% | Current pitch: 4 sentences, ~25 seconds spoken |

---

## 2. Anti-patrones (errores a NO repetir)

| Anti-patron | Que pasa | Solucion |
|-------------|----------|----------|
| Sending unencrypted quests to external clan | Breaks trust model. Relay is encrypted for a reason | Always encrypt bilateral messages. Use ECDHE or static sealed |
| Pinging more than 2x in 5 days | Perceived as pushy. JEI is sovereign — they respond on their schedule | 1 ping per 5 days max. If no response after 3 pings, escalate to Daniel |
| Updating SKILL.md with stale quest status | QUEST-002 was listed as "proposed" weeks after completion | Keep SKILL.md timeless (capabilities). Quest status in memory/experience only |
| ASCII art in main docs | Looks dated next to D2 SVGs. Inconsistent visual quality | ASCII only in specs (L1 layer). README/ARCHITECTURE = D2 SVGs |
| Marketing language in specs | "Revolutionary protocol" in an ARC = credibility loss | Specs are engineering docs. Marketing lives in POSITIONING.md and pitch deck |

---

## 3. Calibracion (umbrales ajustados)

| Metrica | Valor calibrado | Fuente |
|---------|----------------|--------|
| Quest acceptance rate (JEI) | 80% (4/5 proposed accepted) | QUEST-001 through QUEST-005 |
| Quest completion rate (JEI) | 60% (3/5 accepted completed or in progress) | Measured at Phase 2 stage |
| JEI response time | 2-5 days typical | Measured across 10+ relay exchanges |
| D2 diagrams maintained | 16 total | docs/diagrams/d2/ |
| Mermaid diagrams maintained | 13 total | Inline in specs and docs |
| Brand assets | 7 colors, 3 fonts, Techno-Amaru ouroboros concept | docs/brand/ |
| Visual stack coverage | L1-L3 LIVE, L4-L5 PLANNED | AES-2040 |

---

## 4. Vocabulario de dominio

| Termino | Significado | Contexto |
|---------|------------|----------|
| Clan | Autonomous group using HERMES. Has keypair, bus, namespaces | momoshod, jei, nymyka are clans |
| Soberano/a | Human leader of a clan | Daniel = soberano of momoshod. Jeimmy = soberana of jei |
| Relay | Private git repo for encrypted bilateral messages | hermes-relay (DANI↔JEI) |
| QUEST | Structured bilateral mission between clans | Sequential numbering. Phases: propose → accept → execute → close |
| Ping | Reminder message to unresponsive clan | Max 1 per 5 days. Relay or email |
| D2 | Declarative diagramming language | terrastruct.com/d2. Used for L3 visual layer |
| Mermaid | Markdown-native diagrams | GitHub renders natively. Used for L2 |
| Techno-Amaru | HERMES brand mascot concept | Ouroboros serpent (Incan+tech fusion). docs/brand/ |
| AES-2040 | Visualization stack spec | 5 layers: ASCII → Mermaid → D2 → Excalidraw → Protocol Explorer |

---

## 5. Workflows probados

### A. New clan onboarding

```
1. Establish contact (email, chat, bus message)
2. Share HERMES repo link + QUICKSTART.md
3. Clan generates keypair: `hermes install --clan-id <name>`
4. Exchange public keys via secure channel
5. Store peer pubkey in ~/.hermes/keys/peers/
6. Send QUEST-001 (simple, completable in 1 session)
7. Confirm bilateral crypto works (decrypt test message)
8. Graduate to complex quests (QUEST-002+)
```

### B. QUEST lifecycle management

```
1. Design quest doc (docs/QUEST-XXX-TITLE.md):
   - Objective, phases, timeline, deliverables, success criteria
2. Encrypt proposal with clan pubkey
3. Push to relay (dani_outbox.jsonl)
4. Track in MEMORY.md (Pending section)
5. If no response in 5 days: 1 ping
6. On acceptance: update status, begin Phase 1
7. On each phase completion: update doc, relay ACK
8. On quest close: update doc, MEMORY.md, bus.jsonl state
```

### C. Visual asset production (D2)

```
1. Identify what needs a diagram (spec, architecture, flow)
2. Write .d2 file in docs/diagrams/d2/
3. Render: d2 --theme 0 --pad 80 file.d2 file.svg
4. Embed SVG in target doc (README, ARCHITECTURE, spec)
5. Commit both .d2 source and .svg output
```

---

## 6. Arena Track Record

| Session | Date | Mode | Score | XP | Output |
|---------|------|------|-------|----|--------|
| BR-008 | 2026-03-16 | BR 3-skill | 4.3 | 86 | QUEST-003 design, CTO review quest, overhead model |
| PVP-014 | 2026-03-16 | PvP w/research | 4.0 | 40 | ASCII→SVG migration (12 diagrams), ECDHE visual |
| BR-010 | 2026-03-18 | BR 5-skill | 4.3 | 86 | Doc updates, install-flow.d2, onboarding UX |
| BR-018 | 2026-03-23 | BR 3-skill | 3.9 | 78 | Hub-blind reframe, Signal/Matrix precedent, sovereignty narrative |

**Medals**: TE (1, shared PVP-014)
**Total XP**: 250 | **Avg score**: 4.13 | **Sessions**: 4

### Patterns from Arena

| Pattern | Observation | Actionable |
|---------|------------|------------|
| Community shines in BR format | BR-008 and BR-010 both 4.3 — parallel doc/visual work suits community | Default to BR for team sessions |
| PvP with research is complementary | "Research = precision, community = experience" (PVP-014 insight) | Pair for doc/visual sessions |
| Community adds less in pure spec PvPs | Not invited to PVP-015 (ARC-0369) — correct decision | Spec design is PA+Research territory |

---

## 7. Clan Network Status

| Clan | Onboarded | Keys | QUESTs | Status |
|------|-----------|------|--------|--------|
| momoshod | 2026-02-28 | momoshod.key/pub | N/A (self) | ACTIVE — origin clan |
| jei | 2026-03-07 | sign=65bf:b893, dh=7cc6:ef39 | 5 (3 complete, 2 in progress) | ACTIVE — first external |
| nymyka | 2026-03-17 | bilateral keys | 1 (QUEST-CROSS-001 ACK) | ACTIVE — same machine |

---

## Estadisticas acumuladas

| Metrica | Valor |
|---------|-------|
| Clans onboarded | 2 external (jei, nymyka) |
| QUESTs managed | 6 (QUEST-001 through 005 + CROSS-001) |
| D2 diagrams produced | 16 |
| Mermaid diagrams produced | 13 |
| Brand assets created | 7 colors, 3 fonts, 1 mascot concept |
| Arena sessions | 3 (172 XP) |
| Visual layers live | 3 of 5 (L1-L3) |
