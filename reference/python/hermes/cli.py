"""HERMES CLI — Gateway management for inter-clan communication.

Usage:
    python -m hermes.cli init <clan-id> <display-name> [--agora-url URL] [--dir PATH]
    python -m hermes.cli status [--dir PATH]
    python -m hermes.cli publish [--dir PATH]
    python -m hermes.cli peer add <clan-id> [--dir PATH]
    python -m hermes.cli peer list [--dir PATH]
    python -m hermes.cli send <target-clan> <message> [--dir PATH]
    python -m hermes.cli inbox [--dir PATH]
    python -m hermes.cli bus [--filter-type TYPE] [--pending] [--dir PATH]
    python -m hermes.cli discover <capability> [--dir PATH]
    python -m hermes.cli daemon start [--dir PATH] [--foreground]
    python -m hermes.cli daemon stop [--dir PATH]
    python -m hermes.cli daemon status [--dir PATH]
    python -m hermes.cli install --clan-id <id> --display-name <name> [options]
    python -m hermes.cli uninstall [--purge] [--keep-hooks] [--dir PATH]
    python -m hermes.cli hook <pull-on-start|pull-on-prompt|exit-reminder>
    python -m hermes.cli adapt <adapter-name> [--hermes-dir PATH] [--target-dir PATH]
    python -m hermes.cli llm list [--dir PATH]
    python -m hermes.cli llm status [--dir PATH]
    python -m hermes.cli llm test [--backend NAME] [--dir PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from .agora import AgoraDirectory
from .config import (
    GatewayConfig,
    PeerConfig,
    init_clan,
    load_config,
    migrate_json_to_toml,
    resolve_config_path,
    save_config,
)
from .gateway import (
    AgentMapping,
    Gateway,
    InboundValidator,
    TranslationTable,
)


def _resolve_clan_dir(args: argparse.Namespace) -> Path:
    """Resolve the clan directory from CLI args.

    Priority: --dir flag > ~/.hermes/ (if exists) > current directory.
    """
    explicit = getattr(args, "dir", None)
    if explicit and explicit != ".":
        return Path(explicit)

    # Check default clan dir before falling back to cwd
    default = Path.home() / ".hermes"
    if (default / "config.toml").exists() or (default / "gateway.json").exists():
        return default

    return Path(".")


def _load_gateway(clan_dir: Path) -> tuple[GatewayConfig, Gateway, AgoraDirectory]:
    """Load config, build gateway, and connect to Agora."""
    config = load_config(clan_dir)

    # Build translation table from config
    mappings = []
    for a in config.agents:
        internal = a.get("internal", {})
        mappings.append(
            AgentMapping(
                namespace=internal.get("namespace", ""),
                agent=internal.get("agent", ""),
                external_alias=a.get("external", ""),
                published=a.get("published", True),
                capabilities=a.get("capabilities", []),
            )
        )

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

    config_format = getattr(args, "format", "json") or "json"

    config = init_clan(
        clan_dir=clan_dir,
        clan_id=args.clan_id,
        display_name=args.display_name,
        agora_url=agora_url,
        config_format=config_format,
    )

    # Initialize Agora directory structure
    agora = AgoraDirectory(clan_dir / config.agora_local_cache)
    agora.ensure_structure()

    config_file = "config.toml" if config_format == "toml" else "gateway.json"
    print(f"Clan '{config.clan_id}' initialized at {clan_dir}")
    print(f"  Config:  {clan_dir / config_file}")
    print(f"  Keys:    {clan_dir / '.keys/'}")
    print(f"  Agora:   {clan_dir / config.agora_local_cache}")
    print()
    print("Next steps:")
    print(f"  1. Add agents to {config_file}")
    print("  2. Run: hermes publish    (publish profile to Agora)")
    print("  3. Run: hermes peer add <clan-id>  (connect to peers)")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show gateway status — full dashboard."""
    from .terminal import print_clan_status

    clan_dir = _resolve_clan_dir(args)
    try:
        config, gateway, agora = _load_gateway(clan_dir)
    except FileNotFoundError:
        print("Error: No config found. Run 'hermes init' first.", file=sys.stderr)
        return 1

    profile = gateway.build_public_profile()

    # Fingerprint (if crypto keys exist — check both keys/ and .keys/)
    fingerprint = ""
    for keys_subdir in [config.keys_private.rsplit("/", 1)[0], ".keys"]:
        keys_dir = clan_dir / keys_subdir
        key_file = keys_dir / f"{config.clan_id}.key"
        if key_file.exists():
            try:
                from .crypto import ClanKeyPair

                kp = ClanKeyPair.load(str(keys_dir), config.clan_id)
                fingerprint = kp.fingerprint()
            except Exception:
                pass
            break

    # Daemon status
    daemon_pid = None
    daemon_alive = False
    pid_file = clan_dir / ".agent-node.pid"
    if pid_file.exists():
        try:
            daemon_pid = int(pid_file.read_text().strip())
            import os

            os.kill(daemon_pid, 0)
            daemon_alive = True
        except (ValueError, ProcessLookupError, PermissionError):
            pass

    # Bus stats
    bus_messages = 0
    bus_pending = 0
    bus_path = clan_dir / "bus.jsonl"
    if bus_path.exists():
        try:
            from .bus import filter_for_namespace, read_bus

            all_msgs = read_bus(bus_path)
            bus_messages = len(all_msgs)
            pending = filter_for_namespace(all_msgs, config.clan_id)
            bus_pending = len(pending)
        except Exception:
            pass

    print_clan_status(
        clan_id=config.clan_id,
        display_name=config.display_name,
        protocol_version=config.protocol_version,
        heraldo_alias=config.heraldo_alias,
        agents=profile.get("agents", []),
        peers=config.peers,
        fingerprint=fingerprint,
        daemon_pid=daemon_pid,
        daemon_alive=daemon_alive,
        bus_messages=bus_messages,
        bus_pending=bus_pending,
        clan_dir=str(clan_dir),
    )
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    """Publish clan profile to Agora."""
    clan_dir = _resolve_clan_dir(args)
    try:
        config, gateway, agora = _load_gateway(clan_dir)
    except FileNotFoundError:
        print("Error: No config found.", file=sys.stderr)
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
        print("Error: No config found.", file=sys.stderr)
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
    save_config(config, resolve_config_path(clan_dir))

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
        print("Error: No config found.", file=sys.stderr)
        return 1

    if not config.peers:
        print("No peers registered.")
        return 0

    print(f"Peers for {config.clan_id}:")
    for p in config.peers:
        print(f"  {p.clan_id:24s} status:{p.status:12s} added:{p.added}")
    return 0


