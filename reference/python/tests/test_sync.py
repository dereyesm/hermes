"""Comprehensive tests for HERMES SYN/FIN protocol (sync.py).

Covers: syn, syn_report, fin, FinAction, SynResult.
"""

from datetime import date, timedelta

import pytest

from hermes.bus import read_bus, write_message
from hermes.message import Message, create_message
from hermes.sync import FinAction, SynResult, fin, syn, syn_report

# ─── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def bus_file(tmp_path):
    """Create an empty bus file and return its path."""
    f = tmp_path / "bus.jsonl"
    f.touch()
    return f


def _make_msg(src="eng", dst="*", type="state", msg="test", ttl=7, ts=None, ack=None):
    return Message(
        ts=ts or date.today(),
        src=src,
        dst=dst,
        type=type,
        msg=msg,
        ttl=ttl,
        ack=ack or [],
    )


# ─── SYN Protocol ─────────────────────────────────────────────────


class TestSyn:
    def test_empty_bus(self, bus_file):
        result = syn(bus_file, "eng")
        assert result.pending == []
        assert result.stale == []
        assert result.total_bus_messages == 0

    def test_nonexistent_bus(self, tmp_path):
        result = syn(tmp_path / "nope.jsonl", "eng")
        assert result.pending == []
        assert result.total_bus_messages == 0

    def test_pending_broadcast(self, bus_file):
        write_message(bus_file, create_message(src="ops", dst="*", type="alert", msg="deadline"))
        result = syn(bus_file, "eng")
        assert len(result.pending) == 1
        assert result.pending[0].msg == "deadline"

    def test_pending_unicast(self, bus_file):
        write_message(
            bus_file, create_message(src="ops", dst="eng", type="request", msg="need-info")
        )
        result = syn(bus_file, "eng")
        assert len(result.pending) == 1

    def test_other_namespace_excluded(self, bus_file):
        write_message(bus_file, create_message(src="ops", dst="fin", type="request", msg="costs"))
        result = syn(bus_file, "eng")
        assert len(result.pending) == 0

    def test_already_acked_excluded(self, bus_file):
        msg = _make_msg(src="ops", dst="*", ack=["eng"], msg="old-news")
        write_message(bus_file, msg)
        result = syn(bus_file, "eng")
        assert len(result.pending) == 0

    def test_stale_detection(self, bus_file):
        old = _make_msg(src="ops", dst="*", ts=date.today() - timedelta(days=5), msg="forgotten")
        write_message(bus_file, old)
        result = syn(bus_file, "eng")
        assert len(result.stale) == 1
        assert result.stale[0].msg == "forgotten"

    def test_total_bus_messages_count(self, bus_file):
        for i in range(4):
            write_message(
                bus_file,
                create_message(src="ops", dst="fin" if i % 2 else "*", type="state", msg=f"m-{i}"),
            )
        result = syn(bus_file, "eng")
        assert result.total_bus_messages == 4
        # Only broadcasts (i=0, i=2) are pending for eng
        assert len(result.pending) == 2

    def test_mixed_pending_and_acked(self, bus_file):
        write_message(bus_file, _make_msg(src="ops", dst="*", msg="pending-one"))
        write_message(bus_file, _make_msg(src="ops", dst="*", msg="acked-one", ack=["eng"]))
        write_message(bus_file, _make_msg(src="ops", dst="eng", msg="pending-two"))
        result = syn(bus_file, "eng")
        assert len(result.pending) == 2
        assert {m.msg for m in result.pending} == {"pending-one", "pending-two"}


# ─── SYN Report ───────────────────────────────────────────────────


class TestSynReport:
    def test_no_messages(self):
        result = SynResult(pending=[], stale=[], total_bus_messages=0)
        report = syn_report(result, "eng")
        assert "[HERMES]" in report
        assert "No pending" in report

    def test_pending_messages_listed(self):
        result = SynResult(
            pending=[_make_msg(src="ops", msg="deadline")],
            stale=[],
            total_bus_messages=1,
        )
        report = syn_report(result, "eng")
        assert "1 pending" in report
        assert "deadline" in report
        assert "ops" in report

    def test_stale_warning(self):
        old_msg = _make_msg(
            src="fin", dst="*", ts=date.today() - timedelta(days=5), msg="old-alert"
        )
        result = SynResult(
            pending=[old_msg],
            stale=[old_msg],
            total_bus_messages=1,
        )
        report = syn_report(result, "eng")
        assert "WARNING" in report
        assert "unACKed" in report
        assert "5d old" in report

    def test_total_count_shown(self):
        result = SynResult(pending=[], stale=[], total_bus_messages=42)
        report = syn_report(result, "eng")
        assert "42" in report

    def test_multiple_pending(self):
        msgs = [
            _make_msg(src="ops", msg="msg-a"),
            _make_msg(src="fin", msg="msg-b"),
        ]
        result = SynResult(pending=msgs, stale=[], total_bus_messages=2)
        report = syn_report(result, "eng")
        assert "2 pending" in report
        assert "msg-a" in report
        assert "msg-b" in report


