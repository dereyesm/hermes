"""Amaru Agent Gateway — ARC-3022 Reference Implementation.

Identity translation (NAT), outbound filtering, inbound validation,
attestation storage, Resonance computation, and profile publication
for inter-clan communication through the Agora.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, ClassVar

from .message import Message

# ─── Identity Translation (Section 5) ─────────────────────────────


@dataclass
class AgentMapping:
    """Internal-to-external agent identity mapping.

    Maps a clan's private (namespace, agent) pair to a public alias
    for Agora interactions.  Unpublished agents are invisible externally.
    """

    namespace: str
    agent: str
    external_alias: str
    published: bool
    capabilities: list[str] = field(default_factory=list)


class TranslationTable:
    """NAT-like identity translation per ARC-3022 Section 5.

    Maintains a bidirectional mapping between internal identities
    (namespace + agent) and external aliases.  Only published agents
    are visible to the Agora.
    """

    def __init__(self, clan_id: str, mappings: list[AgentMapping]) -> None:
        self.clan_id = clan_id
        self._mappings = list(mappings)

        # Build lookup indices
        self._internal_to_external: dict[tuple[str, str], AgentMapping] = {}
        self._external_to_internal: dict[str, AgentMapping] = {}

        for m in self._mappings:
            self._internal_to_external[(m.namespace, m.agent)] = m
            if m.external_alias:
                self._external_to_internal[m.external_alias] = m

    def translate_outbound(self, namespace: str, agent: str) -> str | None:
        """Translate an internal (namespace, agent) to its external alias.

        Returns None if the agent is not mapped or not published.
        Per Section 5.2 rule 5: unpublished agents are invisible.
        """
        mapping = self._internal_to_external.get((namespace, agent))
        if mapping is None or not mapping.published:
            return None
        return mapping.external_alias

    def translate_inbound(self, external_alias: str) -> tuple[str, str] | None:
        """Translate an external alias to its internal (namespace, agent).

        Returns None if the alias is unknown or maps to an unpublished agent.
        """
        mapping = self._external_to_internal.get(external_alias)
        if mapping is None or not mapping.published:
            return None
        return (mapping.namespace, mapping.agent)

    def published_agents(self) -> list[AgentMapping]:
        """Return all published agent mappings."""
        return [m for m in self._mappings if m.published]


# ─── Outbound Filter (Section 7) ──────────────────────────────────


class OutboundFilter:
    """Egress filtering per ARC-3022 Section 7.

    Implements default-deny outbound policy.  Only explicitly allowed
    message types may leave the clan, and payloads are scanned for
    prohibited data patterns (Section 7.4).
    """

    # Allowed outbound message types (Section 7.3)
    ALLOWED_TYPES = frozenset({"profile_update", "attestation", "quest_response"})

    # Prohibited outbound data patterns (Section 7.4)
    # 1. Internal bus messages
    # 2. Routing table contents
    # 3. Agent configurations (SKILL.md, registry.json)
    # 4. Credentials, tokens, API keys
    # 5. Memory files
    # 6. Session logs
    # 7. Evolution/Dojo data (XP, Bounty, level, medallas)
    PROHIBITED_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(r"bus\.jsonl", re.IGNORECASE),
        re.compile(r"routes\.md", re.IGNORECASE),
        re.compile(r"SKILL\.md", re.IGNORECASE),
        re.compile(r"registry\.json", re.IGNORECASE),
        re.compile(r"(api[_-]?key|token|secret|password|credential)", re.IGNORECASE),
        re.compile(r"MEMORY\.md", re.IGNORECASE),
        re.compile(r"session[_-]?log", re.IGNORECASE),
        re.compile(r"\b(XP|bounty|medalla|level\s*\d|dojo[_-]?event)\b", re.IGNORECASE),
    ]

    def evaluate(self, message_type: str, payload: str) -> tuple[bool, str]:
        """Evaluate whether an outbound message is allowed.

        Returns (allowed, reason).  If allowed is False, reason explains why.
        """
        # Step 1: Check message type against allowed set
        if message_type not in self.ALLOWED_TYPES:
            return (False, f"message type '{message_type}' not in allowed outbound types")

        # Step 2: Scan payload for prohibited patterns
        for pattern in self.PROHIBITED_PATTERNS:
            if pattern.search(payload):
                return (False, f"payload contains prohibited data: {pattern.pattern}")

        return (True, "ok")


# ─── Inbound Validator (Section 8) ─────────────────────────────────


class InboundValidator:
    """Ingress validation per ARC-3022 Section 8.

    Implements the validate_inbound pseudocode from Section 8.2:
    source verification, type check, target resolution, payload
    inspection, and rate limiting.
    """

    # Supported inbound message types (Section 8.1)
    SUPPORTED_INBOUND_TYPES = frozenset({"discovery", "attestation", "quest_proposal"})

    # Simple heuristic for executable content detection
    _EXECUTABLE_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(r"<script", re.IGNORECASE),
        re.compile(r"__import__\s*\("),
        re.compile(r"\beval\s*\("),
        re.compile(r"\bexec\s*\("),
    ]

    def __init__(
        self,
        known_clans: set[str],
        published_aliases: set[str],
        max_payload_bytes: int = 4096,
        rate_limit_per_clan: int = 10,
    ) -> None:
        self.known_clans = set(known_clans)
        self.published_aliases = set(published_aliases)
        self.max_payload_bytes = max_payload_bytes
        self.rate_limit_per_clan = rate_limit_per_clan

        # Simple in-memory rate tracking: clan_id -> message count
        self._rate_counts: dict[str, int] = {}

    def validate(
        self,
        source_clan: str,
        target_agent: str,
        message_type: str,
        payload: str,
    ) -> tuple[bool, str]:
        """Validate an inbound message per Section 8.2.

        Returns (accepted, reason).  If accepted is False, reason explains why.
        """
        # Step 1: Source verification
        if source_clan not in self.known_clans:
            return (False, "unknown source clan")

        # Step 2: Message type check
        if message_type not in self.SUPPORTED_INBOUND_TYPES:
            return (False, "unsupported inbound type")

        # Step 3: Target resolution
        if target_agent not in self.published_aliases:
            return (False, "unknown agent")

        # Step 4: Payload inspection — executable content
        for pattern in self._EXECUTABLE_PATTERNS:
            if pattern.search(payload):
                return (False, "executable content not permitted")

        # Step 4b: Payload inspection — size limit
        if len(payload.encode("utf-8")) > self.max_payload_bytes:
            return (False, "payload too large")

        # Step 5: Rate limiting
        count = self._rate_counts.get(source_clan, 0)
        if count >= self.rate_limit_per_clan:
            return (False, "rate limit exceeded")
        self._rate_counts[source_clan] = count + 1

        return (True, "ok")

    def reset_rate_limits(self) -> None:
        """Reset all rate limit counters (call at the start of each period)."""
        self._rate_counts.clear()


# ─── Attestation Store (Section 9) ─────────────────────────────────


class AttestationStore:
    """Storage and verification of attestations per ARC-3022 Section 9.

    Attestations are append-only.  Self-attestation is prohibited.
    Duplicates (same from_clan + to_agent + quest_id) are rejected.
    """

    def __init__(self) -> None:
        self._attestations: list[dict[str, Any]] = []
        # Track (from_clan, to_agent, quest_id) to detect duplicates
        self._seen: set[tuple[str, str, str]] = set()

    def add(self, attestation: dict[str, Any]) -> bool:
        """Add an attestation to the store.

        Returns True if accepted, False if rejected (self-attestation,
        duplicate, or missing fields).
        """
        from_clan = attestation.get("from_clan", "")
        to_clan = attestation.get("to_clan", "")
        to_agent = attestation.get("to_agent", "")
        quest_id = attestation.get("quest_id", "")

        # Section 9.3 rule 2: Self-attestation is prohibited
        if from_clan == to_clan:
            return False

        # Section 9.3 rule 3: One attestation per quest per agent pair
        key = (from_clan, to_agent, quest_id)
        if key in self._seen:
            return False

        self._seen.add(key)
        self._attestations.append(dict(attestation))
        return True

    def get_for_agent(self, alias: str) -> list[dict[str, Any]]:
        """Retrieve all attestations for a given external alias."""
        return [a for a in self._attestations if a.get("to_agent") == alias]

    def count_unique_clans(self, alias: str) -> int:
        """Count the number of unique clans that have attested for an agent."""
        clans = {a["from_clan"] for a in self._attestations if a.get("to_agent") == alias}
        return len(clans)


# ─── Resonance Calculator (Section 10) ─────────────────────────────


class ResonanceCalculator:
    """Compute Resonance scores from attestations per ARC-3022 Section 10.

    Resonance(agent) = sum of:
        attestation_score(a) * recency_weight(a) * diversity_weight(a)
        for each verified attestation a

    Where:
        attestation_score = (quality + reliability + collaboration) / 3
        recency_weight    = max(0, 1 - (days_since / 365))
        diversity_weight  = 1 + (0.1 * unique_clans_attesting)
    """

    def compute(self, attestations: list[dict[str, Any]], today: date | None = None) -> float:
        """Compute the Resonance score for a list of attestations.

        All attestations are assumed to be for the same agent.
        Returns 0.0 if the list is empty.
        """
        if not attestations:
            return 0.0

        if today is None:
            today = date.today()

        # Compute diversity_weight once: based on unique attesting clans
        unique_clans = len({a.get("from_clan", "") for a in attestations})
        diversity_weight = 1.0 + (0.1 * unique_clans)

        total = 0.0
        for a in attestations:
            rating = a.get("rating", {})
            quality = rating.get("quality", 0)
            reliability = rating.get("reliability", 0)
            collaboration = rating.get("collaboration", 0)
            attestation_score = (quality + reliability + collaboration) / 3.0

            ts_str = a.get("timestamp", "")
            try:
                att_date = date.fromisoformat(ts_str)
            except (ValueError, TypeError):
                att_date = today
            days_since = (today - att_date).days
            recency_weight = max(0.0, 1.0 - (days_since / 365.0))

            total += attestation_score * recency_weight * diversity_weight

        return round(total, 4)


# ─── Gateway (Main Component) ──────────────────────────────────────


class Gateway:
    """Main gateway component per ARC-3022.

    Ties together identity translation, outbound filtering, inbound
    validation, attestation storage, and profile publication.
    """

    def __init__(
        self,
        clan_id: str,
        display_name: str,
        translation_table: TranslationTable,
        outbound_filter: OutboundFilter | None = None,
        inbound_validator: InboundValidator | None = None,
        attestation_store: AttestationStore | None = None,
        resonance_calculator: ResonanceCalculator | None = None,
        protocol_version: str = "0.1.0",
    ) -> None:
        self.clan_id = clan_id
        self.display_name = display_name
        self.translation_table = translation_table
        self.outbound_filter = outbound_filter or OutboundFilter()
        self.inbound_validator = inbound_validator
        self.attestation_store = attestation_store or AttestationStore()
        self.resonance_calculator = resonance_calculator or ResonanceCalculator()
        self.protocol_version = protocol_version

    def build_public_profile(self) -> dict[str, Any]:
        """Build the clan's public profile per Section 6.

        Contains only published agents, their capabilities, and
        Resonance scores.  No internal data is included.
        """
        published = self.translation_table.published_agents()
        agents_list = []
        total_resonance = 0.0

        for mapping in published:
            attestations = self.attestation_store.get_for_agent(mapping.external_alias)
            resonance = self.resonance_calculator.compute(attestations)
            total_resonance += resonance
            agents_list.append(
                {
                    "alias": mapping.external_alias,
                    "capabilities": list(mapping.capabilities),
                    "resonance": resonance,
                    "attestations_received": len(attestations),
                }
            )

        return {
            "clan_id": self.clan_id,
            "display_name": self.display_name,
            "protocol_version": self.protocol_version,
            "agents": agents_list,
            "clan_stats": {
                "total_published_agents": len(published),
                "total_resonance": round(total_resonance, 4),
            },
        }

    def process_inbound(
        self,
        source_clan: str,
        message: dict[str, Any],
    ) -> Message | None:
        """Process an inbound message from the Agora.

        Validates the message and, if accepted, translates it to an
        internal bus Message with the AGORA: prefix.

        Returns a Message suitable for the internal bus, or None if rejected.
        """
        if self.inbound_validator is None:
            return None

        target_agent = message.get("target_agent", "")
        msg_type = message.get("type", "")
        payload = message.get("payload", "")

        accepted, reason = self.inbound_validator.validate(
            source_clan=source_clan,
            target_agent=target_agent,
            message_type=msg_type,
            payload=payload,
        )

        if not accepted:
            return None

        # Translate external alias to internal identity
        internal = self.translation_table.translate_inbound(target_agent)
        if internal is None:
            return None

        namespace, agent = internal

        # Build internal bus message with AGORA: prefix (Section 13.2)
        internal_msg = f"AGORA:{msg_type} from {source_clan} for {target_agent}"
        # Truncate to 120 chars if needed (ARC-5322 MAX_MSG_LENGTH)
        if len(internal_msg) > 120:
            internal_msg = internal_msg[:120]

        return Message(
            ts=date.today(),
            src="gateway",
            dst=namespace,
            type="event",
            msg=internal_msg,
            ttl=7,
            ack=[],
        )

    def format_outbound(self, internal_message: Message) -> dict[str, Any] | None:
        """Format an internal message for outbound transmission.

        Applies the outbound filter and translates internal identity
        to external alias.  Returns the Agora-format dict, or None
        if the message is blocked by the filter.

        The caller must supply message_type and target info in the
        internal_message.msg field.  The outbound type is derived
        from the msg content prefix convention.
        """
        # Determine outbound type from message metadata
        msg_text = internal_message.msg
        outbound_type = _extract_outbound_type(msg_text)

        # Apply outbound filter
        allowed, reason = self.outbound_filter.evaluate(outbound_type, msg_text)
        if not allowed:
            return None

        # Translate source identity
        external_alias = self.translation_table.translate_outbound(
            internal_message.src,
            internal_message.src,
        )

        return {
            "source_clan": self.clan_id,
            "source_agent": external_alias,
            "type": outbound_type,
            "payload": msg_text,
        }


def _extract_outbound_type(msg: str) -> str:
    """Extract an outbound message type from the message text.

    Convention: messages destined for outbound carry a type prefix
    like "profile_update:", "attestation:", "quest_response:".
    Falls back to the raw text as type if no prefix is found.
    """
    for known_type in ("profile_update", "attestation", "quest_response"):
        if msg.startswith(known_type + ":") or msg.startswith(known_type + " "):
            return known_type
        if msg == known_type:
            return known_type
    return msg
