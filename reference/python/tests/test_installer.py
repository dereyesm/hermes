"""Tests for HERMES installer, hooks, and CLI integration."""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hermes.installer import (
    _HUB_LABEL,
    _HUB_LISTEN_LABEL,
    _LAUNCHAGENT_LABEL,
    Platform,
    _atomic_json_write,
    _sanitize_for_shell,
    add_agent_node_section,
    default_clan_dir,
    detect_platform,
    generate_hub_service,
    generate_keypair,
    generate_launchagent,
    generate_systemd_unit,
    generate_windows_task,
    init_clan_if_needed,
    install_hooks,
    install_hub_service,
    run_install,
    run_uninstall,
    send_notification,
    uninstall_hub_service,
    uninstall_hooks,
)

# ---------------------------------------------------------------------------
# Platform Detection
# ---------------------------------------------------------------------------


class TestPlatformDetection:
    """Test detect_platform() with monkeypatched platform.system()."""

    def test_macos(self, monkeypatch):
        monkeypatch.setattr("hermes.installer.platform.system", lambda: "Darwin")
        assert detect_platform() == Platform.MACOS

    def test_linux(self, monkeypatch):
        monkeypatch.setattr("hermes.installer.platform.system", lambda: "Linux")
        assert detect_platform() == Platform.LINUX

    def test_windows(self, monkeypatch):
        monkeypatch.setattr("hermes.installer.platform.system", lambda: "Windows")
        assert detect_platform() == Platform.WINDOWS

    def test_unsupported_raises(self, monkeypatch):
        monkeypatch.setattr("hermes.installer.platform.system", lambda: "FreeBSD")
        with pytest.raises(RuntimeError, match="Unsupported"):
            detect_platform()


class TestDefaultClanDir:
    """Test default_clan_dir() for each platform."""

    def test_unix_dir(self):
        result = default_clan_dir(Platform.MACOS)
        assert result == Path.home() / ".hermes"

    def test_linux_dir(self):
        result = default_clan_dir(Platform.LINUX)
        assert result == Path.home() / ".hermes"

    def test_windows_dir(self, monkeypatch):
        monkeypatch.setenv("APPDATA", "/fake/appdata")
        result = default_clan_dir(Platform.WINDOWS)
        assert result == Path("/fake/appdata/hermes")


# ---------------------------------------------------------------------------
# Init Clan
# ---------------------------------------------------------------------------


class TestInitClanIfNeeded:
    """Test init_clan_if_needed()."""

    def test_creates_new_clan(self, tmp_path):
        created, msg = init_clan_if_needed(tmp_path / "test-clan", "test", "Test Clan")
        assert created is True
        assert "initialized" in msg
        assert (tmp_path / "test-clan" / "gateway.json").exists()

    def test_skips_existing_clan(self, tmp_path):
        clan_dir = tmp_path / "existing"
        clan_dir.mkdir()
        (clan_dir / "gateway.json").write_text('{"clan_id": "x", "display_name": "X"}')
        created, msg = init_clan_if_needed(clan_dir, "x", "X")
        assert created is False
        assert "already" in msg

    def test_passes_agora_url(self, tmp_path):
        created, msg = init_clan_if_needed(
            tmp_path / "with-agora", "test", "Test", agora_url="https://agora.example.com"
        )
        assert created is True
        config = json.loads((tmp_path / "with-agora" / "gateway.json").read_text())
        assert config["agora"]["url"] == "https://agora.example.com"


# ---------------------------------------------------------------------------
# Keypair Generation
# ---------------------------------------------------------------------------


