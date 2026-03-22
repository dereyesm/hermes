"""HERMES Bus Operations — ARC-0793 Reference Implementation.

Read, write, and archive operations on the HERMES message bus.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from .message import (
    ENCODING_SEALED,
    ENCODING_SEALED_ECDHE,
    Message,
    ValidationError,
    extract_cid,
    extract_re,
    is_sealed,
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


def read_bus_with_integrity(
    bus_path: str | Path,
    seq_tracker: "SequenceTracker | None" = None,
    wv_tracker: "WriteVectorTracker | None" = None,
    conflict_log: "ConflictLog | None" = None,
) -> tuple[list[Message], list[dict]]:
    """Read bus and validate sequence + causal integrity (ARC-9001 F1+F3).

    Returns (messages, anomalies) where anomalies is a list of
    {"type": "gap"|"duplicate"|"concurrent", "src": ..., "seq": ..., ...}.

    If seq_tracker is None, a fresh one is created for the scan.
    Messages without seq are included in the list but not validated.
    When wv_tracker is provided, messages with `w` field are checked for
    causal conflicts. Detected conflicts are logged to conflict_log if available.
    """
    from .integrity import SequenceTracker as _ST, WriteVector as _WV

    messages = read_bus(bus_path)
    if seq_tracker is None:
        seq_tracker = _ST()
    anomalies = seq_tracker.load_from_bus(messages)

    # F3: Validate write vectors and detect concurrent writes
    if wv_tracker is not None:
        for msg in messages:
            w_data = getattr(msg, "w", None)
            seq = getattr(msg, "seq", None)
            if w_data is not None and seq is not None:
                wv = _WV.from_dict(w_data)
                conflicts = wv_tracker.detect_conflicts(msg.src, seq, wv)
                for c in conflicts:
                    anomalies.append(c)
                    # F4: Log conflict
                    if conflict_log is not None:
                        conflict_log.record_concurrent(
                            c["src1"], c["seq1"], c["src2"], c["seq2"],
                        )
                ts_str = msg.ts.isoformat() if hasattr(msg.ts, "isoformat") else ""
                wv_tracker.record(msg.src, seq, wv, ts_str)

    return messages, anomalies


def write_message(
    bus_path: str | Path,
    message: Message,
    compact: bool = False,
    seq_tracker: "SequenceTracker | None" = None,
    wv_tracker: "WriteVectorTracker | None" = None,
) -> Message:
    """Append a single message to the bus file.

    Args:
        bus_path: Path to the bus JSONL file.
        message: The Message to write.
        compact: If True, write in compact format (ARC-5322 §14).
                 Default False (verbose) for backward compatibility.
        seq_tracker: Optional SequenceTracker (ARC-9001 F1). When provided
                     and message.seq is None, auto-assigns the next sequence
                     number for message.src.
        wv_tracker: Optional WriteVectorTracker (ARC-9001 F3). When provided
                    and message.w is None, auto-assigns the current write vector.
                    After writing, records the message for conflict detection.

    Returns:
        The message as written (may have seq and/or w assigned).
    """
    # F3: Auto-assign write vector before seq (captures pre-write state)
    w = message.w
    if wv_tracker is not None and w is None:
        w = wv_tracker.current_vector().to_dict()

    if seq_tracker is not None and message.seq is None:
        next_seq = seq_tracker.next_seq(message.src)
        message = Message(
            ts=message.ts, src=message.src, dst=message.dst,
            type=message.type, msg=message.msg, ttl=message.ttl,
            ack=list(message.ack), encoding=message.encoding,
            seq=next_seq, w=w,
        )
        seq_tracker.record(message.src, next_seq)
    elif seq_tracker is not None and message.seq is not None:
        seq_tracker.record(message.src, message.seq)
        if w is not None and message.w is None:
            message = Message(
                ts=message.ts, src=message.src, dst=message.dst,
                type=message.type, msg=message.msg, ttl=message.ttl,
                ack=list(message.ack), encoding=message.encoding,
                seq=message.seq, w=w,
            )
    elif w is not None and message.w is None:
        message = Message(
            ts=message.ts, src=message.src, dst=message.dst,
            type=message.type, msg=message.msg, ttl=message.ttl,
            ack=list(message.ack), encoding=message.encoding,
            seq=message.seq, w=w,
        )

    # F3: Record in tracker after write
    if wv_tracker is not None and message.seq is not None:
        from .integrity import WriteVector as _WV
        wv = _WV.from_dict(message.w) if message.w is not None else _WV()
        wv_tracker.record(
            message.src, message.seq, wv,
            message.ts.isoformat() if hasattr(message.ts, "isoformat") else "",
        )

    bus_path = Path(bus_path)
    line = message.to_compact_jsonl() if compact else message.to_jsonl()
    with bus_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    return message


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


# ─── Sealed Envelope Operations (ARC-8446 + ARC-5322 §14) ─────


def _envelope_meta(m: Message) -> dict:
    """Build envelope_meta AAD from a Message's own fields."""
    return {"src": m.src, "dst": m.dst, "ts": m.ts.isoformat(), "type": m.type}


