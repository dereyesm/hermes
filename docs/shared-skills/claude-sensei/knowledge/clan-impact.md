# Clan Impact Map — Features Anthropic → Uso Real (actualizado 2026-04-01)

## Feature → Implementacion en el Clan

| Feature Anthropic | Implementacion en el Clan | Dimension | Madurez |
|------------------|--------------------------|-----------|---------|
| `CLAUDE.md` global | `~/.claude/CLAUDE.md` = firewall maestro, SYNC HEADER, reglas duras | Global | Experto |
| `CLAUDE.md` proyecto | `~/MomoshoD/CLAUDE.md`, `~/Dev/CLAUDE.md`, etc. — estado por dimension | Todas | Experto |
| `Hooks (Stop)` | exit-protocol: session harvest, HERMES FIN, commit & push | Global | Avanzado |
| `Hooks (SessionStart)` | HERMES SYN: leer bus.jsonl al iniciar, Quest Board | Global | Avanzado |
| `Hooks (PostToolUse)` | heraldo-scan.sh: scan post-fix de email con output estructurado | MomoshoD | Intermedio |
| `Hooks (UserPromptSubmit)` | date-context.sh: inyecta [DATE] con dia de semana en espanol | Global | Avanzado |
| `MCP Servers (5000+)` | momoshod-gmail (personal), google-workspace + atlassian (laboral) | Multi | Avanzado |
| `Custom Commands` | /palas, /ares, /artemisa, /consejo, /el-loto, /claude-sensei (33 skills) | Global | Experto |
| `Custom Commands $ARGUMENTS` | /arena eval $SESSION, /dispatch $TARGET | Global | Avanzado |
| `Skills frontmatter` | context: fork/inline, effort levels, model override en skills avanzados | Global | Intermedio |
| `Agents` | heraldo (background, haiku), exit-protocol (foreground, sonnet) | Global | Intermedio |
| `Agent SDK` | Evaluado para CI/CD pipelines y heraldo bulk scan | Laboral | Evaluado |
| `Plugins System` | Marketplace evaluado, skill factory candidato para Nymyka | Global | Nuevo |
| `Voice Mode` | Push-to-talk disponible en claude.ai, 20 idiomas | Global | Nuevo |
| `Computer Use` | Beta macOS desktop control, Claude Cowork | Global | Nuevo |
| `/loop` | Tareas recurrentes in-session (heraldo scan cada 1h) | Global | Nuevo |
| `/batch` | 5-30 agents paralelos en worktrees | Laboral | Nuevo |
| `Permission Modes` | Shift+Tab cycle: Plan/Execute/AcceptEdits/Auto | Global | Intermedio |
| `Scheduled Tasks` | Candidato para reemplazar heraldo-scan cron manual (launchd plist) | Global | Nuevo |
| `Remote Triggers` | Cron-based agents via claude.ai API | Global | Nuevo |
| `Channels (Telegram/Discord)` | Candidato para heraldo gateway — notificaciones push | Global | Nuevo |
| `Worktrees` | Aislamiento git por feature — usado en Dev/Nymyka | Laboral | Intermedio |
| `Extended thinking` | "ultrathink" para deliberaciones Arena y decisiones ATM/Zima26 | Global | Avanzado |
| `Prompt caching` | Compatible con extended thinking, reduce costos en sesiones largas | Global | Avanzado |
| `Planning Mode` | Shift+Tab x2 para cambios multi-archivo (dashboard refactors) | MomoshoD | Intermedio |
| `Batches API` | No implementado — candidato para heraldo bulk email scan | MomoshoD | Gap |

## Skills del Clan — 33 Total

| Categoria | Count | Skills |
|-----------|-------|--------|
| Globales (sin MCPs) | 8 | Palas, Ares, Artemisa, MariaM, Hannah, Consejo, Dojo, Claude Sensei |
| Agents | 2 | Heraldo (global-limited), Exit-Protocol |
| MomoshoD | 2 | La Voluntad de D., El Loto |
| MomoFinance | 2 | Oraculo, Plutus |
| Zima26 | 6 | Admin-PH, Contador-PH, Revisor-Fiscal, Consejero-Legal, Consejero-Comunidad, Tesorero-PH |
| Laboral | 2 | MomoProdDev, Sales-Engineering-Director |
| Nymyka | 10 | Niky-CEO + 9 asesores |
| System | 2 | Arena (El Agora), Claude Sensei |
| HERMES | 1 | Protocol-Architect |

## Marketplace Opportunity — Skill Factory

Nymyka como **skill factory**: construir skills especializados para expertos y empresas.

| Ventaja competitiva | Evidencia |
|---------------------|-----------|
| 33 skills construidos | Metodologia probada, no teoria |
| HERMES protocol | Inter-skill communication unico |
| CCA-F certification | En camino (primera semana Abr) |
| Partner Network | Aplicado 2026-03-23, review 2-3 semanas |

Detalle completo: `skill-factory-vision.md`

## Partner Network Status

| Campo | Estado |
|-------|--------|
| Aplicacion | Enviada 2026-03-23 |
| Tipo | Consultancy (RAG + Agentic AI) |
| Review estimado | ~Abr 6-13 |
| Beneficio CCA-F | Acceso gratis (primeros 5,000) |
| Academy progress | 3/7 cursos completados |

