"""HERMES Hub Mode — Server-side Agent Node (ARC-4601 §15).

A Hub accepts WebSocket connections from peer daemons, routes encrypted
messages between them, and provides store-and-forward for offline peers.

The Hub operates in E2E passthrough mode: it routes ARC-8446 encrypted
envelopes without decryption. It is a routing convenience, not a trust
boundary.

Reference: ARC-4601 §15 (Hub Mode Server-Side Extension)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("hermes.hub")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class HubConfig:
    """Configuration for Hub mode (ARC-4601 §15.10)."""

    listen_host: str = "0.0.0.0"
    listen_port: int = 8443
    ws_path: str = "/ws"
    tls_cert: str | None = None
    tls_key: str | None = None
    peers_file: str = "hub-peers.json"
    federation_file: str = "federation-peers.json"
    max_queue_depth: int = 1000
    queue_sweep_interval: int = 60
    legacy_endpoints: bool = True
    max_connections: int = 100
    auth_timeout: int = 10
    s2s_reconnect_interval: int = 30
    s2s_max_backoff: int = 300

    @classmethod
    def from_dict(cls, d: dict) -> HubConfig:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in known})


def load_hub_config(config_path: Path) -> HubConfig:
    """Load HubConfig from gateway.json or config.toml."""
    if not config_path.exists():
        return HubConfig()

    text = config_path.read_text()
    if config_path.suffix == ".toml":
        import tomllib

        data = tomllib.loads(text)
    else:
        data = json.loads(text)

    agent_node = data.get("agent_node", {})
    hub_section = agent_node.get("hub", {})
    return HubConfig.from_dict(hub_section)


# ---------------------------------------------------------------------------
# Peer Registry
# ---------------------------------------------------------------------------


@dataclass
class PeerInfo:
    """A registered peer clan."""

    clan_id: str
    sign_pub_hex: str
    display_name: str = ""
    registered_at: str = ""


def load_peers(peers_path: Path) -> dict[str, PeerInfo]:
    """Load registered peers from hub-peers.json."""
    if not peers_path.exists():
        return {}
    data = json.loads(peers_path.read_text())
    peers = {}
    for clan_id, info in data.get("peers", {}).items():
        peers[clan_id] = PeerInfo(
            clan_id=clan_id,
            sign_pub_hex=info.get("sign_pub", ""),
            display_name=info.get("display_name", ""),
            registered_at=info.get("registered_at", ""),
        )
    return peers


# ---------------------------------------------------------------------------
# Connection Table
# ---------------------------------------------------------------------------


@dataclass
class ConnectionEntry:
    """An active WebSocket connection."""

    ws: Any  # websockets.WebSocketServerProtocol
    clan_id: str
    connected_at: float = field(default_factory=time.time)
    msgs_routed: int = 0


class ConnectionTable:
    """Maps clan_id -> active WebSocket connection (ARC-4601 §15.3)."""

    def __init__(self, max_connections: int = 100):
        self._connections: dict[str, ConnectionEntry] = {}
        self.max_connections = max_connections

    def add(self, clan_id: str, ws: Any) -> ConnectionEntry:
        if len(self._connections) >= self.max_connections:
            raise RuntimeError(f"Max connections ({self.max_connections}) reached")
        entry = ConnectionEntry(ws=ws, clan_id=clan_id)
        self._connections[clan_id] = entry
        return entry

    def remove(self, clan_id: str) -> ConnectionEntry | None:
        return self._connections.pop(clan_id, None)

    def get(self, clan_id: str) -> ConnectionEntry | None:
        return self._connections.get(clan_id)

    def is_online(self, clan_id: str) -> bool:
        return clan_id in self._connections

    def all_except(self, exclude: str) -> list[ConnectionEntry]:
        return [e for cid, e in self._connections.items() if cid != exclude]

    def connected_clan_ids(self) -> list[str]:
        return list(self._connections.keys())

    def __len__(self) -> int:
        return len(self._connections)


# ---------------------------------------------------------------------------
# Store-and-Forward Queue
# ---------------------------------------------------------------------------


@dataclass
class QueuedMessage:
    """A message waiting for an offline peer."""

    payload: dict
    queued_at: float = field(default_factory=time.time)
    ttl_seconds: int = 604800  # 7 days default


class StoreForwardQueue:
    """Per-peer FIFO queue with TTL eviction (ARC-4601 §15.7)."""

    def __init__(self, max_depth: int = 1000):
        self._queues: dict[str, list[QueuedMessage]] = {}
        self.max_depth = max_depth

    def enqueue(self, dst: str, payload: dict, ttl_seconds: int = 604800) -> bool:
        """Enqueue a message for an offline peer. Returns False if queue full."""
        queue = self._queues.setdefault(dst, [])
        if len(queue) >= self.max_depth:
            return False
        queue.append(QueuedMessage(payload=payload, ttl_seconds=ttl_seconds))
        return True

    def drain(self, dst: str, batch_size: int = 100) -> tuple[list[dict], int]:
        """Drain up to batch_size messages. Returns (messages, remaining)."""
        queue = self._queues.get(dst, [])
        batch = queue[:batch_size]
        self._queues[dst] = queue[batch_size:]
        remaining = len(self._queues[dst])
        if remaining == 0:
            self._queues.pop(dst, None)
        return [m.payload for m in batch], remaining

    def depth(self, dst: str) -> int:
        return len(self._queues.get(dst, []))

    def total_depth(self) -> int:
        return sum(len(q) for q in self._queues.values())

    def sweep_expired(self) -> int:
        """Remove messages with expired TTL. Returns count removed."""
        now = time.time()
        removed = 0
        for dst in list(self._queues.keys()):
            before = len(self._queues[dst])
            self._queues[dst] = [
                m for m in self._queues[dst] if (now - m.queued_at) < m.ttl_seconds
            ]
            removed += before - len(self._queues[dst])
            if not self._queues[dst]:
                del self._queues[dst]
        return removed

    def all_depths(self) -> dict[str, int]:
        return {dst: len(q) for dst, q in self._queues.items()}


# ---------------------------------------------------------------------------
# S2S Federation (ARC-4601 §17)
# ---------------------------------------------------------------------------


@dataclass
class FederationLink:
    """A hub-to-hub S2S link."""

    hub_id: str
    ws_uri: str
    sign_pub_hex: str
    remote_peers: list[str] = field(default_factory=list)
    auto_connect: bool = True
    ws: Any = None
    connected: bool = False
    reconnect_backoff: float = 1.0


class FederationTable:
    """Maps clan_id -> FederationLink for inter-hub routing (ARC-4601 §17)."""

    def __init__(self) -> None:
        self._links: dict[str, FederationLink] = {}  # hub_id -> link
        self._routing: dict[str, str] = {}  # clan_id -> hub_id

    @classmethod
    def load(cls, path: Path) -> FederationTable:
        """Load federation config from federation-peers.json."""
        table = cls()
        if not path.exists():
            return table
        data = json.loads(path.read_text())
        for hub_id, info in data.get("hubs", {}).items():
            link = FederationLink(
                hub_id=hub_id,
                ws_uri=info.get("ws_uri", ""),
                sign_pub_hex=info.get("sign_pub", ""),
                remote_peers=info.get("peers", []),
                auto_connect=info.get("auto_connect", True),
            )
            table._links[hub_id] = link
            for peer in link.remote_peers:
                table._routing[peer] = hub_id
        return table

    def get_link_for(self, dst: str) -> FederationLink | None:
        """Find the S2S link responsible for a destination clan_id."""
        hub_id = self._routing.get(dst)
        if hub_id:
            return self._links.get(hub_id)
        # Case-insensitive fallback
        for cid, hid in self._routing.items():
            if cid.lower() == dst.lower():
                return self._links.get(hid)
        return None

    def is_federated(self, dst: str) -> bool:
        """Check if dst is reachable via a federation link."""
        return self.get_link_for(dst) is not None

    def register_link(self, hub_id: str, ws: Any, remote_peers: list[str]) -> FederationLink:
        """Register an inbound S2S link from a remote hub."""
        link = self._links.get(hub_id)
        if link:
            link.ws = ws
            link.connected = True
            link.remote_peers = remote_peers
        else:
            link = FederationLink(
                hub_id=hub_id,
                ws_uri="",
                sign_pub_hex="",
                remote_peers=remote_peers,
                ws=ws,
                connected=True,
            )
            self._links[hub_id] = link
        for peer in remote_peers:
            self._routing[peer] = hub_id
        return link

    def unregister_link(self, hub_id: str) -> None:
        """Mark a federation link as disconnected."""
        link = self._links.get(hub_id)
        if link:
            link.ws = None
            link.connected = False

    def active_links(self) -> list[FederationLink]:
        """Return all connected S2S links."""
        return [l for l in self._links.values() if l.connected and l.ws]

    def update_remote_peers(self, hub_id: str, peers: list[str]) -> None:
        """Update the peer list for a remote hub (e.g. from s2s_presence)."""
        link = self._links.get(hub_id)
        if not link:
            return
        # Remove old routing entries for this hub
        self._routing = {k: v for k, v in self._routing.items() if v != hub_id}
        link.remote_peers = peers
        for peer in peers:
            self._routing[peer] = hub_id

    def all_links(self) -> dict[str, FederationLink]:
        return dict(self._links)

    def routing_table(self) -> dict[str, str]:
        return dict(self._routing)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


class AuthHandler:
    """Ed25519 challenge-response authentication (ARC-4601 §15.6)."""

    def __init__(self, peers: dict[str, PeerInfo]):
        self._peers = peers

    def generate_challenge(self) -> str:
        """Generate a random 32-byte hex nonce."""
        return os.urandom(32).hex()

    def verify_response(
        self, clan_id: str, nonce_hex: str, signature_hex: str, sign_pub_hex: str
    ) -> bool:
        """Verify Ed25519 signature of nonce against registered peer.

        Tolerant lookup: tries exact clan_id, then lowercase, then scans all peers.
        If sign_pub_hex is empty, uses the registered key for verification.
        """
        # Tolerant clan_id lookup
        peer = self._peers.get(clan_id)
        if not peer:
            peer = self._peers.get(clan_id.lower())
        if not peer:
            # Scan all peers for case-insensitive match
            for pid, p in self._peers.items():
                if pid.lower() == clan_id.lower():
                    peer = p
                    break
        if not peer:
            logger.warning("Auth: clan_id '%s' not in peers: %s", clan_id, list(self._peers.keys()))
            return False

        # Use registered key if client didn't send one
        verify_pub = sign_pub_hex if sign_pub_hex else peer.sign_pub_hex

        # If client sent a key, verify it matches registered (optional strict check)
        if sign_pub_hex and peer.sign_pub_hex and sign_pub_hex != peer.sign_pub_hex:
            logger.warning("Auth: key mismatch for %s. sent=%s...  registered=%s...",
                          clan_id, sign_pub_hex[:16], peer.sign_pub_hex[:16])
            # Still try with registered key (client may have sent wrong pub)
            verify_pub = peer.sign_pub_hex

        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PublicKey,
            )

            pub_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(verify_pub))
            pub_key.verify(bytes.fromhex(signature_hex), bytes.fromhex(nonce_hex))
            return True
        except Exception as e:
            logger.warning("Auth: signature verify failed for %s: %s", clan_id, e)
            return False

    def is_registered(self, clan_id: str) -> bool:
        return clan_id in self._peers


# ---------------------------------------------------------------------------
# Message Router
# ---------------------------------------------------------------------------


class MessageRouter:
    """Routes messages between peers (ARC-4601 §15.5.2).

    The router operates in E2E passthrough mode: it inspects only the
    `dst` and `src` fields for routing. The `msg` field (encrypted
    ARC-8446 envelope) is forwarded without inspection or modification.

    Federation (§17): If dst is not a local peer, the router checks
    the FederationTable and forwards to the responsible hub via S2S link.
    """

    def __init__(
        self,
        connections: ConnectionTable,
        queue: StoreForwardQueue,
        federation: FederationTable | None = None,
    ):
        self._connections = connections
        self._queue = queue
        self._federation = federation
        self.total_routed = 0

    async def route(self, payload: dict, sender: str) -> dict:
        """Route a message. Returns status dict.

        payload: ARC-5322 message as dict (with src, dst, type, msg, etc.)
        sender: clan_id of the sender (for broadcast exclusion)
        """
        dst = payload.get("dst", "")

        if dst == "*":
            return await self._broadcast(payload, sender)
        else:
            return await self._unicast(payload, dst)

    async def _unicast(self, payload: dict, dst: str) -> dict:
        # 1. Try local delivery
        entry = self._connections.get(dst)
        if entry:
            try:
                await entry.ws.send(json.dumps({"type": "msg", "payload": payload}))
                entry.msgs_routed += 1
                self.total_routed += 1
                return {"status": "delivered", "dst": dst}
            except Exception as e:
                logger.warning("Failed to send to %s: %s", dst, e)
                self._queue.enqueue(dst, payload, payload.get("ttl", 604800))
                return {"status": "queued", "dst": dst, "reason": str(e)}

        # 2. Try federation routing (S2S)
        if self._federation:
            link = self._federation.get_link_for(dst)
            if link and link.connected and link.ws:
                try:
                    await link.ws.send(json.dumps({"type": "msg", "payload": payload}))
                    self.total_routed += 1
                    return {"status": "federated", "dst": dst, "via": link.hub_id}
                except Exception as e:
                    logger.warning("S2S send to %s via %s failed: %s", dst, link.hub_id, e)
                    # Fall through to local queue

        # 3. Queue locally (offline or unreachable)
        ttl = payload.get("ttl", 604800)
        if isinstance(ttl, int):
            ttl_sec = ttl if ttl > 86400 else ttl * 86400  # handle days vs seconds
        else:
            ttl_sec = 604800
        ok = self._queue.enqueue(dst, payload, ttl_sec)
        return {"status": "queued" if ok else "queue_full", "dst": dst}

    async def _broadcast(self, payload: dict, sender: str) -> dict:
        # Local broadcast
        peers = self._connections.all_except(sender)
        delivered = 0
        failed = 0
        for entry in peers:
            try:
                await entry.ws.send(json.dumps({"type": "msg", "payload": payload}))
                entry.msgs_routed += 1
                delivered += 1
            except Exception:
                failed += 1

        # S2S broadcast: forward to federated hubs (except sender's hub)
        s2s_delivered = 0
        if self._federation:
            for link in self._federation.active_links():
                try:
                    await link.ws.send(json.dumps({"type": "msg", "payload": payload}))
                    s2s_delivered += 1
                except Exception:
                    pass

        self.total_routed += delivered + s2s_delivered
        return {
            "status": "broadcast",
            "delivered": delivered,
            "failed": failed,
            "s2s_delivered": s2s_delivered,
        }


# ---------------------------------------------------------------------------
# Hub State
# ---------------------------------------------------------------------------


@dataclass
class HubState:
    """Persistent hub state (ARC-4601 §15.9)."""

    pid: int = 0
    started_at: str = ""
    mode: str = "hub"
    total_msgs_routed: int = 0
    uptime_seconds: float = 0

    def to_dict(self) -> dict:
        return {
            "pid": self.pid,
            "started_at": self.started_at,
            "mode": self.mode,
            "total_msgs_routed": self.total_msgs_routed,
            "uptime_seconds": self.uptime_seconds,
        }

    @classmethod
    def from_dict(cls, d: dict) -> HubState:
        return cls(
            pid=d.get("pid", 0),
            started_at=d.get("started_at", ""),
            mode=d.get("mode", "hub"),
            total_msgs_routed=d.get("total_msgs_routed", 0),
            uptime_seconds=d.get("uptime_seconds", 0),
        )

    def save(self, path: Path) -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2))
        os.rename(str(tmp), str(path))

    @classmethod
    def load(cls, path: Path) -> HubState | None:
        if not path.exists():
            return None
        try:
            return cls.from_dict(json.loads(path.read_text()))
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Hub Server
# ---------------------------------------------------------------------------


class HubServer:
    """WebSocket Hub server (ARC-4601 §15).

    Accepts peer connections, authenticates via Ed25519 challenge-response,
    routes messages between peers, and provides store-and-forward for
    offline peers.
    """

    def __init__(self, config: HubConfig, hub_dir: Path):
        self.config = config
        self.hub_dir = hub_dir
        self.peers = load_peers(hub_dir / config.peers_file)
        self.auth = AuthHandler(self.peers)
        self.connections = ConnectionTable(config.max_connections)
        self.queue = StoreForwardQueue(config.max_queue_depth)

        # S2S Federation (ARC-4601 §17)
        fed_path = hub_dir / config.federation_file
        self.federation = FederationTable.load(fed_path)
        self.router = MessageRouter(self.connections, self.queue, self.federation)

        # Hub identity for S2S auth
        self._hub_id = self._load_hub_id(fed_path)

        self.state = HubState(
            pid=os.getpid(),
            started_at=datetime.now(UTC).isoformat(),
        )
        self._server = None
        self._started_at = time.time()
        self._running = False
        self._s2s_tasks: list[asyncio.Task] = []

    @staticmethod
    def _load_hub_id(fed_path: Path) -> str:
        """Load hub_id from federation config, default 'hub'."""
        if not fed_path.exists():
            return "hub"
        try:
            data = json.loads(fed_path.read_text())
            return data.get("self", {}).get("hub_id", "hub")
        except Exception:
            return "hub"

    async def start(self) -> None:
        """Start the Hub server."""
        import websockets

        ssl_context = None
        if self.config.tls_cert and self.config.tls_key:
            import ssl

            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(self.config.tls_cert, self.config.tls_key)

        self._running = True
        logger.info(
            "Hub starting on %s:%d (peers: %d)",
            self.config.listen_host,
            self.config.listen_port,
            len(self.peers),
        )

        self._server = await websockets.serve(  # type: ignore[assignment]
            self._handle_connection,
            self.config.listen_host,
            self.config.listen_port,
            ssl=ssl_context,
            process_request=self._process_http if self.config.legacy_endpoints else None,  # type: ignore[arg-type]
        )

        self.state.save(self.hub_dir / "hub-state.json")

        # Launch S2S outbound connections
        for hub_id, link in self.federation.all_links().items():
            if link.auto_connect and link.ws_uri:
                task = asyncio.create_task(self._s2s_outbound(link))
                self._s2s_tasks.append(task)
                logger.info("S2S outbound task started for %s (%s)", hub_id, link.ws_uri)

        # Run sweep loop alongside server
        try:
            await self._sweep_loop()
        except asyncio.CancelledError:
            pass
        finally:
            self._running = False
            for task in self._s2s_tasks:
                task.cancel()

    async def stop(self) -> None:
        """Graceful shutdown."""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        self._save_state()

    def _save_state(self) -> None:
        self.state.uptime_seconds = time.time() - self._started_at
        self.state.total_msgs_routed = self.router.total_routed
        self.state.save(self.hub_dir / "hub-state.json")

    # -- WebSocket handler --------------------------------------------------

    async def _handle_connection(self, ws: Any) -> None:
        """Handle a single WebSocket peer or S2S hub connection."""
        clan_id = None
        is_hub = False
        try:
            # Step 1: Authentication (§15.6 / §17)
            clan_id, role, remote_peers = await self._authenticate(ws)
            if not clan_id:
                return

            is_hub = role == "hub"

            if is_hub:
                # S2S inbound: register as federation link
                link = self.federation.register_link(clan_id, ws, remote_peers)
                logger.info("S2S hub connected: %s (peers: %s)", clan_id, remote_peers)

                # Message loop for S2S link — route locally
                async for raw in ws:
                    try:
                        frame = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    frame_type = frame.get("type", "")

                    if frame_type == "msg":
                        payload = frame.get("payload", {})
                        if not isinstance(payload, dict) or "dst" not in payload:
                            continue
                        # Route the message locally (or to another S2S link)
                        await self.router.route(payload, clan_id)

                    elif frame_type == "s2s_presence":
                        # Remote hub notifying us of peer status changes
                        peer_id = frame.get("clan_id", "")
                        status = frame.get("status", "")
                        hub_id = frame.get("hub_id", clan_id)
                        if status == "online" and peer_id:
                            current = list(link.remote_peers)
                            if peer_id not in current:
                                current.append(peer_id)
                                self.federation.update_remote_peers(hub_id, current)
                        elif status == "offline" and peer_id:
                            current = [p for p in link.remote_peers if p != peer_id]
                            self.federation.update_remote_peers(hub_id, current)
                        logger.info("S2S presence: %s %s (via %s)", peer_id, status, hub_id)

                    elif frame_type == "ping":
                        await ws.send(json.dumps({
                            "type": "pong",
                            "ts": datetime.now(UTC).isoformat(),
                        }))

            else:
                # Regular peer connection
                # Step 2: Register connection
                self.connections.add(clan_id, ws)
                logger.info("Peer connected: %s", clan_id)

                # Step 3: Notify other peers + S2S links
                await self._broadcast_presence(clan_id, "online")

                # Step 4: Drain queued messages
                await self._drain_queue(ws, clan_id)

                # Step 5: Message loop
                async for raw in ws:
                    try:
                        frame = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    frame_type = frame.get("type", "")

                    if frame_type == "msg":
                        payload = frame.get("payload", {})
                        if not isinstance(payload, dict) or "dst" not in payload:
                            continue
                        await self.router.route(payload, clan_id)

                    elif frame_type == "ping":
                        depth = self.queue.depth(clan_id)
                        await ws.send(
                            json.dumps(
                                {
                                    "type": "pong",
                                    "ts": datetime.now(UTC).isoformat(),
                                    "queue_depth": depth,
                                }
                            )
                        )

        except Exception as e:
            if clan_id:
                logger.info("%s disconnected: %s (%s)",
                            "S2S hub" if is_hub else "Peer", clan_id, type(e).__name__)
        finally:
            if clan_id:
                if is_hub:
                    self.federation.unregister_link(clan_id)
                else:
                    self.connections.remove(clan_id)
                    await self._broadcast_presence(clan_id, "offline")
                self._save_state()

    async def _authenticate(self, ws: Any) -> tuple[str | None, str, list[str]]:
        """Run HELLO + challenge-response auth (ARC-4601 §15.6, §17).

        Wire sequence (normative):
          1. Client → Server: HELLO  {type:"hello", clan_id, sign_pub, protocol_version, capabilities:[], [role, local_peers]}
          2. Server → Client: CHALLENGE {type:"challenge", nonce, server_version, server_clan_id, server_capabilities:[]}
          3. Client → Server: AUTH  {type:"auth", nonce_response (Ed25519 signature of nonce)}
          4. Server → Client: AUTH_OK {type:"auth_ok", clan_id, queue_depth}

        Returns (clan_id, role, remote_peers) on success, (None, "", []) on failure.
        Role is "hub" for S2S connections, "peer" for regular peers.
        """
        from hermes import __version__

        fail = (None, "", [])

        # Step 1: Wait for client HELLO (client initiates)
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=self.config.auth_timeout)
            hello = json.loads(raw)
        except (TimeoutError, json.JSONDecodeError):
            await ws.send(json.dumps({"type": "auth_fail", "reason": "timeout waiting for hello"}))
            await ws.close()
            return fail

        if hello.get("type") != "hello":
            # Backward compat: any non-hello frame goes to legacy auth
            clan_id = await self._authenticate_legacy(ws, hello)
            return (clan_id, "peer", []) if clan_id else fail

        client_clan_id = hello.get("clan_id", "")
        client_pub = hello.get("sign_pub", "")
        client_version = hello.get("protocol_version", "unknown")
        client_caps = hello.get("capabilities", [])
        client_role = hello.get("role", "peer")
        client_local_peers = hello.get("local_peers", [])

        logger.info("HELLO from %s (v%s, role=%s, caps=%s)", client_clan_id, client_version, client_role, client_caps)

        # For S2S hubs: verify against federation config instead of peers
        if client_role == "hub":
            fed_link = self.federation.all_links().get(client_clan_id)
            if not fed_link:
                # Unknown hub — check if sign_pub matches any configured hub
                found = False
                for hid, fl in self.federation.all_links().items():
                    if fl.sign_pub_hex and fl.sign_pub_hex == client_pub:
                        client_clan_id = hid
                        found = True
                        break
                if not found:
                    logger.warning("S2S: unknown hub %s (not in federation config)", client_clan_id)
                    await ws.send(json.dumps({"type": "auth_fail", "reason": "unknown hub"}))
                    await ws.close()
                    return fail

        # Step 2: Send CHALLENGE with server identity
        nonce = self.auth.generate_challenge()
        server_caps = ["store_forward", "e2e_passthrough", "presence"]
        if self.federation.all_links():
            server_caps.append("s2s")
        await ws.send(json.dumps({
            "type": "challenge",
            "nonce": nonce,
            "server_version": __version__,
            "server_clan_id": self._hub_id,
            "server_capabilities": server_caps,
        }))

        # Step 3: Wait for AUTH (signed nonce)
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=self.config.auth_timeout)
            auth_frame = json.loads(raw)
        except (TimeoutError, json.JSONDecodeError):
            await ws.send(json.dumps({"type": "auth_fail", "reason": "timeout waiting for auth"}))
            await ws.close()
            return fail

        if auth_frame.get("type") != "auth":
            await ws.send(json.dumps({"type": "auth_fail", "reason": "expected auth after challenge"}))
            await ws.close()
            return fail

        sig = auth_frame.get("nonce_response", "")

        # For S2S: verify using federation sign_pub
        if client_role == "hub":
            fed_link = self.federation.all_links().get(client_clan_id)
            verify_pub = fed_link.sign_pub_hex if fed_link and fed_link.sign_pub_hex else client_pub
            try:
                from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
                pub_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(verify_pub))
                pub_key.verify(bytes.fromhex(sig), bytes.fromhex(nonce))
            except Exception as e:
                logger.warning("S2S auth failed for %s: %s", client_clan_id, e)
                await ws.send(json.dumps({"type": "auth_fail", "reason": "s2s authentication failed"}))
                await ws.close()
                return fail
        else:
            if not self.auth.verify_response(client_clan_id, nonce, sig, client_pub):
                await ws.send(json.dumps({"type": "auth_fail", "reason": "authentication failed"}))
                await ws.close()
                return fail

        # Step 4: AUTH_OK
        depth = self.queue.depth(client_clan_id) if client_role != "hub" else 0
        await ws.send(json.dumps({
            "type": "auth_ok",
            "clan_id": client_clan_id,
            "queue_depth": depth,
        }))
        return (client_clan_id, client_role, client_local_peers)

    async def _authenticate_legacy(self, ws: Any, first_frame: dict) -> str | None:
        """Handle legacy clients that skip HELLO and send auth directly.

        Tolerant mode: extracts clan_id/sign_pub from whatever the client
        sent first, then runs challenge-response. Accepts clan_id and sign_pub
        from either the first frame or the auth response frame.
        """
        # Extract identity from first frame (whatever type it is)
        initial_clan_id = first_frame.get("clan_id", first_frame.get("from", ""))
        initial_pub = first_frame.get("sign_pub", "")

        # Generate challenge and send it
        nonce = self.auth.generate_challenge()
        await ws.send(json.dumps({"type": "challenge", "nonce": nonce}))

        # Wait for auth response with signed nonce
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=self.config.auth_timeout)
            frame = json.loads(raw)
        except (TimeoutError, json.JSONDecodeError):
            await ws.send(json.dumps({"type": "auth_fail", "reason": "timeout"}))
            await ws.close()
            return None

        # Tolerant: accept any frame with nonce_response, not just type=auth
        sig = frame.get("nonce_response", "")
        if not sig:
            await ws.send(json.dumps({"type": "auth_fail", "reason": "missing nonce_response"}))
            await ws.close()
            return None

        # Use clan_id/sign_pub from auth frame if present, fall back to first frame
        clan_id = frame.get("clan_id", initial_clan_id)
        pub = frame.get("sign_pub", initial_pub)

        if not self.auth.verify_response(clan_id, nonce, sig, pub):
            await ws.send(json.dumps({"type": "auth_fail", "reason": "authentication failed"}))
            await ws.close()
            return None

        depth = self.queue.depth(clan_id)
        await ws.send(json.dumps({"type": "auth_ok", "clan_id": clan_id, "queue_depth": depth}))
        return clan_id

    async def _drain_queue(self, ws: Any, clan_id: str) -> None:
        """Send queued messages to a newly connected peer (§15.7.2)."""
        while True:
            messages, remaining = self.queue.drain(clan_id)
            if not messages:
                break
            await ws.send(
                json.dumps(
                    {
                        "type": "drain",
                        "messages": messages,
                        "remaining": remaining,
                    }
                )
            )

    async def _broadcast_presence(self, clan_id: str, status: str) -> None:
        """Notify connected peers of presence change (§15.5.1)."""
        frame = json.dumps(
            {
                "type": "presence",
                "clan_id": clan_id,
                "status": status,
            }
        )
        for entry in self.connections.all_except(clan_id):
            try:
                await entry.ws.send(frame)
            except Exception:
                pass

        # S2S: Notify federated hubs of local peer status change (§17)
        s2s_frame = json.dumps({
            "type": "s2s_presence",
            "clan_id": clan_id,
            "status": status,
            "hub_id": self._hub_id,
        })
        for link in self.federation.active_links():
            try:
                await link.ws.send(s2s_frame)
            except Exception:
                pass

    # -- S2S Outbound (§17) ------------------------------------------------

    async def _s2s_outbound(self, link: FederationLink) -> None:
        """Maintain a persistent S2S connection to a remote hub."""
        import websockets

        while self._running:
            try:
                link.reconnect_backoff = max(link.reconnect_backoff, 1.0)
                logger.info("S2S connecting to %s (%s)", link.hub_id, link.ws_uri)

                async with websockets.connect(link.ws_uri) as ws:
                    # HELLO with role: "hub"
                    local_peers = self.connections.connected_clan_ids()
                    await ws.send(json.dumps({
                        "type": "hello",
                        "clan_id": self._hub_id,
                        "role": "hub",
                        "sign_pub": self._get_hub_sign_pub(),
                        "protocol_version": self._get_version(),
                        "capabilities": ["e2e_crypto", "store_forward", "s2s"],
                        "local_peers": local_peers,
                    }))

                    # CHALLENGE
                    raw = await asyncio.wait_for(ws.recv(), timeout=10)
                    frame = json.loads(raw)
                    if frame.get("type") != "challenge":
                        logger.warning("S2S %s: expected challenge, got %s", link.hub_id, frame.get("type"))
                        continue

                    nonce_hex = frame["nonce"]
                    sig = self._sign_nonce(nonce_hex)
                    if not sig:
                        logger.error("S2S %s: cannot sign nonce (no keys)", link.hub_id)
                        continue

                    await ws.send(json.dumps({"type": "auth", "nonce_response": sig}))

                    # AUTH_OK
                    raw = await asyncio.wait_for(ws.recv(), timeout=10)
                    frame = json.loads(raw)
                    if frame.get("type") != "auth_ok":
                        logger.warning("S2S %s: auth failed: %s", link.hub_id, frame)
                        await asyncio.sleep(link.reconnect_backoff)
                        link.reconnect_backoff = min(link.reconnect_backoff * 2, self.config.s2s_max_backoff)
                        continue

                    # Connected!
                    link.ws = ws
                    link.connected = True
                    link.reconnect_backoff = 1.0
                    logger.info("S2S connected to %s", link.hub_id)

                    # Recv loop: forward incoming messages to local router
                    async for raw in ws:
                        try:
                            frame = json.loads(raw)
                        except json.JSONDecodeError:
                            continue

                        ftype = frame.get("type", "")

                        if ftype == "msg":
                            payload = frame.get("payload", {})
                            if isinstance(payload, dict) and "dst" in payload:
                                await self.router.route(payload, link.hub_id)

                        elif ftype == "s2s_presence":
                            peer_id = frame.get("clan_id", "")
                            status = frame.get("status", "")
                            hub_id = frame.get("hub_id", link.hub_id)
                            if peer_id:
                                current = list(link.remote_peers)
                                if status == "online" and peer_id not in current:
                                    current.append(peer_id)
                                elif status == "offline":
                                    current = [p for p in current if p != peer_id]
                                self.federation.update_remote_peers(hub_id, current)
                            logger.info("S2S presence from %s: %s %s", hub_id, peer_id, status)

                        elif ftype == "pong":
                            pass  # keepalive

            except (ConnectionRefusedError, OSError) as e:
                logger.info("S2S %s: connection failed: %s (retry in %.0fs)",
                            link.hub_id, e, link.reconnect_backoff)
            except Exception as e:
                logger.info("S2S %s: disconnected: %s (retry in %.0fs)",
                            link.hub_id, e, link.reconnect_backoff)
            finally:
                link.ws = None
                link.connected = False

            if not self._running:
                break
            await asyncio.sleep(link.reconnect_backoff)
            link.reconnect_backoff = min(link.reconnect_backoff * 2, self.config.s2s_max_backoff)

    def _get_hub_sign_pub(self) -> str:
        """Get this hub's Ed25519 public key hex for S2S auth."""
        fed_path = self.hub_dir / self.config.federation_file
        if not fed_path.exists():
            return ""
        try:
            data = json.loads(fed_path.read_text())
            return data.get("self", {}).get("sign_pub", "")
        except Exception:
            return ""

    def _sign_nonce(self, nonce_hex: str) -> str | None:
        """Sign a nonce with this hub's Ed25519 private key."""
        fed_path = self.hub_dir / self.config.federation_file
        if not fed_path.exists():
            return None
        try:
            data = json.loads(fed_path.read_text())
            key_file = data.get("self", {}).get("key_file", "")
            if not key_file:
                return None
            key_path = Path(os.path.expanduser(key_file))
            key_data = json.loads(key_path.read_text())
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(key_data["sign_private"]))
            sig = priv.sign(bytes.fromhex(nonce_hex))
            return sig.hex()
        except Exception as e:
            logger.error("Failed to sign nonce: %s", e)
            return None

    @staticmethod
    def _get_version() -> str:
        try:
            from hermes import __version__
            return __version__
        except Exception:
            return "0.4.2a1"

    # -- Legacy HTTP handler ------------------------------------------------

    async def _process_http(self, connection: Any, request: Any) -> Any:
        """Handle legacy HTTP endpoints alongside WebSocket (§15.4.2).

        In websockets >= 13, process_request receives (connection, request).
        Return a Response to short-circuit, or None to proceed with WS upgrade.
        """
        # websockets 13+ changed the process_request signature.
        # For now, skip legacy endpoints and let all connections proceed as WebSocket.
        return None

    # -- Sweep loop ---------------------------------------------------------

    async def _sweep_loop(self) -> None:
        """Periodic TTL eviction of store-and-forward queues (§15.7.1)."""
        while self._running:
            await asyncio.sleep(self.config.queue_sweep_interval)
            removed = self.queue.sweep_expired()
            if removed:
                logger.debug("Sweep: removed %d expired messages", removed)
            self._save_state()


