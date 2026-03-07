"""Tests for HERMES Agora Directory Client — ARC-2606."""

import json

import pytest

from hermes.agora import AgoraDirectory


# ─── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def agora(tmp_path):
    """An AgoraDirectory with structure ensured."""
    d = AgoraDirectory(tmp_path / "agora")
    d.ensure_structure()
    return d


@pytest.fixture
def sample_profile():
    """A sample clan profile."""
    return {
        "clan_id": "clan-alpha",
        "display_name": "Alpha Collective",
        "protocol_version": "0.3.0",
        "agents": [
            {
                "alias": "scout",
                "capabilities": ["research.literature", "research.patents"],
                "resonance": 4.5,
            },
            {
                "alias": "herald",
                "capabilities": ["messaging.inter-clan"],
                "resonance": 2.0,
            },
        ],
    }


@pytest.fixture
def second_profile():
    """A second clan profile for multi-clan tests."""
    return {
        "clan_id": "clan-beta",
        "display_name": "Beta Hive",
        "protocol_version": "0.3.0",
        "agents": [
            {
                "alias": "engineer",
                "capabilities": ["engineering.code-review", "engineering.architecture"],
                "resonance": 7.0,
            },
            {
                "alias": "researcher",
                "capabilities": ["research.ml", "research.literature"],
                "resonance": 3.0,
            },
        ],
    }


# ─── ensure_structure ──────────────────────────────────────────────


class TestEnsureStructure:
    """Tests for directory scaffolding."""

    def test_creates_all_directories(self, tmp_path):
        agora = AgoraDirectory(tmp_path / "new-agora")
        agora.ensure_structure()

        assert (agora.path / "profiles").is_dir()
        assert (agora.path / "inbox").is_dir()
        assert (agora.path / "attestations").is_dir()
        assert (agora.path / "quest_log").is_dir()

    def test_idempotent(self, tmp_path):
        agora = AgoraDirectory(tmp_path / "agora")
        agora.ensure_structure()
        agora.ensure_structure()  # Should not raise
        assert (agora.path / "profiles").is_dir()


# ─── publish_profile / read_profile ────────────────────────────────


class TestProfiles:
    """Tests for profile publishing and reading."""

    def test_publish_creates_file(self, agora, sample_profile):
        path = agora.publish_profile(sample_profile)
        assert path.exists()
        assert path.name == "clan-alpha.json"

    def test_read_published_profile(self, agora, sample_profile):
        agora.publish_profile(sample_profile)
        loaded = agora.read_profile("clan-alpha")
        assert loaded is not None
        assert loaded["clan_id"] == "clan-alpha"
        assert loaded["display_name"] == "Alpha Collective"
        assert len(loaded["agents"]) == 2

    def test_read_nonexistent_profile(self, agora):
        assert agora.read_profile("clan-nonexistent") is None

    def test_overwrite_profile(self, agora, sample_profile):
        agora.publish_profile(sample_profile)
        updated = dict(sample_profile)
        updated["display_name"] = "Alpha Revised"
        agora.publish_profile(updated)
        loaded = agora.read_profile("clan-alpha")
        assert loaded["display_name"] == "Alpha Revised"


# ─── list_clans ────────────────────────────────────────────────────


class TestListClans:
    """Tests for clan listing."""

    def test_empty_agora(self, agora):
        assert agora.list_clans() == []

    def test_lists_published_clans(self, agora, sample_profile, second_profile):
        agora.publish_profile(sample_profile)
        agora.publish_profile(second_profile)
        clans = agora.list_clans()
        assert clans == ["clan-alpha", "clan-beta"]

    def test_sorted_alphabetically(self, agora):
        agora.publish_profile({"clan_id": "zeta"})
        agora.publish_profile({"clan_id": "alpha"})
        agora.publish_profile({"clan_id": "mu"})
        assert agora.list_clans() == ["alpha", "mu", "zeta"]


# ─── send_message / read_inbox ─────────────────────────────────────


