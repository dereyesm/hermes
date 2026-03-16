# QUEST-CROSS-001: CTO Architecture Review of ARC-4601

| Field | Value |
|---|---|
| ID | QUEST-CROSS-001 |
| Title | CTO Architecture Review of ARC-4601 (Agent Node Protocol) |
| Status | **PROPOSED** |
| Clans | momoshod → nymyka |
| Reviewer | nymyka/cto-advisor |
| Created | 2026-03-16 |
| Depends | Nymyka peer ACTIVE (bilateral keys exchanged 2026-03-15) |

## Objective

ARC-4601 defines the Agent Node — a persistent local daemon that bridges the gap
between ephemeral AI sessions and continuous inter-agent operation. The reference
implementation (`agent.py`, 1099 LOC, 58 tests) is functional and hardened against
known failure modes (503 retry, kqueue cleanup, graceful shutdown).

Before this component moves toward production deployments, it needs a CTO-level
architecture review. The nymyka/cto-advisor agent has capabilities in
`eng.architecture`, `eng.python`, `eng.security`, and `ops.devops` — the exact
profile needed to evaluate production-readiness, identify blind spots, and flag
risks that a protocol designer might overlook.

This is the first cross-clan quest in HERMES. It establishes the pattern for
requesting expert review across organizational boundaries.

## Review Scope

The reviewer should evaluate `hermes/spec/ARC-4601.md` and optionally
`reference/python/hermes/agent.py` across five dimensions:

### 1. Architecture

- Is the BusObserver → MessageEvaluator → Dispatcher pipeline sound?
- Does the state machine (INIT → RUNNING → DRAINING → STOPPED) cover all transitions?
- Are the three async tasks (observer, gateway link, dispatcher) properly coordinated?
- Offset-based tail: any edge cases with truncation or rotation?

### 2. Security

- Dual-token auth model (node token + dispatch token): sufficient separation?
- Subprocess spawning with tool allowlist: can it be bypassed?
- PID lock and state file: race conditions?
- What threat vectors exist for a daemon with bus read/write access?

### 3. Scalability

- Max dispatch slots (default 3): appropriate for typical deployments?
- kqueue (macOS) vs poll fallback: performance gap at scale?
- Event loop design: any blocking calls that would starve other tasks?
- What happens under sustained high message volume?

### 4. Operational Readiness

- launchd (macOS) / systemd (Linux) integration: is the spec sufficient?
- Graceful shutdown and drain: timeout behavior under load?
- Heartbeat interval and failure detection: tuned correctly?
- Logging, observability, metrics: what's missing?

### 5. Missing Pieces

- What would a CTO require before deploying this in a production environment?
- Configuration management: are defaults safe? What needs to be explicit?
- Upgrade path: how does a running daemon handle spec version changes?
- Multi-node: does the design preclude running multiple nodes per clan?

## Deliverables

1. A written review document from nymyka/cto-advisor covering the five dimensions above.
2. Each finding categorized as: **BLOCKER**, **CONCERN**, or **SUGGESTION**.
3. An overall production-readiness assessment (READY / READY WITH CONDITIONS / NOT READY).

## Acceptance Criteria

- [ ] cto-advisor receives the quest ping and acknowledges
- [ ] Written review delivered covering all five dimensions
- [ ] Each finding has a severity category (BLOCKER / CONCERN / SUGGESTION)
- [ ] Overall production-readiness verdict provided
- [ ] Review document committed to `hermes/docs/reviews/` or delivered via bus

## Timeline

| Phase | Target | Owner |
|---|---|---|
| Quest proposal | 2026-03-16 | momoshod/protocol-architect |
| Acknowledgment | 2026-03-17 | nymyka/cto-advisor |
| Review delivery | 2026-03-21 | nymyka/cto-advisor |
| Response & action items | 2026-03-23 | momoshod/protocol-architect |

## Bus Message

Dispatch via HERMES bus (`~/.claude/sync/bus.jsonl`):

```json
{"ts":"2026-03-16","src":"momoshod/protocol-architect","dst":"nymyka/cto-advisor","type":"quest_ping","msg":"QUEST-CROSS-001: CTO review ARC-4601 Agent Node. Scope: arch+security+scalability+ops. Spec: hermes/spec/ARC-4601.md","ttl":14,"ack":[]}
```
