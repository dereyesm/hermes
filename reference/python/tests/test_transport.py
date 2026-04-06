"""Comprehensive tests for ARC-0768: Datagram & Reliable Message Semantics.

Covers: transport_mode, extract_cid, extract_re, RELIABLE_TYPES,
find_unresolved, find_expired_unresolved, correlate, generate_escalation,
SynResult.unresolved, syn_report with unresolved.
"""

from datetime import date, timedelta

import pytest

from amaru.bus import (
    correlate,
    find_expired_unresolved,
    find_unresolved,
    generate_escalation,
    read_bus,
    write_message,
)
from amaru.message import (
    RELIABLE_TYPES,
    Message,
    create_message,
    extract_cid,
    extract_re,
    transport_mode,
)
from amaru.sync import SynResult, syn, syn_report

# ─── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def bus_file(tmp_path):
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


# ─── Transport Mode Classification ────────────────────────────────


class TestTransportMode:
    def test_state_is_dgm(self):
        assert transport_mode("state") == "DGM"

    def test_event_is_dgm(self):
        assert transport_mode("event") == "DGM"

    def test_alert_is_dgm(self):
        assert transport_mode("alert") == "DGM"

    def test_dojo_event_is_dgm(self):
        assert transport_mode("dojo_event") == "DGM"

    def test_request_is_rel(self):
        assert transport_mode("request") == "REL"

    def test_dispatch_is_rel(self):
        assert transport_mode("dispatch") == "REL"

    def test_data_cross_is_rel(self):
        assert transport_mode("data_cross") == "REL"

    def test_reliable_types_constant(self):
        assert {"request", "dispatch", "data_cross"} == RELIABLE_TYPES


# ─── CID / RE Extraction ──────────────────────────────────────────


class TestExtractCid:
    def test_cid_present(self):
        assert extract_cid("need costs [CID:dev-q4]") == "dev-q4"

    def test_cid_absent(self):
        assert extract_cid("just a normal message") is None

    def test_cid_min_length(self):
        assert extract_cid("task [CID:abcd]") == "abcd"

    def test_cid_max_length(self):
        assert extract_cid("task [CID:abcdef-12345]") == "abcdef-12345"

    def test_cid_too_short(self):
        assert extract_cid("task [CID:ab]") is None

    def test_cid_not_at_end(self):
        assert extract_cid("[CID:dev-q4] extra text") is None

    def test_cid_with_hyphens(self):
        assert extract_cid("msg [CID:ops-deploy-3]") == "ops-deploy-3"


class TestExtractRe:
    def test_re_present(self):
        assert extract_re("costs: $2400 [RE:dev-q4]") == "dev-q4"

    def test_re_absent(self):
        assert extract_re("no correlation here") is None

    def test_re_at_end(self):
        assert extract_re("done [RE:ops-rev3]") == "ops-rev3"

    def test_re_not_at_end(self):
        assert extract_re("[RE:ops-rev3] extra") is None


# ─── find_unresolved ──────────────────────────────────────────────


class TestFindUnresolved:
    def test_empty_list(self):
        assert find_unresolved([]) == []

    def test_dgm_excluded(self):
        msg = _make_msg(type="state", msg="update [CID:dev-upd1]", ack=["ops"])
        assert find_unresolved([msg]) == []

    def test_rel_without_cid_excluded(self):
        msg = _make_msg(type="request", msg="need info", ack=["ops"])
        assert find_unresolved([msg]) == []

    def test_rel_with_cid_no_ack_excluded(self):
        """SENT state — not yet acked, so not unresolved."""
        msg = _make_msg(type="dispatch", msg="do task [CID:dev-task]")
        assert find_unresolved([msg]) == []

    def test_rel_with_cid_acked_no_re(self):
        """ACKED state — acked but no resolution."""
        msg = _make_msg(type="dispatch", msg="do task [CID:dev-task]", ack=["ops"])
        result = find_unresolved([msg])
        assert len(result) == 1
        assert result[0].msg == "do task [CID:dev-task]"

    def test_resolved_excluded(self):
        """RESOLVED — has companion RE message."""
        req = _make_msg(type="request", msg="need data [CID:fin-data]", ack=["fin"])
        res = _make_msg(type="state", src="fin", msg="data: 42 [RE:fin-data]")
        assert find_unresolved([req, res]) == []

    def test_expired_excluded(self):
        """Expired messages are not unresolved (they are expired_unresolved)."""
        msg = _make_msg(
            type="dispatch",
            msg="old task [CID:dev-old1]",
            ts=date.today() - timedelta(days=10),
            ttl=3,
            ack=["ops"],
        )
        assert find_unresolved([msg]) == []

    def test_multiple_unresolved(self):
        m1 = _make_msg(type="request", msg="q1 [CID:dev-q001]", ack=["fin"])
        m2 = _make_msg(type="dispatch", msg="t1 [CID:ops-t001]", ack=["eng"])
        m3 = _make_msg(type="state", msg="info only")
        result = find_unresolved([m1, m2, m3])
        assert len(result) == 2


