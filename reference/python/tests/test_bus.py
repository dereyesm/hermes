"""Comprehensive tests for HERMES bus operations (bus.py).

Covers: read_bus, write_message, filter_for_namespace, find_stale,
find_expired, archive_expired, ack_message.
"""

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from hermes.bus import (
    ack_message,
    archive_expired,
    filter_for_namespace,
    find_expired,
    find_stale,
    read_bus,
    write_message,
)
from hermes.message import Message, create_message


# ─── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def bus_file(tmp_path):
    """Create an empty bus file and return its path."""
    f = tmp_path / "bus.jsonl"
    f.touch()
    return f


@pytest.fixture
def archive_file(tmp_path):
    """Create an empty archive file and return its path."""
    f = tmp_path / "bus-archive.jsonl"
    f.touch()
    return f


def _make_msg(src="eng", dst="*", type="state", msg="test", ttl=7,
              ts=None, ack=None):
    """Helper to create a Message with sensible defaults."""
    return Message(
        ts=ts or date.today(),
        src=src, dst=dst, type=type, msg=msg, ttl=ttl,
        ack=ack or [],
    )


# ─── read_bus ──────────────────────────────────────────────────────


class TestReadBus:
    def test_empty_file(self, bus_file):
        assert read_bus(bus_file) == []

    def test_nonexistent_file(self, tmp_path):
        assert read_bus(tmp_path / "does-not-exist.jsonl") == []

    def test_single_message(self, bus_file):
        msg = create_message(src="eng", dst="*", type="state", msg="hello")
        write_message(bus_file, msg)
        result = read_bus(bus_file)
        assert len(result) == 1
        assert result[0].msg == "hello"

    def test_multiple_messages(self, bus_file):
        for i in range(5):
            write_message(bus_file, create_message(
                src="eng", dst="*", type="state", msg=f"msg-{i}"
            ))
        result = read_bus(bus_file)
        assert len(result) == 5
        assert [m.msg for m in result] == [f"msg-{i}" for i in range(5)]

    def test_invalid_lines_skipped(self, bus_file):
        # Write one valid, one invalid, one valid
        valid = create_message(src="eng", dst="*", type="state", msg="valid")
        bus_file.write_text(
            valid.to_jsonl() + "\n"
            + '{"broken": true}\n'
            + valid.to_jsonl() + "\n",
            encoding="utf-8",
        )
        result = read_bus(bus_file)
        assert len(result) == 2

    def test_empty_lines_skipped(self, bus_file):
        valid = create_message(src="eng", dst="*", type="state", msg="ok")
        bus_file.write_text(
            "\n\n" + valid.to_jsonl() + "\n\n",
            encoding="utf-8",
        )
        result = read_bus(bus_file)
        assert len(result) == 1

    def test_malformed_json_skipped(self, bus_file):
        valid = create_message(src="eng", dst="*", type="state", msg="ok")
        bus_file.write_text(
            "not json at all\n" + valid.to_jsonl() + "\n",
            encoding="utf-8",
        )
        result = read_bus(bus_file)
        assert len(result) == 1

    def test_preserves_ack_array(self, bus_file):
        msg = _make_msg(ack=["fin", "ops"])
        write_message(bus_file, msg)
        result = read_bus(bus_file)
        assert result[0].ack == ["fin", "ops"]


# ─── write_message ─────────────────────────────────────────────────


class TestWriteMessage:
    def test_creates_on_first_write(self, tmp_path):
        bus = tmp_path / "new-bus.jsonl"
        assert not bus.exists()
        msg = create_message(src="eng", dst="*", type="state", msg="first")
        write_message(bus, msg)
        assert bus.exists()
        assert len(read_bus(bus)) == 1

    def test_appends_not_overwrites(self, bus_file):
        msg1 = create_message(src="eng", dst="*", type="state", msg="one")
        msg2 = create_message(src="ops", dst="*", type="event", msg="two")
        write_message(bus_file, msg1)
        write_message(bus_file, msg2)
        result = read_bus(bus_file)
        assert len(result) == 2
        assert result[0].msg == "one"
        assert result[1].msg == "two"

    def test_message_ends_with_newline(self, bus_file):
        msg = create_message(src="eng", dst="*", type="state", msg="test")
        write_message(bus_file, msg)
        content = bus_file.read_text(encoding="utf-8")
        assert content.endswith("\n")
        assert content.count("\n") == 1


# ─── filter_for_namespace ──────────────────────────────────────────


