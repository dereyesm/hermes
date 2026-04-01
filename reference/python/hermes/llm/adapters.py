"""LLM Adapters — Multi-backend abstraction layer.

Each adapter wraps a different LLM provider API behind a common interface.
The system doesn't care which LLM answers — it cares that the answer follows
the skill's instructions.

API keys are resolved from environment variables (never stored in config files).
SDKs are imported lazily so the core protocol works without them installed.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .telemetry import TokenTracker


@dataclass
class LLMResponse:
    """Standardized response from any LLM backend."""

    text: str
    backend: str
    model: str
    usage: dict[str, int] | None = None


class LLMAdapter(ABC):
    """Abstract interface for LLM backends."""

    @abstractmethod
    def complete(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
    ) -> LLMResponse: ...

    @abstractmethod
    def name(self) -> str: ...

    def health_check(self) -> bool:
        """Quick check if the backend is reachable."""
        try:
            resp = self.complete(
                "You are a health check bot. Respond with exactly: pong",
                "ping",
                max_tokens=50,
            )
            return bool(resp.text)
        except Exception:
            return False


class GeminiAdapter(LLMAdapter):
    """Google Gemini API adapter (google-genai SDK).

    Requires: pip install google-genai>=1.0.0
    Env var: GEMINI_API_KEY (or pass api_key_env to override)
    """

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        api_key: str | None = None,
        api_key_env: str = "GEMINI_API_KEY",
    ):
        key = api_key or os.environ.get(api_key_env, "")
        if not key:
            raise ValueError(f"Gemini API key not found. Set {api_key_env} environment variable.")

        try:
            from google import genai
        except ImportError as exc:
            raise ImportError(
                "google-genai SDK not installed. Run: pip install 'hermes-protocol[llm]'"
            ) from exc

        self._client = genai.Client(api_key=key)
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
    """Anthropic Claude API adapter.

    Requires: pip install anthropic>=0.42.0
    Env var: ANTHROPIC_API_KEY (or pass api_key_env to override)
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        api_key: str | None = None,
        api_key_env: str = "ANTHROPIC_API_KEY",
    ):
        key = api_key or os.environ.get(api_key_env, "")
        if not key:
            raise ValueError(
                f"Anthropic API key not found. Set {api_key_env} environment variable."
            )

        try:
            import anthropic
        except ImportError as exc:
            raise ImportError(
                "anthropic SDK not installed. Run: pip install 'hermes-protocol[llm]'"
            ) from exc

        self._client = anthropic.Anthropic(api_key=key)
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
    """Manages LLM backends with priority-ordered fallback.

    Optionally integrates with :class:`~hermes.llm.telemetry.TokenTracker`
    to automatically record token usage from every LLM call.
    """

    def __init__(self, adapters: list[LLMAdapter] | None = None):
        self._adapters: list[LLMAdapter] = adapters or []
        self.tracker: TokenTracker | None = None

    def enable_telemetry(self, tracker: TokenTracker) -> None:
        """Attach a token tracker to auto-record usage on ``complete()``."""
        self.tracker = tracker

    def complete(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
        backend: str | None = None,
    ) -> LLMResponse:
        """Run a completion on the first healthy adapter and track usage.

        Args:
            system_prompt: System prompt text.
            user_message: User message text.
            max_tokens: Maximum tokens to generate.
            backend: Optional backend name prefix to target (e.g. "gemini").

        Raises:
            RuntimeError: If no healthy adapter is available.
        """
        adapter: LLMAdapter | None = None
        if backend:
            adapter = self.get_by_name(backend)
        if adapter is None:
            adapter = self.get_healthy()
        if adapter is None:
            raise RuntimeError("No healthy LLM adapter available")

        response = adapter.complete(system_prompt, user_message, max_tokens)

        if self.tracker and response.usage:
            self.tracker.record(response)

        return response

    def add(self, adapter: LLMAdapter) -> None:
        self._adapters.append(adapter)

    @property
    def backends(self) -> list[LLMAdapter]:
        return list(self._adapters)

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
        return [{"name": a.name(), "healthy": a.health_check()} for a in self._adapters]


def create_adapter(backend: str, **kwargs: Any) -> LLMAdapter:
    """Factory function to create an adapter by backend name.

    Args:
        backend: "gemini" or "claude"
        **kwargs: Passed to the adapter constructor (model, api_key, api_key_env)

    Returns:
        Configured LLMAdapter instance.

    Raises:
        ValueError: If backend name is not recognized.
    """
    adapters: dict[str, type[LLMAdapter]] = {
        "gemini": GeminiAdapter,
        "claude": ClaudeAdapter,
    }
    cls = adapters.get(backend)
    if cls is None:
        raise ValueError(f"Unknown LLM backend: '{backend}'. Available: {list(adapters.keys())}")
    return cls(**kwargs)