def cmd_peer_invite(args: argparse.Namespace) -> int:
    """Generate a shareable invite for peering."""
    import base64

    clan_dir = _resolve_clan_dir(args)
    try:
        config, _, _ = _load_gateway(clan_dir)
    except FileNotFoundError:
        print("Error: No config found.", file=sys.stderr)
        return 1

    # Load signing public key (try keys/ then .keys/)
    keys_dir = clan_dir / "keys"
    if not keys_dir.exists():
        keys_dir = clan_dir / ".keys"
    pub_path = keys_dir / f"{config.clan_id}.pub"
    if not pub_path.exists():
        for f in keys_dir.glob("*.pub"):
            if f.name != "peers":
                pub_path = f
                break

    if not pub_path.exists():
        print("Error: No public key found.", file=sys.stderr)
        return 1

    pub_data = json.loads(pub_path.read_text())

    invite = {
        "hermes_invite": "1.0",
        "clan_id": config.clan_id,
        "display_name": config.display_name,
        "sign_pub": pub_data.get("ed25519_pub", pub_data.get("sign_public", "")),
        "dh_pub": pub_data.get("x25519_pub", pub_data.get("dh_public", "")),
        "protocol_version": config.protocol_version,
    }

    invite_json = json.dumps(invite, separators=(",", ":"))
    invite_b64 = base64.urlsafe_b64encode(invite_json.encode()).decode()

    print(f"HERMES Invite for {config.clan_id} ({config.display_name})")
    print()
    print("Share this token with your peer:")
    print(f"  hermes peer accept {invite_b64}")
    print()
    print("Or share the JSON:")
    print(json.dumps(invite, indent=2))
    return 0


def cmd_peer_accept(args: argparse.Namespace) -> int:
    """Accept a peer invite and add them as a peer."""
    import base64

    clan_dir = _resolve_clan_dir(args)
    try:
        config, _, _ = _load_gateway(clan_dir)
    except FileNotFoundError:
        print("Error: No config found.", file=sys.stderr)
        return 1

    token = args.invite_token

    # Decode invite: try base64 first, then file path, then raw JSON
    invite = None
    try:
        decoded = base64.urlsafe_b64decode(token)
        invite = json.loads(decoded)
    except Exception:
        pass

    if invite is None:
        token_path = Path(token)
        if token_path.exists():
            try:
                invite = json.loads(token_path.read_text())
            except Exception:
                pass

    if invite is None:
        try:
            invite = json.loads(token)
        except Exception:
            pass

    if not invite or "hermes_invite" not in invite:
        print("Error: Invalid invite token. Expected base64, file path, or JSON.", file=sys.stderr)
        return 1

    peer_clan_id = invite["clan_id"]
    display_name = invite.get("display_name", peer_clan_id)
    sign_pub = invite.get("sign_pub", "")
    dh_pub = invite.get("dh_pub", "")

    if not sign_pub or not dh_pub:
        print("Error: Invite missing public keys.", file=sys.stderr)
        return 1

    # Save peer public key
    peers_dir = clan_dir / "keys" / "peers"
    peers_dir.mkdir(parents=True, exist_ok=True)
    pub_file = peers_dir / f"{peer_clan_id}.pub"
    pub_data = {"sign_public": sign_pub, "dh_public": dh_pub}
    pub_file.write_text(json.dumps(pub_data, indent=2))

    # Add peer to config
    from hermes.config import PeerConfig
    new_peer = PeerConfig(
        clan_id=peer_clan_id,
        public_key_file=f"keys/peers/{peer_clan_id}.pub",
        status="active",
        added=str(date.today()),
    )

    # Check for duplicate
    existing = [p for p in config.peers if p.clan_id == peer_clan_id]
    if existing:
        print(f"Peer {peer_clan_id} already exists (status: {existing[0].status}). Updating keys.")
        config.peers = [p for p in config.peers if p.clan_id != peer_clan_id]

    config.peers.append(new_peer)

    from hermes.config import save_config
    config_path = clan_dir / "config.toml"
    if not config_path.exists():
        config_path = clan_dir / "gateway.json"
    save_config(config, config_path)

    print(f"Peer accepted: {peer_clan_id} ({display_name})")
    print(f"  Public key saved to: {pub_file}")
    print(f"  Status: active")
    print(f"  Protocol: {invite.get('protocol_version', 'unknown')}")
    return 0


