# QUEST-003 Kick-off — Email Draft for JEI

| Field | Value |
|-------|-------|
| From | danielreyesma@gmail.com (via MomoshoD) |
| To | Jeimmy Gómez (Clan JEI) |
| Date | 2026-03-16 |
| Ref | QUEST-003-ECDHE-FORWARD-SECRECY |

---

## Bus Message (for relay dispatch)

```json
{"ts":"2026-03-16","src":"momoshod","dst":"jei","type":"quest_ping","msg":"QUEST-003: ECDHE Forward Secrecy. Per-message ephemeral X25519 DH. Spec: ARC-8446 s11.2. Depends: QUEST-002 COMPLETE. Full proposal: github.com/amaru-protocol/amaru/blob/main/docs/QUEST-003-ECDHE-FORWARD-SECRECY.md","ttl":14,"ack":[]}
```

## Email Draft

**Subject**: HERMES QUEST-003 — Forward Secrecy (ECDHE) — Kick-off

**Body**:

Jeimmy,

QUEST-002 cerrada bilateralmente. El canal E2E con AAD está operativo y verificado por ambos lados. Excelente trabajo.

El siguiente paso natural es QUEST-003: **Forward Secrecy via ECDHE** (Bruja finding B-04 — la última pieza crítica de crypto).

### ¿Qué resuelve?

Hoy, si la clave estática X25519 de cualquiera de los dos clanes se compromete, un adversario puede descifrar TODOS los mensajes pasados. Forward secrecy elimina este riesgo: cada mensaje usa un keypair efímero que se destruye inmediatamente después de usarse.

### Diseño técnico (resumen)

- **Per-message ephemeral X25519 keypair** — generado con CSPRNG, destruido tras DH
- **Single ephemeral DH**: `HKDF(X25519(eph_priv, peer_static_pub), info="HERMES-ARC8446-ECDHE-v1")`
- **No double-DH** — la firma Ed25519 ya autentica al sender (ARC-8446 §11.2.6)
- **Signature extendida**: `sign(ciphertext + eph_pub)` — bind del sender al ephemeral session
- **AAD incluye `eph_pub`** — previene sustitución MITM del key efímero
- **Backward compat**: presencia de `eph_pub` en envelope activa path ECDHE; sin él, path estático sigue funcionando

### Envelope v3

```json
{
  "eph_pub": "<hex 32B X25519 ephemeral>",
  "enc": "ed25519+x25519e+aes256gcm+hkdf",
  ...v2 fields...
}
```

### Timeline propuesto

| Fase | Target | Qué |
|------|--------|-----|
| Review | 17 Mar | Ambos revisan la propuesta |
| Phase 1 | 19 Mar | Tests locales independientes (8 tests cada uno) |
| Phase 2 | 22 Mar | Bilateral: ping/pong ECDHE vía relay |
| Phase 3 | 24 Mar | Documentación + activar `require_ecdhe=true` |

### Propuesta completa

https://github.com/amaru-protocol/amaru/blob/main/docs/QUEST-003-ECDHE-FORWARD-SECRECY.md

Con QUEST-003 complete, ARC-8446 llega a production-grade en crypto. La tríada Ed25519+X25519+AES-256-GCM con AAD+ECDHE cubre autenticidad, confidencialidad, integridad, y forward secrecy.

¿Lista para arrancar?

Daniel Reyes — Protocol Architect, Clan DANI
*Ref: QUEST-003-ECDHE-FORWARD-SECRECY | ARC-8446 §11.2 | HERMES v0.3.1-alpha*
