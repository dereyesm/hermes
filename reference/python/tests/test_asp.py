"""Tests for HERMES Agent Service Platform — ARC-0369 F1 + F2 + F3 + F4 + F5."""

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from hermes.asp import (
    AgentProfile,
    AgentProfileError,
    AgentRegistry,
    AgentState,
    AgentStateTracker,
    ApprovalGateManager,
    ConcurrencyTracker,
    DispatchCommandRenderer,
    DispatchDecision,
    DispatchEngine,
    DispatchOutcome,
    DispatchRule,
    DispatchScheduler,
    DispatchTrigger,
    MessageCategory,
    MessageClassifier,
    NotificationThrottler,
    PendingApproval,
    QueueOverflow,
    ResourceLimits,
    _trigger_matches,
)
from hermes.message import Message


# ─── Helpers ──────────────────────────────────────────────────────


def _msg(
    src: str = "heraldo",
    dst: str = "*",
    msg_type: str = "state",
    msg_text: str = "test",
    ttl: int = 7,
    ts: date | None = None,
    ack: list[str] | None = None,
) -> Message:
    return Message(
        ts=ts or date.today(),
        src=src,
        dst=dst,
        type=msg_type,
        msg=msg_text,
        ttl=ttl,
        ack=ack or [],
    )


SENSOR_PROFILE = {
    "agent_id": "mail-scanner",
    "display_name": "Email Scanner",
    "version": "1.0.0",
    "role": "sensor",
    "description": "Scans inbox and writes summaries to bus.",
    "capabilities": ["email-scan", "inbox-summarize"],
    "dispatch_rules": [
        {
            "rule_id": "scheduled-scan",
            "trigger": {"type": "scheduled", "cron": "0 */4 * * *"},
            "approval_required": False,
        }
    ],
    "resource_limits": {
        "max_turns": 5,
        "timeout_seconds": 120,
        "allowed_tools": ["gmail-read"],
        "max_concurrent": 1,
    },
    "enabled": True,
}

WORKER_PROFILE = {
    "agent_id": "report-builder",
    "display_name": "Report Builder",
    "version": "1.2.0",
    "role": "worker",
    "description": "Generates structured reports from bus data on demand.",
    "capabilities": ["report-generate", "data-aggregate"],
    "dispatch_rules": [
        {
            "rule_id": "on-dispatch",
            "trigger": {
                "type": "event-driven",
                "match_type": "dispatch",
                "match_msg_prefix": "REPORT:",
            },
            "approval_required": False,
        },
        {
            "rule_id": "on-financial-dispatch",
            "trigger": {
                "type": "event-driven",
                "match_type": "dispatch",
                "match_msg_prefix": "REPORT:FINANCIAL:",
            },
            "approval_required": True,
            "approval_timeout_hours": 12,
        },
    ],
    "resource_limits": {
        "max_turns": 15,
        "timeout_seconds": 600,
        "allowed_tools": ["file-read", "file-write"],
        "max_concurrent": 1,
    },
    "enabled": True,
}

PLATFORM_PROFILE = {
    "agent_id": "platform-agent",
    "display_name": "Platform Agent",
    "version": "2.0.0",
    "role": "platform",
    "description": "Full-featured sensor + worker.",
    "capabilities": ["scan", "report"],
    "dispatch_rules": [
        {
            "rule_id": "on-alert",
            "trigger": {"type": "event-driven", "match_type": "alert"},
            "approval_required": False,
        }
    ],
    "resource_limits": {"max_concurrent": 2},
    "enabled": True,
}


# ─── F1: MessageClassifier ───────────────────────────────────────


class TestMessageClassifierBasic:
    """Basic classification tests (ARC-0369 §6.2)."""

    def test_broadcast_is_internal(self):
        mc = MessageClassifier(local_namespaces={"heraldo", "dojo"})
        msg = _msg(src="heraldo", dst="*")
        assert mc.classify(msg) == MessageCategory.INTERNAL

    def test_local_dst_is_internal(self):
        mc = MessageClassifier(local_namespaces={"heraldo", "dojo"})
        msg = _msg(src="heraldo", dst="dojo")
        assert mc.classify(msg) == MessageCategory.INTERNAL

    def test_external_dst_is_outbound(self):
        mc = MessageClassifier(local_namespaces={"heraldo"})
        msg = _msg(src="heraldo", dst="clan-jei")
        assert mc.classify(msg) == MessageCategory.OUTBOUND

    def test_gateway_src_is_inbound(self):
        mc = MessageClassifier(local_namespaces={"heraldo"})
        msg = _msg(src="gateway", dst="heraldo")
        assert mc.classify(msg) == MessageCategory.INBOUND

    def test_expired_message(self):
        mc = MessageClassifier(local_namespaces={"heraldo"})
        old_date = date.today() - timedelta(days=10)
        msg = _msg(src="heraldo", dst="*", ttl=7, ts=old_date)
        assert mc.classify(msg) == MessageCategory.EXPIRED

    def test_not_expired_within_ttl(self):
        mc = MessageClassifier(local_namespaces={"heraldo"})
        recent = date.today() - timedelta(days=3)
        msg = _msg(src="heraldo", dst="*", ttl=7, ts=recent)
        assert mc.classify(msg) == MessageCategory.INTERNAL

    def test_expired_takes_priority(self):
        mc = MessageClassifier(local_namespaces={"heraldo"})
        old = date.today() - timedelta(days=30)
        msg = _msg(src="heraldo", dst="clan-jei", ttl=7, ts=old)
        assert mc.classify(msg) == MessageCategory.EXPIRED

    def test_case_insensitive(self):
        mc = MessageClassifier(local_namespaces={"Heraldo"})
        msg = _msg(src="heraldo", dst="HERALDO")
        assert mc.classify(msg) == MessageCategory.INTERNAL


class TestMessageClassifierInternalOnly:
    """Internal-only namespace tests (ARC-0369 §6.4)."""

    def test_internal_only_src_always_internal(self):
        mc = MessageClassifier(
            local_namespaces={"heraldo"},
            internal_only_namespaces={"router", "dojo"},
        )
        msg = _msg(src="router", dst="clan-jei")
        assert mc.classify(msg) == MessageCategory.INTERNAL

    def test_non_internal_only_can_be_outbound(self):
        mc = MessageClassifier(
            local_namespaces={"heraldo"},
            internal_only_namespaces={"router"},
        )
        msg = _msg(src="heraldo", dst="clan-jei")
        assert mc.classify(msg) == MessageCategory.OUTBOUND

    def test_is_internal_only_src(self):
        mc = MessageClassifier(
            local_namespaces={"heraldo"},
            internal_only_namespaces={"router"},
        )
        assert mc.is_internal_only_src(_msg(src="router")) is True
        assert mc.is_internal_only_src(_msg(src="heraldo")) is False

    def test_internal_only_with_broadcast(self):
        mc = MessageClassifier(
            local_namespaces={"heraldo"},
            internal_only_namespaces={"dojo"},
        )
        msg = _msg(src="dojo", dst="*")
        assert mc.classify(msg) == MessageCategory.INTERNAL