# ─── FIN Protocol ─────────────────────────────────────────────────


class TestFin:
    def test_no_actions(self, bus_file):
        written = fin(bus_file, "eng", [])
        assert written == []
        assert read_bus(bus_file) == []

    def test_none_actions(self, bus_file):
        written = fin(bus_file, "eng", None)
        assert written == []

    def test_single_action(self, bus_file):
        actions = [FinAction(dst="*", type="state", msg="sprint-done")]
        written = fin(bus_file, "eng", actions)
        assert len(written) == 1
        assert written[0].src == "eng"
        assert written[0].dst == "*"
        assert written[0].msg == "sprint-done"

        # Verify on bus
        msgs = read_bus(bus_file)
        assert len(msgs) == 1
        assert msgs[0].msg == "sprint-done"

    def test_multiple_actions(self, bus_file):
        actions = [
            FinAction(dst="*", type="state", msg="state-change"),
            FinAction(dst="fin", type="data_cross", msg="costs-500usd"),
            FinAction(dst="*", type="event", msg="deploy-complete"),
        ]
        written = fin(bus_file, "eng", actions)
        assert len(written) == 3

        msgs = read_bus(bus_file)
        assert len(msgs) == 3
        assert all(m.src == "eng" for m in msgs)

    def test_custom_ttl(self, bus_file):
        actions = [FinAction(dst="*", type="alert", msg="urgent", ttl=1)]
        written = fin(bus_file, "eng", actions)
        assert written[0].ttl == 1

    def test_default_ttl_by_type(self, bus_file):
        actions = [
            FinAction(dst="*", type="state", msg="s"),
            FinAction(dst="*", type="alert", msg="a"),
            FinAction(dst="*", type="event", msg="e"),
        ]
        written = fin(bus_file, "eng", actions)
        assert written[0].ttl == 7  # state default
        assert written[1].ttl == 5  # alert default
        assert written[2].ttl == 3  # event default

    def test_fin_appends_to_existing_bus(self, bus_file):
        # Pre-existing message
        existing = create_message(src="ops", dst="*", type="state", msg="old")
        write_message(bus_file, existing)

        actions = [FinAction(dst="*", type="state", msg="new")]
        fin(bus_file, "eng", actions)

        msgs = read_bus(bus_file)
        assert len(msgs) == 2
        assert msgs[0].msg == "old"
        assert msgs[1].msg == "new"

    def test_fin_messages_have_empty_ack(self, bus_file):
        actions = [FinAction(dst="*", type="state", msg="fresh")]
        written = fin(bus_file, "eng", actions)
        assert written[0].ack == []

    def test_fin_messages_have_today_timestamp(self, bus_file):
        actions = [FinAction(dst="*", type="state", msg="now")]
        written = fin(bus_file, "eng", actions)
        assert written[0].ts == date.today()


# ─── FinAction Dataclass ──────────────────────────────────────────


class TestFinAction:
    def test_defaults(self):
        action = FinAction(dst="*", type="state", msg="test")
        assert action.ttl is None

    def test_with_ttl(self):
        action = FinAction(dst="*", type="alert", msg="urgent", ttl=1)
        assert action.ttl == 1


# ─── SynResult Dataclass ──────────────────────────────────────────


class TestSynResult:
    def test_creation(self):
        result = SynResult(
            pending=[_make_msg()],
            stale=[],
            total_bus_messages=5,
        )
        assert len(result.pending) == 1
        assert result.total_bus_messages == 5

    def test_empty(self):
        result = SynResult(pending=[], stale=[], total_bus_messages=0)
        assert result.pending == []
        assert result.stale == []


# ─── Integration: SYN then FIN ────────────────────────────────────


class TestSynFinIntegration:
    def test_full_lifecycle(self, bus_file):
        """Simulate a full session: SYN reads, work happens, FIN writes."""
        # Setup: another namespace left messages
        write_message(
            bus_file, create_message(src="ops", dst="*", type="alert", msg="review-needed")
        )

        # SYN: eng session starts
        result = syn(bus_file, "eng")
        assert len(result.pending) == 1

        # FIN: eng session ends, writes state
        actions = [
            FinAction(dst="*", type="state", msg="review-done"),
        ]
        fin(bus_file, "eng", actions)

        # Bus now has 2 messages
        msgs = read_bus(bus_file)
        assert len(msgs) == 2
        assert msgs[1].src == "eng"
        assert msgs[1].msg == "review-done"

    def test_syn_after_fin_shows_new_messages(self, bus_file):
        """After FIN writes, another namespace's SYN should see them."""
        # eng does FIN
        fin(
            bus_file,
            "eng",
            [
                FinAction(dst="*", type="state", msg="eng-update"),
            ],
        )

        # ops does SYN
        result = syn(bus_file, "ops")
        assert len(result.pending) == 1
        assert result.pending[0].msg == "eng-update"
