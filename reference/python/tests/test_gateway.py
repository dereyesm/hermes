"""Tests for Amaru Agent Gateway — ARC-3022 Reference Implementation.

Covers: TranslationTable, OutboundFilter, InboundValidator,
AttestationStore, ResonanceCalculator, Gateway.
"""

from datetime import date, timedelta

import pytest

from amaru.gateway import (
    AgentMapping,
    AttestationStore,
    Gateway,
    InboundValidator,
    OutboundFilter,
    ResonanceCalculator,
    TranslationTable,
)
from amaru.message import Message

# ─── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def sample_mappings():
    """A list of AgentMappings for testing."""
    return [
        AgentMapping(
            namespace="community",
            agent="admin-ph",
            external_alias="zeta-legal-alpha",
            published=True,
            capabilities=["property-law", "financial-audit"],
        ),
        AgentMapping(
            namespace="finance",
            agent="plutus",
            external_alias="aureus",
            published=True,
            capabilities=["personal-finance", "debt-strategy"],
        ),
        AgentMapping(
            namespace="engineering",
            agent="eng-lead",
            external_alias="shadow-eng",
            published=False,
            capabilities=["code-review"],
        ),
    ]


@pytest.fixture
def translation_table(sample_mappings):
    return TranslationTable(clan_id="test-clan", mappings=sample_mappings)


@pytest.fixture
def outbound_filter():
    return OutboundFilter()


@pytest.fixture
def inbound_validator():
    return InboundValidator(
        known_clans={"nakama-crew", "alliance-x"},
        published_aliases={"zeta-legal-alpha", "aureus"},
        max_payload_bytes=4096,
        rate_limit_per_clan=3,
    )


@pytest.fixture
def attestation_store():
    return AttestationStore()


@pytest.fixture
def resonance_calculator():
    return ResonanceCalculator()


def _make_attestation(
    from_clan="nakama-crew",
    to_clan="test-clan",
    to_agent="aureus",
    quest_id="quest-001",
    quality=5,
    reliability=5,
    collaboration=4,
    timestamp=None,
):
    """Helper to build an attestation dict."""
    return {
        "id": f"att-{quest_id}",
        "from_clan": from_clan,
        "to_clan": to_clan,
        "to_agent": to_agent,
        "quest_id": quest_id,
        "timestamp": timestamp or date.today().isoformat(),
        "rating": {
            "quality": quality,
            "reliability": reliability,
            "collaboration": collaboration,
        },
        "summary": "Great collaboration.",
    }


# ─── TranslationTable ─────────────────────────────────────────────


class TestTranslationTable:
    def test_outbound_published_agent(self, translation_table):
        alias = translation_table.translate_outbound("community", "admin-ph")
        assert alias == "zeta-legal-alpha"

    def test_outbound_another_published_agent(self, translation_table):
        alias = translation_table.translate_outbound("finance", "plutus")
        assert alias == "aureus"

    def test_outbound_unpublished_returns_none(self, translation_table):
        alias = translation_table.translate_outbound("engineering", "eng-lead")
        assert alias is None

    def test_outbound_unknown_agent_returns_none(self, translation_table):
        alias = translation_table.translate_outbound("finance", "unknown-agent")
        assert alias is None

    def test_inbound_published_agent(self, translation_table):
        result = translation_table.translate_inbound("zeta-legal-alpha")
        assert result == ("community", "admin-ph")

    def test_inbound_another_published_agent(self, translation_table):
        result = translation_table.translate_inbound("aureus")
        assert result == ("finance", "plutus")

    def test_inbound_unpublished_returns_none(self, translation_table):
        result = translation_table.translate_inbound("shadow-eng")
        assert result is None

    def test_inbound_unknown_alias_returns_none(self, translation_table):
        result = translation_table.translate_inbound("does-not-exist")
        assert result is None

    def test_published_agents_list(self, translation_table):
        published = translation_table.published_agents()
        assert len(published) == 2
        aliases = {m.external_alias for m in published}
        assert aliases == {"zeta-legal-alpha", "aureus"}


# ─── OutboundFilter ────────────────────────────────────────────────


