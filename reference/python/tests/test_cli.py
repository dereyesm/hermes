"""Tests for HERMES CLI — hermes init, status, publish, peer, send, inbox, discover."""

from __future__ import annotations

from hermes.cli import main


class TestInit:
    def test_init_creates_structure(self, tmp_path):
        rc = main(["init", "test-clan", "Test Clan", "--dir", str(tmp_path)])
        assert rc == 0
        assert (tmp_path / "gateway.json").exists()
        assert (tmp_path / ".keys" / "gateway.key").exists()
        assert (tmp_path / ".keys" / "gateway.pub").exists()
        assert (tmp_path / ".keys" / "peers").is_dir()
        assert (tmp_path / ".agora" / "profiles").is_dir()

    def test_init_config_content(self, tmp_path):
        import json

        main(["init", "my-clan", "My Clan", "--dir", str(tmp_path)])
        config = json.loads((tmp_path / "gateway.json").read_text())
        assert config["clan_id"] == "my-clan"
        assert config["display_name"] == "My Clan"

    def test_init_with_agora_url(self, tmp_path):
        import json

        main([
            "init", "url-clan", "URL Clan",
            "--agora-url", "https://github.com/hermes-agora/directory",
            "--dir", str(tmp_path),
        ])
        config = json.loads((tmp_path / "gateway.json").read_text())
        assert config["agora"]["url"] == "https://github.com/hermes-agora/directory"