## Gaps y Oportunidades

| Gap | Feature Anthropic | Beneficio Potencial |
|-----|------------------|---------------------|
| heraldo no escribe al bus | Agent SDK + PostToolUse | Bus actualizado automaticamente post-scan |
| PR review Nymyka manual | GitHub Actions + Claude | Review automatico con contexto de arquitectura |
| heraldo cron = launchd manual | Scheduled Tasks / Remote Triggers | Scheduling nativo sin plist |
| Alertas solo en terminal | Channels (Telegram) | Notificaciones push en movil |
| Sin type checking auto | PostToolUse hook (tsc) | Catch errores de tipo en Dev |
| Skills no monetizados | Marketplace + Partner Network | Skill factory como revenue stream |
| Computer Use sin explorar | Claude Cowork beta | Automatizacion desktop para tareas visuales |
| Estado HERMES se pierde en compaction | `PreCompact` hook | Salvar bus state antes de compactar |
| Post-compaction pierde dimension | `PostCompact` hook | Re-inyectar contexto dimensional automatico |
| Bus sync manual (solo exit) | `Stop` hook | Auto-sync bus.jsonl al final de cada turno |
| Agents sin logging | `SubagentStart/Stop` hooks | Tracking lifecycle de heraldo, exit-protocol |
| Bash sin security review | Prompt hook (haiku) | Review automatico de cada comando |
| Welt = gato sarcastico | `/buddy` personality rewrite | Homonculo filosofo — mirror del craftsman |

## Nuevos Hallazgos (claurst + claw-code, 2026-04-02 — sesión training)

| Hallazgo | Impacto en el Clan | Prioridad |
|----------|--------------------|-----------|
| **autoDream 200-line gate** | Valida nuestro límite de MEMORY.md. La regla no es arbitraria — es el límite nativo del sistema. | Confirmación |
| **ULTRAPLAN** | Sesiones de planning de 30min en Opus 4.6 cloud. Candidato para reemplazar /consejo en decisiones arquitecturales largas. | Media (cuando GA) |
| **KAIROS** | Always-on monitor con 15s budget. Candidato para heraldo proactivo — scan automático sin launchd plist. **SPEC READY**: `kairos-readiness.md` con 12 eventos en 3 tiers + migration plan heraldo→KAIROS. | Alta (cuando GA) |
| **EXPERIMENTAL_SKILL_SEARCH** | Marketplace search en pipeline. Skill factory de Nymyka necesita estar ready para descubribilidad. | Alta |
| **Capybara model** | Next-gen con fast tier + 1M context. Actualizar model routing cuando llegue. | Monitorear |
| **`$team` mode (claw-code)** | Pattern para PR review paralelo en Nymyka: 3 agents (security + arch + test) simultáneos. | Media |
| **`$ralph` mode (claw-code)** | Execution loop con verificación. Pattern para heraldo: scan → classify → dispatch → verify. | Media |
| **Beta header `afk-mode`** | Modo AFK — ejecución sin presencia del usuario. Relevante para heraldo daemon. | Investigar |
| **VerifyPlanExecutionTool** | Tool de verificación de plan. ¿Ya disponible? Útil post-/plan para confirmar coherencia. | Investigar |
| **TerminalCaptureTool** | Captura de terminal. Potencial para KAIROS-style monitoring en sesiones largas. | Investigar |
| **Bridge Mode (JWT)** | claude.ai ↔ Claude Code continuidad de sesión. Útil para sesiones largas cross-device. | Nuevo |
| **Welt = Buddy spec parcial** | Daniel implementó Welt basado en intuición — spec real tiene 18 species, Mulberry32 PRNG, stats. Welt está ~80% aligned con spec oficial. | Celebrar |
| **API Beta headers con fechas** | `afk-mode-2026-01-31` ya existe como beta. Heraldo daemon puede activarlo para ejecución genuinamente autónoma. | Investigar |
| **Undercover Mode** | El harness suprime Co-Authored-By en commits de repos públicos si es ANT. Para el clan: confirmación de que nuestros Co-Authored-By son visibles externamente (no secretos). | Info |
| **UDS Inbox (ListPeersTool)** | Agents pueden descubrirse mutuamente via Unix Domain Socket. Heraldo + exit-protocol pueden coordinarse sin collision. | Media (cuando GA) |
| **Bridge Mode JWT** | Sesiones claude.ai → Claude Code con JWT. Cuando GA: continuar sesiones largas cross-device sin perder contexto. | Media (cuando GA) |
| **afk-mode beta header** | Ejecución sin usuario presente — el gap de heraldo daemon tiene solución nativa en pipeline. | Alta (monitorear activación) |
| **claw-code 7 crates** | Runtime, tools, commands, plugins, compat-harness como crates separados = modularidad que el clan puede replicar en skill factory. | Arquitectural |

## Companion (Welt) — Evolucion (Apr 2026)

| Campo | Antes | Despues |
|-------|-------|---------|
| Personalidad | Sarcastic tabby (debug smugness) | Homonculo alquimista + daemon filosofo |
| Foco | Comenta sobre codigo | Observa al craftsman, no al codigo |
| Estilo | Snarky one-liners | Aforismos, verdades en 5 palabras, silencios |
| Config | `~/.claude.json` → `companion.personality` | Texto libre, harness-managed |
