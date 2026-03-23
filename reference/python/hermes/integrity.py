"""ARC-9001: Bus Integrity Protocol — F1-F4 Reference Implementation.

Provides bus-level integrity guarantees for the HERMES protocol:

F1 (SequenceTracker): Monotonic sequence numbers per source namespace.
   Detects gaps, duplicates, and replay attempts on the bus.
   Reference: SS7 sequence numbering (ITU-T Q.703 §5.2).

F2 (OwnershipRegistry): Maps namespaces to authorized writers.
   Enforces that only the registered owner can write src=namespace.
   Reference: 3GPP TS 23.501 §6.2.6 NF registration/ownership.

F3 (WriteVector + WriteVectorTracker): Causal ordering across namespaces.
   Write vectors capture the writer's view of the bus at write time.
   Conflict detection via vector clock semantics.
   Reference: Kung & Robinson (1981), Lamport vector clocks.

F4 (ConflictLog): Append-only forensic log for integrity violations.
   Records gaps, duplicates, ownership breaches, and concurrent writes.
   File: bus-conflicts.jsonl, independent of bus archival.

F5 (BusSnapshot + ReplayRequest): Periodic snapshots for fast recovery.
   Replay protocol for gap resolution between daemon and relay.
   Reference: PostgreSQL WAL snapshots, SS7 link recovery.

F6 (BusGC): Sequence-aware garbage collection preserving pending refs.
   Atomic compaction via temp file + rename.
   Conflict log independence guaranteed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path


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
# F3: Multi-Version Concurrency Control (Write Vectors)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WriteVector:
    """Causal state snapshot at write time (ARC-9001 F3).

    Captures {src: last_seen_seq} for all sources the writer has observed.
    Two write vectors are concurrent if neither dominates the other
    (vector clock semantics — Lamport, Kung & Robinson 1981).
    """

    state: dict[str, int] = field(default_factory=dict)

    def dominates(self, other: WriteVector) -> bool:
        """Return True if self >= other on all keys and > on at least one.

        Missing keys are treated as 0 (writer hasn't seen that source).
        """
        all_keys = set(self.state) | set(other.state)
        if not all_keys:
            return False
        at_least_one_greater = False
        for k in all_keys:
            s = self.state.get(k, 0)
            o = other.state.get(k, 0)
            if s < o:
                return False
            if s > o:
                at_least_one_greater = True
        return at_least_one_greater

    def concurrent_with(self, other: WriteVector) -> bool:
        """Return True if neither vector dominates the other.

        Equal vectors are NOT concurrent (they represent the same state).
        """
        if self.state == other.state:
            return False
        return not self.dominates(other) and not other.dominates(self)

    def to_dict(self) -> dict[str, int]:
        """Serialize for JSON embedding in message `w` field."""
        return dict(self.state)

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> WriteVector:
        """Restore from serialized form."""
        return cls(state=dict(data))


class WriteVectorTracker:
    """Tracks write vectors for conflict detection (ARC-9001 F3).

    Pure logic, no I/O. Builds on SequenceTracker to generate and validate
    write vectors. Maintains a sliding window of recent messages for
    conflict comparison.
    """

    def __init__(
        self,
        seq_tracker: SequenceTracker,
        window_size: int = 100,
    ) -> None:
        self._seq = seq_tracker
        self._window_size = window_size
        # Recent messages: (src, seq, WriteVector, ts_iso)
        self._recent: list[tuple[str, int, WriteVector, str]] = []

    def current_vector(self) -> WriteVector:
        """Snapshot the current seq_tracker state as a write vector.

        This represents the writer's view of the bus right now.
        """
        return WriteVector(state=self._seq.to_dict())

    def record(self, src: str, seq: int, w: WriteVector, ts: str = "") -> None:
        """Record a message's write vector for conflict detection.

        Maintains a sliding window of the most recent messages.
        """
        self._recent.append((src, seq, w, ts))
        if len(self._recent) > self._window_size:
            self._recent = self._recent[-self._window_size:]

    def detect_conflicts(
        self,
        src: str,
        seq: int,
        w: WriteVector,
    ) -> list[dict]:
        """Check if a message's write vector conflicts with recent messages.

        Returns list of conflict descriptors:
          {"type": "concurrent", "src1": ..., "seq1": ..., "src2": ..., "seq2": ...}

        Only checks messages from different sources (same-source messages
        are ordered by seq and cannot conflict).
        """
        conflicts = []
        for r_src, r_seq, r_w, _ts in self._recent:
            if r_src == src:
                continue  # Same source: ordered by seq, no conflict possible
            if w.concurrent_with(r_w):
                conflicts.append({
                    "type": "concurrent",
                    "src1": src,
                    "seq1": seq,
                    "src2": r_src,
                    "seq2": r_seq,
                })
        return conflicts

    @property
    def recent_count(self) -> int:
        """Number of messages in the sliding window."""
        return len(self._recent)


# ---------------------------------------------------------------------------
# F4: Conflict Log
# ---------------------------------------------------------------------------

class ConflictResolution(str, Enum):
    """Resolution strategy for detected conflicts (ARC-9001 F3)."""

    LAST_WRITER_WINS = "last_writer_wins"
    MANUAL = "manual"
    MERGE = "merge"


@dataclass(frozen=True)
class ConflictRecord:
    """A single conflict/anomaly record for the forensic log."""

    detected_at: str  # ISO datetime
    type: str  # "gap" | "duplicate" | "ownership" | "concurrent"
    src: str
    seq: int | None = None
    expected: int | None = None
    resolution: str = "logged"
    messages: list[str] = field(default_factory=list)
    details: str = ""

    def to_dict(self) -> dict:
        d: dict = {
            "detected_at": self.detected_at,
            "type": self.type,
            "src": self.src,
        }
        if self.seq is not None:
            d["seq"] = self.seq
        if self.expected is not None:
            d["expected"] = self.expected
        d["resolution"] = self.resolution
        if self.messages:
            d["messages"] = list(self.messages)
        if self.details:
            d["details"] = self.details
        return d

    @classmethod
    def from_dict(cls, data: dict) -> ConflictRecord:
        return cls(
            detected_at=data["detected_at"],
            type=data["type"],
            src=data["src"],
            seq=data.get("seq"),
            expected=data.get("expected"),
            resolution=data.get("resolution", "logged"),
            messages=data.get("messages", []),
            details=data.get("details", ""),
        )


class ConflictLog:
    """Append-only conflict log for forensics (ARC-9001 F4).

    Writes to bus-conflicts.jsonl. Independent of bus archival lifecycle.
    POSIX append atomicity — no locking needed for short writes.
    """

    def __init__(self, log_path: str | Path) -> None:
        self._path = Path(log_path)

    @property
    def path(self) -> Path:
        return self._path

    def record_anomaly(
        self,
        anomaly_type: str,
        src: str,
        seq: int | None = None,
        expected: int | None = None,
        resolution: str = "logged",
        messages: list[str] | None = None,
        details: str = "",
    ) -> ConflictRecord:
        """Record an anomaly to the conflict log.

        Returns the ConflictRecord written.
        """
        record = ConflictRecord(
            detected_at=datetime.now().isoformat(timespec="seconds"),
            type=anomaly_type,
            src=src,
            seq=seq,
            expected=expected,
            resolution=resolution,
            messages=messages or [],
            details=details,
        )
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        return record

    def record_concurrent(
        self,
        src1: str,
        seq1: int,
        src2: str,
        seq2: int,
        resolution: str = "logged",
    ) -> ConflictRecord:
        """Record a concurrent-write conflict between two messages."""
        return self.record_anomaly(
            anomaly_type="concurrent",
            src=src1,
            seq=seq1,
            messages=[f"{src1}:{seq1}", f"{src2}:{seq2}"],
            resolution=resolution,
            details=f"Concurrent write vectors: {src1}@{seq1} vs {src2}@{seq2}",
        )

    def read_all(self) -> list[ConflictRecord]:
        """Read all records from the conflict log."""
        if not self._path.exists():
            return []
        records = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(ConflictRecord.from_dict(json.loads(line)))
            except (json.JSONDecodeError, KeyError):
                continue
        return records

    def count(self) -> int:
        """Count records without fully parsing."""
        if not self._path.exists():
            return 0
        return sum(
            1 for line in self._path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )


# ---------------------------------------------------------------------------
# F5: Recovery (Snapshots + Replay Requests)
# ---------------------------------------------------------------------------

import hashlib
import os
import tempfile


@dataclass(frozen=True)
class BusSnapshot:
    """Periodic state snapshot for fast recovery (ARC-9001 F5).

    Captures seq_state, ownership_claims, bus hash, and message count.
    On restart, the daemon restores from the snapshot instead of scanning
    the entire bus. Created every N messages or on clean shutdown.
    """

    seq_state: dict[str, int]
    ownership_claims: dict[str, dict]
    bus_hash: str  # SHA-256 of bus file at snapshot time
    message_count: int
    created_at: str  # ISO datetime

    def to_dict(self) -> dict:
        return {
            "seq_state": dict(self.seq_state),
            "ownership_claims": dict(self.ownership_claims),
            "bus_hash": self.bus_hash,
            "message_count": self.message_count,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> BusSnapshot:
        return cls(
            seq_state=data["seq_state"],
            ownership_claims=data["ownership_claims"],
            bus_hash=data["bus_hash"],
            message_count=data["message_count"],
            created_at=data["created_at"],
        )


class SnapshotManager:
    """Manages bus-snapshot.json for fast recovery (ARC-9001 F5).

    Creates snapshots of SequenceTracker + OwnershipRegistry state.
    On recovery, restores from snapshot if bus hash matches (no full scan).
    """

    def __init__(self, snapshot_path: str | Path) -> None:
        self._path = Path(snapshot_path)

    @property
    def path(self) -> Path:
        return self._path

    def create(
        self,
        seq_tracker: SequenceTracker,
        ownership: OwnershipRegistry,
        bus_path: str | Path,
    ) -> BusSnapshot:
        """Create a snapshot from current state.

        Computes SHA-256 of the bus file for integrity verification.
        """
        bus_path = Path(bus_path)
        bus_hash = ""
        message_count = 0
        if bus_path.exists():
            content = bus_path.read_bytes()
            bus_hash = hashlib.sha256(content).hexdigest()
            message_count = sum(
                1 for line in content.decode("utf-8", errors="replace").splitlines()
                if line.strip()
            )

        snapshot = BusSnapshot(
            seq_state=seq_tracker.to_dict(),
            ownership_claims=ownership.to_dict(),
            bus_hash=bus_hash,
            message_count=message_count,
            created_at=datetime.now().isoformat(timespec="seconds"),
        )

        with self._path.open("w", encoding="utf-8") as f:
            json.dump(snapshot.to_dict(), f, indent=2)

        return snapshot

    def load(self) -> BusSnapshot | None:
        """Load snapshot from file. Returns None if not found or invalid."""
        if not self._path.exists():
            return None
        try:
            with self._path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return BusSnapshot.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None

    def verify(self, snapshot: BusSnapshot, bus_path: str | Path) -> bool:
        """Verify that the bus file matches the snapshot's hash.

        Returns True if the bus content SHA-256 matches. If it doesn't,
        the snapshot is stale and a full bus scan is needed.
        """
        bus_path = Path(bus_path)
        if not bus_path.exists():
            return snapshot.bus_hash == "" and snapshot.message_count == 0
        content = bus_path.read_bytes()
        current_hash = hashlib.sha256(content).hexdigest()
        return current_hash == snapshot.bus_hash


@dataclass(frozen=True)
class ReplayRequest:
    """A request to replay missing messages (ARC-9001 F5).

    Sent when a gap is detected: the receiver asks the source to
    resend messages from from_seq to to_seq inclusive.
    """

    src: str  # Source namespace that has the gap
    from_seq: int  # First missing seq
    to_seq: int  # Last missing seq
    requested_at: str  # ISO datetime

    def to_dispatch_msg(self) -> str:
        """Format as a dispatch message payload (<120 chars)."""
        return f"REPLAY_REQUEST:{self.src}:{self.from_seq}-{self.to_seq}"

    @classmethod
    def from_gap(cls, src: str, expected: int, actual: int) -> ReplayRequest:
        """Create from a detected gap (expected vs actual seq)."""
        return cls(
            src=src,
            from_seq=expected,
            to_seq=actual - 1,
            requested_at=datetime.now().isoformat(timespec="seconds"),
        )


# ---------------------------------------------------------------------------
# F6: Garbage Collection
# ---------------------------------------------------------------------------

class BusGC:
    """Sequence-aware garbage collection for the bus (ARC-9001 F6).

    Archives messages below a sequence threshold per source. Uses atomic
    compaction (write to temp file + rename). Conflict log is never touched.
    """

    @staticmethod
    def compute_threshold(
        seq_tracker: SequenceTracker,
        keep_last: int = 50,
    ) -> dict[str, int]:
        """Compute per-source archive thresholds.

        Keeps the last `keep_last` messages per source.
        Returns {src: min_seq_to_keep}.
        """
        thresholds: dict[str, int] = {}
        for src, state in seq_tracker.all_sources().items():
            threshold = max(1, state.last_seq - keep_last + 1)
            thresholds[src] = threshold
        return thresholds

    @staticmethod
    def collect(
        bus_path: str | Path,
        archive_path: str | Path,
        thresholds: dict[str, int],
        compact: bool = False,
    ) -> int:
        """Archive messages below thresholds and compact the bus.

        Messages with seq < threshold[src] are moved to archive.
        Messages without seq are always kept (legacy compatibility).
        Uses atomic write: temp file + os.replace().

        Returns the number of messages archived.
        """
        bus_path = Path(bus_path)
        archive_path = Path(archive_path)

        if not bus_path.exists():
            return 0

        # Read all messages (using permissive parsing to handle edge cases)
        from .bus import read_bus
        messages = read_bus(bus_path)

        active = []
        archived = []

        for msg in messages:
            seq = getattr(msg, "seq", None)
            src = msg.src
            if seq is not None and src in thresholds and seq < thresholds[src]:
                archived.append(msg)
            else:
                active.append(msg)

        if not archived:
            return 0

        from .message import Message
        _serialize = Message.to_compact_jsonl if compact else Message.to_jsonl

        # Append archived to archive file
        with archive_path.open("a", encoding="utf-8") as f:
            for msg in archived:
                f.write(_serialize(msg) + "\n")

        # Atomic compaction: write active to temp, then rename
        bus_dir = bus_path.parent
        fd, tmp_path = tempfile.mkstemp(dir=bus_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                for msg in active:
                    f.write(_serialize(msg) + "\n")
            os.replace(tmp_path, bus_path)
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        return len(archived)


# ---------------------------------------------------------------------------
# Integration Helper
# ---------------------------------------------------------------------------

class BusIntegrityChecker:
    """Combines SequenceTracker + OwnershipRegistry + F3/F4 for bus validation.

    Provides a single check_write() / check_read() entry point.
    F3: WriteVectorTracker for causal ordering (optional).
    F4: ConflictLog for forensic recording (optional).
    """

    def __init__(
        self,
        seq_tracker: SequenceTracker,
        ownership: OwnershipRegistry,
        wv_tracker: WriteVectorTracker | None = None,
        conflict_log: ConflictLog | None = None,
    ) -> None:
        self.seq = seq_tracker
        self.ownership = ownership
        self.wv = wv_tracker
        self.conflict_log = conflict_log

    def generate_write_vector(self) -> WriteVector | None:
        """Generate a write vector from current seq_tracker state.

        Returns None if no WriteVectorTracker is configured.
        """
        if self.wv is None:
            return None
        return self.wv.current_vector()

    def check_write(
        self,
        message,
        writer_id: str,
        seq: int | None = None,
        w: WriteVector | None = None,
    ) -> list[str]:
        """Validate a message before writing to bus.

        Returns list of violation descriptions (empty = OK).
        Checks:
        1. Ownership: writer_id authorized for message.src
        2. Sequence: seq is next expected for message.src (if seq provided)
        3. Write vector: no concurrent conflicts (if w provided and tracker available)
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
        # F3: Write vector conflict check
        if w is not None and self.wv is not None and seq is not None:
            conflicts = self.wv.detect_conflicts(message.src, seq, w)
            for c in conflicts:
                violations.append(
                    f"concurrent: {c['src1']}@{c['seq1']} conflicts with "
                    f"{c['src2']}@{c['seq2']}"
                )
                # F4: Log conflict if log is available
                if self.conflict_log is not None:
                    self.conflict_log.record_concurrent(
                        c["src1"], c["seq1"], c["src2"], c["seq2"],
                    )
        return violations

    def check_read(self, message, seq: int | None = None) -> list[str]:
        """Validate a message read from bus.

        Returns list of anomaly descriptions.
        Checks sequence gap/duplicate detection.
        Logs anomalies to conflict log if available.
        """
        anomalies: list[str] = []
        if seq is not None:
            if self.seq.detect_duplicate(message.src, seq):
                desc = f"duplicate: seq={seq} for src='{message.src}'"
                anomalies.append(desc)
                if self.conflict_log is not None:
                    self.conflict_log.record_anomaly(
                        "duplicate", message.src, seq=seq,
                        expected=self.seq.next_seq(message.src),
                    )
            gap = self.seq.detect_gap(message.src, seq)
            if gap is not None:
                desc = f"gap: src='{message.src}' expected={gap[0]} got={gap[1]}"
                anomalies.append(desc)
                if self.conflict_log is not None:
                    self.conflict_log.record_anomaly(
                        "gap", message.src, seq=seq, expected=gap[0],
                    )
        # F3: Record write vector if present
        w_data = getattr(message, "w", None)
        if w_data is not None and self.wv is not None and seq is not None:
            w = WriteVector.from_dict(w_data) if isinstance(w_data, dict) else w_data
            conflicts = self.wv.detect_conflicts(message.src, seq, w)
            for c in conflicts:
                desc = (
                    f"concurrent: {c['src1']}@{c['seq1']} conflicts with "
                    f"{c['src2']}@{c['seq2']}"
                )
                anomalies.append(desc)
                if self.conflict_log is not None:
                    self.conflict_log.record_concurrent(
                        c["src1"], c["seq1"], c["src2"], c["seq2"],
                    )
            ts_str = message.ts.isoformat() if hasattr(message, "ts") else ""
            self.wv.record(message.src, seq, w, ts_str)
        return anomalies
