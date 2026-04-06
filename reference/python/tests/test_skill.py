"""Tests for SkillLoader — SKILL.md parsing and system prompt generation."""

from __future__ import annotations

import pytest

from amaru.llm.skill import SkillLoader


@pytest.fixture
def loader():
    return SkillLoader()


# --- Loading mechanics ---


def test_load_from_file(tmp_path, loader):
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("---\nname: test-skill\ndescription: A test\n---\nBody here.")
    ctx = loader.load(skill_file)
    assert ctx.name == "test-skill"
    assert ctx.system_prompt == "Body here."


def test_load_from_directory(tmp_path, loader):
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("---\nname: dir-skill\n---\nDir body.")
    ctx = loader.load(tmp_path)
    assert ctx.name == "dir-skill"


def test_load_missing_file(tmp_path, loader):
    with pytest.raises(FileNotFoundError):
        loader.load(tmp_path / "nonexistent.md")


def test_load_missing_skill_in_dir(tmp_path, loader):
    with pytest.raises(FileNotFoundError):
        loader.load(tmp_path)


def test_source_path_stored(tmp_path, loader):
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("Body only.")
    ctx = loader.load(skill_file)
    assert ctx.source_path == str(skill_file)


# --- Frontmatter defaults ---


def test_no_frontmatter_defaults(tmp_path, loader):
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("Just body content.")
    ctx = loader.load(skill_dir)
    assert ctx.name == "my-skill"  # defaults to parent dir name
    assert ctx.model_hint == "sonnet"
    assert ctx.description == ""


def test_model_hint_default(tmp_path, loader):
    (tmp_path / "SKILL.md").write_text("---\nname: x\n---\nBody.")
    ctx = loader.load(tmp_path)
    assert ctx.model_hint == "sonnet"


def test_empty_file(tmp_path, loader):
    skill_dir = tmp_path / "empty-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("")
    ctx = loader.load(skill_dir)
    assert ctx.name == "empty-skill"
    assert ctx.system_prompt == ""


# --- Frontmatter field parsing ---


def test_full_frontmatter(tmp_path, loader):
    content = "---\nname: full\ndescription: Full skill\nmodel: opus\n---\nFull body."
    (tmp_path / "SKILL.md").write_text(content)
    ctx = loader.load(tmp_path)
    assert ctx.name == "full"
    assert ctx.description == "Full skill"
    assert ctx.model_hint == "opus"


def test_license_field(tmp_path, loader):
    (tmp_path / "SKILL.md").write_text("---\nname: lic\nlicense: MIT\n---\nBody.")
    ctx = loader.load(tmp_path)
    assert ctx.license == "MIT"


def test_compatibility_field(tmp_path, loader):
    (tmp_path / "SKILL.md").write_text("---\nname: compat\ncompatibility: Python 3.11+\n---\nBody.")
    ctx = loader.load(tmp_path)
    assert ctx.compatibility == "Python 3.11+"


def test_argument_hint(tmp_path, loader):
    (tmp_path / "SKILL.md").write_text("---\nname: ah\nargument-hint: issue number\n---\nBody.")
    ctx = loader.load(tmp_path)
    assert ctx.argument_hint == "issue number"


def test_unknown_fields_in_metadata(tmp_path, loader):
    (tmp_path / "SKILL.md").write_text("---\nname: meta\ncustom_field: hello\n---\nBody.")
    ctx = loader.load(tmp_path)
    assert ctx.metadata["custom_field"] == "hello"


# --- Frontmatter edge cases ---


def test_multiline_description(tmp_path, loader):
    content = "---\nname: ml\ndescription: >\n  Line one\n  Line two\n---\nBody."
    (tmp_path / "SKILL.md").write_text(content)
    ctx = loader.load(tmp_path)
    assert "Line one" in ctx.description
    assert "Line two" in ctx.description


def test_quoted_values_stripped(tmp_path, loader):
    (tmp_path / "SKILL.md").write_text('---\nname: "quoted-name"\n---\nBody.')
    ctx = loader.load(tmp_path)
    assert ctx.name == "quoted-name"


def test_colon_in_value(tmp_path, loader):
    (tmp_path / "SKILL.md").write_text(
        "---\nname: colon\ndescription: Has: colons: here\n---\nBody."
    )
    ctx = loader.load(tmp_path)
    assert ctx.description == "Has: colons: here"


def test_empty_frontmatter(tmp_path, loader):
    (tmp_path / "SKILL.md").write_text("---\n---\nBody after empty fm.")
    ctx = loader.load(tmp_path)
    # Empty frontmatter block is not recognized as valid YAML frontmatter
    # so the entire content (including ---\n---\n) becomes the body
    assert "Body after empty fm." in ctx.system_prompt


# --- Body handling ---


def test_frontmatter_only_no_body(tmp_path, loader):
    (tmp_path / "SKILL.md").write_text("---\nname: no-body\n---\n")
    ctx = loader.load(tmp_path)
    assert ctx.system_prompt == ""


def test_body_only(tmp_path, loader):
    skill_dir = tmp_path / "body-only"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("Just a body\nwith multiple lines.")
    ctx = loader.load(skill_dir)
    assert "Just a body" in ctx.system_prompt
    assert "multiple lines" in ctx.system_prompt


# --- to_system_prompt ---


def test_to_system_prompt_basic(tmp_path, loader):
    (tmp_path / "SKILL.md").write_text(
        "---\nname: prompt-test\ndescription: Desc\n---\nInstructions here."
    )
    ctx = loader.load(tmp_path)
    prompt = loader.to_system_prompt(ctx)
    assert "# Role: prompt-test" in prompt
    assert "## Description\nDesc" in prompt
    assert "## Instructions\nInstructions here." in prompt


def test_to_system_prompt_with_context(tmp_path, loader):
    (tmp_path / "SKILL.md").write_text("---\nname: ctx\n---\nBody.")
    ctx = loader.load(tmp_path)
    prompt = loader.to_system_prompt(ctx, context={"date": "2026-03-31", "dim": "amaru"})
    assert "## Context" in prompt
    assert "- date: 2026-03-31" in prompt
    assert "- dim: amaru" in prompt


def test_to_system_prompt_no_context(tmp_path, loader):
    (tmp_path / "SKILL.md").write_text("---\nname: noctx\n---\nBody.")
    ctx = loader.load(tmp_path)
    prompt = loader.to_system_prompt(ctx)
    assert "## Context" not in prompt
