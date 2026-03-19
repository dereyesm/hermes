"""HERMES Terminal — Brand-aware CLI output.

Uses `rich` for styled terminal output aligned with the HERMES brand kit.
Falls back gracefully to plain text if rich is not installed.

Brand colors (AES-2040 / BRAND-MANUAL.md):
    Indigo  #1A1A2E  — primary, titles, protocol identity
    Teal    #00D4AA  — success, active, connected
    Amber   #F5A623  — warnings, dispatch, quests
    Emerald #27AE60  — clans, peers, growth
    Crimson #E74C3C  — errors, alerts, critical
    Slate   #7F8C8D  — metadata, timestamps, secondary text
"""

from __future__ import annotations

from typing import Any

# Brand palette
INDIGO = "#1A1A2E"
TEAL = "#00D4AA"
AMBER = "#F5A623"
EMERALD = "#27AE60"
CRIMSON = "#E74C3C"
SLATE = "#7F8C8D"

# Message type → color mapping
TYPE_COLORS = {
    "state": "cyan",
    "event": TEAL,
    "alert": CRIMSON,
    "dispatch": AMBER,
    "request": "magenta",
    "data_cross": EMERALD,
    "dojo_event": "blue",
}

try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
    from rich.panel import Panel
    from rich.columns import Columns

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


def get_console() -> Any:
    """Get a rich Console, or None if rich is not available."""
    if HAS_RICH:
        return Console()
    return None


# ---------------------------------------------------------------------------
# Status display
# ---------------------------------------------------------------------------

def print_clan_status(
    clan_id: str,
    display_name: str,
    protocol_version: str,
    heraldo_alias: str,
    agents: list[dict],
    peers: list[Any],
    fingerprint: str = "",
    daemon_pid: int | None = None,
    daemon_alive: bool = False,
    bus_messages: int = 0,
    bus_pending: int = 0,
    clan_dir: str = "",
) -> None:
    """Print clan status with brand styling — full dashboard view."""
    if not HAS_RICH:
        print(f"Clan: {clan_id} ({display_name})")
        print(f"Protocol: {protocol_version}")
        if fingerprint:
            print(f"Fingerprint: {fingerprint}")
        if daemon_pid:
            status = "running" if daemon_alive else "stale"
            print(f"Daemon: {status} (PID {daemon_pid})")
        print(f"Bus: {bus_messages} messages ({bus_pending} pending)")
        print()
        if agents:
            print(f"Published agents ({len(agents)}):")
            for a in agents:
                res = a.get("resonance", 0)
                caps = ", ".join(a.get("capabilities", []))
                print(f"  {a['alias']:24s} R:{res:6.2f}  [{caps}]")
        else:
            print("No published agents. Add agents to gateway.json.")
        print()
        if peers:
            print(f"Peers ({len(peers)}):")
            for p in peers:
                print(f"  {p.clan_id:24s} status:{p.status}  added:{p.added}")
        else:
            print("No peers. Run 'hermes peer add <clan-id>'.")
        return

    console = Console()

    # Header panel
    title = Text()
    title.append("H E R M E S", style="bold white")
    title.append("  ", style="default")
    title.append(f"{clan_id}", style=f"bold {TEAL}")
    title.append(f"  ({display_name})", style=SLATE)

    console.print(Panel(title, subtitle=f"protocol {protocol_version}", border_style=TEAL))

    # Info grid — fingerprint, daemon, bus stats
    info = Table(show_header=False, box=None, padding=(0, 2))
    info.add_column("Key", style=f"bold {SLATE}", min_width=14)
    info.add_column("Value", min_width=40)

    if fingerprint:
        fp_text = Text(fingerprint, style=f"bold {AMBER}")
        info.add_row("Fingerprint", fp_text)

    if clan_dir:
        info.add_row("Clan dir", Text(clan_dir, style="dim"))

    # Daemon status
    if daemon_pid:
        daemon_text = Text()
        if daemon_alive:
            daemon_text.append("● ", style=f"bold {TEAL}")
            daemon_text.append(f"running (PID {daemon_pid})", style=TEAL)
        else:
            daemon_text.append("○ ", style=f"bold {CRIMSON}")
            daemon_text.append(f"stale (PID {daemon_pid})", style=CRIMSON)
        info.add_row("Agent Node", daemon_text)
    else:
        info.add_row("Agent Node", Text("not running", style="dim"))

    # Bus stats
    bus_text = Text()
    bus_text.append(f"{bus_messages}", style=f"bold {TEAL}")
    bus_text.append(" messages", style="default")
    if bus_pending > 0:
        bus_text.append(f"  ({bus_pending} pending)", style=f"bold {AMBER}")
    info.add_row("Bus", bus_text)

    console.print(info)
    console.print()

    # Agents table
    if agents:
        t = Table(title=f"Agents ({len(agents)})", border_style=SLATE, title_style="bold white")
        t.add_column("Namespace", style=f"bold {TEAL}", min_width=20)
        t.add_column("Resonance", justify="right", style=AMBER)
        t.add_column("Capabilities", style=SLATE)
        for a in agents:
            res = a.get("resonance", 0)
            caps = ", ".join(a.get("capabilities", []))
            t.add_row(a["alias"], f"{res:.2f}", caps)
        console.print(t)
    else:
        console.print(f"  [dim]No published agents. Add agents to gateway.json.[/dim]")

    # Peers table
    if peers:
        t = Table(title=f"Peers ({len(peers)})", border_style=SLATE, title_style=f"bold {EMERALD}")
        t.add_column("Clan", style=f"bold {EMERALD}", min_width=20)
        t.add_column("Status", justify="center")
        t.add_column("Added", style=SLATE)
        for p in peers:
            status_style = TEAL if p.status == "active" else AMBER
            t.add_row(p.clan_id, Text(p.status, style=status_style), p.added)
        console.print(t)
    else:
        console.print(f"  [dim]No peers. Run 'hermes peer add <clan-id>'.[/dim]")


