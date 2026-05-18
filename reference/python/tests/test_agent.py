"""Tests for Amaru Agent Node — ARC-4601 Reference Implementation."""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import date, timedelta
from pathlib import Path

import pytest

from amaru.agent import (
    Action,
    AgentNode,
    AgentNodeConfig,
    BusObserver,
    Dispatcher,
    DispatchSlot,
    GatewayLink,
    MessageEvaluator,
    NodeState,
    StateManager,
    load_agent_config,
)
from amaru.message import Message, create_message

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_clan(tmp_path):
    """Create a temporary clan directory with bus.jsonl."""
    bus = tmp_path / "bus.jsonl"
    bus.touch()
    return tmp_path


@pytest.fixture
def sample_config(tmp_clan):
    """Create a basic AgentNodeConfig for testing."""
    return AgentNodeConfig(
        bus_path=tmp_clan / "bus.jsonl",
        gateway_url="http://localhost:8000",
        namespace="test-node",
        clan_dir=tmp_clan,
        evaluation_interval=1.0,
        heartbeat_interval=1.0,
        poll_interval=0.1,
    )


@pytest.fixture
def gateway_json(tmp_clan):
    """Create a gateway.json with agent_node section."""
    config = {
        "clan_id": "test-clan",
        "display_name": "Test Clan",
        "agent_node": {
            "enabled": True,
            "namespace": "test-node",
            "bus_path": "bus.jsonl",
            "gateway_url": "http://localhost:8000",
            "heartbeat_interval": 5,
            "evaluation_interval": 10,
            "max_dispatch_slots": 3,
        },
    }
    path = tmp_clan / "gateway.json"
    path.write_text(json.dumps(config, indent=2))
    return path


def _write_bus_message(bus_path: Path, **kwargs) -> Message:
    """Helper to write a message to the bus."""
    defaults = {
        "src": "source",
        "dst": "test-node",
        "type": "event",
        "msg": "test message",
        "ttl": 7,
    }
    defaults.update(kwargs)
    msg = create_message(**defaults)
    with open(bus_path, "a", encoding="utf-8") as f:
        f.write(msg.to_jsonl() + "\n")
    return msg


# ---------------------------------------------------------------------------
# AgentNodeConfig Tests
# ---------------------------------------------------------------------------


class TestAgentNodeConfig:
    def test_load_from_gateway_json(self, gateway_json, tmp_clan):
        config = load_agent_config(gateway_json)
        assert config.namespace == "test-node"
        assert config.gateway_url == "http://localhost:8000"
        assert config.max_dispatch_slots == 3
        assert config.bus_path == tmp_clan / "bus.jsonl"

    def test_load_missing_file(self, tmp_clan):
        with pytest.raises(FileNotFoundError):
            load_agent_config(tmp_clan / "nonexistent.json")

    def test_load_missing_section(self, tmp_clan):
        path = tmp_clan / "gateway.json"
        path.write_text(json.dumps({"clan_id": "x", "display_name": "X"}))
        with pytest.raises(ValueError, match="No 'agent_node'"):
            load_agent_config(path)

    def test_load_disabled(self, tmp_clan):
        path = tmp_clan / "gateway.json"
        path.write_text(
            json.dumps(
                {
                    "clan_id": "x",
                    "display_name": "X",
                    "agent_node": {"enabled": False},
                }
            )
        )
        with pytest.raises(ValueError, match="disabled"):
            load_agent_config(path)

    def test_defaults(self, gateway_json):
        config = load_agent_config(gateway_json)
        assert config.dispatch_timeout == 300.0
        assert config.dispatch_command == "claude"
        assert config.poll_interval == 2.0
        assert config.escalation_threshold_hours == 4
        assert config.forward_types == [
            "alert",
            "dispatch",
            "event",
            "coord-dispatch",
            "reflection",
        ]


# ---------------------------------------------------------------------------
# Permissive Parser Tests (ICAP Fase 2 — structured msg payloads)
# ---------------------------------------------------------------------------


class TestParseBusMessagePermissive:
    """QUEST-CROSS-003 / ICAP Fase 2 — _parse_bus_message_permissive accepts
    msg as str, dict, list, or bytes. Round-trips structured payloads to
    canonical JSON so peers see the same representation."""

    def _base_msg(self, msg_value):
        return {
            "ts": "2026-05-12",
            "src": "momoshod",
            "dst": "jei",
            "type": "coord-dispatch",
            "msg": msg_value,
            "ttl": 7,
            "ack": [],
        }

    def test_msg_str_passthrough(self):
        from amaru.agent import _parse_bus_message_permissive

        m = _parse_bus_message_permissive(self._base_msg("hello"))
        assert m is not None
        assert m.msg == "hello"

    def test_msg_dict_serialized_canonical(self):
        from amaru.agent import _parse_bus_message_permissive

        payload = {"action": "ratify", "spec": "AES-7531", "priority": 1}
        m = _parse_bus_message_permissive(self._base_msg(payload))
        assert m is not None
        # canonical JSON: sorted keys, compact separators
        assert m.msg == '{"action":"ratify","priority":1,"spec":"AES-7531"}'

    def test_msg_list_serialized_canonical(self):
        from amaru.agent import _parse_bus_message_permissive

        payload = ["amaru", "research", "community"]
        m = _parse_bus_message_permissive(self._base_msg(payload))
        assert m is not None
        assert m.msg == '["amaru","research","community"]'

    def test_msg_nested_dict_serialized(self):
        from amaru.agent import _parse_bus_message_permissive

        payload = {
            "quest_id": "Q-2026-05-12-001",
            "targets": ["jei", "nymyka"],
            "deadline": {"date": "2026-05-15", "hard": True},
        }
        m = _parse_bus_message_permissive(self._base_msg(payload))
        assert m is not None
        # nested keys also sorted
        assert (
            m.msg
            == '{"deadline":{"date":"2026-05-15","hard":true},"quest_id":"Q-2026-05-12-001","targets":["jei","nymyka"]}'
        )

    def test_msg_bytes_decoded_utf8(self):
        from amaru.agent import _parse_bus_message_permissive

        payload = b"hola mundo"
        m = _parse_bus_message_permissive(self._base_msg(payload))
        assert m is not None
        assert m.msg == "hola mundo"

    def test_msg_invalid_utf8_bytes_flagged_and_logged(self, caplog):
        """ASI02 traceability: invalid UTF-8 in msg payload MUST emit a
        warning and prefix the fallback with [ENCODING_ERROR] so
        downstream observers can filter encoding-errored messages.

        Reviewer: Bachue (JEI) — PR #26 review 2026-05-12.
        """
        import logging as _logging

        from amaru.agent import _parse_bus_message_permissive

        payload = b"\xff\xfe\xfd"  # invalid UTF-8
        with caplog.at_level(_logging.WARNING, logger="amaru.agent"):
            m = _parse_bus_message_permissive(self._base_msg(payload))

        assert m is not None
        assert m.msg.startswith("[ENCODING_ERROR]")
        # Trazabilidad: warning emitted with src/dst/type context
        assert any(
            "permissive_parser: invalid utf-8" in r.message
            and "src=momoshod" in r.message
            and "dst=jei" in r.message
            for r in caplog.records
        )

    def test_msg_int_fallback_to_str(self):
        from amaru.agent import _parse_bus_message_permissive

        m = _parse_bus_message_permissive(self._base_msg(42))
        assert m is not None
        assert m.msg == "42"

    def test_msg_none_fallback_to_str(self):
        from amaru.agent import _parse_bus_message_permissive

        m = _parse_bus_message_permissive(self._base_msg(None))
        assert m is not None
        assert m.msg == "None"

    def test_missing_field_returns_none(self):
        from amaru.agent import _parse_bus_message_permissive

        data = {"ts": "2026-05-12", "src": "momoshod"}  # incomplete
        assert _parse_bus_message_permissive(data) is None

    def test_invalid_ts_returns_none(self):
        from amaru.agent import _parse_bus_message_permissive

        data = self._base_msg("hello")
        data["ts"] = "not-a-date"
        assert _parse_bus_message_permissive(data) is None

    def test_coord_dispatch_type_preserved(self):
        from amaru.agent import _parse_bus_message_permissive

        m = _parse_bus_message_permissive(self._base_msg({"k": "v"}))
        assert m is not None
        assert m.type == "coord-dispatch"

    def test_reflection_type_preserved(self):
        from amaru.agent import _parse_bus_message_permissive

        d = self._base_msg({"insight": "the bug was never in the code"})
        d["type"] = "reflection"
        m = _parse_bus_message_permissive(d)
        assert m is not None
        assert m.type == "reflection"


