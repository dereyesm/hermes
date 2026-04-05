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

from amaru.hub import HubConfig, HubServer
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
        from amaru.agent import AgentNode
        from amaru.agent import AgentNodeConfig
        from amaru.config import load_config

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
        from amaru.agent import AgentNode
        from amaru.agent import AgentNodeConfig

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
        from amaru.agent import AgentNode, AgentNodeConfig

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
        from amaru.bus import read_bus

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
        from amaru.bus import read_bus

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
        from amaru.bus import read_bus

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
        from amaru.bus import read_bus

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
        from amaru.bus import read_bus

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
        from amaru.bus import read_bus

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


# ---------------------------------------------------------------------------
# Tier 3: Dual Clan End-to-End (hub + bridge + evaluator)
# ---------------------------------------------------------------------------

# (TestDualClanDispatch class follows below)

# ---------------------------------------------------------------------------
# Tier 4: Multi-Clan Quest (3 clans: nymyka dispatches, dani+jei process)
# ---------------------------------------------------------------------------


class TestMultiClanQuest:
    """Test multi-clan quest: one clan dispatches, two others process and respond."""

    def test_broadcast_reaches_both_peers(self, clan_factory):
        """A broadcast dispatch (dst=*) reaches both peers through the hub."""
        nymyka_key, nymyka_pub = _generate_keys()
        dani_key, dani_pub = _generate_keys()
        jei_key, jei_pub = _generate_keys()
        port = random.randint(19000, 19999)

        async def _test():
            hub_info = clan_factory("hub-mc", port, {
                "nymyka": nymyka_pub, "dani": dani_pub, "jei": jei_pub,
            })
            config = HubConfig(listen_host="127.0.0.1", listen_port=port,
                               auth_timeout=5, max_queue_depth=100)
            server = HubServer(config, hub_info.dir)
            hub_task = asyncio.create_task(server.start())
            await asyncio.sleep(0.15)

            uri = f"ws://127.0.0.1:{port}"
            nymyka = await connect_hub_client(uri, "nymyka", nymyka_key)
            dani = await connect_hub_client(uri, "dani", dani_key)
            jei = await connect_hub_client(uri, "jei", jei_key)
            await _drain(nymyka)
            await _drain(dani)
            await _drain(jei)

            # Nymyka broadcasts a quest
            await nymyka.send_msg("*", "dispatch", "QUEST-CROSS-002: multi-clan test")

            # Both dani and jei should receive it
            dani_frame = await dani.recv_until("msg", timeout=3.0)
            assert dani_frame["payload"]["msg"] == "QUEST-CROSS-002: multi-clan test"
            assert dani_frame["payload"]["src"] == "nymyka"

            jei_frame = await jei.recv_until("msg", timeout=3.0)
            assert jei_frame["payload"]["msg"] == "QUEST-CROSS-002: multi-clan test"
            assert jei_frame["payload"]["src"] == "nymyka"

            await _cleanup(server, hub_task, nymyka, dani, jei)

        _run(_test())

    def test_both_peers_respond_independently(self, clan_factory):
        """Both peers process a broadcast quest and send responses back to origin."""
        nymyka_key, nymyka_pub = _generate_keys()
        dani_key, dani_pub = _generate_keys()
        jei_key, jei_pub = _generate_keys()
        port = random.randint(19000, 19999)

        async def _test():
            hub_info = clan_factory("hub-mc2", port, {
                "nymyka": nymyka_pub, "dani": dani_pub, "jei": jei_pub,
            })
            config = HubConfig(listen_host="127.0.0.1", listen_port=port,
                               auth_timeout=5, max_queue_depth=100)
            server = HubServer(config, hub_info.dir)
            hub_task = asyncio.create_task(server.start())
            await asyncio.sleep(0.15)

            uri = f"ws://127.0.0.1:{port}"
            nymyka = await connect_hub_client(uri, "nymyka", nymyka_key)
            dani = await connect_hub_client(uri, "dani", dani_key)
            jei = await connect_hub_client(uri, "jei", jei_key)
            await _drain(nymyka)
            await _drain(dani)
            await _drain(jei)

            # Nymyka dispatches
            await nymyka.send_msg("*", "dispatch", "QUEST-CROSS-003: solve this")

            # Both receive
            await dani.recv_until("msg", timeout=3.0)
            await jei.recv_until("msg", timeout=3.0)

            # Both respond independently to nymyka
            await dani.send_msg("nymyka", "event", "[RE:QUEST-CROSS-003] DANI done")
            await jei.send_msg("nymyka", "event", "[RE:QUEST-CROSS-003] JEI done")

            # Nymyka receives both responses
            responses = []
            try:
                for _ in range(5):
                    frame = await asyncio.wait_for(nymyka.ws.recv(), timeout=3.0)
                    parsed = json.loads(frame)
                    if parsed.get("type") == "msg" and "RE:QUEST-CROSS-003" in parsed["payload"].get("msg", ""):
                        responses.append(parsed["payload"])
                    if len(responses) == 2:
                        break
            except (TimeoutError, asyncio.TimeoutError):
                pass

            assert len(responses) == 2, f"Expected 2 responses, got {len(responses)}"
            sources = {r["src"] for r in responses}
            assert sources == {"dani", "jei"}

            await _cleanup(server, hub_task, nymyka, dani, jei)

        _run(_test())

    def test_partial_failure_other_succeeds(self, clan_factory):
        """If one peer disconnects, the other still receives and responds."""
        nymyka_key, nymyka_pub = _generate_keys()
        dani_key, dani_pub = _generate_keys()
        jei_key, jei_pub = _generate_keys()
        port = random.randint(19000, 19999)

        async def _test():
            hub_info = clan_factory("hub-mc3", port, {
                "nymyka": nymyka_pub, "dani": dani_pub, "jei": jei_pub,
            })
            config = HubConfig(listen_host="127.0.0.1", listen_port=port,
                               auth_timeout=5, max_queue_depth=100)
            server = HubServer(config, hub_info.dir)
            hub_task = asyncio.create_task(server.start())
            await asyncio.sleep(0.15)

            uri = f"ws://127.0.0.1:{port}"
            nymyka = await connect_hub_client(uri, "nymyka", nymyka_key)
            dani = await connect_hub_client(uri, "dani", dani_key)
            jei = await connect_hub_client(uri, "jei", jei_key)
            await _drain(nymyka)
            await _drain(dani)
            await _drain(jei)

            # JEI disconnects (simulating failure)
            await jei.close()
            await asyncio.sleep(0.1)

            # Nymyka dispatches — only dani is online
            await nymyka.send_msg("*", "dispatch", "QUEST-CROSS-004: partial")

            # Dani receives and responds
            dani_frame = await dani.recv_until("msg", timeout=3.0)
            assert "QUEST-CROSS-004" in dani_frame["payload"]["msg"]
            await dani.send_msg("nymyka", "event", "[RE:QUEST-CROSS-004] DANI done")

            # Nymyka gets dani's response
            resp = await nymyka.recv_until("msg", timeout=3.0)
            assert resp["payload"]["src"] == "dani"
            assert "DANI done" in resp["payload"]["msg"]

            # Broadcast is best-effort: offline peers don't get queued
            # (store-and-forward only works for unicast dst)
            # JEI reconnecting later would NOT receive the broadcast

            # But if nymyka sends unicast to jei, it DOES queue
            await nymyka.send_msg("jei", "dispatch", "QUEST-CROSS-004b: unicast to offline")
            await asyncio.sleep(0.1)
            assert server.queue.depth("jei") >= 1

            await _cleanup(server, hub_task, nymyka, dani)

        _run(_test())


