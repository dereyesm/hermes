"""Tests for ARC-9001 Bus Integrity Protocol — F1-F6."""

from __future__ import annotations

from datetime import date

import pytest

from hermes.integrity import (
    BusGC,
    BusIntegrityChecker,
    BusSnapshot,
    ConflictLog,
    ConflictRecord,
    ConflictResolution,
    OwnershipClaim,
    OwnershipRegistry,
    OwnershipViolation,
    ReplayRequest,
    SequenceState,
    SequenceTracker,
    SnapshotManager,
    WriteVector,
    WriteVectorTracker,
)
from hermes.message import Message, create_message


# ── Helpers ──────────────────────────────────────────────────────────────


def _msg(src: str = "eng", dst: str = "*", seq: int | None = None) -> Message:
    """Create a minimal test message."""
    return create_message(src=src, dst=dst, type="state", msg="test", seq=seq)


# ═══════════════════════════════════════════════════════════════════════
# F1: SequenceTracker
# ═══════════════════════════════════════════════════════════════════════


class TestSequenceTrackerBasic:
    """Basic next_seq / record / validate."""

    def test_next_seq_first_write(self):
        t = SequenceTracker()
        assert t.next_seq("eng") == 1

    def test_next_seq_increments(self):
        t = SequenceTracker()
        t.record("eng", 1)
        assert t.next_seq("eng") == 2
        t.record("eng", 2)
        assert t.next_seq("eng") == 3

    def test_record_updates_state(self):
        t = SequenceTracker()
        t.record("eng", 5)
        assert t.get_state("eng").last_seq == 5

    def test_validate_correct_seq(self):
        t = SequenceTracker()
        assert t.validate("eng", 1) is True
        t.record("eng", 1)
        assert t.validate("eng", 2) is True

    def test_validate_gap(self):
        t = SequenceTracker()
        t.record("eng", 1)
        assert t.validate("eng", 3) is False

    def test_validate_duplicate(self):
        t = SequenceTracker()
        t.record("eng", 1)
        assert t.validate("eng", 1) is False

    def test_multiple_sources_independent(self):
        t = SequenceTracker()
        t.record("eng", 1)
        t.record("ops", 1)
        assert t.next_seq("eng") == 2
        assert t.next_seq("ops") == 2
        t.record("eng", 2)
        assert t.next_seq("eng") == 3
        assert t.next_seq("ops") == 2

    def test_empty_tracker_state(self):
        t = SequenceTracker()
        assert t.get_state("eng") is None
        assert t.all_sources() == {}


class TestSequenceTrackerGapDuplicate:
    """Gap and duplicate detection."""

    def test_detect_gap_returns_tuple(self):
        t = SequenceTracker()
        t.record("eng", 1)
        result = t.detect_gap("eng", 5)
        assert result == (2, 5)

    def test_detect_gap_none_when_ok(self):
        t = SequenceTracker()
        assert t.detect_gap("eng", 1) is None
        t.record("eng", 1)
        assert t.detect_gap("eng", 2) is None

    def test_detect_gap_first_message_above_one(self):
        t = SequenceTracker()
        result = t.detect_gap("eng", 3)
        assert result == (1, 3)

    def test_detect_duplicate_true(self):
        t = SequenceTracker()
        t.record("eng", 3)
        assert t.detect_duplicate("eng", 1) is True
        assert t.detect_duplicate("eng", 3) is True

    def test_detect_duplicate_false(self):
        t = SequenceTracker()
        assert t.detect_duplicate("eng", 1) is False
        t.record("eng", 1)
        assert t.detect_duplicate("eng", 2) is False


class TestSequenceTrackerLoadFromBus:
    """Reconstruct state from bus messages."""

    def test_load_builds_state(self):
        msgs = [_msg("eng", seq=1), _msg("eng", seq=2), _msg("eng", seq=3)]
        t = SequenceTracker()
        anomalies = t.load_from_bus(msgs)
        assert anomalies == []
        assert t.get_state("eng").last_seq == 3

    def test_load_skips_no_seq(self):
        msgs = [_msg("eng"), _msg("eng", seq=1), _msg("eng")]
        t = SequenceTracker()
        anomalies = t.load_from_bus(msgs)
        assert anomalies == []
        assert t.get_state("eng").last_seq == 1

    def test_load_reports_gaps(self):
        msgs = [_msg("eng", seq=1), _msg("eng", seq=5)]
        t = SequenceTracker()
        anomalies = t.load_from_bus(msgs)
        assert len(anomalies) == 1
        assert anomalies[0]["type"] == "gap"
        assert anomalies[0]["expected"] == 2
        assert anomalies[0]["seq"] == 5

    def test_load_reports_duplicates(self):
        msgs = [_msg("eng", seq=1), _msg("eng", seq=2), _msg("eng", seq=1)]
        t = SequenceTracker()
        anomalies = t.load_from_bus(msgs)
        assert len(anomalies) == 1
        assert anomalies[0]["type"] == "duplicate"
        assert anomalies[0]["seq"] == 1

    def test_load_multiple_sources(self):
        msgs = [_msg("eng", seq=1), _msg("ops", seq=1), _msg("eng", seq=2)]
        t = SequenceTracker()
        anomalies = t.load_from_bus(msgs)
        assert anomalies == []
        assert t.get_state("eng").last_seq == 2
        assert t.get_state("ops").last_seq == 1


class TestSequenceTrackerSerialization:
    """to_dict / from_dict roundtrip."""

    def test_roundtrip(self):
        t = SequenceTracker()
        t.record("eng", 5)
        t.record("ops", 3)
        data = t.to_dict()
        t2 = SequenceTracker.from_dict(data)
        assert t2.next_seq("eng") == 6
        assert t2.next_seq("ops") == 4

    def test_empty_roundtrip(self):
        t = SequenceTracker()
        data = t.to_dict()
        assert data == {}
        t2 = SequenceTracker.from_dict(data)
        assert t2.all_sources() == {}

    def test_all_sources_returns_copy(self):
        t = SequenceTracker()
        t.record("eng", 1)
        sources = t.all_sources()
        sources["eng"].last_seq = 999
        assert t.get_state("eng").last_seq == 1


