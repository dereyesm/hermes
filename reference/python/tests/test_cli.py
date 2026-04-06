"""Tests for Amaru CLI — amaru init, status, publish, peer, send, inbox, discover, bus."""

from __future__ import annotations

from amaru.cli import main
from amaru.message import create_message


class TestInit:
    def test_init_creates_structure(self, tmp_path):
        rc = main(["init", "test-clan", "Test Clan", "--dir", str(tmp_path)])
        assert rc == 0
        assert (tmp_path / "gateway.json").exists()
        assert (tmp_path / ".keys" / "test-clan.key").exists()
        assert (tmp_path / ".keys" / "test-clan.pub").exists()
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

        main(
            [
                "init",
                "url-clan",
                "URL Clan",
                "--agora-url",
                "https://github.com/amaru-agora/directory",
                "--dir",
                str(tmp_path),
            ]
        )
        config = json.loads((tmp_path / "gateway.json").read_text())
        assert config["agora"]["url"] == "https://github.com/amaru-agora/directory"


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
        profile = json.loads((tmp_path / ".agora" / "profiles" / "pub2.json").read_text())
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
        from amaru.agora import AgoraDirectory

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
        from amaru.agora import AgoraDirectory

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
    def test_send_no_hub_returns_error(self, tmp_path):
        """amaru send fails gracefully when no hub is reachable."""
        main(["init", "sender", "Sender", "--dir", str(tmp_path)])
        rc = main(["send", "receiver", "Hello from sender!", "--dir", str(tmp_path)])
        # Should fail (rc=1) because no hub is running
        assert rc == 1

    def test_send_blocked_by_filter(self, tmp_path):
        main(["init", "leaky", "Leaky", "--dir", str(tmp_path)])
        rc = main(
            [
                "send",
                "target",
                "Check bus.jsonl for secrets",
                "--dir",
                str(tmp_path),
            ]
        )
        assert rc == 1

    def test_send_writes_to_bus_even_without_hub(self, tmp_path):
        """Durable bus record MUST exist even when live delivery fails.

        Regression guard: before this fix, `amaru send` was pure
        WebSocket — no hub reachable meant zero trace of the attempt.
        The bus is the source of truth for intent; delivery is a
        separate concern (ATR-Q.931 §8 delivery receipts).
        """
        from amaru.bus import read_bus

        main(["init", "sender", "Sender", "--dir", str(tmp_path)])
        bus_path = tmp_path / "bus.jsonl"
        # Clean slate — init may or may not touch bus.jsonl
        if bus_path.exists():
            bus_path.unlink()

        rc = main(
            [
                "send",
                "receiver",
                "persistent hello",
                "--type",
                "alert",
                "--dir",
                str(tmp_path),
            ]
        )
        # Live send still fails (no hub), but bus write MUST have happened.
        assert rc == 1
        assert bus_path.exists(), "bus.jsonl should be created even without hub"

        msgs = read_bus(bus_path)
        assert len(msgs) == 1
        m = msgs[0]
        assert m.src == "sender"
        assert m.dst == "receiver"
        assert m.type == "alert"
        assert m.msg == "persistent hello"
        assert m.ttl == 7
        assert m.ack == []

    def test_send_default_type_is_event_on_bus(self, tmp_path):
        """When --type is omitted, the bus record MUST use 'event'."""
        from amaru.bus import read_bus

        main(["init", "sender", "Sender", "--dir", str(tmp_path)])
        bus_path = tmp_path / "bus.jsonl"
        if bus_path.exists():
            bus_path.unlink()

        main(["send", "receiver", "default type test", "--dir", str(tmp_path)])

        msgs = read_bus(bus_path)
        assert len(msgs) == 1
        assert msgs[0].type == "event"

    def test_send_bus_output_tag(self, tmp_path, capsys):
        """Stdout MUST reflect bus write outcome alongside delivery result."""
        main(["init", "sender", "Sender", "--dir", str(tmp_path)])
        main(["send", "receiver", "tagline test", "--dir", str(tmp_path)])
        out = capsys.readouterr().out
        assert "bus ok" in out
        # no hub → failed — no hub reachable
        assert "failed" in out


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
        from amaru.agora import AgoraDirectory

        agora = AgoraDirectory(tmp_path / ".agora")
        agora.send_message(
            "recv",
            {
                "type": "quest_proposal",
                "source_clan": "other-clan",
                "payload": "Need help with finance",
                "timestamp": "2026-03-06",
            },
        )

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
        config["agents"] = [
            {
                "internal": {"namespace": "finance", "agent": "auditor"},
                "external": "gold-auditor",
                "published": True,
                "capabilities": ["finance/audit", "finance/tax"],
            }
        ]
        config_path.write_text(json.dumps(config, indent=2))

        # Publish profile
        main(["publish", "--dir", str(tmp_path)])

        # Discover
        from amaru.agora import AgoraDirectory

        agora = AgoraDirectory(tmp_path / ".agora")
        matches = agora.discover("finance")
        assert len(matches) == 1
        assert matches[0]["agent_alias"] == "gold-auditor"


