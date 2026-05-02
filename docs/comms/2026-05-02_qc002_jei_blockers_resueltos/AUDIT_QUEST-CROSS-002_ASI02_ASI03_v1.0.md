# AUDITORÍA SEGURIDAD: QUEST-CROSS-002 Bilateral JEI↔DANI
**Versión:** 1.0 (Fase 1)  
**Fecha:** 2026-04-29 COT  
**Lead Auditoría:** Bruja (CISO-IA)  
**Scope:** ASI02 (Tool Misuse & Exploitation) + ASI03 (Identity & Privilege Abuse)  
**Baseline:** QUEST-006 bilateral (auditoría previa pasada)  
**Estado:** 🔴 PENDIENTE EJECUCIÓN (bloqueado por confirmación Dani)

---

## 🎯 Objetivo

Validar que escalado de QUEST-006 (bilateral) a QUEST-CROSS-002 (multicast JEI↔DANI) **no introduce nuevos vectores de ataque** en:
- **ASI02:** Tool Misuse (rate limiting, unauthorized bulk ops, dispatcher hijack)
- **ASI03:** Identity & Privilege Abuse (session spoofing, elevation of privilege)

---

## 📋 Matriz de amenazas identificadas (ACTUALIZADO 30-abr — Feedback Dani Issue #13)

| ID | Amenaza | Severidad | Clasificación OWASP | Vector | Mitigación | Test |
|---|---|---|---|---|---|---|
| **ASI04-01** *(fue ASI02-01)* | Rate limiting bypass (dispatch loop) | ALTA | **ASI04 Resource Overload** | Agent loops `send()` sin backoff → resource exhaustion | Budget separado sig/data (RFC 3261 §26.4) | Test 2: Concurrent 20x |
| **ASI02-02** | Unauthorized bulk export (session table) | ALTA | ASI02 Tool Misuse | Hub expone session_id → {peers, timestamps} a client no-auth | Hub MUST maintain private session table, expose solo inactivity GC | Auditoría estática: hub.py FederationTable access control |
| **ASI07-01** *(fue ASI02-03)* | Dispatcher hijack (fake INVITE) | ALTA | **ASI07 Comm Poisoning** | Fake INVITE con spoofed sender → inter-agent routing compromised | Session table + INVITE ACK match (per ARC-4601 §18.3) | Test 1: Round-trip 3-hops (verif sender chain) |
| **ASI02-04** | Replay attack (old signature) | **CRÍTICA** *(escalado)* | **ASI07 + KCI** | Attacker replays old SENT/DELIVERED frame + long-term key compromise → impersonation | Anti-replay sliding-window (RFC 6479) + AAD=(sender_id, monotonic_counter, timestamp); HKDF keys nuevas por sesión | Test 13: Symmetric key derivation + sliding-window |
| **KCI-001** *(NUEVO)* | Key Compromise Impersonation | **CRÍTICA** | **KCI** | Si DH private key (JEI o DANI) se compromete → attacker puede impersonar otro clan | Identity binding en X25519 derivation context: `(srcID, dstID, pubkey_fingerprint)` | TBD: Test KCI resilience (new test 17) |
| **ASI04-02** *(NUEVO)* | Downgrade attack residual | ALTA | **ASI04 Resource Exhaustion** | Peers en v0.4.2a1 exponen fallback ECDHE (deprecated) → forced downgrade | Hub DEBE rechazar downgrade con `err` frame (code 1002) | TBD: Test forced downgrade (new test 18) |
| **ASI02-05** | Channel discrimination bypass | MEDIA | ASI02 Tool Misuse | Client sends `channel: "admin"` sin autorización → hub procesa | Frame validation + `err` rejection (unknown-channel code) | Test 5: Channel discrimination |
| **ASI02-06** | Man-in-the-middle (hub as proxy) | MEDIA | ASI02 Tool Misuse | Hub re-signs peer receipts (READ/PROCESSED) → modifica cadena de custodia | Hub MUST forward opaquely (NO re-sign per §8.3/§8.4) | Test 4: Receipt chain (sig validation) |
| **ASI07-02** *(NUEVO)* | Hub metadata oracle | MEDIA | **ASI07 Comm Poisoning** | AES-256-GCM no oculta frame size + timing + session_id → correlation en hub logs | Padding a 256-byte align + log retention cap (24h) + access control en hub_logs | TBD: Test metadata oracle (new test 19) |
| **ASI03-01** | Session hijacking (fake ACK) | ALTA | ASI03 Identity Abuse | Attacker sends ACK para sesión no-existente → spoofs estado | Session table lookup previa a ACK processing; estado DEBE estar en INVITE state | Test 1: Round-trip (ACK phase) + Test 6: Session maint |
| **ASI03-02** | Privilege escalation (auth bypass) | ALTA | ASI03 Identity Abuse | Legacy client (pre-§18) negocia caps no-existentes → hub otorga capacidades | Backward compat strict: pre-amendment hub + post-amendment client = graceful degrade | Test 7: Auth capabilities (legacy compat) |
| **ASI03-03** | Identity spoofing (fake Ed25519 sig) | ALTA | ASI03 Identity Abuse | Client sends SENT frame con hub's Ed25519 key (stolen) | Key rotation DEBE ocurrir per-sesión; signature verification DEBE usar hub's published key | Test 4: Receipt chain (sig on SENT) |
| **ASI04-03** *(NUEVO)* | Store-and-forward DoS amplification | MEDIA | **ASI04 Resource Exhaustion** | Attacker spams messages a offline peer → hub queue overflow | Per-`(src,dst)` queue cap (256 msgs max) + backpressure 503 | TBD: Test DoS amplification (new test 20) |
| **ASI03-04** | Privilege escalation via channel | MEDIA | ASI03 Identity Abuse | Attacker discovers internal channel name → negocia access | Channel whitelist DEBE estar en auth_ok (§18.5); unknown channels → `err` | Test 5: Channel discrimination |
| **ASI03-05** | Store-and-forward tampering | BAJA | ASI03 Identity Abuse | Mensaje en store-and-forward alterado entre enqueue y redelivery | Cifrado end-to-end (AES-256-GCM); hub no decripta en tránsito | Test 3: Offline queueing |

