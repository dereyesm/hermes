"""HERMES CLI — Gateway management for inter-clan communication.

Usage:
    python -m hermes.cli init <clan-id> <display-name> [--agora-url URL] [--dir PATH]
    python -m hermes.cli status [--dir PATH]
    python -m hermes.cli publish [--dir PATH]
    python -m hermes.cli peer add <clan-id> [--dir PATH]
    python -m hermes.cli peer list [--dir PATH]
    python -m hermes.cli send <target-clan> <message> [--dir PATH]
    python -m hermes.cli inbox [--dir PATH]
    python -m hermes.cli discover <capability> [--dir PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from .agora import AgoraDirectory
from .config import GatewayConfig, PeerConfig, init_clan, load_config, save_config
from .gateway import (
    AgentMapping,
    Gateway,
    InboundValidator,
    TranslationTable,
)


def _resolve_clan_dir(args: argparse.Namespace) -> Path:
    """Resolve the clan directory from CLI args."""
    return Path(getattr(args, "dir", None) or ".")


def _load_gateway(clan_dir: Path) -> tuple[GatewayConfig, Gateway, AgoraDirectory]:
    """Load config, build gateway, and connect to Agora."""
    config_path = clan_dir / "gateway.json"
    config = load_config(config_path)

    # Build translation table from config
    mappings = []
    for a in config.agents:
        internal = a.get("internal", {})
        mappings.append(AgentMapping(
            namespace=internal.get("namespace", ""),
            agent=internal.get("agent", ""),
            external_alias=a.get("external", ""),
            published=a.get("published", True),
            capabilities=a.get("capabilities", []),
        ))

    tt = TranslationTable(clan_id=config.clan_id, mappings=mappings)

    # Build inbound validator from peers
    known_clans = {p.clan_id for p in config.peers}
    published_aliases = {m.external_alias for m in mappings if m.published}
    validator = InboundValidator(
        known_clans=known_clans,
        published_aliases=published_aliases,
        max_payload_bytes=config.inbound_max_payload,
        rate_limit_per_clan=config.inbound_rate_limit,
    )

    gateway = Gateway(
        clan_id=config.clan_id,
        display_name=config.display_name,
        translation_table=tt,
        inbound_validator=validator,
        protocol_version=config.protocol_version,
    )

    # Connect to Agora
    agora_path = clan_dir / config.agora_local_cache
    agora = AgoraDirectory(agora_path)

    return config, gateway, agora


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize a new clan."""
    clan_dir = _resolve_clan_dir(args)
    agora_url = getattr(args, "agora_url", "") or ""

    config = init_clan(
        clan_dir=clan_dir,
        clan_id=args.clan_id,
        display_name=args.display_name,
        agora_url=agora_url,
    )

    # Initialize Agora directory structure
    agora = AgoraDirectory(clan_dir / config.agora_local_cache)
    agora.ensure_structure()

    print(f"Clan '{config.clan_id}' initialized at {clan_dir}")
    print(f"  Config:  {clan_dir / 'gateway.json'}")
    print(f"  Keys:    {clan_dir / '.keys/'}")
    print(f"  Agora:   {clan_dir / config.agora_local_cache}")
    print()
    print("Next steps:")
    print("  1. Add agents to gateway.json")
    print("  2. Run: hermes publish    (publish profile to Agora)")
    print("  3. Run: hermes peer add <clan-id>  (connect to peers)")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show gateway status."""
    clan_dir = _resolve_clan_dir(args)
    try:
        config, gateway, agora = _load_gateway(clan_dir)
    except FileNotFoundError:
        print("Error: No gateway.json found. Run 'hermes init' first.", file=sys.stderr)
        return 1

    profile = gateway.build_public_profile()

    print(f"Clan: {config.clan_id} ({config.display_name})")
    print(f"Protocol: {config.protocol_version}")
    print(f"Heraldo: {config.heraldo_alias}")
    print()

    agents = profile.get("agents", [])
    if agents:
        print(f"Published agents ({len(agents)}):")
        for a in agents:
            res = a.get("resonance", 0)
            caps = ", ".join(a.get("capabilities", []))
            print(f"  {a['alias']:24s} R:{res:6.2f}  [{caps}]")
    else:
        print("No published agents. Add agents to gateway.json.")

    print()
    peers = config.peers
    if peers:
        print(f"Peers ({len(peers)}):")
        for p in peers:
            print(f"  {p.clan_id:24s} status:{p.status}  added:{p.added}")
    else:
        print("No peers. Run 'hermes peer add <clan-id>'.")

    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    """Publish clan profile to Agora."""
    clan_dir = _resolve_clan_dir(args)
    try:
        config, gateway, agora = _load_gateway(clan_dir)
    except FileNotFoundError:
        print("Error: No gateway.json found.", file=sys.stderr)
        return 1

    profile = gateway.build_public_profile()
    # Add public key to profile
    pub_key_path = clan_dir / config.keys_public
    if pub_key_path.exists():
        profile["public_key"] = pub_key_path.read_text().strip()

    path = agora.publish_profile(profile)
    print(f"Profile published: {path}")
    print(f"  Clan: {profile['clan_id']}")
    print(f"  Agents: {profile['clan_stats']['total_published_agents']}")
    return 0


def cmd_peer_add(args: argparse.Namespace) -> int:
    """Add a peer clan."""
    clan_dir = _resolve_clan_dir(args)
    try:
        config, gateway, agora = _load_gateway(clan_dir)
    except FileNotFoundError:
        print("Error: No gateway.json found.", file=sys.stderr)
        return 1

    peer_id = args.peer_clan_id

    # Check if already a peer
    for p in config.peers:
        if p.clan_id == peer_id:
            print(f"Peer '{peer_id}' already registered (status: {p.status}).")
            return 0

    # Try to find peer profile on Agora
    peer_profile = agora.read_profile(peer_id)
    if peer_profile is not None:
        # Store peer's public key
        peer_key = peer_profile.get("public_key", "")
        if peer_key:
            key_path = clan_dir / ".keys" / "peers" / f"{peer_id}.pub"
            key_path.parent.mkdir(parents=True, exist_ok=True)
            key_path.write_text(peer_key)
            print(f"  Public key stored: {key_path}")
    else:
        print(f"  Note: No profile found on Agora for '{peer_id}'. Adding anyway (TOFU).")

    # Add peer to config
    peer = PeerConfig(
        clan_id=peer_id,
        public_key_file=f".keys/peers/{peer_id}.pub",
        status="pending_ack",
        added=date.today().isoformat(),
    )
    config.peers.append(peer)
    save_config(config, clan_dir / "gateway.json")

    # Send hello message via Agora inbox
    hello = {
        "type": "hello",
        "source_clan": config.clan_id,
        "display_name": config.display_name,
        "protocol_version": config.protocol_version,
        "timestamp": date.today().isoformat(),
    }
    pub_key_path = clan_dir / config.keys_public
    if pub_key_path.exists():
        hello["source_key"] = pub_key_path.read_text().strip()

    agora.send_message(peer_id, hello)
    print(f"Peer '{peer_id}' added (status: pending_ack).")
    print(f"  Hello message sent to {peer_id}'s Agora inbox.")
    return 0


def cmd_peer_list(args: argparse.Namespace) -> int:
    """List all peers."""
    clan_dir = _resolve_clan_dir(args)
    try:
        config, _, _ = _load_gateway(clan_dir)
    except FileNotFoundError:
        print("Error: No gateway.json found.", file=sys.stderr)
        return 1

    if not config.peers:
        print("No peers registered.")
        return 0

    print(f"Peers for {config.clan_id}:")
    for p in config.peers:
        print(f"  {p.clan_id:24s} status:{p.status:12s} added:{p.added}")
    return 0


def cmd_send(args: argparse.Namespace) -> int:
    """Send a message to a peer clan via Agora inbox."""
    clan_dir = _resolve_clan_dir(args)
    try:
        config, gateway, agora = _load_gateway(clan_dir)
    except FileNotFoundError:
        print("Error: No gateway.json found.", file=sys.stderr)
        return 1

    target = args.target_clan
    payload = args.message

    # Check outbound filter
    allowed, reason = gateway.outbound_filter.evaluate("quest_response", payload)
    if not allowed:
        print(f"Blocked by outbound filter: {reason}", file=sys.stderr)
        return 1

    message = {
        "type": "quest_response",
        "source_clan": config.clan_id,
        "target_clan": target,
        "payload": payload,
        "timestamp": date.today().isoformat(),
    }

    path = agora.send_message(target, message)
    print(f"Message sent to {target}: {path}")
    return 0


def cmd_inbox(args: argparse.Namespace) -> int:
    """Read messages from the clan's Agora inbox."""
    clan_dir = _resolve_clan_dir(args)
    try:
        config, gateway, agora = _load_gateway(clan_dir)
    except FileNotFoundError:
        print("Error: No gateway.json found.", file=sys.stderr)
        return 1

    messages = agora.read_inbox(config.clan_id)
    if not messages:
        print("Inbox empty.")
        return 0

    print(f"Inbox for {config.clan_id} ({len(messages)} messages):")
    for i, msg in enumerate(messages, 1):
        src = msg.get("source_clan", "unknown")
        msg_type = msg.get("type", "unknown")
        ts = msg.get("timestamp", "")
        payload = msg.get("payload", msg.get("display_name", ""))
        print(f"  [{i}] {ts} from:{src} type:{msg_type}")
        if payload:
            print(f"      {payload[:80]}")
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    """Discover agents by capability on the Agora."""
    clan_dir = _resolve_clan_dir(args)
    try:
        config, _, agora = _load_gateway(clan_dir)
    except FileNotFoundError:
        print("Error: No gateway.json found.", file=sys.stderr)
        return 1

    matches = agora.discover(args.capability)
    if not matches:
        print(f"No agents found for capability '{args.capability}'.")
        return 0

    print(f"Agents matching '{args.capability}':")
    for m in matches:
        caps = ", ".join(m["capabilities"])
        print(f"  {m['clan_id']:20s} {m['agent_alias']:20s} R:{m['resonance']:6.2f}  [{caps}]")
    return 0