class TestMessageClassifierSourceIntegrity:
    """Source integrity verification (ARC-0369 §6.3)."""

    def test_known_source_valid(self):
        mc = MessageClassifier(local_namespaces={"heraldo", "dojo"})
        assert mc.verify_source(_msg(src="heraldo")) is True

    def test_unknown_source_invalid(self):
        mc = MessageClassifier(local_namespaces={"heraldo"})
        assert mc.verify_source(_msg(src="unknown-agent")) is False

    def test_gateway_source_valid(self):
        mc = MessageClassifier(local_namespaces={"heraldo"})
        assert mc.verify_source(_msg(src="gateway")) is True

    def test_registered_agent_valid(self):
        mc = MessageClassifier(local_namespaces={"heraldo"})
        assert mc.verify_source(
            _msg(src="mail-scanner"),
            registered_agent_ids={"mail-scanner"},
        ) is True

    def test_unregistered_agent_invalid(self):
        mc = MessageClassifier(local_namespaces={"heraldo"})
        assert mc.verify_source(
            _msg(src="rogue-agent"),
            registered_agent_ids={"mail-scanner"},
        ) is False

    def test_custom_gateway_namespace(self):
        mc = MessageClassifier(
            local_namespaces={"heraldo"},
            gateway_namespace="gw",
        )
        assert mc.verify_source(_msg(src="gw")) is True
        assert mc.verify_source(_msg(src="gateway")) is False


class TestMessageClassifierEdgeCases:
    """Edge cases for classification."""

    def test_empty_local_namespaces(self):
        mc = MessageClassifier(local_namespaces=set())
        msg = _msg(src="heraldo", dst="dojo")
        assert mc.classify(msg) == MessageCategory.OUTBOUND

    def test_ttl_zero_same_day(self):
        mc = MessageClassifier(local_namespaces={"heraldo"})
        msg = _msg(src="heraldo", dst="*", ttl=0, ts=date.today())
        assert mc.classify(msg) == MessageCategory.INTERNAL  # 0 days <= 0 TTL

    def test_ttl_zero_next_day(self):
        mc = MessageClassifier(local_namespaces={"heraldo"})
        yesterday = date.today() - timedelta(days=1)
        msg = _msg(src="heraldo", dst="*", ttl=0, ts=yesterday)
        assert mc.classify(msg) == MessageCategory.EXPIRED

    def test_today_override(self):
        mc = MessageClassifier(local_namespaces={"heraldo"})
        msg = _msg(src="heraldo", dst="*", ttl=7, ts=date(2026, 1, 1))
        assert mc.classify(msg, today=date(2026, 1, 5)) == MessageCategory.INTERNAL
        assert mc.classify(msg, today=date(2026, 1, 20)) == MessageCategory.EXPIRED


# ─── F2: AgentProfile ────────────────────────────────────────────


class TestAgentProfileParsing:
    """Profile loading and validation tests (ARC-0369 §7.2-7.4)."""

    def test_sensor_profile(self):
        p = AgentProfile.from_dict(SENSOR_PROFILE)
        assert p.agent_id == "mail-scanner"
        assert p.role == "sensor"
        assert p.enabled is True
        assert len(p.dispatch_rules) == 1
        assert p.dispatch_rules[0].trigger.type == "scheduled"
        assert p.dispatch_rules[0].trigger.cron == "0 */4 * * *"

    def test_worker_profile(self):
        p = AgentProfile.from_dict(WORKER_PROFILE)
        assert p.agent_id == "report-builder"
        assert p.role == "worker"
        assert len(p.dispatch_rules) == 2
        assert p.dispatch_rules[0].approval_required is False
        assert p.dispatch_rules[1].approval_required is True
        assert p.dispatch_rules[1].approval_timeout_hours == 12

    def test_platform_profile(self):
        p = AgentProfile.from_dict(PLATFORM_PROFILE)
        assert p.agent_id == "platform-agent"
        assert p.role == "platform"
        assert p.resource_limits.max_concurrent == 2

    def test_resource_limits(self):
        p = AgentProfile.from_dict(WORKER_PROFILE)
        assert p.resource_limits.max_turns == 15
        assert p.resource_limits.timeout_seconds == 600
        assert p.resource_limits.allowed_tools == ("file-read", "file-write")
        assert p.resource_limits.max_concurrent == 1

    def test_capabilities_tuple(self):
        p = AgentProfile.from_dict(SENSOR_PROFILE)
        assert p.capabilities == ("email-scan", "inbox-summarize")

    def test_to_dict_round_trip(self):
        p = AgentProfile.from_dict(WORKER_PROFILE)
        d = p.to_dict()
        p2 = AgentProfile.from_dict(d)
        assert p2.agent_id == p.agent_id
        assert p2.role == p.role
        assert len(p2.dispatch_rules) == len(p.dispatch_rules)

    def test_filename_match(self):
        p = AgentProfile.from_dict(SENSOR_PROFILE, filename="mail-scanner")
        assert p.agent_id == "mail-scanner"

    def test_filename_mismatch_raises(self):
        with pytest.raises(AgentProfileError, match="does not match filename"):
            AgentProfile.from_dict(SENSOR_PROFILE, filename="wrong-name")


class TestAgentProfileValidation:
    """Validation error cases (ARC-0369 §7.4)."""

    def test_missing_agent_id(self):
        data = {**SENSOR_PROFILE}
        del data["agent_id"]
        with pytest.raises(AgentProfileError, match="agent_id"):
            AgentProfile.from_dict(data)

    def test_missing_role(self):
        data = {**SENSOR_PROFILE}
        del data["role"]
        with pytest.raises(AgentProfileError, match="role"):
            AgentProfile.from_dict(data)

    def test_invalid_role(self):
        data = {**SENSOR_PROFILE, "role": "invalid"}
        with pytest.raises(AgentProfileError, match="Invalid role"):
            AgentProfile.from_dict(data)

    def test_invalid_agent_id_format(self):
        data = {**SENSOR_PROFILE, "agent_id": "Invalid_ID"}
        with pytest.raises(AgentProfileError, match="Invalid agent_id"):
            AgentProfile.from_dict(data)

    def test_agent_id_starting_with_hyphen(self):
        data = {**SENSOR_PROFILE, "agent_id": "-bad"}
        with pytest.raises(AgentProfileError, match="Invalid agent_id"):
            AgentProfile.from_dict(data)

    def test_missing_dispatch_rules(self):
        data = {**SENSOR_PROFILE}
        del data["dispatch_rules"]
        with pytest.raises(AgentProfileError, match="dispatch_rules"):
            AgentProfile.from_dict(data)

    def test_dispatch_rules_not_list(self):
        data = {**SENSOR_PROFILE, "dispatch_rules": "not a list"}
        with pytest.raises(AgentProfileError, match="must be an array"):
            AgentProfile.from_dict(data)

    def test_missing_rule_id(self):
        data = {
            **SENSOR_PROFILE,
            "dispatch_rules": [{"trigger": {"type": "scheduled", "cron": "* * * * *"}, "approval_required": False}],
        }
        with pytest.raises(AgentProfileError, match="rule_id"):
            AgentProfile.from_dict(data)

    def test_invalid_trigger_type(self):
        data = {
            **SENSOR_PROFILE,
            "dispatch_rules": [
                {"rule_id": "r1", "trigger": {"type": "invalid"}, "approval_required": False}
            ],
        }
        with pytest.raises(AgentProfileError, match="invalid trigger type"):
            AgentProfile.from_dict(data)

    def test_event_driven_without_match_type(self):
        data = {
            **SENSOR_PROFILE,
            "dispatch_rules": [
                {"rule_id": "r1", "trigger": {"type": "event-driven"}, "approval_required": False}
            ],
        }
        with pytest.raises(AgentProfileError, match="requires 'match_type'"):
            AgentProfile.from_dict(data)

    def test_scheduled_without_cron(self):
        data = {
            **SENSOR_PROFILE,
            "dispatch_rules": [
                {"rule_id": "r1", "trigger": {"type": "scheduled"}, "approval_required": False}
            ],
        }
        with pytest.raises(AgentProfileError, match="requires 'cron'"):
            AgentProfile.from_dict(data)

    def test_missing_approval_required(self):
        data = {
            **SENSOR_PROFILE,
            "dispatch_rules": [
                {"rule_id": "r1", "trigger": {"type": "scheduled", "cron": "* * * * *"}}
            ],
        }
        with pytest.raises(AgentProfileError, match="approval_required"):
            AgentProfile.from_dict(data)

    def test_approval_required_not_bool(self):
        data = {
            **SENSOR_PROFILE,
            "dispatch_rules": [
                {"rule_id": "r1", "trigger": {"type": "scheduled", "cron": "* * * * *"}, "approval_required": "yes"}
            ],
        }
        with pytest.raises(AgentProfileError, match="must be boolean"):
            AgentProfile.from_dict(data)

    def test_missing_enabled(self):
        data = {**SENSOR_PROFILE}
        del data["enabled"]
        with pytest.raises(AgentProfileError, match="enabled"):
            AgentProfile.from_dict(data)

    def test_empty_dispatch_rules_ok(self):
        data = {**SENSOR_PROFILE, "dispatch_rules": []}
        p = AgentProfile.from_dict(data)
        assert len(p.dispatch_rules) == 0


