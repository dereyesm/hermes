# HERMES Protocol — Integration with Claude Code

> How HERMES inter-agent communication works within the Claude/Anthropic ecosystem.

## What is HERMES?

HERMES is an open-source protocol for inter-agent AI communication, inspired by TCP/IP and telecom standards (3GPP, ITU-T, IETF). It enables AI agents to coordinate across tools, sessions, and teams using a lightweight file-based message bus.

- **Repo**: https://github.com/dereyesm/hermes (MIT license)
- **Version**: v0.4.2-alpha (20 spec files, 1146 tests, 17 Python modules)
- **Philosophy**: Sovereign-first (runs on local files, no cloud required), with optional Hub Mode for real-time connectivity

## How HERMES Integrates with Claude Code

### 1. Hooks (Claude Code → HERMES)

HERMES registers three Claude Code hooks that activate automatically:

| Hook | Event | What it does |
|------|-------|-------------|
| `pull_on_start` | SessionStart | Reads bus.jsonl, shows pending messages as systemMessage |
| `pull_on_prompt` | UserPromptSubmit | Activates on `/hermes` commands, refreshes bus state |
| `exit_reminder` | Stop | Reminds about unacked messages before session close |

Hooks are installed via `hermes install` and configured in Claude Code's `settings.json`. They use stdin/stdout JSON (no bash dependency, cross-platform).

**Implementation**: `~/.hermes/hooks.py` (or venv wrapper at `~/.hermes/bin/hermes-hook`)

### 2. Adapter Pattern (HERMES → Claude Code)

The `hermes adapt claude-code` command generates Claude Code configuration from the canonical `~/.hermes/` directory:

```
~/.hermes/                    ~/.claude/
├── config.toml          →    (reads config)
├── bus.jsonl             →    sync/bus.jsonl (symlink)
├── skills/*.md           →    skills/ (symlinks)
└── rules/*.md            →    rules/ (symlinks)
```

**Key design**: Symlinks, not copies — single source of truth stays in `~/.hermes/`.

Other agents get their own adapter: `hermes adapt cursor` compiles a `.cursorrules` file instead of symlinks. The adapter pattern is agent-agnostic.

### 3. Bus Protocol (Inter-Session Communication)

The HERMES bus (`bus.jsonl`) enables communication between Claude Code sessions, even across different projects:

```jsonl
{"ts":"2026-03-28","src":"hermes","dst":"*","type":"state","msg":"ARC-1122 spec DONE","ttl":7,"ack":[]}
```

- **SYN**: At session start, read bus for pending messages (messages where your namespace is not in `ack[]`)
- **FIN**: At session close, write state changes to bus, ACK consumed messages
- **TTL**: Messages expire after N days — bus is self-cleaning

### 4. Skills as HERMES Nodes

Claude Code skills (`.claude/skills/*.md`) can be HERMES nodes — they read from and write to the bus. Example: the `protocol-architect` skill in the HERMES dimension reads quest dispatches from the bus and writes progress updates.

Skills don't need special HERMES code. They just follow the SYN/FIN protocol naturally as part of their session lifecycle.

### 5. Agent Node Daemon

The `hermes agent start` command runs a persistent daemon that:
- Watches bus.jsonl for changes (kqueue/inotify)
- Dispatches messages to registered agent profiles
- Connects to Hub for real-time cross-clan delivery
- Manages agent lifecycle (7-state FSM)

This runs alongside Claude Code, not inside it.

## Conformance Levels (ARC-1122)

| Level | Name | What it means |
|-------|------|---------------|
| 1 | Bus-Compatible | Can read/write bus.jsonl correctly |
| 2 | Clan-Ready | Sessions, namespaces, gateway, isolation |
| 3 | Network-Ready | Crypto (Ed25519 + ECDHE), integrity, hub connectivity |

Claude Code with HERMES hooks = **Level 2** (Clan-Ready). With daemon + crypto = **Level 3**.

## Key Specs for Claude Code Users

| Spec | What it defines | Why it matters |
|------|----------------|----------------|
| ARC-5322 | Message format (7 fields) | Wire format for bus.jsonl |
| ARC-0793 | SYN/FIN session lifecycle | How sessions start and end |
| ARC-1918 | Namespace isolation | Firewall between dimensions |
| ARC-8446 | Ed25519 + ECDHE encryption | End-to-end crypto for cross-clan |
| ARC-4601 | Agent Node + Hub Mode | Persistent daemon, WebSocket hub |

## CLI Quick Reference

```bash
hermes install          # One-command setup (hooks + config + keys)
hermes status           # Show clan status, bus stats, peers
hermes bus              # Show bus messages
hermes bus --pending    # Show unacked messages
hermes adapt claude-code  # Generate Claude Code config from ~/.hermes/
hermes adapt cursor     # Generate .cursorrules from ~/.hermes/
hermes agent start      # Start persistent daemon
hermes hub start        # Start hub server (for multi-peer routing)
```

## Architecture Relationship

```
Claude Code Session
    ↕ hooks (stdin/stdout JSON)
~/.hermes/ (canonical HERMES config)
    ↕ bus.jsonl (JSONL message bus)
Agent Node Daemon (optional)
    ↕ WebSocket
Hub Server (optional, for real-time multi-clan)
```

HERMES is NOT a Claude Code plugin — it's an independent protocol that integrates with Claude Code through hooks and adapters. The same HERMES installation can also serve Cursor, VS Code, or any future AI assistant.