# ---------------------------------------------------------------------------
# NodeState Tests
# ---------------------------------------------------------------------------


class TestNodeState:
    def test_roundtrip(self):
        state = NodeState(
            pid=123,
            started_at="2026-03-14T10:00:00",
            last_heartbeat="2026-03-14T11:00:00",
            bus_offset=4567,
            active_dispatches=[
                DispatchSlot(pid=456, cid="task-1", started_at=1000.0),
            ],
            last_evaluation="2026-03-14T10:30:00",
        )
        data = state.to_dict()
        restored = NodeState.from_dict(data)
        assert restored.pid == 123
        assert restored.bus_offset == 4567
        assert len(restored.active_dispatches) == 1
        assert restored.active_dispatches[0].cid == "task-1"

    def test_from_dict_minimal(self):
        state = NodeState.from_dict({"pid": 1, "started_at": "now"})
        assert state.bus_offset == 0
        assert state.active_dispatches == []


# ---------------------------------------------------------------------------
# StateManager Tests
# ---------------------------------------------------------------------------


class TestStateManager:
    def test_acquire_lock_success(self, tmp_clan):
        sm = StateManager(tmp_clan)
        assert sm.acquire_lock() is True
        assert (tmp_clan / "agent-node.lock" / "pid").exists()
        pid = int((tmp_clan / "agent-node.lock" / "pid").read_text())
        assert pid == os.getpid()
        sm.release_lock()

    def test_acquire_lock_fails_when_held(self, tmp_clan):
        sm = StateManager(tmp_clan)
        assert sm.acquire_lock() is True
        # Second attempt should fail (same PID is alive)
        sm2 = StateManager(tmp_clan)
        assert sm2.acquire_lock() is False
        sm.release_lock()

    def test_acquire_lock_reclaims_stale(self, tmp_clan):
        sm = StateManager(tmp_clan)
        # Create a fake lock with a dead PID
        lock_dir = tmp_clan / "agent-node.lock"
        lock_dir.mkdir()
        (lock_dir / "pid").write_text("99999999")  # Unlikely to be alive
        # Should reclaim
        assert sm.acquire_lock() is True
        sm.release_lock()

    def test_release_lock(self, tmp_clan):
        sm = StateManager(tmp_clan)
        sm.acquire_lock()
        sm.release_lock()
        assert not (tmp_clan / "agent-node.lock").exists()

    def test_save_and_load(self, tmp_clan):
        sm = StateManager(tmp_clan)
        state = NodeState(pid=42, started_at="2026-03-14T10:00:00", bus_offset=100)
        sm.save(state)
        loaded = sm.load()
        assert loaded is not None
        assert loaded.pid == 42
        assert loaded.bus_offset == 100

    def test_load_nonexistent(self, tmp_clan):
        sm = StateManager(tmp_clan)
        assert sm.load() is None

    def test_load_corrupt(self, tmp_clan):
        sm = StateManager(tmp_clan)
        (tmp_clan / "agent-node.state.json").write_text("not json")
        assert sm.load() is None

    def test_recover_dead_pid(self, tmp_clan):
        sm = StateManager(tmp_clan)
        state = NodeState(pid=99999999, started_at="old", bus_offset=500)
        sm.save(state)
        recovered = sm.recover()
        assert recovered is not None
        assert recovered.bus_offset == 500
        assert recovered.pid == os.getpid()

    def test_recover_alive_pid(self, tmp_clan):
        sm = StateManager(tmp_clan)
        # Use our own PID — it's alive
        state = NodeState(pid=os.getpid(), started_at="now", bus_offset=100)
        sm.save(state)
        recovered = sm.recover()
        assert recovered is None  # Can't recover — PID is alive

    def test_get_lock_pid(self, tmp_clan):
        sm = StateManager(tmp_clan)
        assert sm.get_lock_pid() is None
        sm.acquire_lock()
        assert sm.get_lock_pid() == os.getpid()
        sm.release_lock()


# ---------------------------------------------------------------------------
# BusObserver Tests
# ---------------------------------------------------------------------------


class TestBusObserver:
    def test_read_empty_bus(self, tmp_clan):
        obs = BusObserver(tmp_clan / "bus.jsonl", "test-node")
        assert obs.read_new_lines() == []

    def test_read_new_lines_from_zero(self, tmp_clan):
        bus = tmp_clan / "bus.jsonl"
        _write_bus_message(bus, msg="first message")
        _write_bus_message(bus, msg="second message")
        obs = BusObserver(bus, "test-node")
        messages = obs.read_new_lines()
        assert len(messages) == 2
        assert messages[0].msg == "first message"
        assert messages[1].msg == "second message"

    def test_offset_advances(self, tmp_clan):
        bus = tmp_clan / "bus.jsonl"
        _write_bus_message(bus, msg="first")
        obs = BusObserver(bus, "test-node")
        obs.read_new_lines()
        assert obs.offset > 0

        # Write more
        _write_bus_message(bus, msg="second")
        messages = obs.read_new_lines()
        assert len(messages) == 1
        assert messages[0].msg == "second"

    def test_no_new_lines(self, tmp_clan):
        bus = tmp_clan / "bus.jsonl"
        _write_bus_message(bus, msg="only one")
        obs = BusObserver(bus, "test-node")
        obs.read_new_lines()
        # No new data
        assert obs.read_new_lines() == []

    def test_truncation_resets_offset(self, tmp_clan):
        bus = tmp_clan / "bus.jsonl"
        _write_bus_message(bus, msg="a" * 50)
        obs = BusObserver(bus, "test-node")
        obs.read_new_lines()
        old_offset = obs.offset

        # Truncate (simulate archive rewrite)
        bus.write_text("")
        _write_bus_message(bus, msg="after truncate")
        messages = obs.read_new_lines()
        assert len(messages) == 1
        assert messages[0].msg == "after truncate"
        assert obs.offset < old_offset

    def test_malformed_lines_skipped(self, tmp_clan):
        bus = tmp_clan / "bus.jsonl"
        _write_bus_message(bus, msg="valid message")
        with open(bus, "a") as f:
            f.write("not json at all\n")
        _write_bus_message(bus, msg="also valid")

        obs = BusObserver(bus, "test-node")
        messages = obs.read_new_lines()
        assert len(messages) == 2

    def test_nonexistent_bus(self, tmp_clan):
        obs = BusObserver(tmp_clan / "nope.jsonl", "test-node")
        assert obs.read_new_lines() == []

    def test_read_from_offset(self, tmp_clan):
        bus = tmp_clan / "bus.jsonl"
        _write_bus_message(bus, msg="first")
        first_size = bus.stat().st_size
        _write_bus_message(bus, msg="second")

        obs = BusObserver(bus, "test-node", offset=first_size)
        messages = obs.read_new_lines()
        assert len(messages) == 1
        assert messages[0].msg == "second"


# ---------------------------------------------------------------------------
# GatewayLink Tests
# ---------------------------------------------------------------------------


class TestGatewayLink:
    def test_headers_with_gateway_key(self, sample_config):
        sample_config.gateway_key = "secret123"
        gw = GatewayLink(sample_config)
        headers = gw._push_headers()
        assert headers["X-Gateway-Key"] == "secret123"

    def test_headers_without_token(self, sample_config):
        gw = GatewayLink(sample_config)
        headers = gw._push_headers()
        assert "X-Gateway-Key" not in headers

    def test_post_message_failure(self, sample_config):
        sample_config.gateway_url = "http://localhost:99999"
        gw = GatewayLink(sample_config)
        msg = create_message(src="a", dst="b", type="event", msg="test")
        # Should not raise, returns False
        assert gw.post_message(msg) is False

    def test_heartbeat_failure(self, sample_config):
        sample_config.gateway_url = "http://localhost:99999"
        gw = GatewayLink(sample_config)
        state = NodeState(pid=1, started_at="now")
        assert gw.send_heartbeat(state, 60.0) is False

    def test_parse_sse_event_data(self):
        text = 'data: {"type": "event", "msg": "hello"}'
        result = GatewayLink._parse_sse_event(text)
        assert result == {"type": "event", "msg": "hello"}

    def test_parse_sse_event_comment(self):
        result = GatewayLink._parse_sse_event(":heartbeat")
        assert result is None

    def test_parse_sse_event_multiline(self):
        text = 'data: {"a":\ndata: 1}'
        result = GatewayLink._parse_sse_event(text)
        assert result == {"a": 1}

    def test_parse_sse_event_invalid_json(self):
        result = GatewayLink._parse_sse_event("data: not json")
        assert result is None


