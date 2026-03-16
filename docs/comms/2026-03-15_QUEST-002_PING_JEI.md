# QUEST-002 Ping — Relay Bus Message + Email Draft

> Prepared by Team Bravo (Arena BR) | 2026-03-15
> HERMES dimension — no MCPs used. Daniel sends from appropriate dimension.

---

## 1. HERMES Bus Message (JSONL)

Append this line to the relay (`dani_outbox.jsonl` via heraldo-gateway or GitHub API):

```json
{"ts":"2026-03-15","src":"momoshod","dst":"jei","type":"quest","msg":"QUEST-002_AAD_PING: Friendly reminder — QUEST-002 (Bilateral AAD Adoption) has been open since 2026-03-08 with no response. The proposal and re-sealed message were sent 2026-03-09 (DANI-HERMES-005). Phase 1 local tests can be done independently. Full spec: https://github.com/dereyesm/hermes/blob/main/docs/QUEST-002-AAD-BILATERAL.md — Please confirm receipt and estimated timeline. If blocked, let us know how we can help.","ttl":7,"ack":[]}
```

---

## 2. Email Draft for Jeimmy

**From**: danielreyesma@gmail.com (send from MomoshoD or MomoFinance dimension)
**To**: [Jeimmy's email — Daniel knows it]
**Subject**: HERMES QUEST-002 — AAD Bilateral — Ping (7 days)

---

Hola Jeimmy,

Espero que estes bien. Te escribo porque QUEST-002 (Bilateral AAD Adoption) lleva 7 dias sin respuesta desde que envie la propuesta y el mensaje re-sealed el 9 de marzo (DANI-HERMES-005).

### Contexto rapido

QUEST-001 (security hardening de Bruja) esta COMPLETE de ambos lados. El siguiente paso natural es QUEST-002: que ambos clanes adopten AAD (Associated Authenticated Data) en los mensajes cifrados. Esto vincula los metadatos (src, dst, ts, type) al ciphertext via AES-256-GCM, previniendo manipulacion de metadatos sin deteccion.

### Que necesitas hacer (3 pasos)

**Phase 1 — Local (puedes hacer ya, sin coordinacion):**

1. **Actualizar tu rutina de cifrado** para pasar AAD cuando llamas a AES-256-GCM encrypt:
   ```python
   aad = json.dumps({"dst": dst, "src": src, "ts": ts, "type": msg_type},
                     sort_keys=True, separators=(',', ':')).encode('utf-8')
   # Pasar aad como associated_data al cifrar
   ```

2. **Actualizar tu rutina de descifrado** para reconstruir el AAD desde el envelope del mensaje y pasarlo al decrypt. Si el AAD no coincide, GCM rechaza el descifrado (InvalidTag).

3. **Correr dos tests locales:**
   - Positivo: seal con AAD, open con mismo AAD → exito
   - Negativo: seal con AAD, open con AAD modificado → falla (InvalidTag)

**Phase 2 — Bilateral (necesita coordinacion):**

4. Enviar un mensaje `quest_pong` por el relay con AAD activo. Yo lo descifro y confirmo.

**Phase 3 — Cierre:**

5. Ambos confirmamos interop. QUEST-002 → COMPLETE.

### Sobre el formato del envelope

La propuesta unifica ambos formatos (ver tabla en el doc). Los campos AAD son `dst`, `src`, `ts`, `type` — serializados como JSON canonico (keys sorted, sin espacios). El doc completo:
https://github.com/dereyesm/hermes/blob/main/docs/QUEST-002-AAD-BILATERAL.md

### Nota sobre HKDF (cambio en key derivation)

Desde DANI-HERMES-005, los mensajes se sellan con HKDF-SHA256 en vez de SHA-256 directo. El campo `enc` indica la version:
- `ed25519+x25519+aes256gcm` → SHA-256 legacy
- `ed25519+x25519+aes256gcm+hkdf` → HKDF-SHA256 (actual)

Tu implementacion deberia soportar ambos durante la transicion.

### Timeline

El timeline original era 5 dias (Mar 9-13). Entiendo que puede haber habido otros compromisos. Si necesitas mas tiempo o estas bloqueada con algo, dimelo y ajustamos. Lo importante es mantener la comunicacion abierta.

Tambien tengo en borrador QUEST-003 (Forward Secrecy / ECDHE) que depende de que QUEST-002 este completa.

Un saludo,
Daniel

---

*Ref: QUEST-002-AAD-BILATERAL | DANI-HERMES-005 | ARC-8446 v1.1*
