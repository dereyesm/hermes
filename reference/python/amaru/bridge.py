"""Amaru Bridge Protocol Mapping — ARC-7231 Reference Implementation.

Translates between Amaru JSONL messages and external agent protocols
(Google A2A, Anthropic MCP) per ARC-7231.  This module implements the
semantic translation layer — it does NOT include HTTP servers or transports.

Usage:
    from amaru.bridge import A2ABridge, MCPBridge, BridgeConfig

    config = BridgeConfig(cid_prefix="brg")
    a2a = A2ABridge(config)
    mcp = MCPBridge(config)

    # Inbound: A2A JSON-RPC → Amaru Message
    msg = a2a.a2a_to_amaru(jsonrpc_request)

    # Outbound: Amaru Message → A2A JSON-RPC result
    result = a2a.amaru_to_a2a(message)
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from datetime import date
from typing import Any

from .message import Message

# ─── Configuration (Section 7.1) ─────────────────────────────────


@dataclass
class BridgeConfig:
    """Bridge configuration per ARC-7231 Section 7.1."""

    a2a_enabled: bool = True
    mcp_enabled: bool = True
    cid_prefix: str = "brg"
    response_timeout_seconds: int = 300
    max_external_payload_bytes: int = 65536


# ─── CID Generator (Section 7.1) ─────────────────────────────────


class CIDGenerator:
    """Thread-safe correlation ID generator.

    Format: {prefix}-{protocol}-{counter}
    Example: brg-a2a-1, brg-mcp-42
    """

    def __init__(self, prefix: str = "brg") -> None:
        self._prefix = prefix
        self._counter = 0
        self._lock = threading.Lock()

    def next(self, protocol: str) -> str:
        """Generate the next CID for the given protocol."""
        with self._lock:
            self._counter += 1
            return f"{self._prefix}-{protocol}-{self._counter}"


# Module-level generator for the generate_cid convenience function
_global_cid_gen = CIDGenerator()


def generate_cid(prefix: str = "brg", protocol: str = "a2a") -> str:
    """Generate a unique CID. Convenience wrapper around CIDGenerator."""
    return _global_cid_gen.next(protocol)


# ─── Error Translation (Section 8.1) ─────────────────────────────


# Amaru condition → (A2A error message, MCP error code, HTTP status)
_ERROR_MAP: dict[str, tuple[str, int, int]] = {
    "not_found": ("Task failed: agent not found", -32601, 404),
    "namespace_not_found": ("Task failed: agent not found", -32601, 404),
    "rate_limited": ("Task rejected: rate limited", -32000, 429),
    "rate_limit_exceeded": ("Task rejected: rate limited", -32000, 429),
    "payload_too_large": ("Task failed: payload exceeded", -32602, 413),
    "timeout": ("Task failed: timeout", -32603, 504),
    "ttl_expired": ("Task failed: timeout", -32603, 504),
    "not_authorized": ("Task failed: not authorized", -32000, 403),
    "invalid_request": ("Task rejected: invalid request", -32600, 400),
    "not_configured": ("Task failed: unsupported", -32601, 501),
}


def translate_error(condition: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Translate a Amaru error condition to A2A and MCP error dicts.

    Returns (a2a_error, mcp_error) where each is a dict with
    'code' and 'message' keys.
    """
    a2a_msg, mcp_code, _ = _ERROR_MAP.get(condition, ("Task failed: unknown error", -32603, 500))
    a2a_error = {"code": -32603, "message": a2a_msg}
    mcp_error = {"code": mcp_code, "message": condition.replace("_", " ")}
    return a2a_error, mcp_error


def translate_error_a2a(condition: str, request_id: int | str = 1) -> dict[str, Any]:
    """Translate a Amaru error condition to an A2A JSON-RPC error response."""
    a2a_err, _ = translate_error(condition)
    return {
        "jsonrpc": "2.0",
        "error": a2a_err,
        "id": request_id,
    }


def translate_error_mcp(condition: str, request_id: int | str = 1) -> dict[str, Any]:
    """Translate a Amaru error condition to an MCP JSON-RPC error response."""
    _, mcp_err = translate_error(condition)
    return {
        "jsonrpc": "2.0",
        "error": mcp_err,
        "id": request_id,
    }


# ─── Sanitization helpers ────────────────────────────────────────

