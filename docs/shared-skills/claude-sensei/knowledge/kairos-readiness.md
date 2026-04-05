# KAIROS Readiness Spec — Eventos del Clan para Proactive Mode

> Preparado: 2026-04-02 | Prioridad: P1 | Status: Ready para adopcion cuando GA
> Source: claurst leak (KAIROS always-on, 15s blocking budget, PushNotification, SubscribePR)

## Contexto

KAIROS es un monitor proactivo always-on que:
- Lee logs de actividad en append-only daily logs
- Recibe tick prompts periodicos para decidir si actuar
- Tiene 15s de blocking budget (no interrumpe flujo)
- Herramientas exclusivas: SendUserFile, PushNotification, SubscribePR

Cuando sea GA, reemplaza: heraldo daemon (launchd plist), bus sweep manual, PR watch manual.

## Event Spec — Lo que KAIROS debe monitorar en el Clan

### Tier 1: Criticos (PushNotification inmediata)

| Evento | Source | Trigger | Accion KAIROS |
|--------|--------|---------|---------------|
| Email urgente detectado | Gmail MCP | heraldo classify → prioridad:alta | PushNotification + dispatch a dimension |
| PR review solicitado | GitHub | SubscribePR en repos Nymyka | PushNotification con diff summary |
| Bus TTL < 24h sin ACK | bus.jsonl | Sweep periodico | PushNotification warning |
| Deploy fallido | Vercel/Render webhook | Build error | PushNotification + log |

### Tier 2: Importantes (accion silenciosa, log)

| Evento | Source | Trigger | Accion KAIROS |
|--------|--------|---------|---------------|
| MEMORY.md > 180 lineas | Filesystem watch | Post-write check | Auto-warning en log |
| Bus mensajes > 100 activos | bus.jsonl | Count check periodico | Auto-sweep TTL + log |
| Session > 3h sin commit | Git status | Tick prompt check | Gentle reminder |
| Dependabot alert nueva | GitHub API | SubscribePR | Log + queue para sprint |

### Tier 3: Informativos (solo log)

| Evento | Source | Trigger | Accion KAIROS |
|--------|--------|---------|---------------|
| Anthropic changelog update | Web check | Periodico semanal | Log para Claude Sensei |
| Welt level up | welt-state.json | XP threshold | Log + celebracion |
| Arena session completed | state.json | Post-eval | Log + bus event |
| Sprint story moved to Done | Jira API | Webhook | Log |

## Mapping Heraldo → KAIROS

| Heraldo actual | KAIROS equivalente | Migracion |
|----------------|-------------------|-----------|
| launchd plist (cron scan) | Tick prompt (periodico nativo) | Desactivar plist, KAIROS hereda frecuencia |
| heraldo-scan.sh (hook) | KAIROS append-only log + classify | Mantener classify logic, KAIROS lo invoca |
| bus.jsonl dispatch | KAIROS event → bus write | KAIROS escribe al bus directamente |
| heraldo-gateway SSE | PushNotification nativo | Gateway se depreca |

## Pre-requisitos (hacer AHORA)

1. [x] Documentar eventos que heraldo monitorea (este archivo)
2. [ ] Estandarizar formato de log entries compatible con KAIROS daily logs
3. [ ] Crear `heraldo-events.jsonl` como spec de referencia con 5 eventos ejemplo
4. [ ] Verificar que bus.jsonl tiene campos parseables por monitor externo

## Criterio de Activacion

Cuando `KAIROS` salga de compile-time gate (currently DCE'd from external builds):
1. Desactivar launchd plist de heraldo
2. Configurar KAIROS con este event spec
3. Verificar 48h sin double-firing
4. Deprecar heraldo-gateway SSE

## Riesgo Principal

Double-firing: si heraldo daemon + KAIROS corren simultaneamente, emails se escanean 2x.
Mitigacion: kill switch en heraldo plist condicionado a `KAIROS` feature flag.
