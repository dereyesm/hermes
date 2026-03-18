# Quickstart: Deploy HERMES in 5 Minutes

Set up a working HERMES instance for your team of AI agents.

## Prerequisites

- A file system (local disk, shared drive, or git repo)
- AI agents that can read and write files (Claude Code, Cursor, custom LLM pipelines, etc.)
- Python 3.10+ (optional, for the reference implementation)

## Step 1: Create the Directory Structure

```bash
mkdir -p ~/.hermes
cd ~/.hermes
```

## Step 2: Create the Bus

```bash
touch bus.jsonl
touch bus-archive.jsonl
```

The bus starts empty. Messages will accumulate as agents communicate.

## Step 3: Define Your Namespaces

Decide how to partition your work. Each namespace is an isolated workspace. Example:

| Namespace | Purpose | Agents |
|-----------|---------|--------|
| `engineering` | Code, PRs, deployments | lead-dev, reviewer, devops |
| `operations` | Project management, scheduling | pm, coordinator |
| `finance` | Budgets, expenses, invoicing | accountant, auditor |
| `controller` | Read-only oversight | router |

## Step 4: Create the Routing Table

Create `routes.md`:

```markdown
# Routing Table

## Namespace → Files

| Namespace | Config | Memory | Agents |
|-----------|--------|--------|--------|
| controller | ~/.hermes/controller/config.md | ~/.hermes/controller/memory/ | ~/.hermes/controller/agents/ |
| engineering | ~/.hermes/engineering/config.md | ~/.hermes/engineering/memory/ | ~/.hermes/engineering/agents/ |
| operations | ~/.hermes/operations/config.md | ~/.hermes/operations/memory/ | ~/.hermes/operations/agents/ |
| finance | ~/.hermes/finance/config.md | ~/.hermes/finance/memory/ | ~/.hermes/finance/agents/ |

## Namespace → Tools

| Namespace | Head Agent | Allowed Tools | Account |
|-----------|-----------|---------------|---------|
| controller | router | NONE (read-only) | — |
| engineering | lead-dev | github, jira | eng@company.com |
| operations | pm | calendar, jira | ops@company.com |
| finance | accountant | sheets, banking | fin@company.com |

## Permitted Data Crosses

| Source | Destination | Type | Example |
|--------|-------------|------|---------|
| engineering | finance | data_cross | Project costs as "Engineering" category |
| operations | finance | data_cross | Vendor invoices as "Operations" category |
```

## Step 5: Create Namespace Directories

```bash
for ns in controller engineering operations finance; do
  mkdir -p ~/.hermes/$ns/{memory,agents}
  cat > ~/.hermes/$ns/config.md << 'EOF'
# Namespace Configuration

## SYNC HEADER
<!-- HERMES Protocol — do not edit manually -->
| Field | Value |
|-------|-------|
| version | 1 |
| last_sync | — |
| state | initialized |
| pending_out | 0 |
| pending_in | 0 |
EOF
done
```

## Step 6: Instruct Your Agents

Add HERMES instructions to each agent's system prompt or configuration file. The core instructions are:

```
## HERMES Protocol

At session start (SYN):
1. Read ~/.hermes/bus.jsonl
2. Filter messages where dst = [your-namespace] OR dst = "*"
   AND [your-namespace] NOT IN ack array
3. Report any pending messages
4. Flag messages unACKed for >3 days

At session end (FIN):
1. If state changed → append message to bus.jsonl
2. Update SYNC HEADER in config.md (increment version)
3. ACK consumed messages (add namespace to ack array)

Message format (one JSON object per line):
{"ts":"YYYY-MM-DD","src":"namespace","dst":"namespace|*","type":"state|alert|event|request|data_cross","msg":"payload max 120 chars","ttl":7,"ack":[]}
```

## Step 7: Send Your First Message

Test the bus by writing a message directly:

```bash
echo '{"ts":"2026-01-01","src":"controller","dst":"*","type":"event","msg":"hermes_instance_initialized. welcome_to_the_network","ttl":7,"ack":[]}' >> ~/.hermes/bus.jsonl
```

Now start a session in any namespace — the agent should pick up this message during SYN.

## Step 8: Verify

```bash
# Check the bus has your message
cat ~/.hermes/bus.jsonl | python -m json.tool --no-ensure-ascii

# If using the reference implementation:
cd /path/to/hermes/reference/python
pip install -e .
python -c "
from hermes.bus import read_bus
msgs = read_bus('$HOME/.hermes/bus.jsonl')
for m in msgs:
    print(f'[{m.src} → {m.dst}] {m.msg}')
"
```

## Step 9: Run the Example Agent

Try the included example agent to see a full SYN -> WORK -> FIN cycle:

```bash
# From the repo root:
cd reference/python && pip install -e . && cd ../..

# Run as "engineering" namespace against the sample bus:
HERMES_BUS=examples/bus-sample.jsonl python examples/simple_agent.py engineering

# Run as your own namespace against your real bus:
python examples/simple_agent.py [your-namespace]
```

The example agent (`examples/simple_agent.py`) is a working template — copy it and adapt the WORK phase for your own logic.

## Automated Setup

### Option A — Full one-command install (recommended)

Instead of steps 1-8 above, run:

```bash
cd reference/python && pip install -e .
hermes install --clan-id my-clan --display-name "My Clan"
```

What it does:

| Step | Action |
|------|--------|
| 1 | Initializes `~/.hermes/` with `gateway.json` and empty bus |
| 2 | Generates Ed25519 (signing) + X25519 (DH) keypairs in `~/.hermes/.keys/` |
| 3 | Adds `agent_node` block to `gateway.json` |
| 4 | Installs OS service: **macOS** LaunchAgent, **Linux** systemd user unit, **Windows** scheduled task |
| 5 | Registers 3 Claude Code hooks (`pull_on_start`, `pull_on_prompt`, `exit_reminder`) |
| 6 | Starts the daemon and sends a desktop notification |

All steps are idempotent — safe to re-run. To reverse:

```bash
hermes uninstall              # stop + remove service (keeps ~/.hermes data)
hermes uninstall --purge      # also remove ~/.hermes and all keys
hermes uninstall --keep-hooks # remove service but preserve Claude Code hooks
```

### Option B — Shell script bootstrap (directory structure only)

```bash
# Default namespaces (controller, engineering, operations, finance):
bash scripts/init_hermes.sh

# Custom namespaces for your team:
bash scripts/init_hermes.sh sales engineering support

# Custom location:
HERMES_HOME=/path/to/shared/dir bash scripts/init_hermes.sh
```

This creates the directory structure, bus files, routing table template, and namespace configs. Safe to re-run. Does not install OS services or Claude Code hooks.

## What's Next?

- Read the [Architecture Guide](ARCHITECTURE.md) for the full picture
- Check the [Glossary](GLOSSARY.md) for canonical terminology
- Explore the [specs](../spec/INDEX.md) for protocol details
- Set up a controller agent with `/router` capabilities for cross-namespace coordination

## Common Patterns

### Financial Reporting
```
engineering ──data_cross──► finance    (project costs)
operations  ──data_cross──► finance    (vendor invoices)
finance     ──state──────► *           (monthly report)
```

### Sprint Coordination
```
operations  ──dispatch───► engineering (sprint tasks)
engineering ──state──────► operations  (progress updates)
engineering ──alert──────► operations  (blockers)
```

### Incident Response
```
engineering ──alert──────► *           (system down)
controller  ──dispatch───► engineering (assign on-call)
engineering ──event──────► *           (resolved)
```
