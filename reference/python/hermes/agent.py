"""HERMES Agent Node — ARC-4601 Reference Implementation.

A persistent local daemon that observes the HERMES bus continuously,
maintains a bidirectional link with a remote gateway, and dispatches
sub-agent processes with defined guardrails.

Zero external dependencies — uses stdlib only (asyncio, subprocess,
select, json, os, signal, http.client, urllib.request).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from http.client import HTTPConnection, HTTPSConnection
from pathlib import Path
from typing import Any, AsyncIterator, Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .bus import filter_for_namespace, read_bus, write_message
from .message import Message, ValidationError, create_message, validate_message

logger = logging.getLogger("hermes.agent")


def _sanitize_payload(text: str) -> str:
    """Remove control characters and truncate to 120 chars for ARC-5322."""
    clean = "".join(c for c in text if ord(c) >= 32 or c == "\t")
    return clean[:110]  # Leave room for ESCALATION: prefix


def _parse_bus_message_permissive(data: dict) -> Message | None:
    """Parse a bus message permissively for the Agent Node observer.

    Tolerates: extra fields (seq, w per ARC-9001), long payloads (>120 chars),
    mixed-case namespaces. Only rejects if core fields are missing.
    """
    required = {"ts", "src", "dst", "type", "msg", "ttl", "ack"}
    if not required.issubset(data.keys()):
        return None

    try:
        ts = date.fromisoformat(data["ts"])
    except (ValueError, TypeError):
        return None

    src = str(data["src"]).lower()
    dst = str(data["dst"]) if data["dst"] == "*" else str(data["dst"]).lower()
    msg_type = str(data["type"])
    msg_text = str(data["msg"])
    ttl = int(data["ttl"]) if isinstance(data["ttl"], int) else 7
    ack = list(data["ack"]) if isinstance(data["ack"], list) else []

    return Message(
        ts=ts, src=src, dst=dst, type=msg_type, msg=msg_text,
        ttl=ttl, ack=[str(a).lower() for a in ack],
    )


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class AgentNodeConfig:
    """Agent Node configuration per ARC-4601 Section 9."""

    bus_path: Path
    gateway_url: str
    namespace: str = "heraldo"
    gateway_sse_path: str = "/events"
    gateway_push_path: str = "/bus/push"
    gateway_heartbeat_path: str = "/healthz"
    auth_token: str = ""
    gateway_key: str = ""  # X-Gateway-Key for /bus/push
    sse_token: str = ""  # token query param for /events
    heartbeat_interval: float = 60.0
    evaluation_interval: float = 300.0
    max_dispatch_slots: int = 2
    dispatch_timeout: float = 300.0
    dispatch_command: str = "claude"
    dispatch_max_turns: int = 10
    dispatch_allowed_tools: list[str] = field(default_factory=list)
    poll_interval: float = 2.0
    escalation_threshold_hours: int = 4
    forward_types: list[str] = field(
        default_factory=lambda: ["alert", "dispatch", "event"]
    )
    clan_dir: Path = field(default_factory=lambda: Path("."))


def load_agent_config(gateway_json_path: Path) -> AgentNodeConfig:
    """Load AgentNodeConfig from the agent_node section of gateway.json.

    Returns None-equivalent by raising ValueError if agent_node is missing
    or disabled.
    """
    path = Path(gateway_json_path)
    if not path.exists():
        raise FileNotFoundError(f"Gateway config not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    section = data.get("agent_node")
    if section is None:
        raise ValueError("No 'agent_node' section in gateway.json")
    if not section.get("enabled", False):
        raise ValueError("Agent node is disabled (enabled=false)")

    clan_dir = path.parent

    return AgentNodeConfig(
        bus_path=Path(section.get("bus_path", "bus.jsonl")).expanduser()
        if Path(section.get("bus_path", "bus.jsonl")).is_absolute()
        else clan_dir / section.get("bus_path", "bus.jsonl"),
        gateway_url=section.get("gateway_url", ""),
        namespace=section.get("namespace", "heraldo"),
        gateway_sse_path=section.get("gateway_sse_path", "/events"),
        gateway_push_path=section.get("gateway_push_path", "/bus/push"),
        gateway_heartbeat_path=section.get(
            "gateway_heartbeat_path", "/healthz"
        ),
        auth_token=section.get("auth_token", ""),
        gateway_key=section.get("gateway_key", ""),
        sse_token=section.get("sse_token", ""),
        heartbeat_interval=float(section.get("heartbeat_interval", 60)),
        evaluation_interval=float(section.get("evaluation_interval", 300)),
        max_dispatch_slots=int(section.get("max_dispatch_slots", 2)),
        dispatch_timeout=float(section.get("dispatch_timeout", 300)),
        dispatch_command=section.get("dispatch_command", "claude"),
        dispatch_max_turns=int(section.get("dispatch_max_turns", 10)),
        dispatch_allowed_tools=list(
            section.get("dispatch_allowed_tools", [])
        ),
        poll_interval=float(section.get("poll_interval", 2.0)),
        escalation_threshold_hours=int(
            section.get("escalation_threshold_hours", 4)
        ),
        forward_types=list(
            section.get("forward_types", ["alert", "dispatch", "event"])
        ),
        clan_dir=clan_dir,
    )


# ---------------------------------------------------------------------------
# State Management
# ---------------------------------------------------------------------------

@dataclass
class DispatchSlot:
    """A running sub-agent dispatch."""

    pid: int
    cid: str
    started_at: float
    command: list[str] = field(default_factory=list)


@dataclass
class NodeState:
    """Persistent state for the Agent Node."""

    pid: int
    started_at: str
    last_heartbeat: str | None = None
    bus_offset: int = 0
    active_dispatches: list[DispatchSlot] = field(default_factory=list)
    last_evaluation: str | None = None

    def to_dict(self) -> dict:
        return {
            "pid": self.pid,
            "started_at": self.started_at,
            "last_heartbeat": self.last_heartbeat,
            "bus_offset": self.bus_offset,
            "active_dispatches": [
                {
                    "pid": d.pid,
                    "cid": d.cid,
                    "started_at": d.started_at,
                    "command": d.command,
                }
                for d in self.active_dispatches
            ],
            "last_evaluation": self.last_evaluation,
        }

    @classmethod
    def from_dict(cls, data: dict) -> NodeState:
        dispatches = [
            DispatchSlot(
                pid=d["pid"],
                cid=d["cid"],
                started_at=d["started_at"],
                command=d.get("command", []),
            )
            for d in data.get("active_dispatches", [])
        ]
        return cls(
            pid=data["pid"],
            started_at=data["started_at"],
            last_heartbeat=data.get("last_heartbeat"),
            bus_offset=data.get("bus_offset", 0),
            active_dispatches=dispatches,
            last_evaluation=data.get("last_evaluation"),
        )


class StateManager:
    """Manages Agent Node state persistence and PID locking."""

    def __init__(self, clan_dir: Path):
        self.state_path = clan_dir / "agent-node.state.json"
        self.lock_dir = clan_dir / "agent-node.lock"

    def acquire_lock(self) -> bool:
        """Acquire the PID lock. Returns True if acquired."""
        try:
            os.mkdir(self.lock_dir)
        except FileExistsError:
            # Check if the existing lock is stale
            pid_file = self.lock_dir / "pid"
            if pid_file.exists():
                try:
                    existing_pid = int(pid_file.read_text().strip())
                    os.kill(existing_pid, 0)
                    # Process is alive — lock is held
                    return False
                except (ValueError, OSError):
                    # Process is dead or PID invalid — stale lock
                    pass
            # Reclaim stale lock
            try:
                self._remove_lock_dir()
                os.mkdir(self.lock_dir)
            except OSError:
                return False

        # Write our PID
        pid_file = self.lock_dir / "pid"
        pid_file.write_text(str(os.getpid()))
        return True

    def release_lock(self) -> None:
        """Release the PID lock."""
        self._remove_lock_dir()

    def _remove_lock_dir(self) -> None:
        pid_file = self.lock_dir / "pid"
        if pid_file.exists():
            pid_file.unlink()
        if self.lock_dir.exists():
            self.lock_dir.rmdir()

    def save(self, state: NodeState) -> None:
        """Atomically save state to disk."""
        tmp_path = self.state_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, indent=2)
            f.write("\n")
        os.rename(tmp_path, self.state_path)

    def load(self) -> NodeState | None:
        """Load state from disk. Returns None if no state file exists."""
        if not self.state_path.exists():
            return None
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return NodeState.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None

    def recover(self) -> NodeState | None:
        """Recover from a previous state, cleaning up orphaned dispatches.

        Returns the recovered state or None if no recovery is possible.
        """
        state = self.load()
        if state is None:
            return None

        # Check if the recorded PID is still alive
        try:
            os.kill(state.pid, 0)
            # PID is alive — another node is running
            return None
        except OSError:
            pass

        # Clean up orphaned dispatches
        for slot in state.active_dispatches:
            _kill_process(slot.pid)

        state.active_dispatches = []
        state.pid = os.getpid()
        return state

    def get_lock_pid(self) -> int | None:
        """Read the PID from the lock directory. Returns None if not locked."""
        pid_file = self.lock_dir / "pid"
        if not pid_file.exists():
            return None
        try:
            return int(pid_file.read_text().strip())
        except (ValueError, OSError):
            return None


def _kill_process(pid: int) -> None:
    """Attempt to kill a process: SIGTERM, wait 5s, SIGKILL."""
    try:
        os.kill(pid, signal.SIGTERM)
        # Give it a moment
        for _ in range(50):
            try:
                os.kill(pid, 0)
                time.sleep(0.1)
            except OSError:
                return
        # Still alive — force kill
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass  # Process already gone


# ---------------------------------------------------------------------------
# Bus Observer
# ---------------------------------------------------------------------------

class BusObserver:
    """Watches bus.jsonl for new messages using offset-based tail.

    Uses kqueue (macOS) where available, falls back to stat polling.
    """

    def __init__(
        self,
        bus_path: Path,
        namespace: str,
        offset: int = 0,
        poll_interval: float = 2.0,
    ):
        self.bus_path = Path(bus_path)
        self.namespace = namespace
        self.offset = offset
        self.poll_interval = poll_interval
        self._kqueue_available = self._check_kqueue()

    @staticmethod
    def _check_kqueue() -> bool:
        """Check if kqueue is available (macOS/BSD)."""
        try:
            import select
            return hasattr(select, "kqueue")
        except ImportError:
            return False

    def read_new_lines(self) -> list[Message]:
        """Read new messages from the bus starting at current offset.

        Uses permissive parsing to handle real-world bus messages that may
        have extra fields (seq, w per ARC-9001) or long payloads.
        """
        if not self.bus_path.exists():
            return []

        file_size = self.bus_path.stat().st_size

        # File was rewritten (smaller than offset) — reset
        if file_size < self.offset:
            logger.info("Bus file truncated, resetting offset to 0")
            self.offset = 0

        if file_size == self.offset:
            return []

        messages = []
        with open(self.bus_path, "r", encoding="utf-8") as f:
            f.seek(self.offset)
            new_data = f.read()
            new_offset = f.tell()

        for line in new_data.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                msg = _parse_bus_message_permissive(data)
                if msg is not None:
                    messages.append(msg)
            except json.JSONDecodeError as e:
                logger.warning("Skipping malformed JSON: %s", e)

        self.offset = new_offset
        return messages

    async def watch(self) -> AsyncIterator[list[Message]]:
        """Yield batches of new messages as they appear.

        Uses kqueue where available, falls back to polling.
        """
        if self._kqueue_available:
            async for batch in self._kqueue_watch():
                yield batch
        else:
            async for batch in self._poll_watch():
                yield batch

    async def _kqueue_watch(self) -> AsyncIterator[list[Message]]:
        """Watch using kqueue (macOS/BSD)."""
        import select as sel

        kq = sel.kqueue()
        try:
            while True:
                # Ensure bus file exists
                if not self.bus_path.exists():
                    await asyncio.sleep(self.poll_interval)
                    continue

                fd = os.open(str(self.bus_path), os.O_RDONLY)
                try:
                    ev = sel.kevent(
                        fd,
                        filter=sel.KQ_FILTER_VNODE,
                        flags=sel.KQ_EV_ADD | sel.KQ_EV_CLEAR,
                        fflags=sel.KQ_NOTE_WRITE | sel.KQ_NOTE_EXTEND,
                    )

                    # Check for existing new data first
                    messages = self.read_new_lines()
                    if messages:
                        yield messages

                    # Wait for file modification
                    events = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: kq.control([ev], 1, self.poll_interval),
                    )

                    if events:
                        messages = self.read_new_lines()
                        if messages:
                            yield messages
                finally:
                    os.close(fd)
        finally:
            kq.close()

    async def _poll_watch(self) -> AsyncIterator[list[Message]]:
        """Watch using stat-based polling (fallback)."""
        while True:
            messages = self.read_new_lines()
            if messages:
                yield messages
            await asyncio.sleep(self.poll_interval)


# ---------------------------------------------------------------------------
# Gateway Link
# ---------------------------------------------------------------------------

class GatewayLink:
    """Manages bidirectional connection with a remote gateway."""

    def __init__(self, config: AgentNodeConfig):
        self.config = config
        self._parsed_url = urlparse(config.gateway_url)
        self._backoff = 1.0
        self._max_backoff = 60.0

    def _push_headers(self) -> dict[str, str]:
        """Headers for /bus/push endpoint (X-Gateway-Key auth)."""
        headers = {"Content-Type": "application/json"}
        key = self.config.gateway_key or self.config.auth_token
        if key:
            headers["X-Gateway-Key"] = key
        return headers

    def post_message(self, message: Message) -> bool:
        """POST a message to the gateway push endpoint. Returns success."""
        url = self.config.gateway_url + self.config.gateway_push_path
        payload = json.dumps(message.to_dict()).encode("utf-8")

        try:
            req = Request(
                url,
                data=payload,
                headers=self._push_headers(),
                method="POST",
            )
            with urlopen(req, timeout=10) as resp:
                return resp.status < 400
        except Exception as e:
            logger.warning("POST to gateway failed: %s", e)
            return False

    def send_heartbeat(self, state: NodeState, uptime: float) -> bool:
        """Send heartbeat via GET /healthz (liveness check)."""
        url = self.config.gateway_url + self.config.gateway_heartbeat_path

        try:
            req = Request(url, method="GET")
            with urlopen(req, timeout=10) as resp:
                return resp.status < 400
        except Exception as e:
            logger.debug("Heartbeat failed: %s", e)
            return False

    async def sse_connect(self) -> AsyncIterator[dict]:
        """Connect to gateway SSE endpoint and yield parsed events.

        Reconnects with exponential backoff on failure.
        """
        while True:
            try:
                async for event in self._sse_stream():
                    self._backoff = 1.0  # Reset on success
                    yield event
            except Exception as e:
                logger.warning(
                    "SSE connection lost: %s (reconnecting in %.0fs)",
                    e, self._backoff,
                )
                await asyncio.sleep(self._backoff)
                self._backoff = min(self._backoff * 2, self._max_backoff)

    async def _sse_stream(self) -> AsyncIterator[dict]:
        """SSE stream reader using raw socket for non-blocking reads."""
        import select as sel
        import socket
        import ssl

        parsed = self._parsed_url
        sse_path = self.config.gateway_sse_path
        token = self.config.sse_token or self.config.auth_token
        if token:
            sep = "&" if "?" in sse_path else "?"
            sse_path += f"{sep}token={token}"

        hostname = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)

        # Create raw socket connection
        raw_sock = socket.create_connection((hostname, port), timeout=10)
        if parsed.scheme == "https":
            ctx = ssl.create_default_context()
            sock = ctx.wrap_socket(raw_sock, server_hostname=hostname)
        else:
            sock = raw_sock

        try:
            # Send HTTP GET request manually
            request_line = (
                f"GET {sse_path} HTTP/1.1\r\n"
                f"Host: {hostname}\r\n"
                f"Accept: text/event-stream\r\n"
                f"Connection: keep-alive\r\n"
                f"\r\n"
            )
            sock.sendall(request_line.encode())

            # Read response headers
            header_buf = b""
            while b"\r\n\r\n" not in header_buf:
                chunk = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: sock.recv(4096)
                )
                if not chunk:
                    raise ConnectionError("SSE connection closed during headers")
                header_buf += chunk

            header_text, body_start = header_buf.split(b"\r\n\r\n", 1)
            status_line = header_text.split(b"\r\n")[0].decode()
            if "200" not in status_line:
                raise ConnectionError(f"SSE returned: {status_line}")

            logger.info("SSE connected to %s%s", hostname, sse_path.split("?")[0])

            # Set socket to non-blocking for select-based reads
            sock.setblocking(False)
            buffer = body_start.decode("utf-8", errors="replace")

            while True:
                # Use select with 5s timeout for interruptibility
                ready = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: sel.select([sock], [], [], 5.0)
                )

                if ready[0]:
                    try:
                        data = sock.recv(4096)
                    except (ssl.SSLWantReadError, BlockingIOError):
                        continue
                    if not data:
                        break  # Connection closed
                    buffer += data.decode("utf-8", errors="replace")

                # Parse complete events from buffer
                while "\n\n" in buffer:
                    event_text, buffer = buffer.split("\n\n", 1)
                    event = self._parse_sse_event(event_text)
                    if event is not None:
                        yield event

        finally:
            sock.close()

    @staticmethod
    def _parse_sse_event(text: str) -> dict | None:
        """Parse a single SSE event block into a dict."""
        data_lines = []
        for line in text.split("\n"):
            if line.startswith("data:"):
                data_lines.append(line[5:].strip())
            elif line.startswith(":"):
                continue  # Comment (heartbeat)
        if not data_lines:
            return None
        try:
            return json.loads("\n".join(data_lines))
        except json.JSONDecodeError:
            return None


# ---------------------------------------------------------------------------
# Message Evaluator
# ---------------------------------------------------------------------------

class Action(str, Enum):
    """Actions the evaluator can assign to a message."""

    DISPATCH = "dispatch"
    ESCALATE = "escalate"
    FORWARD = "forward"
    IGNORE = "ignore"


class MessageEvaluator:
    """Decides what to do with pending messages per ARC-4601 Section 7.2."""

    def __init__(self, config: AgentNodeConfig):
        self.config = config

    def evaluate(self, message: Message) -> Action:
        """Determine action for a message."""
        # Already ACKed by this node — ignore
        if self.config.namespace in message.ack:
            return Action.IGNORE

        # Not addressed to us
        if message.dst != self.config.namespace and message.dst != "*":
            # Check if it's an external-bound message to forward
            if message.type in self.config.forward_types:
                return Action.FORWARD
            return Action.IGNORE

        # State messages are informational — ignore
        if message.type == "state":
            return Action.IGNORE

        # dojo_event messages are informational — ignore
        if message.type == "dojo_event":
            return Action.IGNORE

        # Dispatch type addressed to us — auto-dispatch
        if message.type == "dispatch":
            return Action.DISPATCH

        # Request type — always escalate (requires human)
        if message.type == "request":
            return Action.ESCALATE

        # Alert — check age
        if message.type == "alert":
            age_hours = (date.today() - message.ts).days * 24
            if age_hours > self.config.escalation_threshold_hours:
                return Action.ESCALATE
            return Action.FORWARD

        # Event — forward
        if message.type == "event":
            return Action.FORWARD

        # data_cross — escalate (human decision)
        if message.type == "data_cross":
            return Action.ESCALATE

        return Action.IGNORE


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

@dataclass
class DispatchResult:
    """Result of a dispatch execution."""

    cid: str
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool


class Dispatcher:
    """Manages sub-agent process spawning with guardrails."""

    def __init__(self, config: AgentNodeConfig):
        self.config = config
        self.active: list[DispatchSlot] = []

    @property
    def available_slots(self) -> int:
        return self.config.max_dispatch_slots - len(self.active)

    def build_command(self, message: Message) -> list[str]:
        """Build the subprocess command with guardrails."""
        cmd = [self.config.dispatch_command, "-p", message.msg]
        cmd.extend(["--max-turns", str(self.config.dispatch_max_turns)])
        cmd.extend(["--output-format", "json"])
        if self.config.dispatch_allowed_tools:
            cmd.extend([
                "--allowedTools",
                ",".join(self.config.dispatch_allowed_tools),
            ])
        return cmd

    async def dispatch(self, message: Message, cid: str) -> DispatchSlot:
        """Spawn a sub-agent for the given message.

        Raises RuntimeError if no slots available.
        """
        if self.available_slots <= 0:
            raise RuntimeError("No dispatch slots available")

        cmd = self.build_command(message)
        logger.info("Dispatching [%s]: %s", cid, " ".join(cmd[:3]))

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (FileNotFoundError, OSError) as e:
            raise RuntimeError(f"Dispatch command not found: {cmd[0]!r}: {e}") from e

        slot = DispatchSlot(
            pid=proc.pid,
            cid=cid,
            started_at=time.time(),
            command=cmd,
        )
        self.active.append(slot)
        return slot

    async def wait_slot(self, slot: DispatchSlot) -> DispatchResult:
        """Wait for a dispatch to complete, enforcing timeout."""
        # Find the process by PID
        try:
            proc = await asyncio.create_subprocess_exec(
                "kill", "-0", str(slot.pid),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
        except Exception:
            pass

        duration = time.time() - slot.started_at
        timed_out = duration > self.config.dispatch_timeout

        result = DispatchResult(
            cid=slot.cid,
            exit_code=-1 if timed_out else 0,
            stdout="",
            stderr="timeout" if timed_out else "",
            duration_seconds=duration,
            timed_out=timed_out,
        )

        self._remove_slot(slot)
        return result

    async def cancel_slot(self, slot: DispatchSlot) -> None:
        """Cancel a running dispatch."""
        _kill_process(slot.pid)
        self._remove_slot(slot)

    def _remove_slot(self, slot: DispatchSlot) -> None:
        self.active = [s for s in self.active if s.pid != slot.pid]


# ---------------------------------------------------------------------------
# Agent Node (main daemon)
# ---------------------------------------------------------------------------

class AgentNode:
    """The persistent Agent Node daemon per ARC-4601."""

    def __init__(self, config: AgentNodeConfig):
        self.config = config
        self.state_manager = StateManager(config.clan_dir)
        self.observer = BusObserver(
            config.bus_path,
            config.namespace,
            poll_interval=config.poll_interval,
        )
        self.gateway = GatewayLink(config)
        self.evaluator = MessageEvaluator(config)
        self.dispatcher = Dispatcher(config)
        self.state: NodeState | None = None
        self._running = False
        self._start_time = 0.0

    async def run(self) -> None:
        """Main event loop. Starts all async tasks."""
        # Acquire lock
        if not self.state_manager.acquire_lock():
            existing_pid = self.state_manager.get_lock_pid()
            logger.error(
                "Another node is running (PID %s). Aborting.", existing_pid
            )
            raise RuntimeError(f"Node already running (PID {existing_pid})")

        try:
            # Initialize or recover state
            recovered = self.state_manager.recover()
            if recovered:
                self.state = recovered
                self.observer.offset = recovered.bus_offset
                logger.info("Recovered state from previous run (offset=%d)", recovered.bus_offset)
            else:
                self.state = NodeState(
                    pid=os.getpid(),
                    started_at=datetime.now().isoformat(),
                )

            self._running = True
            self._start_time = time.time()

            logger.info(
                "Agent Node starting (namespace=%s, PID=%d)",
                self.config.namespace,
                os.getpid(),
            )

            # Run all tasks concurrently
            await asyncio.gather(
                self._bus_loop(),
                self._heartbeat_loop(),
                self._evaluation_loop(),
                self._sse_loop(),
            )
        except asyncio.CancelledError:
            logger.info("Agent Node shutting down...")
        finally:
            await self.drain()
            self._persist_state()
            self.state_manager.release_lock()
            self._running = False
            logger.info("Agent Node stopped.")

    async def _bus_loop(self) -> None:
        """Process new bus messages as they appear."""
        async for batch in self.observer.watch():
            for msg in batch:
                action = self.evaluator.evaluate(msg)

                if action == Action.DISPATCH:
                    if self.dispatcher.available_slots > 0:
                        from .message import extract_cid
                        cid = extract_cid(msg.msg) or f"auto-{int(time.time())}"
                        try:
                            slot = await self.dispatcher.dispatch(msg, cid)
                            logger.info("Dispatched [%s] PID=%d", cid, slot.pid)
                        except RuntimeError:
                            logger.warning("No slots for dispatch [%s]", cid)

                elif action == Action.FORWARD:
                    success = await asyncio.get_event_loop().run_in_executor(
                        None, self.gateway.post_message, msg
                    )
                    if success:
                        logger.debug("Forwarded message: %s", msg.msg[:50])

                elif action == Action.ESCALATE:
                    safe_payload = _sanitize_payload(msg.msg[:80])
                    try:
                        escalation = create_message(
                            src=self.config.namespace,
                            dst="*",
                            type="alert",
                            msg=f"ESCALATION:{msg.type}:{safe_payload}",
                        )
                        await asyncio.get_event_loop().run_in_executor(
                            None, self.gateway.post_message, escalation
                        )
                        logger.info("Escalated: %s", safe_payload[:50])
                    except ValidationError:
                        logger.warning("Could not create escalation for: %s", msg.msg[:50])

            # Update state
            if self.state:
                self.state.bus_offset = self.observer.offset
                self.state.active_dispatches = self.dispatcher.active
                self._persist_state()

    async def _sse_loop(self) -> None:
        """Process inbound messages from gateway SSE."""
        if not self.config.gateway_url:
            return

        async for event in self.gateway.sse_connect():
            try:
                msg = validate_message(event)
                # Deduplicate: check if message already on bus
                existing = read_bus(self.config.bus_path)
                is_dup = any(
                    m.src == msg.src and m.ts == msg.ts and m.msg == msg.msg
                    for m in existing
                )
                if not is_dup:
                    write_message(self.config.bus_path, msg)
                    logger.info("SSE → bus: %s", msg.msg[:50])
            except (ValidationError, Exception) as e:
                logger.debug("SSE event skipped: %s", e)

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats to the gateway."""
        if not self.config.gateway_url:
            return

        while self._running:
            uptime = time.time() - self._start_time
            if self.state:
                success = await asyncio.get_event_loop().run_in_executor(
                    None, self.gateway.send_heartbeat, self.state, uptime
                )
                if success:
                    self.state.last_heartbeat = datetime.now().isoformat()
                    logger.debug("Heartbeat sent (uptime=%ds)", int(uptime))
            await asyncio.sleep(self.config.heartbeat_interval)

    async def _evaluation_loop(self) -> None:
        """Periodic evaluation of all pending messages."""
        while self._running:
            await asyncio.sleep(self.config.evaluation_interval)
            try:
                messages = read_bus(self.config.bus_path)
                pending = filter_for_namespace(messages, self.config.namespace)
                for msg in pending:
                    action = self.evaluator.evaluate(msg)
                    if action == Action.ESCALATE:
                        escalation = create_message(
                            src=self.config.namespace,
                            dst="*",
                            type="alert",
                            msg=f"ESCALATION:{msg.type}:{msg.msg[:80]}",
                        )
                        await asyncio.get_event_loop().run_in_executor(
                            None, self.gateway.post_message, escalation
                        )
                if self.state:
                    self.state.last_evaluation = datetime.now().isoformat()
            except Exception as e:
                logger.warning("Evaluation cycle failed: %s", e)

    async def drain(self) -> None:
        """Graceful shutdown: wait for in-flight dispatches to complete."""
        if not self.dispatcher.active:
            return

        logger.info(
            "Draining %d active dispatches...", len(self.dispatcher.active)
        )
        for slot in list(self.dispatcher.active):
            try:
                await asyncio.wait_for(
                    self.dispatcher.wait_slot(slot),
                    timeout=min(30.0, self.config.dispatch_timeout),
                )
            except asyncio.TimeoutError:
                logger.warning("Force-killing dispatch PID=%d", slot.pid)
                await self.dispatcher.cancel_slot(slot)

    def _persist_state(self) -> None:
        """Save current state to disk."""
        if self.state:
            self.state_manager.save(self.state)

    def stop(self) -> None:
        """Signal the node to stop."""
        self._running = False


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_daemon_start(clan_dir: Path, foreground: bool = True) -> int:
    """Start the Agent Node daemon."""
    try:
        config = load_agent_config(clan_dir / "gateway.json")
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    node = AgentNode(config)

    # Handle signals for graceful shutdown
    loop = asyncio.new_event_loop()

    def _shutdown(sig: int, frame: Any) -> None:
        node.stop()
        for task in asyncio.all_tasks(loop):
            task.cancel()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        loop.run_until_complete(node.run())
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        loop.close()

    return 0


