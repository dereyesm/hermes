# ARC-COORD-01 — Coordinated Dispatch Type

**Status**: DRAFT
**Tier**: Extension
**Origin**: Council Ampliado QUEST-ULTRAPLAN-001 GO PILOT, 2026-04-28
**Responsible** (Hannah condition): Dojo (SDN Controller, see [ARC-2314](ARC-2314.md)) + Palas
**Approved deadline**: 2026-05-09 (rescheduled from original 2026-05-05)

---

## Abstract

ARC-COORD-01 introduces a new bus message type, `coord-dispatch`, that allows a skill or human operator to trigger a coordinated dispatch to **3-5 skills** on the same topic with explicit routing rules. Today, [ARC-5322](ARC-5322.md) `dispatch` is 1→1; ARC-COORD-01 is 1→N with N constrained by Cemri 2026 cognitive limits (>8 skills = degradation).

This converts the Sensei Federation (and other groupings) from **nominal listings** to **real coordination with handoff logic**.

## Non-goals

- Not a swarm: window slot fixed at 3-5
- Not unbounded fanout: routing is explicit
- Does not replace 1→1 `dispatch`, which remains valid for simple delegation
- Does not execute actions without gating: receivers decide whether to respond, the operator decides whether to convert responses to action
- Does not cross dimensional firewalls: respects existing visibility rules (see [ARC-1918](ARC-1918.md))

## Terminology

This document uses the requirement keywords defined in [ARC-2119](ARC-2119.md).

| Term | Definition |
|------|-----------|
| **Coord-dispatch** | A coordinated 1→N dispatch message |
| **Required skills** | Skills that MUST respond before deadline (3-5) |
| **Optional skills** | Skills that MAY respond if available |
| **Routing mode** | One of `all`, `first`, or `best` (see §Routing Modes) |
| **Reconciler** | Process (Dojo) that closes a coord-dispatch with a `dojo_event` |

## Message Schema

```json
{
  "ts": "YYYY-MM-DD",
  "src": "<requester_skill_or_dim>",
  "dst": "*",
  "type": "coord-dispatch",
  "msg": {
    "coord_id": "<UUID or ts+src>",
    "topic": "<short description of the question or decision>",
    "context_ref": "<absolute path or url to full context>",
    "required_skills": ["<skill_1>", "<skill_2>", "<skill_3>"],
    "optional_skills": ["<skill_n>"],
    "routing": "all | first | best",
    "deadline": "ISO8601 timestamp",
    "response_format": "structured | freeform",
    "max_response_lines": 20
  },
  "ttl": 3,
  "ack": []
}
```

### Payload `msg` Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `coord_id` | string | YES | Unique correlation identifier for responses |
| `topic` | string | YES | Question or decision motivating the coordination (MUST include `[responsible:<subject>]` tag — see §Siksika Frame) |
| `context_ref` | string | YES | Where to find full context (not inline, to avoid bus bloat) |
| `required_skills` | string[] | YES | 3-5 skills that MUST respond |
| `optional_skills` | string[] | NO | Skills suggested but not required |
| `routing` | enum | YES | Response mode (see §Routing Modes) |
| `deadline` | ISO8601 | YES | When the coordination expires |
| `response_format` | enum | YES | `structured` (JSON schema) or `freeform` |
| `max_response_lines` | int | NO | Per-response length cap (default 20) |

### Constraints

- `len(required_skills)` MUST be in `[3, 5]` (Cemri 2026 hard limit)
- `len(required_skills) + len(optional_skills)` MUST be ≤ 8
- `topic` MUST be ≤ 200 characters
- TTL MUST be 3 days (longer coordinations are projects, not coordinations)
- `deadline` MUST be ≤ TTL of the message
- `context_ref` MUST be a path or URL readable by all target skills

## Routing Modes

| Mode | Description | When to use |
|------|-------------|-------------|
| `all` | All `required_skills` MUST respond before deadline | Council decisions, architectural deliberation |
| `first` | First responder wins, others abort | Urgent triage, troubleshooting |
| `best` | Dojo selects most appropriate based on topic + skill expertise | Intelligent routing, technical dispatch |

**Default**: `all` (most conservative, avoids race conditions).

## Response Protocol

Each responding skill writes a `dispatch` message (existing type) with `dst: <requester>` referencing the `coord_id`:

```json
{
  "ts": "...",
  "src": "<responder_skill>",
  "dst": "<requester>",
  "type": "dispatch",
  "msg": {
    "coord_id": "<same UUID>",
    "skill": "<responder_skill>",
    "response": "<text or structured JSON>",
    "confidence": 0.0-1.0
  },
  "ttl": 3,
  "ack": []
}
```

### Reconciliation

When all required responses have arrived (or deadline expires), the Dojo writes a closing `dojo_event`:

```json
{
  "ts": "...",
  "src": "dojo",
  "dst": "<requester>",
  "type": "dojo_event",
  "msg": {
    "coord_id": "<UUID>",
    "status": "complete | partial | timeout",
    "received": ["skill_1", "skill_2"],
    "missing": ["skill_3"],
    "synthesis_ref": "<path to synthesis doc or null>"
  },
  "ttl": 7,
  "ack": []
}
```

## Operational Rules

### Authorization to Trigger

- Any skill with `dispatch_capability: true` in `~/.claude/skills/registry.json`
- The human operator via slash command (e.g., `/consejo` SHOULD migrate to `coord-dispatch` internally)
- The Dojo automatically when meta-coordination criteria are detected

### Response Obligation