def cmd_send(args: argparse.Namespace) -> int:
    """Send a message to a peer clan via Agora inbox."""
    clan_dir = _resolve_clan_dir(args)
    try:
        config, gateway, agora = _load_gateway(clan_dir)
    except FileNotFoundError:
        print("Error: No config found.", file=sys.stderr)
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
    from .terminal import print_inbox

    clan_dir = _resolve_clan_dir(args)
    try:
        config, gateway, agora = _load_gateway(clan_dir)
    except FileNotFoundError:
        print("Error: No config found.", file=sys.stderr)
        return 1

    messages = agora.read_inbox(config.clan_id)
    print_inbox(config.clan_id, messages)
    return 0


def cmd_bus(args: argparse.Namespace) -> int:
    """Show bus messages for the clan."""
    from .bus import filter_for_namespace, read_bus
    from .terminal import print_bus_messages

    clan_dir = _resolve_clan_dir(args)
    try:
        config, _, _ = _load_gateway(clan_dir)
    except FileNotFoundError:
        print("Error: No config found. Run 'hermes init' first.", file=sys.stderr)
        return 1

    bus_path = clan_dir / "bus.jsonl"
    if not bus_path.exists():
        print("Bus file not found.", file=sys.stderr)
        return 1

    messages = read_bus(bus_path)

    # --filter-type: keep only messages of a given type
    filter_type = getattr(args, "filter_type", None)
    if filter_type:
        messages = [m for m in messages if m.type.lower() == filter_type.lower()]

    # --pending: show only messages not ACKed by this clan's namespace
    pending = getattr(args, "pending", False)
    if pending:
        messages = filter_for_namespace(messages, config.clan_id)

    # --compact: output in compact JSONL format (ARC-5322 §14)
    compact = getattr(args, "compact", False)
    if compact:
        for m in messages:
            print(m.to_compact_jsonl())
        return 0

    # --expand: output in verbose JSONL format
    expand = getattr(args, "expand", False)
    if expand:
        for m in messages:
            print(m.to_jsonl())
        return 0

    print_bus_messages(messages, namespace=config.clan_id)
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    """Discover agents by capability on the Agora."""
    clan_dir = _resolve_clan_dir(args)
    try:
        config, _, agora = _load_gateway(clan_dir)
    except FileNotFoundError:
        print("Error: No config found.", file=sys.stderr)
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


def cmd_install(args: argparse.Namespace) -> int:
    """Run the full HERMES install sequence."""
    from .installer import run_install

    clan_dir = None
    if getattr(args, "dir", None) and args.dir != ".":
        clan_dir = Path(args.dir)

    result = run_install(
        clan_id=args.clan_id,
        display_name=args.display_name,
        clan_dir=clan_dir,
        gateway_url=getattr(args, "gateway_url", "") or "",
        relay_url=getattr(args, "relay_url", "") or "",
        skip_hooks=getattr(args, "skip_hooks", False),
        skip_service=getattr(args, "skip_service", False),
    )
    return 0 if result.success else 1


def cmd_uninstall(args: argparse.Namespace) -> int:
    """Run the HERMES uninstall sequence."""
    from .installer import run_uninstall

    clan_dir = None
    if getattr(args, "dir", None) and args.dir != ".":
        clan_dir = Path(args.dir)

    result = run_uninstall(
        clan_dir=clan_dir,
        purge=getattr(args, "purge", False),
        keep_hooks=getattr(args, "keep_hooks", False),
    )
    return 0 if result.success else 1


def _detect_installed_agents() -> list[str]:
    """Detect which AI agents are installed on this system.

    Returns list of adapter names whose target directories exist.
    """
    checks = {
        "claude-code": Path.home() / ".claude",
        "cursor": Path.home() / ".cursor",
        "opencode": Path.home() / ".config" / "opencode",
        "gemini": Path.home() / ".gemini",
    }
    return [name for name, path in sorted(checks.items()) if path.exists()]


