"""HERMES Hook Handlers — Claude Code integration hooks.

Cross-platform (no bash dependency). Invoked via `python -m hermes.hooks <cmd>`.

Hook types:
- pull_on_start: SessionStart — shows pending bus messages
- pull_on_prompt: UserPromptSubmit — activates on /hermes commands
- exit_reminder: Stop — reminds about unacked messages

Each hook reads JSON from stdin and writes JSON to stdout per the
Claude Code hooks contract.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _default_clan_dir() -> Path:
    """Return default clan dir (~/.hermes/)."""
    return Path.home() / ".hermes"


def _get_clan_id(clan_dir: Path) -> str:
    """Resolve clan_id from config."""
    try:
        gw = clan_dir / "gateway.json"
        if gw.exists():
            return json.loads(gw.read_text()).get("clan_id", "")
        toml = clan_dir / "config.toml"
        if toml.exists():
            import tomllib
            with open(toml, "rb") as f:
                return tomllib.load(f).get("clan", {}).get("id", "")
    except Exception:
        pass
    return ""


def _write_dojo_event(clan_dir: Path, namespace: str, msg: str) -> None:
    """Write a dojo_event to the bus (best-effort, never blocks)."""
    try:
        from datetime import date
        bus_path = clan_dir / "bus.jsonl"
        event = {
            "ts": str(date.today()),
            "src": namespace,
            "dst": "*",
            "type": "dojo_event",
            "msg": msg[:120],
            "ttl": 1,
            "ack": [namespace],  # Self-ACK: dojo_events don't need human attention
        }
        with open(bus_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except Exception:
        pass


def _read_bus_pending(clan_dir: Path) -> list[dict]:
    """Read pending bus messages for this clan."""
    bus_path = clan_dir / "bus.jsonl"
    if not bus_path.exists():
        return []

    # Resolve clan_id from TOML or JSON config
    namespace = ""
    toml_path = clan_dir / "config.toml"
    json_path = clan_dir / "gateway.json"

    try:
        if toml_path.exists():
            import tomllib

            with open(toml_path, "rb") as f:
                data = tomllib.load(f)
            namespace = data.get("clan", {}).get("id", "")
        elif json_path.exists():
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            namespace = data.get("clan_id", "")
        else:
            return []

        messages = []
        with open(bus_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    ack = msg.get("ack", [])
                    dst = msg.get("dst", "")
                    if namespace not in ack and (dst == "*" or dst == namespace):
                        messages.append(msg)
                except json.JSONDecodeError:
                    continue

        return messages
    except Exception:
        return []


def cmd_hook_pull_on_start() -> None:
    """SessionStart hook: read bus, show pending messages as systemMessage.

    Reads hook input from stdin, writes hook output to stdout.
    """
    # Read stdin (hook input — consumed but not used for this hook)
    try:
        json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        pass

    clan_dir = _default_clan_dir()
    pending = _read_bus_pending(clan_dir)

    if not pending:
        # No output needed — hook passes through
        return

    # Build system message with pending count
    count = len(pending)
    summary_lines = []
    for msg in pending[:5]:  # Show at most 5
        src = msg.get("src", "?")
        mtype = msg.get("type", "?")
        text = msg.get("msg", "")[:80]
        summary_lines.append(f"  [{mtype}] from {src}: {text}")

    if count > 5:
        summary_lines.append(f"  ... and {count - 5} more")

    summary = "\n".join(summary_lines)
    system_msg = (
        f"HERMES: {count} pending message(s) on the bus:\n{summary}\n"
        f"Use 'hermes bus --pending' to see all."
    )

    output = {"systemMessage": system_msg}
    json.dump(output, sys.stdout)
    sys.stdout.write("\n")
    sys.stdout.flush()


def cmd_hook_dojo_register() -> None:
    """SessionStart hook: register Claude Code as active Dojo skill.

    Writes SKILL_ONLINE dojo_event to bus so the daemon knows this
    session is available for quest dispatch.
    """
    try:
        json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        pass

    clan_dir = _default_clan_dir()
    namespace = _get_clan_id(clan_dir)
    if namespace:
        import os
        cwd = os.environ.get("HERMES_CWD", os.getcwd())
        dim = Path(cwd).name if cwd else "unknown"
        _write_dojo_event(
            clan_dir,
            namespace,
            f"SKILL_ONLINE:claude-code:dim={dim}:caps=eng.software,creative.writing",
        )


def cmd_hook_pull_on_prompt() -> None:
    """UserPromptSubmit hook: activate only on /hermes commands.

    If the user prompt starts with /hermes, refresh bus state.
    Otherwise, pass through silently.
    """
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        hook_input = {}

    prompt = hook_input.get("prompt", "")
    if not prompt.strip().startswith("/hermes"):
        return

    clan_dir = _default_clan_dir()
    pending = _read_bus_pending(clan_dir)

    if pending:
        output = {"systemMessage": f"HERMES bus: {len(pending)} pending message(s)."}
        json.dump(output, sys.stdout)
        sys.stdout.write("\n")
        sys.stdout.flush()


def cmd_hook_hub_inject() -> None:
    """UserPromptSubmit hook: inject pending hub messages into conversation.

    Reads ~/.hermes/hub-inbox.jsonl from cursor position, injects new
    messages as systemMessage. Updates cursor after reading.
    Runs on EVERY prompt — no prefix required. Fast (file read only).
    """
    try:
        json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        pass

    clan_dir = _default_clan_dir()
    inbox_path = clan_dir / "hub-inbox.jsonl"
    cursor_path = clan_dir / "hub-inbox.cursor"

    if not inbox_path.exists():
        return

    # Read cursor (byte offset)
    cursor = 0
    if cursor_path.exists():
        try:
            cursor = int(cursor_path.read_text().strip())
        except (ValueError, OSError):
            cursor = 0

    # Read new lines from cursor
    try:
        file_size = inbox_path.stat().st_size
        if file_size < cursor:
            # File was truncated/cleaned — reset cursor
            cursor = 0
        if file_size <= cursor:
            return  # No new data

        new_messages = []
        with open(inbox_path, encoding="utf-8") as f:
            f.seek(cursor)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    if msg.get("type") != "presence":
                        new_messages.append(msg)
                except json.JSONDecodeError:
                    continue
            new_cursor = f.tell()

        if not new_messages:
            # Update cursor even if only presence events
            cursor_path.write_text(str(new_cursor))
            return

        # Format messages
        lines = []
        for msg in new_messages[-5:]:  # Last 5 max
            src = msg.get("from", msg.get("src", "?"))
            text = msg.get("msg", msg.get("text", ""))
            lines.append(f"  [{src}] {text}")

        if len(new_messages) > 5:
            lines.insert(0, f"  ({len(new_messages) - 5} earlier messages omitted)")

        summary = "\n".join(lines)
        system_msg = f"[HUB] {len(new_messages)} new message(s) from peers:\n{summary}"

        output = {"systemMessage": system_msg}
        json.dump(output, sys.stdout)
        sys.stdout.write("\n")
        sys.stdout.flush()

        # Update cursor
        cursor_path.write_text(str(new_cursor))

    except Exception:
        pass  # Never block the prompt


def cmd_hook_exit_reminder() -> None:
    """Stop hook: count unacked messages, remind user. Write SKILL_OFFLINE.

    Best-effort — never blocks session exit.
    """
    try:
        json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        pass

    clan_dir = _default_clan_dir()

    # Dojo: mark session offline
    namespace = _get_clan_id(clan_dir)
    if namespace:
        _write_dojo_event(clan_dir, namespace, "SKILL_OFFLINE:claude-code")

    pending = _read_bus_pending(clan_dir)

    if pending:
        output = {
            "systemMessage": (
                f"HERMES reminder: {len(pending)} unacked message(s) on the bus. "
                f"Consider running 'hermes bus --pending' before leaving."
            )
        }
        json.dump(output, sys.stdout)
        sys.stdout.write("\n")
        sys.stdout.flush()


def main() -> None:
    """Entry point for python -m hermes.hooks <command>."""
    if len(sys.argv) < 2:
        print(
            "Usage: python -m hermes.hooks <pull_on_start|pull_on_prompt|exit_reminder>",
            file=sys.stderr,
        )
        sys.exit(1)

    commands = {
        "pull_on_start": cmd_hook_pull_on_start,
        "pull_on_prompt": cmd_hook_pull_on_prompt,
        "hub_inject": cmd_hook_hub_inject,
        "exit_reminder": cmd_hook_exit_reminder,
        "dojo_register": cmd_hook_dojo_register,
    }

    cmd = sys.argv[1]
    if cmd not in commands:
        print(f"Unknown hook command: {cmd}", file=sys.stderr)
        sys.exit(1)

    commands[cmd]()


if __name__ == "__main__":
    main()