# ---------------------------------------------------------------------------
# CLI Entry Points
# ---------------------------------------------------------------------------


def cmd_hub_start(hub_dir: Path, foreground: bool = False) -> int:
    """Start the Hub server."""
    config_path = hub_dir / "gateway.json"
    if not config_path.exists():
        config_path = hub_dir / "config.toml"

    config = load_hub_config(config_path)

    peers_path = hub_dir / config.peers_file
    if not peers_path.exists():
        print(f"Error: peers file not found: {peers_path}")
        print("  Run 'hermes hub init' to generate it from your peer registry.")
        return 1

    # PID lock
    lock_dir = hub_dir / "hub.lock"
    try:
        os.mkdir(lock_dir)
    except FileExistsError:
        pid_file = lock_dir / "pid"
        if pid_file.exists():
            old_pid = int(pid_file.read_text().strip())
            try:
                os.kill(old_pid, 0)
                print(f"Hub already running (PID {old_pid})")
                return 1
            except OSError:
                pass  # Stale lock
        import shutil

        shutil.rmtree(lock_dir)
        os.mkdir(lock_dir)

    (lock_dir / "pid").write_text(str(os.getpid()))

    hub = HubServer(config, hub_dir)

    def _shutdown(signum: int, frame: Any) -> None:
        logger.info("Shutdown signal received")
        hub._running = False

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    loop = asyncio.new_event_loop()
    try:
        if foreground:
            print(f"Hub starting on {config.listen_host}:{config.listen_port}")
        loop.run_until_complete(hub.start())
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(hub.stop())
        loop.close()
        import shutil

        shutil.rmtree(lock_dir, ignore_errors=True)
    return 0


