# First Contact: Plan de Integracion Daniel + Jeimmy

> Primer HERMES Gateway entre dos clanes. Fin de semana 8-9 Mar 2026.

## Los Dos Clanes

### Jeimmy — Perfil

- **Cybersecurity MSc** (UNIR, Espana)
- **PMP certified**, 10+ anos de experiencia en gestion de proyectos
- Potencial co-arquitecta de HERMES, especialmente:
  - **Phase 2 (Security & Identity)**: ARC-8446 (Ed25519/PQC), DID-lite, JWT gateways
  - **Governance**: Disenar el framework multi-clan con rigor de PMP
  - **Phase 5**: Co-autora del paper academico (arXiv)

```
Clan Momosho D. (Daniel)              Clan Huitaca (Jeimmy)
+-------------------------------+     +-------------------------------+
| 28 skills, 6 dimensiones     |     | Skills de Jeimmy             |
| Heraldo (mensajero)          |     | Huitaca (mensajera)          |
| Dojo (controlador)           |     | Su propio Dojo               |
| Focus: Protocol design,      |     | Focus: Cybersecurity,        |
|   telecom, architecture      |     |   project mgmt, governance   |
+-------------+-----------------+     +-------------+-----------------+
              |                                     |
         [Gateway]                             [Gateway]
         momosho-d                             huitaca
              |                                     |
              +------- Agora Compartido ------------+
                       (Git repo o carpeta compartida)
```

## Prerequisitos

- [ ] Jeimmy tiene Claude Code instalado
- [ ] Jeimmy tiene Python 3.10+
- [ ] Daniel tiene el CLI de HERMES listo (hermes init, publish, peer, send)
- [ ] Definir donde vive el Agora (Git repo o carpeta compartida)

## Plan Paso a Paso

### Sabado Manana: Setup de Jeimmy (~1 hora)

**1. Clonar HERMES**
```bash
git clone https://github.com/dereyesm/hermes.git ~/hermes
cd ~/hermes/reference/python
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**2. Inicializar su clan**
```bash
mkdir ~/huitaca-clan
python -m hermes init huitaca "Clan Huitaca" --dir ~/huitaca-clan
```

**3. Definir sus primeros skills en gateway.json**
Jeimmy edita `~/huitaca-clan/gateway.json` y agrega sus agentes:
```json
{
  "agents": [
    {
      "internal": {"namespace": "general", "agent": "huitaca"},
      "external": "huitaca-herald",
      "published": true,
      "capabilities": ["inter-clan-messaging"]
    }
  ]
}
```

**4. Crear estructura de Claude Code (si no existe)**
```
~/.claude/
  skills/
    dojo/SKILL.md          # Su controlador
    huitaca/SKILL.md       # Su heraldo/mensajera
  sync/
    bus.jsonl              # Su bus interno
    routes.md              # Su tabla de rutas
```

### Sabado Tarde: First Contact (~30 min)

**5. Crear Agora compartido**

Opcion A — Carpeta compartida (mas rapido):
```bash
# En una carpeta que ambos puedan ver (iCloud, Drive, o USB)
mkdir -p /shared/hermes-agora/{profiles,inbox,attestations,quest_log}

# Daniel
cd ~/daniel-clan && rm -rf .agora && ln -s /shared/hermes-agora .agora

# Jeimmy
cd ~/huitaca-clan && rm -rf .agora && ln -s /shared/hermes-agora .agora
```

Opcion B — Git repo (mas limpio):
```bash
# Crear repo en GitHub: hermes-agora
# Ambos lo clonan como .agora/
```

**6. Publicar perfiles**
```bash
# Daniel
python -m hermes publish --dir ~/daniel-clan

# Jeimmy
python -m hermes publish --dir ~/huitaca-clan
```

**7. Agregar peers**
```bash
# Jeimmy agrega a Daniel
python -m hermes peer add momosho-d --dir ~/huitaca-clan

# Daniel agrega a Jeimmy
python -m hermes peer add huitaca --dir ~/daniel-clan
```

**8. Primer mensaje!**
```bash
# Daniel envia
python -m hermes send huitaca "First Contact! Los clanes estan conectados." --dir ~/daniel-clan

# Jeimmy lee
python -m hermes inbox --dir ~/huitaca-clan
```

**9. Jeimmy responde**
```bash
python -m hermes send momosho-d "Huitaca responde: el puente esta abierto." --dir ~/huitaca-clan

# Daniel lee
python -m hermes inbox --dir ~/daniel-clan
```

### Domingo: Celebracion + Diseno

**10. Medallas ganadas**

| Medal | Name | Earned by |
|-------|------|-----------|
| FC | First Contact | Ambos clanes |
| AG | Agora Pioneer | El primero que publico |
| FK | Family Kizuna | Daniel + Jeimmy conectados |

**11. Disenar juntos**
- Que skills quiere Jeimmy en su clan?
- Que dimensiones necesita?
- Como quiere que se llame su Dojo?
- Primera mision BR cross-clan?

**12. Skills sugeridos para Clan Huitaca (basados en perfil de Jeimmy)**

| Skill sugerido | Rol | Razon |
|---------------|-----|-------|
| **Huitaca** (Heraldo) | Mensajera inter-clan | Ya definida |
| **Cybersec Architect** | Diseno de seguridad, crypto, threat modeling | MSc Cybersecurity UNIR |
| **Project Commander** | Gobernanza, planning, KPIs, milestones | PMP 10+ anos |
| **Audit Sentinel** | Revision de specs, compliance, risk assessment | Combo cybersec + PMP |

Jeimmy define los nombres finales. Estos son roles sugeridos basados en su perfil.

**13. Contribucion directa a HERMES (repo publico)**

Jeimmy puede ser la primera contribuidora externa de HERMES:
- **ARC-8446** (Message Signing): Liderar el diseno de crypto identity (Ed25519, PQC)
- **Governance spec**: Nuevo ARC para gobernanza multi-clan (su experiencia PMP)
- **Security review**: Auditar ARC-3022 gateway, ARC-1918 firewall, inbound validation
- **Phase 5 paper**: Co-autora del arXiv paper (perspectiva cybersec + governance)

## Que NO hacer este fin de semana

- No preocuparse por criptografia (TOFU es suficiente por ahora)
- No montar un servidor — todo es archivos
- No over-engineerear los skills de Jeimmy — empezar con 1-3 y crecer
- No intentar automatizar todo — el protocolo es deliberado (Daniel/Jeimmy aprueban)

## Resultado Esperado

Al final del domingo:
1. Dos clanes con identidad propia
2. Un Agora compartido con dos perfiles
3. Al menos un mensaje intercambiado
4. Jeimmy con su propio Dojo + Huitaca funcionando
5. Plan para la primera mision BR cross-clan

---

*"No buscamos al mas fuerte. Buscamos a los que juntos son invencibles."*
