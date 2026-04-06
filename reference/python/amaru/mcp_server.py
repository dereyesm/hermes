"""Amaru MCP Server — Native protocol access for Claude Code sessions.

Exposes the full Amaru protocol stack as MCP tools:
- Bus operations (ARC-5322, ARC-0793): read, write, ACK
- Session lifecycle (SYN/FIN): session start/end protocols
- Crypto (ARC-8446): ECDHE seal/open with per-peer keys
- Identity & config: clan status, peer list
- Bus integrity (ARC-9001): sequence tracking, ownership

Usage:
    python -m amaru.mcp_server              # stdio transport (for Claude Code)
    amaru mcp serve                         # via CLI
    amaru mcp serve --amaru-dir ~/.amaru  # custom clan directory

Environment:
    AMARU_DIR: Path to clan directory (default: ~/.amaru)
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path

from amaru import __version__
from amaru.bus import (
    ack_message,
    filter_for_namespace,
    find_expired,
    find_stale,
    read_bus,
    write_message,
)
from amaru.message import Message, create_message

# ---------- helpers ----------

_AMARU_DIR = Path(os.environ.get("AMARU_DIR", os.path.expanduser("~/.amaru")))


def _bus_path() -> Path:
    return _AMARU_DIR / "bus.jsonl"


def _msg_to_dict(m: Message) -> dict:
    """Convert a Message to a JSON-serializable dict."""
    d: dict = {
        "ts": str(m.ts),
        "src": m.src,
        "dst": m.dst,
        "type": m.type,
        "msg": m.msg,
        "ttl": m.ttl,
        "ack": list(m.ack),
    }
    if m.seq is not None:
        d["seq"] = m.seq
    return d


# ---------- session cursor ----------


class SessionCursor:
    """Tracks last-read line number for new_only support."""

    def __init__(self) -> None:
        self._last_line: int = 0

    def read_new(self, bus_path: Path) -> list[Message]:
        """Read only messages appended since last call."""
        if not bus_path.exists():
            return []
        lines = bus_path.read_text().splitlines()
        new_lines = lines[self._last_line :]
        self._last_line = len(lines)
        results = []
        for line in new_lines:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                from amaru.message import validate_message

                results.append(validate_message(data))
            except Exception:
                continue
        return results

    def advance_to_end(self, bus_path: Path) -> None:
        """Move cursor to current end without reading."""
        if bus_path.exists():
            self._last_line = len(bus_path.read_text().splitlines())


_cursor = SessionCursor()


# ---------- tool implementations ----------


def tool_bus_read(
    since_minutes: int | None = None,
    namespace: str | None = None,
    type_filter: str | None = None,
    pending_only: bool = False,
    new_only: bool = False,
) -> list[dict]:
    """Read bus messages with filters."""
    bp = _bus_path()

    if new_only:
        messages = _cursor.read_new(bp)
    else:
        if not bp.exists():
            return []
        messages = read_bus(str(bp))
        _cursor.advance_to_end(bp)

    if since_minutes is not None:
        cutoff = date.today() - timedelta(days=since_minutes / 1440)
        messages = [m for m in messages if m.ts >= cutoff]

    if namespace:
        messages = filter_for_namespace(messages, namespace)

    if type_filter:
        messages = [m for m in messages if m.type == type_filter]

    if pending_only:
        messages = [m for m in messages if not m.ack]

    return [_msg_to_dict(m) for m in messages]


def tool_bus_write(
    src: str,
    dst: str,
    type: str,
    msg: str,
    ttl: int = 7,
) -> dict:
    """Write a message to the bus."""
    bp = _bus_path()
    message = create_message(src=src, dst=dst, type=type, msg=msg, ttl=ttl)
    written = write_message(str(bp), message)
    return _msg_to_dict(written)


def tool_bus_ack(
    namespace: str,
    src_filter: str | None = None,
    type_filter: str | None = None,
) -> dict:
    """ACK messages matching filters."""
    bp = _bus_path()

    def match_fn(m: Message) -> bool:
        if namespace not in (m.dst, "*") and m.dst != namespace:
            return False
        if src_filter and m.src != src_filter:
            return False
        if type_filter and m.type != type_filter:
            return False
        return namespace not in m.ack

    count = ack_message(str(bp), namespace, match_fn)
    return {"acked": count, "namespace": namespace}


def tool_syn(namespace: str) -> dict:
    """Execute SYN protocol — returns pending messages and session report."""
    from amaru.sync import syn, syn_report

    bp = _bus_path()
    if not bp.exists():
        return {"report": "No bus file found.", "pending": 0, "stale": 0}
    result = syn(str(bp), namespace)
    report = syn_report(result, namespace)
    return {
        "report": report,
        "pending": len(result.pending),
        "stale": len(result.stale),
        "unresolved": len(result.unresolved) if result.unresolved else 0,
        "total_bus_messages": result.total_bus_messages,
        "messages": [_msg_to_dict(m) for m in result.pending[:20]],
    }


def tool_fin(namespace: str, actions: list[dict] | None = None) -> dict:
    """Execute FIN protocol — write state changes, ACK consumed."""
    from amaru.sync import FinAction, fin

    bp = _bus_path()
    fin_actions = None
    if actions:
        fin_actions = [
            FinAction(
                dst=a.get("dst", "*"),
                type=a.get("type", "state"),
                msg=a["msg"],
                ttl=a.get("ttl"),
            )
            for a in actions
            if "msg" in a
        ]
    written = fin(str(bp), namespace, fin_actions)
    return {"written": len(written), "messages": [_msg_to_dict(m) for m in written]}


def tool_status() -> dict:
    """Clan status, protocol version, bus stats."""
    result: dict = {
        "protocol_version": __version__,
        "amaru_dir": str(_AMARU_DIR),
    }

    try:
        from amaru.config import load_config

        cfg = load_config(str(_AMARU_DIR))
        result["clan_id"] = cfg.clan_id
        result["display_name"] = cfg.display_name
        result["peers"] = len(cfg.peers)
    except Exception:
        result["clan_id"] = "not_configured"

    bp = _bus_path()
    if bp.exists():
        messages = read_bus(str(bp))
        expired = find_expired(messages)
        stale = find_stale(messages)
        result["bus"] = {
            "total": len(messages),
            "expired": len(expired),
            "stale": len(stale),
        }
    else:
        result["bus"] = {"total": 0, "expired": 0, "stale": 0}

    return result


def tool_peers() -> list[dict]:
    """List known peers with status."""
    try:
        from amaru.config import load_config

        cfg = load_config(str(_AMARU_DIR))
        return [
            {
                "clan_id": p.clan_id,
                "status": p.status,
                "public_key_file": p.public_key_file,
                "added": p.added,
            }
            for p in cfg.peers
        ]
    except Exception:
        return []


def tool_seal(peer_clan_id: str, msg: str, envelope_meta: dict | None = None) -> dict:
    """Encrypt + sign a message for a peer using ECDHE (ARC-8446)."""
    from amaru.config import load_config
    from amaru.crypto import ClanKeyPair, seal_bus_message_ecdhe

    cfg = load_config(str(_AMARU_DIR))
    my_keys = ClanKeyPair.load(str(_AMARU_DIR / ".keys"), cfg.clan_id)

    peer_pub_path = None
    for p in cfg.peers:
        if p.clan_id == peer_clan_id:
            peer_pub_path = _AMARU_DIR / p.public_key_file
            break

    if not peer_pub_path or not peer_pub_path.exists():
        return {"error": f"Peer {peer_clan_id} public key not found"}

    peer_data = json.loads(peer_pub_path.read_text())
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey

    peer_dh_pub = X25519PublicKey.from_public_bytes(bytes.fromhex(peer_data["dh_public"]))

    sealed = seal_bus_message_ecdhe(my_keys, peer_dh_pub, msg, envelope_meta=envelope_meta)
    return {"sealed": sealed, "peer": peer_clan_id, "enc": "ECDHE-X25519-AES256GCM"}


def tool_open(sealed_json: dict, sender_clan_id: str, envelope_meta: dict | None = None) -> dict:
    """Decrypt + verify a sealed message from a peer (ARC-8446)."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey

    from amaru.config import load_config
    from amaru.crypto import ClanKeyPair, open_bus_message

    cfg = load_config(str(_AMARU_DIR))
    my_keys = ClanKeyPair.load(str(_AMARU_DIR / ".keys"), cfg.clan_id)

    peer_pub_path = None
    for p in cfg.peers:
        if p.clan_id == sender_clan_id:
            peer_pub_path = _AMARU_DIR / p.public_key_file
            break

    if not peer_pub_path or not peer_pub_path.exists():
        return {"error": f"Peer {sender_clan_id} public key not found"}

    peer_data = json.loads(peer_pub_path.read_text())
    peer_sign_pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(peer_data["sign_public"]))
    peer_dh_pub = X25519PublicKey.from_public_bytes(bytes.fromhex(peer_data["dh_public"]))

    plaintext = open_bus_message(
        my_keys, peer_sign_pub, peer_dh_pub, sealed_json, envelope_meta=envelope_meta
    )

    if plaintext is None:
        return {"error": "Decryption failed — bad key, tampered, or wrong peer"}
    return {"plaintext": plaintext, "sender": sender_clan_id, "verified": True}