# ─── find_expired_unresolved ──────────────────────────────────────


class TestFindExpiredUnresolved:
    def test_empty_list(self):
        assert find_expired_unresolved([]) == []

    def test_expired_rel_no_re(self):
        msg = _make_msg(
            type="dispatch",
            msg="task [CID:dev-exp1]",
            ts=date.today() - timedelta(days=10),
            ttl=3,
            ack=["ops"],
        )
        result = find_expired_unresolved([msg])
        assert len(result) == 1

    def test_expired_rel_with_re_excluded(self):
        req = _make_msg(
            type="dispatch", msg="task [CID:dev-exp2]", ts=date.today() - timedelta(days=10), ttl=3
        )
        res = _make_msg(type="state", msg="done [RE:dev-exp2]")
        assert find_expired_unresolved([req, res]) == []

    def test_active_rel_excluded(self):
        msg = _make_msg(type="dispatch", msg="task [CID:dev-act1]", ack=["ops"])
        assert find_expired_unresolved([msg]) == []

    def test_dgm_expired_excluded(self):
        msg = _make_msg(
            type="state", msg="old info [CID:dev-inf1]", ts=date.today() - timedelta(days=10), ttl=3
        )
        assert find_expired_unresolved([msg]) == []


# ─── correlate ────────────────────────────────────────────────────


class TestCorrelate:
    def test_both_found(self):
        req = _make_msg(type="request", msg="need X [CID:dev-corr]")
        res = _make_msg(type="state", src="fin", msg="X is 42 [RE:dev-corr]")
        result = correlate([req, res], "dev-corr")
        assert result["request"] == req
        assert result["response"] == res

    def test_request_only(self):
        req = _make_msg(type="request", msg="need Y [CID:dev-half]")
        result = correlate([req], "dev-half")
        assert result["request"] == req
        assert result["response"] is None

    def test_no_match(self):
        msg = _make_msg(type="state", msg="nothing here")
        result = correlate([msg], "dev-none")
        assert result["request"] is None
        assert result["response"] is None


# ─── generate_escalation ─────────────────────────────────────────


class TestGenerateEscalation:
    def test_basic_escalation(self):
        original = _make_msg(
            type="dispatch", src="ops", dst="eng", msg="review code [CID:ops-rev3]"
        )
        esc = generate_escalation(original)
        assert esc.src == "ops"
        assert esc.dst == "*"
        assert esc.type == "alert"
        assert esc.msg.startswith("UNRESOLVED:dispatch:")
        assert "review code" in esc.msg

    def test_escalation_truncation(self):
        long_msg = "x" * 100 + " [CID:dev-long]"
        original = _make_msg(type="request", src="eng", msg=long_msg)
        esc = generate_escalation(original)
        assert len(esc.msg) <= 120

    def test_escalation_is_dgm(self):
        original = _make_msg(type="dispatch", msg="task [CID:dev-esc1]")
        esc = generate_escalation(original)
        assert transport_mode(esc.type) == "DGM"

    def test_escalation_has_today_ts(self):
        original = _make_msg(
            type="request", msg="old [CID:dev-esc2]", ts=date.today() - timedelta(days=10)
        )
        esc = generate_escalation(original)
        assert esc.ts == date.today()


