# TEST PLAN: QUEST-CROSS-002 Multicast Bilateral JEI↔DANI
**Versión:** 1.0 (Fase 1 — Bilateral)  
**Fecha:** 2026-04-29 COT  
**Lead QA:** Bachue (QA Lead)  
**Triada:** Chiminigagua + Bruja + Bachue  
**Estado:** 🟡 PENDIENTE CONFIRMACIÓN DANI

---

## 🎯 Objetivo

Validar que QUEST-006 (bilateral dispatch JEI↔DANI) **escala correctamente** a multicast autónomo con:
- Cobertura completa de escenarios alta/media/baja criticidad
- Expansión anticipada para 3 clanes (Nymyka futuro)
- Cifrado + identidad validados en cada dirección
- Manejo de fallos y recuperación

---

## 📊 Cobertura de test plan

### Baseline QUEST-006 (22 tests bilaterales ya GREEN)
- ✅ Tier 1: Conexión y autenticación (4 tests)
- ✅ Tier 2: Dispatch básico JEI→DANI, DANI→JEI (6 tests)
- ✅ Tier 3: Receipts + cifrado (8 tests)
- ✅ Tier 4: Recuperación y edge cases (4 tests)

### Nuevos tests Fase 1 (8 tests ALTA criticidad)

#### 1. **Multicast round-trip — 3 hops** (ALTA)
- **Escenario:** JEI dispatcher envía mensaje → DANI recibe + procesa + responde → JEI recibe respuesta
- **Validar:** Latencia <2s, cifrado preservado en cada hop, session_id consistente
- **Criterio:** Response llega a JEI con ASI02 compliance (sin inyección de prompts)
- **Setup:** 2 clanes, dispatcher activo, agentes escuchando

#### 2. **Concurrent dispatch (20 msgs simultáneos)** (ALTA)
- **Escenario:** JEI envía 20 mensajes casi simultáneamente a DANI; DANI procesa todos
- **Validar:** Rate limiting no bloquea legítimas, orden preservado (FIFO), receipt cabal por cada msg
- **Criterio:** 20/20 mensajes procesados, 0 pérdidas, latencia <3s acumulada
- **Setup:** Medir throughput, validar budget rate-limit separado sig vs data

#### 3. **Offline message queueing (DELIVERED semantics — opción a)** (ALTA)
- **Escenario:** DANI desconecta, JEI envía msg → hub emite `QUEUED` → msg queda en store-and-forward → DANI reconecta → hub emite `DELIVERED`
- **Validar:** Mensaje entregado on reconnect, receipt secuencia `QUEUED` (enqueue) → `DELIVERED` (reconnect), opción a (SS7 SMSC) correcta
- **Criterio:** Msg procesado post-reconnect, 2 receipts emitidos (QUEUED + DELIVERED), timestamps monótonos, auditoría completa
- **Notas:** Corregido por Dani (29-abr). SS7/SMSC analogy: RP-ACK=QUEUED, SMS-STATUS-REPORT=DELIVERED. Option a es autoridad en ARC-4601 §18.4 (HEAD f5cd21c)

#### 4. **Receipt chain (SENT → DELIVERED → READ → PROCESSED)** (ALTA)
- **Escenario:** JEI env message, DANI env SENT, luego DELIVERED, luego READ (app-level), luego PROCESSED
- **Validar:** Secuencia correcta, timestamps monótonos, firma Ed25519 en SENT+DELIVERED, forwarded opaque
- **Criterio:** Chain completa observado, sin re-firma en forwarded (ASI06 compliance)

#### 5. **Channel discrimination (hub rejects unknown channels)** (ALTA)
- **Escenario:** Client envía frame con `channel: "unknown"` → hub responde `err` (unknown-channel)
- **Validar:** Error code correcto (1000-4 registry), backward compat (legacy client ignores)
- **Criterio:** Hub emite `err` frame con type + code + ref + detail; legacy client unaffected
- **Setup:** Validate ARC-4601 §18.10 `err` frame type (4-code registry)

#### 6. **Session table maintenance (inactivity GC @ 1800s)** (MEDIA)
- **Escenario:** JEI↔DANI establece sesión, inactivity 30+ minutos → hub GC recolecta sesión
- **Validar:** Session table entries cleaned per RFC 4028 §4 SIP Session-Expires
- **Criterio:** Sesión removida post-timeout, nueva INVITE re-establece sin error histórico
- **Setup:** Larga ejecución (30+ min), monitorear session table; verificar mem footprint

