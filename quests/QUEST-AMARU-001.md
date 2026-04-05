# Quest-Amaru-001: La Serpiente Despierta

*HERMES se transforma en Amaru. El protocolo cambia de nombre, no de alma.*

---

## Contexto

El Consejo Ampliado (5 voces, MULTI-060, 2026-04-04) decidio renombrar el ecosistema con identidad quechua:

| Antes | Despues | Significado |
|-------|---------|-------------|
| HERMES (protocolo) | **Amaru** | Serpiente cosmica andina — conecta mundos |
| Heraldo (sensor email) | **Wayra** | Viento — lo que trae las senales |
| Tinkuy (ecosistema) | **Tinkuy** | Encuentro — se mantiene |
| Kitsune (gateway local) | **Kitsune** | Zorro — se mantiene |

**Por que**: Los nombres griegos eran placeholder. La familia quechua refleja la identidad cultural del proyecto y forma un moat narrativo coherente: Amaru conecta, Wayra sensa, Tinkuy reune, Kitsune ejecuta local.

**Org GitHub**: `amaru-protocol` (reservada).

---

## Que cambia (scope tecnico)

### Package & CLI
| Componente | Antes | Despues |
|-----------|-------|---------|
| PyPI package | `hermes-protocol` | `amaru-protocol` |
| CLI command | `hermes` | `amaru` |
| Python module | `hermes/` | `amaru/` |
| Import paths | `from hermes.*` | `from amaru.*` |

### Runtime
| Componente | Antes | Despues |
|-----------|-------|---------|
| Config dir | `~/.hermes/` | `~/.amaru/` |
| Hub daemon | `com.hermes.hub` | `com.amaru.hub` |
| Agent daemon | `com.hermes.agent-node` | `com.amaru.agent-node` |
| Bus local | `~/.hermes/bus.jsonl` | `~/.amaru/bus.jsonl` |
| Peers | `~/.hermes/peers/` | `~/.amaru/peers/` |
| Keys | `~/.hermes/keys/` | `~/.amaru/keys/` |

### Docs & Specs
- README, CHANGELOG, specs (ARC/ATR/AES): "HERMES" → "Amaru" en titulos y descripciones
- Acronimo legacy: "HERMES" puede aparecer como referencia historica donde tenga sentido

### Lo que NO cambia
- Specs IDs (ARC-XXXX, ATR-XXXX) — se mantienen
- Wire protocol — los mensajes no cambian formato
- Criptografia — keys, signatures, peers intactos
- Bus JSONL format — mismo schema
- Hub S2S protocol — mismo handshake

---

## Tu parte (para JEI y futuros colaboradores)

### Paso 1 — Lee y opina (antes de que ejecutemos)

Este quest es una **invitacion a opinar**, no una notificacion unilateral.

Si ves algo que no hayamos considerado sobre el rebrand — impacto en tu setup, confusion de nombres, mejor alternativa — tienes **48 horas** para responder via HERMES:

```bash
hermes send dani "QUEST-AMARU-001: [tu feedback]"
```

Si no hay feedback en 48h, ejecutamos el rebrand en code.

### Paso 2 — Migra tu instalacion (despues del rebrand)

Cuando el rebrand este en code (te avisamos via HERMES), ejecuta:

```bash
# 1. Pull la ultima version
cd ~/hermes   # o donde tengas el repo clonado
git pull origin main

# 2. Reinstala
cd reference/python
uv sync

# 3. Verifica CLI
amaru status    # antes era: hermes status

# 4. Migra runtime dir
# El instalador lo hara automatico, pero si prefieres manual:
mv ~/.hermes ~/.amaru
# Symlink de transicion (opcional, por 30 dias):
ln -s ~/.amaru ~/.hermes
```

### Paso 3 — Verifica federation

```bash
amaru status          # debe mostrar tu clan + peers
amaru send dani "migration complete"
```

---

## Timeline

| Fecha | Evento |
|-------|--------|
| 2026-04-05 | Quest publicado. JEI notificado via HERMES |
| 2026-04-07 | Deadline feedback JEI (48h) |
| 2026-04-07+ | Rebrand mecanico ejecutado en code |
| 2026-04-08 | JEI migra su instalacion |
| 2026-04-24 | hermes-relay sunset (ultimo vestigio del nombre viejo) |

---

## Quest completada cuando

- [ ] JEI recibio notificacion y tuvo oportunidad de opinar
- [ ] Python module renombrado `hermes/` → `amaru/`
- [ ] CLI responde a `amaru` (no `hermes`)
- [ ] `~/.amaru/` es el runtime dir (con symlink `~/.hermes/` transitorio)
- [ ] 1563+ tests pasan en verde
- [ ] TestPyPI tiene `amaru-protocol` publicado
- [ ] JEI migro su instalacion
- [ ] Docs/specs actualizados (segunda pasada)

---

*"La serpiente no muere al mudar de piel. Despierta."*
