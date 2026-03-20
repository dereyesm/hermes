"""Tests for HERMES Adapter — Agent-agnostic bridge (installable-model.md Phase 2)."""

import json
from pathlib import Path

import pytest

from hermes.adapter import (
    ADAPTERS,
    AdaptResult,
    AdapterBase,
    ClaudeCodeAdapter,
    _safe_symlink,
    _write_file_if_changed,
    get_adapter,
    list_adapters,
    run_adapter,
)
from hermes.config import GatewayConfig, PeerConfig, init_clan, save_config_toml


# ─── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def hermes_dir(tmp_path):
    """Create a minimal ~/.hermes/ structure with TOML config."""
    hdir = tmp_path / ".hermes"
    init_clan(hdir, "clan-test", "Test Clan", config_format="toml")
    return hdir


@pytest.fixture
def hermes_dir_with_dims(hermes_dir):
    """Add dimension structure to hermes_dir."""
    dims = hermes_dir / "dimensions"

    # global dimension with skills
    global_skills = dims / "global" / "skills" / "consejo"
    global_skills.mkdir(parents=True)
    (global_skills / "SKILL.md").write_text("# Consejo Skill\n")

    global_skills2 = dims / "global" / "skills" / "palas"
    global_skills2.mkdir(parents=True)
    (global_skills2 / "SKILL.md").write_text("# Palas Skill\n")

    # nymyka dimension with skills and rules
    nym_skills = dims / "nymyka" / "skills" / "niky-ceo"
    nym_skills.mkdir(parents=True)
    (nym_skills / "SKILL.md").write_text("# Niky CEO\n")

    nym_rules = dims / "nymyka" / "rules"
    nym_rules.mkdir(parents=True)
    (nym_rules / "firewall.md").write_text("# Firewall rules\n")
    (nym_rules / "sops.md").write_text("# SOPs\n")

    return hermes_dir


@pytest.fixture
def hermes_dir_with_bus(hermes_dir):
    """Add bus file to hermes_dir."""
    bus_dir = hermes_dir / "bus"
    bus_dir.mkdir(exist_ok=True)
    bus_file = bus_dir / "active.jsonl"
    bus_file.write_text(
        '{"ts":"2026-03-19","src":"test","dst":"*","type":"state",'
        '"msg":"test message","ttl":7,"ack":[]}\n'
    )
    return hermes_dir


@pytest.fixture
def hermes_dir_with_peers(tmp_path):
    """Create hermes_dir with peers configured."""
    hdir = tmp_path / ".hermes"
    config = GatewayConfig(
        clan_id="clan-test",
        display_name="Test Clan",
        peers=[
            PeerConfig("clan-jei", ".keys/peers/jei.pub", "established", "2026-03-01"),
            PeerConfig("clan-nymyka", ".keys/peers/nymyka.pub", "pending_ack", "2026-03-15"),
        ],
    )
    hdir.mkdir(parents=True)
    save_config_toml(config, hdir / "config.toml")
    return hdir


@pytest.fixture
def target_dir(tmp_path):
    """Create target directory for Claude Code output."""
    tdir = tmp_path / ".claude"
    tdir.mkdir()
    return tdir


# ─── _safe_symlink ────────────────────────────────────────────────


