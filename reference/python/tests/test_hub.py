"""Tests for HERMES Hub Mode (ARC-4601 §15)."""

import asyncio
import json
import os
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from hermes.hub import (
    AuthHandler,
    ConnectionEntry,
    ConnectionTable,
    HubConfig,
    HubServer,
    HubState,
    MessageRouter,
    PeerInfo,
    QueuedMessage,
    StoreForwardQueue,
    cmd_hub_init,
    load_hub_config,
    load_peers,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_hub(tmp_path):
    """Temporary hub directory with peers file."""
    peers = {
        "peers": {
            "momoshod": {
                "sign_pub": "aa" * 32,
                "display_name": "Clan MomoshoD",
                "registered_at": "2026-03-23T00:00:00Z",
            },
            "jei": {
                "sign_pub": "bb" * 32,
                "display_name": "Clan JEI",
                "registered_at": "2026-03-17T00:00:00Z",
            },
        }
    }
    (tmp_path / "hub-peers.json").write_text(json.dumps(peers))
    return tmp_path


@pytest.fixture
def sample_config():
    return HubConfig(listen_port=9999, auth_timeout=5)


@pytest.fixture
def sample_peers():
    return {
        "momoshod": PeerInfo("momoshod", "aa" * 32, "Clan MomoshoD"),
        "jei": PeerInfo("jei", "bb" * 32, "Clan JEI"),
    }


def _make_ws_mock():
    """Create a mock WebSocket with send/recv/close."""
    ws = AsyncMock()
    ws.send = AsyncMock()
    ws.close = AsyncMock()
    return ws


# ---------------------------------------------------------------------------
# TestHubConfig
# ---------------------------------------------------------------------------


class TestHubConfig:
    def test_defaults(self):
        c = HubConfig()
        assert c.listen_host == "0.0.0.0"
        assert c.listen_port == 8443
        assert c.ws_path == "/ws"
        assert c.max_queue_depth == 1000
        assert c.max_connections == 100
        assert c.auth_timeout == 10
        assert c.legacy_endpoints is True

    def test_from_dict(self):
        c = HubConfig.from_dict({"listen_port": 9000, "max_connections": 50, "extra_field": True})
        assert c.listen_port == 9000
        assert c.max_connections == 50

    def test_load_from_json(self, tmp_path):
        config = {
            "agent_node": {
                "mode": "hub",
                "hub": {
                    "listen_port": 7777,
                    "max_queue_depth": 500,
                },
            }
        }
        (tmp_path / "gateway.json").write_text(json.dumps(config))
        c = load_hub_config(tmp_path / "gateway.json")
        assert c.listen_port == 7777
        assert c.max_queue_depth == 500

    def test_load_missing_file(self, tmp_path):
        c = load_hub_config(tmp_path / "nonexistent.json")
        assert c.listen_port == 8443  # defaults


# ---------------------------------------------------------------------------
# TestPeerRegistry
# ---------------------------------------------------------------------------


class TestPeerRegistry:
    def test_load_peers(self, tmp_hub):
        peers = load_peers(tmp_hub / "hub-peers.json")
        assert len(peers) == 2
        assert "momoshod" in peers
        assert peers["jei"].sign_pub_hex == "bb" * 32

    def test_load_missing_file(self, tmp_path):
        peers = load_peers(tmp_path / "nope.json")
        assert peers == {}


# ---------------------------------------------------------------------------
# TestConnectionTable
# ---------------------------------------------------------------------------


class TestConnectionTable:
    def test_add_and_get(self):
        ct = ConnectionTable()
        ws = _make_ws_mock()
        entry = ct.add("momoshod", ws)
        assert ct.get("momoshod") is entry
        assert ct.is_online("momoshod")
        assert len(ct) == 1

    def test_remove(self):
        ct = ConnectionTable()
        ct.add("momoshod", _make_ws_mock())
        removed = ct.remove("momoshod")
        assert removed is not None
        assert not ct.is_online("momoshod")
        assert len(ct) == 0

    def test_remove_nonexistent(self):
        ct = ConnectionTable()
        assert ct.remove("ghost") is None

    def test_all_except(self):
        ct = ConnectionTable()
        ct.add("a", _make_ws_mock())
        ct.add("b", _make_ws_mock())
        ct.add("c", _make_ws_mock())
        result = ct.all_except("b")
        assert len(result) == 2
        assert all(e.clan_id != "b" for e in result)

    def test_max_connections(self):
        ct = ConnectionTable(max_connections=2)
        ct.add("a", _make_ws_mock())
        ct.add("b", _make_ws_mock())
        with pytest.raises(RuntimeError, match="Max connections"):
            ct.add("c", _make_ws_mock())

    def test_connected_clan_ids(self):
        ct = ConnectionTable()
        ct.add("x", _make_ws_mock())
        ct.add("y", _make_ws_mock())
        ids = ct.connected_clan_ids()
        assert set(ids) == {"x", "y"}


# ---------------------------------------------------------------------------
# TestStoreForwardQueue
# ---------------------------------------------------------------------------


class TestStoreForwardQueue:
    def test_enqueue_and_drain(self):
        q = StoreForwardQueue()
        q.enqueue("jei", {"msg": "hello"})
        q.enqueue("jei", {"msg": "world"})
        msgs, remaining = q.drain("jei")
        assert len(msgs) == 2
        assert msgs[0]["msg"] == "hello"
        assert remaining == 0

    def test_drain_empty(self):
        q = StoreForwardQueue()
        msgs, remaining = q.drain("nobody")
        assert msgs == []
        assert remaining == 0

    def test_drain_batch_size(self):
        q = StoreForwardQueue()
        for i in range(5):
            q.enqueue("jei", {"n": i})
        msgs, remaining = q.drain("jei", batch_size=3)
        assert len(msgs) == 3
        assert remaining == 2

    def test_max_depth(self):
        q = StoreForwardQueue(max_depth=2)
        assert q.enqueue("jei", {"a": 1}) is True
        assert q.enqueue("jei", {"b": 2}) is True
        assert q.enqueue("jei", {"c": 3}) is False  # Full

    def test_sweep_expired(self):
        q = StoreForwardQueue()
        # Add a message with very short TTL
        q._queues["jei"] = [
            QueuedMessage(payload={"old": True}, queued_at=time.time() - 100, ttl_seconds=50),
            QueuedMessage(payload={"new": True}, queued_at=time.time(), ttl_seconds=3600),
        ]
        removed = q.sweep_expired()
        assert removed == 1
        assert q.depth("jei") == 1

    def test_sweep_removes_empty_queues(self):
        q = StoreForwardQueue()
        q._queues["jei"] = [
            QueuedMessage(payload={}, queued_at=time.time() - 100, ttl_seconds=1),
        ]
        q.sweep_expired()
        assert "jei" not in q._queues

    def test_depth(self):
        q = StoreForwardQueue()
        q.enqueue("a", {"x": 1})
        q.enqueue("a", {"x": 2})
        q.enqueue("b", {"x": 3})
        assert q.depth("a") == 2
        assert q.depth("b") == 1
        assert q.total_depth() == 3

    def test_all_depths(self):
        q = StoreForwardQueue()
        q.enqueue("a", {})
        q.enqueue("b", {})
        q.enqueue("b", {})
        depths = q.all_depths()
        assert depths == {"a": 1, "b": 2}


# ---------------------------------------------------------------------------
# TestAuthHandler
# ---------------------------------------------------------------------------


class TestAuthHandler:
    def test_generate_challenge(self, sample_peers):
        auth = AuthHandler(sample_peers)
        nonce = auth.generate_challenge()
        assert len(nonce) == 64  # 32 bytes hex
        # Each call is different
        assert auth.generate_challenge() != nonce

    def test_is_registered(self, sample_peers):
        auth = AuthHandler(sample_peers)
        assert auth.is_registered("momoshod")
        assert auth.is_registered("jei")
        assert not auth.is_registered("unknown")

    def test_verify_valid_signature(self, sample_peers):
        """Test with real Ed25519 keys."""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        privkey = Ed25519PrivateKey.generate()
        pubkey = privkey.public_key()
        pub_hex = pubkey.public_bytes_raw().hex()

        # Register the peer with the real pubkey
        peers = {"test_clan": PeerInfo("test_clan", pub_hex, "Test")}
        auth = AuthHandler(peers)

        nonce = auth.generate_challenge()
        signature = privkey.sign(bytes.fromhex(nonce)).hex()

        assert auth.verify_response("test_clan", nonce, signature, pub_hex) is True

    def test_verify_invalid_signature(self, sample_peers):
        auth = AuthHandler(sample_peers)
        nonce = auth.generate_challenge()
        # Bad signature
        assert auth.verify_response("momoshod", nonce, "ff" * 64, "aa" * 32) is False

    def test_verify_unknown_clan(self, sample_peers):
        auth = AuthHandler(sample_peers)
        nonce = auth.generate_challenge()
        assert auth.verify_response("ghost", nonce, "ff" * 64, "cc" * 32) is False

    def test_verify_wrong_pubkey(self, sample_peers):
        auth = AuthHandler(sample_peers)
        nonce = auth.generate_challenge()
        # Correct clan but wrong pubkey
        assert auth.verify_response("momoshod", nonce, "ff" * 64, "cc" * 32) is False


# ---------------------------------------------------------------------------
# TestMessageRouter
# ---------------------------------------------------------------------------


class TestMessageRouter:
    def _make_router(self):
        ct = ConnectionTable()
        q = StoreForwardQueue()
        return MessageRouter(ct, q), ct, q

    def test_unicast_online(self):
        router, ct, q = self._make_router()
        ws = _make_ws_mock()
        ct.add("jei", ws)

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                router.route({"src": "momoshod", "dst": "jei", "msg": "encrypted"}, "momoshod")
            )
        finally:
            loop.close()

        assert result["status"] == "delivered"
        ws.send.assert_called_once()
        sent = json.loads(ws.send.call_args[0][0])
        assert sent["type"] == "msg"
        assert sent["payload"]["msg"] == "encrypted"

    def test_unicast_offline_queues(self):
        router, ct, q = self._make_router()

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                router.route({"src": "momoshod", "dst": "jei", "msg": "enc"}, "momoshod")
            )
        finally:
            loop.close()

        assert result["status"] == "queued"
        assert q.depth("jei") == 1

    def test_broadcast(self):
        router, ct, q = self._make_router()
        ws_a = _make_ws_mock()
        ws_b = _make_ws_mock()
        ct.add("a", ws_a)
        ct.add("b", ws_b)

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                router.route({"src": "sender", "dst": "*", "msg": "all"}, "sender")
            )
        finally:
            loop.close()

        assert result["status"] == "broadcast"
        assert result["delivered"] == 2
        ws_a.send.assert_called_once()
        ws_b.send.assert_called_once()

    def test_broadcast_excludes_sender(self):
        router, ct, q = self._make_router()
        ws_self = _make_ws_mock()
        ws_other = _make_ws_mock()
        ct.add("sender", ws_self)
        ct.add("other", ws_other)

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                router.route({"src": "sender", "dst": "*", "msg": "x"}, "sender")
            )
        finally:
            loop.close()

        assert result["delivered"] == 1
        ws_self.send.assert_not_called()
        ws_other.send.assert_called_once()

    def test_broadcast_not_queued_for_offline(self):
        router, ct, q = self._make_router()
        # No peers connected
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                router.route({"src": "s", "dst": "*", "msg": "x"}, "s")
            )
        finally:
            loop.close()

        assert result["delivered"] == 0
        assert q.total_depth() == 0  # Broadcast NOT queued

    def test_e2e_passthrough(self):
        """The router MUST NOT modify the msg field (E2E passthrough)."""
        router, ct, q = self._make_router()
        ws = _make_ws_mock()
        ct.add("jei", ws)

        encrypted_payload = {
            "src": "momoshod",
            "dst": "jei",
            "type": "quest005",
            "msg": {
                "enc": "ECDHE",
                "ciphertext": "deadbeef" * 10,
                "nonce": "aabb" * 6,
                "eph_pub": "ccdd" * 16,
                "signature": "eeff" * 32,
            },
        }

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(router.route(encrypted_payload, "momoshod"))
        finally:
            loop.close()

        sent = json.loads(ws.send.call_args[0][0])
        # Verify msg field is identical — untouched by router
        assert sent["payload"]["msg"] == encrypted_payload["msg"]

    def test_total_routed_counter(self):
        router, ct, q = self._make_router()
        ws = _make_ws_mock()
        ct.add("jei", ws)

        loop = asyncio.new_event_loop()
        try:
            for i in range(5):
                loop.run_until_complete(
                    router.route({"dst": "jei", "msg": str(i)}, "x")
                )
        finally:
            loop.close()

        assert router.total_routed == 5

    def test_queue_full_returns_status(self):
        ct = ConnectionTable()
        q = StoreForwardQueue(max_depth=1)
        router = MessageRouter(ct, q)
        q.enqueue("jei", {"old": True})

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                router.route({"dst": "jei", "msg": "new"}, "x")
            )
        finally:
            loop.close()

        assert result["status"] == "queue_full"