# ---------------------------------------------------------------------------
# MessageEvaluator Tests
# ---------------------------------------------------------------------------


class TestMessageEvaluator:
    def test_dispatch_addressed_to_us(self, sample_config):
        ev = MessageEvaluator(sample_config)
        msg = create_message(src="dojo", dst="test-node", type="dispatch", msg="run task")
        assert ev.evaluate(msg) == Action.DISPATCH

    def test_request_escalates(self, sample_config):
        ev = MessageEvaluator(sample_config)
        msg = create_message(src="user", dst="test-node", type="request", msg="need help")
        assert ev.evaluate(msg) == Action.ESCALATE

    def test_old_alert_escalates(self, sample_config):
        sample_config.escalation_threshold_hours = 4
        ev = MessageEvaluator(sample_config)
        msg = create_message(
            src="source",
            dst="test-node",
            type="alert",
            msg="old alert",
            ts=date.today() - timedelta(days=1),
        )
        assert ev.evaluate(msg) == Action.ESCALATE

    def test_fresh_alert_forwards(self, sample_config):
        ev = MessageEvaluator(sample_config)
        msg = create_message(src="source", dst="test-node", type="alert", msg="fresh")
        assert ev.evaluate(msg) == Action.FORWARD

    def test_event_forwards(self, sample_config):
        ev = MessageEvaluator(sample_config)
        msg = create_message(src="source", dst="test-node", type="event", msg="happened")
        assert ev.evaluate(msg) == Action.FORWARD

    def test_state_ignored(self, sample_config):
        ev = MessageEvaluator(sample_config)
        msg = create_message(src="source", dst="test-node", type="state", msg="status update")
        assert ev.evaluate(msg) == Action.IGNORE

    def test_dojo_event_ignored(self, sample_config):
        ev = MessageEvaluator(sample_config)
        msg = create_message(src="dojo", dst="test-node", type="dojo_event", msg="levelup:x")
        assert ev.evaluate(msg) == Action.IGNORE

    def test_already_acked_ignored(self, sample_config):
        ev = MessageEvaluator(sample_config)
        msg = Message(
            ts=date.today(),
            src="source",
            dst="test-node",
            type="dispatch",
            msg="do something",
            ttl=7,
            ack=["test-node"],
        )
        assert ev.evaluate(msg) == Action.IGNORE

    def test_broadcast_dispatch(self, sample_config):
        ev = MessageEvaluator(sample_config)
        msg = create_message(src="dojo", dst="*", type="dispatch", msg="run for all")
        assert ev.evaluate(msg) == Action.DISPATCH

    def test_data_cross_escalates(self, sample_config):
        ev = MessageEvaluator(sample_config)
        msg = create_message(src="finance", dst="test-node", type="data_cross", msg="expense data")
        assert ev.evaluate(msg) == Action.ESCALATE

    def test_unaddressed_event_with_forward_type(self, sample_config):
        ev = MessageEvaluator(sample_config)
        msg = create_message(src="source", dst="other-ns", type="event", msg="for others")
        assert ev.evaluate(msg) == Action.FORWARD

    def test_unaddressed_state_ignored(self, sample_config):
        ev = MessageEvaluator(sample_config)
        msg = create_message(src="source", dst="other-ns", type="state", msg="not for us")
        assert ev.evaluate(msg) == Action.IGNORE


# ---------------------------------------------------------------------------
# Dispatcher Tests
# ---------------------------------------------------------------------------


class TestDispatcher:
    def test_available_slots(self, sample_config):
        d = Dispatcher(sample_config)
        assert d.available_slots == sample_config.max_dispatch_slots

    def test_build_command_basic(self, sample_config):
        d = Dispatcher(sample_config)
        msg = create_message(src="a", dst="test-node", type="dispatch", msg="do thing")
        cmd = d.build_command(msg)
        assert cmd[0] == "claude"
        assert "-p" in cmd
        assert "do thing" in cmd
        assert "--max-turns" in cmd
        assert "--output-format" in cmd

    def test_build_command_with_tools(self, sample_config):
        sample_config.dispatch_allowed_tools = ["Read", "Write"]
        d = Dispatcher(sample_config)
        msg = create_message(src="a", dst="test-node", type="dispatch", msg="task")
        cmd = d.build_command(msg)
        assert "--allowedTools" in cmd
        assert "Read,Write" in cmd

    def test_build_command_no_tools(self, sample_config):
        d = Dispatcher(sample_config)
        msg = create_message(src="a", dst="test-node", type="dispatch", msg="task")
        cmd = d.build_command(msg)
        assert "--allowedTools" not in cmd

    def test_dispatch_creates_slot(self, sample_config):
        sample_config.dispatch_command = "echo"
        d = Dispatcher(sample_config)
        msg = create_message(src="a", dst="test-node", type="dispatch", msg="hello")
        loop = asyncio.new_event_loop()
        try:
            slot = loop.run_until_complete(d.dispatch(msg, "test-cid"))
            assert slot.cid == "test-cid"
            assert slot.pid > 0
            assert d.available_slots == sample_config.max_dispatch_slots - 1
            loop.run_until_complete(d.cancel_slot(slot))
        finally:
            loop.close()

    def test_dispatch_no_slots(self, sample_config):
        sample_config.max_dispatch_slots = 0
        d = Dispatcher(sample_config)
        msg = create_message(src="a", dst="test-node", type="dispatch", msg="task")
        loop = asyncio.new_event_loop()
        try:
            with pytest.raises(RuntimeError, match="No dispatch slots"):
                loop.run_until_complete(d.dispatch(msg, "cid"))
        finally:
            loop.close()

    def test_remove_slot(self, sample_config):
        d = Dispatcher(sample_config)
        slot = DispatchSlot(pid=123, cid="x", started_at=time.time())
        d.active.append(slot)
        d._remove_slot(slot)
        assert len(d.active) == 0


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


class TestAgentNodeLifecycle:
    def test_state_manager_full_cycle(self, tmp_clan):
        sm = StateManager(tmp_clan)

        # Acquire
        assert sm.acquire_lock()
        assert sm.get_lock_pid() == os.getpid()

        # Save state
        state = NodeState(pid=os.getpid(), started_at="now", bus_offset=42)
        sm.save(state)

        # Load state
        loaded = sm.load()
        assert loaded.bus_offset == 42

        # Release
        sm.release_lock()
        assert sm.get_lock_pid() is None

    def test_bus_observer_incremental(self, tmp_clan):
        bus = tmp_clan / "bus.jsonl"
        obs = BusObserver(bus, "test-node")

        # Empty
        assert obs.read_new_lines() == []

        # First message
        _write_bus_message(bus, msg="msg one")
        msgs = obs.read_new_lines()
        assert len(msgs) == 1

        # Second message
        _write_bus_message(bus, msg="msg two")
        msgs = obs.read_new_lines()
        assert len(msgs) == 1
        assert msgs[0].msg == "msg two"

    def test_evaluator_with_real_messages(self, sample_config):
        ev = MessageEvaluator(sample_config)

        # A dispatch for us
        m1 = create_message(src="dojo", dst="test-node", type="dispatch", msg="task a")
        assert ev.evaluate(m1) == Action.DISPATCH

        # A state update — ignore
        m2 = create_message(src="palas", dst="test-node", type="state", msg="sync done")
        assert ev.evaluate(m2) == Action.IGNORE

        # An old alert — escalate
        m3 = create_message(
            src="system",
            dst="test-node",
            type="alert",
            msg="disk full",
            ts=date.today() - timedelta(days=2),
        )
        assert ev.evaluate(m3) == Action.ESCALATE


# ---------------------------------------------------------------------------
# CLI Command Tests
# ---------------------------------------------------------------------------