def cmd_hub_stop(hub_dir: Path) -> int:
    """Stop the running Hub."""
    lock_dir = hub_dir / "hub.lock"
    pid_file = lock_dir / "pid"
    if not pid_file.exists():
        print("No Hub running")
        return 1

    pid = int(pid_file.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"Sent SIGTERM to Hub (PID {pid})")
        return 0
    except OSError as e:
        print(f"Failed to stop Hub: {e}")
        return 1


def cmd_hub_status(hub_dir: Path) -> int:
    """Print Hub status."""
    state_path = hub_dir / "hub-state.json"
    state = HubState.load(state_path)
    if not state:
        print("No Hub state found")
        return 1

    lock_dir = hub_dir / "hub.lock"
    pid_file = lock_dir / "pid"
    running = False
    if pid_file.exists():
        pid = int(pid_file.read_text().strip())
        try:
            os.kill(pid, 0)
            running = True
        except OSError:
            pass

    print(f"Hub Status: {'RUNNING' if running else 'STOPPED'}")
    print(f"  PID: {state.pid}")
    print(f"  Started: {state.started_at}")
    print(f"  Uptime: {state.uptime_seconds:.0f}s")
    print(f"  Messages routed: {state.total_msgs_routed}")
    return 0


def cmd_hub_init(hub_dir: Path, force: bool = False) -> int:
    """Generate hub-peers.json from existing gateway config + peer keys."""
    from .config import load_config

    peers_path = hub_dir / "hub-peers.json"
    if peers_path.exists() and not force:
        print(f"hub-peers.json already exists: {peers_path}")
        print("  Use --force to overwrite.")
        return 1

    # Load gateway config for peer list + self identity
    config_path = hub_dir / "gateway.json"
    if not config_path.exists():
        config_path = hub_dir / "config.toml"
    if not config_path.exists():
        print("Error: no gateway.json or config.toml found")
        return 1

    gw = load_config(config_path)
    hub_peers: dict[str, dict[str, str]] = {}

    # Self-registration: read own public key
    own_pub_path = hub_dir / gw.keys_public
    if own_pub_path.exists():
        sign_hex = _read_sign_pub(own_pub_path)
        if sign_hex:
            hub_peers[gw.clan_id] = {
                "sign_pub": sign_hex,
                "display_name": gw.display_name,
                "registered_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }

    # Peer registration
    for peer in gw.peers:
        pub_path = hub_dir / peer.public_key_file
        if not pub_path.exists():
            print(f"  Warning: key file not found for {peer.clan_id}: {pub_path}")
            continue
        sign_hex = _read_sign_pub(pub_path)
        if not sign_hex:
            print(f"  Warning: could not extract sign_pub for {peer.clan_id}")
            continue
        hub_peers[peer.clan_id] = {
            "sign_pub": sign_hex,
            "display_name": "",
            "registered_at": peer.added or "",
        }

    peers_path.write_text(json.dumps({"peers": hub_peers}, indent=2) + "\n")
    print(f"Created {peers_path} with {len(hub_peers)} peer(s)")
    for clan_id, info in hub_peers.items():
        pub_short = info["sign_pub"][:8] + "..." if info["sign_pub"] else "?"
        print(f"  {clan_id}: (pub: {pub_short})")
    return 0


def _read_sign_pub(pub_path: Path) -> str | None:
    """Read Ed25519 sign public key from a .pub file (JSON or raw hex)."""
    text = pub_path.read_text().strip()
    # Raw hex string (64 hex chars = 32 bytes Ed25519)
    if len(text) == 64 and all(c in "0123456789abcdefABCDEF" for c in text):
        return text
    try:
        data = json.loads(text)
        return data.get("sign_public") or data.get("ed25519_pub") or None
    except (json.JSONDecodeError, AttributeError):
        return None


def cmd_hub_peers(hub_dir: Path) -> int:
    """List registered peers."""
    config = load_hub_config(hub_dir / "gateway.json")
    peers = load_peers(hub_dir / config.peers_file)

    if not peers:
        print("No peers registered")
        return 0

    print(f"Registered peers ({len(peers)}):")
    for clan_id, info in peers.items():
        pub_short = info.sign_pub_hex[:8] + "..." if info.sign_pub_hex else "?"
        print(f"  {clan_id}: {info.display_name} (pub: {pub_short})")
    return 0
