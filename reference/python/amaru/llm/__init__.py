"""Amaru LLM — Multi-backend adapter layer.

Provides a unified interface for LLM backends (Claude, Gemini, etc.)
so that Amaru skills can execute on any provider.

The adapters are optional — core Amaru works without any LLM SDK installed.
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
from .telemetry import (
    COST_PER_MTOK,
    BackendUsage,
    TokenEvent,
    TokenSummary,
    TokenTracker,
    estimate_cost,
)

__all__ = [
    "COST_PER_MTOK",
    "AdapterManager",
    "BackendUsage",
    "ClaudeAdapter",
    "GeminiAdapter",
    "LLMAdapter",
    "LLMResponse",
    "SkillContext",
    "SkillLoader",
    "TokenEvent",
    "TokenSummary",
    "TokenTracker",
    "create_adapter",
    "estimate_cost",
]