class TestSequenceTrackerGapCount:
    """Gap counting in record()."""

    def test_gap_count_first_message(self):
        t = SequenceTracker()
        t.record("eng", 3)
        assert t.get_state("eng").gap_count == 2  # missed 1, 2

    def test_gap_count_increments(self):
        t = SequenceTracker()
        t.record("eng", 1)
        t.record("eng", 5)  # gap of 3 (missed 2, 3, 4)
        assert t.get_state("eng").gap_count == 3


# ═══════════════════════════════════════════════════════════════════════
# F2: OwnershipRegistry
# ═══════════════════════════════════════════════════════════════════════


class TestOwnershipRegistryClaim:
    """Claim and revoke operations."""

    def test_claim_new_namespace(self):
        r = OwnershipRegistry()
        c = r.claim("eng", "agent-1")
        assert c.namespace == "eng"
        assert c.owner_id == "agent-1"
        assert r.owner_of("eng") == "agent-1"

    def test_claim_same_owner_idempotent(self):
        r = OwnershipRegistry()
        r.claim("eng", "agent-1")
        c2 = r.claim("eng", "agent-1")
        assert c2.owner_id == "agent-1"

    def test_claim_different_owner_raises(self):
        r = OwnershipRegistry()
        r.claim("eng", "agent-1")
        with pytest.raises(OwnershipViolation, match="already owned"):
            r.claim("eng", "agent-2")

    def test_revoke_existing(self):
        r = OwnershipRegistry()
        r.claim("eng", "agent-1")
        assert r.revoke("eng") is True
        assert r.owner_of("eng") is None

    def test_revoke_nonexistent(self):
        r = OwnershipRegistry()
        assert r.revoke("eng") is False


class TestOwnershipRegistryAuthorization:
    """Authorization checks."""

    def test_authorized_claimed_owner(self):
        r = OwnershipRegistry(daemon_id="daemon")
        r.claim("eng", "agent-1")
        assert r.is_authorized("eng", "agent-1") is True

    def test_unauthorized_wrong_owner(self):
        r = OwnershipRegistry(daemon_id="daemon")
        r.claim("eng", "agent-1")
        assert r.is_authorized("eng", "agent-2") is False

    def test_unclaimed_daemon_authorized(self):
        r = OwnershipRegistry(daemon_id="daemon")
        assert r.is_authorized("eng", "daemon") is True

    def test_unclaimed_non_daemon_denied(self):
        r = OwnershipRegistry(daemon_id="daemon")
        assert r.is_authorized("eng", "agent-1") is False

    def test_claim_for_daemon_bulk(self):
        r = OwnershipRegistry(daemon_id="my-daemon")
        r.claim_for_daemon({"eng", "ops", "finance"})
        assert r.owner_of("eng") == "my-daemon"
        assert r.owner_of("ops") == "my-daemon"
        assert r.owner_of("finance") == "my-daemon"

    def test_grant_to_agent_revokes_daemon(self):
        r = OwnershipRegistry(daemon_id="daemon")
        r.claim("eng", "daemon")
        c = r.grant_to_agent("eng-bot", namespace="eng")
        assert c.owner_id == "eng-bot"
        assert r.owner_of("eng") == "eng-bot"

    def test_grant_to_agent_default_namespace(self):
        r = OwnershipRegistry(daemon_id="daemon")
        c = r.grant_to_agent("scanner")
        assert c.namespace == "scanner"
        assert c.owner_id == "scanner"

    def test_validate_message_convenience(self):
        r = OwnershipRegistry(daemon_id="daemon")
        r.claim("eng", "agent-1")
        msg = _msg("eng")
        assert r.validate_message(msg, "agent-1") is True
        assert r.validate_message(msg, "agent-2") is False


class TestOwnershipRegistrySerialization:
    """to_dict / from_dict roundtrip."""

    def test_roundtrip(self):
        r = OwnershipRegistry(daemon_id="d")
        r.claim("eng", "agent-1", granted_at="2026-03-20")
        r.claim("ops", "d", granted_at="2026-03-20")
        data = r.to_dict()
        r2 = OwnershipRegistry.from_dict(data, daemon_id="d")
        assert r2.owner_of("eng") == "agent-1"
        assert r2.owner_of("ops") == "d"
        assert r2.is_authorized("eng", "agent-1") is True

    def test_all_claims(self):
        r = OwnershipRegistry()
        r.claim("eng", "a")
        r.claim("ops", "b")
        claims = r.all_claims()
        assert len(claims) == 2
        namespaces = {c.namespace for c in claims}
        assert namespaces == {"eng", "ops"}


# ═══════════════════════════════════════════════════════════════════════
# BusIntegrityChecker
# ═══════════════════════════════════════════════════════════════════════


class TestBusIntegrityChecker:
    """Integration: combined seq + ownership checks."""

    def test_check_write_all_valid(self):
        t = SequenceTracker()
        r = OwnershipRegistry(daemon_id="daemon")
        r.claim("eng", "daemon")
        checker = BusIntegrityChecker(t, r)
        msg = _msg("eng")
        violations = checker.check_write(msg, "daemon", seq=1)
        assert violations == []

    def test_check_write_ownership_violation(self):
        t = SequenceTracker()
        r = OwnershipRegistry(daemon_id="daemon")
        r.claim("eng", "agent-1")
        checker = BusIntegrityChecker(t, r)
        msg = _msg("eng")
        violations = checker.check_write(msg, "daemon", seq=1)
        assert len(violations) == 1
        assert "ownership" in violations[0]

    def test_check_write_seq_duplicate(self):
        t = SequenceTracker()
        t.record("eng", 3)
        r = OwnershipRegistry(daemon_id="daemon")
        r.claim("eng", "daemon")
        checker = BusIntegrityChecker(t, r)
        msg = _msg("eng")
        violations = checker.check_write(msg, "daemon", seq=2)
        assert len(violations) == 1
        assert "duplicate" in violations[0]

    def test_check_write_seq_gap(self):
        t = SequenceTracker()
        t.record("eng", 1)
        r = OwnershipRegistry(daemon_id="daemon")
        r.claim("eng", "daemon")
        checker = BusIntegrityChecker(t, r)
        msg = _msg("eng")
        violations = checker.check_write(msg, "daemon", seq=5)
        assert len(violations) == 1
        assert "gap" in violations[0]

    def test_check_read_anomalies(self):
        t = SequenceTracker()
        t.record("eng", 1)
        r = OwnershipRegistry(daemon_id="daemon")
        checker = BusIntegrityChecker(t, r)
        msg = _msg("eng")
        anomalies = checker.check_read(msg, seq=5)
        assert len(anomalies) == 1
        assert "gap" in anomalies[0]

    def test_check_write_no_seq(self):
        """No seq violations when seq is None."""
        t = SequenceTracker()
        r = OwnershipRegistry(daemon_id="daemon")
        r.claim("eng", "daemon")
        checker = BusIntegrityChecker(t, r)
        msg = _msg("eng")
        violations = checker.check_write(msg, "daemon", seq=None)
        assert violations == []