# ---------------------------------------------------------------------------
# Daemon status
# ---------------------------------------------------------------------------

def print_daemon_status(
    alive: bool,
    pid: int | None,
    started_at: str | None = None,
    last_heartbeat: str | None = None,
    bus_offset: int = 0,
    active_dispatches: int = 0,
    dispatch_slots: int = 2,
    last_evaluation: str | None = None,
) -> None:
    """Print Agent Node daemon status with brand styling."""
    if not HAS_RICH:
        status = "running" if alive else ("stale (not running)" if pid else "not running")
        print(f"Agent Node: {status}")
        if pid:
            print(f"  PID: {pid}")
        if started_at:
            print(f"  Started: {started_at}")
            print(f"  Last heartbeat: {last_heartbeat or 'never'}")
            print(f"  Bus offset: {bus_offset} bytes")
            print(f"  Active dispatches: {active_dispatches}")
            print(f"  Last evaluation: {last_evaluation or 'never'}")
        return

    console = Console()

    if pid is None:
        console.print(Panel(
            Text("Agent Node: not running", style="dim"),
            border_style=SLATE,
        ))
        return

    status_text = Text()
    if alive:
        status_text.append("● ", style=f"bold {TEAL}")
        status_text.append("RUNNING", style=f"bold {TEAL}")
    else:
        status_text.append("○ ", style=f"bold {CRIMSON}")
        status_text.append("STALE", style=f"bold {CRIMSON}")

    t = Table(show_header=False, border_style=TEAL if alive else CRIMSON, padding=(0, 2))
    t.add_column("Key", style=f"bold {SLATE}", min_width=14)
    t.add_column("Value", min_width=30)

    t.add_row("Status", status_text)
    t.add_row("PID", str(pid))

    if started_at:
        t.add_row("Started", started_at)
        hb = last_heartbeat or "never"
        hb_style = TEAL if last_heartbeat else CRIMSON
        t.add_row("Heartbeat", Text(hb, style=hb_style))
        t.add_row("Bus offset", f"{bus_offset:,} bytes")

        slots_text = Text()
        slots_text.append(f"{active_dispatches}", style=AMBER if active_dispatches > 0 else TEAL)
        slots_text.append(f"/{dispatch_slots} slots")
        t.add_row("Dispatch", slots_text)

        eval_text = last_evaluation or "never"
        t.add_row("Last eval", Text(eval_text, style=SLATE))

    title = Text()
    title.append(" HERMES ", style="bold white")
    title.append("Agent Node", style=f"bold")

    console.print(Panel(t, title=title, border_style=TEAL if alive else CRIMSON))


