#!/usr/bin/env python3
"""HERMES Hub Client — Connect to a peer's Hub via WebSocket.

Usage:
    python3 scripts/quest005_hub_client.py --clan DANI --host 192.168.68.101 --port 8443

Authenticates via Ed25519 challenge-response (ARC-4601 §15.6),
then enters interactive message exchange mode.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

# Add reference implementation to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "reference" / "python"))

from hermes.crypto import ClanKeyPair, seal_bus_message_ecdhe, load_peer_public


CLAN_MAP = {
    "DANI": {"clan_id": "momoshod", "key_dir": "~/.hermes/keys", "key_file": "momoshod.key"},
    "JEI": {"clan_id": "jei", "key_dir": "~/.hermes/keys", "key_file": "jei.key"},
}


def load_clan_keys(clan_name: str) -> tuple[ClanKeyPair, str]:
    """Load clan keypair. Returns (keypair, clan_id)."""
    info = CLAN_MAP.get(clan_name.upper())
    if not info:
        raise ValueError(f"Unknown clan: {clan_name}. Known: {list(CLAN_MAP.keys())}")

    key_dir = Path(os.path.expanduser(info["key_dir"]))
    key_path = key_dir / info["key_file"]

    with open(key_path) as f:
        priv_data = json.load(f)

    keys = ClanKeyPair.from_private_hex(priv_data["sign_private"], priv_data["dh_private"])
    return keys, info["clan_id"]


async def hub_session(host: str, port: int, keys: ClanKeyPair, clan_id: str):
    """Connect to hub, authenticate, and run interactive session."""
    import websockets

    uri = f"ws://{host}:{port}"
    print(f"[HUB] Connecting to {uri} as '{clan_id}'...")

    async with websockets.connect(uri) as ws:
        sign_pub_hex = keys.sign_public.public_bytes_raw().hex()

        # Step 1: Send HELLO (ARC-4601 §15.6 — client initiates)
        hello = {
            "type": "hello",
            "clan_id": clan_id,
            "sign_pub": sign_pub_hex,
            "protocol_version": "0.4.2a1",
            "capabilities": ["e2e_crypto", "store_forward"],
        }
        await ws.send(json.dumps(hello))
        print(f"[HUB] HELLO sent (clan={clan_id}, v0.4.2a1)")

        # Step 2: Receive CHALLENGE
        raw = await asyncio.wait_for(ws.recv(), timeout=10)
        frame = json.loads(raw)

        if frame.get("type") != "challenge":
            print(f"[HUB] Expected challenge, got: {frame}")
            return

        nonce_hex = frame["nonce"]
        server_version = frame.get("server_version", "unknown")
        server_caps = frame.get("server_capabilities", [])
        print(f"[HUB] Challenge from server (v{server_version}, caps={server_caps})")

        # Step 3: Sign nonce with Ed25519
        nonce_bytes = bytes.fromhex(nonce_hex)
        signature = keys.sign_private.sign(nonce_bytes)

        auth_frame = {
            "type": "auth",
            "nonce_response": signature.hex(),
        }
        await ws.send(json.dumps(auth_frame))

        # Step 4: Wait for auth result
        raw = await asyncio.wait_for(ws.recv(), timeout=10)
        frame = json.loads(raw)

        if frame.get("type") == "auth_ok":
            queue_depth = frame.get("queue_depth", 0)
            print(f"[HUB] Authenticated! Queue depth: {queue_depth}")
        elif frame.get("type") == "auth_fail":
            print(f"[HUB] Auth FAILED: {frame.get('reason', 'unknown')}")
            return
        else:
            print(f"[HUB] Unexpected: {frame}")
            return

        # Step 4: Interactive loop
        print("[HUB] Connected. Commands:")
        print("  /send <text>  — Send plaintext message to all peers")
        print("  /status       — Show connection status")
        print("  /ping         — Ping hub")
        print("  /quit         — Disconnect")
        print("  (any text)    — Send as bus message")
        print()

        # Run receive loop in background
        receive_task = asyncio.create_task(_receive_loop(ws))

        try:
            # Send a presence announcement
            announce = {
                "type": "msg",
                "payload": {
                    "ts": datetime.now(UTC).isoformat(),
                    "src": clan_id,
                    "dst": "*",
                    "type": "state",
                    "msg": f"DANI connected to hub bilateral. 35 skills, 1451 tests, 4 adapters, ARC-1122 conformance 126 vectors. Ready for QUEST-005 Phase 5.",
                    "ttl": 1,
                    "ack": [],
                },
            }
            await ws.send(json.dumps(announce))
            print("[HUB] Announcement sent.")

            # Interactive input loop
            while True:
                try:
                    line = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: input("[DANI] > ")
                    )
                except EOFError:
                    break

                line = line.strip()
                if not line:
                    continue

                if line == "/quit":
                    print("[HUB] Disconnecting...")
                    break

                if line == "/ping":
                    await ws.send(json.dumps({"type": "ping"}))
                    continue

                if line == "/status":
                    print(f"[HUB] Clan: {clan_id} | Host: {host}:{port}")
                    continue

                # Send as bus message
                payload = {
                    "ts": datetime.now(UTC).isoformat(),
                    "src": clan_id,
                    "dst": "*",
                    "type": "event",
                    "msg": line,
                    "ttl": 1,
                    "ack": [],
                }
                await ws.send(json.dumps({"type": "msg", "payload": payload}))
                print(f"[HUB] Sent.")

        except asyncio.CancelledError:
            pass
        finally:
            receive_task.cancel()


async def _receive_loop(ws):
    """Background loop to print incoming messages."""
    try:
        async for raw in ws:
            frame = json.loads(raw)
            ftype = frame.get("type", "")

            if ftype == "msg":
                payload = frame.get("payload", {})
                src = payload.get("src", "?")
                msg = payload.get("msg", "")
                print(f"\n[{src.upper()}] {msg[:200]}")
                print("[DANI] > ", end="", flush=True)

            elif ftype == "presence":
                cid = frame.get("clan_id", "?")
                status = frame.get("status", "?")
                print(f"\n[HUB] Peer {cid}: {status}")
                print("[DANI] > ", end="", flush=True)

            elif ftype == "pong":
                ts = frame.get("ts", "")
                qd = frame.get("queue_depth", 0)
                print(f"\n[HUB] Pong — ts: {ts}, queue: {qd}")
                print("[DANI] > ", end="", flush=True)

            elif ftype == "drain":
                msgs = frame.get("messages", [])
                remaining = frame.get("remaining", 0)
                print(f"\n[HUB] Draining {len(msgs)} queued messages ({remaining} remaining)")
                for m in msgs:
                    src = m.get("src", "?")
                    msg = m.get("msg", "")
                    print(f"  [{src}] {msg[:150]}")
                print("[DANI] > ", end="", flush=True)

            else:
                print(f"\n[HUB] Frame: {json.dumps(frame)[:200]}")
                print("[DANI] > ", end="", flush=True)

    except asyncio.CancelledError:
        pass
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="HERMES Hub Client")
    parser.add_argument("--clan", required=True, help="Clan name (DANI or JEI)")
    parser.add_argument("--host", required=True, help="Hub host IP")
    parser.add_argument("--port", type=int, default=8443, help="Hub port (default: 8443)")
    args = parser.parse_args()

    keys, clan_id = load_clan_keys(args.clan)
    print(f"[INIT] Loaded keys for {args.clan} (clan_id: {clan_id})")
    print(f"[INIT] Sign pub: {keys.sign_public.public_bytes_raw().hex()[:16]}...")

    asyncio.run(hub_session(args.host, args.port, keys, clan_id))


if __name__ == "__main__":
    main()