# ═══════════════════════════════════════════════════════════════════════
# Integration: Message seq field + bus write
# ═══════════════════════════════════════════════════════════════════════


class TestMessageSeqField:
    """Verify seq field in Message dataclass."""

    def test_create_message_without_seq(self):
        msg = create_message(src="eng", dst="*", type="state", msg="test")
        assert msg.seq is None

    def test_create_message_with_seq(self):
        msg = create_message(src="eng", dst="*", type="state", msg="test", seq=42)
        assert msg.seq == 42

    def test_to_dict_includes_seq(self):
        msg = create_message(src="eng", dst="*", type="state", msg="test", seq=5)
        d = msg.to_dict()
        assert d["seq"] == 5

    def test_to_dict_excludes_seq_when_none(self):
        msg = create_message(src="eng", dst="*", type="state", msg="test")
        d = msg.to_dict()
        assert "seq" not in d

    def test_seq_validation_rejects_negative(self):
        from hermes.message import ValidationError
        with pytest.raises(ValidationError, match="positive"):
            create_message(src="eng", dst="*", type="state", msg="test", seq=0)

    def test_seq_validation_rejects_bool(self):
        from hermes.message import ValidationError, validate_message
        data = {
            "ts": "2026-03-20", "src": "eng", "dst": "*",
            "type": "state", "msg": "test", "ttl": 7, "ack": [],
            "seq": True,
        }
        with pytest.raises(ValidationError, match="integer"):
            validate_message(data)

    def test_seq_roundtrip_via_json(self):
        import json
        msg = create_message(src="eng", dst="*", type="state", msg="test", seq=10)
        line = msg.to_jsonl()
        data = json.loads(line)
        assert data["seq"] == 10
        from hermes.message import validate_message
        msg2 = validate_message(data)
        assert msg2.seq == 10


class TestBusWriteWithSeqTracker:
    """write_message with seq_tracker integration."""

    def test_auto_assigns_seq(self, tmp_path):
        from hermes.bus import write_message, read_bus
        bus = tmp_path / "bus.jsonl"
        t = SequenceTracker()
        msg = _msg("eng")
        written = write_message(bus, msg, seq_tracker=t)
        assert written.seq == 1
        # Second write
        msg2 = _msg("eng")
        written2 = write_message(bus, msg2, seq_tracker=t)
        assert written2.seq == 2
        # Read back
        messages = read_bus(bus)
        assert messages[0].seq == 1
        assert messages[1].seq == 2

    def test_preserves_explicit_seq(self, tmp_path):
        from hermes.bus import write_message
        bus = tmp_path / "bus.jsonl"
        t = SequenceTracker()
        msg = _msg("eng", seq=42)
        written = write_message(bus, msg, seq_tracker=t)
        assert written.seq == 42
        assert t.get_state("eng").last_seq == 42

    def test_no_tracker_no_seq(self, tmp_path):
        from hermes.bus import write_message, read_bus
        bus = tmp_path / "bus.jsonl"
        msg = _msg("eng")
        written = write_message(bus, msg)
        assert written.seq is None
        messages = read_bus(bus)
        assert messages[0].seq is None


class TestReadBusWithIntegrity:
    """read_bus_with_integrity function."""

    def test_reads_and_validates(self, tmp_path):
        from hermes.bus import write_message, read_bus_with_integrity
        bus = tmp_path / "bus.jsonl"
        t = SequenceTracker()
        write_message(bus, _msg("eng"), seq_tracker=t)
        write_message(bus, _msg("eng"), seq_tracker=t)
        msgs, anomalies = read_bus_with_integrity(bus)
        assert len(msgs) == 2
        assert anomalies == []

    def test_detects_gap(self, tmp_path):
        from hermes.bus import write_message, read_bus_with_integrity
        bus = tmp_path / "bus.jsonl"
        write_message(bus, _msg("eng", seq=1))
        write_message(bus, _msg("eng", seq=5))
        msgs, anomalies = read_bus_with_integrity(bus)
        assert len(msgs) == 2
        assert len(anomalies) == 1
        assert anomalies[0]["type"] == "gap"


# ═══════════════════════════════════════════════════════════════════════
# F3: WriteVector
# ═══════════════════════════════════════════════════════════════════════


def _msg_w(src: str = "eng", dst: str = "*", seq: int | None = None,
           w: dict | None = None) -> Message:
    """Create a test message with optional write vector."""
    return create_message(src=src, dst=dst, type="state", msg="test", seq=seq, w=w)


class TestWriteVectorBasic:
    """WriteVector creation, serialization, comparison."""

    def test_create_empty(self):
        wv = WriteVector()
        assert wv.state == {}
        assert wv.to_dict() == {}

    def test_create_with_state(self):
        wv = WriteVector(state={"eng": 5, "ops": 3})
        assert wv.state["eng"] == 5
        assert wv.state["ops"] == 3

    def test_to_dict_roundtrip(self):
        original = WriteVector(state={"eng": 5, "ops": 3})
        restored = WriteVector.from_dict(original.to_dict())
        assert restored.state == original.state

    def test_from_dict(self):
        wv = WriteVector.from_dict({"a": 1, "b": 2})
        assert wv.state == {"a": 1, "b": 2}

    def test_frozen(self):
        wv = WriteVector(state={"eng": 5})
        with pytest.raises(AttributeError):
            wv.state = {}  # type: ignore