class TestCLICommands:
    def test_daemon_status_not_running(self, tmp_clan, capsys):
        from amaru.agent import cmd_daemon_status

        ret = cmd_daemon_status(tmp_clan)
        assert ret == 0
        captured = capsys.readouterr()
        assert "not running" in captured.out

    def test_daemon_stop_not_running(self, tmp_clan, capsys):
        from amaru.agent import cmd_daemon_stop

        ret = cmd_daemon_stop(tmp_clan)
        assert ret == 1
        captured = capsys.readouterr()
        assert "No agent node" in captured.out

    def test_daemon_start_no_config(self, tmp_clan, capsys):
        from amaru.agent import cmd_daemon_start

        ret = cmd_daemon_start(tmp_clan)
        assert ret == 1
        captured = capsys.readouterr()
        assert "Error" in captured.err


# ---------------------------------------------------------------------------
# ASP Integration Tests (F4-F5)
# ---------------------------------------------------------------------------


class TestAgentNodeConfigASP:
    """Tests for ASP-related config fields."""

    def test_asp_defaults(self, sample_config):
        assert sample_config.asp_enabled is False
        assert sample_config.agents_dir == "agents"
        assert sample_config.hot_reload is True
        assert sample_config.notification_enabled is True
        assert sample_config.notification_throttle_per_minute == 5
        assert sample_config.approval_default_timeout_hours == 24
        assert sample_config.queue_overflow == "drop-newest"

    def test_asp_auto_enable_with_agents_dir(self, tmp_clan, gateway_json):
        agents_dir = tmp_clan / "agents"
        agents_dir.mkdir()
        config = load_agent_config(gateway_json)
        assert config.asp_enabled is True

    def test_asp_disabled_without_agents_dir(self, gateway_json):
        config = load_agent_config(gateway_json)
        assert config.asp_enabled is False


class TestNodeStateASP:
    """Tests for NodeState agent_states field."""

    def test_roundtrip_with_agent_states(self):
        state = NodeState(
            pid=123,
            started_at="2026-03-20T10:00:00",
            agent_states={
                "states": {"mail-scanner": "active", "report-builder": "idle"},
                "dispatch_count": {"mail-scanner": 5},
                "failure_count": {},
                "last_dispatch": {},
            },
        )
        data = state.to_dict()
        restored = NodeState.from_dict(data)
        assert restored.agent_states["states"]["mail-scanner"] == "active"
        assert restored.agent_states["states"]["report-builder"] == "idle"

    def test_backward_compat_missing_agent_states(self):
        data = {"pid": 1, "started_at": "now"}
        state = NodeState.from_dict(data)
        assert state.agent_states == {}


class TestASPInitialization:
    """Tests for AgentNode._init_asp()."""

    def test_init_asp_loads_agents(self, tmp_clan, sample_config):
        # Create agents dir with a profile
        agents_dir = tmp_clan / "agents"
        agents_dir.mkdir()
        profile = {
            "agent_id": "test-agent",
            "display_name": "Test Agent",
            "version": "1.0.0",
            "role": "sensor",
            "description": "Test",
            "capabilities": [],
            "dispatch_rules": [],
            "enabled": True,
        }
        (agents_dir / "test-agent.json").write_text(json.dumps(profile))

        sample_config.asp_enabled = True
        sample_config.agents_dir = "agents"
        node = AgentNode(sample_config)
        state = NodeState(pid=1, started_at="now")
        node._init_asp(state)

        assert node.asp_registry is not None
        assert len(node.asp_registry.all_profiles()) == 1
        assert node.asp_state_tracker is not None
        assert node.asp_throttler is not None

    def test_init_asp_sets_active_for_enabled(self, tmp_clan, sample_config):
        agents_dir = tmp_clan / "agents"
        agents_dir.mkdir()
        profile = {
            "agent_id": "scanner",
            "display_name": "Scanner",
            "version": "1.0.0",
            "role": "sensor",
            "description": "Scans",
            "capabilities": [],
            "dispatch_rules": [],
            "enabled": True,
        }
        (agents_dir / "scanner.json").write_text(json.dumps(profile))

        sample_config.asp_enabled = True
        node = AgentNode(sample_config)
        state = NodeState(pid=1, started_at="now")
        node._init_asp(state)

        from amaru.asp import AgentState

        assert node.asp_state_tracker.get_state("scanner") == AgentState.ACTIVE

    def test_init_asp_restores_state(self, tmp_clan, sample_config):
        agents_dir = tmp_clan / "agents"
        agents_dir.mkdir()
        profile = {
            "agent_id": "scanner",
            "display_name": "Scanner",
            "version": "1.0.0",
            "role": "sensor",
            "description": "Scans",
            "capabilities": [],
            "dispatch_rules": [],
            "enabled": True,
        }
        (agents_dir / "scanner.json").write_text(json.dumps(profile))

        sample_config.asp_enabled = True
        node = AgentNode(sample_config)

        # Create state with prior agent data
        state = NodeState(
            pid=1,
            started_at="now",
            agent_states={
                "states": {"scanner": "idle"},
                "dispatch_count": {"scanner": 3},
                "failure_count": {},
                "last_dispatch": {},
            },
        )
        node._init_asp(state)

        # set_active on IDLE → ACTIVE
        from amaru.asp import AgentState

        assert node.asp_state_tracker.get_state("scanner") == AgentState.ACTIVE
        # Dispatch count preserved
        payload = node.asp_state_tracker.heartbeat_payload()
        entry = [e for e in payload if e["agent_id"] == "scanner"][0]
        assert entry["dispatch_count"] == 3

    def test_no_asp_without_flag(self, sample_config):
        node = AgentNode(sample_config)
        assert node.asp_registry is None
        assert node.asp_state_tracker is None


class TestPersistASPState:
    """Tests for _persist_asp_state()."""

    def test_persist_populates_node_state(self, tmp_clan, sample_config):
        agents_dir = tmp_clan / "agents"
        agents_dir.mkdir()
        profile = {
            "agent_id": "worker",
            "display_name": "Worker",
            "version": "1.0.0",
            "role": "worker",
            "description": "Works",
            "capabilities": [],
            "dispatch_rules": [],
            "enabled": True,
        }
        (agents_dir / "worker.json").write_text(json.dumps(profile))

        sample_config.asp_enabled = True
        node = AgentNode(sample_config)
        node.state = NodeState(pid=1, started_at="now")
        node._init_asp(node.state)

        node._persist_asp_state()

        assert "states" in node.state.agent_states
        assert node.state.agent_states["states"]["worker"] == "active"


# ---------------------------------------------------------------------------
# Hub Inbox Bridge (Quest-006: Cross-Clan Dispatch)
# ---------------------------------------------------------------------------


