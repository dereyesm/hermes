"""HERMES Agora Directory Client — Git-based clan discovery.

Reference implementation for the Agora directory per ARC-2606.
Uses a local folder structure for profiles, inboxes, and attestations.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


class AgoraDirectory:
    """Client for a local Agora directory (Git-based).

    The Agora directory is a folder structure:
        profiles/<clan-id>.json     — clan profiles
        inbox/<clan-id>/<msg>.json  — message drops
        attestations/<id>.json      — attestation records
        quest_log/                  — quest history
    """

    def __init__(self, agora_path: str | Path) -> None:
        self.path = Path(agora_path)

    def ensure_structure(self) -> None:
        """Create the Agora directory structure if it doesn't exist."""
        (self.path / "profiles").mkdir(parents=True, exist_ok=True)
        (self.path / "inbox").mkdir(exist_ok=True)
        (self.path / "attestations").mkdir(exist_ok=True)
        (self.path / "quest_log").mkdir(exist_ok=True)

    def publish_profile(self, profile: dict[str, Any]) -> Path:
        """Publish a clan profile to the Agora directory.

        The profile dict must contain a ``clan_id`` key.
        Returns the path to the written profile file.
        """
        clan_id = profile["clan_id"]
        profile_path = self.path / "profiles" / f"{clan_id}.json"
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path.write_text(
            json.dumps(profile, indent=2, ensure_ascii=False) + "\n"
        )
        return profile_path

    def read_profile(self, clan_id: str) -> dict[str, Any] | None:
        """Read a clan profile from the Agora directory.

        Returns None if the profile does not exist.
        """
        profile_path = self.path / "profiles" / f"{clan_id}.json"
        if not profile_path.exists():
            return None
        return json.loads(profile_path.read_text(encoding="utf-8"))

    def list_clans(self) -> list[str]:
        """List all clan IDs with profiles in the Agora."""
        profiles_dir = self.path / "profiles"
        if not profiles_dir.exists():
            return []
        return sorted(p.stem for p in profiles_dir.glob("*.json"))

    def send_message(self, target_clan: str, message: dict[str, Any]) -> Path:
        """Drop a message in a clan's inbox.

        Returns the path to the written message file.
        """
        inbox_dir = self.path / "inbox" / target_clan
        inbox_dir.mkdir(parents=True, exist_ok=True)

        msg_type = message.get("type", "msg")
        seq = len(list(inbox_dir.glob("*.json")))
        msg_id = f"{date.today().isoformat()}-{msg_type}-{seq:04d}"
        msg_path = inbox_dir / f"{msg_id}.json"
        msg_path.write_text(
            json.dumps(message, indent=2, ensure_ascii=False) + "\n"
        )
        return msg_path

    def read_inbox(self, clan_id: str) -> list[dict[str, Any]]:
        """Read all messages from a clan's inbox, sorted by filename."""
        inbox_dir = self.path / "inbox" / clan_id
        if not inbox_dir.exists():
            return []

        messages = []
        for msg_file in sorted(inbox_dir.glob("*.json")):
            messages.append(json.loads(msg_file.read_text(encoding="utf-8")))
        return messages

    def clear_inbox(self, clan_id: str) -> int:
        """Clear a clan's inbox. Returns number of messages removed."""
        inbox_dir = self.path / "inbox" / clan_id
        if not inbox_dir.exists():
            return 0

        count = 0
        for msg_file in inbox_dir.glob("*.json"):
            msg_file.unlink()
            count += 1
        return count

    def discover(self, capability: str) -> list[dict[str, Any]]:
        """Find agents with a specific capability across all clans.

        Returns a list of matches with clan_id, agent alias, capabilities,
        and resonance score.  Simple prefix matching on capability paths.
        Results are sorted by resonance descending.
        """
        matches = []
        for clan_id in self.list_clans():
            profile = self.read_profile(clan_id)
            if profile is None:
                continue
            for agent in profile.get("agents", []):
                for cap in agent.get("capabilities", []):
                    if cap.startswith(capability) or capability.startswith(cap):
                        matches.append({
                            "clan_id": clan_id,
                            "agent_alias": agent["alias"],
                            "capabilities": agent["capabilities"],
                            "resonance": agent.get("resonance", 0),
                        })
                        break  # Don't duplicate agent in results

        # Sort by resonance descending
        matches.sort(key=lambda m: m.get("resonance", 0), reverse=True)
        return matches

    def store_attestation(self, attestation: dict[str, Any]) -> Path:
        """Store an attestation in the Agora.

        Returns the path to the written attestation file.
        """
        att_dir = self.path / "attestations"
        att_dir.mkdir(parents=True, exist_ok=True)
        att_id = attestation.get("id", f"att-{date.today().isoformat()}")
        att_path = att_dir / f"{att_id}.json"
        att_path.write_text(
            json.dumps(attestation, indent=2, ensure_ascii=False) + "\n"
        )
        return att_path