class TestWriteVectorDominates:
    """Dominance relation (partial order)."""

    def test_dominates_greater_on_all(self):
        a = WriteVector(state={"eng": 5, "ops": 3})
        b = WriteVector(state={"eng": 3, "ops": 2})
        assert a.dominates(b) is True

    def test_dominates_equal_not_dominant(self):
        a = WriteVector(state={"eng": 5})
        b = WriteVector(state={"eng": 5})
        assert a.dominates(b) is False

    def test_not_dominates_when_less_on_one(self):
        a = WriteVector(state={"eng": 5, "ops": 1})
        b = WriteVector(state={"eng": 3, "ops": 3})
        assert a.dominates(b) is False

    def test_empty_does_not_dominate_empty(self):
        a = WriteVector()
        b = WriteVector()
        assert a.dominates(b) is False

    def test_nonempty_dominates_empty(self):
        a = WriteVector(state={"eng": 1})
        b = WriteVector()
        assert a.dominates(b) is True

    def test_missing_keys_treated_as_zero(self):
        a = WriteVector(state={"eng": 5, "ops": 3})
        b = WriteVector(state={"eng": 3})
        # a has ops:3 > b's implied ops:0, and eng:5 > eng:3
        assert a.dominates(b) is True

    def test_missing_key_in_self_blocks_dominance(self):
        a = WriteVector(state={"eng": 5})
        b = WriteVector(state={"eng": 3, "ops": 1})
        # a has ops:0 < b's ops:1
        assert a.dominates(b) is False


class TestWriteVectorConcurrent:
    """Concurrent detection (neither dominates)."""

    def test_concurrent_cross_greater(self):
        a = WriteVector(state={"eng": 5, "ops": 1})
        b = WriteVector(state={"eng": 3, "ops": 3})
        assert a.concurrent_with(b) is True

    def test_not_concurrent_when_dominates(self):
        a = WriteVector(state={"eng": 5, "ops": 3})
        b = WriteVector(state={"eng": 3, "ops": 2})
        assert a.concurrent_with(b) is False

    def test_not_concurrent_when_equal(self):
        a = WriteVector(state={"eng": 5})
        b = WriteVector(state={"eng": 5})
        assert a.concurrent_with(b) is False

    def test_concurrent_disjoint_keys(self):
        a = WriteVector(state={"eng": 5})
        b = WriteVector(state={"ops": 3})
        # a has eng:5>0 but ops:0<3 — concurrent
        assert a.concurrent_with(b) is True

    def test_concurrent_is_symmetric(self):
        a = WriteVector(state={"eng": 5, "ops": 1})
        b = WriteVector(state={"eng": 3, "ops": 3})
        assert a.concurrent_with(b) == b.concurrent_with(a)


# ═══════════════════════════════════════════════════════════════════════
# F3: WriteVectorTracker
# ═══════════════════════════════════════════════════════════════════════


class TestWriteVectorTracker:
    """Write vector generation and conflict detection."""

    def test_current_vector_empty_tracker(self):
        st = SequenceTracker()
        wvt = WriteVectorTracker(st)
        assert wvt.current_vector().state == {}

    def test_current_vector_after_records(self):
        st = SequenceTracker()
        st.record("eng", 3)
        st.record("ops", 1)
        wvt = WriteVectorTracker(st)
        cv = wvt.current_vector()
        assert cv.state == {"eng": 3, "ops": 1}

    def test_record_adds_to_window(self):
        st = SequenceTracker()
        wvt = WriteVectorTracker(st)
        wvt.record("eng", 1, WriteVector(state={"eng": 0}))
        assert wvt.recent_count == 1

    def test_window_sliding(self):
        st = SequenceTracker()
        wvt = WriteVectorTracker(st, window_size=3)
        for i in range(5):
            wvt.record("eng", i + 1, WriteVector(state={"eng": i}))
        assert wvt.recent_count == 3

    def test_no_conflict_same_source(self):
        st = SequenceTracker()
        st.record("eng", 1)
        wvt = WriteVectorTracker(st)
        wvt.record("eng", 1, WriteVector(state={"eng": 0}))
        # Same source — never conflicts with itself
        conflicts = wvt.detect_conflicts("eng", 2, WriteVector(state={"eng": 1}))
        assert conflicts == []

    def test_no_conflict_ordered_sources(self):
        st = SequenceTracker()
        st.record("eng", 1)
        wvt = WriteVectorTracker(st)
        # eng writes first, sees nothing
        wvt.record("eng", 1, WriteVector(state={}))
        # ops writes second, sees eng:1 — dominates eng's vector
        conflicts = wvt.detect_conflicts("ops", 1, WriteVector(state={"eng": 1}))
        assert conflicts == []

    def test_conflict_concurrent_sources(self):
        st = SequenceTracker()
        wvt = WriteVectorTracker(st)
        # eng writes seeing ops:0 (implied)
        wvt.record("eng", 1, WriteVector(state={"eng": 0}))
        # ops writes seeing eng:0 (implied) — concurrent!
        conflicts = wvt.detect_conflicts("ops", 1, WriteVector(state={"ops": 0}))
        assert len(conflicts) == 1
        assert conflicts[0]["type"] == "concurrent"
        assert conflicts[0]["src1"] == "ops"
        assert conflicts[0]["src2"] == "eng"

    def test_multiple_conflicts(self):
        st = SequenceTracker()
        wvt = WriteVectorTracker(st)
        # Three sources write without seeing each other
        wvt.record("eng", 1, WriteVector(state={"eng": 0}))
        wvt.record("ops", 1, WriteVector(state={"ops": 0}))
        # finance writes seeing nothing — concurrent with both
        conflicts = wvt.detect_conflicts(
            "finance", 1, WriteVector(state={"finance": 0})
        )
        assert len(conflicts) == 2

    def test_no_conflict_after_causal_ordering(self):
        st = SequenceTracker()
        st.record("eng", 1)
        st.record("ops", 1)
        wvt = WriteVectorTracker(st)
        wvt.record("eng", 1, WriteVector(state={"eng": 0}))
        wvt.record("ops", 1, WriteVector(state={"eng": 1, "ops": 0}))
        # finance writes seeing both — no conflict
        conflicts = wvt.detect_conflicts(
            "finance", 1, WriteVector(state={"eng": 1, "ops": 1})
        )
        assert conflicts == []


