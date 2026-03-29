"""HERMES LLM — Multi-backend adapter layer.

Provides a unified interface for LLM backends (Claude, Gemini, etc.)
so that HERMES skills can execute on any provider.

The adapters are optional — core HERMES works without any LLM SDK installed.
"""

from __future__ import annotations

from .adapters import (
    AdapterManager,
    ClaudeAdapter,
    GeminiAdapter,
    LLMAdapter,
    LLMResponse,
    create_adapter,
)
from .skill import SkillContext, SkillLoader

__all__ = [
    "AdapterManager",
    "ClaudeAdapter",
    "GeminiAdapter",
    "LLMAdapter",
    "LLMResponse",
    "SkillContext",
    "SkillLoader",
    "create_adapter",
]