# ─── SYN Integration ─────────────────────────────────────────────


class TestSynUnresolved:
    def test_syn_result_default_unresolved(self):
        result = SynResult(pending=[], stale=[], total_bus_messages=0)
        assert result.unresolved == []

    def test_syn_detects_unresolved(self, bus_file):
        msg = create_message(src="ops", dst="eng", type="dispatch", msg="review pr [CID:ops-pr01]")
        write_message(bus_file, msg)
        # Manually ACK it
        from amaru.bus import ack_message

        ack_message(bus_file, "eng", lambda m: True)

        result = syn(bus_file, "eng")
        assert len(result.unresolved) == 1
        assert "ops-pr01" in result.unresolved[0].msg

    def test_syn_report_shows_unresolved(self):
        msg = _make_msg(type="dispatch", src="ops", msg="review pr [CID:ops-pr01]", ack=["eng"])
        result = SynResult(
            pending=[],
            stale=[],
            total_bus_messages=1,
            unresolved=[msg],
        )
        report = syn_report(result, "eng")
        assert "UNRESOLVED" in report
        assert "ops-pr01" in report

    def test_syn_report_no_unresolved_section(self):
        result = SynResult(pending=[], stale=[], total_bus_messages=0)
        report = syn_report(result, "eng")
        assert "UNRESOLVED" not in report


# ─── Full Lifecycle Integration ───────────────────────────────────


class TestLifecycleIntegration:
    def test_request_response_lifecycle(self, bus_file):
        """Full flow: request → ack → resolve."""
        # 1. Request sent
        req = create_message(
            src="ops", dst="eng", type="request", msg="need cost data [CID:ops-cost]"
        )
        write_message(bus_file, req)

        # 2. SYN: eng sees the request
        result = syn(bus_file, "eng")
        assert len(result.pending) == 1

        # 3. ACK: eng acknowledges
        from amaru.bus import ack_message

        ack_message(bus_file, "eng", lambda m: True)

        # 4. Unresolved: acked but no response yet
        msgs = read_bus(bus_file)
        unresolved = find_unresolved(msgs)
        assert len(unresolved) == 1

        # 5. Resolve: eng sends response
        res = create_message(src="eng", dst="ops", type="state", msg="cost:2400usd [RE:ops-cost]")
        write_message(bus_file, res)

        # 6. Now resolved
        msgs = read_bus(bus_file)
        unresolved = find_unresolved(msgs)
        assert len(unresolved) == 0

        # 7. Correlate
        pair = correlate(msgs, "ops-cost")
        assert pair["request"].src == "ops"
        assert pair["response"].src == "eng"

    def test_dispatch_expire_escalate(self, bus_file):
        """Dispatch expires without resolution → escalation."""
        dispatch = _make_msg(
            type="dispatch",
            src="ops",
            dst="eng",
            msg="deploy v2 [CID:ops-dep2]",
            ts=date.today() - timedelta(days=10),
            ttl=3,
            ack=["eng"],
        )
        write_message(bus_file, dispatch)

        msgs = read_bus(bus_file)
        expired = find_expired_unresolved(msgs)
        assert len(expired) == 1

        esc = generate_escalation(expired[0])
        assert esc.type == "alert"
        assert "UNRESOLVED" in esc.msg
        assert esc.src == "ops"

    def test_backward_compat_no_cid(self, bus_file):
        """Old messages without CID work exactly as before."""
        old_dispatch = create_message(
            src="ops", dst="eng", type="dispatch", msg="old style task no cid"
        )
        write_message(bus_file, old_dispatch)

        msgs = read_bus(bus_file)
        # No CID → not in unresolved tracking
        assert find_unresolved(msgs) == []
        assert find_expired_unresolved(msgs) == []
        # But transport_mode still classifies it as REL
        assert transport_mode(old_dispatch.type) == "REL"
