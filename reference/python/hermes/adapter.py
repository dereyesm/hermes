"""HERMES Adapter — Agent-agnostic bridge between ~/.hermes/ and agent configs.

The adapter reads the canonical HERMES structure at ~/.hermes/ and generates
the configuration files each AI assistant expects. This module implements the
adapter contract defined in docs/architecture/installable-model.md.

Usage:
    hermes adapt claude-code [--hermes-dir PATH] [--target-dir PATH]
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import GatewayConfig, load_config, resolve_config_path


@dataclass
class AdaptResult:
    """Result of an adapter run."""

    success: bool
    adapter_name: str
    steps: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    files_written: list[str] = field(default_factory=list)
    symlinks_created: list[str] = field(default_factory=list)


class AdapterBase(ABC):
    """Abstract base for agent adapters.

    An adapter reads ~/.hermes/ and generates the config structure
    that a specific AI assistant expects.
    """

    name: str = "base"

    def __init__(self, hermes_dir: Path, target_dir: Path) -> None:
        self.hermes_dir = Path(hermes_dir)
        self.target_dir = Path(target_dir)
        self.config: GatewayConfig | None = None

    def load_config(self) -> GatewayConfig:
        """Load HERMES config from hermes_dir (auto-discovery)."""
        self.config = load_config(self.hermes_dir)
        return self.config

    @abstractmethod
    def adapt(self) -> AdaptResult:
        """Run the adapter. Must be idempotent."""
        ...


def _safe_symlink(link: Path, target: Path) -> bool:
    """Create or update a symlink atomically.

    Returns True if the symlink was created/updated, False if already correct.
    """
    target = target.resolve()

    if link.is_symlink():
        if link.resolve() == target:
            return False
        link.unlink()
    elif link.exists():
        link.unlink()

    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target)
    return True


def _write_file_if_changed(path: Path, content: str) -> bool:
    """Write content to file only if it differs from current content.

    Returns True if the file was written, False if unchanged.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == content:
            return False

    path.write_text(content, encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Claude Code Adapter
# ---------------------------------------------------------------------------


class ClaudeCodeAdapter(AdapterBase):
    """Generates ~/.claude/ structure from ~/.hermes/.

    Reads:
        ~/.hermes/config.toml     -> clan identity, peers, firewall
        ~/.hermes/dimensions/     -> skills, rules per dimension
        ~/.hermes/bus/active.jsonl -> bus messages

    Writes:
        ~/.claude/CLAUDE.md       -> generated from config + dimensions
        ~/.claude/sync/bus.jsonl  -> symlink to .hermes/bus/active.jsonl
        ~/.claude/skills/         -> symlinks to dimension skills

    Contract (per installable-model.md):
        - Idempotent (safe to re-run)
        - Never modifies HERMES state
        - Never bypasses firewall rules
        - Never hardcodes dimension names
    """

    name = "claude-code"

    def __init__(
        self,
        hermes_dir: Path | None = None,
        target_dir: Path | None = None,
    ) -> None:
        if hermes_dir is None:
            hermes_dir = Path.home() / ".hermes"
        if target_dir is None:
            target_dir = Path.home() / ".claude"
        super().__init__(hermes_dir, target_dir)

    def adapt(self) -> AdaptResult:
        """Run full Claude Code adaptation."""
        result = AdaptResult(success=True, adapter_name=self.name)

        # 1. Load config
        try:
            self.load_config()
            result.steps.append(f"Config loaded from {self.hermes_dir}")
        except (FileNotFoundError, ValueError) as e:
            result.success = False
            result.errors.append(f"Config error: {e}")
            return result

        # 2. Generate CLAUDE.md
        try:
            written = self._generate_claude_md()
            if written:
                result.steps.append("CLAUDE.md generated")
                result.files_written.append(str(self.target_dir / "CLAUDE.md"))
            else:
                result.steps.append("CLAUDE.md unchanged")
        except Exception as e:
            result.errors.append(f"CLAUDE.md generation failed: {e}")

        # 3. Link bus
        try:
            linked = self._link_bus()
            if linked:
                result.steps.append("Bus symlinked")
                result.symlinks_created.append(
                    str(self.target_dir / "sync" / "bus.jsonl")
                )
            else:
                result.steps.append("Bus symlink unchanged")
        except Exception as e:
            result.errors.append(f"Bus link failed: {e}")

        # 4. Link dimension skills
        try:
            skill_links = self._link_dimension_skills()
            if skill_links:
                result.steps.append(
                    f"Skills linked ({len(skill_links)} skills)"
                )
                result.symlinks_created.extend(skill_links)
            else:
                result.steps.append("No dimension skills found")
        except Exception as e:
            result.errors.append(f"Skills link failed: {e}")

        # 5. Link dimension rules
        try:
            rule_links = self._link_dimension_rules()
            if rule_links:
                result.steps.append(
                    f"Rules linked ({len(rule_links)} files)"
                )
                result.symlinks_created.extend(rule_links)
            else:
                result.steps.append("No dimension rules found")
        except Exception as e:
            result.errors.append(f"Rules link failed: {e}")

        if result.errors:
            result.success = False

        return result

    def _generate_claude_md(self) -> bool:
        """Generate CLAUDE.md from config + dimension states.

        Returns True if the file was written/updated.
        """
        assert self.config is not None

        sections = []

        # Header
        sections.append(
            f"# {self.config.display_name} — HERMES Protocol\n\n"
            f"> Auto-generated by `hermes adapt claude-code`. "
            f"Do not edit manually.\n"
        )

        # Clan identity
        sections.append(
            f"## Clan Identity\n\n"
            f"| Field | Value |\n"
            f"|-------|-------|\n"
            f"| Clan ID | `{self.config.clan_id}` |\n"
            f"| Display Name | {self.config.display_name} |\n"
            f"| Protocol Version | {self.config.protocol_version} |\n"
        )

        # Peers
        if self.config.peers:
            rows = ""
            for p in self.config.peers:
                rows += f"| `{p.clan_id}` | {p.status} | {p.added} |\n"
            sections.append(
                f"## Peers\n\n"
                f"| Clan | Status | Added |\n"
                f"|------|--------|-------|\n"
                f"{rows}"
            )

        # Dimensions
        dims_dir = self.hermes_dir / "dimensions"
        if dims_dir.is_dir():
            dim_names = sorted(
                d.name for d in dims_dir.iterdir() if d.is_dir()
            )
            if dim_names:
                dim_list = ", ".join(f"`{d}`" for d in dim_names)
                sections.append(
                    f"## Dimensions\n\n"
                    f"Active dimensions: {dim_list}\n"
                )

        # Bus location
        sections.append(
            f"## Bus\n\n"
            f"Messages: `sync/bus.jsonl` (symlink to HERMES bus)\n"
        )

        # Footer
        sections.append(
            f"## HERMES\n\n"
            f"This configuration is managed by HERMES. "
            f"Run `hermes adapt claude-code` to regenerate.\n"
            f"Source: `{self.hermes_dir}/config.toml`\n"
        )

        content = "\n".join(sections)
        target = self.target_dir / "CLAUDE.md"
        return _write_file_if_changed(target, content)

    def _link_bus(self) -> bool:
        """Symlink bus.jsonl into the Claude Code sync directory.

        Returns True if the symlink was created/updated.
        """
        # Try bus/active.jsonl (TOML layout) then bus.jsonl (legacy)
        bus_source = self.hermes_dir / "bus" / "active.jsonl"
        if not bus_source.exists():
            bus_source = self.hermes_dir / "bus.jsonl"
        if not bus_source.exists():
            # Create empty bus file in canonical location
            bus_source = self.hermes_dir / "bus" / "active.jsonl"
            bus_source.parent.mkdir(parents=True, exist_ok=True)
            bus_source.touch()

        link_path = self.target_dir / "sync" / "bus.jsonl"
        return _safe_symlink(link_path, bus_source)

    def _link_dimension_skills(self) -> list[str]:
        """Symlink dimension skills into ~/.claude/skills/.

        Returns list of created symlink paths.
        """
        dims_dir = self.hermes_dir / "dimensions"
        if not dims_dir.is_dir():
            return []

        created = []
        skills_target = self.target_dir / "skills"

        for dim_dir in sorted(dims_dir.iterdir()):
            if not dim_dir.is_dir():
                continue

            skills_src = dim_dir / "skills"
            if not skills_src.is_dir():
                continue

            # Each skill inside the dimension gets its own symlink
            for skill_dir in sorted(skills_src.iterdir()):
                if not skill_dir.is_dir():
                    continue

                link = skills_target / dim_dir.name / skill_dir.name
                if _safe_symlink(link, skill_dir):
                    created.append(str(link))

        return created

    def _link_dimension_rules(self) -> list[str]:
        """Symlink dimension rules into ~/.claude/rules/.

        Returns list of created symlink paths.
        """
        dims_dir = self.hermes_dir / "dimensions"
        if not dims_dir.is_dir():
            return []

        created = []
        rules_target = self.target_dir / "rules"

        for dim_dir in sorted(dims_dir.iterdir()):
            if not dim_dir.is_dir():
                continue

            rules_src = dim_dir / "rules"
            if not rules_src.is_dir():
                continue

            # Each rule file gets a symlink with dimension prefix
            for rule_file in sorted(rules_src.iterdir()):
                if not rule_file.is_file():
                    continue

                # Prefix with dimension name to avoid collisions
                link_name = f"{dim_dir.name}-{rule_file.name}"
                link = rules_target / link_name
                if _safe_symlink(link, rule_file):
                    created.append(str(link))

        return created


# ---------------------------------------------------------------------------
# Cursor Adapter
# ---------------------------------------------------------------------------


class CursorAdapter(AdapterBase):
    """Generates .cursorrules from ~/.hermes/ for Cursor AI editor.

    Unlike Claude Code (which uses a directory of symlinks), Cursor expects
    a single .cursorrules file at the project root. This adapter compiles
    dimension skills and rules into that file.

    Reads:
        ~/.hermes/config.toml     -> clan identity, peers
        ~/.hermes/dimensions/     -> skills, rules per dimension
        ~/.hermes/bus/active.jsonl -> bus messages (optional link)

    Writes:
        <project>/.cursorrules       -> compiled markdown from config+skills+rules
        <project>/.cursor/bus.jsonl  -> symlink to HERMES bus (optional)

    Contract (per installable-model.md):
        - Idempotent (safe to re-run)
        - Never modifies HERMES state
        - Never bypasses firewall rules
        - Never hardcodes dimension names
    """

    name = "cursor"

    # Markers to delimit auto-generated sections
    HEADER_MARKER = "<!-- HERMES:BEGIN -->"
    FOOTER_MARKER = "<!-- HERMES:END -->"

    def __init__(
        self,
        hermes_dir: Path | None = None,
        target_dir: Path | None = None,
    ) -> None:
        if hermes_dir is None:
            hermes_dir = Path.home() / ".hermes"
        if target_dir is None:
            target_dir = Path.cwd()
        super().__init__(hermes_dir, target_dir)

    def adapt(self) -> AdaptResult:
        """Run full Cursor adaptation."""
        result = AdaptResult(success=True, adapter_name=self.name)

        # 1. Load config
        try:
            self.load_config()
            result.steps.append(f"Config loaded from {self.hermes_dir}")
        except (FileNotFoundError, ValueError) as e:
            result.success = False
            result.errors.append(f"Config error: {e}")
            return result

        # 2. Generate .cursorrules
        try:
            written = self._generate_cursorrules()
            if written:
                result.steps.append(".cursorrules generated")
                result.files_written.append(
                    str(self.target_dir / ".cursorrules")
                )
            else:
                result.steps.append(".cursorrules unchanged")
        except Exception as e:
            result.errors.append(f".cursorrules generation failed: {e}")

        # 3. Link bus (optional)
        try:
            linked = self._link_bus()
            if linked:
                result.steps.append("Bus symlinked")
                result.symlinks_created.append(
                    str(self.target_dir / ".cursor" / "bus.jsonl")
                )
            else:
                result.steps.append("Bus symlink unchanged")
        except Exception as e:
            result.errors.append(f"Bus link failed: {e}")

        if result.errors:
            result.success = False

        return result

    def _generate_cursorrules(self) -> bool:
        """Generate .cursorrules from config + compiled skills + rules.

        Returns True if the file was written/updated.
        """
        assert self.config is not None

        sections = []

        # Header marker
        sections.append(self.HEADER_MARKER)

        # Auto-generated notice
        sections.append(
            f"# {self.config.display_name} — HERMES Protocol\n\n"
            f"> Auto-generated by `hermes adapt cursor`. "
            f"Do not edit between HERMES markers.\n"
        )

        # Clan identity
        sections.append(
            f"## Clan Identity\n\n"
            f"- **Clan ID**: `{self.config.clan_id}`\n"
            f"- **Display Name**: {self.config.display_name}\n"
            f"- **Protocol Version**: {self.config.protocol_version}\n"
        )

        # Peers
        if self.config.peers:
            peer_lines = ""
            for p in self.config.peers:
                peer_lines += f"| `{p.clan_id}` | {p.status} | {p.added} |\n"
            sections.append(
                f"## Peers\n\n"
                f"| Clan | Status | Added |\n"
                f"|------|--------|-------|\n"
                f"{peer_lines}"
            )

        # Compiled skills
        skills_content = self._compile_skills()
        if skills_content:
            sections.append(f"## Skills\n\n{skills_content}")

        # Compiled rules
        rules_content = self._compile_rules()
        if rules_content:
            sections.append(f"## Rules\n\n{rules_content}")

        # Footer
        sections.append(
            f"## HERMES\n\n"
            f"This configuration is managed by HERMES. "
            f"Run `hermes adapt cursor` to regenerate.\n"
            f"Source: `{self.hermes_dir}/config.toml`\n"
        )

        # Footer marker
        sections.append(self.FOOTER_MARKER)

        content = "\n".join(sections) + "\n"
        target = self.target_dir / ".cursorrules"

        # If file exists with non-HERMES content, preserve it
        if target.exists():
            existing = target.read_text(encoding="utf-8")
            if self.HEADER_MARKER in existing and self.FOOTER_MARKER in existing:
                # Replace only the HERMES section
                before = existing[: existing.index(self.HEADER_MARKER)]
                after = existing[
                    existing.index(self.FOOTER_MARKER) + len(self.FOOTER_MARKER) :
                ]
                # Strip trailing newline from after to avoid double newlines
                new_content = before + content + after.lstrip("\n")
                return _write_file_if_changed(target, new_content)

        return _write_file_if_changed(target, content)

    def _compile_skills(self) -> str:
        """Read and merge skill content from all dimensions.

        Returns compiled markdown string (empty if no skills found).
        """
        dims_dir = self.hermes_dir / "dimensions"
        if not dims_dir.is_dir():
            return ""

        parts = []
        for dim_dir in sorted(dims_dir.iterdir()):
            if not dim_dir.is_dir():
                continue

            skills_src = dim_dir / "skills"
            if not skills_src.is_dir():
                continue

            dim_skills = []
            for skill_dir in sorted(skills_src.iterdir()):
                if not skill_dir.is_dir():
                    continue

                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    content = skill_md.read_text(encoding="utf-8").strip()
                    dim_skills.append(
                        f"### {skill_dir.name}\n\n{content}"
                    )

            if dim_skills:
                parts.append(
                    f"**Dimension: {dim_dir.name}**\n\n"
                    + "\n\n".join(dim_skills)
                )

        return "\n\n".join(parts)

    def _compile_rules(self) -> str:
        """Read and merge rule content from all dimensions.

        Returns compiled markdown string (empty if no rules found).
        """
        dims_dir = self.hermes_dir / "dimensions"
        if not dims_dir.is_dir():
            return ""

        parts = []
        for dim_dir in sorted(dims_dir.iterdir()):
            if not dim_dir.is_dir():
                continue

            rules_src = dim_dir / "rules"
            if not rules_src.is_dir():
                continue

            dim_rules = []
            for rule_file in sorted(rules_src.iterdir()):
                if not rule_file.is_file():
                    continue

                content = rule_file.read_text(encoding="utf-8").strip()
                dim_rules.append(
                    f"### {rule_file.stem}\n\n{content}"
                )

            if dim_rules:
                parts.append(
                    f"**Dimension: {dim_dir.name}**\n\n"
                    + "\n\n".join(dim_rules)
                )

        return "\n\n".join(parts)

    def _link_bus(self) -> bool:
        """Symlink bus.jsonl into .cursor/ directory.

        Returns True if the symlink was created/updated.
        """
        bus_source = self.hermes_dir / "bus" / "active.jsonl"
        if not bus_source.exists():
            bus_source = self.hermes_dir / "bus.jsonl"
        if not bus_source.exists():
            return False

        link_path = self.target_dir / ".cursor" / "bus.jsonl"
        return _safe_symlink(link_path, bus_source)


# ---------------------------------------------------------------------------
# Registry of available adapters
# ---------------------------------------------------------------------------

ADAPTERS: dict[str, type[AdapterBase]] = {
    "claude-code": ClaudeCodeAdapter,
    "cursor": CursorAdapter,
}


def list_adapters() -> list[str]:
    """Return names of all registered adapters."""
    return sorted(ADAPTERS.keys())


def get_adapter(name: str) -> type[AdapterBase] | None:
    """Look up an adapter class by name."""
    return ADAPTERS.get(name)


def run_adapter(
    name: str,
    hermes_dir: Path | None = None,
    target_dir: Path | None = None,
) -> AdaptResult:
    """Instantiate and run a named adapter.

    Raises KeyError if the adapter name is not registered.
    """
    cls = ADAPTERS.get(name)
    if cls is None:
        raise KeyError(
            f"Unknown adapter '{name}'. Available: {', '.join(list_adapters())}"
        )

    adapter = cls(hermes_dir=hermes_dir, target_dir=target_dir)
    return adapter.adapt()