---

## 🔐 Verificaciones técnicas

### ASI02: Tool Misuse & Exploitation

#### 1. **Rate limiting — sig vs data budget separado**
```
Verificar en reference/python/amaru/hub.py:
- RateLimiter(sig_budget, data_budget) inicializado
- Per-client tracking: client_id → [sig_credits, data_credits]
- Sig frames (INVITE/BYE/NOTIFY) usan sig_budget
- Data frames (mensaje content) usan data_budget
- Depleción en uno NO afecta otro
```
**Criterio:** Código inspección + test concurrent bajo load
**Riesgo:** Bypass → agent puede flood indefinidamente

---

#### 2. **Session table — access control (no leakage)**
```
Verificar:
- session_id → {peers, established_at, last_activity_at} PRIVADA en hub
- Solo metadatos públicos: session_id (opaco), capabilities
- GC a 1800s SIN exposición de razón (no leak "inactivity reason")
- Test: client intenta listar sesiones → denied
```
**Criterio:** API endpoint review + rejection test
**Riesgo:** Attacker enumerates active sesiones → target weak clients

---

#### 3. **Dispatcher — routing validations**
```
Verificar en cross-clan-dispatcher.py:
- INVITE DEBE contener recipient + sender verificados
- Hub DEBE lookup en session table BEFORE ACK
- Routing DEBE ser: INVITE → session_id lookup → peer list → DELIVERED frame
- No shortcuts (no direct routing sin session)
```
**Criterio:** Code review + test round-trip (inspect logs)
**Riesgo:** Spoofed recipient → msg routed a atacante

---

