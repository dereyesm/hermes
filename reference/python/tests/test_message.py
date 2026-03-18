"""Tests for HERMES message validation and bus operations."""

import json
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from hermes.message import (
    COMPACT_EPOCH,
    INT_TO_TYPE,
    MAX_MSG_LENGTH,
    TYPE_TO_INT,
    VALID_ENCODINGS,
    Message,
    ValidationError,
    create_message,
    parse_line,
    validate_compact,
    validate_message,
    validate_namespace,
)
from hermes.bus import (
    ack_message,
    archive_expired,
    filter_for_namespace,
    find_expired,
    find_stale,
    read_bus,
    write_message,
)
from hermes.sync import FinAction, SynResult, fin, syn, syn_report


# ─── Namespace Validation ───────────────────────────────────────────


class TestValidateNamespace:
    def test_valid_namespace(self):
        validate_namespace("engineering")
        validate_namespace("my-team")
        validate_namespace("a")
        validate_namespace("team-alpha-01")

    def test_broadcast_allowed(self):
        validate_namespace("*", allow_broadcast=True)

    def test_broadcast_not_allowed(self):
        with pytest.raises(ValidationError):
            validate_namespace("*", allow_broadcast=False)

    def test_uppercase_rejected(self):
        with pytest.raises(ValidationError):
            validate_namespace("Engineering")

    def test_spaces_rejected(self):
        with pytest.raises(ValidationError):
            validate_namespace("my team")

    def test_empty_rejected(self):
        with pytest.raises(ValidationError):
            validate_namespace("")

    def test_starts_with_number_rejected(self):
        with pytest.raises(ValidationError):
            validate_namespace("1team")

    def test_too_long_rejected(self):
        with pytest.raises(ValidationError):
            validate_namespace("a" * 64)

    def test_max_length_accepted(self):
        validate_namespace("a" * 63)


# ─── Message Validation ─────────────────────────────────────────────


def _valid_data(**overrides) -> dict:
    """Return a valid message dict with optional overrides."""
    base = {
        "ts": "2026-01-15",
        "src": "engineering",
        "dst": "*",
        "type": "state",
        "msg": "sprint_started",
        "ttl": 7,
        "ack": [],
    }
    base.update(overrides)
    return base


class TestValidateMessage:
    def test_valid_message(self):
        msg = validate_message(_valid_data())
        assert msg.src == "engineering"
        assert msg.dst == "*"
        assert msg.type == "state"
        assert msg.ts == date(2026, 1, 15)

    def test_missing_field(self):
        data = _valid_data()
        del data["ts"]
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_message(data)

    def test_invalid_date(self):
        with pytest.raises(ValidationError, match="Invalid date"):
            validate_message(_valid_data(ts="not-a-date"))

    def test_invalid_src(self):
        with pytest.raises(ValidationError, match="Invalid namespace"):
            validate_message(_valid_data(src="BAD NAME"))

    def test_src_cannot_be_broadcast(self):
        with pytest.raises(ValidationError, match="Invalid namespace"):
            validate_message(_valid_data(src="*"))

    def test_src_equals_dst(self):
        with pytest.raises(ValidationError, match="must differ"):
            validate_message(_valid_data(src="eng", dst="eng"))

    def test_broadcast_dst_ok(self):
        msg = validate_message(_valid_data(dst="*"))
        assert msg.dst == "*"

    def test_invalid_type(self):
        with pytest.raises(ValidationError, match="Invalid message type"):
            validate_message(_valid_data(type="invalid"))

    def test_all_valid_types(self):
        for t in ["state", "alert", "event", "request", "data_cross", "dispatch", "dojo_event"]:
            msg = validate_message(_valid_data(type=t))
            assert msg.type == t

    def test_empty_msg(self):
        with pytest.raises(ValidationError, match="must not be empty"):
            validate_message(_valid_data(msg=""))

    def test_msg_too_long(self):
        with pytest.raises(ValidationError, match="exceeds"):
            validate_message(_valid_data(msg="x" * (MAX_MSG_LENGTH + 1)))

    def test_msg_max_length_ok(self):
        msg = validate_message(_valid_data(msg="x" * MAX_MSG_LENGTH))
        assert len(msg.msg) == MAX_MSG_LENGTH

    def test_control_chars_rejected(self):
        with pytest.raises(ValidationError, match="control characters"):
            validate_message(_valid_data(msg="hello\x00world"))

    def test_negative_ttl(self):
        with pytest.raises(ValidationError, match="must be positive"):
            validate_message(_valid_data(ttl=0))

    def test_boolean_ttl_rejected(self):
        with pytest.raises(ValidationError, match="must be an integer"):
            validate_message(_valid_data(ttl=True))

    def test_duplicate_ack_rejected(self):
        with pytest.raises(ValidationError, match="Duplicate"):
            validate_message(_valid_data(ack=["eng", "eng"]))

    def test_invalid_ack_namespace(self):
        with pytest.raises(ValidationError, match="Invalid namespace"):
            validate_message(_valid_data(ack=["INVALID"]))


