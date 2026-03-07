"""Tests for HERMES Dojo — ARC-2314 Orchestration Plane.

Covers: SkillProfile, Quest, Dojo (roster, dispatch, XP, plane validation).
"""

import json
import pytest
from pathlib import Path

from hermes.dojo import (
    Dojo,
    Plane,
    Quest,
    QuestStatus,
    QuestType,
    SkillAvailability,
    SkillProfile,
)


# --- Fixtures ---

@pytest.fixture
def clan_id():
    return "momoshod"


@pytest.fixture
def dojo(clan_id):
    return Dojo(clan_id)


@pytest.fixture
def protocol_architect(clan_id):
    return SkillProfile(
        skill_id="protocol-architect",
        clan_id=clan_id,
        capabilities=(
            "eng.protocol-design",
            "eng.telecom.3gpp",
            "research.standards",
            "eng.python",
        ),
        experience={"quests_completed": 47, "arena_xp": 259},
    )


@pytest.fixture
def cybersec_advisor(clan_id):
    return SkillProfile(
        skill_id="cybersec-advisor",
        clan_id=clan_id,
        capabilities=(
            "eng.cybersecurity",
            "eng.threat-modeling",
            "ops.audit",
        ),
        experience={"quests_completed": 12, "arena_xp": 86},
    )


@pytest.fixture
def pm_skill(clan_id):
    return SkillProfile(
        skill_id="project-commander",
        clan_id=clan_id,
        capabilities=(
            "ops.project-management",
            "ops.governance",
            "ops.risk-assessment",
        ),
        experience={"quests_completed": 30, "arena_xp": 120},
    )


@pytest.fixture
def offline_skill(clan_id):
    return SkillProfile(
        skill_id="inactive-skill",
        clan_id=clan_id,
        capabilities=("eng.rust",),
        availability=SkillAvailability.OFFLINE,
    )


@pytest.fixture
def populated_dojo(dojo, protocol_architect, cybersec_advisor, pm_skill):
    dojo.register_skill(protocol_architect)
    dojo.register_skill(cybersec_advisor)
    dojo.register_skill(pm_skill)
    return dojo


# --- Plane Enum ---

class TestPlane:
    def test_three_planes_exist(self):
        assert Plane.CONTROL == "control"
        assert Plane.ORCHESTRATION == "orchestration"
        assert Plane.USER == "user"

    def test_plane_values(self):
        assert len(Plane) == 3


# --- SkillProfile ---

class TestSkillProfile:
    def test_create_profile(self, protocol_architect):
        assert protocol_architect.skill_id == "protocol-architect"
        assert protocol_architect.clan_id == "momoshod"
        assert len(protocol_architect.capabilities) == 4
        assert protocol_architect.availability == SkillAvailability.ACTIVE

    def test_matches_exact(self, protocol_architect):
        assert protocol_architect.matches("eng.protocol-design")

    def test_matches_prefix(self, protocol_architect):
        assert protocol_architect.matches("eng")

    def test_matches_deep_prefix(self, protocol_architect):
        assert protocol_architect.matches("eng.telecom")

    def test_no_match(self, protocol_architect):
        assert not protocol_architect.matches("legal")

    def test_matches_any(self, protocol_architect):
        assert protocol_architect.matches_any(["legal", "eng.python"])

    def test_matches_any_none(self, protocol_architect):
        assert not protocol_architect.matches_any(["legal", "finance"])

    def test_to_dict(self, protocol_architect):
        d = protocol_architect.to_dict()
        assert d["skill_id"] == "protocol-architect"
        assert d["availability"] == "active"
        assert isinstance(d["capabilities"], list)

    def test_immutable(self, protocol_architect):
        with pytest.raises(AttributeError):
            protocol_architect.skill_id = "hacked"


# --- Dojo Roster ---

