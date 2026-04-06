# Amaru Architecture Guide

A visual guide to the Amaru (formerly HERMES) protocol stack.

## The 5-Layer Stack

<p align="center">
  <img src="diagrams/d2/five-layer-stack.svg" alt="Amaru 5-layer protocol stack" width="800"/>
</p>

## Message Lifecycle

<p align="center">
  <img src="diagrams/d2/message-lifecycle.svg" alt="Amaru message lifecycle" width="600"/>
</p>

## Namespace Topology

Amaru uses a **star topology** with the controller at the center:

<p align="center">
  <img src="diagrams/d2/namespace-topology.svg" alt="Amaru star topology with controller hub" width="600"/>
</p>

**Key rules**:
- Namespaces NEVER communicate directly — all traffic goes through the bus
- The controller can read all namespaces but cannot execute in any
- Each namespace has its own isolated set of tools and credentials
- Data crosses require explicit firewall rules + human approval

## Firewall Model

<p align="center">
  <img src="diagrams/d2/firewall-model.svg" alt="Amaru firewall model with namespace isolation" width="700"/>
</p>

## Session Lifecycle (SYN/FIN)

<p align="center">
  <img src="diagrams/d2/session-lifecycle.svg" alt="Amaru session lifecycle (SYN/FIN)" width="700"/>
</p>

## Control Plane vs Data Plane

<p align="center">
  <img src="diagrams/d2/control-vs-data-plane.svg" alt="Amaru control plane vs data plane separation" width="700"/>
</p>

Amaru is a **signaling protocol**, not a data protocol. Like SS7 in telecom networks, it carries the coordination messages that tell agents where to work and what changed — but the actual work happens outside the bus.

## File System Layout

A typical Amaru deployment:

```
~/.amaru/                          # or any root directory
├── bus.jsonl                       # active messages
├── bus-archive.jsonl               # expired messages
├── routes.md                       # routing table
│
├── engineering/                    # namespace: engineering
│   ├── config.md                   # namespace config + SYNC HEADER
│   ├── memory/                     # persistent state
│   │   └── MEMORY.md
│   └── agents/                     # agent definitions
│       ├── lead.md
│       └── reviewer.md
│
├── finance/                        # namespace: finance
│   ├── config.md
│   ├── memory/
│   │   └── MEMORY.md
│   └── agents/
│       └── accountant.md
│
└── controller/                     # namespace: controller
    ├── config.md
    └── agents/
        └── router.md
```

## Gateway: The Clan Boundary

When a clan wants to connect with other clans on the Agora (public inter-clan network), it deploys a **Gateway** — a NAT-like component at the boundary.

<p align="center">
  <img src="diagrams/d2/gateway-clan-boundary.svg" alt="Amaru gateway at clan boundary with NAT and Agora" width="800"/>
</p>

**What the gateway exposes**: Public profiles (alias, capabilities, Resonance score).

**What the gateway protects**: Internal names, bus messages, Bounty/XP, credentials, namespace topology, memory, session logs.

See [ARC-3022](../spec/ARC-3022.md) for the full specification.

## Dual Reputation Model

<p align="center">
  <img src="diagrams/d2/dual-reputation.svg" alt="Amaru dual reputation model — Bounty vs Resonance" width="600"/>
</p>

## Compact Wire Format (ARC-5322 §14)

Amaru supports a **dual-mode wire format**: verbose (JSON objects) and compact (JSON arrays). Both are valid JSON, readable by standard tools, and can coexist on the same bus.

### Verbose vs Compact

```
Verbose:  {"ts":"2026-03-17","src":"engineering","dst":"*","type":"state","msg":"API deployed","ttl":7,"ack":[]}
Compact:  [9572,"engineering","*",0,"API deployed",7,[]]
```

The compact format replaces key names with positional indices and uses integer encodings for `ts` (epoch-day since 2000-01-01) and `type` (enum 0-6). This eliminates ~69 bytes of overhead per message.

### Efficiency