# ─── Message Creation ────────────────────────────────────────────────


class TestCreateMessage:
    def test_defaults(self):
        msg = create_message(
            src="engineering", dst="*", type="alert", msg="system_down"
        )
        assert msg.ts == date.today()
        assert msg.ttl == 5  # alert default
        assert msg.ack == []

    def test_custom_ttl(self):
        msg = create_message(
            src="engineering", dst="finance", type="data_cross",
            msg="costs_q4_2400usd@aws", ttl=14,
        )
        assert msg.ttl == 14

    def test_custom_date(self):
        msg = create_message(
            src="ops", dst="*", type="event", msg="deploy_complete",
            ts=date(2026, 6, 1),
        )
        assert msg.ts == date(2026, 6, 1)


# ─── Serialization ──────────────────────────────────────────────────


class TestSerialization:
    def test_to_dict_roundtrip(self):
        msg = create_message(src="eng", dst="*", type="state", msg="ok")
        d = msg.to_dict()
        msg2 = validate_message(d)
        assert msg.src == msg2.src
        assert msg.msg == msg2.msg

    def test_to_jsonl(self):
        msg = create_message(src="eng", dst="*", type="state", msg="ok")
        line = msg.to_jsonl()
        data = json.loads(line)
        assert data["src"] == "eng"
        assert "\n" not in line


# ─── Payload Encoding (ARC-5322 Section 7) ─────────────────────────


class TestPayloadEncoding:
    def test_no_encoding_field_backward_compat(self):
        """Messages without encoding field work as before."""
        msg = validate_message(_valid_data())
        assert msg.encoding is None

    def test_raw_encoding_enforces_limit(self):
        """encoding=raw enforces 120-char limit."""
        with pytest.raises(ValidationError, match="exceeds"):
            validate_message(_valid_data(msg="x" * 121, encoding="raw"))

    def test_raw_encoding_within_limit(self):
        msg = validate_message(_valid_data(msg="x" * 120, encoding="raw"))
        assert msg.encoding == "raw"

    def test_cbor_encoding_allows_long_payload(self):
        """encoding=cbor skips the 120-char limit."""
        long_payload = "o2Rjb3N0GQl4" * 20  # >120 chars
        msg = validate_message(_valid_data(msg=long_payload, encoding="cbor"))
        assert msg.encoding == "cbor"
        assert len(msg.msg) > 120

    def test_ref_encoding_allows_file_path(self):
        """encoding=ref allows file paths as payload."""
        msg = validate_message(_valid_data(
            msg="/shared/reports/q1-analysis.json", encoding="ref"
        ))
        assert msg.encoding == "ref"

    def test_invalid_encoding_rejected(self):
        with pytest.raises(ValidationError, match="Invalid encoding"):
            validate_message(_valid_data(encoding="protobuf"))

    def test_serialization_omits_raw_encoding(self):
        """to_dict omits encoding when raw (backward compat)."""
        msg = create_message(src="eng", dst="*", type="state", msg="ok")
        d = msg.to_dict()
        assert "encoding" not in d

    def test_serialization_includes_cbor_encoding(self):
        """to_dict includes encoding when cbor."""
        msg = create_message(
            src="eng", dst="ops", type="data_cross",
            msg="o2Rjb3N0GQl4", encoding="cbor",
        )
        d = msg.to_dict()
        assert d["encoding"] == "cbor"

    def test_roundtrip_with_encoding(self):
        """Serialization/deserialization preserves encoding."""
        msg = create_message(
            src="eng", dst="ops", type="data_cross",
            msg="/path/to/data.csv", encoding="ref",
        )
        d = msg.to_dict()
        msg2 = validate_message(d)
        assert msg2.encoding == "ref"
        assert msg2.msg == "/path/to/data.csv"

    def test_create_message_with_encoding(self):
        msg = create_message(
            src="eng", dst="ops", type="data_cross",
            msg="o2Rjb3N0GQl4" * 20, encoding="cbor",
        )
        assert msg.encoding == "cbor"
        assert len(msg.msg) > 120

    def test_extra_unknown_field_still_rejected(self):
        """encoding is allowed, but other extra fields are not."""
        data = _valid_data()
        data["priority"] = "high"
        with pytest.raises(ValidationError, match="Extra fields"):
            validate_message(data)