def cmd_adapt(args: argparse.Namespace) -> int:
    """Run an adapter to generate agent-specific config from ~/.hermes/."""
    from .adapter import list_adapters, run_adapter

    # --list: show available adapters with detection status
    if getattr(args, "list_adapters", False):
        detected = _detect_installed_agents()
        print("  Available adapters:\n")
        for name in list_adapters():
            status = " (detected)" if name in detected else ""
            print(f"    {name}{status}")
        print("\n  Usage: hermes adapt <name>")
        print("         hermes adapt --all  (adapt all detected agents)")
        return 0

    # --all: adapt all detected agents
    if getattr(args, "adapt_all", False):
        detected = _detect_installed_agents()
        if not detected:
            print("  No AI agents detected. Install one first, then run hermes adapt --all.")
            return 1

        hermes_dir = Path(args.hermes_dir) if getattr(args, "hermes_dir", None) else None
        failed = False
        for name in detected:
            print(f"\n  ── {name} ──")
            try:
                result = run_adapter(name, hermes_dir=hermes_dir, target_dir=None)
                for step in result.steps:
                    marker = "[OK]" if result.success or "error" not in step.lower() else "[!!]"
                    print(f"  {marker} {step}")
                if result.errors:
                    for err in result.errors:
                        print(f"  [!!] {err}")
                    failed = True
            except KeyError as e:
                print(f"  [!!] {e}")
                failed = True

        adapted_count = len(detected) - (1 if failed else 0)
        print(f"\n  Adapted {adapted_count}/{len(detected)} agents: {', '.join(detected)}")
        return 1 if failed else 0

    adapter_name = getattr(args, "adapter_name", None)
    if adapter_name is None:
        print(f"Available adapters: {', '.join(list_adapters())}", file=sys.stderr)
        print("Usage: hermes adapt <name> | --list | --all", file=sys.stderr)
        return 1

    hermes_dir = None
    target_dir = None
    if getattr(args, "hermes_dir", None):
        hermes_dir = Path(args.hermes_dir)
    if getattr(args, "target_dir", None):
        target_dir = Path(args.target_dir)

    try:
        result = run_adapter(adapter_name, hermes_dir=hermes_dir, target_dir=target_dir)
    except KeyError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    for step in result.steps:
        marker = "[OK]" if result.success or "error" not in step.lower() else "[!!]"
        print(f"  {marker} {step}")

    if result.files_written:
        print(f"\n  Files written: {len(result.files_written)}")
        for f in result.files_written:
            print(f"    {f}")

    if result.symlinks_created:
        print(f"\n  Symlinks created: {len(result.symlinks_created)}")
        for s in result.symlinks_created:
            print(f"    {s}")

    if result.errors:
        print("\n  Errors:")
        for err in result.errors:
            print(f"    {err}")
        return 1

    print(f"\n  Adapter '{adapter_name}' completed successfully.")
    return 0


def cmd_agent(args: argparse.Namespace) -> int:
    """Manage registered agents (ARC-0369)."""
    from .asp import AgentRegistry

    clan_dir = _resolve_clan_dir(args)
    agents_dir = clan_dir / "agents"

    agent_cmd = getattr(args, "agent_command", None)

    if agent_cmd == "list":
        reg = AgentRegistry(agents_dir)
        reg.load_all()
        profiles = reg.all_profiles()

        if not profiles:
            print("No agents registered.")
            if not agents_dir.is_dir():
                print(f"  (Create {agents_dir}/ with agent profiles)")
            return 0

        print(f"Registered agents ({agents_dir}):\n")
        for p in profiles:
            status = "enabled" if p.enabled else "DISABLED"
            rules = len(p.dispatch_rules)
            caps = ", ".join(p.capabilities) if p.capabilities else "none"
            print(f"  {p.agent_id:20s} {p.role:10s} {status:8s} rules:{rules}  [{caps}]")

        if reg.errors:
            print(f"\n  Validation errors ({len(reg.errors)}):")
            for e in reg.errors:
                print(f"    {e}")
        return 0

    elif agent_cmd == "show":
        agent_id = getattr(args, "agent_id", None)
        if not agent_id:
            print("Usage: hermes agent show <agent-id>", file=sys.stderr)
            return 1

        reg = AgentRegistry(agents_dir)
        reg.load_all()
        profile = reg.get(agent_id)
        if profile is None:
            print(f"Agent '{agent_id}' not found.", file=sys.stderr)
            return 1

        import json as _json

        print(_json.dumps(profile.to_dict(), indent=2))
        return 0

    elif agent_cmd == "validate":
        reg = AgentRegistry(agents_dir)
        reg.load_all()

        valid = len(reg.all_profiles())
        errors = len(reg.errors)
        print(f"Validated: {valid} profiles OK, {errors} errors")
        for e in reg.errors:
            print(f"  [!!] {e}")
        return 1 if errors else 0

    elif agent_cmd == "dispatch-status":
        state_file = clan_dir / ".agent-node.state.json"
        if not state_file.exists():
            print("No agent-node state found. Is the daemon running?", file=sys.stderr)
            return 1

        state = json.loads(state_file.read_text())
        pending = state.get("pending_approvals", [])
        sched = state.get("scheduler_last_fire", {})

        print(f"Dispatch status ({clan_dir}):\n")
        print(f"  Pending approvals: {len(pending)}")
        for pa in pending:
            print(
                f"    {pa['agent_id']}:{pa['rule_id']} "
                f"escalated:{pa.get('escalation_ts', '?')} "
                f"timeout:{pa.get('timeout_hours', '?')}h"
            )

        print(f"\n  Scheduled rules: {len(sched)}")
        for key, ts in sched.items():
            print(f"    {key} last_fire:{ts:.0f}")
        return 0

    else:
        print("Usage: hermes agent <list|show|validate|dispatch-status>", file=sys.stderr)
        return 1