class TestBusCommand:
    """Tests for amaru bus command with --compact and --expand flags."""

    def _setup_clan_with_bus(self, tmp_path, capsys):
        """Create a clan dir with gateway.json and a bus with test messages."""
        from datetime import date

        main(["init", "test-clan", "Test Clan", "--dir", str(tmp_path)])
        capsys.readouterr()  # discard init output
        bus_path = tmp_path / "bus.jsonl"
        msg = create_message(
            src="alpha",
            dst="*",
            type="state",
            msg="test message",
            ttl=7,
            ts=date(2026, 3, 17),
        )
        bus_path.write_text(msg.to_jsonl() + "\n")
        return bus_path

    def test_bus_compact_output(self, tmp_path, capsys):
        """amaru bus --compact should output compact JSONL."""
        self._setup_clan_with_bus(tmp_path, capsys)
        rc = main(["bus", "--compact", "--dir", str(tmp_path)])
        assert rc == 0
        out = capsys.readouterr().out.strip()
        assert out.startswith("[")  # compact format starts with [

    def test_bus_expand_output(self, tmp_path, capsys):
        """amaru bus --expand should output verbose JSONL."""
        self._setup_clan_with_bus(tmp_path, capsys)
        rc = main(["bus", "--expand", "--dir", str(tmp_path)])
        assert rc == 0
        out = capsys.readouterr().out.strip()
        assert out.startswith("{")  # verbose format starts with {

    def test_bus_default_output(self, tmp_path, capsys):
        """amaru bus (no flags) should use print_bus_messages."""
        self._setup_clan_with_bus(tmp_path, capsys)
        rc = main(["bus", "--dir", str(tmp_path)])
        assert rc == 0

    def test_bus_compact_reads_mixed_format(self, tmp_path, capsys):
        """amaru bus --compact should handle mixed verbose+compact input."""
        from datetime import date

        self._setup_clan_with_bus(tmp_path, capsys)
        bus_path = tmp_path / "bus.jsonl"
        # Add a compact message
        msg2 = create_message(
            src="beta",
            dst="*",
            type="event",
            msg="compact msg",
            ttl=3,
            ts=date(2026, 3, 17),
        )
        with bus_path.open("a") as f:
            f.write(msg2.to_compact_jsonl() + "\n")

        rc = main(["bus", "--compact", "--dir", str(tmp_path)])
        assert rc == 0
        lines = capsys.readouterr().out.strip().split("\n")
        assert len(lines) == 2
        assert all(line.startswith("[") for line in lines)

    def test_bus_compact_with_filter(self, tmp_path, capsys):
        """--compact works with --filter-type."""
        from datetime import date

        self._setup_clan_with_bus(tmp_path, capsys)
        bus_path = tmp_path / "bus.jsonl"
        msg2 = create_message(
            src="beta",
            dst="*",
            type="alert",
            msg="alert msg",
            ttl=5,
            ts=date(2026, 3, 17),
        )
        with bus_path.open("a") as f:
            f.write(msg2.to_jsonl() + "\n")

        rc = main(["bus", "--compact", "--filter-type", "alert", "--dir", str(tmp_path)])
        assert rc == 0
        lines = capsys.readouterr().out.strip().split("\n")
        assert len(lines) == 1
        assert "alert msg" in lines[0]