class TestInbox:
    """Tests for message inbox operations."""

    def test_send_creates_file(self, agora):
        msg = {"type": "hello", "from": "clan-alpha", "payload": "greetings"}
        path = agora.send_message("clan-beta", msg)
        assert path.exists()
        assert "hello" in path.name

    def test_read_inbox_returns_messages(self, agora):
        msg1 = {"type": "hello", "from": "clan-alpha", "payload": "first"}
        msg2 = {"type": "quest_proposal", "from": "clan-alpha", "payload": "second"}
        agora.send_message("clan-beta", msg1)
        agora.send_message("clan-beta", msg2)

        inbox = agora.read_inbox("clan-beta")
        assert len(inbox) == 2
        assert inbox[0]["payload"] == "first"
        assert inbox[1]["payload"] == "second"

    def test_read_empty_inbox(self, agora):
        assert agora.read_inbox("clan-nobody") == []

    def test_messages_isolated_per_clan(self, agora):
        agora.send_message("clan-a", {"type": "msg", "data": "for-a"})
        agora.send_message("clan-b", {"type": "msg", "data": "for-b"})

        inbox_a = agora.read_inbox("clan-a")
        inbox_b = agora.read_inbox("clan-b")
        assert len(inbox_a) == 1
        assert len(inbox_b) == 1
        assert inbox_a[0]["data"] == "for-a"
        assert inbox_b[0]["data"] == "for-b"


# ─── clear_inbox ───────────────────────────────────────────────────


class TestClearInbox:
    """Tests for inbox clearing."""

    def test_clear_returns_count(self, agora):
        agora.send_message("clan-x", {"type": "msg", "data": "1"})
        agora.send_message("clan-x", {"type": "msg", "data": "2"})
        agora.send_message("clan-x", {"type": "msg", "data": "3"})

        count = agora.clear_inbox("clan-x")
        assert count == 3

    def test_clear_removes_files(self, agora):
        agora.send_message("clan-x", {"type": "msg", "data": "1"})
        agora.clear_inbox("clan-x")
        assert agora.read_inbox("clan-x") == []

    def test_clear_nonexistent_inbox(self, agora):
        assert agora.clear_inbox("clan-ghost") == 0


# ─── discover ──────────────────────────────────────────────────────


class TestDiscover:
    """Tests for capability-based agent discovery."""

    def test_discover_by_prefix(self, agora, sample_profile, second_profile):
        agora.publish_profile(sample_profile)
        agora.publish_profile(second_profile)

        matches = agora.discover("research")
        # Should find scout (research.literature, research.patents) and researcher (research.ml, research.literature)
        assert len(matches) == 2
        aliases = {m["agent_alias"] for m in matches}
        assert aliases == {"scout", "researcher"}

    def test_discover_specific_capability(self, agora, sample_profile, second_profile):
        agora.publish_profile(sample_profile)
        agora.publish_profile(second_profile)

        matches = agora.discover("engineering.code-review")
        assert len(matches) == 1
        assert matches[0]["agent_alias"] == "engineer"

    def test_discover_no_matches(self, agora, sample_profile):
        agora.publish_profile(sample_profile)
        assert agora.discover("quantum-computing") == []

    def test_discover_sorted_by_resonance(self, agora, sample_profile, second_profile):
        agora.publish_profile(sample_profile)
        agora.publish_profile(second_profile)

        matches = agora.discover("research")
        # scout has resonance 4.5, researcher has 3.0
        assert matches[0]["resonance"] >= matches[1]["resonance"]

    def test_discover_empty_agora(self, agora):
        assert agora.discover("anything") == []

    def test_discover_no_duplicate_agents(self, agora):
        """An agent matching multiple capabilities should appear only once."""
        profile = {
            "clan_id": "clan-multi",
            "agents": [
                {
                    "alias": "polymath",
                    "capabilities": ["research.ml", "research.nlp", "research.cv"],
                    "resonance": 5.0,
                },
            ],
        }
        agora.publish_profile(profile)
        matches = agora.discover("research")
        assert len(matches) == 1


# ─── store_attestation ─────────────────────────────────────────────


class TestStoreAttestation:
    """Tests for attestation storage."""

    def test_store_creates_file(self, agora):
        att = {
            "id": "att-001",
            "from_clan": "clan-beta",
            "to_clan": "clan-alpha",
            "to_agent": "scout",
            "quest_id": "q-42",
            "rating": {"quality": 5, "reliability": 4, "collaboration": 5},
        }
        path = agora.store_attestation(att)
        assert path.exists()
        assert path.name == "att-001.json"

    def test_stored_attestation_readable(self, agora):
        att = {"id": "att-002", "from_clan": "clan-beta", "rating": {"quality": 3}}
        agora.store_attestation(att)
        loaded = json.loads((agora.path / "attestations" / "att-002.json").read_text())
        assert loaded["from_clan"] == "clan-beta"

    def test_default_id(self, agora):
        att = {"from_clan": "clan-x"}
        path = agora.store_attestation(att)
        assert "att-" in path.name