def cmd_config_migrate(args: argparse.Namespace) -> int:
    """Migrate gateway.json to config.toml."""
    clan_dir = _resolve_clan_dir(args)
    json_path = clan_dir / "gateway.json"

    if not json_path.exists():
        print("Error: No gateway.json to migrate.", file=sys.stderr)
        return 1

    if (clan_dir / "config.toml").exists():
        print("config.toml already exists. Migration skipped.")
        return 0

    toml_path = migrate_json_to_toml(json_path)
    print(f"Migrated: {json_path} -> {toml_path}")
    print("  gateway.json kept as backup.")
    print("  HERMES will now use config.toml (preferred over gateway.json).")
    return 0


def cmd_hook(args: argparse.Namespace) -> int:
    """Dispatch to hook handlers."""
    from .hooks import (
        cmd_hook_exit_reminder,
        cmd_hook_pull_on_prompt,
        cmd_hook_pull_on_start,
    )

    hook_commands = {
        "pull-on-start": cmd_hook_pull_on_start,
        "pull-on-prompt": cmd_hook_pull_on_prompt,
        "exit-reminder": cmd_hook_exit_reminder,
    }

    hook_cmd = getattr(args, "hook_command", None)
    if hook_cmd is None:
        print("Usage: hermes hook <pull-on-start|pull-on-prompt|exit-reminder>", file=sys.stderr)
        return 1

    hook_commands[hook_cmd]()
    return 0


