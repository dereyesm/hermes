# JEI Environment Assessment — Prompt Chain

> Para Jeimmy (Clan JEI). Ejecutar cada prompt en orden en Claude Code.
> Cada prompt construye sobre el anterior — no saltar pasos.
> Tiempo estimado: 30-45 min.

---

## Prompt 1: Inventario del entorno

Copia y pega esto en tu Claude Code:

```
Necesito que hagas un inventario completo de mi entorno de trabajo con Claude Code.

1. Lee ~/.claude/CLAUDE.md (si existe) y reporta:
   - Que reglas tengo definidas?
   - Que dimensiones/proyectos estan configurados?
   - Hay un firewall de identidad (separacion de cuentas/MCPs)?

2. Lista todos los archivos en ~/.claude/ (sin entrar a subcarpetas profundas):
   - settings.json existe? Que hooks tengo configurados?
   - Hay skills en ~/.claude/skills/? Cuales?
   - Hay memoria en ~/.claude/projects/? Cuantos directorios?
   - Hay sync/ o bus.jsonl?

3. Revisa ~/.claude/session-logs/ — hay logs de sesiones anteriores?

4. Revisa si hay un exit protocol definido en ~/.claude/rules/

5. Genera un reporte en tabla:

| Area | Estado | Nota |
|------|--------|------|
| CLAUDE.md global | existe/no | ... |
| Settings/hooks | N hooks | ... |
| Skills | N skills | ... |
| Memoria | N proyectos | ... |
| Session logs | existe/no | ... |
| Exit protocol | existe/no | ... |
| Bus HERMES | existe/no | ... |

No cambies nada — solo observa y reporta.
```

---

## Prompt 2: Assessment de madurez

Copia y pega esto despues de obtener el reporte del Prompt 1:

```
Basandote en el inventario anterior, evalua mi entorno en estas 8 areas.
Escala: 0 (no existe) / 1 (basico) / 2 (funcional) / 3 (maduro).

| # | Area | Que evaluar | Score | Evidencia |
|---|------|------------|-------|-----------|
| 1 | **Identidad** | Tengo CLAUDE.md con reglas claras? Hay separacion de contextos (personal/trabajo)? | ? | ? |
| 2 | **Memoria** | Mis sesiones persisten conocimiento? Hay MEMORY.md con indice? Topic files? | ? | ? |
| 3 | **Skills** | Tengo skills especializados? Estan registrados? Tienen SKILL.md con identidad clara? | ? | ? |
| 4 | **Hooks** | Tengo hooks configurados (pre-commit, session start/stop, prompt submit)? | ? | ? |
| 5 | **Exit Protocol** | Al cerrar sesion, se guarda estado? Se hace commit? Se actualiza memoria? | ? | ? |
| 6 | **Session Logs** | Hay registro historico de que se hizo en cada sesion? Decision journal? | ? | ? |
| 7 | **HERMES Integration** | Bus activo? Peers configurados? Hub funcional? Agent node corriendo? | ? | ? |
| 8 | **Security** | Secretos en ~/.secrets/ con permisos 600? .gitignore protege credenciales? Lockfiles al dia? | ? | ? |

Calcula el score total (max 24) y clasifica:

| Rango | Nivel | Descripcion |
|-------|-------|-------------|
| 0-6 | Novato | Entorno basico, sin persistencia ni estructura |
| 7-12 | Aprendiz | Tiene lo minimo, falta consistencia y automatizacion |
| 13-18 | Practicante | Buen entorno, puede mejorar en areas especificas |
| 19-24 | Maestro | Entorno completo, optimizado, con automatizaciones |

Se honesto — el objetivo es mejorar, no quedar bien.
```

---

## Prompt 3: Mapa de dimensiones

```
Analiza como organizo mi trabajo. Revisa:

1. Mis directorios principales de proyectos (ls ~/ y ~/Dev/ si existe)
2. Cuantos CLAUDE.md por proyecto tengo?
3. Hay separacion clara entre trabajo personal, profesional, y proyectos open-source?

Propone un mapa de dimensiones basado en lo que encuentres:

| Dimension | Directorio | Tipo | CLAUDE.md | Memoria |
|-----------|-----------|------|-----------|---------|
| ? | ? | personal/profesional/open-source | si/no | si/no |

Las dimensiones son "contextos de trabajo" — cada uno con sus propias reglas, 
cuentas, y skills. La clave es que NO se mezclen credenciales ni contextos.

Pregunta: en cuantos contextos diferentes trabajo? Estan bien separados?
```

---

## Prompt 4: Ruta de mejora personalizada

```
Basandote en el assessment (Prompt 2) y el mapa de dimensiones (Prompt 3), 
genera una ruta de mejora con 3 niveles. YO ELIJO que implementar — no hagas 
nada automaticamente.

## Nivel 1: Fundamentos (1 sesion, ~30 min)
Lista las 3-5 acciones mas importantes para subir de nivel.
Solo lo esencial — lo que da mas impacto con menos esfuerzo.

## Nivel 2: Estructura (2-3 sesiones)
Acciones para tener un entorno robusto:
- Memoria persistente
- Exit protocol basico
- Session logs
- Skills especializados (si aplica)

## Nivel 3: Automatizacion (cuando quieras)
Acciones avanzadas:
- Hooks automaticos
- Bus HERMES para coordinacion
- Dashboard de estado
- Backup de memoria

Para CADA accion, incluye:
- Que hacer (1 linea)
- Por que importa (1 linea)
- Comando o archivo a crear
- Tiempo estimado

IMPORTANTE: Esto es un menu, no una obligacion. Elige lo que te sirva.
No tienes que implementar todo. Un buen CLAUDE.md ya es un salto enorme.
```