#### 4. **Replay protection (HKDF key rotation)**
```
Verificar:
- Cada sesión (INVITE → 200 OK → ACK) genera nuevas HKDF keys
- Key derivation: HKDF-SHA256(shared_secret, info="AMARU-ARC8446-ECDHE-v1", salt=session_id)
- Viejo key DEBE ser rechazado (cryptographic verification fail)
- Timestamp checks: frame.timestamp DEBE ser monótonamente creciente por sesión
```
**Criterio:** Crypto test (derive keys, replay old key, verificar falla)
**Riesgo:** Replay old SENT → state corruption en recipient

---

### ASI03: Identity & Privilege Abuse

#### 5. **Session validation (ACK-INVITE matching)**
```
Verificar:
- Hub mantiene sesión state: SENT_INVITE → RCVD_200_OK → VERIFIED_ACK → ACTIVE
- ACK DEBE incluir session_id + sender (de INVITE)
- Hub DEBE rechazar ACK si no hay INVITE matching previa
- Rechazo DEBE ser silencioso (no leak sesión no-existe)
```
**Criterio:** State machine inspection + test false ACK
**Riesgo:** Session hijack (fake ACK → active sesión sin INVITE)

---

#### 6. **Capability negotiation — backward compat**
```
Verificar:
- auth_ok frame PUEDE tener caps: null (legacy) o {channels: [...]} (§18)
- Hub tratando legacy client: caps=null → no channel discrimination
- Hub tratando post-amendment client: caps validado contra canales permitidos
- Post-amendment hub + legacy client = client ignora `caps` field (backward compat)
```
**Criterio:** Interop test (legacy client + modern hub)
**Riesgo:** Client claims capabilities que hub no soporta → undefined behavior

---

#### 7. **Ed25519 signature on hub-emitted receipts**
```
Verificar en hub.py:_emit_sent_receipt():
- SENT frame DEBE estar firmado con hub's Ed25519 private key
- Signature: Ed25519Sign(frame_json, hub_key)
- Client DEBE verificar contra hub's published public key
- Forwarded frames (READ/PROCESSED de peer) DEBEN ser opacos (hub NO re-firma)
```
**Criterio:** Signature verification test + forwarded frame inspection
**Riesgo:** Attacker forges SENT frame (fake sig) → client thinks msg fue entregado

---

#### 8. **Channel whitelist (no discovery)**
```
Verificar:
- auth_ok.caps.channels = ["data", ...] (allowlist, no discovery)
- Client envía unknown channel → hub retorna err frame (unknown-channel code)
- Hub DEBE rechazar opaquely (no leak "channel exists but denied")
```
**Criterio:** Fuzzing test (try invalid channels)
**Riesgo:** Attacker discovers internal channels → attempts privilege escalation

---

## ⚠️ Gaps en mitigación (Feedback Dani)

### Gap 1: Replay protection incompleta (ASI02-04)
**Problema:** HKDF keys nuevas por sesión NO es suficiente. Replay dentro de misma sesión + clock-skew = estado inconsistente.

**Requerimiento:** Anti-replay sliding-window (RFC 6479) con:
- Per-sesión monotonic counter (incrementa cada frame)
- AAD (Additional Authenticated Data) = `(sender_id, counter, timestamp)`
- Window size: últimos 1024 frames
- Clock-skew tolerance: ±30s

**Timeline Phase 1:** Implementación en `amaru/crypto.py` (¿DT-020?) → fase 2 o 3
**Estado:** Roadmap, CRÍTICA pero no blocker para bilateral Phase 1 — es una mejora, no una vulnerabilidad descubierta en pruebas

---

### Gap 2: Forward secrecy (ASI03-03)
**Problema:** Key rotation per-sesión = protege a nivel de sesión. Pero si session key se compromete, attacker lee TODO el historial de esa sesión.

**Requerimiento:** Double Ratchet (Signal Protocol-style) para long-term forward secrecy:
- Root key + chain keys (DH ratchet + symmetric ratchet)
- Cada mensaje usa key derivado del chain key
- Viejo keys auto-delete tras uso

**Timeline Phase 1:** Roadmap FUTURO (después de Phase 5 trilateral)
**Estado:** Longterm vision, no fase 1

---

