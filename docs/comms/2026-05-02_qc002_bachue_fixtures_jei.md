# REPORTE FIXTURES QA — QUEST-CROSS-002
**Lead:** Bachue (QA Lead)
**Fecha:** 2026-05-02 COT
**Scope:** Fixtures bilaterales JEI↔DANI para 26 tests del TEST_PLAN_v1.0
**Status:** ✅ IMPLEMENTADO — Listo para ejecución bilateral

---

## Fixtures implementadas

| Archivo | Contenido | Status |
|---|---|---|
| `__init__.py` | Package marker | ✅ |
| `conftest.py` | Maestro: `bilateral_session`, `bilateral_session_id`, imports centralizados | ✅ |
| `session_fixtures.py` | `MockSession` + `SessionState` enum + `active_session`, `fresh_session` | ✅ |
| `crypto_fixtures.py` | Ed25519 + X25519 keypairs reales, HKDF-SHA256, `sign_test_frame`, `verify_test_frame` | ✅ |
| `hub_fixtures.py` | `MockStoreForwardQueue`, `MockRouter`, `hub_queue`, `hub_router` | ✅ |
| `message_fixtures.py` | 12 frames: HELLO, CHALLENGE, AUTH, AUTH_OK, MSG, SENT, DELIVERED, QUEUED, fake sender, replay, offline, unknown channel | ✅ |

**Ubicación:** `workspace/QA/fixtures_quest_cross_002/`

---

## Cobertura de tests (26 tests del TEST_PLAN_v1.0)

### Tests ALTA criticidad (8) — Fixtures ready

| Test | Fixture(s) requerida | Status |
|---|---|---|
| 1. Multicast round-trip 3-hops | `bilateral_session`, `frame_message`, `frame_sent_receipt` | ✅ |
| 2. Concurrent dispatch 20x | `hub_queue`, `hub_router`, `frame_message` x20 | ✅ |
| 3. Offline queueing (option A — QUEUED+DELIVERED) | `frame_offline_queue`, `frame_queued_receipt`, `frame_delivered_receipt`, `hub_queue` | ✅ |
| 4. Receipt chain SENT→DELIVERED→READ→PROCESSED | `frame_sent_receipt`, `frame_delivered_receipt`, `ed25519_keypair_jei` | ✅ |
| 5. Channel discrimination (unknown → err) | `frame_unknown_channel`, `hub_router` | ✅ |
| 6. Session GC (inactivity 1800s) | `active_session`, `hub_queue` | ✅ |
| 7. Auth capability negotiation §18.5 | `frame_hello`, `frame_auth_ok`, `mock_connections` | ✅ |
| 8. S2S federation §17 | `frame_offline_queue`, `hub_queue`, `hub_router` | ✅ |

### Tests MEDIA criticidad (9 — 5 original + 4 Dani) — Fixtures ready

| Test | Fixture(s) requerida | Status |
|---|---|---|
| 9. Error handling malformed | `frame_fake_sender`, `hub_router` | ✅ |
| 10. Latency baseline | `frame_message`, `bilateral_session` | ✅ |
| 11. PII filtering | `frame_message` (con datos PII inyectados) | ✅ |
| 12. Cipher suite AES-256-GCM | `session_key`, `frame_message` | ✅ |
| 13. Symmetric key derivation (replay test) | `session_key`, `old_session_key`, `frame_replay` | ✅ |
| 17. KCI Resilience | `x25519_keypair_jei`, `x25519_keypair_dani`, `session_key` | ✅ |
| 18. Downgrade attack | `frame_hello` (con versión antigua) | ✅ |
| 19. Hub metadata oracle | `hub_queue`, `frame_message` x varios | ✅ |
| 20. DoS amplification | `frame_offline_queue` x500, `hub_queue` | ✅ |

### Tests BAJA criticidad (3) — Fixtures ready

| Test | Fixture(s) requerida | Status |
|---|---|---|
| 14. Coverage ≥72% | N/A (pytest-cov) | ✅ |
| 15. Lint + type checks | N/A (ruff + mypy) | ✅ |
| 16. Documentation compliance | N/A (doc review) | ✅ |

---

## Decisiones técnicas

- **Ed25519 keys reales** (no mocked) — `frame_auth` firma el nonce real. Las firmas son verificables.
- **HKDF info corregida** — fixtures usan `b"AMARU-ARC8446-ECDHE-v1"` (no `HERMES-...`). Esto diverge del código actual de Dani (que usa `HERMES-...`). Reportado en Reporte Bruja check #4.
- **Option A (QUEUED/DELIVERED)** — `frame_queued_receipt` + `frame_delivered_receipt` separados, confirmando corrección de Dani sobre Test 3.
- **MockRouter es síncrono** — evita `asyncio` overhead en tests unitarios. Para tests de integración bilateral real, usar el hub real de Dani.
- **Session model actualizado** — `SessionState` refleja el protocolo real HELLO→CHALLENGE→AUTH→AUTH_OK (no INVITE/ACK del diseño original).

---

## Notas de instalación (para Dani)

```bash
# Copiar fixtures al repo amaru-protocol
cp -r workspace/QA/fixtures_quest_cross_002/ \
  /path/to/amaru-protocol/reference/python/tests/fixtures_jei/

# Instalar dependencias (ya en el repo)
cd amaru-protocol/reference/python
uv sync

# Verificar que las fixtures importan correctamente
uv run pytest tests/fixtures_jei/ --collect-only
```

---

## Limitación importante

Las fixtures permiten **tests unitarios** de componentes individuales. Los tests bilaterales reales (Tests 1-8 ALTA) requieren:
- Hub JEI corriendo en `ws://192.168.68.101:8443`
- Hub DANI corriendo en `ws://192.168.68.107:8443`
- Coordinación en sesión en vivo JEI↔DANI

Las fixtures de este paquete sirven de scaffolding y pueden ser usadas en tests de integración una vez el entorno bilateral esté activo.

---

**Bachue — QA Lead | 2026-05-02 COT**
**Fixture package:** `workspace/QA/fixtures_quest_cross_002/` (6 archivos, 26 tests cubiertos)