class TestGenerateKeypair:
    """Test generate_keypair()."""

    def test_generates_new_keys(self, tmp_path):
        # Create .keys/ dir without keys (init_clan now generates real keys,
        # so we set up manually to test generate_keypair independently)
        keys_dir = tmp_path / ".keys"
        keys_dir.mkdir(parents=True)

        created, msg, fp = generate_keypair(tmp_path, "testclan")
        assert created is True
        assert "generated" in msg
        assert ":" in fp  # Fingerprint format
        assert (tmp_path / ".keys" / "testclan.key").exists()
        assert (tmp_path / ".keys" / "testclan.pub").exists()

    def test_skips_existing_keys(self, tmp_path):
        init_clan_if_needed(tmp_path, "testclan", "Test")
        generate_keypair(tmp_path, "testclan")

        created, msg, fp = generate_keypair(tmp_path, "testclan")
        assert created is False
        assert "already exist" in msg
        assert ":" in fp


# ---------------------------------------------------------------------------
# Agent Node Section
# ---------------------------------------------------------------------------


class TestAddAgentNodeSection:
    """Test add_agent_node_section()."""

    def test_adds_section(self, tmp_path):
        init_clan_if_needed(tmp_path, "test", "Test")
        modified, msg = add_agent_node_section(tmp_path)
        assert modified is True

        config = json.loads((tmp_path / "gateway.json").read_text())
        assert "agent_node" in config
        assert config["agent_node"]["enabled"] is True

    def test_idempotent(self, tmp_path):
        init_clan_if_needed(tmp_path, "test", "Test")
        add_agent_node_section(tmp_path)
        modified, msg = add_agent_node_section(tmp_path)
        assert modified is False
        assert "already present" in msg

    def test_no_config(self, tmp_path):
        modified, msg = add_agent_node_section(tmp_path)
        assert modified is False


# ---------------------------------------------------------------------------
# Service Generation
# ---------------------------------------------------------------------------


class TestServiceGeneration:
    """Test OS service file generation."""

    def test_launchagent_valid_plist(self, tmp_path):
        target, content = generate_launchagent(tmp_path)
        assert _LAUNCHAGENT_LABEL in content
        assert "RunAtLoad" in content
        assert "KeepAlive" in content
        assert "ThrottleInterval" in content
        assert str(tmp_path.resolve()) in content
        assert target.name.endswith(".plist")

    def test_systemd_unit_valid(self, tmp_path):
        target, content = generate_systemd_unit(tmp_path)
        assert "[Unit]" in content
        assert "[Service]" in content
        assert "[Install]" in content
        assert "Restart=on-failure" in content
        assert str(tmp_path.resolve()) in content
        assert target.name == "hermes-agent.service"

    def test_windows_task_valid(self, tmp_path):
        bat_path, content = generate_windows_task(tmp_path)
        assert "@echo off" in content
        assert "daemon start" in content
        assert str(tmp_path.resolve()) in content
        assert bat_path.name == "hermes-agent.bat"

    def test_launchagent_has_log_paths(self, tmp_path):
        _, content = generate_launchagent(tmp_path)
        assert "agent-node.log" in content
        assert "agent-node.err" in content

    def test_systemd_user_scope(self, tmp_path):
        target, _ = generate_systemd_unit(tmp_path)
        assert ".config/systemd/user" in str(target)


# ---------------------------------------------------------------------------
# Hub Service Generation
# ---------------------------------------------------------------------------