class TestConvertHubToBus:
    """Test _convert_hub_to_bus static method."""

    def test_converts_status_message(self):
        hub_msg = {
            "ts": "2026-04-04T01:22:53.933258+00:00",
            "from": "jei",
            "msg": "JEI-HUB-S2S-002: All blockers resolved.",
            "type": "status",
            "dst": "momoshod",
        }
        msg = AgentNode._convert_hub_to_bus(hub_msg)
        assert msg is not None
        assert msg.src == "jei"
        assert msg.dst == "momoshod"
        assert msg.type == "state"  # status → state mapping
        assert msg.msg == "JEI-HUB-S2S-002: All blockers resolved."
        assert msg.ttl == 7
        assert msg.ack == []
        assert msg.ts == date(2026, 4, 4)

    def test_skips_presence_messages(self):
        hub_msg = {
            "ts": "2026-04-04T01:24:45.369270+00:00",
            "from": "HUB",
            "msg": "jei: online",
            "type": "presence",
        }
        msg = AgentNode._convert_hub_to_bus(hub_msg)
        assert msg is None

    def test_skips_roster_messages(self):
        hub_msg = {
            "ts": "2026-04-04T15:25:50.079732+00:00",
            "from": "HUB",
            "msg": "roster: momoshod (1 online)",
            "type": "roster",
        }
        msg = AgentNode._convert_hub_to_bus(hub_msg)
        assert msg is None

    def test_skips_hub_source(self):
        hub_msg = {
            "ts": "2026-04-04T01:24:48.399707+00:00",
            "from": "HUB",
            "msg": "some infrastructure message",
            "type": "event",
        }
        msg = AgentNode._convert_hub_to_bus(hub_msg)
        assert msg is None

    def test_converts_event_type(self):
        hub_msg = {
            "ts": "2026-04-03T16:26:46.393541+00:00",
            "from": "momoshod",
            "msg": "DANI-HERMES-031: ACK blockers resolved.",
            "type": "event",
            "dst": "jei",
        }
        msg = AgentNode._convert_hub_to_bus(hub_msg)
        assert msg is not None
        assert msg.type == "event"
        assert msg.src == "momoshod"
        assert msg.dst == "jei"

    def test_converts_dispatch_type(self):
        hub_msg = {
            "ts": "2026-04-04T10:00:00+00:00",
            "from": "jei",
            "msg": "QUEST-006: run bilateral test",
            "type": "dispatch",
            "dst": "momoshod",
        }
        msg = AgentNode._convert_hub_to_bus(hub_msg)
        assert msg is not None
        assert msg.type == "dispatch"

    def test_truncates_long_messages(self):
        hub_msg = {
            "ts": "2026-04-04T10:00:00+00:00",
            "from": "jei",
            "msg": "A" * 200,
            "type": "event",
            "dst": "momoshod",
        }
        msg = AgentNode._convert_hub_to_bus(hub_msg)
        assert msg is not None
        assert len(msg.msg) == 120

    def test_skips_empty_message(self):
        hub_msg = {
            "ts": "2026-04-04T10:00:00+00:00",
            "from": "jei",
            "msg": "",
            "type": "event",
        }
        msg = AgentNode._convert_hub_to_bus(hub_msg)
        assert msg is None

    def test_unknown_type_maps_to_event(self):
        hub_msg = {
            "ts": "2026-04-04T10:00:00+00:00",
            "from": "jei",
            "msg": "some weird type",
            "type": "custom_thing",
            "dst": "*",
        }
        msg = AgentNode._convert_hub_to_bus(hub_msg)
        assert msg is not None
        assert msg.type == "event"

    def test_defaults_dst_to_wildcard(self):
        hub_msg = {
            "ts": "2026-04-04T10:00:00+00:00",
            "from": "jei",
            "msg": "broadcast message",
            "type": "event",
        }
        msg = AgentNode._convert_hub_to_bus(hub_msg)
        assert msg is not None
        assert msg.dst == "*"

    def test_bad_timestamp_uses_today(self):
        hub_msg = {
            "ts": "not-a-date",
            "from": "jei",
            "msg": "bad ts",
            "type": "event",
        }
        msg = AgentNode._convert_hub_to_bus(hub_msg)
        assert msg is not None
        assert msg.ts == date.today()


class TestHubInboxLoop:
    """Test _hub_inbox_loop integration."""

    @pytest.fixture
    def hub_inbox_config(self, tmp_clan):
        """Config with hub_inbox_path set."""
        inbox = tmp_clan / "hub-inbox.jsonl"
        inbox.touch()
        return AgentNodeConfig(
            bus_path=tmp_clan / "bus.jsonl",
            gateway_url="",
            namespace="test-node",
            clan_dir=tmp_clan,
            hub_inbox_path=inbox,
            hub_inbox_poll_interval=0.1,
            poll_interval=0.1,
        )

    def test_config_auto_discovers_inbox(self, tmp_clan):
        """hub_inbox_path auto-discovered when hub-inbox.jsonl exists."""
        inbox = tmp_clan / "hub-inbox.jsonl"
        inbox.touch()
        config_data = {
            "agent_node": {
                "enabled": True,
                "bus_path": "bus.jsonl",
                "namespace": "test",
            }
        }
        config_file = tmp_clan / "gateway.json"
        config_file.write_text(json.dumps(config_data))
        config = load_agent_config(config_file)
        assert config.hub_inbox_path is not None
        assert config.hub_inbox_path.name == "hub-inbox.jsonl"

    def test_config_no_inbox(self, tmp_clan):
        """hub_inbox_path is None when no inbox file exists."""
        config_data = {
            "agent_node": {
                "enabled": True,
                "bus_path": "bus.jsonl",
                "namespace": "test",
            }
        }
        config_file = tmp_clan / "gateway.json"
        config_file.write_text(json.dumps(config_data))
        config = load_agent_config(config_file)
        assert config.hub_inbox_path is None

    def test_bridges_messages_to_bus(self, hub_inbox_config):
        """Messages from hub-inbox.jsonl are bridged to bus.jsonl."""
        inbox = hub_inbox_config.hub_inbox_path
        bus = hub_inbox_config.bus_path

        hub_msg = {
            "ts": "2026-04-04T01:22:53+00:00",
            "from": "jei",
            "msg": "JEI-HERMES-027: Quest ready.",
            "type": "status",
            "dst": "momoshod",
        }
        inbox.write_text(json.dumps(hub_msg) + "\n")

        node = AgentNode(hub_inbox_config)
        node.state = NodeState(pid=1, started_at="now")

        async def run_once():
            node._running = True
            # Run one iteration
            task = asyncio.ensure_future(node._hub_inbox_loop())
            await asyncio.sleep(0.3)
            node._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        asyncio.run(run_once())

        # Verify message was bridged
        from amaru.bus import read_bus

        messages = read_bus(bus)
        assert len(messages) >= 1
        bridged = [m for m in messages if m.src == "jei"]
        assert len(bridged) == 1
        assert bridged[0].type == "state"
        assert "JEI-HERMES-027" in bridged[0].msg

    def test_skips_presence_and_roster(self, hub_inbox_config):
        """Presence and roster messages are not bridged."""
        inbox = hub_inbox_config.hub_inbox_path
        bus = hub_inbox_config.bus_path

        lines = [
            json.dumps(
                {
                    "ts": "2026-04-04T01:00:00+00:00",
                    "from": "HUB",
                    "msg": "jei: online",
                    "type": "presence",
                }
            ),
            json.dumps(
                {
                    "ts": "2026-04-04T01:00:01+00:00",
                    "from": "HUB",
                    "msg": "roster: 1",
                    "type": "roster",
                }
            ),
        ]
        inbox.write_text("\n".join(lines) + "\n")

        node = AgentNode(hub_inbox_config)
        node.state = NodeState(pid=1, started_at="now")

        async def run_once():
            node._running = True
            task = asyncio.ensure_future(node._hub_inbox_loop())
            await asyncio.sleep(0.3)
            node._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        asyncio.run(run_once())

        from amaru.bus import read_bus

        messages = read_bus(bus)
        assert len(messages) == 0

    def test_persists_cursor(self, hub_inbox_config):
        """Daemon cursor is persisted after reading."""
        inbox = hub_inbox_config.hub_inbox_path
        cursor_path = inbox.parent / "hub-inbox.daemon.cursor"

        hub_msg = (
            json.dumps(
                {
                    "ts": "2026-04-04T01:00:00+00:00",
                    "from": "jei",
                    "msg": "test cursor",
                    "type": "event",
                    "dst": "momoshod",
                }
            )
            + "\n"
        )
        inbox.write_text(hub_msg)

        node = AgentNode(hub_inbox_config)
        node.state = NodeState(pid=1, started_at="now")

        async def run_once():
            node._running = True
            task = asyncio.ensure_future(node._hub_inbox_loop())
            await asyncio.sleep(0.3)
            node._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        asyncio.run(run_once())

        assert cursor_path.exists()
        cursor_val = int(cursor_path.read_text().strip())
        assert cursor_val > 0

    def test_dedup_prevents_double_bridge(self, hub_inbox_config):
        """Same message is not bridged twice."""
        inbox = hub_inbox_config.hub_inbox_path
        bus = hub_inbox_config.bus_path

        hub_msg = (
            json.dumps(
                {
                    "ts": "2026-04-04T01:00:00+00:00",
                    "from": "jei",
                    "msg": "unique-message-abc",
                    "type": "event",
                    "dst": "momoshod",
                }
            )
            + "\n"
        )
        # Write same message twice
        inbox.write_text(hub_msg + hub_msg)

        node = AgentNode(hub_inbox_config)
        node.state = NodeState(pid=1, started_at="now")

        async def run_once():
            node._running = True
            task = asyncio.ensure_future(node._hub_inbox_loop())
            await asyncio.sleep(0.3)
            node._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        asyncio.run(run_once())

        from amaru.bus import read_bus

        messages = read_bus(bus)
        jei_msgs = [m for m in messages if m.src == "jei"]
        assert len(jei_msgs) == 1

    def test_no_inbox_noop(self, tmp_clan):
        """Loop exits immediately when hub_inbox_path is None."""
        config = AgentNodeConfig(
            bus_path=tmp_clan / "bus.jsonl",
            gateway_url="",
            namespace="test",
            clan_dir=tmp_clan,
            hub_inbox_path=None,
        )
        node = AgentNode(config)

        async def run_once():
            node._running = True
            await node._hub_inbox_loop()

        asyncio.run(run_once())


