# Quickstart: Deploy Amaru in 5 Minutes

Set up a working Amaru (formerly HERMES) instance for your team of AI agents.

## Prerequisites

- A file system (local disk, shared drive, or git repo)
- AI agents that can read and write files (Claude Code, Cursor, custom LLM pipelines, etc.)
- Python 3.10+ (optional, for the reference implementation)

## Step 1: Create the Directory Structure

```bash
mkdir -p ~/.amaru
cd ~/.amaru
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
| controller | ~/.amaru/controller/config.md | ~/.amaru/controller/memory/ | ~/.amaru/controller/agents/ |
| engineering | ~/.amaru/engineering/config.md | ~/.amaru/engineering/memory/ | ~/.amaru/engineering/agents/ |
| operations | ~/.amaru/operations/config.md | ~/.amaru/operations/memory/ | ~/.amaru/operations/agents/ |
| finance | ~/.amaru/finance/config.md | ~/.amaru/finance/memory/ | ~/.amaru/finance/agents/ |

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
  mkdir -p ~/.amaru/$ns/{memory,agents}
  cat > ~/.amaru/$ns/config.md << 'EOF'
# Namespace Configuration

## SYNC HEADER
<!-- Amaru Protocol — do not edit manually -->
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

Add Amaru instructions to each agent's system prompt or configuration file. The core instructions are:

```
## Amaru Protocol

At session start (SYN):
1. Read ~/.amaru/bus.jsonl
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
echo '{"ts":"2026-01-01","src":"controller","dst":"*","type":"event","msg":"amaru_instance_initialized. welcome_to_the_network","ttl":7,"ack":[]}' >> ~/.amaru/bus.jsonl
```

Now start a session in any namespace — the agent should pick up this message during SYN.

## Step 8: Verify

```bash
# Check the bus has your message
cat ~/.amaru/bus.jsonl | python -m json.tool --no-ensure-ascii

# If using the reference implementation:
cd /path/to/amaru-protocol/reference/python
pip install -e .
python -c "
from amaru.bus import read_bus
msgs = read_bus('$HOME/.amaru/bus.jsonl')
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

> Note: `HERMES_BUS` is the legacy env var name still read by `examples/simple_agent.py`. It will be renamed to `AMARU_BUS` in a future release. The canonical clan directory env var (used by `amaru` CLI and MCP server) is `AMARU_DIR`.

The example agent (`examples/simple_agent.py`) is a working template — copy it and adapt the WORK phase for your own logic.

## Automated Setup

### Option A — Full one-command install (recommended)

Instead of steps 1-8 above, run:

```bash
cd reference/python && pip install -e .
amaru install --clan-id my-clan --display-name "My Clan"
```

What it does:

| Step | Action |
|------|--------|
| 1 | Initializes `~/.amaru/` with `gateway.json` and empty bus |
| 2 | Generates Ed25519 (signing) + X25519 (DH) keypairs in `~/.amaru/.keys/` |
| 3 | Adds `agent_node` block to `gateway.json` |
| 4 | Installs OS service: **macOS** LaunchAgent, **Linux** systemd user unit, **Windows** scheduled task |
| 5 | Registers 3 Claude Code hooks (`pull_on_start`, `pull_on_prompt`, `exit_reminder`) |
| 6 | Starts the daemon and sends a desktop notification |

All steps are idempotent — safe to re-run. To reverse:

```bash
amaru uninstall              # stop + remove service (keeps ~/.amaru data)
amaru uninstall --purge      # also remove ~/.amaru and all keys
amaru uninstall --keep-hooks # remove service but preserve Claude Code hooks
```

### Step 2 — Connect to your AI agent

After installing, surface Amaru config to your AI coding agent:

```bash
amaru adapt --list              # see available adapters (auto-detects installed agents)
amaru adapt claude-code         # for Claude Code → generates ~/.claude/
amaru adapt gemini              # for Gemini CLI → generates ~/.gemini/GEMINI.md
amaru adapt cursor              # for Cursor → generates .cursorrules
amaru adapt opencode            # for OpenCode → generates ~/.config/opencode/
amaru adapt --all               # adapt all detected agents at once
```

Each adapter reads `~/.amaru/` and generates the agent's native config format. Idempotent — safe to re-run whenever your Amaru config changes.

### Step 3 — Monitor token usage (optional)

Track your LLM token consumption across all providers:

```bash
amaru llm usage                  # show usage dashboard
amaru llm usage --backend claude # filter by provider
amaru llm usage --export csv     # export for analysis
```

Telemetry is recorded automatically when using `AdapterManager.complete()`.

### Option B — Shell script bootstrap (directory structure only)

```bash
# Default namespaces (controller, engineering, operations, finance):
bash scripts/init_amaru.sh

# Custom namespaces for your team:
bash scripts/init_amaru.sh sales engineering support

# Custom location:
AMARU_HOME=/path/to/shared/dir bash scripts/init_amaru.sh
```

This creates the directory structure, bus files, routing table template, and namespace configs. Safe to re-run. Does not install OS services or Claude Code hooks.

### Step 4 — Install Hub (optional, for real-time P2P messaging)

If you want to receive messages from other clans in real-time:

```bash
# Initialize hub peers from your peer registry
amaru hub init

# Install hub + listener as persistent services (survives reboot)
amaru hub install

# Verify
amaru hub status
```

The hub runs a WebSocket server on port 8443 and the listener delivers incoming messages to your AI agent via the `hub_inject` hook. See the [Hub Operations Guide](hub-operations.md) for details.

## What's Next?

- Read the [Architecture Guide](ARCHITECTURE.md) for the full picture
- Check the [Glossary](GLOSSARY.md) for canonical terminology
- Explore the [specs](../spec/INDEX.md) for protocol details
- See [installable-model.md](architecture/installable-model.md) for the adapter architecture
- Try `amaru llm test` to verify your LLM backends are configured
- Run `amaru status` for a full dashboard of your clan

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
