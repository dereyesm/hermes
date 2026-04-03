#!/usr/bin/env python3
"""HERMES Hub P2P MCP Server — Real-time bilateral communication.

Connects to a HERMES hub via WebSocket (ARC-4601 §15) and exposes
MCP tools for sending/receiving messages between clans.

Supports two auth modes:
  - ed25519: HELLO/CHALLENGE/AUTH flow (ARC-4601 §15.6)
  - token: Simple token-based auth (JEI hub compat)

Usage:
    # Ed25519 auth (DANI hub):
    python3 quest005_hub_mcp.py --clan-id momoshod --host 127.0.0.1 --auth ed25519 --key-file ~/.hermes/keys/momoshod.key

    # Token auth (JEI hub):
    python3 quest005_hub_mcp.py --clan-id momoshod --host 192.168.68.101 --auth token --token <hex>

    # Register as MCP server in Claude Code:
    claude mcp add hub-p2p -- python3 /path/to/quest005_hub_mcp.py --clan-id momoshod --host 127.0.0.1 --auth ed25519 --key-file ~/.hermes/keys/momoshod.key
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import threading
import queue
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import websockets
except ImportError:
    sys.stderr.write("ERROR: pip install websockets\n")
    sys.exit(1)


# Message queues for async WebSocket <-> sync MCP bridge
incoming_queue: queue.Queue = queue.Queue()
outgoing_queue: queue.Queue = queue.Queue()
ws_connected = threading.Event()
ws_error: str | None = None
online_peers: list[str] = []
_peer_lock = threading.Lock()


def now_cot() -> str:
    cot = timezone(timedelta(hours=-5))
    return datetime.now(cot).strftime("%H:%M:%S COT")


# ---------------------------------------------------------------------------
# Ed25519 auth helpers
# ---------------------------------------------------------------------------

def _load_ed25519_keys(key_file: str):
    """Load Ed25519 signing key from HERMES key file."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "reference" / "python"))
    from hermes.crypto import ClanKeyPair
    with open(os.path.expanduser(key_file)) as f:
        data = json.load(f)
    return ClanKeyPair.from_private_hex(data["sign_private"], data["dh_private"])


async def _auth_ed25519(ws, clan_id: str, keys) -> bool:
    """ARC-4601 §15.6 HELLO/CHALLENGE/AUTH flow."""
    sign_pub_hex = keys.sign_public.public_bytes_raw().hex()
    hello = {
        "type": "hello",
        "clan_id": clan_id,
        "sign_pub": sign_pub_hex,
        "protocol_version": "0.4.2a1",
        "capabilities": ["e2e_crypto", "store_forward"],
    }
    await ws.send(json.dumps(hello))

    raw = await asyncio.wait_for(ws.recv(), timeout=10)
    frame = json.loads(raw)
    if frame.get("type") != "challenge":
        return False

    nonce_hex = frame["nonce"]
    sig = keys.sign_private.sign(bytes.fromhex(nonce_hex))
    await ws.send(json.dumps({"type": "auth", "nonce_response": sig.hex()}))

    raw = await asyncio.wait_for(ws.recv(), timeout=10)
    frame = json.loads(raw)
    return frame.get("type") == "auth_ok"


async def _auth_token(ws, clan_id: str, token: str) -> bool:
    """Token-based auth (JEI hub compat)."""
    await ws.send(json.dumps({"from": clan_id, "token": token, "hello": True}))
    raw = await asyncio.wait_for(ws.recv(), timeout=10)
    frame = json.loads(raw)
    return frame.get("ack", False)


# ---------------------------------------------------------------------------
# WebSocket background thread (with reconnect)
# ---------------------------------------------------------------------------