| Format | Overhead | Efficiency | vs gRPC |
|--------|----------|-----------|---------|
| Verbose | 105 B | 53.1% | 1.7x better |
| **Compact** | **36 B** | **76.9%** | **4.9x better** |
| gRPC (HTTP/2+protobuf) | 180 B | 40.0% | — |

### Mixed-Mode Bus

The bus auto-detects format by the first character of each line (`{` = verbose, `[` = compact). Implementations read both formats regardless of which they write.

```
{"ts":"2026-03-17","src":"alpha","dst":"*","type":"state","msg":"old agent","ttl":7,"ack":[]}
[9572,"beta","*",2,"new agent",3,[]]
```

### CLI Support

```bash
amaru bus --compact      # Output all messages in compact format
amaru bus --expand       # Output all messages in verbose format
cat bus.jsonl | python -m amaru.message --compact   # Convert to compact
cat bus.jsonl | python -m amaru.message --expand    # Convert to verbose
```

### Compact Sealed Envelopes (ARC-8446)

Encrypted messages also support compact representation:

| Mode | Format | Elements |
|------|--------|----------|
| Static | `[ciphertext, nonce, signature, sender_pub, aad]` | 5 |
| ECDHE | `[ciphertext, nonce, signature, sender_pub, aad, eph_pub]` | 6 |

Auto-detection by array length: 5 = static, 6 = ECDHE with forward secrecy.

<p align="center">
  <img src="diagrams/d2/compact-wire-format.svg" alt="Amaru compact wire format comparison" width="700"/>
</p>

See [ARC-5322 §14](../spec/ARC-5322.md) and [ATR-G.711](../spec/ATR-G711.md) for the full specification and efficiency analysis.

## Installer & Claude Code Integration

The `installer` module ([`reference/python/amaru/installer.py`](../reference/python/amaru/installer.py)) provides one-command setup for the full Amaru stack:

```
amaru install --clan-id <id> --display-name <name>
       │
       ├─ 1. init_clan_if_needed()     → ~/.amaru/gateway.json + bus.jsonl
       ├─ 2. generate_keypair()        → ~/.amaru/.keys/<id>.key (Ed25519 + X25519)
       ├─ 3. add_agent_node_section()  → gateway.json agent_node block
       ├─ 4. install_service()         → OS-specific daemon registration
       ├─ 5. install_hooks()           → Claude Code hooks (3 events)
       └─ 6. notify()                  → desktop notification
```

**OS service targets**:

| Platform | Mechanism | Path |
|----------|-----------|------|
| macOS | LaunchAgent plist | `~/Library/LaunchAgents/com.amaru.agent-node.plist` |
| Linux | systemd user unit | `~/.config/systemd/user/amaru-agent.service` |
| Windows | Scheduled task | `AmaruAgentNode` (schtasks) |

**Claude Code hooks** ([`hooks.py`](../reference/python/amaru/hooks.py)):

| Hook | Event | Behavior |
|------|-------|----------|
| `pull_on_start` | `SessionStart` | Shows pending bus messages as `systemMessage` |
| `pull_on_prompt` | `UserPromptSubmit` | Activates on `/amaru` prefixed prompts |
| `exit_reminder` | `Stop` | Reminds about unacked messages |

Hooks are cross-platform (no bash dependency), invoked as `python -m amaru.hooks <cmd>`.

![Install Flow](diagrams/d2/install-flow.svg)

## Adapter Pattern — Agent-Agnostic Bridge

The **Adapter** ([`adapter.py`](../reference/python/amaru/adapter.py)) bridges Amaru's canonical filesystem structure (`~/.amaru/`) to each AI assistant's native config format.

**Claude Code Adapter** reads `~/.amaru/config.toml` and generates:

```
~/.claude/
├── CLAUDE.md              ← from config.toml + dimension states
├── skills/                ← symlinks to .amaru/dimensions/*/skills/
├── rules/                 ← symlinks to .amaru/dimensions/*/rules/ (prefixed by dimension)
└── sync/
    └── bus.jsonl          ← symlink to .amaru/bus/active.jsonl
```