# ─── Bus Operations ─────────────────────────────────────────────────


@pytest.fixture
def bus_dir(tmp_path):
    """Create a temporary directory with bus and archive files."""
    bus = tmp_path / "bus.jsonl"
    archive = tmp_path / "bus-archive.jsonl"
    bus.touch()
    archive.touch()
    return tmp_path


class TestBusOperations:
    def test_read_empty_bus(self, bus_dir):
        msgs = read_bus(bus_dir / "bus.jsonl")
        assert msgs == []

    def test_write_and_read(self, bus_dir):
        bus = bus_dir / "bus.jsonl"
        msg = create_message(src="eng", dst="*", type="state", msg="hello")
        write_message(bus, msg)
        msgs = read_bus(bus)
        assert len(msgs) == 1
        assert msgs[0].msg == "hello"

    def test_filter_unicast(self, bus_dir):
        msgs = [
            create_message(src="eng", dst="finance", type="data_cross", msg="costs"),
            create_message(src="eng", dst="ops", type="request", msg="need_info"),
            create_message(src="eng", dst="*", type="state", msg="sprint_done"),
        ]
        filtered = filter_for_namespace(msgs, "finance")
        assert len(filtered) == 2  # unicast to finance + broadcast

    def test_filter_excludes_acked(self):
        msg = Message(
            ts=date.today(), src="eng", dst="*", type="state",
            msg="done", ttl=7, ack=["finance"],
        )
        filtered = filter_for_namespace([msg], "finance")
        assert len(filtered) == 0

    def test_find_stale(self):
        old = Message(
            ts=date.today() - timedelta(days=5),
            src="eng", dst="*", type="alert", msg="old_alert",
            ttl=7, ack=[],
        )
        recent = Message(
            ts=date.today(),
            src="eng", dst="*", type="state", msg="new",
            ttl=7, ack=[],
        )
        stale = find_stale([old, recent], threshold_days=3)
        assert len(stale) == 1
        assert stale[0].msg == "old_alert"

    def test_find_expired(self):
        expired = Message(
            ts=date.today() - timedelta(days=10),
            src="eng", dst="*", type="event", msg="old_event",
            ttl=3, ack=[],
        )
        active = Message(
            ts=date.today(),
            src="eng", dst="*", type="state", msg="current",
            ttl=7, ack=[],
        )
        result = find_expired([expired, active])
        assert len(result) == 1
        assert result[0].msg == "old_event"

    def test_archive_expired(self, bus_dir):
        bus = bus_dir / "bus.jsonl"
        archive = bus_dir / "bus-archive.jsonl"

        # Write one expired and one active message
        expired = Message(
            ts=date.today() - timedelta(days=10),
            src="eng", dst="*", type="event", msg="expired_event",
            ttl=3, ack=[],
        )
        active = create_message(src="eng", dst="*", type="state", msg="active")

        write_message(bus, expired)
        write_message(bus, active)

        count = archive_expired(bus, archive)
        assert count == 1

        # Bus should only have active
        remaining = read_bus(bus)
        assert len(remaining) == 1
        assert remaining[0].msg == "active"

        # Archive should have expired
        archived = read_bus(archive)
        assert len(archived) == 1
        assert archived[0].msg == "expired_event"

    def test_ack_message(self, bus_dir):
        bus = bus_dir / "bus.jsonl"
        msg = create_message(src="eng", dst="*", type="state", msg="update")
        write_message(bus, msg)

        count = ack_message(bus, "finance", lambda m: m.msg == "update")
        assert count == 1

        msgs = read_bus(bus)
        assert "finance" in msgs[0].ack


