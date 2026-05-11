# ARC-REFLECT-01 — Reflection Message Type

**Status**: DRAFT
**Tier**: Extension
**Origin**: Council Ampliado QUEST-ULTRAPLAN-001 GO PILOT, 2026-04-28
**Responsible** (Hannah condition): protocol-architect
**Approved deadline**: 2026-05-09 (rescheduled from original 2026-05-05)

---

## Abstract

ARC-REFLECT-01 introduces a new bus message type, `reflection`, that allows a designated skill to write a structured observation at session close. The reflection becomes available to subsequent sessions, which read it during SYN and surface it as pre-deliberative input. This converts the open/close cycle into a persistent learning loop without requiring the human operator to author it post-hoc.

The type complements existing message types (`state`, `event`, `alert`, `dispatch`, `dojo_event`) by providing observation-without-instruction semantics: reflections are descriptive, not directive.

## Non-goals

- Does not replace session logs (`~/.claude/session-logs/YYYY-MM.md`) — those are human journals
- Does not replace `MEMORY.md` updates — those remain consolidated decisions
- Does not execute actions — reflections are observation, not instruction
- Does not bypass human gating — Daniel decides whether a reflection becomes action

## Terminology

This document uses the requirement keywords defined in [ARC-2119](ARC-2119.md).

| Term | Definition |
|------|-----------|
| **Reflection** | A structured observation written by a designated skill at session close |
| **Designated skill** | The skill authorized to author reflections for a given dimension |
| **Session ID** | UUID or `<timestamp>+<dim>` identifier of the session being reflected upon |
| **Wellness arc** | One of `🟢 / 🟡 / 🟠 / 🔴` per `~/.claude/intake/wellness-signals.md` |

## Message Schema

```json
{
  "ts": "YYYY-MM-DD",
  "src": "<dimension>",
  "dst": "*",
  "type": "reflection",
  "msg": {
    "session_id": "<UUID or timestamp+dim>",
    "skill_author": "<skill_name>",
    "summary": "<1-3 lines, natural language>",
    "insights": ["<insight_1>", "<insight_2>"],
    "concerns": ["<concern_1>"],
    "next_session_hint": "<actionable suggestion or null>",
    "metric": {
      "skills_invoked": <int>,
      "context_switches": <int>,
      "wellness_arc": "🟢|🟡|🟠|🔴"
    }
  },
  "ttl": 7,
  "ack": []
}
```

### Payload `msg` Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | YES | Unique identifier of the session |
| `skill_author` | string | YES | Designated skill that authored the reflection |
| `summary` | string | YES | 1-3 lines: most important observation |
| `insights` | string[] | YES | Non-obvious patterns detected (MAY be empty) |
| `concerns` | string[] | NO | Risks, frictions, wellness signals |
| `next_session_hint` | string \| null | NO | Suggestion for the next session |
| `metric.skills_invoked` | int | YES | Count of skills invoked in the session |
| `metric.context_switches` | int | YES | Count of topic transitions |
| `metric.wellness_arc` | enum | YES | Emotional arc per wellness-signals.md |

### Constraints

- `summary` MUST be ≤ 280 characters (Twitter rule — forces concision)
- `insights` MUST contain ≤ 5 items
- `concerns` MUST contain ≤ 3 items
- TTL MUST be 7 days (sufficient for the next session to consume)
- `dst` MUST be `*` (broadcast — all dimensions MAY read)

## Operational Rules

### Authorship

**Pilot scope (Global dimension)**: designated skill = **Palas**.

Rationale: Palas is already Council facilitator and tableau observer. It has the broadest perspective on inter-dimensional traffic. It does not concentrate authority because the human operator retains final decision-making.

**Other dimensions (post-pilot)**: each dimension assigns its own reflector during the extension phase post-2026-05-26.

### Write Trigger

`SessionEnd` hook — integrated into exit-protocol Step 2 (Amaru FIN).

If session close is abrupt (Stop without SessionEnd), the reflection is omitted. There is no backfill — a reflection that was not written is lost, which is acceptable (do not break the loop on edge cases).

### Read Trigger

`SessionStart` hook — integrated into the SYN protocol. The next session opening any dimension surfaces pending `reflection` messages on the bus (`dst:*`, no entry in `ack` array).

### ACK Semantics

When a session presents a reflection to the human operator and the operator processes it (continues, discards, or converts to action), the dimension appends its identifier to the `ack` array. The reflection remains alive on the bus until TTL expires or all interested dimensions have ACKed.

## Comparison with Other Types