class TestSafeSymlink:
    """Tests for _safe_symlink helper."""

    def test_creates_symlink(self, tmp_path):
        target = tmp_path / "target.txt"
        target.write_text("content")
        link = tmp_path / "link.txt"
        assert _safe_symlink(link, target) is True
        assert link.is_symlink()
        assert link.read_text() == "content"

    def test_creates_parent_dirs(self, tmp_path):
        target = tmp_path / "target.txt"
        target.write_text("content")
        link = tmp_path / "nested" / "deep" / "link.txt"
        assert _safe_symlink(link, target) is True
        assert link.is_symlink()

    def test_returns_false_if_unchanged(self, tmp_path):
        target = tmp_path / "target.txt"
        target.write_text("content")
        link = tmp_path / "link.txt"
        _safe_symlink(link, target)
        assert _safe_symlink(link, target) is False

    def test_updates_stale_symlink(self, tmp_path):
        old = tmp_path / "old.txt"
        old.write_text("old")
        new = tmp_path / "new.txt"
        new.write_text("new")
        link = tmp_path / "link.txt"
        _safe_symlink(link, old)
        assert _safe_symlink(link, new) is True
        assert link.read_text() == "new"

    def test_replaces_regular_file(self, tmp_path):
        target = tmp_path / "target.txt"
        target.write_text("target")
        link = tmp_path / "link.txt"
        link.write_text("regular file")
        assert _safe_symlink(link, target) is True
        assert link.is_symlink()
        assert link.read_text() == "target"


# ─── _write_file_if_changed ──────────────────────────────────────


class TestWriteFileIfChanged:
    """Tests for _write_file_if_changed helper."""

    def test_creates_new_file(self, tmp_path):
        path = tmp_path / "new.txt"
        assert _write_file_if_changed(path, "content") is True
        assert path.read_text() == "content"

    def test_returns_false_if_unchanged(self, tmp_path):
        path = tmp_path / "file.txt"
        path.write_text("content")
        assert _write_file_if_changed(path, "content") is False

    def test_updates_changed_content(self, tmp_path):
        path = tmp_path / "file.txt"
        path.write_text("old content")
        assert _write_file_if_changed(path, "new content") is True
        assert path.read_text() == "new content"

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "nested" / "deep" / "file.txt"
        assert _write_file_if_changed(path, "content") is True
        assert path.exists()


# ─── ClaudeCodeAdapter basic ─────────────────────────────────────


class TestClaudeCodeAdapterBasic:
    """Basic adapter tests with minimal config."""

    def test_adapt_success(self, hermes_dir, target_dir):
        adapter = ClaudeCodeAdapter(hermes_dir=hermes_dir, target_dir=target_dir)
        result = adapter.adapt()
        assert result.success is True
        assert result.adapter_name == "claude-code"
        assert len(result.steps) >= 2  # config loaded + CLAUDE.md

    def test_generates_claude_md(self, hermes_dir, target_dir):
        adapter = ClaudeCodeAdapter(hermes_dir=hermes_dir, target_dir=target_dir)
        adapter.adapt()
        claude_md = target_dir / "CLAUDE.md"
        assert claude_md.exists()
        content = claude_md.read_text()
        assert "clan-test" in content
        assert "Test Clan" in content

    def test_claude_md_contains_identity(self, hermes_dir, target_dir):
        adapter = ClaudeCodeAdapter(hermes_dir=hermes_dir, target_dir=target_dir)
        adapter.adapt()
        content = (target_dir / "CLAUDE.md").read_text()
        assert "Clan ID" in content
        assert "Protocol Version" in content

    def test_claude_md_contains_hermes_footer(self, hermes_dir, target_dir):
        adapter = ClaudeCodeAdapter(hermes_dir=hermes_dir, target_dir=target_dir)
        adapter.adapt()
        content = (target_dir / "CLAUDE.md").read_text()
        assert "hermes adapt claude-code" in content

    def test_claude_md_auto_generated_notice(self, hermes_dir, target_dir):
        adapter = ClaudeCodeAdapter(hermes_dir=hermes_dir, target_dir=target_dir)
        adapter.adapt()
        content = (target_dir / "CLAUDE.md").read_text()
        assert "Auto-generated" in content
        assert "Do not edit manually" in content


# ─── Bus linking ─────────────────────────────────────────────────