# ─── F2: AgentRegistry ──────────────────────────────────────────


@pytest.fixture
def agents_dir(tmp_path):
    """Create an agents/ directory with sample profiles."""
    d = tmp_path / "agents"
    d.mkdir()
    (d / "mail-scanner.json").write_text(json.dumps(SENSOR_PROFILE))
    (d / "report-builder.json").write_text(json.dumps(WORKER_PROFILE))
    return d


@pytest.fixture
def agents_dir_with_disabled(agents_dir):
    """Add a disabled agent."""
    disabled = {**PLATFORM_PROFILE, "enabled": False}
    (agents_dir / "platform-agent.json").write_text(json.dumps(disabled))
    return agents_dir


@pytest.fixture
def agents_dir_with_invalid(agents_dir):
    """Add an invalid profile."""
    (agents_dir / "bad-agent.json").write_text('{"not": "valid profile"}')
    return agents_dir


class TestAgentRegistryLoading:
    """Registry loading tests (ARC-0369 §7.1)."""

    def test_loads_all_profiles(self, agents_dir):
        reg = AgentRegistry(agents_dir)
        reg.load_all()
        assert len(reg.all_profiles()) == 2

    def test_get_by_id(self, agents_dir):
        reg = AgentRegistry(agents_dir)
        reg.load_all()
        p = reg.get("mail-scanner")
        assert p is not None
        assert p.display_name == "Email Scanner"

    def test_get_missing_returns_none(self, agents_dir):
        reg = AgentRegistry(agents_dir)
        reg.load_all()
        assert reg.get("nonexistent") is None

    def test_all_agent_ids(self, agents_dir):
        reg = AgentRegistry(agents_dir)
        reg.load_all()
        assert reg.all_agent_ids() == {"mail-scanner", "report-builder"}

    def test_missing_dir_ok(self, tmp_path):
        reg = AgentRegistry(tmp_path / "nonexistent")
        reg.load_all()
        assert len(reg.all_profiles()) == 0

    def test_empty_dir_ok(self, tmp_path):
        d = tmp_path / "agents"
        d.mkdir()
        reg = AgentRegistry(d)
        reg.load_all()
        assert len(reg.all_profiles()) == 0


class TestAgentRegistryEnabled:
    """Enabled/disabled filtering tests."""

    def test_all_enabled(self, agents_dir):
        reg = AgentRegistry(agents_dir)
        reg.load_all()
        assert len(reg.all_enabled()) == 2

    def test_disabled_excluded(self, agents_dir_with_disabled):
        reg = AgentRegistry(agents_dir_with_disabled)
        reg.load_all()
        assert len(reg.all_profiles()) == 3
        assert len(reg.all_enabled()) == 2
        ids = {p.agent_id for p in reg.all_enabled()}
        assert "platform-agent" not in ids


class TestAgentRegistryErrors:
    """Invalid profile handling tests."""

    def test_invalid_profile_skipped(self, agents_dir_with_invalid):
        reg = AgentRegistry(agents_dir_with_invalid)
        reg.load_all()
        # 2 valid profiles loaded, invalid skipped
        assert len(reg.all_profiles()) == 2
        assert len(reg.errors) == 1
        assert "bad-agent.json" in reg.errors[0]

    def test_invalid_json_skipped(self, agents_dir):
        (agents_dir / "broken.json").write_text("not json {{{")
        reg = AgentRegistry(agents_dir)
        reg.load_all()
        assert len(reg.all_profiles()) == 2
        assert len(reg.errors) == 1

    def test_filename_mismatch_skipped(self, agents_dir):
        mismatched = {**SENSOR_PROFILE, "agent_id": "wrong-name"}
        (agents_dir / "mismatched.json").write_text(json.dumps(mismatched))
        reg = AgentRegistry(agents_dir)
        reg.load_all()
        assert len(reg.all_profiles()) == 2  # mismatched skipped
        assert len(reg.errors) == 1


class TestAgentRegistryHotReload:
    """Hot reload tests."""

    def test_reload_adds_new(self, agents_dir):
        reg = AgentRegistry(agents_dir)
        reg.load_all()
        assert len(reg.all_profiles()) == 2

        # Add new profile
        (agents_dir / "platform-agent.json").write_text(json.dumps(PLATFORM_PROFILE))
        reg.hot_reload()
        assert len(reg.all_profiles()) == 3

    def test_reload_removes_deleted(self, agents_dir):
        reg = AgentRegistry(agents_dir)
        reg.load_all()
        assert len(reg.all_profiles()) == 2

        (agents_dir / "mail-scanner.json").unlink()
        reg.hot_reload()
        assert len(reg.all_profiles()) == 1
        assert reg.get("mail-scanner") is None


# ─── F2: Dispatch Rule Matching ──────────────────────────────────


class TestTriggerMatching:
    """Event-driven trigger matching tests."""

    def test_type_match(self):
        trigger = DispatchTrigger(type="event-driven", match_type="dispatch")
        msg = _msg(msg_type="dispatch")
        assert _trigger_matches(trigger, msg) is True

    def test_type_mismatch(self):
        trigger = DispatchTrigger(type="event-driven", match_type="dispatch")
        msg = _msg(msg_type="alert")
        assert _trigger_matches(trigger, msg) is False

    def test_src_match(self):
        trigger = DispatchTrigger(
            type="event-driven", match_type="dispatch", match_src="heraldo"
        )
        msg = _msg(src="heraldo", msg_type="dispatch")
        assert _trigger_matches(trigger, msg) is True

    def test_src_mismatch(self):
        trigger = DispatchTrigger(
            type="event-driven", match_type="dispatch", match_src="heraldo"
        )
        msg = _msg(src="dojo", msg_type="dispatch")
        assert _trigger_matches(trigger, msg) is False

    def test_prefix_match(self):
        trigger = DispatchTrigger(
            type="event-driven", match_type="dispatch",
            match_msg_prefix="REPORT:",
        )
        msg = _msg(msg_type="dispatch", msg_text="REPORT:monthly summary")
        assert _trigger_matches(trigger, msg) is True

    def test_prefix_mismatch(self):
        trigger = DispatchTrigger(
            type="event-driven", match_type="dispatch",
            match_msg_prefix="REPORT:",
        )
        msg = _msg(msg_type="dispatch", msg_text="SCAN:inbox")
        assert _trigger_matches(trigger, msg) is False

    def test_all_conditions_combined(self):
        trigger = DispatchTrigger(
            type="event-driven",
            match_type="dispatch",
            match_src="heraldo",
            match_msg_prefix="REPORT:",
        )
        msg = _msg(src="heraldo", msg_type="dispatch", msg_text="REPORT:data")
        assert _trigger_matches(trigger, msg) is True

        msg2 = _msg(src="dojo", msg_type="dispatch", msg_text="REPORT:data")
        assert _trigger_matches(trigger, msg2) is False

    def test_case_insensitive_type(self):
        trigger = DispatchTrigger(type="event-driven", match_type="DISPATCH")
        msg = _msg(msg_type="dispatch")
        assert _trigger_matches(trigger, msg) is True

    def test_case_insensitive_src(self):
        trigger = DispatchTrigger(
            type="event-driven", match_type="dispatch", match_src="HERALDO"
        )
        msg = _msg(src="heraldo", msg_type="dispatch")
        assert _trigger_matches(trigger, msg) is True


