"""HERMES Installer — Cross-platform one-command setup.

Orchestrates: clan init, keypair generation, OS service installation,
Claude Code hooks, and desktop notifications. Supports macOS, Linux, Windows.

Usage:
    hermes install --clan-id <id> --display-name <name>
    hermes uninstall [--purge] [--keep-hooks]
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Platform(Enum):
    """Supported operating systems."""

    MACOS = "macos"
    LINUX = "linux"
    WINDOWS = "windows"


@dataclass
class InstallResult:
    """Result of an install/uninstall operation."""

    success: bool
    steps: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    clan_dir: str = ""
    fingerprint: str = ""
    pid: int = 0


def detect_platform() -> Platform:
    """Detect the current OS platform."""
    system = platform.system().lower()
    if system == "darwin":
        return Platform.MACOS
    elif system == "linux":
        return Platform.LINUX
    elif system == "windows":
        return Platform.WINDOWS
    else:
        raise RuntimeError(f"Unsupported platform: {system}")


def default_clan_dir(plat: Platform) -> Path:
    """Return the default clan directory for the platform."""
    if plat == Platform.WINDOWS:
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        return Path(appdata) / "hermes"
    return Path.home() / ".hermes"


def hermes_executable_path() -> str:
    """Find the hermes executable or fall back to python -m."""
    exe = shutil.which("hermes")
    if exe:
        return exe
    return f"{sys.executable} -m hermes.cli"


def init_clan_if_needed(
    clan_dir: Path, clan_id: str, display_name: str,
    agora_url: str = "",
) -> tuple[bool, str]:
    """Initialize clan directory if it doesn't already exist.

    Returns (created: bool, message: str).
    """
    if (clan_dir / "config.toml").exists() or (clan_dir / "gateway.json").exists():
        return False, f"Clan already initialized at {clan_dir}"

    from .config import init_clan

    init_clan(
        clan_dir=clan_dir,
        clan_id=clan_id,
        display_name=display_name,
        agora_url=agora_url,
    )
    return True, f"Clan initialized at {clan_dir}"


def generate_keypair(clan_dir: Path, clan_id: str) -> tuple[bool, str, str]:
    """Generate Ed25519 + X25519 keypair if not already present.

    Returns (created: bool, message: str, fingerprint: str).
    """
    keys_dir = clan_dir / ".keys"
    key_file = keys_dir / f"{clan_id}.key"

    if key_file.exists():
        from .crypto import ClanKeyPair

        kp = ClanKeyPair.load(str(keys_dir), clan_id)
        fp = kp.fingerprint()
        return False, f"Keys already exist ({fp[:9]}...)", fp

    from .crypto import ClanKeyPair

    kp = ClanKeyPair.generate()
    kp.save(str(keys_dir), clan_id)
    fp = kp.fingerprint()
    return True, f"Ed25519 + X25519 keys generated", fp


def add_agent_node_section(clan_dir: Path) -> tuple[bool, str]:
    """Add daemon/agent_node block to config if missing.

    Supports both config.toml ([daemon] section) and gateway.json (agent_node).
    Returns (modified: bool, message: str).
    """
    import tomllib

    toml_path = clan_dir / "config.toml"
    json_path = clan_dir / "gateway.json"

    # Prefer TOML
    if toml_path.exists():
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)

        if "daemon" in data:
            return False, "daemon section already present in config.toml"

        import tomli_w
        data["daemon"] = {
            "enabled": True,
            "namespace": data.get("clan", {}).get("id", "heraldo"),
            "poll_interval": 2.0,
            "forward_types": ["alert", "dispatch", "event"],
        }

        from .config import _atomic_write
        _atomic_write(toml_path, tomli_w.dumps(data))
        return True, "daemon section added to config.toml"

    if not json_path.exists():
        return False, "No config found"

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "agent_node" in data:
        return False, "agent_node section already present"

    data["agent_node"] = {
        "enabled": True,
        "bus_path": "bus.jsonl",
        "namespace": data.get("clan_id", "heraldo"),
        "poll_interval": 2.0,
        "forward_types": ["alert", "dispatch", "event"],
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return True, "agent_node section added to gateway.json"


# ---------------------------------------------------------------------------
# Service generators
# ---------------------------------------------------------------------------

_LAUNCHAGENT_LABEL = "com.hermes.agent-node"


def generate_launchagent(clan_dir: str | Path) -> tuple[Path, str]:
    """Generate a macOS LaunchAgent plist for the agent node daemon.

    Returns (target_path, plist_content).
    """
    clan_dir = str(Path(clan_dir).resolve())
    hermes_exe = hermes_executable_path()

    # Split compound commands (e.g. "python -m hermes.cli")
    parts = hermes_exe.split()
    program_args = "".join(
        f"    <string>{p}</string>\n" for p in parts
    )
    program_args += (
        f"    <string>daemon</string>\n"
        f"    <string>start</string>\n"
        f"    <string>--foreground</string>\n"
        f"    <string>--dir</string>\n"
        f"    <string>{clan_dir}</string>\n"
    )

    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{_LAUNCHAGENT_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
{program_args.rstrip()}
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>10</integer>
  <key>StandardOutPath</key>
  <string>{clan_dir}/agent-node.log</string>
  <key>StandardErrorPath</key>
  <string>{clan_dir}/agent-node.err</string>
</dict>
</plist>
"""
    target = Path.home() / "Library" / "LaunchAgents" / f"{_LAUNCHAGENT_LABEL}.plist"
    return target, plist