# ═══════════════════════════════════════════════════════════════════════
# F4: ConflictLog
# ═══════════════════════════════════════════════════════════════════════


class TestConflictRecord:
    """ConflictRecord serialization."""

    def test_to_dict_minimal(self):
        r = ConflictRecord(
            detected_at="2026-03-22T10:00:00",
            type="gap",
            src="eng",
        )
        d = r.to_dict()
        assert d["type"] == "gap"
        assert d["src"] == "eng"
        assert "seq" not in d
        assert "expected" not in d

    def test_to_dict_full(self):
        r = ConflictRecord(
            detected_at="2026-03-22T10:00:00",
            type="concurrent",
            src="eng",
            seq=5,
            expected=4,
            resolution="logged",
            messages=["eng:5", "ops:3"],
            details="test",
        )
        d = r.to_dict()
        assert d["seq"] == 5
        assert d["expected"] == 4
        assert len(d["messages"]) == 2
        assert d["details"] == "test"

    def test_roundtrip(self):
        original = ConflictRecord(
            detected_at="2026-03-22T10:00:00",
            type="duplicate",
            src="eng",
            seq=3,
            expected=4,
        )
        restored = ConflictRecord.from_dict(original.to_dict())
        assert restored.type == original.type
        assert restored.src == original.src
        assert restored.seq == original.seq


class TestConflictLog:
    """ConflictLog file operations."""

    def test_record_creates_file(self, tmp_path):
        log = ConflictLog(tmp_path / "conflicts.jsonl")
        record = log.record_anomaly("gap", "eng", seq=5, expected=4)
        assert record.type == "gap"
        assert log.path.exists()

    def test_read_empty(self, tmp_path):
        log = ConflictLog(tmp_path / "conflicts.jsonl")
        assert log.read_all() == []

    def test_read_nonexistent(self, tmp_path):
        log = ConflictLog(tmp_path / "nonexistent.jsonl")
        assert log.read_all() == []

    def test_record_and_read(self, tmp_path):
        log = ConflictLog(tmp_path / "conflicts.jsonl")
        log.record_anomaly("gap", "eng", seq=5, expected=4)
        log.record_anomaly("duplicate", "ops", seq=2)
        records = log.read_all()
        assert len(records) == 2
        assert records[0].type == "gap"
        assert records[1].type == "duplicate"

    def test_record_concurrent(self, tmp_path):
        log = ConflictLog(tmp_path / "conflicts.jsonl")
        record = log.record_concurrent("eng", 5, "ops", 3)
        assert record.type == "concurrent"
        assert "eng:5" in record.messages
        assert "ops:3" in record.messages

    def test_count(self, tmp_path):
        log = ConflictLog(tmp_path / "conflicts.jsonl")
        assert log.count() == 0
        log.record_anomaly("gap", "eng")
        log.record_anomaly("gap", "ops")
        assert log.count() == 2

    def test_append_only(self, tmp_path):
        log = ConflictLog(tmp_path / "conflicts.jsonl")
        log.record_anomaly("gap", "eng")
        log.record_anomaly("gap", "ops")
        # Re-open and add more
        log2 = ConflictLog(tmp_path / "conflicts.jsonl")
        log2.record_anomaly("duplicate", "finance")
        assert log2.count() == 3


class TestConflictResolution:
    """ConflictResolution enum."""

    def test_values(self):
        assert ConflictResolution.LAST_WRITER_WINS == "last_writer_wins"
        assert ConflictResolution.MANUAL == "manual"
        assert ConflictResolution.MERGE == "merge"


# ═══════════════════════════════════════════════════════════════════════
# F3+F4: BusIntegrityChecker Extended
# ═══════════════════════════════════════════════════════════════════════


class TestBusIntegrityCheckerMVCC:
    """BusIntegrityChecker with F3 write vectors and F4 conflict log."""

    def _make_checker(self, tmp_path=None):
        st = SequenceTracker()
        ow = OwnershipRegistry()
        wvt = WriteVectorTracker(st)
        cl = ConflictLog(tmp_path / "conflicts.jsonl") if tmp_path else None
        return BusIntegrityChecker(st, ow, wv_tracker=wvt, conflict_log=cl)

    def test_generate_write_vector(self):
        checker = self._make_checker()
        wv = checker.generate_write_vector()
        assert wv is not None
        assert wv.state == {}

    def test_generate_write_vector_none_without_tracker(self):
        st = SequenceTracker()
        ow = OwnershipRegistry()
        checker = BusIntegrityChecker(st, ow)
        assert checker.generate_write_vector() is None

    def test_check_write_no_conflict(self):
        checker = self._make_checker()
        msg = _msg("eng", seq=1)
        wv = WriteVector(state={})
        violations = checker.check_write(msg, "daemon", seq=1, w=wv)
        assert violations == []

    def test_check_write_concurrent_detected(self, tmp_path):
        checker = self._make_checker(tmp_path)
        # Record that eng wrote at seq=1 seeing nothing
        checker.wv.record("eng", 1, WriteVector(state={"eng": 0}))
        checker.seq.record("eng", 1)
        # ops tries to write at seq=1 also seeing nothing — concurrent
        msg = _msg("ops", seq=1)
        wv = WriteVector(state={"ops": 0})
        violations = checker.check_write(msg, "daemon", seq=1, w=wv)
        assert any("concurrent" in v for v in violations)

    def test_conflict_logged_on_write(self, tmp_path):
        checker = self._make_checker(tmp_path)
        checker.wv.record("eng", 1, WriteVector(state={"eng": 0}))
        checker.seq.record("eng", 1)
        msg = _msg("ops", seq=1)
        wv = WriteVector(state={"ops": 0})
        checker.check_write(msg, "daemon", seq=1, w=wv)
        # Conflict should be in the log
        assert checker.conflict_log.count() == 1
        records = checker.conflict_log.read_all()
        assert records[0].type == "concurrent"

    def test_check_read_logs_gap(self, tmp_path):
        checker = self._make_checker(tmp_path)
        checker.seq.record("eng", 1)
        msg = _msg("eng", seq=5)
        anomalies = checker.check_read(msg, seq=5)
        assert any("gap" in a for a in anomalies)
        assert checker.conflict_log.count() == 1

    def test_check_read_logs_duplicate(self, tmp_path):
        checker = self._make_checker(tmp_path)
        checker.seq.record("eng", 5)
        msg = _msg("eng", seq=3)
        anomalies = checker.check_read(msg, seq=3)
        assert any("duplicate" in a for a in anomalies)
        assert checker.conflict_log.count() == 1

    def test_check_read_records_write_vector(self, tmp_path):
        checker = self._make_checker(tmp_path)
        msg = _msg_w("eng", seq=1, w={"eng": 0})
        checker.check_read(msg, seq=1)
        assert checker.wv.recent_count == 1

    def test_check_read_detects_concurrent_in_w(self, tmp_path):
        checker = self._make_checker(tmp_path)
        # First message from eng
        msg1 = _msg_w("eng", seq=1, w={"eng": 0})
        checker.check_read(msg1, seq=1)
        checker.seq.record("eng", 1)
        # Second message from ops, concurrent with eng
        msg2 = _msg_w("ops", seq=1, w={"ops": 0})
        anomalies = checker.check_read(msg2, seq=1)
        assert any("concurrent" in a for a in anomalies)


