"""HERMES SYN/FIN Protocol — ARC-0793 Reference Implementation.

Session lifecycle management: SYN (session start) and FIN (session end).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .bus import filter_for_namespace, find_stale, find_unresolved, read_bus, write_message
from .message import Message, create_message


@dataclass
class SynResult:
    """Result of a SYN handshake."""

    pending: list[Message]
    stale: list[Message]
    total_bus_messages: int
    unresolved: list[Message] = None

    def __post_init__(self):
        if self.unresolved is None:
            self.unresolved = []


def syn(bus_path: str | Path, namespace: str) -> SynResult:
    """Execute the SYN protocol for a namespace.

    Per ARC-0793:
    1. Read bus
    2. Filter for messages addressed to this namespace
    3. Detect stale messages (unACKed >3 days)

    Returns a SynResult with pending messages and stale warnings.
    """
    messages = read_bus(bus_path)
    pending = filter_for_namespace(messages, namespace)
    stale = find_stale(pending, threshold_days=3)

    unresolved = find_unresolved(messages)

    return SynResult(
        pending=pending,
        stale=stale,
        total_bus_messages=len(messages),
        unresolved=unresolved,
    )


def syn_report(result: SynResult, namespace: str) -> str:
    """Format SYN results as a human-readable report."""
    lines = []

    if result.pending:
        lines.append(f"[HERMES] {len(result.pending)} pending message(s) for '{namespace}':")
        for m in result.pending:
            lines.append(f"  [{m.src} → {m.dst}] ({m.type}) {m.msg}")
    else:
        lines.append(f"[HERMES] No pending messages for '{namespace}'.")

    if result.stale:
        lines.append(f"[HERMES] WARNING: {len(result.stale)} message(s) unACKed >3 days:")
        for m in result.stale:
            age = (date.today() - m.ts).days
            lines.append(f"  [{m.src}] {m.msg} ({age}d old)")

    if result.unresolved:
        lines.append(f"[HERMES] WARNING: {len(result.unresolved)} UNRESOLVED reliable message(s):")
        for m in result.unresolved:
            age = (date.today() - m.ts).days
            lines.append(f"  [{m.src}] {m.msg} ({age}d, ACKED but no resolution)")

    lines.append(f"[HERMES] Bus total: {result.total_bus_messages} active message(s).")
    return "\n".join(lines)


@dataclass
class FinAction:
    """A state change to write to the bus during FIN."""

    dst: str
    type: str
    msg: str
    ttl: int | None = None


def fin(
    bus_path: str | Path,
    namespace: str,
    actions: list[FinAction] | None = None,
    compact: bool = False,
) -> list[Message]:
    """Execute the FIN protocol for a namespace.

    Per ARC-0793:
    1. Write state changes to bus
    2. Return the messages written (caller handles SYNC HEADER update and ACKs)

    Args:
        compact: If True, write messages in compact format (ARC-5322 §14).

    Returns list of messages written to the bus.
    """
    if not actions:
        return []

    written = []
    for action in actions:
        msg = create_message(
            src=namespace,
            dst=action.dst,
            type=action.type,
            msg=action.msg,
            ttl=action.ttl,
        )
        write_message(bus_path, msg, compact=compact)
        written.append(msg)

    return written
