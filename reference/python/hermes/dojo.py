"""HERMES Dojo — ARC-2314 Orchestration Plane Reference Implementation.

The Dojo is the Orchestration Plane agent responsible for quest dispatch,
skill roster management, backlog prioritization, and XP tracking.

This module implements the Grand Dojo standard: the template that all
clan-local Dojos MUST conform to per ARC-2314.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Optional


# --- Enums ---

class Plane(str, Enum):
    """The three operational planes defined by ARC-2314."""

    CONTROL = "control"
    ORCHESTRATION = "orchestration"
    USER = "user"


class QuestStatus(str, Enum):
    """Quest lifecycle states per ARC-2314 Section 6.2."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class QuestType(str, Enum):
    """Arena quest types per ARC-2314 Section 8.5."""

    SOLO = "solo"
    CO_TRAINING = "co_training"
    BATTLE_ROYALE = "battle_royale"
    PVP = "pvp"
    CROSS_CLAN = "cross_clan"


class SkillAvailability(str, Enum):
    """Skill availability states."""

    ACTIVE = "active"
    BUSY = "busy"
    OFFLINE = "offline"


# --- Data Classes ---

@dataclass(frozen=True)
class SkillProfile:
    """A Skill's capability profile for Dojo quest matching (ARC-2314 s7.2).

    Follows ARC-2606 capability taxonomy (9 top-level domains).
    """

    skill_id: str
    clan_id: str
    capabilities: tuple[str, ...]
    experience: dict = field(default_factory=dict)
    availability: SkillAvailability = SkillAvailability.ACTIVE

    def matches(self, required: str) -> bool:
        """Check if this Skill matches a required capability.

        Supports prefix matching: "eng" matches "eng.protocol-design".
        """
        for cap in self.capabilities:
            if cap == required or cap.startswith(required + "."):
                return True
        return False

    def matches_any(self, required: list[str]) -> bool:
        """Check if this Skill matches any of the required capabilities."""
        return any(self.matches(r) for r in required)

    def to_dict(self) -> dict:
        return {
            "skill_id": self.skill_id,
            "clan_id": self.clan_id,
            "capabilities": list(self.capabilities),
            "experience": self.experience,
            "availability": self.availability.value,
        }


@dataclass
class Quest:
    """A unit of work dispatched by the Dojo (ARC-2314 s8.3)."""

    quest_id: str
    quest_type: QuestType
    title: str
    skills: list[str]
    priority: str = "normal"
    deadline: Optional[str] = None
    acceptance_criteria: list[str] = field(default_factory=list)
    status: QuestStatus = QuestStatus.PENDING
    xp_reward: int = 10
    results: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "quest_id": self.quest_id,
            "type": self.quest_type.value,
            "title": self.title,
            "skills": self.skills,
            "priority": self.priority,
            "deadline": self.deadline,
            "acceptance_criteria": self.acceptance_criteria,
            "status": self.status.value,
            "xp_reward": self.xp_reward,
            "results": self.results,
        }


# --- Dojo (Orchestration Plane) ---