class TestClaudeCodeAdapterBus:
    """Bus symlink tests."""

    def test_links_bus_active(self, hermes_dir_with_bus, target_dir):
        adapter = ClaudeCodeAdapter(
            hermes_dir=hermes_dir_with_bus, target_dir=target_dir
        )
        result = adapter.adapt()
        bus_link = target_dir / "sync" / "bus.jsonl"
        assert bus_link.is_symlink()
        assert "test message" in bus_link.read_text()

    def test_bus_link_resolves_to_hermes(self, hermes_dir_with_bus, target_dir):
        adapter = ClaudeCodeAdapter(
            hermes_dir=hermes_dir_with_bus, target_dir=target_dir
        )
        adapter.adapt()
        bus_link = target_dir / "sync" / "bus.jsonl"
        resolved = bus_link.resolve()
        assert ".hermes" in str(resolved)
        assert resolved.name == "active.jsonl"

    def test_creates_bus_if_missing(self, hermes_dir, target_dir):
        # hermes_dir has no bus file — adapter should create one
        adapter = ClaudeCodeAdapter(hermes_dir=hermes_dir, target_dir=target_dir)
        adapter.adapt()
        bus_link = target_dir / "sync" / "bus.jsonl"
        assert bus_link.is_symlink()
        # Source should have been created
        bus_source = hermes_dir / "bus" / "active.jsonl"
        assert bus_source.exists()

    def test_legacy_bus_path(self, tmp_path):
        """Adapter falls back to bus.jsonl (legacy) if bus/active.jsonl doesn't exist."""
        hdir = tmp_path / ".hermes"
        init_clan(hdir, "clan-test", "Test Clan", config_format="toml")
        # Create legacy bus.jsonl at root
        legacy_bus = hdir / "bus.jsonl"
        legacy_bus.write_text('{"ts":"2026-03-19","src":"x","dst":"*","type":"state","msg":"legacy","ttl":7,"ack":[]}\n')
        # Remove bus/active.jsonl if it exists
        bus_active = hdir / "bus" / "active.jsonl"
        if bus_active.exists():
            bus_active.unlink()

        tdir = tmp_path / ".claude"
        tdir.mkdir()
        adapter = ClaudeCodeAdapter(hermes_dir=hdir, target_dir=tdir)
        adapter.adapt()
        bus_link = tdir / "sync" / "bus.jsonl"
        assert bus_link.is_symlink()
        assert "legacy" in bus_link.read_text()


# ─── Dimension skills ────────────────────────────────────────────


class TestClaudeCodeAdapterSkills:
    """Dimension skill linking tests."""

    def test_links_global_skills(self, hermes_dir_with_dims, target_dir):
        adapter = ClaudeCodeAdapter(
            hermes_dir=hermes_dir_with_dims, target_dir=target_dir
        )
        result = adapter.adapt()

        consejo = target_dir / "skills" / "global" / "consejo"
        palas = target_dir / "skills" / "global" / "palas"
        assert consejo.is_symlink()
        assert palas.is_symlink()
        assert (consejo / "SKILL.md").read_text() == "# Consejo Skill\n"

    def test_links_dimension_skills(self, hermes_dir_with_dims, target_dir):
        adapter = ClaudeCodeAdapter(
            hermes_dir=hermes_dir_with_dims, target_dir=target_dir
        )
        adapter.adapt()

        niky = target_dir / "skills" / "nymyka" / "niky-ceo"
        assert niky.is_symlink()
        assert (niky / "SKILL.md").read_text() == "# Niky CEO\n"

    def test_no_skills_dir_ok(self, hermes_dir, target_dir):
        adapter = ClaudeCodeAdapter(hermes_dir=hermes_dir, target_dir=target_dir)
        result = adapter.adapt()
        assert result.success is True
        assert "No dimension skills found" in result.steps

    def test_reports_linked_count(self, hermes_dir_with_dims, target_dir):
        adapter = ClaudeCodeAdapter(
            hermes_dir=hermes_dir_with_dims, target_dir=target_dir
        )
        result = adapter.adapt()
        skill_step = [s for s in result.steps if "Skills linked" in s]
        assert len(skill_step) == 1
        # 3 skill links: consejo, palas (global) + niky-ceo (nymyka)
        assert "3 skills" in skill_step[0]


