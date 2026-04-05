"""Shared fixtures for HERMES test suite.

Includes bilateral test infrastructure for simulating multiple clans
on a single machine with real WebSocket connections.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from amaru.hub import HubConfig, HubServer


# ---------------------------------------------------------------------------
# Clan Factory — creates temporary clan directories with keys
# ---------------------------------------------------------------------------

@dataclass
class ClanInfo:
    """Info about a test clan created by clan_factory."""

    clan_id: str
    dir: Path
    port: int
    sign_key: Ed25519PrivateKey
    sign_pub_hex: str


def _generate_keys() -> tuple[Ed25519PrivateKey, str]:
    """Generate Ed25519 keypair, return (private_key, public_hex)."""
    priv = Ed25519PrivateKey.generate()
    pub_hex = priv.public_key().public_bytes_raw().hex()
    return priv, pub_hex


@pytest.fixture
def clan_factory(tmp_path):
    """Factory fixture to create temporary clan directories.

    Usage:
        clan_a = clan_factory("alice", 18443, {"bob": bob_pub_hex})
    """

    def _create(
        clan_id: str,
        port: int,
        peers: dict[str, str] | None = None,
    ) -> ClanInfo:
        peers = peers or {}
        clan_dir = tmp_path / clan_id
        clan_dir.mkdir(parents=True, exist_ok=True)

        # Generate clan keys
        sign_key, sign_pub_hex = _generate_keys()

        # gateway.json (hub config)
        gateway = {
            "agent_node": {
                "hub": {
                    "listen_port": port,
                    "listen_host": "127.0.0.1",
                    "auth_timeout": 5,
                    "max_queue_depth": 100,
                }
            }
        }
        (clan_dir / "gateway.json").write_text(json.dumps(gateway))

        # hub-peers.json (self + peers)
        peer_entries = {
            clan_id: {
                "sign_pub": sign_pub_hex,
                "display_name": f"Test Clan {clan_id}",
            }
        }
        for pid, pub_hex in peers.items():
            peer_entries[pid] = {
                "sign_pub": pub_hex,
                "display_name": f"Test Clan {pid}",
            }
        (clan_dir / "hub-peers.json").write_text(
            json.dumps({"peers": peer_entries})
        )

        # Empty federation config (no S2S for Tier 1)
        (clan_dir / "federation-peers.json").write_text(
            json.dumps({"hubs": {}, "self": {"hub_id": f"{clan_id}-hub", "sign_pub": sign_pub_hex}})
        )

        # Empty bus and inbox
        (clan_dir / "bus.jsonl").touch()
        (clan_dir / "hub-inbox.jsonl").touch()

        # Keys directory
        keys_dir = clan_dir / "keys"
        keys_dir.mkdir(exist_ok=True)
        key_data = {
            "sign_private": sign_key.private_bytes_raw().hex(),
            "sign_public": sign_pub_hex,
        }
        (keys_dir / f"{clan_id}.key").write_text(json.dumps(key_data))

        # Peer pub keys
        peers_dir = keys_dir / "peers"
        peers_dir.mkdir(exist_ok=True)
        for pid, pub_hex in peers.items():
            (peers_dir / f"{pid}.pub").write_text(pub_hex)

        return ClanInfo(
            clan_id=clan_id,
            dir=clan_dir,
            port=port,
            sign_key=sign_key,
            sign_pub_hex=sign_pub_hex,
        )

    return _create


# ---------------------------------------------------------------------------
# Hub Test Client — WebSocket client with HELLO/AUTH handshake
# ---------------------------------------------------------------------------

@dataclass
class HubTestClient:
    """Lightweight WebSocket client for bilateral testing."""

    ws: object  # websockets connection
    clan_id: str
    _sign_key: Ed25519PrivateKey

    async def send_msg(self, dst: str, msg_type: str, msg: str) -> None:
        """Send a routed message through the hub."""
        frame = {
            "type": "msg",
            "payload": {
                "src": self.clan_id,
                "dst": dst,
                "type": msg_type,
                "msg": msg,
            },
        }
        await self.ws.send(json.dumps(frame))

    async def recv(self, timeout: float = 5.0) -> dict:
        """Receive and parse the next frame from the hub."""
        raw = await asyncio.wait_for(self.ws.recv(), timeout=timeout)
        return json.loads(raw)

    async def recv_until(
        self, frame_type: str, timeout: float = 5.0
    ) -> dict:
        """Receive frames until one matches the given type."""
        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise TimeoutError(f"No {frame_type!r} frame within {timeout}s")
            frame = await self.recv(timeout=remaining)
            if frame.get("type") == frame_type:
                return frame

    async def close(self) -> None:
        await self.ws.close()


async def connect_hub_client(
    uri: str,
    clan_id: str,
    sign_key: Ed25519PrivateKey,
    protocol_version: str = "0.4.2a1",
) -> HubTestClient:
    """Connect to a hub and perform HELLO/CHALLENGE/AUTH handshake.

    Returns an authenticated HubTestClient ready to send/receive.
    """
    import websockets

    ws = await websockets.connect(uri)

    # HELLO
    pub_hex = sign_key.public_key().public_bytes_raw().hex()
    await ws.send(json.dumps({
        "type": "hello",
        "clan_id": clan_id,
        "sign_pub": pub_hex,
        "protocol_version": protocol_version,
        "capabilities": ["e2e_crypto"],
    }))

    # CHALLENGE
    challenge = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
    assert challenge["type"] == "challenge", f"Expected challenge, got {challenge}"

    # AUTH (sign the nonce)
    nonce_bytes = bytes.fromhex(challenge["nonce"])
    signature = sign_key.sign(nonce_bytes)
    await ws.send(json.dumps({
        "type": "auth",
        "nonce_response": signature.hex(),
    }))

    # AUTH_OK
    auth_ok = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
    assert auth_ok["type"] == "auth_ok", f"Expected auth_ok, got {auth_ok}"

    return HubTestClient(ws=ws, clan_id=clan_id, _sign_key=sign_key)


