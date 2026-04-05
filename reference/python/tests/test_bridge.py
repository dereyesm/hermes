"""Tests for HERMES Bridge Protocol Mapping — ARC-7231 Reference Implementation.

Covers: A2ABridge, MCPBridge, BridgeConfig, CID generation,
error translation, and round-trip translation flows.
"""

from datetime import date

import pytest

from amaru.bridge import (
    A2ABridge,
    BridgeConfig,
    CIDGenerator,
    MCPBridge,
    generate_cid,
    translate_error,
    translate_error_a2a,
    translate_error_mcp,
)
from amaru.message import Message

# ─── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def a2a_bridge():
    config = BridgeConfig(cid_prefix="brg")
    return A2ABridge(config)


@pytest.fixture
def mcp_bridge():
    config = BridgeConfig(cid_prefix="brg")
    return MCPBridge(config)


@pytest.fixture
def sample_amaru_profile():
    return {
        "alias": "aureus",
        "clan_id": "momosho-d",
        "description": "Personal finance agent",
        "capabilities": [
            {"path": "finance/personal/debt-strategy", "confidence": "primary"},
            {"path": "finance/personal/budget", "confidence": "primary"},
        ],
        "protocol_versions": ["0.3.0"],
        "gateway_url": "https://gateway.example.com/a2a",
    }


@pytest.fixture
def sample_agent_card():
    return {
        "name": "aureus",
        "description": "Personal finance agent",
        "url": "https://gateway.example.com/a2a",
        "provider": {"organization": "momosho-d", "url": "https://gateway.example.com"},
        "version": "0.3.0",
        "capabilities": {"streaming": False, "pushNotifications": True},
        "skills": [
            {"id": "finance/personal/debt-strategy", "name": "Debt Strategy"},
            {"id": "finance/personal/budget", "name": "Budget"},
        ],
        "authentication": {"schemes": ["none"]},
    }


# ─── A2ABridge ─────────────────────────────────────────────────────


