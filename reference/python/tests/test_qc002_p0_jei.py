"""QC002 P0 — Bachue JEI validation against PR #15 fixes.

Tests three P0 findings from Bruja audit (2026-05-02):
  #9  Downgrade protection   — protocol_version < "0.5" → err 1002
  #1  Rate limiting          — sig/data budget exhausted → err 429
  #10 Queue backpressure     — queue overflow → err 503 with dst+ref

Also validates Bachue fixture package imports cleanly and that the
corrected HKDF_INFO diverges from the legacy HERMES string.

Author: Bachue (QA Lead) / JEI — 2026-05-04 COT
"""

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Fixture package import check
# ---------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).parent))


class TestBachueFixtureImports:
    """Verify all Bachue fixture modules import without error."""

    def test_crypto_fixtures_import(self):
        from fixtures_jei.crypto_fixtures import HKDF_INFO

        assert HKDF_INFO == b"AMARU-ARC8446-ECDHE-v1"

    def test_hkdf_info_is_not_legacy_hermes(self):
        from fixtures_jei.crypto_fixtures import HKDF_INFO

        assert b"HERMES" not in HKDF_INFO, "HKDF_INFO must use AMARU rebrand, not legacy HERMES"

    def test_session_fixtures_import(self):
        from fixtures_jei.session_fixtures import SessionState

        assert hasattr(SessionState, "ACTIVE")

    def test_hub_fixtures_import(self):
        from fixtures_jei.hub_fixtures import MockStoreForwardQueue

        q = MockStoreForwardQueue(max_depth=10)
        assert q.depth("dani") == 0

    def test_message_fixtures_frame_shapes(self):
        # frame_hello is a pytest fixture; verify module loads without error
        import fixtures_jei.message_fixtures as mf

        assert hasattr(mf, "frame_hello")
        assert hasattr(mf, "frame_auth")
        assert hasattr(mf, "frame_message")
        assert hasattr(mf, "frame_fake_sender")
        assert hasattr(mf, "frame_replay")
        assert hasattr(mf, "frame_offline_queue")
        assert hasattr(mf, "frame_unknown_channel")


# ---------------------------------------------------------------------------
# P0 #9 — Downgrade protection (ARC-4601 §15.1, Bruja check #9)
# ---------------------------------------------------------------------------


class TestDowngradeProtection:
    """protocol_version below MIN_PROTOCOL_VERSION must be rejected with 1002."""

    def test_parse_version_stable(self):
        from amaru.hub import _parse_version

        assert _parse_version("0.5.0") == (0, 5, 0)
        assert _parse_version("1.0.0") == (1, 0, 0)

    def test_parse_version_pre_release(self):
        from amaru.hub import _parse_version

        # Pre-release suffix stripped — "0.5.0a1" → (0, 5, 0)
        assert _parse_version("0.5.0a1") == (0, 5, 0)

    def test_version_at_least_accepts_current(self):
        from amaru.hub import MIN_PROTOCOL_VERSION, _version_at_least

        assert _version_at_least("0.5.0", MIN_PROTOCOL_VERSION)
        assert _version_at_least("0.5.0a1", MIN_PROTOCOL_VERSION)
        assert _version_at_least("1.0.0", MIN_PROTOCOL_VERSION)

    def test_version_at_least_rejects_old(self):
        from amaru.hub import MIN_PROTOCOL_VERSION, _version_at_least

        assert not _version_at_least("0.4.2a1", MIN_PROTOCOL_VERSION)
        assert not _version_at_least("0.3.0", MIN_PROTOCOL_VERSION)
        assert not _version_at_least("0.1.0", MIN_PROTOCOL_VERSION)

    def test_frame_hello_version_passes_gate(self):
        """Bachue frame_hello uses protocol_version 0.5.0 — passes downgrade gate."""
        from amaru.hub import MIN_PROTOCOL_VERSION, _version_at_least

        # Simulate what frame_hello fixture produces
        hello_version = "0.5.0"
        assert _version_at_least(hello_version, MIN_PROTOCOL_VERSION)

    def test_old_hello_version_rejected_by_gate(self):
        """A HELLO with version 0.4.x is rejected — confirms downgrade protection."""
        from amaru.hub import MIN_PROTOCOL_VERSION, _version_at_least

        old_version = "0.4.2a1"
        assert not _version_at_least(old_version, MIN_PROTOCOL_VERSION)


# ---------------------------------------------------------------------------
# P0 #1 — Rate limiting (ARC-4601 §15.X, Bruja check #1)
# ---------------------------------------------------------------------------


