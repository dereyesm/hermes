"""HERMES Agent Service Platform — ARC-0369 Reference Implementation.

F1: Bus Convergence — message classification (internal/outbound/inbound/expired).
F2: Agent Registration — declarative profiles, registry, dispatch rule matching.

Extends the Agent Node (ARC-4601) with structured agent management.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any

from .message import Message

logger = logging.getLogger("hermes.asp")


# ---------------------------------------------------------------------------
# F1: Bus Convergence — Message Classification
# ---------------------------------------------------------------------------


class MessageCategory(str, Enum):
    """ARC-0369 Section 6.2 message categories."""

    INTERNAL = "internal"
    OUTBOUND = "outbound"
    INBOUND = "inbound"
    EXPIRED = "expired"


class MessageClassifier:
    """Classifies bus messages per ARC-0369 Section 6.

    Determines if a message is internal (stays in clan), outbound (crosses
    gateway), inbound (received from external), or expired (TTL exceeded).
    """

    def __init__(
        self,
        local_namespaces: set[str],
        internal_only_namespaces: set[str] | None = None,
        gateway_namespace: str = "gateway",
    ):
        self.local_namespaces = {ns.lower() for ns in local_namespaces}
        self.internal_only = {
            ns.lower() for ns in (internal_only_namespaces or set())
        }
        self.gateway_namespace = gateway_namespace.lower()

    def classify(self, message: Message, today: date | None = None) -> MessageCategory:
        """Classify a message into exactly one category (ARC-0369 §6.2).

        Args:
            message: The bus message to classify.
            today: Override for testing (defaults to date.today()).
        """
        if today is None:
            today = date.today()

        # Check TTL expiry first
        age_days = (today - message.ts).days
        if age_days > message.ttl:
            return MessageCategory.EXPIRED

        src = message.src.lower()
        dst = message.dst if message.dst == "*" else message.dst.lower()

        # Inbound: written by gateway
        if src == self.gateway_namespace:
            return MessageCategory.INBOUND

        # Internal-only source: always internal regardless of dst (§6.4)
        if src in self.internal_only:
            return MessageCategory.INTERNAL

        # Broadcast is always internal
        if dst == "*":
            return MessageCategory.INTERNAL

        # Local destination = internal
        if dst in self.local_namespaces:
            return MessageCategory.INTERNAL

        # Otherwise outbound
        return MessageCategory.OUTBOUND

    def verify_source(self, message: Message, registered_agent_ids: set[str] | None = None) -> bool:
        """Verify source integrity per ARC-0369 §6.3.

        Returns True if src is a known local namespace or registered agent.
        """
        src = message.src.lower()
        known = self.local_namespaces | {self.gateway_namespace}
        if registered_agent_ids:
            known |= {aid.lower() for aid in registered_agent_ids}
        return src in known

    def is_internal_only_src(self, message: Message) -> bool:
        """Check if message src is in the internal-only list (§6.4)."""
        return message.src.lower() in self.internal_only


# ---------------------------------------------------------------------------
# F2: Agent Registration — Data Structures
# ---------------------------------------------------------------------------


_AGENT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_VALID_ROLES = {"sensor", "worker", "platform"}
_VALID_TRIGGER_TYPES = {"event-driven", "scheduled"}


class AgentProfileError(Exception):
    """Raised when an agent profile fails validation."""


@dataclass(frozen=True)
class DispatchTrigger:
    """A trigger condition for a dispatch rule (ARC-0369 §7.3.2)."""

    type: str  # "event-driven" | "scheduled"
    match_type: str | None = None
    match_src: str | None = None
    match_msg_prefix: str | None = None
    cron: str | None = None


@dataclass(frozen=True)
class DispatchRule:
    """A dispatch rule within an agent profile (ARC-0369 §7.3.2)."""

    rule_id: str
    trigger: DispatchTrigger
    command_template: str | None = None
    approval_required: bool = False
    approval_timeout_hours: int = 24


@dataclass(frozen=True)
class ResourceLimits:
    """Per-agent resource limits (ARC-0369 §7.3.3)."""

    max_turns: int | None = None
    timeout_seconds: int | None = None
    allowed_tools: tuple[str, ...] = ()
    max_concurrent: int = 1


@dataclass(frozen=True)
class AgentProfile:
    """A registered agent profile per ARC-0369 §7.2.

    Immutable after loading. The daemon resolves dispatch rules
    against incoming messages to decide which agent to invoke.
    """

    agent_id: str
    display_name: str
    version: str
    role: str  # "sensor" | "worker" | "platform"
    description: str
    capabilities: tuple[str, ...]
    dispatch_rules: tuple[DispatchRule, ...]
    resource_limits: ResourceLimits
    enabled: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any], filename: str | None = None) -> AgentProfile:
        """Parse and validate an agent profile from a dict.

        Args:
            data: The parsed JSON data.
            filename: Expected filename (without .json) to validate agent_id match.

        Raises:
            AgentProfileError: If validation fails.
        """
        # Required fields
        for key in ("agent_id", "display_name", "version", "role",
                     "description", "capabilities", "dispatch_rules", "enabled"):
            if key not in data:
                raise AgentProfileError(f"Missing required field: '{key}'")

        agent_id = str(data["agent_id"])

        # Validate agent_id format
        if not _AGENT_ID_PATTERN.match(agent_id):
            raise AgentProfileError(
                f"Invalid agent_id '{agent_id}': must match [a-z0-9][a-z0-9-]*"
            )

        # Validate filename match (§7.4 rule 1)
        if filename is not None and agent_id != filename:
            raise AgentProfileError(
                f"agent_id '{agent_id}' does not match filename '{filename}'"
            )

        # Validate role (§7.4 rule 2)
        role = str(data["role"])
        if role not in _VALID_ROLES:
            raise AgentProfileError(
                f"Invalid role '{role}': must be one of {_VALID_ROLES}"
            )

        # Validate dispatch_rules is a list (§7.4 rule 3)
        raw_rules = data["dispatch_rules"]
        if not isinstance(raw_rules, list):
            raise AgentProfileError("dispatch_rules must be an array")

        # Parse dispatch rules
        rules = []
        for i, raw_rule in enumerate(raw_rules):
            rules.append(_parse_dispatch_rule(raw_rule, i))

        # Parse resource limits
        raw_limits = data.get("resource_limits", {})
        limits = ResourceLimits(
            max_turns=raw_limits.get("max_turns"),
            timeout_seconds=raw_limits.get("timeout_seconds"),
            allowed_tools=tuple(raw_limits.get("allowed_tools", [])),
            max_concurrent=int(raw_limits.get("max_concurrent", 1)),
        )

        return cls(
            agent_id=agent_id,
            display_name=str(data["display_name"]),
            version=str(data["version"]),
            role=role,
            description=str(data["description"]),
            capabilities=tuple(data["capabilities"]),
            dispatch_rules=tuple(rules),
            resource_limits=limits,
            enabled=bool(data["enabled"]),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "agent_id": self.agent_id,
            "display_name": self.display_name,
            "version": self.version,
            "role": self.role,
            "description": self.description,
            "capabilities": list(self.capabilities),
            "dispatch_rules": [
                {
                    "rule_id": r.rule_id,
                    "trigger": {
                        "type": r.trigger.type,
                        **({"match_type": r.trigger.match_type} if r.trigger.match_type else {}),
                        **({"match_src": r.trigger.match_src} if r.trigger.match_src else {}),
                        **({"match_msg_prefix": r.trigger.match_msg_prefix} if r.trigger.match_msg_prefix else {}),
                        **({"cron": r.trigger.cron} if r.trigger.cron else {}),
                    },
                    "approval_required": r.approval_required,
                    **({"approval_timeout_hours": r.approval_timeout_hours} if r.approval_required else {}),
                    **({"command_template": r.command_template} if r.command_template else {}),
                }
                for r in self.dispatch_rules
            ],
            "resource_limits": {
                **({"max_turns": self.resource_limits.max_turns} if self.resource_limits.max_turns else {}),
                **({"timeout_seconds": self.resource_limits.timeout_seconds} if self.resource_limits.timeout_seconds else {}),
                **({"allowed_tools": list(self.resource_limits.allowed_tools)} if self.resource_limits.allowed_tools else {}),
                "max_concurrent": self.resource_limits.max_concurrent,
            },
            "enabled": self.enabled,
        }


def _parse_dispatch_rule(data: dict, index: int) -> DispatchRule:
    """Parse and validate a single dispatch rule."""
    if "rule_id" not in data:
        raise AgentProfileError(f"dispatch_rules[{index}]: missing 'rule_id'")

    trigger_data = data.get("trigger", {})
    trigger_type = trigger_data.get("type")

    if trigger_type not in _VALID_TRIGGER_TYPES:
        raise AgentProfileError(
            f"dispatch_rules[{index}]: invalid trigger type '{trigger_type}'"
        )

    # Validate event-driven rules (§7.4 rule 4)
    if trigger_type == "event-driven" and not trigger_data.get("match_type"):
        raise AgentProfileError(
            f"dispatch_rules[{index}]: event-driven trigger requires 'match_type'"
        )

    # Validate scheduled rules (§7.4 rule 5)
    if trigger_type == "scheduled" and not trigger_data.get("cron"):
        raise AgentProfileError(
            f"dispatch_rules[{index}]: scheduled trigger requires 'cron'"
        )

    # Validate approval_required (§7.4 rule 6)
    if "approval_required" not in data:
        raise AgentProfileError(
            f"dispatch_rules[{index}]: missing 'approval_required'"
        )
    if not isinstance(data["approval_required"], bool):
        raise AgentProfileError(
            f"dispatch_rules[{index}]: 'approval_required' must be boolean"
        )

    trigger = DispatchTrigger(
        type=trigger_type,
        match_type=trigger_data.get("match_type"),
        match_src=trigger_data.get("match_src"),
        match_msg_prefix=trigger_data.get("match_msg_prefix"),
        cron=trigger_data.get("cron"),
    )

    return DispatchRule(
        rule_id=str(data["rule_id"]),
        trigger=trigger,
        command_template=data.get("command_template"),
        approval_required=data["approval_required"],
        approval_timeout_hours=int(data.get("approval_timeout_hours", 24)),
    )


# ---------------------------------------------------------------------------
# F2: Agent Registry
# ---------------------------------------------------------------------------


class AgentRegistry:
    """Loads and manages agent profiles from the agents/ directory.

    Per ARC-0369 §7.1: scans agents/ at startup, validates profiles,
    provides lookup and dispatch rule matching.
    """

    def __init__(self, agents_dir: Path):
        self.agents_dir = Path(agents_dir)
        self._registry: dict[str, AgentProfile] = {}
        self._errors: list[str] = []

    def load_all(self) -> None:
        """Scan agents/ directory and load all *.json profiles.

        Failed profiles are logged and skipped (§7.4).
        """
        self._registry.clear()
        self._errors.clear()

        if not self.agents_dir.is_dir():
            logger.debug("No agents/ directory at %s", self.agents_dir)
            return

        for profile_path in sorted(self.agents_dir.glob("*.json")):
            filename = profile_path.stem
            try:
                with open(profile_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                profile = AgentProfile.from_dict(data, filename=filename)
                self._registry[profile.agent_id] = profile
                logger.info("Loaded agent profile: %s", profile.agent_id)
            except (json.JSONDecodeError, AgentProfileError) as e:
                error_msg = f"Failed to load {profile_path.name}: {e}"
                self._errors.append(error_msg)
                logger.error(error_msg)

    @property
    def errors(self) -> list[str]:
        """Validation errors from the last load."""
        return list(self._errors)

    def get(self, agent_id: str) -> AgentProfile | None:
        """Look up an agent profile by ID."""
        return self._registry.get(agent_id)

    def all_profiles(self) -> list[AgentProfile]:
        """Return all loaded profiles (including disabled)."""
        return list(self._registry.values())

    def all_enabled(self) -> list[AgentProfile]:
        """Return only enabled agent profiles."""
        return [p for p in self._registry.values() if p.enabled]

    def all_agent_ids(self) -> set[str]:
        """Return the set of all registered agent IDs."""
        return set(self._registry.keys())

    def find_matching_rules(
        self, message: Message
    ) -> list[tuple[AgentProfile, DispatchRule]]:
        """Find all (agent, rule) pairs whose trigger matches this message.

        Only considers enabled agents with event-driven rules.
        Scheduled rules are not matched here (handled by scheduler).
        """
        matches = []
        for profile in self.all_enabled():
            for rule in profile.dispatch_rules:
                if rule.trigger.type != "event-driven":
                    continue
                if _trigger_matches(rule.trigger, message):
                    matches.append((profile, rule))
        return matches

    def hot_reload(self) -> int:
        """Reload profiles from disk. Returns count of changes.

        Existing profiles are updated, new ones added, removed ones deleted.
        """
        old_ids = set(self._registry.keys())
        self.load_all()
        new_ids = set(self._registry.keys())
        changes = len(old_ids ^ new_ids)  # symmetric difference
        return changes


def _trigger_matches(trigger: DispatchTrigger, message: Message) -> bool:
    """Check if an event-driven trigger matches a bus message."""
    # match_type is required for event-driven
    if trigger.match_type and message.type.lower() != trigger.match_type.lower():
        return False

    # match_src is optional
    if trigger.match_src and message.src.lower() != trigger.match_src.lower():
        return False

    # match_msg_prefix is optional
    if trigger.match_msg_prefix and not message.msg.startswith(trigger.match_msg_prefix):
        return False

    return True
