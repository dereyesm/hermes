# Bilateral Communication — Issues & Solutions Plan

> Post-mortem from Quest-006 bilateral session (Apr 5, 2026).
> 10 commits, 6 bugs found, first autonomous dispatch achieved.

## Issues Found (prioritized)

### P0: Signaling vs Data Plane Separation

**Problem**: Hub mixes control (presence, routing, auth) and data (quest dispatch, responses) on a single WebSocket. Failures in one affect the other.

**Solution**: SIP-inspired architecture:
- **Control plane**: lightweight, always-on connection for presence, capabilities, session setup
- **Data plane**: on-demand encrypted tunnels for quest dispatch and responses
- **Reference**: SIP (RFC 3261), 3GPP signaling/bearer separation, SRTP

**Spec**: New ARC needed. Plan mode first.
**Skill**: /protocol-architect, /hermes-research
**Effort**: 2-3 sessions

### P1: Direct Peering vs S2S Federation

**Problem**: S2S federation (hub-to-hub) was built for WAN but used on LAN. Caused: remote_peers clearing, hub_id confusion (jei vs jei-hub), routing table loss on reconnect.

**Solution**: Two modes, clear separation:
- **LAN (direct peering)**: listeners connect to peer hubs directly as regular peers. Simple, works now.
- **WAN (S2S federation)**: hub-to-hub with proper signaling plane. Only for cross-network routing.

**Implementation**:
1. `hermes hub listen --peer ws://192.168.68.101:8443` — connect to a peer hub directly
2. Multi-hub listener support in `cmd_hub_listen` (connect to N hubs from config)
3. Federation config: `mode: "direct"` (LAN) vs `mode: "s2s"` (WAN)

**Skill**: /protocol-architect
**Effort**: 1 session

### P2: Ping Storm Protection (ELEVATED — caused P3 failure)

**Problem**: JEI's broadcast test created 241K messages (9.8MB), corrupted inbox, invalidated cursor, caused 1M+ hub routes. **Additionally**: the ping storm batch (~24,900 identical lines) directly caused QUEST-006-FINAL to fail bridging to bus — the daemon processed the batch but the final dispatch message was lost due to missing per-message exception handling in `_hub_inbox_loop`.

**Solution**:
1. **Rate limiting in hub**: max N messages per client per minute (already in ARC-4601 §15 as SHOULD)
2. **Inbox rotation**: `hub-inbox.jsonl` → rotate when > 1MB, keep last N lines
3. **Cursor resilience**: DONE (4e7cfc5) — auto-reset when file truncated
4. **Per-message exception handling**: DONE (Apr 4, 2026) — `write_message` wrapped in try/except inside for-loop

**Skill**: /protocol-architect
**Effort**: 1 session

### P3: Autonomous Response Loop — RESOLVED (Apr 4, 2026)

**Problem**: Daemon dispatches quests but response doesn't reliably travel back to originating peer via hub. Code written (5a9df9d) but untested end-to-end.

**Root cause found**: QUEST-006-FINAL arrived in hub-inbox (line 24978) but wasn't bridged to bus. The daemon cursor advanced to EOF, but `write_message` had no per-message exception handling — a failure in the ping storm batch (P2) silently prevented subsequent messages from being written.

**Fix applied**:
1. Per-message try/except around `write_message` in `_hub_inbox_loop` (agent.py L1779)
2. `exc_info=True` on outer exception handler (agent.py L1800)
3. Daemon cursor reset to byte 3,050,514 (just before QUEST-006-FINAL)
4. Daemon restarted → QUEST-006-FINAL bridged to bus at seq 7
5. Dispatch executed: `cross-clan-dispatch` OK + `heraldo-dispatch-inbound` OK
6. Response auto-forwarded to JEI via hub (DANI-HERMES-059 confirmed)

**Verification**: QUEST-006-FINAL in bus (seq 7), responses at seq 5+6 with `dst: jei`. Hub send confirmed `via: hub@localhost:8443`.

**Status**: DONE

### P4: Peer Status pending_ack → active

**Problem**: Both clans show each other as `pending_ack`. No mechanism to upgrade to `active` after bilateral verification.

**Solution**: Auto-upgrade peer status when:
1. Received a valid signed message from peer (TOFU verified), OR
2. Both peers exchanged at least 1 message via hub (bilateral confirmed)

Add to `_auto_peer_from_presence()` or new method `_upgrade_peer_status()`.

**Skill**: /protocol-architect
**Effort**: <1 session

### P5: Zombie Process Cleanup

**Problem**: pytest leaves daemon processes running (60+ zombies). Hub SIGTERM ignored (needs SIGKILL).

**Evidence** (Apr 4, 2026): 6 zombie pytest daemon processes confirmed (PIDs 1956-1963, all from `/tmp/pytest-*/test_install_*` and `/tmp/pytest-*/test_uninstall_*` dirs). Manually killed this session.

**Solution**:
1. Test fixtures: add `atexit` or `finally` cleanup for daemon processes
2. Hub: handle SIGTERM properly (graceful shutdown)
3. `hermes daemon stop` should fallback to SIGKILL after timeout

**Skill**: /protocol-architect
**Effort**: <1 session

## Architecture Target

```
         Control Plane (SIP-like)              Data Plane (encrypted)
         ┌─────────────────────┐              ┌──────────────────────┐
DANI     │ presence, caps,     │              │ quest dispatch,      │
clan  ←──│ session setup,      │──── LAN ────→│ responses, bus sync  │──→ JEI
         │ keepalive, routing  │              │ (AES-256-GCM, E2E)  │    clan
         └─────────────────────┘              └──────────────────────┘
              always-on                           on-demand
              lightweight                         encrypted tunnel
```

## Verification Checklist

- [x] `hermes status` shows peer as `● online` on both sides (Apr 5)
- [x] Send message from DANI → JEI receives within 30s (Apr 5, DANI-HERMES-059)
- [x] Send message from JEI → DANI receives within 30s (Apr 5, QUEST-006-FINAL)
- [x] Quest dispatch → daemon auto-processes → response auto-forwards (Apr 4, P3 RESOLVED)
- [ ] Inbox cleanup doesn't break communication
- [ ] No zombie processes after test runs (P5 pending)
- [ ] Ping storm protection in place (P2 pending)