class TestA2ABridge:
    def test_a2a_task_send_to_amaru_dispatch(self, a2a_bridge):
        """A2A tasks/send → HERMES dispatch message with CID."""
        request = {
            "jsonrpc": "2.0",
            "method": "tasks/send",
            "params": {
                "id": "task-ext-001",
                "message": {
                    "role": "user",
                    "parts": [{"text": "Analyze debt scenario: 3 cards"}],
                },
            },
            "id": 1,
        }

        msg = a2a_bridge.a2a_to_amaru(request)
        assert isinstance(msg, Message)
        assert msg.type == "dispatch"
        assert msg.src == "gateway"
        assert "[CID:" in msg.msg
        assert "Analyze debt" in msg.msg

    def test_amaru_response_to_a2a_result(self, a2a_bridge):
        """HERMES [RE:token] → A2A completed task response."""
        response = Message(
            ts=date(2026, 3, 15),
            src="finance",
            dst="gateway",
            type="state",
            msg="[RE:task-001] Avalanche method saves $2.1M over 18mo",
            ttl=7,
            ack=[],
        )

        result = a2a_bridge.amaru_to_a2a(response, task_id="task-ext-001")
        assert result["jsonrpc"] == "2.0"
        assert result["result"]["id"] == "task-ext-001"
        assert result["result"]["status"]["state"] == "completed"
        artifacts = result["result"]["artifacts"]
        assert len(artifacts) >= 1
        assert "Avalanche" in artifacts[0]["parts"][0]["text"]

    def test_build_agent_card_from_profile(self, a2a_bridge, sample_amaru_profile):
        """HERMES profile → A2A Agent Card."""
        card = a2a_bridge.build_agent_card(sample_amaru_profile)
        assert card["name"] == "aureus"
        assert card["provider"]["organization"] == "momosho-d"
        assert card["version"] == "0.3.0"
        assert card["capabilities"]["streaming"] is False
        assert card["capabilities"]["pushNotifications"] is True
        assert len(card["skills"]) == 2
        skill_ids = {s["id"] for s in card["skills"]}
        assert "finance/personal/debt-strategy" in skill_ids

    def test_parse_agent_card_to_profile(self, a2a_bridge, sample_agent_card):
        """A2A Agent Card → HERMES profile."""
        profile = a2a_bridge.parse_agent_card(sample_agent_card)
        assert profile["alias"] == "aureus"
        assert profile["clan_id"] == "momosho-d"
        assert len(profile["capabilities"]) == 2
        paths = {c["path"] for c in profile["capabilities"]}
        assert "finance/personal/debt-strategy" in paths
        assert profile["availability"] == "on-demand"
        assert profile["protocol_versions"] == ["a2a-bridge"]
        assert profile["visibility"] == "direct-request"

    def test_task_state_submitted(self, a2a_bridge):
        """Submitted: dispatch with no ack, no RE."""
        msg = Message(
            ts=date(2026, 3, 15),
            src="gateway",
            dst="finance",
            type="dispatch",
            msg="[CID:t-001] Test task",
            ttl=5,
            ack=[],
        )
        assert a2a_bridge.translate_task_state(msg) == "submitted"

    def test_task_state_working(self, a2a_bridge):
        """Working: ack present, no RE."""
        msg = Message(
            ts=date(2026, 3, 15),
            src="gateway",
            dst="finance",
            type="dispatch",
            msg="[CID:t-001] Test task",
            ttl=5,
            ack=["finance"],
        )
        assert a2a_bridge.translate_task_state(msg) == "working"

    def test_task_state_completed(self, a2a_bridge):
        """Completed: RE token with state type."""
        msg = Message(
            ts=date(2026, 3, 15),
            src="finance",
            dst="gateway",
            type="state",
            msg="[RE:t-001] Result delivered",
            ttl=7,
            ack=[],
        )
        assert a2a_bridge.translate_task_state(msg) == "completed"

    def test_task_state_failed(self, a2a_bridge):
        """Failed: alert without RE."""
        msg = Message(
            ts=date(2026, 3, 15),
            src="finance",
            dst="gateway",
            type="alert",
            msg="TTL expired for task",
            ttl=5,
            ack=[],
        )
        assert a2a_bridge.translate_task_state(msg) == "failed"

    def test_task_state_canceled(self, a2a_bridge):
        """Canceled: RE with CANCELLED."""
        msg = Message(
            ts=date(2026, 3, 15),
            src="gateway",
            dst="finance",
            type="alert",
            msg="[RE:t-001] CANCELLED",
            ttl=5,
            ack=[],
        )
        assert a2a_bridge.translate_task_state(msg) == "canceled"

    def test_task_state_input_required(self, a2a_bridge):
        """Input-required: request type."""
        msg = Message(
            ts=date(2026, 3, 15),
            src="finance",
            dst="gateway",
            type="request",
            msg="Need more details about scenario",
            ttl=5,
            ack=[],
        )
        assert a2a_bridge.translate_task_state(msg) == "input-required"

    def test_a2a_task_get(self, a2a_bridge):
        """tasks/get → request message."""
        request = {
            "jsonrpc": "2.0",
            "method": "tasks/get",
            "params": {"id": "task-ext-001"},
            "id": 2,
        }
        msg = a2a_bridge.a2a_to_amaru(request)
        assert msg.type == "request"
        assert "[CID:task-ext-001]" in msg.msg

    def test_a2a_task_cancel(self, a2a_bridge):
        """tasks/cancel → alert with CANCELLED."""
        request = {
            "jsonrpc": "2.0",
            "method": "tasks/cancel",
            "params": {"id": "task-ext-001"},
            "id": 3,
        }
        msg = a2a_bridge.a2a_to_amaru(request)
        assert msg.type == "alert"
        assert "CANCELLED" in msg.msg
        assert "[RE:task-ext-001]" in msg.msg

    def test_unsupported_method_raises(self, a2a_bridge):
        """Unsupported A2A method raises ValueError."""
        request = {
            "jsonrpc": "2.0",
            "method": "tasks/unknown",
            "params": {},
            "id": 1,
        }
        with pytest.raises(ValueError, match="Unsupported A2A method"):
            a2a_bridge.a2a_to_amaru(request)


# ─── MCPBridge ─────────────────────────────────────────────────────