def generate_systemd_unit(clan_dir: str | Path) -> tuple[Path, str]:
    """Generate a systemd user unit for the agent node daemon.

    Returns (target_path, unit_content).
    """
    clan_dir = str(Path(clan_dir).resolve())
    hermes_exe = hermes_executable_path()

    unit = f"""[Unit]
Description=HERMES Agent Node
After=network.target

[Service]
Type=simple
ExecStart={hermes_exe} daemon start --foreground --dir {clan_dir}
Restart=on-failure
RestartSec=10
WorkingDirectory={clan_dir}

[Install]
WantedBy=default.target
"""
    config_dir = Path.home() / ".config" / "systemd" / "user"
    target = config_dir / "hermes-agent.service"
    return target, unit


def generate_windows_task(clan_dir: str | Path) -> tuple[Path, str]:
    """Generate a Windows batch file + schtasks command.

    Returns (bat_path, bat_content).
    """
    clan_dir = str(Path(clan_dir).resolve())
    hermes_exe = hermes_executable_path()

    bat = f"""@echo off
REM HERMES Agent Node — auto-start
cd /d "{clan_dir}"
{hermes_exe} daemon start --foreground --dir "{clan_dir}"
"""
    bat_path = Path(clan_dir) / "hermes-agent.bat"
    return bat_path, bat


# ---------------------------------------------------------------------------
# Service install / uninstall
# ---------------------------------------------------------------------------

def install_service(plat: Platform, clan_dir: Path) -> tuple[bool, str]:
    """Write service file and load/enable the service.

    Returns (success: bool, message: str).
    """
    try:
        if plat == Platform.MACOS:
            target, content = generate_launchagent(clan_dir)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            subprocess.run(
                ["launchctl", "load", "-w", str(target)],
                capture_output=True, check=True,
            )
            return True, "LaunchAgent installed (survives reboot)"

        elif plat == Platform.LINUX:
            target, content = generate_systemd_unit(clan_dir)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            subprocess.run(
                ["systemctl", "--user", "enable", "--now", "hermes-agent"],
                capture_output=True, check=True,
            )
            return True, "systemd user service enabled"

        elif plat == Platform.WINDOWS:
            bat_path, bat_content = generate_windows_task(clan_dir)
            bat_path.write_text(bat_content)
            task_name = "HermesAgentNode"
            subprocess.run(
                [
                    "schtasks", "/Create", "/TN", task_name,
                    "/TR", str(bat_path),
                    "/SC", "ONLOGON", "/F",
                ],
                capture_output=True, check=True,
            )
            return True, "Windows scheduled task created"

    except subprocess.CalledProcessError as e:
        return False, f"Service install failed: {e}"
    except Exception as e:
        return False, f"Service install error: {e}"

    return False, "Unknown platform"


