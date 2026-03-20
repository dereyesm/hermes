#!/bin/bash
# HERMES in 90 seconds — asciinema recording script
# Usage (from repo root):
#   cd reference/python
#   asciinema rec --command "bash ../../tools/demo-recording.sh" ../../docs/demo/hermes-demo.cast
#
# Requires: venv activated or HERMES_PYTHON set to venv python path
#
# Demonstrates the full HERMES stack:
# 1. One-command install (sovereign, file-based)
# 2. Agent profile registration (ASP F2)
# 3. Message on the bus
# 4. Bus reader + agent list CLI
# 5. Agent validation
# 6. Clan keys (Ed25519 + X25519)
# 7. Status dashboard

set -e

# Resolve python — use venv if available
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="$REPO_ROOT/reference/python/.venv/bin/python"
if [ ! -f "$VENV_PYTHON" ]; then
    VENV_PYTHON="${HERMES_PYTHON:-python3}"
fi
HERMES="$VENV_PYTHON -m hermes"
PY="$VENV_PYTHON"
DEMO_DIR=$(mktemp -d)/hermes-demo

# Typing effect
type_cmd() {
    echo ""
    echo -n "$ "
    for (( i=0; i<${#1}; i++ )); do
        echo -n "${1:$i:1}"
        sleep 0.03
    done
    echo ""
    sleep 0.3
    eval "$1"
    sleep 1
}

section() {
    echo ""
    echo "  $1"
    sleep 0.8
}

clear
echo ""
echo "  ┌─────────────────────────────────────────────┐"
echo "  │  HERMES — Inter-Agent Communication         │"
echo "  │  Protocol in 90 seconds                     │"
echo "  │                                             │"
echo "  │  v0.4.2-alpha · 865 tests · 19 specs       │"
echo "  │  E2E encrypted · file-based · sovereign     │"
echo "  └─────────────────────────────────────────────┘"
echo ""
sleep 2

# --- Step 1: Install ---
section "# 1. One-command sovereign install"
type_cmd "$HERMES install --clan-id demo-clan --display-name 'Demo Clan' --dir $DEMO_DIR --skip-service --skip-hooks"

sleep 0.5

# --- Step 2: Register an agent profile ---
section "# 2. Register an AI agent (ASP — ARC-0369)"

mkdir -p "$DEMO_DIR/agents"
cat > "$DEMO_DIR/agents/mail-scanner.json" << 'PROFILE'
{
  "agent_id": "mail-scanner",
  "display_name": "Email Scanner",
  "version": "1.0.0",
  "role": "sensor",
  "description": "Scans inbox periodically and writes summaries to bus.",
  "capabilities": ["email-scan", "inbox-summarize"],
  "dispatch_rules": [
    {
      "rule_id": "scheduled-scan",
      "trigger": {"type": "scheduled", "cron": "0 */4 * * *"},
      "approval_required": false
    }
  ],
  "resource_limits": {"max_turns": 5, "max_concurrent": 1},
  "enabled": true
}
PROFILE

type_cmd "$HERMES agent list --dir $DEMO_DIR"

sleep 0.5

# --- Step 3: Write a message to the bus ---
section "# 3. Write a dispatch message to the bus"
type_cmd "$PY -c \"
from hermes.message import create_message
from hermes.bus import write_message
msg = create_message(
    src='engineering', dst='ops',
    type='dispatch', msg='REPORT:Build green. 865 tests. 0 regressions.'
)
write_message('$DEMO_DIR/bus.jsonl', msg)
print('Dispatch written to bus.')
\""

sleep 0.5

# --- Step 4: Read the bus ---
section "# 4. Read pending messages"
type_cmd "$HERMES bus --dir $DEMO_DIR"

sleep 0.5

# --- Step 5: Validate agent profiles ---
section "# 5. Validate all agent profiles"
type_cmd "$HERMES agent validate --dir $DEMO_DIR"

sleep 0.5

# --- Step 6: Show clan keys ---
section "# 6. Your clan keys (Ed25519 + X25519)"
type_cmd "cat $DEMO_DIR/.keys/demo-clan.pub | $PY -m json.tool"

sleep 0.5

# --- Step 7: Status ---
section "# 7. Status dashboard"
type_cmd "$HERMES status --dir $DEMO_DIR"

# Cleanup
rm -rf "$(dirname $DEMO_DIR)"

echo ""
echo "  ┌─────────────────────────────────────────────┐"
echo "  │  90 seconds. Sovereign. Encrypted.          │"
echo "  │  No cloud. No vendor lock-in. Just files.   │"
echo "  │                                             │"
echo "  │  github.com/dereyesm/hermes                 │"
echo "  └─────────────────────────────────────────────┘"
echo ""
sleep 3