class TestFilterForNamespace:
    def test_empty_list(self):
        assert filter_for_namespace([], "eng") == []

    def test_unicast_match(self):
        msg = _make_msg(src="ops", dst="eng")
        result = filter_for_namespace([msg], "eng")
        assert len(result) == 1

    def test_unicast_mismatch(self):
        msg = _make_msg(src="ops", dst="fin")
        result = filter_for_namespace([msg], "eng")
        assert len(result) == 0

    def test_broadcast_match(self):
        msg = _make_msg(src="ops", dst="*")
        result = filter_for_namespace([msg], "eng")
        assert len(result) == 1

    def test_already_acked_excluded(self):
        msg = _make_msg(src="ops", dst="*", ack=["eng"])
        result = filter_for_namespace([msg], "eng")
        assert len(result) == 0

    def test_acked_by_other_not_excluded(self):
        msg = _make_msg(src="ops", dst="*", ack=["fin"])
        result = filter_for_namespace([msg], "eng")
        assert len(result) == 1

    def test_mixed_scenario(self):
        msgs = [
            _make_msg(src="ops", dst="eng"),           # match: unicast
            _make_msg(src="ops", dst="fin"),           # no match
            _make_msg(src="ops", dst="*"),              # match: broadcast
            _make_msg(src="ops", dst="*", ack=["eng"]),  # acked
            _make_msg(src="ops", dst="eng", ack=["eng"]),  # acked unicast
        ]
        result = filter_for_namespace(msgs, "eng")
        assert len(result) == 2

    def test_source_namespace_gets_own_broadcast(self):
        """Source namespace CAN see its own broadcast if not acked."""
        msg = _make_msg(src="eng", dst="*")
        result = filter_for_namespace([msg], "eng")
        # The filter checks dst match and ack — src is not excluded
        assert len(result) == 1


# ─── find_stale ────────────────────────────────────────────────────


class TestFindStale:
    def test_no_stale_messages(self):
        msg = _make_msg(ts=date.today())
        assert find_stale([msg]) == []

    def test_stale_message_detected(self):
        old = _make_msg(ts=date.today() - timedelta(days=5))
        result = find_stale([old])
        assert len(result) == 1

    def test_boundary_exactly_3_days(self):
        """3 days old with threshold=3 should NOT be stale (> not >=)."""
        msg = _make_msg(ts=date.today() - timedelta(days=3))
        result = find_stale([msg], threshold_days=3)
        assert len(result) == 0

    def test_boundary_4_days(self):
        msg = _make_msg(ts=date.today() - timedelta(days=4))
        result = find_stale([msg], threshold_days=3)
        assert len(result) == 1

    def test_custom_threshold(self):
        msg = _make_msg(ts=date.today() - timedelta(days=2))
        assert find_stale([msg], threshold_days=1) == [msg]
        assert find_stale([msg], threshold_days=5) == []

    def test_acked_messages_not_stale(self):
        """Messages with non-empty ack are not considered stale."""
        old = _make_msg(ts=date.today() - timedelta(days=5), ack=["fin"])
        result = find_stale([old])
        assert len(result) == 0

    def test_mixed_stale_and_fresh(self):
        msgs = [
            _make_msg(ts=date.today() - timedelta(days=10)),  # stale
            _make_msg(ts=date.today()),                         # fresh
            _make_msg(ts=date.today() - timedelta(days=5)),   # stale
        ]
        result = find_stale(msgs)
        assert len(result) == 2


# ─── find_expired ──────────────────────────────────────────────────


class TestFindExpired:
    def test_no_expired(self):
        msg = _make_msg(ts=date.today(), ttl=7)
        assert find_expired([msg]) == []

    def test_expired_message(self):
        msg = _make_msg(ts=date.today() - timedelta(days=10), ttl=3)
        result = find_expired([msg])
        assert len(result) == 1

    def test_boundary_exactly_ttl(self):
        """Message at exactly TTL boundary: today - ts == ttl should NOT be expired (> not >=)."""
        msg = _make_msg(ts=date.today() - timedelta(days=7), ttl=7)
        result = find_expired([msg])
        assert len(result) == 0

    def test_boundary_one_day_past_ttl(self):
        msg = _make_msg(ts=date.today() - timedelta(days=8), ttl=7)
        result = find_expired([msg])
        assert len(result) == 1

    def test_ttl_1(self):
        """TTL=1 means message expires after 1 day."""
        yesterday = _make_msg(ts=date.today() - timedelta(days=2), ttl=1)
        today_msg = _make_msg(ts=date.today(), ttl=1)
        result = find_expired([yesterday, today_msg])
        assert len(result) == 1

    def test_mixed_expired_and_active(self):
        msgs = [
            _make_msg(ts=date.today() - timedelta(days=20), ttl=3),  # expired
            _make_msg(ts=date.today(), ttl=7),                         # active
            _make_msg(ts=date.today() - timedelta(days=6), ttl=7),   # active (6 <= 7)
            _make_msg(ts=date.today() - timedelta(days=8), ttl=5),   # expired
        ]
        result = find_expired(msgs)
        assert len(result) == 2