class TestDualClanDispatch:
    """Test full bilateral dispatch: alice sends via hub → bob processes → response returns."""

    def test_alice_dispatch_reaches_bob_bus(self, clan_factory):
        """Alice sends dispatch via hub, bob's bridge writes it to bob's bus."""
        from amaru.agent import AgentNode, AgentNodeConfig
        from amaru.bus import read_bus

        alice_key, alice_pub = _generate_keys()
        bob_key, bob_pub = _generate_keys()
        port = random.randint(19000, 19999)

        async def _test():
            # Start hub with both peers registered
            hub_info = clan_factory("hub-t3", port, {"alice": alice_pub, "bob": bob_pub})
            config = HubConfig(listen_host="127.0.0.1", listen_port=port,
                               auth_timeout=5, max_queue_depth=100)
            server = HubServer(config, hub_info.dir)
            hub_task = asyncio.create_task(server.start())
            await asyncio.sleep(0.15)

            uri = f"ws://127.0.0.1:{port}"

            # Bob's clan dir with inbox for bridge
            bob_dir = clan_factory("bob-clan", port + 1, {"alice": alice_pub})
            bob_inbox = bob_dir.dir / "hub-inbox.jsonl"

            # Connect alice as sender
            alice = await connect_hub_client(uri, "alice", alice_key)
            await _drain(alice)

            # Connect bob as receiver — listen for messages and write to inbox
            bob_ws = await connect_hub_client(uri, "bob", bob_key)
            await _drain(bob_ws)

            # Alice sends dispatch
            await alice.send_msg("bob", "dispatch", "QUEST-T3-001: bilateral test")

            # Bob receives via hub
            frame = await bob_ws.recv_until("msg", timeout=3.0)
            assert frame["payload"]["type"] == "dispatch"

            # Write to bob's inbox (simulating hub listener)
            inbox_entry = {
                "ts": frame["payload"].get("ts", "2026-04-05T12:00:00Z"),
                "from": frame["payload"]["src"],
                "msg": frame["payload"]["msg"],
                "type": frame["payload"]["type"],
                "dst": frame["payload"]["dst"],
            }
            with open(bob_inbox, "a") as f:
                f.write(json.dumps(inbox_entry) + "\n")

            # Bob's agent node bridges inbox → bus
            bob_config = AgentNodeConfig(
                namespace="bob", clan_dir=bob_dir.dir,
                bus_path=bob_dir.dir / "bus.jsonl", gateway_url="",
                hub_inbox_path=bob_inbox, hub_inbox_poll_interval=0.1,
            )
            bob_node = AgentNode(bob_config)
            bob_node._running = True

            bridge_task = asyncio.create_task(bob_node._hub_inbox_loop())
            await asyncio.sleep(0.3)
            bob_node._running = False
            bridge_task.cancel()
            try:
                await bridge_task
            except asyncio.CancelledError:
                pass

            # Verify: dispatch is now in bob's bus
            bob_bus = read_bus(bob_dir.dir / "bus.jsonl")
            quest_msgs = [m for m in bob_bus if "QUEST-T3-001" in m.msg]
            assert len(quest_msgs) == 1
            assert quest_msgs[0].src == "alice"
            assert quest_msgs[0].type == "dispatch"
            assert quest_msgs[0].dst == "bob"

            await _cleanup(server, hub_task, alice, bob_ws)

        _run(_test())

    def test_evaluator_dispatches_cross_clan(self, tmp_path):
        """MessageEvaluator returns DISPATCH for a dispatch message addressed to us."""
        from amaru.agent import AgentNodeConfig, MessageEvaluator, Action
        from amaru.message import Message
        from datetime import date

        config = AgentNodeConfig(
            namespace="bob", clan_dir=tmp_path,
            bus_path=tmp_path / "bus.jsonl", gateway_url="",
        )
        evaluator = MessageEvaluator(config)

        msg = Message(
            ts=date.today(), src="alice", dst="bob",
            type="dispatch", msg="QUEST-T3: test", ttl=7, ack=[],
        )
        assert evaluator.evaluate(msg) == Action.DISPATCH

    def test_evaluator_ignores_own_acked(self, tmp_path):
        """Messages already ACKed by this node are ignored."""
        from amaru.agent import AgentNodeConfig, MessageEvaluator, Action
        from amaru.message import Message
        from datetime import date

        config = AgentNodeConfig(
            namespace="bob", clan_dir=tmp_path,
            bus_path=tmp_path / "bus.jsonl", gateway_url="",
        )
        evaluator = MessageEvaluator(config)

        msg = Message(
            ts=date.today(), src="alice", dst="bob",
            type="dispatch", msg="QUEST-T3: test", ttl=7, ack=["bob"],
        )
        assert evaluator.evaluate(msg) == Action.IGNORE

    def test_full_bilateral_round_trip(self, clan_factory):
        """Full round-trip: alice dispatch → hub → bob inbox → bob bus → evaluator → response to alice."""
        from amaru.agent import AgentNode, AgentNodeConfig, MessageEvaluator, Action
        from amaru.bus import read_bus
        from amaru.bus import write_message
        from amaru.message import create_message

        alice_key, alice_pub = _generate_keys()
        bob_key, bob_pub = _generate_keys()
        port = random.randint(19000, 19999)

        async def _test():
            # Hub
            hub_info = clan_factory("hub-rt", port, {"alice": alice_pub, "bob": bob_pub})
            config = HubConfig(listen_host="127.0.0.1", listen_port=port,
                               auth_timeout=5, max_queue_depth=100)
            server = HubServer(config, hub_info.dir)
            hub_task = asyncio.create_task(server.start())
            await asyncio.sleep(0.15)

            uri = f"ws://127.0.0.1:{port}"

            # Bob's infrastructure
            bob_dir = clan_factory("bob-rt", port + 1, {"alice": alice_pub})
            bob_inbox = bob_dir.dir / "hub-inbox.jsonl"

            # Connect both
            alice = await connect_hub_client(uri, "alice", alice_key)
            bob_ws = await connect_hub_client(uri, "bob", bob_key)
            await _drain(alice)
            await _drain(bob_ws)

            # Step 1: Alice sends dispatch
            await alice.send_msg("bob", "dispatch", "QUEST-RT-001: round trip")

            # Step 2: Bob receives via hub
            frame = await bob_ws.recv_until("msg", timeout=3.0)

            # Step 3: Write to bob's inbox (hub listener simulation)
            inbox_entry = {
                "ts": frame["payload"].get("ts", "2026-04-05T12:00:00Z"),
                "from": frame["payload"]["src"],
                "msg": frame["payload"]["msg"],
                "type": frame["payload"]["type"],
                "dst": frame["payload"]["dst"],
            }
            with open(bob_inbox, "a") as f:
                f.write(json.dumps(inbox_entry) + "\n")

            # Step 4: Bob's bridge processes inbox → bus
            bob_config = AgentNodeConfig(
                namespace="bob", clan_dir=bob_dir.dir,
                bus_path=bob_dir.dir / "bus.jsonl", gateway_url="",
                hub_inbox_path=bob_inbox, hub_inbox_poll_interval=0.1,
            )
            bob_node = AgentNode(bob_config)
            bob_node._running = True

            bridge_task = asyncio.create_task(bob_node._hub_inbox_loop())
            await asyncio.sleep(0.3)
            bob_node._running = False
            bridge_task.cancel()
            try:
                await bridge_task
            except asyncio.CancelledError:
                pass

            # Step 5: Verify dispatch in bob's bus
            bob_bus = read_bus(bob_dir.dir / "bus.jsonl")
            dispatch_msg = next(m for m in bob_bus if "QUEST-RT-001" in m.msg)
            assert dispatch_msg.type == "dispatch"

            # Step 6: Evaluator decides → DISPATCH
            evaluator = MessageEvaluator(bob_config)
            assert evaluator.evaluate(dispatch_msg) == Action.DISPATCH

            # Step 7: Simulate dispatch response (what _execute_decision does)
            response = create_message(
                src="bob", dst="alice",  # Cross-clan: reply to sender
                type="event", msg="[RE:cross-clan-dispatch] OK",
            )
            write_message(bob_dir.dir / "bus.jsonl", response)

            # Step 8: Bob sends response back via hub
            await bob_ws.send_msg("alice", "event", "[RE:QUEST-RT-001] OK")

            # Step 9: Alice receives the response
            resp_frame = await alice.recv_until("msg", timeout=3.0)
            assert resp_frame["payload"]["src"] == "bob"
            assert "OK" in resp_frame["payload"]["msg"]

            await _cleanup(server, hub_task, alice, bob_ws)

        _run(_test())
