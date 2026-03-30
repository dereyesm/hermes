"""Tests for hermes.llm — Multi-LLM adapter layer."""

from __future__ import annotations

import os
import textwrap
from unittest.mock import patch

import pytest

from hermes.config import GatewayConfig, LLMBackendConfig, load_config, save_config
from hermes.llm.adapters import (
    AdapterManager,
    ClaudeAdapter,
    GeminiAdapter,
    LLMAdapter,
    LLMResponse,
    create_adapter,
)
from hermes.llm.skill import SkillContext, SkillLoader

# ─── LLMResponse ────────────────────────────────────────────────


class TestLLMResponse:
    def test_basic_fields(self):
        r = LLMResponse(text="hello", backend="test", model="test-1")
        assert r.text == "hello"
        assert r.backend == "test"
        assert r.model == "test-1"
        assert r.usage is None

    def test_with_usage(self):
        r = LLMResponse(
            text="hi", backend="x", model="y", usage={"input_tokens": 5, "output_tokens": 3}
        )
        assert r.usage["input_tokens"] == 5
        assert r.usage["output_tokens"] == 3


# ─── create_adapter factory ─────────────────────────────────────


class TestCreateAdapter:
    def test_unknown_backend(self):
        with pytest.raises(ValueError, match="Unknown LLM backend"):
            create_adapter("openai")

    def test_gemini_no_key(self):
        with patch.dict(os.environ, {}, clear=True):
            # Remove GEMINI_API_KEY if present
            os.environ.pop("GEMINI_API_KEY", None)
            with pytest.raises(ValueError, match="API key not found"):
                create_adapter("gemini")

    def test_claude_no_key(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            with pytest.raises(ValueError, match="API key not found"):
                create_adapter("claude")

    @patch("hermes.llm.adapters.GeminiAdapter.__init__", return_value=None)
    def test_gemini_factory(self, mock_init):
        adapter = create_adapter("gemini", api_key="test-key", model="gemini-pro")
        assert isinstance(adapter, GeminiAdapter)

    @patch("hermes.llm.adapters.ClaudeAdapter.__init__", return_value=None)
    def test_claude_factory(self, mock_init):
        adapter = create_adapter("claude", api_key="test-key")
        assert isinstance(adapter, ClaudeAdapter)


# ─── GeminiAdapter ──────────────────────────────────────────────


class TestGeminiAdapter:
    def test_missing_sdk(self):
        with (
            patch.dict("sys.modules", {"google": None, "google.genai": None}),
            pytest.raises((ImportError, ValueError)),
        ):
            GeminiAdapter(api_key="test-key")

    def test_env_var_resolution(self):
        with (
            patch.dict(os.environ, {"MY_GEMINI_KEY": "fake-key"}),
            patch("hermes.llm.adapters.GeminiAdapter.__init__", return_value=None),
        ):
            key = os.environ.get("MY_GEMINI_KEY", "")
            assert key == "fake-key"

    @patch("hermes.llm.adapters.GeminiAdapter.__init__", return_value=None)
    def test_name(self, mock_init):
        adapter = GeminiAdapter.__new__(GeminiAdapter)
        adapter._model_name = "gemini-2.5-flash"
        assert adapter.name() == "gemini/gemini-2.5-flash"


# ─── ClaudeAdapter ──────────────────────────────────────────────


class TestClaudeAdapter:
    def test_missing_sdk(self):
        with (
            patch.dict("sys.modules", {"anthropic": None}),
            pytest.raises((ImportError, ValueError)),
        ):
            ClaudeAdapter(api_key="test-key")

    @patch("hermes.llm.adapters.ClaudeAdapter.__init__", return_value=None)
    def test_name(self, mock_init):
        adapter = ClaudeAdapter.__new__(ClaudeAdapter)
        adapter._model = "claude-sonnet-4-6"
        assert adapter.name() == "claude/claude-sonnet-4-6"


# ─── AdapterManager ────────────────────────────────────────────


class _MockAdapter(LLMAdapter):
    """Test adapter that doesn't call any API."""

    def __init__(self, adapter_name: str = "mock/test-1", healthy: bool = True):
        self._name = adapter_name
        self._healthy = healthy

    def complete(
        self, system_prompt: str, user_message: str, max_tokens: int = 4096
    ) -> LLMResponse:
        return LLMResponse(text="mock response", backend="mock", model="test-1")

    def name(self) -> str:
        return self._name

    def health_check(self) -> bool:
        return self._healthy


class TestAdapterManager:
    def test_empty_manager(self):
        mgr = AdapterManager()
        assert mgr.get_healthy() is None
        assert mgr.list_backends() == []

    def test_add_and_list(self):
        mgr = AdapterManager()
        mgr.add(_MockAdapter("mock/a"))
        mgr.add(_MockAdapter("mock/b"))
        assert len(mgr.list_backends()) == 2

    def test_get_healthy_priority(self):
        unhealthy = _MockAdapter("mock/first", healthy=False)
        healthy = _MockAdapter("mock/second", healthy=True)
        mgr = AdapterManager([unhealthy, healthy])
        assert mgr.get_healthy().name() == "mock/second"

    def test_get_by_name(self):
        a1 = _MockAdapter("gemini/flash")
        a2 = _MockAdapter("claude/sonnet")
        mgr = AdapterManager([a1, a2])
        assert mgr.get_by_name("claude").name() == "claude/sonnet"
        assert mgr.get_by_name("gemini").name() == "gemini/flash"
        assert mgr.get_by_name("openai") is None

    def test_all_unhealthy(self):
        a1 = _MockAdapter("mock/a", healthy=False)
        a2 = _MockAdapter("mock/b", healthy=False)
        mgr = AdapterManager([a1, a2])
        assert mgr.get_healthy() is None

    def test_backends_property(self):
        a = _MockAdapter("mock/a")
        mgr = AdapterManager([a])
        assert len(mgr.backends) == 1
        assert mgr.backends[0].name() == "mock/a"

    def test_list_backends_health(self):
        a1 = _MockAdapter("mock/healthy", healthy=True)
        a2 = _MockAdapter("mock/sick", healthy=False)
        mgr = AdapterManager([a1, a2])
        result = mgr.list_backends()
        assert result[0] == {"name": "mock/healthy", "healthy": True}
        assert result[1] == {"name": "mock/sick", "healthy": False}

    def test_complete_via_manager(self):
        adapter = _MockAdapter()
        mgr = AdapterManager([adapter])
        healthy = mgr.get_healthy()
        resp = healthy.complete("sys", "user")
        assert resp.text == "mock response"


# ─── SkillLoader ────────────────────────────────────────────────


class TestSkillLoader:
    def test_load_skill_with_frontmatter(self, tmp_path):
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            textwrap.dedent("""\
            ---
            name: protocol-architect
            description: Protocol design and research
            model: opus
            argument-hint: Describe your protocol question
            ---

            # Protocol Architect

            You design protocols.
        """)
        )

        loader = SkillLoader()
        skill = loader.load(skill_dir)

        assert skill.name == "protocol-architect"
        assert skill.description == "Protocol design and research"
        assert skill.model_hint == "opus"
        assert skill.argument_hint == "Describe your protocol question"
        assert "You design protocols." in skill.system_prompt

    def test_load_skill_no_frontmatter(self, tmp_path):
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text("# Simple Skill\n\nJust instructions.")

        loader = SkillLoader()
        skill = loader.load(skill_file)

        assert skill.name == tmp_path.name  # directory name as fallback
        assert skill.model_hint == "sonnet"  # default
        assert "Simple Skill" in skill.system_prompt

    def test_load_skill_file_not_found(self, tmp_path):
        loader = SkillLoader()
        with pytest.raises(FileNotFoundError):
            loader.load(tmp_path / "nonexistent")

    def test_load_from_directory(self, tmp_path):
        (tmp_path / "SKILL.md").write_text("---\nname: test\n---\nBody.")
        loader = SkillLoader()
        skill = loader.load(tmp_path)
        assert skill.name == "test"

    def test_to_system_prompt_basic(self):
        skill = SkillContext(
            name="test",
            description="A test skill",
            model_hint="sonnet",
            argument_hint="",
            system_prompt="Do the thing.",
            source_path="/tmp/test",
            license="",
            compatibility="",
        )
        loader = SkillLoader()
        prompt = loader.to_system_prompt(skill)

        assert "# Role: test" in prompt
        assert "A test skill" in prompt
        assert "Do the thing." in prompt

    def test_to_system_prompt_with_context(self):
        skill = SkillContext(
            name="test",
            description="desc",
            model_hint="sonnet",
            argument_hint="",
            system_prompt="Instructions.",
            source_path="/tmp/test",
            license="",
            compatibility="",
        )
        loader = SkillLoader()
        prompt = loader.to_system_prompt(skill, context={"clan_id": "momoshod", "version": "0.4.2"})

        assert "## Context" in prompt
        assert "clan_id: momoshod" in prompt
        assert "version: 0.4.2" in prompt

    def test_frontmatter_multiline_value(self, tmp_path):
        (tmp_path / "SKILL.md").write_text(
            textwrap.dedent("""\
            ---
            name: multi
            description: >
              A skill that
              spans multiple lines
            model: haiku
            ---

            Body here.
        """)
        )

        loader = SkillLoader()
        skill = loader.load(tmp_path)
        assert skill.name == "multi"
        assert "spans multiple lines" in skill.description
        assert skill.model_hint == "haiku"

    def test_frontmatter_quoted_values(self, tmp_path):
        (tmp_path / "SKILL.md").write_text(
            textwrap.dedent("""\
            ---
            name: "quoted-name"
            description: 'single quoted'
            ---

            Content.
        """)
        )

        loader = SkillLoader()
        skill = loader.load(tmp_path)
        assert skill.name == "quoted-name"
        assert skill.description == "single quoted"

    def test_agent_skills_standard_fields(self, tmp_path):
        """Agent Skills Open Standard fields (license, compatibility) are parsed."""
        (tmp_path / "SKILL.md").write_text(
            textwrap.dedent("""\
            ---
            name: portable-skill
            description: A cross-platform skill
            license: MIT
            compatibility: Python 3.11+, HERMES v0.4+
            ---

            Portable instructions.
        """)
        )
        loader = SkillLoader()
        skill = loader.load(tmp_path)
        assert skill.name == "portable-skill"
        assert skill.license == "MIT"
        assert skill.compatibility == "Python 3.11+, HERMES v0.4+"

    def test_agent_skills_standard_fields_default_empty(self, tmp_path):
        """license and compatibility default to empty string when not specified."""
        (tmp_path / "SKILL.md").write_text("---\nname: basic\n---\nBody.")
        loader = SkillLoader()
        skill = loader.load(tmp_path)
        assert skill.license == ""
        assert skill.compatibility == ""