_ALIAS_RE = re.compile(r"[^a-z0-9\-]")
_MAX_ALIAS_LEN = 64
_MAX_MSG_LENGTH = 120


def _sanitize_alias(name: str) -> str:
    """Sanitize a name to [a-z0-9-] per ARC-2606 Section 4.2."""
    sanitized = _ALIAS_RE.sub("-", name.lower().strip())
    sanitized = re.sub(r"-{2,}", "-", sanitized).strip("-")
    return sanitized[:_MAX_ALIAS_LEN] if sanitized else "unknown"


def _truncate_payload(text: str) -> str:
    """Truncate payload to 120 chars per ARC-5322."""
    return text[:_MAX_MSG_LENGTH] if len(text) > _MAX_MSG_LENGTH else text


# ─── A2A Bridge (Section 3) ──────────────────────────────────────


class A2ABridge:
    """Translates between Google A2A JSON-RPC and Amaru JSONL.

    Implements the semantic mapping defined in ARC-7231 Section 3.
    """

    def __init__(self, config: BridgeConfig | None = None) -> None:
        self.config = config or BridgeConfig()
        self._cid_gen = CIDGenerator(self.config.cid_prefix)

    def a2a_to_amaru(self, jsonrpc_request: dict[str, Any]) -> Message:
        """Translate an A2A JSON-RPC request to a Amaru Message.

        Supports: tasks/send, tasks/get, tasks/cancel (Section 3.3).
        Raises ValueError for unsupported methods.
        """
        method = jsonrpc_request.get("method", "")
        params = jsonrpc_request.get("params", {})

        if method == "tasks/send":
            return self._translate_task_send(params)
        elif method == "tasks/get":
            return self._translate_task_get(params)
        elif method == "tasks/cancel":
            return self._translate_task_cancel(params)
        else:
            raise ValueError(f"Unsupported A2A method: {method}")

    def _translate_task_send(self, params: dict[str, Any]) -> Message:
        """Translate tasks/send → dispatch message (Section 3.3)."""
        cid = self._cid_gen.next("a2a")
        task_id = params.get("id", cid)

        message = params.get("message", {})
        parts = message.get("parts", [])
        text = " ".join(p.get("text", "") for p in parts if "text" in p).strip()

        payload = _truncate_payload(f"[CID:{task_id}] {text}" if text else f"[CID:{task_id}]")

        return Message(
            ts=date.today(),
            src="gateway",
            dst=params.get("namespace", "gateway"),
            type="dispatch",
            msg=payload,
            ttl=5,
            ack=[],
        )

    def _translate_task_get(self, params: dict[str, Any]) -> Message:
        """Translate tasks/get → request message (Section 3.3)."""
        task_id = params.get("id", "unknown")
        payload = _truncate_payload(f"[CID:{task_id}] Query task status")

        return Message(
            ts=date.today(),
            src="gateway",
            dst=params.get("namespace", "gateway"),
            type="request",
            msg=payload,
            ttl=5,
            ack=[],
        )

    def _translate_task_cancel(self, params: dict[str, Any]) -> Message:
        """Translate tasks/cancel → alert message (Section 3.3)."""
        task_id = params.get("id", "unknown")
        payload = _truncate_payload(f"[RE:{task_id}] CANCELLED")

        return Message(
            ts=date.today(),
            src="gateway",
            dst=params.get("namespace", "gateway"),
            type="alert",
            msg=payload,
            ttl=5,
            ack=[],
        )

    def amaru_to_a2a(self, message: Message, task_id: str | None = None) -> dict[str, Any]:
        """Translate a Amaru Message to an A2A JSON-RPC result."""
        task_state = self.translate_task_state(message)
        resolved_task_id = task_id or _extract_token(message.msg) or "unknown"
        response_text = _strip_correlation_prefix(message.msg)

        result: dict[str, Any] = {
            "id": resolved_task_id,
            "status": {"state": task_state},
        }

        if task_state == "completed":
            result["artifacts"] = [{"parts": [{"text": response_text}]}]

        return {
            "jsonrpc": "2.0",
            "result": result,
            "id": 1,
        }

    def translate_task_state(self, message: Message) -> str:
        """Map Amaru message to A2A task state per Section 3.4."""
        msg = message.msg

        if "[RE:" in msg and "CANCELLED" in msg.upper():
            return "canceled"
        if "[RE:" in msg and message.type in ("state", "event", "dispatch"):
            return "completed"
        if message.type == "alert":
            return "failed"
        if message.type == "request":
            return "input-required"
        if message.ack and "[RE:" not in msg:
            return "working"
        return "submitted"

    def build_agent_card(self, profile: dict[str, Any]) -> dict[str, Any]:
        """Build an A2A Agent Card from a Amaru profile (Section 3.2.1)."""
        alias = profile.get("alias", "unknown")
        capabilities = profile.get("capabilities", [])

        skills = []
        for cap in capabilities:
            path = cap if isinstance(cap, str) else cap.get("path", "")
            parts = path.rsplit("/", 1)
            skill_name = parts[-1].replace("-", " ").title() if parts else path
            skills.append({"id": path, "name": skill_name})

        protocol_versions = profile.get("protocol_versions", ["0.3.0"])
        version = protocol_versions[0] if protocol_versions else "0.3.0"

        return {
            "name": alias,
            "description": profile.get("description", ""),
            "url": profile.get("gateway_url", ""),
            "provider": {
                "organization": profile.get("clan_id", ""),
                "url": profile.get("provider_url", ""),
            },
            "version": version,
            "capabilities": {
                "streaming": False,
                "pushNotifications": True,
            },
            "skills": skills,
            "authentication": {"schemes": ["none"]},
        }

    def parse_agent_card(self, card: dict[str, Any]) -> dict[str, Any]:
        """Parse an A2A Agent Card into a Amaru profile (Section 3.2.2)."""
        name = card.get("name", "unknown")
        alias = _sanitize_alias(name)

        provider = card.get("provider", {})
        clan_id_raw = provider.get("organization", "")
        clan_id = (
            _sanitize_alias(clan_id_raw)
            if clan_id_raw
            else _derive_clan_from_url(card.get("url", ""))
        )

        skills = card.get("skills", [])
        capabilities: list[dict[str, str]] = []
        for skill in skills:
            skill_id = skill.get("id", "")
            if "/" in skill_id:
                domain = skill_id.split("/")[0]
            else:
                domain = f"x-{_sanitize_alias(skill_id)}"
            capabilities.append(
                {
                    "domain": domain,
                    "path": skill_id if "/" in skill_id else f"{domain}/{skill_id}",
                    "confidence": "secondary",
                }
            )

        caps = card.get("capabilities", {})
        streaming = caps.get("streaming", False)
        availability = "always-on" if streaming else "on-demand"

        return {
            "alias": alias,
            "clan_id": clan_id,
            "capabilities": capabilities,
            "availability": availability,
            "protocol_versions": ["a2a-bridge"],
            "visibility": "direct-request",
        }