class TestMCPBridge:
    def test_mcp_tool_call_to_amaru(self, mcp_bridge):
        """MCP tools/call → HERMES dispatch."""
        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "aureus_debt_strategy",
                "arguments": {"scenario": "3 cards, $27M total"},
            },
            "id": 3,
        }

        msg = mcp_bridge.mcp_to_amaru(request)
        assert isinstance(msg, Message)
        assert msg.type == "dispatch"
        assert msg.src == "gateway"
        assert msg.dst == "aureus"  # derived from tool name
        assert "[CID:" in msg.msg

    def test_amaru_to_mcp_result(self, mcp_bridge):
        """HERMES response → MCP result."""
        response = Message(
            ts=date(2026, 3, 15),
            src="finance",
            dst="gateway",
            type="state",
            msg="[RE:mcp-001] Avalanche saves $2.1M/18mo",
            ttl=7,
            ack=[],
        )

        result = mcp_bridge.amaru_to_mcp(response, request_id=3)
        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 3
        content = result["result"]["content"]
        assert len(content) >= 1
        assert content[0]["type"] == "text"
        assert "Avalanche" in content[0]["text"]
        assert result["result"]["isError"] is False

    def test_amaru_alert_to_mcp_error(self, mcp_bridge):
        """HERMES alert → MCP result with isError=True."""
        alert = Message(
            ts=date(2026, 3, 15),
            src="finance",
            dst="gateway",
            type="alert",
            msg="[RE:mcp-002] Processing failed",
            ttl=5,
            ack=[],
        )
        result = mcp_bridge.amaru_to_mcp(alert)
        assert result["result"]["isError"] is True

    def test_build_tool_list(self, mcp_bridge):
        """HERMES capabilities → MCP tool list."""
        agents = [
            {
                "alias": "aureus",
                "capabilities": [
                    {"path": "finance/personal/debt-strategy"},
                    {"path": "finance/personal/budget"},
                ],
            },
        ]
        tools = mcp_bridge.build_tool_list(agents)
        assert len(tools) == 2
        tool_names = {t["name"] for t in tools}
        assert "aureus_debt_strategy" in tool_names
        assert "aureus_budget" in tool_names
        for tool in tools:
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"

    def test_build_resource_list(self, mcp_bridge):
        """HERMES namespaces → MCP resource list."""
        namespaces = [
            {"id": "finance", "description": "Financial data"},
            {"id": "engineering", "description": "Engineering data"},
        ]
        resources = mcp_bridge.build_resource_list(namespaces)
        assert len(resources) == 2
        uris = {r["uri"] for r in resources}
        assert "amaru://finance" in uris
        assert "amaru://engineering" in uris

    def test_mcp_resource_read_to_amaru(self, mcp_bridge):
        """MCP resources/read → HERMES request."""
        request = {
            "jsonrpc": "2.0",
            "method": "resources/read",
            "params": {"uri": "amaru://finance/debt-balance"},
            "id": 5,
        }
        msg = mcp_bridge.mcp_to_amaru(request)
        assert msg.type == "request"
        assert msg.dst == "finance"
        assert "[CID:" in msg.msg

    def test_unsupported_method_raises(self, mcp_bridge):
        """Unsupported MCP method raises ValueError."""
        request = {
            "jsonrpc": "2.0",
            "method": "prompts/get",
            "params": {},
            "id": 1,
        }
        with pytest.raises(ValueError, match="Unsupported MCP method"):
            mcp_bridge.mcp_to_amaru(request)


# ─── BridgeConfig ─────────────────────────────────────────────────


class TestBridgeConfig:
    def test_default_config(self):
        config = BridgeConfig()
        assert config.a2a_enabled is True
        assert config.mcp_enabled is True
        assert config.cid_prefix == "brg"
        assert config.response_timeout_seconds == 300
        assert config.max_external_payload_bytes == 65536

    def test_custom_config(self):
        config = BridgeConfig(
            a2a_enabled=False,
            cid_prefix="cst",
            response_timeout_seconds=60,
            max_external_payload_bytes=1024,
        )
        assert config.a2a_enabled is False
        assert config.cid_prefix == "cst"
        assert config.response_timeout_seconds == 60
        assert config.max_external_payload_bytes == 1024


# ─── CID Generation ───────────────────────────────────────────────


class TestCIDGeneration:
    def test_cid_format(self):
        """CID format is '{prefix}-{protocol}-{counter}'."""
        gen = CIDGenerator(prefix="test")
        cid = gen.next("a2a")
        parts = cid.split("-")
        assert len(parts) == 3
        assert parts[0] == "test"
        assert parts[1] == "a2a"
        assert parts[2].isdigit()

    def test_cid_uniqueness(self):
        """Each call generates a unique CID."""
        gen = CIDGenerator(prefix="uniq")
        cids = {gen.next("mcp") for _ in range(100)}
        assert len(cids) == 100

    def test_cid_sequential(self):
        """CIDs increment sequentially."""
        gen = CIDGenerator(prefix="seq")
        c1 = gen.next("a2a")
        c2 = gen.next("a2a")
        n1 = int(c1.split("-")[-1])
        n2 = int(c2.split("-")[-1])
        assert n2 == n1 + 1

    def test_generate_cid_convenience(self):
        """Module-level generate_cid function works."""
        cid = generate_cid(prefix="brg", protocol="a2a")
        assert cid.startswith("brg-")


