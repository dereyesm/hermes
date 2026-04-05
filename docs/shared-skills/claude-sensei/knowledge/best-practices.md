# Best Practices — Claude Code (actualizado 2026-04-01)

## CLAUDE.md Hierarchy (ya implementado en el clan)

| Archivo | Scope | Uso |
|---------|-------|-----|
| `~/.claude/CLAUDE.md` | Global (todos los proyectos) | Firewall de identidad, reglas universales, SOPs |
| `[proyecto]/CLAUDE.md` | Proyecto (compartido, versionado) | Arquitectura, convenciones, skills disponibles |
| `[proyecto]/CLAUDE.local.md` | Proyecto (personal, no commit) | Preferencias locales, overrides personales |

**`/init` command**: genera CLAUDE.md analizando el codebase. Usar en proyectos nuevos.

**`@file` syntax**: incluir archivos en cada request (`@prisma/schema.prisma`). Inline: `@auth` muestra opciones.

**`#` shortcut (memory mode)**: escribe directamente en CLAUDE.md. Util para correcciones recurrentes.

## Skills Frontmatter — Opciones Avanzadas

```yaml
---
name: my-skill
description: "Does X. NO invocar para: Y (→other-skill)"
context: fork          # fork (default) | inline | agent
agent: Explore         # Explore (read-only) | Code (full access)
effort: high           # low | medium | high | max (Opus 4.6 only for max)
model: opus            # Override model for this skill
argument-hint: "[target] [options]"
---
```

- **$ARGUMENTS**: placeholder en SKILL.md, reemplazado por lo que el usuario escribe post-slash
- **context: fork**: skill corre en subagent aislado (default)
- **context: inline**: skill corre en el thread principal (comparte contexto)
- **effort: max**: solo Opus 4.6, maximo adaptive thinking

## Hooks — 27 Eventos, 4 Tipos (actualizado Apr 2026)

### 27 Hookable Events (5 categorias)

**Tool Lifecycle (3)**
| Evento | Puede bloquear | Caso de uso |
|--------|---------------|-------------|
| `PreToolUse` | Si (exit 2) | Proteger .env, access control, bloquear git force |
| `PostToolUse` | No | Formatear, tests, type check |
| `PostToolUseFailure` | No | Logging de fallos, retry logic |

**Session Management (5)**
| Evento | Caso de uso |
|--------|-------------|
| `SessionStart` | SYN de bus HERMES, memory health check |
| `SessionEnd` | FIN de bus HERMES |
| `UserPromptSubmit` | Date injection, intake logging |
| `Stop` | Notificaciones, exit-protocol, auto-sync bus |
| `StopFailure` | Error tracking |

**Permissions (3)**
| Evento | Caso de uso |
|--------|-------------|
| `PermissionRequest` | Auto-approve en CI, custom security rules |
| `PermissionDenied` | Logging, alternative suggestions |
| `Notification` | Alertas externas |

**Subagents & Teams (4)**
| Evento | Caso de uso |
|--------|-------------|
| `SubagentStart` / `SubagentStop` | Agent lifecycle logging |
| `TeammateIdle` | Redistribuir trabajo |
| `TaskCreated` / `TaskCompleted` | Task lifecycle tracking |

**Context & System (7+)**
| Evento | Caso de uso |
|--------|-------------|
| `PreCompact` / `PostCompact` | Salvar/restaurar estado HERMES pre/post compaction |
| `InstructionsLoaded` | Detectar cambios en CLAUDE.md |
| `ConfigChange` | Detectar cambios en settings |
| `Elicitation` / `ElicitationResult` | MCP user input requests |
| `WorktreeCreate` / `WorktreeRemove` | Worktree lifecycle |
| `CwdChanged` / `FileChanged` | Directory/file watch events |

### 4 Tipos de Hook

| Tipo | Config | Timeout default | Caso de uso |
|------|--------|----------------|-------------|
| **command** | `"command": "script.sh"` | 10 min | Shell scripts, formateo, validacion |
| **prompt** | `"prompt": "Review: $ARGUMENTS"` | 30s | Evaluacion con LLM (security, quality) |
| **agent** | `"prompt": "Verify: $ARGUMENTS"` | 60s | Verificacion multi-turn |
| **http** | `"url": "https://..."` | 10 min | Webhooks externos |

### Matching y Filtrado

- Exact: `"Write"`, Pipe: `"Write|Edit"`, Regex: `"^Write.*"`
- Conditional: `"if": "Bash(git *)"`, `"if": "Write(*.ts)"`, `"if": "Edit(src/api/*)"`

### Patrones Avanzados

- **asyncRewake**: hook async que despierta al modelo al terminar (exit code 2)
- **Interactive prompts**: hooks pueden pedir input via stdout/stdin protocol
- **Auto-approve CI**: `PermissionRequest` hook que emite `{"hookSpecificOutput":{"decision":{"behavior":"allow"}}}`
- **Config priority**: Managed Policy > User > Project > Local > Plugin > Session > Function

**Exit codes**: `0` = allow, `2` = block (PreToolUse) o rewake (async). Stderr → mensaje que ve Claude.

**Debug tip**: `"matcher": "*"` con `"command": "jq . > hook-log.json"` para inspeccionar stdin.

### Hooks que el Clan deberia explorar (P2)

| Hook | Beneficio |
|------|-----------|
| `PreCompact` | Salvar estado HERMES/dimension antes de perder contexto |
| `PostCompact` | Re-inyectar contexto dimensional post-compaction |
| `Stop` | Auto-sync bus.jsonl al final de cada turno |
| `SubagentStart/Stop` | Logging de heraldo y exit-protocol agents |
| `FileChanged` | Watch de bus.jsonl para real-time sync |
| Prompt hook (haiku) | Security review de cada Bash command |