class TestOutboundFilter:
    def test_allowed_type_clean_payload(self, outbound_filter):
        allowed, reason = outbound_filter.evaluate("profile_update", "Updated agent capabilities.")
        assert allowed is True
        assert reason == "ok"

    def test_attestation_type_allowed(self, outbound_filter):
        allowed, _ = outbound_filter.evaluate("attestation", "Quality excellent.")
        assert allowed is True

    def test_quest_response_allowed(self, outbound_filter):
        allowed, _ = outbound_filter.evaluate("quest_response", "Debt strategy delivered.")
        assert allowed is True

    def test_unknown_type_denied(self, outbound_filter):
        allowed, reason = outbound_filter.evaluate("internal_state", "sprint data")
        assert allowed is False
        assert "not in allowed" in reason

    def test_prohibited_bus_reference(self, outbound_filter):
        allowed, reason = outbound_filter.evaluate(
            "profile_update", "Contents of bus.jsonl leaked."
        )
        assert allowed is False
        assert "prohibited" in reason

    def test_prohibited_routes_reference(self, outbound_filter):
        allowed, reason = outbound_filter.evaluate("attestation", "See routes.md for topology.")
        assert allowed is False
        assert "prohibited" in reason

    def test_prohibited_credentials(self, outbound_filter):
        allowed, reason = outbound_filter.evaluate("quest_response", "The api_key is abc123.")
        assert allowed is False
        assert "prohibited" in reason

    def test_prohibited_bounty_data(self, outbound_filter):
        allowed, reason = outbound_filter.evaluate("profile_update", "Agent has Bounty score 85.")
        assert allowed is False
        assert "prohibited" in reason

    def test_prohibited_xp_data(self, outbound_filter):
        allowed, reason = outbound_filter.evaluate("profile_update", "Current XP is 1200.")
        assert allowed is False
        assert "prohibited" in reason

    def test_clean_payload_passes(self, outbound_filter):
        allowed, _ = outbound_filter.evaluate(
            "attestation", "Provided debt restructuring strategy that reduced costs by 15%."
        )
        assert allowed is True


# ─── InboundValidator ──────────────────────────────────────────────


class TestInboundValidator:
    def test_valid_message_accepted(self, inbound_validator):
        accepted, reason = inbound_validator.validate(
            source_clan="nakama-crew",
            target_agent="aureus",
            message_type="attestation",
            payload="Great work on the quest.",
        )
        assert accepted is True
        assert reason == "ok"

    def test_unknown_clan_rejected(self, inbound_validator):
        accepted, reason = inbound_validator.validate(
            source_clan="shadow-corp",
            target_agent="aureus",
            message_type="attestation",
            payload="test",
        )
        assert accepted is False
        assert "unknown source clan" in reason

    def test_unknown_agent_rejected(self, inbound_validator):
        accepted, reason = inbound_validator.validate(
            source_clan="nakama-crew",
            target_agent="nonexistent",
            message_type="attestation",
            payload="test",
        )
        assert accepted is False
        assert "unknown agent" in reason

    def test_unsupported_type_rejected(self, inbound_validator):
        accepted, reason = inbound_validator.validate(
            source_clan="nakama-crew",
            target_agent="aureus",
            message_type="internal_command",
            payload="test",
        )
        assert accepted is False
        assert "unsupported inbound type" in reason

    def test_executable_content_rejected(self, inbound_validator):
        accepted, reason = inbound_validator.validate(
            source_clan="nakama-crew",
            target_agent="aureus",
            message_type="quest_proposal",
            payload="<script>alert('xss')</script>",
        )
        assert accepted is False
        assert "executable content" in reason

    def test_payload_too_large(self, inbound_validator):
        big_payload = "x" * 5000
        accepted, reason = inbound_validator.validate(
            source_clan="nakama-crew",
            target_agent="aureus",
            message_type="discovery",
            payload=big_payload,
        )
        assert accepted is False
        assert "payload too large" in reason

    def test_rate_limit_exceeded(self, inbound_validator):
        # Rate limit is 3 per clan in the fixture
        for _ in range(3):
            accepted, _ = inbound_validator.validate(
                source_clan="alliance-x",
                target_agent="aureus",
                message_type="discovery",
                payload="hello",
            )
            assert accepted is True

        # Fourth should be rejected
        accepted, reason = inbound_validator.validate(
            source_clan="alliance-x",
            target_agent="aureus",
            message_type="discovery",
            payload="hello",
        )
        assert accepted is False
        assert "rate limit exceeded" in reason

    def test_rate_limit_per_clan_independent(self, inbound_validator):
        # Use up alliance-x's limit
        for _ in range(3):
            inbound_validator.validate(
                source_clan="alliance-x",
                target_agent="aureus",
                message_type="discovery",
                payload="hello",
            )
        # nakama-crew should still work
        accepted, _ = inbound_validator.validate(
            source_clan="nakama-crew",
            target_agent="aureus",
            message_type="discovery",
            payload="hello",
        )
        assert accepted is True

    def test_discovery_type_accepted(self, inbound_validator):
        accepted, _ = inbound_validator.validate(
            source_clan="nakama-crew",
            target_agent="zeta-legal-alpha",
            message_type="discovery",
            payload="requesting profile",
        )
        assert accepted is True