| Type | Trigger | Expected action | TTL |
|------|---------|----------------|-----|
| `state` | Session close | Notify current state | 7d |
| `event` | Dimension milestone | Mark historical event | 30d |
| `alert` | System/skill detects problem | Resolve urgently | 5d |
| `dispatch` | Skill delegates | Receiver executes | 14d |
| `dojo_event` | Dojo SDN | Local coordination | 3d |
| **`reflection`** | **Skill at close** | **Observational learning, no obligation** | **7d** |

The key difference: `reflection` does NOT require action. It is cognitive metabolism for the Clan, not instruction.

## Reference Implementation

```bash
#!/bin/bash
# reflect-on-session-end.sh — registered in SessionEnd hook

# 1. Determine active dimension via $CWD
# 2. Determine designated skill for that dimension (pilot: Global → Palas)
# 3. Collect session metrics:
#    - skills_invoked: parse transcript
#    - context_switches: count topic changes via intake protocol
#    - wellness_arc: read from session-log if already written, else derive from welt-state
# 4. Generate payload `msg` (skill produces summary/insights/concerns)
# 5. Append to ~/.claude/sync/bus.jsonl
# 6. Sync to dashboard (cp + commit + push)
```

**Non-spec note**: generation of `summary`/`insights`/`concerns` is the responsibility of the authoring skill — it is not produced by mechanical code. The skill (LLM) reads the session and produces the reflection. The hook only orchestrates the write.

## Examples

### Reflection generated after a productive session

```json
{
  "ts": "2026-05-07",
  "src": "amaru",
  "dst": "*",
  "type": "reflection",
  "msg": {
    "session_id": "20260507-amaru-1",
    "skill_author": "Palas",
    "summary": "Closed two QC002 P0 fronts with JEI: Bachue fixtures committed (#15), KCI v2 promoted ready (#17). Bilateral ACK explicit.",
    "insights": [
      "JEI sequence proposal (PR#15→main first, PR#17 rebased on top) reduces merge risk vs parallel landing",
      "Local ruff version drift caused two CI lint cycles — pin ruff to a stable version in dev venv"
    ],
    "concerns": [
      "Untracked fixtures sat in disk for 2 days before commit"
    ],
    "next_session_hint": "Confirm JEI re-approval on PR#15 7795203 before requesting #17 review",
    "metric": {
      "skills_invoked": 2,
      "context_switches": 3,
      "wellness_arc": "🟢"
    }
  },
  "ttl": 7,
  "ack": []
}
```

### SYN consumption next session

The next session opening any dimension reads the bus, sees the pending reflection, and presents it to the human operator as part of the dashboard:

```
[REFLECTION pending — amaru session 20260507-amaru-1, by Palas]
Closed two QC002 P0 fronts with JEI...

Hint: Confirm JEI re-approval on PR#15 7795203 before requesting #17 review.

Process? [continue / discard / convert to action]
```

## Success Metrics (4-week pilot)

- ≥ 1 reflection generated per closed session (no skip)
- ≥ 1 `next_session_hint` actioned by human operator every 2 weeks
- 0 reflections with unread `concerns` for > 7 days
- 0 reflections marked as "not useful" by operator > 50% of the time

## Abort Criteria

- If reflections become cognitive load → kill the format
- If Palas becomes a bottleneck → distribute authorship across multiple skills
- If no `next_session_hint` is actioned in 4 weeks → format adds no value → kill

## Security Considerations

- Reflections are broadcast (`dst:*`) and contain operational metadata. They MUST NOT include credentials, tokens, or personal data.
- The authoring skill MUST sanitize `summary`, `insights`, `concerns`, and `next_session_hint` before write.
- Cross-dimension firewall applies: a dimension MAY read reflections from any source, but MUST NOT act on cross-dimensional content beyond presentation per the Clan firewall rules.

## Open Questions (Q3 Council)

- MAY a reflection invoke another skill cross-dimension if the insight warrants? (Today: NO — human-approved proposals only.) Re-evaluate Q3.

## References

- [ARC-2119](ARC-2119.md) — Requirement keywords
- [ARC-5322](ARC-5322.md) — Message format (this type extends the `type` enum)
- [ARC-9001](ARC-9001.md) — Bus integrity (TTL and ACK semantics)
- Council Ampliado deliberation: `knowledge-vault/insights/2026-04-28-consejo-ampliado-ultraplan-001-mvp-piloto.md`
- Original draft: `~/.claude/sync/ARC-REFLECT-01.md` (2026-04-28)

---

*Draft delivered 2026-04-28. Landed as official spec 2026-05-07.*
