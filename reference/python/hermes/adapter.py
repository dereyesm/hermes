"""HERMES Adapter — Agent-agnostic bridge between ~/.hermes/ and agent configs.

The adapter reads the canonical HERMES structure at ~/.hermes/ and generates
the configuration files each AI assistant expects. This module implements the
adapter contract defined in docs/architecture/installable-model.md.

Supported adapters:
    hermes adapt claude-code   — generates ~/.claude/ (symlinks + CLAUDE.md)
    hermes adapt cursor        — generates .cursorrules (compiled markdown)
    hermes adapt opencode      — generates ~/.config/opencode/ (AGENTS.md + opencode.json)
    hermes adapt gemini        — generates ~/.gemini/ (GEMINI.md + settings.json)
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from .config import GatewayConfig, load_config


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

    def _compile_skills(self) -> str:
        """Read and merge skill content from all dimensions.

        Returns compiled markdown string (empty if no skills found).
        Shared by adapters that compile skills into a single output file.
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
                    dim_skills.append(f"### {skill_dir.name}\n\n{content}")

            if dim_skills:
                parts.append(f"**Dimension: {dim_dir.name}**\n\n" + "\n\n".join(dim_skills))

        return "\n\n".join(parts)

    def _find_bus_source(self) -> Path | None:
        """Locate the HERMES bus file (TOML layout or legacy).

        Returns the path if found, None otherwise.
        """
        bus_source = self.hermes_dir / "bus" / "active.jsonl"
        if bus_source.exists():
            return bus_source
        bus_source = self.hermes_dir / "bus.jsonl"
        if bus_source.exists():
            return bus_source
        return None

    def _compile_rules(self) -> str:
        """Read and merge rule content from all dimensions.

        Returns compiled markdown string (empty if no rules found).
        Shared by adapters that compile rules into a single output file.
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
                dim_rules.append(f"### {rule_file.stem}\n\n{content}")

            if dim_rules:
                parts.append(f"**Dimension: {dim_dir.name}**\n\n" + "\n\n".join(dim_rules))

        return "\n\n".join(parts)

    def _generate_compiled_md(self, adapt_command: str) -> str:
        """Build compiled markdown content from config + skills + rules.

        Shared template for adapters that produce a single compiled file
        (Cursor .cursorrules, OpenCode AGENTS.md, etc.). Each adapter wraps
        this with its own marker/filename logic.

        Args:
            adapt_command: CLI command shown in the notice (e.g. "hermes adapt cursor").

        Returns:
            Compiled markdown string with identity, peers, skills, rules, footer.
        """
        assert self.config is not None

        sections = []

        # Auto-generated notice
        sections.append(
            f"# {self.config.display_name} — HERMES Protocol\n\n"
            f"> Auto-generated by `{adapt_command}`. "
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
                f"## Peers\n\n| Clan | Status | Added |\n|------|--------|-------|\n{peer_lines}"
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
            f"Run `{adapt_command}` to regenerate.\n"
            f"Source: `{self.hermes_dir}/config.toml`\n"
        )

        return "\n".join(sections)


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
                result.symlinks_created.append(str(self.target_dir / "sync" / "bus.jsonl"))
            else:
                result.steps.append("Bus symlink unchanged")
        except Exception as e:
            result.errors.append(f"Bus link failed: {e}")

        # 4. Link dimension skills
        try:
            skill_links = self._link_dimension_skills()
            if skill_links:
                result.steps.append(f"Skills linked ({len(skill_links)} skills)")
                result.symlinks_created.extend(skill_links)
            else:
                result.steps.append("No dimension skills found")
        except Exception as e:
            result.errors.append(f"Skills link failed: {e}")

        # 5. Link dimension rules
        try:
            rule_links = self._link_dimension_rules()
            if rule_links:
                result.steps.append(f"Rules linked ({len(rule_links)} files)")
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
                f"## Peers\n\n| Clan | Status | Added |\n|------|--------|-------|\n{rows}"
            )

        # Dimensions
        dims_dir = self.hermes_dir / "dimensions"
        if dims_dir.is_dir():
            dim_names = sorted(d.name for d in dims_dir.iterdir() if d.is_dir())
            if dim_names:
                dim_list = ", ".join(f"`{d}`" for d in dim_names)
                sections.append(f"## Dimensions\n\nActive dimensions: {dim_list}\n")

        # Bus location
        sections.append("## Bus\n\nMessages: `sync/bus.jsonl` (symlink to HERMES bus)\n")

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
                result.files_written.append(str(self.target_dir / ".cursorrules"))
            else:
                result.steps.append(".cursorrules unchanged")
        except Exception as e:
            result.errors.append(f".cursorrules generation failed: {e}")

        # 3. Link bus (optional)
        try:
            linked = self._link_bus()
            if linked:
                result.steps.append("Bus symlinked")
                result.symlinks_created.append(str(self.target_dir / ".cursor" / "bus.jsonl"))
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
        body = self._generate_compiled_md("hermes adapt cursor")
        content = self.HEADER_MARKER + "\n" + body + "\n" + self.FOOTER_MARKER + "\n"
        target = self.target_dir / ".cursorrules"

        # If file exists with non-HERMES content, preserve it
        if target.exists():
            existing = target.read_text(encoding="utf-8")
            if self.HEADER_MARKER in existing and self.FOOTER_MARKER in existing:
                before = existing[: existing.index(self.HEADER_MARKER)]
                after = existing[existing.index(self.FOOTER_MARKER) + len(self.FOOTER_MARKER) :]
                new_content = before + content + after.lstrip("\n")
                return _write_file_if_changed(target, new_content)

        return _write_file_if_changed(target, content)

    def _link_bus(self) -> bool:
        """Symlink bus.jsonl into .cursor/ directory.

        Returns True if the symlink was created/updated.
        """
        bus_source = self._find_bus_source()
        if bus_source is None:
            return False

        link_path = self.target_dir / ".cursor" / "bus.jsonl"
        return _safe_symlink(link_path, bus_source)


# ---------------------------------------------------------------------------
# OpenCode Adapter
# ---------------------------------------------------------------------------


class OpenCodeAdapter(AdapterBase):
    """Generates AGENTS.md + opencode.json from ~/.hermes/ for OpenCode CLI.

    OpenCode is an open-source AI coding agent (https://opencode.ai) supporting
    75+ LLM providers including Gemini, Claude, and OpenAI. This adapter bridges
    HERMES into OpenCode's configuration system.

    Output strategy is hybrid — compiled AGENTS.md (like Cursor) plus JSON config
    and skill symlinks (like Claude Code):

    Reads:
        ~/.hermes/config.toml     -> clan identity, peers
        ~/.hermes/dimensions/     -> skills, rules per dimension
        ~/.hermes/bus/active.jsonl -> bus messages (optional link)

    Writes:
        ~/.config/opencode/AGENTS.md      -> compiled markdown (HERMES markers)
        ~/.config/opencode/opencode.json  -> config with instructions ref (merge)
        ~/.config/opencode/skills/        -> symlinks to dimension skills
        ~/.config/opencode/bus.jsonl      -> symlink to HERMES bus

    The AGENTS.md format is compatible with the Agent Skills Open Standard
    (agentskills.io), enabling skill portability across Claude Code, Gemini CLI,
    Cursor, OpenCode, and 30+ other AI coding tools.

    Contract (per installable-model.md):
        - Idempotent (safe to re-run)
        - Never modifies HERMES state
        - Never bypasses firewall rules
        - Never hardcodes dimension names
    """

    name = "opencode"

    # Markers to delimit auto-generated sections in AGENTS.md
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
            target_dir = Path.home() / ".config" / "opencode"
        super().__init__(hermes_dir, target_dir)

    def adapt(self) -> AdaptResult:
        """Run full OpenCode adaptation."""
        result = AdaptResult(success=True, adapter_name=self.name)

        # 1. Load config
        try:
            self.load_config()
            result.steps.append(f"Config loaded from {self.hermes_dir}")
        except (FileNotFoundError, ValueError) as e:
            result.success = False
            result.errors.append(f"Config error: {e}")
            return result

        # 2. Generate AGENTS.md
        try:
            written = self._generate_agents_md()
            if written:
                result.steps.append("AGENTS.md generated")
                result.files_written.append(str(self.target_dir / "AGENTS.md"))
            else:
                result.steps.append("AGENTS.md unchanged")
        except Exception as e:
            result.errors.append(f"AGENTS.md generation failed: {e}")

        # 3. Generate/merge opencode.json
        try:
            written = self._generate_opencode_json()
            if written:
                result.steps.append("opencode.json generated")
                result.files_written.append(str(self.target_dir / "opencode.json"))
            else:
                result.steps.append("opencode.json unchanged")
        except Exception as e:
            result.errors.append(f"opencode.json generation failed: {e}")

        # 4. Link skills
        try:
            skill_links = self._link_skills()
            if skill_links:
                result.steps.append(f"Skills linked ({len(skill_links)} skills)")
                result.symlinks_created.extend(skill_links)
            else:
                result.steps.append("No dimension skills found")
        except Exception as e:
            result.errors.append(f"Skills link failed: {e}")

        # 5. Link bus (optional)
        try:
            linked = self._link_bus()
            if linked:
                result.steps.append("Bus symlinked")
                result.symlinks_created.append(str(self.target_dir / "bus.jsonl"))
            else:
                result.steps.append("Bus symlink unchanged")
        except Exception as e:
            result.errors.append(f"Bus link failed: {e}")

        if result.errors:
            result.success = False

        return result

    def _generate_agents_md(self) -> bool:
        """Generate AGENTS.md from config + compiled skills + rules.

        Uses HERMES:BEGIN/END markers to preserve user content outside
        the auto-generated section (same pattern as CursorAdapter).

        Returns True if the file was written/updated.
        """
        body = self._generate_compiled_md("hermes adapt opencode")
        content = self.HEADER_MARKER + "\n" + body + "\n" + self.FOOTER_MARKER + "\n"
        target = self.target_dir / "AGENTS.md"

        # If file exists with non-HERMES content, preserve it
        if target.exists():
            existing = target.read_text(encoding="utf-8")
            if self.HEADER_MARKER in existing and self.FOOTER_MARKER in existing:
                before = existing[: existing.index(self.HEADER_MARKER)]
                after = existing[existing.index(self.FOOTER_MARKER) + len(self.FOOTER_MARKER) :]
                new_content = before + content + after.lstrip("\n")
                return _write_file_if_changed(target, new_content)

        return _write_file_if_changed(target, content)

    def _generate_opencode_json(self) -> bool:
        """Generate or merge opencode.json with HERMES-managed fields.

        Only touches HERMES-controlled keys ($schema, instructions, _hermes).
        Preserves all user-configured keys (model, mcp, agents, etc.).

        Returns True if the file was written/updated.
        """
        assert self.config is not None

        target = self.target_dir / "opencode.json"

        # Load existing config if present
        existing: dict = {}
        if target.exists():
            try:
                existing = json.loads(target.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, ValueError):
                existing = {}

        # Schema reference
        existing.setdefault("$schema", "https://opencode.ai/config.json")

        # Point instructions to AGENTS.md (OpenCode accepts string or list)
        instructions = existing.get("instructions", [])
        if isinstance(instructions, str):
            instructions = [instructions] if instructions else []
        if "AGENTS.md" not in instructions:
            instructions.append("AGENTS.md")
        existing["instructions"] = instructions

        # HERMES metadata for idempotency tracking
        existing["_hermes"] = {
            "managed_by": "hermes adapt opencode",
            "clan_id": self.config.clan_id,
            "protocol_version": self.config.protocol_version,
        }

        content = json.dumps(existing, indent=2, ensure_ascii=False) + "\n"
        return _write_file_if_changed(target, content)

    def _link_skills(self) -> list[str]:
        """Symlink dimension skills into skills/<dim>/<name>/ directory.

        Uses subdirectories per dimension (like ClaudeCodeAdapter) so that
        the skill directory name matches the skill's ``name`` field — required
        by the Agent Skills Open Standard (agentskills.io).

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

            for skill_dir in sorted(skills_src.iterdir()):
                if not skill_dir.is_dir():
                    continue

                # Subdirectory per dimension avoids collisions while
                # keeping skill directory name == skill name (standard)
                link = skills_target / dim_dir.name / skill_dir.name
                if _safe_symlink(link, skill_dir):
                    created.append(str(link))

        return created

    def _link_bus(self) -> bool:
        """Symlink bus.jsonl into the OpenCode config directory.

        Returns True if the symlink was created/updated.
        """
        bus_source = self._find_bus_source()
        if bus_source is None:
            return False

        link_path = self.target_dir / "bus.jsonl"
        return _safe_symlink(link_path, bus_source)


# ---------------------------------------------------------------------------
# Gemini CLI Adapter
# ---------------------------------------------------------------------------


class GeminiCLIAdapter(AdapterBase):
    """Generates GEMINI.md + settings.json from ~/.hermes/ for Gemini CLI.

    Gemini CLI (https://github.com/google-gemini/gemini-cli) is Google's
    open-source AI agent for the terminal. It reads context from GEMINI.md
    files at both global (~/.gemini/) and project level, with settings.json
    for configuration.

    Output strategy mirrors OpenCode — compiled GEMINI.md with markers, JSON
    config merge for settings.json, skill symlinks, and optional bus link:

    Reads:
        ~/.hermes/config.toml     -> clan identity, peers
        ~/.hermes/dimensions/     -> skills, rules per dimension
        ~/.hermes/bus/active.jsonl -> bus messages (optional link)

    Writes:
        ~/.gemini/GEMINI.md       -> compiled markdown (HERMES markers)
        ~/.gemini/settings.json   -> config with context refs (merge)
        ~/.gemini/skills/         -> symlinks to dimension skills
        ~/.gemini/bus.jsonl       -> symlink to HERMES bus

    The GEMINI.md format is compatible with the Agent Skills Open Standard
    (agentskills.io), enabling skill portability across Claude Code, Gemini CLI,
    Cursor, OpenCode, and 30+ other AI coding tools.

    Contract (per installable-model.md):
        - Idempotent (safe to re-run)
        - Never modifies HERMES state
        - Never bypasses firewall rules
        - Never hardcodes dimension names
    """

    name = "gemini"

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
            target_dir = Path.home() / ".gemini"
        super().__init__(hermes_dir, target_dir)

    def adapt(self) -> AdaptResult:
        """Run full Gemini CLI adaptation."""
        result = AdaptResult(success=True, adapter_name=self.name)

        # 1. Load config
        try:
            self.load_config()
            result.steps.append(f"Config loaded from {self.hermes_dir}")
        except (FileNotFoundError, ValueError) as e:
            result.success = False
            result.errors.append(f"Config error: {e}")
            return result

        # 2. Generate GEMINI.md
        try:
            written = self._generate_gemini_md()
            if written:
                result.steps.append("GEMINI.md generated")
                result.files_written.append(str(self.target_dir / "GEMINI.md"))
            else:
                result.steps.append("GEMINI.md unchanged")
        except Exception as e:
            result.errors.append(f"GEMINI.md generation failed: {e}")

        # 3. Generate/merge settings.json
        try:
            written = self._generate_settings_json()
            if written:
                result.steps.append("settings.json generated")
                result.files_written.append(str(self.target_dir / "settings.json"))
            else:
                result.steps.append("settings.json unchanged")
        except Exception as e:
            result.errors.append(f"settings.json generation failed: {e}")

        # 4. Link skills
        try:
            skill_links = self._link_skills()
            if skill_links:
                result.steps.append(f"Skills linked ({len(skill_links)} skills)")
                result.symlinks_created.extend(skill_links)
            else:
                result.steps.append("No dimension skills found")
        except Exception as e:
            result.errors.append(f"Skills link failed: {e}")

        # 5. Link bus (optional)
        try:
            linked = self._link_bus()
            if linked:
                result.steps.append("Bus symlinked")
                result.symlinks_created.append(str(self.target_dir / "bus.jsonl"))
            else:
                result.steps.append("Bus symlink unchanged")
        except Exception as e:
            result.errors.append(f"Bus link failed: {e}")

        if result.errors:
            result.success = False

        return result

    def _generate_gemini_md(self) -> bool:
        """Generate GEMINI.md from config + compiled skills + rules.

        Uses HERMES:BEGIN/END markers to preserve user content outside
        the auto-generated section (same pattern as Cursor/OpenCode).

        Returns True if the file was written/updated.
        """
        body = self._generate_compiled_md("hermes adapt gemini")
        content = self.HEADER_MARKER + "\n" + body + "\n" + self.FOOTER_MARKER + "\n"
        target = self.target_dir / "GEMINI.md"

        if target.exists():
            existing = target.read_text(encoding="utf-8")
            if self.HEADER_MARKER in existing and self.FOOTER_MARKER in existing:
                before = existing[: existing.index(self.HEADER_MARKER)]
                after = existing[existing.index(self.FOOTER_MARKER) + len(self.FOOTER_MARKER) :]
                new_content = before + content + after.lstrip("\n")
                return _write_file_if_changed(target, new_content)

        return _write_file_if_changed(target, content)

    def _generate_settings_json(self) -> bool:
        """Generate or merge settings.json with HERMES-managed fields.

        Only touches HERMES-controlled keys (context, _hermes).
        Preserves all user-configured keys (model, sandbox, theme, etc.).

        Gemini CLI settings.json supports a ``context.fileName`` array that
        specifies which markdown files to load as context.  We ensure
        ``GEMINI.md`` is in that list so our compiled context is picked up.

        Returns True if the file was written/updated.
        """
        assert self.config is not None

        target = self.target_dir / "settings.json"

        existing: dict = {}
        if target.exists():
            try:
                existing = json.loads(target.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, ValueError):
                existing = {}

        # Ensure context.fileName includes GEMINI.md
        context = existing.get("context", {})
        if not isinstance(context, dict):
            context = {}
        file_names = context.get("fileName", [])
        if isinstance(file_names, str):
            file_names = [file_names] if file_names else []
        if "GEMINI.md" not in file_names:
            file_names.append("GEMINI.md")
        context["fileName"] = file_names
        existing["context"] = context

        # HERMES metadata for idempotency tracking
        existing["_hermes"] = {
            "managed_by": "hermes adapt gemini",
            "clan_id": self.config.clan_id,
            "protocol_version": self.config.protocol_version,
        }

        content = json.dumps(existing, indent=2, ensure_ascii=False) + "\n"
        return _write_file_if_changed(target, content)

    def _link_skills(self) -> list[str]:
        """Symlink dimension skills into skills/<dim>/<name>/ directory.

        Uses subdirectories per dimension (like Claude Code / OpenCode) so that
        the skill directory name matches the skill's ``name`` field — required
        by the Agent Skills Open Standard (agentskills.io).

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

            for skill_dir in sorted(skills_src.iterdir()):
                if not skill_dir.is_dir():
                    continue

                link = skills_target / dim_dir.name / skill_dir.name
                if _safe_symlink(link, skill_dir):
                    created.append(str(link))

        return created

    def _link_bus(self) -> bool:
        """Symlink bus.jsonl into the Gemini config directory.

        Returns True if the symlink was created/updated.
        """
        bus_source = self._find_bus_source()
        if bus_source is None:
            return False

        link_path = self.target_dir / "bus.jsonl"
        return _safe_symlink(link_path, bus_source)


# ---------------------------------------------------------------------------
# Registry of available adapters
# ---------------------------------------------------------------------------

ADAPTERS: dict[str, type[AdapterBase]] = {
    "claude-code": ClaudeCodeAdapter,
    "cursor": CursorAdapter,
    "opencode": OpenCodeAdapter,
    "gemini": GeminiCLIAdapter,
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
        raise KeyError(f"Unknown adapter '{name}'. Available: {', '.join(list_adapters())}")

    adapter = cls(hermes_dir=hermes_dir, target_dir=target_dir)  # type: ignore[arg-type]
    return adapter.adapt()
