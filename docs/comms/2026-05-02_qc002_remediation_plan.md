# QC002 Phase 1 — Plan de Remediación P0/P1/P2

> **Status:** PROPUESTA — pendiente Consejo Núcleo + GO Daniel
> **Trigger:** Bruja audit (JEI, 2-may 16:53) — 3 hallazgos P0 que bloquean green-light bilateral
> **Repo HEAD:** `8421cc5` (main, post-PR#14)
> **Demand ID:** `2026-05-02-qc002-p0-remediation` (a registrar en `~/.claude/queue/demands/`)

---

## 1. Contexto

JEI completó auditoría estática 10-checks sobre `hub.py` + `crypto.py` y entregó fixtures Bachue para los 26 tests del TEST_PLAN_v1.0. Veredicto: **BLOQUEADO** por 3 hallazgos críticos. Las fixtures usan `"AMARU-ARC8446-ECDHE-v1"` (string canónica), confirmando que el código actual diverge.

Resumen de hallazgos (ver `/tmp/qc002-jei-reports/REPORTE_AUDITORIA_QUEST-CROSS-002_Bruja_2may2026.md`):

| Sev | # | Check | Estado actual | Archivo |
|-----|---|-------|---------------|---------|
| P0 | 8 | KCI identity binding | NO EXISTE | `crypto.py` |
| P0 | 1 | Rate limiting | NO EXISTE | `hub.py` |
| P0 | 9 | Downgrade protection | NO EXISTE | `hub.py` |
| P1 | 4 | HKDF info HERMES→AMARU + salt | PARCIAL | `crypto.py` |
| P1 | 10 | Queue backpressure 503 | PARCIAL | `hub.py` |
| P2 | 6 | Channel whitelist §18.5 | PARCIAL | `hub.py` |

Checks OK: #2 session table, #3 dispatcher routing, #5 Ed25519 + forwarded opacos.

---

## 2. Clasificación change-management

| Eje | Valor |
|-----|-------|
| Urgencia | P0 (block bilateral) |
| Riesgo | **high** (tocar crypto + hub auth + rate limiting) |
| Path | **Consejo Núcleo obligatorio** (ver matriz `change-management.md`) |
| Convocatoria | Palas + Ares + Artemisa antes de abrir branch |
| Veto crypto | Sensei-ml + JWA opcional para validar diseño KCI |

---

## 3. P0 fixes — diseño técnico

### P0-A | KCI identity binding (#8) — `crypto.py`

**Causa raíz**: HKDF deriva `session_key = HKDF(DH_secret, info="HERMES-ARC8446-v1", salt=None)`. Si DH private key se compromete, attacker deriva la misma key sin probar identidad — impersonación trivial.

**Fix**: vincular `(srcID, dstID, sign_pubkey_fingerprint)` al `info` string del HKDF.

```python
# crypto.py:153 (derive_shared_secret) — nueva firma
def derive_shared_secret(
    my_dh_private: X25519PrivateKey,
    peer_dh_public: X25519PublicKey,
    src_id: str,
    dst_id: str,
    peer_sign_fingerprint: str,
    session_id: str | None = None,
) -> bytes:
    raw_shared = my_dh_private.exchange(peer_dh_public)
    info = (
        f"AMARU-ARC8446-v2|src={src_id}|dst={dst_id}|fp={peer_sign_fingerprint}"
    ).encode()
    salt = session_id.encode() if session_id else None
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=info,
    )
    return hkdf.derive(raw_shared)
```

**Coordina con P1-A (#4)** — mismo edit. Bumpea info string a `v2` para denotar break (canonical-only post-sunset, sin fallback v1).

**Callers a actualizar**:
- `seal_bus_message()` (crypto.py:259) — añadir `src_id`, `dst_id`, `peer_sign_fp` desde `envelope_meta` + `peer_keys`
- `open_bus_message()` (crypto.py:439, 413-419) — idem
- `seal_bus_message_ecdhe()` (crypto.py:300) — idem para ECDHE path
- `seal_bus_message_compact()` (crypto.py:465) y `open_bus_message_compact()` (crypto.py:535) — propagar params
- `bus.py` y consumidores upstream — verificar fingerprint disponible

**Spec**: ARC-8446 §4 (Key Derivation) — actualizar a v2 + sección "Identity Binding".

**Tests**: 4-6 nuevos en `test_crypto.py`:
- `test_kci_resilience_compromised_dh` — DH key leak no permite forge sin sign key
- `test_hkdf_info_includes_identity` — info string contiene src/dst/fp
- `test_hkdf_salt_includes_session_id`
- `test_kci_cross_clan_isolation` — JEI no puede impersonar DANI

**Riesgo bilateral**: JEI debe upgrade simultáneo. El `v2` rompe `v1` por diseño (canonical-only, ningún fallback). Coordinar bump versión protocolo simultáneo.

---

### P0-B | Rate limiting (#1) — `hub.py`

**Causa raíz**: sin restricción de mensajes/firmas/datos por client_id. Solo `max_connections=100` global. Flood trivial.

**Diseño**: token-bucket per `client_id`, dos buckets separados (signatures vs data bytes).

```python
# hub.py — nuevo módulo o inline
@dataclass
class RateBuckets:
    sig_tokens: float = 60.0   # max sig/min
    data_tokens: float = 1_048_576.0  # 1MB/min
    last_refill: float = field(default_factory=time.monotonic)

    def consume(self, sig: int = 0, data: int = 0,
                sig_max: float = 60.0, data_max: float = 1_048_576.0,
                refill_per_sec: float = 1.0) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.sig_tokens = min(sig_max, self.sig_tokens + elapsed * (sig_max / 60))
        self.data_tokens = min(data_max, self.data_tokens + elapsed * (data_max / 60))
        self.last_refill = now
        if self.sig_tokens < sig or self.data_tokens < data:
            return False
        self.sig_tokens -= sig
        self.data_tokens -= data
        return True
```

**Inyección**:
- `HubConfig` (hub.py:33-50): añadir `sig_budget_per_min: int = 60`, `data_budget_bytes_per_min: int = 1_048_576`
- `ConnectionEntry` (hub.py:117-128): añadir `rate: RateBuckets = field(default_factory=RateBuckets)`
- En `_handle_connection()` post-AUTH_OK (hub.py:865): inicializar `conn_entry.rate = RateBuckets(...)`
- En message loop (hub.py:891) antes de `await self.router.route(payload, clan_id)`: validar `conn_entry.rate.consume(sig=1, data=len(raw))`. Si `False` → emitir `err` frame code `429`, no rutear.

**Spec**: ARC-4601 §15 (Hub Operations) — nueva subsección "Rate Limiting" + ARC-4601 §X nuevo si extenso.

**Tests**: 5 en `test_hub.py`:
- `test_rate_limit_sig_budget_exhausted`
- `test_rate_limit_data_budget_exhausted`
- `test_rate_limit_refill_over_time`
- `test_rate_limit_per_client_isolation` — flood JEI no afecta DANI
- `test_rate_limit_err_frame_429`

---

### P0-C | Downgrade protection (#9) — `hub.py`

**Causa raíz**: HELLO acepta cualquier `protocol_version`. Peers v0.4.x pueden negociar protocolo viejo sin rechazo.

**Fix**: validar `protocol_version >= "0.5"` en HELLO. Rechazar con err frame code `1002` + close.

```python
# hub.py:981 — post extracción client_version
client_version = hello.get("protocol_version", "0.0")
MIN_PROTOCOL = "0.5"
if _semver_lt(client_version, MIN_PROTOCOL):
    await ws.send(json.dumps({
        "type": "err",
        "code": 1002,
        "reason": f"protocol version {client_version} below minimum {MIN_PROTOCOL}",
    }))
    await ws.close()
    return
```

Helper `_semver_lt()` simple (split + tuple compare). Si en el futuro hay pre-releases (a1, b2), usar `packaging.version`.

**Spec**: ARC-4601 §15.1 (HELLO Frame) — añadir requisito protocol_version mínimo.

**Tests**: 3 en `test_hub.py`:
- `test_downgrade_protection_old_version_rejected`
- `test_downgrade_protection_current_version_accepted`
- `test_downgrade_protection_err_1002_emitted`

---

## 4. P1 fixes (incluidos en mismo branch — atomic con P0)

### P1-A | HKDF rebrand + salt (#4)

Ya cubierto en P0-A (mismo edit). Bumpea info string a `AMARU-ARC8446-v2` (no `v1` con `HERMES`). Salt = `session_id` cuando disponible.

**Tests adicionales**:
- `test_canonical_v2_info_string` — verifica `b"AMARU-ARC8446-v2|..."`
- `test_v1_hermes_info_rejected` — regression que confirma v1 no funciona

### P1-B | Queue backpressure 503 (#10)

**Causa raíz**: `MessageRouter._unicast()` retorna `{"status": "queue_full"}` (hub.py:604) pero el sender no recibe nada.

**Fix**: en message loop (hub.py:891), capturar status y emitir err al sender.

```python
# hub.py:891 — wrap route call
result = await self.router.route(payload, clan_id)
if result.get("status") == "queue_full":
    await ws.send(json.dumps({
        "type": "err",
        "code": 503,
        "reason": "destination queue full",
        "dst": result.get("dst"),
        "ref": payload.get("id"),
    }))
```

**Tests**: 2 en `test_hub.py`:
- `test_queue_full_emits_err_503_to_sender`
- `test_queue_full_includes_dst_and_ref`

---

## 5. P2 fix — diferido a sub-branch (no blockea bilateral)

### P2-A | Channel whitelist §18.5 (#6)

Capability negotiation de §18.5. Necesario para conformance §18 completa pero no blockea bilateral (lista vacía = todo permitido en transición).

**Sub-branch sugerido**: `feat/arc-4601-s18.5-channel-whitelist` post-merge P0/P1.

---

## 6. Branch & PR strategy

**Single branch atómico** para P0+P1 (no separar — JEI necesita coordinación bilateral simultánea):

```
feat/qc002-p0-bruja-fixes
```

**Commits** (atomic, secuenciales):
1. `feat(crypto): KCI identity binding + AMARU-v2 info + session salt (#8 #4)`
2. `feat(hub): RateLimiter token-bucket per client_id (#1)`
3. `feat(hub): downgrade protection minimum protocol_version 0.5 (#9)`
4. `feat(hub): err 503 backpressure on queue overflow (#10)`
5. `spec: ARC-8446 v2 + ARC-4601 §15 rate-limit + downgrade`
6. `test: 17 nuevos tests qc002 P0/P1`
7. `docs(comms): bilateral coordination plan v2 bump`

**PR title**: `feat: QC002 Phase 1 P0/P1 remediation — Bruja audit fixes (KCI + rate-limit + downgrade)`

**Co-firma**: enviar PR link a JEI por email respondiendo al thread `19deaae935f45dcc` antes de merge. JEI valida con sus fixtures Bachue local.

---

## 7. Test plan

| Categoría | Nuevos | Existentes afectados | Total esperado |
|-----------|--------|---------------------|----------------|
| `test_crypto.py` (KCI + HKDF v2) | 6 | ~10 (regenerar firmas) | regen |
| `test_hub.py` (rate + downgrade + 503) | 10 | ~5 (HELLO/AUTH) | regen |
| `test_bilateral_*.py` (post-bump) | 1 (KCI cross-clan) | varios | regen |
| **Total nuevos** | **17** | — | tests pasando 1573 → ~1590 |

Coverage threshold: mantener 70% temporal. Post-merge revisar restaurar 80%.

---

## 8. Spec changes resumen

| Spec | Sección | Cambio |
|------|---------|--------|
| `spec/ARC-8446.md` | §4 Key Derivation | bump a v2, identity binding obligatorio, salt session_id, v1 deprecated |
| `spec/ARC-8446.md` | nueva §4.3 | "KCI Resilience" — definir attack model + binding requirements |
| `spec/ARC-4601.md` | §15.1 HELLO | añadir `protocol_version >= "0.5"` requirement |
| `spec/ARC-4601.md` | nueva §15.7 | "Rate Limiting" — token-bucket sig + data per client |
| `spec/ARC-4601.md` | §15.X (queue) | err 503 backpressure cuando max_depth alcanzado |

---

## 9. Bilateral coordination plan

**Pre-merge**:
1. Daniel envía PR link a JEI por email + comentario en Issue #13
2. JEI corre fixtures Bachue contra DANI branch antes de merge
3. JEI confirma `AMARU-v2` info string converge con sus fixtures
4. Si JEI APPROVE → merge

**Post-merge**:
1. JEI upgrade `amaru` a versión nueva (v0.6.0a1 sugerido por bump v2)
2. Daniel reinicia hubs locales con nueva versión
3. Sesión bilateral en vivo: hubs JEI `ws://192.168.68.101:8443` ↔ DANI `ws://192.168.68.107:8443`
4. Asciinema record: `docs/comms/2026-05-XX_qc002_p0_bilateral.cast`
5. Tests 1-8 ALTA criticidad ejecutados en vivo
6. Tests 17-20 KCI/Downgrade/DoS ejecutados
7. Si pasa → green-light Phase 1 → close Issue #13 + bus dispatch

---

## 10. Riesgos y mitigaciones

| Riesgo | Severidad | Mitigación |
|--------|-----------|------------|
| Bump v2 rompe peers que no upgradean | high | Coordinación email pre-merge JEI; documentar break en CHANGELOG |
| RateLimiter mal calibrado bloquea tráfico legítimo | medium | Defaults generosos (60sig/min, 1MB/min); HubConfig override |
| KCI binding aumenta tamaño info string | low | ~80 bytes adicional, negligible vs 32-byte HKDF output |
| `_semver_lt()` mal implementado acepta v0.4.x | high | Tests cubren edge cases pre-release (v0.5.0a1) |
| Tests bilaterales en vivo requieren JEI online | medium | Coordinar slot 1-2h post-merge; fixtures permiten unit pre-bilateral |

---

## 11. Verificación end-to-end

```bash
# 1. Branch + commits secuenciales
cd ~/amaru-protocol
git checkout -b feat/qc002-p0-bruja-fixes

# 2. Tests locales
cd reference/python
uv run pytest tests/test_crypto.py -v
uv run pytest tests/test_hub.py -v
uv run pytest --cov=amaru --cov-fail-under=70

# 3. Lint + types
uv run ruff check amaru/
uv run mypy amaru/

# 4. Push + PR
git push origin feat/qc002-p0-bruja-fixes
gh pr create --title "feat: QC002 Phase 1 P0/P1 — Bruja audit remediation" \
  --body-file docs/comms/2026-05-02_qc002_remediation_plan.md

# 5. Email JEI thread reply con PR link

# 6. Post-merge: bilateral en vivo
amaru hub start  # DANI side
# JEI side: amaru hub start
# Asciinema: asciinema rec docs/comms/2026-05-XX_qc002_p0_bilateral.cast
```

---

## 12. Próximos pasos secuenciales

1. **Convocar Consejo Núcleo** (Palas + Ares + Artemisa) — change-management high-risk obligatorio
2. Si GO → registrar demanda en `~/.claude/queue/demands/2026-05-02-qc002-p0-remediation.md`
3. Crear branch `feat/qc002-p0-bruja-fixes`
4. Implementar P0-A → P0-B → P0-C → P1-A (incluido en A) → P1-B (commits secuenciales)
5. Tests + lint + types
6. PR + email JEI
7. Post-APPROVE: merge + bilateral en vivo

---

**Plan author**: Protocol Architect (Daniel Reyes)
**Bruja audit**: Jeimmy Gómez Gil
**Bachue fixtures**: idem
**Date**: 2026-05-02 (sábado)
**Repo HEAD baseline**: `8421cc5`
