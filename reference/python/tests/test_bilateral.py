"""Bilateral integration tests — Tier 1: Single Hub, Two Peers.

Tests real WebSocket connections between two peers through a hub server,
all running on the same machine via asyncio. No mocks, no subprocesses.

These tests validate the exact code paths that fail during LAN bilateral
sessions with JEI — the gap that caused QUEST-006-FINAL bridge failures
and ping storm cascading issues.
"""

from __future__ import annotations

import asyncio
import json
import random

import pytest

from hermes.hub import HubConfig, HubServer
from tests.conftest import (
    _generate_keys,
    connect_hub_client,
)


# ---------------------------------------------------------------------------
# Async runner helper — wraps async test body in asyncio.run()
# ---------------------------------------------------------------------------

def _run(coro):
    """Run an async coroutine in a fresh event loop."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _start_hub(clan_factory, alice_pub: str, bob_pub: str, port: int):
    """Start a hub server with alice and bob registered as peers."""
    hub_info = clan_factory("hub-op", port, {"alice": alice_pub, "bob": bob_pub})
    config = HubConfig(
        listen_host="127.0.0.1",
        listen_port=port,
        auth_timeout=5,
        max_queue_depth=100,
    )
    server = HubServer(config, hub_info.dir)
    task = asyncio.create_task(server.start())
    await asyncio.sleep(0.15)
    return server, task


async def _drain(client, timeout=0.3):
    """Drain all pending frames from a client."""
    try:
        while True:
            await asyncio.wait_for(client.ws.recv(), timeout=timeout)
    except (TimeoutError, asyncio.TimeoutError):
        pass


async def _cleanup(server, task, *clients):
    """Clean up hub server and clients."""
    for c in clients:
        try:
            await c.close()
        except Exception:
            pass
    await server.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


# ---------------------------------------------------------------------------
# Tier 1: Single Hub, Two Peers
# ---------------------------------------------------------------------------


class TestMessageDelivery:
    """Test basic message routing between two peers through a hub."""

    def test_alice_sends_bob_receives(self, clan_factory):
        """Messages sent from alice to bob are delivered correctly."""
        async def _test():
            alice_key, alice_pub = _generate_keys()
            bob_key, bob_pub = _generate_keys()
            port = random.randint(19000, 19999)

            server, task = await _start_hub(clan_factory, alice_pub, bob_pub, port)
            try:
                uri = f"ws://127.0.0.1:{port}"
                alice = await connect_hub_client(uri, "alice", alice_key)
                bob = await connect_hub_client(uri, "bob", bob_key)
                await _drain(alice)
                await _drain(bob)

                await alice.send_msg("bob", "event", "QUEST-TEST-001: hello from alice")

                frame = await bob.recv_until("msg", timeout=3.0)
                assert frame["type"] == "msg"
                payload = frame["payload"]
                assert payload["src"] == "alice"
                assert payload["dst"] == "bob"
                assert payload["msg"] == "QUEST-TEST-001: hello from alice"
                assert payload["type"] == "event"
            finally:
                await _cleanup(server, task, alice, bob)

        _run(_test())

    def test_bidirectional_exchange(self, clan_factory):
        """Both peers can send and receive messages simultaneously."""
        async def _test():
            alice_key, alice_pub = _generate_keys()
            bob_key, bob_pub = _generate_keys()
            port = random.randint(19000, 19999)

            server, task = await _start_hub(clan_factory, alice_pub, bob_pub, port)
            try:
                uri = f"ws://127.0.0.1:{port}"
                alice = await connect_hub_client(uri, "alice", alice_key)
                bob = await connect_hub_client(uri, "bob", bob_key)
                await _drain(alice)
                await _drain(bob)

                await alice.send_msg("bob", "event", "alice-to-bob")
                await bob.send_msg("alice", "event", "bob-to-alice")

                bob_frame = await bob.recv_until("msg", timeout=3.0)
                assert bob_frame["payload"]["msg"] == "alice-to-bob"

                alice_frame = await alice.recv_until("msg", timeout=3.0)
                assert alice_frame["payload"]["msg"] == "bob-to-alice"
            finally:
                await _cleanup(server, task, alice, bob)

        _run(_test())

    def test_dispatch_type_preserved(self, clan_factory):
        """Dispatch messages (the type used for quests) route correctly."""
        async def _test():
            alice_key, alice_pub = _generate_keys()
            bob_key, bob_pub = _generate_keys()
            port = random.randint(19000, 19999)

            server, task = await _start_hub(clan_factory, alice_pub, bob_pub, port)
            try:
                uri = f"ws://127.0.0.1:{port}"
                alice = await connect_hub_client(uri, "alice", alice_key)
                bob = await connect_hub_client(uri, "bob", bob_key)
                await _drain(alice)
                await _drain(bob)

                await alice.send_msg("bob", "dispatch", "QUEST-007: test dispatch")

                frame = await bob.recv_until("msg", timeout=3.0)
                assert frame["payload"]["type"] == "dispatch"
                assert frame["payload"]["msg"] == "QUEST-007: test dispatch"
            finally:
                await _cleanup(server, task, alice, bob)

        _run(_test())


class TestOfflineQueueDrain:
    """Test store-and-forward: messages queued for offline peers."""

    def test_peer_offline_then_reconnect(self, clan_factory):
        """Messages sent to an offline peer are delivered when they reconnect."""
        async def _test():
            alice_key, alice_pub = _generate_keys()
            bob_key, bob_pub = _generate_keys()
            port = random.randint(19000, 19999)

            server, task = await _start_hub(clan_factory, alice_pub, bob_pub, port)
            try:
                uri = f"ws://127.0.0.1:{port}"

                alice = await connect_hub_client(uri, "alice", alice_key)
                await _drain(alice)

                for i in range(3):
                    await alice.send_msg("bob", "event", f"queued-msg-{i}")

                await asyncio.sleep(0.1)

                bob = await connect_hub_client(uri, "bob", bob_key)

                received_msgs = []
                try:
                    while True:
                        raw = await asyncio.wait_for(bob.ws.recv(), timeout=1.0)
                        parsed = json.loads(raw)
                        if parsed.get("type") == "drain":
                            for m in parsed.get("messages", []):
                                received_msgs.append(m["msg"])
                        elif parsed.get("type") == "msg":
                            received_msgs.append(parsed["payload"]["msg"])
                except (TimeoutError, asyncio.TimeoutError):
                    pass

                assert len(received_msgs) >= 3, f"Expected 3+ messages, got {received_msgs}"
                for i in range(3):
                    assert f"queued-msg-{i}" in received_msgs
            finally:
                await _cleanup(server, task, alice, bob)

        _run(_test())


class TestPresence:
    """Test presence notifications between peers."""

    def test_peer_connect_presence(self, clan_factory):
        """When bob connects, alice receives a presence notification."""
        async def _test():
            alice_key, alice_pub = _generate_keys()
            bob_key, bob_pub = _generate_keys()
            port = random.randint(19000, 19999)

            server, task = await _start_hub(clan_factory, alice_pub, bob_pub, port)
            try:
                uri = f"ws://127.0.0.1:{port}"

                alice = await connect_hub_client(uri, "alice", alice_key)
                await _drain(alice)

                bob = await connect_hub_client(uri, "bob", bob_key)
                await _drain(bob)

                frame = await alice.recv_until("presence", timeout=3.0)
                assert frame["clan_id"] == "bob"
                assert frame["status"] == "online"
            finally:
                await _cleanup(server, task, alice, bob)

        _run(_test())

    def test_peer_disconnect_presence(self, clan_factory):
        """When bob disconnects, alice receives an offline presence."""
        async def _test():
            alice_key, alice_pub = _generate_keys()
            bob_key, bob_pub = _generate_keys()
            port = random.randint(19000, 19999)

            server, task = await _start_hub(clan_factory, alice_pub, bob_pub, port)
            try:
                uri = f"ws://127.0.0.1:{port}"

                alice = await connect_hub_client(uri, "alice", alice_key)
                bob = await connect_hub_client(uri, "bob", bob_key)
                await _drain(alice)
                await _drain(bob)

                # Drain bob's online presence
                await _drain(alice)

                await bob.close()
                await asyncio.sleep(0.15)

                frame = await alice.recv_until("presence", timeout=3.0)
                assert frame["clan_id"] == "bob"
                assert frame["status"] == "offline"
            finally:
                await _cleanup(server, task, alice)

        _run(_test())


class TestBurstProtection:
    """Test hub behavior under message bursts (ping storm prevention)."""

    def test_burst_does_not_crash_hub(self, clan_factory):
        """Sending many messages rapidly doesn't crash the hub or block peers."""
        async def _test():
            alice_key, alice_pub = _generate_keys()
            bob_key, bob_pub = _generate_keys()
            port = random.randint(19000, 19999)

            server, task = await _start_hub(clan_factory, alice_pub, bob_pub, port)
            try:
                uri = f"ws://127.0.0.1:{port}"
                alice = await connect_hub_client(uri, "alice", alice_key)
                bob = await connect_hub_client(uri, "bob", bob_key)
                await _drain(alice)
                await _drain(bob)

                for i in range(100):
                    await alice.send_msg("bob", "event", f"burst-{i}")

                await alice.send_msg("bob", "dispatch", "post-burst-test")

                received_post_burst = False
                try:
                    for _ in range(110):
                        frame = await asyncio.wait_for(bob.ws.recv(), timeout=2.0)
                        parsed = json.loads(frame)
                        if parsed.get("type") == "msg":
                            if parsed["payload"]["msg"] == "post-burst-test":
                                received_post_burst = True
                                break
                except (TimeoutError, asyncio.TimeoutError):
                    pass

                assert received_post_burst, "Hub survived burst but post-burst message not received"
            finally:
                await _cleanup(server, task, alice, bob)

        _run(_test())