```bash
amaru adapt claude-code                    # default paths
amaru adapt claude-code --amaru-dir /opt/amaru --target-dir ~/.claude
```

Adapters are idempotent (safe to re-run) and follow the contract in [installable-model.md](architecture/installable-model.md).

**4 adapters available:**

| Adapter | Target | Output Strategy | Command |
|---------|--------|----------------|---------|
| Claude Code | `~/.claude/` | Symlinks + CLAUDE.md | `amaru adapt claude-code` |
| Cursor | Project root | Compiled `.cursorrules` (Amaru:BEGIN/END markers) | `amaru adapt cursor` |
| OpenCode | `~/.config/opencode/` | AGENTS.md + opencode.json merge + symlinks | `amaru adapt opencode` |
| Gemini CLI | `~/.gemini/` | GEMINI.md + settings.json merge + symlinks | `amaru adapt gemini` |

Auto-detect and adapt all: `amaru adapt --all`. List available: `amaru adapt --list`.

## Token Telemetry

The **Telemetry** module ([`llm/telemetry.py`](../reference/python/amaru/llm/telemetry.py)) monitors token usage across LLM providers in real time.

- **TokenTracker**: Records `input_tokens`, `output_tokens`, and estimates cost per call
- **COST_PER_MTOK**: Built-in pricing table for 10 models (Claude, Gemini, OpenAI)
- **Persistence**: Append-only JSONL (`~/.amaru/telemetry.jsonl`)
- **CLI**: `amaru llm usage` — dashboard with per-model breakdown, budget tracking, CSV export
- **Auto-instrument**: `AdapterManager.complete()` records telemetry automatically

## Agent Service Platform (ARC-0369)

The **ASP** ([`asp.py`](../reference/python/amaru/asp.py)) extends the daemon with structured agent management:

- **F1 Bus Convergence**: `MessageClassifier` categorizes every bus message as `internal`, `outbound`, `inbound`, or `expired`. Internal-only namespaces are enforced. Source integrity is verified.
- **F2 Agent Registration**: `AgentRegistry` loads declarative agent profiles from `agents/*.json`. Each profile declares capabilities, dispatch rules (event-driven or scheduled), resource limits, and approval gates.
- **F3 Dispatch Protocol**: `DispatchEngine` evaluates messages against all enabled agents, producing `DispatchDecision` objects. Includes `ConcurrencyTracker`, `ApprovalGateManager`, `DispatchScheduler`, and `DispatchCommandRenderer`.
- **F4 Agent Lifecycle**: `AgentStateTracker` tracks per-agent state (INACTIVE→ACTIVE→PENDING→RUNNING→IDLE→FAILED→REMOVED) with legal transition enforcement, dispatch counters, and heartbeat payload.
- **F5 Notification Flow**: `NotificationThrottler` enforces max 5 notifications/min/source with suppression rules for dispatch results, `data_cross`, and `state` messages.

```bash
amaru agent list       # list registered agents
amaru agent show <id>  # show agent profile JSON
amaru agent validate   # validate all profiles
```

See [ARC-0369](../spec/ARC-0369.md) for the full specification.

## Bus Integrity (ARC-9001)

The **Bus Integrity Protocol** ([`integrity.py`](../reference/python/amaru/integrity.py)) provides message sequencing and write ownership for the Amaru bus:

