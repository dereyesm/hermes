# Ecosistema Claude/Anthropic — Mapa (actualizado 2026-04-01)

## Stack Completo

```
ANTHROPIC
├── Models
│   ├── Claude Opus 4.6 (flagship, 1M context, adaptive thinking)
│   ├── Claude Sonnet 4.6 (balanced)
│   └── Claude Haiku 4.5 (fast/cheap)
│
├── Interfaces
│   ├── claude.ai (web/mobile)
│   │   ├── Voice Mode (push-to-talk, 20 languages) ← NUEVO Mar 2026
│   │   ├── Skills UI (Personalizar > Skills)
│   │   └── Scheduled Tasks / Remote Triggers (cron via web)
│   ├── Claude Code (CLI + Desktop)
│   │   ├── Skills (slash commands personalizados)
│   │   ├── Hooks (shell/HTTP/prompt/agent hooks)
│   │   ├── Agents (subprocesos autonomos)
│   │   ├── MCP Servers (5000+ integraciones)
│   │   ├── Plugins System (marketplace, /plugin commands)
│   │   ├── Channels (Telegram/Discord)
│   │   ├── Scheduled Tasks (cron nativo)
│   │   ├── Remote Control (web/mobile triggers)
│   │   ├── Worktrees (aislamiento git)
│   │   ├── /loop (recurring tasks in-session)
│   │   ├── /batch (5-30 parallel worktree agents)
│   │   └── Permission Modes (Plan/Execute/AcceptEdits/Auto)
│   ├── Computer Use (beta — macOS desktop control, Claude Cowork)
│   └── API directa
│
├── API & SDKs
│   ├── Messages API (core)
│   ├── Tool Use (function calling)
│   ├── Streaming (SSE)
│   ├── Batches API
│   ├── @anthropic-ai/sdk (TypeScript)
│   ├── anthropic (Python)
│   └── Claude Agent SDK (Python + TypeScript)
│       ├── claude-agent-sdk (pip)
│       └── @anthropic-ai/claude-agent-sdk (npm)
│
├── MCP (Model Context Protocol)
│   ├── Spec: open standard
│   ├── 5000+ servers (Gmail, Slack, GitHub, Figma, etc.)
│   └── Custom servers (stdio/SSE)
│
├── Safety & Alignment
│   ├── Constitutional AI (CAI)
│   ├── RLHF
│   ├── System prompts & guardrails
│   └── Usage policies
│
├── Enterprise
│   ├── Team / Enterprise / Max plans
│   ├── SSO / SCIM
│   ├── Audit logs
│   ├── Admin controls
│   └── 1M token context (Max/Team/Enterprise)
│
├── Partner Network
│   ├── $100M investment 2026
│   ├── CCA-F Certification ($99)
│   ├── Partner Portal + Academy
│   └── Services Directory
│
└── Learning
    ├── Anthropic Academy (Skilljar)
    ├── Anthropic Cookbook (GitHub)
    ├── Documentation (docs.anthropic.com, code.claude.com)
    ├── Skills Marketplace (github.com/anthropics/skills)
    ├── Community Ambassadors Program
    └── CCA-F Certification path
```

## Internals — Claude Code Architecture (source: decodeclaude.com + helmcode.com + claurst + claw-code, Apr 2026)

| Metrica | Valor |
|---------|-------|
| Codebase | ~512,000 lineas TypeScript, ~1,884 archivos |
| Tools integrados | 45 (categorizados por funcion) |
| Agent types | 6 built-in |
| Slash commands | ~100 across 5 categorias |
| Bundled skills | 17 |
| Hookable events | 27 (5 categorias: tool lifecycle, session, permissions, subagents, context) |
| Hook types | 4 (command, prompt, agent, HTTP) |
| MCP transports | 4 |
| Bash security validators | 22+ (5 defense layers, seatbelt/bubblewrap sandbox) |
| Security principles | 12 core |
| Context window | 200K tokens default |

### System Prompt — 6 Capas (prioridad descendente)

| Capa | Prioridad | Activacion |
|------|-----------|------------|
| Override | Maxima | Simple Mode (`CLAUDE_CODE_SIMPLE` → 3 lineas) |
| Coordinator | Alta | Multi-agent orchestration |
| Agent | Alta | Subagent o KAIROS proactivo |
| Custom | Media | `--system-prompt` CLI flag |
| Default | Base | Siempre (7 secciones estaticas + cache boundary) |
| Append | Ultima | Siempre (memoria, MCPs, env, idioma) |

**Cache boundary**: `__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__` separa contenido cacheable (pre) del dinamico (post).
**CLAUDE.md se carga como parte de la capa Default** — misma jerarquia que reglas core.

### Compaction — 3 Capas

| Capa | Mecanismo | Trigger |
|------|-----------|---------|
| Microcompaction | Hot tail reciente inline, outputs viejos archivados a disco | Continuo |
| Auto-compaction | Headroom threshold (espacio libre < reserva) | Automatico |
| Manual (`/compact`) | Hints de foco, respeta CLAUDE.md para que preservar | Usuario |