# ─── Compact Bus Operations (ARC-5322 §14 + bus.py) ────────────────


class TestCompactBusOperations:
    def test_write_compact_and_read(self, bus_dir):
        bus = bus_dir / "bus.jsonl"
        msg = create_message(src="eng", dst="*", type="state", msg="compact_test")
        write_message(bus, msg, compact=True)
        raw = bus.read_text()
        assert raw.startswith("[")  # compact format
        msgs = read_bus(bus)
        assert len(msgs) == 1
        assert msgs[0].msg == "compact_test"

    def test_mixed_mode_bus(self, bus_dir):
        """Bus with both verbose and compact messages reads correctly."""
        bus = bus_dir / "bus.jsonl"
        msg1 = create_message(src="eng", dst="*", type="state", msg="verbose_msg")
        msg2 = create_message(src="ops", dst="*", type="alert", msg="compact_msg")
        write_message(bus, msg1, compact=False)
        write_message(bus, msg2, compact=True)

        raw_lines = bus.read_text().strip().split("\n")
        assert raw_lines[0].startswith("{")  # verbose
        assert raw_lines[1].startswith("[")  # compact

        msgs = read_bus(bus)
        assert len(msgs) == 2
        assert msgs[0].msg == "verbose_msg"
        assert msgs[1].msg == "compact_msg"

    def test_ack_on_compact_bus(self, bus_dir):
        bus = bus_dir / "bus.jsonl"
        msg = create_message(src="eng", dst="*", type="state", msg="needs_ack")
        write_message(bus, msg, compact=True)

        count = ack_message(bus, "finance", lambda m: m.msg == "needs_ack")
        assert count == 1

        msgs = read_bus(bus)
        assert "finance" in msgs[0].ack

    def test_archive_compact(self, bus_dir):
        bus = bus_dir / "bus.jsonl"
        archive = bus_dir / "bus-archive.jsonl"

        expired = Message(
            ts=date.today() - timedelta(days=10),
            src="eng", dst="*", type="event", msg="old_compact",
            ttl=3, ack=[],
        )
        active = create_message(src="eng", dst="*", type="state", msg="active_compact")

        write_message(bus, expired, compact=True)
        write_message(bus, active, compact=True)

        count = archive_expired(bus, archive, compact=True)
        assert count == 1

        remaining = read_bus(bus)
        assert len(remaining) == 1
        assert remaining[0].msg == "active_compact"

        archived = read_bus(archive)
        assert len(archived) == 1
        assert archived[0].msg == "old_compact"

    def test_compact_write_is_smaller(self, bus_dir):
        """Compact bus file is smaller than verbose for same messages."""
        bus_v = bus_dir / "verbose.jsonl"
        bus_c = bus_dir / "compact.jsonl"

        for i in range(10):
            msg = create_message(
                src="eng", dst="*", type="state",
                msg=f"message number {i} with some payload",
            )
            write_message(bus_v, msg, compact=False)
            write_message(bus_c, msg, compact=True)

        size_v = bus_v.stat().st_size
        size_c = bus_c.stat().st_size
        assert size_c < size_v
        # At least 20% smaller
        assert size_c < size_v * 0.80


