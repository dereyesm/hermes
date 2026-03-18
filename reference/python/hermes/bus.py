"""HERMES Bus Operations — ARC-0793 Reference Implementation.

Read, write, and archive operations on the HERMES message bus.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from .message import (
    Message,
    ValidationError,
    extract_cid,
    extract_re,
    parse_line,
    transport_mode,
    validate_message,
)


def read_bus(bus_path: str | Path) -> list[Message]:
    """Read all valid messages from a bus file.

    Supports both verbose (object) and compact (array) formats per
    ARC-5322 §14.5 auto-detection. Invalid lines are skipped with a
    warning printed to stderr. Returns messages in file order.
    """
    bus_path = Path(bus_path)
    if not bus_path.exists():
        return []

    messages = []
    for line_num, line in enumerate(bus_path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            msg = parse_line(line)
            messages.append(msg)
        except (json.JSONDecodeError, ValidationError) as e:
            import sys
            print(f"Warning: bus line {line_num} skipped: {e}", file=sys.stderr)

    return messages


def write_message(
    bus_path: str | Path,
    message: Message,
    compact: bool = False,
) -> None:
    """Append a single message to the bus file.

    Args:
        bus_path: Path to the bus JSONL file.
        message: The Message to write.
        compact: If True, write in compact format (ARC-5322 §14).
                 Default False (verbose) for backward compatibility.
    """
    bus_path = Path(bus_path)
    line = message.to_compact_jsonl() if compact else message.to_jsonl()
    with bus_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def filter_for_namespace(
    messages: list[Message],
    namespace: str,
) -> list[Message]:
    """Filter messages relevant to a namespace (SYN protocol).

    Returns messages where:
    - dst matches the namespace OR dst is "*" (broadcast)
    - AND the namespace has NOT already ACKed
    """
    return [
        m for m in messages
        if (m.dst == namespace or m.dst == "*")
        and namespace not in m.ack
    ]


def find_stale(messages: list[Message], threshold_days: int = 3) -> list[Message]:
    """Find messages that have been unACKed for longer than threshold.

    Per ARC-0793: if unACKed >3 days, flag as stale.
    """
    today = date.today()
    stale = []
    for m in messages:
        age = (today - m.ts).days
        if age > threshold_days and len(m.ack) == 0:
            stale.append(m)
    return stale


def find_expired(messages: list[Message]) -> list[Message]:
    """Find messages whose TTL has expired."""
    today = date.today()
    return [
        m for m in messages
        if (today - m.ts).days > m.ttl
    ]


def archive_expired(
    bus_path: str | Path,
    archive_path: str | Path,
    compact: bool = False,
) -> int:
    """Move expired messages from bus to archive.

    Returns the number of messages archived.
    """
    bus_path = Path(bus_path)
    archive_path = Path(archive_path)

    messages = read_bus(bus_path)
    today = date.today()

    active = []
    expired = []

    for m in messages:
        if (today - m.ts).days > m.ttl:
            expired.append(m)
        else:
            active.append(m)

    if not expired:
        return 0

    _serialize = Message.to_compact_jsonl if compact else Message.to_jsonl

    # Append expired to archive
    with archive_path.open("a", encoding="utf-8") as f:
        for m in expired:
            f.write(_serialize(m) + "\n")

    # Rewrite bus with only active messages
    with bus_path.open("w", encoding="utf-8") as f:
        for m in active:
            f.write(_serialize(m) + "\n")

    return len(expired)


def ack_message(
    bus_path: str | Path,
    namespace: str,
    match_fn: callable,
    compact: bool = False,
) -> int:
    """ACK messages matching a predicate by adding namespace to their ack array.

    match_fn receives a Message and returns True if it should be ACKed.
    Returns the number of messages ACKed.

    Note: This rewrites the bus file. In production, consider file locking.
    """
    bus_path = Path(bus_path)
    messages = read_bus(bus_path)
    acked = 0

    updated = []
    for m in messages:
        if match_fn(m) and namespace not in m.ack:
            new_ack = list(m.ack) + [namespace]
            updated.append(Message(
                ts=m.ts, src=m.src, dst=m.dst, type=m.type,
                msg=m.msg, ttl=m.ttl, ack=new_ack,
            ))
            acked += 1
        else:
            updated.append(m)

    if acked > 0:
        _serialize = Message.to_compact_jsonl if compact else Message.to_jsonl
        with bus_path.open("w", encoding="utf-8") as f:
            for m in updated:
                f.write(_serialize(m) + "\n")

    return acked


def find_unresolved(messages: list[Message]) -> list[Message]:
    """Find REL messages that are ACKed but not yet resolved (ARC-0768).

    Returns messages where:
    - type is REL (request, dispatch, data_cross)
    - msg contains [CID:X]
    - ack array is non-empty (someone has seen it)
    - no companion [RE:X] message exists on the bus
    - TTL has NOT expired
    """
    today = date.today()
    # Build set of resolved CIDs
    resolved_cids: set[str] = set()
    for m in messages:
        re_token = extract_re(m.msg)
        if re_token:
            resolved_cids.add(re_token)

    unresolved = []
    for m in messages:
        if transport_mode(m.type) != "REL":
            continue
        cid = extract_cid(m.msg)
        if cid is None:
            continue
        if not m.ack:
            continue
        if cid in resolved_cids:
            continue
        if (today - m.ts).days > m.ttl:
            continue
        unresolved.append(m)

    return unresolved


def find_expired_unresolved(messages: list[Message]) -> list[Message]:
    """Find REL messages that expired without resolution (ARC-0768).

    Returns messages where:
    - type is REL
    - msg contains [CID:X] with no companion [RE:X]
    - TTL HAS expired
    """
    today = date.today()
    resolved_cids: set[str] = set()
    for m in messages:
        re_token = extract_re(m.msg)
        if re_token:
            resolved_cids.add(re_token)

    expired_unresolved = []
    for m in messages:
        if transport_mode(m.type) != "REL":
            continue
        cid = extract_cid(m.msg)
        if cid is None:
            continue
        if cid in resolved_cids:
            continue
        if (today - m.ts).days <= m.ttl:
            continue
        expired_unresolved.append(m)

    return expired_unresolved


def correlate(messages: list[Message], cid: str) -> dict:
    """Find the request/response pair for a given CID (ARC-0768).

    Returns {"request": Message | None, "response": Message | None}.
    """
    result: dict = {"request": None, "response": None}
    for m in messages:
        if extract_cid(m.msg) == cid:
            result["request"] = m
        if extract_re(m.msg) == cid:
            result["response"] = m
    return result


def generate_escalation(original: Message) -> Message:
    """Create an escalation alert for an unresolved REL message (ARC-0768).

    The alert is addressed to the original sender so they know
    their request was not resolved before expiry.
    """
    from .message import create_message

    prefix = f"UNRESOLVED:{original.type}:"
    # Truncate original msg to fit within 120 chars
    max_payload = 120 - len(prefix)
    truncated = original.msg[:max_payload]
    payload = prefix + truncated

    return create_message(
        src=original.src,
        dst="*",
        type="alert",
        msg=payload,
    )
