# Bilateral Hub Test Log — 2026-04-02

> First live WebSocket bilateral attempt between Clan DANI and Clan JEI.

## Participants

| Clan | IP | Port | Hub Version | Status |
|------|-----|------|-------------|--------|
| DANI (momoshod) | 192.168.68.100 | 8443 | 0.4.2a1 | Running (PID 45900) |
| JEI | 192.168.68.101 | 8443 | Unknown | Reachable (TCP OK) |

## Timeline

| Time (UTC) | Event | Detail |
|------------|-------|--------|
| ~21:00 | DANI hub start | `hermes hub start --dir ~/.hermes`, PID 45900, :8443 |
| ~21:10 | TCP connectivity confirmed | `nc -z 192.168.68.101 8443` succeeded |
| ~21:15 | WebSocket connect to JEI | `ws://192.168.68.101:8443` — TCP+WS handshake OK |
| ~21:15 | **JEI no challenge** | Connected but JEI hub does not send challenge frame |
| ~21:20 | DANI sends hello to JEI | `{"type":"hello","clan_id":"momoshod",...}` — no response (timeout) |
| ~21:25 | DANI hub HTTP 500 discovered | `_process_http` bug: websockets v16 changed `process_request` signature |
| ~21:30 | Fix deployed (45a226d) | `_process_http` simplified, legacy endpoints bypassed |
| ~21:35 | DANI hub challenge confirmed | Local test: HELLO → CHALLENGE → AUTH → AUTH_OK (4-frame handshake) |
| ~21:40 | HELLO frame implemented (0dea423) | Client-initiates protocol, backward compat for legacy |
| ~21:45 | DANI-HERMES-026 sent to relay | Debug info for JEI |
| ~22:00 | JEI tokens exhausted | Bilateral paused, waiting for JEI to resume |
| ~22:10 | DANI-HERMES-027 sent to relay | Full instructions for JEI to connect as client |
| ~22:30 | Conformance tests added (80a33ae) | L3-40/41/42: HELLO, capabilities, legacy compat |

## Findings

### Bug: websockets v16 API change (Fixed)
- **Symptom**: HTTP 500 on every WebSocket connection
- **Root cause**: `process_request` callback changed from `(path, headers)` to `(connection, request)` in websockets 13+
- **Fix**: Simplified `_process_http` to skip legacy endpoints (commit 45a226d)

### Interop gap: Missing HELLO frame (Fixed)
- **Symptom**: Both hubs are servers, neither initiates handshake
- **Root cause**: Original auth flow was server-initiates (sends challenge without client identification)
- **Fix**: Added HELLO frame as first client message (commit 0dea423)
- **Wire sequence now**: `HELLO → CHALLENGE → AUTH → AUTH_OK`
- **Backward compat**: `_authenticate_legacy()` handles pre-§15.6 clients

### Discovery: JEI hub protocol divergence (Open)
- **Symptom**: JEI's hub accepts WebSocket connections but doesn't follow ARC-4601 §15.6
- **Hypothesis**: JEI may have a different hub implementation, or the hub is listening but not fully implemented
- **Resolution**: Pending JEI reconnection. Instructions sent via relay (DANI-HERMES-027).

## Metrics

| Metric | Value |
|--------|-------|
| Time to discover websockets v16 bug | ~15 min |
| Time to fix + deploy | ~10 min |
| Time to design + implement HELLO frame | ~20 min |
| Time to add conformance tests | ~15 min |
| Total commits this bilateral session | 5 |
| Tests before | 1475 |
| Tests after | 1478 |
| Conformance vectors before | 126 |
| Conformance vectors after | 129 |

## Lessons Learned

1. **Version-pin WebSocket library in tests.** The `websockets>=13.0` dep allows breaking API changes. Add integration tests that actually start/connect a hub.
2. **Capability negotiation solves "who speaks first."** The HELLO frame eliminates the ambiguity that caused the JEI stall.
3. **First bilateral finds bugs no unit test catches.** The HTTP 500 existed since hub.py was written but was invisible because tests mock the WebSocket layer.
4. **Relay as async fallback works.** When real-time fails, the relay (git push/pull) keeps the bilateral alive with ~minute latency.

## Files Changed

| File | Commit | Change |
|------|--------|--------|
| `hermes/hub.py` | 45a226d | Fix `_process_http` for websockets v16 |
| `hermes/hub.py` | 0dea423 | HELLO frame + `_authenticate` rewrite + `_authenticate_legacy` |
| `scripts/quest005_hub_client.py` | 0dea423 | Client sends HELLO first |
| `hermes/cli.py` | e8bbf36 | `hermes peer invite/accept` commands |
| `README.md` | 3e94c8d | Reframe: sovereignty > wire efficiency |
| `tests/test_conformance.py` | 80a33ae | L3-40/41/42 hub handshake vectors |

---

*Log produced by Protocol Architect. All commits pushed to main (80a33ae). Hub running on :8443 awaiting JEI reconnection.*
