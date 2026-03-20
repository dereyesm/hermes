"""HERMES Agent Service Platform — ARC-0369 Reference Implementation.

F1: Bus Convergence — message classification (internal/outbound/inbound/expired).
F2: Agent Registration — declarative profiles, registry, dispatch rule matching.
F3: Dispatch Protocol — trigger evaluation, approval gates, scheduling, command rendering.
F4: Agent Lifecycle — per-agent state tracking with transition history.
F5: Notification Flow — throttled notifications with suppression rules.

Extends the Agent Node (ARC-4601) with structured agent management.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
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


# ---------------------------------------------------------------------------
# F3: Dispatch Protocol — ARC-0369 §8
# ---------------------------------------------------------------------------

# Priority tiers for trigger evaluation (§8.8)
_TYPE_PRIORITY = {"alert": 0, "dispatch": 1, "event": 2, "state": 3}


class AgentState(str, Enum):
    """ARC-0369 §9.1 agent lifecycle states."""

    INACTIVE = "inactive"
    ACTIVE = "active"
    PENDING = "pending"
    RUNNING = "running"
    IDLE = "idle"
    FAILED = "failed"
    REMOVED = "removed"


class DispatchOutcome(str, Enum):
    """Outcome of a dispatch attempt per §8.7."""

    DISPATCHED = "dispatched"
    APPROVAL_PENDING = "approval_pending"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_TIMEOUT = "approval_timeout"
    CAPACITY_EXCEEDED = "capacity_exceeded"
    DISABLED_AGENT = "disabled_agent"
    NO_RULE_MATCH = "no_rule_match"


class QueueOverflow(str, Enum):
    """§8.4 queue_overflow policy."""

    DROP_NEWEST = "drop-newest"
    DROP_OLDEST = "drop-oldest"


@dataclass(frozen=True)
class DispatchDecision:
    """Output of DispatchEngine.evaluate_message() for one (agent, rule) pair.

    The daemon feeds this to its ARC-4601 Dispatcher. F3 produces decisions;
    ARC-4601 executes them.
    """

    agent_id: str
    rule_id: str
    outcome: DispatchOutcome
    command: list[str] = field(default_factory=list)
    trigger_msg: Message | None = None
    payload: str = ""
    approval_key: str | None = None


@dataclass
class PendingApproval:
    """A dispatch awaiting operator approval (§8.5, §11.3).

    Stored in agent-node.state.json under "pending_approvals".
    """

    agent_id: str
    rule_id: str
    trigger_ts: str
    trigger_msg_hash: str  # SHA-256 hex digest of msg field
    escalation_ts: str  # ISO datetime when APPROVAL_REQUIRED was written
    timeout_hours: int
    payload: str


class ConcurrencyTracker:
    """Tracks active invocation counts per agent to enforce max_concurrent.

    Pure dict, no I/O. The daemon increments/decrements as it
    spawns and completes dispatch slots.
    """

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def increment(self, agent_id: str) -> None:
        """Increment the active count for an agent."""
        self._counts[agent_id] = self._counts.get(agent_id, 0) + 1

    def decrement(self, agent_id: str) -> None:
        """Decrement the active count (floors at 0)."""
        current = self._counts.get(agent_id, 0)
        self._counts[agent_id] = max(0, current - 1)

    def active_count(self, agent_id: str) -> int:
        """Return the current active count for an agent."""
        return self._counts.get(agent_id, 0)

    def at_capacity(self, agent_id: str, limit: int) -> bool:
        """Check if agent is at or over its max_concurrent limit.

        A limit of 0 means unlimited.
        """
        if limit <= 0:
            return False
        return self.active_count(agent_id) >= limit

    def reset(self, agent_id: str) -> None:
        """Reset the active count for an agent to zero."""
        self._counts[agent_id] = 0


class ApprovalGateManager:
    """Manages pending approvals: add, check, expire, match operator signals.

    Persists to/from a list of dicts (caller serializes to state JSON).
    Pure logic — no bus I/O performed here.
    """

    def __init__(
        self,
        default_timeout_hours: int = 24,
        pending: list[PendingApproval] | None = None,
    ):
        self._pending: list[PendingApproval] = list(pending or [])
        self.default_timeout_hours = default_timeout_hours

    @property
    def pending(self) -> list[PendingApproval]:
        """Return a copy of the pending approvals list."""
        return list(self._pending)

    def add(
        self,
        agent_id: str,
        rule_id: str,
        trigger: Message,
        timeout_hours: int | None = None,
        now: datetime | None = None,
    ) -> PendingApproval:
        """Create and store a new pending approval."""
        if now is None:
            now = datetime.now()

        msg_hash = hashlib.sha256(trigger.msg.encode("utf-8")).hexdigest()

        pa = PendingApproval(
            agent_id=agent_id,
            rule_id=rule_id,
            trigger_ts=trigger.ts.isoformat(),
            trigger_msg_hash=msg_hash,
            escalation_ts=now.isoformat(),
            timeout_hours=timeout_hours or self.default_timeout_hours,
            payload=trigger.msg,
        )
        self._pending.append(pa)
        return pa

    def find_expired(self, now: datetime | None = None) -> list[PendingApproval]:
        """Return approvals whose timeout_hours has elapsed."""
        if now is None:
            now = datetime.now()

        expired = []
        for pa in self._pending:
            escalation = datetime.fromisoformat(pa.escalation_ts)
            if now >= escalation + timedelta(hours=pa.timeout_hours):
                expired.append(pa)
        return expired

    def remove(self, agent_id: str, rule_id: str) -> None:
        """Remove a pending approval by agent_id + rule_id."""
        self._pending = [
            pa for pa in self._pending
            if not (pa.agent_id == agent_id and pa.rule_id == rule_id)
        ]

    def match_approval_signal(self, message: Message) -> PendingApproval | None:
        """Check if a bus message is an operator approval for a pending gate.

        Matches: type=="dispatch", msg=="APPROVE:<agent_id>:<rule_id>:<ts>"
        Also verifies ts matches stored trigger_ts (§11.3 integrity check).
        """
        if message.type.lower() != "dispatch":
            return None

        if not message.msg.startswith("APPROVE:"):
            return None

        parts = message.msg.split(":", 3)
        if len(parts) < 4:
            return None

        _, agent_id, rule_id, ts = parts

        for pa in self._pending:
            if (pa.agent_id == agent_id
                    and pa.rule_id == rule_id
                    and pa.trigger_ts == ts):
                return pa

        return None

    def to_list(self) -> list[dict]:
        """Serialize to a list of dicts for JSON persistence."""
        return [
            {
                "agent_id": pa.agent_id,
                "rule_id": pa.rule_id,
                "trigger_ts": pa.trigger_ts,
                "trigger_msg_hash": pa.trigger_msg_hash,
                "escalation_ts": pa.escalation_ts,
                "timeout_hours": pa.timeout_hours,
                "payload": pa.payload,
            }
            for pa in self._pending
        ]

    @classmethod
    def from_list(
        cls, data: list[dict], default_timeout_hours: int = 24
    ) -> ApprovalGateManager:
        """Restore from serialized list."""
        pending = [
            PendingApproval(
                agent_id=d["agent_id"],
                rule_id=d["rule_id"],
                trigger_ts=d["trigger_ts"],
                trigger_msg_hash=d["trigger_msg_hash"],
                escalation_ts=d["escalation_ts"],
                timeout_hours=d.get("timeout_hours", default_timeout_hours),
                payload=d.get("payload", ""),
            )
            for d in data
        ]
        return cls(default_timeout_hours=default_timeout_hours, pending=pending)


class DispatchCommandRenderer:
    """Renders a dispatch command from a DispatchRule and triggering message.

    Per §8.4 step 2: substitutes {{payload}}, {{agent_id}}, {{rule_id}}
    in command_template. MUST use list form (never shell=True) — T4 §11.4.
    """

    def __init__(
        self,
        default_command: str = "claude",
        default_max_turns: int = 10,
        default_allowed_tools: list[str] | None = None,
    ):
        self.default_command = default_command
        self.default_max_turns = default_max_turns
        self.default_allowed_tools = default_allowed_tools or []

    def render(
        self,
        rule: DispatchRule,
        profile: AgentProfile,
        trigger_msg: Message,
    ) -> list[str]:
        """Return subprocess argv list (no shell interpolation).

        If rule.command_template is set: parse and substitute.
        Otherwise use default_command with profile overrides.
        """
        if rule.command_template:
            template = rule.command_template
            template = template.replace("{{payload}}", trigger_msg.msg)
            template = template.replace("{{agent_id}}", profile.agent_id)
            template = template.replace("{{rule_id}}", rule.rule_id)
            return template.split()

        # Build default command
        cmd = [self.default_command]
        max_turns = profile.resource_limits.max_turns or self.default_max_turns
        cmd.extend(["--max-turns", str(max_turns)])

        tools = (
            list(profile.resource_limits.allowed_tools)
            if profile.resource_limits.allowed_tools
            else self.default_allowed_tools
        )
        if tools:
            cmd.extend(["--allowedTools", ",".join(tools)])

        cmd.extend(["-p", trigger_msg.msg])
        return cmd


class DispatchEngine:
    """ARC-0369 §8 Dispatch Protocol — pure decision engine.

    Given a bus message and the current registry/state, produces
    DispatchDecision objects. Does NOT perform I/O or spawn processes.
    """

    def __init__(
        self,
        registry: AgentRegistry,
        concurrency: ConcurrencyTracker,
        approval_manager: ApprovalGateManager,
        renderer: DispatchCommandRenderer,
        overflow_policy: QueueOverflow = QueueOverflow.DROP_NEWEST,
    ):
        self.registry = registry
        self.concurrency = concurrency
        self.approval_manager = approval_manager
        self.renderer = renderer
        self.overflow_policy = overflow_policy

    def evaluate_message(
        self,
        message: Message,
        now: datetime | None = None,
    ) -> list[DispatchDecision]:
        """Evaluate a bus message against all enabled agents.

        Returns one DispatchDecision per matching (agent, rule) pair,
        in priority order per §8.8: alert > dispatch > event > state.
        """
        matches = self.registry.find_matching_rules(message)
        if not matches:
            return []

        # Sort by priority tier (§8.8)
        matches.sort(key=lambda pair: _TYPE_PRIORITY.get(
            pair[1].trigger.match_type or "", 3
        ))

        decisions = []
        for profile, rule in matches:
            decisions.append(self._evaluate_single(profile, rule, message, now))
        return decisions

    def check_approval_signal(self, message: Message) -> DispatchDecision | None:
        """Check if a bus message is an operator approval.

        Returns APPROVAL_GRANTED decision if it matches, None otherwise.
        """
        pa = self.approval_manager.match_approval_signal(message)
        if pa is None:
            return None

        profile = self.registry.get(pa.agent_id)
        if profile is None:
            return None

        # Find the matching rule
        rule = None
        for r in profile.dispatch_rules:
            if r.rule_id == pa.rule_id:
                rule = r
                break

        if rule is None:
            return None

        # Build the original trigger message for rendering
        trigger_msg = Message(
            ts=date.fromisoformat(pa.trigger_ts),
            src="",
            dst=pa.agent_id,
            type="dispatch",
            msg=pa.payload,
            ttl=7,
            ack=[],
        )

        cmd = self.renderer.render(rule, profile, trigger_msg)
        self.approval_manager.remove(pa.agent_id, pa.rule_id)

        return DispatchDecision(
            agent_id=pa.agent_id,
            rule_id=pa.rule_id,
            outcome=DispatchOutcome.APPROVAL_GRANTED,
            command=cmd,
            trigger_msg=trigger_msg,
            payload=pa.payload,
        )

    def expire_approvals(
        self, now: datetime | None = None
    ) -> list[DispatchDecision]:
        """Scan pending approvals for timeouts.

        Returns APPROVAL_TIMEOUT decisions for each expired one.
        """
        expired = self.approval_manager.find_expired(now)
        decisions = []
        for pa in expired:
            self.approval_manager.remove(pa.agent_id, pa.rule_id)
            decisions.append(DispatchDecision(
                agent_id=pa.agent_id,
                rule_id=pa.rule_id,
                outcome=DispatchOutcome.APPROVAL_TIMEOUT,
                payload=pa.payload,
            ))
        return decisions

    def _evaluate_single(
        self,
        profile: AgentProfile,
        rule: DispatchRule,
        message: Message,
        now: datetime | None = None,
    ) -> DispatchDecision:
        """Build a DispatchDecision for one (profile, rule, message) triple."""
        # Check capacity
        if self.concurrency.at_capacity(
            profile.agent_id, profile.resource_limits.max_concurrent
        ):
            return DispatchDecision(
                agent_id=profile.agent_id,
                rule_id=rule.rule_id,
                outcome=DispatchOutcome.CAPACITY_EXCEEDED,
                trigger_msg=message,
                payload=message.msg,
            )

        # Approval gate
        if rule.approval_required:
            pa = self.approval_manager.add(
                agent_id=profile.agent_id,
                rule_id=rule.rule_id,
                trigger=message,
                timeout_hours=rule.approval_timeout_hours,
                now=now,
            )
            return DispatchDecision(
                agent_id=profile.agent_id,
                rule_id=rule.rule_id,
                outcome=DispatchOutcome.APPROVAL_PENDING,
                trigger_msg=message,
                payload=message.msg,
                approval_key=f"{pa.agent_id}:{pa.rule_id}:{pa.trigger_ts}",
            )

        # Direct dispatch
        cmd = self.renderer.render(rule, profile, message)
        return DispatchDecision(
            agent_id=profile.agent_id,
            rule_id=rule.rule_id,
            outcome=DispatchOutcome.DISPATCHED,
            command=cmd,
            trigger_msg=message,
            payload=message.msg,
        )


class DispatchScheduler:
    """Manages scheduled dispatch rules (§8.6).

    Validates cron expressions at load time (§7.4 rule 5, §11.2).
    Fires synthetic dispatch messages when cron matches.
    Pure logic — no asyncio. Caller polls due_rules() at intervals.
    """

    MIN_INTERVAL_SECONDS: int = 300  # 5 minutes (§11.2)

    def __init__(self, registry: AgentRegistry, daemon_namespace: str = "daemon"):
        self._schedule: dict[str, float] = {}  # "agent_id:rule_id" → last_fire_ts
        self._registry = registry
        self._daemon_namespace = daemon_namespace

    def load(self) -> list[str]:
        """Load scheduled rules from registry. Returns errors for invalid crons."""
        errors = []
        self._schedule.clear()

        for profile in self._registry.all_enabled():
            for rule in profile.dispatch_rules:
                if rule.trigger.type != "scheduled":
                    continue
                err = self.validate_cron(rule.trigger.cron or "")
                if err:
                    errors.append(
                        f"{profile.agent_id}/{rule.rule_id}: {err}"
                    )
                else:
                    key = f"{profile.agent_id}:{rule.rule_id}"
                    self._schedule.setdefault(key, 0.0)
        return errors

    def due_rules(
        self, now: float | None = None
    ) -> list[tuple[AgentProfile, DispatchRule]]:
        """Return (profile, rule) pairs whose cron is due.

        Uses a simplified interval model: fires if enough time elapsed
        since last fire. Marks as fired to prevent re-fire.
        """
        if now is None:
            now = time.time()

        due = []
        for profile in self._registry.all_enabled():
            for rule in profile.dispatch_rules:
                if rule.trigger.type != "scheduled":
                    continue
                key = f"{profile.agent_id}:{rule.rule_id}"
                last_fire = self._schedule.get(key, 0.0)

                if now - last_fire >= self.MIN_INTERVAL_SECONDS:
                    due.append((profile, rule))
                    self._schedule[key] = now

        return due

    def synthetic_message(
        self,
        profile: AgentProfile,
        rule: DispatchRule,
        now: date | None = None,
    ) -> Message:
        """Build the synthetic dispatch message for a scheduled rule (§8.6)."""
        if now is None:
            now = date.today()

        return Message(
            ts=now,
            src=self._daemon_namespace,
            dst=profile.agent_id,
            type="dispatch",
            msg=f"SCHEDULED:{rule.rule_id}:{now.isoformat()}",
            ttl=1,
            ack=[],
        )

    @property
    def schedule_state(self) -> dict[str, float]:
        """Return the schedule state for serialization."""
        return dict(self._schedule)

    def restore_state(self, state: dict[str, float]) -> None:
        """Restore schedule state from deserialization."""
        self._schedule.update(state)

    @staticmethod
    def validate_cron(expr: str, min_interval_minutes: int = 5) -> str | None:
        """Validate a 5-field cron expression.

        Returns None if valid, or an error string if invalid.
        Checks: field count, basic value ranges.
        No external deps — stdlib only.
        """
        if not expr or not expr.strip():
            return "empty cron expression"

        fields = expr.strip().split()
        if len(fields) != 5:
            return f"expected 5 fields, got {len(fields)}"

        # Field ranges: minute(0-59), hour(0-23), dom(1-31), month(1-12), dow(0-7)
        ranges = [
            ("minute", 0, 59),
            ("hour", 0, 23),
            ("day-of-month", 1, 31),
            ("month", 1, 12),
            ("day-of-week", 0, 7),
        ]

        for field_val, (name, low, high) in zip(fields, ranges):
            err = _validate_cron_field(field_val, name, low, high)
            if err:
                return err

        return None


def _validate_cron_field(
    field_val: str, name: str, low: int, high: int
) -> str | None:
    """Validate a single cron field. Returns error string or None."""
    # Handle wildcard
    if field_val == "*":
        return None

    # Handle */N step
    if field_val.startswith("*/"):
        try:
            step = int(field_val[2:])
            if step < 1:
                return f"{name}: step must be >= 1"
        except ValueError:
            return f"{name}: invalid step '{field_val}'"
        return None

    # Handle comma-separated values and ranges
    for part in field_val.split(","):
        if "-" in part:
            # Range: N-M
            bounds = part.split("-", 1)
            try:
                lo, hi = int(bounds[0]), int(bounds[1])
                if lo < low or hi > high:
                    return f"{name}: range {lo}-{hi} out of bounds ({low}-{high})"
            except ValueError:
                return f"{name}: invalid range '{part}'"
        else:
            # Single value
            try:
                val = int(part)
                if val < low or val > high:
                    return f"{name}: {val} out of range ({low}-{high})"
            except ValueError:
                return f"{name}: invalid value '{part}'"

    return None


# ---------------------------------------------------------------------------
# F4: Agent Lifecycle — ARC-0369 §9
# ---------------------------------------------------------------------------

# Legal transitions per §9.1
_LEGAL_TRANSITIONS: dict[AgentState, set[AgentState]] = {
    AgentState.INACTIVE: {AgentState.ACTIVE},
    AgentState.ACTIVE: {AgentState.PENDING, AgentState.RUNNING, AgentState.REMOVED},
    AgentState.PENDING: {AgentState.RUNNING, AgentState.ACTIVE},
    AgentState.RUNNING: {AgentState.IDLE, AgentState.FAILED},
    AgentState.IDLE: {AgentState.ACTIVE, AgentState.REMOVED},
    AgentState.FAILED: {AgentState.ACTIVE, AgentState.REMOVED},
    AgentState.REMOVED: set(),
}


class AgentStateTracker:
    """Tracks per-agent lifecycle state with transition history (§9).

    Pure logic — no I/O. The daemon calls transition methods as dispatch
    events occur. Serializes to/from dict for state persistence.
    """

    def __init__(self) -> None:
        self._states: dict[str, AgentState] = {}
        self._last_dispatch: dict[str, str] = {}  # agent_id → ISO datetime
        self._dispatch_count: dict[str, int] = {}
        self._failure_count: dict[str, int] = {}

    def transition(
        self, agent_id: str, new_state: AgentState
    ) -> AgentState | None:
        """Transition an agent to a new state.

        Returns the old state if the transition is legal, None if illegal.
        Agents not yet tracked are treated as INACTIVE.
        """
        old_state = self._states.get(agent_id, AgentState.INACTIVE)
        legal = _LEGAL_TRANSITIONS.get(old_state, set())
        if new_state not in legal:
            logger.warning(
                "Illegal transition for %s: %s → %s", agent_id, old_state, new_state
            )
            return None
        self._states[agent_id] = new_state
        return old_state

    def get_state(self, agent_id: str) -> AgentState:
        """Return current state for an agent (INACTIVE if unknown)."""
        return self._states.get(agent_id, AgentState.INACTIVE)

    def set_active(self, agent_id: str) -> None:
        """Mark agent as ACTIVE (profile loaded or recovery)."""
        current = self.get_state(agent_id)
        if current in (AgentState.INACTIVE, AgentState.IDLE, AgentState.FAILED):
            self._states[agent_id] = AgentState.ACTIVE

    def set_running(self, agent_id: str) -> None:
        """Mark agent as RUNNING (dispatch started)."""
        self.transition(agent_id, AgentState.RUNNING)

    def set_idle(self, agent_id: str) -> None:
        """Mark agent as IDLE (dispatch completed)."""
        self.transition(agent_id, AgentState.IDLE)

    def set_failed(self, agent_id: str) -> None:
        """Mark agent as FAILED (dispatch error/timeout)."""
        self.transition(agent_id, AgentState.FAILED)

    def set_pending(self, agent_id: str) -> None:
        """Mark agent as PENDING (approval gate)."""
        self.transition(agent_id, AgentState.PENDING)

    def set_removed(self, agent_id: str) -> None:
        """Mark agent as REMOVED (profile deleted/disabled)."""
        self.transition(agent_id, AgentState.REMOVED)

    def record_dispatch(self, agent_id: str, success: bool) -> None:
        """Record a dispatch attempt for metrics."""
        self._dispatch_count[agent_id] = self._dispatch_count.get(agent_id, 0) + 1
        self._last_dispatch[agent_id] = datetime.now().isoformat()
        if not success:
            self._failure_count[agent_id] = self._failure_count.get(agent_id, 0) + 1

    def heartbeat_payload(self) -> list[dict]:
        """Return §9.2 heartbeat payload — agent state summary."""
        agents = []
        for agent_id, state in sorted(self._states.items()):
            agents.append({
                "agent_id": agent_id,
                "state": state.value,
                "dispatch_count": self._dispatch_count.get(agent_id, 0),
                "failure_count": self._failure_count.get(agent_id, 0),
                "last_dispatch": self._last_dispatch.get(agent_id),
            })
        return agents

    def to_dict(self) -> dict[str, Any]:
        """Serialize for state persistence."""
        return {
            "states": {k: v.value for k, v in self._states.items()},
            "last_dispatch": dict(self._last_dispatch),
            "dispatch_count": dict(self._dispatch_count),
            "failure_count": dict(self._failure_count),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentStateTracker:
        """Restore from serialized dict. Tolerates missing keys."""
        tracker = cls()
        for agent_id, state_str in data.get("states", {}).items():
            try:
                tracker._states[agent_id] = AgentState(state_str)
            except ValueError:
                logger.warning("Unknown state '%s' for agent '%s'", state_str, agent_id)
        tracker._last_dispatch = dict(data.get("last_dispatch", {}))
        tracker._dispatch_count = {
            k: int(v) for k, v in data.get("dispatch_count", {}).items()
        }
        tracker._failure_count = {
            k: int(v) for k, v in data.get("failure_count", {}).items()
        }
        return tracker


# ---------------------------------------------------------------------------
# F5: Notification Flow — ARC-0369 §10
# ---------------------------------------------------------------------------


class NotificationThrottler:
    """Rate-limited notification dispatcher per §10.1-§10.5.

    Enforces max notifications per source per time window and suppression
    rules for message types that should never trigger notifications.
    Pure logic — does not send notifications (caller handles platform).
    """

    def __init__(
        self,
        window_seconds: int = 60,
        max_per_window: int = 5,
    ):
        self.window_seconds = window_seconds
        self.max_per_window = max_per_window
        self._history: dict[str, list[float]] = {}  # src → timestamps
        self._suppressed_count: dict[str, int] = {}

    @staticmethod
    def should_suppress(msg_type: str, msg_text: str) -> bool:
        """Check §10.1 suppression rules — MUST NOT notify for these.

        Rules:
        - msg_text starts with "[RE:" → dispatch result, suppress
        - msg_type == "data_cross" → cross-dim data, suppress
        - msg_type == "state" → normal state, suppress
        """
        if msg_text.startswith("[RE:"):
            return True
        if msg_type == "data_cross":
            return True
        if msg_type == "state":
            return True
        return False

    def should_notify(self, src: str, now: float | None = None) -> bool:
        """Check if a notification from this source is within rate limit.

        Returns True if under the limit, False if throttled.
        Does NOT record — call record() separately after sending.
        """
        if now is None:
            now = time.time()

        history = self._history.get(src, [])
        cutoff = now - self.window_seconds
        recent = [t for t in history if t > cutoff]
        return len(recent) < self.max_per_window

    def record(self, src: str, now: float | None = None) -> None:
        """Record that a notification was sent for this source."""
        if now is None:
            now = time.time()
        self._history.setdefault(src, []).append(now)
        # Prune old entries beyond 2x window to prevent unbounded growth
        cutoff = now - self.window_seconds * 2
        self._history[src] = [t for t in self._history[src] if t > cutoff]

    def record_suppressed(self, src: str) -> None:
        """Record that a notification was suppressed for this source."""
        self._suppressed_count[src] = self._suppressed_count.get(src, 0) + 1

    def suppressed_summary(self) -> list[tuple[str, int]]:
        """Return (src, count) pairs for suppressed notifications."""
        return sorted(self._suppressed_count.items())