class TestPeerStatusUpgrade:
    """Test pending_ack -> active upgrade (P4 fix)."""

    def test_pending_ack_upgrades_on_message(self, tmp_path):
        """Peer in pending_ack upgrades to active on receiving direct message."""
        from hermes.agent import AgentNode
        from hermes.agent import AgentNodeConfig
        from hermes.config import load_config

        clan_dir = tmp_path / "clan-upgrade"
        clan_dir.mkdir()
        (clan_dir / "bus.jsonl").touch()
        (clan_dir / "gateway.json").write_text(json.dumps({
            "clan_id": "alice",
            "display_name": "Test Alice",
            "namespace": "alice",
            "agent_node": {"hub": {"listen_port": 9999}},
            "peers": [
                {"clan_id": "bob", "public_key_file": "keys/peers/bob.pub",
                 "status": "pending_ack", "added": "2026-04-04"}
            ],
        }))
        (clan_dir / "hub-peers.json").write_text(json.dumps({
            "peers": {"bob": {"sign_pub": "bb" * 32}}
        }))
        (clan_dir / "federation-peers.json").write_text(json.dumps({
            "hubs": {}, "self": {"hub_id": "test"}
        }))

        config = load_config(clan_dir / "gateway.json")
        assert next(p for p in config.peers if p.clan_id == "bob").status == "pending_ack"

        node = AgentNode(AgentNodeConfig(
            namespace="alice", clan_dir=clan_dir,
            bus_path=clan_dir / "bus.jsonl",
            gateway_url="",
        ))

        node._auto_peer_from_presence({
            "type": "event", "from": "bob",
            "msg": "hello from bob", "ts": "2026-04-04T12:00:00Z",
        })

        config = load_config(clan_dir / "gateway.json")
        assert next(p for p in config.peers if p.clan_id == "bob").status == "active"

    def test_already_active_no_rewrite(self, tmp_path):
        """Active peer stays active without rewriting config."""
        from hermes.agent import AgentNode
        from hermes.agent import AgentNodeConfig

        clan_dir = tmp_path / "clan-active"
        clan_dir.mkdir()
        (clan_dir / "bus.jsonl").touch()
        (clan_dir / "gateway.json").write_text(json.dumps({
            "clan_id": "alice",
            "display_name": "Test Alice",
            "namespace": "alice",
            "agent_node": {"hub": {"listen_port": 9999}},
            "peers": [
                {"clan_id": "bob", "public_key_file": "keys/peers/bob.pub",
                 "status": "active", "added": "2026-04-04"}
            ],
        }))
        (clan_dir / "hub-peers.json").write_text(json.dumps({"peers": {}}))
        (clan_dir / "federation-peers.json").write_text(json.dumps({
            "hubs": {}, "self": {"hub_id": "test"}
        }))

        node = AgentNode(AgentNodeConfig(
            namespace="alice", clan_dir=clan_dir,
            bus_path=clan_dir / "bus.jsonl",
            gateway_url="",
        ))

        mtime_before = (clan_dir / "gateway.json").stat().st_mtime
        node._auto_peer_from_presence({
            "type": "event", "from": "bob",
            "msg": "hello", "ts": "2026-04-04T12:00:00Z",
        })
        mtime_after = (clan_dir / "gateway.json").stat().st_mtime
        assert mtime_before == mtime_after