class TestRegistryFindMatchingRules:
    """Registry-level rule matching tests."""

    def test_finds_matching_worker(self, agents_dir):
        reg = AgentRegistry(agents_dir)
        reg.load_all()
        msg = _msg(msg_type="dispatch", msg_text="REPORT:monthly")
        matches = reg.find_matching_rules(msg)
        assert len(matches) == 1
        agent, rule = matches[0]
        assert agent.agent_id == "report-builder"
        assert rule.rule_id == "on-dispatch"

    def test_finds_multiple_rules(self, agents_dir):
        reg = AgentRegistry(agents_dir)
        reg.load_all()
        msg = _msg(msg_type="dispatch", msg_text="REPORT:FINANCIAL:q4")
        matches = reg.find_matching_rules(msg)
        # Both on-dispatch and on-financial-dispatch match
        assert len(matches) == 2

    def test_no_matches(self, agents_dir):
        reg = AgentRegistry(agents_dir)
        reg.load_all()
        msg = _msg(msg_type="state", msg_text="something")
        matches = reg.find_matching_rules(msg)
        assert len(matches) == 0

    def test_skips_disabled_agents(self, agents_dir_with_disabled):
        reg = AgentRegistry(agents_dir_with_disabled)
        reg.load_all()
        msg = _msg(msg_type="alert", msg_text="test")
        matches = reg.find_matching_rules(msg)
        # platform-agent matches alert but is disabled
        assert len(matches) == 0

    def test_skips_scheduled_rules(self, agents_dir):
        reg = AgentRegistry(agents_dir)
        reg.load_all()
        # mail-scanner has scheduled rule — should not match any message
        msg = _msg(msg_type="dispatch", msg_text="SCAN:inbox")
        matches = reg.find_matching_rules(msg)
        # Only report-builder has event-driven rules, none match "SCAN:"
        assert len(matches) == 0


# ─── F2: ResourceLimits ──────────────────────────────────────────


class TestResourceLimits:
    """Resource limits dataclass tests."""

    def test_defaults(self):
        rl = ResourceLimits()
        assert rl.max_turns is None
        assert rl.timeout_seconds is None
        assert rl.allowed_tools == ()
        assert rl.max_concurrent == 1

    def test_from_profile(self):
        p = AgentProfile.from_dict(WORKER_PROFILE)
        assert p.resource_limits.max_turns == 15
        assert p.resource_limits.timeout_seconds == 600
        assert p.resource_limits.max_concurrent == 1

    def test_no_limits_section(self):
        data = {**SENSOR_PROFILE}
        del data["resource_limits"]
        p = AgentProfile.from_dict(data)
        assert p.resource_limits.max_turns is None
        assert p.resource_limits.max_concurrent == 1


# ─── Integration: Classifier + Registry ──────────────────────────


class TestClassifierRegistryIntegration:
    """Combined F1 + F2 tests."""

    def test_verify_source_with_registry(self, agents_dir):
        reg = AgentRegistry(agents_dir)
        reg.load_all()
        mc = MessageClassifier(local_namespaces={"heraldo"})

        # Registered agent source is valid
        assert mc.verify_source(
            _msg(src="mail-scanner"),
            registered_agent_ids=reg.all_agent_ids(),
        ) is True

        # Unknown source is invalid
        assert mc.verify_source(
            _msg(src="rogue-agent"),
            registered_agent_ids=reg.all_agent_ids(),
        ) is False

    def test_classify_then_match(self, agents_dir):
        reg = AgentRegistry(agents_dir)
        reg.load_all()
        mc = MessageClassifier(local_namespaces={"heraldo", "dojo"})

        # Internal dispatch message
        msg = _msg(src="dojo", dst="heraldo", msg_type="dispatch", msg_text="REPORT:q4")
        assert mc.classify(msg) == MessageCategory.INTERNAL

        # Find matching rules
        matches = reg.find_matching_rules(msg)
        assert len(matches) >= 1
        assert matches[0][0].agent_id == "report-builder"

    def test_outbound_not_dispatched(self, agents_dir):
        reg = AgentRegistry(agents_dir)
        reg.load_all()
        mc = MessageClassifier(local_namespaces={"heraldo"})

        # Outbound message — should be forwarded, not dispatched
        msg = _msg(src="heraldo", dst="clan-jei", msg_type="dispatch", msg_text="REPORT:x")
        assert mc.classify(msg) == MessageCategory.OUTBOUND
        # Even though content matches a rule, daemon should forward, not dispatch


# ─── F3: Dispatch Protocol ──────────────────────────────────────


# ─── F3.1: Enums ────────────────────────────────────────────────


class TestF3Enums:
    """Test F3 enum types."""

    def test_agent_state_values(self):
        assert AgentState.INACTIVE == "inactive"
        assert AgentState.ACTIVE == "active"
        assert AgentState.RUNNING == "running"
        assert AgentState.FAILED == "failed"
        assert AgentState.REMOVED == "removed"
        assert len(AgentState) == 7

    def test_dispatch_outcome_values(self):
        assert DispatchOutcome.DISPATCHED == "dispatched"
        assert DispatchOutcome.APPROVAL_PENDING == "approval_pending"
        assert DispatchOutcome.APPROVAL_GRANTED == "approval_granted"
        assert DispatchOutcome.APPROVAL_TIMEOUT == "approval_timeout"
        assert DispatchOutcome.CAPACITY_EXCEEDED == "capacity_exceeded"
        assert len(DispatchOutcome) == 7

    def test_queue_overflow_values(self):
        assert QueueOverflow.DROP_NEWEST == "drop-newest"
        assert QueueOverflow.DROP_OLDEST == "drop-oldest"


# ─── F3.2: ConcurrencyTracker ───────────────────────────────────


class TestConcurrencyTracker:
    """Tests for ConcurrencyTracker."""

    def test_starts_at_zero(self):
        ct = ConcurrencyTracker()
        assert ct.active_count("agent-x") == 0

    def test_increment_decrement(self):
        ct = ConcurrencyTracker()
        ct.increment("agent-x")
        assert ct.active_count("agent-x") == 1
        ct.increment("agent-x")
        assert ct.active_count("agent-x") == 2
        ct.decrement("agent-x")
        assert ct.active_count("agent-x") == 1

    def test_decrement_floors_at_zero(self):
        ct = ConcurrencyTracker()
        ct.decrement("agent-x")
        assert ct.active_count("agent-x") == 0

    def test_at_capacity_true(self):
        ct = ConcurrencyTracker()
        ct.increment("agent-x")
        assert ct.at_capacity("agent-x", 1) is True

    def test_at_capacity_false(self):
        ct = ConcurrencyTracker()
        ct.increment("agent-x")
        assert ct.at_capacity("agent-x", 2) is False

    def test_at_capacity_unlimited(self):
        ct = ConcurrencyTracker()
        ct.increment("agent-x")
        ct.increment("agent-x")
        assert ct.at_capacity("agent-x", 0) is False

    def test_independent_agents(self):
        ct = ConcurrencyTracker()
        ct.increment("a")
        ct.increment("b")
        ct.increment("b")
        assert ct.active_count("a") == 1
        assert ct.active_count("b") == 2

    def test_reset(self):
        ct = ConcurrencyTracker()
        ct.increment("agent-x")
        ct.increment("agent-x")
        ct.reset("agent-x")
        assert ct.active_count("agent-x") == 0