# ---------------------------------------------------------------------------
# Inbox display
# ---------------------------------------------------------------------------

def print_inbox(clan_id: str, messages: list[dict]) -> None:
    """Print inbox messages with color-coded types."""
    if not messages:
        if HAS_RICH:
            Console().print(f"[dim]Inbox empty.[/dim]")
        else:
            print("Inbox empty.")
        return

    if not HAS_RICH:
        print(f"Inbox for {clan_id} ({len(messages)} messages):")
        for i, msg in enumerate(messages, 1):
            src = msg.get("source_clan", "unknown")
            msg_type = msg.get("type", "unknown")
            ts = msg.get("timestamp", "")
            payload = msg.get("payload", msg.get("display_name", ""))
            print(f"  [{i}] {ts} from:{src} type:{msg_type}")
            if payload:
                print(f"      {payload[:80]}")
        return

    console = Console()

    t = Table(
        title=f"Inbox — {clan_id} ({len(messages)} messages)",
        border_style=SLATE,
        title_style="bold white",
    )
    t.add_column("#", justify="right", style="dim", width=3)
    t.add_column("Time", style=SLATE, width=12)
    t.add_column("From", style=f"bold {EMERALD}", min_width=15)
    t.add_column("Type", justify="center", no_wrap=True)
    t.add_column("Message", style="default", max_width=50)

    for i, msg in enumerate(messages, 1):
        src = msg.get("source_clan", "unknown")
        msg_type = msg.get("type", "unknown")
        ts = msg.get("timestamp", "")
        payload = msg.get("payload", msg.get("display_name", ""))[:50]
        type_color = TYPE_COLORS.get(msg_type, "white")
        type_text = Text(msg_type, style=f"bold {type_color}")
        t.add_row(str(i), ts, src, type_text, payload)

    console.print(t)


# ---------------------------------------------------------------------------
# Bus display (for future `hermes bus` command)
# ---------------------------------------------------------------------------

def print_bus_messages(messages: list[Any], namespace: str | None = None) -> None:
    """Print bus messages with brand-colored types."""
    if not messages:
        if HAS_RICH:
            Console().print("[dim]Bus empty.[/dim]")
        else:
            print("Bus empty.")
        return

    if not HAS_RICH:
        for msg in messages:
            ack_mark = "✓" if namespace and namespace in getattr(msg, "ack", []) else " "
            print(f"  {ack_mark} [{msg.ts}] {msg.src} → {msg.dst}  ({msg.type}) {msg.msg[:60]}")
        return

    console = Console()

    t = Table(border_style=SLATE, title_style="bold white")
    t.add_column("", width=1)  # ACK mark
    t.add_column("Date", style=SLATE, width=10)
    t.add_column("From", style=f"bold", min_width=12)
    t.add_column("→", justify="center", width=1, style="dim")
    t.add_column("To", style=f"bold", min_width=12)
    t.add_column("Type", justify="center", width=10)
    t.add_column("Message", max_width=45)

    for msg in messages:
        ack_mark = Text("✓", style=TEAL) if namespace and namespace in msg.ack else Text(" ")
        type_color = TYPE_COLORS.get(msg.type, "white")
        t.add_row(
            ack_mark,
            str(msg.ts),
            Text(msg.src, style=EMERALD),
            "→",
            Text(msg.dst, style=AMBER if msg.dst != "*" else "dim"),
            Text(msg.type, style=f"bold {type_color}"),
            msg.msg[:45],
        )

    console.print(t)