## Plugin Creation — Estructura

```
my-plugin/
├── plugin.md           # Required: metadata + description
├── skills/             # Slash commands
│   └── my-skill/
│       └── SKILL.md
├── commands/           # Custom commands (.md files)
├── hooks/              # Hook configurations
├── agents/             # Agent definitions
└── README.md           # For marketplace listing
```

- **Install**: `/plugin marketplace add author/plugin-name`
- **Per-skill**: `/plugin install skill-name@repo`
- **Publish**: PR to `github.com/anthropics/skills` (Apache 2.0)

## Permission Modes (Shift+Tab cycle)

| Modo | Que hace | Cuando usar |
|------|---------|-------------|
| **Plan** | Solo lectura + razonamiento | Exploracion, entender antes de cambiar |
| **Execute** | Lee + escribe con confirmacion | Default seguro |
| **AcceptEdits** | Auto-acepta ediciones, confirma Bash | Refactors confiables |
| **AutoMode** | Auto-acepta todo | Tareas mecanicas conocidas |

## Effort Levels (Opus 4.6)

| Nivel | Uso | Tokens |
|-------|-----|--------|
| `low` | Tareas triviales, one-liners | Minimo |
| `medium` | Tareas estandar | Normal |
| `high` | Multi-archivo, arquitectura | Alto |
| `max` | Solo Opus 4.6 — maximo adaptive thinking | Maximo |

## --bare Mode

Para uso programatico con Agent SDK: `claude --bare "prompt"`. Sin UI, sin interactividad, output directo. Ideal para scripts y CI/CD.

## Prompt Caching + Extended Thinking

- Prompt caching es compatible con extended thinking
- Cache persiste system prompt + CLAUDE.md + tool definitions entre turns
- Reduce costos significativamente en sesiones largas
- El clan ya se beneficia: sesiones 3h+ con compaction management

## Context Management

| Comando | Cuando usar |
|---------|-------------|
| `/compact` | Conversacion larga, mantener conocimiento del proyecto |
| `/clear` | Cambio de tarea no relacionada, empezar fresco |
| `Escape` | Redirigir mid-response |
| `Esc + Esc` | Rewind a mensaje anterior |

## Memory Architecture Pattern (Clan Momosho D.)

### MEMORY.md as Pure Index
- MEMORY.md is NOT a content store — it is an index with 1-line entries
- Deep content lives in topic files (`memory/*.md`) with YAML frontmatter
- Limits: 180 soft / 200 hard lines per MEMORY.md
- Next Session Prompts: max 3, max 5 lines each, no COMPLETADO blocks

### Compaction Protocol
- Enforced by `memory-health-check.sh` (SessionStart hook, warns only)
- Every compaction logged to `~/.claude/automation/logs/compaction-log.md`
- Weekly audit via `memory-audit.sh` (launchd, Sundays 9 AM)
- Full guide: `knowledge/memory-management.md`

### Topic File Naming
- snake_case: `soul_bot_economics.md`, `vapi_patterns.md`
- Prefix by type: `feedback_*.md`, `project_*.md`, `reference_*.md`
- Max 100 lines recommended per topic file

## MCP Servers — Gestion

```bash
# Agregar server
claude mcp add playwright npx @playwright/mcp@latest
# Pre-aprobar en settings.local.json
{ "permissions": { "allow": ["mcp__playwright"], "deny": [] } }
```

**Nota**: doble underscore en permisos (`mcp__playwright`).

## Token Efficiency — Real vs Percibido (evaluado 2026-04-03)

### Lo que NO ahorra tokens (mitos comunes)
- "No sycophantic openers" — Opus/Sonnet 4.6 ya no los genera. Regla obsoleta.
- "Edit don't rewrite" — Es comportamiento DEFAULT de Claude Code (Edit tool > Write).
- "User instructions override" — Es arquitectura de Claude Code (user > project > system). No necesita regla.
- Poner 8 lineas de "se breve" en CLAUDE.md — ahorro marginal vs baseline actual.

### Lo que SI ahorra tokens (80% del ahorro real)
1. **Model routing**: Haiku para busqueda (5-20x mas barato que Opus). Sonnet para ejecucion.
2. **Parallel tool calls**: 1 mensaje con 3 tools vs 3 mensajes secuenciales.
3. **Agent delegation**: Haiku subagents para grep/explore — fraccion del costo de Opus.
4. **Session discipline**: Max 2-3h, no acumular contexto. Cada msg mas caro con contexto largo.
5. **Plan mode**: Pensar antes de escribir codigo — evita rewrite loops costosos.
6. **Prompt caching**: System prompt + CLAUDE.md + tools cacheados entre turns (automatico).
7. **Hooks**: Inyectar solo el contexto necesario automaticamente (date, bus state, etc.).

### Referencia: drona23/claude-token-efficient
8 reglas basicas para CLAUDE.md. Claim: 63% menos tokens. Realidad: compara vs baseline sin reglas que ya no existe en modelos 4.6. Util como intro para principiantes (7/10), irrelevante para usuarios avanzados (3/10). Fuente: tododeia.com/@soyenriquerocha.

## Prompting — Framework 4D (AI Fluency)

| D | Que es | En la practica |
|---|--------|----------------|
| **Delegation** | Decidir que hace humano vs IA | Firewall de identidad |
| **Description** | Comunicar: rol + tarea + reglas | Stage → Task → Rules |
| **Discernment** | Evaluar outputs criticamente | Arena eval cadence |
| **Diligence** | Usar IA responsablemente | NUNCA publicar sin APROBADO |