def ws_thread(clan_id: str, host: str, port: int, auth_mode: str,
              key_file: str | None = None, token: str | None = None):
    """Run WebSocket connection in background thread with auto-reconnect."""
    global ws_error

    keys = None
    if auth_mode == "ed25519" and key_file:
        keys = _load_ed25519_keys(key_file)

    async def _run():
        global ws_error
        uri = f"ws://{host}:{port}"
        backoff = 1

        while True:  # reconnect loop
            try:
                ws_error = None
                async with websockets.connect(uri) as ws:
                    # Authenticate
                    if auth_mode == "ed25519" and keys:
                        ok = await _auth_ed25519(ws, clan_id, keys)
                    elif auth_mode == "token" and token:
                        ok = await _auth_token(ws, clan_id, token)
                    else:
                        ok = False

                    if not ok:
                        ws_error = f"Auth failed ({auth_mode})"
                        ws_connected.set()
                        return

                    ws_connected.set()
                    backoff = 1  # reset on success
                    sys.stderr.write(f"[HUB-MCP] Connected to {uri} as {clan_id} ({auth_mode})\n")

                    # Background receiver
                    async def recv_loop():
                        async for raw in ws:
                            try:
                                frame = json.loads(raw)
                            except json.JSONDecodeError:
                                continue

                            ftype = frame.get("type", "")

                            if ftype == "msg":
                                # ARC-4601 routed message
                                payload = frame.get("payload", {})
                                incoming_queue.put({
                                    "from": payload.get("src", "?"),
                                    "text": payload.get("msg", ""),
                                    "dst": payload.get("dst", "*"),
                                    "msg_type": payload.get("type", "event"),
                                })

                            elif ftype == "presence":
                                cid = frame.get("clan_id", "?")
                                status = frame.get("status", "?")
                                with _peer_lock:
                                    if status == "online" and cid not in online_peers:
                                        online_peers.append(cid)
                                    elif status == "offline" and cid in online_peers:
                                        online_peers.remove(cid)
                                incoming_queue.put({
                                    "from": "HUB",
                                    "text": f"Peer {cid}: {status}",
                                    "presence": True,
                                })

                            elif ftype == "drain":
                                for m in frame.get("messages", []):
                                    incoming_queue.put({
                                        "from": m.get("src", "?"),
                                        "text": m.get("msg", ""),
                                        "queued": True,
                                    })

                            elif ftype == "pong":
                                pass  # keepalive ack

                            elif frame.get("text") or frame.get("from"):
                                # Fallback: JEI hub simple format
                                incoming_queue.put({
                                    "from": frame.get("from", "?"),
                                    "text": frame.get("text", ""),
                                })

                    # Background sender (ARC-4601 format)
                    async def send_loop():
                        while True:
                            await asyncio.sleep(0.05)
                            try:
                                item = outgoing_queue.get_nowait()
                                if isinstance(item, dict):
                                    dst = item.get("dst", "*")
                                    text = item.get("text", "")
                                else:
                                    dst = "*"
                                    text = str(item)

                                await ws.send(json.dumps({
                                    "type": "msg",
                                    "payload": {
                                        "src": clan_id,
                                        "dst": dst,
                                        "type": "event",
                                        "msg": text,
                                        "ttl": 3600,
                                    }
                                }))
                            except queue.Empty:
                                pass

                    # Keepalive
                    async def ping_loop():
                        while True:
                            await asyncio.sleep(45)
                            try:
                                await ws.send(json.dumps({"type": "ping"}))
                            except Exception:
                                break

                    await asyncio.gather(recv_loop(), send_loop(), ping_loop())

            except (ConnectionRefusedError, OSError) as e:
                ws_error = f"Connection failed: {e}"
                sys.stderr.write(f"[HUB-MCP] {ws_error}, retry in {backoff}s\n")
                ws_connected.set()
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
            except Exception as e:
                ws_error = f"Disconnected: {e}"
                sys.stderr.write(f"[HUB-MCP] {ws_error}, retry in {backoff}s\n")
                ws_connected.set()
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# MCP Protocol (JSON-RPC over stdio)
# ---------------------------------------------------------------------------

def read_message() -> dict | None:
    """Read a JSON-RPC message from stdin (MCP stdio transport)."""
    headers = {}
    while True:
        line = sys.stdin.readline()
        if not line:
            return None
        line = line.strip()
        if line == "":
            break
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()

    length = int(headers.get("content-length", 0))
    if length == 0:
        return None

    body = sys.stdin.read(length)
    return json.loads(body)


def write_message(msg: dict):
    """Write a JSON-RPC message to stdout (MCP stdio transport)."""
    body = json.dumps(msg)
    header = f"Content-Length: {len(body)}\r\n\r\n"
    sys.stdout.write(header)
    sys.stdout.write(body)
    sys.stdout.flush()


def handle_initialize(req: dict) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": req["id"],
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {
                "name": "hub-bilateral",
                "version": "1.0.0",
            },
        },
    }


def handle_tools_list(req: dict) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": req["id"],
        "result": {
            "tools": [
                {
                    "name": "hub_send",
                    "description": "Send a message through the HERMES hub (ARC-4601). Delivered in real-time via WebSocket to online peers, or queued for offline peers.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "message": {
                                "type": "string",
                                "description": "The message text to send",
                            },
                            "dst": {
                                "type": "string",
                                "description": "Destination clan_id (e.g. 'jei', 'momoshod') or '*' for broadcast. Default: '*'",
                                "default": "*",
                            },
                        },
                        "required": ["message"],
                    },
                },
                {
                    "name": "hub_read",
                    "description": "Read the next message from the hub. Returns the oldest unread message, or waits up to timeout_seconds.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "timeout_seconds": {
                                "type": "integer",
                                "description": "How long to wait for a message (default: 30)",
                                "default": 30,
                            }
                        },
                    },
                },
                {
                    "name": "hub_peers",
                    "description": "List currently connected peers on the hub.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                    },
                },
                {
                    "name": "hub_status",
                    "description": "Check the hub connection status, error state, and queue depths.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                    },
                },
            ]
        },
    }