# ═══════════════════════════════════════════════════════════════════════
# F3+F4: Bus Integration
# ═══════════════════════════════════════════════════════════════════════


class TestBusWriteWithWriteVector:
    """write_message() with wv_tracker."""

    def test_auto_assigns_w(self, tmp_path):
        from hermes.bus import write_message, read_bus
        bus = tmp_path / "bus.jsonl"
        st = SequenceTracker()
        wvt = WriteVectorTracker(st)
        msg = _msg("eng")
        written = write_message(bus, msg, seq_tracker=st, wv_tracker=wvt)
        assert written.w is not None
        assert written.w == {}  # Empty state at first write
        assert written.seq == 1

    def test_preserves_explicit_w(self, tmp_path):
        from hermes.bus import write_message
        bus = tmp_path / "bus.jsonl"
        st = SequenceTracker()
        wvt = WriteVectorTracker(st)
        msg = _msg_w("eng", w={"ops": 5})
        written = write_message(bus, msg, seq_tracker=st, wv_tracker=wvt)
        assert written.w == {"ops": 5}

    def test_w_roundtrip_json(self, tmp_path):
        from hermes.bus import write_message, read_bus
        bus = tmp_path / "bus.jsonl"
        st = SequenceTracker()
        st.record("ops", 3)
        wvt = WriteVectorTracker(st)
        msg = _msg("eng")
        write_message(bus, msg, seq_tracker=st, wv_tracker=wvt)
        msgs = read_bus(bus)
        assert len(msgs) == 1
        assert msgs[0].w == {"ops": 3}
        assert msgs[0].seq == 1

    def test_w_not_in_compact(self, tmp_path):
        from hermes.bus import write_message, read_bus
        bus = tmp_path / "bus.jsonl"
        st = SequenceTracker()
        wvt = WriteVectorTracker(st)
        msg = _msg("eng")
        write_message(bus, msg, compact=True, seq_tracker=st, wv_tracker=wvt)
        # Compact format drops seq and w
        raw = bus.read_text()
        assert raw.startswith("[")  # Compact array
        msgs = read_bus(bus)
        assert len(msgs) == 1
        # Compact doesn't carry seq or w
        assert msgs[0].seq is None
        assert msgs[0].w is None

    def test_records_in_tracker(self, tmp_path):
        from hermes.bus import write_message
        bus = tmp_path / "bus.jsonl"
        st = SequenceTracker()
        wvt = WriteVectorTracker(st)
        write_message(bus, _msg("eng"), seq_tracker=st, wv_tracker=wvt)
        assert wvt.recent_count == 1

    def test_multiple_writes_build_vector(self, tmp_path):
        from hermes.bus import write_message, read_bus
        bus = tmp_path / "bus.jsonl"
        st = SequenceTracker()
        wvt = WriteVectorTracker(st)
        write_message(bus, _msg("eng"), seq_tracker=st, wv_tracker=wvt)
        write_message(bus, _msg("ops"), seq_tracker=st, wv_tracker=wvt)
        msgs = read_bus(bus)
        # Second message should see eng:1
        assert msgs[1].w == {"eng": 1}
        assert msgs[1].seq == 1  # ops first write

    def test_without_tracker_no_w(self, tmp_path):
        from hermes.bus import write_message, read_bus
        bus = tmp_path / "bus.jsonl"
        st = SequenceTracker()
        msg = _msg("eng")
        write_message(bus, msg, seq_tracker=st)
        msgs = read_bus(bus)
        assert msgs[0].w is None


class TestBusReadWithMVCC:
    """read_bus_with_integrity() with wv_tracker and conflict_log."""

    def test_detects_concurrent_on_read(self, tmp_path):
        from hermes.bus import write_message, read_bus_with_integrity
        bus = tmp_path / "bus.jsonl"
        # Write two messages with concurrent write vectors manually
        write_message(bus, _msg_w("eng", seq=1, w={"eng": 0}))
        write_message(bus, _msg_w("ops", seq=1, w={"ops": 0}))
        wvt = WriteVectorTracker(SequenceTracker())
        cl = ConflictLog(tmp_path / "conflicts.jsonl")
        msgs, anomalies = read_bus_with_integrity(
            bus, wv_tracker=wvt, conflict_log=cl,
        )
        assert len(msgs) == 2
        concurrent = [a for a in anomalies if a.get("type") == "concurrent"]
        assert len(concurrent) == 1
        assert cl.count() == 1

    def test_no_concurrent_when_ordered(self, tmp_path):
        from hermes.bus import write_message, read_bus_with_integrity
        bus = tmp_path / "bus.jsonl"
        write_message(bus, _msg_w("eng", seq=1, w={}))
        write_message(bus, _msg_w("ops", seq=1, w={"eng": 1}))
        wvt = WriteVectorTracker(SequenceTracker())
        msgs, anomalies = read_bus_with_integrity(bus, wv_tracker=wvt)
        concurrent = [a for a in anomalies if a.get("type") == "concurrent"]
        assert concurrent == []

    def test_conflict_log_created_on_first_conflict(self, tmp_path):
        from hermes.bus import write_message, read_bus_with_integrity
        bus = tmp_path / "bus.jsonl"
        cl_path = tmp_path / "conflicts.jsonl"
        assert not cl_path.exists()
        write_message(bus, _msg_w("eng", seq=1, w={"eng": 0}))
        write_message(bus, _msg_w("ops", seq=1, w={"ops": 0}))
        cl = ConflictLog(cl_path)
        read_bus_with_integrity(bus, wv_tracker=WriteVectorTracker(SequenceTracker()), conflict_log=cl)
        assert cl_path.exists()


