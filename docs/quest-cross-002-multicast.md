# QUEST-CROSS-002: Multi-Clan Quest Dispatch

> First 3-clan quest: Nymyka dispatches, DANI + JEI process, responses consolidated.

## Participants

| Clan | Role | Status |
|------|------|--------|
| **nymyka** | Quest originator (dispatcher) | active, bilateral keys |
| **momoshod** (DANI) | Worker — processes quest autonomously | active, AgentNode running |
| **jei** (JEI) | Worker — processes quest autonomously | active, AgentNode running |

## Prerequisites

### All clans
- [ ] Pull latest: `cd ~/Dev/hermes-dani && git pull` (HEAD 62c192c)
- [ ] Install: `pip install -e reference/python/`
- [ ] Hub running: `amaru hub start`
- [ ] Agent Node running: `amaru daemon start --dir ~/.hermes`
- [ ] `amaru status` shows all peers as `active`

### Nymyka (dispatcher)
- [ ] Hub access configured (either MCP hermes-bus or `amaru send` CLI)
- [ ] Both peers (momoshod + jei) registered in hub-peers.json
- [ ] Federation config with both peer hub URIs

### DANI (worker)
- [ ] cross-clan-dispatcher agent registered in `~/.amaru/agents/`
- [ ] Hub listener connected to JEI's hub (for bidirectional)
- [ ] Listener connected to own hub (for Nymyka's messages)

### JEI (worker)
- [ ] cross-clan-dispatcher agent registered in `~/.amaru/agents/`
- [ ] Hub listener connected to DANI's hub
- [ ] `amaru send` CLI working (PR#4 merged)

## Protocol

### Phase 0: Connectivity Check (5 min)

Each clan verifies bilateral connectivity:

```bash
# From each clan:
hermes status
# Should show: peers as active, hub running, agent node running

# Test send:
hermes send <peer> "QUEST-CROSS-002-PING: connectivity check" --type event
```

**Exit criteria**: All 3 clans can send/receive from each other.

### Phase 1: Nymyka Dispatches Quest (5 min)

Nymyka sends the quest to both workers. Since broadcast doesn't queue for offline peers,
use unicast to each:

```bash
# Nymyka sends to DANI
hermes send momoshod "QUEST-CROSS-002: [TASK DESCRIPTION HERE]. Report findings. --nymyka" --type dispatch

# Nymyka sends to JEI
hermes send jei "QUEST-CROSS-002: [TASK DESCRIPTION HERE]. Report findings. --nymyka" --type dispatch
```

**Wire format** (what the hub sees):
```json
{"type": "msg", "payload": {"src": "nymyka", "dst": "momoshod", "type": "dispatch", "msg": "QUEST-CROSS-002: ..."}}
```

### Phase 2: Autonomous Processing (5-10 min)

Each worker's AgentNode detects the dispatch:

```
hub-inbox.jsonl ← hub listener receives message
      ↓
_hub_inbox_loop() bridges to bus.jsonl
      ↓
MessageEvaluator.evaluate() → Action.DISPATCH
      ↓
Dispatcher executes cross-clan-dispatcher agent
      ↓
Response written to bus + auto-forwarded via hub
```

**What to watch** (on each worker):
```bash
# Check if dispatch arrived in bus
hermes bus --pending | grep QUEST-CROSS-002

# Check agent node logs for dispatch activity
tail -20 ~/.amaru/agent-node.log 2>/dev/null
```

### Phase 3: Response Collection (5 min)

Nymyka checks for responses:

```bash
# Check inbox for responses
hermes inbox --last 10

# Or listen for new messages
hermes hub listen --timeout 60
```

**Expected responses**:
```
[RE:cross-clan-dispatch] OK  (from momoshod)
[RE:cross-clan-dispatch] OK  (from jei)
```

### Phase 4: Verification (5 min)

```bash
# All clans verify:
hermes status              # peers active, msgs routed
hermes bus --pending       # quest + responses visible

# DANI verifies bilateral with both:
hermes send jei "QUEST-CROSS-002-VERIFY: round trip check" --type event
hermes send nymyka "QUEST-CROSS-002-VERIFY: round trip check" --type event
```

## Quest Task Suggestions

Pick one for the first run:

| # | Task | Complexity | What it tests |
|---|------|-----------|---------------|
| A | "Report your hermes status: version, peers, tests, bus depth" | Low | Basic dispatch + response |
| B | "Run pytest and report: total tests, failures, coverage %" | Medium | Agent executes real work |
| C | "Review docs/architecture/signaling-plane-outline.md and propose 1 improvement" | High | Agent reads file + analyzes |

**Recommendation**: Start with Task A for the first run. Simple, verifiable, low risk.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Dispatch not in bus | Bridge not running or cursor stale | Restart daemon, reset cursor |
| Response not forwarded | _forward_to_hub failed silently | Check hub PID in hub-state.json |
| Peer shows pending_ack | Auto-upgrade not triggered yet | Send any message to trigger upgrade |
| Broadcast not received | Peer was offline | Use unicast (hermes send <peer>) instead |
| hermes send fails | No hub running | `amaru hub start` first |

## Success Criteria

- [ ] Nymyka sends quest to both DANI and JEI (unicast)
- [ ] Both AgentNodes process the dispatch autonomously
- [ ] Both auto-forward responses via hub
- [ ] Nymyka receives 2 responses (one from each worker)
- [ ] No manual intervention required after dispatch
- [ ] Total round-trip time < 2 minutes

## Timeline

| Phase | Duration | When |
|-------|----------|------|
| Prerequisites | 15 min per clan | Before quest |
| Phase 0-4 | 30 min | All 3 clans online simultaneously |
| **Target date** | TBD | Next session with JEI online (Apr 12-19 window) |

## Notes

- This quest tests the EXACT pipeline validated by Tier 1-4 bilateral tests (22 tests, all GREEN)
- Broadcast is best-effort (Tier 4 finding) — use unicast for guaranteed delivery
- `amaru send` CLI (PR#4 by JEI) eliminates the 40-line script friction
- If any step fails, document in bilateral-issues-plan.md as P6+

---

*Quest designed by Clan MomoshoD (Protocol Architect) — Apr 5, 2026*