def handle_tool_call(req: dict) -> dict:
    params = req.get("params", {})
    tool_name = params.get("name", "")
    args = params.get("arguments", {})

    if tool_name == "hub_send":
        message = args.get("message", "")
        dst = args.get("dst", "*")
        if not ws_connected.is_set():
            return _tool_result(req, f"Error: WebSocket not connected. {ws_error or ''}")
        if ws_error:
            return _tool_result(req, f"Error: {ws_error}")
        outgoing_queue.put({"text": message, "dst": dst})
        return _tool_result(req, f"Sent at {now_cot()} → dst:{dst}. Message: {message[:200]}")

    elif tool_name == "hub_read":
        timeout = args.get("timeout_seconds", 30)
        try:
            msg = incoming_queue.get(timeout=timeout)
            sender = msg.get("from", "?")
            text = msg.get("text", json.dumps(msg))
            remaining = incoming_queue.qsize()
            result = {
                "from": sender,
                "text": text,
                "received_at": now_cot(),
                "queue_remaining": remaining,
            }
            if msg.get("presence"):
                result["presence"] = True
            if msg.get("queued"):
                result["queued"] = True
            return _tool_result(req, json.dumps(result, ensure_ascii=False))
        except queue.Empty:
            return _tool_result(req, json.dumps({
                "from": None,
                "text": None,
                "status": "timeout",
                "waited_seconds": timeout,
            }))

    elif tool_name == "hub_peers":
        with _peer_lock:
            peers = list(online_peers)
        return _tool_result(req, json.dumps({
            "online_peers": peers,
            "count": len(peers),
        }))

    elif tool_name == "hub_status":
        return _tool_result(req, json.dumps({
            "connected": ws_connected.is_set() and ws_error is None,
            "error": ws_error,
            "incoming_queue": incoming_queue.qsize(),
            "outgoing_queue": outgoing_queue.qsize(),
            "online_peers": len(online_peers),
        }))

    else:
        return _tool_result(req, f"Unknown tool: {tool_name}")


def _tool_result(req: dict, text: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": req["id"],
        "result": {
            "content": [{"type": "text", "text": text}],
        },
    }


def main():
    parser = argparse.ArgumentParser(description="HERMES Hub P2P MCP Server (ARC-4601)")
    parser.add_argument("--clan-id", required=True, help="Your clan_id (e.g. momoshod, jei)")
    parser.add_argument("--host", default="127.0.0.1", help="Hub host IP")
    parser.add_argument("--port", type=int, default=8443, help="Hub port")
    parser.add_argument("--auth", choices=["ed25519", "token"], default="ed25519",
                        help="Auth mode: ed25519 (DANI hub) or token (JEI hub)")
    parser.add_argument("--key-file", help="Path to HERMES key file (for ed25519 auth)")
    parser.add_argument("--token", help="Auth token (for token auth)")
    args = parser.parse_args()

    if args.auth == "ed25519" and not args.key_file:
        sys.stderr.write("ERROR: --key-file required for ed25519 auth\n")
        sys.exit(1)
    if args.auth == "token" and not args.token:
        sys.stderr.write("ERROR: --token required for token auth\n")
        sys.exit(1)

    # Start WebSocket in background thread
    t = threading.Thread(
        target=ws_thread,
        args=(args.clan_id, args.host, args.port, args.auth),
        kwargs={"key_file": args.key_file, "token": args.token},
        daemon=True,
    )
    t.start()

    # Wait for initial connection
    ws_connected.wait(timeout=15)
    if ws_error:
        sys.stderr.write(f"[HUB-MCP] WebSocket error: {ws_error}\n")

    # MCP message loop
    while True:
        msg = read_message()
        if msg is None:
            break

        method = msg.get("method", "")

        if method == "initialize":
            write_message(handle_initialize(msg))
        elif method == "notifications/initialized":
            pass  # no response needed
        elif method == "tools/list":
            write_message(handle_tools_list(msg))
        elif method == "tools/call":
            write_message(handle_tool_call(msg))
        elif method == "ping":
            write_message({"jsonrpc": "2.0", "id": msg.get("id"), "result": {}})
        else:
            sys.stderr.write(f"[HUB-MCP] Unknown method: {method}\n")


if __name__ == "__main__":
    main()