class TestStatus:
    def test_status_no_config(self, tmp_path):
        rc = main(["status", "--dir", str(tmp_path)])
        assert rc == 1

    def test_status_after_init(self, tmp_path, capsys):
        main(["init", "st-clan", "Status Clan", "--dir", str(tmp_path)])
        rc = main(["status", "--dir", str(tmp_path)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "st-clan" in out
        assert "Status Clan" in out


class TestPublish:
    def test_publish_creates_profile(self, tmp_path):
        main(["init", "pub-clan", "Pub Clan", "--dir", str(tmp_path)])
        rc = main(["publish", "--dir", str(tmp_path)])
        assert rc == 0
        profile_path = tmp_path / ".agora" / "profiles" / "pub-clan.json"
        assert profile_path.exists()

    def test_publish_profile_content(self, tmp_path):
        import json

        main(["init", "pub2", "Pub 2", "--dir", str(tmp_path)])
        main(["publish", "--dir", str(tmp_path)])
        profile = json.loads(
            (tmp_path / ".agora" / "profiles" / "pub2.json").read_text()
        )
        assert profile["clan_id"] == "pub2"
        assert "agents" in profile
        assert "public_key" in profile


class TestPeer:
    def _setup_two_clans(self, tmp_path):
        """Create two clans sharing the same Agora directory."""
        clan_a = tmp_path / "clan-a"
        clan_b = tmp_path / "clan-b"
        shared_agora = tmp_path / "agora"

        # Init both clans
        main(["init", "alpha", "Clan Alpha", "--dir", str(clan_a)])
        main(["init", "beta", "Clan Beta", "--dir", str(clan_b)])

        # Point both to shared agora by symlinking
        import shutil
        # Remove default .agora dirs and replace with shared
        shutil.rmtree(clan_a / ".agora")
        shutil.rmtree(clan_b / ".agora")
        shared_agora.mkdir()
        from hermes.agora import AgoraDirectory
        agora = AgoraDirectory(shared_agora)
        agora.ensure_structure()
        (clan_a / ".agora").symlink_to(shared_agora)
        (clan_b / ".agora").symlink_to(shared_agora)

        return clan_a, clan_b

    def test_peer_add_sends_hello(self, tmp_path):
        clan_a, clan_b = self._setup_two_clans(tmp_path)

        # Publish alpha's profile
        main(["publish", "--dir", str(clan_a)])

        # Beta adds alpha as peer
        rc = main(["peer", "add", "alpha", "--dir", str(clan_b)])
        assert rc == 0

        # Alpha should have hello in inbox
        from hermes.agora import AgoraDirectory
        agora = AgoraDirectory(clan_a / ".agora")
        messages = agora.read_inbox("alpha")
        assert len(messages) == 1
        assert messages[0]["type"] == "hello"
        assert messages[0]["source_clan"] == "beta"

    def test_peer_list(self, tmp_path, capsys):
        clan_a, clan_b = self._setup_two_clans(tmp_path)
        main(["publish", "--dir", str(clan_a)])
        main(["peer", "add", "alpha", "--dir", str(clan_b)])

        rc = main(["peer", "list", "--dir", str(clan_b)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "alpha" in out
        assert "pending_ack" in out

    def test_peer_add_duplicate(self, tmp_path, capsys):
        clan_a, clan_b = self._setup_two_clans(tmp_path)
        main(["publish", "--dir", str(clan_a)])
        main(["peer", "add", "alpha", "--dir", str(clan_b)])
        rc = main(["peer", "add", "alpha", "--dir", str(clan_b)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "already registered" in out


class TestSend:
    def test_send_drops_message(self, tmp_path):
        main(["init", "sender", "Sender", "--dir", str(tmp_path)])
        rc = main(["send", "receiver", "Hello from sender!", "--dir", str(tmp_path)])
        assert rc == 0

        from hermes.agora import AgoraDirectory
        agora = AgoraDirectory(tmp_path / ".agora")
        messages = agora.read_inbox("receiver")
        assert len(messages) == 1
        assert messages[0]["payload"] == "Hello from sender!"
        assert messages[0]["source_clan"] == "sender"

    def test_send_blocked_by_filter(self, tmp_path):
        main(["init", "leaky", "Leaky", "--dir", str(tmp_path)])
        rc = main([
            "send", "target", "Check bus.jsonl for secrets",
            "--dir", str(tmp_path),
        ])
        assert rc == 1


class TestInbox:
    def test_inbox_empty(self, tmp_path, capsys):
        main(["init", "empty-inbox", "Empty", "--dir", str(tmp_path)])
        rc = main(["inbox", "--dir", str(tmp_path)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "empty" in out.lower()

    def test_inbox_with_messages(self, tmp_path, capsys):
        main(["init", "recv", "Receiver", "--dir", str(tmp_path)])
        # Drop a message manually
        from hermes.agora import AgoraDirectory
        agora = AgoraDirectory(tmp_path / ".agora")
        agora.send_message("recv", {
            "type": "quest_proposal",
            "source_clan": "other-clan",
            "payload": "Need help with finance",
            "timestamp": "2026-03-06",
        })

        rc = main(["inbox", "--dir", str(tmp_path)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "other-clan" in out
        assert "quest_proposal" in out


class TestDiscover:
    def test_discover_finds_agents(self, tmp_path):
        import json

        main(["init", "disco", "Disco Clan", "--dir", str(tmp_path)])
        # Add an agent to config
        config_path = tmp_path / "gateway.json"
        config = json.loads(config_path.read_text())
        config["agents"] = [{
            "internal": {"namespace": "finance", "agent": "auditor"},
            "external": "gold-auditor",
            "published": True,
            "capabilities": ["finance/audit", "finance/tax"],
        }]
        config_path.write_text(json.dumps(config, indent=2))

        # Publish profile
        main(["publish", "--dir", str(tmp_path)])

        # Discover
        from hermes.agora import AgoraDirectory
        agora = AgoraDirectory(tmp_path / ".agora")
        matches = agora.discover("finance")
        assert len(matches) == 1
        assert matches[0]["agent_alias"] == "gold-auditor"


class TestEndToEnd:
    """Full flow: init two clans, publish, peer, send, inbox."""

    def test_first_contact(self, tmp_path):
        import shutil
        from hermes.agora import AgoraDirectory

        # Shared Agora
        shared = tmp_path / "agora"
        shared.mkdir()
        agora = AgoraDirectory(shared)
        agora.ensure_structure()

        clan_d = tmp_path / "daniel"
        clan_j = tmp_path / "jeimmy"

        # Init both
        main(["init", "momosho-d", "Clan Momosho D.", "--dir", str(clan_d)])
        main(["init", "jeimmy-clan", "Clan Jeimmy", "--dir", str(clan_j)])

        # Point to shared Agora
        for clan in (clan_d, clan_j):
            shutil.rmtree(clan / ".agora")
            (clan / ".agora").symlink_to(shared)

        # Daniel publishes
        main(["publish", "--dir", str(clan_d)])
        assert agora.read_profile("momosho-d") is not None

        # Jeimmy publishes
        main(["publish", "--dir", str(clan_j)])
        assert agora.read_profile("jeimmy-clan") is not None

        # Jeimmy adds Daniel as peer
        main(["peer", "add", "momosho-d", "--dir", str(clan_j)])

        # Daniel checks inbox — should have hello
        msgs = agora.read_inbox("momosho-d")
        assert len(msgs) == 1
        assert msgs[0]["type"] == "hello"
        assert msgs[0]["source_clan"] == "jeimmy-clan"

        # Daniel adds Jeimmy as peer
        main(["peer", "add", "jeimmy-clan", "--dir", str(clan_d)])

        # Jeimmy checks inbox — should have hello from Daniel
        msgs_j = agora.read_inbox("jeimmy-clan")
        assert len(msgs_j) == 1
        assert msgs_j[0]["source_clan"] == "momosho-d"

        # Daniel sends a message
        main(["send", "jeimmy-clan", "First Contact achieved!", "--dir", str(clan_d)])

        # Jeimmy reads inbox — hello + quest_response
        msgs_j2 = agora.read_inbox("jeimmy-clan")
        assert len(msgs_j2) == 2
        assert any(
            m.get("payload") == "First Contact achieved!" for m in msgs_j2
        )