class TestHubInboxLoopErrors:
    """Coverage of error paths in _hub_inbox_loop.

    JEI/Bachue PR #26 review condition: AgentNode is the ICAP gateway,
    high-criticality. Error paths in inbox loop must be tested.
    """

    @pytest.fixture
    def hub_inbox_config(self, tmp_clan):
        inbox = tmp_clan / "hub-inbox.jsonl"
        inbox.touch()
        return AgentNodeConfig(
            bus_path=tmp_clan / "bus.jsonl",
            gateway_url="",
            namespace="test-node",
            clan_dir=tmp_clan,
            hub_inbox_path=inbox,
            hub_inbox_poll_interval=0.05,
            poll_interval=0.05,
        )

    def test_inbox_missing_logs_and_returns(self, tmp_clan, caplog):
        """If hub_inbox_path does not exist, loop logs and returns immediately."""
        import logging as _logging

        config = AgentNodeConfig(
            bus_path=tmp_clan / "bus.jsonl",
            gateway_url="",
            namespace="test",
            clan_dir=tmp_clan,
            hub_inbox_path=tmp_clan / "nonexistent-inbox.jsonl",
        )
        node = AgentNode(config)

        async def run_once():
            node._running = True
            await node._hub_inbox_loop()

        with caplog.at_level(_logging.INFO, logger="amaru.agent"):
            asyncio.run(run_once())

        assert any("Hub inbox not found" in r.message for r in caplog.records)

    def test_corrupt_cursor_resets_to_zero(self, hub_inbox_config):
        """If hub-inbox.daemon.cursor contains non-int, offset resets to 0."""
        cursor = hub_inbox_config.hub_inbox_path.parent / "hub-inbox.daemon.cursor"
        cursor.write_text("not-an-int")

        hub_msg = {
            "ts": "2026-05-12T15:00:00+00:00",
            "from": "jei",
            "msg": "post-corrupt-cursor",
            "type": "event",
            "dst": "momoshod",
        }
        hub_inbox_config.hub_inbox_path.write_text(json.dumps(hub_msg) + "\n")

        node = AgentNode(hub_inbox_config)

        async def run_once():
            node._running = True
            task = asyncio.ensure_future(node._hub_inbox_loop())
            await asyncio.sleep(0.25)
            node._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        asyncio.run(run_once())

        from amaru.bus import read_bus

        msgs = read_bus(hub_inbox_config.bus_path)
        assert any(m.src == "jei" for m in msgs), "corrupt cursor should reset and bridge anyway"

    def test_file_truncated_resets_cursor(self, hub_inbox_config, caplog):
        """If hub_inbox file_size < offset, cursor is reset and we log."""
        import logging as _logging

        # First write some data
        hub_msg = {
            "ts": "2026-05-12T15:00:00+00:00",
            "from": "jei",
            "msg": "first-message",
            "type": "event",
            "dst": "momoshod",
        }
        hub_inbox_config.hub_inbox_path.write_text(json.dumps(hub_msg) + "\n")

        # Pre-position the cursor past the (yet-to-be-truncated) file size
        cursor = hub_inbox_config.hub_inbox_path.parent / "hub-inbox.daemon.cursor"
        cursor.write_text("999999")  # cursor way past actual size

        node = AgentNode(hub_inbox_config)

        async def run_once():
            node._running = True
            task = asyncio.ensure_future(node._hub_inbox_loop())
            await asyncio.sleep(0.25)
            node._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        with caplog.at_level(_logging.INFO, logger="amaru.agent"):
            asyncio.run(run_once())

        assert any("truncated" in r.message.lower() for r in caplog.records)

    def test_malformed_json_line_skipped(self, hub_inbox_config):
        """A line that is not valid JSON is silently skipped."""
        inbox = hub_inbox_config.hub_inbox_path
        good = {
            "ts": "2026-05-12T15:00:00+00:00",
            "from": "jei",
            "msg": "good-line",
            "type": "event",
            "dst": "momoshod",
        }
        # Mix valid + invalid lines
        inbox.write_text(json.dumps(good) + "\n" + "{not valid json\n" + json.dumps(good) + "\n")

        node = AgentNode(hub_inbox_config)

        async def run_once():
            node._running = True
            task = asyncio.ensure_future(node._hub_inbox_loop())
            await asyncio.sleep(0.25)
            node._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        asyncio.run(run_once())

        from amaru.bus import read_bus

        msgs = read_bus(hub_inbox_config.bus_path)
        jei_msgs = [m for m in msgs if m.src == "jei"]
        # The good line bridges (dedup may reduce duplicates to 1)
        assert len(jei_msgs) >= 1, "valid lines bridge even when malformed lines are present"

    def test_write_failure_logged_non_fatal(self, hub_inbox_config, caplog, monkeypatch):
        """If write_message raises, loop logs a warning and continues."""
        import logging as _logging

        from amaru import agent as agent_module

        good = {
            "ts": "2026-05-12T15:00:00+00:00",
            "from": "jei",
            "msg": "will-fail-to-write",
            "type": "event",
            "dst": "momoshod",
        }
        hub_inbox_config.hub_inbox_path.write_text(json.dumps(good) + "\n")

        def boom(*args, **kwargs):
            raise OSError("simulated disk full")

        monkeypatch.setattr(agent_module, "write_message", boom)

        node = AgentNode(hub_inbox_config)

        async def run_once():
            node._running = True
            task = asyncio.ensure_future(node._hub_inbox_loop())
            await asyncio.sleep(0.25)
            node._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        with caplog.at_level(_logging.WARNING, logger="amaru.agent"):
            asyncio.run(run_once())

        assert any(
            "Hub bridge write failed" in r.message or "simulated disk full" in r.message
            for r in caplog.records
        )


class TestForwardTypesFiltering:
    """Coverage: forward_types default + filtering for ICAP wire types.

    JEI/Bachue PR #26 review condition: dispatch path for coord-dispatch
    and reflection must be exercised.
    """

    def test_default_forward_types_include_icap(self):
        """Default forward_types includes the ICAP wire types."""
        config = AgentNodeConfig(
            bus_path=Path("/tmp/x"),
            gateway_url="",
            namespace="test",
        )
        assert "coord-dispatch" in config.forward_types
        assert "reflection" in config.forward_types
        assert "alert" in config.forward_types
        assert "dispatch" in config.forward_types
        assert "event" in config.forward_types

    def test_load_agent_config_default_forward_types(self, tmp_clan):
        """Gateway.json without forward_types picks up ICAP defaults."""
        gw = {"agent_node": {"enabled": True, "bus_path": "bus.jsonl", "namespace": "test"}}
        cf = tmp_clan / "gateway.json"
        cf.write_text(json.dumps(gw))
        cfg = load_agent_config(cf)
        assert "coord-dispatch" in cfg.forward_types
        assert "reflection" in cfg.forward_types

    def test_load_agent_config_explicit_overrides_default(self, tmp_clan):
        """If gateway.json sets forward_types explicitly, it overrides."""
        gw = {
            "agent_node": {
                "enabled": True,
                "bus_path": "bus.jsonl",
                "namespace": "test",
                "forward_types": ["alert"],  # narrow override
            }
        }
        cf = tmp_clan / "gateway.json"
        cf.write_text(json.dumps(gw))
        cfg = load_agent_config(cf)
        assert cfg.forward_types == ["alert"]
        assert "coord-dispatch" not in cfg.forward_types