#### 7. **Auth capability negotiation (§18.5 extension)** (MEDIA)
- **Escenario:** Client negocia `caps`/`channels` via `auth_ok` frame; hub respeta selectores
- **Validar:** Capability field parsed, hub mantiene per-client capability map, respeta selectores
- **Criterio:** Hub puede discriminar clientes que soportan §18 vs legacy
- **Setup:** Validate ARC-4601 §18.5 (extend auth_ok, no new HELLO frame)

#### 8. **S2S federation (§17 implied — store-and-forward entre hubs)** (MEDIA)
- **Escenario:** Hub A (JEI) forwards message a Hub B (DANI) cuando B offline
- **Validar:** Implementación `FederationLink`/`FederationTable` (reference/python/amaru/hub.py)
- **Criterio:** Mensaje queued en store-and-forward, reenviado post-reconnect, ref impl sin errores
- **Notas:** §17 spec body TBD en próximo amendment; ref impl ya existe (611b88a)

---

### Escenarios MEDIA criticidad (9 tests — 5 anteriores + 4 NUEVOS por Dani feedback)

#### 9. **Error handling — malformed message** (MEDIA)
- Mensaje sin signature → hub rechaza con `err` (unknown-session o similar)

#### 10. **Latency baseline** (MEDIA)
- P50 <200ms, P95 <500ms entre JEI dispatch y DANI receipt (en LAN)

#### 11. **PII filtering (ASI01 input sanitization)** (MEDIA)
- Mensaje contiene datos sensibles (email, phone) → validar que no se loggean sin encriptación

#### 12. **Cifrado cipher suite (AES-256-GCM validation)** (MEDIA)
- Interceptar traffic JEI↔DANI en wire; validar ciphertext (no plaintext)

#### 13. **Symmetric key derivation (HKDF+Ed25519)** (MEDIA)
- Validar que claves derivadas son diferentes entre sesiones; replay test (old key rejected)

#### 17. **KCI Resilience (Key Compromise Impersonation)** (MEDIA — NUEVO)
- **Escenario:** Simular compromiso de DANI's DH private key → validate identity binding mitigation
- **Validar:** X25519 derivation incluye `(srcID, dstID, pubkey_fingerprint)` en HKDF info string
- **Criterio:** Keys derivados con diferente identidad son criptográficamente inválidos
- **Setup:** Crypto test (derive con identity A, intenta usar con identity B → falla)

#### 18. **Downgrade attack residual** (MEDIA — NUEVO)
- **Escenario:** Client intenta forzar ECDHE fallback (deprecated) → hub responde `err` (1002)
- **Validar:** Hub RECHAZA downgrade sin procesamiento
- **Criterio:** Error frame code=1002, no state corruption
- **Setup:** Intentar ECDHE negotiation en post-PR#11 hub

#### 19. **Hub metadata oracle** (MEDIA — NUEVO)
- **Escenario:** Análisis de frame size + timing + session_id en hub logs → validar padding + access control
- **Validar:** Frames son 256-byte aligned, logs retention ≤24h, access control privado
- **Criterio:** Metadata oracle mitigated (no correlation channel posible)
- **Setup:** Wireshark/tcpdump analysis + hub config audit

#### 20. **Store-and-forward DoS amplification** (MEDIA — NUEVO)
- **Escenario:** Attacker spams 500 msgs a offline DANI → validate queue cap (256 max)
- **Validar:** Hub rechaza msgs posteriores con `err` backpressure (503)
- **Criterio:** Queue no overflow, hub recovers post-cleanup, no resource exhaustion
- **Setup:** Stress test con client-side msg flood

---

### Escenarios BAJA criticidad (3 tests)

#### 14. **Coverage report (code + docstring coverage ≥72%)** (BAJA)
- Validar pytest coverage; mantener threshold

#### 15. **Lint + type checks (ruff + mypy pass)** (BAJA)
- CI pipeline 5/5 GREEN

#### 16. **Documentation compliance (ARC-4601 specs versioned)** (BAJA)
- Validar que cambios en protocol están documentados; no código sin spec

---

## 📋 Matriz de cobertura (Bilateral → Trilateral) — ACTUALIZADO 30-abr

