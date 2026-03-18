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


def _read_bus_pending(clan_dir: Path) -> list[dict]:
    """Read pending bus messages for this clan."""
    config_path = clan_dir / "gateway.json"
    bus_path = clan_dir / "bus.jsonl"

    if not config_path.exists() or not bus_path.exists():
        return []

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        namespace = config.get("clan_id", "")

        messages = []
        with open(bus_path, "r", encoding="utf-8") as f:
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
    # Read stdin (hook input)
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        hook_input = {}

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
        output = {
            "systemMessage": f"HERMES bus: {len(pending)} pending message(s)."
        }
        json.dump(output, sys.stdout)
        sys.stdout.write("\n")
        sys.stdout.flush()


def cmd_hook_exit_reminder() -> None:
    """Stop hook: count unacked messages, remind user.

    Best-effort — never blocks session exit.
    """
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        hook_input = {}

    clan_dir = _default_clan_dir()
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
        print("Usage: python -m hermes.hooks <pull_on_start|pull_on_prompt|exit_reminder>",
              file=sys.stderr)
        sys.exit(1)

    commands = {
        "pull_on_start": cmd_hook_pull_on_start,
        "pull_on_prompt": cmd_hook_pull_on_prompt,
        "exit_reminder": cmd_hook_exit_reminder,
    }

    cmd = sys.argv[1]
    if cmd not in commands:
        print(f"Unknown hook command: {cmd}", file=sys.stderr)
        sys.exit(1)

    commands[cmd]()


if __name__ == "__main__":
    main()