async def tool_hub_send(dst: str, msg_type: str, msg: str, ttl: int = 14) -> dict:
    """Send a message to a peer via the local Amaru hub (WebSocket).

    Completes the outbound path: Claude Code -> MCP -> Hub -> Peer.
    Authenticates as local clan via Ed25519 challenge-response (ARC-4601 section 15.6).
    """
    import asyncio

    hub_state_path = _AMARU_DIR / "hub-state.json"
    if not hub_state_path.exists():
        return {"error": "Hub not running. Start with: amaru hub start"}

    hub_state = json.loads(hub_state_path.read_text())
    port = hub_state.get("port", 8443)
    host = "localhost"

    # Load clan keys
    key_path = _AMARU_DIR / "keys" / "momoshod.key"
    if not key_path.exists():
        # Try to discover key file from gateway.json
        gw_path = _AMARU_DIR / "gateway.json"
        if gw_path.exists():
            gw = json.loads(gw_path.read_text())
            key_file = gw.get("keys", {}).get("private", "keys/momoshod.key")
            key_path = _AMARU_DIR / key_file
        if not key_path.exists():
            return {"error": "Clan private key not found"}

    try:
        from amaru.crypto import ClanKeyPair

        key_data = json.loads(key_path.read_text())
        keys = ClanKeyPair.from_private_hex(key_data["sign_private"], key_data["dh_private"])
    except Exception as e:
        return {"error": f"Failed to load keys: {e}"}

    # Determine clan_id from gateway.json
    clan_id = "momoshod"
    gw_path = _AMARU_DIR / "gateway.json"
    if gw_path.exists():
        try:
            clan_id = json.loads(gw_path.read_text()).get("clan_id", "momoshod")
        except Exception:
            pass

    try:
        import websockets
    except ImportError:
        return {"error": "websockets package required: pip install websockets"}

    from datetime import UTC, datetime

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
                return {"error": f"Expected challenge, got: {frame.get('type')}"}

            # AUTH (sign raw nonce bytes, NOT utf-8 string)
            nonce_bytes = bytes.fromhex(frame["nonce"])
            signature = keys.sign_private.sign(nonce_bytes)
            await ws.send(json.dumps({"type": "auth", "nonce_response": signature.hex()}))

            # AUTH_OK
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            frame = json.loads(raw)
            if frame.get("type") != "auth_ok":
                return {"error": f"Auth failed: {frame.get('reason', 'unknown')}"}

            # SEND MESSAGE
            payload = {
                "type": "msg",
                "payload": {
                    "ts": datetime.now(UTC).isoformat(),
                    "src": clan_id,
                    "dst": dst,
                    "type": msg_type,
                    "msg": msg,
                    "ttl": ttl,
                    "ack": [],
                },
            }
            await ws.send(json.dumps(payload))
            return {
                "sent": True,
                "dst": dst,
                "type": msg_type,
                "msg": msg[:120],
                "via": f"hub@{host}:{port}",
            }

    except Exception as e:
        return {"error": f"Hub send failed: {e}"}


