"""Tests for HERMES Gateway Configuration — ARC-3022 Section 16."""

import json

import pytest

from hermes.config import (
    GatewayConfig,
    PeerConfig,
    init_clan,
    load_config,
    save_config,
)


# ─── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def minimal_config():
    """A minimal GatewayConfig with defaults."""
    return GatewayConfig(
        clan_id="clan-alpha",
        display_name="Alpha Collective",
    )


@pytest.fixture
def full_config():
    """A GatewayConfig with all fields populated."""
    return GatewayConfig(
        clan_id="clan-beta",
        display_name="Beta Hive",
        protocol_version="0.4.0",
        keys_private=".keys/beta.key",
        keys_public=".keys/beta.pub",
        agents=[
            {"alias": "scout", "capabilities": ["research"]},
            {"alias": "herald", "capabilities": ["messaging"]},
        ],
        heraldo_alias="herald",
        peers=[
            PeerConfig(
                clan_id="clan-gamma",
                public_key_file=".keys/peers/gamma.pub",
                status="established",
                added="2026-03-01",
            ),
        ],
        agora_type="git",
        agora_url="https://github.com/example/agora",
        agora_local_cache=".agora/",
        inbound_max_payload=8192,
        inbound_rate_limit=20,
        inbound_quarantine_first_contact=False,
        inbound_auto_accept_hello=False,
    )


# ─── save_config / load_config ─────────────────────────────────────


class TestSaveLoadConfig:
    """Round-trip serialization tests."""

    def test_save_creates_file(self, tmp_path, minimal_config):
        config_path = tmp_path / "gateway.json"
        save_config(minimal_config, config_path)
        assert config_path.exists()

    def test_save_produces_valid_json(self, tmp_path, minimal_config):
        config_path = tmp_path / "gateway.json"
        save_config(minimal_config, config_path)
        data = json.loads(config_path.read_text())
        assert data["clan_id"] == "clan-alpha"
        assert data["display_name"] == "Alpha Collective"

    def test_round_trip_minimal(self, tmp_path, minimal_config):
        config_path = tmp_path / "gateway.json"
        save_config(minimal_config, config_path)
        loaded = load_config(config_path)
        assert loaded.clan_id == minimal_config.clan_id
        assert loaded.display_name == minimal_config.display_name
        assert loaded.protocol_version == minimal_config.protocol_version
        assert loaded.peers == []

    def test_round_trip_full(self, tmp_path, full_config):
        config_path = tmp_path / "gateway.json"
        save_config(full_config, config_path)
        loaded = load_config(config_path)
        assert loaded.clan_id == "clan-beta"
        assert loaded.display_name == "Beta Hive"
        assert loaded.protocol_version == "0.4.0"
        assert loaded.keys_private == ".keys/beta.key"
        assert loaded.keys_public == ".keys/beta.pub"
        assert len(loaded.agents) == 2
        assert loaded.heraldo_alias == "herald"
        assert len(loaded.peers) == 1
        assert loaded.peers[0].clan_id == "clan-gamma"
        assert loaded.peers[0].status == "established"
        assert loaded.agora_url == "https://github.com/example/agora"
        assert loaded.inbound_max_payload == 8192
        assert loaded.inbound_rate_limit == 20
        assert loaded.inbound_quarantine_first_contact is False
        assert loaded.inbound_auto_accept_hello is False

    def test_save_creates_parent_dirs(self, tmp_path, minimal_config):
        config_path = tmp_path / "nested" / "deep" / "gateway.json"
        save_config(minimal_config, config_path)
        assert config_path.exists()


# ─── load_config error handling ────────────────────────────────────


class TestLoadConfigErrors:
    """Error cases for load_config."""

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.json")

    def test_missing_clan_id(self, tmp_path):
        config_path = tmp_path / "gateway.json"
        config_path.write_text(json.dumps({"display_name": "Test"}))
        with pytest.raises(ValueError, match="clan_id"):
            load_config(config_path)

    def test_missing_display_name(self, tmp_path):
        config_path = tmp_path / "gateway.json"
        config_path.write_text(json.dumps({"clan_id": "test"}))
        with pytest.raises(ValueError, match="display_name"):
            load_config(config_path)

    def test_invalid_json(self, tmp_path):
        config_path = tmp_path / "gateway.json"
        config_path.write_text("not json at all {{{")
        with pytest.raises(json.JSONDecodeError):
            load_config(config_path)