# ─── Dimension rules ─────────────────────────────────────────────


class TestClaudeCodeAdapterRules:
    """Dimension rule linking tests."""

    def test_links_rules_with_prefix(self, hermes_dir_with_dims, target_dir):
        adapter = ClaudeCodeAdapter(
            hermes_dir=hermes_dir_with_dims, target_dir=target_dir
        )
        adapter.adapt()

        rules_dir = target_dir / "rules"
        assert (rules_dir / "nymyka-firewall.md").is_symlink()
        assert (rules_dir / "nymyka-sops.md").is_symlink()
        assert "Firewall rules" in (rules_dir / "nymyka-firewall.md").read_text()

    def test_no_rules_dir_ok(self, hermes_dir, target_dir):
        adapter = ClaudeCodeAdapter(hermes_dir=hermes_dir, target_dir=target_dir)
        result = adapter.adapt()
        assert result.success is True
        assert "No dimension rules found" in result.steps


# ─── Peers in CLAUDE.md ──────────────────────────────────────────


class TestClaudeCodeAdapterPeers:
    """Peer display in CLAUDE.md."""

    def test_claude_md_includes_peers(self, hermes_dir_with_peers, target_dir):
        adapter = ClaudeCodeAdapter(
            hermes_dir=hermes_dir_with_peers, target_dir=target_dir
        )
        adapter.adapt()
        content = (target_dir / "CLAUDE.md").read_text()
        assert "clan-jei" in content
        assert "established" in content
        assert "clan-nymyka" in content
        assert "pending_ack" in content

    def test_no_peers_section_when_empty(self, hermes_dir, target_dir):
        adapter = ClaudeCodeAdapter(hermes_dir=hermes_dir, target_dir=target_dir)
        adapter.adapt()
        content = (target_dir / "CLAUDE.md").read_text()
        assert "## Peers" not in content


# ─── Dimensions in CLAUDE.md ─────────────────────────────────────


class TestClaudeCodeAdapterDimensions:
    """Dimension listing in CLAUDE.md."""

    def test_lists_dimensions(self, hermes_dir_with_dims, target_dir):
        adapter = ClaudeCodeAdapter(
            hermes_dir=hermes_dir_with_dims, target_dir=target_dir
        )
        adapter.adapt()
        content = (target_dir / "CLAUDE.md").read_text()
        assert "`global`" in content
        assert "`nymyka`" in content

    def test_no_dimensions_section_when_missing(self, hermes_dir, target_dir):
        adapter = ClaudeCodeAdapter(hermes_dir=hermes_dir, target_dir=target_dir)
        adapter.adapt()
        content = (target_dir / "CLAUDE.md").read_text()
        assert "## Dimensions" not in content


# ─── Idempotency ─────────────────────────────────────────────────


class TestClaudeCodeAdapterIdempotency:
    """Adapter is safe to run multiple times."""

    def test_run_twice_no_errors(self, hermes_dir_with_dims, target_dir):
        adapter = ClaudeCodeAdapter(
            hermes_dir=hermes_dir_with_dims, target_dir=target_dir
        )
        r1 = adapter.adapt()
        r2 = adapter.adapt()
        assert r1.success is True
        assert r2.success is True

    def test_run_twice_unchanged(self, hermes_dir_with_dims, target_dir):
        adapter = ClaudeCodeAdapter(
            hermes_dir=hermes_dir_with_dims, target_dir=target_dir
        )
        adapter.adapt()
        r2 = adapter.adapt()
        # Second run should report "unchanged" for most steps
        assert "CLAUDE.md unchanged" in r2.steps
        assert "Bus symlink unchanged" in r2.steps

    def test_symlinks_survive_rerun(self, hermes_dir_with_dims, target_dir):
        adapter = ClaudeCodeAdapter(
            hermes_dir=hermes_dir_with_dims, target_dir=target_dir
        )
        adapter.adapt()
        adapter.adapt()
        # Skills still linked
        assert (target_dir / "skills" / "global" / "consejo").is_symlink()
        assert (target_dir / "skills" / "nymyka" / "niky-ceo").is_symlink()