class TestRateLimitingP0:
    """Token-bucket per-client rate limiting — sig + data budgets."""

    def test_rate_buckets_fresh_has_full_budget(self):
        from amaru.hub import RateBuckets

        rb = RateBuckets(sig_max=60, data_max=1_048_576)
        assert rb.sig_tokens > 0
        assert rb.data_tokens > 0

    def test_sig_budget_exhausted_returns_false(self):
        from amaru.hub import RateBuckets

        rb = RateBuckets(sig_max=1, data_max=100_000)
        assert rb.consume(sig=1, data=10)  # first consumes OK
        assert not rb.consume(sig=1, data=10)  # budget gone → False

    def test_data_budget_exhausted_returns_false(self):
        from amaru.hub import RateBuckets

        rb = RateBuckets(sig_max=100, data_max=50)
        assert rb.consume(sig=1, data=40)  # OK
        assert not rb.consume(sig=1, data=40)  # data would exceed max → False

    def test_consume_is_atomic_no_partial_drain(self):
        """A rejected consume must not partially drain sig when data is exhausted."""
        from amaru.hub import RateBuckets

        rb = RateBuckets(sig_max=10, data_max=50)
        rb.consume(sig=1, data=40)  # succeeds
        sig_after_first = rb.sig_tokens
        # Second consume fails on data — sig must not decrease (refill can increase it)
        rb.consume(sig=1, data=40)
        assert rb.sig_tokens >= sig_after_first, (
            "Atomic consume: sig bucket must not drain when data check fails"
        )

    def test_two_clients_are_isolated(self):
        from amaru.hub import RateBuckets

        rb_jei = RateBuckets(sig_max=2, data_max=100)
        rb_dani = RateBuckets(sig_max=2, data_max=100)
        rb_jei.consume(sig=2, data=10)  # exhaust JEI
        assert not rb_jei.consume(sig=1, data=10)
        assert rb_dani.consume(sig=1, data=10)  # DANI unaffected


# ---------------------------------------------------------------------------
# P0 #10 — Queue 503 backpressure (Bruja check #10)
# ---------------------------------------------------------------------------


class TestQueueBackpressureP0:
    """On queue overflow, hub must emit err 503 with dst + ref to sender."""

    def test_store_forward_queue_full_returns_false(self):
        """StoreForwardQueue.enqueue() returns False when queue at max_depth."""
        from amaru.hub import StoreForwardQueue

        q = StoreForwardQueue(max_depth=2)
        assert q.enqueue("dani", {"msg": "a"}) is True
        assert q.enqueue("dani", {"msg": "b"}) is True
        assert q.enqueue("dani", {"msg": "c"}) is False  # queue full

    def test_message_router_reports_queue_full_status(self):
        """MessageRouter.route() returns {"status": "queue_full"} on overflow."""
        import asyncio

        from amaru.hub import ConnectionTable, MessageRouter, StoreForwardQueue

        q = StoreForwardQueue(max_depth=1)
        ct = ConnectionTable()
        router = MessageRouter(ct, q)
        q.enqueue("dani", {"msg": "pre-fill"})  # fill to capacity

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                router.route({"dst": "dani", "msg": "overflow"}, "jei")
            )
        finally:
            loop.close()

        assert result["status"] == "queue_full"
        assert result["dst"] == "dani"

    def test_mock_queue_matches_real_enqueue_bool_interface(self):
        """Bachue MockStoreForwardQueue.enqueue() matches real StoreForwardQueue interface (bool)."""
        from fixtures_jei.hub_fixtures import MockStoreForwardQueue

        q = MockStoreForwardQueue(max_depth=2)
        assert q.enqueue("dani", {"msg": "a"}) is True
        assert q.enqueue("dani", {"msg": "b"}) is True
        assert q.enqueue("dani", {"msg": "c"}) is False  # queue full

    def test_mock_router_returns_queue_full_status(self):
        """MockRouter.route() returns {"status": "queue_full"} when queue is full."""
        from fixtures_jei.hub_fixtures import MockRouter, MockStoreForwardQueue

        q = MockStoreForwardQueue(max_depth=1)
        router = MockRouter(connections={}, queue=q)  # no online peers → always queues
        router.route({"dst": "dani", "msg": "pre-fill"}, "jei")  # fills queue
        result = router.route({"dst": "dani", "msg": "overflow"}, "jei")
        assert result["status"] == "queue_full"
        assert result["dst"] == "dani"
