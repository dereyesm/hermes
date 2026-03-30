"""SkillLoader — Reads SKILL.md and converts to universal system prompt.

Skills are markdown with YAML-like frontmatter.  The content (prompts,
frameworks, deliberation) is 100% portable across LLM backends.
Only the invocation mechanism (e.g. /skill in Claude Code) is provider-specific.

Compatible with the Agent Skills Open Standard (agentskills.io).
Core fields (name, description) are shared across Claude Code, Gemini CLI,
Cursor, OpenCode, and 30+ AI coding tools. Provider-specific fields
(context, effort, hooks, temperature) are stored in metadata and
gracefully ignored by tools that don't support them.

No PyYAML dependency — uses a lightweight parser for the frontmatter subset
that HERMES skills actually use.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SkillContext:
    """Parsed skill ready for any LLM backend.

    Core fields follow the Agent Skills Open Standard (agentskills.io):
      - name: skill identifier (max 64 chars, lowercase+hyphens)
      - description: what the skill does (max 1024 chars)
      - license: optional license identifier (e.g. "MIT", "Apache-2.0")
      - compatibility: optional environment requirements (e.g. "Python 3.11+")

    Additional fields are HERMES extensions stored in metadata.
    """

    name: str
    description: str
    model_hint: str  # "opus", "sonnet", "haiku" — advisory, not binding
    argument_hint: str
    system_prompt: str  # The full markdown body as system prompt
    source_path: str
    license: str  # Agent Skills Standard: optional license identifier
    compatibility: str  # Agent Skills Standard: environment requirements
    metadata: dict = field(default_factory=dict)


class SkillLoader:
    """Reads SKILL.md files and produces LLM-agnostic SkillContext objects."""

    FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

    def load(self, skill_path: str | Path) -> SkillContext:
        """Load a skill from a SKILL.md file or directory containing one."""
        path = Path(skill_path)
        if path.is_dir():
            path = path / "SKILL.md"

        if not path.exists():
            raise FileNotFoundError(f"Skill file not found: {path}")

        text = path.read_text(encoding="utf-8")

        fm_match = self.FRONTMATTER_RE.match(text)
        frontmatter: dict = {}
        body = text

        if fm_match:
            fm_text = fm_match.group(1)
            frontmatter = self._parse_frontmatter(fm_text)
            body = text[fm_match.end() :]

        return SkillContext(
            name=frontmatter.get("name", path.parent.name),
            description=frontmatter.get("description", ""),
            model_hint=frontmatter.get("model", "sonnet"),
            argument_hint=frontmatter.get("argument-hint", ""),
            system_prompt=body.strip(),
            source_path=str(path),
            license=frontmatter.get("license", ""),
            compatibility=frontmatter.get("compatibility", ""),
            metadata=frontmatter,
        )

    def _parse_frontmatter(self, text: str) -> dict:
        """Simple YAML-like parser for the frontmatter subset used by HERMES skills."""
        result: dict[str, str] = {}
        current_key: str | None = None
        current_value: list[str] = []

        for line in text.split("\n"):
            if ":" in line and not line.startswith((" ", "\t")):
                if current_key and current_value:
                    result[current_key] = " ".join(current_value).strip()
                parts = line.split(":", 1)
                current_key = parts[0].strip()
                val = parts[1].strip()
                if val and not val.startswith(">"):
                    result[current_key] = val.strip('"').strip("'")
                    current_key = None
                    current_value = []
                else:
                    current_value = []
            elif current_key:
                current_value.append(line.strip())

        if current_key and current_value:
            result[current_key] = " ".join(current_value).strip()

        return result

    def to_system_prompt(self, skill: SkillContext, context: dict | None = None) -> str:
        """Convert skill to a universal system prompt string.

        Args:
            skill: Parsed SkillContext.
            context: Optional key-value pairs injected as a Context section.
        """
        parts = [
            f"# Role: {skill.name}",
            f"## Description\n{skill.description}",
            f"## Instructions\n{skill.system_prompt}",
        ]

        if context:
            ctx_lines = [f"- {k}: {v}" for k, v in context.items()]
            parts.append("## Context\n" + "\n".join(ctx_lines))

        return "\n\n".join(parts)
