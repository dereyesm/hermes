"""Tests for HERMES Hook Handlers (hooks.py).

Covers:
- _read_bus_pending: bus parsing, config discovery (TOML/JSON), filtering
- cmd_hook_pull_on_start: SessionStart hook stdout output
- cmd_hook_pull_on_prompt: UserPromptSubmit hook /hermes activation
- cmd_hook_exit_reminder: Stop hook unacked reminder
- main: CLI entry point dispatch
"""

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from hermes.hooks import (
    _read_bus_pending,
    cmd_hook_exit_reminder,
    cmd_hook_pull_on_prompt,
    cmd_hook_pull_on_start,
    main,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def clan_dir_json(tmp_path):
    """Clan dir with gateway.json config and a bus file."""
    config = {"clan_id": "momoshod"}
    (tmp_path / "gateway.json").write_text(json.dumps(config))
    return tmp_path


@pytest.fixture
def clan_dir_toml(tmp_path):
    """Clan dir with config.toml."""
    toml_content = '[clan]\nid = "momoshod"\n'
    (tmp_path / "config.toml").write_text(toml_content)
    return tmp_path


def _write_bus(clan_dir: Path, messages: list[dict]) -> None:
    """Helper to write bus.jsonl."""
    lines = [json.dumps(m) for m in messages]
    (clan_dir / "bus.jsonl").write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# _read_bus_pending tests
# ---------------------------------------------------------------------------


class TestReadBusPending:
    """Tests for _read_bus_pending()."""

    def test_no_bus_file(self, clan_dir_json):
        """Returns empty list when bus.jsonl doesn't exist."""
        result = _read_bus_pending(clan_dir_json)
        assert result == []

    def test_no_config(self, tmp_path):
        """Returns empty list when no config file exists."""
        (tmp_path / "bus.jsonl").write_text('{"src":"a","dst":"*","ack":[]}\n')
        result = _read_bus_pending(tmp_path)
        assert result == []

    def test_empty_bus(self, clan_dir_json):
        """Returns empty list for empty bus file."""
        (clan_dir_json / "bus.jsonl").write_text("")
        result = _read_bus_pending(clan_dir_json)
        assert result == []

    def test_pending_broadcast_json_config(self, clan_dir_json):
        """Finds pending broadcast messages (dst=*) with JSON config."""
        _write_bus(
            clan_dir_json,
            [
                {"src": "nymyka", "dst": "*", "type": "state", "msg": "hello", "ack": []},
            ],
        )
        result = _read_bus_pending(clan_dir_json)
        assert len(result) == 1
        assert result[0]["src"] == "nymyka"

    def test_pending_direct_message(self, clan_dir_json):
        """Finds pending direct messages (dst=momoshod)."""
        _write_bus(
            clan_dir_json,
            [
                {"src": "jei", "dst": "momoshod", "type": "event", "msg": "ping", "ack": []},
            ],
        )
        result = _read_bus_pending(clan_dir_json)
        assert len(result) == 1

    def test_already_acked(self, clan_dir_json):
        """Excludes messages already acknowledged by this clan."""
        _write_bus(
            clan_dir_json,
            [
                {"src": "jei", "dst": "*", "type": "state", "msg": "done", "ack": ["momoshod"]},
            ],
        )
        result = _read_bus_pending(clan_dir_json)
        assert result == []

    def test_different_dst_excluded(self, clan_dir_json):
        """Excludes messages addressed to a different clan."""
        _write_bus(
            clan_dir_json,
            [
                {"src": "jei", "dst": "nymyka", "type": "state", "msg": "private", "ack": []},
            ],
        )
        result = _read_bus_pending(clan_dir_json)
        assert result == []

    def test_toml_config(self, clan_dir_toml):
        """Works with TOML config format."""
        _write_bus(
            clan_dir_toml,
            [
                {"src": "jei", "dst": "*", "type": "state", "msg": "hello", "ack": []},
            ],
        )
        result = _read_bus_pending(clan_dir_toml)
        assert len(result) == 1

    def test_mixed_messages(self, clan_dir_json):
        """Correctly filters a mix of pending, acked, and other-dst messages."""
        _write_bus(
            clan_dir_json,
            [
                {"src": "a", "dst": "*", "type": "state", "msg": "1", "ack": []},
                {"src": "b", "dst": "*", "type": "state", "msg": "2", "ack": ["momoshod"]},
                {"src": "c", "dst": "momoshod", "type": "event", "msg": "3", "ack": []},
                {"src": "d", "dst": "nymyka", "type": "state", "msg": "4", "ack": []},
            ],
        )
        result = _read_bus_pending(clan_dir_json)
        assert len(result) == 2
        sources = {m["src"] for m in result}
        assert sources == {"a", "c"}

    def test_malformed_json_lines_skipped(self, clan_dir_json):
        """Gracefully skips malformed JSON lines."""
        bus_content = '{"src":"a","dst":"*","type":"state","msg":"ok","ack":[]}\n'
        bus_content += "this is not json\n"
        bus_content += '{"src":"b","dst":"*","type":"state","msg":"ok2","ack":[]}\n'
        (clan_dir_json / "bus.jsonl").write_text(bus_content)
        result = _read_bus_pending(clan_dir_json)
        assert len(result) == 2

    def test_blank_lines_skipped(self, clan_dir_json):
        """Skips blank lines in bus file."""
        bus_content = '\n{"src":"a","dst":"*","type":"state","msg":"ok","ack":[]}\n\n'
        (clan_dir_json / "bus.jsonl").write_text(bus_content)
        result = _read_bus_pending(clan_dir_json)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# cmd_hook_pull_on_start tests
# ---------------------------------------------------------------------------


class TestHookPullOnStart:
    """Tests for cmd_hook_pull_on_start()."""

    def test_no_pending_no_output(self, clan_dir_json):
        """Produces no output when there are no pending messages."""
        stdin = io.StringIO("{}")
        stdout = io.StringIO()
        with (
            patch.object(sys, "stdin", stdin),
            patch.object(sys, "stdout", stdout),
            patch("hermes.hooks._default_clan_dir", return_value=clan_dir_json),
        ):
            cmd_hook_pull_on_start()
        assert stdout.getvalue() == ""

    def test_pending_messages_output(self, clan_dir_json):
        """Writes systemMessage JSON when pending messages exist."""
        _write_bus(
            clan_dir_json,
            [
                {"src": "jei", "dst": "*", "type": "state", "msg": "hello world", "ack": []},
            ],
        )
        stdin = io.StringIO("{}")
        stdout = io.StringIO()
        with (
            patch.object(sys, "stdin", stdin),
            patch.object(sys, "stdout", stdout),
            patch("hermes.hooks._default_clan_dir", return_value=clan_dir_json),
        ):
            cmd_hook_pull_on_start()
        output = json.loads(stdout.getvalue())
        assert "systemMessage" in output
        assert "1 pending" in output["systemMessage"]
        assert "jei" in output["systemMessage"]

    def test_truncates_at_5_messages(self, clan_dir_json):
        """Shows at most 5 messages and indicates more exist."""
        msgs = [
            {"src": f"clan{i}", "dst": "*", "type": "state", "msg": f"msg{i}", "ack": []}
            for i in range(8)
        ]
        _write_bus(clan_dir_json, msgs)
        stdin = io.StringIO("{}")
        stdout = io.StringIO()
        with (
            patch.object(sys, "stdin", stdin),
            patch.object(sys, "stdout", stdout),
            patch("hermes.hooks._default_clan_dir", return_value=clan_dir_json),
        ):
            cmd_hook_pull_on_start()
        output = json.loads(stdout.getvalue())
        assert "and 3 more" in output["systemMessage"]

    def test_invalid_stdin_json(self, clan_dir_json):
        """Handles invalid JSON on stdin gracefully."""
        _write_bus(
            clan_dir_json,
            [
                {"src": "jei", "dst": "*", "type": "state", "msg": "ok", "ack": []},
            ],
        )
        stdin = io.StringIO("not json")
        stdout = io.StringIO()
        with (
            patch.object(sys, "stdin", stdin),
            patch.object(sys, "stdout", stdout),
            patch("hermes.hooks._default_clan_dir", return_value=clan_dir_json),
        ):
            cmd_hook_pull_on_start()
        output = json.loads(stdout.getvalue())
        assert "systemMessage" in output


# ---------------------------------------------------------------------------
# cmd_hook_pull_on_prompt tests
# ---------------------------------------------------------------------------


class TestHookPullOnPrompt:
    """Tests for cmd_hook_pull_on_prompt()."""

    def test_non_hermes_prompt_no_output(self, clan_dir_json):
        """Produces no output for non-/hermes prompts."""
        stdin = io.StringIO(json.dumps({"prompt": "hello world"}))
        stdout = io.StringIO()
        with (
            patch.object(sys, "stdin", stdin),
            patch.object(sys, "stdout", stdout),
            patch("hermes.hooks._default_clan_dir", return_value=clan_dir_json),
        ):
            cmd_hook_pull_on_prompt()
        assert stdout.getvalue() == ""

    def test_hermes_prompt_with_pending(self, clan_dir_json):
        """Outputs pending count when prompt starts with /hermes."""
        _write_bus(
            clan_dir_json,
            [
                {"src": "jei", "dst": "*", "type": "state", "msg": "ok", "ack": []},
                {"src": "nymyka", "dst": "*", "type": "event", "msg": "ok2", "ack": []},
            ],
        )
        stdin = io.StringIO(json.dumps({"prompt": "/hermes status"}))
        stdout = io.StringIO()
        with (
            patch.object(sys, "stdin", stdin),
            patch.object(sys, "stdout", stdout),
            patch("hermes.hooks._default_clan_dir", return_value=clan_dir_json),
        ):
            cmd_hook_pull_on_prompt()
        output = json.loads(stdout.getvalue())
        assert "2 pending" in output["systemMessage"]

    def test_hermes_prompt_no_pending(self, clan_dir_json):
        """No output for /hermes prompt when bus is empty."""
        stdin = io.StringIO(json.dumps({"prompt": "/hermes bus"}))
        stdout = io.StringIO()
        with (
            patch.object(sys, "stdin", stdin),
            patch.object(sys, "stdout", stdout),
            patch("hermes.hooks._default_clan_dir", return_value=clan_dir_json),
        ):
            cmd_hook_pull_on_prompt()
        assert stdout.getvalue() == ""

    def test_empty_prompt(self, clan_dir_json):
        """Handles empty prompt gracefully."""
        stdin = io.StringIO(json.dumps({"prompt": ""}))
        stdout = io.StringIO()
        with (
            patch.object(sys, "stdin", stdin),
            patch.object(sys, "stdout", stdout),
            patch("hermes.hooks._default_clan_dir", return_value=clan_dir_json),
        ):
            cmd_hook_pull_on_prompt()
        assert stdout.getvalue() == ""


# ---------------------------------------------------------------------------
# cmd_hook_exit_reminder tests
# ---------------------------------------------------------------------------


class TestHookExitReminder:
    """Tests for cmd_hook_exit_reminder()."""

    def test_no_pending_no_output(self, clan_dir_json):
        """No reminder when nothing is pending."""
        stdin = io.StringIO("{}")
        stdout = io.StringIO()
        with (
            patch.object(sys, "stdin", stdin),
            patch.object(sys, "stdout", stdout),
            patch("hermes.hooks._default_clan_dir", return_value=clan_dir_json),
        ):
            cmd_hook_exit_reminder()
        assert stdout.getvalue() == ""

    def test_pending_shows_reminder(self, clan_dir_json):
        """Shows reminder when unacked messages exist."""
        _write_bus(
            clan_dir_json,
            [
                {"src": "jei", "dst": "*", "type": "state", "msg": "todo", "ack": []},
            ],
        )
        stdin = io.StringIO("{}")
        stdout = io.StringIO()
        with (
            patch.object(sys, "stdin", stdin),
            patch.object(sys, "stdout", stdout),
            patch("hermes.hooks._default_clan_dir", return_value=clan_dir_json),
        ):
            cmd_hook_exit_reminder()
        output = json.loads(stdout.getvalue())
        assert "reminder" in output["systemMessage"].lower()
        assert "1 unacked" in output["systemMessage"]


# ---------------------------------------------------------------------------
# main() entry point tests
# ---------------------------------------------------------------------------


class TestMain:
    """Tests for CLI entry point."""

    def test_no_args_exits(self):
        """Exits with error when no command given."""
        with patch.object(sys, "argv", ["hermes.hooks"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_unknown_command_exits(self):
        """Exits with error for unknown hook command."""
        with patch.object(sys, "argv", ["hermes.hooks", "unknown_cmd"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_dispatches_pull_on_start(self, clan_dir_json):
        """Dispatches to cmd_hook_pull_on_start for 'pull_on_start'."""
        stdin = io.StringIO("{}")
        stdout = io.StringIO()
        with (
            patch.object(sys, "argv", ["hermes.hooks", "pull_on_start"]),
            patch.object(sys, "stdin", stdin),
            patch.object(sys, "stdout", stdout),
            patch("hermes.hooks._default_clan_dir", return_value=clan_dir_json),
        ):
            main()
        # No crash, no output (no pending messages)
        assert stdout.getvalue() == ""

    def test_dispatches_exit_reminder(self, clan_dir_json):
        """Dispatches to cmd_hook_exit_reminder for 'exit_reminder'."""
        stdin = io.StringIO("{}")
        stdout = io.StringIO()
        with (
            patch.object(sys, "argv", ["hermes.hooks", "exit_reminder"]),
            patch.object(sys, "stdin", stdin),
            patch.object(sys, "stdout", stdout),
            patch("hermes.hooks._default_clan_dir", return_value=clan_dir_json),
        ):
            main()
        assert stdout.getvalue() == ""