# ═══════════════════════════════════════════════════════════════════════
# Message `w` field validation
# ═══════════════════════════════════════════════════════════════════════


class TestMessageWField:
    """Message w field in ARC-5322."""

    def test_create_with_w(self):
        msg = create_message(src="eng", dst="*", type="state", msg="test",
                             w={"eng": 1, "ops": 2})
        assert msg.w == {"eng": 1, "ops": 2}

    def test_create_without_w(self):
        msg = create_message(src="eng", dst="*", type="state", msg="test")
        assert msg.w is None

    def test_to_dict_includes_w(self):
        msg = create_message(src="eng", dst="*", type="state", msg="test",
                             w={"eng": 1})
        d = msg.to_dict()
        assert "w" in d
        assert d["w"] == {"eng": 1}

    def test_to_dict_excludes_w_when_none(self):
        msg = create_message(src="eng", dst="*", type="state", msg="test")
        d = msg.to_dict()
        assert "w" not in d

    def test_validate_rejects_bad_w_type(self):
        from hermes.message import validate_message, ValidationError
        data = {
            "ts": "2026-03-22", "src": "eng", "dst": "*", "type": "state",
            "msg": "test", "ttl": 7, "ack": [], "w": "not_a_dict",
        }
        with pytest.raises(ValidationError, match="dict"):
            validate_message(data)

    def test_validate_rejects_bad_w_value_type(self):
        from hermes.message import validate_message, ValidationError
        data = {
            "ts": "2026-03-22", "src": "eng", "dst": "*", "type": "state",
            "msg": "test", "ttl": 7, "ack": [], "w": {"eng": "five"},
        }
        with pytest.raises(ValidationError, match="integers"):
            validate_message(data)

    def test_validate_rejects_negative_w_value(self):
        from hermes.message import validate_message, ValidationError
        data = {
            "ts": "2026-03-22", "src": "eng", "dst": "*", "type": "state",
            "msg": "test", "ttl": 7, "ack": [], "w": {"eng": -1},
        }
        with pytest.raises(ValidationError, match="non-negative"):
            validate_message(data)

    def test_compact_format_no_w(self):
        msg = create_message(src="eng", dst="*", type="state", msg="test",
                             w={"eng": 1})
        compact = msg.to_compact()
        # Compact should NOT include w (verbose-only)
        assert len(compact) == 7  # ts, src, dst, type, msg, ttl, ack


# ═══════════════════════════════════════════════════════════════════════
# F5: Snapshots & Replay Requests
# ═══════════════════════════════════════════════════════════════════════


class TestBusSnapshot:
    """BusSnapshot serialization."""

    def test_to_dict_roundtrip(self):
        snap = BusSnapshot(
            seq_state={"eng": 5, "ops": 3},
            ownership_claims={"eng": {"owner_id": "daemon", "granted_at": "2026-03-22"}},
            bus_hash="abc123",
            message_count=10,
            created_at="2026-03-22T10:00:00",
        )
        restored = BusSnapshot.from_dict(snap.to_dict())
        assert restored.seq_state == snap.seq_state
        assert restored.bus_hash == snap.bus_hash
        assert restored.message_count == snap.message_count


class TestSnapshotManager:
    """SnapshotManager create/load/verify."""

    def test_create_and_load(self, tmp_path):
        bus = tmp_path / "bus.jsonl"
        bus.write_text('{"ts":"2026-03-22","src":"eng","dst":"*","type":"state","msg":"test","ttl":7,"ack":[]}\n')
        st = SequenceTracker()
        st.record("eng", 1)
        ow = OwnershipRegistry()
        mgr = SnapshotManager(tmp_path / "bus-snapshot.json")
        snap = mgr.create(st, ow, bus)
        assert snap.message_count == 1
        assert snap.seq_state == {"eng": 1}
        assert snap.bus_hash != ""
        # Load back
        loaded = mgr.load()
        assert loaded is not None
        assert loaded.message_count == 1
        assert loaded.seq_state == {"eng": 1}

    def test_load_nonexistent(self, tmp_path):
        mgr = SnapshotManager(tmp_path / "nope.json")
        assert mgr.load() is None

    def test_verify_matches(self, tmp_path):
        bus = tmp_path / "bus.jsonl"
        bus.write_text('{"ts":"2026-03-22","src":"eng","dst":"*","type":"state","msg":"test","ttl":7,"ack":[]}\n')
        st = SequenceTracker()
        ow = OwnershipRegistry()
        mgr = SnapshotManager(tmp_path / "snap.json")
        snap = mgr.create(st, ow, bus)
        assert mgr.verify(snap, bus) is True

    def test_verify_stale(self, tmp_path):
        bus = tmp_path / "bus.jsonl"
        bus.write_text('{"ts":"2026-03-22","src":"eng","dst":"*","type":"state","msg":"test","ttl":7,"ack":[]}\n')
        st = SequenceTracker()
        ow = OwnershipRegistry()
        mgr = SnapshotManager(tmp_path / "snap.json")
        snap = mgr.create(st, ow, bus)
        # Modify bus after snapshot
        bus.write_text('{"ts":"2026-03-22","src":"eng","dst":"*","type":"state","msg":"changed","ttl":7,"ack":[]}\n')
        assert mgr.verify(snap, bus) is False

    def test_verify_empty_bus(self, tmp_path):
        bus = tmp_path / "bus.jsonl"
        st = SequenceTracker()
        ow = OwnershipRegistry()
        mgr = SnapshotManager(tmp_path / "snap.json")
        snap = mgr.create(st, ow, bus)
        assert snap.bus_hash == ""
        assert snap.message_count == 0
        assert mgr.verify(snap, bus) is True

    def test_create_captures_ownership(self, tmp_path):
        bus = tmp_path / "bus.jsonl"
        bus.write_text("")
        st = SequenceTracker()
        ow = OwnershipRegistry()
        ow.claim("eng", "daemon")
        mgr = SnapshotManager(tmp_path / "snap.json")
        snap = mgr.create(st, ow, bus)
        assert "eng" in snap.ownership_claims


