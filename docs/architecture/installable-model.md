# HERMES Installable Model

> HERMES is a protocol, not an agent. The agent is a client.

## The Problem

HERMES v0.4 is tightly coupled to Claude Code:
- Skills live in `.claude/skills/`
- Config lives in `.claude/CLAUDE.md`
- Rules live in `.claude/rules/`
- Bus lives in `.claude/sync/bus.jsonl`

This means HERMES only works with Claude Code. It should work with **any** AI coding assistant.

## Core Principle: Agent-Agnostic

```
┌─────────────────────────────────────┐
│         Agent (any)                 │
│  Claude Code / Cursor / Copilot /  │
│  Windsurf / custom CLI             │
│         "speaks" HERMES            │
└──────────────┬──────────────────────┘
               │ reads/writes
┌──────────────▼──────────────────────┐
│         HERMES Runtime              │
│  bus · dimensions · skills · config │
│  daemons (heraldo, etc)             │
└──────────────┬──────────────────────┘
               │ lives on
┌──────────────▼──────────────────────┐
│     Filesystem (FHS-compliant)      │
│  ~/.hermes   /opt/hermes   /etc/    │
└─────────────────────────────────────┘
```

The **adapter** bridges HERMES ↔ Agent. Each agent has its own config format
(Claude uses CLAUDE.md, Cursor uses .cursorrules, etc). The adapter translates.

## User Model

Every HERMES user has a **home** (`~/`) and N dimensions organized by domain:

```
~/                          ← User's Global Home (NOT a dimension)
│
├── Labor dimensions        (varies per user)
│   ├── Org A/              e.g. Nymyka
│   └── Org B/              e.g. Techentix
│
├── Personal dimensions     (varies per user)
│   ├── Finance/            e.g. MomoFinance pattern
│   ├── Wellness/           e.g. MomoshoD pattern
│   └── Housing/            e.g. Zima26 pattern
│
└── Global                  ← cross-dimensional (deliberation, strategy)
```

Dimensions are not hardcoded. Each user defines their own topology.
HERMES provides the structure; the user fills the content.

## System Agents

Two agent roles are part of the HERMES runtime (not the AI assistant):

| Role | Daniel's instance | Purpose | Runs as |
|------|-------------------|---------|---------|
| **Controller** | Claude Code + /dojo | Main assistant, dispatches to skills, manages lifecycle | Interactive (user-invoked) |
| **Messenger** | Heraldo | Reads external buses (email, Slack, etc), injects into HERMES bus | Daemon (background) |

For another user:
- Controller could be Cursor + a dojo-equivalent plugin
- Messenger could be named anything, connected to their email/Slack

## Filesystem Layout (FHS-compliant)

### Per-user install (recommended for personal use)

```
~/.hermes/                  ← HERMES home (XDG-compatible)
├── config.toml             ← dimensions, firewalls, MCP bindings
├── bus/
│   ├── active.jsonl        ← live messages
│   └── archive.jsonl       ← expired messages
├── dimensions/
│   ├── nymyka/
│   │   ├── skills/         ← dimension-scoped skills
│   │   ├── rules/          ← dimension-scoped rules
│   │   └── state.toml      ← sync header, health
│   ├── personal/
│   │   ├── skills/
│   │   └── state.toml
│   └── global/
│       ├── skills/         ← cross-dimensional (consejo, palas, ares, artemisa)
│       └── state.toml
├── daemons/
│   ├── messenger/          ← heraldo config + state
│   │   ├── config.toml     ← sources (gmail, slack, etc)
│   │   └── state.json      ← last scan, processed IDs
│   └── ...                 ← future daemons
├── adapters/
│   ├── claude-code/        ← generates .claude/ structure from .hermes/
│   ├── cursor/             ← generates .cursorrules from .hermes/
│   └── generic/            ← spec for building new adapters
├── memory/                 ← persistent memory (cross-session)
│   └── MEMORY.md
└── logs/
    └── sessions/           ← session harvest logs
```

### System-wide install (multi-user, server)

```
/opt/hermes/                ← binaries, runtime
/etc/hermes/                ← system-wide config defaults
/var/lib/hermes/            ← shared state (multi-user bus)
/var/log/hermes/            ← centralized logs
```

Each user still has `~/.hermes/` for their personal dimensions.
System install provides shared infrastructure (bus relay, daemon supervisor).

### Dedicated user

```bash
useradd --system --home-dir /var/lib/hermes --shell /usr/sbin/nologin hermes
```

Daemons (messenger, etc.) run as `hermes` user. Interactive sessions run as
the human user, reading from `~/.hermes/`.

## Config Schema (config.toml)

HERMES uses TOML for its canonical configuration format. The schema maps 1:1 to
the `GatewayConfig` dataclass in the reference implementation.