---

## Prompt 5: Implementar lo elegido

```
Quiero implementar [las acciones que elegi del Prompt 4].

Hazlo paso a paso, explicandome que hace cada cambio.
Si algo requiere mi decision (nombre de dimension, que reglas poner), 
preguntame antes de escribir.

Al terminar, muestra un diff de todo lo que cambio y pregunta si quiero 
hacer commit.
```

---

## Notas para JEI

- **No hay respuestas incorrectas** — cada persona organiza su entorno diferente
- **El assessment es privado** — no necesitas compartir el reporte completo, solo lo que quieras
- **Empieza por Prompt 1 y 2** — eso te da el panorama. Los demas son opcionales
- **Si algo no aplica, saltalo** — no todos necesitan dimensiones o bus HERMES
- **El exit protocol es lo que mas impacto tiene** — un cierre de sesion ordenado vale mas que 10 skills

---

---

## Checklist de Buenas Practicas — Claude Code Environment

Referencia rapida. Marca lo que ya tienes, identifica lo que falta.

### Identidad y Contexto
- [ ] `~/.claude/CLAUDE.md` existe con reglas globales
- [ ] Cada proyecto tiene su propio `CLAUDE.md` (no solo el global)
- [ ] Separacion clara de dimensiones (personal vs trabajo vs open-source)
- [ ] Firewall de identidad: cada dimension tiene MCPs permitidos/prohibidos
- [ ] Nunca se cruzan credenciales entre contextos

### Memoria Persistente
- [ ] `~/.claude/projects/<proyecto>/memory/MEMORY.md` como indice puro (1 linea por entrada)
- [ ] Topic files en `memory/*.md` para contenido detallado (no inline en MEMORY.md)
- [ ] MEMORY.md bajo 200 lineas (hard limit)
- [ ] Feedback memories: correcciones y confirmaciones del usuario guardadas
- [ ] Project memories: decisiones, estados, deadlines con fechas absolutas

### Skills
- [ ] Skills definidos en `.claude/skills/` con SKILL.md cada uno
- [ ] Cada SKILL.md tiene: identidad, dominio, funciones, firewall
- [ ] Skills registrados en `registry.json` (si usas registry)
- [ ] Separacion skill global (delibera) vs skill de dimension (ejecuta)

### Hooks y Automatizacion
- [ ] `~/.claude/settings.json` con hooks configurados
- [ ] Hook `UserPromptSubmit` para inyectar contexto (fecha, estado, etc.)
- [ ] Hook `SessionStart` para inicializacion (sync, welcome, estado)
- [ ] Pre-commit hooks para validar antes de commitear

### Exit Protocol
- [ ] Al cerrar sesion: harvest de lo hecho (que, decisiones, insight, pendiente)
- [ ] Session log en `~/.claude/session-logs/YYYY-MM.md`
- [ ] Memoria actualizada con patrones confirmados
- [ ] Commit + push de cambios pendientes
- [ ] Next session prompt escrito (para arrancar sin ramp-up)

### Session Logs
- [ ] Formato consistente: fecha, proyecto, duracion, que se hizo, insight
- [ ] Decision journal: las decisiones no-obvias y su razon
- [ ] No es debug trace — es lo que haria la proxima sesion mas inteligente
- [ ] Dedup check: no duplicar entries del mismo dia/dimension

### Seguridad
- [ ] `~/.secrets/` con permisos 700 (directorio) y 600 (archivos)
- [ ] `.gitignore` protege: `.env`, `*.secret`, `credentials*.json`, `tokens*.json`
- [ ] Dependencias criticas pineadas con `==` en pyproject.toml
- [ ] Lockfiles (`uv.lock`, `package-lock.json`) commiteados y al dia
- [ ] Nunca commitear API keys, tokens, o passwords

### Comunicacion Inter-Agente (HERMES — opcional)
- [ ] `~/.hermes/` existe con `gateway.json` y keys
- [ ] Bus activo (`bus.jsonl`) con mensajes entre sesiones
- [ ] Hub configurado y funcional (si se usa modo hosted)
- [ ] Peers registrados con pub keys verificadas
- [ ] Agent Node corriendo con dispatch rules

### Workflow Git
- [ ] Commits con formato consistente: `type(scope): mensaje`
- [ ] Co-Authored-By en commits asistidos por AI
- [ ] Nunca force push a main sin aprobacion
- [ ] PRs para repos compartidos (no push directo a main)
- [ ] Branch protection en repos criticos

### Eficiencia
- [ ] Modelo correcto por tarea: Opus para pensar, Sonnet para hacer, Haiku para buscar
- [ ] Sesiones de max 2-3h enfocadas (context acumulado = mas caro)
- [ ] Agents paralelos para tareas independientes
- [ ] Plan mode para tareas no triviales antes de escribir codigo
- [ ] Read before write — entender codigo existente antes de cambiarlo

---

*Preparado por Daniel Reyes (Clan MomoshoD) — Apr 4, 2026*
*"La tecnologia con alma te libera tiempo para dedicar al compartir."*
