# UC-04: Agent Node Daemon Lifecycle

> How the Agent Node starts, operates continuously, handles events, and shuts down gracefully.

The Agent Node is the persistent counterpart to ephemeral sessions — it keeps your clan alive between human interactions.

## Use Case Flow

```mermaid
flowchart TD
    START([Human wants continuous<br/>bus observation + auto-dispatch]) --> CONFIG

    subgraph setup ["1. Configuration"]
        CONFIG["Configure gateway.json:<br/>agent_node.enabled = true<br/>namespace, bus_path,<br/>gateway_url, auth tokens"]
        CONFIG --> LAUNCH["hermes daemon start<br/>or launchctl load (macOS)<br/>or systemctl start (Linux)"]
    end

    subgraph init ["2. Initialization"]
        LAUNCH --> LOCK{"PID lock<br/>exists?"}
        LOCK -->|"Lock exists,<br/>PID alive"| ABORT([Abort: node already running])
        LOCK -->|"Lock exists,<br/>PID dead"| RECOVER["Recover: load state,<br/>resume from bus_offset"]
        LOCK -->|"No lock"| FRESH["Fresh start:<br/>offset = 0"]
        RECOVER --> RUNNING
        FRESH --> RUNNING
    end

    subgraph running ["3. Steady State (three parallel tasks)"]
        RUNNING["RUNNING state"]

        RUNNING --> OBS["BusObserver:<br/>Watch bus.jsonl<br/>(kqueue/inotify/poll)"]
        RUNNING --> LINK["GatewayLink:<br/>SSE inbound<br/>HTTP POST outbound<br/>Heartbeat every 60s"]
        RUNNING --> EVAL["Evaluation Cycle:<br/>Every 300s check<br/>pending messages"]

        OBS --> NEW["New message detected"]
        LINK --> INBOUND["Inbound from gateway"]
        EVAL --> DECIDE

        NEW --> DECIDE{"Message type?"}
        INBOUND --> VALIDATE["Validate ARC-5322<br/>Dedup check<br/>Write to bus"]

        DECIDE -->|"dispatch"| DISPATCH["Spawn sub-agent<br/>(max 2 slots,<br/>timeout 300s)"]
        DECIDE -->|"alert > 4h"| ESCALATE["Forward to gateway<br/>with escalation flag"]
        DECIDE -->|"request"| HUMAN["Escalate: requires<br/>human decision"]
        DECIDE -->|"event (external)"| FORWARD["Forward via<br/>HTTP POST"]
        DECIDE -->|"state / ACKed"| IGNORE["Ignore"]

        DISPATCH --> RESULT{"Dispatch<br/>result?"}
        RESULT -->|"Success"| WRITE_OK["Write event<br/>[RE:CID] to bus"]
        RESULT -->|"Failure"| WRITE_FAIL["Write alert<br/>DISPATCH_FAILED"]
        RESULT -->|"Timeout"| WRITE_TO["Write alert<br/>DISPATCH_TIMEOUT"]
    end

    subgraph shutdown ["4. Graceful Shutdown"]
        SIGTERM["SIGTERM received"]
        SIGTERM --> DRAIN["DRAINING:<br/>Stop new dispatches"]
        DRAIN --> WAIT["Wait for in-flight<br/>dispatches to complete"]
        WAIT --> PERSIST["Persist state<br/>(atomic write)"]
        PERSIST --> RELEASE["Release PID lock"]
        RELEASE --> STOPPED([STOPPED])
    end

    style START fill:#1a1a2e,color:#fff
    style RUNNING fill:#1a3a1a,color:#fff
    style STOPPED fill:#16213e,color:#fff
    style ABORT fill:#3e1616,color:#fff
```

## Key Design Points

- **Zero-to-running**: configure `gateway.json`, run one command
- **Three parallel tasks**: BusObserver + GatewayLink + Evaluator run concurrently
- **Dispatch guardrails**: max slots, timeout, tool allowlist — prevents runaway agents
- **Graceful shutdown**: DRAINING state ensures in-flight work completes
- **Recovery**: stale PID lock is reclaimed, bus_offset resumes from stored state
- **Process manager friendly**: `--foreground` flag works with launchd, systemd, Docker

## Referenced By

- [ARC-4601: Agent Node Protocol](../../spec/ARC-4601.md) -- Full specification
- [SEQ-4601: Agent Node Sequence](seq-4601-agent-node.md) -- Detailed message flow
