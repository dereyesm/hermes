# Agent Registration Guide — HERMES ARC-0369

> How to register agents so your AgentNode can dispatch work autonomously.

## Quick Start

```bash
mkdir -p ~/.hermes/agents
cat > ~/.hermes/agents/my-agent.json << 'EOF'
{
  "agent_id": "my-agent",
  "display_name": "My First Agent",
  "version": "1.0.0",
  "role": "worker",
  "description": "What this agent does in one sentence.",
  "capabilities": ["communication/messaging"],
  "dispatch_rules": [
    {
      "rule_id": "my-rule",
      "trigger": {
        "type": "event-driven",
        "match_type": "dispatch"
      },
      "approval_required": false
    }
  ],
  "resource_limits": {
    "max_turns": 5,
    "timeout_seconds": 120,
    "allowed_tools": ["Read", "Grep", "Glob", "Bash"],
    "max_concurrent": 1
  },
  "enabled": true
}
EOF
```

Then ensure your `gateway.json` has an `agent_node` section:

```json
{
  "agent_node": {
    "enabled": true,
    "bus_path": "bus.jsonl",
    "namespace": "your-clan-id",
    "auto_peer_enabled": true,
    "hub_inbox_path": "hub-inbox.jsonl",
    "max_dispatch_slots": 2,
    "evaluation_interval": 300,
    "dispatch_command": "claude",
    "dispatch_max_turns": 10
  }
}
```

Restart daemon: `hermes daemon stop && hermes daemon start`

## Agent JSON Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent_id` | string | Yes | Unique ID (used in routing, logs, state) |
| `display_name` | string | Yes | Human-readable name |
| `version` | string | Yes | SemVer version |
| `role` | string | Yes | `sensor`, `worker`, `orchestrator` |
| `description` | string | Yes | What the agent does (1-2 sentences) |
| `capabilities` | string[] | Yes | Capability tags (see below) |
| `dispatch_rules` | object[] | Yes | When and how the agent gets triggered |
| `resource_limits` | object | Yes | Guardrails for the agent |
| `enabled` | bool | Yes | `true` to activate, `false` to disable |

## Roles

| Role | Purpose | Example |
|------|---------|---------|
| `sensor` | Observe and classify (no side effects) | Email scanner, message classifier |
| `worker` | Execute tasks (read/write) | Quest handler, code generator |
| `orchestrator` | Coordinate other agents | Quest dispatcher, workflow manager |

## Capabilities

Standard capability tags (ARC-2314):

```
communication/messaging    — send/receive messages
communication/email        — email operations
operations/support         — general support
operations/triage          — classify and route
operations/dispatch        — forward to handlers
operations/cross-clan      — inter-clan operations
engineering/software       — code tasks
engineering/review         — code review
creative/writing           — content creation
data/analysis              — data processing
```

## Dispatch Rules

Each rule defines when the AgentNode triggers this agent:

```json
{
  "rule_id": "unique-rule-name",
  "trigger": {
    "type": "event-driven",       // or "scheduled"
    "match_type": "dispatch",     // bus message type to match
    "match_msg_prefix": "QUEST-"  // optional: only match messages starting with this
  },
  "approval_required": true,      // human must approve before dispatch
  "approval_timeout_hours": 24    // auto-reject after this time
}
```

### Trigger Types

| Type | Fires When | Example |
|------|------------|---------|
| `event-driven` | Bus message matches `match_type` (+ optional `match_msg_prefix`) | Quest arrives from peer |
| `scheduled` | Cron schedule (evaluation_interval) | Periodic bus scan |

### Match Types (bus message types)

| match_type | Description |
|------------|-------------|
| `dispatch` | Action request — someone wants work done |
| `event` | Status update — informational |
| `alert` | Urgent — needs immediate attention |
| `state` | State change — session boundary |
| `data_cross` | Cross-dimensional data transfer |

## Resource Limits

Guardrails to prevent runaway agents:

```json
{
  "max_turns": 10,           // max conversation turns with Claude
  "timeout_seconds": 300,    // hard timeout
  "allowed_tools": [         // which tools the agent can use
    "Read", "Grep", "Glob", "Bash"
  ],
  "max_concurrent": 2        // max simultaneous dispatches
}
```

## Example: Cross-Clan Dispatcher (for Quest-006)

This is the minimum agent needed for bilateral quest handling:

```json
{
  "agent_id": "cross-clan-dispatcher",
  "display_name": "Cross-Clan Dispatcher",
  "version": "0.1.0",
  "role": "worker",
  "description": "Processes incoming dispatch and event messages from peer clans via the hub.",
  "capabilities": [
    "communication/messaging",
    "operations/dispatch",
    "operations/cross-clan"
  ],
  "dispatch_rules": [
    {
      "rule_id": "cross-clan-dispatch",
      "trigger": {
        "type": "event-driven",
        "match_type": "dispatch",
        "match_msg_prefix": "QUEST-"
      },
      "approval_required": true,
      "approval_timeout_hours": 24
    },
    {
      "rule_id": "cross-clan-event-ack",
      "trigger": {
        "type": "event-driven",
        "match_type": "event",
        "match_msg_prefix": "DANI-HERMES-"
      },
      "approval_required": false
    }
  ],
  "resource_limits": {
    "max_turns": 10,
    "timeout_seconds": 300,
    "allowed_tools": ["Read", "Grep", "Glob", "Bash"],
    "max_concurrent": 2
  },
  "enabled": true
}
```

Save as `~/.hermes/agents/cross-clan-dispatcher.json`, restart daemon, done.

## Verification

After registering an agent:

```bash
# Check daemon sees it
hermes status
# Should show agent in Agent Node row

# Check agent file is valid JSON
python3 -m json.tool ~/.hermes/agents/your-agent.json

# Test dispatch manually
hermes bus write --type dispatch --msg "QUEST-TEST: ping" --dst your-clan-id
# Agent should pick it up on next evaluation cycle
```

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Agent not showing in status | No `agent_node` section in gateway.json | Add the section (see Quick Start) |
| "No agent_node section" error | Missing config | Add `agent_node` to gateway.json |
| Agent not triggering | `match_type` doesn't match bus message type | Check dispatch_rules trigger |
| Daemon won't start | Stale PID lock | `rm ~/.hermes/.agent-node.pid` then start |