class TestDojoRoster:
    def test_register_skill(self, dojo, protocol_architect):
        dojo.register_skill(protocol_architect)
        assert dojo.roster_size == 1

    def test_register_wrong_clan(self, dojo):
        foreign = SkillProfile(
            skill_id="spy",
            clan_id="enemy-clan",
            capabilities=("eng.hacking",),
        )
        with pytest.raises(ValueError, match="Cannot register"):
            dojo.register_skill(foreign)

    def test_unregister_skill(self, dojo, protocol_architect):
        dojo.register_skill(protocol_architect)
        dojo.unregister_skill("protocol-architect")
        assert dojo.roster_size == 0

    def test_unregister_nonexistent(self, dojo):
        # Should not raise
        dojo.unregister_skill("ghost")
        assert dojo.roster_size == 0

    def test_get_skill(self, dojo, protocol_architect):
        dojo.register_skill(protocol_architect)
        found = dojo.get_skill("protocol-architect")
        assert found is protocol_architect

    def test_get_skill_not_found(self, dojo):
        assert dojo.get_skill("ghost") is None

    def test_list_skills(self, populated_dojo):
        skills = populated_dojo.list_skills()
        assert len(skills) == 3

    def test_list_skills_by_availability(self, dojo, protocol_architect, offline_skill):
        dojo.register_skill(protocol_architect)
        dojo.register_skill(offline_skill)
        active = dojo.list_skills(availability=SkillAvailability.ACTIVE)
        assert len(active) == 1
        offline = dojo.list_skills(availability=SkillAvailability.OFFLINE)
        assert len(offline) == 1


# --- Skill Matching ---

class TestSkillMatching:
    def test_match_exact_capability(self, populated_dojo):
        matches = populated_dojo.match_skills(["eng.cybersecurity"])
        assert len(matches) == 1
        assert matches[0].skill_id == "cybersec-advisor"

    def test_match_prefix_capability(self, populated_dojo):
        matches = populated_dojo.match_skills(["eng"])
        # protocol-architect has 3 eng.* caps, cybersec has 2 eng.* caps
        assert len(matches) >= 2
        assert matches[0].skill_id == "protocol-architect"

    def test_match_multiple_capabilities(self, populated_dojo):
        matches = populated_dojo.match_skills(
            ["eng.protocol-design", "ops.governance"]
        )
        assert len(matches) == 2

    def test_match_no_results(self, populated_dojo):
        matches = populated_dojo.match_skills(["legal.contracts"])
        assert len(matches) == 0

    def test_match_excludes_offline(self, dojo, protocol_architect, offline_skill):
        dojo.register_skill(protocol_architect)
        dojo.register_skill(offline_skill)
        matches = dojo.match_skills(["eng"])
        assert len(matches) == 1
        assert matches[0].skill_id == "protocol-architect"

    def test_match_sorted_by_relevance(self, populated_dojo):
        matches = populated_dojo.match_skills(
            ["eng.protocol-design", "eng.python", "eng.telecom.3gpp"]
        )
        # protocol-architect matches all 3, cybersec matches 0 of these specific
        assert matches[0].skill_id == "protocol-architect"


# --- Quest Lifecycle ---