# ─── init_clan ─────────────────────────────────────────────────────


class TestInitClan:
    """Tests for clan directory initialization."""

    def test_creates_directory_structure(self, tmp_path):
        clan_dir = tmp_path / "my-clan"
        init_clan(clan_dir, "clan-test", "Test Clan")

        assert clan_dir.exists()
        assert (clan_dir / ".keys").is_dir()
        assert (clan_dir / ".keys" / "peers").is_dir()
        assert (clan_dir / ".agora").is_dir()
        assert (clan_dir / "gateway.json").exists()

    def test_creates_placeholder_keys(self, tmp_path):
        clan_dir = tmp_path / "my-clan"
        init_clan(clan_dir, "clan-test", "Test Clan")

        key_file = clan_dir / ".keys" / "gateway.key"
        pub_file = clan_dir / ".keys" / "gateway.pub"
        assert key_file.exists()
        assert pub_file.exists()
        # Placeholder keys are hex strings (64 chars = 32 bytes)
        assert len(key_file.read_text()) == 64
        assert len(pub_file.read_text()) == 64

    def test_creates_gitignore(self, tmp_path):
        clan_dir = tmp_path / "my-clan"
        init_clan(clan_dir, "clan-test", "Test Clan")

        gitignore = clan_dir / ".keys" / ".gitignore"
        assert gitignore.exists()
        assert "gateway.key" in gitignore.read_text()

    def test_does_not_overwrite_existing_keys(self, tmp_path):
        clan_dir = tmp_path / "my-clan"
        keys_dir = clan_dir / ".keys"
        keys_dir.mkdir(parents=True)
        key_file = keys_dir / "gateway.key"
        key_file.write_text("existing-secret-key")

        init_clan(clan_dir, "clan-test", "Test Clan")
        assert key_file.read_text() == "existing-secret-key"

    def test_returns_config(self, tmp_path):
        clan_dir = tmp_path / "my-clan"
        config = init_clan(clan_dir, "clan-test", "Test Clan", agora_url="https://example.com/agora")

        assert config.clan_id == "clan-test"
        assert config.display_name == "Test Clan"
        assert config.agora_url == "https://example.com/agora"

    def test_config_file_loadable(self, tmp_path):
        clan_dir = tmp_path / "my-clan"
        init_clan(clan_dir, "clan-test", "Test Clan")

        loaded = load_config(clan_dir / "gateway.json")
        assert loaded.clan_id == "clan-test"

    def test_idempotent(self, tmp_path):
        clan_dir = tmp_path / "my-clan"
        config1 = init_clan(clan_dir, "clan-test", "Test Clan")
        config2 = init_clan(clan_dir, "clan-test", "Test Clan")

        assert config1.clan_id == config2.clan_id


# ─── PeerConfig ────────────────────────────────────────────────────


class TestPeerConfig:
    """Tests for peer serialization."""

    def test_peer_defaults(self):
        peer = PeerConfig(clan_id="clan-x", public_key_file="x.pub")
        assert peer.status == "pending_ack"
        assert peer.added == ""

    def test_peers_round_trip(self, tmp_path):
        config = GatewayConfig(
            clan_id="clan-main",
            display_name="Main",
            peers=[
                PeerConfig("clan-a", "a.pub", "established", "2026-01-01"),
                PeerConfig("clan-b", "b.pub", "suspended", "2026-02-15"),
            ],
        )
        config_path = tmp_path / "gateway.json"
        save_config(config, config_path)
        loaded = load_config(config_path)

        assert len(loaded.peers) == 2
        assert loaded.peers[0].clan_id == "clan-a"
        assert loaded.peers[0].status == "established"
        assert loaded.peers[1].clan_id == "clan-b"
        assert loaded.peers[1].status == "suspended"
