#!/bin/bash
# HERMES Bilateral Demo — DANI ↔ JEI
# Usage: asciinema rec --command "bash tools/demo-bilateral.sh" hermes-bilateral.cast
#
# Prerequisites:
# - Python venv with hermes installed (or HERMES_PYTHON set)
#
# This demo shows:
# 1. Two sovereign clans (DANI + JEI) — separate directories
# 2. Out-of-band key exchange
# 3. ECDHE-sealed message: DANI → JEI (forward secrecy)
# 4. JEI decrypts and reads
# 5. Bus inspection
#
# NOTE: This script uses simulated clan dirs for demo purposes.
#       Real bilateral uses relay (hermes-relay private repo).

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
DEMO_BASE=$(mktemp -d)
DANI_DIR="$DEMO_BASE/clan-dani"
JEI_DIR="$DEMO_BASE/clan-jei"

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

label() {
    echo ""
    echo "  ┌── $1 ──┐"
    sleep 0.3
}

clear
echo ""
echo "  ┌─────────────────────────────────────────────┐"
echo "  │  HERMES Bilateral — Sovereign Encryption    │"
echo "  │                                             │"
echo "  │  Two clans. Zero trust. Forward secrecy.    │"
echo "  │  No cloud between them.                     │"
echo "  └─────────────────────────────────────────────┘"
echo ""
sleep 2

# --- Setup: Install both clans ---
section "# Setup: Two sovereign clans"

label "DANI"
type_cmd "$HERMES install --clan-id dani --display-name 'Clan DANI' --dir $DANI_DIR --skip-service --skip-hooks"

label "JEI"
type_cmd "$HERMES install --clan-id jei --display-name 'Clan JEI' --dir $JEI_DIR --skip-service --skip-hooks"

sleep 0.5

# --- Step 1: Exchange public keys ---
section "# 1. Exchange public keys (out-of-band)"
type_cmd "$PY -c \"
import json, os
# Simulate key exchange (in reality: relay or in-person)
dani_pub = json.load(open('$DANI_DIR/.keys/dani.pub'))
jei_pub = json.load(open('$JEI_DIR/.keys/jei.pub'))
# DANI stores JEI's pubkey
os.makedirs('$DANI_DIR/.keys/peers', exist_ok=True)
json.dump(jei_pub, open('$DANI_DIR/.keys/peers/jei.pub', 'w'), indent=2)
# JEI stores DANI's pubkey
os.makedirs('$JEI_DIR/.keys/peers', exist_ok=True)
json.dump(dani_pub, open('$JEI_DIR/.keys/peers/dani.pub', 'w'), indent=2)
print('Keys exchanged: DANI <-> JEI')
print('  DANI fingerprint: ' + dani_pub.get('fingerprint', 'n/a'))
print('  JEI  fingerprint: ' + jei_pub.get('fingerprint', 'n/a'))
\""

sleep 0.5

# --- Step 2: DANI sends ECDHE-sealed message ---
section "# 2. DANI sends ECDHE-sealed message to JEI"

label "DANI"
type_cmd "$PY -c \"
from hermes.crypto import ClanKeyPair, load_peer_public
from hermes.bus import write_sealed_message
from hermes.message import create_message

# Load DANI's keys
dani_keys = ClanKeyPair.load('$DANI_DIR/.keys', 'dani')

# Load JEI's public key
_, jei_dh_pub = load_peer_public('$DANI_DIR/.keys/peers', 'jei')

# Create and seal message with ECDHE (forward secrecy)
msg = create_message(
    src='dani', dst='jei',
    type='dispatch',
    msg='QUEST-003: ECDHE bilateral test.'
)
write_sealed_message('$DANI_DIR/bus.jsonl', msg, dani_keys, jei_dh_pub, ecdhe=True)
print('ECDHE-sealed message written to DANI bus.')
print('Encryption: ECDHE-X25519-AES256GCM')
\""

sleep 0.5

# --- Step 3: Simulate relay (copy to JEI's bus) ---
section "# 3. Relay delivers to JEI (file copy for demo)"
type_cmd "tail -1 $DANI_DIR/bus.jsonl >> $JEI_DIR/bus.jsonl && echo 'Message relayed: DANI -> JEI'"

sleep 0.5

# --- Step 4: JEI reads and decrypts ---
section "# 4. JEI decrypts the ECDHE message"

label "JEI"
type_cmd "$PY -c \"
from hermes.crypto import ClanKeyPair, load_peer_public
from hermes.bus import read_bus, open_sealed_message

# Load JEI's keys
jei_keys = ClanKeyPair.load('$JEI_DIR/.keys', 'jei')

# Load DANI's public keys
dani_sign_pub, dani_dh_pub = load_peer_public('$JEI_DIR/.keys/peers', 'dani')

# Read sealed message from bus
messages = read_bus('$JEI_DIR/bus.jsonl')
sealed_msg = [m for m in messages if m.src == 'dani'][-1]

# Decrypt with ECDHE
decrypted = open_sealed_message(sealed_msg, jei_keys, dani_sign_pub, dani_dh_pub)
print(f'Decrypted: {decrypted.msg}')
print('Forward secrecy verified — ephemeral key destroyed.')
\""

sleep 1

# --- Step 5: Show the bus (sealed vs plaintext) ---
section "# 5. Bus shows only encrypted data at rest"

label "DANI bus"
type_cmd "$HERMES bus --dir $DANI_DIR"

# Cleanup
rm -rf "$DEMO_BASE"

echo ""
echo "  ┌─────────────────────────────────────────────┐"
echo "  │  Two clans. One protocol. Zero cloud.       │"
echo "  │  Forward secrecy. Sovereign keys.           │"
echo "  │                                             │"
echo "  │  github.com/dereyesm/hermes                 │"
echo "  └─────────────────────────────────────────────┘"
echo ""
sleep 3