class TestQuestLifecycle:
    def test_create_quest(self, populated_dojo):
        quest = populated_dojo.create_quest(
            quest_id="BR-003",
            quest_type=QuestType.BATTLE_ROYALE,
            title="Triple-Plane Architecture",
            required_capabilities=["eng.protocol-design"],
        )
        assert quest.quest_id == "BR-003"
        assert quest.status == QuestStatus.PENDING
        assert "protocol-architect" in quest.skills

    def test_create_quest_no_match(self, populated_dojo):
        with pytest.raises(ValueError, match="No active skills"):
            populated_dojo.create_quest(
                quest_id="FAIL-001",
                quest_type=QuestType.SOLO,
                title="Impossible quest",
                required_capabilities=["legal.international-law"],
            )

    def test_dispatch_quest(self, populated_dojo):
        quest = populated_dojo.create_quest(
            quest_id="Q-001",
            quest_type=QuestType.SOLO,
            title="Test",
            required_capabilities=["eng"],
        )
        dispatched = populated_dojo.dispatch_quest("Q-001")
        assert dispatched.status == QuestStatus.IN_PROGRESS

    def test_dispatch_non_pending(self, populated_dojo):
        populated_dojo.create_quest(
            quest_id="Q-001",
            quest_type=QuestType.SOLO,
            title="Test",
            required_capabilities=["eng"],
        )
        populated_dojo.dispatch_quest("Q-001")
        with pytest.raises(ValueError, match="cannot dispatch"):
            populated_dojo.dispatch_quest("Q-001")

    def test_complete_quest(self, populated_dojo):
        populated_dojo.create_quest(
            quest_id="Q-001",
            quest_type=QuestType.SOLO,
            title="Test",
            required_capabilities=["eng.protocol-design"],
            xp_reward=50,
        )
        populated_dojo.dispatch_quest("Q-001")
        quest = populated_dojo.complete_quest(
            "Q-001",
            results={"spec": "ARC-2314.md"},
        )
        assert quest.status == QuestStatus.COMPLETED
        assert quest.results["spec"] == "ARC-2314.md"

    def test_complete_awards_xp(self, populated_dojo):
        populated_dojo.create_quest(
            quest_id="Q-001",
            quest_type=QuestType.SOLO,
            title="Test",
            required_capabilities=["eng.protocol-design"],
            xp_reward=50,
        )
        populated_dojo.dispatch_quest("Q-001")
        populated_dojo.complete_quest("Q-001")
        assert populated_dojo.get_xp("protocol-architect") == 50

    def test_complete_non_dispatched(self, populated_dojo):
        populated_dojo.create_quest(
            quest_id="Q-001",
            quest_type=QuestType.SOLO,
            title="Test",
            required_capabilities=["eng"],
        )
        with pytest.raises(ValueError, match="cannot complete"):
            populated_dojo.complete_quest("Q-001")

    def test_fail_quest(self, populated_dojo):
        populated_dojo.create_quest(
            quest_id="Q-001",
            quest_type=QuestType.SOLO,
            title="Test",
            required_capabilities=["eng"],
        )
        populated_dojo.dispatch_quest("Q-001")
        quest = populated_dojo.fail_quest("Q-001", reason="blocked")
        assert quest.status == QuestStatus.FAILED
        assert quest.results["failure_reason"] == "blocked"

    def test_cancel_quest(self, populated_dojo):
        populated_dojo.create_quest(
            quest_id="Q-001",
            quest_type=QuestType.SOLO,
            title="Test",
            required_capabilities=["eng"],
        )
        quest = populated_dojo.cancel_quest("Q-001")
        assert quest.status == QuestStatus.CANCELLED

    def test_quest_not_found(self, populated_dojo):
        with pytest.raises(KeyError, match="not found"):
            populated_dojo.dispatch_quest("GHOST")


# --- Backlog ---

class TestBacklog:
    def test_list_backlog(self, populated_dojo):
        populated_dojo.create_quest(
            quest_id="Q-001",
            quest_type=QuestType.SOLO,
            title="A",
            required_capabilities=["eng"],
        )
        populated_dojo.create_quest(
            quest_id="Q-002",
            quest_type=QuestType.PVP,
            title="B",
            required_capabilities=["ops"],
        )
        assert len(populated_dojo.list_backlog()) == 2

    def test_list_backlog_by_status(self, populated_dojo):
        populated_dojo.create_quest(
            quest_id="Q-001",
            quest_type=QuestType.SOLO,
            title="A",
            required_capabilities=["eng"],
        )
        populated_dojo.create_quest(
            quest_id="Q-002",
            quest_type=QuestType.PVP,
            title="B",
            required_capabilities=["ops"],
        )
        populated_dojo.dispatch_quest("Q-001")
        pending = populated_dojo.list_backlog(status=QuestStatus.PENDING)
        assert len(pending) == 1
        in_progress = populated_dojo.list_backlog(status=QuestStatus.IN_PROGRESS)
        assert len(in_progress) == 1

    def test_completed_moves_from_backlog(self, populated_dojo):
        populated_dojo.create_quest(
            quest_id="Q-001",
            quest_type=QuestType.SOLO,
            title="A",
            required_capabilities=["eng"],
        )
        populated_dojo.dispatch_quest("Q-001")
        populated_dojo.complete_quest("Q-001")
        assert len(populated_dojo.list_backlog()) == 0
        assert len(populated_dojo.list_completed()) == 1