# ─── archive_expired ──────────────────────────────────────────────


class TestArchiveExpired:
    def test_no_expired_returns_zero(self, bus_file, archive_file):
        msg = create_message(src="eng", dst="*", type="state", msg="fresh")
        write_message(bus_file, msg)
        count = archive_expired(bus_file, archive_file)
        assert count == 0
        assert len(read_bus(bus_file)) == 1

    def test_all_expired(self, bus_file, archive_file):
        expired = _make_msg(
            ts=date.today() - timedelta(days=20), ttl=3, msg="old"
        )
        write_message(bus_file, expired)
        count = archive_expired(bus_file, archive_file)
        assert count == 1
        assert len(read_bus(bus_file)) == 0
        assert len(read_bus(archive_file)) == 1

    def test_mixed_expired_and_active(self, bus_file, archive_file):
        expired = _make_msg(
            ts=date.today() - timedelta(days=20), ttl=3, msg="expired"
        )
        active = create_message(src="eng", dst="*", type="state", msg="active")
        write_message(bus_file, expired)
        write_message(bus_file, active)

        count = archive_expired(bus_file, archive_file)
        assert count == 1

        remaining = read_bus(bus_file)
        assert len(remaining) == 1
        assert remaining[0].msg == "active"

        archived = read_bus(archive_file)
        assert len(archived) == 1
        assert archived[0].msg == "expired"

    def test_archive_appends_not_overwrites(self, bus_file, archive_file):
        """Running archive twice should append to archive, not overwrite."""
        # First batch
        exp1 = _make_msg(
            ts=date.today() - timedelta(days=20), ttl=3, msg="batch1"
        )
        write_message(bus_file, exp1)
        archive_expired(bus_file, archive_file)

        # Second batch
        exp2 = _make_msg(
            ts=date.today() - timedelta(days=20), ttl=3, msg="batch2"
        )
        write_message(bus_file, exp2)
        archive_expired(bus_file, archive_file)

        archived = read_bus(archive_file)
        assert len(archived) == 2
        assert {m.msg for m in archived} == {"batch1", "batch2"}

    def test_empty_bus(self, bus_file, archive_file):
        count = archive_expired(bus_file, archive_file)
        assert count == 0


# ─── ack_message ───────────────────────────────────────────────────


class TestAckMessage:
    def test_ack_matching_message(self, bus_file):
        msg = create_message(src="eng", dst="*", type="state", msg="update")
        write_message(bus_file, msg)

        count = ack_message(bus_file, "finance", lambda m: m.msg == "update")
        assert count == 1

        msgs = read_bus(bus_file)
        assert "finance" in msgs[0].ack

    def test_ack_no_match(self, bus_file):
        msg = create_message(src="eng", dst="*", type="state", msg="update")
        write_message(bus_file, msg)

        count = ack_message(bus_file, "finance", lambda m: m.msg == "nonexist")
        assert count == 0

        msgs = read_bus(bus_file)
        assert msgs[0].ack == []

    def test_already_acked_skipped(self, bus_file):
        msg = _make_msg(ack=["finance"], msg="already-done")
        write_message(bus_file, msg)

        count = ack_message(bus_file, "finance", lambda m: True)
        assert count == 0

    def test_multiple_matches(self, bus_file):
        for i in range(3):
            write_message(bus_file, create_message(
                src="eng", dst="*", type="state", msg=f"msg-{i}"
            ))

        count = ack_message(bus_file, "ops", lambda m: True)
        assert count == 3

        msgs = read_bus(bus_file)
        assert all("ops" in m.ack for m in msgs)

    def test_selective_ack(self, bus_file):
        write_message(bus_file, create_message(
            src="eng", dst="*", type="alert", msg="urgent"
        ))
        write_message(bus_file, create_message(
            src="eng", dst="*", type="state", msg="normal"
        ))

        count = ack_message(bus_file, "ops", lambda m: m.type == "alert")
        assert count == 1

        msgs = read_bus(bus_file)
        assert "ops" in msgs[0].ack     # alert was acked
        assert "ops" not in msgs[1].ack  # state was not

    def test_ack_preserves_existing_acks(self, bus_file):
        msg = _make_msg(ack=["fin"], msg="multi-ack")
        write_message(bus_file, msg)

        ack_message(bus_file, "ops", lambda m: True)

        msgs = read_bus(bus_file)
        assert "fin" in msgs[0].ack
        assert "ops" in msgs[0].ack