### Gap 3: KCI (Key Compromise Impersonation)
**Problema:** Si DH private key (ej. DANI's) se compromete:
- Attacker puede derivar las mismas claves que DANI y el hub
- Attacker puede impersonar DANI a JEI sin ser detectado

**Mitigación Phase 1:**
- Identity binding en X25519 derivation: `(srcID, dstID, pubkey_fingerprint)` en HKDF info string
- Esto hace que viejo keys derivados con diferente identidad sean criptográficamente inválidos
- Test: TBD (new test 17)

---

## 🧪 Plan de ejecución (Fase 1 — ACTUALIZADO)

### Actividad 1: Inspección estática de código (ASI02 + ASI03 + nuevas amenazas)
**Timeline:** 2-3 horas | **Lead:** Bruja | **Scope:** reference/python/amaru/

```bash
# Checklist ASI02/ASI03 (original):
- [ ] Rate limiter exists (sig + data budgets separados)
- [ ] Session table access control (private, no enumeration)
- [ ] Dispatcher routing (INVITE → session lookup → ACK check)
- [ ] HKDF key derivation (new keys per session)
- [ ] Ed25519 hub signature (on SENT frames only)
- [ ] Error handling (channel unknown → err frame)

# Checklist nuevas amenazas:
- [ ] Identity binding en X25519 derivation (srcID, dstID, pubkey_fingerprint en info string) — KCI-001 mitigation
- [ ] Downgrade protection (ECDHE fallback removido o rejected) — ASI04-02 mitigation
- [ ] Store-and-forward queue limit (256 msgs per (src,dst)) — ASI04-03 mitigation
- [ ] Hub metadata: frame size, timing, session_id logging access control — ASI07-02 mitigation
```

### Actividad 2: Auditoría de criptografía
**Timeline:** 2 horas | **Lead:** Bruja | **Scope:** cifrado end-to-end

```bash
# Verificar:
- [ ] AES-256-GCM IV único por frame
- [ ] HKDF params (algo, salt, info string)
- [ ] Key rotation on session boundary
- [ ] Signature verification (Ed25519 public key trusted path)
```

### Actividad 3: Pruebas dinámicas (paralelo a ejecución test plan)
**Timeline:** 4-5 horas | **Link:** TEST_PLAN_QUEST-CROSS-002_v1.0.md tests ASI02/ASI03

```bash
# Tests críticos:
- [ ] Test 1: Round-trip (sender chain verification)
- [ ] Test 2: Concurrent (rate limiting separado)
- [ ] Test 4: Receipt chain (sig validation)
- [ ] Test 5: Channel discrimination (err frame)
- [ ] Test 13: Key derivation (replay test)
```

### Actividad 4: Post-mortem (si bugs encontrados)
**Timeline:** Flexible | **Criterio:** Fix + re-audit antes de merge

---

## 📊 Hallazgos esperados

| Hallazgo | Probabilidad | Mitigación |
|---|---|---|
| Rate limiter no separado (sig/data) | MEDIA | Implement RFC 3261 budget logic |
| Session table exposed vía API | BAJA | Access control layer |
| Replay protection débil | BAJA | Crypto rotation validations |
| Backward compat quebrada | BAJA | Interop test framework |

---

## ✅ Criterios de aprobación

- [ ] 0 hallazgos CRÍTICA (vulnerabilidades explotables)
- [ ] ≤3 hallazgos ALTA (resolubles con cambios menores)
- [ ] Documentación de mitigaciones en ADR (si aplica)
- [ ] Tests ASI02/ASI03 100% GREEN

---

## 📝 Resultado final

**Veredicto:** 🟡 PENDIENTE (esperando confirmación Dani + ejecución tests)

Una vez Bachue confirme tests listos y Bruja completar auditoría:
- **✅ APROBADO** → QUEST-CROSS-002 Fase 1 puede proceder
- **⚠️ APROBADO CON MITIGACIONES** → bugs low/medium resolubles
- **❌ BLOQUEADO** → vulnerabilidad crítica descubierta

---

**Bruja — CISO-IA | 29-abr-2026 COT**  
**Próxima acción:** Esperar green light Dani para iniciar ejecución