# ---------------------------------------------------------------------------
# TestHubState
# ---------------------------------------------------------------------------


class TestHubState:
    def test_roundtrip(self):
        state = HubState(
            pid=1234,
            started_at="2026-03-23T00:00:00Z",
            total_msgs_routed=42,
            uptime_seconds=3600,
        )
        d = state.to_dict()
        restored = HubState.from_dict(d)
        assert restored.pid == 1234
        assert restored.total_msgs_routed == 42

    def test_save_and_load(self, tmp_path):
        state = HubState(pid=5678, started_at="now", total_msgs_routed=10)
        path = tmp_path / "hub-state.json"
        state.save(path)
        loaded = HubState.load(path)
        assert loaded is not None
        assert loaded.pid == 5678

    def test_load_missing(self, tmp_path):
        assert HubState.load(tmp_path / "nope.json") is None


# ---------------------------------------------------------------------------
# TestHubServer
# ---------------------------------------------------------------------------


class TestHubServer:
    def test_init(self, tmp_hub, sample_config):
        server = HubServer(sample_config, tmp_hub)
        assert len(server.peers) == 2
        assert server.auth.is_registered("momoshod")

    def test_drain_queue(self, tmp_hub, sample_config):
        server = HubServer(sample_config, tmp_hub)
        server.queue.enqueue("jei", {"msg": "queued1"})
        server.queue.enqueue("jei", {"msg": "queued2"})

        ws = _make_ws_mock()
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(server._drain_queue(ws, "jei"))
        finally:
            loop.close()

        ws.send.assert_called_once()
        sent = json.loads(ws.send.call_args[0][0])
        assert sent["type"] == "drain"
        assert len(sent["messages"]) == 2

    def test_drain_empty(self, tmp_hub, sample_config):
        server = HubServer(sample_config, tmp_hub)
        ws = _make_ws_mock()
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(server._drain_queue(ws, "nobody"))
        finally:
            loop.close()
        ws.send.assert_not_called()

    def test_broadcast_presence(self, tmp_hub, sample_config):
        server = HubServer(sample_config, tmp_hub)
        ws_a = _make_ws_mock()
        ws_b = _make_ws_mock()
        server.connections.add("a", ws_a)
        server.connections.add("b", ws_b)

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(server._broadcast_presence("a", "online"))
        finally:
            loop.close()

        # Only b gets notified
        ws_a.send.assert_not_called()
        ws_b.send.assert_called_once()
        sent = json.loads(ws_b.send.call_args[0][0])
        assert sent["type"] == "presence"
        assert sent["clan_id"] == "a"
        assert sent["status"] == "online"

    def test_authenticate_success(self, tmp_hub):
        """Test auth flow with real Ed25519 keys."""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        privkey = Ed25519PrivateKey.generate()
        pubkey_hex = privkey.public_key().public_bytes_raw().hex()

        # Create peers file with real key
        peers_data = {
            "peers": {
                "test_clan": {
                    "sign_pub": pubkey_hex,
                    "display_name": "Test",
                }
            }
        }
        (tmp_hub / "hub-peers.json").write_text(json.dumps(peers_data))

        config = HubConfig(auth_timeout=5)
        server = HubServer(config, tmp_hub)

        ws = _make_ws_mock()

        # Simulate auth exchange
        async def mock_recv():
            # Read the challenge that was sent
            challenge_frame = json.loads(ws.send.call_args[0][0])
            nonce = challenge_frame["nonce"]
            sig = privkey.sign(bytes.fromhex(nonce)).hex()
            return json.dumps({
                "type": "auth",
                "clan_id": "test_clan",
                "nonce_response": sig,
                "sign_pub": pubkey_hex,
            })

        ws.recv = mock_recv

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(server._authenticate(ws))
        finally:
            loop.close()

        assert result == "test_clan"

    def test_authenticate_failure(self, tmp_hub, sample_config):
        server = HubServer(sample_config, tmp_hub)
        ws = _make_ws_mock()

        async def mock_recv():
            return json.dumps({
                "type": "auth",
                "clan_id": "momoshod",
                "nonce_response": "ff" * 64,
                "sign_pub": "aa" * 32,
            })

        ws.recv = mock_recv

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(server._authenticate(ws))
        finally:
            loop.close()

        assert result is None
        ws.close.assert_called_once()

    def test_authenticate_timeout(self, tmp_hub):
        config = HubConfig(auth_timeout=0)  # Immediate timeout
        server = HubServer(config, tmp_hub)
        ws = _make_ws_mock()

        async def mock_recv():
            await asyncio.sleep(10)  # Will timeout
            return "{}"

        ws.recv = mock_recv

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(server._authenticate(ws))
        finally:
            loop.close()

        assert result is None