def cmd_daemon_stop(clan_dir: Path) -> int:
    """Stop the Agent Node daemon."""
    sm = StateManager(clan_dir)
    pid = sm.get_lock_pid()
    if pid is None:
        print("No agent node is running.")
        return 1

    try:
        os.kill(pid, 0)
    except OSError:
        print(f"Agent node PID {pid} is not running (stale lock). Cleaning up.")
        sm.release_lock()
        return 0

    print(f"Sending SIGTERM to agent node PID {pid}...")
    os.kill(pid, signal.SIGTERM)
    return 0


def cmd_daemon_status(clan_dir: Path) -> int:
    """Show Agent Node status."""
    sm = StateManager(clan_dir)
    pid = sm.get_lock_pid()
    state = sm.load()

    if pid is None:
        print("Agent Node: not running")
        return 0

    alive = False
    try:
        os.kill(pid, 0)
        alive = True
    except OSError:
        pass

    print(f"Agent Node: {'running' if alive else 'stale (not running)'}")
    print(f"  PID: {pid}")

    if state:
        print(f"  Started: {state.started_at}")
        print(f"  Last heartbeat: {state.last_heartbeat or 'never'}")
        print(f"  Bus offset: {state.bus_offset} bytes")
        print(f"  Active dispatches: {len(state.active_dispatches)}")
        print(f"  Last evaluation: {state.last_evaluation or 'never'}")

    return 0
