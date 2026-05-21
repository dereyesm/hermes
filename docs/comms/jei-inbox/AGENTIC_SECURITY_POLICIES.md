# Políticas de Seguridad Agéntica — Nymyka
**Versión:** 1.0 | **Fecha:** 2026-04-15 COT
**Propietario:** Bruja (CISO-IA) | **Aprueba:** Jeimmy Gomez (CISO)
**Triada:** Bruja + Chiminigagua + Bachue | **Referencia:** OWASP ASI02 Tool Misuse & Exploitation

---

## Principio de Diseño

Cada herramienta de cada agente tiene un scope declarado de:
- **Parámetros permitidos** (narrowest possible function)
- **Acciones prohibidas** (lo que el agente NO debe hacer aunque técnicamente pueda)
- **Aprobación requerida** (qué acciones requieren validación humana)

Violar estas políticas activa REGLA-SEC-001: bloqueo inmediato + escalada a Jeimmy.

---

## JAi / Huitaca — Orquestador + Comunicaciones

### Telegram API (Huitaca Bot)
| Acción | Permitida | Restricciones |
|---|---|---|
| Enviar mensaje a Jeimmy (chat privado) | Sí | Solo canales declarados en `routes.md` |
| Enviar a Santuario Raftel (grupo) | Sí | Solo anuncios, no datos PII |
| Leer mensajes entrantes | Sí | Solo procesar, nunca almacenar en repo |
| Crear nuevo bot o token | No | Requiere aprobación Jeimmy |
| Enviar mensajes a chats no declarados | No | Violación IDENTITY_FIREWALL |

**Prohibido:** Enviar credenciales, tokens, datos financieros o de salud por Telegram. Usar canal solo para notificaciones y resúmenes.

### GitHub API
| Acción | Permitida | Restricciones |
|---|---|---|
| Leer issues y PRs de `la-triada` | Sí | Solo repos declarados en dimensión JEI |
| Escribir en `~/.claude/sync/bus.jsonl` | Sí | Solo formato HERMES v3.0 |
| Crear issues en `la-triada` | Sí | Con aprobación Jeimmy |
| Push de código | Sí | Solo rama `main`, con commit firmado |
| Acceder a repos de `grupo-nymyka` | Condicionada | Requiere gate IDENTITY_FIREWALL |
| Acceder a repos personales `patito/` | No | Scope personal, no corporativo |
| Crear webhooks o GitHub Apps | No | Requiere aprobación Jeimmy + Bruja |

### Memoria de agente (`agents/system/JAi/memory/`)
| Acción | Permitida | Restricciones |
|---|---|---|
| Leer/escribir archivos de memoria | Sí | Solo namespace JAi declarado |
| Almacenar contexto de sesión | Sí | Sin PII identificable de clientes externos |
| Almacenar credenciales o tokens | No | Solo en `~/.secrets/nymyka/` |

---

## Bruja — CISO-IA

### Acceso a logs y auditorías
| Acción | Permitida | Restricciones |
|---|---|---|
| Leer archivos del repo `la-triada` | Sí | Lectura solo — sin modificar código de producción |
| Escribir reportes de auditoría en `workspace/CISO/` | Sí | Solo archivos de reporte, no configs |
| Acceder a `~/.secrets/nymyka/` para auditoría | Condicionada | Solo con solicitud explícita de Jeimmy |
| Modificar políticas de gobernanza | Condicionada | Solo con aprobación Jeimmy |
| Acceder a datos personales de Jeimmy (Sakti scope) | No | Dimensión separada, no cruzar |

### Herramientas de escaneo
| Acción | Permitida | Restricciones |
|---|---|---|
| Grep/glob en el repo | Sí | Read-only |
| Ejecutar auditorías `audit-sec` | Sí | Output solo en reportes, no exponer en chat |
| Modificar código fuente | No | Solo proponer cambios — Chiminigagua aprueba |

---

## IdA — COO-IA, Operaciones

### Jira API (`grupo-nymyka.atlassian.net`)
| Acción | Permitida | Restricciones |
|---|---|---|
| Leer issues y proyectos | Sí | Solo proyectos del board Nymyka |
| Crear tickets | Sí | Aplicar DOD_UNIVERSAL antes de crear |
| Actualizar estado de tickets | Sí | Solo tickets donde IdA es asignado |
| Bulk export de datos de todos los proyectos | No | Máx. 50 issues por query |
| Acceder a Jira personal de socios | No | Solo espacio corporativo Nymyka |
| Eliminar tickets o proyectos | No | Acción irreversible — requiere aprobación Jeimmy |