class Dojo:
    """The Orchestration Plane agent — ARC-2314 Grand Dojo implementation.

    Manages skill roster, quest backlog, dispatch, and XP tracking.
    Does NOT route messages (that's CP/Messenger) or execute work
    (that's UP/Skill).
    """

    def __init__(self, clan_id: str) -> None:
        self.clan_id = clan_id
        self._roster: dict[str, SkillProfile] = {}
        self._backlog: list[Quest] = []
        self._completed: list[Quest] = []
        self._xp: dict[str, int] = {}

    # --- Roster Management ---

    def register_skill(self, profile: SkillProfile) -> None:
        """Register a Skill in the Dojo's roster."""
        if profile.clan_id != self.clan_id:
            raise ValueError(
                f"Cannot register skill from clan '{profile.clan_id}' "
                f"in dojo for clan '{self.clan_id}'"
            )
        self._roster[profile.skill_id] = profile

    def unregister_skill(self, skill_id: str) -> None:
        """Remove a Skill from the roster."""
        self._roster.pop(skill_id, None)

    def get_skill(self, skill_id: str) -> Optional[SkillProfile]:
        """Look up a Skill by ID."""
        return self._roster.get(skill_id)

    def list_skills(
        self,
        availability: Optional[SkillAvailability] = None,
    ) -> list[SkillProfile]:
        """List Skills, optionally filtered by availability."""
        skills = list(self._roster.values())
        if availability is not None:
            skills = [s for s in skills if s.availability == availability]
        return skills

    def match_skills(self, capabilities: list[str]) -> list[SkillProfile]:
        """Find Skills matching any of the required capabilities.

        Used by the Dojo for quest dispatch (ARC-2314 s6.1).
        Returns Skills sorted by number of matching capabilities (best first).
        """
        matches = []
        for skill in self._roster.values():
            if skill.availability != SkillAvailability.ACTIVE:
                continue
            match_count = sum(1 for c in capabilities if skill.matches(c))
            if match_count > 0:
                matches.append((match_count, skill))
        matches.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in matches]

    @property
    def roster_size(self) -> int:
        return len(self._roster)

    # --- Quest Backlog ---

    def create_quest(
        self,
        quest_id: str,
        quest_type: QuestType,
        title: str,
        required_capabilities: list[str],
        priority: str = "normal",
        deadline: Optional[str] = None,
        acceptance_criteria: Optional[list[str]] = None,
        xp_reward: int = 10,
    ) -> Quest:
        """Create a quest and auto-assign matching Skills.

        This is the Dojo's core dispatch function (ARC-2314 s6.2).
        """
        matched = self.match_skills(required_capabilities)
        if not matched:
            raise ValueError(
                f"No active skills match capabilities: {required_capabilities}"
            )

        skill_ids = [s.skill_id for s in matched]
        quest = Quest(
            quest_id=quest_id,
            quest_type=quest_type,
            title=title,
            skills=skill_ids,
            priority=priority,
            deadline=deadline,
            acceptance_criteria=acceptance_criteria or [],
            xp_reward=xp_reward,
        )
        self._backlog.append(quest)
        return quest

    def dispatch_quest(self, quest_id: str) -> Quest:
        """Move a quest from PENDING to IN_PROGRESS (ARC-2314 s6.2 step 3)."""
        quest = self._find_quest(quest_id)
        if quest.status != QuestStatus.PENDING:
            raise ValueError(
                f"Quest '{quest_id}' is {quest.status.value}, cannot dispatch"
            )
        quest.status = QuestStatus.IN_PROGRESS
        return quest

    def complete_quest(
        self,
        quest_id: str,
        results: Optional[dict] = None,
    ) -> Quest:
        """Mark a quest as completed and award XP (ARC-2314 s6.2 steps 7-8)."""
        quest = self._find_quest(quest_id)
        if quest.status != QuestStatus.IN_PROGRESS:
            raise ValueError(
                f"Quest '{quest_id}' is {quest.status.value}, cannot complete"
            )
        quest.status = QuestStatus.COMPLETED
        quest.results = results or {}

        # Award XP to participating skills
        for skill_id in quest.skills:
            self._xp[skill_id] = self._xp.get(skill_id, 0) + quest.xp_reward

        # Move to completed list
        self._backlog.remove(quest)
        self._completed.append(quest)
        return quest

    def fail_quest(self, quest_id: str, reason: str = "") -> Quest:
        """Mark a quest as failed."""
        quest = self._find_quest(quest_id)
        quest.status = QuestStatus.FAILED
        quest.results = {"failure_reason": reason}
        self._backlog.remove(quest)
        self._completed.append(quest)
        return quest

    def cancel_quest(self, quest_id: str) -> Quest:
        """Cancel a pending quest."""
        quest = self._find_quest(quest_id)
        if quest.status not in (QuestStatus.PENDING, QuestStatus.IN_PROGRESS):
            raise ValueError(
                f"Quest '{quest_id}' is {quest.status.value}, cannot cancel"
            )
        quest.status = QuestStatus.CANCELLED
        self._backlog.remove(quest)
        self._completed.append(quest)
        return quest

    def list_backlog(
        self,
        status: Optional[QuestStatus] = None,
    ) -> list[Quest]:
        """List quests in the backlog, optionally filtered by status."""
        if status is not None:
            return [q for q in self._backlog if q.status == status]
        return list(self._backlog)

    def list_completed(self) -> list[Quest]:
        """List completed/failed/cancelled quests."""
        return list(self._completed)

    # --- XP Tracking ---

    def get_xp(self, skill_id: str) -> int:
        """Get accumulated XP for a Skill."""
        return self._xp.get(skill_id, 0)

    def get_leaderboard(self) -> list[tuple[str, int]]:
        """Get the XP leaderboard sorted by XP descending."""
        return sorted(self._xp.items(), key=lambda x: x[1], reverse=True)

    @property
    def total_xp(self) -> int:
        return sum(self._xp.values())

    # --- Plane Validation ---

    @staticmethod
    def validate_plane_separation(
        agent_role: str,
        action: str,
    ) -> bool:
        """Validate that an action is allowed for a given plane role.

        ARC-2314 Section 9.3: No direct CP-UP interface.
        Messengers don't dispatch. Skills don't route.
        """
        forbidden = {
            "messenger": {
                "dispatch_quest", "create_quest", "complete_quest",
                "manage_backlog", "compute_xp",
            },
            "skill": {
                "route_message", "discover_clan", "translate_identity",
                "dispatch_quest", "manage_backlog",
            },
            "dojo": {
                "route_message", "discover_clan", "translate_identity",
                "execute_work",
            },
        }
        role_forbidden = forbidden.get(agent_role, set())
        return action not in role_forbidden

    # --- Serialization ---

    def to_dict(self) -> dict:
        """Serialize the Dojo state for persistence."""
        return {
            "clan_id": self.clan_id,
            "roster": {k: v.to_dict() for k, v in self._roster.items()},
            "backlog": [q.to_dict() for q in self._backlog],
            "completed": [q.to_dict() for q in self._completed],
            "xp": dict(self._xp),
        }

    def save(self, path: str | Path) -> None:
        """Save Dojo state to a JSON file."""
        path = Path(path)
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    # --- Internal ---

    def _find_quest(self, quest_id: str) -> Quest:
        for q in self._backlog:
            if q.quest_id == quest_id:
                return q
        raise KeyError(f"Quest '{quest_id}' not found in backlog")
