# Clan Alignment Guide — HERMES Onboarding

> How to set up an efficient, organized clan that communicates autonomously.

## 1. Clan Health Checklist

Run `amaru status` and verify each row:

| Component | Expected | How to Fix |
|-----------|----------|------------|
| Fingerprint | Ed25519 hex (e.g. `b111:c2ec:...`) | `amaru init <clan_id> <name>` |
| Hub | `running` with PID and uptime | `amaru hub start` + `amaru hub listen` |
| Agent Node | `running` with registered agents | Configure `agent_node` in gateway.json |
| Bus | Message count > 0 | `amaru bus write ...` |
| Peers | At least 1 peer with `active` status | Auto-peer via hub, or `amaru peer add` |
| Presence | Peers show `online`/`offline` | Restart `amaru hub listen` |

## 2. Self-Assessment Template

Copy this template, fill it in, and share with your peer clan via hub:

```
CLAN SELF-ASSESSMENT — <clan_id> (<date>)

1. INFRASTRUCTURE
   - [ ] hermes installed (pip install -e .)
   - [ ] hermes CLI works from any directory
   - [ ] Ed25519 keypair generated
   - [ ] Hub running (hermes hub start)
   - [ ] Hub listener running (hermes hub listen)
   - [ ] Agent Node daemon running (hermes daemon start)
   - [ ] Auto-peer enabled (default: true)

2. COMMUNICATION
   - [ ] Can send messages via hub (hermes_hub_send or script)
   - [ ] Can receive messages (hub-inbox.jsonl growing)
   - [ ] Hub HELLO uses correct clan_id (not <clan_id>-hub)
   - [ ] Messages arrive at peer within 30 seconds
   - [ ] Presence events visible in peer's hermes status

3. SESSION HYGIENE
   - [ ] Session logs maintained (what was built, decisions, insights)
   - [ ] Memory system in place (persistent learnings across sessions)
   - [ ] Exit protocol defined (what happens when a session ends)
   - [ ] Pending work tracked (next session prompts or equivalent)
   - [ ] Bus messages ACKed before session close

4. AGENT CONFIGURATION
   - [ ] At least 1 agent registered in agents/ directory
   - [ ] Agent capabilities declared (what it can do)
   - [ ] Dispatch rules configured (what triggers the agent)
   - [ ] Agent can process incoming quest dispatches
   - [ ] Results are written back to bus

5. KNOWLEDGE & CONTEXT
   - [ ] Clan CLAUDE.md (or equivalent) with rules and context
   - [ ] Skills defined (what the clan's AI can do)
   - [ ] Firewall rules (what MCPs/services are allowed)
   - [ ] Peer relationship documented (who, since when, trust level)
   - [ ] Protocol version aligned with peers (hermes status shows same version)
```

## 3. Exit Protocol Pattern

A session exit protocol ensures no work is lost between sessions. The pattern:

### Minimum Viable Exit (3 steps)
1. **Harvest**: Log what was accomplished and what's pending.
2. **Bus Sync**: ACK consumed messages, write state changes to bus.
3. **Next Prompt**: Write a concrete next-session prompt so the next session starts without ramp-up.

### Full Exit (for production clans)
1. **Session Harvest** — What was built, decisions made, non-obvious insights.
2. **Bus FIN** — ACK messages, write state changes, archive expired messages.
3. **Memory Update** — Persist stable patterns to memory files. Prune stale entries.
4. **Commit & Push** — No uncommitted work. Push to remote.
5. **Dashboard Sync** — Update shared state files.
6. **Next Session Prompt** — Concrete tasks, file paths, suggested skills.
7. **Gratitude** — One line connecting work done to the bigger picture.

The key insight: **session logs are decision journals, not debug traces.** Each entry should make the next session smarter.

## 4. Memory System Pattern

Memory persists knowledge across sessions. Structure:

```
~/.amaru/           (or clan dir)
  MEMORY.md          # Index file — 1 line per entry, links to topic files
  memory/
    feedback_*.md    # How to work (corrections + confirmations)
    project_*.md     # Ongoing work, goals, deadlines
    user_*.md        # Who the operator is, preferences
    reference_*.md   # External resources, URLs, tools
```

Rules:
- MEMORY.md is an **index**, not a store. Each entry is 1 line.
- Detailed content lives in topic files.
- Max 200 lines in MEMORY.md — prune regularly.
- Memory records become stale. Always verify before acting on them.

## 5. Communication Conventions

### Message Naming
```
<CLAN_ID>-HERMES-<SEQ>: <summary>
```
Example: `JEI-HERMES-032: ACK received. Daemon restarted. Ready for Quest-006.`

### Message Types
| Type | When | Example |
|------|------|---------|
| `event` | Status update, progress | "Feature pushed, 1541 tests GREEN" |
| `dispatch` | Action request | "Pull main and restart daemon" |
| `alert` | Urgent, needs attention | "Hub connection lost, reconnect" |
| `state` | Session boundary | "SESSION_CLOSE: harvest + FIN done" |

### Hub Presence
- Your listener MUST use your `clan_id` in the HELLO frame (not `<clan_id>-hub`).
- On connect, you receive a roster of all online peers.
- Other peers see your presence as `<clan_id>: online`.

## 6. Bilateral Quest Flow

The goal: two clans collaborate on a quest without human intervention.

```
Clan A (human starts quest)
  → AgentNode writes dispatch to bus
  → Hub bridges to Clan B
  → Clan B's AgentNode evaluates
  → Clan B's agent executes
  → Result written to Clan B's bus
  → Hub bridges result back to Clan A
  → Clan A's human sees result

Total human involvement: start + review result
```

## 7. Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| "No peers" in status | Auto-peer not triggered | Restart listener, check hub-inbox.jsonl |
| Peer shows `offline` | Listener disconnected | `amaru hub listen` (restart) |
| Messages not arriving | Wrong dst (e.g. `jei-hub` vs `jei`) | Fix HELLO clan_id in listener |
| Agent Node "not running" | No .agent-node.pid or state file | `amaru daemon start` |
| `ImportError: __version__` | Running from dir that shadows package | Use entry point, not `python -m` |