def cmd_llm(args: argparse.Namespace) -> int:
    """Manage LLM backends."""
    from .llm import AdapterManager, create_adapter

    llm_cmd = getattr(args, "llm_command", None)
    if llm_cmd is None:
        print("Usage: hermes llm <list|status|test|usage>", file=sys.stderr)
        return 1

    clan_dir = _resolve_clan_dir(args)
    config = load_config(clan_dir)

    if llm_cmd == "list":
        if not config.llm_backends:
            print("No LLM backends configured.")
            print("Add [llm] section to config.toml or gateway.json.")
            return 0
        print(f"LLM backends ({len(config.llm_backends)}):")
        for b in config.llm_backends:
            status = "enabled" if b.enabled else "disabled"
            default = " (default)" if b.backend == config.llm_default_backend else ""
            model_info = f" model={b.model}" if b.model else ""
            print(f"  {b.backend}{model_info} [{status}]{default}")
            if b.api_key_env:
                import os

                has_key = bool(os.environ.get(b.api_key_env))
                key_status = "set" if has_key else "NOT SET"
                print(f"    env: {b.api_key_env} ({key_status})")
        return 0

    if llm_cmd == "status":
        if not config.llm_backends:
            print("No LLM backends configured.")
            return 0
        print("LLM backend health:")
        for b in config.llm_backends:
            if not b.enabled:
                print(f"  {b.backend}: disabled")
                continue
            try:
                kwargs: dict = {}
                if b.model:
                    kwargs["model"] = b.model
                if b.api_key_env:
                    kwargs["api_key_env"] = b.api_key_env
                adapter = create_adapter(b.backend, **kwargs)
                healthy = adapter.health_check()
                status = "healthy" if healthy else "unhealthy"
                symbol = "+" if healthy else "-"
                print(f"  [{symbol}] {adapter.name()}: {status}")
            except (ValueError, ImportError) as exc:
                print(f"  [-] {b.backend}: error ({exc})")
        return 0

    if llm_cmd == "test":
        backend_name = getattr(args, "backend", None)
        manager = AdapterManager()
        for b in config.llm_backends:
            if not b.enabled:
                continue
            try:
                kwargs = {}
                if b.model:
                    kwargs["model"] = b.model
                if b.api_key_env:
                    kwargs["api_key_env"] = b.api_key_env
                adapter = create_adapter(b.backend, **kwargs)
                manager.add(adapter)
            except (ValueError, ImportError):
                pass

        if backend_name:
            adapter = manager.get_by_name(backend_name)
        else:
            adapter = manager.get_healthy()

        if adapter is None:
            print("No healthy LLM backend available.", file=sys.stderr)
            return 1

        print(f"Testing {adapter.name()}...")
        resp = adapter.complete(
            "You are a HERMES protocol test bot. Respond briefly.",
            "What protocol are you part of?",
            max_tokens=100,
        )
        print(f"Response: {resp.text}")
        if resp.usage:
            print(f"Usage: {resp.usage}")
        return 0

    if llm_cmd == "usage":
        from .llm.telemetry import TokenTracker

        log_path = clan_dir / config.telemetry.log_path
        tracker = TokenTracker(file_path=log_path)
        loaded = tracker.load_from_file()

        backend_filter = getattr(args, "backend", None)
        since_filter = getattr(args, "since", None)
        export_fmt = getattr(args, "export", None)
        do_reset = getattr(args, "reset", False)

        if do_reset:
            tracker.reset_file()
            print("  Telemetry log cleared.")
            return 0

        summary = tracker.summary(backend=backend_filter, since=since_filter)

        if export_fmt == "csv":
            print("backend,model,input_tokens,output_tokens,total_tokens,cost_usd")
            for e in tracker.events:
                print(
                    f"{e.backend},{e.model},{e.input_tokens},{e.output_tokens},{e.total_tokens},{e.cost_usd:.6f}"
                )
            return 0

        if summary.event_count == 0:
            print("  No telemetry data recorded yet.")
            print(f"  Log path: {log_path}")
            return 0

        # Header
        print("\n  Token Usage Summary")
        print("  " + "─" * 72)
        print(
            f"  {'Backend':<12} {'Model':<24} {'Input':>10} {'Output':>10} {'Total':>10} {'Cost':>10}"
        )
        print("  " + "─" * 72)

        for model_name, mu in sorted(summary.by_model.items()):
            # Find the backend for this model
            backend_name = ""
            for e in tracker.events:
                if e.model == model_name:
                    backend_name = e.backend
                    break
            print(
                f"  {backend_name:<12} {model_name:<24} "
                f"{mu.input_tokens:>10,} {mu.output_tokens:>10,} "
                f"{mu.total_tokens:>10,} ${mu.cost_usd:>9.4f}"
            )

        print("  " + "─" * 72)
        print(
            f"  {'TOTAL':<12} {'':<24} "
            f"{summary.total_input:>10,} {summary.total_output:>10,} "
            f"{summary.total_tokens:>10,} ${summary.total_cost_usd:>9.4f}"
        )

        # Budget info
        budget = config.telemetry.token_budget_weekly
        if budget > 0:
            pct = (summary.total_tokens / budget) * 100
            print(f"\n  Budget: {pct:.0f}% of {budget:,} weekly tokens used")

        print(f"\n  Events: {summary.event_count} ({loaded} from file)")
        if summary.first_event:
            print(f"  Period: {summary.first_event} → {summary.last_event}")
        print()
        return 0

    return 1


