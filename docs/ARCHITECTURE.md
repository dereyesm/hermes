# HERMES Architecture Guide

A visual guide to the HERMES protocol stack.

## The 5-Layer Stack

<p align="center">
  <img src="diagrams/d2/five-layer-stack.svg" alt="HERMES 5-layer protocol stack" width="800"/>
</p>

## Message Lifecycle

<p align="center">
  <img src="diagrams/d2/message-lifecycle.svg" alt="HERMES message lifecycle" width="600"/>
</p>

## Namespace Topology

HERMES uses a **star topology** with the controller at the center:

<p align="center">
  <img src="diagrams/d2/namespace-topology.svg" alt="HERMES star topology with controller hub" width="600"/>
</p>

**Key rules**:
- Namespaces NEVER communicate directly — all traffic goes through the bus
- The controller can read all namespaces but cannot execute in any
- Each namespace has its own isolated set of tools and credentials
- Data crosses require explicit firewall rules + human approval

## Firewall Model

<p align="center">
  <img src="diagrams/d2/firewall-model.svg" alt="HERMES firewall model with namespace isolation" width="700"/>
</p>

## Session Lifecycle (SYN/FIN)

<p align="center">
  <img src="diagrams/d2/session-lifecycle.svg" alt="HERMES session lifecycle (SYN/FIN)" width="700"/>
</p>

## Control Plane vs Data Plane

<p align="center">
  <img src="diagrams/d2/control-vs-data-plane.svg" alt="HERMES control plane vs data plane separation" width="700"/>
</p>

HERMES is a **signaling protocol**, not a data protocol. Like SS7 in telecom networks, it carries the coordination messages that tell agents where to work and what changed — but the actual work happens outside the bus.

## File System Layout

A typical HERMES deployment:

```
~/.hermes/                          # or any root directory
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
  <img src="diagrams/d2/gateway-clan-boundary.svg" alt="HERMES gateway at clan boundary with NAT and Agora" width="800"/>
</p>

**What the gateway exposes**: Public profiles (alias, capabilities, Resonance score).

**What the gateway protects**: Internal names, bus messages, Bounty/XP, credentials, namespace topology, memory, session logs.

See [ARC-3022](../spec/ARC-3022.md) for the full specification.

## Dual Reputation Model

<p align="center">
  <img src="diagrams/d2/dual-reputation.svg" alt="HERMES dual reputation model — Bounty vs Resonance" width="600"/>
</p>

## Compact Wire Format (ARC-5322 §14)

HERMES supports a **dual-mode wire format**: verbose (JSON objects) and compact (JSON arrays). Both are valid JSON, readable by standard tools, and can coexist on the same bus.

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
hermes bus --compact      # Output all messages in compact format
hermes bus --expand       # Output all messages in verbose format
cat bus.jsonl | python -m hermes.message --compact   # Convert to compact
cat bus.jsonl | python -m hermes.message --expand    # Convert to verbose
```

### Compact Sealed Envelopes (ARC-8446)

Encrypted messages also support compact representation:

| Mode | Format | Elements |
|------|--------|----------|
| Static | `[ciphertext, nonce, signature, sender_pub, aad]` | 5 |
| ECDHE | `[ciphertext, nonce, signature, sender_pub, aad, eph_pub]` | 6 |

Auto-detection by array length: 5 = static, 6 = ECDHE with forward secrecy.

<p align="center">
  <img src="diagrams/d2/compact-wire-format.svg" alt="HERMES compact wire format comparison" width="700"/>
</p>

See [ARC-5322 §14](../spec/ARC-5322.md) and [ATR-G.711](../spec/ATR-G711.md) for the full specification and efficiency analysis.

## Installer & Claude Code Integration

The `installer` module ([`reference/python/hermes/installer.py`](../reference/python/hermes/installer.py)) provides one-command setup for the full HERMES stack:

```
hermes install --clan-id <id> --display-name <name>
       │
       ├─ 1. init_clan_if_needed()     → ~/.hermes/gateway.json + bus.jsonl
       ├─ 2. generate_keypair()        → ~/.hermes/.keys/<id>.key (Ed25519 + X25519)
       ├─ 3. add_agent_node_section()  → gateway.json agent_node block
       ├─ 4. install_service()         → OS-specific daemon registration
       ├─ 5. install_hooks()           → Claude Code hooks (3 events)
       └─ 6. notify()                  → desktop notification
```

**OS service targets**:

| Platform | Mechanism | Path |
|----------|-----------|------|
| macOS | LaunchAgent plist | `~/Library/LaunchAgents/com.hermes.agent-node.plist` |
| Linux | systemd user unit | `~/.config/systemd/user/hermes-agent.service` |
| Windows | Scheduled task | `HermesAgentNode` (schtasks) |

**Claude Code hooks** ([`hooks.py`](../reference/python/hermes/hooks.py)):

| Hook | Event | Behavior |
|------|-------|----------|
| `pull_on_start` | `SessionStart` | Shows pending bus messages as `systemMessage` |
| `pull_on_prompt` | `UserPromptSubmit` | Activates on `/hermes` prefixed prompts |
| `exit_reminder` | `Stop` | Reminds about unacked messages |

Hooks are cross-platform (no bash dependency), invoked as `python -m hermes.hooks <cmd>`.

![Install Flow](diagrams/d2/install-flow.svg)

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
| [ATR-Q.700](../spec/ATR-Q700.md) | OOB Signaling | Design philosophy |