# ─── SYN/FIN Protocol ───────────────────────────────────────────────


class TestSynProtocol:
    def test_syn_empty_bus(self, bus_dir):
        result = syn(bus_dir / "bus.jsonl", "engineering")
        assert result.pending == []
        assert result.stale == []
        assert result.total_bus_messages == 0

    def test_syn_finds_pending(self, bus_dir):
        bus = bus_dir / "bus.jsonl"
        msg = create_message(src="ops", dst="*", type="alert", msg="deadline_friday")
        write_message(bus, msg)

        result = syn(bus, "engineering")
        assert len(result.pending) == 1
        assert result.pending[0].msg == "deadline_friday"

    def test_syn_report_format(self):
        result = SynResult(
            pending=[
                Message(ts=date.today(), src="ops", dst="*", type="alert",
                        msg="deadline", ttl=5, ack=[]),
            ],
            stale=[],
            total_bus_messages=1,
        )
        report = syn_report(result, "engineering")
        assert "[HERMES]" in report
        assert "1 pending" in report
        assert "deadline" in report


class TestFinProtocol:
    def test_fin_writes_compact(self, bus_dir):
        bus = bus_dir / "bus.jsonl"
        actions = [
            FinAction(dst="*", type="state", msg="compact_fin"),
        ]
        written = fin(bus, "engineering", actions, compact=True)
        assert len(written) == 1
        raw = bus.read_text()
        assert raw.startswith("[")  # compact format
        msgs = read_bus(bus)
        assert msgs[0].msg == "compact_fin"

    def test_fin_writes_messages(self, bus_dir):
        bus = bus_dir / "bus.jsonl"
        actions = [
            FinAction(dst="*", type="state", msg="sprint_completed"),
            FinAction(dst="finance", type="data_cross", msg="costs_q1_5000usd@internal"),
        ]
        written = fin(bus, "engineering", actions)
        assert len(written) == 2

        msgs = read_bus(bus)
        assert len(msgs) == 2
        assert msgs[0].src == "engineering"
        assert msgs[1].dst == "finance"

    def test_fin_no_actions(self, bus_dir):
        bus = bus_dir / "bus.jsonl"
        written = fin(bus, "engineering", [])
        assert written == []

    def test_fin_none_actions(self, bus_dir):
        bus = bus_dir / "bus.jsonl"
        written = fin(bus, "engineering", None)
        assert written == []


# ─── Compact Wire Format (ARC-5322 §14) ───────────────────────────


def _epoch_day(d: date) -> int:
    """Convert date to epoch-day (days since 2000-01-01)."""
    return (d - COMPACT_EPOCH).days


class TestCompactConstants:
    def test_type_enum_coverage(self):
        """All valid types have an integer mapping."""
        from hermes.message import VALID_TYPES
        for t in VALID_TYPES:
            assert t in TYPE_TO_INT, f"Type '{t}' missing from TYPE_TO_INT"

    def test_type_enum_roundtrip(self):
        for name, idx in TYPE_TO_INT.items():
            assert INT_TO_TYPE[idx] == name

    def test_epoch_day_known_values(self):
        assert _epoch_day(date(2000, 1, 1)) == 0
        assert _epoch_day(date(2026, 3, 15)) == 9570
        assert _epoch_day(date(2025, 1, 1)) == 9132


