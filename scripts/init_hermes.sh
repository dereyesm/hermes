#!/usr/bin/env bash
#
# init_hermes.sh — Bootstrap a HERMES instance
#
# Creates the directory structure, bus files, routing table, and namespace
# configs needed to run HERMES. Safe to re-run (won't overwrite existing files).
#
# Usage:
#   bash scripts/init_hermes.sh                          # default namespaces
#   bash scripts/init_hermes.sh sales engineering ops    # custom namespaces
#   HERMES_HOME=/path/to/dir bash scripts/init_hermes.sh # custom location
#

set -euo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
DEFAULT_NAMESPACES=("controller" "engineering" "operations" "finance")
NAMESPACES=("${@:-${DEFAULT_NAMESPACES[@]}}")

echo "=== HERMES Init ==="
echo "Location: $HERMES_HOME"
echo "Namespaces: ${NAMESPACES[*]}"
echo ""

# --- Create base directory ---
mkdir -p "$HERMES_HOME"

# --- Create bus files (don't overwrite) ---
for f in bus.jsonl bus-archive.jsonl; do
    if [ ! -f "$HERMES_HOME/$f" ]; then
        touch "$HERMES_HOME/$f"
        echo "Created: $f"
    else
        echo "Exists:  $f (skipped)"
    fi
done

# --- Create routing table ---
ROUTES="$HERMES_HOME/routes.md"
if [ ! -f "$ROUTES" ]; then
    {
        echo "# Routing Table"
        echo ""
        echo "## Namespace -> Files"
        echo ""
        echo "| Namespace | Config | Memory | Agents |"
        echo "|-----------|--------|--------|--------|"
        for ns in "${NAMESPACES[@]}"; do
            echo "| $ns | $HERMES_HOME/$ns/config.md | $HERMES_HOME/$ns/memory/ | $HERMES_HOME/$ns/agents/ |"
        done
        echo ""
        echo "## Namespace -> Tools"
        echo ""
        echo "| Namespace | Head Agent | Allowed Tools | Account |"
        echo "|-----------|-----------|---------------|---------|"
        for ns in "${NAMESPACES[@]}"; do
            if [ "$ns" = "controller" ]; then
                echo "| $ns | router | NONE (read-only) | — |"
            else
                echo "| $ns | [head-agent] | [tools] | [account] |"
            fi
        done
        echo ""
        echo "## Permitted Data Crosses"
        echo ""
        echo "| Source | Destination | Type | Example |"
        echo "|--------|-------------|------|---------|"
        echo "| [namespace] | [namespace] | data_cross | [description] |"
    } > "$ROUTES"
    echo "Created: routes.md"
else
    echo "Exists:  routes.md (skipped)"
fi

# --- Create namespace directories and configs ---
for ns in "${NAMESPACES[@]}"; do
    mkdir -p "$HERMES_HOME/$ns"/{memory,agents}

    CONFIG="$HERMES_HOME/$ns/config.md"
    if [ ! -f "$CONFIG" ]; then
        cat > "$CONFIG" << EOF
# $ns — Namespace Configuration

## SYNC HEADER
<!-- HERMES Protocol — do not edit manually -->
| Field | Value |
|-------|-------|
| version | 1 |
| last_sync | — |
| state | initialized |
| pending_out | 0 |
| pending_in | 0 |

## Agents

| Agent | Role | Tools |
|-------|------|-------|
| [agent-name] | [role] | [allowed tools] |

## Rules

- [Add namespace-specific rules here]
EOF
        echo "Created: $ns/config.md"
    else
        echo "Exists:  $ns/config.md (skipped)"
    fi
done

# --- Seed welcome message ---
if [ ! -s "$HERMES_HOME/bus.jsonl" ]; then
    TODAY=$(date +%Y-%m-%d)
    echo "{\"ts\":\"$TODAY\",\"src\":\"controller\",\"dst\":\"*\",\"type\":\"event\",\"msg\":\"hermes_instance_initialized. welcome_to_the_network\",\"ttl\":7,\"ack\":[]}" >> "$HERMES_HOME/bus.jsonl"
    echo "Seeded:  welcome message in bus.jsonl"
fi

echo ""
echo "=== HERMES Ready ==="
echo ""
echo "Next steps:"
echo "  1. Edit $HERMES_HOME/routes.md — fill in your agents and tools"
echo "  2. Edit each namespace's config.md — add agents and rules"
echo "  3. Install the Python reference: cd reference/python && pip install -e ."
echo "  4. Run the example agent: python examples/simple_agent.py engineering"
echo "  5. Check the bus: cat $HERMES_HOME/bus.jsonl | python -m json.tool"