# ─── AttestationStore ──────────────────────────────────────────────


class TestAttestationStore:
    def test_add_valid_attestation(self, attestation_store):
        att = _make_attestation()
        assert attestation_store.add(att) is True

    def test_get_for_agent(self, attestation_store):
        att = _make_attestation(to_agent="aureus", quest_id="q1")
        attestation_store.add(att)
        results = attestation_store.get_for_agent("aureus")
        assert len(results) == 1
        assert results[0]["quest_id"] == "q1"

    def test_get_for_agent_empty(self, attestation_store):
        results = attestation_store.get_for_agent("nonexistent")
        assert results == []

    def test_self_attestation_rejected(self, attestation_store):
        att = _make_attestation(from_clan="test-clan", to_clan="test-clan")
        assert attestation_store.add(att) is False

    def test_duplicate_rejected(self, attestation_store):
        att = _make_attestation(quest_id="q1")
        assert attestation_store.add(att) is True
        assert attestation_store.add(att) is False

    def test_different_quests_accepted(self, attestation_store):
        att1 = _make_attestation(quest_id="q1")
        att2 = _make_attestation(quest_id="q2")
        assert attestation_store.add(att1) is True
        assert attestation_store.add(att2) is True
        results = attestation_store.get_for_agent("aureus")
        assert len(results) == 2

    def test_count_unique_clans(self, attestation_store):
        att1 = _make_attestation(from_clan="clan-a", quest_id="q1")
        att2 = _make_attestation(from_clan="clan-b", quest_id="q2")
        att3 = _make_attestation(from_clan="clan-a", quest_id="q3")
        attestation_store.add(att1)
        attestation_store.add(att2)
        attestation_store.add(att3)
        assert attestation_store.count_unique_clans("aureus") == 2

    def test_count_unique_clans_empty(self, attestation_store):
        assert attestation_store.count_unique_clans("nonexistent") == 0


# ─── ResonanceCalculator ──────────────────────────────────────────


class TestResonanceCalculator:
    def test_empty_list_returns_zero(self, resonance_calculator):
        assert resonance_calculator.compute([]) == 0.0

    def test_single_attestation_today(self, resonance_calculator):
        today = date.today()
        att = _make_attestation(
            quality=5, reliability=5, collaboration=5, timestamp=today.isoformat()
        )
        score = resonance_calculator.compute([att], today=today)
        # attestation_score = 5, recency = 1.0, diversity = 1 + 0.1*1 = 1.1
        expected = 5.0 * 1.0 * 1.1
        assert abs(score - expected) < 0.01

    def test_recency_decay(self, resonance_calculator):
        today = date(2026, 6, 1)
        half_year_ago = (today - timedelta(days=182)).isoformat()
        att = _make_attestation(quality=3, reliability=3, collaboration=3, timestamp=half_year_ago)
        score = resonance_calculator.compute([att], today=today)
        # attestation_score = 3.0, recency = 1 - 182/365 ~ 0.5014
        # diversity = 1 + 0.1*1 = 1.1
        recency = 1.0 - (182.0 / 365.0)
        expected = 3.0 * recency * 1.1
        assert abs(score - expected) < 0.01

    def test_fully_decayed_attestation(self, resonance_calculator):
        today = date(2026, 6, 1)
        old = (today - timedelta(days=400)).isoformat()
        att = _make_attestation(timestamp=old)
        score = resonance_calculator.compute([att], today=today)
        assert score == 0.0

    def test_diversity_bonus(self, resonance_calculator):
        today = date.today()
        att1 = _make_attestation(
            from_clan="clan-a",
            quest_id="q1",
            quality=3,
            reliability=3,
            collaboration=3,
            timestamp=today.isoformat(),
        )
        att2 = _make_attestation(
            from_clan="clan-b",
            quest_id="q2",
            quality=3,
            reliability=3,
            collaboration=3,
            timestamp=today.isoformat(),
        )
        score = resonance_calculator.compute([att1, att2], today=today)
        # attestation_score = 3 each, recency = 1.0 each
        # unique clans = 2 -> diversity = 1 + 0.1*2 = 1.2
        expected = (3.0 * 1.0 * 1.2) + (3.0 * 1.0 * 1.2)
        assert abs(score - expected) < 0.01

    def test_multiple_attestations_same_clan(self, resonance_calculator):
        today = date.today()
        att1 = _make_attestation(
            from_clan="clan-a",
            quest_id="q1",
            quality=4,
            reliability=4,
            collaboration=4,
            timestamp=today.isoformat(),
        )
        att2 = _make_attestation(
            from_clan="clan-a",
            quest_id="q2",
            quality=4,
            reliability=4,
            collaboration=4,
            timestamp=today.isoformat(),
        )
        score = resonance_calculator.compute([att1, att2], today=today)
        # unique clans = 1 -> diversity = 1 + 0.1*1 = 1.1
        expected = (4.0 * 1.0 * 1.1) + (4.0 * 1.0 * 1.1)
        assert abs(score - expected) < 0.01


