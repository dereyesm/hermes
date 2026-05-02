#!/usr/bin/env python3
"""
Amaru Simple Agent Example
==========================

A minimal agent that demonstrates the full Amaru session lifecycle:
  SYN (read pending messages) -> WORK (do something) -> FIN (write state + ACK)

Usage:
    # First, set up Amaru (if you haven't already):
    #   bash scripts/init_amaru.sh
    #
    # Then install the reference implementation:
    #   cd reference/python && pip install -e . && cd ../..
    #
    # Run this agent as the "engineering" namespace:
    python examples/simple_agent.py

    # Run as a different namespace:
    python examples/simple_agent.py finance

    # Use a custom bus path:
    AMARU_BUS=./my-bus.jsonl python examples/simple_agent.py
"""

import sys
import os
import warnings
from pathlib import Path

from amaru.sync import syn, syn_report, fin, FinAction
from amaru.bus import ack_message

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

# Which namespace is this agent? Default: "engineering"
NAMESPACE = sys.argv[1] if len(sys.argv) > 1 else "engineering"


def _resolve_bus_path() -> Path:
    """Resolve bus path with backward-compat for legacy HERMES_BUS env var."""
    if "AMARU_BUS" in os.environ:
        return Path(os.environ["AMARU_BUS"])
    if "HERMES_BUS" in os.environ:
        warnings.warn(
            "HERMES_BUS env var is deprecated; use AMARU_BUS instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return Path(os.environ["HERMES_BUS"])
    return Path.home() / ".amaru" / "bus.jsonl"


# Where is the bus? Default: ~/.amaru/bus.jsonl
BUS = _resolve_bus_path()


def main():
    print(f"=== Amaru Agent [{NAMESPACE}] ===\n")

    # ------------------------------------------------------------------
    # PHASE 1: SYN — Read the bus, find messages for this namespace
    # ------------------------------------------------------------------
    print("--- SYN (session start) ---")

    if not BUS.exists():
        print(f"Bus not found at {BUS}. Run 'bash scripts/init_amaru.sh' first.")
        sys.exit(1)

    result = syn(BUS, NAMESPACE)
    print(syn_report(result, NAMESPACE))

    # ------------------------------------------------------------------
    # PHASE 2: WORK — Process pending messages + do your job
    # ------------------------------------------------------------------
    print("\n--- WORK ---")

    if not result.pending:
        print("No pending messages. Nothing to process.")
    else:
        for msg in result.pending:
            print(f"  Processing: [{msg.src} -> {msg.dst}] ({msg.type}) {msg.msg}")
            # Here you would route each message to the appropriate handler.
            # Example:
            #   if msg.type == "dispatch":
            #       handle_dispatch(msg)
            #   elif msg.type == "alert":
            #       handle_alert(msg)

    # Simulate work output — replace this with your agent's real logic
    work_summary = f"{NAMESPACE}_session_complete. processed_{len(result.pending)}_messages"
    print(f"  Result: {work_summary}")

    # ------------------------------------------------------------------
    # PHASE 3: FIN — Write state to bus + ACK consumed messages
    # ------------------------------------------------------------------
    print("\n--- FIN (session end) ---")

    # 3a. Write your state change to the bus
    actions = [
        FinAction(
            dst="*",
            type="state",
            msg=work_summary,
            ttl=7,
        ),
    ]
    written = fin(BUS, NAMESPACE, actions)
    print(f"  Wrote {len(written)} message(s) to bus.")

    # 3b. ACK all messages that were addressed to this namespace
    if result.pending:
        acked = ack_message(
            BUS,
            NAMESPACE,
            lambda m: m.dst in (NAMESPACE, "*") and NAMESPACE not in m.ack,
        )
        print(f"  ACKed {acked} message(s).")

    print(f"\n=== Agent [{NAMESPACE}] session complete ===")


if __name__ == "__main__":
    main()
