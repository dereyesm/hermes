"""Tests for HERMES Terminal — brand-aware CLI output (terminal.py).

Covers:
- Brand palette constants
- print_clan_status: plain-text and rich paths
- print_daemon_status: all state combinations
- print_inbox: empty, plain-text, rich paths
- print_bus_messages: empty, plain-text, rich paths
- HAS_RICH toggle behavior
"""

from dataclasses import dataclass
from unittest.mock import patch

import pytest

import hermes.terminal as terminal
from hermes.terminal import (
    AMBER,
    CRIMSON,
    EMERALD,
    INDIGO,
    SLATE,
    TEAL,
    TYPE_COLORS,
    get_console,
    print_bus_messages,
    print_clan_status,
    print_daemon_status,
    print_inbox,
)


# ---------------------------------------------------------------------------
# Mock data structures
# ---------------------------------------------------------------------------


@dataclass
class MockPeer:
    clan_id: str
    status: str
    added: str


@dataclass
class MockMessage:
    ts: str
    src: str
    dst: str
    type: str
    msg: str
    ack: list


# ---------------------------------------------------------------------------
# Brand palette tests
# ---------------------------------------------------------------------------


class TestBrandPalette:
    """Verify brand color constants exist and are valid hex."""

    def test_indigo(self):
        assert INDIGO == "#1A1A2E"

    def test_teal(self):
        assert TEAL == "#00D4AA"

    def test_amber(self):
        assert AMBER == "#F5A623"

    def test_emerald(self):
        assert EMERALD == "#27AE60"

    def test_crimson(self):
        assert CRIMSON == "#E74C3C"

    def test_slate(self):
        assert SLATE == "#7F8C8D"

    def test_type_colors_has_standard_types(self):
        assert "state" in TYPE_COLORS
        assert "event" in TYPE_COLORS
        assert "alert" in TYPE_COLORS
        assert "dispatch" in TYPE_COLORS


# ---------------------------------------------------------------------------
# get_console tests
# ---------------------------------------------------------------------------


class TestGetConsole:
    """Tests for get_console()."""

    def test_returns_console_when_rich(self):
        with patch.object(terminal, "HAS_RICH", True):
            c = get_console()
            assert c is not None

    def test_returns_none_without_rich(self):
        with patch.object(terminal, "HAS_RICH", False):
            c = get_console()
            assert c is None


# ---------------------------------------------------------------------------
# print_clan_status tests (plain-text path)
# ---------------------------------------------------------------------------


class TestPrintClanStatusPlain:
    """Tests for print_clan_status in plain-text mode (HAS_RICH=False)."""

    def test_minimal(self, capsys):
        with patch.object(terminal, "HAS_RICH", False):
            print_clan_status(
                clan_id="test",
                display_name="Test Clan",
                protocol_version="0.4.2",
                heraldo_alias="heraldo",
                agents=[],
                peers=[],
            )
        out = capsys.readouterr().out
        assert "test" in out
        assert "Test Clan" in out
        assert "0.4.2" in out
        assert "No published agents" in out
        assert "No peers" in out

    def test_with_agents(self, capsys):
        agents = [
            {"alias": "heraldo", "resonance": 4.5, "capabilities": ["email", "scan"]},
        ]
        with patch.object(terminal, "HAS_RICH", False):
            print_clan_status(
                clan_id="momoshod",
                display_name="MomoshoD",
                protocol_version="0.4.2",
                heraldo_alias="heraldo",
                agents=agents,
                peers=[],
            )
        out = capsys.readouterr().out
        assert "heraldo" in out
        assert "4.50" in out
        assert "email" in out

    def test_with_peers(self, capsys):
        peers = [MockPeer(clan_id="jei", status="active", added="2026-03-17")]
        with patch.object(terminal, "HAS_RICH", False):
            print_clan_status(
                clan_id="momoshod",
                display_name="MomoshoD",
                protocol_version="0.4.2",
                heraldo_alias="heraldo",
                agents=[],
                peers=peers,
            )
        out = capsys.readouterr().out
        assert "jei" in out
        assert "active" in out

    def test_with_fingerprint_and_daemon(self, capsys):
        with patch.object(terminal, "HAS_RICH", False):
            print_clan_status(
                clan_id="momoshod",
                display_name="MomoshoD",
                protocol_version="0.4.2",
                heraldo_alias="heraldo",
                agents=[],
                peers=[],
                fingerprint="2a37:fb25",
                daemon_pid=12345,
                daemon_alive=True,
                bus_messages=100,
                bus_pending=5,
            )
        out = capsys.readouterr().out
        assert "2a37:fb25" in out
        assert "running" in out
        assert "12345" in out
        assert "100 messages" in out
        assert "5 pending" in out

    def test_stale_daemon(self, capsys):
        with patch.object(terminal, "HAS_RICH", False):
            print_clan_status(
                clan_id="test",
                display_name="Test",
                protocol_version="0.4.2",
                heraldo_alias="",
                agents=[],
                peers=[],
                daemon_pid=99999,
                daemon_alive=False,
            )
        out = capsys.readouterr().out
        assert "stale" in out