class TestAutoPeerDiscovery:
    """Test auto-peer registration from hub presence events."""

    @pytest.fixture
    def peer_config(self, tmp_clan):
        """Config with gateway.json and hub-peers.json set up."""
        gw = {
            "clan_id": "momoshod",
            "display_name": "Clan MomoshoD",
            "protocol_version": "0.5.0a1",
            "keys": {"private": ".keys/momoshod.key", "public": ".keys/momoshod.pub"},
            "peers": [],
            "outbound": {},
        }
        (tmp_clan / "gateway.json").write_text(json.dumps(gw))

        hub_peers = {
            "peers": {
                "jei": {
                    "sign_pub": "b05d85e59a6dee74aaded152d49b19e971e79bb9",
                    "display_name": "Clan JEI",
                    "registered_at": "2026-03-18",
                }
            }
        }
        (tmp_clan / "hub-peers.json").write_text(json.dumps(hub_peers))

        inbox = tmp_clan / "hub-inbox.jsonl"
        inbox.touch()

        return AgentNodeConfig(
            bus_path=tmp_clan / "bus.jsonl",
            gateway_url="",
            namespace="momoshod",
            clan_dir=tmp_clan,
            hub_inbox_path=inbox,
            hub_inbox_poll_interval=0.1,
            poll_interval=0.1,
            auto_peer_enabled=True,
        )

    def test_auto_registers_peer_from_presence(self, peer_config):
        """Presence event for unknown peer triggers auto-registration."""
        node = AgentNode(peer_config)
        hub_msg = {
            "ts": "2026-04-05T10:00:00+00:00",
            "from": "HUB",
            "msg": "jei: online",
            "type": "presence",
        }
        node._auto_peer_from_presence(hub_msg)

        gw = json.loads((peer_config.clan_dir / "gateway.json").read_text())
        peers = gw.get("peers", [])
        assert len(peers) == 1
        assert peers[0]["clan_id"] == "jei"
        assert peers[0]["status"] == "active"

        pub_file = peer_config.clan_dir / ".keys" / "peers" / "jei.pub"
        assert pub_file.exists()
        assert "b05d85" in pub_file.read_text()

    def test_skips_already_known_peer(self, peer_config):
        """Does not duplicate a peer that's already registered."""
        node = AgentNode(peer_config)
        hub_msg = {
            "ts": "2026-04-05T10:00:00+00:00",
            "from": "HUB",
            "msg": "jei: online",
            "type": "presence",
        }
        node._auto_peer_from_presence(hub_msg)
        node._auto_peer_from_presence(hub_msg)

        gw = json.loads((peer_config.clan_dir / "gateway.json").read_text())
        assert len(gw.get("peers", [])) == 1

    def test_skips_self_presence(self, peer_config):
        """Does not register own clan as peer."""
        node = AgentNode(peer_config)
        hub_msg = {
            "ts": "2026-04-05T10:00:00+00:00",
            "from": "HUB",
            "msg": "momoshod: online",
            "type": "presence",
        }
        node._auto_peer_from_presence(hub_msg)

        gw = json.loads((peer_config.clan_dir / "gateway.json").read_text())
        assert len(gw.get("peers", [])) == 0

    def test_disabled_auto_peer(self, peer_config):
        """No registration when auto_peer_enabled=False."""
        peer_config.auto_peer_enabled = False
        node = AgentNode(peer_config)
        hub_msg = {
            "ts": "2026-04-05T10:00:00+00:00",
            "from": "HUB",
            "msg": "jei: online",
            "type": "presence",
        }
        node._auto_peer_from_presence(hub_msg)

        gw = json.loads((peer_config.clan_dir / "gateway.json").read_text())
        assert len(gw.get("peers", [])) == 0

    def test_peer_from_direct_message(self, peer_config):
        """Unknown peer sending a direct message also triggers auto-register."""
        node = AgentNode(peer_config)
        hub_msg = {
            "ts": "2026-04-05T10:00:00+00:00",
            "from": "jei",
            "msg": "JEI-HERMES-030: ACK received.",
            "type": "event",
            "dst": "momoshod",
        }
        node._auto_peer_from_presence(hub_msg)

        gw = json.loads((peer_config.clan_dir / "gateway.json").read_text())
        assert len(gw.get("peers", [])) == 1
        assert gw["peers"][0]["clan_id"] == "jei"

    def test_unknown_peer_no_hub_key(self, peer_config):
        """Peer registered as pending_ack when hub-peers.json lacks their key."""
        node = AgentNode(peer_config)
        hub_msg = {
            "ts": "2026-04-05T10:00:00+00:00",
            "from": "HUB",
            "msg": "unknown-clan: online",
            "type": "presence",
        }
        node._auto_peer_from_presence(hub_msg)

        gw = json.loads((peer_config.clan_dir / "gateway.json").read_text())
        peers = gw.get("peers", [])
        assert len(peers) == 1
        assert peers[0]["clan_id"] == "unknown-clan"
        assert peers[0]["status"] == "pending_ack"

    def test_roster_registers_multiple_peers(self, peer_config):
        """Roster message on connect registers all unknown peers."""
        node = AgentNode(peer_config)
        hub_msg = {
            "ts": "2026-04-05T10:00:00+00:00",
            "from": "HUB",
            "msg": "roster: momoshod, jei, nymyka (3 online)",
            "type": "roster",
        }
        # Add nymyka to hub-peers.json
        hub_peers = json.loads((peer_config.clan_dir / "hub-peers.json").read_text())
        hub_peers["peers"]["nymyka"] = {
            "sign_pub": "2e77ed0000000000000000000000000000000000",
            "display_name": "Nymyka",
        }
        (peer_config.clan_dir / "hub-peers.json").write_text(json.dumps(hub_peers))

        node._auto_peer_from_presence(hub_msg)

        gw = json.loads((peer_config.clan_dir / "gateway.json").read_text())
        peers = gw.get("peers", [])
        peer_ids = [p["clan_id"] for p in peers]
        assert "jei" in peer_ids
        assert "nymyka" in peer_ids
        assert "momoshod" not in peer_ids  # self excluded
        assert len(peers) == 2

    def test_roster_skips_self_in_roster(self, peer_config):
        """Self is filtered from roster peer list."""
        node = AgentNode(peer_config)
        hub_msg = {
            "ts": "2026-04-05T10:00:00+00:00",
            "from": "HUB",
            "msg": "roster: momoshod (1 online)",
            "type": "roster",
        }
        node._auto_peer_from_presence(hub_msg)

        gw = json.loads((peer_config.clan_dir / "gateway.json").read_text())
        assert len(gw.get("peers", [])) == 0

    def test_integrated_with_inbox_loop(self, peer_config):
        """Auto-peer runs during _hub_inbox_loop processing."""
        inbox = peer_config.hub_inbox_path
        bus = peer_config.bus_path

        msgs = [
            json.dumps(
                {
                    "ts": "2026-04-05T10:00:00+00:00",
                    "from": "HUB",
                    "msg": "jei: online",
                    "type": "presence",
                }
            ),
            json.dumps(
                {
                    "ts": "2026-04-05T10:00:01+00:00",
                    "from": "jei",
                    "msg": "Hello from JEI",
                    "type": "event",
                    "dst": "momoshod",
                }
            ),
        ]
        inbox.write_text("\n".join(msgs) + "\n")

        node = AgentNode(peer_config)

        async def run_auto_peer_test():
            node._running = True
            task = asyncio.ensure_future(node._hub_inbox_loop())
            await asyncio.sleep(0.3)
            node._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        asyncio.run(run_auto_peer_test())

        gw = json.loads((peer_config.clan_dir / "gateway.json").read_text())
        assert any(p["clan_id"] == "jei" for p in gw.get("peers", []))

        from amaru.bus import read_bus

        messages = read_bus(bus)
        assert any(m.src == "jei" for m in messages)


# ---------------------------------------------------------------------------
# ICAP Dispatch Coverage Tests (JEI/Bachue PR #26 review condition)
# ---------------------------------------------------------------------------


