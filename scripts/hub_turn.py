#!/usr/bin/env python3
"""HERMES Hub Turn — Send a message and wait for one response.

Designed to be called from Claude Code via Bash tool for turn-based
bilateral communication (Arena, bilateral reviews, etc.)

Usage:
    # Send and wait for response (30s timeout)
    python3 scripts/hub_turn.py --clan DANI --host 192.168.68.101 --send "Hello JEI"

    # Just listen for next message (no send)
    python3 scripts/hub_turn.py --clan DANI --host 192.168.68.101 --listen

    # Send without waiting
    python3 scripts/hub_turn.py --clan DANI --host 192.168.68.101 --send "msg" --no-wait

Output: JSON to stdout for Claude Code to parse
    {"status": "ok", "sent": true, "response": {"from": "JEI", "text": "..."}}
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

try:
    import websockets
except ImportError:
    print(json.dumps({"status": "error", "msg": "pip install websockets"}))
    sys.exit(1)


async def hub_turn(clan: str, host: str, port: int, message: str | None,
                   listen_only: bool, no_wait: bool, timeout: int):
    uri = f"ws://{host}:{port}"
    result = {"status": "ok", "sent": False, "responses": []}

    try:
        async with websockets.connect(uri) as ws:
            # Handshake
            await ws.send(json.dumps({"from": clan, "hello": True}))
            await asyncio.sleep(0.3)

            # Drain any immediate messages (presence notifications etc.)
            try:
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=0.5)
                    msg = json.loads(raw)
                    if msg.get("text"):
                        result["responses"].append(msg)
            except (asyncio.TimeoutError, Exception):
                pass

            # Send message if provided
            if message and not listen_only:
                await ws.send(json.dumps({"from": clan, "text": message}))
                result["sent"] = True

            # Wait for response(s)
            if not no_wait:
                try:
                    deadline = asyncio.get_event_loop().time() + timeout
                    while asyncio.get_event_loop().time() < deadline:
                        remaining = deadline - asyncio.get_event_loop().time()
                        if remaining <= 0:
                            break
                        raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, timeout))
                        msg = json.loads(raw)
                        if msg.get("text"):
                            result["responses"].append(msg)
                            # Got a substantive response, done
                            break
                except asyncio.TimeoutError:
                    if not result["responses"]:
                        result["status"] = "timeout"
                except Exception:
                    pass

    except ConnectionRefusedError:
        result = {"status": "error", "msg": f"Connection refused: {uri}"}
    except Exception as e:
        result = {"status": "error", "msg": str(e)}

    return result


def main():
    parser = argparse.ArgumentParser(description="HERMES Hub Turn")
    parser.add_argument("--clan", default="DANI")
    parser.add_argument("--host", default="192.168.68.101")
    parser.add_argument("--port", type=int, default=8443)
    parser.add_argument("--send", default=None, help="Message to send")
    parser.add_argument("--listen", action="store_true", help="Listen only")
    parser.add_argument("--no-wait", action="store_true", help="Send without waiting")
    parser.add_argument("--timeout", type=int, default=30, help="Wait timeout (seconds)")
    args = parser.parse_args()

    result = asyncio.run(hub_turn(
        args.clan, args.host, args.port,
        args.send, args.listen, args.no_wait, args.timeout
    ))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