# ─── Gateway ───────────────────────────────────────────────────────


class TestGateway:
    @pytest.fixture
    def gateway(self, sample_mappings):
        table = TranslationTable(clan_id="test-clan", mappings=sample_mappings)
        validator = InboundValidator(
            known_clans={"nakama-crew", "alliance-x"},
            published_aliases={"zeta-legal-alpha", "aureus"},
        )
        return Gateway(
            clan_id="test-clan",
            display_name="Test Clan",
            translation_table=table,
            inbound_validator=validator,
        )

    def test_build_public_profile_structure(self, gateway):
        profile = gateway.build_public_profile()
        assert profile["clan_id"] == "test-clan"
        assert profile["display_name"] == "Test Clan"
        assert len(profile["agents"]) == 2
        assert profile["clan_stats"]["total_published_agents"] == 2

    def test_profile_no_internal_data(self, gateway):
        profile = gateway.build_public_profile()
        profile_str = str(profile)
        # Must not contain internal namespaces or agent names
        assert "community" not in profile_str
        assert "admin-ph" not in profile_str
        assert "engineering" not in profile_str
        assert "eng-lead" not in profile_str
        assert "plutus" not in profile_str

    def test_profile_contains_only_published_aliases(self, gateway):
        profile = gateway.build_public_profile()
        aliases = {a["alias"] for a in profile["agents"]}
        assert aliases == {"zeta-legal-alpha", "aureus"}
        # Unpublished agent must not appear
        assert "shadow-eng" not in aliases

    def test_process_inbound_valid(self, gateway):
        msg = gateway.process_inbound(
            "nakama-crew",
            {
                "target_agent": "aureus",
                "type": "attestation",
                "payload": "Great quest.",
            },
        )
        assert msg is not None
        assert isinstance(msg, Message)
        assert msg.src == "gateway"
        assert msg.dst == "finance"
        assert msg.msg.startswith("AGORA:")

    def test_process_inbound_unknown_clan(self, gateway):
        msg = gateway.process_inbound(
            "shadow-corp",
            {
                "target_agent": "aureus",
                "type": "attestation",
                "payload": "test",
            },
        )
        assert msg is None

    def test_process_inbound_unknown_agent(self, gateway):
        msg = gateway.process_inbound(
            "nakama-crew",
            {
                "target_agent": "nonexistent",
                "type": "attestation",
                "payload": "test",
            },
        )
        assert msg is None

    def test_format_outbound_allowed(self, gateway):
        internal_msg = Message(
            ts=date.today(),
            src="gateway",
            dst="finance",
            type="event",
            msg="attestation: quality excellent",
            ttl=7,
            ack=[],
        )
        result = gateway.format_outbound(internal_msg)
        assert result is not None
        assert result["source_clan"] == "test-clan"
        assert result["type"] == "attestation"

    def test_format_outbound_blocked(self, gateway):
        internal_msg = Message(
            ts=date.today(),
            src="gateway",
            dst="finance",
            type="event",
            msg="internal data from bus.jsonl",
            ttl=7,
            ack=[],
        )
        result = gateway.format_outbound(internal_msg)
        assert result is None