class TestConfigMigrate:
    def test_migrate_json_to_toml(self, tmp_path):
        main(["init", "mig-clan", "Migrate Clan", "--dir", str(tmp_path)])
        assert (tmp_path / "gateway.json").exists()
        rc = main(["config", "migrate", "--dir", str(tmp_path)])
        assert rc == 0
        assert (tmp_path / "config.toml").exists()

    def test_migrate_already_exists(self, tmp_path, capsys):
        main(["init", "mig2", "Mig2", "--dir", str(tmp_path)])
        main(["config", "migrate", "--dir", str(tmp_path)])
        capsys.readouterr()
        rc = main(["config", "migrate", "--dir", str(tmp_path)])
        assert rc == 0
        assert "already exists" in capsys.readouterr().out

    def test_migrate_no_json(self, tmp_path):
        rc = main(["config", "migrate", "--dir", str(tmp_path)])
        assert rc == 1


class TestAgentCommand:
    def test_agent_list_empty(self, tmp_path, capsys):
        main(["init", "ag-clan", "Agent Clan", "--dir", str(tmp_path)])
        capsys.readouterr()
        rc = main(["agent", "list", "--dir", str(tmp_path)])
        assert rc == 0
        assert "No agents" in capsys.readouterr().out

    def test_agent_list_with_profile(self, tmp_path, capsys):
        import json

        main(["init", "ag2", "Agent2", "--dir", str(tmp_path)])
        capsys.readouterr()
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        profile = {
            "agent_id": "test-bot",
            "display_name": "Test Bot",
            "version": "1.0",
            "role": "worker",
            "description": "Test agent",
            "capabilities": ["messaging"],
            "enabled": True,
            "dispatch_rules": [],
            "resource_limits": {},
        }
        (agents_dir / "test-bot.json").write_text(json.dumps(profile))
        rc = main(["agent", "list", "--dir", str(tmp_path)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "test-bot" in out

    def test_agent_validate_empty(self, tmp_path, capsys):
        main(["init", "ag3", "Agent3", "--dir", str(tmp_path)])
        capsys.readouterr()
        (tmp_path / "agents").mkdir()
        rc = main(["agent", "validate", "--dir", str(tmp_path)])
        assert rc == 0
        assert "0 errors" in capsys.readouterr().out

    def test_agent_show_not_found(self, tmp_path):
        main(["init", "ag4", "Agent4", "--dir", str(tmp_path)])
        (tmp_path / "agents").mkdir()
        rc = main(["agent", "show", "nonexistent", "--dir", str(tmp_path)])
        assert rc == 1


class TestAdaptCommand:
    def test_adapt_no_adapter(self):
        rc = main(["adapt"])
        assert rc == 1

    def test_adapt_list(self, capsys):
        rc = main(["adapt", "--list"])
        assert rc == 0
        output = capsys.readouterr().out
        assert "claude-code" in output
        assert "gemini" in output
        assert "opencode" in output
        assert "cursor" in output

    def test_adapt_unknown_adapter(self, tmp_path):
        rc = main(["adapt", "nonexistent", "--amaru-dir", str(tmp_path)])
        assert rc == 1


class TestLlmCommand:
    def test_llm_list_no_backends(self, tmp_path, capsys):
        main(["init", "llm-clan", "LLM Clan", "--dir", str(tmp_path)])
        capsys.readouterr()
        rc = main(["llm", "list", "--dir", str(tmp_path)])
        assert rc == 0
        assert "No LLM" in capsys.readouterr().out

    def test_llm_no_subcommand(self):
        rc = main(["llm"])
        assert rc == 1


class TestHookCommand:
    def test_hook_no_subcommand(self):
        rc = main(["hook"])
        assert rc == 1


class TestEndToEnd:
    """Full flow: init two clans, publish, peer, send, inbox."""

    def test_first_contact(self, tmp_path):
        import shutil

        from amaru.agora import AgoraDirectory

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

        # Daniel sends a message (fails: no hub running, but doesn't crash)
        rc = main(["send", "jeimmy-clan", "First Contact achieved!", "--dir", str(clan_d)])
        assert rc == 1  # No hub → graceful failure

        # Jeimmy inbox still has the hello from peer add
        msgs_j2 = agora.read_inbox("jeimmy-clan")
        assert len(msgs_j2) == 1  # Only the hello, no send without hub
