"""HERMES Gateway Configuration — ARC-3022 Section 16 Reference Implementation.

Load, validate, and save gateway configuration files (JSON and TOML formats).
Supports auto-discovery: config.toml preferred over gateway.json.
"""

from __future__ import annotations

import json
import secrets
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomli_w

CONFIG_SCHEMA_VERSION = 1


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


# ─── Internal helpers ─────────────────────────────────────────────


def _parse_peers(raw_peers: list[dict]) -> list[PeerConfig]:
    """Parse a list of peer dicts into PeerConfig objects."""
    peers = []
    for p in raw_peers:
        peers.append(PeerConfig(
            clan_id=p["clan_id"],
            public_key_file=p.get("public_key_file", ""),
            status=p.get("status", "pending_ack"),
            added=p.get("added", ""),
        ))
    return peers


def _atomic_write(path: Path, content: str) -> None:
    """Write content atomically via tmp file + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


# ─── JSON format (internal) ──────────────────────────────────────


def _load_config_json(path: Path) -> GatewayConfig:
    """Load gateway config from a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for key in ("clan_id", "display_name"):
        if key not in data:
            raise ValueError(f"Missing required config field: '{key}'")

    return GatewayConfig(
        clan_id=data["clan_id"],
        display_name=data["display_name"],
        protocol_version=data.get("protocol_version", "0.3.0"),
        keys_private=data.get("keys", {}).get("private", ".keys/gateway.key"),
        keys_public=data.get("keys", {}).get("public", ".keys/gateway.pub"),
        agents=data.get("agents", []),
        heraldo_alias=data.get("heraldo", {}).get("external", "herald"),
        peers=_parse_peers(data.get("peers", [])),
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


def _save_config_json(config: GatewayConfig, path: Path) -> None:
    """Save gateway config to a JSON file."""
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


# ─── TOML format ─────────────────────────────────────────────────


def _config_to_toml_dict(config: GatewayConfig) -> dict:
    """Convert a GatewayConfig to a TOML-serializable dict."""
    data: dict[str, Any] = {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "clan": {
            "id": config.clan_id,
            "display_name": config.display_name,
            "protocol_version": config.protocol_version,
        },
        "keys": {
            "private": config.keys_private,
            "public": config.keys_public,
        },
        "bus": {
            "active": "bus/active.jsonl",
            "archive": "bus/archive.jsonl",
        },
        "heraldo": {
            "alias": config.heraldo_alias,
            "capabilities": ["inter-clan-messaging"],
        },
        "agora": {
            "type": config.agora_type,
            "url": config.agora_url,
            "local_cache": config.agora_local_cache,
        },
        "inbound": {
            "max_payload_bytes": config.inbound_max_payload,
            "rate_limit_per_clan": config.inbound_rate_limit,
            "quarantine_first_contact": config.inbound_quarantine_first_contact,
            "auto_accept_hello": config.inbound_auto_accept_hello,
        },
        "outbound": {
            "default": "deny",
            "rules": {
                "profile_update": {"action": "allow", "approval": "operator"},
                "attestation": {"action": "allow", "approval": "operator_per_instance"},
                "quest_response": {"action": "allow", "approval": "operator_per_instance"},
                "hello_ack": {"action": "allow", "approval": "auto"},
            },
        },
    }

    if config.agents:
        data["agents"] = config.agents

    if config.peers:
        data["peers"] = [
            {
                "clan_id": p.clan_id,
                "public_key_file": p.public_key_file,
                "status": p.status,
                "added": p.added,
            }
            for p in config.peers
        ]

    return data


def load_config_toml(path: Path) -> GatewayConfig:
    """Load gateway config from a TOML file.

    Raises FileNotFoundError if the file does not exist.
    Raises ValueError if required fields are missing.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    with open(path, "rb") as f:
        data = tomllib.load(f)

    # Validate schema version
    schema_ver = data.get("schema_version", 1)
    if schema_ver > CONFIG_SCHEMA_VERSION:
        raise ValueError(
            f"Config schema version {schema_ver} is newer than supported "
            f"version {CONFIG_SCHEMA_VERSION}. Upgrade HERMES."
        )

    clan = data.get("clan", {})
    if not clan.get("id"):
        raise ValueError("Missing required config field: 'clan.id'")
    if not clan.get("display_name"):
        raise ValueError("Missing required config field: 'clan.display_name'")

    keys = data.get("keys", {})
    heraldo = data.get("heraldo", {})
    agora = data.get("agora", {})
    inbound = data.get("inbound", {})

    return GatewayConfig(
        clan_id=clan["id"],
        display_name=clan["display_name"],
        protocol_version=clan.get("protocol_version", "0.3.0"),
        keys_private=keys.get("private", ".keys/gateway.key"),
        keys_public=keys.get("public", ".keys/gateway.pub"),
        agents=data.get("agents", []),
        heraldo_alias=heraldo.get("alias", "herald"),
        peers=_parse_peers(data.get("peers", [])),
        agora_type=agora.get("type", "git"),
        agora_url=agora.get("url", ""),
        agora_local_cache=agora.get("local_cache", ".agora/"),
        inbound_max_payload=inbound.get("max_payload_bytes", 4096),
        inbound_rate_limit=inbound.get("rate_limit_per_clan", 10),
        inbound_quarantine_first_contact=inbound.get(
            "quarantine_first_contact", True
        ),
        inbound_auto_accept_hello=inbound.get("auto_accept_hello", True),
    )


def save_config_toml(config: GatewayConfig, path: Path) -> None:
    """Save gateway config to a TOML file (atomic write)."""
    data = _config_to_toml_dict(config)
    content = tomli_w.dumps(data)
    _atomic_write(Path(path), content)


def migrate_json_to_toml(
    json_path: str | Path,
    toml_path: str | Path | None = None,
) -> Path:
    """Migrate a gateway.json to config.toml.

    The JSON file is kept as backup. Returns the path to the new TOML file.
    """
    json_path = Path(json_path)
    if toml_path is None:
        toml_path = json_path.parent / "config.toml"
    else:
        toml_path = Path(toml_path)

    config = _load_config_json(json_path)
    save_config_toml(config, toml_path)
    return toml_path


# ─── Public API (auto-discovery) ─────────────────────────────────


def resolve_config_path(clan_dir: Path) -> Path:
    """Find the config file in a clan directory.

    Prefers config.toml over gateway.json.
    Raises FileNotFoundError if neither exists.
    """
    toml_path = clan_dir / "config.toml"
    if toml_path.exists():
        return toml_path
    json_path = clan_dir / "gateway.json"
    if json_path.exists():
        return json_path
    raise FileNotFoundError(
        f"No config.toml or gateway.json in {clan_dir}"
    )


def load_config(path: str | Path) -> GatewayConfig:
    """Load gateway config with auto-discovery.

    - If path is a directory: try config.toml first, then gateway.json.
    - If path is a .toml file: load as TOML.
    - Otherwise: load as JSON.

    Raises FileNotFoundError if the config is not found.
    Raises ValueError if required fields are missing.
    """
    path = Path(path)

    if path.is_dir():
        path = resolve_config_path(path)

    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    if path.suffix == ".toml":
        return load_config_toml(path)
    return _load_config_json(path)


def save_config(config: GatewayConfig, path: str | Path) -> None:
    """Save gateway config, dispatching by file extension."""
    path = Path(path)
    if path.suffix == ".toml":
        save_config_toml(config, path)
    else:
        _save_config_json(config, path)


def init_clan(
    clan_dir: Path,
    clan_id: str,
    display_name: str,
    agora_url: str = "",
    config_format: str = "json",
) -> GatewayConfig:
    """Initialize a new clan directory with config and key placeholders.

    Args:
        config_format: "json" (default) or "toml".
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

    if config_format == "toml":
        # Create bus directory structure for TOML layout
        (clan_dir / "bus").mkdir(exist_ok=True)
        save_config(config, clan_dir / "config.toml")
    else:
        save_config(config, clan_dir / "gateway.json")

    return config
