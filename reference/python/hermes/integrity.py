"""ARC-9001: Bus Integrity Protocol — F1 Message Sequencing + F2 Write Ownership.

Provides bus-level integrity guarantees for the HERMES protocol:

F1 (SequenceTracker): Monotonic sequence numbers per source namespace.
   Detects gaps, duplicates, and replay attempts on the bus.
   Reference: SS7 sequence numbering (ITU-T Q.703 §5.2).

F2 (OwnershipRegistry): Maps namespaces to authorized writers.
   Enforces that only the registered owner can write src=namespace.
   Reference: 3GPP TS 23.501 §6.2.6 NF registration/ownership.

F3-F6 (MVCC, Conflict Log, Recovery, GC): PLANNED — see spec/ARC-9001.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


# ---------------------------------------------------------------------------
# F1: Message Sequencing
# ---------------------------------------------------------------------------

@dataclass
class SequenceState:
    """Per-source sequence tracking state."""

    last_seq: int = 0
    gap_count: int = 0


class SequenceTracker:
    """Tracks monotonic sequence numbers per source namespace.

    Pure logic, no I/O. Caller provides messages; tracker validates.
    Sequence numbers start at 1 and increment monotonically per src.
    """

    def __init__(self) -> None:
        self._state: dict[str, SequenceState] = {}

    def next_seq(self, src: str) -> int:
        """Return the next sequence number for a source.

        If src has never written, returns 1.
        Otherwise returns last_seq + 1.
        """
        state = self._state.get(src)
        if state is None:
            return 1
        return state.last_seq + 1

    def record(self, src: str, seq: int) -> None:
        """Record an observed sequence number from a bus message.

        Used when loading existing bus to reconstruct state.
        Updates last_seq to max(current, seq). Detects gaps.
        """
        state = self._state.get(src)
        if state is None:
            state = SequenceState()
            self._state[src] = state
            if seq > 1:
                state.gap_count += seq - 1
        else:
            expected = state.last_seq + 1
            if seq > expected:
                state.gap_count += seq - expected
        if seq > state.last_seq:
            state.last_seq = seq

    def validate(self, src: str, seq: int) -> bool:
        """Check if seq is the expected next value for src.

        Returns True if seq == last_seq + 1 (or seq == 1 and src unknown).
        Returns False on gap or duplicate.
        """
        expected = self.next_seq(src)
        return seq == expected

    def detect_gap(self, src: str, seq: int) -> tuple[int, int] | None:
        """If seq causes a gap, return (expected, actual).

        Returns None if no gap (seq is expected or a duplicate).
        """
        expected = self.next_seq(src)
        if seq > expected:
            return (expected, seq)
        return None

    def detect_duplicate(self, src: str, seq: int) -> bool:
        """Return True if seq <= last_seq for this src (duplicate/replay)."""
        state = self._state.get(src)
        if state is None:
            return False
        return seq <= state.last_seq

    def get_state(self, src: str) -> SequenceState | None:
        """Return the sequence state for a source, or None if unknown."""
        return self._state.get(src)

    def all_sources(self) -> dict[str, SequenceState]:
        """Return a deep copy of all tracked source states."""
        return {
            src: SequenceState(last_seq=s.last_seq, gap_count=s.gap_count)
            for src, s in self._state.items()
        }

    def load_from_bus(self, messages: list) -> list[dict]:
        """Scan a list of messages and reconstruct sequence state.

        Messages without seq (None) are skipped.
        Returns a list of anomaly dicts:
          {"type": "gap"|"duplicate", "src": ..., "seq": ..., "expected": ...}
        """
        anomalies: list[dict] = []
        for msg in messages:
            seq = getattr(msg, "seq", None)
            if seq is None:
                continue
            src = msg.src
            gap = self.detect_gap(src, seq)
            if gap is not None:
                anomalies.append({
                    "type": "gap",
                    "src": src,
                    "seq": seq,
                    "expected": gap[0],
                })
            elif self.detect_duplicate(src, seq):
                anomalies.append({
                    "type": "duplicate",
                    "src": src,
                    "seq": seq,
                    "expected": self.next_seq(src),
                })
            self.record(src, seq)
        return anomalies

    def to_dict(self) -> dict[str, int]:
        """Serialize to {src: last_seq} for persistence."""
        return {src: state.last_seq for src, state in self._state.items()}

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> SequenceTracker:
        """Restore from serialized state."""
        tracker = cls()
        for src, last_seq in data.items():
            tracker._state[src] = SequenceState(last_seq=last_seq)
        return tracker


# ---------------------------------------------------------------------------
# F2: Write Ownership
# ---------------------------------------------------------------------------

class OwnershipViolation(Exception):
    """Raised when a writer attempts to use a namespace it doesn't own."""


@dataclass(frozen=True)
class OwnershipClaim:
    """A claim that a specific writer owns a namespace."""

    namespace: str
    owner_id: str
    granted_at: str  # ISO date string


