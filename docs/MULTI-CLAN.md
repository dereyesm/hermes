# HERMES Multi-Clan Guide: Your First Connection

> Two clans, one protocol. This guide walks you through setting up your first
> inter-clan HERMES gateway connection.

## Prerequisites

- Python 3.10+
- The `hermes-protocol` package (clone from GitHub)
- Two machines (or two directories simulating two clans)

## Quick Start (5 minutes)

### 1. Initialize Your Clan

```bash
cd ~/my-clan
python -m hermes.cli init my-clan-id "My Clan Name"
```

This creates:
```
my-clan/
  gateway.json          # Gateway configuration
  .keys/
    gateway.key         # Private key (NEVER share)
    gateway.pub         # Public key (shared via Agora)
    peers/              # Peer public keys
    .gitignore          # Protects gateway.key
  .agora/               # Local Agora cache
    profiles/
    inbox/
    attestations/
    quest_log/
```

### 2. Add Your Agents

Edit `gateway.json` to publish agents:

```json
{
  "agents": [
    {
      "internal": {"namespace": "finance", "agent": "auditor"},
      "external": "gold-auditor",
      "published": true,
      "capabilities": ["finance/audit", "finance/tax"]
    }
  ]
}
```

### 3. Publish Your Profile

```bash
python -m hermes.cli publish
```

This writes your public profile to `.agora/profiles/my-clan-id.json`.

### 4. Connect to a Peer

```bash
python -m hermes.cli peer add other-clan-id
```

This:
1. Looks up the peer's profile on the Agora
2. Stores their public key
3. Sends a `hello` message to their Agora inbox
4. Adds them to your `gateway.json` peers list

### 5. Send Your First Message

```bash
python -m hermes.cli send other-clan-id "First Contact achieved!"
```

### 6. Check Your Inbox

```bash
python -m hermes.cli inbox
```

## Two Clans on One Machine (Testing)

For testing, create two clan directories sharing an Agora:

```bash
# Create shared Agora
mkdir -p /tmp/hermes-agora/{profiles,inbox,attestations,quest_log}

# Initialize Clan A
mkdir /tmp/clan-a
cd /tmp/clan-a
python -m hermes.cli init alpha "Clan Alpha"
rm -rf .agora && ln -s /tmp/hermes-agora .agora

# Initialize Clan B
mkdir /tmp/clan-b
cd /tmp/clan-b
python -m hermes.cli init beta "Clan Beta"
rm -rf .agora && ln -s /tmp/hermes-agora .agora

# Clan A publishes
cd /tmp/clan-a && python -m hermes.cli publish

# Clan B publishes
cd /tmp/clan-b && python -m hermes.cli publish

# Clan B peers with A
cd /tmp/clan-b && python -m hermes.cli peer add alpha

# Clan A checks inbox
cd /tmp/clan-a && python -m hermes.cli inbox
# → Shows hello from beta

# Clan A peers with B
cd /tmp/clan-a && python -m hermes.cli peer add beta

# Clan A sends message
cd /tmp/clan-a && python -m hermes.cli send beta "Hello from Alpha!"

# Clan B reads
cd /tmp/clan-b && python -m hermes.cli inbox
# → Shows hello from alpha + message
```

## Two Clans on Separate Machines

For real inter-clan communication, share the Agora via Git:

1. Create a Git repository (e.g., `github.com/your-org/hermes-agora`)
2. Both clans clone it to their `.agora/` directory
3. Publish profiles → commit → push
4. Peer add → reads profile from Git → sends hello via Git
5. Pull periodically to check inbox

```bash
# Replace .agora with the Git repo
cd ~/my-clan
rm -rf .agora
git clone git@github.com:your-org/hermes-agora.git .agora

# After publishing or sending
cd .agora && git add . && git commit -m "Profile update" && git push

# To check inbox
cd .agora && git pull
cd ~/my-clan && python -m hermes.cli inbox
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `hermes init <id> <name>` | Initialize a new clan |
| `hermes status` | Show gateway status |
| `hermes publish` | Publish profile to Agora |
| `hermes peer add <clan-id>` | Add a peer clan |
| `hermes peer list` | List all peers |
| `hermes send <clan-id> <msg>` | Send message to peer |
| `hermes inbox` | Read inbox messages |
| `hermes discover <capability>` | Find agents by capability |

All commands accept `--dir <path>` to specify the clan directory.

## Security Notes

- Your `.keys/gateway.key` is NEVER shared or published
- The outbound filter blocks messages containing internal data (bus.jsonl, registry.json, XP, etc.)
- Inbound messages are rate-limited per source clan
- Phase 2 (May-Jun 2026) will add Ed25519 signatures for message authentication

## Example: Clan Momosho D. + Clan Huitaca (First Contact)

The first two clans on the HERMES network:

```
Clan Momosho D. (Daniel)              Clan Huitaca (Jeimmy)
+-------------------------------+     +-------------------------------+
| bus.jsonl | routes.md         |     | bus.jsonl | routes.md         |
| registry.json (28 skills)    |     | registry.json (N skills)     |
| Dojo (SDN Controller)       |     | Dojo (Controller)            |
| Heraldo (Messenger)         |     | Huitaca (Messenger)          |
| 6 dimensions:               |     | Dimensions:                  |
|   global, nymyka, momoshod,  |     |   (defined by Jeimmy)        |
|   momofinance, zima26, hermes|     |                              |
+-------------+----------------+     +-------------+----------------+
              |                                     |
         [Gateway NAT]                         [Gateway NAT]
         clan: momosho-d                       clan: huitaca
              |                                     |
              +------- Agora Directory -------------+
                       (Git: hermes-agora)
                       +-- profiles/
                       |   +-- momosho-d.json
                       |   +-- huitaca.json
                       +-- inbox/
                       |   +-- momosho-d/
                       |   +-- huitaca/
                       +-- attestations/
                       +-- quest_log/
```

### Key roles per clan

| Role | Clan Momosho D. | Clan Huitaca |
|------|----------------|--------------|
| **Operator** | Daniel | Jeimmy |
| **Dojo** (controller) | El Dojo | (Jeimmy names hers) |
| **Heraldo** (messenger) | Heraldo | Huitaca |
| **Gateway ID** | `momosho-d` | `huitaca` |

Every clan MUST have:
1. A **Dojo** — the skill that hosts and dispatches to other skills
2. A **Heraldo** — the skill that handles inter-clan messaging
3. A **Gateway** — the infrastructure component (NAT + filter)

The names are chosen by each clan's operator. "Dojo" and "Heraldo" are roles,
not fixed names.

## Architecture

```
Your Clan                    Peer Clan
+-----------+                +-----------+
| bus.jsonl |                | bus.jsonl |
| Dojo      |                | Dojo      |
| Skills    |                | Skills    |
+-----+-----+               +-----+-----+
      |                           |
  [Gateway]                   [Gateway]
      |                           |
      +---- Agora Directory ------+
            (Git repo)
            profiles/*.json
            inbox/<clan>/*.json
```

Each clan is sovereign. The gateway is the only boundary component.
Internal names, bus messages, and metrics never leave the clan.

---

*Part of the HERMES project. MIT License.*
