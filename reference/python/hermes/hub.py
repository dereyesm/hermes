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
from datetime import datetime, timezone
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
    max_queue_depth: int = 1000
    queue_sweep_interval: int = 60
    legacy_endpoints: bool = True
    max_connections: int = 100
    auth_timeout: int = 10

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
                m for m in self._queues[dst]
                if (now - m.queued_at) < m.ttl_seconds
            ]
            removed += before - len(self._queues[dst])
            if not self._queues[dst]:
                del self._queues[dst]
        return removed

    def all_depths(self) -> dict[str, int]:
        return {dst: len(q) for dst, q in self._queues.items()}


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
        """Verify Ed25519 signature of nonce against registered peer."""
        peer = self._peers.get(clan_id)
        if not peer:
            return False

        if peer.sign_pub_hex != sign_pub_hex:
            return False

        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PublicKey,
            )

            pub_key = Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(sign_pub_hex)
            )
            pub_key.verify(
                bytes.fromhex(signature_hex), bytes.fromhex(nonce_hex)
            )
            return True
        except Exception:
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
    """

    def __init__(
        self,
        connections: ConnectionTable,
        queue: StoreForwardQueue,
    ):
        self._connections = connections
        self._queue = queue
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
        else:
            ttl = payload.get("ttl", 604800)
            if isinstance(ttl, int):
                ttl_sec = ttl if ttl > 86400 else ttl * 86400  # handle days vs seconds
            else:
                ttl_sec = 604800
            ok = self._queue.enqueue(dst, payload, ttl_sec)
            return {"status": "queued" if ok else "queue_full", "dst": dst}

    async def _broadcast(self, payload: dict, sender: str) -> dict:
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
        self.total_routed += delivered
        return {"status": "broadcast", "delivered": delivered, "failed": failed}


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
        self.router = MessageRouter(self.connections, self.queue)
        self.state = HubState(
            pid=os.getpid(),
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self._server = None
        self._started_at = time.time()
        self._running = False

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

        self._server = await websockets.serve(
            self._handle_connection,
            self.config.listen_host,
            self.config.listen_port,
            ssl=ssl_context,
            process_request=self._process_http if self.config.legacy_endpoints else None,
        )

        self.state.save(self.hub_dir / "hub-state.json")

        # Run sweep loop alongside server
        try:
            await self._sweep_loop()
        except asyncio.CancelledError:
            pass
        finally:
            self._running = False

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
        """Handle a single WebSocket peer connection."""
        clan_id = None
        try:
            # Step 1: Authentication (§15.6)
            clan_id = await self._authenticate(ws)
            if not clan_id:
                return

            # Step 2: Register connection
            entry = self.connections.add(clan_id, ws)
            logger.info("Peer connected: %s", clan_id)

            # Step 3: Notify other peers
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
                    await ws.send(json.dumps({
                        "type": "pong",
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "queue_depth": depth,
                    }))

        except Exception as e:
            if clan_id:
                logger.info("Peer disconnected: %s (%s)", clan_id, type(e).__name__)
        finally:
            if clan_id:
                self.connections.remove(clan_id)
                await self._broadcast_presence(clan_id, "offline")
                self._save_state()

    async def _authenticate(self, ws: Any) -> str | None:
        """Run Ed25519 challenge-response auth. Returns clan_id or None."""
        nonce = self.auth.generate_challenge()
        await ws.send(json.dumps({"type": "challenge", "nonce": nonce}))

        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=self.config.auth_timeout)
            frame = json.loads(raw)
        except (asyncio.TimeoutError, json.JSONDecodeError):
            await ws.send(json.dumps({"type": "auth_fail", "reason": "timeout"}))
            await ws.close()
            return None

        if frame.get("type") != "auth":
            await ws.send(json.dumps({"type": "auth_fail", "reason": "expected auth"}))
            await ws.close()
            return None

        clan_id = frame.get("clan_id", "")
        sig = frame.get("nonce_response", "")
        pub = frame.get("sign_pub", "")

        if not self.auth.verify_response(clan_id, nonce, sig, pub):
            await ws.send(json.dumps({
                "type": "auth_fail",
                "reason": "authentication failed",
            }))
            await ws.close()
            return None

        depth = self.queue.depth(clan_id)
        await ws.send(json.dumps({
            "type": "auth_ok",
            "clan_id": clan_id,
            "queue_depth": depth,
        }))
        return clan_id

    async def _drain_queue(self, ws: Any, clan_id: str) -> None:
        """Send queued messages to a newly connected peer (§15.7.2)."""
        while True:
            messages, remaining = self.queue.drain(clan_id)
            if not messages:
                break
            await ws.send(json.dumps({
                "type": "drain",
                "messages": messages,
                "remaining": remaining,
            }))

    async def _broadcast_presence(self, clan_id: str, status: str) -> None:
        """Notify connected peers of presence change (§15.5.1)."""
        frame = json.dumps({
            "type": "presence",
            "clan_id": clan_id,
            "status": status,
        })
        for entry in self.connections.all_except(clan_id):
            try:
                await entry.ws.send(frame)
            except Exception:
                pass

    # -- Legacy HTTP handler ------------------------------------------------

    async def _process_http(self, path: str, headers: Any) -> Any:
        """Handle legacy HTTP endpoints alongside WebSocket (§15.4.2).

        Returns (status, headers, body) for non-WebSocket requests,
        or None to proceed with WebSocket upgrade.
        """
        from http import HTTPStatus

        if path == "/healthz":
            body = json.dumps({"status": "ok", "uptime": time.time() - self._started_at})
            return HTTPStatus.OK, [("Content-Type", "application/json")], body.encode()

        if path == "/bus/push" or path.startswith("/bus/push"):
            # Legacy POST: we can't easily read POST body in process_request
            # Return 501 — clients should upgrade to WebSocket
            body = json.dumps({"error": "Use WebSocket /ws for message delivery"})
            return HTTPStatus.NOT_IMPLEMENTED, [("Content-Type", "application/json")], body.encode()

        # Not a legacy endpoint — proceed with WebSocket upgrade
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
                "registered_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
