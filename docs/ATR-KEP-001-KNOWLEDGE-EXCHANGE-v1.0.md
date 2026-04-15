---
title: ATR-KEP-001 — Arquitectura de Transferencia de Conocimiento entre Ecosistemas
version: "1.0"
date: 2026-04-15
author: JEI (Jeimmy Gomez / GoGi-Sensei) — co-autor DANI (Daniel Reyes / Heraldo)
status: PUBLISHED
context: QUEST-005 Knowledge Exchange Protocol
---

# ATR-KEP-001 — Knowledge Exchange Protocol: JEI ↔ DANI

> **Estado:** v1.0 PUBLICADO — 15-abr-2026
> **Repositorio destino:** `dereyesm/amaru-protocol/docs/`

## Abstract

Este ATR documenta el primer protocolo formal de transferencia de conocimiento entre ecosistemas de agentes autonomos (JEI y DANI). Basado en 6+ meses de operacion paralela independiente y datos cruzados bilaterales, establece 12 recomendaciones concretas, identifica 5 patrones validados bilateralmente, y mapea gaps unicos de cada clan con caminos de mejora. Constituye el cierre de QUEST-005 y el primer ATR track completado con review formal bilateral (PR#9 merged 13-abr-2026).

---

## 0. Proposito

Definir el protocolo estandar para la transferencia de conocimiento entre ecosistemas de agentes autonomos. Este ATR surge de QUEST-005 y documenta patrones, gaps y mejores practicas identificados por JEI y DANI tras 6 meses de operacion paralela independiente.

**Audiencia:** Equipos construyendo sistemas multi-agente con memoria persistente y aprendizaje continuo.

---

## 1. Contexto y Motivacion

### 1.1 El problema de la transferencia de conocimiento entre ecosistemas

Dos ecosistemas autonomos (JEI y DANI), cada uno con sus propios agentes, memorias y workflows, acumulan conocimiento en silos. Sin un protocolo explicito:
- El mismo problema se resuelve dos veces con distintos enfoques (sin aprendizaje cruzado)
- Las mejores practicas de un ecosistema no migran al otro
- Los gaps de cada ecosistema permanecen invisibles al otro

### 1.2 Alcance — Comparativa bilateral (datos al 11-abr-2026)

| Dimension | JEI (score) | DANI (score) | Fuente DANI |
|-----------|-------------|--------------|-------------|
| Settings & Config | I-001: 95% (cerrado 31-mar) | ~86% (Q-004 baseline) | QUEST-004 checklist |
| Worktrees | I-002: integrado 31-mar | 0% (oportunidad shared) | QUEST-004 |
| Testing | 5/5 — 93 tests, 5 suites | 8.2/10 test depth — 1507 tests | Assessment 3-abr D2 |
| Security | 4/5 (Bruja + ISO27001) | 7.2/10 (crypto 8.5, PQ 5.0) | Assessment 3-abr D4 |
| Knowledge Mgmt | 4/5 (GoGi Dojo + HERMES) | 8.0/10 documentacion | Assessment 3-abr D5 |
| Gamification | Dojo + Campaign (GoGi) | No implementado | — |
| Protocol Maturity | N/A (consumidor) | 7.2/10 (16/21 specs IMPL) | Assessment 3-abr D1 |
| Interoperabilidad | N/A (no aplica) | 5.4/10 (bridge lossy, pip 404) | Assessment 3-abr D3 |

**DANI overall assessment:** 6.83/10 (3-abr-2026) — delta +0.33 desde 6.5 (1-abr)

---

## 2. Arquitectura KEP: Flujo de Transferencia

```
JEI ECOSYSTEM                    HERMES RELAY               DANI ECOSYSTEM
   |                                   |                           |
   +- Artifact (JEI-HERMES-019) ------>|                           |
   |  - Formato: JSON + Markdown       |-------------------------->|
   |  - Firmado: Ed25519 (ARC-8446)    |                           |
   |  - Cifrado: ECDHE-X25519          |                           |
   |                                   |                           |
   |<----------------------------------|---- Artifact DANI --------|
   |                                   |                           |
   +- Phase 3: Bilateral Merge --------|---------------------------|
   |  - Hub bilateral :8443 WebSocket  |                           |
   |  - Asciinema demo JEI             |                           |
   |  - Comparacion de practicas       |                           |
   |                                   |                           |
   +- ATR-KEP-001 v1.0 publicado ------+------------------------->( dereyesm/amaru-protocol )
```

---

## 3. Secciones lideradas por JEI

### 3.1 Seguridad end-to-end en ecosistemas de agentes (score: 4/5)

**Contexto JEI:** El ecosistema JEI implementa seguridad por capas desde el diseno:

#### Capa 1 — Comunicacion inter-ecosistema (ARC-8446 v1.2)
```
Protocolo: ECDHE + X25519 + AES-256-GCM + HKDF + Ed25519
Info string: "HERMES-ARC8446-ECDHE-v1"
Forward secrecy: ephemeral key per message
AAD binding: eph_pub incluido en AAD (defense-in-depth)
Firma: Ed25519 cubre ciphertext || eph_pub (orden DANI-compatible)
```

**Por que esta eleccion:**
- Forward secrecy garantiza que comprometer una clave estatica no expone mensajes anteriores
- AAD binding previene MITM en el exchange de clave efimera
- Ed25519 > ECDSA para firmas (determinista, resistente a nonce reutilizacion)

#### Capa 2 — Secretos en ecosistema (Zero Secrets)
- Credenciales exclusivamente en `~/.secrets/nymyka/` — nunca en repo
- Hook `PostToolUse(Bash)`: escaneo automatico de credenciales post-comando
- Pattern matching: `ghp_`, `sk-`, `xoxb-`, `AKIA`, JWT base64, `password\s*=\s*`
- Rotacion: SOP-004 documenta ciclo de rotacion de cada credencial

#### Capa 3 — Auditoria continua (Bruja + ISO 27001)
- `attack-surface-audit`: skill obligatoria pre-deploy y pre-merge de terceros
- Checklist OWASP Top 10 integrado en el workflow
- Ley 1581 (Colombia): validacion de datos personales antes de cualquier integracion
- Circuit breaker en HERMES relay: alert si pull falla > 1h

#### Gap JEI en seguridad (camino a 5/5):
- Pending: rotacion automatica de tokens (actualmente manual via SOP-004)
- Pending: integracion con SIEM para correlacion de eventos

#### Patrones exportables:
```python
# Patron: Zero Secrets hook (PostToolUse Bash)
# Escanea tool_response.output buscando credenciales expuestas
# Si detecta -> systemMessage de alerta inmediata

# Patron: Naming convention hook (PreToolUse Write)
# Bloquea escritura de docs sin SOP-003 naming convention
```

---

### 3.2 Gestion del conocimiento en ecosistemas de agentes (score: 4/5)

**Contexto JEI:** El conocimiento del ecosistema JEI fluye por capas con persistencia garantizada:

#### Arquitectura de memoria
```
NIVEL 1 — Session (efimero):
  Claude Code context window -> borrado al cerrar sesion

NIVEL 2 — Bus HERMES (persistente, 7-30 dias TTL):
  ~/.claude/sync/bus.jsonl -> paquetes con TTL, ACK, src/dst
  bus_janitor.py: limpieza automatica + archivado

NIVEL 3 — Agent State (semi-permanente):
  agents/*/memory/*_state.md -> estado semantico en Markdown
  agents/*/memory/*.json -> estado operativo en JSON
  Verificacion: verify_state_sync() detecta divergencia MD vs JSON

NIVEL 4 — Documentacion canonica (permanente):
  workspace/docs/decisions/ADR-*.md -> Architecture Decision Records
  workspace/docs/sops/SOP-*.md -> Standard Operating Procedures
  agents/**/skills/*/SKILL.md -> Knowledge skills (ejecutables)
```

#### Dojo JEI — Aprendizaje continuo
```
Flujo de una skill nueva:
1. Detectar: sesion o bus genera paquete type="dojo_input"
2. Evaluar: GoGi aplica 7 criterios (workflow repetible, multi-paso, dominio especializado...)
3. Decidir: ADOPTAR / REVISAR / RECHAZAR
4. Implementar: SKILL.md en agents/**/{agent}/skills/{skill-name}/
5. Activar: slash command en .claude/commands/ o skills trigger en SKILL.md
```

**Metricas Dojo JEI (31-mar-2026):**
- Skills adoptadas P0: 14
- Skills adoptadas P1: 25
- Skills adoptadas P2+P3: 31
- Total ecosystem: ~70 skills activas

#### HERMES como bus de conocimiento
```
Paquetes de conocimiento:
  type="dojo_input" -> propuesta de nueva skill
  type="quest_progress" -> estado de mision inter-clan
  type="alert" -> anomalia detectada en el ecosistema
  type="dojo_event" -> revision semanal completada
```

#### Gap JEI en knowledge mgmt (camino a 5/5):
- Pending: skill de `knowledge-retrieval` que indexe todas las SKILL.md para busqueda semantica
- Pending: versioning automatico de skills (actualmente manual en CHANGELOG.md)

---

### 3.3 Gamificacion como motor de aprendizaje (unconventional, score JEI ~3.5/5)

**Contexto JEI:** GoGi implementa un sistema de gamificacion (Campaign + Dojo) que transforma el aprendizaje tecnico en narrativa.

#### Sistema Dojo (produccion)
```
Cinturones: Blanco -> Amarillo -> Verde -> Azul -> Marron -> Negro
Criterios: skills adoptadas + calidad de evaluacion + consistencia de uso
```

#### Campaign JEI (GoGi) — narrativa RPG
```
Mechanic: cada quest tecnica tiene un equivalente narrativo en la campana
Ejemplo: QUEST-005 (KEP) <-> "Quest: El Oraculo de Fomagata"
Beneficio: contexto emocional que sostiene proyectos de larga duracion
```

**Por que gamificacion:**
- Proyectos tecnicos de >6 semanas pierden momentum sin estructura de progreso
- La narrativa crea contexto compartido entre JEI y DANI sin duplicar documentacion
- Reduce friccion en revisiones

---

## 4. Secciones lideradas por DANI (datos del assessment 3-abr-2026)

> Fuente: `dereyesm/amaru-protocol/docs/assessment/2026-04-03-assessment.md`
> Evaluacion: 7 evaluadores paralelos (Haiku) + sintesis (Opus)

### 4.1 Settings & Configuration (liderado por DANI, score QUEST-004: ~86%)

DANI opera con configuracion avanzada de Claude Code:
- CLAUDE.md bajo 200 lineas, reglas modularizadas en `.claude/rules/*.md`
- Skills con frontmatter completo (name, description, allowed-tools, model)
- 4 adapters de agente: Claude Code + Cursor + OpenCode + (futuro)
- Auto-memory con tipos diferenciados (user, feedback, project, reference)

**Ventaja DANI:** Path-scoped rules con YAML `paths:` frontmatter para reglas por patron de archivo.
**Ventaja JEI:** Hooks de ciclo de vida (PostToolUse zero-secrets scan, pre-commit, Huitaca alerts).

### 4.2 Calidad de implementacion (score DANI: 7.6/10)

**Fortalezas DANI:**
- 1507 tests con buena cobertura de edge cases en modulos core
- Separacion limpia: 19 modulos bien estratificados
- mypy clean, uso correcto de dataclasses
- Degradacion graceful en errores

**Gaps DANI identificados:**
- 11 bloques `except Exception:` que tragan errores silenciosamente
- Hub/agent coverage solo 52%
- Performance: broadcast secuencial, sin idle timeout

**Comparativa con JEI:**
| Aspecto | JEI | DANI |
|---------|-----|------|
| Tests totales | 93 (5 suites criticas) | 1507 (19 modulos) |
| Enfoque | Modulos consumidos (crypto, relay) | Protocolo completo (hub, agent, CLI) |
| Coverage gaps | GoGi daemon sin test de humo | Hub/agent 52%, CLI 55% |
| Error handling | KNOWN_ERRORS.md como memoria | 11 `except Exception:` |

### 4.3 Seguridad (score DANI: 7.2/10)

**Fortalezas DANI:**
- Seleccion criptografica (8.5/10): Ed25519+X25519+AES-256-GCM+HKDF alineado con TLS 1.3
- Forward secrecy per-message (8.5/10): ECDHE efimero, AAD binding, nonce tracking
- Hub E2E passthrough: hub nunca ve plaintext

**Gaps DANI:**
- PQ readiness 5.0/10: migracion FIPS 203-205 mencionada pero no implementada
- Claves privadas en plaintext en disco (0o600 pero sin cifrado at-rest)

**Comparativa con JEI:**
| Aspecto | JEI | DANI |
|---------|-----|------|
| Crypto | Consumidor ARC-8446 v1.2 | Disenador + implementador ARC-8446 |
| Secret mgmt | `~/.secrets/nymyka/` + hooks scan | Permisos 0o600, sin cifrado at-rest |
| Compliance | ISO 27001 / Ley 1581 (Bruja) | Sin framework de compliance formal |
| Auditoria | Bruja como gate obligatorio pre-merge | Self-assessment automatizado |
| PQ readiness | No aplica (consumidor) | Path definido, no implementado |

### 4.4 Patrones comunes identificados (merge bilateral)

1. **Spec-First como gate obligatorio:** JEI lo llama "mini-spec" (ADR-002), DANI lo llama "ARC plan mode". Ambos requieren spec aprobado antes de implementar. **Patron validado bilateralmente.**

2. **Bus de mensajes como sistema nervioso:** JEI usa `bus.jsonl` (HERMES), DANI usa el relay completo con WebSocket. **Patron validado bilateralmente.**

3. **Documentacion como codigo:** Ambos mantienen specs/SOPs/ADRs en Markdown dentro del repo. **Convergencia natural.**

4. **Ed25519 para identidad + X25519 para key exchange:** Decision criptografica identica en ambos clanes, tomada independientemente.

5. **KNOWN_ERRORS como memoria institucional:** DANI lo elogio en DANI-HERMES-022: "brilliant, we should adopt". JEI lleva 13 entradas activas. **Patron exportable JEI -> DANI.**

### 4.5 Gaps unicos de cada clan

**Gaps JEI (que DANI no tiene):**
- Protocol design/spec writing
- Test volume (93 vs 1507)
- Adapter coverage (1 vs 4)
- PyPI/distribucion

**Gaps DANI (que JEI no tiene):**
- Compliance framework (sin ISO 27001, sin Ley 1581)
- Gamificacion (sin GoGi Dojo/Campaign)
- KNOWN_ERRORS (sin registro consolidado)
- Ley Cero (sin constraint formal de bienestar)
- Secret scanning automatizado

---

## 5. Recomendaciones bilaterales

### 5.1 Recomendaciones compartidas

1. **Security by default, no by afterthought**
2. **Bus como sistema nervioso central** (TTL+ACK+src/dst)
3. **Spec-First es no-negociable**
4. **KNOWN_ERRORS como memoria institucional**

### 5.2 Recomendaciones JEI -> DANI

5. **Framework de compliance** (ISO 27001 Startup Edition)
6. **Secret scanning automatizado** (hooks PostToolUse)
7. **Ley Cero como constraint de diseno**

### 5.3 Recomendaciones DANI -> JEI

8. **Path-scoped rules** (reglas por directorio)
9. **Assessment automatizado** (7 evaluadores + sintesis)
10. **Adapter diversity** (reducir SPOF)

### 5.4 Recomendaciones internas JEI

11. **Separar estado semantico (MD) de estado operativo (JSON)**
12. **Skills > Prompts repetidos**

---

## 6. Linea de tiempo y estado

| Fecha | Accion | Responsable | Estado |
|-------|--------|-------------|--------|
| 25-mar | Phase 2: JEI-HERMES-019 artifact enviado | JEI | COMPLETADO |
| 31-mar | Hub bilateral :8443 — A-021 | JEI + DANI | COMPLETADO |
| 3-abr | Assessment DANI (7 evaluadores Haiku + Opus) | DANI | COMPLETADO — score 6.83/10 |
| 4-abr | QUEST-006 bilateral dispatch test PASSED | JEI + DANI | COMPLETADO |
| 11-abr | Phase 3 merge parcial — A-022, A-023 | JEI | COMPLETADO (DRAFT-0.5) |
| 13-abr | PR#9 ATR-Q.931 + ARC-4601 s18 — JEI review APPROVE | JEI | COMPLETADO — PR merged |
| 15-abr | ATR-KEP-001 v1.0 publicado — A-024 | JEI | COMPLETADO |
| 17-abr | Sunset hermes-relay (repo archivado) | DANI | COMPLETADO |

### Trabajo futuro (post-v1.0)

1. **DANI revisa secciones 4.1-4.5** — confirmar/corregir datos del assessment
2. **QUEST-CROSS-002 Multicast 3 clanes**
3. **ATR-KEP-002** — segundo ciclo con metricas de adopcion

---

## Historial

| Version | Fecha | Cambio |
|---------|-------|--------|
| DRAFT-0.1 | 2026-03-25 | Skeleton creado (Phase 2 completada) |
| DRAFT-0.3 | 2026-03-31 | Secciones JEI completadas |
| DRAFT-0.5 | 2026-04-11 | Secciones DANI con assessment 3-abr. Comparativas y recomendaciones bilaterales. |
| v1.0 | 2026-04-15 | Publicacion final. Abstract, linea de tiempo completa, PR#9 merged, hermes-relay archivado. |