- **F1 Message Sequencing**: `SequenceTracker` assigns monotonic `seq` numbers per source namespace. Detects gaps (missing messages) and duplicates (replay). Inspired by SS7 FSN/BSN (ITU-T Q.703 §5.2).
- **F2 Write Ownership**: `OwnershipRegistry` maps namespaces to authorized writers. Only the registered owner can write `src=namespace`. Default: daemon owns all local namespaces; ASP agents get ownership of their namespace.
- **F3 MVCC Write Vectors**: `WriteVector` captures the writer's causal view of the bus (`{src: last_seen_seq}`). `WriteVectorTracker` uses a sliding window to detect concurrent writes (vector clock semantics). The `w` field in messages is verbose-JSON only (compact unchanged).
- **F4 Conflict Log**: `ConflictLog` records integrity violations (gaps, duplicates, ownership breaches, concurrent writes) to `bus-conflicts.jsonl`. Append-only, independent of bus archival. Provides forensic data for security audits.
- **F5 Recovery**: `SnapshotManager` creates `bus-snapshot.json` with seq_state + ownership + SHA-256 bus hash for fast recovery. `ReplayRequest` formats gap-fill requests as dispatch messages. `BusSnapshot` is verified against bus content before restoring.
- **F6 Garbage Collection**: `BusGC` computes per-source archive thresholds, moves old messages to `bus-archive.jsonl`, and compacts the bus atomically (temp file + `os.replace()`). Messages without `seq` are always preserved. Conflict log is never touched.

See [ARC-9001](../spec/ARC-9001.md) for the full specification.

## Hub Mode (ARC-4601 §15)

The **Hub** ([`hub.py`](../reference/python/amaru/hub.py)) extends the Agent Node with a server mode that routes encrypted messages between peer daemons:

- **WebSocket transport**: Bidirectional messaging over a single TCP connection (RFC 6455)
- **Ed25519 challenge-response auth**: Peers authenticate using existing ARC-8446 keys — no new crypto
- **E2E passthrough**: Hub reads only `src`, `dst`, `type`, `ttl` — cannot decrypt the `msg` field
- **Store-and-forward**: FIFO queue per peer with TTL-based eviction; drains on reconnect
- **Presence**: Peers receive online/offline notifications for connected clans
- **Legacy endpoints**: `/events` (SSE), `/bus/push` (POST), `/healthz` for backward compatibility

The Hub is a **routing convenience, not a trust boundary** — ARC-8446 E2E encryption ensures the Hub cannot see message content. Phase B (§16 DRAFT) adds optional P2P tunnels using Noise IK for direct peer connectivity.

```bash
amaru hub init        # bootstrap hub-peers.json from peer registry
amaru hub start       # start Hub server (--foreground for interactive)
amaru hub stop        # graceful shutdown
amaru hub status      # show PID, uptime, messages routed
amaru hub peers       # list registered peers
```

See [ARC-4601 §15](../spec/ARC-4601.md) for the full specification.

## Related Specifications

| Spec | Title | What it covers |
|------|-------|---------------|
| [ARC-0001](../spec/ARC-0001.md) | HERMES Architecture | The meta-standard |
| [ATR-X.200](../spec/ATR-X200.md) | Reference Model | Formal 5-layer model |
| [ARC-5322](../spec/ARC-5322.md) | Message Format | JSONL packet spec |
| [ARC-0793](../spec/ARC-0793.md) | Reliable Transport | SYN/FIN/ACK |
| [ARC-0791](../spec/ARC-0791.md) | Addressing & Routing | Namespaces and routes |
| [ARC-1918](../spec/ARC-1918.md) | Private Spaces | Firewall model |
| [ARC-3022](../spec/ARC-3022.md) | Agent Gateway | NAT, filtering, Agora connection |
| [ARC-9001](../spec/ARC-9001.md) | Bus Integrity | Sequencing, ownership, MVCC |
| [ARC-4601](../spec/ARC-4601.md) | Agent Node + Hub Mode | Daemon, WebSocket Hub (§15), P2P tunnels (§16 DRAFT) |
| [ARC-0369](../spec/ARC-0369.md) | Agent Service Platform | Bus convergence, agent registry, lifecycle |
| [ARC-8446](../spec/ARC-8446.md) | Encrypted Bus Protocol | Ed25519, X25519, AES-256-GCM, ECDHE |
| [ATR-G.711](../spec/ATR-G711.md) | Wire Efficiency | Payload encoding, compact format |
| [ATR-Q.700](../spec/ATR-Q700.md) | OOB Signaling | Design philosophy |
