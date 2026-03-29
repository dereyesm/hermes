"""LLM Adapters — Multi-backend abstraction layer.

Each adapter wraps a different LLM provider API behind a common interface.
The system doesn't care which LLM answers — it cares that the answer follows
the skill's instructions.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    """Standardized response from any LLM backend."""

    text: str
    backend: str
    model: str
    usage: dict | None = None  # tokens in/out if available


class LLMAdapter(ABC):
    """Abstract interface for LLM backends."""

    @abstractmethod
    def complete(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        ...

    @abstractmethod
    def name(self) -> str:
        ...

    def health_check(self) -> bool:
        """Quick check if the backend is reachable."""
        try:
            resp = self.complete(
                "You are a health check bot. Always respond with the word pong.",
                "ping",
                max_tokens=50,
            )
            return resp.text is not None and len(resp.text) > 0
        except Exception:
            return False


class GeminiAdapter(LLMAdapter):
    """Google Gemini API adapter (google-genai SDK)."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._model_name = model

    def complete(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        from google.genai import types

        response = self._client.models.generate_content(
            model=self._model_name,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=max_tokens,
            ),
        )

        usage = None
        if response.usage_metadata:
            usage = {
                "input_tokens": response.usage_metadata.prompt_token_count or 0,
                "output_tokens": response.usage_metadata.candidates_token_count or 0,
            }

        return LLMResponse(
            text=response.text,
            backend="gemini",
            model=self._model_name,
            usage=usage,
        )

    def name(self) -> str:
        return f"gemini/{self._model_name}"


class ClaudeAdapter(LLMAdapter):
    """Anthropic Claude API adapter."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def complete(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        response = self._client.messages.create(
            model=self._model,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=max_tokens,
        )

        return LLMResponse(
            text=response.content[0].text,
            backend="claude",
            model=self._model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        )

    def name(self) -> str:
        return f"claude/{self._model}"


class AdapterManager:
    """Manages LLM backends with automatic fallback."""

    def __init__(self, adapters: list[LLMAdapter] | None = None):
        self._adapters: list[LLMAdapter] = adapters or []

    def add(self, adapter: LLMAdapter) -> None:
        self._adapters.append(adapter)

    def get_healthy(self) -> LLMAdapter | None:
        """Return first healthy adapter in priority order."""
        for adapter in self._adapters:
            if adapter.health_check():
                return adapter
        return None

    def get_by_name(self, prefix: str) -> LLMAdapter | None:
        """Get adapter by name prefix (e.g. 'gemini', 'claude')."""
        for adapter in self._adapters:
            if adapter.name().startswith(prefix):
                return adapter
        return None

    def list_backends(self) -> list[dict[str, Any]]:
        """List all configured backends with health status."""
        return [
            {"name": a.name(), "healthy": a.health_check()}
            for a in self._adapters
        ]
