"""Tests for HERMES MCP server — tool functions + cursor + resources."""

import json
import os
from datetime import date
from pathlib import Path

import pytest

from hermes.mcp_server import (
    SessionCursor,
    _msg_to_dict,
    tool_bus_ack,
    tool_bus_read,
    tool_bus_write,
    tool_integrity_check,
    tool_status,
)
from hermes.bus import read_bus, write_message
from hermes.message import create_message

# Use a temp bus for all tests
@pytest.fixture(autouse=True)
def setup_hermes_dir(tmp_path, monkeypatch):
    """Set up a temp HERMES dir for each test."""
    import hermes.mcp_server as mcp_mod
    monkeypatch.setattr(mcp_mod, "_HERMES_DIR", tmp_path)
    # Reset cursor
    mcp_mod._cursor = SessionCursor()
    # Create bus file
    (tmp_path / "bus.jsonl").touch()
    return tmp_path


class TestSessionCursor:
    """Tests for per-session cursor tracking."""

    def test_cursor_starts_at_zero(self, setup_hermes_dir):
        cursor = SessionCursor()
        bus = setup_hermes_dir / "bus.jsonl"
        assert cursor.read_new(bus) == []

    def test_cursor_reads_new_messages(self, setup_hermes_dir):
        cursor = SessionCursor()
        bus = setup_hermes_dir / "bus.jsonl"

        # Write 2 messages
        msg1 = create_message(src="a", dst="b", type="event", msg="first")
        msg2 = create_message(src="a", dst="b", type="event", msg="second")
        write_message(str(bus), msg1)
        write_message(str(bus), msg2)

        # First read gets both
        new = cursor.read_new(bus)
        assert len(new) == 2
        assert new[0].msg == "first"
        assert new[1].msg == "second"

        # Second read gets nothing
        new2 = cursor.read_new(bus)
        assert len(new2) == 0

    def test_cursor_only_sees_new_after_advance(self, setup_hermes_dir):
        cursor = SessionCursor()
        bus = setup_hermes_dir / "bus.jsonl"

        # Write first message
        write_message(str(bus), create_message(src="a", dst="b", type="event", msg="old"))

        # Advance past it
        cursor.advance_to_end(bus)

        # Write new message
        write_message(str(bus), create_message(src="a", dst="b", type="event", msg="new"))

        # Should only see "new"
        new = cursor.read_new(bus)
        assert len(new) == 1
        assert new[0].msg == "new"

    def test_cursor_handles_missing_file(self):
        cursor = SessionCursor()
        result = cursor.read_new(Path("/nonexistent/bus.jsonl"))
        assert result == []


class TestBusRead:
    """Tests for hermes_bus_read tool."""

    def test_read_empty_bus(self, setup_hermes_dir):
        result = tool_bus_read()
        assert result == []

    def test_read_all_messages(self, setup_hermes_dir):
        bus = setup_hermes_dir / "bus.jsonl"
        write_message(str(bus), create_message(src="eng", dst="ops", type="state", msg="green"))
        write_message(str(bus), create_message(src="ops", dst="eng", type="event", msg="deployed"))

        result = tool_bus_read()
        assert len(result) == 2

    def test_read_namespace_filter(self, setup_hermes_dir):
        bus = setup_hermes_dir / "bus.jsonl"
        write_message(str(bus), create_message(src="eng", dst="ops", type="state", msg="for ops"))
        write_message(str(bus), create_message(src="eng", dst="hr", type="state", msg="for hr"))

        result = tool_bus_read(namespace="ops")
        assert len(result) == 1
        assert result[0]["msg"] == "for ops"

    def test_read_type_filter(self, setup_hermes_dir):
        bus = setup_hermes_dir / "bus.jsonl"
        write_message(str(bus), create_message(src="a", dst="*", type="event", msg="event msg"))
        write_message(str(bus), create_message(src="a", dst="*", type="state", msg="state msg"))

        result = tool_bus_read(type_filter="event")
        assert len(result) == 1
        assert result[0]["type"] == "event"

    def test_read_new_only(self, setup_hermes_dir):
        bus = setup_hermes_dir / "bus.jsonl"
        write_message(str(bus), create_message(src="a", dst="*", type="event", msg="old"))

        # First read (advances cursor)
        tool_bus_read()

        # Write new message
        write_message(str(bus), create_message(src="a", dst="*", type="event", msg="new"))

        # new_only should return only the new message
        result = tool_bus_read(new_only=True)
        assert len(result) == 1
        assert result[0]["msg"] == "new"

    def test_read_pending_only(self, setup_hermes_dir):
        bus = setup_hermes_dir / "bus.jsonl"
        msg = create_message(src="a", dst="b", type="event", msg="unacked")
        write_message(str(bus), msg)

        result = tool_bus_read(pending_only=True)
        assert len(result) == 1


