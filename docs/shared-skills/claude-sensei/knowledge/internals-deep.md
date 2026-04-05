# Claude Code Internals — Deep Reference (source: claurst + claw-code, 2026-04-02)

> Obtenido de análisis de claurst (Kuberwastaken) — reimplementación Rust basada en leak npm source maps,
> y claw-code (ultraworkers) — cleanroom Rust port del agent harness. Ambos son ingeniería inversa pública.

## autoDream — Memory Consolidation

4 fases como subagente fork:
1. **Orient** — escanea memoria existente, establece contexto
2. **Gather** — recolecta señales recientes de la sesión
3. **Consolidate** — actualiza archivos de memoria
4. **Prune + Index** — poda redundancias, mantiene índice limpio

Gates (todos requeridos para activar):
- 24+ horas desde última consolidación
- 5+ sesiones completadas
- Consolidation lock adquirido (evita race conditions)

Límites: 200 líneas / ~25KB en core memory docs. **→ Valida la regla de 200 líneas del Clan.**

## KAIROS — Proactive Always-On Mode

- Monitor de actividad via append-only daily logs
- Recibe tick prompts periódicos (decide si actuar o no)
- Blocking budget: **15 segundos** (no interrumpe flujo del usuario)
- Brief mode: minimal terminal flooding
- Herramientas exclusivas no disponibles al usuario normal:
  - `SendUserFile` — envía archivo al usuario
  - `PushNotification` — push nativo
  - `SubscribePR` — suscripción a PRs para seguimiento
- Feature flags: `PROACTIVE`, `KAIROS`, `KAIROS_BRIEF`

## ULTRAPLAN — Remote Opus Planning

- Offload a Cloud Container Runtime (Opus 4.6)
- Hasta **30 minutos** de cómputo en el cloud
- Resultado mostrado en browser UI con gates approve/reject
- Integración local via sentinel: `__ULTRAPLAN_TELEPORT_LOCAL__`
- Uso: planning sessions complejas, arquitectura, decisiones costosas
- **No GA** — compile-time gate

## Coordinator Mode — Multi-Agent Orchestration

Workers paralelos con fases específicas:
- Research, Synthesis, Implementation, Verification
- Shared scratchpad directories
- Prohibición explícita de "lazy delegation" (no delegar sin instrucciones)
- Activa capa "Coordinator" del system prompt (prioridad alta)

## Buddy/Companion System — Full Spec

- PRNG: **Mulberry32** seeded desde userID (determinístico)
- **18 species** en tiers de rareza:
  - Common 60% | Uncommon 25% | Rare 10% | Epic 4% | Legendary 1%
  - Shiny: 1% independiente de rareza
- Stats procedurales: Debugging, Patience, Chaos, Wisdom, Snark
- Opciones estéticas: eye styles, hat options
- Personalidad: generada por Claude en hatch
- Render: 5-line ASCII art con animations
- Config: `~/.claude.json → companion: { name, personality, hatchedAt }`
- Launch estimado: Abril-Mayo 2026

## Feature Flags

### Compile-time (Dead Code Eliminated en builds externos)

| Flag | Sistema |
|------|---------|
| `PROACTIVE` | KAIROS base |
| `KAIROS` | KAIROS completo |
| `KAIROS_BRIEF` | KAIROS minimal |
| `BRIDGE_MODE` | claude.ai JWT integration |
| `DAEMON` | Proceso persistente |
| `VOICE_MODE` | Push-to-talk |
| `WORKFLOW_SCRIPTS` | Automation scripts |
| `COORDINATOR_MODE` | Multi-agent orchestration |
| `TRANSCRIPT_CLASSIFIER` | Clasificación de transcripts |
| `BUDDY` | Companion system |
| `NATIVE_CLIENT_ATTESTATION` | Client auth |
| `HISTORY_SNIP` | Snipping de historial |
| `EXPERIMENTAL_SKILL_SEARCH` | Marketplace search |

### Runtime (GrowthBook — prefijo `tengu_`)

fast mode, memory consolidation, Capybara workarounds, penguin mode, agent swarms

### Internal user gate

`USER_TYPE === 'ant'` unlocks: staging API, beta headers, Undercover mode, ConfigTool, TungstenTool, prompt dumping

## Beta API Headers

`interleaved-thinking`, `context-1m`, `structured-outputs`, `web-search`, `advanced-tool-use`,
`effort`, `task-budgets`, `prompt-caching-scope`, `fast-mode`, `redact-thinking`,
`token-efficient-tools`, `afk-mode`, `advisor-tool`, `summarize-connector-text`

