"""Tests for HERMES Adapter — Agent-agnostic bridge (installable-model.md Phase 2+3)."""

from pathlib import Path

import pytest

from hermes.adapter import (
    AdaptResult,
    ClaudeCodeAdapter,
    CursorAdapter,
    GeminiCLIAdapter,
    OpenCodeAdapter,
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
        adapter = ClaudeCodeAdapter(hermes_dir=hermes_dir_with_bus, target_dir=target_dir)
        adapter.adapt()
        bus_link = target_dir / "sync" / "bus.jsonl"
        assert bus_link.is_symlink()
        assert "test message" in bus_link.read_text()

    def test_bus_link_resolves_to_hermes(self, hermes_dir_with_bus, target_dir):
        adapter = ClaudeCodeAdapter(hermes_dir=hermes_dir_with_bus, target_dir=target_dir)
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
        legacy_bus.write_text(
            '{"ts":"2026-03-19","src":"x","dst":"*","type":"state","msg":"legacy","ttl":7,"ack":[]}\n'
        )
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
        adapter = ClaudeCodeAdapter(hermes_dir=hermes_dir_with_dims, target_dir=target_dir)
        adapter.adapt()

        consejo = target_dir / "skills" / "global" / "consejo"
        palas = target_dir / "skills" / "global" / "palas"
        assert consejo.is_symlink()
        assert palas.is_symlink()
        assert (consejo / "SKILL.md").read_text() == "# Consejo Skill\n"

    def test_links_dimension_skills(self, hermes_dir_with_dims, target_dir):
        adapter = ClaudeCodeAdapter(hermes_dir=hermes_dir_with_dims, target_dir=target_dir)
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
        adapter = ClaudeCodeAdapter(hermes_dir=hermes_dir_with_dims, target_dir=target_dir)
        result = adapter.adapt()
        skill_step = [s for s in result.steps if "Skills linked" in s]
        assert len(skill_step) == 1
        # 3 skill links: consejo, palas (global) + niky-ceo (nymyka)
        assert "3 skills" in skill_step[0]


# ─── Dimension rules ─────────────────────────────────────────────


class TestClaudeCodeAdapterRules:
    """Dimension rule linking tests."""

    def test_links_rules_with_prefix(self, hermes_dir_with_dims, target_dir):
        adapter = ClaudeCodeAdapter(hermes_dir=hermes_dir_with_dims, target_dir=target_dir)
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
        adapter = ClaudeCodeAdapter(hermes_dir=hermes_dir_with_peers, target_dir=target_dir)
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
        adapter = ClaudeCodeAdapter(hermes_dir=hermes_dir_with_dims, target_dir=target_dir)
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
        adapter = ClaudeCodeAdapter(hermes_dir=hermes_dir_with_dims, target_dir=target_dir)
        r1 = adapter.adapt()
        r2 = adapter.adapt()
        assert r1.success is True
        assert r2.success is True

    def test_run_twice_unchanged(self, hermes_dir_with_dims, target_dir):
        adapter = ClaudeCodeAdapter(hermes_dir=hermes_dir_with_dims, target_dir=target_dir)
        adapter.adapt()
        r2 = adapter.adapt()
        # Second run should report "unchanged" for most steps
        assert "CLAUDE.md unchanged" in r2.steps
        assert "Bus symlink unchanged" in r2.steps

    def test_symlinks_survive_rerun(self, hermes_dir_with_dims, target_dir):
        adapter = ClaudeCodeAdapter(hermes_dir=hermes_dir_with_dims, target_dir=target_dir)
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


# ─── CursorAdapter fixtures ────────────────────────────────────


@pytest.fixture
def cursor_target_dir(tmp_path):
    """Create target directory for Cursor output (project root)."""
    tdir = tmp_path / "my-project"
    tdir.mkdir()
    return tdir


# ─── CursorAdapter basic ───────────────────────────────────────


class TestCursorAdapterBasic:
    """Basic CursorAdapter tests with minimal config."""

    def test_adapt_success(self, hermes_dir, cursor_target_dir):
        adapter = CursorAdapter(hermes_dir=hermes_dir, target_dir=cursor_target_dir)
        result = adapter.adapt()
        assert result.success is True
        assert result.adapter_name == "cursor"
        assert len(result.steps) >= 2

    def test_generates_cursorrules(self, hermes_dir, cursor_target_dir):
        adapter = CursorAdapter(hermes_dir=hermes_dir, target_dir=cursor_target_dir)
        adapter.adapt()
        cursorrules = cursor_target_dir / ".cursorrules"
        assert cursorrules.exists()
        content = cursorrules.read_text()
        assert "clan-test" in content
        assert "Test Clan" in content

    def test_cursorrules_contains_identity(self, hermes_dir, cursor_target_dir):
        adapter = CursorAdapter(hermes_dir=hermes_dir, target_dir=cursor_target_dir)
        adapter.adapt()
        content = (cursor_target_dir / ".cursorrules").read_text()
        assert "Clan ID" in content
        assert "Protocol Version" in content

    def test_cursorrules_auto_generated_notice(self, hermes_dir, cursor_target_dir):
        adapter = CursorAdapter(hermes_dir=hermes_dir, target_dir=cursor_target_dir)
        adapter.adapt()
        content = (cursor_target_dir / ".cursorrules").read_text()
        assert "Auto-generated" in content
        assert "hermes adapt cursor" in content

    def test_cursorrules_has_markers(self, hermes_dir, cursor_target_dir):
        adapter = CursorAdapter(hermes_dir=hermes_dir, target_dir=cursor_target_dir)
        adapter.adapt()
        content = (cursor_target_dir / ".cursorrules").read_text()
        assert CursorAdapter.HEADER_MARKER in content
        assert CursorAdapter.FOOTER_MARKER in content


# ─── CursorAdapter skills compilation ──────────────────────────


class TestCursorAdapterSkills:
    """Skill compilation tests."""

    def test_compiles_skills_into_cursorrules(self, hermes_dir_with_dims, cursor_target_dir):
        adapter = CursorAdapter(hermes_dir=hermes_dir_with_dims, target_dir=cursor_target_dir)
        adapter.adapt()
        content = (cursor_target_dir / ".cursorrules").read_text()
        assert "## Skills" in content
        assert "Consejo Skill" in content
        assert "Palas Skill" in content
        assert "Niky CEO" in content

    def test_skills_grouped_by_dimension(self, hermes_dir_with_dims, cursor_target_dir):
        adapter = CursorAdapter(hermes_dir=hermes_dir_with_dims, target_dir=cursor_target_dir)
        adapter.adapt()
        content = (cursor_target_dir / ".cursorrules").read_text()
        assert "Dimension: global" in content
        assert "Dimension: nymyka" in content

    def test_no_skills_section_when_empty(self, hermes_dir, cursor_target_dir):
        adapter = CursorAdapter(hermes_dir=hermes_dir, target_dir=cursor_target_dir)
        adapter.adapt()
        content = (cursor_target_dir / ".cursorrules").read_text()
        assert "## Skills" not in content


# ─── CursorAdapter rules compilation ───────────────────────────


class TestCursorAdapterRules:
    """Rule compilation tests."""

    def test_compiles_rules_into_cursorrules(self, hermes_dir_with_dims, cursor_target_dir):
        adapter = CursorAdapter(hermes_dir=hermes_dir_with_dims, target_dir=cursor_target_dir)
        adapter.adapt()
        content = (cursor_target_dir / ".cursorrules").read_text()
        assert "## Rules" in content
        assert "Firewall rules" in content
        assert "SOPs" in content

    def test_rules_grouped_by_dimension(self, hermes_dir_with_dims, cursor_target_dir):
        adapter = CursorAdapter(hermes_dir=hermes_dir_with_dims, target_dir=cursor_target_dir)
        adapter.adapt()
        content = (cursor_target_dir / ".cursorrules").read_text()
        # Rules only exist in nymyka dimension in fixture
        assert "Dimension: nymyka" in content

    def test_no_rules_section_when_empty(self, hermes_dir, cursor_target_dir):
        adapter = CursorAdapter(hermes_dir=hermes_dir, target_dir=cursor_target_dir)
        adapter.adapt()
        content = (cursor_target_dir / ".cursorrules").read_text()
        assert "## Rules" not in content


# ─── CursorAdapter bus ──────────────────────────────────────────


class TestCursorAdapterBus:
    """Bus symlink tests for Cursor."""

    def test_links_bus(self, hermes_dir_with_bus, cursor_target_dir):
        adapter = CursorAdapter(hermes_dir=hermes_dir_with_bus, target_dir=cursor_target_dir)
        adapter.adapt()
        bus_link = cursor_target_dir / ".cursor" / "bus.jsonl"
        assert bus_link.is_symlink()
        assert "test message" in bus_link.read_text()

    def test_no_bus_no_error(self, hermes_dir, cursor_target_dir):
        # hermes_dir has no bus file — should not fail
        adapter = CursorAdapter(hermes_dir=hermes_dir, target_dir=cursor_target_dir)
        result = adapter.adapt()
        assert result.success is True
        assert "Bus symlink unchanged" in result.steps


# ─── CursorAdapter peers ───────────────────────────────────────


class TestCursorAdapterPeers:
    """Peer display in .cursorrules."""

    def test_cursorrules_includes_peers(self, hermes_dir_with_peers, cursor_target_dir):
        adapter = CursorAdapter(hermes_dir=hermes_dir_with_peers, target_dir=cursor_target_dir)
        adapter.adapt()
        content = (cursor_target_dir / ".cursorrules").read_text()
        assert "clan-jei" in content
        assert "established" in content

    def test_no_peers_section_when_empty(self, hermes_dir, cursor_target_dir):
        adapter = CursorAdapter(hermes_dir=hermes_dir, target_dir=cursor_target_dir)
        adapter.adapt()
        content = (cursor_target_dir / ".cursorrules").read_text()
        assert "## Peers" not in content


# ─── CursorAdapter idempotency ──────────────────────────────────


class TestCursorAdapterIdempotency:
    """Cursor adapter is safe to run multiple times."""

    def test_run_twice_no_errors(self, hermes_dir_with_dims, cursor_target_dir):
        adapter = CursorAdapter(hermes_dir=hermes_dir_with_dims, target_dir=cursor_target_dir)
        r1 = adapter.adapt()
        r2 = adapter.adapt()
        assert r1.success is True
        assert r2.success is True

    def test_run_twice_unchanged(self, hermes_dir_with_dims, cursor_target_dir):
        adapter = CursorAdapter(hermes_dir=hermes_dir_with_dims, target_dir=cursor_target_dir)
        adapter.adapt()
        r2 = adapter.adapt()
        assert ".cursorrules unchanged" in r2.steps

    def test_preserves_user_content(self, hermes_dir, cursor_target_dir):
        """User content outside HERMES markers is preserved."""
        cursorrules = cursor_target_dir / ".cursorrules"
        # Write file with user content + HERMES markers
        cursorrules.write_text(
            "# My Project Rules\n\nCustom rule 1.\n\n"
            "<!-- HERMES:BEGIN -->\nold hermes content\n<!-- HERMES:END -->\n\n"
            "# More User Rules\n\nCustom rule 2.\n"
        )
        adapter = CursorAdapter(hermes_dir=hermes_dir, target_dir=cursor_target_dir)
        adapter.adapt()
        content = cursorrules.read_text()
        # User content preserved
        assert "My Project Rules" in content
        assert "Custom rule 1" in content
        assert "More User Rules" in content
        assert "Custom rule 2" in content
        # HERMES content updated
        assert "clan-test" in content
        assert "old hermes content" not in content


# ─── CursorAdapter error handling ───────────────────────────────


class TestCursorAdapterErrors:
    """Error handling tests for Cursor adapter."""

    def test_no_config_fails_gracefully(self, tmp_path):
        hdir = tmp_path / ".hermes"
        hdir.mkdir()
        tdir = tmp_path / "project"
        tdir.mkdir()
        adapter = CursorAdapter(hermes_dir=hdir, target_dir=tdir)
        result = adapter.adapt()
        assert result.success is False
        assert any("Config error" in e for e in result.errors)

    def test_target_dir_created_if_missing(self, hermes_dir, tmp_path):
        tdir = tmp_path / "new_project"
        adapter = CursorAdapter(hermes_dir=hermes_dir, target_dir=tdir)
        result = adapter.adapt()
        assert result.success is True
        assert (tdir / ".cursorrules").exists()


# ─── CursorAdapter defaults ────────────────────────────────────


class TestCursorAdapterDefaults:
    """Default path tests for Cursor adapter."""

    def test_default_hermes_dir(self):
        adapter = CursorAdapter()
        assert adapter.hermes_dir == Path.home() / ".hermes"

    def test_default_target_dir_is_cwd(self):
        adapter = CursorAdapter()
        assert adapter.target_dir == Path.cwd()

    def test_custom_dirs(self, tmp_path):
        hdir = tmp_path / "h"
        tdir = tmp_path / "t"
        adapter = CursorAdapter(hermes_dir=hdir, target_dir=tdir)
        assert adapter.hermes_dir == hdir
        assert adapter.target_dir == tdir


# ─── Adapter registry (updated) ────────────────────────────────


class TestAdapterRegistryCursor:
    """Registry tests including Cursor adapter."""

    def test_cursor_in_list(self):
        adapters = list_adapters()
        assert "cursor" in adapters

    def test_get_cursor_adapter(self):
        cls = get_adapter("cursor")
        assert cls is CursorAdapter

    def test_run_cursor_adapter(self, hermes_dir, cursor_target_dir):
        result = run_adapter("cursor", hermes_dir=hermes_dir, target_dir=cursor_target_dir)
        assert result.success is True
        assert result.adapter_name == "cursor"


# ═══════════════════════════════════════════════════════════════════
# OpenCode Adapter Tests
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def opencode_target_dir(tmp_path):
    """Create target directory for OpenCode output."""
    tdir = tmp_path / ".config" / "opencode"
    tdir.mkdir(parents=True)
    return tdir


# ─── OpenCodeAdapter basic ────────────────────────────────────────


class TestOpenCodeAdapterBasic:
    """Basic OpenCodeAdapter tests with minimal config."""

    def test_adapt_success(self, hermes_dir, opencode_target_dir):
        adapter = OpenCodeAdapter(hermes_dir=hermes_dir, target_dir=opencode_target_dir)
        result = adapter.adapt()
        assert result.success is True
        assert result.adapter_name == "opencode"
        assert len(result.steps) >= 3  # config + AGENTS.md + opencode.json

    def test_generates_agents_md(self, hermes_dir, opencode_target_dir):
        adapter = OpenCodeAdapter(hermes_dir=hermes_dir, target_dir=opencode_target_dir)
        adapter.adapt()
        agents_md = opencode_target_dir / "AGENTS.md"
        assert agents_md.exists()
        content = agents_md.read_text()
        assert "clan-test" in content
        assert "Test Clan" in content

    def test_agents_md_contains_identity(self, hermes_dir, opencode_target_dir):
        adapter = OpenCodeAdapter(hermes_dir=hermes_dir, target_dir=opencode_target_dir)
        adapter.adapt()
        content = (opencode_target_dir / "AGENTS.md").read_text()
        assert "Clan ID" in content
        assert "Protocol Version" in content

    def test_agents_md_auto_generated_notice(self, hermes_dir, opencode_target_dir):
        adapter = OpenCodeAdapter(hermes_dir=hermes_dir, target_dir=opencode_target_dir)
        adapter.adapt()
        content = (opencode_target_dir / "AGENTS.md").read_text()
        assert "Auto-generated" in content
        assert "hermes adapt opencode" in content

    def test_agents_md_has_markers(self, hermes_dir, opencode_target_dir):
        adapter = OpenCodeAdapter(hermes_dir=hermes_dir, target_dir=opencode_target_dir)
        adapter.adapt()
        content = (opencode_target_dir / "AGENTS.md").read_text()
        assert OpenCodeAdapter.HEADER_MARKER in content
        assert OpenCodeAdapter.FOOTER_MARKER in content


# ─── OpenCodeAdapter skills ──────────────────────────────────────


class TestOpenCodeAdapterSkills:
    """Skill compilation and linking tests."""

    def test_compiles_skills_into_agents_md(self, hermes_dir_with_dims, opencode_target_dir):
        adapter = OpenCodeAdapter(hermes_dir=hermes_dir_with_dims, target_dir=opencode_target_dir)
        adapter.adapt()
        content = (opencode_target_dir / "AGENTS.md").read_text()
        assert "## Skills" in content
        assert "Consejo Skill" in content
        assert "Palas Skill" in content
        assert "Niky CEO" in content

    def test_symlinks_skills_with_dimension_subdirs(self, hermes_dir_with_dims, opencode_target_dir):
        adapter = OpenCodeAdapter(hermes_dir=hermes_dir_with_dims, target_dir=opencode_target_dir)
        adapter.adapt()
        skills_dir = opencode_target_dir / "skills"
        # Skills in dimension subdirs — directory name matches skill name (Agent Skills Standard)
        assert (skills_dir / "global" / "consejo").is_symlink()
        assert (skills_dir / "global" / "palas").is_symlink()
        assert (skills_dir / "nymyka" / "niky-ceo").is_symlink()
        # Content accessible through symlinks
        assert (skills_dir / "global" / "consejo" / "SKILL.md").read_text() == "# Consejo Skill\n"

    def test_no_skills_ok(self, hermes_dir, opencode_target_dir):
        adapter = OpenCodeAdapter(hermes_dir=hermes_dir, target_dir=opencode_target_dir)
        result = adapter.adapt()
        assert result.success is True
        assert "No dimension skills found" in result.steps

    def test_reports_linked_count(self, hermes_dir_with_dims, opencode_target_dir):
        adapter = OpenCodeAdapter(hermes_dir=hermes_dir_with_dims, target_dir=opencode_target_dir)
        result = adapter.adapt()
        skill_step = [s for s in result.steps if "Skills linked" in s]
        assert len(skill_step) == 1
        assert "3 skills" in skill_step[0]


# ─── OpenCodeAdapter rules ───────────────────────────────────────


class TestOpenCodeAdapterRules:
    """Rule compilation tests."""

    def test_compiles_rules_into_agents_md(self, hermes_dir_with_dims, opencode_target_dir):
        adapter = OpenCodeAdapter(hermes_dir=hermes_dir_with_dims, target_dir=opencode_target_dir)
        adapter.adapt()
        content = (opencode_target_dir / "AGENTS.md").read_text()
        assert "## Rules" in content
        assert "Firewall rules" in content
        assert "SOPs" in content

    def test_rules_grouped_by_dimension(self, hermes_dir_with_dims, opencode_target_dir):
        adapter = OpenCodeAdapter(hermes_dir=hermes_dir_with_dims, target_dir=opencode_target_dir)
        adapter.adapt()
        content = (opencode_target_dir / "AGENTS.md").read_text()
        assert "Dimension: nymyka" in content

    def test_no_rules_section_when_empty(self, hermes_dir, opencode_target_dir):
        adapter = OpenCodeAdapter(hermes_dir=hermes_dir, target_dir=opencode_target_dir)
        adapter.adapt()
        content = (opencode_target_dir / "AGENTS.md").read_text()
        assert "## Rules" not in content


# ─── OpenCodeAdapter bus ─────────────────────────────────────────


class TestOpenCodeAdapterBus:
    """Bus symlink tests for OpenCode."""

    def test_links_bus(self, hermes_dir_with_bus, opencode_target_dir):
        adapter = OpenCodeAdapter(hermes_dir=hermes_dir_with_bus, target_dir=opencode_target_dir)
        adapter.adapt()
        bus_link = opencode_target_dir / "bus.jsonl"
        assert bus_link.is_symlink()
        assert "test message" in bus_link.read_text()

    def test_bus_resolves_to_hermes(self, hermes_dir_with_bus, opencode_target_dir):
        adapter = OpenCodeAdapter(hermes_dir=hermes_dir_with_bus, target_dir=opencode_target_dir)
        adapter.adapt()
        bus_link = opencode_target_dir / "bus.jsonl"
        resolved = bus_link.resolve()
        assert ".hermes" in str(resolved)

    def test_no_bus_no_error(self, hermes_dir, opencode_target_dir):
        adapter = OpenCodeAdapter(hermes_dir=hermes_dir, target_dir=opencode_target_dir)
        result = adapter.adapt()
        assert result.success is True
        assert "Bus symlink unchanged" in result.steps


# ─── OpenCodeAdapter opencode.json ───────────────────────────────


class TestOpenCodeAdapterJson:
    """opencode.json generation and merge tests."""

    def test_generates_json_with_schema(self, hermes_dir, opencode_target_dir):
        adapter = OpenCodeAdapter(hermes_dir=hermes_dir, target_dir=opencode_target_dir)
        adapter.adapt()
        import json

        config = json.loads((opencode_target_dir / "opencode.json").read_text())
        assert config["$schema"] == "https://opencode.ai/config.json"

    def test_json_has_instructions_field(self, hermes_dir, opencode_target_dir):
        adapter = OpenCodeAdapter(hermes_dir=hermes_dir, target_dir=opencode_target_dir)
        adapter.adapt()
        import json

        config = json.loads((opencode_target_dir / "opencode.json").read_text())
        assert "AGENTS.md" in config["instructions"]

    def test_json_has_hermes_metadata(self, hermes_dir, opencode_target_dir):
        adapter = OpenCodeAdapter(hermes_dir=hermes_dir, target_dir=opencode_target_dir)
        adapter.adapt()
        import json

        config = json.loads((opencode_target_dir / "opencode.json").read_text())
        assert config["_hermes"]["managed_by"] == "hermes adapt opencode"
        assert config["_hermes"]["clan_id"] == "clan-test"

    def test_merge_preserves_user_keys(self, hermes_dir, opencode_target_dir):
        """User-configured keys in opencode.json are preserved during merge."""
        import json

        # Pre-existing user config
        user_config = {
            "$schema": "https://opencode.ai/config.json",
            "model": "google/gemini-2.5-flash",
            "mcp": {"sentry": {"enabled": True}},
            "instructions": ["my-rules.md"],
        }
        (opencode_target_dir / "opencode.json").write_text(json.dumps(user_config))

        adapter = OpenCodeAdapter(hermes_dir=hermes_dir, target_dir=opencode_target_dir)
        adapter.adapt()

        config = json.loads((opencode_target_dir / "opencode.json").read_text())
        # User keys preserved
        assert config["model"] == "google/gemini-2.5-flash"
        assert config["mcp"]["sentry"]["enabled"] is True
        # AGENTS.md added to existing instructions
        assert "my-rules.md" in config["instructions"]
        assert "AGENTS.md" in config["instructions"]
        # HERMES metadata added
        assert "_hermes" in config

    def test_handles_instructions_as_string(self, hermes_dir, opencode_target_dir):
        """OpenCode accepts instructions as string — adapter converts to list."""
        import json

        user_config = {"instructions": "my-rules.md"}
        (opencode_target_dir / "opencode.json").write_text(json.dumps(user_config))

        adapter = OpenCodeAdapter(hermes_dir=hermes_dir, target_dir=opencode_target_dir)
        adapter.adapt()

        config = json.loads((opencode_target_dir / "opencode.json").read_text())
        assert isinstance(config["instructions"], list)
        assert "my-rules.md" in config["instructions"]
        assert "AGENTS.md" in config["instructions"]

    def test_handles_corrupt_json(self, hermes_dir, opencode_target_dir):
        """Corrupt opencode.json is replaced with fresh config (not crash)."""
        (opencode_target_dir / "opencode.json").write_text("{invalid json!!!}")

        adapter = OpenCodeAdapter(hermes_dir=hermes_dir, target_dir=opencode_target_dir)
        result = adapter.adapt()

        assert result.success is True
        import json

        config = json.loads((opencode_target_dir / "opencode.json").read_text())
        assert config["$schema"] == "https://opencode.ai/config.json"
        assert "AGENTS.md" in config["instructions"]


# ─── OpenCodeAdapter peers ────────────────────────────────────────


class TestOpenCodeAdapterPeers:
    """Peer display in AGENTS.md."""

    def test_agents_md_includes_peers(self, hermes_dir_with_peers, opencode_target_dir):
        adapter = OpenCodeAdapter(hermes_dir=hermes_dir_with_peers, target_dir=opencode_target_dir)
        adapter.adapt()
        content = (opencode_target_dir / "AGENTS.md").read_text()
        assert "clan-jei" in content
        assert "established" in content

    def test_no_peers_section_when_empty(self, hermes_dir, opencode_target_dir):
        adapter = OpenCodeAdapter(hermes_dir=hermes_dir, target_dir=opencode_target_dir)
        adapter.adapt()
        content = (opencode_target_dir / "AGENTS.md").read_text()
        assert "## Peers" not in content


# ─── OpenCodeAdapter idempotency ──────────────────────────────────


class TestOpenCodeAdapterIdempotency:
    """OpenCode adapter is safe to run multiple times."""

    def test_run_twice_no_errors(self, hermes_dir_with_dims, opencode_target_dir):
        adapter = OpenCodeAdapter(hermes_dir=hermes_dir_with_dims, target_dir=opencode_target_dir)
        r1 = adapter.adapt()
        r2 = adapter.adapt()
        assert r1.success is True
        assert r2.success is True

    def test_run_twice_unchanged(self, hermes_dir_with_dims, opencode_target_dir):
        adapter = OpenCodeAdapter(hermes_dir=hermes_dir_with_dims, target_dir=opencode_target_dir)
        adapter.adapt()
        r2 = adapter.adapt()
        assert "AGENTS.md unchanged" in r2.steps
        assert "opencode.json unchanged" in r2.steps

    def test_preserves_user_content(self, hermes_dir, opencode_target_dir):
        """User content outside HERMES markers is preserved in AGENTS.md."""
        agents_md = opencode_target_dir / "AGENTS.md"
        agents_md.write_text(
            "# My Custom Instructions\n\nCustom rule 1.\n\n"
            "<!-- HERMES:BEGIN -->\nold hermes content\n<!-- HERMES:END -->\n\n"
            "# More User Rules\n\nCustom rule 2.\n"
        )
        adapter = OpenCodeAdapter(hermes_dir=hermes_dir, target_dir=opencode_target_dir)
        adapter.adapt()
        content = agents_md.read_text()
        # User content preserved
        assert "My Custom Instructions" in content
        assert "Custom rule 1" in content
        assert "More User Rules" in content
        assert "Custom rule 2" in content
        # HERMES content updated
        assert "clan-test" in content
        assert "old hermes content" not in content

    def test_symlinks_survive_rerun(self, hermes_dir_with_dims, opencode_target_dir):
        adapter = OpenCodeAdapter(hermes_dir=hermes_dir_with_dims, target_dir=opencode_target_dir)
        adapter.adapt()
        adapter.adapt()
        assert (opencode_target_dir / "skills" / "global" / "consejo").is_symlink()
        assert (opencode_target_dir / "skills" / "nymyka" / "niky-ceo").is_symlink()


# ─── OpenCodeAdapter error handling ───────────────────────────────


class TestOpenCodeAdapterErrors:
    """Error handling tests for OpenCode adapter."""

    def test_no_config_fails_gracefully(self, tmp_path):
        hdir = tmp_path / ".hermes"
        hdir.mkdir()
        tdir = tmp_path / ".config" / "opencode"
        tdir.mkdir(parents=True)
        adapter = OpenCodeAdapter(hermes_dir=hdir, target_dir=tdir)
        result = adapter.adapt()
        assert result.success is False
        assert any("Config error" in e for e in result.errors)

    def test_missing_hermes_dir(self, tmp_path):
        hdir = tmp_path / "nonexistent"
        tdir = tmp_path / ".config" / "opencode"
        tdir.mkdir(parents=True)
        adapter = OpenCodeAdapter(hermes_dir=hdir, target_dir=tdir)
        result = adapter.adapt()
        assert result.success is False

    def test_target_dir_created_if_missing(self, hermes_dir, tmp_path):
        tdir = tmp_path / "new_opencode_dir"
        adapter = OpenCodeAdapter(hermes_dir=hermes_dir, target_dir=tdir)
        result = adapter.adapt()
        assert result.success is True
        assert (tdir / "AGENTS.md").exists()
        assert (tdir / "opencode.json").exists()


# ─── OpenCodeAdapter defaults ─────────────────────────────────────


class TestOpenCodeAdapterDefaults:
    """Default path tests for OpenCode adapter."""

    def test_default_hermes_dir(self):
        adapter = OpenCodeAdapter()
        assert adapter.hermes_dir == Path.home() / ".hermes"

    def test_default_target_dir(self):
        adapter = OpenCodeAdapter()
        assert adapter.target_dir == Path.home() / ".config" / "opencode"

    def test_custom_dirs(self, tmp_path):
        hdir = tmp_path / "h"
        tdir = tmp_path / "t"
        adapter = OpenCodeAdapter(hermes_dir=hdir, target_dir=tdir)
        assert adapter.hermes_dir == hdir
        assert adapter.target_dir == tdir


# ─── Adapter registry (OpenCode) ─────────────────────────────────


class TestAdapterRegistryOpenCode:
    """Registry tests including OpenCode adapter."""

    def test_opencode_in_list(self):
        adapters = list_adapters()
        assert "opencode" in adapters

    def test_get_opencode_adapter(self):
        cls = get_adapter("opencode")
        assert cls is OpenCodeAdapter

    def test_run_opencode_adapter(self, hermes_dir, opencode_target_dir):
        result = run_adapter("opencode", hermes_dir=hermes_dir, target_dir=opencode_target_dir)
        assert result.success is True
        assert result.adapter_name == "opencode"


# ═══════════════════════════════════════════════════════════════════
# Gemini CLI Adapter Tests
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def gemini_target_dir(tmp_path):
    """Create target directory for Gemini CLI output."""
    tdir = tmp_path / ".gemini"
    tdir.mkdir()
    return tdir


# ─── GeminiCLIAdapter basic ──────────────────────────────────────


class TestGeminiCLIAdapterBasic:
    """Basic GeminiCLIAdapter tests with minimal config."""

    def test_adapt_success(self, hermes_dir, gemini_target_dir):
        adapter = GeminiCLIAdapter(hermes_dir=hermes_dir, target_dir=gemini_target_dir)
        result = adapter.adapt()
        assert result.success is True
        assert result.adapter_name == "gemini"
        assert len(result.steps) >= 3  # config + GEMINI.md + settings.json

    def test_generates_gemini_md(self, hermes_dir, gemini_target_dir):
        adapter = GeminiCLIAdapter(hermes_dir=hermes_dir, target_dir=gemini_target_dir)
        adapter.adapt()
        gemini_md = gemini_target_dir / "GEMINI.md"
        assert gemini_md.exists()
        content = gemini_md.read_text()
        assert "clan-test" in content
        assert "Test Clan" in content

    def test_gemini_md_contains_identity(self, hermes_dir, gemini_target_dir):
        adapter = GeminiCLIAdapter(hermes_dir=hermes_dir, target_dir=gemini_target_dir)
        adapter.adapt()
        content = (gemini_target_dir / "GEMINI.md").read_text()
        assert "Clan ID" in content
        assert "Protocol Version" in content

    def test_gemini_md_auto_generated_notice(self, hermes_dir, gemini_target_dir):
        adapter = GeminiCLIAdapter(hermes_dir=hermes_dir, target_dir=gemini_target_dir)
        adapter.adapt()
        content = (gemini_target_dir / "GEMINI.md").read_text()
        assert "Auto-generated" in content
        assert "hermes adapt gemini" in content

    def test_gemini_md_has_markers(self, hermes_dir, gemini_target_dir):
        adapter = GeminiCLIAdapter(hermes_dir=hermes_dir, target_dir=gemini_target_dir)
        adapter.adapt()
        content = (gemini_target_dir / "GEMINI.md").read_text()
        assert GeminiCLIAdapter.HEADER_MARKER in content
        assert GeminiCLIAdapter.FOOTER_MARKER in content


# ─── GeminiCLIAdapter skills ────────────────────────────────────


class TestGeminiCLIAdapterSkills:
    """Skill compilation and linking tests."""

    def test_compiles_skills_into_gemini_md(self, hermes_dir_with_dims, gemini_target_dir):
        adapter = GeminiCLIAdapter(hermes_dir=hermes_dir_with_dims, target_dir=gemini_target_dir)
        adapter.adapt()
        content = (gemini_target_dir / "GEMINI.md").read_text()
        assert "## Skills" in content
        assert "Consejo Skill" in content
        assert "Palas Skill" in content
        assert "Niky CEO" in content

    def test_symlinks_skills_with_dimension_subdirs(self, hermes_dir_with_dims, gemini_target_dir):
        adapter = GeminiCLIAdapter(hermes_dir=hermes_dir_with_dims, target_dir=gemini_target_dir)
        adapter.adapt()
        skills_dir = gemini_target_dir / "skills"
        assert (skills_dir / "global" / "consejo").is_symlink()
        assert (skills_dir / "global" / "palas").is_symlink()
        assert (skills_dir / "nymyka" / "niky-ceo").is_symlink()
        assert (skills_dir / "global" / "consejo" / "SKILL.md").read_text() == "# Consejo Skill\n"

    def test_no_skills_ok(self, hermes_dir, gemini_target_dir):
        adapter = GeminiCLIAdapter(hermes_dir=hermes_dir, target_dir=gemini_target_dir)
        result = adapter.adapt()
        assert result.success is True
        assert "No dimension skills found" in result.steps

    def test_reports_linked_count(self, hermes_dir_with_dims, gemini_target_dir):
        adapter = GeminiCLIAdapter(hermes_dir=hermes_dir_with_dims, target_dir=gemini_target_dir)
        result = adapter.adapt()
        skill_step = [s for s in result.steps if "Skills linked" in s]
        assert len(skill_step) == 1
        assert "3 skills" in skill_step[0]


# ─── GeminiCLIAdapter rules ─────────────────────────────────────


class TestGeminiCLIAdapterRules:
    """Rule compilation tests."""

    def test_compiles_rules_into_gemini_md(self, hermes_dir_with_dims, gemini_target_dir):
        adapter = GeminiCLIAdapter(hermes_dir=hermes_dir_with_dims, target_dir=gemini_target_dir)
        adapter.adapt()
        content = (gemini_target_dir / "GEMINI.md").read_text()
        assert "## Rules" in content
        assert "Firewall rules" in content
        assert "SOPs" in content

    def test_rules_grouped_by_dimension(self, hermes_dir_with_dims, gemini_target_dir):
        adapter = GeminiCLIAdapter(hermes_dir=hermes_dir_with_dims, target_dir=gemini_target_dir)
        adapter.adapt()
        content = (gemini_target_dir / "GEMINI.md").read_text()
        assert "Dimension: nymyka" in content


# ─── GeminiCLIAdapter bus ────────────────────────────────────────


class TestGeminiCLIAdapterBus:
    """Bus symlink tests for Gemini CLI."""

    def test_links_bus(self, hermes_dir_with_bus, gemini_target_dir):
        adapter = GeminiCLIAdapter(hermes_dir=hermes_dir_with_bus, target_dir=gemini_target_dir)
        adapter.adapt()
        bus_link = gemini_target_dir / "bus.jsonl"
        assert bus_link.is_symlink()
        assert "test message" in bus_link.read_text()

    def test_bus_resolves_to_hermes(self, hermes_dir_with_bus, gemini_target_dir):
        adapter = GeminiCLIAdapter(hermes_dir=hermes_dir_with_bus, target_dir=gemini_target_dir)
        adapter.adapt()
        bus_link = gemini_target_dir / "bus.jsonl"
        resolved = bus_link.resolve()
        assert ".hermes" in str(resolved)

    def test_no_bus_no_error(self, hermes_dir, gemini_target_dir):
        adapter = GeminiCLIAdapter(hermes_dir=hermes_dir, target_dir=gemini_target_dir)
        result = adapter.adapt()
        assert result.success is True
        assert "Bus symlink unchanged" in result.steps


# ─── GeminiCLIAdapter settings.json ──────────────────────────────


class TestGeminiCLIAdapterSettingsJson:
    """settings.json generation and merge tests."""

    def test_generates_settings_json(self, hermes_dir, gemini_target_dir):
        adapter = GeminiCLIAdapter(hermes_dir=hermes_dir, target_dir=gemini_target_dir)
        adapter.adapt()
        import json

        config = json.loads((gemini_target_dir / "settings.json").read_text())
        assert "context" in config
        assert "GEMINI.md" in config["context"]["fileName"]

    def test_json_has_hermes_metadata(self, hermes_dir, gemini_target_dir):
        adapter = GeminiCLIAdapter(hermes_dir=hermes_dir, target_dir=gemini_target_dir)
        adapter.adapt()
        import json

        config = json.loads((gemini_target_dir / "settings.json").read_text())
        assert config["_hermes"]["managed_by"] == "hermes adapt gemini"
        assert config["_hermes"]["clan_id"] == "clan-test"

    def test_merge_preserves_user_keys(self, hermes_dir, gemini_target_dir):
        """User-configured keys in settings.json are preserved during merge."""
        import json

        user_config = {
            "model": "gemini-2.5-pro",
            "sandbox": True,
            "theme": "dark",
            "context": {"fileName": ["MY_RULES.md"]},
        }
        (gemini_target_dir / "settings.json").write_text(json.dumps(user_config))

        adapter = GeminiCLIAdapter(hermes_dir=hermes_dir, target_dir=gemini_target_dir)
        adapter.adapt()

        config = json.loads((gemini_target_dir / "settings.json").read_text())
        # User keys preserved
        assert config["model"] == "gemini-2.5-pro"
        assert config["sandbox"] is True
        assert config["theme"] == "dark"
        # GEMINI.md added to existing fileName list
        assert "MY_RULES.md" in config["context"]["fileName"]
        assert "GEMINI.md" in config["context"]["fileName"]
        # HERMES metadata added
        assert "_hermes" in config

    def test_handles_filename_as_string(self, hermes_dir, gemini_target_dir):
        """Gemini CLI accepts fileName as string — adapter converts to list."""
        import json

        user_config = {"context": {"fileName": "MY_RULES.md"}}
        (gemini_target_dir / "settings.json").write_text(json.dumps(user_config))

        adapter = GeminiCLIAdapter(hermes_dir=hermes_dir, target_dir=gemini_target_dir)
        adapter.adapt()

        config = json.loads((gemini_target_dir / "settings.json").read_text())
        assert isinstance(config["context"]["fileName"], list)
        assert "MY_RULES.md" in config["context"]["fileName"]
        assert "GEMINI.md" in config["context"]["fileName"]

    def test_handles_corrupt_json(self, hermes_dir, gemini_target_dir):
        """Corrupt settings.json is replaced with fresh config (not crash)."""
        (gemini_target_dir / "settings.json").write_text("{invalid json!!!}")

        adapter = GeminiCLIAdapter(hermes_dir=hermes_dir, target_dir=gemini_target_dir)
        result = adapter.adapt()

        assert result.success is True
        import json

        config = json.loads((gemini_target_dir / "settings.json").read_text())
        assert "GEMINI.md" in config["context"]["fileName"]

    def test_handles_non_dict_context(self, hermes_dir, gemini_target_dir):
        """If context field is not a dict, it gets replaced."""
        import json

        user_config = {"context": "bad"}
        (gemini_target_dir / "settings.json").write_text(json.dumps(user_config))

        adapter = GeminiCLIAdapter(hermes_dir=hermes_dir, target_dir=gemini_target_dir)
        adapter.adapt()

        config = json.loads((gemini_target_dir / "settings.json").read_text())
        assert isinstance(config["context"], dict)
        assert "GEMINI.md" in config["context"]["fileName"]


# ─── GeminiCLIAdapter peers ──────────────────────────────────────


class TestGeminiCLIAdapterPeers:
    """Peer display in GEMINI.md."""

    def test_gemini_md_includes_peers(self, hermes_dir_with_peers, gemini_target_dir):
        adapter = GeminiCLIAdapter(hermes_dir=hermes_dir_with_peers, target_dir=gemini_target_dir)
        adapter.adapt()
        content = (gemini_target_dir / "GEMINI.md").read_text()
        assert "clan-jei" in content
        assert "established" in content

    def test_no_peers_section_when_empty(self, hermes_dir, gemini_target_dir):
        adapter = GeminiCLIAdapter(hermes_dir=hermes_dir, target_dir=gemini_target_dir)
        adapter.adapt()
        content = (gemini_target_dir / "GEMINI.md").read_text()
        assert "## Peers" not in content


# ─── GeminiCLIAdapter idempotency ────────────────────────────────


class TestGeminiCLIAdapterIdempotency:
    """Gemini CLI adapter is safe to run multiple times."""

    def test_run_twice_no_errors(self, hermes_dir_with_dims, gemini_target_dir):
        adapter = GeminiCLIAdapter(hermes_dir=hermes_dir_with_dims, target_dir=gemini_target_dir)
        r1 = adapter.adapt()
        r2 = adapter.adapt()
        assert r1.success is True
        assert r2.success is True

    def test_run_twice_unchanged(self, hermes_dir_with_dims, gemini_target_dir):
        adapter = GeminiCLIAdapter(hermes_dir=hermes_dir_with_dims, target_dir=gemini_target_dir)
        adapter.adapt()
        r2 = adapter.adapt()
        assert "GEMINI.md unchanged" in r2.steps
        assert "settings.json unchanged" in r2.steps

    def test_preserves_user_content(self, hermes_dir, gemini_target_dir):
        """User content outside HERMES markers is preserved in GEMINI.md."""
        gemini_md = gemini_target_dir / "GEMINI.md"
        gemini_md.write_text(
            "# My Project Context\n\nCustom instructions.\n\n"
            "<!-- HERMES:BEGIN -->\nold hermes content\n<!-- HERMES:END -->\n\n"
            "# More Context\n\nAdditional rules.\n"
        )
        adapter = GeminiCLIAdapter(hermes_dir=hermes_dir, target_dir=gemini_target_dir)
        adapter.adapt()
        content = gemini_md.read_text()
        assert "My Project Context" in content
        assert "Custom instructions" in content
        assert "More Context" in content
        assert "Additional rules" in content
        assert "clan-test" in content
        assert "old hermes content" not in content

    def test_symlinks_survive_rerun(self, hermes_dir_with_dims, gemini_target_dir):
        adapter = GeminiCLIAdapter(hermes_dir=hermes_dir_with_dims, target_dir=gemini_target_dir)
        adapter.adapt()
        adapter.adapt()
        assert (gemini_target_dir / "skills" / "global" / "consejo").is_symlink()
        assert (gemini_target_dir / "skills" / "nymyka" / "niky-ceo").is_symlink()


# ─── GeminiCLIAdapter error handling ─────────────────────────────


class TestGeminiCLIAdapterErrors:
    """Error handling tests for Gemini CLI adapter."""

    def test_no_config_fails_gracefully(self, tmp_path):
        hdir = tmp_path / ".hermes"
        hdir.mkdir()
        tdir = tmp_path / ".gemini"
        tdir.mkdir()
        adapter = GeminiCLIAdapter(hermes_dir=hdir, target_dir=tdir)
        result = adapter.adapt()
        assert result.success is False
        assert any("Config error" in e for e in result.errors)

    def test_missing_hermes_dir(self, tmp_path):
        hdir = tmp_path / "nonexistent"
        tdir = tmp_path / ".gemini"
        tdir.mkdir()
        adapter = GeminiCLIAdapter(hermes_dir=hdir, target_dir=tdir)
        result = adapter.adapt()
        assert result.success is False

    def test_target_dir_created_if_missing(self, hermes_dir, tmp_path):
        tdir = tmp_path / "new_gemini_dir"
        adapter = GeminiCLIAdapter(hermes_dir=hermes_dir, target_dir=tdir)
        result = adapter.adapt()
        assert result.success is True
        assert (tdir / "GEMINI.md").exists()
        assert (tdir / "settings.json").exists()


# ─── GeminiCLIAdapter defaults ───────────────────────────────────


class TestGeminiCLIAdapterDefaults:
    """Default path tests for Gemini CLI adapter."""

    def test_default_hermes_dir(self):
        adapter = GeminiCLIAdapter()
        assert adapter.hermes_dir == Path.home() / ".hermes"

    def test_default_target_dir(self):
        adapter = GeminiCLIAdapter()
        assert adapter.target_dir == Path.home() / ".gemini"

    def test_custom_dirs(self, tmp_path):
        hdir = tmp_path / "h"
        tdir = tmp_path / "t"
        adapter = GeminiCLIAdapter(hermes_dir=hdir, target_dir=tdir)
        assert adapter.hermes_dir == hdir
        assert adapter.target_dir == tdir


# ─── Adapter registry (Gemini) ──────────────────────────────────


class TestAdapterRegistryGemini:
    """Registry tests including Gemini CLI adapter."""

    def test_gemini_in_list(self):
        adapters = list_adapters()
        assert "gemini" in adapters

    def test_get_gemini_adapter(self):
        cls = get_adapter("gemini")
        assert cls is GeminiCLIAdapter

    def test_run_gemini_adapter(self, hermes_dir, gemini_target_dir):
        result = run_adapter("gemini", hermes_dir=hermes_dir, target_dir=gemini_target_dir)
        assert result.success is True
        assert result.adapter_name == "gemini"

    def test_four_adapters_registered(self):
        adapters = list_adapters()
        assert len(adapters) == 4
        assert set(adapters) == {"claude-code", "cursor", "gemini", "opencode"}