def uninstall_service(plat: Platform) -> tuple[bool, str]:
    """Unload and remove the OS service.

    Returns (success: bool, message: str).
    """
    try:
        if plat == Platform.MACOS:
            target = (
                Path.home() / "Library" / "LaunchAgents"
                / f"{_LAUNCHAGENT_LABEL}.plist"
            )
            if target.exists():
                subprocess.run(
                    ["launchctl", "unload", str(target)],
                    capture_output=True,
                )
                target.unlink()
            return True, "LaunchAgent removed"

        elif plat == Platform.LINUX:
            subprocess.run(
                ["systemctl", "--user", "disable", "--now", "hermes-agent"],
                capture_output=True,
            )
            target = (
                Path.home() / ".config" / "systemd" / "user"
                / "hermes-agent.service"
            )
            if target.exists():
                target.unlink()
            return True, "systemd service removed"

        elif plat == Platform.WINDOWS:
            subprocess.run(
                ["schtasks", "/Delete", "/TN", "HermesAgentNode", "/F"],
                capture_output=True,
            )
            return True, "Windows scheduled task removed"

    except Exception as e:
        return False, f"Service uninstall error: {e}"

    return False, "Unknown platform"


# ---------------------------------------------------------------------------
# Claude Code hooks
# ---------------------------------------------------------------------------

_HERMES_HOOKS_MARKER = "hermes-protocol"

_HERMES_HOOKS: dict[str, list[dict[str, Any]]] = {
    "SessionStart": [
        {
            "type": "command",
            "command": f"{sys.executable} -m hermes.hooks pull_on_start",
            "timeout": 5000,
            "_hermes": _HERMES_HOOKS_MARKER,
        }
    ],
    "UserPromptSubmit": [
        {
            "type": "command",
            "command": f"{sys.executable} -m hermes.hooks pull_on_prompt",
            "timeout": 3000,
            "_hermes": _HERMES_HOOKS_MARKER,
        }
    ],
    "Stop": [
        {
            "type": "command",
            "command": f"{sys.executable} -m hermes.hooks exit_reminder",
            "timeout": 3000,
            "_hermes": _HERMES_HOOKS_MARKER,
        }
    ],
}


def _atomic_json_write(path: Path, data: dict) -> None:
    """Write JSON to file atomically (write-tmp-then-rename)."""
    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    tmp_path.replace(path)


def _sanitize_for_shell(text: str) -> str:
    """Remove characters that could break shell/osascript strings."""
    return text.replace('"', "'").replace("\\", "").replace("`", "")


def _settings_path() -> Path:
    """Return the path to Claude Code settings.json."""
    return Path.home() / ".claude" / "settings.json"


def install_hooks(dry_run: bool = False) -> tuple[bool, str, dict[str, Any]]:
    """Safely merge HERMES hooks into Claude Code settings.json.

    Never overwrites existing hooks. Returns (modified, message, resulting_hooks).
    """
    settings_file = _settings_path()
    settings: dict[str, Any] = {}

    if settings_file.exists():
        with open(settings_file, "r", encoding="utf-8") as f:
            settings = json.load(f)

    hooks = settings.get("hooks", {})
    modified = False

    for event, hermes_hooks in _HERMES_HOOKS.items():
        existing = hooks.get(event, [])

        # Check if hermes hooks already installed (by marker)
        has_hermes = any(
            h.get("_hermes") == _HERMES_HOOKS_MARKER
            for h in existing
            if isinstance(h, dict)
        )
        if has_hermes:
            continue

        existing.extend(hermes_hooks)
        hooks[event] = existing
        modified = True

    if modified and not dry_run:
        settings["hooks"] = hooks
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        _atomic_json_write(settings_file, settings)

    msg = "Claude Code hooks installed (3 hooks)" if modified else "Hooks already installed"
    return modified, msg, hooks


