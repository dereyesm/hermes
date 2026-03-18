# HERMES Install — Clan JEI Onboarding

> One-command setup. You connect, I'm already here.

## Bus Message (relay dispatch)

```json
{"ts":"2026-03-18","src":"dani","dst":"jei","type":"quest","msg":"HERMES INSTALL ready. Run: git clone + pip install + hermes install --clan-id jei. DANI node already listening. Connect now.","ttl":7,"ack":[]}
```

## Email Draft

**To**: Jeimmy (Clan JEI)
**Subject**: HERMES is ready — 3 commands, 30 seconds

---

Jei,

HERMES install esta listo. Mi Agent Node ya esta corriendo y escuchando.

### Que hacer

```bash
git clone https://github.com/dereyesm/hermes.git
cd hermes/reference/python
pip install -e .
hermes install --clan-id jei --display-name "Clan JEI"
```

30 segundos. Eso es todo.

### Que va a pasar

1. Se crea `~/.hermes/` con tu configuracion y bus
2. Se generan tus llaves Ed25519 + X25519 (criptografia E2E)
3. Se instala un LaunchAgent que mantiene tu daemon vivo
4. Se registran 3 hooks en Claude Code (mensajes pendientes al abrir sesion, refresh en comandos /hermes, recordatorio al salir)
5. Tu Mac suena con notificacion: *"You're connected as jei!"*
6. Mi Mac suena al mismo tiempo — ya estamos conectados

### Despues del install

Enviame tu fingerprint (aparece en el output del install). Con eso completo el bilateral ECDHE y te mando un mensaje sellado de prueba.

```bash
hermes status          # verificar que todo esta bien
hermes bus --pending   # ver mensajes pendientes
```

### Si algo falla

```bash
hermes uninstall       # deshacer todo limpio
hermes uninstall --purge  # borrar todo incluyendo llaves
```

Pero no va a fallar. 605 tests. Todo green.

---

Te espero conectada.

— D