# ─── Error handling ──────────────────────────────────────────────


class TestClaudeCodeAdapterErrors:
    """Error handling tests."""

    def test_no_config_fails_gracefully(self, tmp_path):
        hdir = tmp_path / ".hermes"
        hdir.mkdir()
        tdir = tmp_path / ".claude"
        tdir.mkdir()
        adapter = ClaudeCodeAdapter(hermes_dir=hdir, target_dir=tdir)
        result = adapter.adapt()
        assert result.success is False
        assert any("Config error" in e for e in result.errors)

    def test_missing_hermes_dir(self, tmp_path):
        hdir = tmp_path / "nonexistent"
        tdir = tmp_path / ".claude"
        tdir.mkdir()
        adapter = ClaudeCodeAdapter(hermes_dir=hdir, target_dir=tdir)
        result = adapter.adapt()
        assert result.success is False

    def test_target_dir_created_if_missing(self, hermes_dir, tmp_path):
        tdir = tmp_path / "new_claude_dir"
        adapter = ClaudeCodeAdapter(hermes_dir=hermes_dir, target_dir=tdir)
        result = adapter.adapt()
        assert result.success is True
        assert (tdir / "CLAUDE.md").exists()


# ─── Adapter registry ────────────────────────────────────────────


class TestAdapterRegistry:
    """Adapter registry tests."""

    def test_list_adapters(self):
        adapters = list_adapters()
        assert "claude-code" in adapters

    def test_get_adapter(self):
        cls = get_adapter("claude-code")
        assert cls is ClaudeCodeAdapter

    def test_get_unknown_returns_none(self):
        assert get_adapter("nonexistent") is None

    def test_run_adapter(self, hermes_dir, target_dir):
        result = run_adapter("claude-code", hermes_dir=hermes_dir, target_dir=target_dir)
        assert result.success is True
        assert result.adapter_name == "claude-code"

    def test_run_unknown_raises(self):
        with pytest.raises(KeyError, match="Unknown adapter"):
            run_adapter("nonexistent")


# ─── Default paths ───────────────────────────────────────────────


class TestClaudeCodeAdapterDefaults:
    """Test that defaults point to ~/.hermes and ~/.claude."""

    def test_default_hermes_dir(self):
        adapter = ClaudeCodeAdapter()
        assert adapter.hermes_dir == Path.home() / ".hermes"

    def test_default_target_dir(self):
        adapter = ClaudeCodeAdapter()
        assert adapter.target_dir == Path.home() / ".claude"

    def test_custom_dirs(self, tmp_path):
        hdir = tmp_path / "h"
        tdir = tmp_path / "t"
        adapter = ClaudeCodeAdapter(hermes_dir=hdir, target_dir=tdir)
        assert adapter.hermes_dir == hdir
        assert adapter.target_dir == tdir


# ─── AdaptResult ─────────────────────────────────────────────────


class TestAdaptResult:
    """Result dataclass tests."""

    def test_default_values(self):
        r = AdaptResult(success=True, adapter_name="test")
        assert r.steps == []
        assert r.errors == []
        assert r.files_written == []
        assert r.symlinks_created == []

    def test_success_with_steps(self):
        r = AdaptResult(
            success=True,
            adapter_name="claude-code",
            steps=["step1", "step2"],
            files_written=["f1"],
            symlinks_created=["s1", "s2"],
        )
        assert len(r.steps) == 2
        assert len(r.files_written) == 1
        assert len(r.symlinks_created) == 2
