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

# ARC-5322 §14: Compact Wire Format
COMPACT_EPOCH = date(2000, 1, 1)

# §14.4: Type enumeration (int → string, string → int)
TYPE_TO_INT: dict[str, int] = {
    "state": 0,
    "alert": 1,
    "event": 2,
    "request": 3,
    "data_cross": 4,
    "dispatch": 5,
    "dojo_event": 6,
}
INT_TO_TYPE: dict[int, str] = {v: k for k, v in TYPE_TO_INT.items()}

# §14.2: Positional field order
COMPACT_FIELD_COUNT = 7  # ts, src, dst, type, msg, ttl, ack
COMPACT_FIELD_COUNT_WITH_ENCODING = 8


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
        """Serialize to a single verbose JSONL line (no trailing newline)."""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    def to_compact(self) -> list:
        """Serialize to a compact array per ARC-5322 §14.

        Returns a list: [epoch_day, src, dst, type_int, msg, ttl, ack]
        with optional 8th element for non-raw encoding.
        """
        epoch_day = (self.ts - COMPACT_EPOCH).days
        type_int = TYPE_TO_INT[self.type]
        arr = [epoch_day, self.src, self.dst, type_int, self.msg, self.ttl, list(self.ack)]
        if self.encoding is not None and self.encoding != "raw":
            arr.append(self.encoding)
        return arr

    def to_compact_jsonl(self) -> str:
        """Serialize to a compact JSONL line per ARC-5322 §14."""
        return json.dumps(self.to_compact(), ensure_ascii=False, separators=(",", ":"))


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


def validate_compact(data: list) -> Message:
    """Validate a compact array against ARC-5322 §14 and return a Message.

    Expects: [epoch_day, src, dst, type_int, msg, ttl, ack]
    Optional 8th element: encoding string.
    """
    if not isinstance(data, list):
        raise ValidationError(f"Compact message must be a JSON array, got {type(data).__name__}")

    if len(data) not in (COMPACT_FIELD_COUNT, COMPACT_FIELD_COUNT_WITH_ENCODING):
        raise ValidationError(
            f"Compact message must have {COMPACT_FIELD_COUNT} or "
            f"{COMPACT_FIELD_COUNT_WITH_ENCODING} elements, got {len(data)}"
        )

    epoch_day, src, dst, type_int, msg, ttl, ack = data[:7]
    encoding_raw = data[7] if len(data) == COMPACT_FIELD_COUNT_WITH_ENCODING else None

    # §14.3: epoch-day → date
    if not isinstance(epoch_day, int) or isinstance(epoch_day, bool):
        raise ValidationError(f"Compact ts (index 0) must be an integer, got {type(epoch_day).__name__}")
    if epoch_day < 0:
        raise ValidationError(f"Compact ts (index 0) must be non-negative, got {epoch_day}")
    from datetime import timedelta
    ts = COMPACT_EPOCH + timedelta(days=epoch_day)

    # §14.4: type int → string
    if not isinstance(type_int, int) or isinstance(type_int, bool):
        raise ValidationError(f"Compact type (index 3) must be an integer, got {type(type_int).__name__}")
    if type_int not in INT_TO_TYPE:
        raise ValidationError(
            f"Invalid compact type {type_int}. Valid range: 0-{max(INT_TO_TYPE.keys())}"
        )
    type_str = INT_TO_TYPE[type_int]

    # Build verbose dict and delegate to existing validation
    verbose = {
        "ts": ts.isoformat(),
        "src": src,
        "dst": dst,
        "type": type_str,
        "msg": msg,
        "ttl": ttl,
        "ack": ack,
    }
    if encoding_raw is not None:
        verbose["encoding"] = encoding_raw

    return validate_message(verbose)


def parse_line(line: str) -> Message:
    """Auto-detect and parse a JSONL line (verbose or compact) per ARC-5322 §14.5.

    Inspects the first non-whitespace character:
    - '{' → verbose format (JSON object)
    - '[' → compact format (JSON array)
    """
    stripped = line.strip()
    if not stripped:
        raise ValidationError("Empty line")

    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as e:
        raise ValidationError(f"JSON parse error: {e}")

    if isinstance(data, dict):
        return validate_message(data)
    elif isinstance(data, list):
        return validate_compact(data)
    else:
        raise ValidationError(
            f"HERMES message must be a JSON object (verbose) or array (compact), "
            f"got {type(data).__name__}"
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
    """Validate JSONL messages from stdin. Exit 1 if any are invalid.

    Supports both verbose and compact formats (auto-detected per §14.5).
    Use --expand to convert compact messages to verbose for human reading.
    Use --compact to convert verbose messages to compact.
    """
    expand_mode = "--expand" in sys.argv
    compact_mode = "--compact" in sys.argv
    errors = 0
    total = 0

    for line_num, line in enumerate(sys.stdin, 1):
        line = line.strip()
        if not line:
            continue
        total += 1

        try:
            msg = parse_line(line)
        except ValidationError as e:
            print(f"Line {line_num}: {e}", file=sys.stderr)
            errors += 1
            continue

        if expand_mode:
            print(msg.to_jsonl())
        elif compact_mode:
            print(msg.to_compact_jsonl())

    if total == 0:
        print("No messages to validate.", file=sys.stderr)
        sys.exit(1)

    if errors:
        print(f"\n{errors}/{total} messages invalid.", file=sys.stderr)
        sys.exit(1)

    if not expand_mode and not compact_mode:
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