def uninstall_hooks() -> tuple[bool, str]:
    """Remove only HERMES hooks from Claude Code settings.json.

    Preserves all other hooks. Returns (modified, message).
    """
    settings_file = _settings_path()
    if not settings_file.exists():
        return False, "No settings.json found"

    with open(settings_file, "r", encoding="utf-8") as f:
        settings = json.load(f)

    hooks = settings.get("hooks", {})
    modified = False

    for event in list(hooks.keys()):
        original = hooks[event]
        filtered = [
            h for h in original
            if not (isinstance(h, dict) and h.get("_hermes") == _HERMES_HOOKS_MARKER)
        ]
        if len(filtered) != len(original):
            modified = True
            if filtered:
                hooks[event] = filtered
            else:
                del hooks[event]

    if modified:
        settings["hooks"] = hooks
        _atomic_json_write(settings_file, settings)

    return modified, "HERMES hooks removed" if modified else "No HERMES hooks found"


# ---------------------------------------------------------------------------
# Desktop notifications
# ---------------------------------------------------------------------------

def send_notification(title: str, msg: str, plat: Platform | None = None) -> bool:
    """Send a desktop notification. Best-effort — never raises.

    Returns True if the notification command succeeded.
    """
    if plat is None:
        try:
            plat = detect_platform()
        except RuntimeError:
            return False

    try:
        if plat == Platform.MACOS:
            safe_title = _sanitize_for_shell(title)
            safe_msg = _sanitize_for_shell(msg)
            script = (
                f'display notification "{safe_msg}" with title "{safe_title}"'
                f' sound name "Glass"'
            )
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, timeout=5,
            )
            return True

        elif plat == Platform.LINUX:
            subprocess.run(
                ["notify-send", title, msg],
                capture_output=True, timeout=5,
            )
            return True

        elif plat == Platform.WINDOWS:
            ps_cmd = (
                f"[Windows.UI.Notifications.ToastNotificationManager,"
                f"Windows.UI.Notifications,ContentType=WindowsRuntime];"
                f'$xml = "<toast><visual><binding template=\\"ToastText02\\">'
                f"<text id=\\\"1\\\">{title}</text>"
                f"<text id=\\\"2\\\">{msg}</text>"
                f"</binding></visual></toast>\";"
                f"$t = [Windows.Data.Xml.Dom.XmlDocument,Windows.Data.Xml.Dom.XmlDocument,"
                f"ContentType=WindowsRuntime]::new();"
                f"$t.LoadXml($xml);"
                f"[Windows.UI.Notifications.ToastNotificationManager]"
                f"::CreateToastNotifier('HERMES').Show("
                f"[Windows.UI.Notifications.ToastNotification]::new($t))"
            )
            subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True, timeout=10,
            )
            return True

    except Exception:
        pass

    return False


# ---------------------------------------------------------------------------
# Orchestrators
# ---------------------------------------------------------------------------

def _print_banner() -> None:
    """Print the HERMES install banner."""
    print()
    print("  ╔══════════════════════════════════════╗")
    print("  ║  H E R M E S   I N S T A L L        ║")
    print("  ╚══════════════════════════════════════╝")


def _print_step(ok: bool, msg: str) -> None:
    """Print an install step result."""
    marker = "[OK]" if ok else "[!!]"
    print(f"  {marker} {msg}")