Post-compaction: boundary marker → summary comprimido → relee 5 archivos recientes → restaura todos/plan → startup hooks.

### YOLO Classifier (Auto Permission Mode) — 2 Etapas

| Stage | Tokens | Funcion |
|-------|--------|---------|
| Stage 1 | 64 | Decision binaria rapida — approve o escalar |
| Stage 2 | 4096 | Razonamiento extenso, veredicto final |

Fallback a interactive si demasiados denials consecutivos.

### ULTRAPLAN — Remote Opus Planning

Offload sesiones de planning de 30 minutos a Cloud Container Runtime con Opus 4.6. Resultado mostrado en browser UI con gates de approve/reject. Integra al contexto local via sentinel `__ULTRAPLAN_TELEPORT_LOCAL__`. Feature flag: compile-time gate (no GA aun).

### autoDream — Memory Consolidation Background Agent

Subagente fork con 4 fases: orient (escanea memoria), gather (señales recientes), consolidate (actualiza archivos), prune (poda + indexa). Gates de activacion: 24h elapsed + 5+ sessions + consolidation lock adquirido. Limite: 200 lineas / ~25KB en core memory. **Valida la regla de 200 lineas del clan.**

### KAIROS — Proactive Mode (Always-On)

Monitor de actividad con append-only daily logs. Tick prompts periodicos para decidir acciones proactivas. Blocking budget: 15 segundos (no interrumpe flujo). Herramientas exclusivas: SendUserFile, PushNotification, SubscribePR. Brief mode para minimal terminal flooding. Flag: KAIROS / KAIROS_BRIEF.

### Companion/Buddy System (`/buddy`)

Feature Apr 2026. Companion = entidad UI separada con speech bubble.
Config en `~/.claude.json` → `companion: { name, personality, hatchedAt }`.
`personality` es texto libre que define comportamiento. Harness-managed, no Claude.
18 species (Common 60%, Uncommon 25%, Rare 10%, Epic 4%, Legendary 1%). Shiny 1%.
Stats procedurales: Debugging, Patience, Chaos, Wisdom, Snark. PRNG: Mulberry32 seed=userID.
5-line ASCII art con animations, eye styles, hat options, Claude-generated personality descriptions.

### Model Codenames (Unreleased — source: claurst leak)

| Codename | Familia | Nota |
|----------|---------|------|
| Capybara | Next-gen | v2 + fast tier, 1M context preparation |
| Opus 4.7 | Opus | Next Opus — sin fecha confirmada |
| Sonnet 4.8 | Sonnet | Next Sonnet — sin fecha confirmada |
| Fennec | Opus (historico) | Codename anterior a Opus 4.6 |
| Tengu | Runtime | Prefijo de feature flags GrowthBook (`tengu_*`) |
| Penguin | Fast mode | Codename interno de Fast Mode |

### Feature Flags — Compile-time (DCE'd from external builds)

`PROACTIVE`, `KAIROS`, `KAIROS_BRIEF`, `BRIDGE_MODE`, `DAEMON`, `VOICE_MODE`, `WORKFLOW_SCRIPTS`, `COORDINATOR_MODE`, `TRANSCRIPT_CLASSIFIER`, `BUDDY`, `NATIVE_CLIENT_ATTESTATION`, `HISTORY_SNIP`, `EXPERIMENTAL_SKILL_SEARCH`

GrowthBook runtime gates (prefijo `tengu_`): fast mode, memory consolidation, Capybara workarounds, penguin mode, agent swarms.
Internal user gate: `USER_TYPE === 'ant'` → staging API, beta headers, Undercover mode, ConfigTool, TungstenTool.

### Undercover Mode — Leak Prevention para Anthropic Employees

Detecta `USER_TYPE === 'ant'` en repos públicos y activa system prompt injection que previene commits/PRs de filtrar:
- Internal codenames (animal names: Capybara, Tengu, etc.)
- Unreleased model versions (e.g., opus-4-7, sonnet-4-8)
- Internal repos, tooling references
- "Claude Code" mentions y Co-Authored-By lines

No hay force-OFF: activo por defecto salvo `CLAUDE_CODE_UNDERCOVER=1` override o repos en allowlist interno.
Implicación para el clan: los commits que incluyen Co-Authored-By Claude son visibles para ANT — no son secretos.

### API Beta Headers — Fechas de Activación

Negociados via `x-anthropic-beta` HTTP header para capacidades pre-GA:

