"""SkillLoader — Reads SKILL.md and converts to universal system prompt.

This is the key piece: skills are markdown with YAML frontmatter.
The content (prompts, frameworks, deliberation) is 100% portable.
Only the invocation (/skill) is Claude Code-specific.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SkillContext:
    """Parsed skill ready for any LLM backend."""

    name: str
    description: str
    model_hint: str  # "opus", "sonnet", "haiku" — advisory, not binding
    argument_hint: str
    system_prompt: str  # The full markdown body as system prompt
    source_path: str
    metadata: dict = field(default_factory=dict)


class SkillLoader:
    """Reads SKILL.md files and produces LLM-agnostic SkillContext."""

    FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

    def load(self, skill_path: str | Path) -> SkillContext:
        path = Path(skill_path)
        if path.is_dir():
            path = path / "SKILL.md"

        text = path.read_text(encoding="utf-8")

        # Parse YAML frontmatter
        fm_match = self.FRONTMATTER_RE.match(text)
        frontmatter = {}
        body = text

        if fm_match:
            fm_text = fm_match.group(1)
            frontmatter = self._parse_frontmatter(fm_text)
            body = text[fm_match.end():]

        return SkillContext(
            name=frontmatter.get("name", path.parent.name),
            description=frontmatter.get("description", ""),
            model_hint=frontmatter.get("model", "sonnet"),
            argument_hint=frontmatter.get("argument-hint", ""),
            system_prompt=body.strip(),
            source_path=str(path),
            metadata=frontmatter,
        )

    def _parse_frontmatter(self, text: str) -> dict:
        """Simple YAML-like parser for frontmatter (no PyYAML dependency for core)."""
        result = {}
        current_key = None
        current_value = []

        for line in text.split("\n"):
            # Key: value on same line
            if ":" in line and not line.startswith(" ") and not line.startswith("\t"):
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
        """Convert skill to a universal system prompt string."""
        parts = [
            f"# Role: {skill.name}",
            f"## Description\n{skill.description}",
            f"## Instructions\n{skill.system_prompt}",
        ]

        if context:
            ctx_lines = [f"- {k}: {v}" for k, v in context.items()]
            parts.append(f"## Context\n" + "\n".join(ctx_lines))

        return "\n\n".join(parts)