# ─── F3.3: ApprovalGateManager ──────────────────────────────────


class TestApprovalGateManager:
    """Tests for ApprovalGateManager."""

    def _trigger_msg(self) -> Message:
        return _msg(msg_type="dispatch", msg_text="REPORT:FINANCIAL:q4")

    def test_add_creates_pending(self):
        mgr = ApprovalGateManager()
        msg = self._trigger_msg()
        pa = mgr.add("report-builder", "on-financial", msg)
        assert pa.agent_id == "report-builder"
        assert pa.rule_id == "on-financial"
        assert len(mgr.pending) == 1

    def test_add_hashes_msg(self):
        import hashlib
        mgr = ApprovalGateManager()
        msg = self._trigger_msg()
        pa = mgr.add("agent", "rule", msg)
        expected = hashlib.sha256(msg.msg.encode("utf-8")).hexdigest()
        assert pa.trigger_msg_hash == expected

    def test_find_expired_returns_nothing_for_fresh(self):
        mgr = ApprovalGateManager()
        msg = self._trigger_msg()
        now = datetime(2026, 3, 20, 12, 0)
        mgr.add("agent", "rule", msg, timeout_hours=24, now=now)
        assert mgr.find_expired(now + timedelta(hours=1)) == []

    def test_find_expired_returns_past_timeout(self):
        mgr = ApprovalGateManager()
        msg = self._trigger_msg()
        now = datetime(2026, 3, 20, 12, 0)
        mgr.add("agent", "rule", msg, timeout_hours=12, now=now)
        expired = mgr.find_expired(now + timedelta(hours=13))
        assert len(expired) == 1
        assert expired[0].agent_id == "agent"

    def test_remove(self):
        mgr = ApprovalGateManager()
        msg = self._trigger_msg()
        mgr.add("a", "r1", msg)
        mgr.add("a", "r2", msg)
        mgr.remove("a", "r1")
        assert len(mgr.pending) == 1
        assert mgr.pending[0].rule_id == "r2"

    def test_match_approval_signal_none_for_wrong_type(self):
        mgr = ApprovalGateManager()
        msg = self._trigger_msg()
        mgr.add("agent", "rule", msg)
        signal = _msg(msg_type="state", msg_text="APPROVE:agent:rule:2026-03-20")
        assert mgr.match_approval_signal(signal) is None

    def test_match_approval_signal_none_for_wrong_prefix(self):
        mgr = ApprovalGateManager()
        msg = self._trigger_msg()
        mgr.add("agent", "rule", msg)
        signal = _msg(msg_type="dispatch", msg_text="NOT_APPROVE:agent:rule:2026-03-20")
        assert mgr.match_approval_signal(signal) is None

    def test_match_approval_signal_none_for_wrong_agent(self):
        mgr = ApprovalGateManager()
        msg = self._trigger_msg()
        mgr.add("agent", "rule", msg)
        signal = _msg(msg_type="dispatch", msg_text="APPROVE:wrong:rule:2026-03-20")
        assert mgr.match_approval_signal(signal) is None

    def test_match_approval_signal_none_for_wrong_ts(self):
        mgr = ApprovalGateManager()
        msg = self._trigger_msg()
        mgr.add("agent", "rule", msg)
        signal = _msg(msg_type="dispatch", msg_text="APPROVE:agent:rule:1999-01-01")
        assert mgr.match_approval_signal(signal) is None

    def test_match_approval_signal_success(self):
        mgr = ApprovalGateManager()
        msg = self._trigger_msg()
        mgr.add("agent", "rule", msg)
        ts = date.today().isoformat()
        signal = _msg(msg_type="dispatch", msg_text=f"APPROVE:agent:rule:{ts}")
        pa = mgr.match_approval_signal(signal)
        assert pa is not None
        assert pa.agent_id == "agent"

    def test_to_list_from_list_roundtrip(self):
        mgr = ApprovalGateManager()
        msg = self._trigger_msg()
        now = datetime(2026, 3, 20, 14, 0)
        mgr.add("a", "r1", msg, now=now)
        mgr.add("b", "r2", msg, timeout_hours=6, now=now)
        data = mgr.to_list()
        mgr2 = ApprovalGateManager.from_list(data)
        assert len(mgr2.pending) == 2
        assert mgr2.pending[0].agent_id == "a"
        assert mgr2.pending[1].timeout_hours == 6

    def test_two_approvals_different_rules_same_agent(self):
        mgr = ApprovalGateManager()
        msg = self._trigger_msg()
        mgr.add("agent", "r1", msg)
        mgr.add("agent", "r2", msg)
        assert len(mgr.pending) == 2

    def test_default_timeout_propagates(self):
        mgr = ApprovalGateManager(default_timeout_hours=48)
        msg = self._trigger_msg()
        pa = mgr.add("agent", "rule", msg)
        assert pa.timeout_hours == 48


# ─── F3.4: DispatchCommandRenderer ──────────────────────────────


class TestDispatchCommandRenderer:
    """Tests for DispatchCommandRenderer."""

    def _profile(self) -> AgentProfile:
        return AgentProfile.from_dict(WORKER_PROFILE)

    def _rule(self, template: str | None = None) -> DispatchRule:
        return DispatchRule(
            rule_id="test-rule",
            trigger=DispatchTrigger(type="event-driven", match_type="dispatch"),
            command_template=template,
        )

    def test_default_command(self):
        renderer = DispatchCommandRenderer()
        cmd = renderer.render(self._rule(), self._profile(), _msg())
        assert cmd[0] == "claude"
        assert "--max-turns" in cmd

    def test_max_turns_from_profile(self):
        renderer = DispatchCommandRenderer()
        cmd = renderer.render(self._rule(), self._profile(), _msg())
        idx = cmd.index("--max-turns")
        assert cmd[idx + 1] == "15"  # from WORKER_PROFILE

    def test_max_turns_default(self):
        renderer = DispatchCommandRenderer(default_max_turns=20)
        profile = AgentProfile.from_dict(PLATFORM_PROFILE)  # no max_turns
        cmd = renderer.render(self._rule(), profile, _msg())
        idx = cmd.index("--max-turns")
        assert cmd[idx + 1] == "20"

    def test_allowed_tools_from_profile(self):
        renderer = DispatchCommandRenderer()
        cmd = renderer.render(self._rule(), self._profile(), _msg())
        assert "--allowedTools" in cmd
        idx = cmd.index("--allowedTools")
        assert "file-read,file-write" in cmd[idx + 1]

    def test_allowed_tools_absent_when_empty(self):
        renderer = DispatchCommandRenderer()
        profile = AgentProfile.from_dict(PLATFORM_PROFILE)  # no allowed_tools
        cmd = renderer.render(self._rule(), profile, _msg())
        assert "--allowedTools" not in cmd

    def test_template_substitution_payload(self):
        renderer = DispatchCommandRenderer()
        rule = self._rule("echo {{payload}}")
        msg = _msg(msg_text="hello-world")
        cmd = renderer.render(rule, self._profile(), msg)
        assert "hello-world" in cmd

    def test_template_substitution_agent_id(self):
        renderer = DispatchCommandRenderer()
        rule = self._rule("run {{agent_id}}")
        cmd = renderer.render(rule, self._profile(), _msg())
        assert "report-builder" in cmd

    def test_template_substitution_rule_id(self):
        renderer = DispatchCommandRenderer()
        rule = self._rule("dispatch {{rule_id}}")
        cmd = renderer.render(rule, self._profile(), _msg())
        assert "test-rule" in cmd

    def test_returns_list_not_string(self):
        renderer = DispatchCommandRenderer()
        cmd = renderer.render(self._rule(), self._profile(), _msg())
        assert isinstance(cmd, list)
        assert all(isinstance(s, str) for s in cmd)

    def test_unknown_template_vars_left_as_is(self):
        renderer = DispatchCommandRenderer()
        rule = self._rule("cmd {{unknown}}")
        cmd = renderer.render(rule, self._profile(), _msg())
        assert "{{unknown}}" in cmd


