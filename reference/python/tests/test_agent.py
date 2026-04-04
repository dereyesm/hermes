"""Tests for HERMES Agent Node — ARC-4601 Reference Implementation."""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import date, timedelta
from pathlib import Path

import pytest

from hermes.agent import (
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
from hermes.message import Message, create_message

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
        assert config.forward_types == ["alert", "dispatch", "event"]


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
        from hermes.agent import cmd_daemon_status

        ret = cmd_daemon_status(tmp_clan)
        assert ret == 0
        captured = capsys.readouterr()
        assert "not running" in captured.out

    def test_daemon_stop_not_running(self, tmp_clan, capsys):
        from hermes.agent import cmd_daemon_stop

        ret = cmd_daemon_stop(tmp_clan)
        assert ret == 1
        captured = capsys.readouterr()
        assert "No agent node" in captured.out

    def test_daemon_start_no_config(self, tmp_clan, capsys):
        from hermes.agent import cmd_daemon_start

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

        from hermes.asp import AgentState

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
        from hermes.asp import AgentState

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
        from hermes.bus import read_bus
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
            json.dumps({"ts": "2026-04-04T01:00:00+00:00", "from": "HUB", "msg": "jei: online", "type": "presence"}),
            json.dumps({"ts": "2026-04-04T01:00:01+00:00", "from": "HUB", "msg": "roster: 1", "type": "roster"}),
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

        from hermes.bus import read_bus
        messages = read_bus(bus)
        assert len(messages) == 0

    def test_persists_cursor(self, hub_inbox_config):
        """Daemon cursor is persisted after reading."""
        inbox = hub_inbox_config.hub_inbox_path
        cursor_path = inbox.parent / "hub-inbox.daemon.cursor"

        hub_msg = json.dumps({
            "ts": "2026-04-04T01:00:00+00:00",
            "from": "jei",
            "msg": "test cursor",
            "type": "event",
            "dst": "momoshod",
        }) + "\n"
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

        hub_msg = json.dumps({
            "ts": "2026-04-04T01:00:00+00:00",
            "from": "jei",
            "msg": "unique-message-abc",
            "type": "event",
            "dst": "momoshod",
        }) + "\n"
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

        from hermes.bus import read_bus
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