# ---------------------------------------------------------------------------
# Tier 2: Hub + Agent Node (dispatch pipeline)
# ---------------------------------------------------------------------------


class TestHubInboxBridge:
    """Test hub-inbox.jsonl → bus.jsonl bridge via AgentNode._hub_inbox_loop."""

    def _make_node(self, tmp_path, namespace="alice"):
        """Create a minimal AgentNode for bridge testing."""
        from hermes.agent import AgentNode, AgentNodeConfig

        clan_dir = tmp_path / f"clan-{namespace}"
        clan_dir.mkdir(exist_ok=True)
        (clan_dir / "bus.jsonl").touch()
        inbox = clan_dir / "hub-inbox.jsonl"
        inbox.touch()
        (clan_dir / "gateway.json").write_text(json.dumps({
            "clan_id": namespace, "display_name": f"Test {namespace}",
            "namespace": namespace,
            "agent_node": {"hub": {"listen_port": 9999}},
            "peers": [],
        }))
        (clan_dir / "hub-peers.json").write_text(json.dumps({"peers": {}}))
        (clan_dir / "federation-peers.json").write_text(json.dumps({
            "hubs": {}, "self": {"hub_id": "test"},
        }))

        config = AgentNodeConfig(
            namespace=namespace, clan_dir=clan_dir,
            bus_path=clan_dir / "bus.jsonl", gateway_url="",
            hub_inbox_path=inbox, hub_inbox_poll_interval=0.1,
        )
        node = AgentNode(config)
        node._running = True  # Enable the loop (normally set by run())
        return node, clan_dir, inbox

    def test_message_bridged_to_bus(self, tmp_path):
        """A hub message gets written to bus.jsonl by the bridge loop."""
        from hermes.bus import read_bus

        node, clan_dir, inbox = self._make_node(tmp_path)

        # Write a message to hub-inbox
        hub_msg = {
            "ts": "2026-04-05T12:00:00Z", "from": "bob",
            "msg": "QUEST-TEST: bridge test", "type": "dispatch", "dst": "alice",
        }
        inbox.write_text(json.dumps(hub_msg) + "\n")

        # Run bridge loop for one cycle
        async def _test():
            task = asyncio.create_task(node._hub_inbox_loop())
            await asyncio.sleep(0.3)
            node._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        _run(_test())

        # Verify message in bus
        msgs = read_bus(clan_dir / "bus.jsonl")
        quest_msgs = [m for m in msgs if "QUEST-TEST" in m.msg]
        assert len(quest_msgs) == 1
        assert quest_msgs[0].src == "bob"
        assert quest_msgs[0].type == "dispatch"

    def test_cursor_persistence(self, tmp_path):
        """Cursor file tracks position so messages aren't re-processed."""
        from hermes.bus import read_bus

        node, clan_dir, inbox = self._make_node(tmp_path)
        cursor_path = clan_dir / "hub-inbox.daemon.cursor"

        # Write 2 messages
        msgs = [
            {"ts": "2026-04-05T12:00:00Z", "from": "bob", "msg": "msg-1", "type": "event", "dst": "alice"},
            {"ts": "2026-04-05T12:01:00Z", "from": "bob", "msg": "msg-2", "type": "event", "dst": "alice"},
        ]
        inbox.write_text("\n".join(json.dumps(m) for m in msgs) + "\n")

        # Run bridge once
        async def _cycle():
            task = asyncio.create_task(node._hub_inbox_loop())
            await asyncio.sleep(0.3)
            node._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        _run(_cycle())

        # Cursor should be at end of file
        assert cursor_path.exists()
        cursor_val = int(cursor_path.read_text().strip())
        file_size = inbox.stat().st_size
        assert cursor_val == file_size

        # Bus should have 2 messages
        bus_msgs = read_bus(clan_dir / "bus.jsonl")
        assert len([m for m in bus_msgs if m.src == "bob"]) == 2

    def test_cursor_reset_on_truncation(self, tmp_path):
        """When inbox is truncated, cursor resets and re-reads from start."""
        from hermes.bus import read_bus

        node, clan_dir, inbox = self._make_node(tmp_path)
        cursor_path = clan_dir / "hub-inbox.daemon.cursor"

        # Set cursor to a large value (simulating old inbox)
        cursor_path.write_text("999999")

        # Write a fresh message (smaller than old cursor)
        hub_msg = {"ts": "2026-04-05T12:00:00Z", "from": "carol",
                   "msg": "after-truncation", "type": "event", "dst": "alice"}
        inbox.write_text(json.dumps(hub_msg) + "\n")

        async def _cycle():
            task = asyncio.create_task(node._hub_inbox_loop())
            await asyncio.sleep(0.3)
            node._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        _run(_cycle())

        # Message should be bridged despite old cursor
        bus_msgs = read_bus(clan_dir / "bus.jsonl")
        carol_msgs = [m for m in bus_msgs if m.src == "carol"]
        assert len(carol_msgs) == 1
        assert carol_msgs[0].msg == "after-truncation"

    def test_skip_types_not_bridged(self, tmp_path):
        """Presence, roster, ping, pong messages are NOT bridged to bus."""
        from hermes.bus import read_bus

        node, clan_dir, inbox = self._make_node(tmp_path)

        skip_msgs = [
            {"ts": "2026-04-05T12:00:00Z", "from": "hub", "msg": "bob: online", "type": "presence"},
            {"ts": "2026-04-05T12:00:01Z", "from": "hub", "msg": "roster: alice, bob (2)", "type": "roster"},
            {"ts": "2026-04-05T12:00:02Z", "from": "hub", "msg": "", "type": "ping"},
            {"ts": "2026-04-05T12:00:03Z", "from": "bob", "msg": "real-message", "type": "event", "dst": "alice"},
        ]
        inbox.write_text("\n".join(json.dumps(m) for m in skip_msgs) + "\n")

        async def _cycle():
            task = asyncio.create_task(node._hub_inbox_loop())
            await asyncio.sleep(0.3)
            node._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        _run(_cycle())

        bus_msgs = read_bus(clan_dir / "bus.jsonl")
        # Only the real event should be bridged (not presence/roster/ping)
        assert len(bus_msgs) == 1
        assert bus_msgs[0].msg == "real-message"

    def test_dedup_prevents_double_bridge(self, tmp_path):
        """Duplicate messages in inbox are not written twice to bus."""
        from hermes.bus import read_bus

        node, clan_dir, inbox = self._make_node(tmp_path)

        # Same message twice (like QUEST-006-FINAL appeared twice)
        dup_msg = {"ts": "2026-04-05T12:00:00Z", "from": "bob",
                   "msg": "QUEST-DUP: same message", "type": "dispatch", "dst": "alice"}
        inbox.write_text(json.dumps(dup_msg) + "\n" + json.dumps(dup_msg) + "\n")

        async def _cycle():
            task = asyncio.create_task(node._hub_inbox_loop())
            await asyncio.sleep(0.3)
            node._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        _run(_cycle())

        bus_msgs = read_bus(clan_dir / "bus.jsonl")
        quest_msgs = [m for m in bus_msgs if "QUEST-DUP" in m.msg]
        assert len(quest_msgs) == 1, f"Expected 1 message, got {len(quest_msgs)}"

    def test_per_message_error_doesnt_block_batch(self, tmp_path):
        """A bad message doesn't prevent subsequent good messages from bridging."""
        from hermes.bus import read_bus

        node, clan_dir, inbox = self._make_node(tmp_path)

        # First: valid message. Second: corrupted JSON. Third: valid message.
        lines = [
            json.dumps({"ts": "2026-04-05T12:00:00Z", "from": "bob",
                        "msg": "good-1", "type": "event", "dst": "alice"}),
            "THIS IS NOT VALID JSON {{{",
            json.dumps({"ts": "2026-04-05T12:00:02Z", "from": "carol",
                        "msg": "good-2", "type": "event", "dst": "alice"}),
        ]
        inbox.write_text("\n".join(lines) + "\n")

        async def _cycle():
            task = asyncio.create_task(node._hub_inbox_loop())
            await asyncio.sleep(0.3)
            node._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        _run(_cycle())

        bus_msgs = read_bus(clan_dir / "bus.jsonl")
        assert len(bus_msgs) == 2
        assert bus_msgs[0].msg == "good-1"
        assert bus_msgs[1].msg == "good-2"
