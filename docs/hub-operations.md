# Hub Operations Guide

The Amaru Hub is a WebSocket server that routes encrypted messages between clan peers in real-time. It provides store-and-forward for offline peers and supports S2S (server-to-server) federation between hubs.

This guide covers installation, monitoring, and troubleshooting.

## Prerequisites

1. HERMES installed (`amaru install` or manual `amaru init`)
2. At least one peer registered (`amaru peer invite` / `amaru peer accept`)
3. Hub peers file generated (`amaru hub init`)

## Quick Start (Manual)

```bash
# Start hub server (foreground)
hermes hub start --foreground

# In another terminal: start listener (writes to hub-inbox.jsonl)
hermes hub listen

# Check status
hermes hub status

# List connected peers
hermes hub peers
```

## Persistent Setup (Recommended)

Install the hub and listener as OS services that survive reboots:

```bash
hermes hub install
```

This creates and loads two services:

| Service | Label | What it does |
|---------|-------|-------------|
| Hub server | `com.hermes.hub` | WebSocket server on port 8443, routes messages |
| Hub listener | `com.hermes.hub-listen` | Connects to hub, writes incoming messages to `hub-inbox.jsonl` |

Both services:
- Start automatically on login (`RunAtLoad`)
- Restart on crash (`KeepAlive`)
- Log to `~/.amaru/hub.log` and `~/.amaru/hub-listen.log`

### Verify Installation

```bash
# macOS
launchctl list | grep hermes

# Linux
systemctl --user status hermes-hub hermes-hub-listen

# Cross-platform
hermes hub status
```

### Uninstall

```bash
hermes hub uninstall
```

## Architecture

```
                    ┌──────────────────┐
                    │   Hub Server     │
                    │  (port 8443)     │
                    │                  │
  Peer A ──WS──────│  ConnectionTable  │──────WS── Peer B
  (clan)           │  MessageRouter   │           (clan)
                    │  StoreForward    │
                    │  FederationTable │──S2S──── Remote Hub
                    └──────────────────┘
                            │
                    ┌───────┴────────┐
                    │  Hub Listener  │
                    │  (local client)│
                    │       │        │
                    │  hub-inbox.jsonl│
                    │       │        │
                    │  hub_inject    │
                    │  (Claude Code  │
                    │   hook)        │
                    └────────────────┘
```

**Message flow**: Remote peer sends message via hub -> hub routes to your clan_id -> listener receives it -> writes to `hub-inbox.jsonl` -> `hub_inject` hook reads inbox on next prompt and injects as `systemMessage` in Claude Code.

## Files

| File | Location | Purpose |
|------|----------|---------|
| `hub-state.json` | `~/.amaru/` | Hub PID, uptime, messages routed |
| `hub.lock/pid` | `~/.amaru/` | PID lock (prevents duplicate hubs) |
| `hub-listen.pid` | `~/.amaru/` | Listener PID (daemon mode only) |
| `hub-inbox.jsonl` | `~/.amaru/` | Incoming messages (read by hub_inject hook) |
| `hub-peers.json` | `~/.amaru/` | Registered peers (clan_id -> public key) |
| `federation-peers.json` | `~/.amaru/` | S2S federation links (hub_id -> host:port) |
| `hub.log` | `~/.amaru/` | Hub stdout (when running as service) |
| `hub.err` | `~/.amaru/` | Hub stderr (when running as service) |

## Monitoring

```bash
# Full status (PID, uptime, messages routed, connected peers)
hermes hub status

# Connected peers
hermes hub peers

# Check service health (macOS)
launchctl list com.hermes.hub
launchctl list com.hermes.hub-listen

# View logs
tail -f ~/.amaru/hub.log
tail -f ~/.amaru/hub-listen.log
```

## Federation (S2S)

Hubs can federate with each other for inter-hub routing. See [ARC-4601 §17](../spec/ARC-4601.md) and the [S2S onboarding guide](s2s-onboarding-jei.md).

```bash
# Configure federation peers
cat ~/.amaru/federation-peers.json

# Hub automatically connects to federation peers on startup
hermes hub status  # shows S2S link status
```

## Troubleshooting

### Hub won't start: "Lock file exists"

Another hub instance is running or crashed without cleanup:

```bash
# Check if the old process is alive
cat ~/.amaru/hub.lock/pid
ps -p $(cat ~/.amaru/hub.lock/pid)

# If dead, remove the lock
rm -rf ~/.amaru/hub.lock
hermes hub start --foreground
```

### Listener connects but no messages appear

1. Verify the hub is running: `amaru hub status`
2. Check that the sender uses `payload.dst` wrapper (common bug — see [wire-protocol-hub.md](wire-protocol-hub.md) §3.2)
3. Verify your clan_id matches what the sender is targeting

### Auth failures

```
Auth failed: {"type": "auth_fail", "reason": "..."}
```

- Verify your Ed25519 public key is registered in hub-peers.json
- Ensure you're signing the nonce bytes, not the hex string
- See [wire-protocol-hub.md](wire-protocol-hub.md) §2 for the full auth flow

### Port 8443 already in use

```bash
lsof -i :8443  # find what's using it

# Change hub port in gateway.json:
# [hub]
# listen_port = 8444
```

## Platform Support

| Platform | Hub Server | Hub Listener | Service Manager |
|----------|-----------|-------------|----------------|
| macOS | LaunchAgent | LaunchAgent | `launchctl` |
| Linux | systemd user | systemd user | `systemctl --user` |
| Windows | Manual only | Manual only | — |