class TestCompactSerialization:
    def test_to_compact_basic(self):
        msg = create_message(
            src="engineering", dst="*", type="state", msg="deployed",
            ts=date(2026, 3, 15),
        )
        arr = msg.to_compact()
        assert arr[0] == 9570  # epoch-day
        assert arr[1] == "engineering"
        assert arr[2] == "*"
        assert arr[3] == 0  # state
        assert arr[4] == "deployed"
        assert arr[5] == 7  # default TTL for state
        assert arr[6] == []
        assert len(arr) == 7  # no encoding element

    def test_to_compact_with_encoding(self):
        msg = create_message(
            src="eng", dst="ops", type="data_cross",
            msg="o2Rjb3N0GQl4", encoding="cbor",
            ts=date(2026, 3, 15),
        )
        arr = msg.to_compact()
        assert len(arr) == 8
        assert arr[7] == "cbor"

    def test_to_compact_jsonl_format(self):
        msg = create_message(
            src="eng", dst="*", type="state", msg="ok",
            ts=date(2026, 3, 15),
        )
        line = msg.to_compact_jsonl()
        assert line.startswith("[")
        assert ", " not in line  # compact separators
        assert ": " not in line

    def test_to_compact_jsonl_size(self):
        """Compact format should be significantly smaller than verbose."""
        msg = create_message(
            src="momoshod", dst="nymyka", type="state",
            msg="x" * 120, ts=date(2026, 3, 15),
        )
        verbose = msg.to_jsonl()
        compact = msg.to_compact_jsonl()
        assert len(compact) < len(verbose)
        # Wrapper savings: ~69 bytes (105 → 36)
        assert len(verbose) - len(compact) > 50

    def test_to_compact_with_ack(self):
        msg = Message(
            ts=date(2026, 3, 15), src="eng", dst="*", type="alert",
            msg="deadline", ttl=5, ack=["ops", "finance"],
        )
        arr = msg.to_compact()
        assert arr[6] == ["ops", "finance"]


class TestCompactValidation:
    def test_valid_compact(self):
        data = [9570, "engineering", "*", 0, "deployed", 7, []]
        msg = validate_compact(data)
        assert msg.ts == date(2026, 3, 15)
        assert msg.src == "engineering"
        assert msg.type == "state"

    def test_valid_compact_with_encoding(self):
        data = [9570, "eng", "ops", 4, "o2Rjb3N0GQl4", 7, [], "cbor"]
        msg = validate_compact(data)
        assert msg.encoding == "cbor"

    def test_wrong_element_count(self):
        with pytest.raises(ValidationError, match="7 or 8 elements"):
            validate_compact([9570, "eng", "*", 0, "ok", 7])  # 6 elements

    def test_too_many_elements(self):
        with pytest.raises(ValidationError, match="7 or 8 elements"):
            validate_compact([9570, "eng", "*", 0, "ok", 7, [], "raw", "extra"])

    def test_invalid_epoch_day_type(self):
        with pytest.raises(ValidationError, match="integer"):
            validate_compact(["2026-03-15", "eng", "*", 0, "ok", 7, []])

    def test_negative_epoch_day(self):
        with pytest.raises(ValidationError, match="non-negative"):
            validate_compact([-1, "eng", "*", 0, "ok", 7, []])

    def test_invalid_type_int(self):
        with pytest.raises(ValidationError, match="Invalid compact type"):
            validate_compact([9570, "eng", "*", 99, "ok", 7, []])

    def test_all_type_ints_valid(self):
        for type_int, type_str in INT_TO_TYPE.items():
            data = [9570, "eng", "*", type_int, "ok", 7, []]
            msg = validate_compact(data)
            assert msg.type == type_str

    def test_compact_inherits_verbose_validation(self):
        """Compact still enforces namespace rules, msg length, etc."""
        with pytest.raises(ValidationError, match="Invalid namespace"):
            validate_compact([9570, "BAD NAME", "*", 0, "ok", 7, []])

        with pytest.raises(ValidationError, match="exceeds"):
            validate_compact([9570, "eng", "*", 0, "x" * 121, 7, []])

    def test_not_a_list(self):
        with pytest.raises(ValidationError, match="JSON array"):
            validate_compact("not a list")

    def test_boolean_epoch_day_rejected(self):
        with pytest.raises(ValidationError, match="integer"):
            validate_compact([True, "eng", "*", 0, "ok", 7, []])

    def test_boolean_type_rejected(self):
        with pytest.raises(ValidationError, match="integer"):
            validate_compact([9570, "eng", "*", True, "ok", 7, []])