# ─── Error Translation ────────────────────────────────────────────


class TestErrorTranslation:
    def test_namespace_not_found(self):
        a2a_err, mcp_err = translate_error("namespace_not_found")
        assert "not found" in a2a_err["message"].lower()
        assert mcp_err["code"] == -32601

    def test_rate_limit_exceeded(self):
        a2a_err, mcp_err = translate_error("rate_limit_exceeded")
        assert "rate" in a2a_err["message"].lower()
        assert mcp_err["code"] == -32000

    def test_payload_too_large(self):
        a2a_err, mcp_err = translate_error("payload_too_large")
        assert "payload" in a2a_err["message"].lower()
        assert mcp_err["code"] == -32602

    def test_ttl_expired(self):
        a2a_err, mcp_err = translate_error("ttl_expired")
        assert "timeout" in a2a_err["message"].lower()
        assert mcp_err["code"] == -32603

    def test_translate_error_a2a_jsonrpc(self):
        """translate_error_a2a returns full JSON-RPC error."""
        result = translate_error_a2a("not_found", request_id=42)
        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 42
        assert "error" in result

    def test_translate_error_mcp_jsonrpc(self):
        """translate_error_mcp returns full JSON-RPC error."""
        result = translate_error_mcp("timeout", request_id=99)
        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 99
        assert result["error"]["code"] == -32603

    def test_unknown_condition(self):
        """Unknown conditions get fallback error codes."""
        a2a_err, mcp_err = translate_error("some_unknown_error")
        assert a2a_err["code"] == -32603
        assert mcp_err["code"] == -32603


# ─── Round-trip Tests ──────────────────────────────────────────────


class TestRoundTrip:
    def test_a2a_roundtrip(self, a2a_bridge):
        """A2A request → HERMES → process → HERMES response → A2A response."""
        request = {
            "jsonrpc": "2.0",
            "method": "tasks/send",
            "params": {
                "id": "rt-a2a-001",
                "message": {
                    "role": "user",
                    "parts": [{"text": "Analyze debt scenario"}],
                },
            },
            "id": 10,
        }

        # Inbound
        amaru_msg = a2a_bridge.a2a_to_amaru(request)
        assert amaru_msg.type == "dispatch"
        assert "[CID:rt-a2a-001]" in amaru_msg.msg

        # Simulate processing
        amaru_response = Message(
            ts=date(2026, 3, 15),
            src="finance",
            dst="gateway",
            type="state",
            msg="[RE:rt-a2a-001] Avalanche method recommended",
            ttl=7,
            ack=[],
        )

        # Outbound
        a2a_response = a2a_bridge.amaru_to_a2a(amaru_response, task_id="rt-a2a-001")
        assert a2a_response["result"]["status"]["state"] == "completed"
        assert "Avalanche" in a2a_response["result"]["artifacts"][0]["parts"][0]["text"]

    def test_mcp_roundtrip(self, mcp_bridge):
        """MCP request → HERMES → process → HERMES response → MCP response."""
        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "aureus_debt_strategy",
                "arguments": {"scenario": "snowball vs avalanche"},
            },
            "id": 20,
        }

        # Inbound
        amaru_msg = mcp_bridge.mcp_to_amaru(request)
        assert amaru_msg.type == "dispatch"
        assert "[CID:" in amaru_msg.msg

        # Extract CID
        cid = amaru_msg.msg.split("[CID:")[1].split("]")[0]

        # Simulate processing
        amaru_response = Message(
            ts=date(2026, 3, 15),
            src="finance",
            dst="gateway",
            type="state",
            msg=f"[RE:{cid}] Avalanche saves $2.1M/18mo",
            ttl=7,
            ack=[],
        )

        # Outbound
        mcp_response = mcp_bridge.amaru_to_mcp(amaru_response, request_id=20)
        assert mcp_response["id"] == 20
        assert mcp_response["result"]["isError"] is False
        assert "Avalanche" in mcp_response["result"]["content"][0]["text"]

    def test_payload_truncation(self, a2a_bridge):
        """Long A2A payloads get truncated to 120 chars."""
        long_text = "A" * 200
        request = {
            "jsonrpc": "2.0",
            "method": "tasks/send",
            "params": {
                "id": "trunc-001",
                "message": {"role": "user", "parts": [{"text": long_text}]},
            },
            "id": 1,
        }
        msg = a2a_bridge.a2a_to_amaru(request)
        assert len(msg.msg) <= 120