# ---------------------------------------------------------------------------
# TestCLIHub
# ---------------------------------------------------------------------------


class TestCLIHub:
    def test_hub_status_no_state(self, tmp_path, capsys):
        from hermes.hub import cmd_hub_status
        ret = cmd_hub_status(tmp_path)
        assert ret == 1
        assert "No Hub state" in capsys.readouterr().out

    def test_hub_status_with_state(self, tmp_path, capsys):
        from hermes.hub import cmd_hub_status
        state = HubState(pid=9999, started_at="2026-03-23", total_msgs_routed=42)
        state.save(tmp_path / "hub-state.json")
        ret = cmd_hub_status(tmp_path)
        assert ret == 0
        out = capsys.readouterr().out
        assert "STOPPED" in out  # No lock file
        assert "42" in out

    def test_hub_peers_empty(self, tmp_path, capsys):
        from hermes.hub import cmd_hub_peers
        (tmp_path / "hub-peers.json").write_text('{"peers":{}}')
        (tmp_path / "gateway.json").write_text('{}')
        ret = cmd_hub_peers(tmp_path)
        assert ret == 0
        assert "No peers" in capsys.readouterr().out

    def test_hub_peers_list(self, tmp_hub, capsys):
        from hermes.hub import cmd_hub_peers
        (tmp_hub / "gateway.json").write_text('{}')
        ret = cmd_hub_peers(tmp_hub)
        assert ret == 0
        out = capsys.readouterr().out
        assert "momoshod" in out
        assert "jei" in out