class TestHubServiceGeneration:
    """Test hub + listener OS service file generation."""

    def test_generate_hub_service_macos(self, tmp_path, monkeypatch):
        monkeypatch.setattr("hermes.installer.detect_platform", lambda: Platform.MACOS)
        services = generate_hub_service(tmp_path)
        assert len(services) == 2

        # Hub server plist
        hub_target, hub_content = services[0]
        assert _HUB_LABEL in hub_content
        assert "hub" in hub_content
        assert "start" in hub_content
        assert "--foreground" in hub_content
        assert "RunAtLoad" in hub_content
        assert "KeepAlive" in hub_content
        assert "hub.log" in hub_content
        assert str(tmp_path.resolve()) in hub_content
        assert hub_target.name == f"{_HUB_LABEL}.plist"

        # Listener plist
        listen_target, listen_content = services[1]
        assert _HUB_LISTEN_LABEL in listen_content
        assert "listen" in listen_content
        assert "hub-listen.log" in listen_content
        assert listen_target.name == f"{_HUB_LISTEN_LABEL}.plist"

    def test_generate_hub_service_linux(self, tmp_path, monkeypatch):
        monkeypatch.setattr("hermes.installer.detect_platform", lambda: Platform.LINUX)
        services = generate_hub_service(tmp_path)
        assert len(services) == 2

        hub_target, hub_content = services[0]
        assert "[Unit]" in hub_content
        assert "[Service]" in hub_content
        assert "hub start --foreground" in hub_content
        assert hub_target.name == "hermes-hub.service"

        listen_target, listen_content = services[1]
        assert "hub listen" in listen_content
        assert listen_target.name == "hermes-hub-listen.service"

    def test_generate_hub_service_windows_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("hermes.installer.detect_platform", lambda: Platform.WINDOWS)
        services = generate_hub_service(tmp_path)
        assert len(services) == 0

    def test_install_hub_service_writes_plists(self, tmp_path, monkeypatch):
        monkeypatch.setattr("hermes.installer.detect_platform", lambda: Platform.MACOS)
        launch_dir = tmp_path / "Library" / "LaunchAgents"
        launch_dir.mkdir(parents=True)

        # Mock Path.home() to use tmp_path
        monkeypatch.setattr("hermes.installer.Path.home", lambda: tmp_path)

        # Mock subprocess to avoid actually loading services
        calls = []
        def mock_run(cmd, **kwargs):
            calls.append(cmd)
            return MagicMock(returncode=0)
        monkeypatch.setattr("hermes.installer.subprocess.run", mock_run)

        ok, msg = install_hub_service(tmp_path)
        assert ok is True
        assert "installed" in msg

        # Verify plists were written
        hub_plist = launch_dir / f"{_HUB_LABEL}.plist"
        listen_plist = launch_dir / f"{_HUB_LISTEN_LABEL}.plist"
        assert hub_plist.exists()
        assert listen_plist.exists()

        # Verify launchctl was called for both
        assert len(calls) == 2
        assert "load" in calls[0]
        assert "load" in calls[1]

    def test_uninstall_hub_service_removes_plists(self, tmp_path, monkeypatch):
        monkeypatch.setattr("hermes.installer.detect_platform", lambda: Platform.MACOS)
        monkeypatch.setattr("hermes.installer.Path.home", lambda: tmp_path)

        # Create fake plists
        launch_dir = tmp_path / "Library" / "LaunchAgents"
        launch_dir.mkdir(parents=True)
        (launch_dir / f"{_HUB_LABEL}.plist").write_text("<plist/>")
        (launch_dir / f"{_HUB_LISTEN_LABEL}.plist").write_text("<plist/>")

        calls = []
        def mock_run(cmd, **kwargs):
            calls.append(cmd)
            return MagicMock(returncode=0)
        monkeypatch.setattr("hermes.installer.subprocess.run", mock_run)

        ok, msg = uninstall_hub_service()
        assert ok is True
        assert "removed" in msg.lower()
        assert not (launch_dir / f"{_HUB_LABEL}.plist").exists()
        assert not (launch_dir / f"{_HUB_LISTEN_LABEL}.plist").exists()

    def test_uninstall_hub_service_no_plists(self, tmp_path, monkeypatch):
        monkeypatch.setattr("hermes.installer.detect_platform", lambda: Platform.MACOS)
        monkeypatch.setattr("hermes.installer.Path.home", lambda: tmp_path)

        ok, msg = uninstall_hub_service()
        assert ok is True
        assert "no hub services" in msg.lower()


# ---------------------------------------------------------------------------
# Hooks Installer
# ---------------------------------------------------------------------------