- Skills listed in `required_skills` receive the message in their SYN
- If a listed skill is NOT active (Rookie in governance), the Dojo writes an error `dojo_event` and the operator decides
- Skills in `optional_skills` respond if they have capacity, with no penalty

### Validation

Before accepting the message on the bus, the validator MUST verify:

1. `len(required_skills)` is in `[3, 4, 5]`
2. `len(required) + len(optional)` ≤ 8
3. All listed skills exist in the skill registry
4. No duplicates between `required` and `optional`
5. `deadline` is within TTL
6. `context_ref` is an accessible path or URL

If any rule fails, the message MUST be rejected with an `alert` to `src`.

## Comparison with `dispatch` 1→1

| Aspect | `dispatch` (existing) | `coord-dispatch` (this spec) |
|--------|----------------------|------------------------------|
| Cardinality | 1→1 | 1→{3..5} |
| Routing | Implicit (dst is known) | Explicit rule in payload |
| Reconciliation | Manual | Dojo writes closing `dojo_event` |
| Use case | Simple delegation | Deliberation, triage, multi-perspective |

`dispatch` remains valid — `coord-dispatch` does not replace it; it extends it.

## Siksika Frame Operationalized

Hannah condition: every `coord-dispatch` MUST name the **responsible subject** for the topic. If no clear subject exists, the coordination MUST NOT be triggered. This prevents "ownerless decisions" (systemic banality).

Implementation: the `topic` field MUST include a `[responsible:<skill_or_human>]` tag. Validation MUST block messages without this tag.

Example valid topic:

```
"topic": "[responsible:Daniel] Decide whether to enable HMAC bus in Global pilot or wait for Q3"
```

## Reference Implementation

Two components:

### 1. Validator (PreToolUse or pre-write)

- Intercepts writes to `bus.jsonl` with `type=coord-dispatch`
- Applies the 6 validation rules
- Rejects with clear reason if any rule fails

### 2. Reconciler (cron or SessionStart)

- Reads bus, finds `coord-dispatch` messages with deadline passed or complete responses
- Writes closing `dojo_event`
- Cleans the bus of resolved coordinations via ACK

## Examples

### Valid coord-dispatch (deliberation)

```json
{
  "ts": "2026-05-07",
  "src": "amaru",
  "dst": "*",
  "type": "coord-dispatch",
  "msg": {
    "coord_id": "20260507-amaru-bus-arch",
    "topic": "[responsible:Daniel] Bus architecture: separate channel for dojo_event vs reconnect symlink",
    "context_ref": "~/.claude/projects/-Users-daniel-reyes-amaru-protocol/memory/MEMORY.md",
    "required_skills": ["Palas", "Ares", "Artemisa"],
    "optional_skills": ["protocol-architect"],
    "routing": "all",
    "deadline": "2026-05-09T18:00:00Z",
    "response_format": "freeform",
    "max_response_lines": 30
  },
  "ttl": 3,
  "ack": []
}
```

### Closing `dojo_event` after reconciliation

```json
{
  "ts": "2026-05-09",
  "src": "dojo",
  "dst": "amaru",
  "type": "dojo_event",
  "msg": {
    "coord_id": "20260507-amaru-bus-arch",
    "status": "complete",
    "received": ["Palas", "Ares", "Artemisa", "protocol-architect"],
    "missing": [],
    "synthesis_ref": "knowledge-vault/insights/2026-05-09-bus-arch-decision.md"
  },
  "ttl": 7,
  "ack": []
}
```

## Success Metrics (4-week pilot)

- ≥ 3 `coord-dispatch` messages per week on the bus (vs 0 today)
- ≥ 80% of coordinations complete before deadline
- ≥ 1 `coord-dispatch` converted to operator decision every 2 weeks
- 0 messages with `required_skills` count outside `[3, 5]`
- 0 cross-dimensional firewall violations

## Abort Criteria

- If responses become noise without differentiation (all skills say the same thing) → revisit skill selection
- If Dojo becomes a reconciliation bottleneck → distribute
- If the operator ignores syntheses → format adds no value → kill

## Security Considerations

- `coord-dispatch` MUST respect dimensional firewall rules per [ARC-1918](ARC-1918.md). A skill in dimension A MUST NOT be required to respond to coordinations originating in dimension B unless cross-dim authorization is explicit.
- `context_ref` MUST point to material accessible by all target skills. References to dimension-private paths MUST be rejected at validation.
- The validator SHOULD log rejected messages (with reason) for audit, but SHOULD NOT broadcast rejections that contain sensitive context.

## Open Questions (Q3 Council)

- MAY `coord-dispatch` use emergent routing (pub-sub) instead of explicit? (Today: NO — Ares ruling: "years of debugging.")
- How many simultaneous `coord-dispatch` messages can the bus support without saturation? (TBD by real load.)
- Does cross-dimensional `coord-dispatch` require FEC review? (Likely YES if it touches architecture.)

## References

- [ARC-1918](ARC-1918.md) — Private spaces & firewall (cross-dim rules)
- [ARC-2119](ARC-2119.md) — Requirement keywords
- [ARC-2314](ARC-2314.md) — Skill Gateway Plane Architecture (Dojo)
- [ARC-5322](ARC-5322.md) — Message format (this type extends the `type` enum)
- [ARC-9001](ARC-9001.md) — Bus integrity (TTL and ACK semantics)
- Council Ampliado deliberation: `knowledge-vault/insights/2026-04-28-consejo-ampliado-ultraplan-001-mvp-piloto.md`
- Original draft: `~/.claude/sync/ARC-COORD-01.md` (2026-04-28)

---

*Draft delivered 2026-04-28. Landed as official spec 2026-05-07.*
