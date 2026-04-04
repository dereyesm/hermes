#!/usr/bin/env python3
"""HERMES Hub Send — One-shot message delivery via hub WebSocket.

Usage:
    python3 scripts/hub_send.py --dst jei --type event --msg "your message"
    python3 scripts/hub_send.py --dst '*' --type state --msg "broadcast"

Connects to local hub, authenticates as momoshod, sends one message, exits.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "reference" / "python"))

from hermes.crypto import ClanKeyPair


def load_keys() -> tuple[ClanKeyPair, str]:
    """Load momoshod keypair from ~/.hermes/keys/."""
    key_path = Path.home() / ".hermes" / "keys" / "momoshod.key"
    with open(key_path) as f:
        priv_data = json.load(f)
    keys = ClanKeyPair.from_private_hex(priv_data["sign_private"], priv_data["dh_private"])
    return keys, "momoshod"


async def send_message(dst: str, msg_type: str, msg: str, host: str, port: int) -> bool:
    """Connect to hub, authenticate, send one message, disconnect."""
    import websockets

    keys, clan_id = load_keys()
    uri = f"ws://{host}:{port}"

    try:
        async with websockets.connect(uri) as ws:
            # HELLO
            hello = {
                "type": "hello",
                "clan_id": clan_id,
                "sign_pub": keys.sign_public.public_bytes_raw().hex(),
                "protocol_version": "0.4.2a1",
                "capabilities": ["e2e_crypto", "store_forward"],
            }
            await ws.send(json.dumps(hello))

            # CHALLENGE
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            frame = json.loads(raw)
            if frame.get("type") != "challenge":
                print(f"[ERROR] Expected challenge, got: {frame.get('type')}", file=sys.stderr)
                return False

            # AUTH
            nonce_bytes = bytes.fromhex(frame["nonce"])
            signature = keys.sign_private.sign(nonce_bytes)
            await ws.send(json.dumps({"type": "auth", "nonce_response": signature.hex()}))

            # AUTH_OK
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            frame = json.loads(raw)
            if frame.get("type") != "auth_ok":
                print(f"[ERROR] Auth failed: {frame.get('reason', 'unknown')}", file=sys.stderr)
                return False

            # SEND MESSAGE
            payload = {
                "type": "msg",
                "payload": {
                    "ts": datetime.now(UTC).isoformat(),
                    "src": clan_id,
                    "dst": dst,
                    "type": msg_type,
                    "msg": msg,
                    "ttl": 14,
                    "ack": [],
                },
            }
            await ws.send(json.dumps(payload))
            print(f"[OK] Sent to {dst}: {msg[:80]}")
            return True

    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Send a message via HERMES hub")
    parser.add_argument("--dst", required=True, help="Destination clan (* for broadcast)")
    parser.add_argument("--type", default="event", help="Message type")
    parser.add_argument("--msg", required=True, help="Message payload")
    parser.add_argument("--host", default="localhost", help="Hub host")
    parser.add_argument("--port", type=int, default=8443, help="Hub port")
    args = parser.parse_args()

    success = asyncio.run(send_message(args.dst, args.type, args.msg, args.host, args.port))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