# --- XP Tracking ---

class TestXPTracking:
    def test_initial_xp_zero(self, populated_dojo):
        assert populated_dojo.get_xp("protocol-architect") == 0

    def test_xp_accumulates(self, populated_dojo):
        for i in range(3):
            populated_dojo.create_quest(
                quest_id=f"Q-{i}",
                quest_type=QuestType.SOLO,
                title=f"Quest {i}",
                required_capabilities=["eng.protocol-design"],
                xp_reward=10,
            )
            populated_dojo.dispatch_quest(f"Q-{i}")
            populated_dojo.complete_quest(f"Q-{i}")
        assert populated_dojo.get_xp("protocol-architect") == 30

    def test_leaderboard(self, populated_dojo):
        # Give protocol-architect 50 XP
        populated_dojo.create_quest(
            quest_id="Q-001",
            quest_type=QuestType.SOLO,
            title="Big quest",
            required_capabilities=["eng.protocol-design"],
            xp_reward=50,
        )
        populated_dojo.dispatch_quest("Q-001")
        populated_dojo.complete_quest("Q-001")

        # Give cybersec-advisor 20 XP
        populated_dojo.create_quest(
            quest_id="Q-002",
            quest_type=QuestType.SOLO,
            title="Small quest",
            required_capabilities=["eng.cybersecurity"],
            xp_reward=20,
        )
        populated_dojo.dispatch_quest("Q-002")
        populated_dojo.complete_quest("Q-002")

        board = populated_dojo.get_leaderboard()
        assert board[0][0] == "protocol-architect"
        assert board[0][1] == 50
        assert board[1][0] == "cybersec-advisor"
        assert board[1][1] == 20

    def test_total_xp(self, populated_dojo):
        populated_dojo.create_quest(
            quest_id="Q-001",
            quest_type=QuestType.BATTLE_ROYALE,
            title="Team quest",
            required_capabilities=["eng", "ops"],
            xp_reward=25,
        )
        populated_dojo.dispatch_quest("Q-001")
        populated_dojo.complete_quest("Q-001")
        # All matched skills get XP
        assert populated_dojo.total_xp >= 25


# --- Plane Separation Validation ---

class TestPlaneSeparation:
    """ARC-2314 Section 9.3: No direct CP-UP interface."""

    def test_messenger_cannot_dispatch(self):
        assert not Dojo.validate_plane_separation("messenger", "dispatch_quest")

    def test_messenger_cannot_create_quest(self):
        assert not Dojo.validate_plane_separation("messenger", "create_quest")

    def test_messenger_cannot_compute_xp(self):
        assert not Dojo.validate_plane_separation("messenger", "compute_xp")

    def test_skill_cannot_route(self):
        assert not Dojo.validate_plane_separation("skill", "route_message")

    def test_skill_cannot_dispatch(self):
        assert not Dojo.validate_plane_separation("skill", "dispatch_quest")

    def test_skill_cannot_discover(self):
        assert not Dojo.validate_plane_separation("skill", "discover_clan")

    def test_dojo_cannot_route(self):
        assert not Dojo.validate_plane_separation("dojo", "route_message")

    def test_dojo_cannot_execute(self):
        assert not Dojo.validate_plane_separation("dojo", "execute_work")

    def test_dojo_can_dispatch(self):
        assert Dojo.validate_plane_separation("dojo", "dispatch_quest")

    def test_dojo_can_manage_backlog(self):
        assert Dojo.validate_plane_separation("dojo", "manage_backlog")

    def test_messenger_can_route(self):
        assert Dojo.validate_plane_separation("messenger", "route_message")

    def test_skill_can_execute(self):
        assert Dojo.validate_plane_separation("skill", "execute_work")

    def test_unknown_role_allows_all(self):
        assert Dojo.validate_plane_separation("unknown", "anything")