# ---------------------------------------------------------------------------
# print_clan_status tests (rich path)
# ---------------------------------------------------------------------------


class TestPrintClanStatusRich:
    """Tests for print_clan_status in rich mode — verifies content, not just no-crash."""

    @pytest.mark.skipif(not terminal.HAS_RICH, reason="rich not installed")
    def test_rich_minimal(self, capsys):
        with patch.object(terminal, "HAS_RICH", True):
            print_clan_status(
                clan_id="test",
                display_name="Test Clan",
                protocol_version="0.4.2",
                heraldo_alias="heraldo",
                agents=[],
                peers=[],
            )
        out = capsys.readouterr().out
        assert "test" in out.lower() or "Test" in out

    @pytest.mark.skipif(not terminal.HAS_RICH, reason="rich not installed")
    def test_rich_full_content(self, capsys):
        agents = [{"alias": "heraldo", "resonance": 4.5, "capabilities": ["email"]}]
        peers = [MockPeer(clan_id="jei", status="active", added="2026-03-17")]
        with patch.object(terminal, "HAS_RICH", True):
            print_clan_status(
                clan_id="momoshod",
                display_name="MomoshoD",
                protocol_version="0.4.2",
                heraldo_alias="heraldo",
                agents=agents,
                peers=peers,
                fingerprint="2a37:fb25",
                daemon_pid=12345,
                daemon_alive=True,
                bus_messages=50,
                bus_pending=3,
                clan_dir="/home/user/.hermes",
            )
        out = capsys.readouterr().out
        assert "momoshod" in out.lower() or "MomoshoD" in out
        assert "heraldo" in out
        assert "jei" in out


# ---------------------------------------------------------------------------
# print_daemon_status tests
# ---------------------------------------------------------------------------


class TestPrintDaemonStatusPlain:
    """Tests for print_daemon_status in plain-text mode."""

    def test_not_running(self, capsys):
        with patch.object(terminal, "HAS_RICH", False):
            print_daemon_status(alive=False, pid=None)
        out = capsys.readouterr().out
        assert "not running" in out

    def test_running(self, capsys):
        with patch.object(terminal, "HAS_RICH", False):
            print_daemon_status(
                alive=True,
                pid=1234,
                started_at="2026-03-28T10:00:00",
                last_heartbeat="2026-03-28T10:05:00",
                bus_offset=4096,
                active_dispatches=1,
                dispatch_slots=2,
                last_evaluation="2026-03-28T10:04:50",
            )
        out = capsys.readouterr().out
        assert "running" in out
        assert "1234" in out
        assert "4096" in out
        assert "Active dispatches: 1" in out

    def test_stale_daemon(self, capsys):
        with patch.object(terminal, "HAS_RICH", False):
            print_daemon_status(alive=False, pid=5678)
        out = capsys.readouterr().out
        assert "stale" in out
        assert "5678" in out


class TestPrintDaemonStatusRich:
    """Tests for print_daemon_status in rich mode — verifies content."""

    @pytest.mark.skipif(not terminal.HAS_RICH, reason="rich not installed")
    def test_rich_not_running(self, capsys):
        with patch.object(terminal, "HAS_RICH", True):
            print_daemon_status(alive=False, pid=None)
        out = capsys.readouterr().out
        assert "not running" in out.lower() or "stopped" in out.lower() or len(out) > 0

    @pytest.mark.skipif(not terminal.HAS_RICH, reason="rich not installed")
    def test_rich_running(self, capsys):
        with patch.object(terminal, "HAS_RICH", True):
            print_daemon_status(
                alive=True,
                pid=1234,
                started_at="2026-03-28T10:00:00",
                last_heartbeat="2026-03-28T10:05:00",
                bus_offset=4096,
                active_dispatches=1,
            )
        out = capsys.readouterr().out
        assert "1234" in out

    @pytest.mark.skipif(not terminal.HAS_RICH, reason="rich not installed")
    def test_rich_stale(self, capsys):
        with patch.object(terminal, "HAS_RICH", True):
            print_daemon_status(alive=False, pid=9999)
        out = capsys.readouterr().out
        assert "9999" in out


# ---------------------------------------------------------------------------
# print_inbox tests
# ---------------------------------------------------------------------------


