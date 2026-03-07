"""HERMES Gateway Configuration — ARC-3022 Section 16 Reference Implementation.

Load, validate, and save gateway configuration files (JSON format).
Zero external dependencies — uses stdlib json only.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PeerConfig:
    """A known peer clan."""

    clan_id: str
    public_key_file: str
    status: str = "pending_ack"  # pending_ack | established | suspended
    added: str = ""


@dataclass
class GatewayConfig:
    """Complete gateway configuration per ARC-3022 Section 16."""

    clan_id: str
    display_name: str
    protocol_version: str = "0.3.0"
    keys_private: str = ".keys/gateway.key"
    keys_public: str = ".keys/gateway.pub"
    agents: list[dict[str, Any]] = field(default_factory=list)
    heraldo_alias: str = "herald"
    peers: list[PeerConfig] = field(default_factory=list)
    agora_type: str = "git"
    agora_url: str = ""
    agora_local_cache: str = ".agora/"
    inbound_max_payload: int = 4096
    inbound_rate_limit: int = 10
    inbound_quarantine_first_contact: bool = True
    inbound_auto_accept_hello: bool = True


def load_config(path: str | Path) -> GatewayConfig:
    """Load gateway config from a JSON file.

    Raises FileNotFoundError if the file does not exist.
    Raises ValueError if the JSON is malformed or missing required fields.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Gateway config not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Required fields
    for key in ("clan_id", "display_name"):
        if key not in data:
            raise ValueError(f"Missing required config field: '{key}'")

    # Parse peers
    peers = []
    for p in data.get("peers", []):
        peers.append(PeerConfig(
            clan_id=p["clan_id"],
            public_key_file=p.get("public_key_file", ""),
            status=p.get("status", "pending_ack"),
            added=p.get("added", ""),
        ))

    return GatewayConfig(
        clan_id=data["clan_id"],
        display_name=data["display_name"],
        protocol_version=data.get("protocol_version", "0.3.0"),
        keys_private=data.get("keys", {}).get("private", ".keys/gateway.key"),
        keys_public=data.get("keys", {}).get("public", ".keys/gateway.pub"),
        agents=data.get("agents", []),
        heraldo_alias=data.get("heraldo", {}).get("external", "herald"),
        peers=peers,
        agora_type=data.get("agora", {}).get("type", "git"),
        agora_url=data.get("agora", {}).get("url", ""),
        agora_local_cache=data.get("agora", {}).get("local_cache", ".agora/"),
        inbound_max_payload=data.get("inbound", {}).get("max_payload_bytes", 4096),
        inbound_rate_limit=data.get("inbound", {}).get("rate_limit_per_clan", 10),
        inbound_quarantine_first_contact=data.get("inbound", {}).get(
            "quarantine_first_contact", True
        ),
        inbound_auto_accept_hello=data.get("inbound", {}).get(
            "auto_accept_hello", True
        ),
    )


def save_config(config: GatewayConfig, path: str | Path) -> None:
    """Save gateway config to a JSON file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "clan_id": config.clan_id,
        "display_name": config.display_name,
        "protocol_version": config.protocol_version,
        "keys": {
            "private": config.keys_private,
            "public": config.keys_public,
        },
        "agents": config.agents,
        "heraldo": {
            "external": config.heraldo_alias,
            "capabilities": ["inter-clan-messaging"],
        },
        "outbound": {
            "profile_update": {"action": "allow", "approval": "operator"},
            "attestation": {"action": "allow", "approval": "operator_per_instance"},
            "quest_response": {
                "action": "allow",
                "approval": "operator_per_instance",
            },
            "hello_ack": {"action": "allow", "approval": "auto"},
            "default": "deny",
        },
        "inbound": {
            "max_payload_bytes": config.inbound_max_payload,
            "rate_limit_per_clan": config.inbound_rate_limit,
            "quarantine_first_contact": config.inbound_quarantine_first_contact,
            "auto_accept_hello": config.inbound_auto_accept_hello,
        },
        "peers": [
            {
                "clan_id": p.clan_id,
                "public_key_file": p.public_key_file,
                "status": p.status,
                "added": p.added,
            }
            for p in config.peers
        ],
        "agora": {
            "type": config.agora_type,
            "url": config.agora_url,
            "local_cache": config.agora_local_cache,
        },
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def init_clan(
    clan_dir: Path,
    clan_id: str,
    display_name: str,
    agora_url: str = "",
) -> GatewayConfig:
    """Initialize a new clan directory with gateway config and key placeholders.

    Creates:
    - gateway.json
    - .keys/ directory
    - .keys/peers/ directory
    - .agora/ directory
    """
    clan_dir = Path(clan_dir)
    clan_dir.mkdir(parents=True, exist_ok=True)

    # Create directory structure
    keys_dir = clan_dir / ".keys"
    keys_dir.mkdir(exist_ok=True)
    (keys_dir / "peers").mkdir(exist_ok=True)
    (clan_dir / ".agora").mkdir(exist_ok=True)

    # Create placeholder key files (NOT cryptographically secure — Phase 2 uses Ed25519)
    key_file = keys_dir / "gateway.key"
    pub_file = keys_dir / "gateway.pub"
    if not key_file.exists():
        placeholder_key = secrets.token_hex(32)
        placeholder_pub = secrets.token_hex(32)
        key_file.write_text(placeholder_key)
        pub_file.write_text(placeholder_pub)

    # Create .gitignore for keys
    gitignore = keys_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("gateway.key\n")

    config = GatewayConfig(
        clan_id=clan_id,
        display_name=display_name,
        agora_url=agora_url,
    )

    save_config(config, clan_dir / "gateway.json")
    return config