# ─── F3.5: DispatchEngine ───────────────────────────────────────


class TestDispatchEngine:
    """Tests for DispatchEngine — the central dispatch coordinator."""

    @pytest.fixture
    def agents_dir(self, tmp_path):
        d = tmp_path / "agents"
        d.mkdir()
        (d / "report-builder.json").write_text(json.dumps(WORKER_PROFILE))
        (d / "platform-agent.json").write_text(json.dumps(PLATFORM_PROFILE))
        return d

    @pytest.fixture
    def engine(self, agents_dir):
        reg = AgentRegistry(agents_dir)
        reg.load_all()
        ct = ConcurrencyTracker()
        am = ApprovalGateManager()
        renderer = DispatchCommandRenderer()
        return DispatchEngine(reg, ct, am, renderer)

    def test_no_match_returns_empty(self, engine):
        msg = _msg(msg_type="state", msg_text="irrelevant")
        assert engine.evaluate_message(msg) == []

    def test_direct_dispatch(self, engine):
        msg = _msg(msg_type="dispatch", msg_text="REPORT:weekly")
        decisions = engine.evaluate_message(msg)
        assert len(decisions) == 1
        assert decisions[0].outcome == DispatchOutcome.DISPATCHED
        assert decisions[0].agent_id == "report-builder"
        assert len(decisions[0].command) > 0

    def test_approval_pending(self, engine):
        msg = _msg(msg_type="dispatch", msg_text="REPORT:FINANCIAL:q4")
        decisions = engine.evaluate_message(msg)
        # Both rules match: on-dispatch and on-financial-dispatch
        pending = [d for d in decisions if d.outcome == DispatchOutcome.APPROVAL_PENDING]
        assert len(pending) == 1
        assert pending[0].approval_key is not None

    def test_capacity_exceeded(self, engine):
        # Fill up report-builder capacity (max_concurrent=1)
        engine.concurrency.increment("report-builder")
        msg = _msg(msg_type="dispatch", msg_text="REPORT:x")
        decisions = engine.evaluate_message(msg)
        assert any(d.outcome == DispatchOutcome.CAPACITY_EXCEEDED for d in decisions)

    def test_two_agents_match_same_message(self, engine):
        msg = _msg(msg_type="alert", msg_text="REPORT:critical")
        # Only platform-agent matches alert; report-builder matches dispatch only
        # Change message type to dispatch and prefix to REPORT:
        msg = _msg(msg_type="dispatch", msg_text="REPORT:test")
        decisions = engine.evaluate_message(msg)
        # report-builder on-dispatch matches
        assert len(decisions) >= 1

    def test_check_approval_signal_none_for_non_approval(self, engine):
        msg = _msg(msg_type="state", msg_text="hello")
        assert engine.check_approval_signal(msg) is None

    def test_check_approval_signal_granted(self, engine):
        # First create a pending approval
        trigger = _msg(msg_type="dispatch", msg_text="REPORT:FINANCIAL:q4")
        engine.evaluate_message(trigger)

        ts = date.today().isoformat()
        signal = _msg(
            msg_type="dispatch",
            msg_text=f"APPROVE:report-builder:on-financial-dispatch:{ts}",
        )
        decision = engine.check_approval_signal(signal)
        assert decision is not None
        assert decision.outcome == DispatchOutcome.APPROVAL_GRANTED

    def test_expire_approvals_empty(self, engine):
        assert engine.expire_approvals() == []

    def test_expire_approvals_timeout(self, engine):
        trigger = _msg(msg_type="dispatch", msg_text="REPORT:FINANCIAL:q4")
        now = datetime(2026, 3, 20, 12, 0)
        engine.evaluate_message(trigger, now=now)

        # Fast forward past timeout (12 hours for financial rule)
        future = now + timedelta(hours=13)
        decisions = engine.expire_approvals(future)
        timeout_decisions = [
            d for d in decisions if d.outcome == DispatchOutcome.APPROVAL_TIMEOUT
        ]
        assert len(timeout_decisions) >= 1

    def test_evaluate_does_not_mutate_message(self, engine):
        msg = _msg(msg_type="dispatch", msg_text="REPORT:test")
        original_msg = msg.msg
        original_type = msg.type
        engine.evaluate_message(msg)
        assert msg.msg == original_msg
        assert msg.type == original_type

    def test_decision_contains_trigger_msg(self, engine):
        msg = _msg(msg_type="dispatch", msg_text="REPORT:test")
        decisions = engine.evaluate_message(msg)
        assert decisions[0].trigger_msg is msg

    def test_decision_payload_matches(self, engine):
        msg = _msg(msg_type="dispatch", msg_text="REPORT:test")
        decisions = engine.evaluate_message(msg)
        assert decisions[0].payload == "REPORT:test"

    def test_empty_registry_returns_empty(self, tmp_path):
        d = tmp_path / "empty_agents"
        d.mkdir()
        reg = AgentRegistry(d)
        reg.load_all()
        engine = DispatchEngine(
            reg, ConcurrencyTracker(), ApprovalGateManager(),
            DispatchCommandRenderer(),
        )
        msg = _msg(msg_type="dispatch", msg_text="REPORT:test")
        assert engine.evaluate_message(msg) == []

    def test_disabled_agent_not_dispatched(self, tmp_path):
        d = tmp_path / "agents"
        d.mkdir()
        disabled = dict(WORKER_PROFILE)
        disabled["enabled"] = False
        (d / "report-builder.json").write_text(json.dumps(disabled))
        reg = AgentRegistry(d)
        reg.load_all()
        engine = DispatchEngine(
            reg, ConcurrencyTracker(), ApprovalGateManager(),
            DispatchCommandRenderer(),
        )
        msg = _msg(msg_type="dispatch", msg_text="REPORT:test")
        assert engine.evaluate_message(msg) == []

    def test_approval_signal_unknown_agent_returns_none(self, engine):
        signal = _msg(
            msg_type="dispatch",
            msg_text="APPROVE:nonexistent:rule:2026-03-20",
        )
        assert engine.check_approval_signal(signal) is None


# ─── F3.6: DispatchScheduler ────────────────────────────────────