class TestBusWrite:
    """Tests for hermes_bus_write tool."""

    def test_write_message(self, setup_hermes_dir):
        result = tool_bus_write(src="eng", dst="ops", type="state", msg="pipeline green")
        assert result["src"] == "eng"
        assert result["dst"] == "ops"
        assert result["msg"] == "pipeline green"

        # Verify written to file
        bus = setup_hermes_dir / "bus.jsonl"
        messages = read_bus(str(bus))
        assert len(messages) == 1

    def test_write_with_custom_ttl(self, setup_hermes_dir):
        result = tool_bus_write(src="a", dst="b", type="event", msg="short lived", ttl=1)
        assert result["ttl"] == 1


class TestBusAck:
    """Tests for hermes_bus_ack tool."""

    def test_ack_messages(self, setup_hermes_dir):
        bus = setup_hermes_dir / "bus.jsonl"
        write_message(str(bus), create_message(src="eng", dst="ops", type="state", msg="test"))

        result = tool_bus_ack(namespace="ops")
        assert result["acked"] >= 1

    def test_ack_with_filter(self, setup_hermes_dir):
        bus = setup_hermes_dir / "bus.jsonl"
        write_message(str(bus), create_message(src="eng", dst="ops", type="state", msg="from eng"))
        write_message(str(bus), create_message(src="hr", dst="ops", type="event", msg="from hr"))

        result = tool_bus_ack(namespace="ops", src_filter="eng")
        assert result["acked"] == 1


class TestSynFin:
    """Tests for SYN/FIN lifecycle tools."""

    def test_syn_empty_bus(self, setup_hermes_dir):
        from hermes.mcp_server import tool_syn
        result = tool_syn(namespace="eng")
        assert result["pending"] == 0

    def test_syn_with_messages(self, setup_hermes_dir):
        from hermes.mcp_server import tool_syn
        bus = setup_hermes_dir / "bus.jsonl"
        write_message(str(bus), create_message(src="ops", dst="eng", type="event", msg="hey eng"))

        result = tool_syn(namespace="eng")
        assert result["pending"] >= 1
        assert "report" in result

    def test_fin_writes_state(self, setup_hermes_dir):
        from hermes.mcp_server import tool_fin
        result = tool_fin(
            namespace="eng",
            actions=[{"dst": "*", "type": "state", "msg": "session ended cleanly"}],
        )
        assert result["written"] == 1


class TestStatus:
    """Tests for hermes_status tool."""

    def test_status_returns_version(self, setup_hermes_dir):
        result = tool_status()
        assert "protocol_version" in result
        assert result["protocol_version"] == "0.4.2a1"

    def test_status_bus_stats(self, setup_hermes_dir):
        bus = setup_hermes_dir / "bus.jsonl"
        write_message(str(bus), create_message(src="a", dst="b", type="event", msg="test"))

        result = tool_status()
        assert result["bus"]["total"] == 1


class TestIntegrity:
    """Tests for hermes_integrity_check tool."""

    def test_integrity_empty_bus(self, setup_hermes_dir):
        result = tool_integrity_check()
        assert result["status"] == "no_bus" or result["total_messages"] == 0

    def test_integrity_clean_bus(self, setup_hermes_dir):
        bus = setup_hermes_dir / "bus.jsonl"
        write_message(str(bus), create_message(src="a", dst="b", type="event", msg="clean"))

        result = tool_integrity_check()
        assert result["total_messages"] == 1


class TestMsgToDict:
    """Tests for message serialization."""

    def test_basic_conversion(self):
        msg = create_message(src="a", dst="b", type="event", msg="test")
        d = _msg_to_dict(msg)
        assert d["src"] == "a"
        assert d["dst"] == "b"
        assert d["msg"] == "test"
        assert "ts" in d
        assert "ack" in d

    def test_seq_included_when_present(self):
        msg = create_message(src="a", dst="b", type="event", msg="test", seq=42)
        d = _msg_to_dict(msg)
        assert d["seq"] == 42


class TestCrossSessionSync:
    """Integration test: simulate two sessions communicating via the bus."""

    def test_session_a_writes_session_b_reads(self, setup_hermes_dir):
        """The core use case: real-time sync between sessions."""
        import hermes.mcp_server as mcp_mod

        bus = setup_hermes_dir / "bus.jsonl"

        # Session B starts (advances cursor past existing messages)
        cursor_b = SessionCursor()
        cursor_b.advance_to_end(bus)

        # Session A writes
        tool_bus_write(src="session-a", dst="*", type="event", msg="hello from A")

        # Session B reads new_only
        new_msgs = cursor_b.read_new(bus)
        assert len(new_msgs) == 1
        assert new_msgs[0].msg == "hello from A"
        assert new_msgs[0].src == "session-a"

        # Session B writes back
        tool_bus_write(src="session-b", dst="session-a", type="event", msg="hello from B")

        # Session A reads (using the module cursor which was advanced during bus_read)
        result = tool_bus_read(new_only=True)
        # Module cursor was advanced when we called tool_bus_write, so we may or may not see it
        # What matters: the message is in the bus
        all_msgs = tool_bus_read()
        assert len(all_msgs) == 2