def run_install(
    clan_id: str,
    display_name: str,
    clan_dir: Path | None = None,
    gateway_url: str = "",
    relay_url: str = "",
    skip_hooks: bool = False,
    skip_service: bool = False,
) -> InstallResult:
    """Full install sequence: detect -> init -> keys -> service -> hooks -> notify.

    Returns an InstallResult with all steps and any errors.
    """
    result = InstallResult(success=True)

    # 1. Platform detection
    plat = detect_platform()
    arch = platform.machine()
    if clan_dir is None:
        clan_dir = default_clan_dir(plat)

    result.clan_dir = str(clan_dir)

    _print_banner()
    print(f"  Platform: {plat.value} ({arch})")
    print(f"  Clan dir: {clan_dir}")
    print()

    # 2. Init clan
    created, msg = init_clan_if_needed(
        clan_dir, clan_id, display_name, agora_url=gateway_url,
    )
    _print_step(True, msg)
    result.steps.append(msg)

    # 3. Generate keypair
    try:
        created_keys, msg, fp = generate_keypair(clan_dir, clan_id)
        _print_step(True, msg)
        if created_keys:
            print(f"       Fingerprint: {fp}")
        result.fingerprint = fp
        result.steps.append(msg)
    except Exception as e:
        msg = f"Keypair generation failed: {e}"
        _print_step(False, msg)
        result.errors.append(msg)

    # 4. Add daemon/agent_node section to config
    modified, msg = add_agent_node_section(clan_dir)
    if modified:
        _print_step(True, msg)
        result.steps.append(msg)

    # 5. Install OS service
    if not skip_service:
        ok, msg = install_service(plat, clan_dir)
        _print_step(ok, msg)
        result.steps.append(msg)
        if not ok:
            result.errors.append(msg)
    else:
        _print_step(True, "Service installation skipped (--skip-service)")
        result.steps.append("Service skipped")

    # 6. Install Claude Code hooks
    if not skip_hooks:
        modified_hooks, msg, _ = install_hooks()
        _print_step(True, msg)
        result.steps.append(msg)
    else:
        _print_step(True, "Hooks installation skipped (--skip-hooks)")
        result.steps.append("Hooks skipped")

    # 7. Start daemon — only if service was NOT installed (service already starts it)
    if skip_service:
        try:
            hermes_exe = hermes_executable_path()
            proc = subprocess.Popen(
                [*hermes_exe.split(), "daemon", "start", "--dir", str(clan_dir)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            result.pid = proc.pid
            _print_step(True, f"Agent Node started (PID {proc.pid})")
            result.steps.append(f"Daemon started PID={proc.pid}")
        except Exception as e:
            msg = f"Daemon start failed: {e}"
            _print_step(False, msg)
            result.errors.append(msg)
    elif not skip_service:
        _print_step(True, "Agent Node started via OS service")
        result.steps.append("Daemon started via service")

    # 8. Notification
    send_notification(
        "HERMES",
        f"Agent Node running. You're connected as {clan_id}!",
        plat,
    )

    print()
    if result.errors:
        print(f"  Completed with {len(result.errors)} warning(s).")
        result.success = False
    else:
        print("  You're connected! Run 'hermes status' to check.")
        print("  Share your public key fingerprint with peers to start exchanging.")

    print()
    return result


def run_uninstall(
    clan_dir: Path | None = None,
    purge: bool = False,
    keep_hooks: bool = False,
) -> InstallResult:
    """Reverse install: stop -> unservice -> unhooks -> optionally purge.

    Returns an InstallResult with all steps and any errors.
    """
    result = InstallResult(success=True)
    plat = detect_platform()

    if clan_dir is None:
        clan_dir = default_clan_dir(plat)

    result.clan_dir = str(clan_dir)

    print()
    print("  HERMES Uninstall")
    print()

    # 1. Stop daemon
    try:
        hermes_exe = hermes_executable_path()
        parts = hermes_exe.split()
        subprocess.run(
            [*parts, "daemon", "stop", "--dir", str(clan_dir)],
            capture_output=True, timeout=10,
        )
        _print_step(True, "Agent Node stopped")
        result.steps.append("Daemon stopped")
    except Exception:
        _print_step(True, "Agent Node not running")
        result.steps.append("Daemon was not running")

    # 2. Remove OS service
    ok, msg = uninstall_service(plat)
    _print_step(ok, msg)
    result.steps.append(msg)

    # 3. Remove hooks
    if not keep_hooks:
        modified, msg = uninstall_hooks()
        _print_step(True, msg)
        result.steps.append(msg)
    else:
        _print_step(True, "Hooks preserved (--keep-hooks)")
        result.steps.append("Hooks kept")

    # 4. Purge clan directory
    if purge:
        if clan_dir.exists():
            shutil.rmtree(clan_dir)
            _print_step(True, f"Clan directory purged: {clan_dir}")
            result.steps.append(f"Purged {clan_dir}")
        else:
            _print_step(True, "Clan directory not found (already clean)")
    else:
        _print_step(True, f"Clan directory preserved at {clan_dir}")

    print()
    return result