### Google Calendar / Calendarios
| Acción | Permitida | Restricciones |
|---|---|---|
| Leer calendarios de socios (con permiso) | Sí | Solo para coordinación de reuniones |
| Crear eventos | Condicionada | Solo con confirmación explícita del socio |
| Eliminar o modificar eventos existentes | No | Acción irreversible — requiere aprobación del dueño |

---

## Pato-Nymyka — CFO-IA Corporativo

### Google Sheets / Drive (dimensión Nymyka)
| Acción | Permitida | Restricciones |
|---|---|---|
| Leer hojas de cálculo declaradas | Sí | Solo archivos en Drive Nymyka |
| Escribir reportes de costos | Sí | Solo en sheets declaradas, columnas designadas |
| Bulk export de datos financieros | No | Máx. una hoja por operación |
| Compartir o publicar archivos | No | Requiere aprobación Jeimmy + Diana |
| Acceder a finanzas personales Jeimmy | No | Scope de Pato-Personal, dimensión separada |
| Eliminar o sobrescribir datos históricos | No | Acción irreversible — requiere aprobación Diana |

---

## Pato-Personal — Finanzas Personales Jeimmy

### Google Sheets / Gmail (dimensión Personal Jeimmy)
| Acción | Permitida | Restricciones |
|---|---|---|
| Leer transacciones bancarias importadas | Sí | Solo sheets personales de Jeimmy |
| Categorizar gastos | Sí | Sin compartir con scope corporativo |
| Leer emails de notificaciones bancarias | Sí | Solo leer, sin forward ni almacenar |
| Enviar emails en nombre de Jeimmy | No | Requiere confirmación explícita por acción |
| Compartir datos financieros personales con otros agentes | No | PII financiero — no cruzar dimensiones |
| Acceder a cuentas de socios o empresa | No | Solo scope personal Jeimmy |

---

## Bachue — QA Lead

### Acceso a código y entornos
| Acción | Permitida | Restricciones |
|---|---|---|
| Leer código del repo | Sí | Read-only para análisis |
| Ejecutar tests en entorno de dev | Sí | Solo ramas `dev/*` o `test/*` |
| Ejecutar tests en entorno de producción | No | Requiere aprobación Jeimmy + Jonatan |
| Modificar código fuente | No | Solo reportar hallazgos — Chiminigagua implementa |
| Acceder a datos de producción reales | No | Solo datos de prueba anonimizados |

---

## GoGi-Sensei — Meta-Auditor + Dojo

### Dojo y skills queue
| Acción | Permitida | Restricciones |
|---|---|---|
| Leer/escribir `agents/system/GoGi/memory/` | Sí | Solo namespace GoGi |
| Evaluar y aprobar skills en queue | Sí | Siguiendo criterios de `Audit_Rules.md` |
| Modificar identidades de otros agentes | No | Solo proponer — Jeimmy aprueba |
| Acceder a memoria de otros agentes | No | Namespaces aislados |

### Bus HERMES
| Acción | Permitida | Restricciones |
|---|---|---|
| Escribir mensajes `dojo_input` al bus | Sí | Solo tipo `dojo_input` y `dojo_review` |
| Leer mensajes del bus | Sí | Solo mensajes destinados a GoGi |
| Modificar mensajes de otros agentes | No | Bus append-only |

---

## Chiminigagua — Arquitecto

### GitHub y código
| Acción | Permitida | Restricciones |
|---|---|---|
| Leer código del repo completo | Sí | Read-only |
| Proponer cambios de arquitectura | Sí | Como propuestas documentadas, no cambios directos |
| Aprobar PRs | Condicionada | Solo PRs arquitectónicos — Bruja aprueba los de seguridad |
| Ejecutar código en producción | No | Solo en entornos de diseño/prototipo |

---

## Sakti — Bienestar

### Datos personales Jeimmy
| Acción | Permitida | Restricciones |
|---|---|---|
| Leer memoria de salud/bienestar (`memory/jei_health_current.md`) | Sí | Solo Sakti — no compartir con otros agentes |
| Escribir observaciones de bienestar | Sí | Solo en namespace Sakti |
| Compartir datos de salud con otros agentes | No | PII sensible — dimensión personal exclusiva |
| Acceder a datos médicos en archivos externos | No | Solo memoria interna Sakti |