# ─── Config LLM fields ─────────────────────────────────────────


class TestConfigLLM:
    def test_gateway_config_defaults(self):
        config = GatewayConfig(clan_id="test", display_name="Test")
        assert config.llm_backends == []
        assert config.llm_default_backend == ""

    def test_llm_backend_config(self):
        b = LLMBackendConfig(
            backend="gemini", model="gemini-2.5-flash", api_key_env="GEMINI_API_KEY"
        )
        assert b.backend == "gemini"
        assert b.enabled is True

    def test_save_load_json_with_llm(self, tmp_path):
        config = GatewayConfig(
            clan_id="test-llm",
            display_name="Test LLM",
            llm_backends=[
                LLMBackendConfig(
                    backend="gemini", model="gemini-2.5-flash", api_key_env="GEMINI_API_KEY"
                ),
                LLMBackendConfig(
                    backend="claude", model="claude-sonnet-4-6", api_key_env="ANTHROPIC_API_KEY"
                ),
            ],
            llm_default_backend="gemini",
        )

        json_path = tmp_path / "gateway.json"
        save_config(config, json_path)
        loaded = load_config(json_path)

        assert len(loaded.llm_backends) == 2
        assert loaded.llm_backends[0].backend == "gemini"
        assert loaded.llm_backends[0].model == "gemini-2.5-flash"
        assert loaded.llm_backends[1].backend == "claude"
        assert loaded.llm_default_backend == "gemini"

    def test_save_load_toml_with_llm(self, tmp_path):
        config = GatewayConfig(
            clan_id="test-llm",
            display_name="Test LLM",
            llm_backends=[
                LLMBackendConfig(
                    backend="gemini", model="gemini-2.5-flash", api_key_env="GEMINI_KEY"
                ),
            ],
            llm_default_backend="gemini",
        )

        toml_path = tmp_path / "config.toml"
        save_config(config, toml_path)
        loaded = load_config(toml_path)

        assert len(loaded.llm_backends) == 1
        assert loaded.llm_backends[0].backend == "gemini"
        assert loaded.llm_default_backend == "gemini"

    def test_load_json_without_llm(self, tmp_path):
        """Backward compatibility: config without LLM section loads fine."""
        config = GatewayConfig(clan_id="old", display_name="Old Config")
        json_path = tmp_path / "gateway.json"
        save_config(config, json_path)
        loaded = load_config(json_path)

        assert loaded.llm_backends == []
        assert loaded.llm_default_backend == ""

    def test_disabled_backend(self):
        b = LLMBackendConfig(backend="claude", enabled=False)
        assert b.enabled is False


# ─── CLI ────────────────────────────────────────────────────────


class TestLLMCLI:
    def test_llm_list_no_backends(self, tmp_path, capsys):
        from hermes.cli import main

        config = GatewayConfig(clan_id="test", display_name="Test")
        save_config(config, tmp_path / "gateway.json")

        result = main(["llm", "list", "--dir", str(tmp_path)])
        assert result == 0
        captured = capsys.readouterr()
        assert "No LLM backends configured" in captured.out

    def test_llm_list_with_backends(self, tmp_path, capsys):
        from hermes.cli import main

        config = GatewayConfig(
            clan_id="test",
            display_name="Test",
            llm_backends=[
                LLMBackendConfig(
                    backend="gemini", model="gemini-2.5-flash", api_key_env="GEMINI_KEY"
                ),
            ],
            llm_default_backend="gemini",
        )
        save_config(config, tmp_path / "gateway.json")

        result = main(["llm", "list", "--dir", str(tmp_path)])
        assert result == 0
        captured = capsys.readouterr()
        assert "gemini" in captured.out
        assert "enabled" in captured.out