# ─── MCP Bridge (Section 4) ──────────────────────────────────────


class MCPBridge:
    """Translates between Anthropic MCP JSON-RPC and Amaru JSONL.

    Implements the semantic mapping defined in ARC-7231 Section 4.
    """

    def __init__(self, config: BridgeConfig | None = None) -> None:
        self.config = config or BridgeConfig()
        self._cid_gen = CIDGenerator(self.config.cid_prefix)

    def mcp_to_amaru(self, jsonrpc_request: dict[str, Any]) -> Message:
        """Translate an MCP JSON-RPC request to a Amaru Message.

        Supports: tools/call, resources/read (Sections 4.2, 4.3).
        Raises ValueError for unsupported methods.
        """
        method = jsonrpc_request.get("method", "")
        params = jsonrpc_request.get("params", {})

        if method == "tools/call":
            return self._translate_tool_call(params)
        elif method == "resources/read":
            return self._translate_resource_read(params)
        else:
            raise ValueError(f"Unsupported MCP method: {method}")

    def _translate_tool_call(self, params: dict[str, Any]) -> Message:
        """Translate tools/call → dispatch message (Section 4.2.2)."""
        cid = self._cid_gen.next("mcp")
        tool_name = params.get("name", "unknown")
        arguments = params.get("arguments", {})

        namespace = _resolve_namespace_from_tool(tool_name)
        args_summary = " ".join(f"{k}={v}" for k, v in arguments.items())
        text = f"{tool_name}: {args_summary}" if args_summary else tool_name
        payload = _truncate_payload(f"[CID:{cid}] {text}")

        return Message(
            ts=date.today(),
            src="gateway",
            dst=namespace,
            type="dispatch",
            msg=payload,
            ttl=5,
            ack=[],
        )

    def _translate_resource_read(self, params: dict[str, Any]) -> Message:
        """Translate resources/read → request message (Section 4.3)."""
        cid = self._cid_gen.next("mcp")
        uri = params.get("uri", "")
        namespace = _resolve_namespace_from_uri(uri)
        payload = _truncate_payload(f"[CID:{cid}] Read resource: {uri}")

        return Message(
            ts=date.today(),
            src="gateway",
            dst=namespace,
            type="request",
            msg=payload,
            ttl=5,
            ack=[],
        )

    def amaru_to_mcp(self, message: Message, request_id: int | str = 1) -> dict[str, Any]:
        """Translate a Amaru Message to an MCP JSON-RPC result."""
        response_text = _strip_correlation_prefix(message.msg)
        is_error = message.type == "alert"

        return {
            "jsonrpc": "2.0",
            "result": {
                "content": [{"type": "text", "text": response_text}],
                "isError": is_error,
            },
            "id": request_id,
        }

    def build_tool_list(self, published_agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Build an MCP tool list from Amaru published agents (Section 7.2)."""
        tools: list[dict[str, Any]] = []
        for agent in published_agents:
            alias = agent.get("alias", "unknown")
            capabilities = agent.get("capabilities", [])
            for cap in capabilities:
                path = cap if isinstance(cap, str) else cap.get("path", "")
                parts = path.rsplit("/", 1)
                specialization = parts[-1] if parts else path

                tool_name = f"{alias}_{specialization}".replace("-", "_")
                description = _description_from_path(path)

                tools.append(
                    {
                        "name": tool_name,
                        "description": description,
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "input": {
                                    "type": "string",
                                    "description": "Request input",
                                },
                            },
                            "required": ["input"],
                        },
                    }
                )
        return tools

    def build_resource_list(self, namespaces: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Build an MCP resource list from Amaru namespaces (Section 4.3)."""
        resources: list[dict[str, Any]] = []
        for ns in namespaces:
            ns_id = ns.get("id", "unknown")
            description = ns.get("description", f"Amaru namespace: {ns_id}")
            resources.append(
                {
                    "uri": f"amaru://{ns_id}",
                    "name": ns_id,
                    "description": description,
                    "mimeType": "application/json",
                }
            )
        return resources


# ─── Internal Helpers ─────────────────────────────────────────────

_CID_OR_RE = re.compile(r"\[(CID|RE):([a-zA-Z0-9_\-]+)\]")


def _extract_token(msg: str) -> str | None:
    """Extract the correlation token from [CID:xxx] or [RE:xxx]."""
    match = _CID_OR_RE.search(msg)
    return match.group(2) if match else None


def _strip_correlation_prefix(msg: str) -> str:
    """Strip [CID:xxx] or [RE:xxx] prefix and leading whitespace."""
    stripped = _CID_OR_RE.sub("", msg).strip()
    return stripped if stripped else msg


def _resolve_namespace_from_tool(tool_name: str) -> str:
    """Derive the target namespace from an MCP tool name."""
    parts = tool_name.split("_", 1)
    ns = parts[0].lower()
    if re.match(r"^[a-z][a-z0-9\-]*$", ns):
        return ns
    return "gateway"


def _resolve_namespace_from_uri(uri: str) -> str:
    """Derive the target namespace from a amaru:// URI."""
    if uri.startswith("amaru://"):
        path = uri[len("amaru://") :]
        ns = path.split("/")[0]
        if re.match(r"^[a-z][a-z0-9\-]*$", ns):
            return ns
    return "gateway"


def _description_from_path(path: str) -> str:
    """Generate a human-readable description from a capability path."""
    if not path:
        return "Amaru agent capability"
    segments = path.replace("-", " ").split("/")
    if len(segments) > 1:
        words = " ".join(segments[1:])
    else:
        words = segments[0]
    return f"{words.capitalize()} analysis"


def _derive_clan_from_url(url: str) -> str:
    """Derive a clan_id from a URL hostname."""
    if not url:
        return "unknown"
    host = url.split("://", 1)[-1].split("/")[0]
    parts = host.split(".")
    return _sanitize_alias(parts[0]) if parts else "unknown"
