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

### P2: Ping Storm Protection

**Problem**: JEI's broadcast test created 241K messages (9.8MB), corrupted inbox, invalidated cursor, caused 1M+ hub routes.

**Solution**:
1. **Rate limiting in hub**: max N messages per client per minute (already in ARC-4601 §15 as SHOULD)
2. **Inbox rotation**: `hub-inbox.jsonl` → rotate when > 1MB, keep last N lines
3. **Cursor resilience**: DONE (4e7cfc5) — auto-reset when file truncated

**Skill**: /protocol-architect
**Effort**: 1 session

### P3: Autonomous Response Loop

**Problem**: Daemon dispatches quests but response doesn't reliably travel back to originating peer via hub. Code written (5a9df9d) but untested end-to-end.

**Solution**:
1. Verify `_forward_to_hub()` works with `tool_hub_send()` from daemon context
2. Test: JEI sends quest → daemon dispatches → response auto-forwards → JEI receives
3. May need to run `tool_hub_send` in a subprocess if MCP server import has side effects

**Skill**: /protocol-architect
**Effort**: 1 session (with JEI online)

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

## Verification Checklist (for next session)

- [ ] `hermes status` shows peer as `● online` on both sides
- [ ] Send message from DANI → JEI receives within 30s
- [ ] Send message from JEI → DANI receives within 30s
- [ ] Quest dispatch → daemon auto-processes → response auto-forwards
- [ ] Inbox cleanup doesn't break communication
- [ ] No zombie processes after test runs
