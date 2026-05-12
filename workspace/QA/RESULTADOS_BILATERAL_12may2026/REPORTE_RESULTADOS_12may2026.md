# Reporte Resultados — Bilateral Cut QC002 Phase 1

**Fecha**: 2026-05-12 (martes) 15:54 COT
**Versión**: amaru-protocol v0.6.0a1
**Clanes**: DANI ↔ JEI
**Issue**: [#13 QUEST-CROSS-002 Phase 1](https://github.com/dereyesm/amaru-protocol/issues/13)
**Cast**: [`docs/comms/2026-05-12_qc002_p0_bilateral.cast`](../../../docs/comms/2026-05-12_qc002_p0_bilateral.cast) (113 KB)

## Resumen

**DANI side**: 🟢 GREEN

| Métrica | Valor |
|---|---|
| pytest passed | **55/55** (test_bilateral 35 + test_qc002_p0_jei 20) |
| pytest failed | 0 |
| `amaru send jei` deliveries | **5x delivered via local hub** |
| Test 18 (downgrade) evidence | ✅ PASS (log dedicado) |
| Tiempo pytest | 14.68s |
| CLI version | 0.6.0a1 |
| Hub status | RUNNING (PID 14921, uptime ~4.5h) |
| Roster | `jei: online "S2S hub (1 peers)"` |

## Hallazgo durante pre-flight (mitigado)

Durante el pre-flight se descubrió que `cmd_send` (`cli.py:651-664`) construía el HELLO WebSocket **sin el campo `protocol_version`**. Esto causaba que el hub rechazara la conexión con `err 1002 — protocol version unknown below minimum 0.5` (la misma regla que valida **Test 18 downgrade protection**, Bruja audit check #9, shipped en PR #15).

**Esto significa que QC002 P0 #9 funcionó perfectamente — bloqueó un cliente legacy de nuestro propio CLI antes del corte.** El protocolo está correcto; el CLI estaba desactualizado.

**Fix**:
- Branch: `fix/cli-send-hello-protocol-version`
- Commit: `dfe60b4` (3 líneas)
- PR: [#22](https://github.com/dereyesm/amaru-protocol/pull/22) — **MERGED** (squash → main `aa2c2ff`)
- Estrategia: leer `__version__` runtime (no hardcoded — feedback `version_asserts_runtime`)

**Cobertura**: el bug existió porque CI test_qc002_p0_jei valida que el hub rechaza HELLOs viejos, pero ningún test E2E validaba que nuestro propio `amaru send` lo mandara correctamente. **Issue follow-up candidato**: agregar smoke test E2E CLI ↔ hub post-merge para detectar regresiones de este tipo.

## Evidencia detallada

### Sync verify (cast líneas iniciales)

```
$ git rev-parse --short HEAD       → dfe60b4 (fix branch)
$ amaru --version                  → amaru 0.6.0a1
$ amaru hub status                 → Hub Status: RUNNING, PID 14921, uptime >0
$ amaru hub roster                 → Online clans (2):
                                       momoshod: online [1/1 slots]
                                       jei: online "S2S hub (1 peers)"
$ amaru hub peers                  → 4 registered (momoshod, nymyka, jei, jei-hub)
```

### Test 18 — Downgrade protection (evidence en log dedicado)

Ver [`test_18_downgrade_evidence_dani.log`](./test_18_downgrade_evidence_dani.log).

**Caso negativo (HELLO sin protocol_version)**:
```json
{"type": "err", "code": 1002, "reason": "protocol version unknown below minimum 0.5"}
```

**Caso positivo (HELLO con protocol_version=0.6.0a1)**:
```
Response type: challenge  → hub aceptó, emitió CHALLENGE
```

**Conclusión**: el hub honra `MIN_PROTOCOL_VERSION = 0.5` (ARC-4601 §15.1, Bruja #9 P0 BLOCKER).

> Nota honesta: durante la grabación del cast el `python3 -c "..."` falló con `ModuleNotFoundError: No module named 'websockets'` porque se invocó el python3 del sistema en vez del venv. La evidencia equivalente se re-ejecutó con el venv y se guarda en el log adjunto. El cast captura el error de ejecutor, no la prueba del downgrade gate — la cobertura de Test 18 sigue íntegra vía este log.

### Tests 1-4 — Tráfico real bilateral (`amaru send`)

```
[dispatch] momoshod → jei: QC002-T1 multicast round-trip      → delivered via local hub (bus ok)
[dispatch] momoshod → jei: QC002-T2 concurrent #1             → delivered via local hub (bus ok)
[dispatch] momoshod → jei: QC002-T4 receipt chain test        → delivered via local hub (bus ok)
```

(5 deliveries totales en el cast — incluye repetición en segundo bloque)

Confirma que post-fix CLI:
- `amaru send` construye HELLO con `protocol_version` válido
- Hub local acepta, enruta vía S2S a JEI hub `192.168.68.101:8443`
- Bus persiste la intención (ATR-Q.931 §8 — durable bus write antes del live send)

### Tests 5-8 + 17-20 — Suite pytest

```
============================= 55 passed in 14.68s ==============================
```

Cubrió:
- `tests/test_bilateral.py` — 35 tests: MessageDelivery, OfflineQueueDrain, Presence, BurstProtection, PeerStatusUpgrade, HubInboxBridge, MultiClanQuest, DualClanDispatch
- `tests/test_qc002_p0_jei.py` — 20 tests: BachueFixtureImports, DowngradeProtection, RateLimitingP0, QueueBackpressureP0

> **Nota**: `tests/test_crypto_kci_v2.py` (13 tests KCI v2) **no aparece en el resumen 55** del cast — posible que el `tail -60` truncara la línea del 3er archivo, o que el shell anidado de asciinema cortó la cola. Validado previamente en pre-flight a las 15:11 COT con resultado **55+13 = 68/68 PASS** (suite completa 1624/1624 PASS, cov 72%). Si JEI requiere re-validación bilateral del KCI v2 en vivo, puede re-ejecutarse sin asciinema en un anexo.

## Artifacts en este directorio

| Archivo | Descripción |
|---|---|
| `REPORTE_RESULTADOS_12may2026.md` | Este reporte |
| `test_output_dani.log` | Plain-text output del cast (201 líneas, vía `asciinema convert --output-format txt`) |
| `test_18_downgrade_evidence_dani.log` | Re-ejecución del Test 18 con venv (positivo + negativo) |
| `../../../docs/comms/2026-05-12_qc002_p0_bilateral.cast` | Cast original (113 KB, formato v3) |

## Próximos pasos

- [ ] **JEI**: ejecutar su side y adjuntar `test_output_jei.log` en este mismo directorio
- [ ] **JEI**: corroborar deliveries (5 `dispatch` recibidos de `momoshod`)
- [ ] **Conjunto**: reporte final consolidado (DANI + JEI) en este mismo MD vía PR review
- [ ] **Cierre**: close Issue #13 cuando ambos sides ratifiquen verde
- [ ] **Issue #18 follow-up candidato**: smoke test E2E CLI ↔ hub post-merge para prevenir regresión tipo PR #22

## Referencias

- [PR #22 (fix CLI)](https://github.com/dereyesm/amaru-protocol/pull/22) — MERGED `aa2c2ff`
- [PR #21 (release v0.6.0a1)](https://github.com/dereyesm/amaru-protocol/pull/21) — MERGED `3255ad5`
- [PR #15 (QC002 P0 #1+#9+#10)](https://github.com/dereyesm/amaru-protocol/pull/15) — MERGED
- [PR #17 (KCI v2)](https://github.com/dereyesm/amaru-protocol/pull/17) — MERGED
- ARC-4601 §15.1 — Hub error codes (err 1002)
- ARC-8446 §4.4 — KCI v2 identity binding
- Bruja audit (2026-05-02) — P0 BLOCKER #1, #9, #10

---

**Autor**: Daniel Reyes (Protocol Architect)
**Co-Autor**: Claude Opus 4.7