# ---------------------------------------------------------------------------
# Hub Init (cmd_hub_init)
# ---------------------------------------------------------------------------


def _make_gateway(tmp_path, peers=None):
    """Helper: create a gateway.json with optional peers."""
    own_pub = {"sign_public": "cc" * 32, "dh_public": "dd" * 32}
    keys_dir = tmp_path / ".keys"
    keys_dir.mkdir(exist_ok=True)
    (keys_dir / "gateway.pub").write_text(json.dumps(own_pub))
    gw = {
        "clan_id": "testclan",
        "display_name": "Test Clan",
        "keys": {"private": ".keys/gateway.key", "public": ".keys/gateway.pub"},
        "peers": peers or [],
    }
    (tmp_path / "gateway.json").write_text(json.dumps(gw))


class TestHubInit:
    def test_creates_peers_file(self, tmp_path, capsys):
        peer_dir = tmp_path / "keys" / "peers"
        peer_dir.mkdir(parents=True)
        (peer_dir / "alpha.pub").write_text(json.dumps({
            "ed25519_pub": "aa" * 32, "x25519_pub": "bb" * 32,
        }))
        _make_gateway(tmp_path, peers=[{
            "clan_id": "alpha",
            "public_key_file": "keys/peers/alpha.pub",
            "status": "active",
            "added": "2026-03-20",
        }])

        ret = cmd_hub_init(tmp_path)
        assert ret == 0

        peers_file = tmp_path / "hub-peers.json"
        assert peers_file.exists()
        data = json.loads(peers_file.read_text())
        assert "testclan" in data["peers"]  # self
        assert "alpha" in data["peers"]  # peer
        assert data["peers"]["alpha"]["sign_pub"] == "aa" * 32
        assert data["peers"]["testclan"]["sign_pub"] == "cc" * 32

    def test_refuses_overwrite(self, tmp_path, capsys):
        _make_gateway(tmp_path)
        (tmp_path / "hub-peers.json").write_text('{"peers":{}}')

        ret = cmd_hub_init(tmp_path)
        assert ret == 1
        assert "already exists" in capsys.readouterr().out

    def test_force_overwrites(self, tmp_path, capsys):
        _make_gateway(tmp_path)
        (tmp_path / "hub-peers.json").write_text('{"peers":{}}')

        ret = cmd_hub_init(tmp_path, force=True)
        assert ret == 0
        data = json.loads((tmp_path / "hub-peers.json").read_text())
        assert "testclan" in data["peers"]

    def test_dual_format_raw_hex_and_json(self, tmp_path, capsys):
        peer_dir = tmp_path / "keys" / "peers"
        peer_dir.mkdir(parents=True)
        # raw hex (64 chars)
        (peer_dir / "rawpeer.pub").write_text("ee" * 32)
        # JSON format
        (peer_dir / "jsonpeer.pub").write_text(json.dumps({
            "sign_public": "ff" * 32, "dh_public": "11" * 32,
        }))
        _make_gateway(tmp_path, peers=[
            {"clan_id": "rawpeer", "public_key_file": "keys/peers/rawpeer.pub", "added": "2026-01-01"},
            {"clan_id": "jsonpeer", "public_key_file": "keys/peers/jsonpeer.pub", "added": "2026-02-01"},
        ])

        ret = cmd_hub_init(tmp_path)
        assert ret == 0
        data = json.loads((tmp_path / "hub-peers.json").read_text())
        assert data["peers"]["rawpeer"]["sign_pub"] == "ee" * 32
        assert data["peers"]["jsonpeer"]["sign_pub"] == "ff" * 32
