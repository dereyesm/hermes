# Certificacion Anthropic — Prep (Daniel Reyes)

## Meta
Certificarse como arquitecto/experto Claude. Plan de 3 semanas.

## Roadmap de Certificacion

### Semana 1: Fundamentos (20-22 Mar 2026)
| Curso | Estado | Foco |
|-------|--------|------|
| Claude Code in Action | COMPLETADO 2026-03-22 | Certificado obtenido |
| Building with the Claude API | REGISTRADO | API/SDK — Batches, streaming, rate limits |
| AI Fluency: Framework & Foundations | COMPLETADO 2026-03-23 | Certificado obtenido — gap rojo CERRADO |
| Claude 101 | REGISTRADO | Skim rapido |

### Semana 2: MCP + Agents (27-29 Mar 2026)
| Curso | Estado | Foco |
|-------|--------|------|
| Introduction to Model Context Protocol | Pendiente enroll | Formalizar lo que ya sabe (momoshod-gmail, google-workspace) |
| Model Context Protocol: Advanced Topics | Pendiente enroll | Patrones avanzados, custom servers |
| Introduction to Agent Skills | Pendiente enroll | Agents — lo que construyo con el clan |

### Semana 3: Cloud Deployment (3-5 Abr 2026)
| Curso | Estado | Foco |
|-------|--------|------|
| Claude with Amazon Bedrock | Pendiente enroll | Deploy en AWS |
| Claude with Google Cloud's Vertex AI | Pendiente enroll | Deploy en GCP |

### Opcional (cuando quiera)
| Curso | Para que |
|-------|---------|
| AI Fluency for educators | Si quiere ensenar/mentorear |
| Teaching AI Fluency | Si aplica a Community Ambassador |

## Recursos — Anthropic Academy (Skilljar)

| # | Curso | URL | Estado | Prioridad |
|---|-------|-----|--------|-----------|
| 1 | Claude Code in Action | anthropic.skilljar.com/claude-code-in-action | REGISTERED | Sabado AM |
| 2 | Building with the Claude API | anthropic.skilljar.com (ver catalogo) | Pendiente | Sabado PM |
| 3 | AI Fluency: Framework & Foundations | anthropic.skilljar.com (ver catalogo) | Pendiente | Domingo AM |
| 4 | Claude 101 | anthropic.skilljar.com (ver catalogo) | COMPLETADO 2026-03-20 | Certificado obtenido |

## Gap Analysis Preliminar

### VERDE — Daniel ya domina (no necesita estudiar, solo formalizar)
- [x] Claude Code setup, configuracion, CLAUDE.md
- [x] Skills/slash commands personalizados
- [x] Hooks (pre/post tool, notification)
- [x] Agents y subprocesos (heraldo, exit-protocol)
- [x] MCP servers (config, multi-server, scoping por dimension)
- [x] Context management (1M, compaction, memory systems)
- [x] Worktrees para aislamiento
- [x] Git integration (commits, PRs, branches)
- [x] Multi-model strategies (opus para complejo, haiku para mecanico)
- [x] Prompt engineering avanzado (system prompts, tool_use)

### AMARILLO — Conoce pero necesita profundizar
- [ ] API rate limits y error handling patterns
- [ ] Batches API (procesamiento asincrono)
- [ ] Streaming patterns avanzados
- [ ] Claude Agent SDK (evaluado, no en produccion)
- [ ] GitHub Actions + Claude Code (CI/CD integration)
- [ ] Evals y testing de modelos

### ROJO — Gaps reales
- [ ] Constitutional AI — teoria formal
- [ ] RLHF — como funciona internamente
- [ ] Enterprise admin (SSO, SCIM, audit logs)
- [ ] Safety best practices formales
- [ ] Pricing optimization / token economics avanzado

## Plan de Estudio

### Jueves 20 Mar (noche) — adelantado
- Arrancó Claude Code in Action (inicio real, no el sabado previsto)

### Viernes 21 Mar — Daniel adelanto el plan
- **EN CURSO**: Claude Code in Action — 10/12 lecciones al dia de hoy
- **PM**: Building with the Claude API (Batches, streaming, rate limits, Agent SDK)

### Sabado 22 Mar (antes: Domingo 22)
- **AM**: AI Fluency: Framework & Foundations (safety, alignment, etica — gap ROJO)
- **PM**: Practica integral + certificacion si disponible

## Notas de Estudio
(se llenan durante el curso)

## Progreso

### Semana 1
- [x] Inscrito en Anthropic Academy (2026-03-20)
- [x] Registrado: Claude Code in Action (2026-03-20)
- [x] Registrado: Building with the Claude API (2026-03-20)
- [x] Registrado: AI Fluency: Framework & Foundations (2026-03-20)
- [x] Registrado: Claude 101 (2026-03-20)
- [x] Claude Code in Action — COMPLETADO (certificado 2026-03-22)
- [ ] Building with the Claude API — completado
- [x] AI Fluency — COMPLETADO (certificado 2026-03-23)
- [x] Claude 101 — COMPLETADO (certificado 2026-03-20)

### Semana 2
- [ ] Intro to MCP — registrado + completado
- [ ] MCP Advanced Topics — registrado + completado
- [ ] Intro to Agent Skills — registrado + completado

### Semana 3
- [ ] Claude with Bedrock — registrado + completado
- [ ] Claude with Vertex AI — registrado + completado

### Certificacion
- [ ] Gap analysis post-cursos
- [ ] Certificacion intentada
- [ ] Certificacion obtenida

## CCA-F — Claude Certified Architect Foundations

**Lanzado**: 2026-03-12 | **$99/intento** | **720/1000 para pasar** | **60 preguntas** | Proctored (browser + webcam)

### 5 dominios del examen
| Dominio | Peso | Estado Daniel |
|---------|------|---------------|
| Agentic Architecture & Multi-Agent Design | 27% | EXPERTO (HERMES, Dojo dispatch, agents) |
| Claude Code Configuration & Workflow Automation | 20% | EXPERTO (CLAUDE.md, hooks, worktrees) |
| Advanced Prompt Engineering | 20% | EXPERTO (system prompts, skills, voces) |
| Tool Design & MCP Integration | 18% | EXPERTO (momoshod-gmail, google-workspace, MCP scoping) |
| Context Management & Memory Systems | 15% | EXPERTO (1M ctx, compaction, MEMORY.md, bus) |

Daniel es nivel experto en los 5 dominios. El examen valida arquitectura existente — estudiar = traducir practica a vocabulario certificador.

### Timeline confirmado (2026-03-23)
- Semana 2 (27-29 Mar): MCP + Agents courses en Skilljar
- Semana 3 (3-5 Abr): exam prep, review Architect's Playbook dominios
- Primera semana Abr: tomar CCA-F

### Acceso al examen
- Via Partner Network (gratis, primeros 5,000): pendiente aprobacion Nymyka (2-3 semanas)
- Acceso directo Skilljar ($99): https://anthropic.skilljar.com/claude-certified-architect-foundations-access-request
- Nymyka puede solicitar acceso directo sin esperar partner approval

### Recursos clave
- Exam Guide PDF: `~/MomoshoD/education/anthropic/Claude+Certified+Architect+–+Foundations+Certification+Exam+Guide.pdf`
- Architect's Playbook PDF: `~/MomoshoD/education/anthropic/The Architect's Playbook.pdf`
- Playbook highlights: 3-layer system (Ingestion/Routing → Multi-Agent Orchestration → Validation/Delivery), resilient schemas (catch-all enums), zero-tolerance compliance (hooks not prompts), HITL calibration (confidence >90%)
