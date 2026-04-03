# S2S Federation Onboarding — JEI Hub

> Quick-start guide for JEI to enable hub-to-hub federation with DANI Hub.
> After this, messages between clans route automatically across hubs.

## Prerequisites

- JEI hub running (quest005_hub.py or hermes hub start)
- Ed25519 keys generated (`~/.hermes/keys/jei.key` + `jei.pub`)
- DANI hub reachable at `192.168.68.100:8443`

## Step 1: Pull latest HERMES code

```bash
cd ~/path-to-hermes
git pull origin main
```

The `hub.py` now includes `FederationTable`, `FederationLink`, and S2S routing in `MessageRouter`.

## Step 2: Create federation-peers.json

Create `~/.hermes/federation-peers.json` (or wherever your hub dir is):

```json
{
  "hubs": {
    "dani-hub": {
      "ws_uri": "ws://192.168.68.100:8443",
      "sign_pub": "85a940d9b5a2f084c660087c7377a07fa8128758a48bd6b55016fd32f7cffe5f",
      "peers": ["momoshod"],
      "auto_connect": true
    }
  },
  "self": {
    "hub_id": "jei-hub",
    "sign_pub": "b05d85e59a6dee74aaded152d49b19e971e79bb9227b3a1382aaab2a69277a0c",
    "key_file": "~/.hermes/keys/jei.key"
  }
}
```

## Step 3: Register DANI hub in hub-peers.json

Your `hub-peers.json` needs an entry for `dani-hub` so the AuthHandler can verify the S2S HELLO:

```json
{
  "peers": {
    "jei": {
      "sign_pub": "b05d85e59a6dee74aaded152d49b19e971e79bb9227b3a1382aaab2a69277a0c",
      "display_name": "Clan JEI"
    },
    "dani-hub": {
      "sign_pub": "85a940d9b5a2f084c660087c7377a07fa8128758a48bd6b55016fd32f7cffe5f",
      "display_name": "DANI Hub (S2S)"
    }
  }
}
```

## Step 4: Start JEI hub with HERMES hub.py

If JEI is using the custom `quest005_hub.py`, it needs to be updated to support S2S. The simplest path: use the reference `hermes hub start`:

```bash
cd ~/path-to-hermes
reference/python/.venv/bin/python3 -m hermes hub start --dir ~/.hermes --foreground
```

Or if using quest005_hub.py, the minimum changes needed are:

1. Accept `role: "hub"` in HELLO frames
2. When `dst` is not a local peer, forward to the S2S link instead of dropping
3. Handle `s2s_presence` frames

## Step 5: Verify S2S link

Once both hubs are running with federation config:

1. DANI hub auto-connects to JEI hub (outbound S2S)
2. JEI hub auto-connects to DANI hub (outbound S2S)
3. Check logs for: `S2S connected to dani-hub` / `S2S hub connected: dani-hub`

## Step 6: Test bilateral messaging

From DANI's Claude Code (via hub-p2p MCP or direct):
```
hub_send --dst jei --message "Hello from DANI via S2S!"
```

JEI should receive the message on her hub, routed through the S2S link.

From JEI's Claude Code:
```
hub_send --dst momoshod --message "Hello from JEI via S2S!"
```

DANI should receive it on their hub.

## Architecture

```
DANI Hub (:8443)                        JEI Hub (:8443)
├── momoshod (local peer)               ├── jei (local peer)
├── [S2S outbound] ──── ws ───────────► ├── [S2S inbound]
│                                        │
│   ◄──── ws ─────────────────────────── ├── [S2S outbound]
├── [S2S inbound]                        │
```

## How S2S routing works

1. momoshod sends `{"dst": "jei", "msg": "..."}` to DANI Hub
2. DANI Hub MessageRouter checks: "jei" not in local ConnectionTable
3. FederationTable lookup: "jei" → "jei-hub" → S2S link
4. Frame forwarded over S2S WebSocket to JEI Hub
5. JEI Hub routes to jei (local peer)
6. E2E passthrough: the `msg` field is never touched by either hub

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "unknown hub" in auth | Add the remote hub to `hub-peers.json` with its `sign_pub` |
| S2S link keeps reconnecting | Check `ws_uri` in federation-peers.json — must be reachable |
| Messages not routing | Verify `peers` list in federation config includes the target clan_id |
| Auth failure | Verify `sign_pub` matches the remote hub's actual Ed25519 public key |

## Key files

| File | Purpose |
|------|---------|
| `federation-peers.json` | S2S hub configuration (which hubs to connect to) |
| `hub-peers.json` | Peer + hub auth registry (Ed25519 public keys) |
| `hub.py` | Reference hub implementation with S2S support |
| `wire-protocol-hub.md` | Wire protocol documentation |