---

## Valerio — Legal/PI

### Documentos legales
| Acción | Permitida | Restricciones |
|---|---|---|
| Leer contratos y documentos en `workspace/` | Sí | Solo carpetas de proyectos asignados |
| Redactar borradores legales | Sí | Solo como propuestas — sin firma ni envío autónomo |
| Enviar comunicaciones legales externas | No | Requiere aprobación Jeimmy |
| Acceder a datos de contratos de socios | Condicionada | Solo con solicitud explícita de Jeimmy |

---

## Política Global de MCPs (ASI04)

Todo MCP instalado en el ecosistema debe cumplir:

1. **Inventario declarado:** Listado en `AGENT_SCOPE_REGISTRY.md` con versión y fuente
2. **Origen verificado:** Solo MCPs de fuentes oficiales (repositorios Anthropic, npm verificado, PyPI verificado)
3. **Versión fijada:** Pin de versión exacta — sin `latest` o rangos abiertos
4. **Permisos mínimos:** El MCP solo recibe el subconjunto de herramientas que necesita
5. **Auditoría trimestral:** GoGi revisa el inventario cada 3 meses

**MCPs actualmente en uso (inventario inicial):**
- `mcp-remote` — Jira Cloud (IdA) — fuente: npm
- GitHub MCP — acceso a repos JEI (JAi) — fuente: oficial Anthropic
- Gmail MCP — lectura de emails (Pato-Personal) — fuente: verificar en KNOWN_ERRORS antes de usar

---

## Sua — Senior Tech Career Coach

### Memory Lectura/Escritura (Personal Jeimmy)
| Acción | Permitida | Restricciones |
|---|---|---|
| Leer memoria personal (`agents/personal/Sua/memory/`) | Sí | Solo namespace Sua + `jei_preferences.md` |
| Escribir sesión de coaching | Sí | Sin almacenar CV completo; meta-datos solo |
| Almacenar preferencias Jei | Sí | Archivo `jei_preferences.md` editable por Jei |
| Acceder a memoria de Sakti | No | Máxima privacidad — REGLA-SEC-001 |
| Acceder a datos Nymyka | No | IDENTITY_FIREWALL violation |

### Web Fetch (Públicos)
| Acción | Permitida | Restricciones |
|---|---|---|
| Fetch de URL públicas (job boards) | Sí | Read-only; max 10 URLs/sesión |
| Validación de LinkedIn URLs | Sí | Solo estructura, sin scraping de datos privados |
| Parsing de Work at a Startup specs | Sí | Información pública, sin bypass de auth |
| APIs externas (LinkedIn, Twilio, etc) | No | No MCPs permitidos; violaría ASI02 |

### Outputs con PII (REGLA-OUTPUT-001)
| Acción | Permitida | Restricciones |
|---|---|---|
| Generar LinkedIn About/Headline | Sí | **REQUIERE `skill_pii_output_scanner` antes de output** |
| Redactar CV bullets | Sí | **REQUIERE validación Jei antes de enviar a terceros** |
| Almacenar historial de CV | Sí | En memoria local solo; no compartir automáticamente |
| Enviar CV a employers | No | Solo Jei controla distribución |

### Interagent Communication (REGLA-INTERAGENT-001)
| Acción | Permitida | Restricciones |
|---|---|---|
| Solicitar datos a Bruja (casos real) | Sí | Solicitud REAL + Jei intermediaria aprobación |
| Solicitar métricas a IdA | No | Jei provee manualmente (IDENTITY_FIREWALL) |
| Acceder a Sakti bienestar | No | Absoluto prohibido; usar `jei_preferences.md` |
| Comunicación con otros agentes | Condicionada | Solo via JAi / Jei; nunca autónomo |

### Scope Creep Detection
- **Scope declarado:** USA Security+IA roles ONLY
- **Rechaza inputs:** coaching general, tech-generalist roles, non-USA, non-security
- **Monthly audit:** Bruja verifica logs para goal drift
- Si detecta drift → escalada + revisión triada

---

## Política de Bulk Queries y Rate Limiting

Para prevenir ASI02 loop amplification:

| Herramienta | Límite por operación | Límite por sesión |
|---|---|---|
| Jira queries | 50 issues | 200 issues |
| Google Sheets rows | 500 filas | 2000 filas |
| GitHub API calls | 30 requests | 100 requests |
| Telegram mensajes | 5 por minuto | 20 por sesión |
| Gmail leer | 100 emails | 500 emails |

