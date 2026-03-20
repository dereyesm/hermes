"""Tests for HERMES Agent Service Platform — ARC-0369 F1 + F2."""

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from hermes.asp import (
    AgentProfile,
    AgentProfileError,
    AgentRegistry,
    DispatchRule,
    DispatchTrigger,
    MessageCategory,
    MessageClassifier,
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