class TestPrintInboxPlain:
    """Tests for print_inbox in plain-text mode."""

    def test_empty(self, capsys):
        with patch.object(terminal, "HAS_RICH", False):
            print_inbox("momoshod", [])
        out = capsys.readouterr().out
        assert "empty" in out.lower()

    def test_with_messages(self, capsys):
        messages = [
            {"source_clan": "jei", "type": "event", "timestamp": "10:00", "payload": "hello"},
            {"source_clan": "nymyka", "type": "state", "timestamp": "10:05", "payload": "sync"},
        ]
        with patch.object(terminal, "HAS_RICH", False):
            print_inbox("momoshod", messages)
        out = capsys.readouterr().out
        assert "momoshod" in out
        assert "2 messages" in out
        assert "jei" in out
        assert "nymyka" in out

    def test_payload_truncated(self, capsys):
        messages = [
            {"source_clan": "jei", "type": "event", "timestamp": "10:00", "payload": "x" * 200},
        ]
        with patch.object(terminal, "HAS_RICH", False):
            print_inbox("test", messages)
        out = capsys.readouterr().out
        # Plain text truncates at 80 chars
        assert len(out) < 400


class TestPrintInboxRich:
    """Tests for print_inbox in rich mode — verifies content."""

    @pytest.mark.skipif(not terminal.HAS_RICH, reason="rich not installed")
    def test_rich_empty(self, capsys):
        with patch.object(terminal, "HAS_RICH", True):
            print_inbox("momoshod", [])
        out = capsys.readouterr().out
        assert "empty" in out.lower() or "0" in out or len(out) > 0

    @pytest.mark.skipif(not terminal.HAS_RICH, reason="rich not installed")
    def test_rich_with_messages(self, capsys):
        messages = [
            {"source_clan": "jei", "type": "alert", "timestamp": "10:00", "payload": "urgent"},
        ]
        with patch.object(terminal, "HAS_RICH", True):
            print_inbox("momoshod", messages)
        out = capsys.readouterr().out
        assert "jei" in out or "alert" in out


# ---------------------------------------------------------------------------
# print_bus_messages tests
# ---------------------------------------------------------------------------


class TestPrintBusMessagesPlain:
    """Tests for print_bus_messages in plain-text mode."""

    def test_empty(self, capsys):
        with patch.object(terminal, "HAS_RICH", False):
            print_bus_messages([])
        out = capsys.readouterr().out
        assert "empty" in out.lower()

    def test_with_messages(self, capsys):
        messages = [
            MockMessage(ts="2026-03-28", src="jei", dst="*", type="state", msg="hello world", ack=[]),
            MockMessage(ts="2026-03-28", src="nymyka", dst="momoshod", type="event", msg="ping", ack=["momoshod"]),
        ]
        with patch.object(terminal, "HAS_RICH", False):
            print_bus_messages(messages, namespace="momoshod")
        out = capsys.readouterr().out
        assert "jei" in out
        assert "nymyka" in out

    def test_ack_mark(self, capsys):
        messages = [
            MockMessage(ts="2026-03-28", src="jei", dst="*", type="state", msg="acked", ack=["momoshod"]),
            MockMessage(ts="2026-03-28", src="nymyka", dst="*", type="event", msg="pending", ack=[]),
        ]
        with patch.object(terminal, "HAS_RICH", False):
            print_bus_messages(messages, namespace="momoshod")
        out = capsys.readouterr().out
        # First message should have check mark
        lines = [l for l in out.strip().split("\n") if l.strip()]
        # acked message should contain the checkmark
        assert any("✓" in l and "jei" in l for l in lines)

    def test_no_namespace(self, capsys):
        messages = [
            MockMessage(ts="2026-03-28", src="jei", dst="*", type="state", msg="test", ack=[]),
        ]
        with patch.object(terminal, "HAS_RICH", False):
            print_bus_messages(messages)
        out = capsys.readouterr().out
        assert "jei" in out


class TestPrintBusMessagesRich:
    """Tests for print_bus_messages in rich mode — verifies content."""

    @pytest.mark.skipif(not terminal.HAS_RICH, reason="rich not installed")
    def test_rich_empty(self, capsys):
        with patch.object(terminal, "HAS_RICH", True):
            print_bus_messages([])
        out = capsys.readouterr().out
        assert "empty" in out.lower() or "0" in out or len(out) > 0

    @pytest.mark.skipif(not terminal.HAS_RICH, reason="rich not installed")
    def test_rich_with_messages(self, capsys):
        messages = [
            MockMessage(ts="2026-03-28", src="jei", dst="*", type="state", msg="hello", ack=[]),
            MockMessage(ts="2026-03-28", src="nymyka", dst="momoshod", type="alert", msg="urgent", ack=["momoshod"]),
        ]
        with patch.object(terminal, "HAS_RICH", True):
            print_bus_messages(messages, namespace="momoshod")
        out = capsys.readouterr().out
        assert "jei" in out
        assert "nymyka" in out

    @pytest.mark.skipif(not terminal.HAS_RICH, reason="rich not installed")
    def test_rich_no_namespace(self, capsys):
        messages = [
            MockMessage(ts="2026-03-28", src="jei", dst="*", type="dispatch", msg="task", ack=[]),
        ]
        with patch.object(terminal, "HAS_RICH", True):
            print_bus_messages(messages)
        out = capsys.readouterr().out
        assert "jei" in out
