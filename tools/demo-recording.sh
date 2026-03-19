#!/bin/bash
# HERMES in 60 seconds — asciinema recording script
# Usage: asciinema rec --command "bash tools/demo-recording.sh" hermes-demo.cast
#
# This script demonstrates:
# 1. hermes install (one-command setup)
# 2. Writing a sealed message to the bus
# 3. Reading pending messages
# 4. hermes status

set -e
DEMO_DIR=$(mktemp -d)/hermes-demo

# Typing effect
type_cmd() {
    echo ""
    echo -n "❯ "
    for (( i=0; i<${#1}; i++ )); do
        echo -n "${1:$i:1}"
        sleep 0.04
    done
    echo ""
    sleep 0.3
    eval "$1"
    sleep 1
}

clear
echo ""
echo "  ┌─────────────────────────────────────────┐"
echo "  │  HERMES — Inter-Agent Communication     │"
echo "  │  Protocol in 60 seconds                 │"
echo "  └─────────────────────────────────────────┘"
echo ""
sleep 2

# Step 1: Install
type_cmd "hermes install --clan-id demo-clan --display-name 'Demo Clan' --dir $DEMO_DIR --skip-service --skip-hooks"

sleep 1

# Step 2: Check status
type_cmd "hermes status --dir $DEMO_DIR"

sleep 1

# Step 3: Write a message to the bus
echo ""
echo "  # Write a message to the bus"
sleep 0.5
type_cmd "python3 -c \"
from hermes.message import create_message
from hermes.bus import write_message
msg = create_message(src='engineering', dst='ops', type='state', msg='Build green. 605 tests passing.')
write_message('$DEMO_DIR/bus.jsonl', msg)
print('Message written to bus.')
\""

sleep 1

# Step 4: Read the bus
type_cmd "hermes bus --dir $DEMO_DIR"

sleep 1

# Step 5: Show fingerprint
echo ""
echo "  # Your clan keys (Ed25519 + X25519)"
sleep 0.5
type_cmd "cat $DEMO_DIR/.keys/demo-clan.pub | python3 -m json.tool"

sleep 1

# Cleanup
rm -rf "$(dirname $DEMO_DIR)"

echo ""
echo "  ┌─────────────────────────────────────────┐"
echo "  │  30 seconds. Sovereign. Encrypted.      │"
echo "  │  github.com/dereyesm/hermes             │"
echo "  └─────────────────────────────────────────┘"
echo ""
sleep 3