class TestHooksInstaller:
    """Test Claude Code hooks installation/uninstallation."""

    def test_fresh_install(self, tmp_path, monkeypatch):
        settings_file = tmp_path / "settings.json"
        monkeypatch.setattr("hermes.installer._settings_path", lambda: settings_file)

        modified, msg, hooks = install_hooks()
        assert modified is True
        assert "3 hooks" in msg
        assert "SessionStart" in hooks
        assert "UserPromptSubmit" in hooks
        assert "Stop" in hooks

        # Verify file written
        data = json.loads(settings_file.read_text())
        assert "hooks" in data

    def test_merge_existing_hooks(self, tmp_path, monkeypatch):
        settings_file = tmp_path / "settings.json"
        existing = {
            "hooks": {
                "SessionStart": [{"type": "command", "command": "echo hello", "timeout": 1000}]
            }
        }
        settings_file.write_text(json.dumps(existing))
        monkeypatch.setattr("hermes.installer._settings_path", lambda: settings_file)

        modified, msg, hooks = install_hooks()
        assert modified is True
        # Original hook preserved + hermes hook added
        assert len(hooks["SessionStart"]) == 2
        assert hooks["SessionStart"][0]["command"] == "echo hello"

    def test_idempotent(self, tmp_path, monkeypatch):
        settings_file = tmp_path / "settings.json"
        monkeypatch.setattr("hermes.installer._settings_path", lambda: settings_file)

        install_hooks()
        modified, msg, hooks = install_hooks()
        assert modified is False
        assert "already installed" in msg

    def test_uninstall_preserves_others(self, tmp_path, monkeypatch):
        settings_file = tmp_path / "settings.json"
        monkeypatch.setattr("hermes.installer._settings_path", lambda: settings_file)

        # Install hermes hooks + a custom hook
        install_hooks()
        data = json.loads(settings_file.read_text())
        data["hooks"]["SessionStart"].insert(
            0, {"type": "command", "command": "echo custom", "timeout": 1000}
        )
        settings_file.write_text(json.dumps(data))

        modified, msg = uninstall_hooks()
        assert modified is True

        result = json.loads(settings_file.read_text())
        # Custom hook preserved
        assert len(result["hooks"]["SessionStart"]) == 1
        assert result["hooks"]["SessionStart"][0]["command"] == "echo custom"

    def test_uninstall_no_settings(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "hermes.installer._settings_path", lambda: tmp_path / "nonexistent.json"
        )
        modified, msg = uninstall_hooks()
        assert modified is False

    def test_dry_run(self, tmp_path, monkeypatch):
        settings_file = tmp_path / "settings.json"
        monkeypatch.setattr("hermes.installer._settings_path", lambda: settings_file)

        modified, msg, hooks = install_hooks(dry_run=True)
        assert modified is True  # Would modify
        assert not settings_file.exists()  # But didn't write


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


class TestNotifications:
    """Test desktop notification dispatch."""

    def test_macos_notification(self, monkeypatch):
        mock_run = MagicMock()
        monkeypatch.setattr("hermes.installer.subprocess.run", mock_run)

        result = send_notification("Test", "Hello world", Platform.MACOS)
        assert result is True
        args = mock_run.call_args
        assert "osascript" in args[0][0][0]

    def test_linux_notification(self, monkeypatch):
        mock_run = MagicMock()
        monkeypatch.setattr("hermes.installer.subprocess.run", mock_run)

        result = send_notification("Test", "Hello world", Platform.LINUX)
        assert result is True
        args = mock_run.call_args
        assert args[0][0][0] == "notify-send"

    def test_failure_silent(self, monkeypatch):
        monkeypatch.setattr(
            "hermes.installer.subprocess.run",
            MagicMock(side_effect=Exception("no display")),
        )
        result = send_notification("Test", "Hello", Platform.LINUX)
        assert result is False

    def test_sanitizes_shell_chars(self, monkeypatch):
        mock_run = MagicMock()
        monkeypatch.setattr("hermes.installer.subprocess.run", mock_run)
        send_notification('Te"st', "He`llo\\world", Platform.MACOS)
        script_arg = mock_run.call_args[0][0][2]
        # User-injected double-quotes should be replaced with single quotes
        assert "Te'st" in script_arg
        # Backticks and backslashes should be stripped
        assert "`" not in script_arg
        assert "\\" not in script_arg


# ---------------------------------------------------------------------------
# Atomic Write + Sanitization
# ---------------------------------------------------------------------------


