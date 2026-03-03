"""HERMES Message Format — ARC-5322 Reference Implementation.

Validates and constructs HERMES messages per the ARC-5322 specification.
Can be run as a script to validate messages from stdin:

    cat bus.jsonl | python -m hermes.message
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime

# ARC-5322: Valid message types
VALID_TYPES = frozenset({
    "state",
    "alert",
    "event",
    "request",
    "data_cross",
    "dispatch",
    "dojo_event",
})

# ARC-5322: Default TTLs per message type
DEFAULT_TTLS: dict[str, int] = {
    "state": 7,
    "alert": 5,
    "event": 3,
    "request": 7,
    "data_cross": 7,
    "dispatch": 3,
    "dojo_event": 3,
}

# ARC-0768: Transport mode classification
RELIABLE_TYPES = frozenset({"request", "dispatch", "data_cross"})

# ARC-0768: Correlation ID patterns
CID_PATTERN = re.compile(r"\[CID:([a-zA-Z0-9\-]{4,12})\]$")
RE_PATTERN = re.compile(r"\[RE:([a-zA-Z0-9\-]{4,12})\]$")

# ARC-0791: Namespace naming rules
_NAMESPACE_RE = re.compile(r"^[a-z][a-z0-9\-]{0,62}$")

# ARC-5322: Max payload length
MAX_MSG_LENGTH = 120

# ARC-5322 Section 7: Valid payload encoding modes
VALID_ENCODINGS = frozenset({"raw", "cbor", "ref"})


@dataclass(frozen=True)
class Message:
    """A single HERMES bus message per ARC-5322."""

    ts: date
    src: str
    dst: str
    type: str
    msg: str
    ttl: int
    ack: list[str] = field(default_factory=list)
    encoding: str | None = None

    def to_dict(self) -> dict:
        """Serialize to a dict suitable for JSON encoding.

        The `encoding` field is omitted when it is None or "raw" to maintain
        backward compatibility with Phase 0 implementations.
        """
        d = {
            "ts": self.ts.isoformat(),
            "src": self.src,
            "dst": self.dst,
            "type": self.type,
            "msg": self.msg,
            "ttl": self.ttl,
            "ack": list(self.ack),
        }
        # Only include encoding when it's not the default (raw/None)
        if self.encoding is not None and self.encoding != "raw":
            d["encoding"] = self.encoding
        return d

    def to_jsonl(self) -> str:
        """Serialize to a single JSONL line (no trailing newline)."""
        return json.dumps(self.to_dict(), ensure_ascii=False)


class ValidationError(Exception):
    """Raised when a message fails ARC-5322 validation."""


def validate_namespace(ns: str, allow_broadcast: bool = False) -> None:
    """Validate a namespace identifier per ARC-0791."""
    if allow_broadcast and ns == "*":
        return
    if not isinstance(ns, str):
        raise ValidationError(f"Namespace must be a string, got {type(ns).__name__}")
    if not _NAMESPACE_RE.match(ns):
        raise ValidationError(
            f"Invalid namespace '{ns}': must be 1-63 chars, lowercase alphanumeric + hyphens, "
            f"starting with a letter"
        )


def validate_message(data: dict) -> Message:
    """Validate a raw dict against ARC-5322 and return a Message.

    Raises ValidationError if the message is invalid.
    """
    # Determine which fields are present; encoding is optional
    required = {"ts", "src", "dst", "type", "msg", "ttl", "ack"}
    allowed_optional = {"encoding"}
    actual = set(data.keys())

    missing = required - actual
    if missing:
        raise ValidationError(f"Missing required fields: {', '.join(sorted(missing))}")

    extra = actual - required - allowed_optional
    if extra:
        raise ValidationError(f"Extra fields not allowed: {', '.join(sorted(extra))}")

    # encoding: optional, defaults to "raw"
    encoding_raw = data.get("encoding", None)
    if encoding_raw is not None:
        if not isinstance(encoding_raw, str):
            raise ValidationError(f"'encoding' must be a string, got {type(encoding_raw).__name__}")
        if encoding_raw not in VALID_ENCODINGS:
            raise ValidationError(
                f"Invalid encoding '{encoding_raw}'. Valid encodings: {', '.join(sorted(VALID_ENCODINGS))}"
            )

    # ts: must be a valid ISO date
    ts_raw = data["ts"]
    if not isinstance(ts_raw, str):
        raise ValidationError(f"'ts' must be a string, got {type(ts_raw).__name__}")
    try:
        ts = date.fromisoformat(ts_raw)
    except ValueError:
        raise ValidationError(f"Invalid date format for 'ts': '{ts_raw}'. Expected YYYY-MM-DD")

    # src: valid namespace, no broadcast
    validate_namespace(data["src"], allow_broadcast=False)
    src = data["src"]

    # dst: valid namespace or "*"
    validate_namespace(data["dst"], allow_broadcast=True)
    dst = data["dst"]

    # src != dst (unless broadcast)
    if dst != "*" and src == dst:
        raise ValidationError(f"Source and destination must differ: '{src}' == '{dst}'")

    # type: must be in the valid set
    msg_type = data["type"]
    if msg_type not in VALID_TYPES:
        raise ValidationError(
            f"Invalid message type '{msg_type}'. Valid types: {', '.join(sorted(VALID_TYPES))}"
        )

    # msg: string, non-empty, no control characters
    msg = data["msg"]
    if not isinstance(msg, str):
        raise ValidationError(f"'msg' must be a string, got {type(msg).__name__}")
    if len(msg) == 0:
        raise ValidationError("'msg' must not be empty")

    # ARC-5322 Section 7: encoding-dependent length validation
    # When encoding is absent or "raw", enforce 120-char limit
    # When encoding is "cbor" or "ref", skip the limit
    effective_encoding = encoding_raw if encoding_raw is not None else "raw"
    if effective_encoding == "raw":
        if len(msg) > MAX_MSG_LENGTH:
            raise ValidationError(
                f"'msg' exceeds {MAX_MSG_LENGTH} chars (got {len(msg)}). "
                f"Consider splitting into multiple messages (atomicity principle)"
            )

    if any(ord(c) < 32 and c not in ("\t",) for c in msg):
        raise ValidationError("'msg' must not contain control characters")

    # ttl: positive integer
    ttl = data["ttl"]
    if not isinstance(ttl, int) or isinstance(ttl, bool):
        raise ValidationError(f"'ttl' must be an integer, got {type(ttl).__name__}")
    if ttl < 1:
        raise ValidationError(f"'ttl' must be positive, got {ttl}")

    # ack: array of valid namespace strings, no duplicates
    ack = data["ack"]
    if not isinstance(ack, list):
        raise ValidationError(f"'ack' must be an array, got {type(ack).__name__}")
    seen = set()
    for ns in ack:
        validate_namespace(ns, allow_broadcast=False)
        if ns in seen:
            raise ValidationError(f"Duplicate namespace in 'ack': '{ns}'")
        seen.add(ns)

    return Message(
        ts=ts, src=src, dst=dst, type=msg_type, msg=msg, ttl=ttl,
        ack=list(ack), encoding=encoding_raw,
    )


def create_message(
    src: str,
    dst: str,
    type: str,
    msg: str,
    ttl: int | None = None,
    ts: date | None = None,
    encoding: str | None = None,
) -> Message:
    """Create and validate a new HERMES message.

    If ttl is not provided, uses the default for the message type.
    If ts is not provided, uses today's date.
    If encoding is not provided, defaults to raw (field omitted).
    """
    if ttl is None:
        ttl = DEFAULT_TTLS.get(type, 7)
    if ts is None:
        ts = date.today()

    data = {
        "ts": ts.isoformat(),
        "src": src,
        "dst": dst,
        "type": type,
        "msg": msg,
        "ttl": ttl,
        "ack": [],
    }
    if encoding is not None:
        data["encoding"] = encoding
    return validate_message(data)


def main() -> None:
    """Validate JSONL messages from stdin. Exit 1 if any are invalid."""
    errors = 0
    total = 0

    for line_num, line in enumerate(sys.stdin, 1):
        line = line.strip()
        if not line:
            continue
        total += 1

        try:
            data = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"Line {line_num}: JSON parse error: {e}", file=sys.stderr)
            errors += 1
            continue

        try:
            validate_message(data)
        except ValidationError as e:
            print(f"Line {line_num}: {e}", file=sys.stderr)
            errors += 1

    if total == 0:
        print("No messages to validate.", file=sys.stderr)
        sys.exit(1)

    if errors:
        print(f"\n{errors}/{total} messages invalid.", file=sys.stderr)
        sys.exit(1)

    print(f"{total}/{total} messages valid.", file=sys.stderr)


def extract_cid(msg: str) -> str | None:
    """Extract a Correlation ID from a message payload per ARC-0768."""
    match = CID_PATTERN.search(msg)
    return match.group(1) if match else None


def extract_re(msg: str) -> str | None:
    """Extract a Resolution Tag from a message payload per ARC-0768."""
    match = RE_PATTERN.search(msg)
    return match.group(1) if match else None


def transport_mode(msg_type: str) -> str:
    """Return the transport mode for a message type per ARC-0768.

    Returns "REL" for reliable types (request, dispatch, data_cross),
    "DGM" for datagram types (state, event, alert, dojo_event).
    """
    return "REL" if msg_type in RELIABLE_TYPES else "DGM"


if __name__ == "__main__":
    main()