def tool_integrity_check() -> dict:
    """Run bus integrity checks (ARC-9001): sequence gaps, ownership, conflicts."""
    from amaru.integrity import (
        BusIntegrityChecker,
        OwnershipRegistry,
        SequenceTracker,
    )

    bp = _bus_path()
    if not bp.exists():
        return {"status": "no_bus", "anomalies": []}

    messages = read_bus(str(bp))
    seq_tracker = SequenceTracker()
    ownership = OwnershipRegistry()
    checker = BusIntegrityChecker(seq_tracker, ownership)

    anomalies = []
    for m in messages:
        issues = checker.check_read(m, seq=m.seq)
        if issues:
            anomalies.append({"message": _msg_to_dict(m), "issues": issues})

    return {
        "status": "ok" if not anomalies else "anomalies_found",
        "total_messages": len(messages),
        "anomaly_count": len(anomalies),
        "anomalies": anomalies[:10],
        "sources_tracked": len(seq_tracker._state),
    }


# ---------- MCP server setup ----------


def create_server():
    """Create and configure the MCP server with all Amaru tools and resources."""
    try:
        import mcp.types as types
        from mcp.server import Server
    except ImportError as err:
        raise ImportError("MCP SDK required: pip install 'amaru-protocol[mcp]'") from err

    server = Server("amaru-bus")

    # Advance cursor to current end on startup (don't replay history)
    _cursor.advance_to_end(_bus_path())

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="amaru_bus_read",
                description="Read Amaru bus messages with filters. Use new_only=true for real-time sync between sessions.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "since_minutes": {
                            "type": "integer",
                            "description": "Only messages from last N minutes",
                        },
                        "namespace": {
                            "type": "string",
                            "description": "Filter by destination namespace",
                        },
                        "type_filter": {
                            "type": "string",
                            "description": "Filter by message type (state/event/alert/dispatch)",
                        },
                        "pending_only": {
                            "type": "boolean",
                            "description": "Only unACKed messages",
                            "default": False,
                        },
                        "new_only": {
                            "type": "boolean",
                            "description": "Only messages since last read (per-session cursor)",
                            "default": False,
                        },
                    },
                },
            ),
            types.Tool(
                name="amaru_bus_write",
                description="Write a message to the Amaru bus. Other sessions will see it via amaru_bus_read.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "src": {"type": "string", "description": "Source namespace"},
                        "dst": {
                            "type": "string",
                            "description": "Destination namespace (* for broadcast)",
                        },
                        "type": {
                            "type": "string",
                            "enum": [
                                "state",
                                "event",
                                "alert",
                                "dispatch",
                                "data_cross",
                                "dojo_event",
                            ],
                            "description": "Message type",
                        },
                        "msg": {"type": "string", "description": "Message payload (max 120 chars)"},
                        "ttl": {
                            "type": "integer",
                            "description": "Time-to-live in days",
                            "default": 7,
                        },
                    },
                    "required": ["src", "dst", "type", "msg"],
                },
            ),
            types.Tool(
                name="amaru_bus_ack",
                description="Acknowledge bus messages matching filters.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "namespace": {"type": "string", "description": "ACKing namespace"},
                        "src_filter": {
                            "type": "string",
                            "description": "Only ACK from this source",
                        },
                        "type_filter": {"type": "string", "description": "Only ACK this type"},
                    },
                    "required": ["namespace"],
                },
            ),
            types.Tool(
                name="amaru_syn",
                description="Execute SYN protocol — start a Amaru session, get pending messages.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "namespace": {"type": "string", "description": "Your namespace"},
                    },
                    "required": ["namespace"],
                },
            ),
            types.Tool(
                name="amaru_fin",
                description="Execute FIN protocol — end a Amaru session, write state changes.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "namespace": {"type": "string", "description": "Your namespace"},
                        "actions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "dst": {"type": "string"},
                                    "type": {"type": "string"},
                                    "msg": {"type": "string"},
                                    "ttl": {"type": "integer"},
                                },
                                "required": ["msg"],
                            },
                            "description": "State changes to write on session end",
                        },
                    },
                    "required": ["namespace"],
                },
            ),
            types.Tool(
                name="amaru_status",
                description="Show Amaru clan status: identity, protocol version, bus stats.",
                inputSchema={"type": "object", "properties": {}},
            ),
            types.Tool(
                name="amaru_peers",
                description="List known Amaru peers with status and fingerprints.",
                inputSchema={"type": "object", "properties": {}},
            ),
            types.Tool(
                name="amaru_seal",
                description="Encrypt + sign a message for a peer using ECDHE (ARC-8446). Forward secrecy per message.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "peer_clan_id": {"type": "string", "description": "Target peer clan ID"},
                        "msg": {"type": "string", "description": "Plaintext message"},
                        "envelope_meta": {
                            "type": "object",
                            "description": "Optional envelope metadata for AAD",
                        },
                    },
                    "required": ["peer_clan_id", "msg"],
                },
            ),
            types.Tool(
                name="amaru_open",
                description="Decrypt + verify a sealed message from a peer (ARC-8446).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sealed_json": {
                            "type": "object",
                            "description": "The sealed envelope dict",
                        },
                        "sender_clan_id": {"type": "string", "description": "Sender peer clan ID"},
                        "envelope_meta": {
                            "type": "object",
                            "description": "Optional envelope metadata for AAD verification",
                        },
                    },
                    "required": ["sealed_json", "sender_clan_id"],
                },
            ),
            types.Tool(
                name="amaru_integrity_check",
                description="Run bus integrity checks (ARC-9001): sequence gaps, ownership violations, MVCC conflicts.",
                inputSchema={"type": "object", "properties": {}},
            ),
            types.Tool(
                name="amaru_hub_send",
                description="Send a message to a peer via the Amaru hub (WebSocket). Completes the outbound path: Claude Code -> Hub -> Peer. Requires hub to be running.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "dst": {
                            "type": "string",
                            "description": "Destination clan ID (* for broadcast)",
                        },
                        "type": {
                            "type": "string",
                            "enum": [
                                "state",
                                "event",
                                "alert",
                                "dispatch",
                                "data_cross",
                                "dojo_event",
                            ],
                            "description": "Message type",
                        },
                        "msg": {"type": "string", "description": "Message payload"},
                        "ttl": {
                            "type": "integer",
                            "description": "Time-to-live in days",
                            "default": 14,
                        },
                    },
                    "required": ["dst", "type", "msg"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        handlers = {
            "amaru_bus_read": lambda a: tool_bus_read(
                since_minutes=a.get("since_minutes"),
                namespace=a.get("namespace"),
                type_filter=a.get("type_filter"),
                pending_only=a.get("pending_only", False),
                new_only=a.get("new_only", False),
            ),
            "amaru_bus_write": lambda a: tool_bus_write(
                src=a["src"],
                dst=a["dst"],
                type=a["type"],
                msg=a["msg"],
                ttl=a.get("ttl", 7),
            ),
            "amaru_bus_ack": lambda a: tool_bus_ack(
                namespace=a["namespace"],
                src_filter=a.get("src_filter"),
                type_filter=a.get("type_filter"),
            ),
            "amaru_syn": lambda a: tool_syn(namespace=a["namespace"]),
            "amaru_fin": lambda a: tool_fin(namespace=a["namespace"], actions=a.get("actions")),
            "amaru_status": lambda _: tool_status(),
            "amaru_peers": lambda _: tool_peers(),
            "amaru_seal": lambda a: tool_seal(
                peer_clan_id=a["peer_clan_id"],
                msg=a["msg"],
                envelope_meta=a.get("envelope_meta"),
            ),
            "amaru_open": lambda a: tool_open(
                sealed_json=a["sealed_json"],
                sender_clan_id=a["sender_clan_id"],
                envelope_meta=a.get("envelope_meta"),
            ),
            "amaru_integrity_check": lambda _: tool_integrity_check(),
        }

        # Async tools (hub_send uses WebSocket)
        if name == "amaru_hub_send":
            try:
                result = await tool_hub_send(
                    dst=arguments["dst"],
                    msg_type=arguments["type"],
                    msg=arguments["msg"],
                    ttl=arguments.get("ttl", 14),
                )
                return [
                    types.TextContent(type="text", text=json.dumps(result, indent=2, default=str))
                ]
            except Exception as e:
                return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]

        handler = handlers.get(name)
        if not handler:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

        try:
            result = handler(arguments)  # type: ignore[assignment]
            return [types.TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
        except Exception as e:
            return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]

    @server.list_resources()
    async def list_resources() -> list[types.Resource]:
        from pydantic import AnyUrl

        return [
            types.Resource(
                uri=AnyUrl("amaru://protocol/version"),
                name="Amaru Protocol Version",
                description=f"Amaru v{__version__} — 21 specs, 1451+ tests, 19 modules, 4 adapters",
                mimeType="application/json",
            ),
            types.Resource(
                uri=AnyUrl("amaru://bus/stats"),
                name="Bus Statistics",
                description="Live bus message counts: total, pending, expired, stale",
                mimeType="application/json",
            ),
            types.Resource(
                uri=AnyUrl("amaru://config/clan"),
                name="Clan Configuration",
                description="Current clan identity and configuration (no secrets)",
                mimeType="application/json",
            ),
        ]

    @server.read_resource()
    async def read_resource(uri: str) -> str:
        if uri == "amaru://protocol/version":
            return json.dumps(
                {
                    "version": __version__,
                    "specs": 21,
                    "tests": "1451+",
                    "modules": 19,
                    "adapters": 4,
                    "adapters_list": ["Claude Code", "Cursor", "OpenCode", "Gemini CLI"],
                }
            )
        elif uri == "amaru://bus/stats":
            return json.dumps(tool_status().get("bus", {}))
        elif uri == "amaru://config/clan":
            status = tool_status()
            return json.dumps({k: v for k, v in status.items() if k != "bus"})
        return json.dumps({"error": f"Unknown resource: {uri}"})

    return server


async def run_server():
    """Run the MCP server with stdio transport."""
    from mcp.server.stdio import stdio_server

    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    """Entry point for python -m amaru.mcp_server."""
    import asyncio

    asyncio.run(run_server())


if __name__ == "__main__":
    main()