```toml
schema_version = 1

[clan]
id = "clan-alpha"
display_name = "Alpha Collective"
protocol_version = "0.4.2"

[keys]
private = ".keys/gateway.key"
public = ".keys/gateway.pub"

[bus]
active = "bus/active.jsonl"
archive = "bus/archive.jsonl"

[heraldo]
alias = "herald"
capabilities = ["inter-clan-messaging"]

[agora]
type = "git"
url = ""
local_cache = ".agora/"

[inbound]
max_payload_bytes = 4096
rate_limit_per_clan = 10
quarantine_first_contact = true
auto_accept_hello = true

[outbound]
default = "deny"

[outbound.rules]
profile_update = { action = "allow", approval = "operator" }
attestation = { action = "allow", approval = "operator_per_instance" }
quest_response = { action = "allow", approval = "operator_per_instance" }
hello_ack = { action = "allow", approval = "auto" }

[[agents]]
alias = "scout"
capabilities = ["research"]

[[peers]]
clan_id = "clan-jei"
public_key_file = ".keys/peers/jei.pub"
status = "established"
added = "2026-03-01"

[daemon]
enabled = true
namespace = "heraldo"
poll_interval = 2.0
forward_types = ["alert", "dispatch", "event"]
```

| Section | Purpose |
|---------|---------|
| `schema_version` | Integer, increments on breaking changes |
| `[clan]` | Identity: id, display name, protocol version |
| `[keys]` | Paths to Ed25519/X25519 keypair (relative to clan dir) |
| `[bus]` | Paths to active and archive bus files |
| `[heraldo]` | Messenger daemon identity |
| `[agora]` | Discovery directory settings |
| `[inbound]` / `[outbound]` | Gateway firewall rules (ARC-3022) |
| `[[agents]]` | Published agent roster |
| `[[peers]]` | Known peer clans |
| `[daemon]` | Agent Node daemon configuration (ARC-4601) |

### Migration from gateway.json

Existing installations using `gateway.json` continue to work. HERMES auto-discovers
the config file, preferring `config.toml` over `gateway.json`.

To migrate: `hermes config migrate` — reads `gateway.json`, writes `config.toml`,
keeps the JSON file as backup.

## The Adapter Pattern

Adapters are the bridge between HERMES's canonical structure and what each
AI assistant expects.

### Claude Code adapter (example)

Reads `~/.hermes/` → generates:

```
~/.claude/
├── CLAUDE.md              ← from config.toml + dimension states
├── skills/                ← symlinks or copies from .hermes/dimensions/*/skills/
├── rules/                 ← from .hermes/dimensions/*/rules/
└── sync/
    └── bus.jsonl          ← symlink to .hermes/bus/active.jsonl
```

### Cursor adapter (example)

Reads `~/.hermes/` → generates:

```
.cursorrules               ← from config.toml + active dimension skills
.cursor/                   ← workspace config
```

### Adapter contract

An adapter MUST:
1. Read `~/.hermes/config.toml` for dimension topology
2. Read active dimension's `skills/` and `rules/`
3. Read `bus/active.jsonl` for pending messages
4. Write session state changes back to `.hermes/` (not to agent-specific dirs)
5. Be idempotent (can re-run safely)

An adapter MUST NOT:
1. Modify HERMES state directly (use the bus)
2. Bypass firewall rules defined in config.toml
3. Hardcode dimension names or paths

## Migration Path (v0.4 → v1.0)

```
Phase 1: Canonical structure
  - Define ~/.hermes/ layout (this document)
  - Build config.toml schema
  - Migrate bus.jsonl → .hermes/bus/

Phase 2: Claude Code adapter
  - Build adapter that generates .claude/ from .hermes/
  - Run both in parallel (dual-write) for validation
  - Daniel keeps working normally — adapter runs on session start

Phase 3: Second adapter
  - Build Cursor or generic adapter
  - Proves agent-agnostic design works

Phase 4: Daemon extraction
  - Heraldo runs as systemd service (not Claude Code agent)
  - Reads .hermes/daemons/messenger/config.toml
  - Writes to .hermes/bus/active.jsonl directly

Phase 5: Package & distribute
  - `hermes init` CLI command
  - npm/pip/brew install
  - User runs `hermes init` → gets ~/.hermes/ scaffold
  - User runs `hermes adapt claude-code` → gets .claude/ generated
```

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Config format | TOML | Human-readable, typed, standard (like Cargo.toml, pyproject.toml) |
| Bus format | JSONL | Append-only, line-diffable, already proven in v0.4 |
| Adapter output | Files | Agents read files, not APIs. Keep it simple. |
| Per-user vs system | Both | Personal use = ~/.hermes/. Server = /opt + /etc + /var |
| Daemon supervisor | systemd | Industry standard. launchd on macOS. |

## Open Questions

- [ ] Should adapters use symlinks or file copies? (symlinks are simpler but some agents may not follow them)
- [ ] Config.toml schema — what's the minimum viable config?
- [ ] How does `hermes init` detect existing .claude/ state and offer migration?
- [ ] Multi-agent: can two agents use the same .hermes/ concurrently? (ARC-9001 applies here)
- [ ] Skill format: keep .md or introduce a structured format (TOML frontmatter + md body)?