| Test | JEI | DANI | Nymyka | Criticidad | Estimado (h) | Status |
|------|-----|------|--------|-----------|-----------|---------|
| 1. Round-trip 3-hops | ✅ | ✅ | — | ALTA | 1.5 | ✅ Diseñado |
| 2. Concurrent 20x | ✅ | ✅ | — | ALTA | 2.0 | ✅ Diseñado |
| 3. Offline queueing (option A) | ✅ | ✅ | — | ALTA | 2.5 | ✅ Redesigned 30-abr |
| 4. Receipt chain | ✅ | ✅ | — | ALTA | 1.5 | ✅ Diseñado |
| 5. Channel discrimination | ✅ | ✅ | — | ALTA | 1.0 | ✅ Diseñado |
| 6. Session GC (1800s) | ✅ | ✅ | — | MEDIA | 2.0 | ✅ Diseñado |
| 7. Auth caps negotiation | ✅ | ✅ | — | MEDIA | 1.5 | ✅ Diseñado |
| 8. S2S federation | ✅ | ✅ | — | MEDIA | 2.0 | ✅ Diseñado |
| 9-13. MEDIA (original) | — | — | — | MEDIA | 6.0 | ✅ Diseñado |
| 17. KCI Resilience | ✅ | ✅ | — | MEDIA | 1.5 | 🆕 NUEVO Dani #13 |
| 18. Downgrade attack | ✅ | ✅ | — | MEDIA | 1.0 | 🆕 NUEVO Dani #13 |
| 19. Hub metadata oracle | ✅ | ✅ | — | MEDIA | 1.5 | 🆕 NUEVO Dani #13 |
| 20. DoS amplification | ✅ | ✅ | — | MEDIA | 1.5 | 🆕 NUEVO Dani #13 |
| 14-16. BAJA | — | — | — | BAJA | 3.0 | ✅ Diseñado |
| **TOTAL Bilateral (26 tests)** | — | — | — | — | **28.5 h** | ⏳ PENDING DANI |

**Cambios vs 29-abr:**
- Test 3 redesigned (QUEUED + DELIVERED separate) — Dani feedback on SS7/SMSC analogy
- +4 tests (17-20) por amenazas faltantes (KCI, downgrade, metadata oracle, DoS)
- Estimado actualizado: 22h → 28.5h (adicionales 6.5h para nuevas mitigaciones)

**Expansión a Trilateral (Nymyka futuro):** +18 tests (interacciones JEI↔Nymyka + DANI↔Nymyka + 3-way), estimado +35-40 h.

---

## 🚀 Execution plan (Fase 1 — esta semana)

### Día 1 (29-abr)
- [ ] Bachue redacta matriz de tests detallados (matriz arriba)
- [ ] Chiminigagua + Bruja validan scope vs specs

### Día 2-3 (30-abr, 1-may)
- [ ] Bachue prepara fixtures (conftest.py trilateral, mock clanes)
- [ ] Paralelamente: Bruja ejecuta auditoría ASI02/ASI03

### Día 4 (2-may)
- [ ] Esperar confirmación Dani (disponibilidad + feedback DELIVERED semantics)
- [ ] Si Dani OK: comenzar tests 1-4 (ALTA criticidad, round-trip + concurrent + offline + receipts)

### Día 5 (3-may)
- [ ] Tests 5-8 (discriminación + sesiones + capabilities + federation)
- [ ] Bruja presenta auditoría finalizada

### Día 6-7 (4-5-may)
- [ ] Tests MEDIA+BAJA + cobertura coverage
- [ ] Reconvocatoria triada (si todos tests GREEN)

---

## ✅ Criterios de aceptación

- [ ] 8 tests ALTA = 100% GREEN (bilaterales JEI↔DANI)
- [ ] 5 tests MEDIA = ≥95% GREEN (tolerance en latency baseline)
- [ ] Cobertura ≥72% (pytest coverage threshold)
- [ ] Ruff + mypy 5/5 GREEN
- [ ] Dani feedback en DELIVERED semantics resuelto en código
- [ ] Auditoría Bruja (ASI02/ASI03) aprobada

---

## 📎 Referencias

- **QUEST-006 tests:** 22 tests bilaterales (Tier 1-4, ref impl conftest.py)
- **PR#9 (ATR-Q.931):** Merged 14-abr, §18 (channel-aware hub routing)
- **RFC 4028:** SIP Session-Expires (inactivity GC)
- **ARC-4601 §18.4:** DELIVERED semantics open question (opción b recomendada)
- **AES-256-GCM + Ed25519 + HKDF:** Cryptography baseline

---

**Bachue — QA Lead | 29-abr-2026 COT**  
**Próxima acción:** Validar con triada + esperar confirmación Dani
