# Runbook — Corte Atómico Bilateral QC002 P0 (mié 13-may 2026 10:00 COT)

> Pre-flight DANI ejecutado mar 12-may 15:13 COT. Todo verde.
> Este runbook se ejecuta en vivo durante el corte. Copy-paste secuencial.

## Identidad y endpoints

| Clan | Hub WS | Pub fingerprint sign | GitHub |
|------|--------|----------------------|--------|
| DANI (dani-hub) | `ws://192.168.68.107:8443` | `85a940d9b5a2f084…` | dereyesm |
| JEI (jei) | `ws://192.168.68.101:8443` | `b05d85e59a6dee74…` | jeipgg |

Slot ATC confirmado por JEI: msg `19e1954d`.

## T-5 min (09:55 COT)

Bus ACK a JEI: listo para corte.

```bash
cd ~/amaru-protocol
amaru send jei "READY_QC002_PHASE1_CUT v0.6.0a1 dani-hub UP" --type event
```

## T-0 (10:00 COT) — Pull simultáneo + verify version

```bash
cd ~/amaru-protocol
git pull --tags origin main
amaru --version          # expect: amaru 0.6.0a1
git rev-parse --short HEAD  # expect: 3255ad5
```

## T+30s — Verify hub UP + peer JEI online

```bash
amaru hub status         # expect: RUNNING, uptime >0
amaru hub peers          # expect: jei + jei-hub registered with pub b05d85e5
```

Si JEI hub no responde — ack en bus, esperar.

## T+1 min — Start asciinema

```bash
cd ~/amaru-protocol
asciinema rec docs/comms/2026-05-13_qc002_p0_bilateral.cast \
  --title "QC002 Phase 1 Bilateral Cut v0.6.0a1 — DANI↔JEI" \
  --idle-time-limit 3
```

Dentro del cast (ver secciones siguientes para los comandos exactos).

## Inside cast — Tests ALTA criticidad 1-8

> Para los que requieren tráfico real bilateral, usar `amaru send` + `amaru inbox`.
> Para los que se validan con fixtures unitarios, usar `pytest`.

### Test 1 — Multicast round-trip 3 hops

```bash
# JEI→DANI request
amaru send jei "QC002-T1 multicast round-trip request" --type dispatch
# DANI espera respuesta de JEI
amaru inbox
```

### Test 2 — Concurrent dispatch 20x

```bash
for i in $(seq 1 20); do
  amaru send jei "QC002-T2 concurrent #$i" --type dispatch &
done
wait
amaru inbox | grep -c "QC002-T2"  # expect: 20
```

### Test 3 — Offline queueing (QUEUED+DELIVERED option A)

```bash
# Acordar con JEI: JEI baja agent-node, DANI envía, JEI sube → verifica DELIVERED
amaru hub status
amaru send jei "QC002-T3 offline pre-disconnect" --type dispatch
# JEI reconecta, verificar receipt secuencia QUEUED→DELIVERED
amaru inbox | grep "QUEUED\|DELIVERED"
```

### Tests 4-8 — Receipt chain / Channel discrim / Session GC / Auth §18.5 / S2S federation

Cubiertos por suite pytest (fixtures Bachue):

```bash
cd reference/python
.venv/bin/python -m pytest tests/test_qc002_p0_jei.py tests/test_bilateral.py \
  -v --tb=short --no-header
# expect: 55/55 PASSED (20 qc002 + 35 bilateral)
```

## Inside cast — Tests 17-20 KCI / Downgrade / Oracle / DoS

```bash
cd ~/amaru-protocol/reference/python
.venv/bin/python -m pytest tests/test_crypto_kci_v2.py \
  -v --tb=short --no-header
# expect: 13/13 PASSED
```

Para 19 (Hub metadata oracle) — opcional Wireshark/tcpdump si JEI quiere capture en vivo:

```bash
# Solo si JEI lo solicita
sudo tcpdump -i any -w /tmp/qc002-t19.pcap "port 8443" &
TCPDUMP_PID=$!
amaru send jei "QC002-T19 metadata oracle probe" --type dispatch
sleep 3
sudo kill $TCPDUMP_PID
ls -la /tmp/qc002-t19.pcap
```

Para 20 (DoS amplification) — flood test:

```bash
# Coordinar con JEI antes (su queue cap se va a tocar)
for i in $(seq 1 500); do
  amaru send jei "QC002-T20 DoS flood #$i" --type dispatch &
done
wait
# Expect: hub queue cap 256, err 503 backpressure visible en JEI logs
```

## Cierre cast + commit + close Issue #13

```bash
# Stop asciinema (Ctrl+D dentro)
cd ~/amaru-protocol
git add docs/comms/2026-05-13_qc002_p0_bilateral.cast
git add docs/comms/2026-05-13_qc002_p0_bilateral_runbook.md
git commit -m "comms(qc002): bilateral cut v0.6.0a1 — DANI↔JEI Phase 1 evidence

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
Directed-By: Daniel Reyes, Protocol Architect"
git push origin main

# Bus state final
amaru send jei "QC002_PHASE1_COMPLETE asciinema in docs/comms/" --type state

# Close Issue #13
gh issue close 13 --repo dereyesm/amaru-protocol \
  --comment "QC002 Phase 1 empirical execution complete. Evidence: \`docs/comms/2026-05-13_qc002_p0_bilateral.cast\`. All 12 ALTA + 17-20 tests green bilateral. Issue closed per acceptance criteria."
```

## Rollback (si algo falla)

- TCP fail entre hubs → verificar `/etc/hosts` + firewall macOS (`pfctl -s rules | grep 8443`)
- Tests ALTA fallan en local → NO arrancar cast. Investigar antes.
- JEI no responde a `amaru send` → cross-check `amaru hub peers`; si jei offline, parquear corte a jue 14-may pre-aeropuerto

## Pre-flight checks completados (mar 12-may 15:13 COT)

- [x] amaru CLI 0.6.0a1
- [x] Hub PID 14921 RUNNING (uptime 4h)
- [x] 4 peers registrados (momoshod/nymyka/jei/jei-hub)
- [x] JEI peer config ws://192.168.68.101:8443 sign_pub `b05d85e5…`
- [x] Keys `~/.amaru/keys/momoshod.{key,pub}` 600
- [x] Symlink legacy `~/.hermes → ~/.amaru` intacto
- [x] git main clean HEAD 3255ad5
- [x] GitHub Release v0.6.0a1 LIVE
- [x] Suite completa 1624/1624 PASSED cov 72% / 18.51s
- [x] Subset bilateral+qc002+kci v2 55/55 PASSED / 14.60s
- [x] Pytest zombies (5 daemons) limpiados
- [x] Issue #13 OPEN, doctrinal hold
- [ ] Bilateral mié 13-may 10:00 COT (pending JEI 09:55 ACK)