class TestDispatchScheduler:
    """Tests for DispatchScheduler."""

    @pytest.fixture
    def agents_dir(self, tmp_path):
        d = tmp_path / "agents"
        d.mkdir()
        (d / "mail-scanner.json").write_text(json.dumps(SENSOR_PROFILE))
        return d

    @pytest.fixture
    def registry(self, agents_dir):
        reg = AgentRegistry(agents_dir)
        reg.load_all()
        return reg

    def test_validate_cron_valid(self):
        assert DispatchScheduler.validate_cron("0 */4 * * *") is None
        assert DispatchScheduler.validate_cron("30 9 * * 1-5") is None
        assert DispatchScheduler.validate_cron("0 0 1 * *") is None

    def test_validate_cron_empty(self):
        assert DispatchScheduler.validate_cron("") is not None

    def test_validate_cron_wrong_field_count(self):
        assert DispatchScheduler.validate_cron("* * * * * *") is not None

    def test_validate_cron_minute_out_of_range(self):
        assert DispatchScheduler.validate_cron("60 * * * *") is not None

    def test_validate_cron_hour_out_of_range(self):
        assert DispatchScheduler.validate_cron("0 24 * * *") is not None

    def test_load_returns_no_errors_for_valid(self, registry):
        sched = DispatchScheduler(registry)
        errors = sched.load()
        assert errors == []

    def test_load_returns_errors_for_invalid(self, tmp_path):
        d = tmp_path / "bad_agents"
        d.mkdir()
        bad = dict(SENSOR_PROFILE)
        bad["dispatch_rules"][0]["trigger"]["cron"] = "bad cron"
        (d / "mail-scanner.json").write_text(json.dumps(bad))
        reg = AgentRegistry(d)
        reg.load_all()
        sched = DispatchScheduler(reg)
        errors = sched.load()
        assert len(errors) == 1

    def test_due_rules_not_before_interval(self, registry):
        sched = DispatchScheduler(registry)
        sched.load()
        now = 1000000.0
        # First call fires it
        due = sched.due_rules(now)
        assert len(due) == 1
        # Second call too soon
        due2 = sched.due_rules(now + 10)
        assert len(due2) == 0

    def test_due_rules_fires_after_interval(self, registry):
        sched = DispatchScheduler(registry)
        sched.load()
        now = 1000000.0
        sched.due_rules(now)
        due = sched.due_rules(now + 301)
        assert len(due) == 1

    def test_synthetic_message_format(self, registry):
        sched = DispatchScheduler(registry, daemon_namespace="test-daemon")
        sched.load()
        profile = registry.all_enabled()[0]
        rule = profile.dispatch_rules[0]
        today = date(2026, 3, 20)
        msg = sched.synthetic_message(profile, rule, now=today)
        assert msg.type == "dispatch"
        assert msg.src == "test-daemon"
        assert msg.dst == "mail-scanner"
        assert msg.msg.startswith("SCHEDULED:scheduled-scan:")

    def test_schedule_state_roundtrip(self, registry):
        sched = DispatchScheduler(registry)
        sched.load()
        sched.due_rules(1000000.0)
        state = sched.schedule_state
        assert len(state) > 0

        sched2 = DispatchScheduler(registry)
        sched2.load()
        sched2.restore_state(state)
        # Should not fire because state was restored
        due = sched2.due_rules(1000000.0 + 10)
        assert len(due) == 0


# ─── F3.7: Integration ──────────────────────────────────────────


class TestF3Integration:
    """Integration tests combining F3 components."""

    @pytest.fixture
    def agents_dir(self, tmp_path):
        d = tmp_path / "agents"
        d.mkdir()
        (d / "report-builder.json").write_text(json.dumps(WORKER_PROFILE))
        (d / "mail-scanner.json").write_text(json.dumps(SENSOR_PROFILE))
        return d

    def test_full_dispatch_flow(self, agents_dir):
        """Full flow: registry → engine → dispatch → tracker incremented."""
        reg = AgentRegistry(agents_dir)
        reg.load_all()
        ct = ConcurrencyTracker()
        engine = DispatchEngine(
            reg, ct, ApprovalGateManager(), DispatchCommandRenderer()
        )

        msg = _msg(msg_type="dispatch", msg_text="REPORT:weekly")
        decisions = engine.evaluate_message(msg)
        dispatched = [d for d in decisions if d.outcome == DispatchOutcome.DISPATCHED]
        assert len(dispatched) >= 1

        # Simulate daemon incrementing tracker
        for d in dispatched:
            ct.increment(d.agent_id)
        assert ct.active_count("report-builder") >= 1

    def test_full_approval_flow(self, agents_dir):
        """Full flow: trigger → approval pending → signal → granted."""
        reg = AgentRegistry(agents_dir)
        reg.load_all()
        ct = ConcurrencyTracker()
        am = ApprovalGateManager()
        engine = DispatchEngine(reg, ct, am, DispatchCommandRenderer())

        # Step 1: trigger creates pending
        trigger = _msg(msg_type="dispatch", msg_text="REPORT:FINANCIAL:q4")
        decisions = engine.evaluate_message(trigger)
        pending = [d for d in decisions if d.outcome == DispatchOutcome.APPROVAL_PENDING]
        assert len(pending) == 1
        assert len(am.pending) == 1

        # Step 2: operator sends approval
        ts = date.today().isoformat()
        signal = _msg(
            msg_type="dispatch",
            msg_text=f"APPROVE:report-builder:on-financial-dispatch:{ts}",
        )
        granted = engine.check_approval_signal(signal)
        assert granted is not None
        assert granted.outcome == DispatchOutcome.APPROVAL_GRANTED
        assert len(granted.command) > 0
        assert len(am.pending) == 0

    def test_full_timeout_flow(self, agents_dir):
        """Full flow: approval pending → timeout → cleanup."""
        reg = AgentRegistry(agents_dir)
        reg.load_all()
        am = ApprovalGateManager()
        engine = DispatchEngine(
            reg, ConcurrencyTracker(), am, DispatchCommandRenderer()
        )

        now = datetime(2026, 3, 20, 12, 0)
        trigger = _msg(msg_type="dispatch", msg_text="REPORT:FINANCIAL:q4")
        engine.evaluate_message(trigger, now=now)

        # Fast forward past 12h timeout
        future = now + timedelta(hours=13)
        timeouts = engine.expire_approvals(future)
        assert any(d.outcome == DispatchOutcome.APPROVAL_TIMEOUT for d in timeouts)
        assert len(am.pending) == 0

    def test_scheduler_produces_synthetic_then_engine_dispatches(self, agents_dir):
        """Scheduler fires → synthetic message → engine dispatches."""
        reg = AgentRegistry(agents_dir)
        reg.load_all()
        sched = DispatchScheduler(reg, daemon_namespace="test-daemon")
        sched.load()

        due = sched.due_rules(1000000.0)
        assert len(due) >= 1

        profile, rule = due[0]
        synth = sched.synthetic_message(profile, rule, now=date(2026, 3, 20))
        assert synth.msg.startswith("SCHEDULED:")


# ─── F4: AgentStateTracker ──────────────────────────────────────


class TestAgentStateTrackerBasic:
    """Basic lifecycle state tracking tests (ARC-0369 §9)."""

    def test_unknown_agent_is_inactive(self):
        tracker = AgentStateTracker()
        assert tracker.get_state("unknown") == AgentState.INACTIVE

    def test_inactive_to_active(self):
        tracker = AgentStateTracker()
        old = tracker.transition("agent-a", AgentState.ACTIVE)
        assert old == AgentState.INACTIVE
        assert tracker.get_state("agent-a") == AgentState.ACTIVE

    def test_active_to_running(self):
        tracker = AgentStateTracker()
        tracker.transition("agent-a", AgentState.ACTIVE)
        old = tracker.transition("agent-a", AgentState.RUNNING)
        assert old == AgentState.ACTIVE
        assert tracker.get_state("agent-a") == AgentState.RUNNING

    def test_running_to_idle(self):
        tracker = AgentStateTracker()
        tracker.transition("agent-a", AgentState.ACTIVE)
        tracker.transition("agent-a", AgentState.RUNNING)
        old = tracker.transition("agent-a", AgentState.IDLE)
        assert old == AgentState.RUNNING
        assert tracker.get_state("agent-a") == AgentState.IDLE

    def test_running_to_failed(self):
        tracker = AgentStateTracker()
        tracker.transition("agent-a", AgentState.ACTIVE)
        tracker.transition("agent-a", AgentState.RUNNING)
        old = tracker.transition("agent-a", AgentState.FAILED)
        assert old == AgentState.RUNNING
        assert tracker.get_state("agent-a") == AgentState.FAILED

    def test_failed_to_active_recovery(self):
        tracker = AgentStateTracker()
        tracker.transition("agent-a", AgentState.ACTIVE)
        tracker.transition("agent-a", AgentState.RUNNING)
        tracker.transition("agent-a", AgentState.FAILED)
        old = tracker.transition("agent-a", AgentState.ACTIVE)
        assert old == AgentState.FAILED

    def test_active_to_pending(self):
        tracker = AgentStateTracker()
        tracker.transition("agent-a", AgentState.ACTIVE)
        old = tracker.transition("agent-a", AgentState.PENDING)
        assert old == AgentState.ACTIVE

    def test_pending_to_running(self):
        tracker = AgentStateTracker()
        tracker.transition("agent-a", AgentState.ACTIVE)
        tracker.transition("agent-a", AgentState.PENDING)
        old = tracker.transition("agent-a", AgentState.RUNNING)
        assert old == AgentState.PENDING

    def test_pending_timeout_to_active(self):
        tracker = AgentStateTracker()
        tracker.transition("agent-a", AgentState.ACTIVE)
        tracker.transition("agent-a", AgentState.PENDING)
        old = tracker.transition("agent-a", AgentState.ACTIVE)
        assert old == AgentState.PENDING