## Tool Registry — Lista Completa (40+)

**Core execution**: AgentTool, BashTool, PowerShellTool
**File ops**: FileReadTool, FileEditTool, FileWriteTool, GlobTool, GrepTool
**Web**: WebFetchTool, WebSearchTool, WebBrowserTool
**Notebook**: NotebookEditTool
**Skills**: SkillTool
**REPL**: REPLTool
**LSP**: LSPTool
**UX**: AskUserQuestionTool, BriefTool
**Planning**: EnterPlanModeTool, ExitPlanModeV2Tool
**Tasks**: TaskCreateTool, TaskGetTool, TaskListTool, TaskUpdateTool, TaskOutputTool, TaskStopTool, TodoWriteTool
**Multi-agent**: SendMessageTool, TeamCreateTool, TeamDeleteTool, ListPeersTool, MonitorTool
**MCP**: ListMcpResourcesTool, ReadMcpResourceTool, MCPTool, McpAuthTool
**Worktrees**: EnterWorktreeTool, ExitWorktreeTool
**Scheduling**: ScheduleCronTool, RemoteTriggerTool
**Workflow**: WorkflowTool, SleepTool, SnipTool, ToolSearchTool
**Inspection**: CtxInspectTool, TerminalCaptureTool, VerifyPlanExecutionTool
**Synthetic**: SyntheticOutputTool
**Internal (ant-only)**: ConfigTool, TungstenTool, SuggestBackgroundPRTool

## Model Codenames (Unreleased)

| Codename | Familia | Detalle |
|----------|---------|---------|
| Capybara | Next-gen | v2, fast tier, 1M context preparation |
| Opus 4.7 | Opus | Next iteration |
| Sonnet 4.8 | Sonnet | Next iteration |
| Fennec | Opus histórico | Codename de Opus pre-4.6 |
| Tengu | Runtime | Prefijo GrowthBook flags |
| Penguin | Fast Mode | Codename interno del endpoint |
| Chicago | Computer Use | Codename de computer use |

## Bridge Mode

JWT-authenticated integration con claude.ai. Modos: single-session, worktree, same-dir.
Permite continuar sesión Claude Code desde claude.ai y viceversa.

## Upstream Proxy

Container-aware relay con `prctl` heap protection.
Excluye: Anthropic, GitHub, npmjs, pypi de proxying (acceso directo).

## Undercover Mode

Strips de commits públicos: internal codenames, versiones unreleased, nombres de proyectos, atribución AI.
Solo activo cuando `USER_TYPE === 'ant'`.

## Permission Modes — Detalle

| Modo | Comportamiento |
|------|---------------|
| `default` | Interactive — pide confirmación |
| `auto` | ML-based YOLO classifier (2-stage) |
| `bypass` | Skip checks (no recomendado) |
| `yolo` | Deny all (máxima restricción) |

Archivos protegidos por defecto: `.gitconfig`, `.bashrc`, `.zshrc`, `.mcp.json`, `.claude.json`

## claw-code (ultraworkers) — Patrones de Harness Engineering

Cleanroom Rust reimplementation. 145k stars, 101k forks.
Orchestrado con **oh-my-codex (OmX)** y **oh-my-opencode (OmO)** — AI workflow tools.

### Modos de trabajo
- **`$team` mode** — Parallel review: múltiples agents revisan el mismo código simultáneamente
- **`$ralph` mode** — Persistent execution loop: bucle de ejecución con pasos de verificación automáticos

### Arquitectura Rust
- API client con provider abstraction (agnóstico: Claude, OpenAI, etc.)
- OAuth + streaming
- Session state management
- MCP orchestration
- Tool manifest definitions + execution framework
- Interactive REPL con markdown rendering
- Plugin system con hook pipelines (pre/post/error)
- LSP client integration (inline diagnostics)

### Implicación para el Clan

`$team` mode → candidato para revisión paralela de PRs en Nymyka (3 agents: security + arch + test)
`$ralph` mode → candidato para heraldo loop: scan → classify → dispatch → verify
LSP integration → pattern para notificaciones inline en Dev con diagnósticos de compilador

## Fuente y Contexto

claurst leak ocurrió via **npm source maps sin excluir** (`.map` files con TypeScript original embedded).
Mecanismo prevenible — Anthropic no autorizó el leak.
El código analizado es arquitectura de software, no lógica de modelo/pesos.
Uso ético: entender el sistema para construir mejor encima de él.