| Header | Fecha activación |
|--------|-----------------|
| `interleaved-thinking-2025-05-14` | May 2025 |
| `context-1m-2025-08-07` | Ago 2025 |
| `structured-outputs-2025-12-15` | Dic 2025 |
| `web-search-2025-03-05` | Mar 2026 |
| `fast-mode-2026-02-01` | Feb 2026 |
| `redact-thinking-2026-02-12` | Feb 2026 |
| `afk-mode-2026-01-31` | Ene 2026 (AFK = ejecución sin usuario presente) |
| `task-budgets-2026-03-13` | Mar 2026 |
| `prompt-caching-scope-2026-01-05` | Ene 2026 |

`afk-mode`: relevante para heraldo daemon — ejecución autónoma sin presencia del usuario.

### UDS Inbox — Peer Agent Communication

Unix Domain Socket (UDS) inbox para descubrimiento y comunicación entre agents peer.
Herramienta asociada: `ListPeersTool`. Permite que agents en una sesión se vean mutuamente.
Implicación para el clan: heraldo + exit-protocol pueden coexistir sin collision si se coordinan via UDS.

### Bridge Mode — claude.ai ↔ Claude Code Continuidad

JWT-authenticated integration entre claude.ai web y Claude Code CLI.
Tres modos: single-session, worktree, same-dir.
Flag compile-time: `BRIDGE_MODE`.
Cuando GA: permite continuar una sesión que empezó en claude.ai directamente en el CLI, con contexto preservado.

### CYBER_RISK_INSTRUCTION — Sección de Seguridad con Owners

El system prompt incluye una sección explícita de cybersecurity con owners nombrados:
- "Owned by the Safeguards team (David Forsythe, Kyla Guru)"
- Distingue authorized security testing vs destructive/supply-chain compromise
- Provee guidance específica para no facilitar ataques reales bajo disfraz de "testing"

### claw-code (ultraworkers) — Rust Harness Reimplementation

Cleanroom Rust port del agent harness. Orchestrado con oh-my-codex (OmX) + oh-my-opencode (OmO).
Patrones clave: `$team` mode (parallel review por multiples agents), `$ralph` mode (persistent execution loop + verification).

Workspace Rust — 7 crates:
- `crates/api-client` — provider-agnostic API, OAuth, streaming
- `crates/runtime` — session state, compaction, MCP orchestration, prompt construction
- `crates/tools` — tool manifest definitions y execution framework
- `crates/commands` — slash commands, skills discovery, config inspection
- `crates/plugins` — plugin model, hook pipeline, bundled plugins
- `crates/compat-harness` — editor integration compatibility layer
- `crates/claw-cli` — interactive REPL, markdown rendering, project flows

→ Detalle completo: `internals-deep.md`

## Features Nuevos Mar 2026

| Feature | Que es | Status |
|---------|--------|--------|
| **Agent SDK** | Mismo toolset que Claude Code, programmatic. Python + TS | GA |
| **Plugins System** | Marketplace de skills, /plugin commands, plugin.md packaging | GA |
| **Voice Mode** | Push-to-talk (spacebar), 20 idiomas, claude.ai | GA Mar 2026 |
| **/loop** | Tareas recurrentes in-session (e.g. `/loop 1h /heraldo scan`) | GA |
| **/batch** | 5-30 agents paralelos en worktrees separados | GA |
| **Computer Use** | Control de macOS desktop, Claude Cowork beta | Beta |
| **Remote Triggers** | Cron-based agents via claude.ai API | GA |
| **Permission Modes** | Shift+Tab cycle: Plan → Execute → AcceptEdits → Auto | GA |
| **Opus 4.6** | Adaptive thinking, effort levels (low/med/high/max) | GA |
| **1M Context** | Disponible en Max/Team/Enterprise plans | GA |
| **5000+ MCP Servers** | Ecosistema creciente de integraciones | GA |
| **Prompt Caching** | Compatible con extended thinking | GA |

## Lo que Daniel ya usa del stack

| Componente | Nivel | Evidencia |
|-----------|-------|-----------|
| Claude Code | **Experto** | 33 skills, hooks, agents, worktrees, MCP servers |
| Models (Opus 4.6 1M) | **Experto** | Sesiones largas, compaction management, effort tuning |
| MCP Servers | **Avanzado** | momoshod-gmail, google-workspace, atlassian configurados |
| Tool Use | **Avanzado** | Skills con tool dispatch, multi-tool patterns |
| API directa | **Intermedio** | Usado via SDK, no directamente en produccion propia |
| Agent SDK | **Evaluado** | Revisado, candidato para CI/CD pipelines |
| Plugins System | **Nuevo** | Marketplace evaluado, skill factory candidato |
| Voice Mode | **Nuevo** | Disponible en claude.ai |
| Computer Use | **Nuevo** | Beta macOS, Claude Cowork |
| Channels | **Nuevo** | Recien anunciado — heraldo gateway candidato |
| Scheduled Tasks | **Nuevo** | Recien anunciado — reemplaza cron manual |
| Safety/Alignment | **Gap** | Conocimiento practico pero no formal |
| Enterprise | **Gap** | Usa Team plan pero no administra enterprise |
