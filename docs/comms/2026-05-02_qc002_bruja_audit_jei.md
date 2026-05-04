# REPORTE AUDITORÍA ESTÁTICA — QUEST-CROSS-002
**Auditor:** Bruja (CISO-IA)
**Fecha:** 2026-05-02 COT
**Scope:** `reference/python/amaru/hub.py` + `reference/python/amaru/crypto.py`
**Repo:** `dereyesm/amaru-protocol` | HEAD `8421cc5` (post-PR#14)
**Método:** Inspección estática + grep (read-only, sin ejecución)

---

## Tabla de hallazgos (10 checks)

| # | Check | Resultado | Hallazgo | Severidad |
|---|---|---|---|---|
| 1 | Rate limiting (sig/data budget separado) | ❌ | No existe `RateLimiter` ni budgets separados | ALTA |
| 2 | Session table access control | ✅ | No hay endpoint de listado; `connections` dict es privado | ALTA |
| 3 | Dispatcher routing con sender verificado | ✅ | `MessageRouter.route()` + `FederationTable` routing correcto | ALTA |
| 4 | HKDF key rotation per sesión | ⚠️ | HKDF existe pero `info=b"HERMES-ARC8446-v1"` (no AMARU); salt=None (no session_id) | ALTA |
| 5 | Ed25519 hub firma + forwarded opacos | ✅ | E2E passthrough mode confirmado; `_emit_sent_receipt()` existe; hub no re-firma | ALTA |
| 6 | Channel whitelist (unknown → err) | ⚠️ | `capabilities` en HELLO/AUTH_OK pero sin validación de channel ni err frame | MEDIA |
| 7 | Session state machine (strict transitions) | ⚠️ | Auth model es HELLO→CHALLENGE→AUTH→AUTH_OK (no §18 INVITE/ACK) | ALTA |
| 8 | KCI identity binding en X25519 derivation | ❌ | No existe `(srcID, dstID, pubkey_fingerprint)` en HKDF info string | CRÍTICA |
| 9 | Downgrade protection (ECDHE fallback → err 1002) | ❌ | No hay protección explícita de downgrade; ECDHE fallback no rechaza | ALTA |
| 10 | Store-and-forward queue cap per (src,dst) | ⚠️ | `StoreForwardQueue` con `max_depth=1000` por peer existe; devuelve False al overflow; sin backpressure 503 | MEDIA |

---

## Detalle por check

### ✅ CHECK #2 — Session table (no leakage)
**Evidencia:** `connections` dict privado en `AmHub`. No hay endpoint `/sessions`. GC de conexiones manejada internamente. Sin leak de razón de desconexión.
**Veredicto:** IMPLEMENTADO CORRECTAMENTE

---

### ✅ CHECK #3 — Dispatcher routing
**Evidencia (hub.py:495-511):**
```python
async def route(self, payload: dict, sender: str) -> dict:
    await self._emit_sent_receipt(payload, sender)
    dst = payload.get("dst", "")
    if dst == "*":
        return await self._broadcast(payload, sender)
    else:
        return await self._unicast(payload, dst)
```
`FederationTable` (hub.py:293-389) maneja routing S2S. Sender excluido de broadcast. Routing lookup correcto.
**Veredicto:** IMPLEMENTADO CORRECTAMENTE

---

### ✅ CHECK #5 — Ed25519 + forwarded opacos
**Evidencia (hub.py:1-10):**
```
"The Hub operates in E2E passthrough mode: it routes ARC-8446 encrypted
envelopes without decryption. It is a routing convenience, not a trust boundary."
```
`_emit_sent_receipt()` (hub.py:513) emite SENT con firma hub. Hub NO re-firma frames de peers (forwarded opacos). `Ed25519PrivateKey` importado y usado en challenge-response (hub.py:1346-1359).
**Veredicto:** IMPLEMENTADO CORRECTAMENTE

---

### ❌ CHECK #1 — Rate limiting
**Evidencia:** Búsqueda exhaustiva en hub.py — NO existe:
- Clase `RateLimiter`
- Campo `sig_budget` o `data_budget`
- Método `check_limit()`
- Ningún mecanismo de rate limiting per-client-id

Solo existe `max_connections: int = 100` (HubConfig) — límite de conexiones totales, no rate limit.

**Impacto:** Agente puede hacer flood indefinido de mensajes sin restricción. Riesgo ASI04 (Resource Overload).
**Mitigación requerida:** Implementar `RateLimiter` con `sig_budget` y `data_budget` separados por `client_id`.

---

### ⚠️ CHECK #4 — HKDF key rotation
**Evidencia (crypto.py:153-158):**
```python
hkdf = HKDF(
    algorithm=hashes.SHA256(),
    length=32,
    salt=None,
    info=b"HERMES-ARC8446-v1",   # ← debería ser AMARU-ARC8446-ECDHE-v1
)
```
ECDHE mode (crypto.py:216-222) usa `info=b"HERMES-ARC8446-ECDHE-v1"` — string `HERMES` en lugar de `AMARU`.
`salt=None` en ambos modos — no se usa `session_id` como salt.

**Impacto:** Info string podría colisionar con versión anterior del protocolo (HERMES). Salt fijo = menor entropía por sesión.
**Mitigación:** Actualizar `info` a `b"AMARU-ARC8446-ECDHE-v1"` + usar `session_id` como salt.

---

### ⚠️ CHECK #6 — Channel whitelist
**Evidencia (hub.py:982-992):**
```python
client_caps = hello.get("capabilities", [])
# ...se loggea pero no se valida contra whitelist
```
`capabilities` se recibe y loggea pero no hay:
- Validación de channel desconocido
- `err` frame con code `unknown-channel`
- Whitelist en AUTH_OK

**Impacto:** ARC-4601 §18.5 capability negotiation no está implementada. Sin channel discrimination.
**Mitigación:** Implementar `_validate_channel()` con whitelist y `err` frame (§18.10).

---

### ⚠️ CHECK #7 — Session state machine
**Hallazgo:** El modelo de sesión real es `HELLO → CHALLENGE → AUTH → AUTH_OK` (diferente a §18 INVITE-based).
ARC-4601 §18 (channel-aware hub routing) describe INVITE/ACK para sesiones. El hub implementa el modelo base §15.
**Impacto:** §18.4 DELIVERED semantics (QUEUED/DELIVERED en reconnect) opera sobre el modelo de `StoreForwardQueue`, no sobre INVITE/ACK. El modelo es consistente internamente — la diferencia es semántica.
**Mitigación:** Aclaración documental con Dani: §18 extension no implementada en reference impl; store-and-forward como mecanismo equivalente.

---

### ❌ CHECK #8 — KCI identity binding
**Evidencia:** Búsqueda en crypto.py — NO existe:
- `srcID` / `dstID` en HKDF info
- `pubkey_fingerprint` en derivation context
- Identity binding en X25519 DH

**Impacto:** CRÍTICO. Si DH private key comprometida → attacker puede impersonar cualquier clan. No hay binding de identidad en la derivación de claves.
**Mitigación requerida:** Añadir a HKDF info string: `f"AMARU-ARC8446-{src_id}-{dst_id}-{pubkey_fp}"`.

---

### ❌ CHECK #9 — Downgrade protection
**Evidencia:** No hay:
- Código `1002` en hub.py
- Verificación de versión de protocolo pre-conexión
- Rechazo explícito de ECDHE fallback

Solo hay `client_version = hello.get("protocol_version", "0.1")` pero sin validación de versión mínima.
**Impacto:** Peers en versión antigua pueden negociar protocolo degradado sin ser rechazados.
**Mitigación:** Validar `protocol_version >= "0.5"` en HELLO; rechazar con `err` (code 1002) si menor.

---

### ⚠️ CHECK #10 — Queue cap
**Evidencia (hub.py:225-238):**
```python
class StoreForwardQueue:
    def __init__(self, max_depth: int = 1000):
        self._queues: dict[str, list[QueuedMessage]] = {}
        self.max_depth = max_depth

    def enqueue(self, dst: str, payload: dict, ttl_seconds: int = 604800) -> bool:
        queue = self._queues.setdefault(dst, [])
        if len(queue) >= self.max_depth:
            return False   # devuelve False, sin error 503 al sender
```
Queue cap existe (1000 per peer). Devuelve `False` en overflow — pero el sender NO recibe backpressure 503.
**Impacto:** Sender no sabe que su mensaje fue descartado. Sin presión de retroceso.
**Mitigación:** Emitir `err` frame al sender cuando `enqueue()` devuelve `False`.

---

## Resumen ejecutivo

| Resultado | Cantidad | Checks |
|---|---|---|
| ✅ IMPLEMENTADO | 3 | #2 Session table, #3 Dispatcher, #5 Ed25519 |
| ⚠️ PARCIAL | 4 | #4 HKDF, #6 Channel whitelist, #7 State machine, #10 Queue |
| ❌ NO EXISTE | 3 | #1 Rate limiting, #8 KCI binding, #9 Downgrade |

---

## Veredicto

**🔴 BLOQUEADO — No apto para green-light bilateral en estado actual**

**Críticos (bloquean Fase 1):**
- ❌ #1 Rate limiting — riesgo ASI04 inmediato
- ❌ #8 KCI identity binding — riesgo criptográfico CRÍTICO
- ❌ #9 Downgrade protection — riesgo ASI04

**Observaciones (resolubles pre-merge):**
- ⚠️ #4 HKDF info string "HERMES" → "AMARU" + salt=session_id
- ⚠️ #6 Channel whitelist — §18.5 no implementado
- ⚠️ #10 Queue backpressure — falta notificación al sender

---

## Acciones requeridas (propuesta para Dani)

| Prioridad | Check | Acción | Archivo |
|---|---|---|---|
| P0 | #8 KCI | Añadir identity binding a HKDF info | `crypto.py` |
| P0 | #1 Rate limit | Implementar `RateLimiter` per client_id | `hub.py` |
| P0 | #9 Downgrade | Validar `protocol_version >= 0.5` en HELLO | `hub.py` |
| P1 | #4 HKDF | Renombrar info + salt=session_id | `crypto.py` |
| P1 | #10 Queue | Emitir err frame en overflow | `hub.py` |
| P2 | #6 Channel | Implementar §18.5 whitelist + err frame | `hub.py` |

---

**Bruja — CISO-IA | 2026-05-02 COT**
**Repo auditado:** `dereyesm/amaru-protocol` HEAD `8421cc5`
**Próxima auditoría:** Post-fixes P0 (estimado: antes de tests bilaterales)