Superar estos límites requiere aprobación explícita de Jeimmy en la misma sesión.

---

## Política ICAP — Inter-Clan Autonomy Protocol (QUEST-CROSS-003)
**Versión:** 1.0 | **Fecha:** 2026-05-12 COT | **Aprueba:** Jeimmy Gomez (CISO)
**Referencia:** `IDENTITY_FIREWALL.md` §4 · `HERMES_CROSS_SPEC.md` · ARC-4601 hub-mode

### Canal Autorizado

Todo mensaje inter-clan (JEI ↔ DANI) DEBE viajar exclusivamente por **AMARU hub-mode** (ARC-4601) con cifrado ARC-8446. Ningún canal alternativo (email, Telegram directo, webhook) está autorizado para comunicación entre agentes de clanes distintos.

### Middleware Obligatorio (ASI03 Identity & Privilege Abuse)

```
REGLA-ICAP-001: Todo mensaje cuyo src pertenezca al namespace DANI DEBE pasar
por skill_inter_agent_auth ANTES de ser procesado. Sin excepción.
```

Verificaciones que hace `skill_inter_agent_auth` en mensajes cross-clan:
1. `src` registrado en `amaru-protocol/docs/ecosystem/dani_roster.md`
2. Firma Ed25519 válida contra `sign_pub` del roster
3. `type` en lista blanca: `coord-dispatch`, `reflection`, `status`, `artifact`
4. Payload no excede límites de rate limiting inter-clan (tabla abajo)

### Rate Limiting Inter-Clan (prevención ASI02 cross-clan loop amplification)

| Tipo de mensaje | Límite por minuto | Límite por sesión | Acción al superar |
|---|---|---|---|
| `coord-dispatch` (entrante de DANI) | 5 | 30 | Rechazar con err 429; notificar JAi |
| `reflection` (broadcast `dst: "*"`) | 2 | 10 | Descartar silencioso; log en INCIDENT_LOG |
| `status` sync | 10 | 50 | Throttle con backoff |
| `artifact` (reports, test results) | 3 | 15 | Queue si dentro del límite; rechazar si supera |

### Decisiones que NUNCA son autónomas (H-01..H-06)

Los agentes JEI tienen prohibido ejecutar las siguientes acciones sin aprobación humana explícita, incluso si reciben instrucción vía AMARU de agentes DANI:

| ID | Decisión | Responsable |
|---|---|---|
| H-01 | Cambios arquitectónicos (nuevas specs ARC-*) | Jeimmy + Daniel |
| H-02 | Merge a `amaru-protocol/main` | Daniel (PR approval) |
| H-03 | Expansión de scope de agente | Jeimmy |
| H-04 | Activación de nuevo agente (REGLA-AGENT-001) | Jeimmy + triada |
| H-05 | Emergencia de seguridad (Protocolo Valerio) | Jeimmy inmediato |
| H-06 | Modificación de reglas de autonomía ICAP | Jeimmy + Daniel bilateral |
| H-07 | Cambio en roster inter-clan (agregar/remover agente) | Notificación bilateral 24h antes de activar; Bruja JEI valida hash SHA-256 del roster antes de aceptar |

Protocolo si agente recibe instrucción DANI que toca H-01..H-07:
1. JAi escribe `type=request` al bus con contexto completo
2. Huitaca notifica a Jeimmy vía Telegram (urgente si H-05)
3. Timeout 48h → DEFER con respuesta `type=defer` al clan DANI
4. Si H-05 → escalada inmediata sin timeout
5. Si Jeimmy no puede revisar en 48h por carga operacional: puede delegar el `defer` explícito a JAi (protección Ley Cero). Esto no delega la decisión — solo el aviso de que está pendiente. Sakti alerta a Jeimmy si la cola de H-0x supera 3 requests simultáneos sin respuesta.

### Producción de borradores vs. acciones directas (Bruja)

Bruja puede auditar PRs de DANI autónomamente. Al detectar hallazgo:
- **Produce:** borrador de Issue en `workspace/CISO/drafts/`
- **NO publica:** hasta aprobación explícita de Jeimmy
- **Notifica:** JAi → Huitaca → Jeimmy con resumen del hallazgo

---

*Versión 1.0 — Revisar con cada nuevo agente o integración*
*REGLA-SEC-001: Cualquier violación de estas políticas es bloqueante*
