#!/usr/bin/env bash
#
# init_amaru.sh — Bootstrap a Amaru instance
#
# Creates the directory structure, bus files, routing table, and namespace
# configs needed to run Amaru. Safe to re-run (won't overwrite existing files).
#
# Usage:
#   bash scripts/init_amaru.sh                          # default namespaces
#   bash scripts/init_amaru.sh sales engineering ops    # custom namespaces
#   AMARU_HOME=/path/to/dir bash scripts/init_amaru.sh # custom location
#

set -euo pipefail

AMARU_HOME="${AMARU_HOME:-$HOME/.amaru}"
DEFAULT_NAMESPACES=("controller" "engineering" "operations" "finance")
NAMESPACES=("${@:-${DEFAULT_NAMESPACES[@]}}")

echo "=== Amaru Init ==="
echo "Location: $AMARU_HOME"
echo "Namespaces: ${NAMESPACES[*]}"
echo ""

# --- Create base directory ---
mkdir -p "$AMARU_HOME"

# --- Create bus files (don't overwrite) ---
for f in bus.jsonl bus-archive.jsonl; do
    if [ ! -f "$AMARU_HOME/$f" ]; then
        touch "$AMARU_HOME/$f"
        echo "Created: $f"
    else
        echo "Exists:  $f (skipped)"
    fi
done

# --- Create routing table ---
ROUTES="$AMARU_HOME/routes.md"
if [ ! -f "$ROUTES" ]; then
    {
        echo "# Routing Table"
        echo ""
        echo "## Namespace -> Files"
        echo ""
        echo "| Namespace | Config | Memory | Agents |"
        echo "|-----------|--------|--------|--------|"
        for ns in "${NAMESPACES[@]}"; do
            echo "| $ns | $AMARU_HOME/$ns/config.md | $AMARU_HOME/$ns/memory/ | $AMARU_HOME/$ns/agents/ |"
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
    mkdir -p "$AMARU_HOME/$ns"/{memory,agents}

    CONFIG="$AMARU_HOME/$ns/config.md"
    if [ ! -f "$CONFIG" ]; then
        cat > "$CONFIG" << EOF
# $ns — Namespace Configuration

## SYNC HEADER
<!-- Amaru Protocol — do not edit manually -->
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
if [ ! -s "$AMARU_HOME/bus.jsonl" ]; then
    TODAY=$(date +%Y-%m-%d)
    echo "{\"ts\":\"$TODAY\",\"src\":\"controller\",\"dst\":\"*\",\"type\":\"event\",\"msg\":\"amaru_instance_initialized. welcome_to_the_network\",\"ttl\":7,\"ack\":[]}" >> "$AMARU_HOME/bus.jsonl"
    echo "Seeded:  welcome message in bus.jsonl"
fi

echo ""
echo "=== Amaru Ready ==="
echo ""
echo "Next steps:"
echo "  1. Edit $AMARU_HOME/routes.md — fill in your agents and tools"
echo "  2. Edit each namespace's config.md — add agents and rules"
echo "  3. Install the Python reference: cd reference/python && pip install -e ."
echo "  4. Run the example agent: python examples/simple_agent.py engineering"
echo "  5. Check the bus: cat $AMARU_HOME/bus.jsonl | python -m json.tool"
