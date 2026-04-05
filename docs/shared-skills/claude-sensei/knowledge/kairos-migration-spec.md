# KAIROS Migration Spec — Clan Momosho D.

> Creado: 2026-04-02 | Prioridad: P1 | Status: Pre-GA preparation
> Source: claurst reverse engineering (claw-code + Kuberwastaken/claurst)
> Complementa: `kairos-readiness.md` (event spec + heraldo mapping)

## Qué es KAIROS

Monitor proactivo always-on compilado detrás de feature flag `PROACTIVE`/`KAIROS`.
No está en builds externos actuales (Dead Code Eliminated).
Cuando salga de gate: reemplaza heraldo daemon, bus sweep manual, PR watch manual.

Especificación técnica:
- Append-only daily logs (filesystem)
- Tick-based decision prompts con 15s blocking budget
- Herramientas exclusivas: `SendUserFile`, `PushNotification`, `SubscribePR`
- Brief output mode (flag `KAIROS_BRIEF`) para minimal terminal noise

## Event Spec — 10 Eventos en 3 Tiers para el Clan

### Tier 1: Críticos (PushNotification inmediata — acción requerida)

| # | Evento | Source | Trigger | Acción KAIROS |
|---|--------|--------|---------|---------------|
| E01 | Email urgente | Gmail MCP | heraldo classify → urgencia:alta | PushNotification + dispatch HERMES bus |
| E02 | PR review solicitado | GitHub | SubscribePR en repos Nymyka (sprints activos) | PushNotification con diff summary |
| E03 | Deploy fallido | Vercel/Render webhook | Build error en main | PushNotification + SendUserFile (log) |
| E04 | Bus TTL crítico | bus.jsonl | Mensaje con TTL < 24h sin ACK | PushNotification warning + auto-ACK si expired |

### Tier 2: Importantes (acción silenciosa, append a daily log)

| # | Evento | Source | Trigger | Acción KAIROS |
|---|--------|--------|---------|---------------|
| E05 | MEMORY.md sobre límite | Filesystem | Líneas > 180 post-write | Log entry + queue compaction prompt |
| E06 | Bus sobrecargado | bus.jsonl | Count mensajes activos > 80 | Auto-sweep TTL expired + log |
| E07 | Sesión > 3h sin commit | Git status | Tick check cada hora | Gentle log reminder (no PushNotification) |

### Tier 3: Informativos (solo log, procesados en batch)

| # | Evento | Source | Trigger | Acción KAIROS |
|---|--------|--------|---------|---------------|
| E08 | Welt level up | welt-state.json | XP cruza threshold de stage | Log + bus event `type:event dst:*` |
| E09 | Anthropic changelog | Web check | Semanal (lunes 9AM COT) | Log para Claude Sensei KB update queue |
| E10 | Arena session completada | arena/state.json | Post-eval write | Log + bus `type:event src:arena` |

## Plan de Migración Heraldo → KAIROS

### Fase 0: Pre-KAIROS (AHORA — independiente de GA)

| Tarea | Archivo | Status |
|-------|---------|--------|
| Documentar eventos monitoreados | `kairos-readiness.md` + este archivo | [x] DONE |
| Estandarizar log entries | Formato abajo | [ ] TODO |
| Crear `heraldo-events.jsonl` spec | `~/.claude/skills/heraldo/events-spec.jsonl` | [ ] TODO |
| Verificar bus.jsonl parseabilidad | Campos ts/src/dst/type/msg/ttl/ack | [x] Verificado |

Formato de log entry compatible con KAIROS daily logs:
```
[YYYY-MM-DDTHH:MM:SS] [tier] [event_id] source=X trigger=Y action=Z
```
Ejemplo:
```
[2026-04-02T09:00:00] [T1] [E02] source=github trigger=PR#31-opened action=push_notification
```

### Fase 1: KAIROS GA (cuando flag sale de compile-time gate)

1. Activar KAIROS en `~/.claude.json` settings
2. Configurar con este event spec
3. Desactivar heraldo launchd plist (`com.momoshod.heraldo-scan.plist` → `Disabled=true`)
4. Monitorear 48h para detectar double-firing (KAIROS + heraldo simultáneos)
5. Si 0 double-fires → deprecar heraldo daemon

### Fase 2: Post-migración

- Convertir heraldo a KAIROS event handler (classify logic reusable)
- Deprecar heraldo-gateway SSE (PushNotification nativo lo reemplaza)
- Actualizar agents-guide.md para reflejar nueva arquitectura

## Kill Switch Anti-Double-Firing

Criticidad alta: si heraldo daemon + KAIROS corren simultáneamente = emails escaneados 2x.

Solución: añadir a heraldo plist un check antes de ejecutar:
```bash
# En heraldo-scan.sh (línea 1 post-shebang)
if [ "${KAIROS_ACTIVE}" = "1" ]; then
  echo "KAIROS active — heraldo daemon skip" && exit 0
fi
```

Env var `KAIROS_ACTIVE` se seteará cuando KAIROS esté corriendo (parte de su startup).

## Pre-requisitos Técnicos (hacer antes de GA)

1. **Permisos KAIROS**: verificar que SendUserFile, PushNotification, SubscribePR
   estén en allowlist cuando KAIROS salga de gate
2. **bus.jsonl write access**: KAIROS necesita write a `~/.claude/sync/bus.jsonl`
   — actualmente solo heraldo + exit-protocol tienen permiso explícito
3. **Daily log location**: acordar path para KAIROS append-only logs
   Propuesta: `~/.claude/kairos/daily/YYYY-MM-DD.log`
4. **SubscribePR config**: lista de repos Nymyka a monitorear
   - `github.com/grupo-nymyka/niky-chatbot`
   - `github.com/grupo-nymyka/superinflables-chatbot`

## Diferencia con kairos-readiness.md

| Archivo | Enfoque |
|---------|---------|
| `kairos-readiness.md` | Event spec + tabla heraldo→KAIROS mapping + criterio de activación |
| `kairos-migration-spec.md` (este) | Plan de migración en fases + kill switch + prereqs técnicos + log format |

Ambos son complementarios. Leer juntos antes de activar KAIROS.