class OwnershipRegistry:
    """Maps namespaces to their authorized writers.

    Default: daemon owns all local namespaces (implicit).
    ASP agents can be granted ownership of their namespace.

    Authorization rules (in priority order):
    1. Explicit claim exists → writer must match owner_id
    2. No claim + writer is daemon → authorized (implicit)
    3. No claim + writer is NOT daemon → denied
    """

    def __init__(self, daemon_id: str = "daemon") -> None:
        self._claims: dict[str, OwnershipClaim] = {}
        self._daemon_id = daemon_id

    @property
    def daemon_id(self) -> str:
        return self._daemon_id

    def claim(
        self,
        namespace: str,
        owner_id: str,
        granted_at: str | None = None,
    ) -> OwnershipClaim:
        """Register ownership of a namespace by a writer.

        Raises OwnershipViolation if already owned by a different writer.
        Idempotent if same owner reclaims.
        """
        existing = self._claims.get(namespace)
        if existing is not None and existing.owner_id != owner_id:
            raise OwnershipViolation(
                f"Namespace '{namespace}' already owned by '{existing.owner_id}', "
                f"cannot claim for '{owner_id}'"
            )
        if granted_at is None:
            granted_at = str(date.today())
        c = OwnershipClaim(namespace=namespace, owner_id=owner_id, granted_at=granted_at)
        self._claims[namespace] = c
        return c

    def revoke(self, namespace: str) -> bool:
        """Remove an ownership claim. Returns True if existed."""
        return self._claims.pop(namespace, None) is not None

    def owner_of(self, namespace: str) -> str | None:
        """Return the owner_id for a namespace, or None if unclaimed."""
        c = self._claims.get(namespace)
        return c.owner_id if c is not None else None

    def is_authorized(self, namespace: str, writer_id: str) -> bool:
        """Check if writer_id is authorized to write src=namespace.

        Rules:
        1. Explicit claim → writer must match owner_id
        2. No claim + daemon → authorized (implicit ownership)
        3. No claim + non-daemon → denied
        """
        c = self._claims.get(namespace)
        if c is not None:
            return c.owner_id == writer_id
        # No explicit claim: daemon is implicitly authorized
        return writer_id == self._daemon_id

    def claim_for_daemon(self, namespaces: set[str]) -> None:
        """Bulk-claim all namespaces for the daemon (startup default)."""
        for ns in namespaces:
            if ns not in self._claims:
                self.claim(ns, self._daemon_id)

    def grant_to_agent(
        self,
        agent_id: str,
        namespace: str | None = None,
    ) -> OwnershipClaim:
        """Grant an ASP agent ownership of its namespace.

        By default, namespace = agent_id (convention).
        Revokes daemon claim on that namespace first.
        """
        ns = namespace if namespace is not None else agent_id
        existing = self._claims.get(ns)
        if existing is not None and existing.owner_id == self._daemon_id:
            self.revoke(ns)
        return self.claim(ns, agent_id)

    def all_claims(self) -> list[OwnershipClaim]:
        """Return all current claims."""
        return list(self._claims.values())

    def to_dict(self) -> dict[str, dict]:
        """Serialize for persistence: {namespace: {owner_id, granted_at}}."""
        return {
            c.namespace: {"owner_id": c.owner_id, "granted_at": c.granted_at}
            for c in self._claims.values()
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, dict],
        daemon_id: str = "daemon",
    ) -> OwnershipRegistry:
        """Restore from serialized state."""
        reg = cls(daemon_id=daemon_id)
        for ns, info in data.items():
            reg._claims[ns] = OwnershipClaim(
                namespace=ns,
                owner_id=info["owner_id"],
                granted_at=info.get("granted_at", ""),
            )
        return reg

    def validate_message(self, message, writer_id: str) -> bool:
        """Convenience: check if writer_id may write a message with this src."""
        return self.is_authorized(message.src, writer_id)


# ---------------------------------------------------------------------------
# Integration Helper
# ---------------------------------------------------------------------------

class BusIntegrityChecker:
    """Combines SequenceTracker + OwnershipRegistry for bus validation.

    Provides a single check_write() / check_read() entry point.
    """

    def __init__(
        self,
        seq_tracker: SequenceTracker,
        ownership: OwnershipRegistry,
    ) -> None:
        self.seq = seq_tracker
        self.ownership = ownership

    def check_write(
        self,
        message,
        writer_id: str,
        seq: int | None = None,
    ) -> list[str]:
        """Validate a message before writing to bus.

        Returns list of violation descriptions (empty = OK).
        Checks:
        1. Ownership: writer_id authorized for message.src
        2. Sequence: seq is next expected for message.src (if seq provided)
        """
        violations: list[str] = []
        if not self.ownership.is_authorized(message.src, writer_id):
            owner = self.ownership.owner_of(message.src)
            violations.append(
                f"ownership: '{writer_id}' not authorized for "
                f"namespace '{message.src}' (owner: {owner or 'daemon (implicit)'})"
            )
        if seq is not None:
            if self.seq.detect_duplicate(message.src, seq):
                violations.append(
                    f"sequence: duplicate seq={seq} for src='{message.src}' "
                    f"(last={self.seq.get_state(message.src).last_seq})"
                )
            gap = self.seq.detect_gap(message.src, seq)
            if gap is not None:
                violations.append(
                    f"sequence: gap for src='{message.src}' "
                    f"(expected={gap[0]}, got={gap[1]})"
                )
        return violations

    def check_read(self, message, seq: int | None = None) -> list[str]:
        """Validate a message read from bus.

        Returns list of anomaly descriptions.
        Checks sequence gap/duplicate detection.
        """
        anomalies: list[str] = []
        if seq is not None:
            if self.seq.detect_duplicate(message.src, seq):
                anomalies.append(
                    f"duplicate: seq={seq} for src='{message.src}'"
                )
            gap = self.seq.detect_gap(message.src, seq)
            if gap is not None:
                anomalies.append(
                    f"gap: src='{message.src}' expected={gap[0]} got={gap[1]}"
                )
        return anomalies
