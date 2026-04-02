#!/usr/bin/env python3
"""HERMES Hub MCP Server — Bilateral communication via MCP tools.

Exposes hub_send and hub_read as MCP tools so Claude Code can
communicate directly with peer clans through the WebSocket hub.

Usage:
    # Register as MCP server
    claude mcp add hub-bilateral -- python3 /path/to/quest005_hub_mcp.py --clan DANI --host 192.168.68.101

    # Then in Claude Code:
    #   tool: mcp__hub-bilateral__hub_send(message="Hello JEI")
    #   tool: mcp__hub-bilateral__hub_read()
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import threading
import queue
from datetime import datetime, timezone, timedelta

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


def now_cot() -> str:
    cot = timezone(timedelta(hours=-5))
    return datetime.now(cot).strftime("%H:%M:%S COT")


# ---------------------------------------------------------------------------
# WebSocket background thread
# ---------------------------------------------------------------------------

def ws_thread(clan: str, host: str, port: int):
    """Run WebSocket connection in background thread."""
    global ws_error

    async def _run():
        global ws_error
        uri = f"ws://{host}:{port}"
        try:
            async with websockets.connect(uri) as ws:
                # Handshake
                await ws.send(json.dumps({"from": clan, "hello": True}))
                ws_connected.set()
                sys.stderr.write(f"[HUB-MCP] Connected to {uri} as {clan}\n")

                # Background receiver
                async def recv_loop():
                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                            if msg.get("text") or msg.get("from"):
                                incoming_queue.put(msg)
                        except json.JSONDecodeError:
                            pass

                # Background sender
                async def send_loop():
                    while True:
                        await asyncio.sleep(0.1)
                        try:
                            text = outgoing_queue.get_nowait()
                            await ws.send(json.dumps({"from": clan, "text": text}))
                        except queue.Empty:
                            pass

                await asyncio.gather(recv_loop(), send_loop())

        except ConnectionRefusedError:
            ws_error = f"Connection refused: ws://{host}:{port}"
            ws_connected.set()
        except Exception as e:
            ws_error = str(e)
            ws_connected.set()

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
                    "description": "Send a message to the peer clan through the HERMES hub. The message will be delivered in real-time via WebSocket.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "message": {
                                "type": "string",
                                "description": "The message text to send to the peer clan",
                            }
                        },
                        "required": ["message"],
                    },
                },
                {
                    "name": "hub_read",
                    "description": "Read the next message from the peer clan. Returns the oldest unread message, or waits up to timeout_seconds for one to arrive.",
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
                    "name": "hub_status",
                    "description": "Check the hub connection status and message queue depth.",
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
        if not ws_connected.is_set():
            return _tool_result(req, f"Error: WebSocket not connected. {ws_error or ''}")
        if ws_error:
            return _tool_result(req, f"Error: {ws_error}")
        outgoing_queue.put(message)
        return _tool_result(req, f"Sent at {now_cot()}. Message: {message[:100]}...")

    elif tool_name == "hub_read":
        timeout = args.get("timeout_seconds", 30)
        try:
            msg = incoming_queue.get(timeout=timeout)
            sender = msg.get("from", "?")
            text = msg.get("text", json.dumps(msg))
            ts = msg.get("hub_ts", now_cot())
            remaining = incoming_queue.qsize()
            return _tool_result(req, json.dumps({
                "from": sender,
                "text": text,
                "received_at": ts,
                "queue_remaining": remaining,
            }, ensure_ascii=False))
        except queue.Empty:
            return _tool_result(req, json.dumps({
                "from": None,
                "text": None,
                "status": "timeout",
                "waited_seconds": timeout,
            }))

    elif tool_name == "hub_status":
        return _tool_result(req, json.dumps({
            "connected": ws_connected.is_set() and ws_error is None,
            "error": ws_error,
            "incoming_queue": incoming_queue.qsize(),
            "outgoing_queue": outgoing_queue.qsize(),
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
    parser = argparse.ArgumentParser(description="HERMES Hub MCP Server")
    parser.add_argument("--clan", default="DANI")
    parser.add_argument("--host", default="192.168.68.101")
    parser.add_argument("--port", type=int, default=8443)
    args = parser.parse_args()

    # Start WebSocket in background thread
    t = threading.Thread(target=ws_thread, args=(args.clan, args.host, args.port), daemon=True)
    t.start()

    # Wait for connection
    ws_connected.wait(timeout=10)
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