class TestAtomicWrite:
    """Test atomic JSON write and shell sanitization."""

    def test_atomic_write_creates_file(self, tmp_path):
        target = tmp_path / "test.json"
        _atomic_json_write(target, {"key": "value"})
        assert target.exists()
        assert json.loads(target.read_text()) == {"key": "value"}
        assert not (tmp_path / "test.tmp").exists()  # tmp cleaned up

    def test_atomic_write_replaces_existing(self, tmp_path):
        target = tmp_path / "test.json"
        target.write_text('{"old": true}')
        _atomic_json_write(target, {"new": True})
        assert json.loads(target.read_text()) == {"new": True}

    def test_sanitize_for_shell(self):
        assert _sanitize_for_shell('hello"world') == "hello'world"
        assert _sanitize_for_shell("back`tick") == "backtick"
        assert _sanitize_for_shell("back\\slash") == "backslash"
        assert _sanitize_for_shell("clean") == "clean"


# ---------------------------------------------------------------------------
# Run Install Orchestrator
# ---------------------------------------------------------------------------


class TestRunInstall:
    """Test the full install orchestration."""

    def test_full_install_skip_service(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr("hermes.installer.platform.system", lambda: "Darwin")
        monkeypatch.setattr("hermes.installer.platform.machine", lambda: "arm64")
        monkeypatch.setattr("hermes.installer.send_notification", lambda *a, **k: True)

        result = run_install(
            clan_id="test-clan",
            display_name="Test Clan",
            clan_dir=tmp_path,
            skip_hooks=True,
            skip_service=True,
        )

        assert result.success is True
        assert result.clan_dir == str(tmp_path)
        assert result.fingerprint  # Non-empty
        assert len(result.steps) >= 3
        assert len(result.errors) == 0

        # Verify files created
        assert (tmp_path / "gateway.json").exists()
        assert (tmp_path / ".keys").is_dir()

        output = capsys.readouterr().out
        assert "H E R M E S" in output

    def test_install_creates_agent_node_section(self, tmp_path, monkeypatch):
        monkeypatch.setattr("hermes.installer.platform.system", lambda: "Linux")
        monkeypatch.setattr("hermes.installer.platform.machine", lambda: "x86_64")
        monkeypatch.setattr("hermes.installer.send_notification", lambda *a, **k: True)

        run_install(
            clan_id="test",
            display_name="Test",
            clan_dir=tmp_path,
            skip_hooks=True,
            skip_service=True,
        )

        config = json.loads((tmp_path / "gateway.json").read_text())
        assert "agent_node" in config

    def test_install_idempotent(self, tmp_path, monkeypatch):
        monkeypatch.setattr("hermes.installer.platform.system", lambda: "Darwin")
        monkeypatch.setattr("hermes.installer.platform.machine", lambda: "arm64")
        monkeypatch.setattr("hermes.installer.send_notification", lambda *a, **k: True)

        # Run twice
        run_install("x", "X", tmp_path, skip_hooks=True, skip_service=True)
        result = run_install("x", "X", tmp_path, skip_hooks=True, skip_service=True)

        assert result.success is True
        assert result.fingerprint  # Still returns fingerprint

    def test_service_install_no_double_spawn(self, tmp_path, monkeypatch, capsys):
        """When service is installed, daemon should NOT be spawned separately."""
        monkeypatch.setattr("hermes.installer.platform.system", lambda: "Darwin")
        monkeypatch.setattr("hermes.installer.platform.machine", lambda: "arm64")
        monkeypatch.setattr("hermes.installer.send_notification", lambda *a, **k: True)
        monkeypatch.setattr(
            "hermes.installer.install_service",
            lambda p, d: (True, "LaunchAgent installed"),
        )

        result = run_install(
            clan_id="test",
            display_name="Test",
            clan_dir=tmp_path,
            skip_hooks=True,
            skip_service=False,  # Service IS installed
        )

        assert result.success is True
        # PID should be 0 — daemon started via service, not Popen
        assert result.pid == 0
        output = capsys.readouterr().out
        assert "via OS service" in output

    def test_install_with_gateway_url(self, tmp_path, monkeypatch):
        monkeypatch.setattr("hermes.installer.platform.system", lambda: "Darwin")
        monkeypatch.setattr("hermes.installer.platform.machine", lambda: "arm64")
        monkeypatch.setattr("hermes.installer.send_notification", lambda *a, **k: True)

        run_install(
            clan_id="test",
            display_name="Test",
            clan_dir=tmp_path,
            gateway_url="https://gw.example.com",
            skip_hooks=True,
            skip_service=True,
        )
        config = json.loads((tmp_path / "gateway.json").read_text())
        assert config["agora"]["url"] == "https://gw.example.com"


# ---------------------------------------------------------------------------
# Run Uninstall Orchestrator
# ---------------------------------------------------------------------------


class TestRunUninstall:
    """Test the uninstall orchestration."""

    def test_uninstall_purge(self, tmp_path, monkeypatch):
        monkeypatch.setattr("hermes.installer.platform.system", lambda: "Darwin")
        monkeypatch.setattr("hermes.installer.platform.machine", lambda: "arm64")
        monkeypatch.setattr("hermes.installer.send_notification", lambda *a, **k: True)

        # Use subdirectory to avoid deleting pytest's tmp_path root (causes OSError on cleanup)
        clan_dir = tmp_path / "test-clan"

        # Install first
        run_install("x", "X", clan_dir, skip_hooks=True, skip_service=True)
        assert (clan_dir / "gateway.json").exists()

        # Mock service uninstall (no real launchctl)
        monkeypatch.setattr(
            "hermes.installer.uninstall_service",
            lambda p: (True, "Service removed"),
        )
        monkeypatch.setattr("hermes.installer.shutil.which", lambda x: None)

        result = run_uninstall(clan_dir=clan_dir, purge=True, keep_hooks=True)
        assert result.success is True
        assert not clan_dir.exists()  # Purged

    def test_uninstall_preserve(self, tmp_path, monkeypatch):
        monkeypatch.setattr("hermes.installer.platform.system", lambda: "Linux")
        monkeypatch.setattr("hermes.installer.platform.machine", lambda: "x86_64")
        monkeypatch.setattr("hermes.installer.send_notification", lambda *a, **k: True)
        monkeypatch.setattr(
            "hermes.installer.uninstall_service",
            lambda p: (True, "Service removed"),
        )
        monkeypatch.setattr("hermes.installer.shutil.which", lambda x: None)

        run_install("x", "X", tmp_path, skip_hooks=True, skip_service=True)
        result = run_uninstall(clan_dir=tmp_path, purge=False, keep_hooks=True)

        assert result.success is True
        assert tmp_path.exists()  # Preserved


# ---------------------------------------------------------------------------
# Hook Commands
# ---------------------------------------------------------------------------


class TestHookCommands:
    """Test hook stdin/stdout JSON contract."""

    def test_pull_on_start_with_pending(self, tmp_path, monkeypatch):
        from hermes.hooks import cmd_hook_pull_on_start

        # Create clan dir with bus
        clan_dir = tmp_path / ".hermes"
        clan_dir.mkdir()
        (clan_dir / "gateway.json").write_text(
            json.dumps({"clan_id": "test", "display_name": "Test"})
        )
        (clan_dir / "bus.jsonl").write_text(
            json.dumps(
                {
                    "ts": "2026-03-18",
                    "src": "peer",
                    "dst": "test",
                    "type": "alert",
                    "msg": "Hello!",
                    "ttl": 7,
                    "ack": [],
                }
            )
            + "\n"
        )

        monkeypatch.setattr("hermes.hooks._default_clan_dir", lambda: clan_dir)

        stdin = io.StringIO("{}")
        stdout = io.StringIO()
        monkeypatch.setattr("sys.stdin", stdin)
        monkeypatch.setattr("sys.stdout", stdout)

        cmd_hook_pull_on_start()

        output = stdout.getvalue()
        assert output  # Should have output
        data = json.loads(output)
        assert "systemMessage" in data
        assert "1 pending" in data["systemMessage"]

    def test_pull_on_start_no_pending(self, tmp_path, monkeypatch):
        from hermes.hooks import cmd_hook_pull_on_start

        clan_dir = tmp_path / ".hermes"
        clan_dir.mkdir()
        (clan_dir / "gateway.json").write_text(
            json.dumps({"clan_id": "test", "display_name": "Test"})
        )
        (clan_dir / "bus.jsonl").write_text("")

        monkeypatch.setattr("hermes.hooks._default_clan_dir", lambda: clan_dir)
        monkeypatch.setattr("sys.stdin", io.StringIO("{}"))

        stdout = io.StringIO()
        monkeypatch.setattr("sys.stdout", stdout)

        cmd_hook_pull_on_start()
        assert stdout.getvalue() == ""  # No output for no pending

    def test_pull_on_prompt_ignores_non_hermes(self, tmp_path, monkeypatch):
        from hermes.hooks import cmd_hook_pull_on_prompt

        monkeypatch.setattr("hermes.hooks._default_clan_dir", lambda: tmp_path)
        monkeypatch.setattr("sys.stdin", io.StringIO('{"prompt": "hello world"}'))

        stdout = io.StringIO()
        monkeypatch.setattr("sys.stdout", stdout)

        cmd_hook_pull_on_prompt()
        assert stdout.getvalue() == ""  # Ignored non-/hermes prompt

    def test_exit_reminder_with_pending(self, tmp_path, monkeypatch):
        from hermes.hooks import cmd_hook_exit_reminder

        clan_dir = tmp_path / ".hermes"
        clan_dir.mkdir()
        (clan_dir / "gateway.json").write_text(
            json.dumps({"clan_id": "test", "display_name": "Test"})
        )
        (clan_dir / "bus.jsonl").write_text(
            json.dumps(
                {
                    "ts": "2026-03-18",
                    "src": "peer",
                    "dst": "*",
                    "type": "event",
                    "msg": "Something happened",
                    "ttl": 7,
                    "ack": [],
                }
            )
            + "\n"
        )

        monkeypatch.setattr("hermes.hooks._default_clan_dir", lambda: clan_dir)
        monkeypatch.setattr("sys.stdin", io.StringIO("{}"))

        stdout = io.StringIO()
        monkeypatch.setattr("sys.stdout", stdout)

        cmd_hook_exit_reminder()

        data = json.loads(stdout.getvalue())
        assert "reminder" in data["systemMessage"].lower()


# ---------------------------------------------------------------------------
# CLI Integration
# ---------------------------------------------------------------------------


class TestCLIIntegration:
    """Test CLI parser routing for new commands."""

    def test_install_parser(self):
        from hermes.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(
            [
                "install",
                "--clan-id",
                "test",
                "--display-name",
                "Test Clan",
                "--skip-hooks",
                "--skip-service",
            ]
        )
        assert args.command == "install"
        assert args.clan_id == "test"
        assert args.display_name == "Test Clan"
        assert args.skip_hooks is True
        assert args.skip_service is True

    def test_uninstall_parser(self):
        from hermes.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["uninstall", "--purge", "--keep-hooks"])
        assert args.command == "uninstall"
        assert args.purge is True
        assert args.keep_hooks is True

    def test_hook_parser(self):
        from hermes.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["hook", "pull-on-start"])
        assert args.command == "hook"
        assert args.hook_command == "pull-on-start"

    def test_install_full_flags(self):
        from hermes.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(
            [
                "install",
                "--clan-id",
                "jei",
                "--display-name",
                "Clan JEI",
                "--gateway-url",
                "https://gw.example.com",
                "--relay-url",
                "https://relay.example.com",
                "--dir",
                "/tmp/test",
            ]
        )
        assert args.clan_id == "jei"
        assert args.gateway_url == "https://gw.example.com"
        assert args.relay_url == "https://relay.example.com"
        assert args.dir == "/tmp/test"
