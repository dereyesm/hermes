"""Tests for ARC-9001 Bus Integrity Protocol — F1 Sequencing + F2 Ownership."""

from __future__ import annotations

from datetime import date

import pytest

from hermes.integrity import (
    BusIntegrityChecker,
    OwnershipClaim,
    OwnershipRegistry,
    OwnershipViolation,
    SequenceState,
    SequenceTracker,
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