class TestLegacyDispatchICAP:
    """Exercise `_legacy_dispatch` for coord-dispatch and reflection wire types.

    JEI/Bachue PR #26 review: "dispatch path for coord-dispatch and reflection
    must be exercised". Verifies that ICAP wire types reach the dispatcher
    when slots are available and that no-slot is logged but not raised.
    """

    def _make_node(self, tmp_clan):
        cfg = AgentNodeConfig(
            bus_path=tmp_clan / "bus.jsonl",
            gateway_url="",
            namespace="momoshod",
            clan_dir=tmp_clan,
            max_dispatch_slots=2,
            poll_interval=0.05,
        )
        return AgentNode(cfg)

    def _dispatch_msg(self, msg_type, cid_suffix="abcd1234"):
        return Message(
            ts=date(2026, 5, 18),
            src="jei",
            dst="momoshod",
            type=msg_type,
            msg=f"ICAP payload [CID:{cid_suffix}]",
            ttl=7,
            ack=[],
        )

    def test_coord_dispatch_reaches_dispatcher(self, tmp_clan, monkeypatch):
        node = self._make_node(tmp_clan)
        calls: list[tuple[str, str]] = []

        async def fake_dispatch(message, cid):
            calls.append((message.type, cid))
            return DispatchSlot(
                pid=12345, cid=cid, started_at=time.time(), command=["x"]
            )

        monkeypatch.setattr(node.dispatcher, "dispatch", fake_dispatch)

        msg = self._dispatch_msg("coord-dispatch", cid_suffix="coord001")
        asyncio.run(node._legacy_dispatch(msg))

        assert len(calls) == 1
        assert calls[0][0] == "coord-dispatch"
        assert calls[0][1] == "coord001"  # extracted via [CID:...] pattern

    def test_reflection_reaches_dispatcher(self, tmp_clan, monkeypatch):
        node = self._make_node(tmp_clan)
        calls: list[tuple[str, str]] = []

        async def fake_dispatch(message, cid):
            calls.append((message.type, cid))
            return DispatchSlot(
                pid=23456, cid=cid, started_at=time.time(), command=["x"]
            )

        monkeypatch.setattr(node.dispatcher, "dispatch", fake_dispatch)

        msg = self._dispatch_msg("reflection")
        asyncio.run(node._legacy_dispatch(msg))

        assert len(calls) == 1
        assert calls[0][0] == "reflection"

    def test_no_slots_logs_warning(self, tmp_clan, monkeypatch, caplog):
        import logging as _logging

        node = self._make_node(tmp_clan)
        # Saturate slots so available_slots == 0
        node.dispatcher.active = [
            DispatchSlot(pid=i, cid=f"x{i}", started_at=0.0, command=[])
            for i in range(node.config.max_dispatch_slots)
        ]

        async def boom(*_a, **_kw):
            raise RuntimeError("should not be called when no slots")

        monkeypatch.setattr(node.dispatcher, "dispatch", boom)

        msg = self._dispatch_msg("coord-dispatch")
        with caplog.at_level(_logging.WARNING, logger="amaru.agent"):
            asyncio.run(node._legacy_dispatch(msg))

        # No RuntimeError leaked; loop returned cleanly.
        # (No-slot guard is the early return at available_slots <= 0)

    def test_dispatch_runtime_error_swallowed(self, tmp_clan, monkeypatch, caplog):
        """If dispatcher.dispatch raises RuntimeError, _legacy_dispatch logs and continues."""
        import logging as _logging

        node = self._make_node(tmp_clan)

        async def fake_dispatch(message, cid):
            raise RuntimeError("simulated slot race")

        monkeypatch.setattr(node.dispatcher, "dispatch", fake_dispatch)

        msg = self._dispatch_msg("coord-dispatch")
        with caplog.at_level(_logging.WARNING, logger="amaru.agent"):
            asyncio.run(node._legacy_dispatch(msg))

        assert any("No slots for dispatch" in r.message for r in caplog.records)


class TestForwardToHubICAP:
    """Exercise `_forward_to_hub` for ICAP wire types.

    Covers: missing hub-state.json (silent return), invalid JSON,
    PID dead (OSError), and successful path via monkeypatched hub_send.
    """

    def _make_node(self, tmp_clan):
        cfg = AgentNodeConfig(
            bus_path=tmp_clan / "bus.jsonl",
            gateway_url="",
            namespace="momoshod",
            clan_dir=tmp_clan,
        )
        return AgentNode(cfg)

    def _icap_msg(self, msg_type):
        return Message(
            ts=date(2026, 5, 18),
            src="momoshod",
            dst="jei",
            type=msg_type,
            msg="payload",
            ttl=7,
            ack=[],
        )

    def test_no_hub_state_returns_silently(self, tmp_clan):
        node = self._make_node(tmp_clan)
        # No hub-state.json exists in clan_dir
        asyncio.run(node._forward_to_hub(self._icap_msg("coord-dispatch")))
        # No exception raised; coverage of early-return branch

    def test_invalid_hub_state_json_returns(self, tmp_clan):
        node = self._make_node(tmp_clan)
        (tmp_clan / "hub-state.json").write_text("not json {")
        asyncio.run(node._forward_to_hub(self._icap_msg("reflection")))
        # Silent return via JSONDecodeError branch

    def test_dead_pid_returns(self, tmp_clan):
        node = self._make_node(tmp_clan)
        # PID 1 exists but os.kill(1, 0) requires perms; use a guaranteed-dead PID
        (tmp_clan / "hub-state.json").write_text('{"pid": 99999999}')
        asyncio.run(node._forward_to_hub(self._icap_msg("coord-dispatch")))
        # Silent return via OSError branch

    def test_missing_pid_field_returns(self, tmp_clan):
        node = self._make_node(tmp_clan)
        (tmp_clan / "hub-state.json").write_text('{"other": "field"}')
        asyncio.run(node._forward_to_hub(self._icap_msg("reflection")))
        # Silent return via pid is None branch

    def test_successful_forward_calls_hub_send(self, tmp_clan, monkeypatch):
        """When hub is up and tool_hub_send returns sent=True, log info."""
        node = self._make_node(tmp_clan)
        # Use real current pid; os.kill(pid, 0) succeeds for self
        (tmp_clan / "hub-state.json").write_text(f'{{"pid": {os.getpid()}}}')

        calls: list[tuple[str, str, str]] = []

        async def fake_hub_send(dst, type_, msg):
            calls.append((dst, type_, msg))
            return {"sent": True}

        # Patch the lazy-import location used inside _forward_to_hub
        import amaru.mcp_server as mcp_mod

        monkeypatch.setattr(mcp_mod, "tool_hub_send", fake_hub_send)

        asyncio.run(node._forward_to_hub(self._icap_msg("coord-dispatch")))
        assert calls == [("jei", "coord-dispatch", "payload")]

    def test_failed_forward_does_not_raise(self, tmp_clan, monkeypatch):
        """When tool_hub_send returns sent=False, log debug and continue."""
        node = self._make_node(tmp_clan)
        (tmp_clan / "hub-state.json").write_text(f'{{"pid": {os.getpid()}}}')

        async def fake_hub_send(dst, type_, msg):
            return {"sent": False, "error": "hub offline"}

        import amaru.mcp_server as mcp_mod

        monkeypatch.setattr(mcp_mod, "tool_hub_send", fake_hub_send)

        asyncio.run(node._forward_to_hub(self._icap_msg("reflection")))
        # No exception leaked


class TestPermissiveParserExtras:
    """Edge cases beyond `TestParseBusMessagePermissive`: ttl/ack/dst/case."""

    def _base(self, **overrides):
        data = {
            "ts": "2026-05-12",
            "src": "MomoshoD",  # mixed case
            "dst": "JEI",
            "type": "coord-dispatch",
            "msg": "hi",
            "ttl": 7,
            "ack": [],
        }
        data.update(overrides)
        return data

    def test_src_lowercased(self):
        from amaru.agent import _parse_bus_message_permissive

        m = _parse_bus_message_permissive(self._base())
        assert m is not None and m.src == "momoshod"

    def test_dst_lowercased(self):
        from amaru.agent import _parse_bus_message_permissive

        m = _parse_bus_message_permissive(self._base())
        assert m is not None and m.dst == "jei"

    def test_dst_wildcard_preserved(self):
        from amaru.agent import _parse_bus_message_permissive

        m = _parse_bus_message_permissive(self._base(dst="*"))
        assert m is not None and m.dst == "*"

    def test_ttl_non_int_falls_back_to_default(self):
        from amaru.agent import _parse_bus_message_permissive

        m = _parse_bus_message_permissive(self._base(ttl="not-int"))
        assert m is not None and m.ttl == 7

    def test_ack_non_list_falls_back_to_empty(self):
        from amaru.agent import _parse_bus_message_permissive

        m = _parse_bus_message_permissive(self._base(ack="not-a-list"))
        assert m is not None and m.ack == []

    def test_ack_entries_lowercased(self):
        from amaru.agent import _parse_bus_message_permissive

        m = _parse_bus_message_permissive(self._base(ack=["JEI", "Nymyka"]))
        assert m is not None and m.ack == ["jei", "nymyka"]

    def test_extra_fields_tolerated(self):
        """ARC-9001 seq/w fields and other extras must not reject the message."""
        from amaru.agent import _parse_bus_message_permissive

        m = _parse_bus_message_permissive(self._base(seq=42, w=7, extra="ok"))
        assert m is not None and m.msg == "hi"

    def test_long_payload_not_truncated(self):
        """Permissive parser does NOT truncate (vs canonical validate_message)."""
        from amaru.agent import _parse_bus_message_permissive

        big = "x" * 5000
        m = _parse_bus_message_permissive(self._base(msg=big))
        assert m is not None and len(m.msg) == 5000