def _add_dir_arg(parser: argparse.ArgumentParser) -> None:
    """Add --dir argument to a subparser."""
    parser.add_argument("--dir", default=".", help="Clan directory (default: current)")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    from hermes import __version__

    parser = argparse.ArgumentParser(
        prog="hermes",
        description="HERMES Gateway CLI — Inter-clan communication",
    )
    parser.add_argument("--version", action="version", version=f"hermes {__version__}")
    sub = parser.add_subparsers(dest="command")

    # init
    p_init = sub.add_parser("init", help="Initialize a new clan")
    p_init.add_argument("clan_id", help="Unique clan identifier")
    p_init.add_argument("display_name", help="Human-readable clan name")
    p_init.add_argument("--agora-url", default="", help="Agora directory URL")
    p_init.add_argument(
        "--format", choices=["json", "toml"], default="json", help="Config format (default: json)"
    )
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
    p_peer_invite = peer_sub.add_parser("invite", help="Generate a shareable invite for peering")
    _add_dir_arg(p_peer_invite)
    p_peer_accept = peer_sub.add_parser("accept", help="Accept a peer invite")
    p_peer_accept.add_argument("invite_token", help="Base64 invite token or path to invite JSON file")
    _add_dir_arg(p_peer_accept)

    # send
    p_send = sub.add_parser("send", help="Send message to peer")
    p_send.add_argument("target_clan", help="Target clan ID")
    p_send.add_argument("message", help="Message payload")
    # Note: --compact not supported for send (uses Agora JSON transport, not bus compact encoding)
    _add_dir_arg(p_send)

    # inbox
    p_inbox = sub.add_parser("inbox", help="Read inbox messages")
    _add_dir_arg(p_inbox)

    # bus
    p_bus = sub.add_parser("bus", help="Show bus messages")
    p_bus.add_argument(
        "--filter-type",
        default=None,
        dest="filter_type",
        help="Filter by message type (e.g. STATE, alert)",
    )
    p_bus.add_argument(
        "--pending", action="store_true", help="Show only messages not yet ACKed by this clan"
    )
    p_bus.add_argument(
        "--compact", action="store_true", help="Output in compact JSONL format (ARC-5322 §14)"
    )
    p_bus.add_argument("--expand", action="store_true", help="Output in verbose JSONL format")
    _add_dir_arg(p_bus)

    # discover
    p_discover = sub.add_parser("discover", help="Discover agents by capability")
    p_discover.add_argument("capability", help="Capability path to search")
    _add_dir_arg(p_discover)

    # adapt
    p_adapt = sub.add_parser("adapt", help="Generate agent config from ~/.hermes/")
    p_adapt.add_argument(
        "adapter_name", nargs="?", default=None, help="Adapter name (e.g. claude-code, gemini)"
    )
    p_adapt.add_argument(
        "--list", action="store_true", dest="list_adapters", help="List available adapters"
    )
    p_adapt.add_argument(
        "--all", action="store_true", dest="adapt_all", help="Adapt all detected agents"
    )
    p_adapt.add_argument(
        "--hermes-dir",
        default=None,
        dest="hermes_dir",
        help="HERMES directory (default: ~/.hermes/)",
    )
    p_adapt.add_argument(
        "--target-dir",
        default=None,
        dest="target_dir",
        help="Target agent directory (default: adapter-specific)",
    )

    # config
    p_config = sub.add_parser("config", help="Configuration management")
    config_sub = p_config.add_subparsers(dest="config_command")
    p_config_migrate = config_sub.add_parser("migrate", help="Migrate gateway.json to config.toml")
    _add_dir_arg(p_config_migrate)

    # install
    p_install = sub.add_parser("install", help="One-command HERMES setup")
    p_install.add_argument(
        "--clan-id", required=True, dest="clan_id", help="Unique clan identifier"
    )
    p_install.add_argument(
        "--display-name", required=True, dest="display_name", help="Human-readable clan name"
    )
    p_install.add_argument(
        "--gateway-url", default="", dest="gateway_url", help="Remote gateway URL"
    )
    p_install.add_argument(
        "--relay-url", default="", dest="relay_url", help="Relay URL for bilateral exchange"
    )
    p_install.add_argument(
        "--skip-hooks",
        action="store_true",
        dest="skip_hooks",
        help="Skip Claude Code hooks installation",
    )
    p_install.add_argument(
        "--skip-service",
        action="store_true",
        dest="skip_service",
        help="Skip OS service installation",
    )
    _add_dir_arg(p_install)

    # uninstall
    p_uninstall = sub.add_parser("uninstall", help="Remove HERMES installation")
    p_uninstall.add_argument(
        "--purge", action="store_true", help="Delete clan directory and all data"
    )
    p_uninstall.add_argument(
        "--keep-hooks", action="store_true", dest="keep_hooks", help="Preserve Claude Code hooks"
    )
    _add_dir_arg(p_uninstall)

    # hook
    p_hook = sub.add_parser("hook", help="Claude Code hook handlers")
    hook_sub = p_hook.add_subparsers(dest="hook_command")
    hook_sub.add_parser("pull-on-start", help="SessionStart hook")
    hook_sub.add_parser("pull-on-prompt", help="UserPromptSubmit hook")
    hook_sub.add_parser("exit-reminder", help="Stop hook")

    # agent (ARC-0369)
    p_agent = sub.add_parser("agent", help="Manage registered agents (ARC-0369)")
    agent_sub = p_agent.add_subparsers(dest="agent_command")
    p_agent_list = agent_sub.add_parser("list", help="List registered agents")
    _add_dir_arg(p_agent_list)
    p_agent_show = agent_sub.add_parser("show", help="Show agent profile")
    p_agent_show.add_argument("agent_id", help="Agent ID to show")
    _add_dir_arg(p_agent_show)
    p_agent_validate = agent_sub.add_parser("validate", help="Validate all profiles")
    _add_dir_arg(p_agent_validate)
    p_agent_dispatch = agent_sub.add_parser("dispatch-status", help="Show dispatch status")
    _add_dir_arg(p_agent_dispatch)

    # daemon (ARC-4601)
    p_daemon = sub.add_parser("daemon", help="Manage Agent Node daemon")
    daemon_sub = p_daemon.add_subparsers(dest="daemon_command")

    p_daemon_start = daemon_sub.add_parser("start", help="Start agent node")
    p_daemon_start.add_argument(
        "--foreground",
        action="store_true",
        help="Run in foreground (for process managers)",
    )
    _add_dir_arg(p_daemon_start)

    p_daemon_stop = daemon_sub.add_parser("stop", help="Stop agent node")
    _add_dir_arg(p_daemon_stop)

    p_daemon_status = daemon_sub.add_parser("status", help="Show agent node status")
    _add_dir_arg(p_daemon_status)

    # hub (ARC-4601 §15)
    p_hub = sub.add_parser("hub", help="Manage Hub server (ARC-4601 §15)")
    hub_sub = p_hub.add_subparsers(dest="hub_command")

    p_hub_start = hub_sub.add_parser("start", help="Start Hub server")
    p_hub_start.add_argument(
        "--foreground",
        action="store_true",
        help="Run in foreground (for process managers)",
    )
    _add_dir_arg(p_hub_start)

    p_hub_stop = hub_sub.add_parser("stop", help="Stop Hub server")
    _add_dir_arg(p_hub_stop)

    p_hub_status = hub_sub.add_parser("status", help="Show Hub status")
    _add_dir_arg(p_hub_status)

    p_hub_init = hub_sub.add_parser("init", help="Generate hub-peers.json from peer registry")
    p_hub_init.add_argument("--force", action="store_true", help="Overwrite existing file")
    _add_dir_arg(p_hub_init)

    p_hub_peers = hub_sub.add_parser("peers", help="List registered peers")
    _add_dir_arg(p_hub_peers)

    # llm (Multi-LLM adapters)
    p_llm = sub.add_parser("llm", help="Manage LLM backends")
    llm_sub = p_llm.add_subparsers(dest="llm_command")

    p_llm_list = llm_sub.add_parser("list", help="List configured LLM backends")
    _add_dir_arg(p_llm_list)

    p_llm_status = llm_sub.add_parser("status", help="Show LLM backend health status")
    _add_dir_arg(p_llm_status)

    p_llm_test = llm_sub.add_parser("test", help="Send a test prompt to a backend")
    p_llm_test.add_argument("--backend", default=None, help="Backend name (default: first healthy)")
    _add_dir_arg(p_llm_test)

    p_llm_usage = llm_sub.add_parser("usage", help="Show token usage telemetry")
    p_llm_usage.add_argument("--since", default=None, help="Filter events from date (ISO format)")
    p_llm_usage.add_argument("--backend", default=None, help="Filter by backend (claude, gemini)")
    p_llm_usage.add_argument("--export", default=None, choices=["csv"], help="Export format")
    p_llm_usage.add_argument("--reset", action="store_true", help="Clear telemetry log")
    _add_dir_arg(p_llm_usage)

    # mcp
    p_mcp = sub.add_parser("mcp", help="MCP server for Claude Code integration")
    mcp_sub = p_mcp.add_subparsers(dest="mcp_command")

    p_mcp_serve = mcp_sub.add_parser("serve", help="Start the hermes-bus MCP server (stdio)")
    p_mcp_serve.add_argument(
        "--hermes-dir", default=None, help="Clan directory (default: ~/.hermes)"
    )

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
        "bus": cmd_bus,
        "discover": cmd_discover,
        "install": cmd_install,
        "uninstall": cmd_uninstall,
        "adapt": cmd_adapt,
    }

    if args.command == "hook":
        return cmd_hook(args)

    if args.command == "config":
        config_commands = {"migrate": cmd_config_migrate}
        if args.config_command is None:
            parser.parse_args(["config", "--help"])
            return 0
        return config_commands[args.config_command](args)

    if args.command == "peer":
        peer_commands = {
            "add": cmd_peer_add,
            "list": cmd_peer_list,
            "invite": cmd_peer_invite,
            "accept": cmd_peer_accept,
        }
        if args.peer_command is None:
            parser.parse_args(["peer", "--help"])
            return 0
        return peer_commands[args.peer_command](args)

    if args.command == "agent":
        return cmd_agent(args)

    if args.command == "daemon":
        from .agent import cmd_daemon_start, cmd_daemon_status, cmd_daemon_stop

        clan_dir = _resolve_clan_dir(args)
        daemon_commands = {
            "start": lambda: cmd_daemon_start(
                clan_dir, foreground=getattr(args, "foreground", True)
            ),
            "stop": lambda: cmd_daemon_stop(clan_dir),
            "status": lambda: cmd_daemon_status(clan_dir),
        }
        if args.daemon_command is None:
            parser.parse_args(["daemon", "--help"])
            return 0
        return daemon_commands[args.daemon_command]()

    if args.command == "llm":
        return cmd_llm(args)

    if args.command == "mcp":
        if getattr(args, "mcp_command", None) == "serve":
            import os
            if args.hermes_dir:
                os.environ["HERMES_DIR"] = args.hermes_dir
            from .mcp_server import main as mcp_main
            mcp_main()
            return 0
        parser.parse_args(["mcp", "--help"])
        return 0

    if args.command == "hub":
        from .hub import cmd_hub_init, cmd_hub_peers, cmd_hub_start, cmd_hub_status, cmd_hub_stop

        hub_dir = _resolve_clan_dir(args)
        hub_commands = {
            "init": lambda: cmd_hub_init(hub_dir, force=getattr(args, "force", False)),
            "start": lambda: cmd_hub_start(hub_dir, foreground=getattr(args, "foreground", True)),
            "stop": lambda: cmd_hub_stop(hub_dir),
            "status": lambda: cmd_hub_status(hub_dir),
            "peers": lambda: cmd_hub_peers(hub_dir),
        }
        if args.hub_command is None:
            parser.parse_args(["hub", "--help"])
            return 0
        return hub_commands[args.hub_command]()

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