class TestCompactRoundtrip:
    def test_verbose_to_compact_roundtrip(self):
        """Message survives verbose → compact → verbose."""
        original = create_message(
            src="engineering", dst="operations", type="request",
            msg="need_capacity_estimate", ts=date(2026, 3, 15), ttl=5,
        )
        compact_arr = original.to_compact()
        restored = validate_compact(compact_arr)
        assert restored.ts == original.ts
        assert restored.src == original.src
        assert restored.dst == original.dst
        assert restored.type == original.type
        assert restored.msg == original.msg
        assert restored.ttl == original.ttl
        assert restored.ack == original.ack

    def test_compact_jsonl_roundtrip(self):
        """Message survives to_compact_jsonl → parse_line."""
        original = create_message(
            src="eng", dst="*", type="state", msg="ok",
            ts=date(2026, 3, 15),
        )
        line = original.to_compact_jsonl()
        restored = parse_line(line)
        assert restored.src == original.src
        assert restored.ts == original.ts

    def test_verbose_jsonl_roundtrip(self):
        """parse_line handles verbose format too."""
        original = create_message(
            src="eng", dst="*", type="state", msg="ok",
            ts=date(2026, 3, 15),
        )
        line = original.to_jsonl()
        restored = parse_line(line)
        assert restored.src == original.src

    def test_all_types_roundtrip(self):
        for type_str in TYPE_TO_INT:
            msg = create_message(
                src="eng", dst="ops" if type_str != "state" else "*",
                type=type_str, msg="test", ts=date(2026, 3, 15),
            )
            compact = msg.to_compact_jsonl()
            restored = parse_line(compact)
            assert restored.type == type_str

    def test_roundtrip_with_encoding(self):
        msg = create_message(
            src="eng", dst="ops", type="data_cross",
            msg="/path/to/data.csv", encoding="ref",
            ts=date(2026, 3, 15),
        )
        compact = msg.to_compact_jsonl()
        restored = parse_line(compact)
        assert restored.encoding == "ref"
        assert restored.msg == "/path/to/data.csv"


class TestParseLine:
    def test_auto_detect_verbose(self):
        line = '{"ts":"2026-03-15","src":"eng","dst":"*","type":"state","msg":"ok","ttl":7,"ack":[]}'
        msg = parse_line(line)
        assert msg.src == "eng"

    def test_auto_detect_compact(self):
        line = '[9570,"eng","*",0,"ok",7,[]]'
        msg = parse_line(line)
        assert msg.src == "eng"
        assert msg.ts == date(2026, 3, 15)

    def test_empty_line_error(self):
        with pytest.raises(ValidationError, match="Empty line"):
            parse_line("")

    def test_invalid_json_error(self):
        with pytest.raises(ValidationError, match="JSON parse error"):
            parse_line("not json at all")

    def test_unexpected_type_error(self):
        with pytest.raises(ValidationError, match="JSON object.*or array"):
            parse_line('"just a string"')

    def test_mixed_bus(self):
        """Both formats can coexist on the same bus."""
        verbose = '{"ts":"2026-03-15","src":"eng","dst":"*","type":"state","msg":"verbose","ttl":7,"ack":[]}'
        compact = '[9570,"ops","*",1,"compact",5,[]]'
        m1 = parse_line(verbose)
        m2 = parse_line(compact)
        assert m1.msg == "verbose"
        assert m2.msg == "compact"
        assert m2.type == "alert"


# ─── Sample Bus Validation ──────────────────────────────────────────


class TestSampleBus:
    """Validate the example bus-sample.jsonl against the spec."""

    def test_sample_bus_is_valid(self):
        sample_path = Path(__file__).parent.parent.parent.parent / "examples" / "bus-sample.jsonl"
        if not sample_path.exists():
            pytest.skip("bus-sample.jsonl not found")

        msgs = read_bus(sample_path)
        assert len(msgs) == 10  # 10 representative messages
        for msg in msgs:
            assert msg.src != ""
            assert msg.msg != ""
            assert msg.ttl > 0