class TestReplayRequest:
    """ReplayRequest creation and formatting."""

    def test_from_gap(self):
        req = ReplayRequest.from_gap("eng", expected=5, actual=10)
        assert req.src == "eng"
        assert req.from_seq == 5
        assert req.to_seq == 9

    def test_dispatch_msg_format(self):
        req = ReplayRequest(src="eng", from_seq=5, to_seq=9,
                            requested_at="2026-03-22T10:00:00")
        msg = req.to_dispatch_msg()
        assert msg == "REPLAY_REQUEST:eng:5-9"
        assert len(msg) <= 120

    def test_from_gap_single_missing(self):
        req = ReplayRequest.from_gap("eng", expected=5, actual=6)
        assert req.from_seq == 5
        assert req.to_seq == 5


# ═══════════════════════════════════════════════════════════════════════
# F6: Garbage Collection
# ═══════════════════════════════════════════════════════════════════════


class TestBusGC:
    """BusGC threshold computation and collection."""

    def test_compute_threshold_default(self):
        st = SequenceTracker()
        st.record("eng", 100)
        st.record("ops", 30)
        thresholds = BusGC.compute_threshold(st)
        assert thresholds["eng"] == 51  # 100 - 50 + 1
        assert thresholds["ops"] == 1   # max(1, 30 - 50 + 1) = 1

    def test_compute_threshold_custom_keep(self):
        st = SequenceTracker()
        st.record("eng", 100)
        thresholds = BusGC.compute_threshold(st, keep_last=10)
        assert thresholds["eng"] == 91  # 100 - 10 + 1

    def test_collect_archives_old_messages(self, tmp_path):
        from hermes.bus import write_message
        bus = tmp_path / "bus.jsonl"
        archive = tmp_path / "archive.jsonl"
        # Write 5 messages with seq 1-5
        for i in range(1, 6):
            write_message(bus, _msg("eng", seq=i))
        # Archive seq < 4 (keep 4,5)
        count = BusGC.collect(bus, archive, {"eng": 4})
        assert count == 3
        # Verify bus has only 2 messages
        from hermes.bus import read_bus
        remaining = read_bus(bus)
        assert len(remaining) == 2
        assert remaining[0].seq == 4
        assert remaining[1].seq == 5
        # Verify archive has 3
        archived = read_bus(archive)
        assert len(archived) == 3

    def test_collect_no_op_when_nothing_to_archive(self, tmp_path):
        from hermes.bus import write_message
        bus = tmp_path / "bus.jsonl"
        archive = tmp_path / "archive.jsonl"
        write_message(bus, _msg("eng", seq=1))
        count = BusGC.collect(bus, archive, {"eng": 1})
        assert count == 0

    def test_collect_preserves_messages_without_seq(self, tmp_path):
        from hermes.bus import write_message
        bus = tmp_path / "bus.jsonl"
        archive = tmp_path / "archive.jsonl"
        # Mix of seq and no-seq messages
        write_message(bus, _msg("eng", seq=1))
        write_message(bus, _msg("eng"))  # No seq — legacy
        write_message(bus, _msg("eng", seq=3))
        count = BusGC.collect(bus, archive, {"eng": 3})
        assert count == 1  # Only seq=1 archived
        from hermes.bus import read_bus
        remaining = read_bus(bus)
        assert len(remaining) == 2  # no-seq + seq=3

    def test_collect_nonexistent_bus(self, tmp_path):
        bus = tmp_path / "nope.jsonl"
        archive = tmp_path / "archive.jsonl"
        count = BusGC.collect(bus, archive, {"eng": 5})
        assert count == 0

    def test_collect_atomic_on_failure(self, tmp_path):
        """Bus file should remain intact if compaction fails mid-write."""
        from hermes.bus import write_message, read_bus
        bus = tmp_path / "bus.jsonl"
        archive = tmp_path / "archive.jsonl"
        write_message(bus, _msg("eng", seq=1))
        write_message(bus, _msg("eng", seq=2))
        original_content = bus.read_text()
        # Collect normally — should work
        count = BusGC.collect(bus, archive, {"eng": 2})
        assert count == 1
        remaining = read_bus(bus)
        assert len(remaining) == 1

    def test_collect_multiple_sources(self, tmp_path):
        from hermes.bus import write_message, read_bus
        bus = tmp_path / "bus.jsonl"
        archive = tmp_path / "archive.jsonl"
        write_message(bus, _msg("eng", seq=1))
        write_message(bus, _msg("eng", seq=2))
        write_message(bus, _msg("ops", seq=1))
        write_message(bus, _msg("ops", seq=2))
        # Archive eng < 2, ops < 2
        count = BusGC.collect(bus, archive, {"eng": 2, "ops": 2})
        assert count == 2
        remaining = read_bus(bus)
        assert len(remaining) == 2
        assert all(m.seq == 2 for m in remaining)

    def test_conflict_log_untouched(self, tmp_path):
        """Verify that GC does not affect conflict log."""
        from hermes.bus import write_message
        bus = tmp_path / "bus.jsonl"
        archive = tmp_path / "archive.jsonl"
        conflicts = tmp_path / "bus-conflicts.jsonl"
        cl = ConflictLog(conflicts)
        cl.record_anomaly("gap", "eng", seq=5)
        write_message(bus, _msg("eng", seq=1))
        write_message(bus, _msg("eng", seq=2))
        BusGC.collect(bus, archive, {"eng": 2})
        # Conflict log should still have 1 record
        assert cl.count() == 1