def write_sealed_message(
    bus_path: str | Path,
    message: Message,
    my_keys,
    peer_dh_public,
    compact: bool = False,
    ecdhe: bool = True,
) -> None:
    """Seal and write a message to the bus.

    Encrypts message.msg via compact sealed envelope, then writes a new
    Message with the sealed array as msg and encoding marker.

    Args:
        bus_path: Path to the bus JSONL file.
        message: Plaintext Message to seal and write.
        my_keys: Sender's ClanKeyPair.
        peer_dh_public: Recipient's X25519 public key.
        compact: If True, write bus line in compact format.
        ecdhe: If True (default), use ECDHE. If False, use static DH.
    """
    from .crypto import seal_bus_message_compact, seal_bus_message_ecdhe_compact

    meta = _envelope_meta(message)

    if ecdhe:
        sealed_array = seal_bus_message_ecdhe_compact(
            my_keys, peer_dh_public, message.msg, envelope_meta=meta,
        )
        encoding = ENCODING_SEALED_ECDHE
    else:
        sealed_array = seal_bus_message_compact(
            my_keys, peer_dh_public, message.msg, envelope_meta=meta,
        )
        encoding = ENCODING_SEALED

    sealed_msg = Message(
        ts=message.ts,
        src=message.src,
        dst=message.dst,
        type=message.type,
        msg=json.dumps(sealed_array, separators=(",", ":")),
        ttl=message.ttl,
        ack=list(message.ack),
        encoding=encoding,
    )
    write_message(bus_path, sealed_msg, compact=compact)


def open_sealed_message(
    message: Message,
    my_keys,
    peer_sign_public,
    peer_dh_public,
    nonce_tracker=None,
) -> Message | None:
    """Decrypt a sealed bus message and return a plaintext Message.

    Args:
        message: A Message with encoding "sealed" or "sealed-ecdhe".
        my_keys: Recipient's ClanKeyPair.
        peer_sign_public: Sender's Ed25519 public key.
        peer_dh_public: Sender's X25519 public key.
        nonce_tracker: Optional NonceTracker for replay detection.

    Returns:
        A new Message with decrypted msg and encoding=None,
        or None if decryption/verification fails.
    """
    from .crypto import open_bus_message_compact

    if not is_sealed(message):
        return message

    meta = _envelope_meta(message)

    try:
        sealed_array = json.loads(message.msg)
    except (json.JSONDecodeError, TypeError):
        return None

    plaintext = open_bus_message_compact(
        my_keys, peer_sign_public, peer_dh_public,
        sealed_array, envelope_meta=meta, nonce_tracker=nonce_tracker,
    )
    if plaintext is None:
        return None

    return Message(
        ts=message.ts,
        src=message.src,
        dst=message.dst,
        type=message.type,
        msg=plaintext,
        ttl=message.ttl,
        ack=list(message.ack),
        encoding=None,
    )


def read_bus_sealed(
    bus_path: str | Path,
    my_keys,
    peer_sign_public,
    peer_dh_public,
    nonce_tracker=None,
) -> list[Message]:
    """Read bus and transparently decrypt any sealed messages.

    Plaintext messages pass through unchanged. Sealed messages that fail
    decryption are replaced with None (filtered out).

    Args:
        bus_path: Path to the bus JSONL file.
        my_keys: Recipient's ClanKeyPair.
        peer_sign_public: Sender's Ed25519 public key.
        peer_dh_public: Sender's X25519 public key.
        nonce_tracker: Optional NonceTracker for replay detection.

    Returns:
        List of plaintext Messages (sealed messages decrypted in place).
    """
    messages = read_bus(bus_path)
    result = []
    for m in messages:
        if is_sealed(m):
            opened = open_sealed_message(
                m, my_keys, peer_sign_public, peer_dh_public,
                nonce_tracker=nonce_tracker,
            )
            if opened is not None:
                result.append(opened)
        else:
            result.append(m)
    return result