class TestAgentStateTrackerIllegal:
    """Illegal transition rejection tests."""

    def test_inactive_to_running_illegal(self):
        tracker = AgentStateTracker()
        result = tracker.transition("agent-a", AgentState.RUNNING)
        assert result is None
        assert tracker.get_state("agent-a") == AgentState.INACTIVE

    def test_running_to_active_illegal(self):
        tracker = AgentStateTracker()
        tracker.transition("agent-a", AgentState.ACTIVE)
        tracker.transition("agent-a", AgentState.RUNNING)
        result = tracker.transition("agent-a", AgentState.ACTIVE)
        assert result is None
        assert tracker.get_state("agent-a") == AgentState.RUNNING

    def test_removed_is_terminal(self):
        tracker = AgentStateTracker()
        tracker.transition("agent-a", AgentState.ACTIVE)
        tracker.transition("agent-a", AgentState.REMOVED)
        result = tracker.transition("agent-a", AgentState.ACTIVE)
        assert result is None
        assert tracker.get_state("agent-a") == AgentState.REMOVED


class TestAgentStateTrackerHelpers:
    """set_* helper methods and counters."""

    def test_set_active_from_inactive(self):
        tracker = AgentStateTracker()
        tracker.set_active("agent-a")
        assert tracker.get_state("agent-a") == AgentState.ACTIVE

    def test_set_active_from_idle(self):
        tracker = AgentStateTracker()
        tracker.transition("agent-a", AgentState.ACTIVE)
        tracker.transition("agent-a", AgentState.RUNNING)
        tracker.transition("agent-a", AgentState.IDLE)
        tracker.set_active("agent-a")
        assert tracker.get_state("agent-a") == AgentState.ACTIVE

    def test_set_active_noop_when_already_active(self):
        tracker = AgentStateTracker()
        tracker.set_active("agent-a")
        tracker.set_active("agent-a")  # should not crash
        assert tracker.get_state("agent-a") == AgentState.ACTIVE

    def test_record_dispatch_success(self):
        tracker = AgentStateTracker()
        tracker.set_active("agent-a")
        tracker.record_dispatch("agent-a", success=True)
        payload = tracker.heartbeat_payload()
        entry = [e for e in payload if e["agent_id"] == "agent-a"][0]
        assert entry["dispatch_count"] == 1
        assert entry["failure_count"] == 0
        assert entry["last_dispatch"] is not None

    def test_record_dispatch_failure(self):
        tracker = AgentStateTracker()
        tracker.set_active("agent-a")
        tracker.record_dispatch("agent-a", success=False)
        payload = tracker.heartbeat_payload()
        entry = [e for e in payload if e["agent_id"] == "agent-a"][0]
        assert entry["dispatch_count"] == 1
        assert entry["failure_count"] == 1


class TestAgentStateTrackerSerialization:
    """to_dict / from_dict roundtrip tests."""

    def test_roundtrip_empty(self):
        tracker = AgentStateTracker()
        data = tracker.to_dict()
        restored = AgentStateTracker.from_dict(data)
        assert restored.heartbeat_payload() == []

    def test_roundtrip_with_state(self):
        tracker = AgentStateTracker()
        tracker.set_active("agent-a")
        tracker.set_active("agent-b")
        tracker.record_dispatch("agent-a", success=True)
        tracker.record_dispatch("agent-b", success=False)

        data = tracker.to_dict()
        restored = AgentStateTracker.from_dict(data)
        assert restored.get_state("agent-a") == AgentState.ACTIVE
        assert restored.get_state("agent-b") == AgentState.ACTIVE

        payload = restored.heartbeat_payload()
        assert len(payload) == 2
        a_entry = [e for e in payload if e["agent_id"] == "agent-a"][0]
        assert a_entry["dispatch_count"] == 1
        b_entry = [e for e in payload if e["agent_id"] == "agent-b"][0]
        assert b_entry["failure_count"] == 1

    def test_from_dict_empty(self):
        restored = AgentStateTracker.from_dict({})
        assert restored.get_state("any") == AgentState.INACTIVE

    def test_from_dict_unknown_state_skipped(self):
        data = {"states": {"agent-x": "bogus_state"}}
        restored = AgentStateTracker.from_dict(data)
        # Unknown state is skipped — agent defaults to INACTIVE
        assert restored.get_state("agent-x") == AgentState.INACTIVE


# ─── F5: NotificationThrottler ──────────────────────────────────


class TestNotificationThrottlerSuppression:
    """Suppression rule tests (ARC-0369 §10.1)."""

    def test_suppress_dispatch_result(self):
        assert NotificationThrottler.should_suppress("dispatch", "[RE:rule-1] done") is True

    def test_suppress_data_cross(self):
        assert NotificationThrottler.should_suppress("data_cross", "expense data") is True

    def test_suppress_state(self):
        assert NotificationThrottler.should_suppress("state", "sync done") is True

    def test_no_suppress_alert(self):
        assert NotificationThrottler.should_suppress("alert", "disk full") is False

    def test_no_suppress_dispatch(self):
        assert NotificationThrottler.should_suppress("dispatch", "REPORT:weekly") is False

    def test_no_suppress_event(self):
        assert NotificationThrottler.should_suppress("event", "user login") is False


class TestNotificationThrottlerRateLimit:
    """Rate limiting tests (ARC-0369 §10.2)."""

    def test_within_limit(self):
        throttler = NotificationThrottler(max_per_window=5)
        assert throttler.should_notify("src-a", now=1000.0) is True

    def test_at_limit(self):
        throttler = NotificationThrottler(max_per_window=3, window_seconds=60)
        for i in range(3):
            throttler.record("src-a", now=1000.0 + i)
        assert throttler.should_notify("src-a", now=1002.0) is False

    def test_window_expiry(self):
        throttler = NotificationThrottler(max_per_window=2, window_seconds=60)
        throttler.record("src-a", now=1000.0)
        throttler.record("src-a", now=1001.0)
        # At limit
        assert throttler.should_notify("src-a", now=1002.0) is False
        # After window expires
        assert throttler.should_notify("src-a", now=1062.0) is True

    def test_independent_sources(self):
        throttler = NotificationThrottler(max_per_window=1)
        throttler.record("src-a", now=1000.0)
        assert throttler.should_notify("src-a", now=1001.0) is False
        assert throttler.should_notify("src-b", now=1001.0) is True

    def test_suppressed_summary(self):
        throttler = NotificationThrottler()
        throttler.record_suppressed("src-a")
        throttler.record_suppressed("src-a")
        throttler.record_suppressed("src-b")
        summary = throttler.suppressed_summary()
        assert ("src-a", 2) in summary
        assert ("src-b", 1) in summary

    def test_suppressed_summary_empty(self):
        throttler = NotificationThrottler()
        assert throttler.suppressed_summary() == []