# --- Quest Types ---

class TestQuestTypes:
    """ARC-2314 Section 8.5: Arena quest types."""

    def test_solo_quest(self, populated_dojo):
        quest = populated_dojo.create_quest(
            quest_id="TR-001",
            quest_type=QuestType.SOLO,
            title="Solo training",
            required_capabilities=["eng.protocol-design"],
        )
        assert quest.quest_type == QuestType.SOLO

    def test_battle_royale_multi_skill(self, populated_dojo):
        quest = populated_dojo.create_quest(
            quest_id="BR-003",
            quest_type=QuestType.BATTLE_ROYALE,
            title="Triple-Plane Architecture",
            required_capabilities=["eng", "ops"],
        )
        assert quest.quest_type == QuestType.BATTLE_ROYALE
        assert len(quest.skills) >= 2

    def test_pvp_quest(self, populated_dojo):
        quest = populated_dojo.create_quest(
            quest_id="PVP-001",
            quest_type=QuestType.PVP,
            title="Head to head",
            required_capabilities=["eng"],
        )
        assert quest.quest_type == QuestType.PVP

    def test_cross_clan_type(self, populated_dojo):
        quest = populated_dojo.create_quest(
            quest_id="XC-001",
            quest_type=QuestType.CROSS_CLAN,
            title="Joint security audit",
            required_capabilities=["eng.cybersecurity"],
        )
        assert quest.quest_type == QuestType.CROSS_CLAN


# --- Serialization ---

class TestSerialization:
    def test_quest_to_dict(self, populated_dojo):
        quest = populated_dojo.create_quest(
            quest_id="Q-001",
            quest_type=QuestType.BATTLE_ROYALE,
            title="Test",
            required_capabilities=["eng"],
            xp_reward=50,
        )
        d = quest.to_dict()
        assert d["quest_id"] == "Q-001"
        assert d["type"] == "battle_royale"
        assert d["status"] == "pending"
        assert d["xp_reward"] == 50

    def test_dojo_to_dict(self, populated_dojo):
        d = populated_dojo.to_dict()
        assert d["clan_id"] == "momoshod"
        assert len(d["roster"]) == 3
        assert isinstance(d["xp"], dict)

    def test_dojo_save(self, populated_dojo, tmp_path):
        populated_dojo.create_quest(
            quest_id="Q-001",
            quest_type=QuestType.SOLO,
            title="Test",
            required_capabilities=["eng"],
        )
        path = tmp_path / "dojo.json"
        populated_dojo.save(path)
        data = json.loads(path.read_text())
        assert data["clan_id"] == "momoshod"
        assert len(data["backlog"]) == 1

    def test_dojo_full_lifecycle_serialization(self, populated_dojo, tmp_path):
        """Full lifecycle: create -> dispatch -> complete -> save."""
        populated_dojo.create_quest(
            quest_id="Q-001",
            quest_type=QuestType.BATTLE_ROYALE,
            title="Full test",
            required_capabilities=["eng.protocol-design", "ops.governance"],
            xp_reward=100,
        )
        populated_dojo.dispatch_quest("Q-001")
        populated_dojo.complete_quest("Q-001", results={"output": "ARC-2314.md"})

        path = tmp_path / "dojo.json"
        populated_dojo.save(path)
        data = json.loads(path.read_text())
        assert len(data["backlog"]) == 0
        assert len(data["completed"]) == 1
        assert data["completed"][0]["status"] == "completed"
        assert sum(data["xp"].values()) >= 100