def _add_dir_arg(parser: argparse.ArgumentParser) -> None:
    """Add --dir argument to a subparser."""
    parser.add_argument("--dir", default=".", help="Clan directory (default: current)")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="hermes",
        description="HERMES Gateway CLI — Inter-clan communication",
    )
    sub = parser.add_subparsers(dest="command")

    # init
    p_init = sub.add_parser("init", help="Initialize a new clan")
    p_init.add_argument("clan_id", help="Unique clan identifier")
    p_init.add_argument("display_name", help="Human-readable clan name")
    p_init.add_argument("--agora-url", default="", help="Agora directory URL")
    _add_dir_arg(p_init)

    # status
    p_status = sub.add_parser("status", help="Show gateway status")
    _add_dir_arg(p_status)

    # publish
    p_publish = sub.add_parser("publish", help="Publish profile to Agora")
    _add_dir_arg(p_publish)

    # peer
    p_peer = sub.add_parser("peer", help="Manage peers")
    peer_sub = p_peer.add_subparsers(dest="peer_command")
    p_peer_add = peer_sub.add_parser("add", help="Add a peer clan")
    p_peer_add.add_argument("peer_clan_id", help="Peer clan ID")
    _add_dir_arg(p_peer_add)
    p_peer_list = peer_sub.add_parser("list", help="List all peers")
    _add_dir_arg(p_peer_list)

    # send
    p_send = sub.add_parser("send", help="Send message to peer")
    p_send.add_argument("target_clan", help="Target clan ID")
    p_send.add_argument("message", help="Message payload")
    _add_dir_arg(p_send)

    # inbox
    p_inbox = sub.add_parser("inbox", help="Read inbox messages")
    _add_dir_arg(p_inbox)

    # discover
    p_discover = sub.add_parser("discover", help="Discover agents by capability")
    p_discover.add_argument("capability", help="Capability path to search")
    _add_dir_arg(p_discover)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    commands = {
        "init": cmd_init,
        "status": cmd_status,
        "publish": cmd_publish,
        "send": cmd_send,
        "inbox": cmd_inbox,
        "discover": cmd_discover,
    }

    if args.command == "peer":
        peer_commands = {
            "add": cmd_peer_add,
            "list": cmd_peer_list,
        }
        if args.peer_command is None:
            parser.parse_args(["peer", "--help"])
            return 0
        return peer_commands[args.peer_command](args)

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
